import json
import logging
from typing import Any

import httpx

log = logging.getLogger("sapo.gemini")

Messages = list[dict[str, Any]]
BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiError(Exception):
    def __init__(self, reason: str, backoff: bool = True):
        super().__init__(reason)
        self.reason = reason
        self.backoff = backoff


def to_contents(messages: Messages) -> tuple[str, list[dict[str, Any]]]:
    system: list[str] = []
    contents: list[dict[str, Any]] = []

    def push(role: str, parts: list[dict[str, Any]]) -> None:
        if not parts:
            return
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"].extend(parts)
        else:
            contents.append({"role": role, "parts": parts})

    for m in messages:
        role = m.get("role")
        text = m.get("content") or ""
        if role == "system":
            system.append(text)
        elif role == "user":
            parts: list[dict[str, Any]] = [{"text": text}] if text else []
            for image in m.get("images") or []:
                parts.append({"inlineData": {"mimeType": "image/jpeg", "data": image}})
            push("user", parts)
        elif role == "assistant":
            parts = [{"text": text}] if text else []
            for call in m.get("tool_calls") or []:
                raw = call.get("gemini_part")
                if raw:
                    parts.append(raw)
                    continue
                fn = call.get("function") or {}
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args or "{}")
                    except ValueError:
                        args = {}
                parts.append({"functionCall": {"name": fn.get("name", ""), "args": args}})
            push("model", parts)
        elif role == "tool":
            push("user", [{"functionResponse": {"name": m.get("tool_name") or m.get("name") or "tool", "response": {"result": text}}}])
    return "\n\n".join(s for s in system if s), contents


def to_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decls = []
    for t in tools:
        fn = t.get("function") or t
        decls.append({"name": fn["name"], "description": fn.get("description", ""), "parametersJsonSchema": fn.get("parameters") or {"type": "object", "properties": {}}})
    return [{"functionDeclarations": decls}]


def from_response(data: dict[str, Any]) -> dict[str, Any]:
    candidates = data.get("candidates") or []
    if not candidates:
        reason = (data.get("promptFeedback") or {}).get("blockReason") or "sin respuesta"
        raise GeminiError(f"gemini sin candidatos: {reason}", backoff=False)
    parts = (candidates[0].get("content") or {}).get("parts") or []
    texts = [p["text"] for p in parts if isinstance(p.get("text"), str) and not p.get("thought")]
    calls = [
        {"function": {"name": p["functionCall"].get("name", ""), "arguments": p["functionCall"].get("args") or {}}, "gemini_part": p}
        for p in parts
        if isinstance(p.get("functionCall"), dict)
    ]
    message: dict[str, Any] = {"role": "assistant", "content": "".join(texts)}
    if calls:
        message["tool_calls"] = calls
    return message


class Gemini:
    def __init__(self, key, client: httpx.AsyncClient | None = None, base: str = BASE, max_tokens: int = 300):
        self.key = key
        self.base = base.rstrip("/")
        self.max_tokens = max_tokens
        self.http = client or httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5))
        self.no_thinking: dict[str, bool] = {}

    def has_key(self) -> bool:
        return bool(self.key())

    async def generate(
        self,
        model: str,
        messages: Messages,
        tools: list[dict[str, Any]] | None = None,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.9,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        key = self.key()
        if not key:
            raise GeminiError("sin key de Gemini")
        system, contents = to_contents(messages)
        config: dict[str, Any] = {"temperature": temperature, "maxOutputTokens": max_tokens or self.max_tokens}
        if schema is not None and not tools:
            config["responseMimeType"] = "application/json"
            config["responseJsonSchema"] = schema
        body: dict[str, Any] = {"contents": contents or [{"role": "user", "parts": [{"text": "..."}]}], "generationConfig": config}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if tools:
            body["tools"] = to_tools(tools)
        if self.no_thinking.get(model, True):
            config["thinkingConfig"] = {"thinkingBudget": 0}
        r = await self.post(model, body, key)
        if r.status_code == 400 and "thinking" in r.text.lower() and "thinkingConfig" in config:
            self.no_thinking[model] = False
            config.pop("thinkingConfig")
            r = await self.post(model, body, key)
        if r.status_code == 429:
            raise GeminiError("gemini sin cupo (429)")
        if r.status_code in (401, 403) or (r.status_code == 400 and "api key" in r.text.lower()):
            raise GeminiError(f"gemini rechazó la key ({r.status_code})")
        if r.status_code == 404:
            raise GeminiError(f"gemini no conoce el modelo {model}")
        if r.status_code >= 500:
            raise GeminiError(f"gemini caído ({r.status_code})")
        if r.status_code != 200:
            raise GeminiError(f"gemini respondió {r.status_code}: {self.safe(r.text, key)[:200]}", backoff=False)
        try:
            return from_response(r.json())
        except ValueError as e:
            raise GeminiError(f"gemini mandó algo raro: {e}", backoff=False) from e

    async def post(self, model: str, body: dict[str, Any], key: str) -> httpx.Response:
        try:
            return await self.http.post(f"{self.base}/models/{model}:generateContent", json=body, headers={"x-goog-api-key": key})
        except httpx.HTTPError as e:
            raise GeminiError(f"sin red con Gemini ({type(e).__name__})") from None

    async def models(self) -> list[str]:
        key = self.key()
        if not key:
            return []
        try:
            r = await self.http.get(f"{self.base}/models", params={"pageSize": 200}, headers={"x-goog-api-key": key})
        except httpx.HTTPError as e:
            raise GeminiError(f"sin red con Gemini ({type(e).__name__})") from None
        if r.status_code != 200:
            raise GeminiError(f"models.list respondió {r.status_code}")
        try:
            return [m.get("name", "").removeprefix("models/") for m in r.json().get("models", []) if isinstance(m, dict)]
        except (ValueError, AttributeError):
            raise GeminiError("models.list mandó algo raro") from None

    @staticmethod
    def safe(text: str, key: str) -> str:
        return text.replace(key, "***") if key else text
