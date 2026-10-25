import asyncio
import json
import logging
import random
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from .llm import LLM
from .memory import Memory
from .personality import Persona, Reply, parse_reply
from .protocol import action, say, thinking
from .ratelimit import RateLimiter

log = logging.getLogger("sapo.brain")

Send = Callable[[dict[str, Any]], Awaitable[None]]


class Brain:
    def __init__(
        self,
        llm: LLM,
        memory: Memory,
        persona: Persona,
        send: Send,
        rng: random.Random | None = None,
        history: int = 12,
        event_limiter: RateLimiter | None = None,
        auto_limiter: RateLimiter | None = None,
        llm_timeout: float = 60.0,
        min_delay: float = 120.0,
        max_delay: float = 360.0,
    ):
        self.llm = llm
        self.memory = memory
        self.persona = persona
        self.send = send
        self.rng = rng or random.Random()
        self.history = history
        self.event_limiter = event_limiter or RateLimiter(per_key=25, max_hits=4, window=60)
        self.auto_limiter = auto_limiter or RateLimiter(per_key=60, max_hits=12, window=3600)
        self.llm_timeout = llm_timeout
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.boredom = 0.0
        self.game = False
        self.lock = asyncio.Lock()

    async def handle(self, msg: dict[str, Any]) -> None:
        kind = msg["type"]
        if kind == "hello":
            await self.send(say(self.persona.canned("hello", self.rng), self.persona.mood_for("hello")))
        elif kind == "chat":
            await self.on_chat(msg["text"])
        elif kind == "event":
            await self.on_event(msg["name"], msg.get("boredom", 0.0))

    def build(self, instruction: str | None = None) -> list[dict[str, str]]:
        system = self.persona.system_prompt(self.memory.facts(20), datetime.now())
        messages = [{"role": "system", "content": system}]
        for role, text in self.memory.recent_messages(self.history):
            if role == "user":
                messages.append({"role": "user", "content": text})
            elif role == "sapo":
                messages.append({"role": "assistant", "content": json.dumps({"say": text}, ensure_ascii=False)})
        if instruction:
            messages.append({"role": "user", "content": instruction})
        return messages

    async def think(self, messages: list[dict[str, str]]) -> Reply | None:
        await self.send(thinking(True))
        try:
            raw = await asyncio.wait_for(self.llm.complete(messages), self.llm_timeout)
            return parse_reply(raw)
        except Exception as e:
            log.warning("el LLM falló: %r", e)
            return None
        finally:
            await self.send(thinking(False))

    async def deliver(self, reply: Reply) -> None:
        if reply.fact:
            self.memory.add_fact(reply.fact)
        if reply.say:
            self.memory.add_message("sapo", reply.say)
            await self.send(say(reply.say, reply.mood))
        if reply.action != "none":
            await self.send(action(reply.action))

    async def on_chat(self, text: str) -> None:
        async with self.lock:
            messages = self.build(text)
            self.memory.add_message("user", text)
            reply = await self.think(messages)
        if reply is None or not reply.say:
            reply = Reply(self.persona.canned("error", self.rng), self.persona.mood_for("error"))
        await self.deliver(reply)

    async def on_event(self, name: str, boredom: float) -> None:
        self.boredom = boredom
        self.memory.add_event(name, boredom)
        if name == "game_on":
            self.game = True
            await self.llm.set_game(True)
            await self.send(say(self.persona.canned(name, self.rng), self.persona.mood_for(name)))
            await self.send(action("sleep"))
            return
        if name == "game_off":
            self.game = False
            await self.llm.set_game(False)
            await self.send(say(self.persona.canned(name, self.rng), self.persona.mood_for(name)))
            return
        if self.game or not self.event_limiter.allow(name):
            return
        if self.lock.locked():
            await self.send(say(self.persona.canned(name, self.rng), self.persona.mood_for(name)))
            return
        async with self.lock:
            reply = await self.think(self.build(self.persona.event_prompt(name, boredom)))
        if reply is None or not reply.say:
            reply = Reply(self.persona.canned(name, self.rng), self.persona.mood_for(name))
        await self.deliver(reply)

    def next_delay(self) -> float:
        return self.rng.uniform(self.min_delay, self.max_delay) * (1.0 - 0.6 * self.boredom)

    async def tick(self) -> bool:
        if self.game or self.lock.locked() or not self.auto_limiter.allow("auto"):
            return False
        age = self.memory.last_chat_age()
        idle = None if age is None else int(age // 60)
        async with self.lock:
            reply = await self.think(self.build(self.persona.autonomous_prompt(self.boredom, idle)))
        if reply is None:
            return False
        await self.deliver(reply)
        return bool(reply.say or reply.action != "none")

    async def autonomous_loop(self) -> None:
        while True:
            await asyncio.sleep(self.next_delay())
            try:
                await self.tick()
            except Exception as e:
                log.warning("tick autónomo falló: %r", e)
