"""Capability-centric AI administration without learner runtime activation."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable

from writing_coach.ai.base import (
    AICapabilityConfigInvalid,
    AICapabilityUnsupported,
    AICapabilityDisabled,
    AICapabilityNotConfigured,
    AIModelCatalogEmpty,
    AIModelUnavailable,
    AIProviderError,
    AIProviderNotConfigured,
    AIProviderResponseInvalid,
    normalized_latency,
    normalized_rate_limit,
    normalized_usage,
    telemetry_error_class,
    http_status_class,
    sanitize_telemetry,
)
from writing_coach.ai.pricing import estimate_token_cost
from writing_coach.ai.capabilities import all_capabilities, require_capability
from writing_coach.ai.config import CapabilityConfig, validate_capability_config
from writing_coach.ai.providers import build_providers, provider_definitions
from writing_coach.persistence.platform_repository import PlatformRepository


_SUSPICIOUS_MODEL = re.compile(
    r"(?:^[a-z][a-z0-9+.-]*://|[?#]|(?:api[_-]?key|token|secret|password|authorization)\s*=)",
    re.IGNORECASE,
)

_OPERATION_HEALTH_WINDOW = 20
_DEGRADED_FAILURE_RATE_PERCENT = 50
_DEGRADED_LATENCY_MS = 2000
_PROVIDER_FAILURE_CLASSES = frozenset({
    "provider_error",
    "provider_unavailable",
    "provider_not_configured",
    "model_catalog_empty",
    "model_unavailable",
    "provider_response_invalid",
})
_TREND_WINDOW_DAYS = 7


def _operation_health(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify a bounded persisted-event sample without probing providers."""

    sample = events[:_OPERATION_HEALTH_WINDOW]
    evidence_count = len(sample)
    if not evidence_count:
        return {
            "health_state": "no_data",
            "evidence_count": 0,
            "failure_count": 0,
            "provider_failure_count": 0,
            "failure_rate_percent": None,
            "avg_latency_ms": None,
        }
    failure_count = sum(event.get("outcome") == "failure" for event in sample)
    provider_failure_count = sum(
        event.get("outcome") == "failure"
        and event.get("error_class") in _PROVIDER_FAILURE_CLASSES
        for event in sample
    )
    latencies = [
        event["latency_ms"]
        for event in sample
        if isinstance(event.get("latency_ms"), int)
    ]
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else None
    failure_rate_percent = round(failure_count * 100 / evidence_count)
    if provider_failure_count:
        health_state = "provider_failure"
    elif (
        failure_rate_percent >= _DEGRADED_FAILURE_RATE_PERCENT
        or (avg_latency is not None and avg_latency >= _DEGRADED_LATENCY_MS)
    ):
        health_state = "degraded"
    else:
        health_state = "healthy"
    return {
        "health_state": health_state,
        "evidence_count": evidence_count,
        "failure_count": failure_count,
        "provider_failure_count": provider_failure_count,
        "failure_rate_percent": failure_rate_percent,
        "avg_latency_ms": avg_latency,
    }


def _operation_trend(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bucket persisted evidence into a bounded UTC calendar-day trend."""

    parsed = []
    for event in events:
        stamp = event.get("created_at")
        if not isinstance(stamp, str):
            parsed.append((None, event))
            continue
        try:
            value = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            parsed.append((value.astimezone(timezone.utc) if value.tzinfo is not None else None, event))
        except (TypeError, ValueError, OverflowError):
            parsed.append((None, event))
    dated = [value for value, _event in parsed if value is not None]
    anchor = max(dated).date() if dated else None
    buckets: dict[str, list[dict[str, Any]]] = {}
    for value, event in parsed:
        if value is None or anchor is None:
            key = "unknown"
        else:
            age = (anchor - value.date()).days
            if age < 0 or age >= _TREND_WINDOW_DAYS:
                continue
            key = value.date().isoformat()
        buckets.setdefault(key, []).append(event)
    result = []
    for key, bucket_events in sorted(buckets.items(), key=lambda item: item[0], reverse=True):
        token_keys = ("prompt_tokens", "completion_tokens", "total_tokens")
        token_totals = {name: 0 for name in token_keys}
        token_seen = set()
        latencies = [event["latency_ms"] for event in bucket_events if isinstance(event.get("latency_ms"), int)]
        usage_known = usage_partial = usage_unknown = 0
        rate_limit_reported = 0
        failures = 0
        cost_totals: dict[tuple[str, str], dict[str, Any]] = {}
        cost_state_counts = {state: 0 for state in ("estimated", "unpriced", "partial", "unknown")}
        for event in bucket_events:
            failures += event.get("outcome") == "failure"
            usage = event.get("usage") or {}
            known = [name for name in token_keys if isinstance(usage.get(name), int)]
            for name in known:
                token_totals[name] += usage[name]
                token_seen.add(name)
            if len(known) == len(token_keys):
                usage_known += 1
            elif known:
                usage_partial += 1
            else:
                usage_unknown += 1
            rate_limit = event.get("rate_limit") or {}
            if any(isinstance(rate_limit.get(name), int) for name in ("requests_limit", "requests_remaining", "tokens_limit", "tokens_remaining")):
                rate_limit_reported += 1
            cost = event.get("cost") if isinstance(event.get("cost"), dict) else {"state": "unknown"}
            state = cost.get("state")
            if state in cost_state_counts:
                cost_state_counts[state] += 1
            amount = cost.get("amount")
            currency = cost.get("currency")
            provenance = cost.get("provenance") or {}
            if state == "estimated" and isinstance(amount, (int, float)) and currency:
                version = str(provenance.get("catalog_version") or "unknown")
                cost_key = (currency, version)
                item = cost_totals.setdefault(cost_key, {"currency": currency, "amount": 0.0, "evidence_count": 0, "catalog_version": version})
                item["amount"] = round(item["amount"] + float(amount), 8)
                item["evidence_count"] += 1
        result.append({
            "bucket": key,
            "request_count": len(bucket_events),
            "failure_count": failures,
            "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
            "usage_known": usage_known,
            "usage_partial": usage_partial,
            "usage_unknown": usage_unknown,
            "token_totals": {name: token_totals[name] if name in token_seen else None for name in token_keys},
            "rate_limit_reported_count": rate_limit_reported,
            "cost_totals": list(cost_totals.values()),
            "cost_state_counts": cost_state_counts,
        })
    return result


def safe_model_display(model: object) -> tuple[str, bool]:
    """Return an operator-safe model label without modifying persisted data."""

    value = str(model or "")
    if _SUSPICIOUS_MODEL.search(value):
        return "[redacted]", True
    return value, False


def safe_capability_display(capability_key: object) -> str:
    """Return a catalog-owned capability label, never an arbitrary caller value."""

    try:
        return require_capability(capability_key).key
    except AICapabilityUnsupported:
        return "[invalid]"


def _sanitized_config(config: CapabilityConfig) -> dict[str, Any]:
    value = config.to_dict()
    model, redacted = safe_model_display(config.model)
    value["model"] = model
    value["model_redacted"] = redacted
    backup_model, backup_redacted = safe_model_display(config.backup_model)
    value["backup_model"] = backup_model or None
    value["backup_model_redacted"] = backup_redacted
    return value


def _config_provenance(record: Any) -> dict[str, Any]:
    """Expose audit-safe saved-state metadata without the administrator identity."""

    if record is None:
        return {
            "saved": False,
            "updated_at": None,
            "updated_by_present": False,
        }
    updated_at = str(getattr(record, "updated_at", "") or "").strip() or None
    return {
        "saved": True,
        "updated_at": updated_at,
        "updated_by_present": bool(str(getattr(record, "updated_by", "") or "").strip()),
    }


def _failure_fields(exc: BaseException) -> dict[str, Any]:
    """The HTTP status class and the reason of a provider failure, so a 429 is not just "provider_error"."""

    if not isinstance(exc, AIProviderError):
        return {}
    from writing_coach.ai.routing import fallback_reason

    return {
        "http_status_class": http_status_class(getattr(exc, "status_code", None)),
        "fallback_reason": fallback_reason(exc),
    }


class AIControlPlane:
    """Orchestrates static config administration and explicit live probes."""

    def __init__(
        self,
        repository: PlatformRepository,
        *,
        provider_factory: Callable[[], dict[str, Any]] = build_providers,
    ) -> None:
        self.repository = repository
        self.provider_factory = provider_factory

    def _record_operation(self, telemetry: dict[str, Any]) -> None:
        recorder = getattr(self.repository, "record_ai_operation", None)
        safe = sanitize_telemetry(telemetry)
        if safe is None or not callable(recorder):
            return
        try:
            recorder(safe)
        except Exception:
            return

    def inspect(self) -> dict[str, Any]:
        """Build a sanitized, network-free view of the product capability catalog."""

        explicit = {
            row.capability_key: row
            for row in self.repository.list_capability_configs()
        }
        runtimes = self.provider_factory()
        capabilities = []
        for definition in all_capabilities():
            record = explicit.get(definition.key)
            config = record.config if record is not None else None
            capabilities.append(
                {
                    "key": definition.key,
                    "operation": definition.operation.value,
                    "implemented": definition.implemented,
                    "provider_backed": definition.provider_backed,
                    "configurable": definition.configurable,
                    "allowed_fallback_policies": sorted(
                        policy.value for policy in definition.allowed_fallback_policies
                    ),
                    "explicit_config_exists": config is not None,
                    "config": _sanitized_config(config) if config is not None else None,
                    "config_provenance": _config_provenance(record),
                }
            )

        providers = []
        for definition in provider_definitions():
            runtime = runtimes.get(definition.id)
            providers.append(
                {
                    "id": definition.id,
                    "name": definition.name,
                    "kind": definition.kind,
                    "secret_mode": definition.secret_mode,
                    "supported_operations": sorted(
                        operation.value for operation in definition.supported_operations
                    ),
                    "supported_config_options": sorted(definition.supported_option_keys),
                    "server_configured": bool(
                        runtime is not None and getattr(runtime, "configured", False)
                    ),
                }
            )

        return {
            "capabilities": capabilities,
            "providers": providers,
            "legacy_runtime": {
                "role": "live-global-routing-until-R2-activation",
                "selection_present": self.repository.get_ai_selection() is not None,
            },
            "policy": {
                "scope": "product-wide",
                "learner_runtime_uses_capability_config": False,
                "automatic_paid_failover": False,
                "secrets": "server-managed",
            },
        }

    def operations(self, *, limit: int = 100) -> dict[str, Any]:
        """Return read-only, sanitized recent events and per-capability totals."""

        loader = getattr(self.repository, "list_ai_operation_events", None)
        raw_events = loader(limit) if callable(loader) else []
        events = []
        for raw in raw_events if isinstance(raw_events, list) else []:
            event = sanitize_telemetry(raw)
            if event is None:
                continue
            created_at = raw.get("created_at") if isinstance(raw, dict) else None
            if isinstance(created_at, str) and created_at:
                event["created_at"] = created_at
            events.append(event)
        aggregates: dict[str, dict[str, Any]] = {}
        for event in events:
            key = event["capability"]
            row = aggregates.setdefault(key, {
                "capability": key, "total": 0, "success": 0, "failure": 0,
                "avg_latency_ms": None, "usage_known": 0, "usage_unknown": 0,
                "usage_partial": 0,
                "_token_totals": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "_token_seen": set(),
                "_rate_limit_events": [],
                "_cost_events": [],
                "_trend_events": [],
                "_health_events": [],
            })
            row["_health_events"].append(event)
            row["_rate_limit_events"].append(event.get("rate_limit") or {})
            row["_cost_events"].append(event.get("cost") if isinstance(event.get("cost"), dict) else {"state": "unknown"})
            row["_trend_events"].append(event)
            row["total"] += 1
            if event["outcome"] == "success":
                row["success"] += 1
            else:
                row["failure"] += 1
            latency = event.get("latency_ms")
            if isinstance(latency, int):
                known = row.setdefault("_latencies", [])
                known.append(latency)
            usage = event.get("usage") or {}
            token_keys = ("prompt_tokens", "completion_tokens", "total_tokens")
            known_tokens = [name for name in token_keys if isinstance(usage.get(name), int)]
            for name in known_tokens:
                row["_token_totals"][name] += usage[name]
                row["_token_seen"].add(name)
            if len(known_tokens) == len(token_keys):
                row["usage_known"] += 1
            elif known_tokens:
                row["usage_partial"] += 1
            else:
                row["usage_unknown"] += 1
        for row in aggregates.values():
            latencies = row.pop("_latencies", [])
            row["avg_latency_ms"] = round(sum(latencies) / len(latencies)) if latencies else None
            health = _operation_health(row.pop("_health_events", []))
            row.update(health)
            token_totals = row.pop("_token_totals", {})
            token_seen = row.pop("_token_seen", set())
            row["token_totals"] = {
                name: token_totals[name] if name in token_seen else None
                for name in ("prompt_tokens", "completion_tokens", "total_tokens")
            }
            rate_limit_events = row.pop("_rate_limit_events", [])
            rate_limit_keys = ("requests_limit", "requests_remaining", "tokens_limit", "tokens_remaining")
            reported = [
                value for value in rate_limit_events
                if any(isinstance(value.get(name), int) for name in rate_limit_keys)
            ]
            latest_rate_limit = reported[0] if reported else {name: None for name in rate_limit_keys}
            exhausted = any(
                latest_rate_limit.get(name) == 0
                for name in ("requests_remaining", "tokens_remaining")
            )
            row["rate_limit"] = latest_rate_limit
            row["rate_limit_reported_count"] = len(reported)
            row["rate_limit_unknown_count"] = row["total"] - len(reported)
            row["quota_state"] = (
                "reported_exhausted" if exhausted else "reported" if reported else "unavailable"
            )
            cost_events = row.pop("_cost_events", [])
            cost_totals: dict[tuple[str, str], dict[str, Any]] = {}
            cost_state_counts = {state: 0 for state in ("estimated", "unpriced", "partial", "unknown")}
            for cost in cost_events:
                state = cost.get("state")
                if state in cost_state_counts:
                    cost_state_counts[state] += 1
                amount = cost.get("amount")
                currency = cost.get("currency")
                provenance = cost.get("provenance") or {}
                if state != "estimated" or not isinstance(amount, (int, float)) or not currency:
                    continue
                version = str(provenance.get("catalog_version") or "unknown")
                cost_key = (currency, version)
                item = cost_totals.setdefault(cost_key, {"currency": currency, "amount": 0.0, "evidence_count": 0, "catalog_version": version})
                item["amount"] = round(item["amount"] + float(amount), 8)
                item["evidence_count"] += 1
            row["cost_totals"] = list(cost_totals.values())
            row["cost_state_counts"] = cost_state_counts
            row["trend"] = _operation_trend(row.pop("_trend_events", []))
        return {
            "available": callable(loader),
            "has_data": bool(events),
            "sample_limit": max(1, min(int(limit), 500)),
            "sample_truncated": bool(isinstance(raw_events, list) and len(raw_events) >= max(1, min(int(limit), 500))),
            "recent": events,
            "by_capability": list(aggregates.values()),
            "usage_note": "Provider usage and token cost are explicit; unsupported models remain unpriced.",
            "trend_window_days": _TREND_WINDOW_DAYS,
        }

    def set_config(
        self,
        capability_key: str,
        config: CapabilityConfig,
        *,
        updated_by: str = "",
    ) -> dict[str, Any]:
        definition, _provider = validate_capability_config(capability_key, config)
        self.repository.set_capability_config(
            definition.key,
            config,
            updated_by=updated_by,
        )
        return {
            "capability": definition.key,
            "config": _sanitized_config(config),
        }

    def explicit_config(self, capability_key: str) -> CapabilityConfig:
        definition = require_capability(capability_key)
        if not definition.implemented or not definition.provider_backed or not definition.configurable:
            raise AICapabilityUnsupported(
                f"AI capability {definition.key!r} is not available for provider live testing."
            )
        row = self.repository.get_capability_config(definition.key)
        if row is None:
            raise AICapabilityNotConfigured(
                f"AI capability {definition.key!r} has no explicit configuration."
            )
        return row.config

    def live_test(self, capability_key: str, *, standby: bool = False) -> dict[str, Any]:
        started = perf_counter()
        provider: str | None = None
        model: str | None = None
        telemetry_capability = safe_capability_display(capability_key)
        try:
            definition = require_capability(capability_key)
            telemetry_capability = definition.key
            row = self.repository.get_capability_config(definition.key)
            if row is not None:
                provider = row.config.backup_provider if standby else row.config.provider
                model = row.config.backup_model if standby else row.config.model
            if standby and (provider is None or model is None):
                raise AICapabilityConfigInvalid("Capability has no configured standby provider/model.")
            result = self._live_test(capability_key, standby=standby)
            reported_usage = result.pop("_telemetry_usage", None)
            reported_rate_limit = result.pop("_telemetry_rate_limit", None)
            model_display, model_redacted = safe_model_display(result.get("model"))
            result["model"] = model_display
            result["model_redacted"] = model_redacted
            result["telemetry"] = {
                "capability": definition.key,
                "origin": "operator_test",
                "provider": result.get("provider"),
                "model": model_display or None,
                "model_redacted": model_redacted,
                "outcome": "success",
                "error_class": None,
                "latency_ms": normalized_latency((perf_counter() - started) * 1000),
                "usage": normalized_usage(reported_usage),
                "rate_limit": normalized_rate_limit(reported_rate_limit),
                "cost": estimate_token_cost(result.get("provider"), model_display, normalized_usage(reported_usage)),
                "quota_available": "unknown",
            }
            self._record_operation(result["telemetry"])
            return result
        except (AICapabilityConfigInvalid, AICapabilityDisabled,
                AICapabilityNotConfigured, AICapabilityUnsupported,
                AIProviderNotConfigured, AIModelCatalogEmpty,
                AIModelUnavailable, AIProviderResponseInvalid,
                AIProviderError) as exc:
            model_display, model_redacted = safe_model_display(model)
            exc.telemetry = {
                "capability": telemetry_capability,
                "origin": "operator_test",
                "provider": provider,
                "model": model_display or None,
                "model_redacted": model_redacted,
                "outcome": "failure",
                "error_class": telemetry_error_class(exc),
                "latency_ms": normalized_latency((perf_counter() - started) * 1000),
                "usage": normalized_usage(None),
                "rate_limit": normalized_rate_limit(getattr(exc, "rate_limit", None)),
                "cost": estimate_token_cost(provider, model_display, None),
                "quota_available": "unknown",
                **_failure_fields(exc),
            }
            self._record_operation(exc.telemetry)
            raise

    def _live_test(self, capability_key: str, *, standby: bool = False) -> dict[str, Any]:
        """Run one small request against an explicitly configured capability."""

        definition = require_capability(capability_key)
        config = self.explicit_config(definition.key)
        if not config.enabled:
            raise AICapabilityDisabled(f"AI capability {definition.key!r} is disabled.")
        validate_capability_config(definition.key, config, enforce_cap=False)

        provider_id = config.backup_provider if standby else config.provider
        model_id = config.backup_model if standby else config.model
        if provider_id is None or model_id is None:
            raise AICapabilityConfigInvalid("Capability has no configured standby provider/model.")
        runtime = self.provider_factory().get(provider_id)
        if runtime is None or not getattr(runtime, "configured", False):
            raise AIProviderNotConfigured("AI provider is not configured on the server.")

        models = runtime.discover_models_live()
        if not models:
            raise AIModelCatalogEmpty("AI provider returned an empty model catalog.")
        if model_id not in models:
            raise AIModelUnavailable("Configured AI model is not available.")

        schema = {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "capability": {"type": "string"},
            },
            "required": ["ok", "capability"],
            "additionalProperties": False,
        }
        started = perf_counter()
        generate_once = getattr(runtime, "generate_json_once", None)
        if generate_once is None:
            generate_once = runtime.generate_json
        result = generate_once(
            messages=[
                {
                    "role": "system",
                    "content": "Return only the requested tiny capability health JSON.",
                },
                {
                    "role": "user",
                    "content": f"Return ok=true and capability={definition.key!r}.",
                },
            ],
            schema=schema,
            model=model_id,
            max_output_tokens=40,
            temperature=config.temperature if config.temperature is not None else 0.0,
        )
        latency_ms = max(0, round((perf_counter() - started) * 1000))
        if (
            not isinstance(result.data, dict)
            or result.data.get("ok") is not True
            or result.data.get("capability") != definition.key
        ):
            raise AIProviderResponseInvalid("AI provider response failed capability validation.")

        model, redacted = safe_model_display(model_id)
        return {
            "ok": True,
            "capability": definition.key,
            "provider": provider_id,
            "model": model,
            "model_redacted": redacted,
            "latency_ms": latency_ms,
            "error_class": None,
            "_telemetry_usage": normalized_usage(result.runtime),
            "_telemetry_rate_limit": normalized_rate_limit(result.runtime.get("rate_limit")),
        }

    def diagnostic_context(self, capability_key: str, *, standby: bool = False) -> dict[str, Any]:
        """Load only safe identifiers for a failed live-test response."""

        definition = require_capability(capability_key)
        row = self.repository.get_capability_config(definition.key)
        if row is None:
            return {"capability": definition.key, "provider": None, "model": None, "model_redacted": False}
        provider = row.config.backup_provider if standby else row.config.provider
        model, redacted = safe_model_display(row.config.backup_model if standby else row.config.model)
        return {
            "capability": definition.key,
            "provider": provider,
            "model": model,
            "model_redacted": redacted,
        }
