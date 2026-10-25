import json
import random
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import PROMPTS
from .protocol import ACTIONS, MAX_SAY, MOODS


@dataclass
class Reply:
    say: str
    mood: str = "sarcastic"
    action: str = "none"
    fact: str = ""


def clip(text: str, limit: int = MAX_SAY) -> str:
    t = " ".join(text.split()).strip().strip('"').strip()
    if len(t) <= limit:
        return t
    cut = t[: limit - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(",;: ") + "…"


def parse_reply(raw: str) -> Reply:
    raw = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S).strip()
    data = None
    try:
        data = json.loads(raw)
    except ValueError:
        found = re.search(r"\{.*\}", raw, re.S)
        if found:
            try:
                data = json.loads(found.group(0))
            except ValueError:
                data = None
    if not isinstance(data, dict):
        data = {"say": raw}
    mood = data.get("mood")
    act = data.get("action")
    return Reply(
        say=clip(str(data.get("say") or "")),
        mood=mood if mood in MOODS else "sarcastic",
        action=act if act in ACTIONS else "none",
        fact=" ".join(str(data.get("fact") or "").split())[:200],
    )


class Persona:
    def __init__(self, lang: str = "es", root: Path = PROMPTS):
        self.lang = lang
        self.system = (root / f"{lang}.md").read_text(encoding="utf-8")
        self.strings = json.loads((root / f"{lang}.json").read_text(encoding="utf-8"))

    def system_prompt(self, facts: list[str], now: datetime | None = None) -> str:
        now = now or datetime.now()
        listed = "\n".join(f"- {f}" for f in facts) or self.strings["no_facts"]
        return self.system.replace("{hechos}", listed).replace("{hora}", f"{self.strings['days'][now.weekday()]} {now:%H:%M}")

    def event_prompt(self, name: str, boredom: float) -> str:
        return (
            self.strings["event_wrap"]
            .replace("{evento}", self.strings["events"].get(name, name))
            .replace("{aburrimiento}", str(round(boredom * 10)))
        )

    def autonomous_prompt(self, boredom: float, idle_minutes: int | None) -> str:
        idle = self.strings["never"] if idle_minutes is None else str(idle_minutes)
        return (
            self.strings["autonomous"]
            .replace("{minutos}", idle)
            .replace("{aburrimiento}", str(round(boredom * 10)))
        )

    def canned(self, key: str, rng: random.Random | None = None) -> str:
        options = self.strings["canned"].get(key) or self.strings["canned"]["error"]
        return clip((rng or random).choice(options))

    def mood_for(self, key: str) -> str:
        mood = self.strings["moods"].get(key, "sarcastic")
        return mood if mood in MOODS else "sarcastic"

    def ui(self, key: str) -> str:
        return self.strings["ui"][key]
