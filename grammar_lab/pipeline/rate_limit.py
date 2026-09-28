"""Client-side rate limiting shared across call sites on the same quota.

SPEC has no quota rule of its own -- this is operational: the Grammar Lab
Gemini key is shared with the Orena Intelligence lane's live traffic and was
measured at ~25-30 requests/minute before 429s start. Both
``llm_client.py``'s Gemini calls and ``evaluator_client.py``'s calls into a
sandbox whose engine is configured for the same Gemini key draw on the same
quota, so they share one named limiter (looked up by a fixed key such as
``"gemini"``) rather than each independently budgeting ~25/min, which
combined would double the real rate against the account.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field

# ~10/min combined budget: comfortably under the measured ~25-30/min ceiling,
# leaving headroom for the Intelligence lane's own concurrent traffic on the
# same key.
GEMINI_MIN_INTERVAL_SECONDS = 6.0


@dataclass
class RateLimiter:
    min_interval_seconds: float
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    _last_call: float = field(default=0.0, repr=False, compare=False)

    def wait(self) -> None:
        """Block, if needed, so consecutive calls stay >= min_interval_seconds apart."""
        with self._lock:
            now = time.monotonic()
            remaining = self.min_interval_seconds - (now - self._last_call)
            if remaining > 0:
                time.sleep(remaining)
            self._last_call = time.monotonic()


_limiters: dict[str, RateLimiter] = {}
_registry_lock = threading.Lock()


def limiter_for(key: str, min_interval_seconds: float) -> RateLimiter:
    """The process-wide limiter named ``key``, created on first use.

    ``min_interval_seconds`` only takes effect the first time a given
    ``key`` is requested; later calls reuse the existing limiter as-is so
    concurrent callers agreeing on the same key always share one clock.
    """
    with _registry_lock:
        existing = _limiters.get(key)
        if existing is None:
            existing = RateLimiter(min_interval_seconds)
            _limiters[key] = existing
        return existing


def reset_for_tests() -> None:
    with _registry_lock:
        _limiters.clear()


def backoff_delay(attempt: int, *, base: float = 5.0, cap: float = 60.0) -> float:
    """Exponential backoff with jitter for a rate-limited (429) retry."""
    delay = min(cap, base * (2**attempt))
    return delay + random.uniform(0, delay * 0.25)
