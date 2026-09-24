"""Privacy-bounded aggregation for the Admin activity view.

Inputs are already scoped repository facts; output deliberately contains no
learner identifiers, text, URLs, or per-event rows.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any

SKILLS = ("writing", "reading", "listening", "speaking")
FUNNEL_SUPPORT = {
    "writing": {"started": False, "attempted": True, "completed": True},
    # Canonical Reading has no "started" record: an attempt exists only once
    # submitted (D-075), so the stage is unsupported, never counted as zero.
    "reading": {"started": False, "attempted": True, "completed": True},
    "listening": {"started": False, "attempted": True, "completed": True},
    "speaking": {"started": False, "attempted": False, "completed": True},
}
LEARNER_DEGRADED_ERROR_CLASSES = frozenset({
    "capability_disabled", "capability_not_configured", "capability_invalid",
    "capability_unsupported", "provider_not_configured", "provider_unavailable",
    "model_catalog_empty", "model_unavailable", "provider_response_invalid",
    "provider_error", "operation_failed",
})


def _when(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def aggregate_product_activity(rows: Any, *, window_days: int = 7, now: datetime | None = None, cohort_start: datetime | None = None) -> dict[str, Any]:
    days = max(1, min(int(window_days or 7), 30))
    end = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    # The window is the current calendar day plus the preceding days-1 days;
    # this keeps every in-window event represented by exactly one bucket.
    start = datetime.combine(end.date() - timedelta(days=days - 1), datetime.min.time(), tzinfo=timezone.utc)
    cohort_floor = (cohort_start or (start - timedelta(days=7))).astimezone(timezone.utc)
    buckets = {(start.date() + timedelta(days=i)).isoformat(): {"activities": 0, "completions": 0} for i in range(days)}
    by_skill = {skill: {"skill": skill, "activities": 0, "completions": 0, "days": {key: {"activities": 0, "completions": 0} for key in buckets}} for skill in SKILLS}
    learners: set[str] = set()
    cohort_days: dict[str, set[str]] = {}
    cohort_skills: dict[str, set[str]] = {}
    learner_days: dict[str, set[str]] = {}
    learner_completed: dict[str, int] = {}
    learner_skills: dict[str, set[str]] = {}
    funnel_keys = {skill: {stage: set() for stage in FUNNEL_SUPPORT[skill]} for skill in SKILLS}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        skill = row.get("skill")
        occurred = _when(row.get("occurred_at"))
        learner = row.get("learner_key")
        if skill not in by_skill or occurred is None or not (cohort_floor <= occurred <= end) or not isinstance(learner, str) or not learner:
            continue
        day = occurred.date().isoformat()
        cohort_days.setdefault(learner, set()).add(day)
        cohort_skills.setdefault(learner, set()).add(skill)
        funnel_stage = row.get("funnel_stage")
        if row.get("funnel_only") is True:
            funnel_key = row.get("funnel_key")
            if funnel_stage in funnel_keys[skill] and FUNNEL_SUPPORT[skill][funnel_stage] is True and isinstance(funnel_key, str) and funnel_key and start <= occurred <= end:
                funnel_keys[skill][funnel_stage].add(funnel_key)
            continue
        if not (start <= occurred <= end) or day not in buckets:
            continue
        completed = row.get("completed") is True
        learners.add(learner)
        learner_days.setdefault(learner, set()).add(day)
        learner_completed[learner] = learner_completed.get(learner, 0) + int(completed)
        learner_skills.setdefault(learner, set()).add(skill)
        buckets[day]["activities"] += 1
        buckets[day]["completions"] += int(completed)
        by_skill[skill]["activities"] += 1
        by_skill[skill]["completions"] += int(completed)
        by_skill[skill]["days"][day]["activities"] += 1
        by_skill[skill]["days"][day]["completions"] += int(completed)
    skills = []
    for skill in SKILLS:
        row = by_skill[skill]
        row["days"] = [{"date": key, **value} for key, value in row["days"].items()]
        row["completion_rate_percent"] = round(row["completions"] * 100 / row["activities"], 1) if row["activities"] else None
        skills.append(row)
    for skill in SKILLS:
        stages = []
        previous_keys = None
        for stage, supported in FUNNEL_SUPPORT[skill].items():
            keys = funnel_keys[skill][stage] if supported else None
            count = len(keys) if keys is not None else None
            matched = len(keys & previous_keys) if keys is not None and previous_keys is not None else None
            rate = round(matched * 100 / len(previous_keys), 1) if matched is not None and previous_keys else None
            stages.append({"stage": stage, "available": supported, "count": count, "rate_percent": rate})
            previous_keys = keys
        by_skill[skill]["funnel"] = {"stages": stages}
    total = sum(item["activities"] for item in skills)
    return_days = [1, 3, 7]
    return_windows = []
    for offset in return_days:
        eligible = 0
        returned = 0
        for active_days in cohort_days.values():
            first = min(active_days)
            first_date = datetime.fromisoformat(first).date()
            if first_date + timedelta(days=offset) > end.date():
                continue
            eligible += 1
            if any(datetime.fromisoformat(day).date() >= first_date + timedelta(days=offset) for day in active_days):
                returned += 1
        return_windows.append({"days": offset, "eligible_learners": eligible, "returned_learners": returned, "return_rate_percent": round(returned * 100 / eligible, 1) if eligible else None})
    daily_returning = []
    for key in buckets:
        current = {learner for learner, active_days in cohort_days.items() if key in active_days}
        returning = sum(1 for learner in current if any(day < key for day in cohort_days[learner]))
        daily_returning.append({"date": key, "returning_learners": returning})
    return {"available": True, "data_state": "ready" if total else "insufficient_data", "has_data": bool(total), "window_days": days, "window_start": start.isoformat(), "window_end": end.isoformat(), "active_learners": len(learners) if total else None, "returning_learners": sum(1 for active_days in cohort_days.values() if len(active_days) >= 2) if total else None, "repeat_practice_learners": sum(1 for count in learner_completed.values() if count >= 2) if total else None, "cross_skill_returning_learners": sum(1 for learner, skills_seen in cohort_skills.items() if len(skills_seen) >= 2 and len(cohort_days.get(learner, set())) >= 2) if total else None, "return_windows": return_windows, "daily_returning": daily_returning, "total_activities": total, "total_completions": sum(item["completions"] for item in skills), "skills": skills}


def aggregate_cost_per_active_learner(activity: dict[str, Any], operations: Any) -> dict[str, Any]:
    """Join matching-window priced operation evidence to aggregate active learners."""
    if not isinstance(activity, dict) or not isinstance(operations, dict) or operations.get("available") is False:
        return {"available": False, "data_state": "unavailable", "currency_state": "none", "cost_totals": [], "capability_cost": []}
    if operations.get("sample_truncated") is True:
        return {"available": True, "data_state": "insufficient_data", "evidence_state": "partial", "currency_state": "unknown", "cost_totals": [], "capability_cost": [], "considered_operations": operations.get("sample_limit")}
    active = activity.get("active_learners")
    start = _when(activity.get("window_start"))
    end = _when(activity.get("window_end"))
    if start is None or end is None:
        return {"available": False, "data_state": "unavailable", "currency_state": "none", "cost_totals": [], "capability_cost": []}
    totals: dict[tuple[str, str], dict[str, Any]] = {}
    by_capability: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    priced = 0
    considered = 0
    unpriced = 0
    for raw in operations.get("recent") if isinstance(operations.get("recent"), list) else []:
        if not isinstance(raw, dict):
            continue
        occurred = _when(raw.get("created_at"))
        if occurred is None or not (start <= occurred <= end):
            continue
        considered += 1
        cost = raw.get("cost") if isinstance(raw.get("cost"), dict) else {}
        amount = cost.get("amount")
        currency = cost.get("currency")
        state = cost.get("state")
        if state != "estimated" or not isinstance(amount, (int, float)) or not isinstance(currency, str) or not currency.strip() or amount < 0:
            unpriced += 1
            continue
        provenance = cost.get("provenance") if isinstance(cost.get("provenance"), dict) else {}
        version = str(provenance.get("catalog_version") or "unknown")
        key = (currency.strip(), version)
        item = totals.setdefault(key, {"currency": key[0], "catalog_version": version, "amount": 0.0, "evidence_count": 0})
        item["amount"] = round(item["amount"] + float(amount), 8)
        item["evidence_count"] += 1
        capability = str(raw.get("capability") or "unknown")
        cap_item = by_capability.setdefault(capability, {}).setdefault(key, {"currency": key[0], "catalog_version": version, "amount": 0.0, "evidence_count": 0})
        cap_item["amount"] = round(cap_item["amount"] + float(amount), 8)
        cap_item["evidence_count"] += 1
        priced += 1
    currency_state = "none" if not totals else "single" if len({key[0] for key in totals}) == 1 else "mixed"
    evidence_state = "unpriced" if not priced else "partial" if unpriced else "estimated"
    denominator = active if isinstance(active, int) and active > 0 else None
    cost_totals = [{**item, "cost_per_active_learner": round(item["amount"] / denominator, 8) if denominator else None} for item in totals.values()]
    capability_cost = [{"capability": capability, "cost_totals": [{**item, "cost_per_active_learner": round(item["amount"] / denominator, 8) if denominator else None} for item in values.values()]} for capability, values in by_capability.items()]
    return {"available": True, "data_state": "ready" if priced else "insufficient_data", "evidence_state": evidence_state, "currency_state": currency_state, "window_start": activity.get("window_start"), "window_end": activity.get("window_end"), "active_learners": active if denominator else None, "considered_operations": considered, "cost_totals": cost_totals, "capability_cost": capability_cost}


def aggregate_learner_impact_failures(operations: Any, *, window_days: int = 7, now: datetime | None = None) -> dict[str, Any]:
    """Aggregate validated learner-origin failures without learner attribution."""
    days = max(1, min(int(window_days or 7), 30))
    end = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = datetime.combine(end.date() - timedelta(days=days - 1), datetime.min.time(), tzinfo=timezone.utc)
    base = {"window_days": days, "window_start": start.isoformat(), "window_end": end.isoformat(), "by_capability": []}
    if not isinstance(operations, dict) or operations.get("available") is False:
        return {"available": False, "data_state": "unavailable", "has_data": False, **base}
    if operations.get("sample_truncated") is True:
        return {"available": True, "data_state": "insufficient_data", "has_data": False, **base}
    by_capability: dict[str, dict[str, Any]] = {}
    events = operations.get("recent") if isinstance(operations.get("recent"), list) else []
    for event in events:
        if not isinstance(event, dict) or event.get("origin") != "learner" or event.get("outcome") != "failure":
            continue
        capability = event.get("capability")
        occurred = _when(event.get("created_at"))
        error_class = event.get("error_class")
        if not isinstance(capability, str) or not capability or (capability not in {"legacy", "[invalid]"} and not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", capability)) or occurred is None or not (start <= occurred <= end):
            continue
        day = occurred.date().isoformat()
        item = by_capability.setdefault(capability, {"capability": capability, "failure_count": 0, "degraded_count": 0, "days": {}})
        item["failure_count"] += 1
        degraded = isinstance(error_class, str) and error_class in LEARNER_DEGRADED_ERROR_CLASSES
        item["degraded_count"] += int(degraded)
        bucket = item["days"].setdefault(day, {"date": day, "failure_count": 0, "degraded_count": 0})
        bucket["failure_count"] += 1
        bucket["degraded_count"] += int(degraded)
    rows = []
    for item in sorted(by_capability.values(), key=lambda value: value["capability"]):
        item["days"] = [item["days"][key] for key in sorted(item["days"])]
        rows.append(item)
    total = sum(item["failure_count"] for item in rows)
    return {"available": True, "data_state": "ready" if total else "insufficient_data", "has_data": bool(total), **base, "by_capability": rows}


if __name__ == "__main__":
    result = aggregate_product_activity([{"learner_key": "u1", "skill": "writing", "occurred_at": "2026-01-02T12:00:00+00:00", "completed": True}], now=datetime(2026, 1, 3, tzinfo=timezone.utc), window_days=7)
    assert result["active_learners"] == 1 and result["skills"][0]["completions"] == 1
    assert "learner_key" not in result and "text" not in result
    print("product activity selftest: PASS")
