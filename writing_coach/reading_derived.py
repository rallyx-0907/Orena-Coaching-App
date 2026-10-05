"""One content-addressed cache for what Reading generates on demand: a sentence's meaning, an article's
summary and a word's meaning in its sentence (proposals/READING_ON_DEMAND.md).

Every such answer is generated once, when a learner asks, and then reused: by the same learner next time and by
every other learner who asks for the same text. The key is the normalized text, the learning language and the
support language - never a segment id, a route or a screen - so the Reader's paragraph and the Sentence Sheet
share one entry for one sentence.

Two layers. The in-process layer is a bounded LRU and always works. The persistent layer is the
`reading_derived_texts` table (proposed migration 20261005_0028, not yet authorized); it is used only for
*published* text, because the shared table must never hold what was derived from a learner's own imported text
(D-104: learner-owned records go with the account). Before the table exists, or on any database error,
persistence pauses for five minutes and then tries again; nothing a learner does ever fails because of it
(the writing_coach/ai/account_costs.py pattern).
"""

from __future__ import annotations

import hashlib
import logging
import threading
import unicodedata
from collections import OrderedDict
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

KIND_TRANSLATION = "translation"
KIND_SUMMARY = "summary"
KIND_GLOSS = "gloss"
KIND_EXPLANATION = "explanation"
KINDS = (KIND_TRANSLATION, KIND_SUMMARY, KIND_GLOSS, KIND_EXPLANATION)

DEFAULT_ENTRIES = 4096
RETRY_AFTER = timedelta(minutes=5)

_log = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """The text a cache key is made from: Unicode NFC, runs of whitespace collapsed, ends trimmed."""

    return " ".join(unicodedata.normalize("NFC", str(text or "")).split())


def content_key(*parts: str) -> str:
    """A stable sha256 of already-normalized parts (a unit separator keeps ('ab','c') apart from ('a','bc'))."""

    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


class DerivedStore(Protocol):
    """The persistent layer; `ReadingDerivedRepository` is the PostgreSQL one."""

    def get_many(self, kind: str, target_language: str, keys: Sequence[str]) -> dict[str, dict[str, Any]]: ...

    def put_many(
        self,
        kind: str,
        target_language: str,
        source_language: str,
        rows: Sequence[tuple[str, dict[str, Any]]],
        *,
        provider: str,
        model: str,
    ) -> None: ...


class DerivedCache:
    def __init__(
        self,
        store: DerivedStore | None = None,
        *,
        entries: int = DEFAULT_ENTRIES,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._entries = max(1, int(entries))
        self._now = now
        self._memory: OrderedDict[tuple[str, str, str], dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._paused_until: datetime | None = None

    def get_many(
        self, kind: str, target: str, keys: Iterable[str], *, persist: bool
    ) -> dict[str, dict[str, Any]]:
        found: dict[str, dict[str, Any]] = {}
        wanted: list[str] = []
        for key in dict.fromkeys(keys):
            value = self._remembered(kind, target, key)
            if value is None:
                wanted.append(key)
            else:
                found[key] = value
        if wanted and persist and self._store_ready():
            try:
                stored = self._store.get_many(kind, target, wanted)  # type: ignore[union-attr]
            except Exception as error:  # noqa: BLE001 - the table may not exist yet
                self._pause(error)
                stored = {}
            for key, value in stored.items():
                found[key] = value
                self._remember(kind, target, key, value)
        return found

    def get(self, kind: str, target: str, key: str, *, persist: bool) -> dict[str, Any] | None:
        return self.get_many(kind, target, [key], persist=persist).get(key)

    def put_many(
        self,
        kind: str,
        target: str,
        source: str,
        rows: Sequence[tuple[str, dict[str, Any]]],
        *,
        persist: bool,
        provider: str = "",
        model: str = "",
    ) -> None:
        for key, value in rows:
            self._remember(kind, target, key, value)
        if rows and persist and self._store_ready():
            try:
                self._store.put_many(  # type: ignore[union-attr]
                    kind, target, source, rows, provider=provider[:40], model=model[:160]
                )
            except Exception as error:  # noqa: BLE001 - a learner never pays for the cache
                self._pause(error)

    def _store_ready(self) -> bool:
        if self._store is None:
            return False
        return self._paused_until is None or self._now() >= self._paused_until

    def _pause(self, error: Exception) -> None:
        _log.warning("reading cache not persisted (%s); retrying in %s", type(error).__name__, RETRY_AFTER)
        self._paused_until = self._now() + RETRY_AFTER

    def _remembered(self, kind: str, target: str, key: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._memory.get((kind, target, key))
            if value is not None:
                self._memory.move_to_end((kind, target, key))
            return value

    def _remember(self, kind: str, target: str, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._memory[(kind, target, key)] = value
            self._memory.move_to_end((kind, target, key))
            while len(self._memory) > self._entries:
                self._memory.popitem(last=False)
