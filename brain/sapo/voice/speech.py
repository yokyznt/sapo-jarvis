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
STYLE = "Dilo en español mexicano, como un sapito simpático y juguetón, natural y sin exagerar: "


class TtsError(Exception):
    pass


class GeminiTts:
    def __init__(self, key: Callable[[], str | None], model: str, voice: str, client: httpx.Client | None = None, base: str = BASE, timeout: float = 20.0) -> None:
        self.key = key
        self.model = model
        self.voice = voice
        self.base = base
        self.http = client or httpx.Client(timeout=timeout)
        self.down_until = 0.0
        self.fails = 0

    def available(self) -> bool:
        return bool(self.key()) and time.monotonic() >= self.down_until

    def fail(self) -> None:
        self.fails += 1
        self.down_until = time.monotonic() + min(900.0, 30.0 * 2 ** (self.fails - 1))

    def synth(self, text: str) -> tuple[np.ndarray, int]:
        key = self.key()
        if not key:
            raise TtsError("sin key")
        body = {
            "contents": [{"parts": [{"text": STYLE + text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self.voice}}},
            },
        }
        try:
            r = self.http.post(f"{self.base}/models/{self.model}:generateContent", json=body, headers={"x-goog-api-key": key})
        except httpx.HTTPError as e:
            self.fail()
            raise TtsError(f"red: {type(e).__name__}") from None
        if r.status_code != 200:
            self.fail()
            raise TtsError(f"http {r.status_code}")
        try:
            part = next(p for p in r.json()["candidates"][0]["content"]["parts"] if "inlineData" in p)
            data = part["inlineData"]
            pcm = base64.b64decode(data["data"])
            rate = rate_of(data.get("mimeType", ""))
        except (KeyError, IndexError, StopIteration, ValueError, TypeError):
            self.fail()
            raise TtsError("respuesta sin audio") from None
        self.fails = 0
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        if samples.size == 0:
            raise TtsError("audio vacío")
        return samples, rate


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
        h = hashlib.sha256(f"{engine}|{voice}|{text.strip().lower()}".encode()).hexdigest()[:32]
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
    def __init__(self, local, gemini: GeminiTts | None, cache: TtsCache | None, engine: Callable[[], str]) -> None:
        self.local = local
        self.gemini = gemini
        self.cache = cache
        self.engine = engine
        self.last_engine = "local"

    def synth(self, text: str) -> tuple[np.ndarray, int]:
        if self.engine() == "gemini" and self.gemini is not None and self.gemini.available():
            hit = self.cache.get("gemini", self.gemini.voice, text) if self.cache else None
            if hit is not None:
                self.last_engine = "gemini-cache"
                return hit
            try:
                samples, rate = self.gemini.synth(text)
                if self.cache:
                    self.cache.put("gemini", self.gemini.voice, text, samples, rate)
                self.last_engine = "gemini"
                return samples, rate
            except TtsError as e:
                log.info("gemini tts falló (%s), uso voz local", e)
        self.last_engine = "local"
        return self.local.synth(text)
