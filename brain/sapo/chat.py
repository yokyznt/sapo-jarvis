import argparse
import asyncio
import json
import sys
import time

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from .config import Settings
from .personality import Persona
from .protocol import EVENTS, VERSION, encode


class Activity:
    def __init__(self) -> None:
        self.last = time.monotonic()
        self.thinking = False


async def wait_quiet(activity: Activity, quiet: float = 4.0, limit: float = 120.0) -> None:
    start = time.monotonic()
    while time.monotonic() - start < limit:
        if not activity.thinking and time.monotonic() - activity.last >= quiet:
            return
        await asyncio.sleep(0.2)


async def receive(ws: ClientConnection, persona: Persona, activity: Activity) -> None:
    try:
        async for raw in ws:
            msg = json.loads(raw)
            kind = msg.get("type")
            activity.last = time.monotonic()
            if kind == "thinking":
                activity.thinking = bool(msg.get("on"))
            if kind == "say":
                print(f"sapo [{msg.get('mood')}]> {msg.get('text')}", flush=True)
            elif kind == "action":
                print(persona.ui("action").replace("{name}", str(msg.get("name"))), flush=True)
            elif kind == "thinking" and msg.get("on"):
                print(persona.ui("thinking"), flush=True)
    except ConnectionClosed:
        pass


def parse_command(line: str) -> dict | None:
    if not line.startswith("/e"):
        return {"type": "chat", "text": line}
    parts = line.split()
    if len(parts) < 2 or parts[1] not in EVENTS:
        return None
    boredom = float(parts[2]) if len(parts) > 2 else 0.0
    return {"type": "event", "name": parts[1], "boredom": boredom}


async def run(url: str, persona: Persona) -> None:
    try:
        ws = await connect(url)
    except OSError:
        print(persona.ui("no_server").replace("{url}", url))
        return
    async with ws:
        await ws.send(encode({"type": "hello", "version": VERSION}))
        print(persona.ui("connected").replace("{url}", url))
        activity = Activity()
        reader = asyncio.create_task(receive(ws, persona, activity))
        loop = asyncio.get_running_loop()
        while not reader.done():
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                await wait_quiet(activity)
                break
            line = line.strip()
            if not line:
                continue
            if line in ("/salir", "/q"):
                break
            msg = parse_command(line)
            if msg is None:
                print(persona.ui("bad_event").replace("{events}", ", ".join(sorted(EVENTS))))
                continue
            activity.last = time.monotonic()
            await ws.send(encode(msg))
        reader.cancel()
    print(persona.ui("bye"))


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(prog="sapo-chat", description="Chatea por texto con el sapo")
    parser.add_argument("--url", default=f"ws://{settings.host}:{settings.port}")
    args = parser.parse_args()
    try:
        asyncio.run(run(args.url, Persona(settings.lang)))
    except KeyboardInterrupt:
        pass
