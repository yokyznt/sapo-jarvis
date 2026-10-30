import json
import os
import time
from pathlib import Path

BLACKLIST = ["keepass", "1password", "bitwarden", "bbva", "banamex", "santander", "banorte", "whatsapp", "outlook", "gmail", "inprivate", "incógnito", "hermes"]

DEFAULTS = {
    "pc": {"skin": "clasico", "energy": "Normal", "size": 0, "monitor": "auto", "pin": None, "sounds": True, "volume": 0.6},
    "brain": {"provider": "gemini", "personality": "sarcastico", "comment_minutes": 10, "attention": True, "vision": True, "blacklist": BLACKLIST},
    "voice": {"enabled": True, "wake": "oye sapo", "engine": "gemini", "voice": "ef_dora", "pitch": 2.5, "speed": 1.08, "mic": "", "speaker": ""},
    "startup": {"autostart": False, "command": ""},
    "clips": {"enabled": False, "method": "native", "seconds": 30, "folder": ""},
}


def home() -> Path:
    h = os.environ.get("SAPO_HOME")
    if h:
        return Path(h)
    return Path(os.environ.get("APPDATA") or Path.home()) / "Sapo"


def config_path() -> Path:
    return home() / "config.json"


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    for attempt in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)


def _choice(*options):
    def check(v):
        if isinstance(v, str) and v in options:
            return v
        raise ValueError(f"debe ser uno de: {', '.join(options)}")
    return check


def _number(lo, hi, integer=False):
    def check(v):
        if isinstance(v, bool):
            raise ValueError("debe ser número")
        if isinstance(v, str):
            try:
                v = float(v)
            except ValueError:
                raise ValueError("debe ser número") from None
        if not isinstance(v, (int, float)) or v != v:
            raise ValueError("debe ser número")
        if integer:
            if float(v) != int(v):
                raise ValueError("debe ser entero")
            v = int(v)
        if not lo <= v <= hi:
            raise ValueError(f"debe estar entre {lo} y {hi}")
        return v if integer else round(float(v), 3)
    return check


def _bool(v):
    if isinstance(v, bool):
        return v
    raise ValueError("debe ser sí o no")


def _text(limit, strip=True):
    def check(v):
        if not isinstance(v, str):
            raise ValueError("debe ser texto")
        if strip:
            v = v.strip()
        if len(v) > limit or any(ord(c) < 32 for c in v):
            raise ValueError("texto inválido")
        return v
    return check


def _skin(v):
    if isinstance(v, str) and 0 < len(v) <= 40 and all(c.isalnum() or c in "-_" for c in v):
        return v
    raise ValueError("diseño inválido")


def _size(v):
    if isinstance(v, int) and not isinstance(v, bool) and v in (0, 1, 2):
        return v
    raise ValueError("debe ser 0, 1 o 2")


def _monitor(v):
    if v == "auto":
        return v
    if isinstance(v, str) and v.isdigit():
        v = int(v)
    if isinstance(v, int) and not isinstance(v, bool) and 0 <= v < 16:
        return v
    raise ValueError("monitor inválido")


def _blacklist(v):
    if not isinstance(v, list):
        raise ValueError("debe ser lista")
    out = []
    for item in v:
        item = _text(80)(item).lower()
        if item and item not in out:
            out.append(item)
    if len(out) > 200:
        raise ValueError("lista demasiado larga")
    return out


def _wake(v):
    v = _text(40)(v)
    if not v:
        raise ValueError("la palabra clave no puede ir vacía")
    return v.lower()


SCHEMA = {
    "pc": {
        "skin": _skin,
        "energy": _choice("Zen", "Normal", "Travieso"),
        "size": _size,
        "monitor": _monitor,
        "sounds": _bool,
        "volume": _number(0, 1),
    },
    "brain": {
        "provider": _choice("gemini", "ollama"),
        "personality": _choice("sarcastico", "tierno", "tranquilo"),
        "comment_minutes": _number(1, 240, integer=True),
        "attention": _bool,
        "vision": _bool,
        "blacklist": _blacklist,
    },
    "voice": {
        "enabled": _bool,
        "wake": _wake,
        "engine": _choice("gemini", "local"),
        "voice": _text(40),
        "pitch": _number(-12, 12),
        "speed": _number(0.5, 2),
        "mic": _text(200, strip=False),
        "speaker": _text(200, strip=False),
    },
    "startup": {
        "autostart": _bool,
        "command": _text(1000),
    },
    "clips": {
        "enabled": _bool,
        "method": _choice("native", "medal", "gamebar"),
        "seconds": _number(5, 120, integer=True),
        "folder": _text(260),
    },
}


def validate(section: str, key: str, value):
    check = SCHEMA.get(section, {}).get(key)
    if check is None:
        raise KeyError(f"{section}.{key} no existe")
    return check(value)


def _pin(v):
    if isinstance(v, dict) and all(isinstance(v.get(k), (int, float)) and not isinstance(v.get(k), bool) for k in ("x", "y")):
        return {"x": v["x"], "y": v["y"]}
    return None


def effective(data: dict | None = None) -> dict:
    data = read_json(config_path()) if data is None else data
    out = {}
    for section, defaults in DEFAULTS.items():
        raw = data.get(section) if isinstance(data.get(section), dict) else {}
        sec = {}
        for key, default in defaults.items():
            if key == "pin":
                sec[key] = _pin(raw.get(key))
                continue
            try:
                sec[key] = validate(section, key, raw[key])
            except (KeyError, ValueError):
                sec[key] = list(default) if isinstance(default, list) else default
        out[section] = sec
    return out


def update(section: str, key: str, value):
    value = validate(section, key, value)
    path = config_path()
    data = read_json(path)
    sec = data.get(section) if isinstance(data.get(section), dict) else {}
    sec[key] = value
    data[section] = sec
    write_json(path, data)
    return value


def remove(section: str, key: str) -> None:
    path = config_path()
    data = read_json(path)
    sec = data.get(section)
    if isinstance(sec, dict) and key in sec:
        del sec[key]
        write_json(path, data)
