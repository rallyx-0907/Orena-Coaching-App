"""Cost-aware funding of metered work (PR-MON-6; docs/billing/PR-MON-6_DESIGN.md revision 2, approved 2026-10-15).

    feature access (403) -> bypass (deterministic / stored / cache, free) -> promotional allowance (earliest expiry)
    -> plan allowance -> prepaid credits -> refuse (429 quota_exhausted with reason and options)

One source per operation, chosen once, inside the admission's own transaction (`PostgresFundingRepository.admit`).
A credit is a unit of metered work: a credits-funded operation settles `snapshot.price x units` whichever rung served
it (H-3). The meter's credit price (H-1), the cost-gate inputs (H-7) and promotional grants (H-8) are the human's,
in files; with none configured - the default - no meter is credit-eligible, no pack passes the gate and no grant
exists. `media.import` is allowance-only (H-5).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from writing_coach.billing.cost_model import GateInputs, GateResult, evaluate_gate, meter_stats, read_operations
from writing_coach.persistence.funding_repository import (
    AdmissionOutcome,
    FundingIntent,
    PostgresFundingRepository,
    Refusal,
    Snapshot,
    fund_key,
)

_log = logging.getLogger("orena.funding")

# v1 (design §6): only these meters may ever be funded by credits; media.import never (H-5), languages.target never.
CREDIT_ELIGIBLE_V1 = ("writing.review", "orena.message", "pronunciation.audio")
ALLOWANCE_ONLY = ("media.import",)
MAX_HOLD_TTL_SECONDS = 30 * 60
# H-2 (closed): the units of the meters that close R-MON-005. Not enforced before their granularity and limits exist.
NEW_METER_UNITS = {"speech.transcribe": "second", "reading.assist": "request", "word.assist": "request",
                   "writing.task": "request", "speech.evaluate": "second", "audio.tts": "character"}
GATE_WINDOW = timedelta(days=90)
SWITCH = "ORENA_FUNDING_ADMISSIONS"
FUNDING_TABLES = ("funding_admissions", "promotional_grants")
GATE_CACHE_SECONDS = 600


def funding_admissions_enabled(env: Mapping[str, str]) -> bool:
    """Off by default. On, an enforced meter is admitted through `funding_admissions` (PR-MON-6 rollout step 2)."""
    return str(env.get(SWITCH, "")).strip().lower() in {"on", "1", "true", "yes"}


@dataclass(frozen=True)
class MeterPrice:
    """H-1: a meter's credit price per unit and its hold TTL, approved by the human (`revision` names the approval)."""

    meter: str
    credit_price: int
    hold_ttl_seconds: int
    revision: str


def load_meter_prices(env: Mapping[str, str]) -> dict[str, MeterPrice]:
    """`BILLING_METER_PRICES_FILE`, or nothing: no price, no credits for any meter (H-1 OFF)."""
    path = str(env.get("BILLING_METER_PRICES_FILE", "")).strip()
    if not path:
        return {}
    prices: dict[str, MeterPrice] = {}
    for item in json.loads(Path(path).read_text(encoding="utf-8")):
        meter, price, ttl = str(item["meter"]), item["credit_price"], item["hold_ttl_seconds"]
        if meter not in CREDIT_ELIGIBLE_V1:
            raise ValueError(f"{meter} cannot be funded by credits in v1 ({', '.join(CREDIT_ELIGIBLE_V1)})")
        if type(price) is not int or price <= 0 or type(ttl) is not int or not 0 < ttl <= MAX_HOLD_TTL_SECONDS:
            raise ValueError("a meter price is a positive integer, its hold TTL 1..1800 seconds")
        if meter in prices:
            raise ValueError(f"{meter} is priced twice")
        prices[meter] = MeterPrice(meter, price, ttl, str(item["revision"])[:40])
    return prices


@dataclass(frozen=True)
class PlanAllowance:
    """The plan bucket the quota gate computed for this request (its window, policy label and current limit)."""

    window: Any            # quota_repository.BucketWindow
    limit_policy: str = "current"


@dataclass(frozen=True)
class CreditTerms:
    price: int
    hold_ttl_seconds: int
    revision: str
    gate_id: str


class FundingService:
    def __init__(self, repository: PostgresFundingRepository, *, prices: Mapping[str, MeterPrice] | None = None,
                 gate_inputs: GateInputs | None = None, credits_ready: Callable[[], bool] = lambda: False,
                 packs: Callable[[], Mapping[str, Any]] = dict, tier_of: Callable[[str, str], str] | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        self._repository = repository
        self._prices = dict(prices or {})
        self._gate_inputs = gate_inputs
        self._credits_ready = credits_ready
        self._packs = packs
        self._tier_of = tier_of or (lambda provider, model: "paid")
        self._clock = clock or (lambda: datetime.now(UTC))
        self._gate: tuple[float, GateResult] | None = None
        self._gate_lock = threading.Lock()

    @property
    def repository(self) -> PostgresFundingRepository:
        return self._repository

    @property
    def tier_of(self) -> Callable[[str, str], str]:
        return self._tier_of

    @property
    def gate_inputs_configured(self) -> bool:
        return self._gate_inputs is not None

    # ---- H-1 / H-7: may this meter be funded by credits? ------------------------------------------------------------

    def gate(self, *, refresh: bool = False) -> GateResult:
        """The cost gate, recomputed at most every 10 minutes. With no inputs (H-7 OFF) nothing is read and nothing
        passes."""
        with self._gate_lock:
            if not refresh and self._gate is not None and time.monotonic() - self._gate[0] < GATE_CACHE_SECONDS:
                return self._gate[1]
            prices = {m: p.credit_price for m, p in self._prices.items()}
            stats = {}
            if self._gate_inputs is not None and prices:
                operations, _unattributed = read_operations(self._repository.engine,
                                                            since=self._clock() - GATE_WINDOW, tier_of=self._tier_of)
                stats = meter_stats(operations)
            result = evaluate_gate(packs=dict(self._packs()), prices=prices, stats=stats, inputs=self._gate_inputs)
            self._gate = (time.monotonic(), result)
            return result

    def credit_terms(self, meter: str) -> tuple[CreditTerms | None, str]:
        """(terms, "") when `meter` is credit-eligible now; otherwise (None, why). Eligible = v1 meter, an approved
        price (H-1), and at least one sellable pack under which it passes the gate (H-7)."""
        if meter in ALLOWANCE_ONLY or meter not in CREDIT_ELIGIBLE_V1:
            return None, "not_credit_eligible"
        price = self._prices.get(meter)
        if price is None:
            return None, "not_credit_eligible"
        result = self.gate()
        if not result.meter_ok(meter):
            return None, "not_credit_eligible"
        return CreditTerms(price.credit_price, price.hold_ttl_seconds, price.revision, result.gate_id), ""

    def offers_available(self, meter: str) -> bool:
        """Section 9 `buy_credits`: the meter is credit-eligible and at least one pack passes the gate."""
        terms, _why = self.credit_terms(meter)
        return terms is not None and self._credits_ready() and any(self.pack_sellable(k) for k in self._packs())

    def pack_sellable(self, key: str) -> bool:
        """The gate only removes a pack from sale (K1, K5): no inputs, no evidence or a failing meter, no sale."""
        return self.gate().pack_ok(key)

    # ---- admission ------------------------------------------------------------------------------------------------

    def admit(self, intent: FundingIntent, *, plan: PlanAllowance | None, policy_label: str = "") -> AdmissionOutcome:
        """Promotional -> plan -> credits -> refuse, in the admission's transaction. `plan` None: the plan does not
        include the meter's allowance here (the caller already refused a disabled meter with 403)."""
        quota, credits = self._repository.quota, self._repository.credits
        key = fund_key(intent.operation_id)

        def choose(connection: Any, row: dict[str, Any]) -> Snapshot | Refusal:
            facts: dict[str, Any] = {}
            # 1. promotional grants of this account and meter, earliest expiry first (H-8: none configured)
            for bucket in self._promotional_buckets(connection, intent):
                outcome = quota.reserve(incarnation_id=intent.incarnation_id, meter=intent.meter, window=bucket,
                                        operation_id=key, requested_units=intent.units, limit_policy="frozen",
                                        connection=connection)  # fmt: skip
                snapshot = self._allowance(outcome, "promotional", bucket.policy_version)
                if snapshot is not None:
                    return snapshot
                facts.setdefault("promotional", []).append(
                    {"grant": bucket.window_id.removeprefix("promo:"), "remaining": 0,
                     "expires_at": bucket.window_end.isoformat()})  # fmt: skip
            # 2. the plan's window bucket
            if plan is not None:
                outcome = quota.reserve(incarnation_id=intent.incarnation_id, meter=intent.meter, window=plan.window,
                                        operation_id=key, requested_units=intent.units,
                                        limit_policy=plan.limit_policy, connection=connection)  # fmt: skip
                snapshot = self._allowance(outcome, "allowance", policy_label or plan.window.policy_version)
                if snapshot is not None:
                    return snapshot
                facts["allowance"] = {"status": outcome.get("status"), "limit": outcome.get("limit"),
                                      "consumed": outcome.get("consumed"), "reserved": outcome.get("reserved")}
            # 3. prepaid credits
            terms, why = self.credit_terms(intent.meter)
            if terms is None:
                if intent.meter in ALLOWANCE_ONLY:
                    return Refusal("allowance_exhausted", facts)
                return Refusal("not_credit_eligible" if self._credits_ready() else "credits_unavailable", facts)
            if not self._credits_ready() or credits is None:
                return Refusal("credits_unavailable", facts)
            amount = terms.price * intent.units
            outcome = credits.reserve(intent.incarnation_id, amount=amount, operation_id=key, meter=intent.meter,
                                      operation_ref=intent.operation_ref,
                                      ttl=timedelta(seconds=terms.hold_ttl_seconds), connection=connection)  # fmt: skip
            if outcome.ok:
                return Snapshot(source="credits", policy_version=f"{policy_label}|prices:{terms.revision}",
                                credit_reserve_entry_id=str(outcome.entry["id"]), price_per_unit=terms.price,
                                amount_reserved=amount, hold_ttl_seconds=terms.hold_ttl_seconds,
                                cost_gate_id=terms.gate_id)  # fmt: skip
            if outcome.status == "insufficient_credits":
                facts["credits"] = {"available": outcome.extra.get("available", 0), "needed": amount,
                                    "price_per_unit": terms.price}
                return Refusal("insufficient_credits", facts)
            if outcome.status == "not_found":
                facts["credits"] = {"available": 0, "needed": amount, "price_per_unit": terms.price}
                return Refusal("insufficient_credits", facts)
            return Refusal("credits_unavailable", {**facts, "credit_status": outcome.status})

        return self._repository.admit(intent, choose)

    @staticmethod
    def _allowance(outcome: Any, source: str, policy_version: str) -> Snapshot | None:
        status = outcome.get("status")
        if status in ("admit", "duplicate") and outcome.get("reservation_id"):
            # `duplicate`: an exact reservation keyed fund:<op> already exists - adopted (§5.6); the 0034 guard
            # re-checks that it is exact before the row may become funded.
            return Snapshot(source=source, policy_version=policy_version,
                            quota_reservation_id=str(outcome["reservation_id"]))
        if status == "denied":
            raise AccountDeleted()
        if status in ("window_closed", "window_superseded"):
            raise WindowMoved(status)
        return None

    @staticmethod
    def _promotional_buckets(connection: Any, intent: FundingIntent) -> list[Any]:
        from sqlalchemy import text

        from writing_coach.persistence.quota_repository import BucketWindow

        rows = connection.execute(text(
            "SELECT window_id, window_start, window_end, policy_version, unit_limit FROM commerce_quota_buckets "
            "WHERE incarnation_id = :inc AND meter = :meter AND promotional_grant_id IS NOT NULL "
            "AND window_start <= now() AND now() < window_end AND consumed + reserved < unit_limit "
            "ORDER BY window_end, window_id"),
            {"inc": intent.incarnation_id, "meter": intent.meter}).mappings().all()  # fmt: skip
        return [BucketWindow(r["window_id"], r["window_start"], r["window_end"], r["policy_version"],
                             r["unit_limit"]) for r in rows]

    # ---- lifecycle ------------------------------------------------------------------------------------------------

    def dispatch(self, operation_id: str, ref: str = "dispatch") -> str:
        return self._repository.dispatch(operation_id, ref=ref)

    def settle(self, operation_id: str, actual_units: int, outcome_ref: str | None = None) -> str:
        return self._repository.settle(operation_id, actual_units=actual_units, outcome_ref=outcome_ref)

    def release(self, operation_id: str, reason: str = "") -> str:
        return self._repository.release(operation_id, reason=reason)

    def live(self, operation_id: str, *, request_digest: str, meter: str, min_hold_seconds: float) -> str | None:
        return self._repository.live(operation_id, request_digest=request_digest, meter=meter,
                                     min_hold_seconds=min_hold_seconds)

    def dispatch_for_backstop(self, operation_id: str) -> str:
        status = self._repository.dispatch(operation_id, ref="paid_request")
        if status != "dispatched":
            raise RuntimeError(status)
        return status

    # ---- reconciliation (§5.6 crash table) ---------------------------------------------------------------------------

    def reconcile(self, *, now: datetime | None = None, limit: int = 200,
                  admitting_after: timedelta = timedelta(minutes=MAX_HOLD_TTL_SECONDS // 60)) -> dict[str, int]:
        """Complete what a crash left: a funded/dispatched row whose backing closed is completed from it; an old
        `admitting` row is adopted when an exact backing exists, refused otherwise (with a conflict item when a
        non-exact `fund:<op>` reservation is open); open conflict items close once nothing keyed `fund:<op>` is
        open. Never re-settles, never charges."""
        now = now or self._clock()
        counts: dict[str, int] = {}

        def bump(name: str) -> None:
            counts[name] = counts.get(name, 0) + 1

        for row in self._repository.open_rows(states=("funded", "dispatched"), older_than=now - timedelta(minutes=1),
                                              limit=limit):  # fmt: skip
            outcome = self._repository.complete_from_backing(row["operation_id"])
            if outcome in ("settled", "released", "inconsistent"):
                bump(f"completed_{outcome}")
        for row in self._repository.open_rows(states=("admitting",), older_than=now - admitting_after, limit=limit):
            exact = self._repository.exact_backing(row)
            if exact is not None:
                bump("admitting_with_exact_backing")   # adopted by the next retry of the operation, never orphaned
                continue
            stray = self._repository.stray_open(row["operation_id"])
            if self._repository.refuse(row["operation_id"], reason="non_exact_backing" if stray else "unbacked") \
                    == "refused":
                bump("refused")
                if stray:
                    self._repository.open_conflict(row, reason="a non-exact reservation keyed fund:<op> is open")
                    bump("conflict_opened")
        for item in self._repository.open_conflicts(limit=limit):
            if not self._repository.stray_open(item["operation_id"]):
                self._repository.resolve_conflict(item["id"])
                bump("conflict_resolved")
        return counts


class AccountDeleted(RuntimeError):
    """The incarnation was deleted: never admitted (C1 mirrored)."""


class WindowMoved(RuntimeError):
    """The plan window ended or another window opened between the read and the lock: read again."""
