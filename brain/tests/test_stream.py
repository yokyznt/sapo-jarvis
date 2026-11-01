import asyncio
import json
import types

import httpx
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

import sapo.llm as llm_mod
from sapo.config import Settings
from sapo.gemini import Gemini
from sapo.hardware import pick_profile
from sapo.llm import CLOUD_STREAM, OLLAMA_ENV, Ollama, Router, launch_ollama
from sapo.personality import Sentences
from sapo.protocol import MAX_SAY, decode, relayed, say_end, say_part, say_start
from sapo.server import Hub, make_handler
from tests.conftest import FakeLLM


def feed(text, step=1):
    s = Sentences()
    out = []
    for i in range(0, len(text), step):
        for part in s.feed(text[i : i + step]):
            out.append((i + step, part))
    out += [(len(text), p) for p in s.flush()]
    return out, s


def test_sentences_first_part_is_early():
    text = "[happy] Es la capital de Australia, Canberra, no Sídney. Todos se confunden."
    out, s = feed(text)
    assert s.mood == "happy"
    assert out[0][1] == "Es la capital de Australia,"
    assert out[0][0] <= text.index("Canberra") + 1
    assert [p for _, p in out[1:]] == ["Canberra, no Sídney.", "Todos se confunden."]


def test_sentences_waits_for_three_words_then_cuts_on_terminators():
    out, _ = feed("Es Canberra. Ni modo, así es la vida. Ok, va.")
    assert [p for _, p in out] == ["Es Canberra. Ni modo,", "así es la vida.", "Ok, va."]


def test_sentences_never_cut_numbers():
    out, _ = feed("Mide 3.5 metros y pesa 1,200 kilos. Son las 11:40 ya.", step=2)
    assert [p for _, p in out] == ["Mide 3.5 metros y pesa 1,200 kilos.", "Son las 11:40 ya."]


def test_sentences_keep_whole_sentences_up_to_32_words():
    long = "uno dos tres cuatro cinco seis siete ocho, nueve diez once doce trece catorce quince dieciséis diecisiete"
    out, _ = feed("Hola, qué tal amigo. Bien, gracias por preguntar. " + long + ".")
    parts = [p for _, p in out]
    assert parts == ["Hola, qué tal amigo.", "Bien, gracias por preguntar.", long + "."]


def test_sentences_split_very_long_at_comma():
    words = " ".join(["gato"] * 20)
    text = words + ", " + " ".join(["perro"] * 20) + "."
    out, _ = feed("Va. " + text)
    parts = [p for _, p in out]
    assert len(parts) >= 2 and all(len(p.split()) <= 32 for p in parts)
    assert " ".join(parts) == "Va. " + text


def test_sentences_markers_fact_and_action():
    out, s = feed("[feliz, dance]\nAnotado, Ana la futbolera. Yo solo pateo moscas.\n[dato] El usuario se llama Ana", step=4)
    assert (s.mood, s.action, s.fact) == ("happy", "dance", "El usuario se llama Ana")
    assert all("[" not in p and "dato" not in p for _, p in out)
    assert " ".join(p for _, p in out) == "Anotado, Ana la futbolera. Yo solo pateo moscas."


def test_sentences_without_mood_and_flush_tail():
    out, s = feed("sin punto final al terminar")
    assert s.mood == "sarcastic" and [p for _, p in out] == ["sin punto final al terminar"]


class StreamLLM(FakeLLM):
    def __init__(self, chunks=None, gate=None, fail_after=None):
        super().__init__()
        self.chunks = list(chunks or [])
        self.gate = gate
        self.fail_after = fail_after
        self.streams: list[list[dict]] = []
        self.closed = False

    async def stream(self, messages, factual=False):
        self.factual = factual
        self.streams.append(messages)
        try:
            for i, chunk in enumerate(self.chunks):
                if self.gate is not None and i == 1:
                    await self.gate.wait()
                if self.fail_after is not None and i >= self.fail_after:
                    raise httpx.ReadError("se cayó")
                await asyncio.sleep(0)
                yield chunk
        finally:
            self.closed = True


def kinds(outbox):
    return [m["type"] for m in outbox]


async def test_stream_emits_start_parts_end_and_remembers(make_brain, outbox, memory):
    llm = StreamLLM(["[happy]", " Es Can", "berra, no", " Sídney. ", "Todos caen", ".\n[dato] Al usuario le gusta la geografía"])
    brain = make_brain(llm)
    await brain.handle({"type": "chat", "text": "¿capital de Australia?"})
    assert kinds(outbox) == ["thinking", "thinking", "say_start", "say_part", "say_part", "say_end"]
    sid = outbox[2]["id"]
    assert outbox[2] == say_start(sid, "happy")
    assert outbox[3] == say_part(sid, "Es Canberra, no Sídney.")
    assert outbox[4] == say_part(sid, "Todos caen.")
    assert outbox[5] == say_end(sid, "none")
    assert memory.recent_messages(5) == [("user", "¿capital de Australia?"), ("sapo", "Es Canberra, no Sídney. Todos caen.")]
    assert memory.facts() == []
    system = llm.streams[0][0]["content"]
    assert "objeto JSON" not in system and "[happy]" in system
    assert llm.calls == []


async def test_stream_keeps_fact_only_when_user_talks_about_himself(make_brain, memory):
    brain = make_brain(StreamLLM(["[happy] Dylan el futbolero, anotado.\n[dato] El usuario se llama Dylan."]))
    await brain.handle({"type": "chat", "text": "Soy Dylan y me encanta el fútbol"})
    assert memory.facts() == ["El usuario se llama Dylan"]


async def test_stream_history_is_plain_text_and_verified_kept(make_brain, memory):
    memory.add_message("user", "hola")
    memory.add_message("sapo", "Qué onda")
    llm = StreamLLM(["Son 391, fácil."])
    brain = make_brain(llm)
    await brain.handle({"type": "chat", "text": "17 por 23"})
    msgs = llm.streams[0]
    assert msgs[1:3] == [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "Qué onda"}]
    assert "Dato verificado" in msgs[-1]["content"] and "391" in msgs[-1]["content"]


async def test_stream_empty_says_canned_error(make_brain, outbox, persona):
    brain = make_brain(StreamLLM([]))
    await brain.handle({"type": "chat", "text": "hola"})
    assert "say_start" not in kinds(outbox)
    says = [m for m in outbox if m["type"] == "say"]
    assert len(says) == 1 and says[0]["text"] in persona.strings["canned"]["error"]


async def test_stream_failure_midway_keeps_parts(make_brain, outbox, memory):
    brain = make_brain(StreamLLM(["Primera frase completa. ", "otra", "más"], fail_after=1))
    await brain.handle({"type": "chat", "text": "hola"})
    assert kinds(outbox)[-3:] == ["say_start", "say_part", "say_end"]
    assert memory.recent_messages(2)[-1] == ("sapo", "Primera frase completa.")


async def test_stream_total_is_capped(make_brain, outbox):
    brain = make_brain(StreamLLM(["Esta frase es bastante larga para llenar todo. "] * 30))
    await brain.handle({"type": "chat", "text": "habla mucho"})
    parts = [m["text"] for m in outbox if m["type"] == "say_part"]
    assert len(" ".join(parts)) <= MAX_SAY
    assert outbox[-1]["type"] == "say_end"


async def test_hush_cancels_stream(make_brain, outbox, memory):
    gate = asyncio.Event()
    llm = StreamLLM(["Primera frase ya lista. ", "Esto nunca sale."], gate=gate)
    brain = make_brain(llm)
    chat = asyncio.create_task(brain.handle({"type": "chat", "text": "cuéntame"}))
    for _ in range(100):
        if "say_part" in kinds(outbox):
            break
        await asyncio.sleep(0.01)
    assert brain.streaming is not None
    await brain.handle({"type": "hush"})
    await asyncio.wait_for(chat, 2)
    assert llm.closed
    assert [m["text"] for m in outbox if m["type"] == "say_part"] == ["Primera frase ya lista."]
    assert outbox[-1]["type"] == "say_end" and outbox[-1]["action"] == "none"
    assert "say" not in kinds(outbox)
    assert memory.recent_messages(2)[-1] == ("sapo", "Primera frase ya lista.")
    assert brain.streaming is None and brain.hush() is False


async def test_hush_before_first_token_is_silent(make_brain, outbox):
    gate = asyncio.Event()
    llm = StreamLLM(["", "nunca"], gate=gate)
    brain = make_brain(llm)
    chat = asyncio.create_task(brain.handle({"type": "chat", "text": "hola"}))
    for _ in range(100):
        if brain.streaming is not None:
            break
        await asyncio.sleep(0.01)
    await asyncio.sleep(0.02)
    assert brain.hush() is True
    await asyncio.wait_for(chat, 2)
    assert kinds(outbox) == ["thinking", "thinking"]


async def test_tools_text_stays_one_piece(make_brain, outbox):
    llm = StreamLLM(["no"])
    brain = make_brain(llm, tools=types.SimpleNamespace())
    assert brain.streams("abre spotify") is False
    assert brain.streams("¿quién pintó la Mona Lisa?") is True


async def test_phone_joins_parts_without_say_messages(make_brain, outbox, memory):
    brain = make_brain(StreamLLM(["[curious] Leonardo da Vinci. ", "Por cierto, ", "sonríe raro."]))
    text = await brain.on_phone("¿quién pintó la Mona Lisa?")
    assert text == "Leonardo da Vinci. Por cierto, sonríe raro."
    assert not {"say_start", "say_part", "say_end", "say"} & set(kinds(outbox))
    assert memory.recent_messages(2)[-1] == ("sapo", text)


async def test_chat_prompt_under_800_tokens(make_brain, memory):
    for i in range(20):
        memory.add_fact(f"El usuario tiene el dato número {i} bastante largo sobre sus gustos y su escuela")
    for i in range(10):
        memory.add_message("user", "pregunta larga de relleno " * 20)
        memory.add_message("sapo", "respuesta larga de relleno " * 20)
    llm = StreamLLM(["Ok, va."])
    brain = make_brain(llm)
    await brain.handle({"type": "chat", "text": "¿qué onda?"})
    msgs = llm.streams[0]
    assert len(msgs[0]["content"]) / 4 < 600
    assert sum(len(m["content"]) for m in msgs) / 4 < 800


def ndjson(*parts):
    lines = [json.dumps({"message": {"content": p}, "done": False}) for p in parts]
    lines.append(json.dumps({"message": {"content": ""}, "done": True}))
    return ("\n".join(lines) + "\n").encode()


def sse(*parts):
    return "".join(f"data: {json.dumps({'candidates': [{'content': {'parts': [{'text': p}]}}]})}\r\n\r\n" for p in parts).encode()


def make_router(ollama_handler, gemini_handler=None):
    ollama = Ollama("http://ollama.test", client=httpx.AsyncClient(transport=httpx.MockTransport(ollama_handler)))
    gemini = Gemini(lambda: "k", client=httpx.AsyncClient(transport=httpx.MockTransport(gemini_handler))) if gemini_handler else None
    return Router(pick_profile(Settings(), vram=8151), ollama, gemini=gemini)


async def collect(router, messages=None):
    return [c async for c in router.stream(messages or [{"role": "system", "content": "sapo"}, {"role": "user", "content": "hola"}])]


async def test_router_streams_ollama_plain():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=ndjson("[happy] Hola", ", qué tal."))

    router = make_router(handler, lambda r: httpx.Response(500))
    assert "".join(await collect(router)) == "[happy] Hola, qué tal."
    body = seen[0]
    assert body["stream"] is True and body["think"] is False and body["keep_alive"] == -1
    assert "format" not in body and body["model"] == "qwen3.5:4b"
    assert router.last == "ollama"


async def test_router_falls_back_to_cloud_when_ollama_slow():
    cloud = []

    async def slow(request):
        await asyncio.sleep(3)
        return httpx.Response(200, content=ndjson("tarde"))

    def gemini(request):
        cloud.append(request)
        return httpx.Response(200, content=sse("[happy] Es ", "Canberra."))

    router = make_router(slow, gemini)
    router.first_token = 0.1
    started = asyncio.get_running_loop().time()
    assert "".join(await collect(router)) == "[happy] Es Canberra."
    assert asyncio.get_running_loop().time() - started < 1.5
    req = cloud[0]
    assert req.url.path.endswith(f"/models/{CLOUD_STREAM[0]}:streamGenerateContent") and req.url.params["alt"] == "sse"
    body = json.loads(req.content)
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "minimal"}
    assert body["systemInstruction"]["parts"][0]["text"] == "sapo"
    assert router.last == "gemini"


async def test_router_cloud_rotates_models_on_429():
    paths = []

    def down(request):
        raise httpx.ConnectError("apagado")

    def gemini(request):
        paths.append(request.url.path)
        if CLOUD_STREAM[0] in request.url.path:
            return httpx.Response(429, json={"error": "cuota"})
        return httpx.Response(200, content=sse("desde lite"))

    router = make_router(down, gemini)
    assert await collect(router) == ["desde lite"]
    assert [p.rsplit("/", 1)[-1] for p in paths] == [f"{m}:streamGenerateContent" for m in CLOUD_STREAM[:2]]
    assert CLOUD_STREAM[0] in router.model_retry


async def test_router_game_goes_cloud_first():
    olog = []

    def ollama(request):
        olog.append(request.url.path)
        return httpx.Response(200, content=ndjson("local"))

    router = make_router(ollama, lambda r: httpx.Response(200, content=sse("nube")))
    await router.set_game(True)
    assert await collect(router) == ["nube"]
    assert "/api/chat" not in olog


async def test_router_game_without_cloud_uses_small_local():
    seen = []

    def ollama(request):
        seen.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, content=ndjson("local"))

    router = make_router(ollama)
    await router.set_game(True)
    assert await collect(router) == ["local"]
    assert seen[-1][1]["model"] == "qwen3.5:2b"


async def test_router_raises_when_everything_fails():
    def down(request):
        raise httpx.ConnectError("apagado")

    router = make_router(down)
    try:
        await collect(router)
    except httpx.ConnectError:
        pass
    else:
        raise AssertionError("debió fallar")


async def test_watchdog_relaunches_and_preloads():
    state = {"up": False, "launched": 0}
    log = []

    def handler(request):
        if not state["up"]:
            raise httpx.ConnectError("apagado")
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "x"})
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": []})
        log.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={})

    def launcher():
        state["launched"] += 1
        state["up"] = True
        return True

    ollama = Ollama("http://127.0.0.1:11434", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), launcher=launcher)
    router = Router(pick_profile(Settings(), vram=8151), ollama)
    assert await router.check() is True
    assert state["launched"] == 1
    assert log == [("/api/generate", {"model": "qwen3.5:4b", "keep_alive": -1})]
    assert await router.check(full=True) is True
    assert state["launched"] == 1 and len(log) == 2
    task = asyncio.create_task(router.watchdog(every=0.01, preload_every=0.01))
    await asyncio.sleep(0.1)
    task.cancel()
    assert len(log) > 2


def test_launch_ollama_sets_env(monkeypatch):
    got = {}

    def fake_popen(args, **kw):
        got["args"] = args
        got["env"] = kw.get("env")

    monkeypatch.setattr(llm_mod, "ollama_exe", lambda: "ollama.exe")
    monkeypatch.setattr(llm_mod.subprocess, "Popen", fake_popen)
    assert launch_ollama() is True
    assert got["args"] == ["ollama.exe", "serve"]
    assert {k: got["env"][k] for k in OLLAMA_ENV} == {"OLLAMA_KV_CACHE_TYPE": "q8_0", "OLLAMA_FLASH_ATTENTION": "1"}


def test_protocol_stream_messages():
    assert decode(json.dumps({"type": "hush", "extra": 1})) == {"type": "hush"}
    assert relayed({"type": "hush", "x": 2}) == {"type": "hush"}
    assert say_start("7", "raro") == {"type": "say_start", "id": "7", "mood": "sarcastic"}
    assert say_part("1", "  hola \n  mundo ") == {"type": "say_part", "id": "1", "text": "hola mundo"}
    assert len(say_part("1", "x" * 500)["text"]) == MAX_SAY
    assert say_end("1", "volar") == {"type": "say_end", "id": "1", "action": "none"}
    assert say_end("1", "dance")["action"] == "dance"


async def test_server_relays_hush_to_brain_and_other_clients(make_brain):
    hub = Hub()
    brain = make_brain(FakeLLM())
    hushed = asyncio.Event()
    brain.hush = lambda: hushed.set() or True
    async with serve(make_handler(brain, hub), "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}") as godot, connect(f"ws://127.0.0.1:{port}") as voice:
            for _ in range(100):
                if len(hub.clients) == 2:
                    break
                await asyncio.sleep(0.01)
            await godot.send(json.dumps({"type": "hush"}))
            assert json.loads(await asyncio.wait_for(voice.recv(), 2)) == {"type": "hush"}
            await asyncio.wait_for(hushed.wait(), 2)
            try:
                await asyncio.wait_for(godot.recv(), 0.2)
            except TimeoutError:
                pass
            else:
                raise AssertionError("el que manda hush no debe recibirlo")


def test_asks_fact_detects_questions():
    from sapo.facts import asks_fact
    for q in ["cual es la capital de australia", "¿quién pintó la Mona Lisa?", "oye sapo cuánto es 17 por 23", "dime un dato curioso", "como hago un huevo"]:
        assert asks_fact(q), q
    for q in ["hola sapo", "estoy cansado", "jaja que chistoso", "ya me voy a dormir"]:
        assert not asks_fact(q), q


async def test_question_goes_to_cloud_first(make_brain, outbox):
    llm = StreamLLM(["[happy] Es Canberra."])
    brain = make_brain(llm)
    await brain.handle({"type": "chat", "text": "cual es la capital de australia?"})
    assert llm.factual is True
    await brain.handle({"type": "chat", "text": "estoy aburrido"})
    assert llm.factual is False
