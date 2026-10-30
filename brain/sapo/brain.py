import asyncio
import json
import logging
import random
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from .attention import Attention, Foreground
from .config import LiveConfig, static_config
from .llm import LLM
from .memory import Memory
from .personality import Persona, Reply, clip, parse_reply
from .phrases import RecentPhrases
from .protocol import action, confirm, croak, quiet, say, thinking
from .ratelimit import RateLimiter
from .tools import Toolbox, parse_yes_no, wants_tools

log = logging.getLogger("sapo.brain")

Send = Callable[[dict[str, Any]], Awaitable[None]]
Capture = Callable[[Foreground], bytes]
INTERACTIONS = {"petted", "thrown"}
SPONTANEOUS = {"ignored"}


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
        tools: Toolbox | None = None,
        confirm_timeout: float = 30.0,
        max_calls: int = 4,
        config: LiveConfig | None = None,
        attention: Attention | None = None,
        capture: Capture | None = None,
        clock: Callable[[], float] = time.monotonic,
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
        self.tools = tools
        self.confirm_timeout = confirm_timeout
        self.max_calls = max_calls
        self.pending: dict[str, asyncio.Future] = {}
        self.config = config or static_config()
        self.attention = attention
        self.capture = capture
        self.clock = clock
        self.recent = RecentPhrases(seed=memory.recent_said(50))
        self.last_spontaneous = float("-inf")
        self.gap = 0.0
        self.awaiting = False
        self.quiet_reason: str | None = None
        if tools is not None:
            tools.notify = self.remind

    async def handle(self, msg: dict[str, Any]) -> None:
        kind = msg["type"]
        if kind == "hello":
            await self.send(say(self.persona.canned("hello", self.rng), self.persona.mood_for("hello")))
        elif kind == "chat":
            await self.on_chat(msg["text"])
        elif kind == "event":
            await self.on_event(msg["name"], msg.get("boredom", 0.0))
        elif kind == "confirm_reply":
            self.interacted()
            self.answer(msg["ok"], msg["id"])

    def quiet(self) -> bool:
        return self.game or (self.attention is not None and self.config.brain.attention and self.attention.quiet)

    def quiet_cause(self) -> str | None:
        if self.game:
            return "game"
        if self.attention is None or not self.config.brain.attention:
            return None
        if self.attention.call:
            return "call"
        if self.attention.fullscreen:
            return "fullscreen"
        return None

    async def sync_quiet(self) -> None:
        cause = self.quiet_cause()
        if cause == self.quiet_reason:
            return
        if cause is None:
            await self.send(quiet(False, self.quiet_reason or "game"))
        else:
            await self.send(quiet(True, cause))
        self.quiet_reason = cause

    def interacted(self) -> None:
        self.awaiting = False

    def spontaneous_ok(self) -> bool:
        if self.quiet() or self.awaiting:
            return False
        return self.clock() - self.last_spontaneous >= self.gap

    def spoke(self) -> None:
        self.last_spontaneous = self.clock()
        self.gap = self.config.brain.comment_minutes * 60 * self.rng.uniform(0.85, 1.5)
        self.awaiting = True

    def activity(self) -> str:
        if self.attention is None or not self.config.brain.attention:
            return ""
        return self.persona.activity_text(self.attention.describe())

    def build(self, instruction: str | None = None) -> list[dict[str, Any]]:
        system = self.persona.system_prompt(self.memory.facts(20), datetime.now(), self.config.brain.personality, self.activity())
        messages = [{"role": "system", "content": system}]
        for role, text in self.memory.recent_messages(self.history):
            if role == "user":
                messages.append({"role": "user", "content": text})
            elif role == "sapo":
                messages.append({"role": "assistant", "content": json.dumps({"say": text}, ensure_ascii=False)})
        if instruction:
            messages.append({"role": "user", "content": instruction})
        return messages

    async def ask_llm(self, messages: list[dict[str, Any]], lite: bool) -> Reply:
        raw = await asyncio.wait_for(self.llm.complete(messages, lite=lite), self.llm_timeout)
        return parse_reply(raw)

    async def fresh(self, messages: list[dict[str, Any]], lite: bool = False, strict: bool = False) -> Reply:
        reply = await self.ask_llm(messages, lite)
        seen = self.recent.match(reply.say) if reply.say else None
        if seen is None:
            return reply
        log.info("frase repetida (%r ~ %r), regenero", reply.say, seen)
        again = await self.ask_llm(messages + [{"role": "user", "content": self.persona.retry_prompt(seen)}], lite)
        if again.say and not self.recent.repeats(again.say):
            return again
        if strict:
            return Reply("", reply.mood, reply.action)
        return again if again.say else reply

    async def think(self, messages: list[dict[str, Any]], lite: bool = False, strict: bool = False) -> Reply | None:
        await self.send(thinking(True))
        try:
            return await self.fresh(messages, lite, strict)
        except Exception as e:
            log.warning("el LLM falló: %r", e)
            return None
        finally:
            await self.send(thinking(False))

    async def think_tools(self, messages: list[dict[str, Any]]) -> Reply | None:
        assert self.tools is not None
        await self.send(thinking(True))
        used = False
        try:
            msg = await asyncio.wait_for(self.llm.chat_tools(messages, self.tools.specs()), self.llm_timeout)
            calls = [c for c in msg.get("tool_calls") or [] if (c.get("function") or {}).get("name") in self.tools.tools]
            if not calls:
                return await self.fresh(messages)
            used = True
            messages = messages + [{"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls[: self.max_calls]}]
            for call in calls[: self.max_calls]:
                fn = call["function"]
                name = fn["name"]
                log.info("herramienta %s(%s)", name, fn.get("arguments"))
                result = await self.tools.run(name, fn.get("arguments") or {}, game=self.game, ask=self.ask)
                log.info("resultado %s: %s", name, result.text)
                if result.blocked:
                    return Reply(self.persona.canned("game_block", self.rng), self.persona.mood_for("game_block"))
                messages.append({"role": "tool", "tool_name": name, "content": result.text})
            messages.append({"role": "user", "content": self.persona.strings["tool_wrap"]})
            reply = await self.fresh(messages)
            return reply if reply.say else Reply(self.persona.canned("done", self.rng), self.persona.mood_for("done"))
        except Exception as e:
            log.warning("el LLM con herramientas falló: %r", e)
            return Reply(self.persona.canned("done", self.rng), self.persona.mood_for("done")) if used else None
        finally:
            await self.send(thinking(False))

    async def ask(self, question: str) -> bool:
        cid = uuid.uuid4().hex[:8]
        future = asyncio.get_running_loop().create_future()
        self.pending[cid] = future
        await self.send(thinking(False))
        await self.send(confirm(cid, question))
        try:
            return bool(await asyncio.wait_for(future, self.confirm_timeout))
        except TimeoutError:
            return False
        finally:
            self.pending.pop(cid, None)
            await self.send(thinking(True))

    def answer(self, ok: bool, cid: str | None = None) -> bool:
        ids = [cid] if cid else list(self.pending)
        hit = False
        for key in ids:
            future = self.pending.get(key)
            if future is not None and not future.done():
                future.set_result(ok)
                hit = True
        return hit

    async def remind(self, text: str) -> None:
        line = self.persona.strings["reminder"].replace("{texto}", text)
        self.memory.add_message("sapo", line)
        await self.send(say(line, self.persona.mood_for("reminder")))
        await self.send(action("jump"))

    async def deliver(self, reply: Reply) -> None:
        if reply.fact:
            self.memory.add_fact(reply.fact)
        if reply.say:
            self.memory.add_message("sapo", reply.say)
            self.recent.add(reply.say)
            await self.send(say(reply.say, reply.mood))
        if reply.action != "none":
            await self.send(action(reply.action))

    async def on_chat(self, text: str) -> None:
        self.interacted()
        if self.pending:
            answer = parse_yes_no(text)
            self.answer(bool(answer))
            if answer is not None:
                return
        async with self.lock:
            messages = self.build(text)
            self.memory.add_message("user", text)
            use_tools = self.tools is not None and wants_tools(text, self.persona.strings["tool_words"])
            reply = await (self.think_tools(messages) if use_tools else self.think(messages))
        if reply is None or not reply.say:
            reply = Reply(self.persona.canned("error", self.rng), self.persona.mood_for("error"))
        await self.deliver(reply)

    async def on_event(self, name: str, boredom: float) -> None:
        self.boredom = boredom
        self.memory.add_event(name, boredom)
        if name == "game_on":
            self.game = True
            await self.sync_quiet()
            await self.llm.set_game(True)
            await self.send(action("sleep"))
            return
        if name == "game_off":
            self.game = False
            await self.sync_quiet()
            await self.llm.set_game(False)
            await self.send(say(self.persona.canned(name, self.rng), self.persona.mood_for(name)))
            return
        if name in INTERACTIONS:
            self.interacted()
        if self.quiet() or not self.event_limiter.allow(name):
            return
        spontaneous = name in SPONTANEOUS
        if spontaneous and not self.spontaneous_ok():
            return
        if self.lock.locked():
            if not spontaneous:
                await self.send(say(self.persona.canned(name, self.rng), self.persona.mood_for(name)))
            return
        async with self.lock:
            reply = await self.think(self.build(self.persona.event_prompt(name, boredom)), lite=True, strict=True)
        if reply is None or not reply.say:
            reply = Reply(self.persona.canned(name, self.rng), self.persona.mood_for(name))
        await self.deliver(reply)
        if spontaneous:
            self.spoke()

    def next_delay(self) -> float:
        return self.rng.uniform(self.min_delay, self.max_delay) * (1.0 - 0.6 * self.boredom)

    async def tick(self) -> bool:
        if not self.spontaneous_ok() or self.lock.locked() or not self.auto_limiter.allow("auto"):
            return False
        age = self.memory.last_chat_age()
        idle = None if age is None else int(age // 60)
        async with self.lock:
            reply = await self.think(self.build(self.persona.autonomous_prompt(self.boredom, idle)), lite=True, strict=True)
        if reply is None:
            return False
        await self.deliver(reply)
        if reply.say:
            self.spoke()
        return bool(reply.say or reply.action != "none")

    async def attend(self) -> bool:
        att = self.attention
        conf = self.config.brain
        if att is None or not conf.attention or self.lock.locked():
            return False
        fg = att.pending()
        if fg is None or not self.spontaneous_ok():
            return False
        att.mark_commented()
        info = att.describe()
        view = ""
        see = getattr(self.llm, "see", None)
        if self.capture is not None and see is not None and not self.game and att.wants_vision(conf.vision):
            att.captured()
            try:
                image = await asyncio.to_thread(self.capture, fg)
                view = clip(await asyncio.wait_for(see(image, self.persona.strings["vision_prompt"]), self.llm_timeout), 160)
            except Exception as e:
                log.warning("no pude ver la ventana: %r", e)
        async with self.lock:
            reply = await self.think(self.build(self.persona.attention_prompt(info["app"], info["title"], info["here"], view)), lite=True, strict=True)
        if reply is None or not reply.say:
            return False
        await self.deliver(reply)
        self.spoke()
        return True

    async def watch(self, read: Callable[[], Foreground | None], idle: Callable[[], float] = lambda: 0.0, every: float = 3.0) -> None:
        assert self.attention is not None
        while True:
            await asyncio.sleep(every)
            if not self.config.brain.attention:
                continue
            try:
                fg = await asyncio.to_thread(read)
                self.attention.observe(fg, self.config.brain.blacklist, idle())
                await self.sync_quiet()
                await self.attend()
            except Exception as e:
                log.warning("atención falló: %r", e)

    async def autonomous_loop(self) -> None:
        while True:
            await asyncio.sleep(self.next_delay())
            try:
                await self.tick()
            except Exception as e:
                log.warning("tick autónomo falló: %r", e)
