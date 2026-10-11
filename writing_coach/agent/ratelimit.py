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

Best effort, not a quota (independent review 2026-10-04, P2): with N workers a
learner can make up to N times the limit, and a restart forgets every window.
It protects one process from a burst; it is not the account's spending limit.
An authoritative shared quota (per account, across workers) is required before
a multi-worker or public rollout of the agent - an activation condition, not
this module's job (AGENT_SPEC §0 R26).
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable


class SlidingWindowLimiter:
    """`limit` and `window_seconds` may be numbers or callables returning one: a callable is read at each check, so an
    operator's change (Platform Admin, D-172) applies to the next request without a new limiter or a restart."""

    def __init__(
        self,
        limit: int | Callable[[], int],
        window_seconds: float | Callable[[], float],
        *,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        # A fixed number is judged now; a callable is judged (and floored) at each check, so a bad reading never turns
        # a limiter into a refuse-everything or an allow-everything one.
        if (not callable(limit) and limit < 1) or (not callable(window_seconds) and window_seconds <= 0) or max_keys < 1:
            raise ValueError("a limit, a window and a key bound are positive")
        self.max_keys = max_keys
        self._clock = clock
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    @property
    def limit(self) -> int:
        value = self._limit() if callable(self._limit) else self._limit
        return max(1, int(value))

    @limit.setter
    def limit(self, value: int | Callable[[], int]) -> None:
        self._limit = value

    @property
    def window_seconds(self) -> float:
        value = self._window() if callable(self._window) else self._window
        return float(value) if value and float(value) > 0 else 1.0

    @window_seconds.setter
    def window_seconds(self, value: float | Callable[[], float]) -> None:
        self._window = value

    def check(self, key: str) -> float | None:
        """Count one request for `key`: None when it is allowed, else the seconds to wait."""

        now = self._clock()
        limit, window = self.limit, self.window_seconds
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                hits = self._hits[key] = deque()
            else:
                self._hits.move_to_end(key)
            while hits and hits[0] <= now - window:
                hits.popleft()
            if len(hits) >= limit:
                return hits[0] + window - now
            hits.append(now)
            while len(self._hits) > self.max_keys:
                self._hits.popitem(last=False)
            return None

    def __len__(self) -> int:
        return len(self._hits)
