import argparse
import asyncio
import json
import logging
import os
import queue
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

import numpy as np
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from ..config import LiveConfig, Settings
from ..protocol import VERSION, encode, mouth, speaking
from ..vault import KeyStore
from . import models
from .engine import RATE, WAKE, Stt, Tts, Vad, WakeMatcher
from .speech import GeminiTts, TtsCache, Voice, mouth_levels

log = logging.getLogger("sapo.voice")

MIN_COMMAND = 2
REPLY_WINDOW = 60.0


def chat(text: str) -> dict[str, Any]:
    return {"type": "chat", "text": text, "source": "voice"}


def listening(on: bool) -> dict[str, Any]:
    return {"type": "listening", "on": on}


class Listener:
    def __init__(self, vad: Vad, stt: Stt, wake: WakeMatcher, timeout: float = 8.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.vad = vad
        self.stt = stt
        self.wake = wake
        self.timeout = timeout
        self.clock = clock
        self.armed_until: float | None = None
        self.last_text = ""
        self.last_stt = 0.0
        self.lock = threading.Lock()

    @property
    def armed(self) -> bool:
        return self.armed_until is not None

    def feed(self, samples: np.ndarray) -> list[dict[str, Any]]:
        with self.lock:
            out = []
            for segment in self.vad.feed(samples):
                out.extend(self.segment(segment))
            out.extend(self.tick())
            return out

    def flush(self) -> list[dict[str, Any]]:
        with self.lock:
            out = []
            for segment in self.vad.flush():
                out.extend(self.segment(segment))
            return out

    def tick(self) -> list[dict[str, Any]]:
        if self.armed_until is not None and self.clock() > self.armed_until and not self.vad.speaking():
            self.armed_until = None
            return [listening(False)]
        return []

    def reset(self) -> None:
        with self.lock:
            self.vad.reset()

    def transcribe(self, segment: np.ndarray) -> str:
        start = time.perf_counter()
        text = self.stt.transcribe(segment)
        self.last_stt = time.perf_counter() - start
        self.last_text = text
        log.info("stt %.0f ms (%.1f s de audio): %r", self.last_stt * 1000, len(segment) / RATE, text)
        return text

    def segment(self, segment: np.ndarray) -> list[dict[str, Any]]:
        text = self.transcribe(segment)
        if self.armed:
            self.armed_until = None
            hit = self.wake.match(text)
            command = hit.rest if hit.found else text
            if len(command) >= MIN_COMMAND:
                return [chat(command), listening(False)]
            return [listening(False)]
        hit = self.wake.match(text)
        if not hit.found:
            return []
        if len(hit.rest) >= MIN_COMMAND:
            return [listening(True), chat(hit.rest), listening(False)]
        self.armed_until = self.clock() + self.timeout
        return [listening(True)]


class Mic:
    def __init__(self, device: int | str | None = None, block: float = 0.1) -> None:
        import sounddevice as sd

        self.queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)
        self.muted = threading.Event()
        self.stream = sd.InputStream(
            samplerate=RATE, channels=1, dtype="float32", blocksize=int(RATE * block), device=device, callback=self.callback
        )

    def callback(self, data, frames, info, status) -> None:
        if self.muted.is_set():
            return
        try:
            self.queue.put_nowait(data[:, 0].copy())
        except queue.Full:
            pass

    def drain(self) -> None:
        while not self.queue.empty():
            self.queue.get_nowait()

    def __enter__(self) -> "Mic":
        self.stream.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stream.stop()
        self.stream.close()


class Speaker:
    def __init__(self, voice, device: int | str | None = None, on_mouth: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.voice = voice
        self.device = device
        self.on_mouth = on_mouth or (lambda msg: None)
        self.last_first_audio = 0.0

    def play(self, samples: np.ndarray, rate: int) -> None:
        import sounddevice as sd

        with sd.OutputStream(samplerate=rate, channels=1, dtype="float32", device=self.device) as out:
            for block, level in mouth_levels(samples, rate):
                out.write(block.reshape(-1, 1).astype(np.float32))
                self.on_mouth(mouth(level))

    def say(self, text: str) -> None:
        start = time.perf_counter()
        samples, rate = self.voice.synth(text)
        self.last_first_audio = time.perf_counter() - start
        log.info("tts %s %.0f ms: %r", getattr(self.voice, "last_engine", "local"), self.last_first_audio * 1000, text)
        self.on_mouth(speaking(True))
        try:
            self.play(samples, rate)
        finally:
            self.on_mouth(mouth(0.0))
            self.on_mouth(speaking(False))


def build_voice(args: argparse.Namespace, conf: LiveConfig) -> Voice:
    v = conf.voice
    local_voice = v.voice if v.voice[:3] in ("ef_", "em_") else args.voz
    local = Tts(voice=local_voice, pitch=v.pitch, speed=v.speed)
    gemini = GeminiTts(KeyStore().get, conf.voice.tts_model, conf.voice.gemini_voice)
    def engine() -> str:
        gemini.model = conf.voice.tts_model
        gemini.voice = conf.voice.gemini_voice
        return conf.voice.engine
    return Voice(local, gemini, TtsCache(), engine)


async def run(args: argparse.Namespace) -> None:
    loop = asyncio.get_running_loop()
    print("Cargando modelos de voz...", flush=True)
    start = time.perf_counter()
    vad, stt = Vad(silence=args.silencio), Stt()
    conf = LiveConfig()
    listener = Listener(vad, stt, WakeMatcher(args.palabra), timeout=args.espera)
    speaker = Speaker(build_voice(args, conf), args.salida)
    print(f"Modelos listos en {time.perf_counter() - start:.1f} s. Di '{args.palabra}'.", flush=True)
    with Mic(args.mic) as mic:
        while True:
            try:
                async with connect(args.url) as ws:
                    await ws.send(encode({"type": "hello", "version": VERSION}))
                    print(f"Conectado a {args.url}", flush=True)
                    await session(ws, loop, mic, listener, speaker, conf)
            except (OSError, ConnectionClosed) as e:
                log.info("sin conexión (%r)", e)
                print(f"Esperando al cerebro en {args.url}...", flush=True)
                await asyncio.sleep(3)


async def session(ws, loop, mic: Mic, listener: Listener, speaker: Speaker, conf: LiveConfig | None = None) -> None:
    sayings: asyncio.Queue[str] = asyncio.Queue()
    state = {"quiet": False, "asked": 0.0}

    def emit(msg: dict[str, Any]) -> None:
        asyncio.run_coroutine_threadsafe(ws.send(encode(msg)), loop)

    speaker.on_mouth = emit

    def next_chunk() -> np.ndarray | None:
        try:
            return mic.queue.get(timeout=0.5)
        except queue.Empty:
            return None

    async def hear() -> None:
        while True:
            chunk = await loop.run_in_executor(None, next_chunk)
            if mic.muted.is_set():
                continue
            msgs = listener.tick() if chunk is None else await loop.run_in_executor(None, listener.feed, chunk)
            for msg in msgs:
                if msg["type"] == "chat":
                    state["asked"] = time.monotonic()
                    print(f"tú (voz)> {msg['text']}", flush=True)
                await ws.send(encode(msg))

    async def receive() -> None:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            kind = msg.get("type")
            if kind == "quiet":
                state["quiet"] = bool(msg.get("on"))
            elif kind == "say" and msg.get("text"):
                print(f"sapo> {msg['text']}", flush=True)
                if should_speak(state, conf):
                    await sayings.put(msg["text"])

    async def speak() -> None:
        while True:
            text = await sayings.get()
            mic.muted.set()
            was_armed = listener.armed
            try:
                await loop.run_in_executor(None, speaker.say, text)
            finally:
                await asyncio.sleep(0.35)
                mic.drain()
                listener.reset()
                mic.muted.clear()
            if was_armed and not listener.armed:
                await ws.send(encode(listening(False)))

    tasks = [asyncio.create_task(c()) for c in (hear, receive, speak)]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()


def should_speak(state: dict[str, Any], conf: LiveConfig | None, now: float | None = None) -> bool:
    if conf is not None:
        conf.poll()
        if not conf.voice.enabled:
            return False
    replying = (now if now is not None else time.monotonic()) - state.get("asked", 0.0) < REPLY_WINDOW
    return replying or not state.get("quiet")


def device(value: str | None) -> int | str | None:
    if value is None:
        return None
    return int(value) if value.isdigit() else value


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")
    settings = Settings.from_env()
    env = os.environ.get
    parser = argparse.ArgumentParser(prog="sapo-voice", description="Voz del sapo: palabra clave, voz a texto y texto a voz")
    parser.add_argument("--url", default=f"ws://{settings.host}:{settings.port}")
    parser.add_argument("--palabra", default=env("SAPO_WAKE", WAKE))
    parser.add_argument("--voz", default=env("SAPO_VOICE", "ef_dora"))
    parser.add_argument("--tono", type=float, default=float(env("SAPO_VOICE_PITCH", 2.5)))
    parser.add_argument("--velocidad", type=float, default=float(env("SAPO_VOICE_SPEED", 1.08)))
    parser.add_argument("--silencio", type=float, default=0.8)
    parser.add_argument("--espera", type=float, default=8.0)
    parser.add_argument("--mic", type=device, default=device(env("SAPO_MIC")))
    parser.add_argument("--salida", type=device, default=device(env("SAPO_SPEAKER")))
    parser.add_argument("--dispositivos", action="store_true")
    parser.add_argument("--descargar", action="store_true")
    parser.add_argument("--decir")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(asctime)s %(name)s %(message)s")
    if args.dispositivos:
        import sounddevice as sd

        print(sd.query_devices())
        return
    if args.descargar:
        models.main()
        return
    if args.decir:
        Speaker(build_voice(args, LiveConfig()), args.salida).say(args.decir)
        return
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass
