from __future__ import annotations

import json

import pytest
import requests

from scripts import validate_ai_runtime_activation as activation
from writing_coach.ai.base import AICapabilityConfigInvalid
from writing_coach.ai.capabilities import AIFallbackPolicy, configurable_provider_capabilities
from writing_coach.ai.config import CapabilityConfig
from writing_coach.ai.providers import ProviderDefinition
from writing_coach.persistence.platform_repository import CapabilityConfigRecord


EXPECTED_CAPABILITIES = {
    "writing_evaluator",
    "text_discussion",
    "reading_generator",
    "writing_task_generator",
    "writing_improver",
    "learner_dictionary",
    "learner_translation",
    "grammar_lesson_generator",
}
FALLBACK_CAPABILITIES = {
    "reading_generator",
    "writing_task_generator",
    "grammar_lesson_generator",
}


class Repository:
    def __init__(self) -> None:
        self.configs = {
            definition.key: CapabilityConfig(
                enabled=True,
                provider="openai",
                model="model-1",
                fallback_policy=(
                    AIFallbackPolicy.DETERMINISTIC_FALLBACK
                    if definition.key in FALLBACK_CAPABILITIES
                    else AIFallbackPolicy.NONE
                ),
            )
            for definition in configurable_provider_capabilities()
        }
        self.reads = 0

    def list_capability_configs(self):
        self.reads += 1
        return [
            CapabilityConfigRecord(capability_key=key, config=config)
            for key, config in sorted(self.configs.items())
        ]

    def initialize(self):
        pytest.fail("activation gate initialized storage")

    def set_ai_selection(self, **_kwargs):
        pytest.fail("activation gate wrote legacy selection")

    def set_capability_config(self, *_args, **_kwargs):
        pytest.fail("activation gate wrote capability config")


def ready(monkeypatch: pytest.MonkeyPatch, repository: Repository | None = None):
    monkeypatch.setenv("PERSISTENCE_BACKEND", "postgresql")
    monkeypatch.setenv("AI_RUNTIME_MODE", "legacy")
    return activation.validate_activation_readiness(repository or Repository())


def test_static_activation_readiness_passes_with_exact_atomic_contract(monkeypatch) -> None:
    repository = Repository()
    report = ready(monkeypatch, repository)

    assert report == {
        "ok": True,
        "gate": "ai-capability-runtime-activation",
        "current_mode": "legacy",
        "target_mode": "capability",
        "rollback_mode": "legacy",
        "backend": "postgresql",
        "validated_capabilities": sorted(EXPECTED_CAPABILITIES),
        "capability_count": 8,
        "static_validation": "pass",
        "live_validation": "not_executed",
        "requires_human_activation": True,
        "rollback_preserves_capability_config": True,
    }
    assert repository.reads == 1
    assert set(repository.configs) == EXPECTED_CAPABILITIES
    assert not any(key.endswith(("_en", "_zh")) for key in repository.configs)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda repo: repo.configs.pop("writing_evaluator"), "Missing explicit"),
        (
            lambda repo: repo.configs.__setitem__(
                "writing_evaluator",
                CapabilityConfig(enabled=False, provider="openai", model="model-1"),
            ),
            "Disabled",
        ),
        (
            lambda repo: repo.configs.__setitem__(
                "speech_asr",
                CapabilityConfig(enabled=True, provider="openai", model="model-1"),
            ),
            "Forbidden",
        ),
        (
            lambda repo: repo.configs.__setitem__(
                "writing_evaluator_en",
                CapabilityConfig(enabled=True, provider="openai", model="model-1"),
            ),
            "Forbidden",
        ),
        (
            lambda repo: repo.configs.__setitem__(
                "writing_evaluator",
                CapabilityConfig(
                    enabled=True,
                    provider="openai",
                    model="model-1",
                    fallback_policy=AIFallbackPolicy.DETERMINISTIC_FALLBACK,
                ),
            ),
            "invalid",
        ),
        (
            lambda repo: repo.configs.__setitem__(
                "reading_generator",
                CapabilityConfig(enabled=True, provider="openai", model="model-1"),
            ),
            "approved capability set",
        ),
    ],
)
def test_activation_readiness_fails_closed(monkeypatch, change, message) -> None:
    repository = Repository()
    change(repository)
    with pytest.raises(activation.ActivationReadinessError, match=message):
        ready(monkeypatch, repository)


def test_provider_capability_incompatibility_fails(monkeypatch) -> None:
    unsupported = ProviderDefinition(
        id="openai",
        name="OpenAI",
        kind="cloud",
        secret_mode="server-managed",
        supported_operations=frozenset(),
        supported_option_keys=frozenset(),
    )
    monkeypatch.setattr("writing_coach.ai.config.get_provider_definition", lambda _id: unsupported)
    with pytest.raises(activation.ActivationReadinessError, match="invalid"):
        ready(monkeypatch)


def test_malformed_persisted_config_fails_without_leaking_detail(monkeypatch) -> None:
    class MalformedRepository(Repository):
        def list_capability_configs(self):
            raise AICapabilityConfigInvalid("token=super-secret")

    with pytest.raises(activation.ActivationReadinessError, match="configuration is invalid") as caught:
        ready(monkeypatch, MalformedRepository())
    assert "super-secret" not in str(caught.value)


def test_gate_requires_postgresql_and_legacy_preactivation_state(monkeypatch) -> None:
    monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
    monkeypatch.setenv("AI_RUNTIME_MODE", "legacy")
    with pytest.raises(activation.CapabilityPreflightError, match="must be postgresql"):
        activation.validate_activation_readiness(Repository())

    monkeypatch.setenv("PERSISTENCE_BACKEND", "postgresql")
    monkeypatch.setenv("AI_RUNTIME_MODE", "capability")
    with pytest.raises(activation.ActivationReadinessError, match="requires current.*legacy"):
        activation.validate_activation_readiness(Repository())


def test_gate_performs_no_writes_or_provider_network(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        pytest.fail("activation gate performed provider network")

    monkeypatch.setattr(requests, "get", forbidden)
    monkeypatch.setattr(requests, "post", forbidden)
    report = ready(monkeypatch, Repository())
    assert report["ok"] is True


def test_cli_failure_output_is_structured_and_secret_safe(monkeypatch, capsys) -> None:
    secret = "super-secret-runtime-value"

    def fail():
        raise RuntimeError(secret)

    monkeypatch.setattr(activation, "postgres_repository", fail)
    with pytest.raises(SystemExit) as caught:
        activation.main()
    output = capsys.readouterr().out
    assert caught.value.code == 1
    assert secret not in output
    assert json.loads(output) == {
        "ok": False,
        "gate": "ai-capability-runtime-activation",
        "error": "AI runtime activation readiness validation failed.",
    }
