import argparse
import asyncio
import json
import logging
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from .attention import Attention, capture, idle_seconds, read_foreground
from .brain import Brain
from .config import LiveConfig, Settings
from .gemini import Gemini, GeminiError
from .hardware import pick_profile
from .llm import Groq, Ollama, Router
from .memory import Memory
from .pc import WindowsPC
from .personality import Persona
from .protocol import RELAYED, ProtocolError, decode, encode, relayed
from .tools import Toolbox
from .vault import KeyStore

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


async def relay(raw: str | bytes, sender: ServerConnection, hub: Hub) -> bool:
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return False
    if not isinstance(data, dict) or data.get("type") not in RELAYED:
        return False
    clean = relayed(data)
    if clean is None:
        return True
    msg = encode(clean)
    for ws in list(hub.clients - {sender}):
        try:
            await ws.send(msg)
        except ConnectionClosed:
            hub.clients.discard(ws)
    return True


def make_handler(brain: Brain, hub: Hub):
    async def handler(ws: ServerConnection) -> None:
        hub.clients.add(ws)
        log.info("cliente conectado (%d)", len(hub.clients))
        try:
            async for raw in ws:
                if await relay(raw, ws, hub):
                    continue
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


async def check_gemini(gemini: Gemini, config: LiveConfig) -> None:
    if config.brain.provider != "gemini":
        return
    if not gemini.has_key():
        log.warning("sin key de Gemini (GEMINI_API_KEY o secrets.json): uso Ollama")
        return
    try:
        names = set(await gemini.models())
    except GeminiError as e:
        log.warning("no pude listar modelos de Gemini: %s", e.reason)
        return
    for model in (config.brain.gemini_model, config.brain.gemini_lite_model):
        if model not in names:
            log.warning("Gemini no tiene el modelo %s; revisa brain.gemini_model en config.json", model)


async def run(settings: Settings, autonomous: bool = True) -> None:
    profile = pick_profile(settings)
    config = LiveConfig()
    ollama = Ollama(settings.ollama_url, settings.num_predict)
    groq = Groq(settings.groq_key, settings.groq_model) if settings.groq_key else None
    gemini = Gemini(KeyStore().get)
    router = Router(profile, ollama, groq, gemini, config)
    memory = Memory(settings.db_path)
    persona = Persona(settings.lang)
    hub = Hub()
    attention = Attention()
    tools = Toolbox(WindowsPC(), see=router.see, notes_dir=settings.notes_dir, search_url=settings.search_url) if settings.tools else None
    brain = Brain(
        router,
        memory,
        persona,
        hub.send,
        history=settings.history,
        tools=tools,
        confirm_timeout=settings.confirm_timeout,
        config=config,
        attention=attention,
        capture=capture,
    )
    try:
        installed = await ollama.models()
        for model in {router.big_model, router.small_model} - set(installed):
            log.warning("falta el modelo %s: corre `ollama pull %s`", model, model)
        router.warm_up()
    except Exception as e:
        log.warning("Ollama no responde en %s (%r)", settings.ollama_url, e)
    await check_gemini(gemini, config)
    async with serve(make_handler(brain, hub), settings.host, settings.port) as server:
        print(f"Sapo cerebro en ws://{settings.host}:{settings.port} | {router.describe()} | memoria: {settings.db_path}", flush=True)
        hub.spawn(config.watch())
        if autonomous:
            hub.spawn(brain.autonomous_loop())
            hub.spawn(brain.watch(read_foreground, idle_seconds))
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
