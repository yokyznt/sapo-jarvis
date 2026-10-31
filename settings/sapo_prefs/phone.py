import base64
import ipaddress
import json
import random
import socket
import time

from . import secrets, store

PORT = 8766
CODE_TTL = 300
MAX_TRIES = 5
PAIR_KEY = "phone_pair"
TOKENS_KEY = "phone_tokens"
_rng = random.SystemRandom()


def _seal(data: dict) -> str:
    return base64.b64encode(secrets.protect(json.dumps(data).encode("utf-8"))).decode("ascii")


def _open(blob) -> dict | None:
    if not isinstance(blob, str) or not blob:
        return None
    try:
        data = json.loads(secrets.unprotect(base64.b64decode(blob)).decode("utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def new_code(now: float | None = None) -> dict:
    now = time.time() if now is None else now
    code = f"{_rng.randrange(1_000_000):06d}"
    data = store.read_json(secrets.path())
    data[PAIR_KEY] = _seal({"code": code, "expires": now + CODE_TTL, "tries": 0})
    store.write_json(secrets.path(), data)
    return {"code": code, "expires_in": CODE_TTL}


def pending(now: float | None = None) -> int:
    now = time.time() if now is None else now
    pend = _open(store.read_json(secrets.path()).get(PAIR_KEY))
    if pend is None:
        return 0
    expires, tries = pend.get("expires"), pend.get("tries", 0)
    if not isinstance(expires, (int, float)) or not isinstance(tries, int) or tries >= MAX_TRIES:
        return 0
    return max(0, int(expires - now))


def cancel_code() -> None:
    data = store.read_json(secrets.path())
    if PAIR_KEY in data:
        del data[PAIR_KEY]
        store.write_json(secrets.path(), data)


def devices() -> list[dict]:
    out = []
    for e in store.read_json(secrets.path()).get(TOKENS_KEY) or []:
        if isinstance(e, dict) and isinstance(e.get("id"), str):
            device = e.get("device") if isinstance(e.get("device"), str) else ""
            date = e.get("date") if isinstance(e.get("date"), str) else ""
            out.append({"id": e["id"], "device": device or "Celular", "date": date})
    return out


def revoke(tid: str) -> bool:
    data = store.read_json(secrets.path())
    entries = data.get(TOKENS_KEY)
    if not isinstance(entries, list):
        return False
    keep = [e for e in entries if not (isinstance(e, dict) and e.get("id") == tid)]
    if len(keep) == len(entries):
        return False
    data[TOKENS_KEY] = keep
    store.write_json(secrets.path(), data)
    return True


def local_ips() -> list[str]:
    found = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            found.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        found += [info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
    except OSError:
        pass
    out = []
    for ip in found:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if addr.is_private and not addr.is_loopback and not addr.is_link_local and ip not in out:
            out.append(ip)
    return out


def state() -> dict:
    return {"devices": devices(), "pending": pending(), "ips": local_ips(), "port": PORT, "name": socket.gethostname()}
