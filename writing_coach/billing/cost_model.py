"""From provider cost to meter price: operation-level evidence and the per-pack gate (PR-MON-6 §8, P1-4).

No VND, FX, margin or credit value is invented here (H-1, H-7). The system supplies:
- **evidence**: provider cost aggregated per learner operation `(operation_id, meter)` first, then per settled unit;
  p50/p95/max over operations that reached a paid provider and are complete; the zero-cost share reported apart; an
  unpriced, unknown or partial billable call makes its operation incomplete - never USD 0;
- **the gate**: for each configured pack `p` and each meter `m` its credits may fund,
  `credit_price[m] * p.amount_minor / p.credit_units >= p95_paid[m] * fx_usd_vnd * (1 + margin_floor)`, with at least
  `min_operations` complete paid operations and quality at least `min_quality`. Its inputs are the human's (a file);
  absent inputs pass nothing. The gate only removes: a meter from credits, a pack from sale (K1, K5).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import text

COMPLETE_STATES = ("estimated",)


@dataclass(frozen=True)
class GateInputs:
    """H-7, the human's: a configured FX reference (with its source and date, never fetched live), the margin floor,
    and the minimum evidence. No defaults exist for any of them."""

    fx_usd_vnd: Decimal
    fx_source: str
    fx_date: str
    margin_floor: Decimal
    min_operations: int
    min_quality: Decimal


def load_gate_inputs(env: Mapping[str, str]) -> GateInputs | None:
    """`BILLING_COST_GATE_FILE`, or None: no inputs, nothing passes (H-7 OFF)."""
    path = str(env.get("BILLING_COST_GATE_FILE", "")).strip()
    if not path:
        return None
    item = json.loads(Path(path).read_text(encoding="utf-8"))
    inputs = GateInputs(fx_usd_vnd=Decimal(str(item["fx_usd_vnd"])), fx_source=str(item["fx_source"]),
                        fx_date=str(item["fx_date"]), margin_floor=Decimal(str(item["margin_floor"])),
                        min_operations=int(item["min_operations"]), min_quality=Decimal(str(item["min_quality"])))
    if inputs.fx_usd_vnd <= 0 or inputs.margin_floor < 0 or inputs.min_operations < 1 \
            or not Decimal(0) < inputs.min_quality <= 1 or not inputs.fx_source or not inputs.fx_date:
        raise ValueError("the cost gate needs a positive FX with its source and date, a margin floor >= 0, "
                         "min_operations >= 1 and 0 < min_quality <= 1")
    return inputs


@dataclass
class MeterStats:
    meter: str
    settled: int = 0
    complete: int = 0
    incomplete: int = 0
    complete_paid: int = 0
    zero_cost: int = 0
    p50_paid: Decimal | None = None
    p95_paid: Decimal | None = None
    max_paid: Decimal | None = None
    p95_all: Decimal | None = None

    @property
    def quality(self) -> Decimal:
        return Decimal(self.complete) / Decimal(self.settled) if self.settled else Decimal(0)

    @property
    def zero_cost_share(self) -> Decimal:
        return Decimal(self.zero_cost) / Decimal(self.complete) if self.complete else Decimal(0)

    def as_dict(self) -> dict[str, Any]:
        def num(value: Decimal | None) -> str | None:
            return None if value is None else str(value)

        return {"meter": self.meter, "settled": self.settled, "complete": self.complete,
                "incomplete": self.incomplete, "complete_paid": self.complete_paid, "zero_cost": self.zero_cost,
                "zero_cost_share": num(self.zero_cost_share), "quality": num(self.quality),
                "usd_per_unit": {"p50_paid": num(self.p50_paid), "p95_paid": num(self.p95_paid),
                                 "max_paid": num(self.max_paid), "p95_all_complete": num(self.p95_all)}}


def _percentile(values: list[Decimal], q: float) -> Decimal | None:
    """Nearest-rank percentile: the smallest value with at least q of the sample at or below it."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]


@dataclass(frozen=True)
class OperationCost:
    """One settled learner operation and its attributed calls."""

    operation_id: str
    meter: str
    settled_units: int
    calls: tuple[tuple[str, str, Decimal | None], ...]   # (cost_state, tier, cost_usd)


def meter_stats(operations: Iterable[OperationCost]) -> dict[str, MeterStats]:
    """Aggregate per operation first, then per unit (§8). Pure."""
    stats: dict[str, MeterStats] = {}
    paid: dict[str, list[Decimal]] = {}
    complete_all: dict[str, list[Decimal]] = {}
    for op in operations:
        entry = stats.setdefault(op.meter, MeterStats(op.meter))
        if op.settled_units <= 0:
            continue
        entry.settled += 1
        # no attributed call at all is missing evidence, not a free operation
        complete = bool(op.calls) and all(state in COMPLETE_STATES and cost is not None
                                          for state, _tier, cost in op.calls)
        if not complete:
            entry.incomplete += 1
            continue
        entry.complete += 1
        total = sum((cost for _state, _tier, cost in op.calls), Decimal(0))
        per_unit = total / Decimal(op.settled_units)
        complete_all.setdefault(op.meter, []).append(per_unit)
        if any(tier == "paid" for _state, tier, _cost in op.calls):
            entry.complete_paid += 1
            paid.setdefault(op.meter, []).append(per_unit)
        elif total == 0:
            entry.zero_cost += 1
    for meter, entry in stats.items():
        values = paid.get(meter, [])
        entry.p50_paid, entry.p95_paid = _percentile(values, 0.5), _percentile(values, 0.95)
        entry.max_paid = max(values) if values else None
        entry.p95_all = _percentile(complete_all.get(meter, []), 0.95)
    return stats


@dataclass
class GateResult:
    gate_id: str
    meters: dict[str, bool] = field(default_factory=dict)      # meter -> credit-eligible under at least one pack
    packs: dict[str, bool] = field(default_factory=dict)       # pack key -> passes for every eligible meter
    reasons: dict[str, str] = field(default_factory=dict)

    def meter_ok(self, meter: str) -> bool:
        return bool(self.meters.get(meter))

    def pack_ok(self, key: str) -> bool:
        return bool(self.packs.get(key))


def evaluate_gate(*, packs: Mapping[str, Any], prices: Mapping[str, int], stats: Mapping[str, MeterStats],
                  inputs: GateInputs | None) -> GateResult:
    """The per-pack gate (§8). Pure and deterministic; its id is a digest of every input, so an admission can
    snapshot exactly the result it was judged under."""
    material = json.dumps({
        "packs": {k: [p.amount_minor, p.credit_units] for k, p in sorted(packs.items())},
        "prices": dict(sorted(prices.items())),
        "stats": {m: s.as_dict() for m, s in sorted(stats.items())},
        "inputs": None if inputs is None else [str(inputs.fx_usd_vnd), inputs.fx_source, inputs.fx_date,
                                                str(inputs.margin_floor), inputs.min_operations,
                                                str(inputs.min_quality)],
    }, sort_keys=True, default=str)
    result = GateResult(gate_id="cg1:" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24])
    if inputs is None:
        result.reasons["*"] = "no_gate_inputs"
        result.meters = {m: False for m in prices}
        result.packs = {k: False for k in packs}
        return result
    passes: dict[tuple[str, str], bool] = {}
    for meter, price in prices.items():
        entry = stats.get(meter)
        if entry is None or entry.p95_paid is None or entry.complete_paid < inputs.min_operations \
                or entry.quality < inputs.min_quality:
            result.reasons[meter] = "insufficient_evidence"
            for key in packs:
                passes[(key, meter)] = False
            continue
        floor = entry.p95_paid * inputs.fx_usd_vnd * (Decimal(1) + inputs.margin_floor)
        for key, pack in packs.items():
            effective = Decimal(pack.amount_minor) / Decimal(pack.credit_units)
            passes[(key, meter)] = Decimal(price) * effective >= floor
    for meter in prices:
        result.meters[meter] = any(passes.get((key, meter), False) for key in packs)
    eligible = [m for m, ok in result.meters.items() if ok]
    for key in packs:
        result.packs[key] = bool(eligible) and all(passes[(key, m)] for m in eligible)
    return result


# ---- the evidence, read from PostgreSQL -------------------------------------------------------------------------

def read_operations(engine: Any, *, since: datetime, tier_of: Any) -> tuple[list[OperationCost], int]:
    """Settled admissions since `since` with their attributed calls, and the count of unattributed priced calls in
    the same period (counted and reported, never folded into a meter)."""
    with engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT f.operation_id, f.meter, COALESCE(f.settled_units, 0) AS settled_units, c.cost_state, "
            "c.provider, c.model, c.cost_usd FROM funding_admissions f "
            "LEFT JOIN ai_cost_records c ON c.operation_id = f.operation_id AND c.meter = f.meter "
            "WHERE f.state = 'settled' AND f.closed_at >= :since ORDER BY f.operation_id"),
            {"since": since}).mappings().all()  # fmt: skip
        unattributed = int(connection.execute(text(
            "SELECT count(*) FROM ai_cost_records WHERE operation_id IS NULL AND occurred_at >= :since"),
            {"since": since}).scalar() or 0)  # fmt: skip
    grouped: dict[tuple[str, str], tuple[int, list[tuple[str, str, Decimal | None]]]] = {}
    for row in rows:
        key = (row["operation_id"], row["meter"])
        units, calls = grouped.setdefault(key, (int(row["settled_units"]), []))
        if row["cost_state"] is not None:
            cost = None if row["cost_usd"] is None else Decimal(str(row["cost_usd"]))
            calls.append((row["cost_state"], tier_of(row["provider"], row["model"]), cost))
    operations = [OperationCost(op, meter, units, tuple(calls)) for (op, meter), (units, calls) in grouped.items()]
    return operations, unattributed
