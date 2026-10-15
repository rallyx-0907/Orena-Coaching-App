"""Candidate-model benchmark for a routed capability (PR-MON-7A-first, design revision 2.1 §7, human decision H7-2).

Before a capability is listed in `ORENA_CAPABILITY_ROUTING`, its proposed primary (an Ollama Cloud model) is compared
with the current paid baseline on the same cases. The harness measures; it never decides. The acceptance threshold is a
human activation decision, so nothing here is a CI gate and no number below is a threshold.

Per model it reports the five measurements the design names:
- **schema-valid rate**: the share of cases whose output passes the capability's own validator;
- **quality**: the mean task-quality score in [0, 1] from the capability's grader (e.g. the Writing benchmark's
  `evaluate_benchmark_result`), over valid outputs;
- **critical failure rate**: the share of cases the grader marks critical (a wrong verdict, a harmful answer), counting
  invalid outputs and errors as critical;
- **latency**: p50 / p95 / max in milliseconds;
- **estimated cost**: the sum and mean of the catalogue estimate per case, with unpriced and unknown cases counted
  apart, never as USD 0.

The input is either live callables (an operator-run, human-gated step: real providers cost money) or replay records
captured earlier (`run_replay`), so the comparison itself is reproducible offline.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    payload: Mapping[str, Any]
    expect: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CaseOutcome:
    """One model's answer to one case: the output (or the error), its latency and its catalogue cost estimate."""

    case_id: str
    data: Mapping[str, Any] | None
    latency_ms: int
    cost_state: str = "unknown"          # estimated | unpriced | partial | unknown (pricing.estimate_token_cost)
    cost_usd: Decimal | None = None
    error: str | None = None


@dataclass
class ModelReport:
    label: str
    cases: int = 0
    schema_valid: int = 0
    critical: int = 0
    quality_sum: float = 0.0
    quality_count: int = 0
    latencies: list[int] = field(default_factory=list)
    cost_total: Decimal = Decimal(0)
    priced_cases: int = 0
    unpriced_cases: int = 0
    failed_calls: int = 0

    @staticmethod
    def _rate(part: int, whole: int) -> float | None:
        return round(part / whole, 4) if whole else None

    @staticmethod
    def _percentile(values: list[int], q: float) -> int | None:
        if not values:
            return None
        ordered = sorted(values)
        return ordered[max(1, math.ceil(q * len(ordered))) - 1]

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label, "cases": self.cases,
            "schema_valid_rate": self._rate(self.schema_valid, self.cases),
            "quality_mean": round(self.quality_sum / self.quality_count, 4) if self.quality_count else None,
            "critical_failure_rate": self._rate(self.critical, self.cases),
            "latency_ms": {"p50": self._percentile(self.latencies, 0.5), "p95": self._percentile(self.latencies, 0.95),
                           "max": max(self.latencies) if self.latencies else None},
            "cost_usd": {"total_priced": str(self.cost_total), "mean_priced": (
                str(self.cost_total / self.priced_cases) if self.priced_cases else None),
                "priced_cases": self.priced_cases, "unpriced_or_unknown_cases": self.unpriced_cases,
                "failed_calls": self.failed_calls},
        }


Validator = Callable[[Mapping[str, Any]], Any]                      # raises on an invalid output
Grader = Callable[[BenchmarkCase, Mapping[str, Any]], tuple[float, bool]]   # (quality 0..1, critical?)


def score(label: str, cases: Sequence[BenchmarkCase], outcomes: Mapping[str, CaseOutcome], *, validate: Validator,
          grade: Grader) -> ModelReport:
    """The five measurements for one model's outcomes. A missing outcome is an error (critical, invalid)."""
    report = ModelReport(label)
    for case in cases:
        report.cases += 1
        outcome = outcomes.get(case.case_id)
        if outcome is None or outcome.error is not None or outcome.data is None:
            report.critical += 1
            if outcome is not None:
                report.latencies.append(outcome.latency_ms)
                report.failed_calls += 1   # no answer was priced: not counted as an unpriced case
            continue
        report.latencies.append(outcome.latency_ms)
        _cost(report, outcome)
        try:
            validate(outcome.data)
        except Exception:  # noqa: BLE001 - any validator refusal is a schema-invalid output
            report.critical += 1
            continue
        report.schema_valid += 1
        quality, critical = grade(case, outcome.data)
        report.quality_sum += max(0.0, min(1.0, float(quality)))
        report.quality_count += 1
        report.critical += int(bool(critical))
    return report


def _cost(report: ModelReport, outcome: CaseOutcome) -> None:
    if outcome.cost_state == "estimated" and outcome.cost_usd is not None:
        report.cost_total += outcome.cost_usd
        report.priced_cases += 1
    else:
        report.unpriced_cases += 1


def run_live(label: str, cases: Sequence[BenchmarkCase], call: Callable[[BenchmarkCase], tuple[Mapping[str, Any], Mapping[str, Any]]],
             *, price: Callable[[Mapping[str, Any]], tuple[str, Decimal | None]],
             clock: Callable[[], float] = time.monotonic) -> dict[str, CaseOutcome]:
    """Ask one model every case (`call(case) -> (data, runtime)`), timing each and pricing it from its runtime usage.
    A failed call is recorded as an error, never retried here."""
    outcomes: dict[str, CaseOutcome] = {}
    for case in cases:
        started = clock()
        try:
            data, runtime = call(case)
        except Exception as error:  # noqa: BLE001 - recorded as this case's failure
            outcomes[case.case_id] = CaseOutcome(case.case_id, None, int((clock() - started) * 1000),
                                                 error=type(error).__name__)
            continue
        state, amount = price(runtime)
        outcomes[case.case_id] = CaseOutcome(case.case_id, data, int((clock() - started) * 1000), state, amount)
    return outcomes


def run_replay(records: Sequence[Mapping[str, Any]]) -> dict[str, CaseOutcome]:
    """Outcomes from captured records: {case_id, data|null, latency_ms, cost_state, cost_usd|null, error|null}."""
    outcomes: dict[str, CaseOutcome] = {}
    for record in records:
        amount = record.get("cost_usd")
        outcomes[str(record["case_id"])] = CaseOutcome(
            str(record["case_id"]), record.get("data"), int(record.get("latency_ms") or 0),
            str(record.get("cost_state") or "unknown"), None if amount is None else Decimal(str(amount)),
            record.get("error"))
    return outcomes


def compare(candidate: ModelReport, baseline: ModelReport) -> dict[str, Any]:
    """Side by side, with the differences a human reads before H7-2. No verdict."""
    a, b = candidate.as_dict(), baseline.as_dict()

    def delta(x: Any, y: Any) -> Any:
        return None if x is None or y is None else round(float(x) - float(y), 4)

    return {
        "candidate": a, "baseline": b,
        "difference": {
            "schema_valid_rate": delta(a["schema_valid_rate"], b["schema_valid_rate"]),
            "quality_mean": delta(a["quality_mean"], b["quality_mean"]),
            "critical_failure_rate": delta(a["critical_failure_rate"], b["critical_failure_rate"]),
            "latency_p95_ms": delta(a["latency_ms"]["p95"], b["latency_ms"]["p95"]),
            "cost_mean_priced_usd": delta(a["cost_usd"]["mean_priced"], b["cost_usd"]["mean_priced"]),
        },
        "verdict": None,   # H7-2 is a human activation decision
    }
