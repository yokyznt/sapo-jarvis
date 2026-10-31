import asyncio
import json
import time

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.typing import Origin

from sapo.attention import Attention, Foreground
from sapo.config import BrainConfig, LiveConfig, PhoneConfig, static_config
from sapo.phone import MAX_BYTES, PAIR_KEY, TOKENS_KEY, Pairing, PhoneLink, StyleStore
from sapo.vault import protect, unprotect
from tests.conftest import FakeLLM


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SAPO_HOME", str(tmp_path))
    return tmp_path


def secrets_of(home):
    return json.loads((home / "secrets.json").read_text("utf-8"))


def offer(home, code="123456", ttl=300.0, tries=0):
    path = home / "secrets.json"
    data = json.loads(path.read_text("utf-8")) if path.exists() else {}
    data[PAIR_KEY] = protect(json.dumps({"code": code, "expires": time.time() + ttl, "tries": tries}))
    path.write_text(json.dumps(data), "utf-8")


@pytest.fixture
async def setup(home, make_brain):
    brain = make_brain(FakeLLM(), attention=Attention())
    config = static_config()
    config.phone = PhoneConfig(enabled=True, name="PC de prueba")
    style = StyleStore(home / "phone_style.json")
    link = PhoneLink(brain, config, style=style, pairing=Pairing(home / "secrets.json"), host="127.0.0.1", port=0, discovery_port=0)
    await link.tick()
    yield brain, link
    await link.stop()


def url(link):
    return f"ws://127.0.0.1:{link.ws_port}"


async def recv(ws):
    return json.loads(await asyncio.wait_for(ws.recv(), 3))


async def closed(ws):
    with pytest.raises(ConnectionClosed):
        while True:
            await asyncio.wait_for(ws.recv(), 3)
    return ws.close_code


async def paired_token(home, link):
    offer(home)
    async with connect(url(link)) as ws:
        await ws.send(json.dumps({"type": "pair", "code": "123456", "device": "Nothing A059"}))
        msg = await recv(ws)
    return msg["token"]


async def hello(link, token):
    ws = await connect(url(link))
    await ws.send(json.dumps({"type": "hello", "token": token, "device": "Nothing A059"}))
    assert await recv(ws) == {"type": "ok"}
    first = await recv(ws)
    assert first["type"] == "pc"
    return ws


async def test_pair_ok_then_hello(home, setup):
    brain, link = setup
    offer(home)
    async with connect(url(link)) as ws:
        await ws.send(json.dumps({"type": "pair", "code": "123456", "device": "Nothing A059"}))
        msg = await recv(ws)
        assert msg["type"] == "paired" and len(msg["token"]) == 64 and int(msg["token"], 16) >= 0
        assert await recv(ws) == {"type": "pc", "gaming": False, "app": None, "away": False}
    token = msg["token"]
    data = secrets_of(home)
    raw = (home / "secrets.json").read_text("utf-8")
    assert PAIR_KEY not in data and token not in raw
    [entry] = data[TOKENS_KEY]
    assert entry["device"] == "Nothing A059" and entry["date"] and unprotect(entry["token"]) == token
    ws = await hello(link, token)
    await ws.close()


async def test_bad_code_closes_and_counts(home, setup):
    _, link = setup
    offer(home)
    async with connect(url(link)) as ws:
        await ws.send(json.dumps({"type": "pair", "code": "000000", "device": "x"}))
        assert await recv(ws) == {"type": "error", "why": "bad_code"}
        assert await closed(ws) == 1008
    pend = json.loads(unprotect(secrets_of(home)[PAIR_KEY]))
    assert pend["tries"] == 1 and pend["code"] == "123456"


async def test_expired_code(home, setup):
    _, link = setup
    offer(home, ttl=-1)
    async with connect(url(link)) as ws:
        await ws.send(json.dumps({"type": "pair", "code": "123456", "device": "x"}))
        assert await recv(ws) == {"type": "error", "why": "expired"}
    assert PAIR_KEY not in secrets_of(home)


async def test_five_tries_kill_the_code(home, setup):
    _, link = setup
    offer(home)
    answers = []
    for _ in range(5):
        async with connect(url(link)) as ws:
            await ws.send(json.dumps({"type": "pair", "code": "999999", "device": "x"}))
            answers.append((await recv(ws))["why"])
    assert answers == ["bad_code"] * 4 + ["too_many"]
    async with connect(url(link)) as ws:
        await ws.send(json.dumps({"type": "pair", "code": "123456", "device": "x"}))
        assert await recv(ws) == {"type": "error", "why": "no_code"}
    assert TOKENS_KEY not in secrets_of(home)


@pytest.mark.parametrize("first", [
    {"type": "hello", "device": "x"},
    {"type": "hello", "token": "ab" * 32, "device": "x"},
    {"type": "style", "profile": {}, "describe": "hola"},
])
async def test_without_valid_hello_closes(home, setup, first):
    _, link = setup
    async with connect(url(link)) as ws:
        await ws.send(json.dumps(first))
        msg = await recv(ws)
        assert msg["type"] == "error"
        assert await closed(ws) == 1008
    assert not (home / "phone_style.json").exists()


async def test_revoked_token_closes(home, setup):
    _, link = setup
    token = await paired_token(home, link)
    ws = await hello(link, token)
    data = secrets_of(home)
    data[TOKENS_KEY] = []
    (home / "secrets.json").write_text(json.dumps(data, indent=4), "utf-8")
    await link.tick()
    assert await closed(ws) == 1008
    async with connect(url(link)) as again:
        await again.send(json.dumps({"type": "hello", "token": token, "device": "x"}))
        assert await recv(again) == {"type": "error", "why": "bad_token"}


async def test_big_message_closes(home, setup):
    _, link = setup
    token = await paired_token(home, link)
    ws = await hello(link, token)
    await ws.send(json.dumps({"type": "style", "profile": {}, "describe": "a" * (MAX_BYTES + 10)}))
    assert await closed(ws) == 1009
    assert not (home / "phone_style.json").exists()


async def test_style_is_saved_and_reaches_prompt(home, setup, make_brain):
    _, link = setup
    token = await paired_token(home, link)
    ws = await hello(link, token)
    profile = {"avgLen": 22, "emoji": 0.1, "words": ["neta", "jaja"]}
    await ws.send(json.dumps({"type": "style", "profile": profile, "describe": "Frases cortas,\nmucho 'neta' y 'jaja'."}))
    assert await recv(ws) == {"type": "ok"}
    await ws.close()
    saved = json.loads((home / "phone_style.json").read_text("utf-8"))
    assert saved["profile"] == profile and saved["device"] == "Nothing A059"
    assert saved["describe"] == "Frases cortas, mucho 'neta' y 'jaja'."
    store = StyleStore(home / "phone_style.json")
    me = make_brain(FakeLLM(), config=static_config(personality="como_yo"), style=store.describe)
    assert "mucho 'neta' y 'jaja'" in me.build()[0]["content"]
    other = make_brain(FakeLLM(), config=static_config(personality="tierno"), style=store.describe)
    assert "neta' y 'jaja'" not in other.build()[0]["content"]


async def test_phone_state_is_kept(home, setup):
    _, link = setup
    token = await paired_token(home, link)
    ws = await hello(link, token)
    await ws.send(json.dumps({"type": "phone", "busy": "Manual", "auto": True}))
    assert await recv(ws) == {"type": "ok"}
    await ws.send(json.dumps({"type": "phone", "busy": "Siesta", "auto": True}))
    assert await recv(ws) == {"type": "error", "why": "bad_phone"}
    await ws.close()
    [state] = link.phones.values()
    assert state["busy"] == "Manual" and state["auto"] is True


async def test_pc_sent_when_game_changes(home, setup):
    brain, link = setup
    token = await paired_token(home, link)
    ws = await hello(link, token)
    brain.attention.observe(Foreground("C:\\Juegos\\FortniteClient-Win64-Shipping.exe", "Fortnite"))
    await brain.on_event("game_on", 0.0)
    assert await recv(ws) == {"type": "pc", "gaming": True, "app": "FortniteClient-Win64-Shipping.exe", "away": False}
    await brain.on_event("game_off", 0.0)
    assert await recv(ws) == {"type": "pc", "gaming": False, "app": None, "away": False}
    brain.attention.observe(Foreground("code.exe", "brain.py"), idle=900)
    brain.changed()
    assert await recv(ws) == {"type": "pc", "gaming": False, "app": None, "away": True}
    await ws.close()


async def test_discovery_answers(setup):
    _, link = setup
    loop = asyncio.get_running_loop()
    got = loop.create_future()

    class Probe(asyncio.DatagramProtocol):
        def datagram_received(self, data, addr):
            if not got.done():
                got.set_result(data)

    transport, _ = await loop.create_datagram_endpoint(Probe, local_addr=("127.0.0.1", 0))
    try:
        transport.sendto(b"hola", ("127.0.0.1", link.udp_port))
        transport.sendto(b"SAPO?", ("127.0.0.1", link.udp_port))
        reply = json.loads(await asyncio.wait_for(got, 3))
    finally:
        transport.close()
    assert reply == {"sapo": 1, "port": link.ws_port, "name": "PC de prueba"}


async def test_max_three_connections(home, setup):
    _, link = setup
    held = [await connect(url(link)) for _ in range(3)]
    await asyncio.sleep(0.05)
    extra = await connect(url(link))
    assert await closed(extra) == 1013
    for ws in held:
        await ws.close()


async def test_browser_origin_rejected(setup):
    _, link = setup
    with pytest.raises(InvalidStatus) as err:
        async with connect(url(link), origin=Origin("http://evil.example")):
            pass
    assert err.value.response.status_code == 403


async def test_turns_on_and_off_live(home, setup):
    _, link = setup
    token = await paired_token(home, link)
    ws = await hello(link, token)
    link.config.phone = PhoneConfig(enabled=False)
    await link.tick()
    assert link.server is None and link.udp is None
    assert await closed(ws) == 1001
    with pytest.raises(OSError):
        await connect(url(link), open_timeout=2)
    link.config.phone = PhoneConfig(enabled=True)
    await link.tick()
    ws = await hello(link, token)
    await ws.close()


async def test_disabled_by_default(home, make_brain):
    config = LiveConfig(home / "config.json")
    link = PhoneLink(make_brain(FakeLLM()), config, host="127.0.0.1", port=0, discovery_port=0)
    await link.tick()
    assert link.server is None
    (home / "config.json").write_text(json.dumps({"phone": {"enabled": True, "name": "  Mi   PC  "}}), "utf-8")
    assert config.poll() is True
    assert config.phone == PhoneConfig(enabled=True, name="Mi PC")
    await link.tick()
    try:
        assert link.server is not None and link.label() == "Mi PC"
    finally:
        await link.stop()


def test_como_yo_config_and_prompt(persona):
    assert BrainConfig.parse({"personality": "como_yo"}).personality == "como_yo"
    assert BrainConfig.parse({"persona": "como_yo"}).personality == "como_yo"
    assert BrainConfig.parse({"personality": "Como_Yo"}).personality == "como_yo"
    empty = persona.system_prompt([], personality="como_yo")
    assert persona.strings["no_style"] in empty and "{estilo}" not in empty
    assert "escribe puras minúsculas" in persona.system_prompt([], personality="como_yo", style="escribe puras minúsculas")


def test_style_store_cleans_and_caches(tmp_path):
    store = StyleStore(tmp_path / "s.json")
    assert store.describe() == ""
    store.save({"a": 1}, "uno\x00 dos\n" + "x" * 5000, "cel")
    text = store.describe()
    assert text.startswith("uno dos x") and len(text) == 2000
    assert StyleStore(tmp_path / "s.json").describe() == text
