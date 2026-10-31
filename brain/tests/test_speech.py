import base64
import json
import time

import httpx
import numpy as np
import pytest

from sapo.config import LiveConfig
from sapo.protocol import mouth, quiet, relayed
from sapo.voice.client import Speaker, should_speak
from sapo.voice.speech import GeminiTts, LiveTts, TtsCache, TtsError, Voice, mouth_levels, similar

KEY = "FAKE-key-para-pruebas-0000"


def pcm_response(seconds=0.5, rate=24000):
    t = np.arange(int(rate * seconds)) / rate
    pcm = (np.sin(2 * np.pi * 220 * t) * 0.5 * 32767).astype("<i2").tobytes()
    return {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": f"audio/L16;codec=pcm;rate={rate}", "data": base64.b64encode(pcm).decode()}}]}}]}


def client_with(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


class FakeLocal:
    rate = 24000

    def __init__(self):
        self.calls = 0

    def synth(self, text):
        self.calls += 1
        return np.zeros(2400, dtype=np.float32), self.rate


def test_gemini_tts_request_and_audio():
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        seen["key"] = req.headers.get("x-goog-api-key")
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json=pcm_response())

    tts = GeminiTts(lambda: KEY, "gemini-3.8-flash-lite-tts", "Puck", client=client_with(handler))
    samples, rate = tts.synth("hola")
    assert rate == 24000 and samples.size == 12000 and 0.4 < np.max(np.abs(samples)) <= 0.51
    assert KEY not in seen["url"] and seen["key"] == KEY
    assert seen["url"].endswith("/models/gemini-3.8-flash-lite-tts:generateContent")
    cfg = seen["body"]["generationConfig"]
    assert cfg["responseModalities"] == ["AUDIO"]
    assert cfg["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Puck"
    assert seen["body"]["contents"][0]["parts"][0]["text"] == "hola"


@pytest.mark.parametrize("status", [400, 403, 429, 500])
def test_gemini_tts_errors_never_leak_key(status):
    tts = GeminiTts(lambda: KEY, "m", "Puck", client=client_with(lambda r: httpx.Response(status, text=KEY)), fallbacks=())
    with pytest.raises(TtsError) as e:
        tts.synth("hola")
    assert KEY not in str(e.value)
    assert not tts.available()


def test_gemini_network_error_backoff():
    def boom(req):
        raise httpx.ConnectError("sin red")

    tts = GeminiTts(lambda: KEY, "m", "Puck", client=client_with(boom))
    with pytest.raises(TtsError):
        tts.synth("hola")
    assert tts.down_until - time.monotonic() > 20


def test_voice_falls_back_to_local_without_key(tmp_path):
    local = FakeLocal()
    v = Voice(local, GeminiTts(lambda: None, "m", "Puck", client=client_with(lambda r: httpx.Response(200))), TtsCache(tmp_path), lambda: "gemini")
    v.synth("hola")
    assert local.calls == 1 and v.last_engine == "local"


def test_voice_rotates_models_and_never_uses_robot(tmp_path):
    seen = []

    def handler(req):
        model = req.url.path.rsplit("/", 1)[-1].split(":")[0]
        seen.append(model)
        return httpx.Response(429) if model == "lite" else httpx.Response(200, json=pcm_response())

    local = FakeLocal()
    g = GeminiTts(lambda: KEY, "lite", "Puck", client=client_with(handler), fallbacks=("flash", "otro"))
    v = Voice(local, g, TtsCache(tmp_path), lambda: "gemini")
    v.synth("hola")
    assert v.last_engine == "gemini" and g.used == "flash" and local.calls == 0
    v.synth("adiós")
    assert seen == ["lite", "flash", "flash"]
    v.synth("Hola ")
    assert v.last_engine == "gemini-cache" and len(seen) == 3


def test_voice_waits_for_cooldown_then_speaks(tmp_path):
    now = {"t": 0.0}
    state = {"busy": True}

    def handler(req):
        return httpx.Response(429) if state["busy"] else httpx.Response(200, json=pcm_response())

    def sleep(sec):
        now["t"] += sec
        state["busy"] = False

    local = FakeLocal()
    g = GeminiTts(lambda: KEY, "m", "Puck", client=client_with(handler), fallbacks=(), clock=lambda: now["t"])
    g.rest = lambda model, base: g.model_down.__setitem__(model, now["t"] + 5.0)
    v = Voice(local, g, TtsCache(tmp_path), lambda: "gemini", patience=12.0, sleep=sleep)
    v.synth("hola")
    assert v.last_engine == "gemini" and local.calls == 0 and now["t"] == 5.0


def test_voice_silent_instead_of_robot_when_all_down(tmp_path):
    now = {"t": 0.0}

    def sleep(sec):
        now["t"] += sec

    local = FakeLocal()
    g = GeminiTts(lambda: KEY, "m", "Puck", client=client_with(lambda r: httpx.Response(503)), fallbacks=("n",), clock=lambda: now["t"])
    v = Voice(local, g, TtsCache(tmp_path), lambda: "gemini", patience=12.0, sleep=sleep)
    with pytest.raises(TtsError):
        v.synth("hola")
    assert local.calls == 0 and v.last_engine == "silencio" and now["t"] <= 12.0


def test_voice_offline_is_silent_fast(tmp_path):
    def boom(req):
        raise httpx.ConnectError("sin red")

    slept = []
    local = FakeLocal()
    v = Voice(local, GeminiTts(lambda: KEY, "m", "Puck", client=client_with(boom)), TtsCache(tmp_path), lambda: "gemini", sleep=slept.append)
    with pytest.raises(TtsError):
        v.synth("hola")
    assert local.calls == 0 and slept == []


def test_voice_local_engine_skips_gemini(tmp_path):
    local = FakeLocal()
    g = GeminiTts(lambda: KEY, "m", "Puck", client=client_with(lambda r: pytest.fail("no debía llamar")))
    Voice(local, g, TtsCache(tmp_path), lambda: "local").synth("hola")
    assert local.calls == 1


def test_cache_roundtrip_and_limit(tmp_path):
    c = TtsCache(tmp_path, limit=60_000)
    s = np.linspace(-0.5, 0.5, 24000, dtype=np.float32)
    assert c.get("gemini", "Puck", "uno") is None
    c.put("gemini", "Puck", "uno", s, 24000)
    got, rate = c.get("gemini", "Puck", "uno")
    assert rate == 24000 and np.allclose(got, s, atol=1e-3)
    assert c.get("gemini", "Kore", "uno") is None
    for i in range(5):
        c.put("gemini", "Puck", f"frase {i}", s, 24000)
    assert c.size() <= 60_000
    assert c.get("gemini", "Puck", "frase 4") is not None


def test_mouth_levels_range_and_rate():
    rate = 24000
    t = np.arange(rate) / rate
    s = np.concatenate([np.sin(2 * np.pi * 200 * t) * 0.6, np.zeros(rate)]).astype(np.float32)
    levels = [lv for _, lv in mouth_levels(s, rate)]
    assert 59 <= len(levels) <= 61
    assert all(0.0 <= lv <= 1.0 for lv in levels)
    assert max(levels[:30]) > 0.8 and levels[-1] < 0.05


def test_speaker_emits_speaking_and_mouth():
    sent = []

    class Quiet(Speaker):
        def play(self, samples, rate):
            for _, lv in mouth_levels(samples, rate):
                self.on_mouth(mouth(lv))

    Quiet(FakeLocal(), on_mouth=sent.append).say("hola")
    kinds = [m["type"] for m in sent]
    assert kinds[0] == "speaking" and sent[0]["on"] is True
    assert kinds[-1] == "speaking" and sent[-1]["on"] is False
    assert kinds.count("mouth") >= 3 and sent[-2] == {"type": "mouth", "level": 0.0}


def test_should_speak_respects_quiet_and_replies(tmp_path):
    conf = LiveConfig(tmp_path / "config.json")
    now = 1000.0
    assert should_speak({"quiet": False, "asked": 0.0}, conf, now)
    assert not should_speak({"quiet": True, "asked": 0.0}, conf, now)
    assert should_speak({"quiet": True, "asked": now - 5}, conf, now)
    (tmp_path / "config.json").write_text(json.dumps({"voice": {"enabled": False}}), encoding="utf-8")
    assert not should_speak({"quiet": False, "asked": now}, conf, now)


def test_relay_messages_are_clean():
    assert relayed({"type": "mouth", "level": 3}) == {"type": "mouth", "level": 1.0}
    assert relayed({"type": "mouth", "level": "x"}) is None
    assert relayed({"type": "quiet", "on": True, "reason": "raro"}) == quiet(True, "game")
    assert relayed({"type": "croak", "kind": "inexistente"}) == {"type": "croak", "kind": "corto"}


def test_smooth_edges_no_jump_at_ends():
    from sapo.voice.client import smooth_edges
    s = np.full(2400, 0.8, dtype=np.float32)
    out = smooth_edges(s, 24000)
    assert out[0] == 0.0 and abs(out[-1]) < 1e-6
    assert np.abs(np.diff(out)).max() < 0.01
    assert out[1200] == pytest.approx(0.8)


def test_gemini_wav_with_metadata_is_trimmed():
    import struct
    from sapo.voice.speech import decode_audio
    pcm = (np.sin(np.arange(2400) / 5) * 8000).astype("<i2").tobytes()
    meta = b"caBX" + b"\xa3c2pa.trainedAlgorithmicMedia" * 20
    fmt = struct.pack("<HHIIHH", 1, 1, 24000, 48000, 2, 16)
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(pcm)) + pcm + b"C2PA" + struct.pack("<I", len(meta)) + meta
    raw = b"RIFF" + struct.pack("<I", len(body)) + body
    out, rate = decode_audio(raw, "audio/wav")
    assert rate == 24000 and out == pcm


def test_gemini_tts_wav_response_decodes(tmp_path):
    import struct
    pcm = (np.sin(np.arange(4800) / 5) * 8000).astype("<i2").tobytes()
    fmt = struct.pack("<HHIIHH", 1, 1, 24000, 48000, 2, 16)
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(pcm)) + pcm + b"C2PA" + struct.pack("<I", 8) + b"x" * 8
    raw = b"RIFF" + struct.pack("<I", len(body)) + body
    resp = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(raw).decode()}}]}}]}
    seen = {}
    def handler(req):
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json=resp)
    s, rate = GeminiTts(lambda: KEY, "m", "Puck", client=client_with(handler)).synth("hola")
    assert rate == 24000 and len(s) == 4800 and np.abs(s).max() < 0.3
    assert seen["body"]["contents"][0]["parts"][0]["text"] == "hola"


class FakeLiveWs:
    def __init__(self, said, pcm_len=24000, setup=True):
        self.said = said
        self.pcm_len = pcm_len
        self.setup = setup
        self.sent = []
        self.out = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def send(self, raw):
        msg = json.loads(raw)
        self.sent.append(msg)
        if "setup" in msg:
            self.out = [json.dumps({"setupComplete": {}} if self.setup else {"nope": 1})]
        else:
            audio = base64.b64encode((np.ones(self.pcm_len, dtype="<i2") * 1000).tobytes()).decode()
            self.out += [
                json.dumps({"serverContent": {"modelTurn": {"parts": [{"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": audio}}]}}}),
                json.dumps({"serverContent": {"outputTranscription": {"text": self.said}}}),
                json.dumps({"serverContent": {"turnComplete": True}}),
            ]

    def recv(self, timeout=None):
        return self.out.pop(0)


def test_live_reads_exact_text():
    socks = []

    def connect(url, key):
        socks.append(FakeLiveWs("¡Órale! Ya son las cinco."))
        return socks[-1]

    live = LiveTts(lambda: KEY, "gemini-3.8-live", "Aoede", connect=connect)
    samples, rate = live.synth("Órale, ya son las cinco")
    assert rate == 24000 and samples.size == 24000
    setup = socks[0].sent[0]["setup"]
    assert setup["model"] == "models/gemini-3.8-live"
    assert setup["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Aoede"
    assert socks[0].sent[1] == {"realtimeInput": {"text": "Órale, ya son las cinco"}}


def test_live_rejects_paraphrase():
    live = LiveTts(lambda: KEY, "m", "Aoede", connect=lambda u, k: FakeLiveWs("Claro, con gusto te ayudo con lo que necesites hoy"))
    with pytest.raises(TtsError):
        live.synth("ya son las cinco")
    assert not live.available()


def test_similar_ignores_accents_and_punctuation():
    assert similar("¡Órale! Ya son las 5.", "orale ya son las 5") == 1.0
    assert similar("hola", "") == 0.0


def test_voice_uses_live_when_tts_quota_is_gone(tmp_path):
    local = FakeLocal()
    g = GeminiTts(lambda: KEY, "m", "Aoede", client=client_with(lambda r: httpx.Response(429)), fallbacks=())
    live = LiveTts(lambda: KEY, "live", "Aoede", connect=lambda u, k: FakeLiveWs("hola sapito"))
    v = Voice(local, g, TtsCache(tmp_path), lambda: "gemini", live=live, sleep=lambda s: None)
    samples, rate = v.synth("hola sapito")
    assert v.last_engine == "live" and local.calls == 0 and rate == 24000
    v.synth("hola sapito")
    assert v.last_engine == "gemini-cache"
