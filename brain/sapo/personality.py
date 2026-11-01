import json
import random
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import PROMPTS
from .protocol import ACTIONS, MAX_SAY, MOODS

MOOD_WORDS = {
    "feliz": "happy",
    "contento": "happy",
    "alegre": "happy",
    "molesto": "annoyed",
    "enojado": "annoyed",
    "curioso": "curious",
    "sarcastico": "sarcastic",
    "dormido": "sleepy",
    "sueno": "sleepy",
    "sonoliento": "sleepy",
}
MARK = re.compile(r"\[[^\[\]\n]{0,40}\]")
FACT = re.compile(r"^\[\s*(?:dato|fact)\s*\]\s*:?\s*(.*)$", re.I | re.S)
END = re.compile(r"[.!?…:]+[\"'»”)]*(?=\s)|\n")
COMMA = re.compile(r"[,;](?=\s)")
WORD = re.compile(r"\S*\w\S*")
PERSONAL = re.compile(r"\b(soy|me llamo|mi nombre|me gusta|me gustan|me encanta|me encantan|odio|prefiero|tengo|vivo|estudio|trabajo|naci|cumplo|mi|mis)\b")


def personal(text: str) -> bool:
    return bool(PERSONAL.search(fold(text)))


def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def tidy(text: str) -> str:
    text = MARK.sub(" ", text).replace("*", "").replace("#", "").replace("`", "")
    return " ".join(text.split()).strip()


def count(text: str) -> int:
    return len(WORD.findall(text))


class Sentences:
    def __init__(self, first: int = 3, most: int = 32, least: int = 2):
        self.first = first
        self.most = most
        self.least = least
        self.buf = ""
        self.head = True
        self.mood = "sarcastic"
        self.action = "none"
        self.fact = ""
        self.parts = 0

    def feed(self, chunk: str) -> list[str]:
        self.buf += chunk
        return self.drain(False)

    def flush(self) -> list[str]:
        return self.drain(True)

    def drain(self, final: bool) -> list[str]:
        out: list[str] = []
        while True:
            if self.head and not self.read_head(final):
                return out
            if not self.read_marker(final):
                return out
            piece = self.cut(final)
            if piece is None:
                return out
            text = tidy(piece)
            if text:
                out.append(text)
                self.parts += 1

    def read_head(self, final: bool) -> bool:
        s = self.buf.lstrip()
        if not s:
            return final
        if s[0] == "[":
            end = s.find("]")
            if end < 0 and len(s) < 40 and not final:
                return False
            if end >= 0 and not FACT.match(s):
                self.apply(s[1:end])
                s = s[end + 1 :]
        self.buf = s.lstrip()
        self.head = False
        return True

    def apply(self, content: str) -> None:
        for word in re.findall(r"[a-z_]+", fold(content)):
            if self.mood == "sarcastic" and (word in MOODS or word in MOOD_WORDS):
                self.mood = MOOD_WORDS.get(word, word)
            elif word in ACTIONS and word != "none":
                self.action = word

    def read_marker(self, final: bool) -> bool:
        while True:
            s = self.buf.lstrip()
            if not s.startswith("["):
                return True
            nl = s.find("\n")
            if nl < 0 and not final and len(s) < 240:
                return False
            line, rest = (s[:nl], s[nl + 1 :]) if nl >= 0 else (s, "")
            found = FACT.match(line)
            if found:
                fact = tidy(found.group(1))[:200].rstrip(" .")
                if fact:
                    self.fact = fact
                self.buf = rest
                continue
            mark = MARK.match(line)
            if mark:
                self.apply(mark.group(0)[1:-1])
                self.buf = line[mark.end() :] + ("\n" + rest if nl >= 0 else "")
            else:
                self.buf = s[1:]

    def cut(self, final: bool) -> str | None:
        b = self.buf
        stop = b.find("[")
        zone = b if stop < 0 else b[:stop]
        need = self.first if self.parts == 0 else self.least
        for m in END.finditer(zone):
            if count(zone[: m.end()]) >= need:
                return self.take(m.end())
        if self.parts == 0:
            for m in COMMA.finditer(zone):
                if count(zone[: m.end()]) >= self.first:
                    return self.take(m.end())
        done = [w for w in WORD.finditer(zone) if w.end() < len(zone)]
        if len(done) > self.most:
            limit = done[self.most - 1].end()
            commas = [m.end() for m in COMMA.finditer(zone[: limit + 1]) if count(zone[: m.end()]) >= self.first]
            return self.take(commas[-1] if commas else limit)
        if stop > 0:
            return self.take(stop)
        if final and b.strip():
            return self.take(len(b))
        return None

    def take(self, end: int) -> str:
        piece, self.buf = self.buf[:end], self.buf[end:]
        return piece


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


def salvage(raw: str) -> dict:
    found = re.search(r'"say"\s*:\s*"((?:[^"\\]|\\.)*)', raw, re.S)
    if not found:
        return {"say": raw if not raw.lstrip().startswith("{") else ""}
    try:
        say = json.loads('"' + found.group(1).rstrip("\\") + '"')
    except ValueError:
        say = found.group(1)
    data = {"say": say.strip()}
    for key in ("mood", "action"):
        m = re.search(rf'"{key}"\s*:\s*"([a-z_]+)"', raw)
        if m:
            data[key] = m.group(1)
    return data


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
        data = salvage(raw)
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
        chat = root / f"{lang}_chat.md"
        self.chat = chat.read_text(encoding="utf-8") if chat.is_file() else self.system
        self.strings = json.loads((root / f"{lang}.json").read_text(encoding="utf-8"))

    def chat_prompt(self, facts: list[str], now: datetime | None = None, personality: str = "sarcastico", activity: str = "", style: str = "") -> str:
        return self.fill(self.chat, facts, now, personality, activity, style)

    def system_prompt(self, facts: list[str], now: datetime | None = None, personality: str = "sarcastico", activity: str = "", style: str = "") -> str:
        return self.fill(self.system, facts, now, personality, activity, style)

    def fill(self, template: str, facts: list[str], now: datetime | None, personality: str, activity: str, style: str) -> str:
        now = now or datetime.now()
        listed = "\n".join(f"- {f}" for f in facts) or self.strings["no_facts"]
        tones = self.strings["personalities"]
        tone = tones.get(personality, tones["sarcastico"])
        if personality == "como_yo":
            tone = tone.replace("{estilo}", style.strip() or self.strings["no_style"])
        return (
            template.replace("{hechos}", listed)
            .replace("{personalidad}", tone)
            .replace("{actividad}", activity or self.strings["no_activity"])
            .replace("{hora}", f"{self.strings['days'][now.weekday()]} {now:%H:%M}")
        )

    def activity_text(self, info: dict[str, str]) -> str:
        if info.get("app") and info.get("title"):
            return self.strings["activity"].replace("{app}", info["app"]).replace("{titulo}", info["title"]).replace("{aqui}", info.get("here") or "poco").replace("{dia}", info.get("day") or "-")
        if info.get("app"):
            return f"Ahorita: {info['app']}. " + self.strings["activity_day"].replace("{dia}", info.get("day") or "-")
        if info.get("day"):
            return self.strings["activity_day"].replace("{dia}", info["day"])
        return ""

    def attention_prompt(self, app: str, title: str, minutes: str, view: str = "") -> str:
        hint = self.strings["vision_hint"].replace("{vista}", view) if view else ""
        return self.strings["attention"].replace("{app}", app).replace("{titulo}", title).replace("{minutos}", minutes).replace("{vista}", hint)

    def retry_prompt(self, phrase: str) -> str:
        return self.strings["retry"].replace("{frase}", phrase)

    def event_prompt(self, name: str, boredom: float) -> str:
        return (
            self.strings["event_wrap"]
            .replace("{evento}", self.strings["events"].get(name, name))
            .replace("{aburrimiento}", str(round(boredom * 10)))
        )

    def file_prompt(self, name: str, kind: str, content: str) -> str:
        return self.strings["file_wrap"].replace("{nombre}", name).replace("{tipo}", self.strings["file_kinds"].get(kind, kind)).replace("{contenido}", content)

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
