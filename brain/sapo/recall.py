import re
import unicodedata
from collections import Counter
from datetime import datetime

DAYS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")

MEMO = re.compile(
    r"^(?:oye\s+)?(?:sapo\s*,?\s*)?(?:porfa\s+)?(?:recuerda|acuerdate|no\s+(?:se\s+te\s+)?olvides|guarda|apunta|anota)(?:\s+(?:en\s+tu\s+memoria|bien))?\s+(?:de\s+)?que\s+(.{3,240})$"
)
FORGET = re.compile(r"^(?:oye\s+)?(?:sapo\s*,?\s*)?(?:olvida|borra\s+de\s+tu\s+memoria)\s+(?:lo\s+de\s+|que\s+|todo\s+lo\s+de\s+)?(.{2,120})$")
PERSONAL = re.compile(
    r"\b(soy|me llamo|mi nombre|me dicen|me gusta|me gustan|me encanta|me encantan|odio|no me gusta|prefiero|tengo|vivo|estudio|trabajo|naci|cumplo|mi cumpleanos|mi novia|mi novio|mi mama|mi papa|mi hermano|mi hermana|mi perro|mi gato|mi escuela|mi juego|mi color|voy a|quiero)\b"
)
STOP = set(
    "a al algo ante como con de del el en es esa ese eso esta este esto estas hay la las le lo los me mi mas muy no nos o para pero por que se si sin su sus te tu tus un una uno y ya yo eres soy tienes tengo".split()
)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def plain(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s:/.-]", " ", fold(text)).split())


def stamp(now: datetime) -> str:
    return f"({DAYS[now.weekday()]} {now.day} {MONTHS[now.month - 1]})"


def memo(text: str) -> str | None:
    found = MEMO.match(plain(text))
    if not found:
        return None
    body = text.strip()
    m = re.search(r"\bque\s+", body, re.I)
    return (body[m.end():] if m else found.group(1)).strip(" .!¡¿?") or None


def forget(text: str) -> str | None:
    found = FORGET.match(plain(text))
    return found.group(1).strip() if found else None


def learn(text: str, now: datetime | None = None) -> str | None:
    now = now or datetime.now()
    clean = " ".join(text.split()).strip()
    said = memo(clean)
    if said:
        return f"{stamp(now)} {said}"
    if "?" in clean or "¿" in clean or len(clean) > 220:
        return None
    s = plain(clean)
    if len(s.split()) < 3 or not PERSONAL.search(s):
        return None
    if re.match(r"^(que|como|cuando|donde|cual|quien|por que|cuanto)\b", s):
        return None
    return f"{stamp(now)} {clean.rstrip(' .!')}"


def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-zñ]+", fold(text)) if len(w) > 1]


def crutches(said: list[str], window: int = 8, least: int = 3) -> list[str]:
    recent = said[-window:]
    seen: Counter[str] = Counter()
    for line in recent:
        for w in set(words(line)):
            if w not in STOP or w in ("ya", "wey", "neta", "chale", "orale"):
                seen[w] += 1
    openers = Counter(" ".join(words(line)[:2]) for line in recent if len(words(line)) >= 2)
    out = [w for w, n in seen.most_common() if n >= least]
    out += [f"empezar con «{o}»" for o, n in openers.items() if n >= 2]
    return out[:10]


def relevant(query: str, facts: list[str], k: int = 4) -> list[str]:
    q = {w for w in words(query) if w not in STOP and len(w) > 3}
    if not q:
        return []
    scored = []
    for i, f in enumerate(facts):
        fw = set(words(f))
        hits = sum(1 for w in q if any(x.startswith(w[:5]) for x in fw))
        if hits:
            scored.append((hits, i, f))
    scored.sort(key=lambda t: (-t[0], -t[1]))
    return [f for _, _, f in scored[:k]]
