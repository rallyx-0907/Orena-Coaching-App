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

Free tier (D-219, owner decision 2026-10-16). Every event is stamped when it is recorded with the provider and the
`cost.free_tier.<provider>` flag in force then (`free_tier: true|false`, writing_coach/cost_tier.py). The amount is
ALWAYS the public price, free or not, and the caps above sum it either way, so a free plan never turns a cap off: the
flag only decides whether an amount is reported as real spend or as free-tier value. Toggling the flag never rewrites a
stored event. An event written before this change has no `free_tier` field: it is reported as "unknown" tier, apart
from both real spend and free-tier value, and still counts toward every cap. The file keeps `schema_version` 1: an
added field is ignored by an older reader.
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

from writing_coach import cost_env, cost_tier, policies

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()

KIND_ASR = "asr"
KIND_AI = "ai"
KINDS = (KIND_ASR, KIND_AI)
# Supadata captions are paid in credits, not dollars (D-215): each request is one row of this kind (units=1, usd=0), counted
# against a daily request cap. It is not in KINDS: it has no dollar cap and takes no part in the batch and day USD sums.
KIND_SUPADATA = "supadata"
RECORDED_KINDS = (*KINDS, KIND_SUPADATA)
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


def _system_ceiling() -> None:
    """A paid media step (ASR, media AI) is refused once the system's daily AI spend ceiling is reached
    (ai/spend_gate.py, owner 2026-10-18), with the day limit's own code so the operator sees a known reason."""
    from writing_coach.ai import spend_gate

    if spend_gate.ceiling_reached():
        status = spend_gate.ceiling_status()
        raise SpendCapReached("spend_cap_day", limit=float(status.get("ceiling_usd") or 0.0),
                              spent=float(status.get("spent_usd") or 0.0), scope="system")


class SpendLedger:
    def __init__(self, path: Path, *, env: Mapping[str, str] | None = None) -> None:
        self._path = Path(path)
        self._env = env
        key = os.path.normcase(os.path.abspath(self._path))
        with _LOCKS_GUARD:
            self._lock = _LOCKS.setdefault(key, threading.Lock())

    # -- configuration, read each time so an operator change needs no restart -----

    # Each is the effective policy (writing_coach/policies.py, D-172): its environment variable when set, else the
    # administrator's value, else the default that used to be written here.
    def limits(self) -> dict[str, float]:
        return {
            KIND_ASR: float(policies.value("media.batch_cap_asr_usd", env=self._env)),
            KIND_AI: float(policies.value("media.batch_cap_ai_usd", env=self._env)),
            "day": float(policies.value("media.daily_cap_usd", env=self._env)),
        }

    def asr_usd_per_hour(self) -> float:
        # Groq whisper-large-v3-turbo list price; override for another model or provider.
        return float(policies.value("media.asr_usd_per_hour", env=self._env))

    def ai_usd_per_million_tokens(self) -> float:
        # Used only for a model the pricing catalogue does not know.
        return float(policies.value("media.ai_usd_per_million_tokens", env=self._env))

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
        _system_ceiling()
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

    def asr_spent_since(self, since: datetime) -> float:
        """Speech recognition spend since a moment: added to the system's daily AI total (ai/spend_gate.py). Media AI
        is not added here - it goes through the AI platform and its own ledger already."""
        with self._lock:
            events = self._read()
        return self._sum(events, kind=KIND_ASR, since=since.isoformat())

    def requests_today(self, kind: str = KIND_SUPADATA) -> int:
        day_start = _now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        with self._lock:
            events = self._read()
        return sum(1 for event in events if event.get("kind") == kind and str(event.get("at") or "") >= day_start)

    def reserve_request(self, cap: int, *, media_id: str = "", kind: str = KIND_SUPADATA, provider: str = "") -> None:
        """Check today's count against `cap` and record one request, under one lock: callers cannot both pass the check
        (D-215). Raises `SpendCapReached("caption_quota")` and records nothing at the cap."""
        day_start = _now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        with self._lock:
            events = self._read()
            used = sum(1 for event in events if event.get("kind") == kind and str(event.get("at") or "") >= day_start)
            if used >= cap:
                raise SpendCapReached("caption_quota", limit=float(cap), spent=float(used), scope="day")
            events.append({"at": _now().isoformat(), "kind": kind, "usd": 0.0, "batch_id": "captions",
                           "media_id": media_id, "units": 1.0, "provider": provider[:40],
                           "free_tier": cost_tier.is_free_tier(provider, self._env),
                           "environment": cost_env.label(self._env)})
            self._write(events)

    def check_requests(self, cap: int, kind: str = KIND_SUPADATA) -> None:
        """Raise `SpendCapReached("caption_quota")` when today's requests of `kind` have reached `cap` (no call is made)."""
        used = self.requests_today(kind)
        if used >= cap:
            raise SpendCapReached("caption_quota", limit=float(cap), spent=float(used), scope="day")

    def record(self, kind: str, usd: float, *, batch_id: str, media_id: str = "", units: float = 0.0, provider: str = "") -> None:
        if kind not in RECORDED_KINDS:
            raise ValueError("unknown spend kind")
        event = {
            "at": _now().isoformat(),
            "kind": kind,
            "usd": round(max(0.0, float(usd)), 8),
            "batch_id": batch_id,
            "media_id": media_id,
            "units": round(float(units), 3),
            "provider": provider[:40],
            "free_tier": cost_tier.is_free_tier(provider, self._env),
            "environment": cost_env.label(self._env),   # D-221: one provider key, many environments
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
        today_events = [event for event in events if str(event.get("at") or "") >= day_start.isoformat()]
        today_tiers = cost_tier.split(today_events)
        recent = [event for event in events if event.get("kind") in KINDS
                  and str(event.get("at") or "") >= (now - timedelta(days=1)).isoformat()]
        batches: dict[str, dict[str, float]] = {}
        for event in recent:
            row = batches.setdefault(str(event.get("batch_id") or ""), {KIND_ASR: 0.0, KIND_AI: 0.0})
            row[str(event.get("kind"))] = row.get(str(event.get("kind")), 0.0) + float(event.get("usd") or 0)
        return {
            "limits_usd": limits,
            "today_usd": round(today, 6),
            # The same total by tier (D-219): caps use `today_usd`; only `today_real_usd` is money actually spent.
            "today_real_usd": round(today_tiers[cost_tier.TIER_REAL], 6),
            "today_free_tier_usd": round(today_tiers[cost_tier.TIER_FREE], 6),
            "today_unknown_tier_usd": round(today_tiers[cost_tier.TIER_UNKNOWN], 6),
            "today_by_kind": {kind: round(self._sum(events, kind=kind, since=day_start.isoformat()), 6) for kind in KINDS},
            "batches_24h": len(batches),
            "largest_batch_usd": {
                kind: round(max((row.get(kind, 0.0) for row in batches.values()), default=0.0), 6) for kind in KINDS
            },
            "supadata_requests_today": self.requests_today(KIND_SUPADATA),
            "estimated": True,
        }

    def totals(self, days: int = 30, tier_at: Any = None) -> dict[str, Any]:
        """Spend over the last `days` UTC days split by tier, for the Admin cost page (D-219).

        `real_usd` sums only events stamped `free_tier: false`; `free_tier_usd` is the list-price value of the
        free-plan events; `unknown_tier_usd` is events with no stamp that the flag's history cannot place. With `tier_at`
        (`FlagTimeline.tier_at`, D-220 PROPOSED) an unstamped event is placed by its provider's flag at its time:
        a paid provider's past spend is real, a free plan's is free. `requests` counts the credit-priced Supadata rows,
        which have no dollar amount."""
        bounded = max(1, min(int(days), 365))
        today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
        since = (today - timedelta(days=bounded - 1)).isoformat()
        with self._lock:
            events = [event for event in self._read() if str(event.get("at") or "") >= since]
        providers: dict[str, dict[str, Any]] = {}
        for event in events:
            name = str(event.get("provider") or "") or "unknown"
            row = providers.setdefault(name, {"provider": name, "real_usd": 0.0, "free_tier_usd": 0.0,
                                              "unknown_tier_usd": 0.0, "events": 0, "requests": 0,
                                              "requests_by_tier": {"real": 0, "free": 0, "unknown": 0}})
            tier = cost_tier.tier_of(event, tier_at)
            key = {cost_tier.TIER_REAL: "real_usd", cost_tier.TIER_FREE: "free_tier_usd",
                   cost_tier.TIER_UNKNOWN: "unknown_tier_usd"}[tier]
            row[key] += float(event.get("usd") or 0)
            row["events"] += 1
            if event.get("kind") == KIND_SUPADATA:
                row["requests"] += int(event.get("units") or 0)
                row["requests_by_tier"][tier] += int(event.get("units") or 0)
        for row in providers.values():
            for key in ("real_usd", "free_tier_usd", "unknown_tier_usd"):
                row[key] = round(row[key], 6)
        tiers = cost_tier.split(events, tier_at=tier_at)
        # D-221: which environment wrote the events (None: written before the tag). Another environment's ledger is a
        # different file, so this is only ever this one's own spend.
        environments: dict[str | None, dict[str, Any]] = {}
        for event in events:
            name = str(event.get("environment") or "") or None
            row = environments.setdefault(name, {"environment": name, "events": 0, "usd": 0.0})
            row["events"] += 1
            row["usd"] += float(event.get("usd") or 0)
        return {
            "days": bounded, "since": since, "currency": "USD",
            "real_usd": round(tiers[cost_tier.TIER_REAL], 6),
            "free_tier_usd": round(tiers[cost_tier.TIER_FREE], 6),
            "unknown_tier_usd": round(tiers[cost_tier.TIER_UNKNOWN], 6),
            "by_provider": sorted(providers.values(), key=lambda r: (-(r["real_usd"] + r["free_tier_usd"]), r["provider"])),
            "by_environment": [dict(row, usd=round(row["usd"], 6)) for row in
                               sorted(environments.values(), key=lambda r: (-r["usd"], str(r["environment"])))],
            "estimated": True,
        }
