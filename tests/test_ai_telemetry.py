from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

import writing_coach.ai.platform as platform
from writing_coach.ai.base import AICapabilityUnsupported, AIProviderError, AIResult, sanitize_telemetry
from writing_coach.ai.config import CapabilityConfig
from writing_coach.ai.control_plane import AIControlPlane
from writing_coach.ai.pricing import PRICING_CATALOG_VERSION, estimate_token_cost
from writing_coach.persistence.platform_repository import CapabilityConfigRecord


@dataclass
class Repository:
    config: CapabilityConfig | None

    def __post_init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def get_capability_config(self, key: str) -> CapabilityConfigRecord | None:
        return CapabilityConfigRecord(key, self.config) if self.config is not None else None

    def record_ai_operation(self, telemetry: dict[str, Any]) -> None:
        self.events.append(dict(telemetry))

    def list_ai_operation_events(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.events[:limit]


class Provider:
    id = "openai"
    name = "OpenAI API"
    configured = True

    def __init__(self, *, runtime: dict[str, Any] | None = None, error: Exception | None = None):
        self.runtime = runtime or {}
        self.error = error

    def discover_models_live(self) -> list[str]:
        return ["telemetry-model"]

    def generate_json_once(self, **kwargs: Any) -> AIResult:
        if self.error is not None:
            raise self.error
        return AIResult(
            data={"ok": True, "capability": "writing_evaluator"},
            provider=self.id,
            model=kwargs["model"],
            runtime=dict(self.runtime),
        )


def config(**overrides: Any) -> CapabilityConfig:
    values: dict[str, Any] = {
        "enabled": True,
        "provider": "openai",
        "model": "telemetry-model",
        "temperature": 0.1,
        "fallback_policy": "none",
    }
    values.update(overrides)
    return CapabilityConfig(**values)


def invoke(monkeypatch: pytest.MonkeyPatch, provider: Provider, capability_config: CapabilityConfig) -> AIResult:
    monkeypatch.setenv("AI_RUNTIME_MODE", "capability")
    monkeypatch.setattr(platform, "_platform_repository", Repository(capability_config))
    monkeypatch.setattr(platform, "providers", lambda: {"openai": provider})
    return platform.generate_structured(
        messages=[],
        schema={"type": "object"},
        max_output_tokens=20,
        capability_key="writing_evaluator",
    )


def test_success_telemetry_keeps_capability_provider_model_and_reported_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Repository(config())
    monkeypatch.setenv("AI_RUNTIME_MODE", "capability")
    monkeypatch.setattr(platform, "_platform_repository", repository)
    monkeypatch.setattr(platform, "providers", lambda: {"openai": Provider(runtime={"prompt_tokens": 7, "completion_tokens": 5, "total_tokens": 12})})
    result = platform.generate_structured(messages=[], schema={"type": "object"}, max_output_tokens=20, capability_key="writing_evaluator")

    assert result.runtime["telemetry"] == {
        "capability": "writing_evaluator",
        "origin": "learner",
        "provider": "openai",
        "model": "telemetry-model",
        "model_redacted": False,
        "outcome": "success",
        "error_class": None,
        "latency_ms": result.runtime["telemetry"]["latency_ms"],
        "usage": {"prompt_tokens": 7, "completion_tokens": 5, "total_tokens": 12},
        "rate_limit": {"requests_limit": None, "requests_remaining": None, "tokens_limit": None, "tokens_remaining": None},
        "cost": {"state": "unpriced", "currency": None, "amount": None, "provenance": {"catalog_version": PRICING_CATALOG_VERSION, "provider": "openai", "model": "telemetry-model", "input_per_million": None, "output_per_million": None, "reason": "model_not_cataloged"}},
        "quota_available": "unknown",
        "billable_attempt": True,  # PR-MON-6 §8: a provider answered
    }
    assert isinstance(result.runtime["telemetry"]["latency_ms"], int)
    assert result.runtime["telemetry"]["latency_ms"] >= 0
    assert result.runtime["telemetry"]["cost"]["state"] == "unpriced"
    assert repository.events[0] == result.runtime["telemetry"]


def test_absent_or_malformed_usage_remains_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    result = invoke(
        monkeypatch,
        Provider(runtime={"prompt_tokens": "7", "completion_tokens": -1, "total_tokens": None}),
        config(),
    )

    assert result.runtime["telemetry"]["usage"] == {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    }
    assert result.runtime["telemetry"]["quota_available"] == "unknown"


def test_backup_configuration_does_not_change_primary_runtime_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = Provider()
    result = invoke(
        monkeypatch,
        primary,
        config(backup_provider="deepseek", backup_model="deepseek-chat"),
    )
    assert result.provider == "openai"
    assert result.model == "telemetry-model"


def test_rate_limit_telemetry_keeps_only_safe_numeric_evidence() -> None:
    safe = sanitize_telemetry({
        "capability": "writing_evaluator",
        "outcome": "success",
        "rate_limit": {
            "requests_limit": 100,
            "requests_remaining": 0,
            "tokens_limit": "2000",
            "tokens_remaining": -1,
            "reset": "secret-token",
        },
    })

    assert safe["rate_limit"] == {
        "requests_limit": 100,
        "requests_remaining": 0,
        "tokens_limit": None,
        "tokens_remaining": None,
    }


def test_failure_telemetry_is_typed_and_redacts_suspicious_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = Provider(error=AIProviderError("provider secret=do-not-leak"))
    with pytest.raises(AIProviderError) as caught:
        invoke(monkeypatch, provider, config(model="https://provider.invalid/model"))

    assert caught.value.telemetry == {
        "capability": "writing_evaluator",
        "origin": "learner",
        "provider": "openai",
        "model": "[redacted]",
        "model_redacted": True,
        "outcome": "failure",
        "error_class": "provider_error",
        "latency_ms": caught.value.telemetry["latency_ms"],
        "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
        "rate_limit": {"requests_limit": None, "requests_remaining": None, "tokens_limit": None, "tokens_remaining": None},
        "cost": {"state": "unpriced", "currency": None, "amount": None, "provenance": {"catalog_version": PRICING_CATALOG_VERSION, "provider": "openai", "model": "[redacted]", "input_per_million": None, "output_per_million": None, "reason": "model_not_cataloged"}},
        "quota_available": "unknown",
        "billable_attempt": False,  # PR-MON-6 §8: the chain's rungs are recorded each; the summary is not a call
    }
    assert "do-not-leak" not in repr(caught.value.telemetry)


def test_capability_failure_has_same_shape_without_provider_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = Provider()
    monkeypatch.setenv("AI_RUNTIME_MODE", "capability")
    repository = Repository(config(enabled=False))
    monkeypatch.setattr(platform, "_platform_repository", repository)
    monkeypatch.setattr(platform, "providers", lambda: {"openai": provider})

    with pytest.raises(platform.AICapabilityDisabled) as caught:
        platform.generate_structured(
            messages=[], schema={"type": "object"}, max_output_tokens=20,
            capability_key="writing_evaluator",
        )

    assert caught.value.telemetry["error_class"] == "capability_disabled"
    assert caught.value.telemetry["outcome"] == "failure"
    assert caught.value.telemetry["capability"] == "writing_evaluator"
    assert provider.error is None
    assert repository.events[0]["error_class"] == "capability_disabled"


def test_control_plane_success_uses_the_same_telemetry_contract() -> None:
    provider = Provider(
        runtime={"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7}
    )
    repository = Repository(config())
    plane = AIControlPlane(repository, provider_factory=lambda: {"openai": provider})

    result = plane.live_test("writing_evaluator")

    assert result["telemetry"] == {
        "capability": "writing_evaluator",
        "origin": "operator_test",
        "provider": "openai",
        "model": "telemetry-model",
        "model_redacted": False,
        "outcome": "success",
        "error_class": None,
        "latency_ms": result["telemetry"]["latency_ms"],
        "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
        "rate_limit": {"requests_limit": None, "requests_remaining": None, "tokens_limit": None, "tokens_remaining": None},
        "cost": {"state": "unpriced", "currency": None, "amount": None, "provenance": {"catalog_version": PRICING_CATALOG_VERSION, "provider": "openai", "model": "telemetry-model", "input_per_million": None, "output_per_million": None, "reason": "model_not_cataloged"}},
        "quota_available": "unknown",
    }
    assert "_telemetry_rate_limit" not in result
    assert repository.events[0] == result["telemetry"]


def test_control_plane_provider_failure_carries_typed_telemetry() -> None:
    provider = Provider(error=AIProviderError("provider failure"))
    repository = Repository(config())
    plane = AIControlPlane(repository, provider_factory=lambda: {"openai": provider})

    with pytest.raises(AIProviderError) as caught:
        plane.live_test("writing_evaluator")

    assert caught.value.telemetry["capability"] == "writing_evaluator"
    assert caught.value.telemetry["outcome"] == "failure"
    assert caught.value.telemetry["error_class"] == "provider_error"
    assert caught.value.telemetry["quota_available"] == "unknown"
    assert repository.events[0] == caught.value.telemetry


def test_invalid_capability_key_is_redacted_in_failure_telemetry() -> None:
    plane = AIControlPlane(Repository(config()), provider_factory=lambda: {})

    with pytest.raises(AICapabilityUnsupported) as caught:
        plane.live_test("unknown?token=do-not-leak")

    assert caught.value.telemetry["capability"] == "[invalid]"
    assert "do-not-leak" not in repr(caught.value.telemetry)


def test_admin_operations_aggregate_sanitized_events_and_show_no_cost() -> None:
    repository = Repository(config())
    repository.events = [
        {
            "capability": "writing_evaluator",
            "provider": "openai",
            "model": "telemetry-model",
            "model_redacted": False,
            "outcome": "success",
            "error_class": None,
            "latency_ms": 20,
        "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
        "rate_limit": {"requests_limit": None, "requests_remaining": None, "tokens_limit": None, "tokens_remaining": None},
        "quota_available": "unknown",
            "prompt": "must not persist",
            "cost": 99,
            "created_at": "2026-08-28T10:00:00+00:00",
        },
        {
            "capability": "writing_evaluator",
            "provider": "openai",
            "model": "telemetry-model",
            "model_redacted": False,
            "outcome": "failure",
            "error_class": "provider_error",
            "latency_ms": None,
            "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
            "quota_available": "unknown",
        },
    ]

    result = AIControlPlane(repository).operations()

    assert result["has_data"] is True
    assert result["by_capability"] == [{
        "capability": "writing_evaluator",
        "total": 2,
        "success": 1,
        "failure": 1,
        "avg_latency_ms": 20,
        "usage_known": 1,
        "usage_partial": 0,
        "usage_unknown": 1,
        "token_totals": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
        "rate_limit": {"requests_limit": None, "requests_remaining": None, "tokens_limit": None, "tokens_remaining": None},
        "rate_limit_reported_count": 0,
        "rate_limit_unknown_count": 2,
        "quota_state": "unavailable",
        "trend": [
            {"bucket": "unknown", "request_count": 1, "failure_count": 1, "avg_latency_ms": None, "usage_known": 0, "usage_partial": 0, "usage_unknown": 1, "token_totals": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}, "rate_limit_reported_count": 0, "cost_totals": [], "cost_state_counts": {"estimated": 0, "unpriced": 0, "partial": 0, "unknown": 1}},
            {"bucket": "2026-08-28", "request_count": 1, "failure_count": 0, "avg_latency_ms": 20, "usage_known": 1, "usage_partial": 0, "usage_unknown": 0, "token_totals": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7}, "rate_limit_reported_count": 0, "cost_totals": [], "cost_state_counts": {"estimated": 0, "unpriced": 0, "partial": 0, "unknown": 1}},
        ],
        "health_state": "provider_failure",
        "evidence_count": 2,
        "failure_count": 1,
        "provider_failure_count": 1,
        "failure_rate_percent": 50,
        "cost_totals": [],
        "cost_state_counts": {"estimated": 0, "unpriced": 0, "partial": 0, "unknown": 2},
    }]
    assert "prompt" not in result["recent"][0]
    assert "cost" not in result["recent"][0]
    assert result["usage_note"]


def test_admin_operations_aggregate_provider_tokens_and_partial_usage() -> None:
    repository = Repository(config())
    repository.events = [
        {
            "capability": "writing_evaluator",
            "outcome": "success",
            "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
        },
        {
            "capability": "writing_evaluator",
            "outcome": "success",
            "usage": {"prompt_tokens": 2, "completion_tokens": None, "total_tokens": 2},
        },
        {
            "capability": "writing_evaluator",
            "outcome": "failure",
            "usage": {"prompt_tokens": "9", "completion_tokens": -1, "total_tokens": None},
            "cost": 999,
        },
    ]

    row = AIControlPlane(repository).operations()["by_capability"][0]

    assert row["token_totals"] == {
        "prompt_tokens": 6,
        "completion_tokens": 3,
        "total_tokens": 9,
    }
    assert row["usage_known"] == 1
    assert row["usage_partial"] == 1
    assert row["usage_unknown"] == 1
    assert "cost" not in AIControlPlane(repository).operations()["recent"][2]


def test_cost_catalog_is_exact_and_cost_states_remain_distinct() -> None:
    estimated = estimate_token_cost("openai", "gpt-4o-mini", {"prompt_tokens": 1000, "completion_tokens": 500})
    assert estimated["state"] == "estimated"
    assert estimated["currency"] == "USD"
    assert estimated["amount"] == 0.00045
    assert estimated["provenance"]["catalog_version"] == PRICING_CATALOG_VERSION
    assert estimate_token_cost("openai", "gpt-4o-mini", {"total_tokens": 1500})["state"] == "unknown"
    assert estimate_token_cost("openai", "gpt-4o-mini", {"prompt_tokens": 1500})["state"] == "partial"
    assert estimate_token_cost("openai", "unknown-model", {"prompt_tokens": 1000, "completion_tokens": 500})["state"] == "unpriced"
    oversized = estimate_token_cost("openai", "gpt-4o-mini", {"prompt_tokens": 10**20, "completion_tokens": 1})
    assert oversized["state"] == "unknown"
    assert oversized["provenance"]["reason"] == "usage_out_of_range"


def test_admin_operations_aggregates_cost_by_catalog_and_trend() -> None:
    repository = Repository(config())
    repository.events = [
        {"capability": "writing_evaluator", "provider": "openai", "model": "gpt-4o-mini", "outcome": "success", "created_at": "2026-08-28T10:00:00+00:00", "usage": {"prompt_tokens": 1000, "completion_tokens": 500}, "cost": estimate_token_cost("openai", "gpt-4o-mini", {"prompt_tokens": 1000, "completion_tokens": 500})},
        {"capability": "writing_evaluator", "provider": "openai", "model": "gpt-4o-mini", "outcome": "success", "created_at": "2026-08-28T11:00:00+00:00", "usage": {"total_tokens": 10}, "cost": estimate_token_cost("openai", "gpt-4o-mini", {"total_tokens": 10})},
        {"capability": "writing_evaluator", "provider": "openai", "model": "unknown-model", "outcome": "success", "created_at": "2026-08-28T12:00:00+00:00", "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "cost": estimate_token_cost("openai", "unknown-model", {"prompt_tokens": 1, "completion_tokens": 1})},
    ]
    row = AIControlPlane(repository).operations()["by_capability"][0]
    assert row["cost_totals"] == [{"currency": "USD", "amount": 0.00045, "evidence_count": 1, "catalog_version": PRICING_CATALOG_VERSION}]
    assert row["cost_state_counts"] == {"estimated": 1, "unpriced": 1, "partial": 0, "unknown": 1}
    bucket = row["trend"][0]
    assert bucket["cost_totals"] == row["cost_totals"]


def test_admin_operations_reports_latest_rate_limit_state_and_evidence_counts() -> None:
    repository = Repository(config())
    repository.events = [
        {
            "capability": "writing_evaluator",
            "outcome": "success",
            "rate_limit": {
                "requests_limit": 100,
                "requests_remaining": 0,
                "tokens_limit": 10000,
                "tokens_remaining": 25,
            },
        },
        {
            "capability": "writing_evaluator",
            "outcome": "success",
            "rate_limit": {},
        },
    ]

    row = AIControlPlane(repository).operations()["by_capability"][0]

    assert row["rate_limit"] == {
        "requests_limit": 100,
        "requests_remaining": 0,
        "tokens_limit": 10000,
        "tokens_remaining": 25,
    }
    assert row["rate_limit_reported_count"] == 1
    assert row["rate_limit_unknown_count"] == 1
    assert row["quota_state"] == "reported_exhausted"


def test_admin_operations_trend_buckets_timestamps_and_keeps_unknowns_explicit() -> None:
    repository = Repository(config())
    repository.events = [
        {"capability": "writing_evaluator", "outcome": "success", "created_at": "2026-08-28T10:00:00+00:00", "latency_ms": 10, "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}},
        {"capability": "writing_evaluator", "outcome": "failure", "created_at": "2026-08-27T10:00:00+00:00", "latency_ms": 30, "usage": {"prompt_tokens": 2, "completion_tokens": None, "total_tokens": 2}},
        {"capability": "writing_evaluator", "outcome": "success", "created_at": "not-a-timestamp", "usage": {}},
        {"capability": "writing_evaluator", "outcome": "success", "usage": {}},
    ]

    result = AIControlPlane(repository).operations()
    row = result["by_capability"][0]
    trend = {bucket["bucket"]: bucket for bucket in row["trend"]}

    assert result["trend_window_days"] == 7
    assert trend["2026-08-28"]["request_count"] == 1
    assert trend["2026-08-27"]["failure_count"] == 1
    assert trend["2026-08-27"]["usage_partial"] == 1
    assert trend["unknown"]["request_count"] == 2
    assert trend["unknown"]["usage_unknown"] == 2


def test_admin_operations_treats_timezone_less_boundary_timestamp_as_unknown() -> None:
    repository = Repository(config())
    repository.events = [
        {"capability": "writing_evaluator", "outcome": "success", "created_at": "2026-08-28T23:59:59", "usage": {}},
        {"capability": "writing_evaluator", "outcome": "success", "created_at": "2026-08-29T00:00:01+00:00", "usage": {}},
    ]

    trend = {bucket["bucket"]: bucket for bucket in AIControlPlane(repository).operations()["by_capability"][0]["trend"]}

    assert trend["unknown"]["request_count"] == 1
    assert trend["2026-08-29"]["request_count"] == 1


@pytest.mark.parametrize(
    ("events", "health_state"),
    [
        ([{"outcome": "success", "latency_ms": 1999}], "healthy"),
        ([{"outcome": "success", "latency_ms": 2000}], "degraded"),
        ([{"outcome": "success", "latency_ms": 10}, {"outcome": "failure", "error_class": "operation_failed", "latency_ms": 11}], "degraded"),
        ([{"outcome": "failure", "error_class": "provider_response_invalid", "latency_ms": 10}], "provider_failure"),
    ],
)
def test_operations_health_states_use_explicit_evidence_thresholds(events, health_state) -> None:
    repository = Repository(config())
    repository.events = [
        {
            "capability": "writing_evaluator",
            "provider": "openai",
            "model": "telemetry-model",
            "outcome": event["outcome"],
            "error_class": event.get("error_class"),
            "latency_ms": event.get("latency_ms"),
            "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
        }
        for event in events
    ]

    row = AIControlPlane(repository).operations()["by_capability"][0]

    assert row["health_state"] == health_state
    assert row["evidence_count"] == len(events)
    assert row["failure_count"] == sum(event["outcome"] == "failure" for event in events)


def test_operations_without_events_are_explicitly_empty() -> None:
    result = AIControlPlane(Repository(config())).operations()

    assert result["has_data"] is False
    assert result["recent"] == []
    assert result["by_capability"] == []
