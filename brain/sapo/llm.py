import asyncio
import base64
import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

import httpx

from .config import LiveConfig, static_config
from .gemini import Gemini, GeminiError, to_contents
from .hardware import Profile
from .protocol import ACTIONS, MOODS

log = logging.getLogger("sapo.llm")

CLOUD_STREAM = ("gemini-3.5-flash-lite", "gemma-4-26b-a4b-it", "gemini-flash-lite-latest")
THINKING = ({"thinkingLevel": "minimal"}, {"thinkingBudget": 0}, None)
OLLAMA_ENV = {"OLLAMA_KV_CACHE_TYPE": "q8_0", "OLLAMA_FLASH_ATTENTION": "1"}
STREAM_ERRORS = (TimeoutError, httpx.HTTPError, GeminiError, ValueError, KeyError)

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


def cloud_error(status: int, text: str, model: str) -> GeminiError:
    if status == 429:
        return GeminiError("gemini sin cupo (429)")
    if status in (401, 403) or (status == 400 and "api key" in text.lower()):
        return GeminiError(f"gemini rechazó la key ({status})")
    if status == 404:
        return GeminiError(f"gemini no conoce el modelo {model}")
    if status >= 500:
        return GeminiError(f"gemini caído ({status})")
    return GeminiError(f"gemini respondió {status}: {text[:200]}", backoff=False)


def sse_texts(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(data, dict):
        return []
    out = []
    for cand in (data.get("candidates") or [])[:1]:
        for p in (cand.get("content") or {}).get("parts") or []:
            if isinstance(p.get("text"), str) and p["text"] and not p.get("thought"):
                out.append(p["text"])
    return out


def ollama_exe() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    guess = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return str(guess) if guess.is_file() else None


def hidden_console() -> tuple[int, Any]:
    if os.name != "nt":
        return 0, None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = 0
    return subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP, info


def launch_ollama() -> bool:
    exe = ollama_exe()
    if exe is None:
        return False
    flags, info = hidden_console()
    try:
        subprocess.Popen(
            [exe, "serve"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            startupinfo=info,
            close_fds=True,
            env={**os.environ, **OLLAMA_ENV},
        )
    except OSError as e:
        log.warning("no pude arrancar Ollama: %s", e)
        return False
    return True


class Ollama:
    def __init__(self, url: str, num_predict: int = 160, client: httpx.AsyncClient | None = None, launcher: Callable[[], bool] | None = None):
        self.url = url.rstrip("/")
        self.num_predict = num_predict
        self.http = client or httpx.AsyncClient(timeout=httpx.Timeout(120, connect=3))
        self.think_supported: dict[str, bool] = {}
        self.format_ok: dict[str, bool] = {}
        self.launcher = launcher if launcher is not None else launch_ollama
        self.launched_at = -1e9
        self.ready_wait = 25.0

    def local(self) -> bool:
        host = httpx.URL(self.url).host
        return host in ("127.0.0.1", "localhost", "::1")

    async def alive(self) -> bool:
        try:
            r = await self.http.get(f"{self.url}/api/version", timeout=2)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def ensure(self) -> bool:
        if await self.alive():
            return True
        if not self.local() or time.monotonic() - self.launched_at < 60:
            return False
        self.launched_at = time.monotonic()
        if not self.launcher():
            return False
        log.info("Ollama no estaba prendido; lo arranqué")
        end = time.monotonic() + self.ready_wait
        while time.monotonic() < end:
            await asyncio.sleep(0.5)
            if await self.alive():
                return True
        return False

    async def post(self, path: str, body: dict[str, Any]) -> httpx.Response:
        try:
            return await self.http.post(f"{self.url}{path}", json=body)
        except httpx.ConnectError:
            if not await self.ensure():
                raise
            return await self.http.post(f"{self.url}{path}", json=body)

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
            "keep_alive": -1,
            "options": options,
        }
        if fmt is not None:
            body["format"] = fmt
        if tools:
            body["tools"] = tools
        if self.think_supported.get(model, True):
            body["think"] = False
        if "format" in body and not self.format_ok.get(model, True):
            body.pop("format")
        r = await self.post("/api/chat", body)
        if r.status_code == 400 and "think" in r.text and "think" in body:
            self.think_supported[model] = False
            body.pop("think")
            r = await self.post("/api/chat", body)
        if "format" in body and (r.status_code >= 500 or not self.complete_reply(r)):
            log.warning("Ollama falla con formato JSON en %s; sigo sin formato", model)
            self.format_ok[model] = False
            body.pop("format")
            r = await self.post("/api/chat", body)
        r.raise_for_status()
        message = r.json()["message"]
        message.setdefault("content", "")
        return message

    @staticmethod
    def complete_reply(r: httpx.Response) -> bool:
        try:
            data = r.json()
        except ValueError:
            return False
        content = (data.get("message") or {}).get("content") or ""
        return data.get("done") is not False and bool(content.strip()) or bool((data.get("message") or {}).get("tool_calls"))

    async def stream_chat(
        self,
        model: str,
        messages: Messages,
        num_gpu: int | None = None,
        num_predict: int = 160,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        options: dict[str, Any] = {"num_predict": num_predict, "temperature": temperature, "top_p": 0.9}
        if num_gpu is not None:
            options["num_gpu"] = num_gpu
        body: dict[str, Any] = {"model": model, "messages": messages, "stream": True, "keep_alive": -1, "options": options}
        for _ in range(2):
            if self.think_supported.get(model, True):
                body["think"] = False
            else:
                body.pop("think", None)
            async with self.http.stream("POST", f"{self.url}/api/chat", json=body) as r:
                if r.status_code != 200:
                    text = (await r.aread()).decode("utf-8", "replace")
                    if r.status_code == 400 and "think" in body and "think" in text:
                        self.think_supported[model] = False
                        continue
                    r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise ValueError(f"ollama: {data['error']}")
                    chunk = (data.get("message") or {}).get("content") or ""
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        return
                return

    async def loaded(self) -> list[str]:
        try:
            r = await self.http.get(f"{self.url}/api/ps", timeout=3)
            r.raise_for_status()
            return [m.get("name") or m.get("model") or "" for m in r.json().get("models", [])]
        except (httpx.HTTPError, ValueError, AttributeError):
            return []

    async def unload(self, model: str) -> None:
        try:
            await self.http.post(f"{self.url}/api/generate", json={"model": model, "keep_alive": 0})
        except httpx.HTTPError as e:
            log.warning("no pude descargar %s: %s", model, e)

    async def preload(self, model: str, num_gpu: int | None = None) -> None:
        body: dict[str, Any] = {"model": model, "keep_alive": -1}
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
        self.model_retry: dict[str, float] = {}
        self.model_cooldown = 120.0
        self.first_token = 1.5
        self.cloud_wait = 5.0
        self.last_wait = 30.0
        self.stream_tokens = 160
        self.thinking: dict[str, int] = {}

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

    def gemini_models(self, first: str) -> list[str]:
        conf = self.config.brain
        models = list(dict.fromkeys(m for m in (first, conf.gemini_model, conf.gemini_lite_model) if m))
        now = self.clock()
        ready = [m for m in models if self.model_retry.get(m, 0.0) <= now]
        return ready + [m for m in models if m not in ready]

    async def try_gemini(self, call: Callable[[str], Awaitable[dict[str, Any]]], models: list[str]) -> dict[str, Any] | None:
        if not self.gemini_ready():
            return None
        last: GeminiError | None = None
        for model in models:
            try:
                out = await call(model)
            except GeminiError as e:
                last = e
                log.warning("%s (%s)", e.reason, model)
                if e.backoff:
                    self.model_retry[model] = self.clock() + self.model_cooldown
                continue
            self.model_retry.pop(model, None)
            if self.failures:
                log.info("Gemini volvió")
            self.failures = 0
            self.last = "gemini"
            return out
        if last is not None and last.backoff:
            self.failures += 1
            wait = min(self.max_backoff, self.base_backoff * 2 ** (self.failures - 1))
            self.retry_at = self.clock() + wait
            log.warning("Gemini no respondió con ningún modelo; uso Ollama y reintento en %.0f s", wait)
        return None

    async def complete(self, messages: Messages, lite: bool = False) -> str:
        conf = self.config.brain
        model = conf.gemini_lite_model if lite else conf.gemini_model
        msg = await self.try_gemini(lambda m: self.gemini.generate(m, messages, schema=REPLY_SCHEMA), self.gemini_models(model))
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
        msg = await self.try_gemini(lambda m: self.gemini.generate(m, messages, tools=tools, temperature=0.2), self.gemini_models(model))
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

    async def stream(self, messages: Messages, factual: bool = False) -> AsyncIterator[str]:
        order = ("cloud", "ollama") if self.game or factual else ("ollama", "cloud")
        sources = [s for s in order if s == "ollama" or self.cloud_ready()]
        last: Exception | None = None
        for i, source in enumerate(sources):
            final = i == len(sources) - 1
            wait = self.last_wait if final else self.first_token if source == "ollama" else self.cloud_wait
            gen = self.stream_cloud(messages) if source == "cloud" else self.ollama.stream_chat(self.model, messages, self.gpu, self.stream_tokens)
            try:
                try:
                    async with asyncio.timeout(wait):
                        first = await anext(gen)
                except StopAsyncIteration:
                    log.warning("%s no dio texto", source)
                    continue
                except STREAM_ERRORS as e:
                    last = e
                    log.warning("%s no respondió a tiempo (%r)%s", source, e, "" if final else ", sigo con el siguiente")
                    continue
                self.last = "gemini" if source == "cloud" else "ollama"
                yield first
                async for chunk in gen:
                    yield chunk
                return
            finally:
                await gen.aclose()
        if last is not None:
            raise last

    def cloud_ready(self) -> bool:
        return self.gemini is not None and self.gemini.has_key() and bool(self.cloud_models())

    def cloud_models(self) -> list[str]:
        now = self.clock()
        return [m for m in CLOUD_STREAM if self.model_retry.get(m, 0.0) <= now]

    async def stream_cloud(self, messages: Messages) -> AsyncGenerator[str, None]:
        last: GeminiError | None = None
        for model in self.cloud_models():
            started = False
            try:
                async for chunk in self.stream_gemini(model, messages):
                    started = True
                    yield chunk
            except GeminiError as e:
                if started:
                    raise
                last = e
                log.warning("%s (%s)", e.reason, model)
                if e.backoff:
                    self.model_retry[model] = self.clock() + self.model_cooldown
                continue
            if started:
                self.model_retry.pop(model, None)
                return
        if last is not None:
            raise last

    async def stream_gemini(self, model: str, messages: Messages) -> AsyncGenerator[str, None]:
        assert self.gemini is not None
        g = self.gemini
        key = g.key()
        if not key:
            raise GeminiError("sin key de Gemini")
        system, contents = to_contents(messages)
        for level in range(self.thinking.get(model, 0), len(THINKING)):
            config: dict[str, Any] = {"temperature": 0.8, "maxOutputTokens": self.stream_tokens * 2}
            if THINKING[level] is not None:
                config["thinkingConfig"] = THINKING[level]
            body: dict[str, Any] = {"contents": contents or [{"role": "user", "parts": [{"text": "..."}]}], "generationConfig": config}
            if system:
                body["systemInstruction"] = {"parts": [{"text": system}]}
            try:
                async with g.http.stream(
                    "POST", f"{g.base}/models/{model}:streamGenerateContent", params={"alt": "sse"}, json=body, headers={"x-goog-api-key": key}
                ) as r:
                    if r.status_code != 200:
                        text = g.safe((await r.aread()).decode("utf-8", "replace"), key)
                        if r.status_code == 400 and "think" in text.lower() and THINKING[level] is not None:
                            continue
                        raise cloud_error(r.status_code, text, model)
                    self.thinking[model] = level
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        for chunk in sse_texts(line[5:]):
                            yield chunk
                    return
            except httpx.HTTPError as e:
                raise GeminiError(f"sin red con Gemini ({type(e).__name__})") from None

    async def check(self, full: bool = False) -> bool:
        if await self.ollama.alive():
            if full and not self.game and self.big_model not in await self.ollama.loaded():
                log.info("el modelo %s no estaba cargado; lo precargo", self.big_model)
                await self.ollama.preload(self.big_model, self.profile.num_gpu)
            return True
        log.warning("Ollama no contesta; lo relanzo")
        if not await self.ollama.ensure():
            return False
        if not self.game:
            await self.ollama.preload(self.big_model, self.profile.num_gpu)
        return True

    async def watchdog(self, every: float = 10.0, preload_every: float = 300.0) -> None:
        ticks = 0
        full = max(1, round(preload_every / every))
        while True:
            await asyncio.sleep(every)
            ticks += 1
            try:
                await self.check(ticks % full == 0)
            except Exception as e:
                log.warning("vigilancia de Ollama falló: %r", e)

    async def see(self, image: bytes, prompt: str) -> str:
        message = {"role": "user", "content": prompt, "images": [base64.b64encode(image).decode()]}
        model = self.config.brain.gemini_model
        msg = await self.try_gemini(lambda m: self.gemini.generate(m, [message], temperature=0.3, max_tokens=260), self.gemini_models(model))
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
            self.background(self.ollama.preload(self.big_model, self.profile.num_gpu))

    def warm_up(self) -> None:
        self.background(self.wake_ollama())

    async def wake_ollama(self) -> None:
        if await self.ollama.ensure() and not self.game:
            await self.ollama.preload(self.big_model, self.profile.num_gpu)

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
