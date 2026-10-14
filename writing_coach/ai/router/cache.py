"""The router's L1 result cache: a bounded in-process LRU with single-flight and a short negative cache.

The key is made of the capability, contract version, prompt version and normalised input - never the model, so an
operator changing the model does not pay again for a request already answered (owner instruction, D-195). The
value is the contract's output plus its provenance.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable
from time import monotonic
from typing import Any

DEFAULT_MAX_ENTRIES = 4096
NEGATIVE_SECONDS = 60.0


class Flight:
    """One in-progress request that later identical requests join instead of repeating."""

    def __init__(self) -> None:
        self.done = threading.Event()
        self.result: Any = None
        self.error: BaseException | None = None

    def set_result(self, result: Any) -> None:
        self.result = result
        self.done.set()

    def set_error(self, error: BaseException) -> None:
        self.error = error
        self.done.set()


class ResultCache:
    def __init__(self, clock: Callable[[], float] = monotonic, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        self._clock = clock
        self._max = max_entries
        self._lock = threading.Lock()
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._negative: dict[str, float] = {}
        self._flights: dict[str, Flight] = {}

    def get(self, key: str) -> Any | None:
        with self._lock:
            held = self._entries.get(key)
            if held is None:
                return None
            if held[0] <= self._clock():
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return held[1]

    def put(self, key: str, value: Any, ttl_seconds: float) -> None:
        with self._lock:
            self._entries[key] = (self._clock() + ttl_seconds, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max:
                self._entries.popitem(last=False)
            self._negative.pop(key, None)

    def is_unavailable(self, key: str) -> bool:
        with self._lock:
            until = self._negative.get(key)
            if until is None:
                return False
            if until <= self._clock():
                del self._negative[key]
                return False
            return True

    def mark_unavailable(self, key: str, seconds: float = NEGATIVE_SECONDS) -> None:
        with self._lock:
            if len(self._negative) >= self._max:
                self._negative.clear()
            self._negative[key] = self._clock() + seconds

    def join(self, key: str) -> tuple[Flight, bool]:
        """The flight for `key` and whether the caller leads it (and must `leave` it when done)."""

        with self._lock:
            flight = self._flights.get(key)
            if flight is not None:
                return flight, False
            flight = self._flights[key] = Flight()
            return flight, True

    def leave(self, key: str, flight: Flight) -> None:
        with self._lock:
            if self._flights.get(key) is flight:
                del self._flights[key]
        if not flight.done.is_set():  # the leader ended without an outcome: never leave followers waiting
            flight.set_error(RuntimeError("The request ended without an answer."))

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._negative.clear()
            self._flights.clear()
