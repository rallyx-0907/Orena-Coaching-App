from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import writing_coach.ai.config as config_module
from writing_coach.ai.base import (
    AICapabilityConfigInvalid,
    AICapabilityUnsupported,
    AIProviderUnsupportedOperation,
)
from writing_coach.ai.capabilities import AIFallbackPolicy, AIOperation
from writing_coach.ai.config import CapabilityConfig, validate_capability_config
from writing_coach.ai.providers import (
    ProviderDefinition,
    build_providers,
    provider_definitions,
)
from writing_coach.persistence.models import Base, PlatformSetting
from writing_coach.persistence.platform_repository import (
    PostgresPlatformRepository,
    SQLitePlatformRepository,
)


def config(**overrides) -> CapabilityConfig:
    values = {
        "enabled": True,
        "provider": "openai",
        "model": "model-1",
        "temperature": 0.2,
        "fallback_policy": AIFallbackPolicy.NONE,
    }
    values.update(overrides)
    return CapabilityConfig(**values)


def test_config_round_trip_is_strict_and_secret_free() -> None:
    original = config()
    restored = CapabilityConfig.from_dict(original.to_dict())
    assert restored == original
    assert set(original.to_dict()) == {
        "config_version",
        "enabled",
        "provider",
        "model",
        "backup_provider",
        "backup_model",
        "timeout_seconds",
        "temperature",
        "fallback_policy",
    }
    assert not any("key" in field or "credential" in field for field in original.to_dict())


@pytest.mark.parametrize(
    "raw",
    [
        None,
        {},
        {
            "config_version": 1,
            "enabled": True,
            "provider": "openai",
            "model": "m",
            "fallback_policy": "none",
            "unexpected": True,
        },
        {
            "config_version": 2,
            "enabled": True,
            "provider": "openai",
            "model": "m",
            "fallback_policy": "none",
        },
        {
            "config_version": 1,
            "enabled": "true",
            "provider": "openai",
            "model": "m",
            "fallback_policy": "none",
        },
    ],
)
def test_malformed_config_fails_explicitly(raw) -> None:
    with pytest.raises(AICapabilityConfigInvalid):
        CapabilityConfig.from_dict(raw)


def test_static_validation_rejects_unknown_provider_and_invalid_options() -> None:
    with pytest.raises(AICapabilityUnsupported, match="Unknown AI provider"):
        validate_capability_config("writing_evaluator", config(provider="unknown"))
    with pytest.raises(AIProviderUnsupportedOperation, match="timeout_seconds"):
        validate_capability_config("writing_evaluator", config(timeout_seconds=30))
    with pytest.raises(AICapabilityConfigInvalid):
        config(temperature=3.0)


def test_static_validation_rejects_unsupported_operation(monkeypatch) -> None:
    descriptor = ProviderDefinition(
        id="openai",
        name="text-disabled",
        kind="cloud",
        secret_mode="server-managed",
        supported_operations=frozenset(),
        supported_option_keys=frozenset(),
    )
    monkeypatch.setattr(config_module, "get_provider_definition", lambda _provider: descriptor)
    with pytest.raises(AIProviderUnsupportedOperation, match="structured_text_generation"):
        validate_capability_config("writing_evaluator", config(temperature=None))


def test_static_validation_requires_options_supported_by_primary_and_backup(monkeypatch) -> None:
    primary = ProviderDefinition(
        id="openai", name="primary", kind="cloud", secret_mode="server-managed",
        supported_operations=frozenset({AIOperation.STRUCTURED_TEXT_GENERATION}),
        supported_option_keys=frozenset({"temperature"}),
    )
    standby = ProviderDefinition(
        id="deepseek", name="standby", kind="cloud", secret_mode="server-managed",
        supported_operations=frozenset({AIOperation.STRUCTURED_TEXT_GENERATION}),
        supported_option_keys=frozenset(),
    )
    monkeypatch.setattr(
        config_module,
        "get_provider_definition",
        lambda provider: {"openai": primary, "deepseek": standby}.get(provider),
    )
    with pytest.raises(AIProviderUnsupportedOperation, match="Backup AI provider"):
        validate_capability_config(
            "writing_evaluator",
            config(backup_provider="deepseek", backup_model="deepseek-chat", temperature=0.2),
        )


@pytest.mark.parametrize(
    "capability_key",
    ["reading_evaluator", "speech_asr", "pronunciation_evaluator", "speaking_evaluator"],
)
def test_non_configurable_capabilities_reject_provider_config(capability_key: str) -> None:
    with pytest.raises(AICapabilityUnsupported, match="not provider-configurable"):
        validate_capability_config(capability_key, config())


def test_fallback_policy_is_capability_owned() -> None:
    fallback = config(fallback_policy=AIFallbackPolicy.DETERMINISTIC_FALLBACK)
    validate_capability_config("reading_generator", fallback)
    with pytest.raises(AICapabilityConfigInvalid, match="not allowed"):
        validate_capability_config("writing_evaluator", fallback)


def test_static_validation_and_provider_id_parity_require_no_network(monkeypatch) -> None:
    def network_forbidden(*_args, **_kwargs):
        pytest.fail("static validation attempted provider network access")

    monkeypatch.setattr("requests.get", network_forbidden)
    monkeypatch.setattr("requests.post", network_forbidden)
    validate_capability_config("writing_evaluator", config())
    assert {item.id for item in provider_definitions()} == set(build_providers())
    # The combined provider-operation contract: codex/work's Azure providers
    # (Azure Speech evaluates pronunciation and generates no text) and the
    # Intelligence lane's agent turns, streamed by the managed chat providers
    # only (D-085) - never by Azure OpenAI or a local model (D2). Every provider
    # is listed: a new one must declare its operations here.
    text = AIOperation.STRUCTURED_TEXT_GENERATION
    agent = AIOperation.AGENT_TURN
    assert {item.id: item.supported_operations for item in provider_definitions()} == {
        "azure-speech": frozenset({AIOperation.PRONUNCIATION_EVALUATION}),
        "azure-openai": frozenset({text}),
        "ollama": frozenset({text}),
        "openai": frozenset({text, agent}),
        "deepseek": frozenset({text, agent}),
        "groq": frozenset({text, agent}),
        "gemini": frozenset({text, agent}),
    }

def _exercise_repository(repository, *, sqlite_path: Path | None = None) -> None:
    assert repository.get_capability_config("writing_evaluator") is None
    assert repository.list_capability_configs() == []
    repository.set_ai_selection(provider="ollama", model="legacy-model", updated_by="legacy")
    assert repository.get_capability_config("writing_evaluator") is None

    selected = config(provider="openai", model="model-a")
    repository.set_capability_config("writing_evaluator", selected, updated_by="admin")
    row = repository.get_capability_config("writing_evaluator")
    assert row is not None and row.config == selected and row.updated_by == "admin"
    canonical = repository.get_capability_config(" WRITING_EVALUATOR ")
    assert canonical is not None and canonical.capability_key == "writing_evaluator"
    assert [item.capability_key for item in repository.list_capability_configs()] == [
        "writing_evaluator"
    ]

    if sqlite_path is not None:
        with sqlite3.connect(sqlite_path) as connection:
            legacy = connection.execute(
                "SELECT provider, model FROM platform_ai_config WHERE id = 1"
            ).fetchone()
            assert legacy == ("ollama", "legacy-model")


def test_sqlite_repository_explicit_capability_storage_and_no_lazy_table(tmp_path: Path) -> None:
    path = tmp_path / "platform.db"
    repository = SQLitePlatformRepository(path)
    repository.initialize()
    assert repository.get_capability_config("writing_evaluator") is None
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='platform_settings'"
        ).fetchone() is None
    _exercise_repository(repository, sqlite_path=path)


def test_postgres_repository_capability_storage_preserves_unrelated_settings() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        session.add(
            PlatformSetting(
                key="unrelated.setting",
                value={"keep": True},
                updated_at=datetime.now(timezone.utc),
                updated_by="test",
            )
        )
    repository = PostgresPlatformRepository(engine)
    _exercise_repository(repository)
    with Session(engine) as session:
        assert session.get(PlatformSetting, "unrelated.setting").value == {"keep": True}
