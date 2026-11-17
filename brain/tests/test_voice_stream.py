import asyncio
import base64
import json
import logging
import queue
import threading
import time

import httpx
import numpy as np
import pytest
from websockets.asyncio.server import serve
from websockets.asyncio.client import connect

from sapo.voice.client import Listener, Speaker, Utterance, session
from sapo.voice.engine import WakeMatcher
from sapo.voice.speech import GeminiTts, LiveSession, Onset, TtsCache, TtsError, Voice

KEY = "FAKE-key-para-pruebas-0000"
RATE = 24000


def pcm(value, n):
    return (np.full(n, value, dtype=np.float32) * 32767).astype("<i2").tobytes()


class FakeWs:
    def __init__(self, chunks=3, size=2400, said=None, broken=False, real=True, late=False, leftover=""):
        self.chunks = chunks
        self.size = size
        self.said = said
        self.broken = broken
        self.real = real
        self.late = late
        self.leftover = leftover
        self.playing = False
        self.sent = []
        self.out = queue.Queue()
        self.closed = False

    def send(self, raw):
        if self.closed:
            raise ConnectionError("cerrado")
        msg = json.loads(raw)
        self.sent.append(msg)
        if "setup" in msg:
            self.out.put({"setupComplete": {}})
            return
        if self.broken:
            raise ConnectionError("roto")
        text = msg["realtimeInput"]["text"]
        if self.playing:
            if self.leftover:
                self.out.put({"serverContent": {"outputTranscription": {"text": self.leftover}}})
            self.out.put({"serverContent": {"interrupted": True}})
            self.out.put({"serverContent": {"turnComplete": True}})
            self.playing = False
        for i in range(self.chunks):
            data = base64.b64encode(pcm(0.1 * (i + 1), self.size)).decode()
            self.out.put({"serverContent": {"modelTurn": {"parts": [{"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": data}}]}}})
        self.out.put({"serverContent": {"outputTranscription": {"text": self.said if self.said is not None else text}}})
        if self.real:
            self.out.put({"serverContent": {"generationComplete": True}})
            if self.late:
                self.out.put({"serverContent": {"turnComplete": True}})
            else:
                self.playing = True
        else:
            self.out.put({"serverContent": {"turnComplete": True}})

    def recv(self, timeout=None):
        try:
            return json.dumps(self.out.get(timeout=timeout))
        except queue.Empty:
            raise TimeoutError from None

    def close(self):
        self.closed = True


class Dialer:
    def __init__(self, *socks):
        self.queue = list(socks)
        self.made = []

    def __call__(self, url, key):
        ws = self.queue.pop(0) if self.queue else FakeWs()
        self.made.append(ws)
        return ws


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def session_with(dialer, clock=None, **kw):
    return LiveSession(lambda: KEY, "gemini-3.8-live", "Aoede", connect=dialer, clock=clock or time.monotonic, **kw)


def test_live_session_streams_blocks_in_order_on_one_socket():
    dialer = Dialer()
    live = session_with(dialer)
    assert live.warm()
    blocks = list(live.speak("hola sapito"))
    assert [round(float(b[0]), 2) for b in blocks] == [0.1, 0.2, 0.3]
    assert all(b.dtype == np.float32 and b.size == 2400 for b in blocks)
    list(live.speak("otra frase"))
    assert live.opens == 1 and len(dialer.made) == 1
    setup = dialer.made[0].sent[0]["setup"]
    assert setup["model"] == "models/gemini-3.8-live"
    assert setup["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Aoede"
    assert [m["realtimeInput"]["text"] for m in dialer.made[0].sent[1:]] == ["hola sapito", "otra frase"]


def test_live_session_ends_turn_at_generation_complete():
    dialer = Dialer(FakeWs(leftover="en Roblox."))
    live = session_with(dialer)
    assert len(list(live.speak("Ya llevas dos horas en Roblox."))) == 3
    assert live.pending
    assert len(list(live.speak("¿No te duelen los ojos?"))) == 3
    assert live.last_said == "¿No te duelen los ojos?" and live.last_score == 1.0
    assert live.opens == 1


def test_live_session_skips_late_turn_complete_and_old_servers():
    for ws in (FakeWs(late=True), FakeWs(real=False)):
        live = session_with(Dialer(ws))
        list(live.speak("uno dos tres"))
        assert len(list(live.speak("cuatro cinco seis"))) == 3
        assert live.last_score == 1.0 and live.opens == 1


def test_live_transcript_tags_are_ignored():
    live = session_with(Dialer(FakeWs(said="🧠[es-MX]<already es>Hola sapito, ya")))
    list(live.speak("Hola sapito, ya llegué a la casa."))
    assert live.last_said.endswith("Hola sapito, ya") and live.last_score >= 0.6


def test_live_session_reopens_after_eight_minutes_and_on_changes():
    clock = Clock()
    dialer = Dialer()
    conf = {"v": (True, "gemini-3.8-live", "Aoede")}
    live = session_with(dialer, clock, settings=lambda: conf["v"])
    list(live.speak("uno"))
    clock.now = 479.0
    list(live.speak("dos"))
    assert live.opens == 1
    clock.now = 481.0
    list(live.speak("tres"))
    assert live.opens == 2 and dialer.made[0].closed
    conf["v"] = (True, "gemini-3.8-live", "Kore")
    list(live.speak("cuatro"))
    assert live.opens == 3 and dialer.made[2].sent[0]["setup"]["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Kore"
    conf["v"] = (False, "gemini-3.8-live", "Kore")
    with pytest.raises(TtsError):
        list(live.speak("cinco"))


def test_live_session_tick_reopens_in_background_when_old():
    clock = Clock()
    dialer = Dialer()
    live = session_with(dialer, clock)
    assert live.warm()
    clock.now = 500.0
    assert live.warm(wait=False)
    assert live.opens == 2 and dialer.made[0].closed and not dialer.made[1].closed


def test_live_session_reconnects_after_dead_socket():
    dialer = Dialer(FakeWs(broken=True), FakeWs())
    live = session_with(dialer)
    assert live.warm()
    blocks = list(live.speak("hola"))
    assert len(blocks) == 3 and live.opens == 2 and live.fails == 0


def test_live_session_failure_backs_off():
    def boom(url, key):
        raise ConnectionError("sin red")

    live = session_with(boom)
    with pytest.raises(TtsError):
        list(live.speak("hola"))
    assert not live.available() and not live.warm()


def test_live_session_warns_when_reading_differs(caplog):
    live = session_with(Dialer(FakeWs(said="Claro, con gusto te ayudo con lo que quieras")))
    with caplog.at_level(logging.WARNING, logger="sapo.voice"):
        blocks = list(live.speak("ya son las cinco"))
    assert blocks and live.last_score < 0.6
    assert any("leyó distinto" in r.message for r in caplog.records)


def test_live_session_abandoned_turn_drops_socket():
    dialer = Dialer()
    live = session_with(dialer)
    stream = live.speak("hola")
    next(stream)
    stream.close()
    assert dialer.made[0].closed
    assert list(live.speak("de nuevo"))
    assert dialer.made[-1] is not dialer.made[0]


class FakeOut:
    def __init__(self, pace=0.0):
        self.pace = pace
        self.writes = []
        self.active = True
        self.aborted = 0

    def __call__(self, rate):
        self.active = True
        return self

    def write(self, data):
        self.writes.append((time.perf_counter(), np.asarray(data, dtype=np.float32).ravel().copy()))
        if self.pace:
            time.sleep(len(data) / RATE * self.pace)

    def abort(self):
        self.aborted += 1
        self.active = False

    def close(self):
        self.active = False

    def audio(self):
        return np.concatenate([w for _, w in self.writes]) if self.writes else np.zeros(0, dtype=np.float32)


class FakeLive:
    def __init__(self, level=None, seconds=0.3, chunks=3, delay=0.0, fail=False):
        self.level = level or {}
        self.seconds = seconds
        self.chunks = chunks
        self.delay = delay
        self.fail = fail
        self.voice = "Aoede"
        self.last_score = 1.0
        self.calls = []

    def speak(self, text):
        self.calls.append((time.perf_counter(), text))
        if self.fail:
            raise TtsError("live caído")
        n = int(RATE * self.seconds / self.chunks)
        for _ in range(self.chunks):
            if self.delay:
                time.sleep(self.delay)
            yield np.full(n, self.level.get(text, 0.5), dtype=np.float32)


class FakeVoice:
    def __init__(self, cache=None, human=True, fail=False):
        self.cache = cache
        self.is_human = human
        self.fail = fail
        self.calls = []
        self.last_engine = "gemini"

    def human(self):
        return self.is_human

    def synth(self, text):
        self.calls.append(text)
        if self.fail:
            raise TtsError("sin voz")
        return np.full(4800, 0.4, dtype=np.float32), RATE


class FakeLocal:
    def __init__(self):
        self.calls = 0

    def synth(self, text):
        self.calls += 1
        return np.full(2400, 0.5, dtype=np.float32), RATE


def speaker_with(live, voice=None, out=None, sent=None):
    out = out or FakeOut()
    sent = sent if sent is not None else []
    return Speaker(voice or FakeVoice(), live=live, output=out, on_mouth=sent.append), out, sent


def phrases_of(out):
    seen = []
    for _, w in out.writes:
        top = round(float(np.max(np.abs(w))), 2) if w.size else 0.0
        if top > 0 and (not seen or seen[-1] != top):
            seen.append(top)
    return seen


def test_stream_plays_parts_in_order_with_mouth():
    live = FakeLive({"uno.": 0.1, "dos.": 0.2, "tres.": 0.3})
    spk, out, sent = speaker_with(live)
    spk.say_parts(["uno.", "dos.", "tres."])
    assert phrases_of(out) == [0.1, 0.2, 0.3]
    assert [t for _, t in live.calls] == ["uno.", "dos.", "tres."]
    kinds = [m["type"] for m in sent]
    assert sent[0] == {"type": "speaking", "on": True} and sent[-1] == {"type": "speaking", "on": False}
    assert kinds.count("speaking") == 2 and kinds.count("mouth") >= 20
    assert sent[-2] == {"type": "mouth", "level": 0.0}
    assert out.audio().size >= int(RATE * 0.9) + int(RATE * 0.25) - 2400


def test_stream_trims_leading_silence():
    spk, out, _ = speaker_with(None)
    spk.stream_say(iter([np.zeros(4800, dtype=np.float32), np.zeros(2400, dtype=np.float32), np.full(2400, 0.5, dtype=np.float32)]))
    audio = out.audio()
    assert np.flatnonzero(np.abs(audio) > 0.01)[0] <= 480
    assert abs(audio[0]) < 0.01
    on = Onset()
    assert on(np.zeros(1000, dtype=np.float32)).size == 0


def test_stream_requests_only_one_phrase_ahead():
    live = FakeLive({"uno.": 0.1, "dos.": 0.2, "tres.": 0.3}, seconds=0.3)
    spk, out, _ = speaker_with(live, out=FakeOut(pace=1.0))
    spk.say_parts(["uno.", "dos.", "tres."])
    started = {t: at for at, t in live.calls}
    uno_end = max(at for at, w in out.writes if w.size and round(float(np.max(np.abs(w))), 2) == 0.1)
    uno_start = min(at for at, w in out.writes if w.size and round(float(np.max(np.abs(w))), 2) == 0.1)
    assert started["dos."] < uno_end
    assert started["dos."] >= uno_start - 0.05
    assert started["tres."] >= uno_end - 0.05
    assert phrases_of(out) == [0.1, 0.2, 0.3]


def test_hush_cuts_audio_fast():
    live = FakeLive({"larga.": 0.5}, seconds=3.0, chunks=30)
    spk, out, sent = speaker_with(live, out=FakeOut(pace=1.0))
    talk = Utterance("1")
    talk.add("larga.")
    talk.add("otra.")
    worker = threading.Thread(target=spk.say_parts, args=(talk,))
    worker.start()
    while not out.writes:
        time.sleep(0.005)
    time.sleep(0.3)
    hushed = time.perf_counter()
    spk.hush()
    talk.end()
    worker.join(1.0)
    assert not worker.is_alive()
    assert time.perf_counter() - hushed < 0.1
    assert all(at < hushed + 0.1 for at, _ in out.writes)
    assert out.aborted >= 1
    assert sent[-1] == {"type": "speaking", "on": False}
    assert [t for _, t in live.calls] == ["larga.", "otra."] or [t for _, t in live.calls] == ["larga."]
    assert out.audio().size < RATE


def test_cache_hit_plays_without_network(tmp_path):
    cache = TtsCache(tmp_path)
    cache.put("gemini", "Aoede", "Hola sapito.", np.full(4800, 0.3, dtype=np.float32), RATE)
    live = FakeLive()
    spk, out, _ = speaker_with(live, voice=FakeVoice(cache=cache))
    spk.say("Hola sapito.")
    assert live.calls == [] and spk.last_engine == "cache"
    assert round(float(np.max(out.audio())), 2) == 0.3


def test_live_phrase_is_saved_to_cache(tmp_path):
    cache = TtsCache(tmp_path)
    live = FakeLive({"Ya llegué.": 0.2})
    spk, _, _ = speaker_with(live, voice=FakeVoice(cache=cache))
    spk.say_parts(["Ya llegué."])
    hit = cache.get("gemini", "Aoede", "Ya llegué.")
    assert hit is not None and hit[0].size == int(RATE * 0.3) // 3 * 3
    spk.say_parts(["Ya llegué."])
    assert len(live.calls) == 1 and spk.last_engine == "cache"


def test_fallback_to_gemini_tts_when_live_fails(tmp_path):
    voice = FakeVoice(cache=TtsCache(tmp_path))
    spk, out, sent = speaker_with(FakeLive(fail=True), voice=voice)
    spk.say_parts(["hola."])
    assert voice.calls == ["hola."] and round(float(np.max(out.audio())), 2) == 0.4
    assert sent[0] == {"type": "speaking", "on": True}


def test_fallback_to_silence_never_local(tmp_path):
    local = FakeLocal()
    g = GeminiTts(lambda: KEY, "m", "Aoede", client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))), fallbacks=())
    voice = Voice(local, g, TtsCache(tmp_path), lambda: "gemini", patience=0.0, sleep=lambda s: None)
    spk, out, sent = speaker_with(FakeLive(fail=True), voice=voice)
    spk.say_parts(["hola."])
    assert out.writes == [] and sent == [] and local.calls == 0 and spk.last_engine == "silencio"
    robot = Voice(local, g, TtsCache(tmp_path), lambda: "local")
    spk, out, sent = speaker_with(FakeLive(fail=True), voice=robot)
    spk.say("hola.")
    assert out.writes == [] and local.calls == 0


def test_real_session_feeds_speaker(tmp_path):
    live = session_with(Dialer())
    spk, out, _ = speaker_with(live, voice=FakeVoice(cache=TtsCache(tmp_path)))
    spk.say_parts(["uno.", "dos."])
    assert spk.last_engine == "live" and out.audio().size >= 2 * 7200 - 480
    assert TtsCache(tmp_path).get("gemini", "Aoede", "dos.") is not None


class FakeMic:
    def __init__(self):
        self.queue = queue.Queue()
        self.muted = threading.Event()

    def drain(self):
        while not self.queue.empty():
            self.queue.get_nowait()


class FakeVad:
    def feed(self, samples):
        return []

    def flush(self):
        return []

    def speaking(self):
        return False

    def reset(self):
        pass


async def run_session(script, live, pace=0.0, settle=None):
    out = FakeOut(pace=pace)
    spk = Speaker(FakeVoice(), live=live, output=out)
    mic = FakeMic()
    muted = []
    got = []

    async def brain(ws):
        for msg in script:
            if isinstance(msg, float):
                await asyncio.sleep(msg)
            else:
                await ws.send(json.dumps(msg))
        async for raw in ws:
            got.append(json.loads(raw))

    async with serve(brain, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}") as ws:
            loop = asyncio.get_running_loop()
            task = asyncio.create_task(session(ws, loop, mic, Listener(FakeVad(), None, WakeMatcher()), spk))
            for _ in range(400):
                await asyncio.sleep(0.01)
                if out.writes:
                    muted.append(mic.muted.is_set())
                if settle and settle(out, got) and not mic.muted.is_set():
                    break
            task.cancel()
    return out, got, muted


async def test_session_streams_say_parts():
    live = FakeLive({"Es Canberra.": 0.2, "No Sídney.": 0.3})
    script = [
        {"type": "say_start", "id": "1", "mood": "happy"},
        {"type": "say_part", "id": "1", "text": "Es Canberra."},
        0.1,
        {"type": "say_part", "id": "1", "text": "No Sídney."},
        {"type": "say_end", "id": "1", "action": "none"},
    ]
    out, got, muted = await run_session(script, live, settle=lambda o, g: any(m == {"type": "speaking", "on": False} for m in g))
    assert phrases_of(out) == [0.2, 0.3]
    assert muted and all(muted[:3])
    assert {"type": "speaking", "on": True} in got and got[-1] == {"type": "speaking", "on": False}


async def test_session_hush_empties_queue():
    live = FakeLive({"larga.": 0.5, "después.": 0.2, "suelta": 0.3}, seconds=2.0, chunks=20)
    script = [
        {"type": "say_start", "id": "7"},
        {"type": "say_part", "id": "7", "text": "larga."},
        {"type": "say_part", "id": "7", "text": "después."},
        {"type": "say", "text": "suelta"},
        0.4,
        {"type": "hush"},
    ]
    out, got, _ = await run_session(script, live, pace=1.0, settle=lambda o, g: any(m == {"type": "speaking", "on": False} for m in g))
    assert phrases_of(out) == [0.5]
    assert out.audio().size < RATE
    assert "suelta" not in [t for _, t in live.calls]
