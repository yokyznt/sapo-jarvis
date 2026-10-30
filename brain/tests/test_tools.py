import asyncio
import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from sapo.chat import Activity, confirm_command
from sapo.config import Settings
from sapo.hardware import pick_profile
from sapo.llm import Ollama, Router
from sapo.pc import Window, best_match
from sapo.protocol import ProtocolError, decode
from sapo.tools import Toolbox, find_window, parse_yes_no, wants_tools
from tests.conftest import FakeLLM

NOW = datetime(2026, 10, 25, 8, 0)


class FakePC:
    def __init__(self, root: Path):
        self.root = root
        self.calls: list[tuple] = []
        self.level = 50
        self.muted = False
        self.clip = "hola portapapeles"
        self.apps = {"Spotify", "Google Chrome", "Visual Studio Code"}
        self.wins = [
            Window(1, "YouTube - Google Chrome", "chrome.exe"),
            Window(2, "Sin título: Bloc de notas", "notepad.exe"),
            Window(3, "sapo-jarvis - Visual Studio Code", "Code.exe"),
        ]
        for key in ("home", "desktop", "documents", "downloads", "pictures", "music", "videos"):
            (root / key).mkdir(parents=True, exist_ok=True)

    def open_app(self, name):
        hit = best_match(name, sorted(self.apps))
        if hit is None:
            raise LookupError(name)
        self.calls.append(("open_app", hit))
        return hit

    def open_url(self, url):
        self.calls.append(("open_url", url))

    def open_path(self, path):
        self.calls.append(("open_path", path))

    def folder(self, key):
        return self.root / key

    def volume(self):
        return self.level, self.muted

    def set_volume(self, percent):
        self.calls.append(("set_volume", percent))
        self.level = percent

    def set_mute(self, on):
        self.calls.append(("set_mute", on))
        self.muted = on

    def media_key(self, action):
        self.calls.append(("media", action))

    def clipboard(self):
        return self.clip

    def set_clipboard(self, text):
        self.calls.append(("set_clipboard", text))
        self.clip = text

    def windows(self):
        return list(self.wins)

    def window_do(self, hwnd, action):
        self.calls.append(("window", hwnd, action))

    def screenshot(self):
        self.calls.append(("screenshot",))
        return b"\xff\xd8jpeg"

    def lock(self):
        self.calls.append(("lock",))

    def power(self, action):
        self.calls.append(("power", action))

    def trash(self, path):
        self.calls.append(("trash", path))


async def instant(_seconds):
    await asyncio.sleep(0)


@pytest.fixture
def pc(tmp_path):
    return FakePC(tmp_path)


@pytest.fixture
def seen():
    return []


@pytest.fixture
def box(pc, seen):
    async def see(image, prompt):
        seen.append((image, prompt))
        return "Se ve VS Code con código Python y Chrome con YouTube."

    return Toolbox(pc, see=see, now=lambda: NOW, sleep=instant)


def yes(answer=True, log=None):
    async def ask(question):
        if log is not None:
            log.append(question)
        return answer

    return ask


def test_specs_are_valid(box):
    specs = box.specs()
    names = [s["function"]["name"] for s in specs]
    assert len(names) == len(set(names)) == 18
    for s in specs:
        params = s["function"]["parameters"]
        assert s["type"] == "function" and params["type"] == "object"
        assert set(params["required"]) <= set(params["properties"])
    assert {t.name for t in box.tools.values() if t.confirms} == {"close_window", "power", "delete_file"}


def test_helpers():
    assert best_match("spoti", ["Spotify", "Steam"]) == "Spotify"
    assert best_match("chrome", ["Google Chrome", "Chrome Remote Desktop Host"]) == "Google Chrome"
    assert best_match("vs code", ["Visual Studio Code"]) is None
    assert best_match("calculadora", ["Calculadora", "Calendario"]) == "Calculadora"
    assert best_match("crhome", ["Chrome"]) == "Chrome"
    assert parse_yes_no("Sí, apágala") is True
    assert parse_yes_no("dale") is True
    assert parse_yes_no("no, mejor no") is False
    assert parse_yes_no("mejor no") is False
    assert parse_yes_no("qué hora es") is None
    ws = [Window(1, "YouTube - Google Chrome", "chrome.exe"), Window(2, "Sin título: Bloc de notas", "notepad.exe")]
    assert find_window(ws, "chrome").hwnd == 1
    assert find_window(ws, "notepad").hwnd == 2
    assert find_window(ws, "bloc de notas").hwnd == 2
    assert find_window(ws, "spotify") is None


async def test_time_volume_media(box, pc):
    assert (await box.run("get_time", {})).text == "domingo 25 de octubre de 2026, 08:00"
    assert (await box.run("volume", {"action": "up"})).text == "volumen: 60%"
    assert (await box.run("volume", {"action": "down", "percent": 80})).text == "volumen: 0%"
    assert (await box.run("volume", {"action": "set", "percent": 150})).text == "volumen: 100%"
    assert (await box.run("volume", {"action": "mute"})).text == "volumen: 100% (silenciado)"
    assert not (await box.run("volume", {"action": "set"})).ok
    assert (await box.run("media", '{"action": "next"}')).ok
    assert ("media", "next") in pc.calls
    assert not (await box.run("media", {"action": "rewind"})).ok
    assert not (await box.run("nope", {})).ok


async def test_open_things(box, pc, tmp_path):
    assert (await box.run("open_app", {"name": "spotify"})).text == "ok: abrí Spotify"
    r = await box.run("open_app", {"name": "photoshop"})
    assert not r.ok and "photoshop" in r.text
    await box.run("open_url", {"url": "github.com"})
    await box.run("web_search", {"query": "clima en Monterrey"})
    assert ("open_url", "https://github.com") in pc.calls
    assert ("open_url", "https://duckduckgo.com/?q=clima+en+Monterrey") in pc.calls
    assert not (await box.run("open_url", {"url": "no es url"})).ok
    assert (await box.run("open_folder", {"name": "Descargas"})).ok
    assert ("open_path", tmp_path / "downloads") in pc.calls
    assert not (await box.run("open_folder", {"name": "carpeta que no existe"})).ok


async def test_note_and_clipboard(box, pc, tmp_path):
    r = await box.run("create_note", {"text": "comprar moscas", "title": "súper/lista"})
    path = tmp_path / "documents" / "Sapo" / "2026-10-25 0800 súperlista.txt"
    assert r.ok and path.read_text(encoding="utf-8") == "comprar moscas\n"
    assert (await box.run("create_note", {"text": "otra", "title": "súper/lista"})).ok
    assert path.with_name("2026-10-25 0800 súperlista 2.txt").exists()
    assert not (await box.run("create_note", {"text": " "})).ok
    assert (await box.run("clipboard_read", {})).text == "portapapeles: hola portapapeles"
    await box.run("clipboard_write", {"text": "croac"})
    assert pc.clip == "croac"


async def test_windows(box, pc):
    r = await box.run("list_windows", {})
    assert "YouTube - Google Chrome (chrome.exe)" in r.text and "Bloc de notas" in r.text
    assert (await box.run("window", {"action": "minimize", "title": "chrome"})).ok
    assert ("window", 1, "minimize") in pc.calls
    assert not (await box.run("window", {"action": "focus", "title": "spotify"})).ok
    asked = []
    r = await box.run("close_window", {"title": "notepad"}, ask=yes(False, asked))
    assert r.text.startswith("cancelado") and asked == ["¿Cierro «Sin título: Bloc de notas»?"]
    assert ("window", 2, "close") not in pc.calls
    assert (await box.run("close_window", {"title": "notepad"})).text.startswith("cancelado")
    assert (await box.run("close_window", {"title": "notepad"}, ask=yes())).ok
    assert ("window", 2, "close") in pc.calls


async def test_power_and_trash_need_confirmation(box, pc, tmp_path):
    assert (await box.run("power", {"action": "shutdown"}, ask=yes(False))).text.startswith("cancelado")
    assert not any(c[0] == "power" for c in pc.calls)
    assert (await box.run("power", {"action": "restart"}, ask=yes())).ok
    assert ("power", "restart") in pc.calls
    target = tmp_path / "desktop" / "basura.txt"
    target.write_text("x")
    asked = []
    assert (await box.run("delete_file", {"path": "basura.txt"}, ask=yes(False, asked))).text.startswith("cancelado")
    assert asked == ["¿Mando «basura.txt» a la papelera?"]
    assert (await box.run("delete_file", {"path": "basura.txt"}, ask=yes())).ok
    assert ("trash", target) in pc.calls
    for path in ("documentos", str(tmp_path / "home"), "C:/Windows/System32/drivers", "C:/"):
        r = await box.run("delete_file", {"path": path}, ask=yes())
        assert not r.ok, path
    assert not (await box.run("delete_file", {"path": "fantasma.txt"}, ask=yes())).ok
    assert sum(1 for c in pc.calls if c[0] == "trash") == 1


async def test_game_mode_blocks_desktop(box, pc):
    for name, args in [("open_app", {"name": "spotify"}), ("media", {"action": "next"}), ("screen", {}), ("window", {"action": "focus", "title": "chrome"}), ("lock_pc", {})]:
        r = await box.run(name, args, game=True)
        assert r.blocked and not r.ok
    assert pc.calls == []
    assert (await box.run("get_time", {}, game=True)).ok
    assert (await box.run("volume", {"action": "get"}, game=True)).ok
    assert (await box.run("list_windows", {}, game=True)).ok


async def test_screen_uses_vision(box, pc, seen):
    r = await box.run("screen", {"question": "¿qué video es?"})
    assert r.text.startswith("pantalla: Se ve VS Code")
    assert seen[0][0] == b"\xff\xd8jpeg" and "qué video es" in seen[0][1]
    assert not (await Toolbox(pc).run("screen", {})).ok


async def test_timer(box):
    fired = []

    async def notify(text):
        fired.append(text)

    box.notify = notify
    r = await box.run("set_timer", {"minutes": 5, "text": "sacar la pizza"})
    assert r.text == "listo: aviso a las 08:05 (5.0 min): sacar la pizza"
    r = await box.run("set_timer", {"at": "7:30", "text": "junta"})
    assert "07:30 (1410.0 min)" in r.text
    await asyncio.gather(*box.timers)
    assert fired == ["sacar la pizza", "junta"]
    assert not (await box.run("set_timer", {"at": "25:00", "text": "x"})).ok
    assert not (await box.run("set_timer", {"minutes": -1, "text": "x"})).ok
    assert not (await box.run("set_timer", {"text": "x"})).ok


class ToolLLM(FakeLLM):
    def __init__(self, steps, replies=None):
        super().__init__(replies)
        self.steps = list(steps)
        self.tool_calls: list[list[dict]] = []

    async def chat_tools(self, messages, tools):
        self.tool_calls.append([dict(m) for m in messages])
        assert tools and all(t["type"] == "function" for t in tools)
        return self.steps.pop(0) if self.steps else {"role": "assistant", "content": json.dumps({"say": "Ya", "mood": "happy", "action": "none"})}

    async def complete(self, messages, lite=False):
        self.calls.append(messages)
        if self.steps:
            return self.steps.pop(0)["content"]
        return json.dumps({"say": "Croac falso", "mood": "happy", "action": "none"})


def call(tool, **args):
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": tool, "arguments": args}}]}


def answer(text):
    return {"role": "assistant", "content": json.dumps({"say": text, "mood": "sarcastic", "action": "none"})}


async def test_brain_runs_tool_and_answers(make_brain, outbox, box, memory):
    llm = ToolLLM([call("get_time"), answer("Son las 8, madrugador.")])
    brain = make_brain(llm, tools=box)
    await brain.handle({"type": "chat", "text": "qué hora es"})
    second = llm.calls[0]
    assert len(llm.tool_calls) == 1
    assert second[-3]["tool_calls"][0]["function"]["name"] == "get_time"
    assert second[-2] == {"role": "tool", "tool_name": "get_time", "content": "domingo 25 de octubre de 2026, 08:00"}
    assert second[-1]["role"] == "user" and "RESULTADO" in second[-1]["content"]
    assert {"type": "say", "text": "Son las 8, madrugador.", "mood": "sarcastic"} in outbox
    assert outbox[-1]["type"] == "say" and {"type": "thinking", "on": False} in outbox
    assert memory.recent_messages(2) == [("user", "qué hora es"), ("sapo", "Son las 8, madrugador.")]


async def test_brain_plain_chat_without_tools(make_brain, outbox, box):
    llm = ToolLLM([answer("Nomás aquí, croando.")])
    brain = make_brain(llm, tools=box)
    await brain.handle({"type": "chat", "text": "qué haces"})
    assert llm.tool_calls == [] and len(llm.calls) == 1
    llm.steps = [answer("borrador frío"), answer("Ni idea, yo nomás croo.")]
    await brain.handle({"type": "chat", "text": "abre tu corazón"})
    assert len(llm.tool_calls) == 1 and len(llm.calls) == 2
    assert outbox[-1] == {"type": "say", "text": "Ni idea, yo nomás croo.", "mood": "sarcastic"}


async def wait_confirm(outbox):
    for _ in range(200):
        found = [m for m in outbox if m["type"] == "confirm"]
        if found:
            return found[-1]
        await asyncio.sleep(0.01)
    raise AssertionError("no llegó confirm")


async def test_brain_confirm_reply_yes(make_brain, outbox, box, pc):
    llm = ToolLLM([call("power", action="shutdown"), answer("Bye, me apago contigo.")])
    brain = make_brain(llm, tools=box)
    task = asyncio.create_task(brain.handle({"type": "chat", "text": "apaga la compu"}))
    msg = await wait_confirm(outbox)
    assert msg["text"] == "¿Apago la compu?" and msg["id"]
    assert not any(c[0] == "power" for c in pc.calls)
    await brain.handle(decode(json.dumps({"type": "confirm_reply", "id": msg["id"], "ok": True})))
    await task
    assert ("power", "shutdown") in pc.calls
    assert llm.calls[0][-2]["content"] == "ok: shutdown en marcha"
    assert brain.pending == {}


async def test_brain_confirm_by_chat_no(make_brain, outbox, box, pc, memory):
    llm = ToolLLM([call("close_window", title="chrome"), answer("Va, no lo cierro.")])
    brain = make_brain(llm, tools=box)
    task = asyncio.create_task(brain.handle({"type": "chat", "text": "cierra chrome"}))
    await wait_confirm(outbox)
    await brain.handle({"type": "chat", "text": "no, déjalo"})
    await task
    assert not any(c[0] == "window" for c in pc.calls)
    assert llm.calls[0][-2]["content"] == "cancelado: el usuario no confirmó"
    assert ("user", "no, déjalo") not in memory.recent_messages(10)


async def test_brain_confirm_by_chat_yes(make_brain, outbox, box, pc, tmp_path):
    (tmp_path / "downloads" / "viejo.zip").write_text("x")
    llm = ToolLLM([call("delete_file", path="viejo.zip"), answer("A la papelera.")])
    brain = make_brain(llm, tools=box)
    task = asyncio.create_task(brain.handle({"type": "chat", "text": "borra viejo.zip"}))
    await wait_confirm(outbox)
    await brain.handle({"type": "chat", "text": "sí"})
    await task
    assert ("trash", tmp_path / "downloads" / "viejo.zip") in pc.calls


async def test_brain_confirm_timeout_cancels(make_brain, outbox, box, pc):
    llm = ToolLLM([call("power", action="restart"), answer("Ni modo.")])
    brain = make_brain(llm, tools=box, confirm_timeout=0.05)
    await brain.handle({"type": "chat", "text": "reinicia"})
    assert any(m["type"] == "confirm" for m in outbox)
    assert not any(c[0] == "power" for c in pc.calls)
    assert llm.calls[0][-2]["content"] == "cancelado: el usuario no confirmó"
    assert brain.pending == {}


async def test_brain_other_chat_cancels_pending(make_brain, outbox, box, pc):
    llm = ToolLLM([call("power", action="sleep"), answer("Ok, no."), answer("Son las 8.")])
    brain = make_brain(llm, tools=box)
    task = asyncio.create_task(brain.handle({"type": "chat", "text": "suspende"}))
    await wait_confirm(outbox)
    await brain.handle({"type": "chat", "text": "mejor dime la hora"})
    await task
    assert not any(c[0] == "power" for c in pc.calls)
    assert len(llm.tool_calls) == 2 and len(llm.calls) == 2


async def test_brain_game_mode_says_not_now(make_brain, outbox, box, pc, persona):
    llm = ToolLLM([call("open_app", name="spotify")])
    brain = make_brain(llm, tools=box)
    await brain.handle({"type": "event", "name": "game_on", "boredom": 0.0})
    await brain.handle({"type": "chat", "text": "abre spotify"})
    assert pc.calls == []
    assert len(llm.tool_calls) == 1
    assert outbox[-1]["text"] in persona.strings["canned"]["game_block"]


async def test_brain_reminder_fires(make_brain, outbox, box):
    llm = ToolLLM([call("set_timer", minutes=1, text="estirarte"), answer("Te aviso en un minuto.")])
    brain = make_brain(llm, tools=box)
    await brain.handle({"type": "chat", "text": "recuérdame estirarme en un minuto"})
    await asyncio.gather(*box.timers)
    assert {"type": "say", "text": "¡Oye! Acuérdate: estirarte", "mood": "curious"} in outbox
    assert outbox[-1] == {"type": "action", "name": "jump"}


async def test_brain_ignores_unknown_tool(make_brain, outbox, box, pc):
    llm = ToolLLM([call("say", say="hola"), answer("Aquí ando.")])
    brain = make_brain(llm, tools=box)
    await brain.handle({"type": "chat", "text": "abre algo"})
    assert pc.calls == [] and len(llm.calls) == 1
    assert outbox[-1] == {"type": "say", "text": "Aquí ando.", "mood": "sarcastic"}


async def test_brain_tool_error_reported(make_brain, outbox, box):
    llm = ToolLLM([call("open_app", name="photoshop"), {"role": "assistant", "content": ""}])
    brain = make_brain(llm, tools=box)
    await brain.handle({"type": "chat", "text": "abre photoshop"})
    assert llm.calls[0][-2]["content"] == "error: no encontré la app photoshop"
    assert outbox[-1]["type"] == "say" and outbox[-1]["text"]


def test_wants_tools(persona):
    words = persona.strings["tool_words"]
    for text in ("qué hora es", "Ábreme Spotify", "súbele al volumen", "recuérdame la junta", "qué hay en mi pantalla", "busca recetas", "abre github.com", "pon la siguiente canción", "apaga la compu"):
        assert wants_tools(text, words), text
    for text in ("hola sapo", "cuéntame un chiste", "qué onda, cómo estás", "me llamo Ana", "ahora no"):
        assert not wants_tools(text, words), text


def test_protocol_confirm_reply():
    assert decode('{"type":"confirm_reply","id":"ab12","ok":false}') == {"type": "confirm_reply", "id": "ab12", "ok": False}
    for raw in ('{"type":"confirm_reply","id":"x"}', '{"type":"confirm_reply","id":"","ok":true}', '{"type":"confirm_reply","id":"x","ok":"si"}'):
        with pytest.raises(ProtocolError):
            decode(raw)


def test_chat_confirm_command():
    a = Activity()
    assert confirm_command("hola", a) is None
    assert confirm_command("/si", a) == {"type": "chat", "text": "sí"}
    a.confirm = "abc"
    assert confirm_command("/no", a) == {"type": "confirm_reply", "id": "abc", "ok": False}
    assert a.confirm is None


async def test_ollama_tools_and_vision_bodies():
    log = []

    def handler(request):
        body = json.loads(request.content)
        log.append(body)
        return httpx.Response(200, json={"message": {"role": "assistant", "tool_calls": [{"function": {"name": "get_time", "arguments": {}}}]}})

    ollama = Ollama("http://o", 120, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    router = Router(pick_profile(Settings(), vram=8151), ollama)
    tools = [{"type": "function", "function": {"name": "get_time", "parameters": {"type": "object", "properties": {}}}}]
    msg = await router.chat_tools([{"role": "user", "content": "hora"}], tools)
    assert msg["tool_calls"][0]["function"]["name"] == "get_time" and msg["content"] == ""
    assert log[0]["tools"] == tools and "format" not in log[0] and log[0]["think"] is False
    await router.see(b"img", "describe")
    assert log[1]["messages"][0]["images"] == ["aW1n"] and log[1]["model"] == "qwen3.5:4b"
    assert log[1]["options"]["num_predict"] == 260 and "tools" not in log[1]
