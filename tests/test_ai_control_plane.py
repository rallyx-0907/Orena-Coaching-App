from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import HTTPException, Request

import writing_coach.ai.platform as platform_module
import requests

from writing_coach.ai.base import (
    AICapabilityConfigInvalid,
    AIProviderError,
    AIProviderNotConfigured,
    AIProviderResponseInvalid,
    AIProviderUnavailable,
    AIResult,
)
from writing_coach.ai.capabilities import all_capabilities
from writing_coach.ai.config import CapabilityConfig
from writing_coach.ai.control_plane import AIControlPlane
from writing_coach.ai.pricing import PRICING_CATALOG_VERSION, estimate_token_cost
from writing_coach.ai.providers import OllamaProvider, OpenAICompatibleProvider
from writing_coach.persistence.platform_repository import (
    AISelectionRecord,
    CapabilityConfigRecord,
)


def capability_config(**overrides: Any) -> CapabilityConfig:
    values = {
        "enabled": True,
        "provider": "openai",
        "model": "model-1",
        "temperature": 0.0,
        "fallback_policy": "none",
    }
    values.update(overrides)
    return CapabilityConfig(**values)


class FakeRepository:
    def __init__(self) -> None:
        self.capabilities: dict[str, CapabilityConfig] = {}
        self.legacy: AISelectionRecord | None = None
        self.capability_writes: list[tuple[str, CapabilityConfig, str]] = []
        self.legacy_writes: list[tuple[str, str, str]] = []
        self.capability_metadata: dict[str, tuple[str, str]] = {}
        self.ai_events: list[dict[str, Any]] = []

    def initialize(self) -> None:
        pass

    def get_ai_selection(self) -> AISelectionRecord | None:
        return self.legacy

    def set_ai_selection(self, *, provider: str, model: str, updated_by: str = "") -> None:
        self.legacy = AISelectionRecord(provider, model, updated_by=updated_by)
        self.legacy_writes.append((provider, model, updated_by))

    def get_capability_config(self, capability_key: str) -> CapabilityConfigRecord | None:
        config = self.capabilities.get(capability_key.strip().casefold())
        if config is None:
            return None
        key = capability_key.strip().casefold()
        updated_at, updated_by = self.capability_metadata.get(key, ("", ""))
        return CapabilityConfigRecord(key, config, updated_at=updated_at, updated_by=updated_by)

    def list_capability_configs(self) -> list[CapabilityConfigRecord]:
        return [
            CapabilityConfigRecord(
                key,
                config,
                updated_at=self.capability_metadata.get(key, ("", ""))[0],
                updated_by=self.capability_metadata.get(key, ("", ""))[1],
            )
            for key, config in sorted(self.capabilities.items())
        ]

    def set_capability_config(
        self,
        capability_key: str,
        config: CapabilityConfig,
        *,
        updated_by: str = "",
    ) -> None:
        self.capabilities[capability_key] = config
        self.capability_writes.append((capability_key, config, updated_by))

    def record_ai_operation(self, telemetry: dict[str, Any]) -> None:
        self.ai_events.append(dict(telemetry))

    def list_ai_operation_events(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.ai_events[:limit]


@dataclass
class FakeProvider:
    id: str = "openai"
    name: str = "OpenAI API"
    kind: str = "cloud"
    secret_mode: str = "server-managed"
    configured: bool = True
    models: tuple[str, ...] = ("model-1",)
    discovery_error: Exception | None = None
    generation_error: Exception | None = None
    response: dict[str, Any] | None = None
    credential: str = "server-secret"
    base_url: str = "https://db-user:db-password@example.invalid"

    @property
    def default_model(self) -> str:
        return self.models[0] if self.models else ""

    def __post_init__(self) -> None:
        self.discovery_calls = 0
        self.generation_calls: list[dict[str, Any]] = []

    def discover_models_live(self) -> list[str]:
        self.discovery_calls += 1
        if self.discovery_error:
            raise self.discovery_error
        return list(self.models)

    def generate_json_once(self, **kwargs: Any) -> AIResult:
        self.generation_calls.append(kwargs)
        if self.generation_error:
            raise self.generation_error
        data = self.response or {
            "ok": True,
            "capability": "writing_evaluator",
        }
        return AIResult(data=data, provider=self.id, model=kwargs["model"], runtime={})

    def generate_json(self, **kwargs: Any) -> AIResult:
        self.generation_calls.append(kwargs)
        if self.generation_error:
            raise self.generation_error
        data = self.response or {"ok": True, "message": "Connection succeeded."}
        return AIResult(data=data, provider=self.id, model=kwargs["model"], runtime={})

    def list_models(self) -> list[str]:
        return list(self.models)


def configure_platform(
    monkeypatch: pytest.MonkeyPatch,
    repository: FakeRepository,
    *,
    providers: dict[str, FakeProvider] | None = None,
    admin: bool = True,
) -> Request:
    runtime_providers = providers or {"openai": FakeProvider()}
    monkeypatch.setattr(platform_module, "_platform_repository", repository)
    if admin:
        monkeypatch.setattr(
            platform_module,
            "_admin_guard",
            lambda _request: {"google_sub": "admin-1", "role": "admin"},
        )
    else:
        def forbidden(_request):
            raise HTTPException(403, "Platform administrator access required")

        monkeypatch.setattr(platform_module, "_admin_guard", forbidden)
    monkeypatch.setattr(
        platform_module,
        "AIControlPlane",
        lambda repo: AIControlPlane(repo, provider_factory=lambda: runtime_providers),
    )
    monkeypatch.setattr(platform_module, "providers", lambda: runtime_providers)
    return Request({"type": "http", "method": "GET", "path": "/", "headers": []})


def valid_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "enabled": True,
        "provider": "openai",
        "model": "model-1",
        "temperature": 0.0,
        "fallback_policy": "none",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "endpoint",
    [
        "get",
        "put",
        "test",
        "legacy_put",
        "legacy_test",
    ],
)
def test_canonical_endpoints_require_admin_guard(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    request = configure_platform(monkeypatch, FakeRepository(), admin=False)
    with pytest.raises(HTTPException) as caught:
        if endpoint == "get":
            platform_module.admin_ai_config(request)
        elif endpoint == "put":
            platform_module.admin_ai_capability_config_update(
                "writing_evaluator",
                platform_module.CapabilityConfigIn(**valid_payload()),
                request,
            )
        elif endpoint == "test":
            platform_module.admin_ai_capability_test("writing_evaluator", request)
        elif endpoint == "legacy_put":
            platform_module.admin_ai_config_update(
                platform_module.AIConfigIn(provider="openai", model="model-1"), request
            )
        else:
            platform_module.admin_ai_test(
                platform_module.AIConfigIn(provider="openai", model="model-1"), request
            )
    assert caught.value.status_code == 403


def test_get_is_capability_centric_network_free_and_secret_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    repository.legacy = AISelectionRecord("openai", "https://legacy:super-secret@example.invalid")
    repository.capabilities["writing_evaluator"] = capability_config(
        model="abc?api_key=super-secret",
        backup_provider="deepseek",
        backup_model="https://backup.invalid/model?token=super-secret",
    )
    repository.capability_metadata["writing_evaluator"] = (
        "2026-08-28T14:00:00+07:00",
        "admin-sub-secret-shaped",
    )
    provider = FakeProvider()

    def forbidden(*_args, **_kwargs):
        pytest.fail("GET attempted provider network/model discovery")

    monkeypatch.setattr("requests.get", forbidden)
    monkeypatch.setattr("requests.post", forbidden)
    monkeypatch.setattr(platform_module, "active_selection", forbidden)
    request = configure_platform(
        monkeypatch,
        repository,
        providers={"openai": provider},
    )
    payload = platform_module.admin_ai_config(request)

    states = {item["key"]: item for item in payload["capabilities"]}
    assert set(states) == {item.key for item in all_capabilities()}
    assert states["reading_evaluator"] | {
        "operation": "deterministic",
        "configurable": False,
    } == states["reading_evaluator"]
    assert all(states[key]["implemented"] is False for key in (
        "speech_asr", "pronunciation_evaluator", "speaking_evaluator"
    ))
    assert states["writing_evaluator"]["config"]["model"] == "[redacted]"
    assert states["writing_evaluator"]["config"]["model_redacted"] is True
    assert states["writing_evaluator"]["config"]["backup_model"] == "[redacted]"
    assert states["writing_evaluator"]["config"]["backup_model_redacted"] is True
    assert states["writing_evaluator"]["config_provenance"] == {
        "saved": True,
        "updated_at": "2026-08-28T14:00:00+07:00",
        "updated_by_present": True,
    }


    assert states["reading_evaluator"]["config_provenance"] == {
        "saved": False,
        "updated_at": None,
        "updated_by_present": False,
    }
    assert payload["legacy_runtime"] == {
        "role": "live-global-routing-until-R2-activation",
        "selection_present": True,
    }
    assert payload["learner_runtime"] == {"mode": "legacy"}
    rendered = json.dumps(payload)
    assert "super-secret" not in rendered
    assert "db-password" not in rendered
    assert "server-secret" not in rendered
    assert "admin-sub-secret-shaped" not in rendered
    assert provider.discovery_calls == 0


def test_operations_endpoint_is_read_only_and_aggregates_without_provider_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    repository.ai_events.append({
        "capability": "writing_evaluator",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "outcome": "success",
        "latency_ms": 12,
        "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
        "prompt": "never return",
        "cost": estimate_token_cost("openai", "gpt-4o-mini", {"prompt_tokens": 2, "completion_tokens": 1}),
    })
    request = configure_platform(monkeypatch, repository)
    monkeypatch.setattr(platform_module, "providers", lambda: pytest.fail("operations endpoint probed providers"))

    result = platform_module.admin_ai_operations(request)

    assert result["has_data"] is True
    assert result["by_capability"][0]["capability"] == "writing_evaluator"
    assert result["by_capability"][0]["usage_known"] == 1
    assert result["by_capability"][0]["health_state"] == "healthy"
    assert result["by_capability"][0]["evidence_count"] == 1
    assert result["by_capability"][0]["failure_rate_percent"] == 0
    assert result["by_capability"][0]["cost_totals"] == [{"currency": "USD", "amount": 0.0000009, "evidence_count": 1, "catalog_version": PRICING_CATALOG_VERSION}]
    assert result["by_capability"][0]["token_totals"] == {
        "prompt_tokens": 2,
        "completion_tokens": 1,
        "total_tokens": 3,
    }
    assert "prompt" not in result["recent"][0]
    assert result["recent"][0]["cost"]["provenance"]["catalog_version"] == PRICING_CATALOG_VERSION


def test_operations_endpoint_reports_mixed_rate_limit_evidence_without_probing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    repository.ai_events = [
        {
            "capability": "writing_evaluator",
            "outcome": "success",
            "rate_limit": {
                "requests_limit": 100,
                "requests_remaining": 0,
                "tokens_limit": 2000,
                "tokens_remaining": 10,
            },
        },
        {"capability": "writing_evaluator", "outcome": "failure", "error_class": "provider_error"},
    ]
    request = configure_platform(monkeypatch, repository)
    monkeypatch.setattr(platform_module, "providers", lambda: pytest.fail("operations endpoint probed providers"))

    result = platform_module.admin_ai_operations(request)
    row = result["by_capability"][0]

    assert row["rate_limit_reported_count"] == 1
    assert row["rate_limit_unknown_count"] == 1
    assert row["quota_state"] == "reported_exhausted"
    assert row["rate_limit"]["requests_remaining"] == 0


def test_capability_put_updates_one_row_offline_without_legacy_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    offline = FakeProvider(configured=False, discovery_error=AssertionError("must not discover"))
    request = configure_platform(
        monkeypatch,
        repository,
        providers={"openai": offline},
    )
    response = platform_module.admin_ai_capability_config_update(
        "writing_evaluator",
        platform_module.CapabilityConfigIn(**valid_payload()),
        request,
    )

    assert response["capability"] == "writing_evaluator"
    assert [row[0] for row in repository.capability_writes] == ["writing_evaluator"]
    assert repository.legacy_writes == []
    assert offline.discovery_calls == 0
    assert offline.generation_calls == []


def test_capability_backup_configuration_is_persisted_and_inspected_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    request = configure_platform(monkeypatch, repository)
    response = platform_module.admin_ai_capability_config_update(
        "writing_evaluator",
        platform_module.CapabilityConfigIn(**valid_payload(
            backup_provider="deepseek", backup_model="deepseek-chat"
        )),
        request,
    )
    saved = repository.capabilities["writing_evaluator"]
    assert saved.backup_provider == "deepseek"
    assert saved.backup_model == "deepseek-chat"
    assert response["config"]["backup_provider"] == "deepseek"
    assert response["config"]["backup_model"] == "deepseek-chat"
    inspected = platform_module.admin_ai_config(request)
    config = next(item for item in inspected["capabilities"] if item["key"] == "writing_evaluator")["config"]
    assert config["backup_provider"] == "deepseek"
    assert config["backup_model"] == "deepseek-chat"


@pytest.mark.parametrize(
    "payload",
    [
        valid_payload(backup_provider="deepseek"),
        valid_payload(backup_model="deepseek-chat"),
        valid_payload(backup_provider="unknown", backup_model="model-2"),
    ],
)
def test_capability_backup_configuration_requires_supported_complete_pair(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, Any],
) -> None:
    repository = FakeRepository()
    request = configure_platform(monkeypatch, repository)
    with pytest.raises(HTTPException) as caught:
        platform_module.admin_ai_capability_config_update(
            "writing_evaluator", platform_module.CapabilityConfigIn(**payload), request
        )
    assert caught.value.status_code == 400
    assert repository.capabilities == {}


def test_standby_health_check_is_explicit_and_does_not_touch_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    repository.capabilities["writing_evaluator"] = capability_config(
        backup_provider="deepseek", backup_model="deepseek-chat"
    )
    primary = FakeProvider()
    standby = FakeProvider(id="deepseek", name="DeepSeek API", models=("deepseek-chat",))
    request = configure_platform(monkeypatch, repository, providers={"openai": primary, "deepseek": standby})
    result = platform_module.admin_ai_capability_test("writing_evaluator", request, standby=True)
    assert result["provider"] == "deepseek"
    assert result["model"] == "deepseek-chat"
    assert primary.discovery_calls == 0
    assert primary.generation_calls == []
    assert standby.discovery_calls == 1
    assert standby.generation_calls[0]["model"] == "deepseek-chat"


@pytest.mark.parametrize(
    ("capability", "payload"),
    [
        ("reading_evaluator", valid_payload()),
        ("speech_asr", valid_payload()),
        ("pronunciation_evaluator", valid_payload()),
        ("speaking_evaluator", valid_payload()),
        ("writing_evaluator", valid_payload(fallback_policy="deterministic_fallback")),
        ("writing_evaluator", valid_payload(timeout_seconds=30)),
        ("writing_evaluator", valid_payload(provider="unknown")),
    ],
)
def test_capability_put_rejects_nonconfigurable_or_invalid_static_contracts(
    monkeypatch: pytest.MonkeyPatch,
    capability: str,
    payload: dict[str, Any],
) -> None:
    repository = FakeRepository()
    request = configure_platform(monkeypatch, repository)
    with pytest.raises(HTTPException) as caught:
        platform_module.admin_ai_capability_config_update(
            capability,
            platform_module.CapabilityConfigIn(**payload),
            request,
        )
    assert caught.value.status_code == 400
    assert repository.capability_writes == []
    assert repository.legacy_writes == []


@pytest.mark.parametrize(
    ("config", "provider", "error_class"),
    [
        (capability_config(enabled=False), FakeProvider(), "capability_disabled"),
        (capability_config(), FakeProvider(configured=False), "provider_not_configured"),
        (
            capability_config(),
            FakeProvider(discovery_error=AIProviderUnavailable("raw network")),
            "provider_unavailable",
        ),
        (capability_config(), FakeProvider(models=()), "model_catalog_empty"),
        (capability_config(), FakeProvider(models=("other-model",)), "model_unavailable"),
    ],
)
def test_live_test_failure_taxonomy_is_distinct_and_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    config: CapabilityConfig,
    provider: FakeProvider,
    error_class: str,
) -> None:
    repository = FakeRepository()
    repository.capabilities["writing_evaluator"] = config
    request = configure_platform(
        monkeypatch, repository, providers={"openai": provider}
    )
    with pytest.raises(HTTPException) as caught:
        platform_module.admin_ai_capability_test("writing_evaluator", request)
    assert caught.value.status_code >= 400
    assert caught.value.detail["error_class"] == error_class
    telemetry = caught.value.detail["telemetry"]
    assert telemetry["capability"] == "writing_evaluator"
    assert telemetry["error_class"] == error_class
    assert telemetry["outcome"] == "failure"
    assert telemetry["usage"] == {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    }
    assert telemetry["quota_available"] == "unknown"
    assert "raw network" not in str(caught.value.detail)
    assert repository.legacy_writes == []


def test_live_test_requires_explicit_config_and_never_uses_legacy_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    repository.legacy = AISelectionRecord("openai", "model-1")
    provider = FakeProvider()
    request = configure_platform(
        monkeypatch, repository, providers={"openai": provider}
    )
    with pytest.raises(HTTPException) as caught:
        platform_module.admin_ai_capability_test("writing_evaluator", request)
    assert caught.value.status_code == 404
    assert caught.value.detail["error_class"] == "capability_not_configured"
    assert provider.discovery_calls == 0
    assert provider.generation_calls == []


def test_malformed_persisted_config_fails_safely_without_echoing_raw_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MalformedRepository(FakeRepository):
        def get_capability_config(self, capability_key: str):
            raise AICapabilityConfigInvalid("persisted token=super-secret is malformed")

    request = configure_platform(monkeypatch, MalformedRepository())
    with pytest.raises(HTTPException) as caught:
        platform_module.admin_ai_capability_test("writing_evaluator", request)
    assert caught.value.status_code == 400
    assert caught.value.detail["error_class"] == "capability_invalid"
    assert "super-secret" not in str(caught.value.detail)


@pytest.mark.parametrize(
    "capability_key",
    ["reading_evaluator", "speech_asr", "pronunciation_evaluator", "speaking_evaluator"],
)
def test_live_test_rejects_deterministic_and_reserved_capabilities(
    monkeypatch: pytest.MonkeyPatch,
    capability_key: str,
) -> None:
    request = configure_platform(monkeypatch, FakeRepository())
    with pytest.raises(HTTPException) as caught:
        platform_module.admin_ai_capability_test(capability_key, request)
    assert caught.value.status_code == 400
    assert caught.value.detail["error_class"] == "capability_invalid"


def test_live_test_invalid_capability_does_not_echo_caller_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    request = configure_platform(monkeypatch, repository)
    supplied = "unknown?token=do-not-leak"

    with pytest.raises(HTTPException) as caught:
        platform_module.admin_ai_capability_test(supplied, request)

    assert caught.value.detail["telemetry"]["capability"] == "[invalid]"
    assert caught.value.detail["capability"] == "[invalid]"
    assert "do-not-leak" not in str(caught.value.detail)


def test_live_test_invokes_exact_provider_model_once_and_validates_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    repository.capabilities["writing_evaluator"] = capability_config()
    selected = FakeProvider()
    fallback = FakeProvider(id="deepseek")
    request = configure_platform(
        monkeypatch,
        repository,
        providers={"openai": selected, "deepseek": fallback},
    )
    response = platform_module.admin_ai_capability_test("writing_evaluator", request)

    assert response | {
        "ok": True,
        "capability": "writing_evaluator",
        "provider": "openai",
        "model": "model-1",
        "error_class": None,
    } == response
    assert response["telemetry"]["capability"] == "writing_evaluator"
    assert response["telemetry"]["outcome"] == "success"
    assert response["telemetry"]["usage"] == {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    }
    assert selected.discovery_calls == 1
    assert len(selected.generation_calls) == 1
    assert selected.generation_calls[0]["model"] == "model-1"
    assert selected.generation_calls[0]["max_output_tokens"] == 40
    assert fallback.discovery_calls == 0
    assert fallback.generation_calls == []


def test_live_test_invalid_response_and_raw_provider_errors_are_not_exposed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    hostile = "abc?api_key=super-secret"
    repository.capabilities["writing_evaluator"] = capability_config(model=hostile)
    malformed = FakeProvider(models=(hostile,), response={"ok": True, "capability": "wrong"})
    request = configure_platform(
        monkeypatch, repository, providers={"openai": malformed}
    )
    with pytest.raises(HTTPException) as caught:
        platform_module.admin_ai_capability_test("writing_evaluator", request)
    assert caught.value.detail["error_class"] == "provider_response_invalid"
    assert caught.value.detail["model"] == "[redacted]"
    assert caught.value.detail["telemetry"]["model"] == "[redacted]"
    assert caught.value.detail["telemetry"]["model_redacted"] is True
    assert "super-secret" not in str(caught.value.detail)
    assert len(malformed.generation_calls) == 1

    failing = FakeProvider(
        models=(hostile,),
        generation_error=AIProviderError("Authorization: Bearer super-secret raw-body"),
    )
    request = configure_platform(
        monkeypatch, repository, providers={"openai": failing}
    )
    with pytest.raises(HTTPException) as caught:
        platform_module.admin_ai_capability_test("writing_evaluator", request)
    assert caught.value.detail["error_class"] == "provider_error"
    assert caught.value.detail["telemetry"]["error_class"] == "provider_error"
    assert "super-secret" not in str(caught.value.detail)
    assert "raw-body" not in str(caught.value.detail)
    assert len(failing.generation_calls) == 1


def test_unexpected_programming_error_is_not_reclassified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    repository.capabilities["writing_evaluator"] = capability_config()
    provider = FakeProvider(generation_error=ValueError("programming defect"))
    request = configure_platform(monkeypatch, repository, providers={"openai": provider})
    with pytest.raises(ValueError, match="programming defect"):
        platform_module.admin_ai_capability_test("writing_evaluator", request)


def test_legacy_endpoints_are_deprecated_and_storage_isolation_is_bidirectional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    provider = FakeProvider()
    request = configure_platform(monkeypatch, repository, providers={"openai": provider})
    legacy_put = platform_module.admin_ai_config_update(
        platform_module.AIConfigIn(provider="openai", model="model-1"), request
    )
    assert legacy_put["active"]["model"] == "model-1"
    assert repository.legacy_writes == [("openai", "model-1", "admin-1")]
    assert repository.capability_writes == []

    platform_module.admin_ai_capability_config_update(
        "writing_evaluator",
        platform_module.CapabilityConfigIn(**valid_payload()),
        request,
    )
    assert len(repository.capability_writes) == 1
    assert len(repository.legacy_writes) == 1

    legacy_test = platform_module.admin_ai_test(
        platform_module.AIConfigIn(provider="openai", model="model-1"), request
    )
    assert legacy_test["provider"] == "openai"
    assert len(repository.capability_writes) == 1
    legacy_routes = {
        (route.path, method): route
        for route in platform_module.router.routes
        for method in route.methods
    }
    assert legacy_routes[("/api/admin/ai/config", "PUT")].deprecated is True
    assert legacy_routes[("/api/admin/ai/test", "POST")].deprecated is True


def test_capability_keys_are_product_wide_not_language_duplicated() -> None:
    keys = {definition.key for definition in all_capabilities()}
    assert not any(key.endswith(("_en", "_zh")) for key in keys)


def openai_provider(monkeypatch: pytest.MonkeyPatch, *, default_models=()) -> OpenAICompatibleProvider:
    monkeypatch.setenv("TEST_AI_KEY", "credential-present")
    monkeypatch.setenv("TEST_AI_URL", "https://provider.invalid/v1")
    monkeypatch.delenv("TEST_AI_MODELS", raising=False)
    return OpenAICompatibleProvider(
        provider_id="openai",
        name="Test Provider",
        api_key_env="TEST_AI_KEY",
        base_url_env="TEST_AI_URL",
        default_base_url="https://provider.invalid/v1",
        models_env="TEST_AI_MODELS",
        default_models=default_models,
    )


def test_live_discovery_distinguishes_credentials_transport_and_configured_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_AI_KEY", raising=False)
    missing = openai_provider(monkeypatch)
    missing.api_key = ""
    with pytest.raises(AIProviderNotConfigured):
        missing.discover_models_live()

    provider = openai_provider(monkeypatch)
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: (_ for _ in ()).throw(
        requests.ConnectionError("secret transport detail")
    ))
    with pytest.raises(AIProviderUnavailable):
        provider.discover_models_live()

    monkeypatch.setenv("TEST_AI_MODELS", "model-b,model-a,model-a")
    configured = openai_provider(monkeypatch)
    configured.allowed_models = ["model-b", "model-a", "model-a"]
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: pytest.fail("configured catalog made HTTP request"))
    assert configured.discover_models_live() == ["model-a", "model-b"]


def test_gemini_live_discovery_uses_configured_openai_compatible_models_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_GEMINI_KEY", "credential-present")
    provider = OpenAICompatibleProvider(
        provider_id="gemini",
        name="Gemini API",
        api_key_env="TEST_GEMINI_KEY",
        base_url_env="TEST_GEMINI_URL",
        default_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        models_env="TEST_GEMINI_MODELS",
        model_filter="gemini-text",
    )
    calls: list[tuple[str, dict[str, Any]]] = []

    def get(url: str, **kwargs: Any) -> ProviderResponse:
        calls.append((url, kwargs))
        return ProviderResponse(
            {
                "data": [
                    {"id": "gemini-2.5-flash"},
                    {"id": "text-embedding-004"},
                ]
            }
        )

    monkeypatch.setattr(requests, "get", get)

    assert provider.discover_models_live() == ["gemini-2.5-flash"]
    assert calls[0][0] == "https://generativelanguage.googleapis.com/v1beta/openai/models"
    assert calls[0][1]["headers"] == {
        "Authorization": "Bearer credential-present",
        "Content-Type": "application/json",
    }


def test_gemini_openai_compatible_catalog_resource_names_are_read_as_model_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The live compatible endpoint answers with "models/<id>"; every model was filtered out."""
    monkeypatch.setenv("TEST_GEMINI_KEY", "credential-present")
    provider = OpenAICompatibleProvider(
        provider_id="gemini",
        name="Gemini API",
        api_key_env="TEST_GEMINI_KEY",
        base_url_env="TEST_GEMINI_URL",
        default_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        models_env="TEST_GEMINI_MODELS",
        model_filter="gemini-text",
    )

    def get(url: str, **kwargs: Any) -> ProviderResponse:
        return ProviderResponse(
            {
                "data": [
                    {"id": "models/gemini-2.5-flash"},
                    {"id": "models/gemini-3.1-flash-lite"},
                    {"id": "models/gemini-2.5-flash-preview-tts"},
                    {"id": "models/text-embedding-004"},
                ]
            }
        )

    monkeypatch.setattr(requests, "get", get)

    assert provider.discover_models_live() == ["gemini-2.5-flash", "gemini-3.1-flash-lite"]
    assert provider.list_models() == ["gemini-2.5-flash", "gemini-3.1-flash-lite"]


def test_gemini_live_discovery_falls_back_to_native_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_GEMINI_KEY", "credential-present")
    provider = OpenAICompatibleProvider(
        provider_id="gemini",
        name="Gemini API",
        api_key_env="TEST_GEMINI_KEY",
        base_url_env="TEST_GEMINI_URL",
        default_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        models_env="TEST_GEMINI_MODELS",
        model_filter="gemini-text",
    )
    calls: list[tuple[str, dict[str, Any]]] = []

    class Response:
        def __init__(self, status_code: int, envelope: dict[str, Any]) -> None:
            self.status_code = status_code
            self._envelope = envelope

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise requests.HTTPError(response=self)

        def json(self) -> dict[str, Any]:
            return self._envelope

    def get(url: str, **kwargs: Any) -> Response:
        calls.append((url, kwargs))
        if url.endswith("/openai/models"):
            return Response(401, {})
        return Response(200, {"models": [{"name": "models/gemini-2.5-flash"}]})

    monkeypatch.setattr(requests, "get", get)

    assert provider.discover_models_live() == ["gemini-2.5-flash"]
    assert calls[1][0] == "https://generativelanguage.googleapis.com/v1beta/models"
    assert calls[1][1]["headers"] == {
        "x-goog-api-key": "credential-present",
        "Content-Type": "application/json",
    }


def test_hardcoded_default_models_are_not_live_discovery_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = openai_provider(monkeypatch, default_models=("suggested-model",))

    class EmptyCatalogResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, list[Any]]:
            return {"data": []}

    calls = []
    monkeypatch.setattr(requests, "get", lambda *_args, **_kwargs: calls.append(True) or EmptyCatalogResponse())
    assert provider.discover_models_live() == []
    assert calls == [True]


def test_one_shot_provider_request_has_typed_transport_and_response_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = openai_provider(monkeypatch)
    kwargs = {
        "messages": [{"role": "user", "content": "test"}],
        "schema": {"type": "object"},
        "model": "model-1",
        "max_output_tokens": 40,
        "temperature": 0.0,
    }
    calls = []

    def unavailable(_body):
        calls.append("unavailable")
        raise requests.ConnectionError("Authorization: Bearer super-secret")

    monkeypatch.setattr(provider, "_post_chat", unavailable)
    with pytest.raises(AIProviderUnavailable, match="not reachable"):
        provider.generate_json_once(**kwargs)
    assert calls == ["unavailable"]

    def malformed(_body):
        calls.append("malformed")
        return {"choices": [{"message": {"content": "not-json"}}]}

    monkeypatch.setattr(provider, "_post_chat", malformed)
    with pytest.raises(AIProviderResponseInvalid):
        provider.generate_json_once(**kwargs)
    assert calls == ["unavailable", "malformed"]


class ProviderResponse:
    def __init__(self, payload: object, *, headers: dict[str, str] | None = None, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        pass

    def json(self) -> object:
        return self.payload


class InvalidJSONResponse(ProviderResponse):
    def json(self) -> object:
        raise ValueError("Authorization: Bearer super-secret raw-body")


def test_openai_structured_response_captures_allowlisted_rate_limit_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = openai_provider(monkeypatch)
    payload = {"choices": [{"message": {"content": '{"ok": true}'}}]}
    response = ProviderResponse(
        payload,
        headers={
            "X-RateLimit-Limit-Requests": "9" * 100,
            "x-ratelimit-remaining-requests": "0",
            "x-ratelimit-limit-tokens": "20000",
            "x-ratelimit-remaining-tokens": "bad",
            "x-ratelimit-reset-requests": "tomorrow",
        },
    )
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: response)

    result = provider.generate_json_once(
        messages=[{"role": "user", "content": "test"}],
        schema={"type": "object"},
        model="model-1",
        max_output_tokens=40,
        temperature=0.0,
    )

    assert result.runtime["rate_limit"] == {
        "requests_limit": None,
        "requests_remaining": 0,
        "tokens_limit": 20000,
        "tokens_remaining": None,
    }
    assert "x-ratelimit-reset-requests" not in result.runtime["rate_limit"]


def test_openai_provider_failure_retains_safe_rate_limit_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = openai_provider(monkeypatch)
    response = ProviderResponse(
        {"error": {"message": "rate limited"}},
        status_code=429,
        headers={
            "x-ratelimit-remaining-requests": "0",
            "x-ratelimit-remaining-tokens": "0",
            "x-ratelimit-reset-requests": "secret-reset-value",
        },
    )
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: response)

    with pytest.raises(AIProviderError) as caught:
        provider.generate_json_once(
            messages=[{"role": "user", "content": "test"}],
            schema={"type": "object"},
            model="model-1",
            max_output_tokens=40,
            temperature=0.0,
        )

    assert caught.value.rate_limit == {
        "requests_limit": None,
        "requests_remaining": 0,
        "tokens_limit": None,
        "tokens_remaining": 0,
    }
    assert "secret-reset-value" not in repr(caught.value.rate_limit)


@pytest.mark.parametrize(
    "provider_factory",
    [
        lambda monkeypatch: openai_provider(monkeypatch),
        lambda _monkeypatch: OllamaProvider(),
    ],
)
def test_live_discovery_rejects_invalid_json_bodies_with_safe_catalog_error(
    monkeypatch: pytest.MonkeyPatch,
    provider_factory,
) -> None:
    provider = provider_factory(monkeypatch)
    calls = []
    monkeypatch.setattr(
        requests,
        "get",
        lambda *_args, **_kwargs: calls.append(True) or InvalidJSONResponse({}),
    )

    with pytest.raises(AIProviderResponseInvalid) as caught:
        provider.discover_models_live()

    assert str(caught.value) == "AI provider returned an invalid model catalog."
    assert "super-secret" not in str(caught.value)
    assert "raw-body" not in str(caught.value)
    assert calls == [True]


@pytest.mark.parametrize(
    "envelope",
    [
        [],
        {"data": None},
        {"data": "invalid"},
        {"data": [None]},
        {"data": [{"id": {"unexpected": "super-secret"}}]},
    ],
)
def test_openai_live_discovery_rejects_malformed_json_envelopes(
    monkeypatch: pytest.MonkeyPatch,
    envelope: object,
) -> None:
    provider = openai_provider(monkeypatch)
    calls = []
    monkeypatch.setattr(
        requests,
        "get",
        lambda *_args, **_kwargs: calls.append(True) or ProviderResponse(envelope),
    )
    with pytest.raises(AIProviderResponseInvalid) as caught:
        provider.discover_models_live()
    assert str(caught.value) == "AI provider returned an invalid model catalog."
    assert "super-secret" not in str(caught.value)
    assert calls == [True]


@pytest.mark.parametrize(
    "envelope",
    [
        [],
        {"models": None},
        {"models": "invalid"},
        {"models": [None]},
        {"models": [{"name": {"unexpected": "super-secret"}}]},
    ],
)
def test_ollama_live_discovery_rejects_malformed_json_envelopes(
    monkeypatch: pytest.MonkeyPatch,
    envelope: object,
) -> None:
    provider = OllamaProvider()
    calls = []
    monkeypatch.setattr(
        requests,
        "get",
        lambda *_args, **_kwargs: calls.append(True) or ProviderResponse(envelope),
    )
    with pytest.raises(AIProviderResponseInvalid) as caught:
        provider.discover_models_live()
    assert str(caught.value) == "AI provider returned an invalid model catalog."
    assert "super-secret" not in str(caught.value)
    assert calls == [True]


@pytest.mark.parametrize(
    "envelope",
    [
        [],
        {"choices": "invalid"},
        {"choices": [None]},
        {"choices": [{}]},
        {"choices": [{"message": None}]},
        {"choices": [{"message": "super-secret raw-body"}]},
    ],
)
def test_openai_one_shot_generation_rejects_malformed_json_envelopes_once(
    monkeypatch: pytest.MonkeyPatch,
    envelope: object,
) -> None:
    provider = openai_provider(monkeypatch)
    calls = []
    monkeypatch.setattr(
        provider,
        "_post_chat",
        lambda _body: calls.append(True) or envelope,
    )
    with pytest.raises(AIProviderResponseInvalid) as caught:
        provider.generate_json_once(
            messages=[{"role": "user", "content": "test"}],
            schema={"type": "object"},
            model="model-1",
            max_output_tokens=40,
            temperature=0.0,
        )
    assert "super-secret" not in str(caught.value)
    assert "raw-body" not in str(caught.value)
    assert calls == [True]


@pytest.mark.parametrize(
    "envelope",
    [
        [],
        {"message": None},
        {"message": "invalid"},
        {"message": {"content": None}},
        {"message": {"content": ""}},
    ],
)
def test_ollama_live_generation_rejects_malformed_json_envelopes_once(
    monkeypatch: pytest.MonkeyPatch,
    envelope: object,
) -> None:
    provider = OllamaProvider()
    calls = []
    monkeypatch.setattr(
        requests,
        "post",
        lambda *_args, **_kwargs: calls.append(True) or ProviderResponse(envelope),
    )
    with pytest.raises(AIProviderResponseInvalid):
        provider.generate_json_once(
            messages=[{"role": "user", "content": "test"}],
            schema={"type": "object"},
            model="model-1",
            max_output_tokens=40,
            temperature=0.0,
        )
    assert calls == [True]


def test_malformed_provider_envelope_is_sanitized_by_admin_endpoint_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    repository.capabilities["writing_evaluator"] = capability_config()
    provider = openai_provider(monkeypatch)
    provider.allowed_models = ["model-1"]
    fallback = FakeProvider(id="deepseek")
    calls = []
    monkeypatch.setattr(
        provider,
        "_post_chat",
        lambda _body: calls.append(True) or {"choices": "super-secret raw-body"},
    )
    request = configure_platform(
        monkeypatch,
        repository,
        providers={"openai": provider, "deepseek": fallback},
    )
    with pytest.raises(HTTPException) as caught:
        platform_module.admin_ai_capability_test("writing_evaluator", request)
    assert caught.value.status_code == 502
    assert caught.value.detail["error_class"] == "provider_response_invalid"
    assert "super-secret" not in str(caught.value.detail)
    assert "raw-body" not in str(caught.value.detail)
    assert calls == [True]
    assert fallback.discovery_calls == 0
    assert fallback.generation_calls == []


def test_invalid_json_catalog_is_sanitized_by_admin_endpoint_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    repository.capabilities["writing_evaluator"] = capability_config()
    provider = openai_provider(monkeypatch)
    fallback = FakeProvider(id="deepseek")
    calls = []
    monkeypatch.setattr(
        requests,
        "get",
        lambda *_args, **_kwargs: calls.append(True) or InvalidJSONResponse({}),
    )
    request = configure_platform(
        monkeypatch,
        repository,
        providers={"openai": provider, "deepseek": fallback},
    )

    with pytest.raises(HTTPException) as caught:
        platform_module.admin_ai_capability_test("writing_evaluator", request)

    assert caught.value.status_code == 502
    assert caught.value.detail["error_class"] == "provider_response_invalid"
    assert "super-secret" not in str(caught.value.detail)
    assert "raw-body" not in str(caught.value.detail)
    assert calls == [True]
    assert fallback.discovery_calls == 0
    assert fallback.generation_calls == []


def test_legacy_endpoints_redact_models_and_provider_errors_without_changing_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hostile = "abc?api_key=super-secret"
    repository = FakeRepository()
    provider = FakeProvider(models=(hostile,), response={"ok": True, "message": "raw-body"})
    request = configure_platform(monkeypatch, repository, providers={"openai": provider})

    put_result = platform_module.admin_ai_config_update(
        platform_module.AIConfigIn(provider="openai", model=hostile), request
    )
    assert repository.legacy is not None and repository.legacy.model == hostile
    assert repository.capability_writes == []
    assert put_result["active"]["model"] == "[redacted]"
    assert put_result["active"]["model_redacted"] is True
    assert put_result["providers"][0]["models"] == ["[redacted]"]
    assert put_result["providers"][0]["models_redacted"] is True
    assert put_result["providers"][0]["default_model"] == "[redacted]"
    assert put_result["providers"][0]["default_model_redacted"] is True
    assert "super-secret" not in json.dumps(put_result)

    success = platform_module.admin_ai_test(
        platform_module.AIConfigIn(provider="openai", model=hostile), request
    )
    assert success["model"] == "[redacted]"
    assert success["model_redacted"] is True
    assert success["message"] == "Connection succeeded."
    assert "super-secret" not in json.dumps(success)
    assert "raw-body" not in json.dumps(success)
    assert repository.capability_writes == []
    legacy_write_count = len(repository.legacy_writes)

    provider.generation_error = AIProviderError(
        "Authorization: Bearer super-secret raw-body"
    )
    with pytest.raises(HTTPException) as caught:
        platform_module.admin_ai_test(
            platform_module.AIConfigIn(provider="openai", model=hostile), request
        )
    assert caught.value.status_code == 502
    assert caught.value.detail == "AI provider request failed."
    assert "super-secret" not in str(caught.value.detail)
    assert "raw-body" not in str(caught.value.detail)
    assert len(repository.legacy_writes) == legacy_write_count
    assert repository.capability_writes == []

    provider.generation_error = AIProviderUnavailable(
        "connection failed with token=super-secret raw-body"
    )
    with pytest.raises(HTTPException) as caught:
        platform_module.admin_ai_test(
            platform_module.AIConfigIn(provider="openai", model=hostile), request
        )
    assert caught.value.status_code == 503
    assert caught.value.detail == "AI provider is unavailable."
    assert "super-secret" not in str(caught.value.detail)
    assert "raw-body" not in str(caught.value.detail)
    assert len(repository.legacy_writes) == legacy_write_count
    assert repository.capability_writes == []
