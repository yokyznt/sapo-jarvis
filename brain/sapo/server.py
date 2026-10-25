import argparse
import asyncio
import logging
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from .brain import Brain
from .config import Settings
from .hardware import pick_profile
from .llm import Groq, Ollama, Router
from .memory import Memory
from .personality import Persona
from .protocol import ProtocolError, decode, encode

log = logging.getLogger("sapo.server")


class Hub:
    def __init__(self) -> None:
        self.clients: set[ServerConnection] = set()
        self.tasks: set[asyncio.Task] = set()

    async def send(self, msg: dict[str, Any]) -> None:
        data = encode(msg)
        for ws in list(self.clients):
            try:
                await ws.send(data)
            except ConnectionClosed:
                self.clients.discard(ws)

    def spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)


def make_handler(brain: Brain, hub: Hub):
    async def handler(ws: ServerConnection) -> None:
        hub.clients.add(ws)
        log.info("cliente conectado (%d)", len(hub.clients))
        try:
            async for raw in ws:
                try:
                    msg = decode(raw)
                except ProtocolError as e:
                    log.warning("mensaje ignorado: %s", e)
                    continue
                hub.spawn(brain.handle(msg))
        except ConnectionClosed:
            pass
        finally:
            hub.clients.discard(ws)
            log.info("cliente desconectado (%d)", len(hub.clients))

    return handler


async def run(settings: Settings, autonomous: bool = True) -> None:
    profile = pick_profile(settings)
    ollama = Ollama(settings.ollama_url, settings.num_predict)
    groq = Groq(settings.groq_key, settings.groq_model) if settings.groq_key else None
    router = Router(profile, ollama, groq)
    memory = Memory(settings.db_path)
    persona = Persona(settings.lang)
    hub = Hub()
    brain = Brain(router, memory, persona, hub.send, history=settings.history)
    try:
        installed = await ollama.models()
        for model in {profile.model, profile.game_model} - set(installed):
            log.warning("falta el modelo %s: corre `ollama pull %s`", model, model)
        router.warm_up()
    except Exception as e:
        log.warning("Ollama no responde en %s (%r)", settings.ollama_url, e)
    async with serve(make_handler(brain, hub), settings.host, settings.port) as server:
        print(f"Sapo cerebro en ws://{settings.host}:{settings.port} | {router.describe()} | memoria: {settings.db_path}", flush=True)
        if autonomous:
            hub.spawn(brain.autonomous_loop())
        await server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(prog="sapo-brain", description="Cerebro local de Sapo-Jarvis")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--sin-autonomo", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    if args.host:
        settings.host = args.host
    if args.port:
        settings.port = args.port
    try:
        asyncio.run(run(settings, autonomous=not args.sin_autonomo))
    except KeyboardInterrupt:
        pass
