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

    def save_screenshot(self):
        self.calls.append(("save_screenshot",))
        return self.root / "Capturas del Sapo" / "captura 1.png"

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
    assert len(names) == len(set(names)) == 25
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
    for name, args in [("open_app", {"name": "spotify"}), ("screen", {}), ("window", {"action": "focus", "title": "chrome"}), ("lock_pc", {})]:
        r = await box.run(name, args, game=True)
        assert r.blocked and not r.ok
    r = await box.run("media", {"action": "next"}, game=True)
    assert not r.ok and "Spotify" in r.text
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
    said = [m for m in outbox if m["type"] in ("say", "say_part")]
    assert said and "photoshop" in said[-1]["text"]
    assert not any("abr" in m["text"].lower() and "no" not in m["text"].lower() for m in said)


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


async def test_take_screenshot_saves_file(box, pc):
    r = await box.run("take_screenshot", {})
    assert r.ok and "Capturas del Sapo/captura 1.png" in r.text
    assert ("save_screenshot",) in pc.calls


def test_app_renames():
    from sapo.pc import RENAMES
    assert RENAMES["vscode"] == "visual studio code" and RENAMES["wasap"] == "whatsapp"


async def test_open_app_falls_back_to_known_site(box):
    from sapo.tools import site_for
    assert site_for("YouTube") == "https://www.youtube.com"
    assert site_for("wikipedia.org") == "https://wikipedia.org"
    assert site_for("photoshop") is None
    r = await box.run("open_app", {"name": "YouTube"})
    assert r.ok and "youtube.com" in r.text
    r = await box.run("open_app", {"name": "photoshop"})
    assert not r.ok


async def test_weather_uses_city_and_tomorrow(pc, seen):
    from sapo.tools import Toolbox
    calls = []

    async def fetch(url, params):
        calls.append(url)
        if "geocoding" in url:
            return {"results": [{"latitude": 25.6, "longitude": -100.3, "name": "Monterrey"}]}
        return {
            "current": {"temperature_2m": 21.4, "weather_code": 0},
            "daily": {"weather_code": [0, 63], "temperature_2m_max": [30.2, 24.6], "temperature_2m_min": [18.0, 16.4], "precipitation_probability_max": [5, 80]},
        }

    box = Toolbox(pc, fetch=fetch)
    r = await box.run("weather", {"city": "Monterrey", "day": "mañana"})
    assert r.ok and "Monterrey mañana" in r.text and "con lluvia" in r.text and "80%" in r.text and "25 °C" in r.text
    r = await box.run("weather", {"city": "Monterrey"})
    assert r.ok and "ahorita 21 °C" in r.text and "despejado" in r.text


async def test_weather_without_internet_fails_softly(pc):
    import httpx
    from sapo.tools import Toolbox

    async def fetch(url, params):
        raise httpx.ConnectError("sin red")

    r = await Toolbox(pc, fetch=fetch).run("weather", {})
    assert not r.ok and "internet" in r.text


async def test_play_music_youtube_plays_first_video(pc):
    from sapo.tools import Toolbox

    async def fetch(url, params):
        return 'algo "videoId":"abcDEF12345" mas'

    box = Toolbox(pc, fetch=fetch)
    r = await box.run("play_music", {"query": "bad bunny"})
    assert r.ok and ("open_url", "https://www.youtube.com/watch?v=abcDEF12345") in pc.calls


def test_misheard_app_names_sound_like_real_ones():
    from sapo.pc import sounds_like
    names = ["Spotify", "Discord", "Fortnite", "WhatsApp", "Google Chrome", "Steam"]
    assert sounds_like("potitis", names) == "Spotify"
    assert sounds_like("disstoro", names) == "Discord"
    assert sounds_like("guasap", names) == "WhatsApp"
    assert sounds_like("calendario", names) is None


class FakeAgent:
    def __init__(self, ok=True, note="Bad Bunny - MONACO", steps=10, done_when=None):
        self.ok, self.note, self.steps, self.done_when, self.runs = ok, note, steps, done_when, []

    async def run(self, hwnd, goal):
        self.runs.append((hwnd, goal))
        return self.ok, self.note


def windowed(pc, *wins):
    from sapo.pc import Window
    pc.windows = lambda: [Window(i + 1, t, p) for i, (t, p) in enumerate(wins)]
    return pc


async def _old_spotify_play_searches_and_lets_agent_press_play(pc):
    from sapo.tools import Toolbox
    made = []

    def agent(steps, done_when=None):
        made.append(FakeAgent(steps=steps, done_when=done_when))
        return made[-1]

    windowed(pc, ("Spotify Free", "Spotify.exe"))
    box = Toolbox(pc, agent=agent, sleep=lambda s: asyncio.sleep(0), spotify=FakeSpotify(ok=False, note="sin cdp"))
    r = await box.run("play_music", {"query": "bad bunny monaco", "where": "spotify"})
    assert r.ok and "MONACO" in r.text
    assert ("open_url", "spotify:search:bad%20bunny%20monaco") in pc.calls
    check = made[0].done_when
    assert check("Bad Bunny - MONACO") and not check("Spotify Free") and not check("Peso Pluma - LADY GAGA")
    assert not check("Bad Bunny - BAILE INoLVIDABLE")


async def test_spotify_play_failure_is_honest(pc):
    from sapo.tools import Toolbox
    box = Toolbox(pc, sleep=lambda s: asyncio.sleep(0), spotify=FakeSpotify(ok=False, note="sin cdp"))
    r = await box.run("play_music", {"query": "rola rara", "where": "spotify"})
    assert not r.ok and "no pude ponerla en Spotify" in r.text


async def test_control_pc_uses_named_window(pc):
    from sapo.tools import Toolbox
    fake = FakeAgent(note="ya está abierto el video")
    windowed(pc, ("Hermes", "Hermes.exe"), ("YouTube - Brave", "brave.exe"))
    box = Toolbox(pc, agent=lambda steps, done_when=None: fake, sleep=lambda s: asyncio.sleep(0))
    r = await box.run("control_pc", {"goal": "abre el primer video", "app": "brave"})
    assert r.ok and fake.runs == [(2, "abre el primer video")]


def test_parse_step_and_mapping():
    from sapo.desktop import Shot, parse_step, to_screen
    s = parse_step('bla {"accion": "doble_click", "punto": [250, 500], "nota": "la canción"}')
    assert s.action == "doble_click" and s.point == (250.0, 500.0)
    assert to_screen(Shot(b"", 100, -800, 1000, 600), s.point) == (600, -650)
    assert parse_step('{"accion": "click", "x": 950, "y": 95}').point == (95.0, 950.0)
    assert parse_step("nada").action == "no_puedo"
    assert parse_step('{"accion": "hackear"}').action == "no_puedo"


async def test_agent_stops_on_danger_and_on_done():
    from sapo.desktop import DesktopAgent, Shot

    class H:
        def __init__(self, titles):
            self.titles, self.clicks = titles, []

        def alive(self, h):
            return True

        def title(self, h):
            return self.titles.pop(0) if len(self.titles) > 1 else self.titles[0]

        def shot(self, h):
            return Shot(b"", 0, 0, 1000, 1000)

        def click(self, x, y, double=False):
            self.clicks.append((x, y, double))

    async def see_pay(img, prompt):
        return '{"accion": "click", "punto": [10, 10], "nota": "botón para pagar premium"}'

    nap = lambda s: asyncio.sleep(0)
    ok, note = await DesktopAgent(H(["x"]), see_pay, lambda h: None, sleep=nap).run(1, "algo")
    assert not ok and "pagar" in note

    async def see_click(img, prompt):
        return '{"accion": "doble_click", "punto": [500, 500], "nota": "la canción"}'

    hands = H(["Spotify Free", "Bad Bunny - MONACO"])
    agent = DesktopAgent(hands, see_click, lambda h: None, sleep=nap, done_when=lambda t: "MONACO" in t)
    ok, note = await agent.run(1, "pon monaco")
    assert ok and note == "Bad Bunny - MONACO" and hands.clicks == [(500, 500, True)]


async def test_agent_double_checks_listo():
    from sapo.desktop import DesktopAgent, Shot

    class H:
        clicks = []

        def alive(self, h):
            return True

        def title(self, h):
            return "Spotify Free"

        def shot(self, h):
            return Shot(b"", 0, 0, 100, 100)

        def click(self, x, y, double=False):
            self.clicks.append((x, y))

    answers = iter([
        '{"accion": "listo", "nota": "ya está la página de Lady Gaga"}',
        '{"cumplido": false, "por_que": "es el álbum GÉNESIS de Peso Pluma"}',
        '{"accion": "click", "x": 300, "y": 900, "nota": "nombre del artista abajo"}',
        '{"accion": "listo", "nota": "página de Peso Pluma"}',
        '{"cumplido": true, "por_que": "página del artista Peso Pluma"}',
    ])
    prompts = []

    async def see(img, prompt):
        prompts.append(prompt)
        return next(answers)

    ok, note = await DesktopAgent(H(), see, lambda h: None, sleep=lambda s: asyncio.sleep(0)).run(1, "página del artista")
    assert ok and note == "página del artista Peso Pluma" and H.clicks == [(30, 90)]
    assert "NO se cumple" in prompts[2]


def test_find_window_prefers_the_app_over_a_browser_tab(pc):
    from sapo.tools import Toolbox
    windowed(pc, ("Spotify Advertising - Brave", "brave.exe"), ("Spotify Free", "Spotify.exe"))
    assert Toolbox(pc).find_window("spotify").process == "Spotify.exe"


async def test_agent_repeating_a_click_checks_if_already_done():
    from sapo.desktop import DesktopAgent, Shot

    class H:
        clicks = []

        def alive(self, h):
            return True

        def title(self, h):
            return "Spotify"

        def shot(self, h):
            return Shot(b"", 0, 0, 100, 100)

        def click(self, x, y, double=False):
            self.clicks.append((x, y))

    answers = iter([
        '{"accion": "click", "x": 305, "y": 352, "nota": "artista"}',
        '{"accion": "click", "x": 306, "y": 351, "nota": "artista otra vez"}',
        '{"cumplido": true, "por_que": "página de Manuel Turizo"}',
    ])

    async def see(img, prompt):
        return next(answers)

    ok, note = await DesktopAgent(H(), see, lambda h: None, sleep=lambda s: asyncio.sleep(0)).run(1, "página del artista")
    assert ok and "Manuel Turizo" in note and len(H.clicks) == 1


class FakeSpotify:
    def __init__(self, ok=True, note="MONACO - Bad Bunny", open_=True):
        self.ok, self.note, self.open_, self.played, self.pressed = ok, note, open_, [], []

    def installed(self):
        return True

    def pages(self):
        return [{"url": "xpui"}] if self.open_ else []

    async def play(self, query, sleep=None):
        self.played.append(query)
        return self.ok, self.note

    async def press(self, testid):
        self.pressed.append(testid)
        return True

    async def pause(self):
        self.pressed.append("pause")
        return True


async def test_music_while_gaming_uses_spotify_without_window(pc):
    from sapo.tools import Toolbox
    sp = FakeSpotify()
    box = Toolbox(pc, spotify=sp)
    r = await box.run("play_music", {"query": "monaco bad bunny"}, game=True)
    assert r.ok and "MONACO" in r.text and sp.played == ["monaco bad bunny"]
    assert not any(c[0] == "open_url" for c in pc.calls)
    r = await box.run("media", {"action": "next"}, game=True)
    assert r.ok and sp.pressed == ["control-button-skip-forward"]
    assert not any(c[0] == "media_key" for c in pc.calls)


async def test_music_while_gaming_fails_honestly(pc):
    from sapo.tools import Toolbox
    box = Toolbox(pc, spotify=FakeSpotify(ok=False, note="sin resultados"))
    r = await box.run("play_music", {"query": "rola rara"}, game=True)
    assert not r.ok and "sin resultados" in r.text
    r = await Toolbox(pc, spotify=FakeSpotify(open_=False)).run("media", {"action": "next"}, game=True)
    assert not r.ok and "Spotify" in r.text
    r = await Toolbox(pc, spotify=FakeSpotify()).run("control_pc", {"goal": "x"}, game=True)
    assert r.blocked


async def test_spotify_outside_game_prefers_hidden_player(pc):
    from sapo.tools import Toolbox
    sp = FakeSpotify()
    r = await Toolbox(pc, spotify=sp, agent=lambda steps, done_when=None: FakeAgent(False, "no")).run("play_music", {"query": "monaco", "where": "spotify"})
    assert r.ok and sp.played == ["monaco"]


async def test_spotify_failure_never_takes_the_window(pc):
    from sapo.tools import Toolbox
    agents = []
    box = Toolbox(pc, spotify=FakeSpotify(ok=False, note="sin resultados"), agent=lambda steps, done_when=None: agents.append(1) or FakeAgent())
    r = await box.run("play_music", {"query": "rola rara", "where": "spotify"})
    assert not r.ok and agents == [] and not any(c[0] in ("open_url", "window_do") for c in pc.calls)


def test_music_intent_finds_app_anywhere():
    from sapo.intents import music
    assert music("ponme una canción de Víctor Mendivil en Spotify") == {"query": "victor mendivil", "where": "spotify"}
    assert music("Abre Spotify y ponme una canción de Victor Mendivil")["where"] == "spotify"
    assert music("pon algo de peso pluma en youtube") == {"query": "peso pluma", "where": "youtube"}
    assert music("quiero escuchar tití me preguntó")["query"] == "titi me pregunto"
    for t in ("pon un temporizador de 5 minutos", "pon la siguiente", "pausa la música", "pon el volumen al 50", "ponme música"):
        assert music(t) is None


async def test_play_music_without_platform_prefers_spotify(pc):
    from sapo.tools import Toolbox
    sp = FakeSpotify()
    r = await Toolbox(pc, spotify=sp).run("play_music", {"query": "victor mendivil", "where": ""})
    assert r.ok and sp.played == ["victor mendivil"]


def test_music_controls_are_understood():
    from sapo.intents import control
    assert control("pausa la música") == "stop"
    assert control("oye sapo pausa") == "stop"
    assert control("pon la siguiente") == "next"
    assert control("la anterior") == "previous"
    assert control("sigue con la música") == "resume"
    assert control("ponme una canción de peso pluma") is None
    assert control("qué sigue en mi agenda de mañana por la tarde") is None


def test_pick_finds_your_spotify_things():
    from sapo.spotify import pick
    items = [
        {"uri": "spotify:playlist:1", "name": "she"},
        {"uri": "spotify:playlist:2", "name": "Tus Me Gusta"},
        {"uri": "spotify:playlist:3", "name": "Chill Underground Rap 2026"},
        {"uri": "spotify:album:4", "name": "La Jangada"},
        {"uri": "spotify:artist:5", "name": "Paulo Londra"},
    ]
    assert pick("she", items)["uri"] == "spotify:playlist:1"
    assert pick("mis me gusta", items)["name"] == "Tus Me Gusta"
    assert pick("chill underground rap", items)["uri"] == "spotify:playlist:3"
    assert pick("paulo londra", items)["uri"] == "spotify:artist:5"
    assert pick("monaco bad bunny", items) is None
    assert pick("victor mendivil", items) is None


def test_music_intent_understands_playlists():
    from sapo.intents import music
    assert music("pon mi playlist she") == {"query": "she", "where": ""}
    assert music("ponme mis me gusta en spotify")["query"] == "mis me gusta"
    assert music("pon la playlist chill underground rap")["query"] == "chill underground rap"
    assert music("pon el álbum la jangada")["query"] == "la jangada"


def test_library_questions_are_answered_not_acted():
    from sapo.intents import library_question
    assert library_question("qué playlists tengo en spotify")
    assert library_question("cuáles son mis playlists")
    assert library_question("dime qué álbumes tengo guardados")
    assert not library_question("pon mi playlist she")
    assert not library_question("abre spotify")


def test_library_summary_lists_your_things_short():
    from sapo.spotify import summary
    items = [{"uri": f"spotify:playlist:{i}", "name": f"lista {i}", "sub": "Playlist • yokyznt"} for i in range(40)]
    items += [{"uri": "spotify:playlist:x", "name": "♥️", "sub": "Playlist • yokyznt"}, {"uri": "spotify:album:1", "name": "La Jangada", "sub": "Álbum • Milo j"}]
    s = summary("qué playlists tengo", items)
    assert s.startswith("Tienes 41 playlists") and "lista 0" in s and "♥️" not in s and len(s) <= 280
    assert summary("cuáles son mis álbumes", items).startswith("Tienes 1 álbumes")
    assert "La Jangada" in summary("qué discos tengo guardados", items)
