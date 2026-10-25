import asyncio
import json
import os
import time

import numpy as np
import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from sapo.server import Hub, make_handler
from sapo.voice import models
from sapo.voice.client import Listener, Speaker, chat, listening, session
from sapo.voice.engine import RATE, WakeMatcher, normalize, resample, shift
from sapo.voice.g2p import number, phonemize

HAVE_MODELS = all((models.model_path(k) / m.marker).exists() for k, m in models.MODELS.items())
needs_models = pytest.mark.skipif(
    not HAVE_MODELS and not os.environ.get("SAPO_VOICE_DOWNLOAD"),
    reason="faltan modelos de voz: uv run sapo-voice --descargar",
)


def test_normalize():
    assert normalize("¡Oye, Sapo! ¿Qué hora es?") == "oye sapo que hora es"


@pytest.mark.parametrize(
    "text,rest",
    [
        ("Oye, sapo, qué hora es.", "qué hora es"),
        ("oye sapo", ""),
        ("Hoy sapo, apaga la luz", "apaga la luz"),
        ("oyesapo cuéntame un chiste", "cuéntame un chiste"),
    ],
)
def test_wake_matches(text, rest):
    hit = WakeMatcher().match(text)
    assert hit.found
    assert hit.rest == rest


@pytest.mark.parametrize("text", ["qué hora es", "el perro come pan", "vamos a jugar", ""])
def test_wake_ignores(text):
    assert not WakeMatcher().match(text).found


def test_wake_configurable():
    assert WakeMatcher("hola rana").match("hola rana baila").rest == "baila"
    assert not WakeMatcher("hola rana").match("oye sapo baila").found


def test_g2p():
    assert "".join(phonemize("oye sapo, ¿qué hora es?")[0]) == "ˈoʝe sˈapo, kˈe ˈoɾa ˈes?"
    assert "".join(phonemize("guerra")[0]) == "gˈera"
    assert "".join(phonemize("chiste")[0]) == "ʧˈiste"
    assert len(phonemize("Hola. ¡Adiós!")) == 2
    assert phonemize("🐸 ...") == []


def test_numbers():
    assert number(21) == "veintiuno"
    assert number(45) == "cuarenta y cinco"
    assert number(100) == "cien"
    assert number(1999) == "mil novecientos noventa y nueve"
    assert "".join(phonemize("las 3:45")[0]) == "las tɾˈes i kwaɾˈenta i sˈinko"


def test_shift_and_resample():
    tone = np.sin(np.arange(24000) / 24000 * 2 * np.pi * 200).astype(np.float32)
    assert abs(len(shift(tone, 2.0)) - 12000) <= 1
    assert abs(len(resample(tone, 24000)) - RATE) <= 1


class FakeVad:
    def __init__(self):
        self.segments = []

    def feed(self, samples):
        out, self.segments = self.segments, []
        return out

    def flush(self):
        return []

    def speaking(self):
        return False

    def reset(self):
        pass


class FakeStt:
    def __init__(self, texts):
        self.texts = list(texts)

    def transcribe(self, samples):
        return self.texts.pop(0)


def test_listener_one_breath():
    vad = FakeVad()
    lis = Listener(vad, FakeStt(["Oye sapo, qué hora es"]), WakeMatcher())
    vad.segments = [np.zeros(10)]
    assert lis.feed(np.zeros(10)) == [listening(True), chat("qué hora es"), listening(False)]


def test_listener_two_steps_and_timeout():
    now = [0.0]
    vad = FakeVad()
    lis = Listener(vad, FakeStt(["oye sapo", "baila", "oye sapo"]), WakeMatcher(), timeout=5, clock=lambda: now[0])
    vad.segments = [np.zeros(10)]
    assert lis.feed(np.zeros(10)) == [listening(True)]
    vad.segments = [np.zeros(10)]
    assert lis.feed(np.zeros(10)) == [chat("baila"), listening(False)]
    vad.segments = [np.zeros(10)]
    assert lis.feed(np.zeros(10)) == [listening(True)]
    now[0] = 6
    assert lis.feed(np.zeros(10)) == [listening(False)]
    assert not lis.armed


def test_listener_ignores_chatter():
    vad = FakeVad()
    lis = Listener(vad, FakeStt(["la tele está hablando"]), WakeMatcher())
    vad.segments = [np.zeros(10)]
    assert lis.feed(np.zeros(10)) == []


class FakeBrain:
    def __init__(self):
        self.got = []

    async def handle(self, msg):
        self.got.append(msg)


async def test_server_relays_listening():
    brain = FakeBrain()
    hub = Hub()
    async with serve(make_handler(brain, hub), "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}") as voice, connect(f"ws://127.0.0.1:{port}") as frog:
            while len(hub.clients) < 2:
                await asyncio.sleep(0.01)
            await voice.send(json.dumps({"type": "listening", "on": True}))
            assert json.loads(await asyncio.wait_for(frog.recv(), 2)) == {"type": "listening", "on": True}
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(voice.recv(), 0.3)
            await voice.send(json.dumps({"type": "chat", "text": "hola", "source": "voice"}))
            for _ in range(100):
                if brain.got:
                    break
                await asyncio.sleep(0.01)
    assert brain.got == [{"type": "chat", "text": "hola"}]


@pytest.fixture(scope="module")
def engines():
    from sapo.voice.engine import Stt, Tts, Vad

    start = time.perf_counter()
    tts, stt = Tts(pitch=0.0), Stt()
    load = time.perf_counter() - start
    return tts, stt, Vad, load


def utterance(tts, text, noise=0.003, seed=0):
    samples, rate = tts.synth(text)
    audio = resample(samples, rate)
    gap = np.zeros(int(RATE * 1.2), dtype=np.float32)
    rng = np.random.default_rng(seed)
    full = np.concatenate([gap[: RATE // 2], audio, gap])
    return (full + rng.normal(0, noise, len(full))).astype(np.float32)


def chunks(audio, size=RATE // 10):
    for i in range(0, len(audio), size):
        yield audio[i : i + size]


@needs_models
def test_tts_stt_round_trip(engines):
    tts, stt, _, load = engines
    start = time.perf_counter()
    samples, rate = tts.synth("oye sapo, ¿qué hora es?")
    t_tts = time.perf_counter() - start
    audio = resample(samples, rate)
    start = time.perf_counter()
    text = stt.transcribe(audio)
    t_stt = time.perf_counter() - start
    print(f"\ncarga {load:.2f}s | tts {t_tts * 1000:.0f} ms para {len(samples) / rate:.2f}s | stt {t_stt * 1000:.0f} ms | {text!r}")
    assert normalize(text) == "oye sapo que hora es"
    hit = WakeMatcher().match(text)
    assert hit.found and normalize(hit.rest) == "que hora es"


@needs_models
def test_pipeline_one_breath(engines):
    tts, stt, Vad, _ = engines
    lis = Listener(Vad(), stt, WakeMatcher())
    audio = utterance(tts, "oye sapo, ¿qué hora es?")
    msgs = []
    for chunk in chunks(audio):
        msgs.extend(lis.feed(chunk))
    assert [m["type"] for m in msgs] == ["listening", "chat", "listening"]
    assert normalize(msgs[1]["text"]) == "que hora es"
    assert msgs[1]["source"] == "voice"


@needs_models
def test_pipeline_two_steps(engines):
    tts, stt, Vad, _ = engines
    lis = Listener(Vad(), stt, WakeMatcher())
    audio = np.concatenate([utterance(tts, "oye sapo", seed=1), utterance(tts, "cuéntame un chiste de ranas", seed=2)])
    msgs = []
    for chunk in chunks(audio):
        msgs.extend(lis.feed(chunk))
    assert msgs[0] == listening(True)
    assert msgs[1]["type"] == "chat" and "chiste" in normalize(msgs[1]["text"])
    assert msgs[2] == listening(False)


@needs_models
def test_pipeline_ignores_other_speech(engines):
    tts, stt, Vad, _ = engines
    lis = Listener(Vad(), stt, WakeMatcher())
    msgs = []
    for chunk in chunks(utterance(tts, "hoy vamos a comer tacos con mi familia")):
        msgs.extend(lis.feed(chunk))
    assert msgs == []


class FakeMic:
    def __init__(self):
        import queue
        import threading

        self.queue = queue.Queue()
        self.muted = threading.Event()
        self.muted_while_playing = []

    def drain(self):
        while not self.queue.empty():
            self.queue.get_nowait()


class SilentSpeaker(Speaker):
    def __init__(self, tts, mic):
        super().__init__(tts)
        self.mic = mic
        self.played = []

    def play(self, samples):
        self.mic.muted_while_playing.append(self.mic.muted.is_set())
        self.played.append(len(samples))


@needs_models
async def test_voice_client_end_to_end(engines):
    tts, stt, Vad, _ = engines
    received = []
    replied = asyncio.Event()

    async def fake_brain(ws):
        async for raw in ws:
            msg = json.loads(raw)
            received.append((time.perf_counter(), msg))
            if msg["type"] == "chat":
                await ws.send(json.dumps({"type": "say", "text": "Son las tres, croac.", "mood": "happy"}))
                replied.set()

    mic = FakeMic()
    speaker = SilentSpeaker(tts, mic)
    lis = Listener(Vad(), stt, WakeMatcher())
    audio = utterance(tts, "oye sapo, ¿qué hora es?")
    async with serve(fake_brain, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}") as ws:
            loop = asyncio.get_running_loop()
            task = asyncio.create_task(session(ws, loop, mic, lis, speaker))
            for chunk in chunks(audio):
                mic.queue.put(chunk)
            end_of_speech = time.perf_counter()
            await asyncio.wait_for(replied.wait(), 30)
            for _ in range(300):
                if speaker.played and not mic.muted.is_set():
                    break
                await asyncio.sleep(0.05)
            task.cancel()
    kinds = [m["type"] for _, m in received]
    assert kinds[:3] == ["listening", "chat", "listening"]
    assert normalize(received[1][1]["text"]) == "que hora es"
    assert speaker.played and all(speaker.mic.muted_while_playing)
    assert not mic.muted.is_set()
    print(f"\nchat enviado {received[1][0] - end_of_speech:.2f}s tras encolar el audio | tts primer audio {speaker.last_first_audio * 1000:.0f} ms")
