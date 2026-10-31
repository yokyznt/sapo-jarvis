import json
from typing import Any

VERSION = 1
MOODS = ("sarcastic", "happy", "annoyed", "sleepy", "curious")
ACTIONS = ("dance", "jump", "sleep", "look_around", "steal_cursor", "none")
EVENTS = frozenset(
    {"petted", "thrown", "ignored", "woke", "game_on", "game_off", "dancing", "stole_cursor", "moved_window", "file_drop", "win"}
)
WIN_EVENTS = frozenset(
    {"maximized", "minimized", "moved", "notification", "battery_low", "offline", "online", "muted", "screenshot", "clipboard", "hour"}
)
CLIP_STATES = ("saved", "error", "recording")
MAX_PATH = 1024
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
        if not isinstance(name, str) or name not in EVENTS:
            raise ProtocolError(f"evento desconocido: {name!r}")
        boredom = data.get("boredom", 0.0)
        if isinstance(boredom, bool) or not isinstance(boredom, (int, float)):
            raise ProtocolError("boredom debe ser número")
        msg = {"type": "event", "name": name, "boredom": float(min(1.0, max(0.0, boredom)))}
        if name == "file_drop":
            path = data.get("path")
            if not isinstance(path, str) or not path.strip() or len(path) > MAX_PATH or "\x00" in path:
                raise ProtocolError("file_drop necesita path")
            msg["path"] = path.strip()
        elif name == "win":
            what = data.get("what")
            if not isinstance(what, str) or what not in WIN_EVENTS:
                raise ProtocolError(f"evento win desconocido: {what!r}")
            msg["what"] = what
        return msg
    if kind == "confirm_reply":
        cid = data.get("id")
        ok = data.get("ok")
        if not isinstance(cid, str) or not cid or not isinstance(ok, bool):
            raise ProtocolError("confirm_reply necesita id y ok")
        return {"type": "confirm_reply", "id": cid[:64], "ok": ok}
    raise ProtocolError(f"tipo desconocido: {kind!r}")


def confirm(cid: str, text: str) -> dict[str, Any]:
    return {"type": "confirm", "id": cid, "text": text[:MAX_SAY]}


def say(text: str, mood: str = "sarcastic") -> dict[str, Any]:
    return {"type": "say", "text": text[:MAX_SAY], "mood": mood if mood in MOODS else "sarcastic"}


def action(name: str) -> dict[str, Any]:
    return {"type": "action", "name": name if name in ACTIONS else "none"}


def thinking(on: bool) -> dict[str, Any]:
    return {"type": "thinking", "on": bool(on)}


def clip(state: str, path: str | None = None, seconds: float | None = None) -> dict[str, Any]:
    msg: dict[str, Any] = {"type": "clip", "state": state if state in CLIP_STATES else "error"}
    if path:
        msg["path"] = str(path)
    if seconds is not None:
        msg["seconds"] = round(float(seconds), 1)
    return msg


QUIET_REASONS = ("game", "call", "fullscreen")
CROAKS = ("corto", "doble", "grunon", "feliz", "sueno", "sorpresa", "aterrizaje", "plop")
RELAYED = frozenset({"listening", "speaking", "mouth", "quiet", "croak"})


def quiet(on: bool, reason: str) -> dict[str, Any]:
    return {"type": "quiet", "on": bool(on), "reason": reason if reason in QUIET_REASONS else "game"}


def croak(kind: str) -> dict[str, Any]:
    return {"type": "croak", "kind": kind if kind in CROAKS else "corto"}


def speaking(on: bool) -> dict[str, Any]:
    return {"type": "speaking", "on": bool(on)}


def mouth(level: float) -> dict[str, Any]:
    return {"type": "mouth", "level": round(float(min(1.0, max(0.0, level))), 3)}


def relayed(data: Any) -> dict[str, Any] | None:
    if not isinstance(data, dict) or not isinstance(data.get("type"), str) or data["type"] not in RELAYED:
        return None
    kind = data["type"]
    if kind in ("listening", "speaking"):
        return {"type": kind, "on": bool(data.get("on"))}
    if kind == "mouth":
        level = data.get("level")
        if isinstance(level, bool) or not isinstance(level, (int, float)):
            return None
        return mouth(level)
    if kind == "quiet":
        return quiet(bool(data.get("on")), str(data.get("reason")))
    return croak(str(data.get("kind")))


def encode(msg: dict[str, Any]) -> str:
    return json.dumps(msg, ensure_ascii=False)
