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
from .config import PROMPTS, LiveConfig, static_config
from .files import read_drop
from .facts import arithmetic, asks_fact, verified
from .llm import LLM
from .memory import Memory
from .personality import Persona, Reply, Sentences, clip, parse_reply, personal
from .phrases import RecentPhrases
from .protocol import MAX_SAY, action, confirm, croak, next_id, quiet, say, say_end, say_part, say_start, thinking
from .ratelimit import RateLimiter
from .tools import Result, Toolbox, clip_seconds, parse_yes_no, wants_clip, wants_tools

log = logging.getLogger("sapo.brain")

Send = Callable[[dict[str, Any]], Awaitable[None]]
Capture = Callable[[Foreground], bytes]
Done = list[tuple[dict[str, Any], Result]]
INTERACTIONS = {"petted", "thrown"}
SPONTANEOUS = {"ignored"}
URGENT_WIN = {"battery_low", "offline"}


class Spoken:
    def __init__(self) -> None:
        self.sid = ""
        self.parts: list[str] = []
        self.full = False

    @property
    def text(self) -> str:
        return " ".join(self.parts)


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
        style: Callable[[], str] | None = None,
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
        self.style = style
        self.on_change: list[Callable[[], None]] = []
        self.streaming: asyncio.Task | None = None
        self.silenced: asyncio.Task | None = None
        self.chat_history = 6
        self.chat_chars = 1200
        self.fact_chars = 500
        neutral = PROMPTS / f"{persona.lang}_tools.md"
        self.tools_prompt = neutral.read_text(encoding="utf-8") if neutral.is_file() else ""
        if tools is not None:
            tools.notify = self.remind
            tools.emit = self.relay

    async def handle(self, msg: dict[str, Any]) -> None:
        kind = msg["type"]
        if kind == "hello":
            await self.send(say(self.persona.canned("hello", self.rng), self.persona.mood_for("hello")))
        elif kind == "chat":
            await self.on_chat(msg["text"])
        elif kind == "event" and msg["name"] == "file_drop":
            await self.on_file_drop(msg["path"])
        elif kind == "event" and msg["name"] == "win":
            await self.on_win(msg["what"])
        elif kind == "event":
            await self.on_event(msg["name"], msg.get("boredom", 0.0))
        elif kind == "confirm_reply":
            self.interacted()
            self.answer(msg["ok"], msg["id"])
        elif kind == "hush":
            self.hush()

    def hush(self) -> bool:
        task = self.streaming
        if task is None or task.done() or self.silenced is task:
            return False
        self.silenced = task
        task.cancel()
        return True

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
        self.changed()

    def changed(self) -> None:
        for listener in list(self.on_change):
            try:
                listener()
            except Exception as e:
                log.warning("aviso de cambio falló: %r", e)

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
        personality = self.config.brain.personality
        style = self.style() if personality == "como_yo" and self.style is not None else ""
        system = self.persona.system_prompt(self.memory.facts(20), datetime.now(), personality, self.activity(), style)
        messages = [{"role": "system", "content": system}]
        for role, text in self.memory.recent_messages(self.history):
            if role == "user":
                messages.append({"role": "user", "content": text})
            elif role == "sapo":
                messages.append({"role": "assistant", "content": json.dumps({"say": text}, ensure_ascii=False)})
        if instruction:
            messages.append({"role": "user", "content": instruction})
        return messages

    def chat_messages(self, instruction: str) -> list[dict[str, Any]]:
        personality = self.config.brain.personality
        style = self.style() if personality == "como_yo" and self.style is not None else ""
        facts: list[str] = []
        used = 0
        for fact in self.memory.facts(20):
            if used + len(fact) > self.fact_chars:
                break
            facts.append(fact)
            used += len(fact)
        system = self.persona.chat_prompt(facts, datetime.now(), personality, self.activity(), style)
        past: list[dict[str, Any]] = []
        used = 0
        for role, text in reversed(self.memory.recent_messages(self.chat_history)):
            if role not in ("user", "sapo"):
                continue
            text = clip(text, 300)
            if used + len(text) > self.chat_chars:
                break
            past.append({"role": "user" if role == "user" else "assistant", "content": text})
            used += len(text)
        return [{"role": "system", "content": system}, *reversed(past), {"role": "user", "content": instruction}]

    @staticmethod
    def noted(text: str) -> str:
        note = verified(text)
        return text if note is None else f"{text}\n\n[{note}]"

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

    def route(self, text: str) -> str:
        if self.tools is not None and wants_clip(text):
            return "clip"
        if arithmetic(text) is not None:
            return "calc"
        if self.tools is not None and wants_tools(text, self.persona.strings["tool_words"]):
            return "tools"
        return "chat"

    def neutral(self, text: str) -> list[dict[str, Any]]:
        return [{"role": "system", "content": self.tools_prompt}, {"role": "user", "content": text}]

    async def act(self, text: str) -> Done:
        assert self.tools is not None
        msg = await asyncio.wait_for(self.llm.chat_tools(self.neutral(text), self.tools.specs()), self.llm_timeout)
        calls = [c for c in msg.get("tool_calls") or [] if (c.get("function") or {}).get("name") in self.tools.tools]
        done: Done = []
        for call in calls[: self.max_calls]:
            fn = call["function"]
            log.info("herramienta %s(%s)", fn["name"], fn.get("arguments"))
            result = await self.tools.run(fn["name"], fn.get("arguments") or {}, game=self.game, ask=self.ask)
            log.info("resultado %s: %s", fn["name"], result.text)
            done.append((call, result))
            if result.blocked:
                break
        return done

    async def attempt(self, text: str) -> Done:
        try:
            return await self.act(text)
        except Exception as e:
            log.warning("la pasada de herramientas falló: %r", e)
            return []

    def verdict(self, done: Done) -> Reply | None:
        if any(r.blocked for _, r in done):
            return self.canned("game_block")
        if done and not any(r.ok for _, r in done):
            reason = done[0][1].text.removeprefix("error: ").strip()
            return self.canned("tool_failed", motivo=reason or "algo falló")
        return None

    def tool_note(self, done: Done) -> str:
        if not done:
            return self.persona.strings["tool_none"]
        lines = [f"{c['function']['name']}: {r.text}" if r.ok else f"{c['function']['name']}: NO SE PUDO ({r.text})" for c, r in done]
        return self.persona.strings["tool_said"].replace("{resultados}", "; ".join(lines))

    async def think_tools(self, text: str, messages: list[dict[str, Any]]) -> Reply | None:
        await self.send(thinking(True))
        try:
            done = await self.attempt(text)
            verdict = self.verdict(done)
            if verdict is not None:
                return verdict
            if not done:
                return await self.fresh(messages[:-1] + [{"role": "user", "content": f"{messages[-1]['content']}\n\n[{self.tool_note(done)}]"}])
            calls = [c for c, _ in done]
            messages = messages + [{"role": "assistant", "content": "", "tool_calls": calls}]
            messages += [{"role": "tool", "tool_name": c["function"]["name"], "content": r.text} for c, r in done]
            messages.append({"role": "user", "content": self.persona.strings["tool_wrap"]})
            reply = await self.fresh(messages)
            return reply if reply.say else self.canned("done")
        except Exception as e:
            log.warning("el LLM con herramientas falló: %r", e)
            return None
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

    async def relay(self, msg: dict[str, Any]) -> None:
        await self.send(msg)

    def canned(self, key: str, **values: Any) -> Reply:
        text = self.persona.canned(key, self.rng)
        for k, v in values.items():
            text = text.replace("{" + k + "}", str(v))
        return Reply(text, self.persona.mood_for(key))

    async def canned_reply(self, key: str, **values: Any) -> None:
        await self.deliver(self.canned(key, **values))

    async def quick_clip(self, text: str) -> Reply:
        assert self.tools is not None
        self.memory.add_message("user", text)
        result = await self.tools.take_clip(clip_seconds(text))
        if result.state == "saved" and result.via != "native":
            return self.canned("clip_external", app="Medal" if result.via == "medal" else "la Game Bar")
        if result.state == "saved":
            return self.canned("clip_saved", n=round(result.seconds or 0))
        if result.reason == "off":
            return self.canned("clip_off")
        return self.canned("clip_error")

    async def on_file_drop(self, path: str) -> None:
        self.interacted()
        self.memory.add_event("file_drop", self.boredom)
        drop = await asyncio.to_thread(read_drop, path, self.config.brain.blacklist)
        if drop.kind == "refused":
            await self.canned_reply({"sensitive": "file_refused", "big": "file_big"}.get(drop.reason, "file_unreadable"))
            return
        content = drop.text
        if drop.kind == "image":
            see = getattr(self.llm, "see", None)
            if see is None:
                await self.canned_reply("file_unreadable")
                return
            await self.send(thinking(True))
            try:
                content = clip(await asyncio.wait_for(see(drop.image, self.persona.strings["file_vision"]), self.llm_timeout), 600)
            except Exception as e:
                log.warning("no pude ver la imagen: %r", e)
                content = ""
            finally:
                await self.send(thinking(False))
            if not content:
                await self.canned_reply("file_unreadable")
                return
        async with self.lock:
            reply = await self.think(self.build(self.persona.file_prompt(drop.name, drop.kind, content)))
        if reply is None or not reply.say:
            await self.canned_reply("file_unreadable")
            return
        await self.deliver(reply)

    async def on_win(self, what: str) -> None:
        name = f"win_{what}"
        self.memory.add_event(name, self.boredom)
        if self.quiet():
            return
        urgent = what in URGENT_WIN
        if not urgent and not self.spontaneous_ok():
            return
        if not self.event_limiter.allow("win"):
            return
        if self.lock.locked():
            if urgent:
                await self.canned_reply(name)
            return
        async with self.lock:
            reply = await self.think(self.build(self.persona.event_prompt(name, self.boredom)), lite=True, strict=True)
        if reply is None or not reply.say:
            reply = Reply(self.persona.canned(name, self.rng), self.persona.mood_for(name))
        await self.deliver(reply)
        if not urgent:
            self.spoke()

    async def remind(self, text: str) -> None:
        line = self.persona.strings["reminder"].replace("{texto}", text)
        self.memory.add_message("sapo", line)
        await self.send(say(line, self.persona.mood_for("reminder")))
        await self.send(action("jump"))

    def remember(self, reply: Reply) -> None:
        if reply.fact:
            self.memory.add_fact(reply.fact)
        if reply.say:
            self.memory.add_message("sapo", reply.say)
            self.recent.add(reply.say)

    async def deliver(self, reply: Reply) -> None:
        self.remember(reply)
        if reply.say:
            await self.send(say(reply.say, reply.mood))
        if reply.action != "none":
            await self.send(action(reply.action))

    async def respond(self, text: str) -> Reply:
        kind = self.route(text)
        if kind == "clip":
            return await self.quick_clip(text)
        async with self.lock:
            messages = self.build(self.noted(text))
            self.memory.add_message("user", text)
            reply = await (self.think_tools(text, messages) if kind == "tools" else self.think(messages))
        if reply is None or not reply.say:
            reply = self.canned("error")
        return reply

    def streams(self, text: str) -> bool:
        if getattr(self.llm, "stream", None) is None:
            return False
        return self.route(text) != "clip"

    async def compose(self, text: str) -> tuple[list[dict[str, Any]], bool, Reply | None]:
        kind = self.route(text)
        instruction = self.noted(text)
        factual = asks_fact(text) and kind == "chat"
        if kind == "tools":
            done = await self.attempt(text)
            verdict = self.verdict(done)
            if verdict is not None:
                return [], False, verdict
            instruction = f"{instruction}\n\n[{self.tool_note(done)}]"
            factual = asks_fact(text) and not done
        return self.chat_messages(instruction), factual, None

    async def put(self, spoken: Spoken, part: str, mood: str, live: bool) -> None:
        room = MAX_SAY - len(spoken.text) - (1 if spoken.parts else 0)
        if len(part) > room:
            spoken.full = True
            part = clip(part, room) if room >= 8 else ""
            if not part:
                return
        if live:
            if not spoken.sid:
                spoken.sid = next_id()
                await self.send(thinking(False))
                await self.send(say_start(spoken.sid, mood))
            await self.send(say_part(spoken.sid, part))
        spoken.parts.append(part)

    async def pump(self, messages: list[dict[str, Any]], live: bool = True, factual: bool = False) -> Reply | None:
        cut = Sentences()
        spoken = Spoken()
        stream = getattr(self.llm, "stream")
        gen = stream(messages, factual=True) if factual else stream(messages)
        try:
            async with asyncio.timeout(self.llm_timeout):
                async for chunk in gen:
                    for part in cut.feed(chunk):
                        await self.put(spoken, part, cut.mood, live)
                    if spoken.full:
                        break
                if not spoken.full:
                    for part in cut.flush():
                        await self.put(spoken, part, cut.mood, live)
        except asyncio.CancelledError:
            task = asyncio.current_task()
            if task is None or self.silenced is not task:
                raise
            task.uncancel()
            log.info("me callaron a media frase")
        except Exception as e:
            log.warning("el streaming falló: %r", e)
        finally:
            await gen.aclose()
        hushed = self.silenced is asyncio.current_task()
        if spoken.sid:
            await self.send(say_end(spoken.sid, "none" if hushed else cut.action))
        else:
            await self.send(thinking(False))
        if not spoken.parts:
            return None
        return Reply(spoken.text, cut.mood, "none" if hushed else cut.action, cut.fact)

    async def respond_stream(self, text: str) -> None:
        hushed = False
        reply = None
        async with self.lock:
            await self.send(thinking(True))
            messages, factual, verdict = await self.compose(text)
            self.memory.add_message("user", text)
            if verdict is None:
                task = asyncio.create_task(self.pump(messages, factual=factual))
                self.streaming = task
                try:
                    reply = await task
                finally:
                    if self.streaming is task:
                        self.streaming = None
                hushed = self.silenced is task
                if reply is not None:
                    if not personal(text):
                        reply.fact = ""
                    self.remember(reply)
        if verdict is not None:
            await self.send(thinking(False))
            await self.deliver(verdict)
        elif reply is None and not hushed:
            await self.deliver(self.canned("error"))

    async def respond_full(self, text: str) -> Reply:
        if not self.streams(text):
            return await self.respond(text)
        async with self.lock:
            await self.send(thinking(True))
            messages, factual, verdict = await self.compose(text)
            self.memory.add_message("user", text)
            if verdict is not None:
                await self.send(thinking(False))
                return verdict
            reply = await self.pump(messages, live=False, factual=factual)
        if reply is not None and not personal(text):
            reply.fact = ""
        return reply or self.canned("error")

    async def on_chat(self, text: str) -> None:
        self.interacted()
        if self.pending:
            answer = parse_yes_no(text)
            self.answer(bool(answer))
            if answer is not None:
                return
        if self.streams(text):
            await self.respond_stream(text)
        else:
            await self.deliver(await self.respond(text))

    async def on_phone(self, text: str) -> str:
        reply = await self.respond_full(text)
        self.remember(reply)
        return reply.say

    async def on_event(self, name: str, boredom: float) -> None:
        self.boredom = boredom
        self.memory.add_event(name, boredom)
        if name == "game_on":
            self.game = True
            self.changed()
            await self.sync_quiet()
            await self.llm.set_game(True)
            await self.send(action("sleep"))
            return
        if name == "game_off":
            self.game = False
            self.changed()
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
                self.changed()
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
