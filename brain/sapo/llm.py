import asyncio
import logging
from typing import Any, Protocol

import httpx

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

Messages = list[dict[str, str]]


class LLM(Protocol):
    async def complete(self, messages: Messages) -> str: ...

    async def set_game(self, on: bool) -> None: ...


class Ollama:
    def __init__(self, url: str, num_predict: int = 160, client: httpx.AsyncClient | None = None):
        self.url = url.rstrip("/")
        self.num_predict = num_predict
        self.http = client or httpx.AsyncClient(timeout=httpx.Timeout(120, connect=3))
        self.think_supported: dict[str, bool] = {}

    async def chat(self, model: str, messages: Messages, num_gpu: int | None = None) -> str:
        options: dict[str, Any] = {"num_predict": self.num_predict, "temperature": 0.8, "top_p": 0.9}
        if num_gpu is not None:
            options["num_gpu"] = num_gpu
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "format": REPLY_SCHEMA,
            "options": options,
        }
        if self.think_supported.get(model, True):
            body["think"] = False
        r = await self.http.post(f"{self.url}/api/chat", json=body)
        if r.status_code == 400 and "think" in r.text and "think" in body:
            self.think_supported[model] = False
            body.pop("think")
            r = await self.http.post(f"{self.url}/api/chat", json=body)
        r.raise_for_status()
        return r.json()["message"]["content"]

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
    def __init__(self, profile: Profile, ollama: Ollama, groq: Groq | None = None):
        self.profile = profile
        self.ollama = ollama
        self.groq = groq
        self.game = False
        self.tasks: set[asyncio.Task] = set()

    @property
    def model(self) -> str:
        return self.profile.game_model if self.game else self.profile.model

    async def complete(self, messages: Messages) -> str:
        gpu = self.profile.game_num_gpu if self.game else self.profile.num_gpu
        try:
            return await self.ollama.chat(self.model, messages, gpu)
        except (httpx.HTTPError, KeyError, ValueError) as e:
            if self.groq is None:
                raise
            log.warning("ollama falló (%s), uso Groq", e)
            return await self.groq.chat(messages)

    async def set_game(self, on: bool) -> None:
        if on == self.game:
            return
        self.game = on
        if not self.profile.unload_on_game:
            return
        if on:
            await self.ollama.unload(self.profile.model)
        else:
            await self.ollama.unload(self.profile.game_model)
            self.background(self.ollama.preload(self.profile.model, self.profile.num_gpu))

    def warm_up(self) -> None:
        self.background(self.ollama.preload(self.profile.model, self.profile.num_gpu))

    def background(self, coro) -> None:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def describe(self) -> str:
        extra = f" + Groq ({self.groq.model}) de respaldo" if self.groq else ""
        where = "GPU" if self.profile.num_gpu is None else "CPU"
        return f"perfil {self.profile.name}: {self.profile.model} en {where}, juego: {self.profile.game_model} en CPU{extra}"
