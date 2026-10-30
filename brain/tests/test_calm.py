import asyncio
import json
import os
import random

import pytest

from sapo.attention import Attention, Foreground, app_name, blocked, in_call, title_is_enough
from sapo.config import BrainConfig, LiveConfig, static_config
from sapo.phrases import RecentPhrases, similarity
from tests.conftest import FakeLLM

CODE = Foreground("Code.exe", "brain.py - sapo-jarvis - Visual Studio Code")
ROBLOX = Foreground("RobloxPlayerBeta.exe", "Roblox")
EXCEL = Foreground("EXCEL.EXE", "presupuesto-octubre.xlsx - Excel")


def reply(text, action="none"):
    return json.dumps({"say": text, "mood": "sarcastic", "action": action})


class SeeingLLM(FakeLLM):
    def __init__(self, replies=None):
        super().__init__(replies)
        self.seen = []

    async def see(self, image, prompt):
        self.seen.append(image)
        return "un juego de bloques con un avatar saltando"


def says(outbox):
    return [m["text"] for m in outbox if m["type"] == "say"]


def test_similarity_and_recent():
    assert similarity("Ya vi que estás en Excel otra vez", "ya vi que andas en excel otra vez") > 0.72
    assert similarity("Tres horas en Roblox, campeón", "Ese reporte de Excel no se hace solo") < 0.5
    recent = RecentPhrases(size=50)
    for i in range(60):
        recent.add(f"frase número {i} sobre la mosca {i * 7}")
    assert len(recent.items) == 50
    assert recent.repeats("Frase número 59 sobre la mosca 413!")
    assert not recent.repeats("Me voy a dormir una siesta larguísima")


async def test_repeated_phrase_regenerates_once(make_brain, outbox, memory):
    memory.add_message("sapo", "Ya vi que estás en Excel otra vez")
    llm = FakeLLM([reply("Ya vi que andas en Excel otra vez"), reply("Ese presupuesto no se va a cuadrar solo")])
    brain = make_brain(llm)
    await brain.handle({"type": "chat", "text": "qué onda"})
    assert says(outbox) == ["Ese presupuesto no se va a cuadrar solo"]
    assert len(llm.calls) == 2
    assert "se parece mucho" in llm.calls[1][-1]["content"]


async def test_repeated_spontaneous_stays_silent(make_brain, outbox, memory):
    memory.add_message("sapo", "Tres horas en Roblox, campeón")
    llm = FakeLLM([reply("Tres horas en Roblox campeón!"), reply("tres horas en roblox, campeon")])
    brain = make_brain(llm)
    assert await brain.tick() is False
    assert says(outbox) == [] and len(llm.calls) == 2


async def test_spontaneous_rate_limit(make_brain, outbox, clock):
    llm = FakeLLM()
    brain = make_brain(llm, config=static_config(comment_minutes=10))
    assert await brain.tick() is True
    assert llm.lites == [True]
    clock.now += 3600
    assert await brain.tick() is False
    await brain.handle({"type": "chat", "text": "jaja sí"})
    assert llm.lites[-1] is False
    assert await brain.tick() is True
    await brain.handle({"type": "event", "name": "petted", "boredom": 0.0})
    clock.now += 5 * 60
    assert await brain.tick() is False
    clock.now += 11 * 60
    assert await brain.tick() is True
    assert len(says(outbox)) == 5


def test_comment_gap_jitter(make_brain):
    brain = make_brain(FakeLLM(), config=static_config(comment_minutes=10))
    brain.rng = random.Random(7)
    gaps = []
    for _ in range(300):
        brain.spoke()
        gaps.append(brain.gap)
    assert 8.5 * 60 <= min(gaps) and max(gaps) <= 15 * 60
    assert max(gaps) - min(gaps) > 4 * 60


async def test_ignored_event_is_spontaneous(make_brain, outbox, clock):
    brain = make_brain(FakeLLM())
    assert await brain.tick() is True
    clock.now += 3600
    await brain.handle({"type": "event", "name": "ignored", "boredom": 0.9})
    assert len(says(outbox)) == 1


@pytest.mark.parametrize("quiet", ["call", "fullscreen", "game"])
async def test_silence_in_call_fullscreen_and_game(make_brain, outbox, clock, quiet):
    att = Attention(clock=clock)
    llm = FakeLLM()
    brain = make_brain(llm, attention=att)
    if quiet == "call":
        att.observe(Foreground("ms-teams.exe", "Reunión diaria | Microsoft Teams"))
    elif quiet == "fullscreen":
        att.observe(Foreground("vlc.exe", "pelicula.mkv - VLC", fullscreen=True))
    else:
        await brain.handle({"type": "event", "name": "game_on", "boredom": 0.0})
    assert await brain.tick() is False
    await brain.handle({"type": "event", "name": "petted", "boredom": 0.0})
    clock.now += 600
    assert await brain.attend() is False
    assert says(outbox) == [] and llm.calls == []
    await brain.handle({"type": "chat", "text": "oye sapo"})
    assert len(says(outbox)) == 1


@pytest.mark.parametrize(
    "process,title,expected",
    [
        ("ms-teams.exe", "Reunión con Ana | Microsoft Teams", True),
        ("ms-teams.exe", "Chat | Equipo | Microsoft Teams", False),
        ("Teams.exe", "Llamada con Luis | Microsoft Teams", True),
        ("Zoom.exe", "Zoom Meeting", True),
        ("Zoom.exe", "Reunión de Zoom", True),
        ("Zoom.exe", "Zoom Workplace", False),
        ("chrome.exe", "Meet - abc-defg-hij - Google Chrome", True),
        ("msedge.exe", "Meet: Daily scrum - Microsoft Edge", True),
        ("chrome.exe", "YouTube - Google Chrome", False),
        ("Discord.exe", "Canal de voz General | Amigos - Discord", True),
        ("Discord.exe", "#memes | Amigos - Discord", False),
        ("slack.exe", "Huddle: diseño - Slack", True),
        ("chrome.exe", "Ana está compartiendo tu pantalla - Google Chrome", True),
        ("Code.exe", "meeting-notes.md - Visual Studio Code", False),
    ],
)
def test_call_detection(process, title, expected):
    assert in_call(Foreground(process, title)) is expected


def test_blacklist_case_insensitive():
    words = BrainConfig().blacklist
    assert blocked(Foreground("WhatsApp.exe", "WhatsApp"), words)
    assert blocked(Foreground("chrome.exe", "BBVA México | Banca en línea - Google Chrome"), words)
    assert blocked(Foreground("msedge.exe", "Nueva pestaña - [InPrivate] - Microsoft Edge"), words)
    assert blocked(Foreground("chrome.exe", "Nueva pestaña - Incognito - Google Chrome"), ("incognito",))
    assert blocked(Foreground("firefox.exe", "Bandeja - Gmail - Mozilla Firefox"), words)
    assert not blocked(CODE, words)


async def test_attention_comments_once_after_two_minutes(make_brain, outbox, clock):
    att = Attention(clock=clock)
    llm = SeeingLLM([reply("Presupuesto de octubre, a ver si ahora sí cuadra")])
    shots = []
    brain = make_brain(llm, attention=att, capture=lambda fg: shots.append(fg) or b"jpg", config=static_config(vision=True))
    att.observe(CODE)
    clock.now += 3
    assert await brain.attend() is False
    att.observe(EXCEL)
    clock.now += 100
    att.observe(EXCEL)
    assert await brain.attend() is False
    clock.now += 21
    att.observe(EXCEL)
    assert await brain.attend() is True
    prompt = llm.calls[0][-1]["content"]
    assert "CAMBIO DE ACTIVIDAD" in prompt and "presupuesto-octubre.xlsx" in prompt and "Excel" in prompt
    assert "presupuesto-octubre.xlsx" in llm.calls[0][0]["content"]
    assert shots == [] and llm.seen == []
    await brain.handle({"type": "chat", "text": "ya sé"})
    clock.now += 3600
    assert await brain.attend() is False
    assert says(outbox)[0] == "Presupuesto de octubre, a ver si ahora sí cuadra"


async def test_attention_uses_vision_only_when_title_is_not_enough(make_brain, clock):
    att = Attention(clock=clock)
    llm = SeeingLLM([reply("Saltando bloques en Roblox desde hace rato"), reply("Otra vez Roblox, ya ni te saludo")])
    shots = []
    brain = make_brain(llm, attention=att, capture=lambda fg: shots.append(fg) or b"jpg", config=static_config(vision=True))
    assert not title_is_enough(ROBLOX) and title_is_enough(EXCEL)
    att.observe(CODE)
    att.observe(ROBLOX)
    clock.now += 125
    assert await brain.attend() is True
    assert shots == [ROBLOX] and len(llm.seen) == 1
    assert "un juego de bloques" in llm.calls[0][-1]["content"]
    brain.interacted()
    att.observe(CODE)
    att.observe(ROBLOX)
    clock.now += 125
    brain.gap = 0
    assert await brain.attend() is True
    assert len(shots) == 1


async def test_vision_off_never_captures(make_brain, clock):
    att = Attention(clock=clock)
    llm = SeeingLLM()
    shots = []
    brain = make_brain(llm, attention=att, capture=lambda fg: shots.append(fg) or b"jpg", config=static_config(vision=False))
    att.observe(CODE)
    att.observe(ROBLOX)
    clock.now += 125
    await brain.attend()
    assert shots == [] and llm.seen == []


async def test_blacklist_never_comments_nor_captures(make_brain, outbox, clock):
    att = Attention(clock=clock)
    llm = SeeingLLM()
    shots = []
    brain = make_brain(llm, attention=att, capture=lambda fg: shots.append(fg) or b"jpg", config=static_config(vision=True))
    secret = Foreground("chrome.exe", "Banorte - Saldo cuenta 1234 - Google Chrome")
    att.observe(CODE)
    for _ in range(100):
        clock.now += 3
        att.observe(secret, brain.config.brain.blacklist)
        await brain.attend()
    assert shots == [] and llm.seen == [] and says(outbox) == []
    assert await brain.tick() is True
    system = llm.calls[-1][0]["content"]
    assert "Banorte" not in system and "1234" not in system and "algo privado" in system


def test_day_summary(clock):
    att = Attention(clock=clock)
    for _ in range(3600):
        att.observe(ROBLOX)
        clock.now += 3
    for _ in range(800):
        att.observe(EXCEL)
        clock.now += 3
    att.observe(EXCEL)
    assert att.summary() == "Roblox 3 h, Excel 40 min"
    assert att.describe()["here"] == "40 min"
    clock.now += 3
    att.observe(CODE, idle=900)
    assert att.summary() == "Roblox 3 h, Excel 40 min"
    assert app_name(ROBLOX) == "Roblox"


async def test_activity_in_system_prompt_and_personality(make_brain, clock):
    att = Attention(clock=clock)
    att.observe(ROBLOX)
    clock.now += 3 * 3600
    att.observe(ROBLOX)
    llm = FakeLLM()
    brain = make_brain(llm, attention=att, config=static_config(personality="tierno"))
    await brain.handle({"type": "chat", "text": "hola"})
    system = llm.calls[0][0]["content"]
    now = system.split("Lo que está haciendo:")[1]
    assert "Roblox" in now and "3 h" in now and "tierno:" in system
    brain.config.brain = BrainConfig(personality="tranquilo", attention=False)
    await brain.handle({"type": "chat", "text": "hola otra vez"})
    system = llm.calls[1][0]["content"]
    assert "tranquilo:" in system and "Roblox" not in system.split("Lo que está haciendo:")[1]


def bump(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))


async def test_live_config_reload(tmp_path):
    path = tmp_path / "config.json"
    conf = LiveConfig(path)
    assert conf.brain == BrainConfig()
    changes = []
    conf.listeners.append(changes.append)
    bump(path, {"pc": {"skin": "rosa"}, "brain": {"provider": "ollama", "personality": "Tierno", "comment_minutes": 3, "blacklist": ["Steam"], "vision": False}})
    assert conf.poll() is True
    assert conf.brain.provider == "ollama" and conf.brain.personality == "tierno" and conf.brain.comment_minutes == 3
    assert conf.brain.blacklist == ("steam",) and conf.brain.vision is False and conf.brain.attention is True
    assert conf.poll() is False
    path.write_text("{roto", encoding="utf-8")
    assert conf.poll() is False and conf.brain.personality == "tierno"
    bump(path, {"brain": {"personality": "malvado", "comment_minutes": "diez", "provider": 3}})
    assert conf.poll() is True and conf.brain == BrainConfig()
    task = asyncio.create_task(conf.watch(every=0.02))
    bump(path, {"brain": {"gemini_model": "gemini-2.5-flash", "attention": False}})
    await asyncio.sleep(0.15)
    task.cancel()
    assert conf.brain.gemini_model == "gemini-2.5-flash" and conf.brain.attention is False
    assert len(changes) == 3
