"""Per-learner request limits on `/api/agent/*` (spec §22).

A sliding window per learner: at most `limit` requests in any `window_seconds`.
A request over the limit is refused before anything runs - no turn, no
provider call, no metering - and told how many seconds remain until the oldest
counted request leaves the window. A refused request is not counted, so a
learner who waits that long gets in.

The key is the authenticated learner: the auth middleware has refused an
anonymous caller before the agent sees it, so a limit per IP would only merge
learners behind one address. The windows live in this process and each worker
counts its own; how many learners are remembered is bounded, least recently
seen forgotten first.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable


class SlidingWindowLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float,
        *,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if limit < 1 or window_seconds <= 0 or max_keys < 1:
            raise ValueError("a limit, a window and a key bound are positive")
        self.limit = limit
        self.window_seconds = float(window_seconds)
        self.max_keys = max_keys
        self._clock = clock
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def check(self, key: str) -> float | None:
        """Count one request for `key`: None when it is allowed, else the seconds to wait."""

        now = self._clock()
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                hits = self._hits[key] = deque()
            else:
                self._hits.move_to_end(key)
            while hits and hits[0] <= now - self.window_seconds:
                hits.popleft()
            if len(hits) >= self.limit:
                return hits[0] + self.window_seconds - now
            hits.append(now)
            while len(self._hits) > self.max_keys:
                self._hits.popitem(last=False)
            return None

    def __len__(self) -> int:
        return len(self._hits)
