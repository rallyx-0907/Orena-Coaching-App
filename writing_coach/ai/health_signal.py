"""Provider health from the AI operation telemetry already recorded (PR BZ, owner rule 2026-10-20).

On 2026-10-19 every Gemini call on :8000 failed with HTTP 429 "Your project has exceeded its monthly spending cap" for
hours, and nobody knew until a learner saw "Orena is busy". This module reads the `ai.operation` rows the runtime
already writes (no new table, no new schema) and says, per provider and per capability, how many calls answered and how
many failed in the last few minutes, why they failed, and whether that is an alert.

Failure classes (a closed vocabulary; the provider's own text is read to classify and never kept):

  spend_cap     the account's spending cap or prepaid credit is exhausted (a 429 with spending-cap text, OpenAI's
                `insufficient_quota`, a 402). Nothing recovers until a person acts: alerts at once, severity high.
  rate_limit    any other 429: per-minute quota, tokens per minute. Recovers on its own.
  auth          401 / 403: the key is wrong, revoked or lacks permission. Alerts at once, severity high.
  unconfigured  no key, no model, a model that no longer exists (404), a disabled or unconfigured capability.
  server        5xx from the provider.
  timeout       no answer in the time allowed.
  schema        the request was refused as invalid (400 / 422) or the answer did not parse.
  other         anything else (unreachable, an unknown provider error).

Alert rule (thresholds are policies, editable in Admin > Policies & limits, group "health"):
  - a provider whose latest failures (since its last success) are `spend_cap` or `auth`: alert now, severity high;
  - otherwise `ai.health_consecutive_failures` failures in a row, or `ai.health_window_failures` failures inside
    `ai.health_window_minutes`: alert, severity medium.

Skipped rungs (a provider cooling down, a paid rung over its budget), an answer the capability's own validator refused,
a learner who left mid-stream and a chain's summary row (each rung is recorded on its own) are not provider failures and
are not counted. Operator tests and configuration checks (origin `operator_test`, `configuration`) are not counted
either: an administrator trying a bad key is not an outage.

The system's daily AI spend (D-251: a monitor, never a refusal) is in the same report as `spend`: today's (UTC) total of
the whole AI ledger against the alert threshold (`ai.daily_spend_ceiling_usd`, at most AI_DAILY_SPEND_CEILING_USD). At
the warning ratio it is severity medium; at the threshold severity high, which makes the whole report an alert, so the
health check raises it at once. No learner is refused because of it.

The report carries counts, closed classes, provider and capability ids and timestamps only - never a prompt, a key, a
learner's words or the provider's message. `python -m writing_coach.ai.health_signal` prints it as one JSON line for the
:8000 health check (scripts/health_check_8000.ps1), which Hermes reads.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

REPORT_VERSION = 1
SAMPLE_LIMIT = 500

FAILURE_CLASSES: tuple[str, ...] = (
    "spend_cap", "rate_limit", "auth", "unconfigured", "server", "timeout", "schema", "other",
)
HIGH_CLASSES = frozenset({"spend_cap", "auth"})
# Stamped on a telemetry row that is not a provider failure (see the module docstring); never counted.
NOT_A_FAILURE = "not_counted"
STAMPED_CLASSES = frozenset({*FAILURE_CLASSES, NOT_A_FAILURE})

WINDOW_POLICY = "ai.health_window_minutes"
CONSECUTIVE_POLICY = "ai.health_consecutive_failures"
WINDOW_FAILURES_POLICY = "ai.health_window_failures"
DEFAULT_THRESHOLDS = {"window_minutes": 10, "consecutive": 3, "window_failures": 3}

# A spending cap or exhausted prepaid credit. Gemini's ordinary per-minute 429 says "You exceeded your current quota,
# please check your plan and billing details" - so neither "quota" nor "billing" may decide a spend cap on its own.
_SPEND_CAP = re.compile(
    r"spend(?:ing)?[\s_-]*(?:cap|limit)|insufficient[\s_-]*(?:quota|funds|credits?|balance)"
    r"|credit balance is too low|out of credits|monthly spend",
    re.IGNORECASE,
)
_AUTH_TEXT = re.compile(r"api[\s_-]*key (?:not valid|invalid)|invalid[\s_-]*api[\s_-]*key|unauthenticated|permission[_\s]denied",
                        re.IGNORECASE)

_ERROR_CLASS_MAP = {
    "provider_timeout": "timeout",
    "provider_not_configured": "unconfigured",
    "capability_not_configured": "unconfigured",
    "capability_disabled": "unconfigured",
    "capability_invalid": "unconfigured",
    "capability_unsupported": "unconfigured",
    "model_unavailable": "unconfigured",
    "model_catalog_empty": "unconfigured",
    "provider_response_invalid": "schema",
}
_REASON_MAP = {
    "timeout": "timeout",
    "rate_limited": "rate_limit",
    "payment_required": "spend_cap",
    "auth_failed": "auth",
    "server_error": "server",
    "client_error": "schema",
    "not_configured": "unconfigured",
    "malformed_response": "schema",
}
_STATUS_CLASS_MAP = {"401": "auth", "402": "spend_cap", "403": "auth", "429": "rate_limit", "5xx": "server",
                     "4xx": "schema"}
# Not a provider failure, whatever the row says (see the module docstring).
_NOT_COUNTED_ERRORS = frozenset({"budget_skipped", "client_abandoned", "abnormal_finish", "output_invalid",
                                 "provider_cooling_down"})
_NOT_COUNTED_REASONS = frozenset({"cooling_down", "budget", "unfunded", "invalid_output", "deadline"})


def classify_failure(*, status: int | None = None, text: str = "", error_class: str | None = None,
                     reason: str | None = None, status_class: str | None = None) -> str:
    """One failure as a class of FAILURE_CLASSES. `text` is the provider's message: read here, never stored."""

    body = str(text or "")
    if type(status) is int:
        if status == 429:
            return "spend_cap" if _SPEND_CAP.search(body) else "rate_limit"
        if status == 402:
            return "spend_cap"
        if status in (401, 403):
            return "auth"
        if status >= 500:
            return "server"
        if status == 404:
            return "unconfigured"
        if status in (400, 422):
            return "spend_cap" if _SPEND_CAP.search(body) else "auth" if _AUTH_TEXT.search(body) else "schema"
        if 400 <= status < 500:
            return "other"
    if _SPEND_CAP.search(body):
        return "spend_cap"
    if error_class in _ERROR_CLASS_MAP:
        return _ERROR_CLASS_MAP[error_class]
    if reason in _REASON_MAP:
        return _REASON_MAP[reason]
    if status_class in _STATUS_CLASS_MAP:
        return _STATUS_CLASS_MAP[status_class]
    lowered = body.casefold()
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout"
    if "not configured" in lowered:
        return "unconfigured"
    return "other"


def failure_class_of(error: BaseException | None, *, error_class: str | None = None) -> str:
    """The class of a raised provider or capability error, for the telemetry row it is recorded in."""

    if error is None:
        return NOT_A_FAILURE if error_class in _NOT_COUNTED_ERRORS else classify_failure(error_class=error_class)
    stamped = getattr(error, "failure_class", None)
    if stamped in STAMPED_CLASSES:
        return stamped
    from writing_coach.ai.base import AIOutputInvalid, AIProviderTimeout, telemetry_error_class

    if isinstance(error, AIOutputInvalid):
        return NOT_A_FAILURE
    if isinstance(error, (AIProviderTimeout, TimeoutError)):
        return "timeout"
    return classify_failure(status=getattr(error, "status_code", None), text=str(error),
                            error_class=error_class or telemetry_error_class(error))


def event_failure_class(event: Mapping[str, Any]) -> str | None:
    """A stored row's failure class, or None when the row is not a counted provider failure."""

    if event.get("outcome") != "failure":
        return None
    stamped = event.get("failure_class")
    if stamped == NOT_A_FAILURE or event.get("chain_summary") is True:
        return None
    if stamped in FAILURE_CLASSES:
        return stamped
    # A row recorded before the class was stamped: decided from the closed fields it carries.
    error_class, reason = event.get("error_class"), event.get("fallback_reason")
    if error_class in _NOT_COUNTED_ERRORS or reason in _NOT_COUNTED_REASONS:
        return None
    return classify_failure(error_class=error_class, reason=reason, status_class=event.get("http_status_class"))


def thresholds(reader: Callable[[str], Any] | None = None) -> dict[str, int]:
    """The alert thresholds in force: the policies, else the defaults."""

    if reader is None:
        from writing_coach import policies

        reader = policies.value
    chosen = dict(DEFAULT_THRESHOLDS)
    for name, key in (("window_minutes", WINDOW_POLICY), ("consecutive", CONSECUTIVE_POLICY),
                      ("window_failures", WINDOW_FAILURES_POLICY)):
        try:
            value = reader(key)
        except Exception:  # noqa: BLE001 - an unreadable policy keeps the default; health must still report
            continue
        if type(value) is int and value >= 1:
            chosen[name] = value
    return chosen


def _stamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str) and value:
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _iso(moment: datetime | None) -> str | None:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


_ID = re.compile(r"[a-z][a-z0-9_-]{0,79}")


def _summarise(rows: list[tuple[datetime, str | None]], limits: Mapping[str, int]) -> dict[str, Any]:
    """`rows` newest first: (time, failure class or None for a success)."""

    ok = sum(1 for _, cls in rows if cls is None)
    failures = [(at, cls) for at, cls in rows if cls is not None]
    consecutive = 0
    for _, cls in rows:
        if cls is None:
            break
        consecutive += 1
    by_class = Counter(cls for _, cls in failures)
    leading = [cls for _, cls in rows[:consecutive]]
    high = next((cls for cls in leading if cls in HIGH_CLASSES), None)
    if consecutive:
        failure_class = high or Counter(leading).most_common(1)[0][0]
    else:
        failure_class = by_class.most_common(1)[0][0] if by_class else None
    severity = None
    if high:
        severity = "high"
    elif consecutive >= limits["consecutive"] or len(failures) >= limits["window_failures"]:
        severity = "medium"
    last_error = failures[0][0] if failures else None
    last_ok = next((at for at, cls in rows if cls is None), None)
    return {
        "status": "alert" if severity else ("degraded" if failures else "ok"),
        "severity": severity,
        "ok": ok,
        "failed": len(failures),
        "consecutive_failures": consecutive,
        "failure_class": failure_class,
        "by_class": {name: by_class[name] for name in FAILURE_CLASSES if by_class[name]},
        "last_error_at": _iso(last_error),
        "last_ok_at": _iso(last_ok),
    }


def provider_health(events: Iterable[Mapping[str, Any]] | None = None, *, now: datetime | None = None,
                    window_minutes: int | None = None, limits: Mapping[str, int] | None = None,
                    truncated: bool = False) -> dict[str, Any]:
    """Per provider (and per capability under it): ok / failed counts, the failure class and whether it alerts.

    `events` are sanitized `ai.operation` rows with `created_at` (the repository's `list_ai_operation_events`)."""

    chosen = dict(limits or thresholds())
    if window_minutes is not None:
        chosen["window_minutes"] = int(window_minutes)
    moment = now or datetime.now(UTC)
    since = moment - timedelta(minutes=chosen["window_minutes"])
    grouped: dict[str, list[tuple[datetime, str | None, str]]] = {}
    whole: dict[str, list[tuple[datetime, str | None]]] = {}   # the whole sample, for "failing since"
    for event in events or ():
        if not isinstance(event, Mapping) or event.get("origin") in {"operator_test", "configuration"}:
            continue
        provider, capability = str(event.get("provider") or ""), str(event.get("capability") or "")
        at = _stamp(event.get("created_at"))
        if at is None or at > moment + timedelta(minutes=1) or not _ID.fullmatch(provider):
            continue
        counted = event.get("outcome") == "success" or event_failure_class(event) is not None
        if counted:
            whole.setdefault(provider, []).append((at, None if event.get("outcome") == "success" else "x"))
        if at < since:
            continue
        outcome = event.get("outcome")
        if outcome == "success":
            cls = None
        elif outcome == "failure":
            cls = event_failure_class(event)
            if cls is None:
                continue
        else:
            continue
        grouped.setdefault(provider, []).append((at, cls, capability if _ID.fullmatch(capability) else "unknown"))

    providers = []
    for provider in sorted(grouped):
        rows = sorted(grouped[provider], key=lambda item: item[0], reverse=True)
        entry = {"provider": provider, **_summarise([(at, cls) for at, cls, _ in rows], chosen)}
        run = []
        for at, cls in sorted(whole.get(provider, []), key=lambda item: item[0], reverse=True):
            if cls is None:
                break
            run.append(at)
        entry["failing_since"] = _iso(min(run)) if run else None
        capabilities = []
        for capability in sorted({cap for _, _, cap in rows}):
            mine = [(at, cls) for at, cls, cap in rows if cap == capability]
            capabilities.append({"capability": capability, **_summarise(mine, chosen)})
        entry["capabilities"] = capabilities
        providers.append(entry)

    alerts = [
        {"provider": item["provider"], "severity": item["severity"], "failure_class": item["failure_class"],
         "failed": item["failed"], "consecutive_failures": item["consecutive_failures"],
         "last_error_at": item["last_error_at"], "failing_since": item["failing_since"],
         "capabilities": [cap["capability"] for cap in item["capabilities"] if cap["failed"]]}
        for item in providers if item["severity"]
    ]
    alerts.sort(key=lambda alert: (alert["severity"] != "high", alert["provider"]))
    severity = "high" if any(a["severity"] == "high" for a in alerts) else "medium" if alerts else None
    return {
        "version": REPORT_VERSION,
        "checked_at": _iso(moment),
        "window_minutes": chosen["window_minutes"],
        "thresholds": {"consecutive_failures": chosen["consecutive"], "window_failures": chosen["window_failures"]},
        "available": True,
        "truncated": bool(truncated),
        "status": "alert" if alerts else "ok",
        "severity": severity,
        "alerts": alerts,
        "providers": providers,
    }


def unavailable_report(now: datetime | None = None) -> dict[str, Any]:
    """The telemetry could not be read: the report says so instead of claiming health."""

    report = provider_health([], now=now, limits=DEFAULT_THRESHOLDS)
    report.update({"available": False, "status": "unknown"})
    return report


def switch_history(events: Iterable[Mapping[str, Any]], *, limit: int = 50) -> list[dict[str, Any]]:
    """The router's recent provider switches (the `provider_switch` field of the recorded operations), newest first."""

    rows = []
    for event in events or ():
        if not isinstance(event, Mapping):
            continue
        switch, at = event.get("provider_switch"), _stamp(event.get("created_at"))
        if not isinstance(switch, Mapping) or at is None:
            continue
        capability = str(event.get("capability") or "")
        rows.append({
            "at": _iso(at), "capability": capability if _ID.fullmatch(capability) else "unknown",
            "from": switch.get("from"), "to": switch.get("to"), "reason": switch.get("reason"),
            "trigger": switch.get("trigger"), "answered": bool(switch.get("to")) and event.get("outcome") == "success",
        })
    rows.sort(key=lambda row: row["at"], reverse=True)
    return rows[:limit]


def down_providers(report: Mapping[str, Any], switches: list[dict[str, Any]],
                   breaker: Mapping[str, Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The providers that are down now: the router's breaker has stood them down (in this process), or the recorded
    operations alert. For each: the reason (a failure class), since when, which capabilities answered on a backup
    since then and which got no answer."""

    alerts = {alert["provider"]: alert for alert in report.get("alerts") or []}
    stood_down: dict[str, Mapping[str, Any]] = {}
    for key, state in (breaker or {}).items():
        # A provider's own entry, or one of its models' (a spending cap is held per model): either stands it down.
        provider = str(state.get("provider") or key) if isinstance(state, Mapping) else ""
        if isinstance(state, Mapping) and state.get("cooling_down") and _ID.fullmatch(provider):
            stood_down.setdefault(provider, state)
    rows = []
    down = set(alerts) | set(stood_down)
    for provider in sorted(down):
        alert, state = alerts.get(provider) or {}, stood_down.get(provider) or {}
        reason = state.get("reason") or alert.get("failure_class") or "other"
        reason = reason if reason in FAILURE_CLASSES else "other"
        since = state.get("down_since") or alert.get("failing_since") or alert.get("last_error_at")
        mine = [row for row in switches if row["from"] == provider and (not since or row["at"] >= since)]
        # Each capability's newest switch says where it stands now: one answer on the backup earlier does not mean it
        # runs on the backup when the switches since got no answer, nor when that backup is itself down now.
        latest: dict[str, Mapping[str, Any]] = {}
        for row in sorted(mine, key=lambda item: item["at"], reverse=True):
            latest.setdefault(row["capability"], row)
        on_backup = sorted(cap for cap, row in latest.items() if row["answered"] and row.get("to") not in down)
        # No working route: the capability's backup is down too.
        backup_down = sorted(cap for cap, row in latest.items() if row.get("to") in down and cap not in on_backup)
        failing = set(alert.get("capabilities") or []) | {cap for cap, row in latest.items() if not row["answered"]}
        rows.append({
            "provider": provider, "reason": reason, "since": since,
            "severity": "high" if reason in HIGH_CLASSES else (alert.get("severity") or "medium"),
            "on_backup": on_backup, "without_backup": sorted(failing - set(on_backup) - set(backup_down)),
            "backup_down": backup_down,
            # The backup each capability last moved to ({capability: provider}), so Admin can name it.
            "backups": {cap: str(latest[cap]["to"]) for cap in sorted(latest) if latest[cap].get("to")},
            "breaker_open": bool(state), "seconds_remaining": int(state.get("seconds_remaining") or 0),
        })
    rows.sort(key=lambda row: (row["severity"] != "high", row["provider"]))
    return rows


def spend_monitor(repository: Any, *, now: datetime | None = None,
                  reader: Callable[[str], Any] | None = None) -> dict[str, Any]:
    """Today's whole-system AI spend against the monitor's threshold: {threshold_usd, spent_usd, ratio, warn_ratio,
    severity (None | medium | high), readable}. Severity high means the threshold is reached; nothing is refused."""

    if reader is None:
        from writing_coach import policies

        reader = policies.value
    moment = now or datetime.now(UTC)
    try:
        threshold = reader("ai.daily_spend_ceiling_usd")
        warn = float(reader("ai.daily_spend_warn_ratio"))
    except Exception:  # noqa: BLE001 - an unreadable threshold is reported, never guessed
        return {"threshold_usd": None, "spent_usd": None, "ratio": None, "warn_ratio": None, "severity": None,
                "readable": False}
    if threshold is None:
        return {"threshold_usd": None, "spent_usd": None, "ratio": None, "warn_ratio": warn, "severity": None,
                "readable": True}
    midnight = datetime(moment.year, moment.month, moment.day, tzinfo=UTC)
    try:
        usd, unpriced = repository.ai_spend_since(midnight)
    except Exception:  # noqa: BLE001 - an unreadable ledger is "unknown", never "below the threshold"
        return {"threshold_usd": float(threshold), "spent_usd": None, "ratio": None, "warn_ratio": warn,
                "severity": None, "readable": False}
    from writing_coach.agent.budget import UNPRICED_ALLOWANCE_USD

    spent = round(float(usd) + int(unpriced) * UNPRICED_ALLOWANCE_USD, 4)
    ratio = round(spent / float(threshold), 4) if threshold else None
    severity = "high" if spent >= float(threshold) else "medium" if spent >= warn * float(threshold) else None
    return {"threshold_usd": float(threshold), "spent_usd": spent, "ratio": ratio, "warn_ratio": warn,
            "severity": severity, "readable": True}


def _with_spend(report: dict[str, Any], spend: dict[str, Any]) -> dict[str, Any]:
    """The spend monitor folded into the report: at the threshold the report is an alert of severity high."""

    report["spend"] = spend
    if spend.get("severity") == "high":
        report["status"], report["severity"] = "alert", "high"
    elif spend.get("severity") == "medium" and report.get("severity") is None:
        report["severity"] = "medium"
    return report


def report_from_repository(repository: Any, *, now: datetime | None = None,
                           breaker: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """The report over the most recent `SAMPLE_LIMIT` operation rows (a busier window is reported as truncated), with
    the recent provider switches and the providers that are down. `breaker` is this process's router breaker
    (`routing.provider_health.snapshot()`); another process (the health check's CLI) has none and reads the rows."""

    try:
        events = list(repository.list_ai_operation_events(SAMPLE_LIMIT))
    except Exception:  # noqa: BLE001 - an unreadable ledger is "unknown", never "healthy"
        report = unavailable_report(now)
        report.update({"switches": [], "down": down_providers(report, [], breaker)})
        return _with_spend(report, spend_monitor(repository, now=now))
    moment = now or datetime.now(UTC)
    limits = thresholds()
    oldest = min((stamp for stamp in (_stamp(e.get("created_at")) for e in events) if stamp), default=None)
    truncated = len(events) >= SAMPLE_LIMIT and oldest is not None and oldest > moment - timedelta(
        minutes=limits["window_minutes"])
    report = provider_health(events, now=moment, limits=limits, truncated=truncated)
    switches = switch_history(events)
    report["switches"] = switches
    report["down"] = down_providers(report, switches, breaker)
    return _with_spend(report, spend_monitor(repository, now=moment))


_CLASS_WORDS = {
    "spend_cap": "spending cap reached", "rate_limit": "rate limited", "auth": "key rejected",
    "unconfigured": "not configured", "server": "provider server error", "timeout": "timing out",
    "schema": "request or answer invalid", "other": "failing",
}


def health_line(report: Mapping[str, Any]) -> str:
    """The text after PASS/FAIL on the health check's `providers` line (English, operator log)."""

    spend = report.get("spend") or {}
    spend_part = ""
    if spend.get("severity"):
        level = "reached" if spend["severity"] == "high" else "near"
        spend_part = (f" spend={level}({spend['severity']}) spent_usd={spend.get('spent_usd')} "
                      f"threshold_usd={spend.get('threshold_usd')} [monitor only; no learner is refused]")
    if not report.get("available", True):
        return "status=unknown telemetry unreadable" + spend_part
    window = report.get("window_minutes")
    if not report.get("alerts"):
        if spend.get("severity") == "high":
            return f"status=alert severity=high window_min={window}" + spend_part
        counted = sum(int(item.get("ok", 0)) + int(item.get("failed", 0)) for item in report.get("providers") or [])
        return f"status=ok calls={counted} window_min={window}" + spend_part
    down = {row["provider"]: row for row in report.get("down") or []}
    parts = []
    for alert in report["alerts"]:
        row = down.get(alert["provider"]) or {}
        parts.append(
            f"{alert['provider']}:{alert['failure_class']}({alert['severity']}) failed={alert['failed']} "
            f"consecutive={alert['consecutive_failures']} since={alert.get('failing_since')} "
            f"last={alert['last_error_at']} caps={','.join(alert['capabilities']) or '-'} "
            f"on_backup={','.join(row.get('on_backup') or []) or '-'} "
            f"[{_CLASS_WORDS.get(alert['failure_class'], 'failing')}]"
        )
    return f"status=alert severity={report.get('severity')} window_min={window} " + "; ".join(parts) + spend_part


def main(argv: list[str] | None = None) -> int:
    """Print the report as ONE JSON line (read-only: one SELECT on audit_logs and the policies document)."""

    from writing_coach import policies
    from writing_coach.persistence.config import create_runtime_engine
    from writing_coach.persistence.platform_repository import PostgresPlatformRepository

    args = list(sys.argv[1:] if argv is None else argv)
    try:
        repository = PostgresPlatformRepository(create_runtime_engine())
        policies.configure(repository)
        report = report_from_repository(repository)
    except Exception:  # noqa: BLE001 - no database URL or no database: say unknown, never print the error's detail
        report = unavailable_report()
    report["line"] = health_line(report)
    if "--line" in args:
        print(report["line"])  # noqa: T201 - the CLI's output
    else:
        print(json.dumps(report, separators=(",", ":"), sort_keys=True, ensure_ascii=True))  # noqa: T201
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through scripts/health_check_8000.ps1
    raise SystemExit(main())
