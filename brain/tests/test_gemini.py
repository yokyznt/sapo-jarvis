import asyncio
import base64
import json
import logging

import httpx
import pytest

from sapo.config import Settings, static_config
from sapo.gemini import Gemini, GeminiError, to_contents
from sapo.hardware import pick_profile
from sapo.llm import Ollama, Router

KEY = "AIzaFAKE-clave-que-no-debe-salir-123"


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def gemini_reply(parts):
    return {"candidates": [{"content": {"role": "model", "parts": parts}}]}


def make_gemini(handler, key=KEY):
    return Gemini(lambda: key, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def make_ollama(log):
    def handler(request):
        body = json.loads(request.content)
        log.append((request.url.path, body))
        if request.url.path == "/api/chat":
            return httpx.Response(200, json={"message": {"content": '{"say":"desde ollama","mood":"happy","action":"none"}'}})
        return httpx.Response(200, json={})

    return Ollama("http://ollama.test", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def make_router(gemini, ollama_log, clock=None, **conf):
    conf.setdefault("provider", "gemini")
    return Router(pick_profile(Settings(), vram=8151), make_ollama(ollama_log), gemini=gemini, config=static_config(**conf), clock=clock or Clock())


async def test_gemini_request_shape_and_json_reply():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=gemini_reply([{"text": '{"say":"hola desde gemini","mood":"happy","action":"none"}'}]))

    router = make_router(make_gemini(handler), [])
    messages = [{"role": "system", "content": "eres un sapo"}, {"role": "user", "content": "hola"}, {"role": "assistant", "content": '{"say":"qué"}'}, {"role": "user", "content": "nada"}]
    out = await router.complete(messages, lite=True)
    assert json.loads(out)["say"] == "hola desde gemini"
    req = seen[0]
    assert req.url.path == "/v1beta/models/gemini-flash-lite-latest:generateContent"
    assert req.headers["x-goog-api-key"] == KEY and KEY not in str(req.url)
    body = json.loads(req.content)
    assert body["systemInstruction"]["parts"][0]["text"] == "eres un sapo"
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["responseJsonSchema"]["required"] == ["say", "mood", "action"]
    await router.complete(messages)
    assert seen[1].url.path.endswith("/gemini-3.5-flash-lite:generateContent")
    assert router.last == "gemini"


async def test_gemini_function_calling_roundtrip():
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        if len(bodies) == 1:
            return httpx.Response(200, json=gemini_reply([{"functionCall": {"name": "volume", "args": {"action": "set", "percent": 30}}, "thoughtSignature": "firma"}]))
        return httpx.Response(200, json=gemini_reply([{"text": "listo"}]))

    router = make_router(make_gemini(handler), [])
    await router.set_game(True)
    tools = [{"type": "function", "function": {"name": "volume", "description": "vol", "parameters": {"type": "object", "properties": {"percent": {"type": "integer"}}, "required": []}}}]
    msg = await router.chat_tools([{"role": "user", "content": "volumen al 30"}], tools)
    call = msg["tool_calls"][0]
    assert call["function"] == {"name": "volume", "arguments": {"action": "set", "percent": 30}}
    decl = bodies[0]["tools"][0]["functionDeclarations"][0]
    assert decl["name"] == "volume" and decl["parametersJsonSchema"]["properties"]["percent"]["type"] == "integer"
    assert "responseMimeType" not in bodies[0]["generationConfig"]
    history = [
        {"role": "user", "content": "volumen al 30"},
        {"role": "assistant", "content": "", "tool_calls": msg["tool_calls"]},
        {"role": "tool", "tool_name": "volume", "content": "ok: volumen 30%"},
        {"role": "user", "content": "contesta"},
    ]
    await router.complete(history)
    contents = bodies[1]["contents"]
    assert contents[1] == {"role": "model", "parts": [{"functionCall": {"name": "volume", "args": {"action": "set", "percent": 30}}, "thoughtSignature": "firma"}]}
    assert contents[2]["parts"][0] == {"functionResponse": {"name": "volume", "response": {"result": "ok: volumen 30%"}}}
    assert contents[2]["parts"][1] == {"text": "contesta"}


async def test_gemini_vision_inline_image():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=gemini_reply([{"text": "una hoja de cálculo"}]))

    router = make_router(make_gemini(handler), [])
    assert await router.see(b"\xff\xd8jpeg", "qué ves") == "una hoja de cálculo"
    part = bodies[0]["contents"][0]["parts"][1]
    assert part == {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(b"\xff\xd8jpeg").decode()}}


async def test_without_key_goes_to_ollama_silently():
    hits = []
    olog = []

    def handler(request):
        hits.append(request)
        return httpx.Response(500)

    router = make_router(make_gemini(handler, key=None), olog)
    out = await router.complete([{"role": "user", "content": "hola"}])
    assert json.loads(out)["say"] == "desde ollama"
    assert hits == [] and olog[-1][0] == "/api/chat" and router.last == "ollama"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429, json={"error": {"status": "RESOURCE_EXHAUSTED"}}),
        httpx.Response(403, json={"error": {"status": "PERMISSION_DENIED"}}),
        httpx.Response(503),
        "network",
    ],
)
async def test_fallback_and_backoff(response):
    clock = Clock()
    hits = []
    olog = []

    def handler(request):
        hits.append(request)
        if response == "network":
            raise httpx.ConnectError("sin red", request=request)
        return response

    router = make_router(make_gemini(handler), olog, clock=clock)
    out = await router.complete([{"role": "user", "content": "hola"}])
    assert json.loads(out)["say"] == "desde ollama"
    assert len(hits) == 2
    await router.complete([{"role": "user", "content": "otra"}])
    assert len(hits) == 2 and len(olog) == 2
    clock.now += 31
    await router.complete([{"role": "user", "content": "ya"}])
    assert len(hits) == 4 and router.failures == 2
    clock.now += 59
    await router.complete([{"role": "user", "content": "aún no"}])
    assert len(hits) == 4
    clock.now += 2
    await router.complete([{"role": "user", "content": "ahora sí"}])
    assert len(hits) == 6


async def test_busy_model_falls_back_to_lite():
    seen = []

    def handler(request):
        seen.append(request.url.path.rsplit("/", 1)[-1])
        if "3.5-flash-lite" in request.url.path:
            return httpx.Response(503, json={"error": {"message": "high demand"}})
        return httpx.Response(200, json=gemini_reply([{"text": '{"say":"París, obvio","mood":"happy","action":"none"}'}]))

    olog = []
    router = make_router(make_gemini(handler), olog)
    out = await router.complete([{"role": "user", "content": "capital de francia"}])
    assert json.loads(out)["say"] == "París, obvio"
    assert router.last == "gemini" and router.failures == 0 and olog == []
    assert [s.split(":")[0] for s in seen] == ["gemini-3.5-flash-lite", "gemini-flash-lite-latest"]


async def test_generic_400_drops_thinking():
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        if "thinkingConfig" in body["generationConfig"]:
            return httpx.Response(400, json={"error": {"message": "Request contains an invalid argument."}})
        return httpx.Response(200, json=gemini_reply([{"text": "{}"}]))

    gemini = make_gemini(handler)
    await gemini.generate("m", [{"role": "user", "content": "x"}])
    await gemini.generate("m", [{"role": "user", "content": "y"}])
    assert len(bodies) == 3


async def test_ollama_started_when_down():
    state = {"up": False, "launched": 0}

    def handler(request):
        if not state["up"]:
            raise httpx.ConnectError("apagado", request=request)
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "1"})
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "hola"}})

    def launcher():
        state["launched"] += 1
        state["up"] = True
        return True

    ollama = Ollama("http://127.0.0.1:11434", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), launcher=launcher)
    assert await ollama.chat("m", [{"role": "user", "content": "x"}]) == "hola"
    assert state["launched"] == 1


async def test_remote_ollama_not_launched():
    calls = []

    def handler(request):
        raise httpx.ConnectError("apagado", request=request)

    ollama = Ollama("http://192.168.1.9:11434", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), launcher=lambda: calls.append(1) or True)
    with pytest.raises(httpx.ConnectError):
        await ollama.chat("m", [{"role": "user", "content": "x"}])
    assert calls == []


async def test_gemini_recovers_after_backoff():
    clock = Clock()
    state = {"fail": True}

    def handler(request):
        if state["fail"]:
            return httpx.Response(429)
        return httpx.Response(200, json=gemini_reply([{"text": '{"say":"volví","mood":"happy","action":"none"}'}]))

    router = make_router(make_gemini(handler), [], clock=clock)
    await router.complete([{"role": "user", "content": "x"}])
    assert router.last == "ollama"
    state["fail"] = False
    clock.now += 30
    out = await router.complete([{"role": "user", "content": "x"}])
    assert json.loads(out)["say"] == "volví" and router.failures == 0 and router.last == "gemini"


async def test_game_mode_keeps_gemini():
    hits = []
    olog = []

    def handler(request):
        hits.append(request)
        return httpx.Response(200, json=gemini_reply([{"text": '{"say":"juego","mood":"happy","action":"none"}'}]))

    router = make_router(make_gemini(handler), olog)
    router.unload_after = 0
    await router.set_game(True)
    await asyncio.gather(*router.tasks)
    await router.complete([{"role": "user", "content": "x"}], lite=True)
    assert len(hits) == 1
    assert [p for p, _ in olog] == ["/api/generate"]
    assert olog[0][1] == {"model": "qwen3.5:4b", "keep_alive": 0}


async def test_provider_ollama_skips_gemini():
    hits = []

    def handler(request):
        hits.append(request)
        return httpx.Response(200, json=gemini_reply([{"text": "{}"}]))

    router = make_router(make_gemini(handler), [], provider="ollama")
    await router.complete([{"role": "user", "content": "x"}])
    assert hits == []


async def test_thinking_config_retry():
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        if "thinkingConfig" in body["generationConfig"]:
            return httpx.Response(400, json={"error": {"message": "thinking budget is not supported"}})
        return httpx.Response(200, json=gemini_reply([{"text": "{}"}]))

    gemini = make_gemini(handler)
    await gemini.generate("m", [{"role": "user", "content": "x"}])
    await gemini.generate("m", [{"role": "user", "content": "y"}])
    assert len(bodies) == 3


async def test_key_never_logged(caplog):
    caplog.set_level(logging.DEBUG)

    def handler(request):
        return httpx.Response(400, text=f"API key not valid: {KEY}")

    router = make_router(make_gemini(handler), [])
    await router.complete([{"role": "user", "content": "x"}])
    with pytest.raises(GeminiError) as err:
        await make_gemini(lambda r: httpx.Response(418, text=f"teapot {KEY}")).generate("m", [])
    assert KEY not in str(err.value)
    assert KEY not in caplog.text
    assert KEY not in repr(router.gemini.__dict__.get("http"))


def test_to_contents_merges_roles():
    system, contents = to_contents([{"role": "system", "content": "a"}, {"role": "system", "content": "b"}, {"role": "user", "content": "1"}, {"role": "user", "content": "2"}])
    assert system == "a\n\nb"
    assert contents == [{"role": "user", "parts": [{"text": "1"}, {"text": "2"}]}]


async def test_slow_model_skipped_for_a_while():
    seen = []

    def handler(request):
        name = request.url.path.rsplit("/", 1)[-1].split(":")[0]
        seen.append(name)
        if name == "gemini-3.5-flash-lite":
            return httpx.Response(503)
        return httpx.Response(200, json=gemini_reply([{"text": '{"say":"ok","mood":"happy","action":"none"}'}]))

    clock = Clock()
    router = make_router(make_gemini(handler), [], clock=clock)
    await router.complete([{"role": "user", "content": "a"}])
    await router.complete([{"role": "user", "content": "b"}])
    assert seen == ["gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-flash-lite-latest"]
    clock.now += 121
    await router.complete([{"role": "user", "content": "c"}])
    assert seen[-2:] == ["gemini-3.5-flash-lite", "gemini-flash-lite-latest"]


async def test_ollama_drops_broken_json_format():
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        if "format" in body:
            return httpx.Response(200, json={"message": {"role": "assistant", "content": '{"say": '}, "done": False})
        return httpx.Response(200, json={"message": {"role": "assistant", "content": '{"say":"El Nilo","mood":"happy","action":"none"}'}, "done": True})

    ollama = Ollama("http://ollama.test", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert json.loads(await ollama.chat("m", [{"role": "user", "content": "x"}]))["say"] == "El Nilo"
    await ollama.chat("m", [{"role": "user", "content": "y"}])
    assert ["format" in b for b in bodies] == [True, False, False]


def test_ollama_launch_keeps_hidden_console(monkeypatch):
    import subprocess
    from sapo import llm
    seen = {}

    def fake_popen(cmd, **kw):
        seen.update(kw)
        return object()

    monkeypatch.setattr(llm, "ollama_exe", lambda: "ollama.exe")
    monkeypatch.setattr(llm.subprocess, "Popen", fake_popen)
    assert llm.launch_ollama()
    flags = seen["creationflags"]
    assert not flags & 0x00000008
    if hasattr(subprocess, "STARTUPINFO"):
        assert flags & 0x00000010
        assert seen["startupinfo"].wShowWindow == 0
