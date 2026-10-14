"""In-process router counters, flushed as one `ai.router.rollup` audit row per capability each minute.

There is no audit row per tap (D-18X): the per-call `ai.operation` rows already carry tokens, cost, latency, tier
and the fallback reason for every provider call, and a cache hit makes no call. These counters add what those rows
cannot: requests, cache hits, fallbacks and the model that actually answered. They hold counts and model ids only -
never a word, a prompt or an answer.
"""

from __future__ import annotations

import threading
from collections import Counter, defaultdict
from collections.abc import Callable
from typing import Any

ROLLUP_ACTION = "ai.router.rollup"
ROLLUP_ACTOR = "system:ai-router"
FLUSH_SECONDS = 60.0


class RouterStats:
    def __init__(self, clock: Callable[[], float], router_version: str) -> None:
        self._clock = clock
        self._version = router_version
        self._lock = threading.Lock()
        self._counters: dict[str, Counter] = defaultdict(Counter)
        self._models: dict[str, Counter] = defaultdict(Counter)
        self._last_flush = clock()

    def count(self, capability: str, counter: str, amount: int | float = 1) -> None:
        if amount:
            with self._lock:
                self._counters[capability][counter] += amount

    def model_answered(self, capability: str, provider: str, model: str) -> None:
        with self._lock:
            self._models[capability][f"{provider}/{model}"] += 1

    def due(self) -> bool:
        return self._clock() - self._last_flush >= FLUSH_SECONDS

    def flush(self, recorder: Callable[..., Any] | None, *, force: bool = False) -> int:
        """Write one row per capability that counted anything; returns how many were written."""

        if not force and not self.due():
            return 0
        with self._lock:
            now = self._clock()
            window = max(0, int(now - self._last_flush))
            self._last_flush = now
            counters, models = self._counters, self._models
            self._counters, self._models = defaultdict(Counter), defaultdict(Counter)
        written = 0
        if recorder is None:
            return 0
        for capability, counted in counters.items():
            payload = {
                "router_version": self._version,
                "window_seconds": window,
                "counters": {
                    name: (round(value, 8) if isinstance(value, float) else value) for name, value in counted.items()
                },
                "models": dict(models.get(capability, {})),
            }
            try:
                recorder(ROLLUP_ACTION, actor=ROLLUP_ACTOR, entity_type="ai_capability", entity_id=capability,
                         payload=payload)
                written += 1
            except Exception:  # noqa: BLE001 - telemetry never changes a learner request
                continue
        return written
