import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self,
        per_key: float,
        max_hits: int,
        window: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.per_key = per_key
        self.max_hits = max_hits
        self.window = window
        self.clock = clock
        self.last: dict[str, float] = {}
        self.hits: deque[float] = deque()

    def allow(self, key: str = "") -> bool:
        now = self.clock()
        while self.hits and now - self.hits[0] >= self.window:
            self.hits.popleft()
        if len(self.hits) >= self.max_hits:
            return False
        previous = self.last.get(key)
        if previous is not None and now - previous < self.per_key:
            return False
        self.last[key] = now
        self.hits.append(now)
        return True
