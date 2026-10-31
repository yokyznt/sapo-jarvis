import asyncio
import json

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from sapo.server import Hub, make_handler
from tests.conftest import FakeLLM


def types(outbox):
    return [m["type"] for m in outbox]


async def test_hello_greets(make_brain, outbox):
    brain = make_brain(FakeLLM())
    await brain.handle({"type": "hello", "version": 1})
    assert outbox[0]["type"] == "say" and outbox[0]["text"]


async def test_chat_flow_and_memory(make_brain, outbox, memory):
    llm = FakeLLM([json.dumps({"say": "Qué onda, Dylan", "mood": "happy", "action": "dance", "fact": "Se llama Dylan"})])
    brain = make_brain(llm)
    await brain.handle({"type": "chat", "text": "hola, soy Dylan"})
    assert outbox == [
        {"type": "thinking", "on": True},
        {"type": "thinking", "on": False},
        {"type": "say", "text": "Qué onda, Dylan", "mood": "happy"},
        {"type": "action", "name": "dance"},
    ]
    assert memory.recent_messages(5) == [("user", "hola, soy Dylan"), ("sapo", "Qué onda, Dylan")]
    assert memory.facts() == ["Se llama Dylan"]
    await brain.handle({"type": "chat", "text": "¿cómo me llamo?"})
    second = llm.calls[1]
    assert "Se llama Dylan" in second[0]["content"]
    assert second[-1] == {"role": "user", "content": "¿cómo me llamo?"}
    assert second[-2]["role"] == "assistant"


async def test_chat_llm_failure_uses_canned(make_brain, outbox, persona):
    brain = make_brain(FakeLLM(fail=True))
    await brain.handle({"type": "chat", "text": "hola"})
    says = [m for m in outbox if m["type"] == "say"]
    assert says and says[0]["text"] in persona.strings["canned"]["error"]
    assert outbox[-1] != {"type": "thinking", "on": True}


async def test_long_reply_clipped(make_brain, outbox):
    brain = make_brain(FakeLLM([json.dumps({"say": "bla " * 80, "mood": "happy", "action": "none"})]))
    await brain.handle({"type": "chat", "text": "cuéntame algo"})
    say = next(m for m in outbox if m["type"] == "say")
    assert len(say["text"]) <= 90


async def test_event_rate_limit(make_brain, outbox, clock):
    llm = FakeLLM()
    brain = make_brain(llm)
    for _ in range(3):
        await brain.handle({"type": "event", "name": "petted", "boredom": 0.1})
    assert len(llm.calls) == 1
    assert types(outbox).count("say") == 1
    clock.now = 30
    await brain.handle({"type": "event", "name": "petted", "boredom": 0.1})
    assert len(llm.calls) == 2
    for name in ("thrown", "dancing", "woke", "moved_window"):
        await brain.handle({"type": "event", "name": name, "boredom": 0.1})
    assert len(llm.calls) == 4


async def test_event_while_busy_uses_canned(make_brain, outbox, persona):
    llm = FakeLLM(delay=0.2)
    brain = make_brain(llm)
    chat = asyncio.create_task(brain.handle({"type": "chat", "text": "hola"}))
    await asyncio.sleep(0.05)
    await brain.handle({"type": "event", "name": "thrown", "boredom": 0.5})
    await chat
    says = [m["text"] for m in outbox if m["type"] == "say"]
    assert says[0] in persona.strings["canned"]["thrown"]
    assert len(llm.calls) == 1


async def test_game_mode(make_brain, outbox):
    llm = FakeLLM()
    brain = make_brain(llm)
    await brain.handle({"type": "event", "name": "game_on", "boredom": 0.0})
    assert llm.game_calls == [True]
    assert {"type": "action", "name": "sleep"} in outbox
    assert await brain.tick() is False
    await brain.handle({"type": "event", "name": "petted", "boredom": 0.0})
    assert llm.calls == []
    await brain.handle({"type": "event", "name": "game_off", "boredom": 0.0})
    assert llm.game_calls == [True, False]
    assert await brain.tick() is True


async def test_autonomous_tick_and_delay(make_brain, outbox, clock):
    llm = FakeLLM([json.dumps({"say": "Me aburro", "mood": "annoyed", "action": "steal_cursor"}), json.dumps({"say": "", "mood": "sleepy", "action": "none"})])
    brain = make_brain(llm)
    assert await brain.tick() is True
    assert {"type": "action", "name": "steal_cursor"} in outbox
    assert "PENSAMIENTO PROPIO" in llm.calls[0][-1]["content"]
    assert await brain.tick() is False
    clock.now = 61
    assert await brain.tick() is False
    brain.boredom = 0.0
    calm = [brain.next_delay() for _ in range(200)]
    brain.boredom = 1.0
    bored = [brain.next_delay() for _ in range(200)]
    assert 120 <= min(calm) and max(calm) <= 360
    assert max(bored) <= 360 * 0.4 + 1e-9
    assert sum(bored) / 200 < sum(calm) / 200


async def test_websocket_roundtrip(make_brain):
    hub = Hub()
    brain = make_brain(FakeLLM([json.dumps({"say": "Hola desde el cerebro", "mood": "curious", "action": "look_around"})]))
    brain.send = hub.send
    async with serve(make_handler(brain, hub), "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({"type": "hello", "version": 1}))
            assert json.loads(await ws.recv())["type"] == "say"
            await ws.send("esto no es json")
            await ws.send(json.dumps({"type": "chat", "text": "qué haces"}))
            got = [json.loads(await asyncio.wait_for(ws.recv(), 2)) for _ in range(4)]
    assert got == [
        {"type": "thinking", "on": True},
        {"type": "thinking", "on": False},
        {"type": "say", "text": "Hola desde el cerebro", "mood": "curious"},
        {"type": "action", "name": "look_around"},
    ]
