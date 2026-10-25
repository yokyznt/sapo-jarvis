import difflib
import os
import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sherpa_onnx

from . import models
from .g2p import phonemize

RATE = 16000
WINDOW = 512
WAKE = "oye sapo"
PREROLL = RATE * 3 // 10


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", text).split())


@dataclass
class Wake:
    found: bool
    rest: str = ""
    score: float = 0.0


class WakeMatcher:
    def __init__(self, phrase: str = WAKE, threshold: float = 0.75) -> None:
        self.phrase = normalize(phrase)
        self.joined = self.phrase.replace(" ", "")
        self.size = len(self.phrase.split())
        self.threshold = threshold

    def score(self, window: str) -> float:
        spaced = difflib.SequenceMatcher(None, window, self.phrase).ratio()
        joined = difflib.SequenceMatcher(None, window.replace(" ", ""), self.joined).ratio()
        return max(spaced, joined)

    def match(self, text: str) -> Wake:
        raw = text.split()
        words = [normalize(w) for w in raw]
        best = Wake(False)
        for size in sorted({max(1, self.size - 1), self.size, self.size + 1}):
            for i in range(len(words) - size + 1):
                window = " ".join(w for w in words[i : i + size] if w)
                score = self.score(window)
                if score > best.score:
                    rest = " ".join(raw[i + size :]).strip(" ,.;:!¡?¿")
                    best = Wake(score >= self.threshold, rest, score)
        return best


def threads() -> int:
    return int(os.environ.get("SAPO_VOICE_THREADS", min(4, os.cpu_count() or 2)))


class Vad:
    def __init__(self, root: Path | None = None, silence: float = 0.8) -> None:
        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = str(models.ensure("vad", root) / "silero_vad.onnx")
        config.silero_vad.threshold = 0.5
        config.silero_vad.min_silence_duration = silence
        config.silero_vad.min_speech_duration = 0.25
        config.silero_vad.max_speech_duration = 15
        config.sample_rate = RATE
        config.num_threads = 1
        self.vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=30)
        self.pending = np.zeros(0, dtype=np.float32)
        self.history = np.zeros(0, dtype=np.float32)
        self.offset = 0

    def take(self) -> np.ndarray:
        seg = self.vad.front
        begin = seg.start
        body = np.array(seg.samples, dtype=np.float32)
        self.vad.pop()
        start = max(begin - PREROLL, self.offset)
        lead = self.history[start - self.offset : max(0, begin - self.offset)]
        return np.concatenate([lead, body])

    def remember(self, window: np.ndarray) -> None:
        self.history = np.concatenate([self.history, window])
        extra = len(self.history) - RATE * 20
        if extra > 0:
            self.history = self.history[extra:]
            self.offset += extra

    def feed(self, samples: np.ndarray) -> list[np.ndarray]:
        self.pending = np.concatenate([self.pending, samples.astype(np.float32)])
        out = []
        while len(self.pending) >= WINDOW:
            window = self.pending[:WINDOW]
            self.remember(window)
            self.vad.accept_waveform(window)
            self.pending = self.pending[WINDOW:]
            while not self.vad.empty():
                out.append(self.take())
        return out

    def flush(self) -> list[np.ndarray]:
        self.vad.flush()
        out = []
        while not self.vad.empty():
            out.append(self.take())
        return out

    def speaking(self) -> bool:
        return self.vad.is_speech_detected()

    def reset(self) -> None:
        self.vad.reset()
        self.pending = np.zeros(0, dtype=np.float32)
        self.history = np.zeros(0, dtype=np.float32)
        self.offset = 0


class Stt:
    def __init__(self, root: Path | None = None) -> None:
        path = models.ensure("stt", root)
        self.rec = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
            model=str(path / "model.int8.onnx"), tokens=str(path / "tokens.txt"), num_threads=threads()
        )

    def transcribe(self, samples: np.ndarray, rate: int = RATE) -> str:
        stream = self.rec.create_stream()
        stream.accept_waveform(rate, samples.astype(np.float32))
        self.rec.decode_stream(stream)
        return stream.result.text.strip()


VOICES = {"ef_dora": 28, "em_alex": 29, "em_santa": 53}


class Tts:
    def __init__(self, root: Path | None = None, voice: str = "ef_dora", pitch: float = 2.5, speed: float = 1.08) -> None:
        path = models.ensure("tts", root)
        kokoro = sherpa_onnx.OfflineTtsKokoroModelConfig(
            model=str(path / "model.onnx"), voices=str(path / "voices.bin"), tokens=str(path / "tokens.txt")
        )
        config = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(kokoro=kokoro, num_threads=threads()))
        self.tts = sherpa_onnx.OfflineTts(config)
        self.rate = self.tts.sample_rate
        self.sid = VOICES.get(voice, 28)
        self.pitch = pitch
        self.speed = speed

    def sentences(self, text: str) -> list[list[str]]:
        return phonemize(text)

    def render(self, tokens: list[str]) -> np.ndarray:
        factor = 2 ** (self.pitch / 12)
        config = sherpa_onnx.GenerationConfig()
        config.sid = self.sid
        config.speed = self.speed / factor
        config.tokens = [tokens]
        audio = self.tts.generate("", config)
        return shift(np.asarray(audio.samples, dtype=np.float32), factor)

    def stream(self, text: str) -> Iterator[np.ndarray]:
        for tokens in self.sentences(text):
            yield self.render(tokens)

    def synth(self, text: str) -> tuple[np.ndarray, int]:
        parts = list(self.stream(text))
        samples = np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)
        return samples, self.rate


def shift(samples: np.ndarray, factor: float) -> np.ndarray:
    if factor == 1.0 or len(samples) == 0:
        return samples
    positions = np.arange(0, len(samples) - 1, factor)
    return np.interp(positions, np.arange(len(samples)), samples).astype(np.float32)


def resample(samples: np.ndarray, src: int, dst: int = RATE) -> np.ndarray:
    if src == dst:
        return samples.astype(np.float32)
    positions = np.arange(0, len(samples) - 1, src / dst)
    return np.interp(positions, np.arange(len(samples)), samples).astype(np.float32)
