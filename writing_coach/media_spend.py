"""Spending caps for automatic media processing (D-111 item 6).

Speech recognition and AI enrichment are paid, and a pipeline that runs without
a person watching it must not be able to spend without a limit. This ledger is
the one place that decides whether a paid step may start, and the one place that
remembers what was spent. Three limits, all configurable and all enforced before
a call is made rather than reported after it:

* speech recognition: at most `MEDIA_ASR_BATCH_CAP_USD` (default 5) per batch;
* AI enrichment (translation): at most `MEDIA_AI_BATCH_CAP_USD` (default 10) per batch;
* everything automatic: at most `MEDIA_DAILY_CAP_USD` (default 25) per UTC day.

A batch is one operator import request, or one learner import. A refusal is a
`SpendCapReached` with a stable code, which the pipeline turns into a visible
reason on the item - nothing is skipped silently and nothing is retried
automatically past a cap. The ledger is a small durable JSON file beside the
media index, so a restart does not reset the day.

Costs are estimates from what the provider exposes: speech providers report the
audio duration they billed, token providers report token usage, and each is
priced from a configurable rate. A provider that reports nothing is charged at
the conservative estimate made before the call.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
import threading
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()

KIND_ASR = "asr"
KIND_AI = "ai"
KINDS = (KIND_ASR, KIND_AI)
MAX_EVENTS = 20_000


class SpendCapReached(Exception):
    """A paid step would pass a configured limit. `code` is stable and shown to the operator."""

    def __init__(self, code: str, *, limit: float, spent: float, scope: str) -> None:
        super().__init__(code)
        self.code = code
        self.limit = limit
        self.spent = spent
        self.scope = scope


def _env_float(name: str, default: float, env: Mapping[str, str] | None = None) -> float:
    values = os.environ if env is None else env
    raw = str(values.get(name, "") or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if math.isfinite(value) and value >= 0 else default


def _now() -> datetime:
    return datetime.now(UTC)


class SpendLedger:
    def __init__(self, path: Path, *, env: Mapping[str, str] | None = None) -> None:
        self._path = Path(path)
        self._env = env
        key = os.path.normcase(os.path.abspath(self._path))
        with _LOCKS_GUARD:
            self._lock = _LOCKS.setdefault(key, threading.Lock())

    # -- configuration, read each time so an operator change needs no restart -----

    def limits(self) -> dict[str, float]:
        return {
            KIND_ASR: _env_float("MEDIA_ASR_BATCH_CAP_USD", 5.0, self._env),
            KIND_AI: _env_float("MEDIA_AI_BATCH_CAP_USD", 10.0, self._env),
            "day": _env_float("MEDIA_DAILY_CAP_USD", 25.0, self._env),
        }

    def asr_usd_per_hour(self) -> float:
        # Groq whisper-large-v3-turbo list price; override for another model or provider.
        return _env_float("MEDIA_ASR_USD_PER_HOUR", 0.04, self._env)

    def ai_usd_per_million_tokens(self) -> float:
        # Used only for a model the pricing catalogue does not know.
        return _env_float("MEDIA_AI_USD_PER_MILLION_TOKENS", 1.0, self._env)

    def asr_estimate(self, audio_seconds: float) -> float:
        billed = max(10.0, float(audio_seconds or 0))
        return round(billed / 3600.0 * self.asr_usd_per_hour(), 6)

    # -- storage ----------------------------------------------------------------------

    def _read(self) -> list[dict[str, Any]]:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            return []
        events = payload.get("events") if isinstance(payload, dict) else None
        return [event for event in events if isinstance(event, dict)] if isinstance(events, list) else []

    def _write(self, events: list[dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps({"schema_version": 1, "events": events[-MAX_EVENTS:]}, ensure_ascii=False)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self._path.parent, delete=False) as handle:
            handle.write(body)
            temporary = Path(handle.name)
        temporary.replace(self._path)

    # -- the decision ---------------------------------------------------------------

    @staticmethod
    def _sum(events: list[dict[str, Any]], *, kind: str | None = None, batch: str | None = None, since: str | None = None) -> float:
        total = 0.0
        for event in events:
            if kind is not None and event.get("kind") != kind:
                continue
            if batch is not None and event.get("batch_id") != batch:
                continue
            if since is not None and str(event.get("at") or "") < since:
                continue
            total += float(event.get("usd") or 0)
        return total

    def check(self, kind: str, batch_id: str, estimate_usd: float) -> None:
        """Raise `SpendCapReached` when this step would pass a limit; otherwise return."""
        if kind not in KINDS:
            raise ValueError("unknown spend kind")
        limits = self.limits()
        with self._lock:
            events = self._read()
        batch_spent = self._sum(events, kind=kind, batch=batch_id)
        if batch_spent + estimate_usd > limits[kind] + 1e-12:
            raise SpendCapReached(f"spend_cap_batch_{kind}", limit=limits[kind], spent=batch_spent, scope="batch")
        day_start = _now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        day_spent = self._sum(events, since=day_start)
        if day_spent + estimate_usd > limits["day"] + 1e-12:
            raise SpendCapReached("spend_cap_day", limit=limits["day"], spent=day_spent, scope="day")

    def record(self, kind: str, usd: float, *, batch_id: str, media_id: str = "", units: float = 0.0, provider: str = "") -> None:
        if kind not in KINDS:
            raise ValueError("unknown spend kind")
        event = {
            "at": _now().isoformat(),
            "kind": kind,
            "usd": round(max(0.0, float(usd)), 8),
            "batch_id": batch_id,
            "media_id": media_id,
            "units": round(float(units), 3),
            "provider": provider[:40],
        }
        with self._lock:
            events = self._read()
            events.append(event)
            self._write(events)

    def summary(self) -> dict[str, Any]:
        """What an operator needs to see: the limits, today's spend and the oldest-first recent batches."""
        limits = self.limits()
        with self._lock:
            events = self._read()
        now = _now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today = self._sum(events, since=day_start.isoformat())
        recent = [event for event in events if str(event.get("at") or "") >= (now - timedelta(days=1)).isoformat()]
        batches: dict[str, dict[str, float]] = {}
        for event in recent:
            row = batches.setdefault(str(event.get("batch_id") or ""), {KIND_ASR: 0.0, KIND_AI: 0.0})
            row[str(event.get("kind"))] = row.get(str(event.get("kind")), 0.0) + float(event.get("usd") or 0)
        return {
            "limits_usd": limits,
            "today_usd": round(today, 6),
            "today_by_kind": {kind: round(self._sum(events, kind=kind, since=day_start.isoformat()), 6) for kind in KINDS},
            "batches_24h": len(batches),
            "largest_batch_usd": {
                kind: round(max((row.get(kind, 0.0) for row in batches.values()), default=0.0), 6) for kind in KINDS
            },
            "estimated": True,
        }
