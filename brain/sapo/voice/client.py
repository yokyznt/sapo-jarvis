import argparse
import asyncio
import json
import logging
import os
import queue
import sys
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from typing import Any

import numpy as np
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from ..config import LiveConfig, Settings
from ..protocol import VERSION, encode, mouth, speaking
from ..vault import KeyStore
from . import models
from .engine import RATE, WAKE, Stt, Tts, Vad, WakeMatcher
from .speech import FPS, GEMINI_RATE, GeminiTts, Lips, LiveSession, LiveTts, Onset, TtsCache, TtsError, Voice, at_rate, mouth_levels

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


class Utterance:
    def __init__(self, id: str, wait: float = 20.0) -> None:
        self.id = id
        self.wait = wait
        self.parts: queue.Queue[str | None] = queue.Queue()
        self.closed = False

    def add(self, text: str) -> None:
        if not self.closed:
            self.parts.put(text)

    def end(self) -> None:
        if not self.closed:
            self.closed = True
            self.parts.put(None)

    def __iter__(self) -> Iterator[str]:
        while True:
            try:
                item = self.parts.get(timeout=self.wait)
            except queue.Empty:
                return
            if item is None:
                return
            yield item


def open_output(device: int | str | None) -> Callable[[int], Any]:
    def make(rate: int):
        import sounddevice as sd

        out = sd.OutputStream(samplerate=rate, channels=1, dtype="float32", device=device, latency="high")
        out.start()
        return out

    return make


class Speaker:
    def __init__(
        self,
        voice,
        device: int | str | None = None,
        on_mouth: Callable[[dict[str, Any]], None] | None = None,
        live: LiveSession | None = None,
        output: Callable[[int], Any] | None = None,
        poll: float = 0.02,
    ) -> None:
        self.voice = voice
        self.device = device
        self.on_mouth = on_mouth or (lambda msg: None)
        self.live = live
        self.output = output or open_output(device)
        self.poll = poll
        self.last_first_audio = 0.0
        self.last_engine = ""
        self.out = None
        self.out_rate = 0
        self.gen = 0
        self.talking = False
        self.began = 0.0

    def stream(self, rate: int):
        if self.out is not None and self.out_rate == rate and getattr(self.out, "active", True):
            return self.out
        self.close()
        self.out = self.output(rate)
        self.out_rate = rate
        return self.out

    def close(self) -> None:
        if self.out is not None:
            try:
                self.out.close()
            except Exception:
                pass
        self.out = None

    def cut(self) -> None:
        out = self.out
        if out is not None:
            try:
                out.abort()
            except Exception:
                pass
        self.close()

    def hush(self) -> None:
        self.gen += 1

    def play(self, samples: np.ndarray, rate: int) -> None:
        gen = self.gen
        out = self.stream(rate)
        for block, level in mouth_levels(smooth_edges(samples, rate), rate):
            if self.gen != gen:
                self.cut()
                return
            out.write(block.reshape(-1, 1).astype(np.float32))
            self.on_mouth(mouth(level))
        out.write(np.zeros((int(rate * 0.25), 1), dtype=np.float32))

    def say(self, text: str, gen: int | None = None) -> None:
        if gen is not None and gen != self.gen:
            return
        if self.live is not None:
            self.say_parts([text], gen)
            return
        start = time.perf_counter()
        try:
            samples, rate = self.voice.synth(text)
        except TtsError as e:
            log.info("no hablo esta vez: %s", e)
            return
        self.last_first_audio = time.perf_counter() - start
        log.info("tts %s %s %.0f ms: %r", getattr(self.voice, "last_engine", "local"), getattr(getattr(self.voice, "gemini", None), "used", ""), self.last_first_audio * 1000, text)
        self.on_mouth(speaking(True))
        try:
            self.play(samples, rate)
        finally:
            self.on_mouth(mouth(0.0))
            self.on_mouth(speaking(False))

    def stream_say(self, blocks: Iterable[np.ndarray], rate: int = GEMINI_RATE, gen: int | None = None) -> bool:
        gen = self.gen if gen is None else gen
        self.talking = False
        self.began = time.perf_counter()
        try:
            played = self.play_blocks(blocks, rate, gen)
            if played and self.gen == gen:
                self.stream(rate).write(np.zeros((int(rate * 0.25), 1), dtype=np.float32))
            return played
        finally:
            self.quiet()

    def quiet(self) -> None:
        if self.talking:
            self.on_mouth(mouth(0.0))
            self.on_mouth(speaking(False))
        self.talking = False

    def play_blocks(self, blocks: Iterable[np.ndarray], rate: int, gen: int) -> bool:
        onset, lips = Onset(), Lips()
        step = max(1, rate // FPS)
        played = False
        for block in blocks:
            audio = onset(block)
            for i in range(0, audio.size, step):
                if self.gen != gen:
                    self.cut()
                    return played
                piece = audio[i : i + step]
                if not self.talking:
                    self.talking = True
                    self.last_first_audio = time.perf_counter() - self.began
                    self.on_mouth(speaking(True))
                self.stream(rate).write(piece.reshape(-1, 1))
                self.on_mouth(mouth(lips(piece)))
                played = True
        if self.gen != gen:
            self.cut()
        return played

    def say_parts(self, parts: Iterable[str], gen: int | None = None) -> None:
        gen = self.gen if gen is None else gen
        if self.gen != gen:
            return
        human = getattr(self.voice, "human", None)
        if human is not None:
            human()
        ready: queue.Queue = queue.Queue(maxsize=1)
        threading.Thread(target=self.produce, args=(parts, ready, gen), daemon=True).start()
        self.talking = False
        self.began = time.perf_counter()
        try:
            while self.gen == gen:
                phrase = self.take(ready, gen)
                if phrase is None:
                    break
                self.play_blocks(self.drain(phrase, gen), GEMINI_RATE, gen)
            if self.talking and self.gen == gen:
                self.stream(GEMINI_RATE).write(np.zeros((int(GEMINI_RATE * 0.25), 1), dtype=np.float32))
        finally:
            self.quiet()

    def take(self, q: queue.Queue, gen: int):
        while self.gen == gen:
            try:
                return q.get(timeout=self.poll)
            except queue.Empty:
                continue
        return None

    def drain(self, q: queue.Queue, gen: int) -> Iterator[np.ndarray]:
        while True:
            block = self.take(q, gen)
            if block is None:
                return
            yield block

    def offer(self, q: queue.Queue, item, gen: int) -> bool:
        while self.gen == gen:
            try:
                q.put(item, timeout=self.poll)
                return True
            except queue.Full:
                continue
        return False

    def produce(self, parts: Iterable[str], ready: queue.Queue, gen: int) -> None:
        try:
            for text in parts:
                text = text.strip()
                if self.gen != gen:
                    return
                if not text:
                    continue
                blocks: queue.Queue = queue.Queue()
                if not self.offer(ready, blocks, gen):
                    return
                try:
                    self.fetch(text, blocks, gen)
                except Exception as e:
                    log.info("no pude preparar la frase: %r", e)
                finally:
                    blocks.put(None)
        finally:
            self.offer(ready, None, gen)

    def voice_name(self) -> str:
        name = getattr(getattr(self.voice, "gemini", None), "voice", None)
        return name or (self.live.voice if self.live is not None else "")

    def fetch(self, text: str, blocks: queue.Queue, gen: int) -> None:
        start = time.perf_counter()
        cache = getattr(self.voice, "cache", None)
        hit = cache.get("gemini", self.voice_name(), text) if cache else None
        if hit is not None:
            blocks.put(at_rate(*hit))
            self.last_engine = "cache"
            return
        if self.live is not None:
            got: list[np.ndarray] = []
            try:
                stream = self.live.speak(text)
                try:
                    for block in stream:
                        if self.gen != gen:
                            return
                        if not got:
                            log.info("live primer audio %.0f ms: %r", (time.perf_counter() - start) * 1000, text)
                        got.append(block)
                        blocks.put(block)
                finally:
                    stream.close()
            except TtsError as e:
                log.info("live no pudo (%s)", e)
                if got:
                    return
            else:
                if got:
                    self.last_engine = "live"
                    if cache and self.live.last_score >= 0.6:
                        cache.put("gemini", self.voice_name(), text, np.concatenate(got), GEMINI_RATE)
                    return
        if self.gen != gen:
            return
        human = getattr(self.voice, "human", None)
        if human is None or not human():
            self.last_engine = "silencio"
            log.info("sin voz humana, me callo: %r", text)
            return
        try:
            samples, rate = self.voice.synth(text)
        except TtsError as e:
            self.last_engine = "silencio"
            log.info("no hablo esta vez: %s", e)
            return
        self.last_engine = getattr(self.voice, "last_engine", "gemini")
        blocks.put(at_rate(samples, rate))


def smooth_edges(samples: np.ndarray, rate: int, ms: float = 12.0) -> np.ndarray:
    n = min(len(samples) // 2, int(rate * ms / 1000))
    if n <= 1:
        return samples.astype(np.float32)
    out = samples.astype(np.float32).copy()
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    out[:n] *= ramp
    out[-n:] *= ramp[::-1]
    return out


def build_voice(args: argparse.Namespace, conf: LiveConfig) -> Voice:
    v = conf.voice
    local_voice = v.voice if v.voice[:3] in ("ef_", "em_") else args.voz
    local = Tts(voice=local_voice, pitch=v.pitch, speed=v.speed)
    gemini = GeminiTts(KeyStore().get, conf.voice.tts_model, conf.voice.gemini_voice)
    live = LiveTts(KeyStore().get, conf.voice.live_model, conf.voice.gemini_voice)
    def engine() -> str:
        gemini.model = conf.voice.tts_model
        gemini.voice = conf.voice.gemini_voice
        live.model = conf.voice.live_model
        live.voice = conf.voice.gemini_voice
        return conf.voice.engine
    return Voice(local, gemini, TtsCache(), engine, live=live)


def build_live(conf: LiveConfig) -> LiveSession:
    v = conf.voice
    return LiveSession(
        KeyStore().get,
        v.live_model,
        v.gemini_voice,
        timeout=v.live_timeout,
        settings=lambda: (conf.voice.live, conf.voice.live_model, conf.voice.gemini_voice),
    )


async def run(args: argparse.Namespace) -> None:
    loop = asyncio.get_running_loop()
    print("Cargando modelos de voz...", flush=True)
    start = time.perf_counter()
    vad, stt = Vad(silence=args.silencio), Stt()
    conf = LiveConfig()
    listener = Listener(vad, stt, WakeMatcher(args.palabra), timeout=args.espera)
    live = build_live(conf)
    live.start()
    speaker = Speaker(build_voice(args, conf), args.salida, live=live)
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
    sayings: asyncio.Queue[tuple[int, str | Utterance]] = asyncio.Queue()
    talks: dict[str, Utterance] = {}
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

    def hush() -> None:
        for talk in talks.values():
            talk.end()
        talks.clear()
        while not sayings.empty():
            _, item = sayings.get_nowait()
            if isinstance(item, Utterance):
                item.end()
        speaker.hush()

    async def receive() -> None:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(msg, dict):
                continue
            kind = msg.get("type")
            if kind == "quiet":
                state["quiet"] = bool(msg.get("on"))
            elif kind == "hush":
                hush()
            elif kind == "say_start":
                hush()
                if should_speak(state, conf):
                    talk = Utterance(str(msg.get("id")))
                    talks[talk.id] = talk
                    await sayings.put((speaker.gen, talk))
            elif kind == "say_part" and isinstance(msg.get("text"), str) and msg["text"].strip():
                print(f"sapo> {msg['text']}", flush=True)
                talk = talks.get(str(msg.get("id")))
                if talk is not None:
                    talk.add(msg["text"])
            elif kind == "say_end":
                talk = talks.pop(str(msg.get("id")), None)
                if talk is not None:
                    talk.end()
            elif kind == "say" and msg.get("text"):
                print(f"sapo> {msg['text']}", flush=True)
                if should_speak(state, conf):
                    await sayings.put((speaker.gen, msg["text"]))

    async def speak() -> None:
        while True:
            gen, item = await sayings.get()
            mic.muted.set()
            was_armed = listener.armed
            try:
                if isinstance(item, Utterance):
                    await loop.run_in_executor(None, speaker.say_parts, item, gen)
                else:
                    await loop.run_in_executor(None, speaker.say, item, gen)
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
        conf = LiveConfig()
        Speaker(build_voice(args, conf), args.salida, live=build_live(conf)).say(args.decir)
        return
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass
