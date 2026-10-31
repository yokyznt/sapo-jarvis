import base64
import json
import time

import httpx
import numpy as np
import pytest

from sapo.config import LiveConfig
from sapo.protocol import mouth, quiet, relayed
from sapo.voice.client import Speaker, should_speak
from sapo.voice.speech import GeminiTts, TtsCache, TtsError, Voice, mouth_levels

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
    assert seen["body"]["contents"][0]["parts"][0]["text"].endswith("hola")


@pytest.mark.parametrize("status", [400, 403, 429, 500])
def test_gemini_tts_errors_never_leak_key(status):
    tts = GeminiTts(lambda: KEY, "m", "Puck", client=client_with(lambda r: httpx.Response(status, text=KEY)))
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


def test_voice_falls_back_on_429_then_uses_cache(tmp_path):
    calls = {"n": 0, "ok": False}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(200, json=pcm_response()) if calls["ok"] else httpx.Response(429)

    local = FakeLocal()
    g = GeminiTts(lambda: KEY, "m", "Puck", client=client_with(handler))
    v = Voice(local, g, TtsCache(tmp_path), lambda: "gemini")
    v.synth("hola")
    assert v.last_engine == "local" and local.calls == 1
    calls["ok"] = True
    g.down_until = 0
    v.synth("hola")
    assert v.last_engine == "gemini"
    v.synth("Hola ")
    assert v.last_engine == "gemini-cache" and calls["n"] == 2


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
