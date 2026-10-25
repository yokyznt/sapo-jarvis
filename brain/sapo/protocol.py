import json
from typing import Any

VERSION = 1
MOODS = ("sarcastic", "happy", "annoyed", "sleepy", "curious")
ACTIONS = ("dance", "jump", "sleep", "look_around", "steal_cursor", "none")
EVENTS = frozenset(
    {"petted", "thrown", "ignored", "woke", "game_on", "game_off", "dancing", "stole_cursor", "moved_window"}
)
MAX_SAY = 90
MAX_CHAT = 2000


class ProtocolError(ValueError):
    pass


def decode(raw: str | bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as e:
        raise ProtocolError(f"json inválido: {e}") from e
    if not isinstance(data, dict):
        raise ProtocolError("se esperaba un objeto")
    kind = data.get("type")
    if kind == "hello":
        version = data.get("version")
        if not isinstance(version, int):
            raise ProtocolError("hello sin version")
        return {"type": "hello", "version": version}
    if kind == "chat":
        text = data.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ProtocolError("chat sin texto")
        return {"type": "chat", "text": text.strip()[:MAX_CHAT]}
    if kind == "event":
        name = data.get("name")
        if name not in EVENTS:
            raise ProtocolError(f"evento desconocido: {name!r}")
        boredom = data.get("boredom", 0.0)
        if isinstance(boredom, bool) or not isinstance(boredom, (int, float)):
            raise ProtocolError("boredom debe ser número")
        return {"type": "event", "name": name, "boredom": min(1.0, max(0.0, float(boredom)))}
    raise ProtocolError(f"tipo desconocido: {kind!r}")


def say(text: str, mood: str = "sarcastic") -> dict[str, Any]:
    return {"type": "say", "text": text[:MAX_SAY], "mood": mood if mood in MOODS else "sarcastic"}


def action(name: str) -> dict[str, Any]:
    return {"type": "action", "name": name if name in ACTIONS else "none"}


def thinking(on: bool) -> dict[str, Any]:
    return {"type": "thinking", "on": bool(on)}


def encode(msg: dict[str, Any]) -> str:
    return json.dumps(msg, ensure_ascii=False)
