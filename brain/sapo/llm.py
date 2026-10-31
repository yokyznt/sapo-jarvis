import asyncio
import base64
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import httpx

from .config import LiveConfig, static_config
from .gemini import Gemini, GeminiError
from .hardware import Profile
from .protocol import ACTIONS, MOODS

log = logging.getLogger("sapo.llm")

REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "say": {"type": "string"},
        "mood": {"type": "string", "enum": list(MOODS)},
        "action": {"type": "string", "enum": list(ACTIONS)},
        "fact": {"type": "string"},
    },
    "required": ["say", "mood", "action"],
}

Messages = list[dict[str, Any]]


class LLM(Protocol):
    async def complete(self, messages: Messages, lite: bool = False) -> str: ...

    async def set_game(self, on: bool) -> None: ...


class ToolLLM(LLM, Protocol):
    async def chat_tools(self, messages: Messages, tools: list[dict[str, Any]]) -> dict[str, Any]: ...

    async def see(self, image: bytes, prompt: str) -> str: ...


def plain(messages: Messages) -> Messages:
    return [
        {"role": m["role"], "content": m.get("content") or ""}
        for m in messages
        if m.get("role") in ("system", "user", "assistant") and not m.get("tool_calls")
    ]


class Ollama:
    def __init__(self, url: str, num_predict: int = 160, client: httpx.AsyncClient | None = None):
        self.url = url.rstrip("/")
        self.num_predict = num_predict
        self.http = client or httpx.AsyncClient(timeout=httpx.Timeout(120, connect=3))
        self.think_supported: dict[str, bool] = {}

    async def chat(self, model: str, messages: Messages, num_gpu: int | None = None) -> str:
        return (await self.post_chat(model, messages, num_gpu))["content"]

    async def post_chat(
        self,
        model: str,
        messages: Messages,
        num_gpu: int | None = None,
        fmt: dict[str, Any] | None = REPLY_SCHEMA,
        tools: list[dict[str, Any]] | None = None,
        num_predict: int | None = None,
        temperature: float = 0.8,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {"num_predict": num_predict or self.num_predict, "temperature": temperature, "top_p": 0.9}
        if num_gpu is not None:
            options["num_gpu"] = num_gpu
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        if fmt is not None:
            body["format"] = fmt
        if tools:
            body["tools"] = tools
        if self.think_supported.get(model, True):
            body["think"] = False
        r = await self.http.post(f"{self.url}/api/chat", json=body)
        if r.status_code == 400 and "think" in r.text and "think" in body:
            self.think_supported[model] = False
            body.pop("think")
            r = await self.http.post(f"{self.url}/api/chat", json=body)
        r.raise_for_status()
        message = r.json()["message"]
        message.setdefault("content", "")
        return message

    async def unload(self, model: str) -> None:
        try:
            await self.http.post(f"{self.url}/api/generate", json={"model": model, "keep_alive": 0})
        except httpx.HTTPError as e:
            log.warning("no pude descargar %s: %s", model, e)

    async def preload(self, model: str, num_gpu: int | None = None) -> None:
        body: dict[str, Any] = {"model": model}
        if num_gpu is not None:
            body["options"] = {"num_gpu": num_gpu}
        try:
            await self.http.post(f"{self.url}/api/generate", json=body)
        except httpx.HTTPError as e:
            log.warning("no pude precargar %s: %s", model, e)

    async def models(self) -> list[str]:
        r = await self.http.get(f"{self.url}/api/tags")
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]


class Groq:
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, key: str, model: str, max_tokens: int = 400, client: httpx.AsyncClient | None = None):
        self.key = key
        self.model = model
        self.max_tokens = max_tokens
        self.http = client or httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5))

    async def chat(self, messages: Messages) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": 0.8,
            "response_format": {"type": "json_object"},
        }
        if "gpt-oss" in self.model:
            body["reasoning_effort"] = "low"
        r = await self.http.post(self.URL, json=body, headers={"Authorization": f"Bearer {self.key}"})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


class Router:
    def __init__(
        self,
        profile: Profile,
        ollama: Ollama,
        groq: Groq | None = None,
        gemini: Gemini | None = None,
        config: LiveConfig | None = None,
        clock: Callable[[], float] = time.monotonic,
        base_backoff: float = 30.0,
        max_backoff: float = 900.0,
    ):
        self.profile = profile
        self.ollama = ollama
        self.groq = groq
        self.gemini = gemini
        self.config = config or static_config(provider="ollama")
        self.clock = clock
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self.failures = 0
        self.retry_at = 0.0
        self.last = "ollama"
        self.game = False
        self.tasks: set[asyncio.Task] = set()

    @property
    def big_model(self) -> str:
        conf = self.config.brain
        if self.profile.name == "cpu":
            return conf.ollama_game_model or self.profile.model
        return conf.ollama_model or self.profile.model

    @property
    def small_model(self) -> str:
        return self.config.brain.ollama_game_model or self.profile.game_model

    @property
    def model(self) -> str:
        return self.small_model if self.game else self.big_model

    @property
    def gpu(self) -> int | None:
        return self.profile.game_num_gpu if self.game else self.profile.num_gpu

    def gemini_ready(self) -> bool:
        return (
            self.gemini is not None
            and self.config.brain.provider == "gemini"
            and self.clock() >= self.retry_at
            and self.gemini.has_key()
        )

    async def try_gemini(self, call: Callable[[], Awaitable[dict[str, Any]]]) -> dict[str, Any] | None:
        if not self.gemini_ready():
            return None
        try:
            out = await call()
        except GeminiError as e:
            if e.backoff:
                self.failures += 1
                wait = min(self.max_backoff, self.base_backoff * 2 ** (self.failures - 1))
                self.retry_at = self.clock() + wait
                log.warning("%s; uso Ollama y reintento Gemini en %.0f s", e.reason, wait)
            else:
                log.warning("%s; esta vez uso Ollama", e.reason)
            return None
        if self.failures:
            log.info("Gemini volvió")
        self.failures = 0
        self.last = "gemini"
        return out

    async def complete(self, messages: Messages, lite: bool = False) -> str:
        conf = self.config.brain
        model = conf.gemini_lite_model if lite else conf.gemini_model
        msg = await self.try_gemini(lambda: self.gemini.generate(model, messages, schema=REPLY_SCHEMA))
        if msg is not None:
            return msg["content"]
        self.last = "ollama"
        try:
            return await self.ollama.chat(self.model, messages, self.gpu)
        except (httpx.HTTPError, KeyError, ValueError) as e:
            if self.groq is None:
                raise
            log.warning("ollama falló (%s), uso Groq", e)
            return await self.groq.chat(plain(messages))

    async def chat_tools(self, messages: Messages, tools: list[dict[str, Any]]) -> dict[str, Any]:
        model = self.config.brain.gemini_model
        msg = await self.try_gemini(lambda: self.gemini.generate(model, messages, tools=tools, temperature=0.2))
        if msg is not None:
            return msg
        self.last = "ollama"
        try:
            return await self.ollama.post_chat(self.model, messages, self.gpu, fmt=None, tools=tools, temperature=0.2)
        except (httpx.HTTPError, KeyError, ValueError) as e:
            if self.groq is None:
                raise
            log.warning("ollama falló (%s), uso Groq sin herramientas", e)
            return {"role": "assistant", "content": await self.groq.chat(plain(messages))}

    async def see(self, image: bytes, prompt: str) -> str:
        message = {"role": "user", "content": prompt, "images": [base64.b64encode(image).decode()]}
        model = self.config.brain.gemini_model
        msg = await self.try_gemini(lambda: self.gemini.generate(model, [message], temperature=0.3, max_tokens=260))
        if msg is not None:
            return msg["content"]
        self.last = "ollama"
        reply = await self.ollama.post_chat(self.model, [message], self.gpu, fmt=None, num_predict=260, temperature=0.3)
        return reply["content"]

    async def set_game(self, on: bool) -> None:
        if on == self.game:
            return
        self.game = on
        if not self.profile.unload_on_game:
            return
        if on:
            await self.ollama.unload(self.big_model)
        else:
            await self.ollama.unload(self.small_model)
            if not self.gemini_ready():
                self.background(self.ollama.preload(self.big_model, self.profile.num_gpu))

    def warm_up(self) -> None:
        if not self.gemini_ready():
            self.background(self.ollama.preload(self.big_model, self.profile.num_gpu))

    def background(self, coro) -> None:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def describe(self) -> str:
        conf = self.config.brain
        where = "GPU" if self.profile.num_gpu is None else "CPU"
        local = f"Ollama perfil {self.profile.name}: {self.big_model} en {where}, juego: {self.small_model} en CPU"
        extra = f" + Groq ({self.groq.model})" if self.groq else ""
        if self.gemini is None or conf.provider != "gemini":
            return local + extra
        key = "con key" if self.gemini.has_key() else "sin key, uso Ollama"
        return f"Gemini {conf.gemini_model} / {conf.gemini_lite_model} ({key}) → {local}{extra}"
