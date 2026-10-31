import asyncio
import hmac
import json
import logging
import secrets
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from .config import LiveConfig, home_dir
from .vault import load_json, protect, save_json, secrets_path, unprotect

log = logging.getLogger("sapo.phone")

PORT = 8766
DISCOVERY_PORT = 8767
PROBE = b"SAPO?"
MAX_BYTES = 64 * 1024
MAX_CLIENTS = 3
MAX_TRIES = 5
MAX_TOKENS = 20
MAX_DESCRIBE = 2000
HELLO_TIMEOUT = 10.0
RETRY_AFTER = 10.0
PAIR_KEY = "phone_pair"
TOKENS_KEY = "phone_tokens"
ORIGINS = [None]
BUSY = ("Manual", "NoMolestar", "PantallaApagada", "Horario", "JugandoPC")


def clean_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join("".join(c if c.isprintable() else " " for c in value).split())[:limit]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def style_path() -> Path:
    return home_dir() / "phone_style.json"


class StyleStore:
    def __init__(self, path: Path | None = None):
        self.path = path or style_path()
        self.stamp: tuple[int, int] | None = None
        self.cached = ""

    def describe(self) -> str:
        try:
            st = self.path.stat()
        except OSError:
            self.stamp, self.cached = None, ""
            return ""
        stamp = (st.st_mtime_ns, st.st_size)
        if stamp != self.stamp:
            self.stamp = stamp
            self.cached = clean_text(load_json(self.path).get("describe"), MAX_DESCRIBE)
        return self.cached

    def save(self, profile: dict[str, Any], describe: Any, device: str) -> None:
        save_json(self.path, {"profile": profile, "describe": clean_text(describe, MAX_DESCRIBE), "device": device, "at": now_iso()})


class Pairing:
    def __init__(self, path: Path | None = None, clock=time.time):
        self.path = path or secrets_path()
        self.clock = clock
        self.stamp: tuple[int, int] | None = None
        self.cache: list[tuple[str, str, str]] = []

    def pending(self, data: dict[str, Any]) -> dict[str, Any] | None:
        blob = data.get(PAIR_KEY)
        if not isinstance(blob, str) or not blob:
            return None
        try:
            raw = json.loads(unprotect(blob))
        except (OSError, ValueError):
            return None
        if not isinstance(raw, dict):
            return None
        code, expires, tries = raw.get("code"), raw.get("expires"), raw.get("tries", 0)
        if not isinstance(code, str) or len(code) != 6 or not code.isdigit():
            return None
        if not isinstance(expires, (int, float)) or isinstance(expires, bool):
            return None
        if not isinstance(tries, int) or isinstance(tries, bool):
            tries = MAX_TRIES
        return {"code": code, "expires": float(expires), "tries": tries}

    def pair(self, code: Any, device: Any) -> tuple[str | None, str]:
        data = load_json(self.path, strict=True)
        pend = self.pending(data)
        if pend is None:
            return None, "no_code"
        if self.clock() > pend["expires"]:
            data.pop(PAIR_KEY, None)
            save_json(self.path, data)
            return None, "expired"
        if pend["tries"] >= MAX_TRIES:
            data.pop(PAIR_KEY, None)
            save_json(self.path, data)
            return None, "too_many"
        given = code.encode() if isinstance(code, str) and code.isascii() else b""
        if not hmac.compare_digest(given, pend["code"].encode()):
            pend["tries"] += 1
            if pend["tries"] >= MAX_TRIES:
                data.pop(PAIR_KEY, None)
                why = "too_many"
            else:
                data[PAIR_KEY] = protect(json.dumps(pend))
                why = "bad_code"
            save_json(self.path, data)
            return None, why
        token = secrets.token_hex(32)
        tid = secrets.token_hex(4)
        entries = [e for e in data.get(TOKENS_KEY) or [] if isinstance(e, dict)][-(MAX_TOKENS - 1) :]
        entries.append({"id": tid, "device": clean_text(device, 60) or "Celular", "date": now_iso(), "token": protect(token)})
        data[TOKENS_KEY] = entries
        data.pop(PAIR_KEY, None)
        save_json(self.path, data)
        self.stamp = None
        return token, tid

    def entries(self) -> list[tuple[str, str, str]]:
        try:
            st = self.path.stat()
        except FileNotFoundError:
            self.stamp, self.cache = None, []
            return []
        except OSError:
            return self.cache
        stamp = (st.st_mtime_ns, st.st_size)
        if stamp == self.stamp:
            return self.cache
        try:
            data = load_json(self.path, strict=True)
        except (OSError, ValueError):
            return self.cache
        found = []
        for e in data.get(TOKENS_KEY) or []:
            if not isinstance(e, dict) or not isinstance(e.get("id"), str) or not isinstance(e.get("token"), str):
                continue
            try:
                secret = unprotect(e["token"])
            except (OSError, ValueError):
                continue
            found.append((e["id"], secret, clean_text(e.get("device"), 60) or "Celular"))
        self.stamp, self.cache = stamp, found
        return found

    def check(self, token: Any) -> str | None:
        if not isinstance(token, str) or len(token) != 64 or not token.isascii():
            return None
        hit = None
        for tid, secret, _ in self.entries():
            if hmac.compare_digest(token.encode(), secret.encode()):
                hit = tid
        return hit

    def ids(self) -> set[str]:
        return {tid for tid, _, _ in self.entries()}

    def device(self, tid: str) -> str:
        return next((name for i, _, name in self.entries() if i == tid), "Celular")


class Discovery(asyncio.DatagramProtocol):
    def __init__(self, link: "PhoneLink"):
        self.link = link
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr) -> None:
        if data.strip() != PROBE or self.transport is None:
            return
        reply = json.dumps({"sapo": 1, "port": self.link.ws_port, "name": self.link.label()}, ensure_ascii=False)
        self.transport.sendto(reply.encode("utf-8"), addr)

    def error_received(self, exc: Exception) -> None:
        log.debug("descubrimiento: %r", exc)


def parse(raw: str | bytes) -> dict[str, Any] | None:
    if not isinstance(raw, str):
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("type"), str):
        return None
    return data


class PhoneLink:
    def __init__(
        self,
        brain,
        config: LiveConfig,
        style: StyleStore | None = None,
        pairing: Pairing | None = None,
        host: str = "0.0.0.0",
        port: int = PORT,
        discovery_port: int = DISCOVERY_PORT,
    ):
        self.brain = brain
        self.config = config
        self.style = style or StyleStore()
        self.pairing = pairing or Pairing()
        self.host = host
        self.port = port
        self.discovery_port = discovery_port
        self.ws_port = port
        self.udp_port: int | None = None
        self.server: Server | None = None
        self.udp: asyncio.DatagramTransport | None = None
        self.conns: set[ServerConnection] = set()
        self.clients: dict[ServerConnection, str] = {}
        self.phones: dict[str, dict[str, Any]] = {}
        self.last_pc: dict[str, Any] | None = None
        self.tasks: set[asyncio.Task] = set()
        self.retry_at = 0.0
        brain.on_change.append(self.notify)

    def label(self) -> str:
        return self.config.phone.name or socket.gethostname()

    def pc_state(self) -> dict[str, Any]:
        att = self.brain.attention
        gaming = bool(self.brain.game)
        app = None
        if gaming and att is not None and att.current is not None and not att.private:
            app = Path(att.current.process).name[:80] or None
        away = bool(att is not None and self.brain.config.brain.attention and att.away)
        return {"gaming": gaming, "app": app, "away": away}

    def notify(self) -> None:
        state = self.pc_state()
        if state == self.last_pc:
            return
        self.last_pc = state
        if not self.clients:
            return
        task = asyncio.get_running_loop().create_task(self.broadcast({"type": "pc", **state}))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def broadcast(self, msg: dict[str, Any]) -> None:
        data = json.dumps(msg, ensure_ascii=False)
        for ws in list(self.clients):
            try:
                await ws.send(data)
            except ConnectionClosed:
                self.clients.pop(ws, None)

    async def send(self, ws: ServerConnection, msg: dict[str, Any]) -> None:
        await ws.send(json.dumps(msg, ensure_ascii=False))

    async def fail(self, ws: ServerConnection, why: str) -> None:
        try:
            await self.send(ws, {"type": "error", "why": why})
            await ws.close(1008, why)
        except ConnectionClosed:
            pass

    async def greet(self, ws: ServerConnection) -> str | None:
        try:
            raw = await asyncio.wait_for(ws.recv(), HELLO_TIMEOUT)
        except TimeoutError:
            await self.fail(ws, "need_hello")
            return None
        msg = parse(raw) or {}
        kind = msg.get("type")
        if kind == "hello":
            tid = self.pairing.check(msg.get("token"))
            if tid is None:
                await self.fail(ws, "bad_token")
                return None
            await self.send(ws, {"type": "ok"})
            return tid
        if kind == "pair":
            try:
                token, result = self.pairing.pair(msg.get("code"), msg.get("device"))
            except (OSError, ValueError) as e:
                log.warning("no pude emparejar: %r", e)
                token, result = None, "unavailable"
            if token is None:
                await self.fail(ws, result)
                return None
            await self.send(ws, {"type": "paired", "token": token})
            log.info("celular vinculado: %s", self.pairing.device(result))
            return result
        await self.fail(ws, "need_hello")
        return None

    async def handler(self, ws: ServerConnection) -> None:
        if len(self.conns) >= MAX_CLIENTS:
            await ws.close(1013, "busy")
            return
        self.conns.add(ws)
        try:
            tid = await self.greet(ws)
            if tid is None:
                return
            self.clients[ws] = tid
            state = self.pc_state()
            self.last_pc = state
            await self.send(ws, {"type": "pc", **state})
            async for raw in ws:
                await self.on_message(ws, tid, raw)
        except ConnectionClosed:
            pass
        finally:
            self.conns.discard(ws)
            self.clients.pop(ws, None)

    async def on_message(self, ws: ServerConnection, tid: str, raw: str | bytes) -> None:
        msg = parse(raw)
        if msg is None:
            await self.send(ws, {"type": "error", "why": "bad_msg"})
            return
        kind = msg["type"]
        if kind == "style":
            profile = msg.get("profile")
            if not isinstance(profile, dict):
                await self.send(ws, {"type": "error", "why": "bad_style"})
                return
            try:
                await asyncio.to_thread(self.style.save, profile, msg.get("describe"), self.pairing.device(tid))
            except OSError as e:
                log.warning("no pude guardar el estilo: %r", e)
                await self.send(ws, {"type": "error", "why": "unavailable"})
                return
            await self.send(ws, {"type": "ok"})
        elif kind == "phone":
            busy = msg.get("busy")
            if busy is not None and busy not in BUSY:
                await self.send(ws, {"type": "error", "why": "bad_phone"})
                return
            self.phones[tid] = {"busy": busy, "auto": msg.get("auto") is True, "at": time.time()}
            await self.send(ws, {"type": "ok"})
        elif kind == "hello":
            await self.send(ws, {"type": "ok"})
        else:
            await self.send(ws, {"type": "error", "why": "unknown"})

    async def drop_revoked(self) -> None:
        ids = self.pairing.ids()
        for ws, tid in list(self.clients.items()):
            if tid not in ids:
                self.clients.pop(ws, None)
                self.phones.pop(tid, None)
                try:
                    await ws.close(1008, "revoked")
                except ConnectionClosed:
                    pass

    async def start(self) -> None:
        self.server = await serve(self.handler, self.host, self.port, origins=ORIGINS, max_size=MAX_BYTES, max_queue=4)
        self.ws_port = next(iter(self.server.sockets)).getsockname()[1]
        loop = asyncio.get_running_loop()
        try:
            self.udp, _ = await loop.create_datagram_endpoint(lambda: Discovery(self), local_addr=(self.host, self.discovery_port))
            self.udp_port = self.udp.get_extra_info("sockname")[1]
        except OSError as e:
            log.warning("descubrimiento UDP no disponible en %s: %r", self.discovery_port, e)
            self.udp, self.udp_port = None, None
        log.info("enlace con el celular en ws://%s:%s", self.host, self.ws_port)

    async def stop(self) -> None:
        if self.udp is not None:
            self.udp.close()
            self.udp, self.udp_port = None, None
        server, self.server = self.server, None
        if server is not None:
            server.close()
            await server.wait_closed()
            log.info("enlace con el celular apagado")
        self.clients.clear()
        self.conns.clear()

    async def tick(self) -> None:
        want = self.config.phone.enabled
        if want and self.server is None and time.monotonic() >= self.retry_at:
            try:
                await self.start()
            except OSError as e:
                log.warning("no pude abrir el puerto %s para el celular: %r", self.port, e)
                self.retry_at = time.monotonic() + RETRY_AFTER
                await self.stop()
        elif not want and self.server is not None:
            await self.stop()
        if self.clients:
            await self.drop_revoked()

    async def run(self, every: float = 1.0) -> None:
        try:
            while True:
                try:
                    await self.tick()
                except Exception as e:
                    log.warning("enlace con el celular falló: %r", e)
                await asyncio.sleep(every)
        finally:
            await self.stop()
