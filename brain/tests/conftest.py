import asyncio
import json
import random

import pytest

from sapo.brain import Brain
from sapo.memory import Memory
from sapo.personality import Persona
from sapo.ratelimit import RateLimiter


class FakeLLM:
    def __init__(self, replies=None, delay=0.0, fail=False):
        self.replies = list(replies or [])
        self.delay = delay
        self.fail = fail
        self.calls: list[list[dict]] = []
        self.game_calls: list[bool] = []

    async def complete(self, messages):
        self.calls.append(messages)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise ConnectionError("sin red")
        if self.replies:
            return self.replies.pop(0)
        return json.dumps({"say": "Croac falso", "mood": "happy", "action": "none"})

    async def set_game(self, on):
        self.game_calls.append(on)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture
def memory():
    m = Memory(":memory:")
    yield m
    m.close()


@pytest.fixture
def persona():
    return Persona("es")


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def outbox():
    return []


@pytest.fixture
def make_brain(memory, persona, outbox, clock):
    def factory(llm, **kw):
        async def send(msg):
            outbox.append(msg)

        kw.setdefault("event_limiter", RateLimiter(per_key=25, max_hits=4, window=60, clock=clock))
        kw.setdefault("auto_limiter", RateLimiter(per_key=60, max_hits=12, window=3600, clock=clock))
        return Brain(llm, memory, persona, send, rng=random.Random(1), **kw)

    return factory
