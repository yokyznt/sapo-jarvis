import asyncio
import json

import httpx

from sapo.config import Settings
from sapo.hardware import pick_profile
from sapo.llm import Ollama, Router


def test_profiles():
    s = Settings()
    gpu = pick_profile(s, vram=8151)
    assert (gpu.name, gpu.model, gpu.num_gpu, gpu.game_model, gpu.game_num_gpu) == ("gpu", "qwen3.5:4b", None, "qwen3.5:2b", 0)
    cpu = pick_profile(s, vram=4096)
    assert (cpu.name, cpu.model, cpu.num_gpu) == ("cpu", "qwen3.5:2b", 0)
    assert pick_profile(s, vram=0).name == "cpu"


def fake_ollama(log):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        log.append((request.url.path, body))
        if request.url.path == "/api/chat":
            return httpx.Response(200, json={"message": {"content": '{"say":"hola","mood":"happy","action":"none"}'}})
        return httpx.Response(200, json={})

    return Ollama("http://ollama.test", 80, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_router_game_switch():
    log = []
    router = Router(pick_profile(Settings(), vram=8151), fake_ollama(log))
    await router.complete([{"role": "user", "content": "hola"}])
    path, body = log[-1]
    assert body["model"] == "qwen3.5:4b" and body["think"] is False
    assert body["options"]["num_predict"] == 80 and "num_gpu" not in body["options"]
    await router.set_game(True)
    assert log[-1] == ("/api/generate", {"model": "qwen3.5:4b", "keep_alive": 0})
    await router.complete([{"role": "user", "content": "hola"}])
    assert log[-1][1]["model"] == "qwen3.5:2b" and log[-1][1]["options"]["num_gpu"] == 0
    await router.set_game(False)
    await asyncio.sleep(0)
    await asyncio.gather(*router.tasks)
    assert ("/api/generate", {"model": "qwen3.5:2b", "keep_alive": 0}) in log
    assert log[-1] == ("/api/generate", {"model": "qwen3.5:4b"})


async def test_think_fallback_when_unsupported():
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if "think" in body:
            return httpx.Response(400, json={"error": "model does not support think"})
        return httpx.Response(200, json={"message": {"content": "{}"}})

    o = Ollama("http://x", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert await o.chat("m", []) == "{}"
    assert await o.chat("m", []) == "{}"
    assert len(calls) == 3
