import json

import pytest

from sapo.clips import ClipResult
from sapo.config import static_config
from sapo.files import read_drop, sensitive
from sapo.protocol import ProtocolError, decode
from sapo.tools import Toolbox, clip_seconds, wants_clip

from .conftest import FakeLLM
from .test_tools import FakePC


class FakeClipper:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or ClipResult("saved", None, 30.0)

    async def save(self, seconds=None):
        self.calls.append(seconds)
        return self.result


def calm_config():
    return static_config(blacklist=("bbva",), comment_minutes=10)


def test_decode_new_events():
    assert decode(json.dumps({"type": "event", "name": "file_drop", "path": " C:/a.txt "})) == {"type": "event", "name": "file_drop", "boredom": 0.0, "path": "C:/a.txt"}
    assert decode(json.dumps({"type": "event", "name": "win", "what": "battery_low"}))["what"] == "battery_low"
    for bad in (
        {"type": "event", "name": "file_drop"},
        {"type": "event", "name": "file_drop", "path": ""},
        {"type": "event", "name": "file_drop", "path": 3},
        {"type": "event", "name": "file_drop", "path": "x" * 2000},
        {"type": "event", "name": "win"},
        {"type": "event", "name": "win", "what": "explode"},
    ):
        with pytest.raises(ProtocolError):
            decode(json.dumps(bad))
    assert "path" not in decode(json.dumps({"type": "event", "name": "petted", "path": "C:/x"}))


def test_clip_words():
    assert wants_clip("oye sapo clipea eso")
    assert wants_clip("graba eso")
    assert wants_clip("guarda eso")
    assert wants_clip("clip")
    assert not wants_clip("guarda eso en una nota")
    assert not wants_clip("abre spotify")
    assert clip_seconds("clipea los últimos 45 segundos") == 45
    assert clip_seconds("clip de un minuto") == 60
    assert clip_seconds("clipea eso") is None


async def test_clip_tool_works_in_game_and_emits(tmp_path):
    clipper = FakeClipper(ClipResult("saved", tmp_path / "Sapo_1.mp4", 10.0))
    box = Toolbox(FakePC(tmp_path), clipper=clipper)
    sent = []

    async def emit(msg):
        sent.append(msg)

    box.emit = emit
    result = await box.run("clip", {"seconds": 10}, game=True)
    assert result.ok and not result.blocked
    assert "10 s" in result.text
    assert clipper.calls == [10]
    assert sent == [{"type": "clip", "state": "saved", "path": str(tmp_path / "Sapo_1.mp4"), "seconds": 10.0}]
    off = Toolbox(FakePC(tmp_path), clipper=FakeClipper(ClipResult("error", reason="off")))
    res = await off.run("clip", {})
    assert not res.ok and "apagados" in res.text


async def test_voice_clip_in_game_skips_llm(make_brain, outbox, tmp_path):
    llm = FakeLLM()
    clipper = FakeClipper(ClipResult("saved", tmp_path / "Sapo_2.mp4", 30.0))
    box = Toolbox(FakePC(tmp_path), clipper=clipper)
    brain = make_brain(llm, tools=box, config=calm_config())
    await brain.handle({"type": "event", "name": "game_on", "boredom": 0.0})
    outbox.clear()
    await brain.handle({"type": "chat", "text": "sapo clipea los últimos 20 segundos"})
    assert llm.calls == []
    assert clipper.calls == [20]
    assert outbox[0]["type"] == "clip" and outbox[0]["state"] == "saved"
    says = [m for m in outbox if m["type"] == "say"]
    assert len(says) == 1 and "30" in says[0]["text"]


async def test_voice_clip_when_off(make_brain, outbox, tmp_path):
    box = Toolbox(FakePC(tmp_path), clipper=FakeClipper(ClipResult("error", reason="off")))
    brain = make_brain(FakeLLM(), tools=box, config=calm_config())
    await brain.handle({"type": "chat", "text": "graba eso"})
    assert outbox[0] == {"type": "clip", "state": "error"}
    assert "Preferencias" in outbox[-1]["text"]


async def test_file_drop_summarizes_text(make_brain, outbox, tmp_path):
    note = tmp_path / "receta.txt"
    note.write_text("Chilaquiles: tortillas, salsa verde, crema y queso.", encoding="utf-8")
    llm = FakeLLM([json.dumps({"say": "Una receta de chilaquiles, ya me dio hambre.", "mood": "happy"})])
    brain = make_brain(llm, config=calm_config())
    await brain.handle(decode(json.dumps({"type": "event", "name": "file_drop", "path": str(note)})))
    prompt = llm.calls[0][-1]["content"]
    assert "receta.txt" in prompt and "salsa verde" in prompt
    assert outbox[-1]["type"] == "say" and "chilaquiles" in outbox[-1]["text"]


async def test_file_drop_refuses_sensitive(make_brain, outbox, tmp_path):
    secret = tmp_path / ".env"
    secret.write_text("GEMINI_API_KEY=abc", encoding="utf-8")
    keyfile = tmp_path / "notas.txt"
    keyfile.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nxxx", encoding="utf-8")
    llm = FakeLLM()
    brain = make_brain(llm, config=calm_config())
    for path in (secret, keyfile, tmp_path / "bbva" / "estado.txt"):
        outbox.clear()
        await brain.on_file_drop(str(path))
        assert outbox[-1]["type"] == "say"
        assert outbox[-1]["mood"] == "annoyed"
    assert llm.calls == []


async def test_file_drop_too_big(make_brain, outbox, tmp_path):
    big = tmp_path / "log.txt"
    big.write_bytes(b"a" * (2 * 1024 * 1024 + 1))
    llm = FakeLLM()
    brain = make_brain(llm, config=calm_config())
    await brain.on_file_drop(str(big))
    assert llm.calls == [] and "2 MB" in outbox[-1]["text"]


def test_read_drop_kinds(tmp_path):
    code = tmp_path / "main.py"
    code.write_text("print('hola')\n", encoding="utf-8")
    assert read_drop(str(code)).kind == "code"
    binary = tmp_path / "x.bin"
    binary.write_bytes(b"\x00\x01\x02" * 10)
    assert read_drop(str(binary)).reason == "unknown"
    assert read_drop(str(tmp_path / "nope.txt")).reason == "missing"
    from PIL import Image

    img = tmp_path / "foto.png"
    Image.new("RGB", (40, 30), "green").save(img)
    drop = read_drop(str(img))
    assert drop.kind == "image" and drop.image[:2] == b"\xff\xd8"
    assert sensitive(tmp_path / ".ssh" / "config")
    assert sensitive(tmp_path / "mis_passwords.txt")
    assert not sensitive(tmp_path / "tokenizer.py")


async def test_file_drop_image_uses_vision(make_brain, outbox, tmp_path):
    from PIL import Image

    img = tmp_path / "gato.jpg"
    Image.new("RGB", (40, 30), "orange").save(img)
    llm = FakeLLM([json.dumps({"say": "Un gato naranja, qué elegancia.", "mood": "happy"})])
    seen = []

    async def see(image, prompt):
        seen.append(image[:2])
        return "Una foto de un gato naranja."

    llm.see = see
    brain = make_brain(llm, config=calm_config())
    await brain.on_file_drop(str(img))
    assert seen == [b"\xff\xd8"]
    assert "gato naranja" in llm.calls[0][-1]["content"]
    assert "gato" in outbox[-1]["text"]


async def test_win_events_respect_calm_and_quiet(make_brain, outbox, clock):
    llm = FakeLLM()
    brain = make_brain(llm, config=calm_config())
    await brain.handle(decode(json.dumps({"type": "event", "name": "win", "what": "screenshot"})))
    assert [m["type"] for m in outbox if m["type"] == "say"] == ["say"]
    outbox.clear()
    clock.now += 30
    await brain.on_win("maximized")
    assert not [m for m in outbox if m["type"] == "say"]
    await brain.on_win("battery_low")
    assert [m for m in outbox if m["type"] == "say"]
    outbox.clear()
    brain.game = True
    clock.now += 3600
    brain.interacted()
    await brain.on_win("battery_low")
    await brain.on_win("hour")
    assert outbox == []
