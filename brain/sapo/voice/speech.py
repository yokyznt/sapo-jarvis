import base64
import hashlib
import io
import logging
import time
import wave
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import numpy as np

from ..config import home_dir

log = logging.getLogger("sapo.voice")

BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_RATE = 24000
FPS = 30


class TtsError(Exception):
    pass


FALLBACK_TTS = ("gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts", "gemini-3.8-flash-lite-tts")


class GeminiTts:
    def __init__(
        self,
        key: Callable[[], str | None],
        model: str,
        voice: str,
        client: httpx.Client | None = None,
        base: str = BASE,
        timeout: float = 20.0,
        fallbacks: tuple[str, ...] = FALLBACK_TTS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.key = key
        self.model = model
        self.voice = voice
        self.base = base
        self.http = client or httpx.Client(timeout=timeout)
        self.fallbacks = tuple(fallbacks)
        self.clock = clock
        self.down_until = 0.0
        self.fails = 0
        self.model_down: dict[str, float] = {}
        self.model_fails: dict[str, int] = {}
        self.used = model

    def chain(self) -> list[str]:
        return list(dict.fromkeys(m for m in (self.model, *self.fallbacks) if m))

    def ready(self) -> list[str]:
        now = self.clock()
        return [m for m in self.chain() if self.model_down.get(m, 0.0) <= now]

    def available(self) -> bool:
        return bool(self.key()) and self.clock() >= self.down_until and bool(self.ready())

    def next_ready(self) -> float:
        now = self.clock()
        times = [max(self.down_until, self.model_down.get(m, 0.0)) for m in self.chain()]
        return max(0.0, min(times) - now) if times else 0.0

    def fail(self) -> None:
        self.fails += 1
        self.down_until = self.clock() + min(900.0, 30.0 * 2 ** (self.fails - 1))

    def rest(self, model: str, base: float) -> None:
        n = self.model_fails.get(model, 0) + 1
        self.model_fails[model] = n
        self.model_down[model] = self.clock() + min(900.0, base * 2 ** (n - 1))

    def synth(self, text: str) -> tuple[np.ndarray, int]:
        key = self.key()
        if not key:
            raise TtsError("sin key")
        if self.clock() < self.down_until:
            raise TtsError("sin red")
        models = self.ready()
        if not models:
            raise TtsError("todos los modelos de voz descansando")
        last = "sin modelos"
        for model in models:
            try:
                out = self.call(model, text, key)
            except TtsError as e:
                last = str(e)
                if last.startswith("red") or last == "key rechazada":
                    raise
                continue
            self.used = model
            return out
        raise TtsError(last)

    def call(self, model: str, text: str, key: str) -> tuple[np.ndarray, int]:
        body = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self.voice}}},
            },
        }
        try:
            r = self.http.post(f"{self.base}/models/{model}:generateContent", json=body, headers={"x-goog-api-key": key})
        except httpx.HTTPError as e:
            self.fail()
            raise TtsError(f"red: {type(e).__name__}") from None
        if r.status_code in (401, 403):
            self.fail()
            raise TtsError("key rechazada")
        if r.status_code != 200:
            self.rest(model, 60.0 if r.status_code in (429, 500, 502, 503, 504) else 900.0)
            raise TtsError(f"http {r.status_code}")
        try:
            part = next(p for p in r.json()["candidates"][0]["content"]["parts"] if "inlineData" in p)
            data = part["inlineData"]
            pcm, rate = decode_audio(base64.b64decode(data["data"]), data.get("mimeType", ""))
        except (KeyError, IndexError, StopIteration, ValueError, TypeError):
            self.rest(model, 60.0)
            raise TtsError("respuesta sin audio") from None
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        if samples.size == 0:
            self.rest(model, 60.0)
            raise TtsError("audio vacío")
        self.fails = 0
        self.model_fails.pop(model, None)
        self.model_down.pop(model, None)
        return samples, rate


LIVE_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
LIVE_READER = (
    "Eres un lector de voz. Lee en voz alta, en español de México, exactamente el texto que recibas, "
    "palabra por palabra, con tono alegre y natural. No agregues, quites ni cambies nada. "
    "No respondas, no comentes, no saludes: solo léelo."
)


def words(text: str) -> list[str]:
    import re
    import unicodedata

    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9ñ]+", t)


def similar(a: str, b: str) -> float:
    from difflib import SequenceMatcher

    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    return SequenceMatcher(None, wa, wb).ratio()


class LiveTts:
    def __init__(self, key: Callable[[], str | None], model: str, voice: str, url: str = LIVE_URL, timeout: float = 25.0, connect=None, clock: Callable[[], float] = time.monotonic) -> None:
        self.key = key
        self.model = model
        self.voice = voice
        self.url = url
        self.timeout = timeout
        self.connect = connect
        self.clock = clock
        self.down_until = 0.0
        self.fails = 0

    def available(self) -> bool:
        return bool(self.key()) and self.clock() >= self.down_until

    def fail(self) -> None:
        self.fails += 1
        self.down_until = self.clock() + min(600.0, 20.0 * 2 ** (self.fails - 1))

    def open(self, key: str):
        if self.connect is not None:
            return self.connect(self.url, key)
        from websockets.sync.client import connect

        return connect(self.url, additional_headers={"x-goog-api-key": key}, max_size=None, open_timeout=10)

    def once(self, text: str, key: str) -> tuple[bytes, str]:
        import json as _json

        with self.open(key) as ws:
            ws.send(_json.dumps({"setup": {
                "model": f"models/{self.model}",
                "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self.voice}}}},
                "systemInstruction": {"parts": [{"text": LIVE_READER}]},
                "outputAudioTranscription": {},
            }}))
            first = _json.loads(ws.recv(timeout=self.timeout))
            if "setupComplete" not in first:
                raise TtsError("live sin setup")
            ws.send(_json.dumps({"realtimeInput": {"text": text}}))
            pcm = bytearray()
            said = []
            end = self.clock() + self.timeout
            while True:
                left = end - self.clock()
                if left <= 0:
                    raise TtsError("live tardó demasiado")
                msg = _json.loads(ws.recv(timeout=left))
                if msg.get("error"):
                    raise TtsError("live respondió error")
                sc = msg.get("serverContent") or {}
                for part in (sc.get("modelTurn") or {}).get("parts", []):
                    data = part.get("inlineData")
                    if data:
                        pcm += base64.b64decode(data["data"])
                if "outputTranscription" in sc:
                    said.append(sc["outputTranscription"].get("text", ""))
                if sc.get("turnComplete"):
                    return bytes(pcm), "".join(said)

    def synth(self, text: str) -> tuple[np.ndarray, int]:
        key = self.key()
        if not key:
            raise TtsError("sin key")
        last = "live sin audio"
        for _ in range(2):
            try:
                pcm, said = self.once(text, key)
            except TtsError as e:
                last = str(e)
                continue
            except Exception as e:
                self.fail()
                raise TtsError(f"live: {type(e).__name__}") from None
            if len(pcm) < 4800:
                last = "live sin audio"
                continue
            if said and similar(text, said) < 0.6:
                last = "live cambió el texto"
                continue
            self.fails = 0
            return np.frombuffer(pcm[: len(pcm) // 2 * 2], dtype="<i2").astype(np.float32) / 32768.0, 24000
        self.fail()
        raise TtsError(last)


def decode_audio(raw: bytes, mime: str) -> tuple[bytes, int]:
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        return raw[: len(raw) // 2 * 2], rate_of(mime)
    rate, pos, pcm = rate_of(mime), 12, None
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        size = int.from_bytes(raw[pos + 4:pos + 8], "little")
        body = raw[pos + 8:pos + 8 + size]
        if cid == b"fmt " and len(body) >= 8:
            rate = int.from_bytes(body[4:8], "little")
        elif cid == b"data":
            pcm = body
            break
        pos += 8 + size + (size & 1)
    if pcm is None:
        raise ValueError("wav sin data")
    return pcm[: len(pcm) // 2 * 2], rate


def rate_of(mime: str) -> int:
    for part in mime.split(";"):
        part = part.strip()
        if part.startswith("rate="):
            return int(part[5:])
    return GEMINI_RATE


class TtsCache:
    def __init__(self, root: Path | None = None, limit: int = 200 * 1024 * 1024) -> None:
        self.root = root or home_dir() / "cache" / "tts"
        self.limit = limit

    def path(self, engine: str, voice: str, text: str) -> Path:
        h = hashlib.sha256(f"v2|{engine}|{voice}|{text.strip().lower()}".encode()).hexdigest()[:32]
        return self.root / f"{h}.wav"

    def get(self, engine: str, voice: str, text: str) -> tuple[np.ndarray, int] | None:
        p = self.path(engine, voice, text)
        try:
            with wave.open(str(p), "rb") as w:
                rate = w.getframerate()
                pcm = w.readframes(w.getnframes())
            p.touch()
        except (OSError, wave.Error, EOFError):
            return None
        return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0, rate

    def put(self, engine: str, voice: str, text: str, samples: np.ndarray, rate: int) -> None:
        p = self.path(engine, voice, text)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes((np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes())
            tmp = p.with_suffix(".tmp")
            tmp.write_bytes(buf.getvalue())
            tmp.replace(p)
            self.trim()
        except OSError as e:
            log.info("no pude guardar en caché: %r", e)

    def size(self) -> int:
        return sum(f.stat().st_size for f in self.root.glob("*.wav"))

    def trim(self) -> None:
        files = sorted(self.root.glob("*.wav"), key=lambda f: f.stat().st_mtime)
        total = sum(f.stat().st_size for f in files)
        for f in files:
            if total <= self.limit:
                break
            total -= f.stat().st_size
            f.unlink(missing_ok=True)


def mouth_levels(samples: np.ndarray, rate: int, fps: int = FPS) -> Iterator[tuple[np.ndarray, float]]:
    step = max(1, rate // fps)
    blocks = [samples[i : i + step] for i in range(0, len(samples), step)]
    rms = [float(np.sqrt(np.mean(b * b))) if b.size else 0.0 for b in blocks]
    ref = max(float(np.percentile(rms, 90)) if rms else 0.0, 0.02)
    level = 0.0
    for block, r in zip(blocks, rms):
        target = min(1.0, r / ref)
        k = 0.6 if target > level else 0.3
        level += (target - level) * k
        yield block, round(level, 3)


class Voice:
    def __init__(self, local, gemini: GeminiTts | None, cache: TtsCache | None, engine: Callable[[], str], patience: float = 12.0, sleep: Callable[[float], None] = time.sleep, live: LiveTts | None = None) -> None:
        self.local = local
        self.gemini = gemini
        self.cache = cache
        self.engine = engine
        self.patience = patience
        self.sleep = sleep
        self.live = live
        self.last_engine = "local"

    def human(self) -> bool:
        return self.engine() == "gemini" and self.gemini is not None and bool(self.gemini.key())

    def synth(self, text: str) -> tuple[np.ndarray, int]:
        if not self.human():
            self.last_engine = "local"
            return self.local.synth(text)
        hit = self.cache.get("gemini", self.gemini.voice, text) if self.cache else None
        if hit is not None:
            self.last_engine = "gemini-cache"
            return hit
        waited = 0.0
        while True:
            try:
                samples, rate = self.gemini.synth(text)
                engine = "gemini"
            except TtsError as e:
                error = e
                samples = None
                if self.live is not None and self.live.available() and not str(e).startswith("red") and str(e) != "key rechazada":
                    try:
                        samples, rate = self.live.synth(text)
                        engine = "live"
                    except TtsError as le:
                        error = le
                if samples is None:
                    wait = self.gemini.next_ready()
                    if str(error).startswith("red") or str(error) == "key rechazada" or waited + max(wait, 0.5) > self.patience:
                        log.info("voz humana no disponible (%s); me callo en vez de usar voz robótica", error)
                        self.last_engine = "silencio"
                        raise TtsError(f"sin voz humana: {error}") from None
                    wait = max(wait, 0.5)
                    self.sleep(wait)
                    waited += wait
                    continue
            if self.cache:
                self.cache.put("gemini", self.gemini.voice, text, samples, rate)
            self.last_engine = engine
            return samples, rate
