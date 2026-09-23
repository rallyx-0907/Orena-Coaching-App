from __future__ import annotations

import sys

import pytest

from scripts import migrate_ai_capability_config as migration
from scripts import validate_ai_capability_control_plane as preflight
from writing_coach.ai.capabilities import AIFallbackPolicy
from writing_coach.ai.config import CapabilityConfig
from writing_coach.persistence.platform_repository import (
    AISelectionRecord,
    CapabilityConfigRecord,
)


class FakeRepository:
    def __init__(self, legacy: AISelectionRecord | None = None) -> None:
        self.legacy = legacy
        self.configs: dict[str, CapabilityConfig] = {}
        self.writes: list[str] = []

    def get_ai_selection(self):
        return self.legacy

    def set_ai_selection(self, **_kwargs):
        raise AssertionError("legacy selection must not be written")

    def initialize(self):
        raise AssertionError("migration/preflight must not initialize storage")

    def get_capability_config(self, capability_key: str):
        value = self.configs.get(capability_key)
        return (
            CapabilityConfigRecord(capability_key=capability_key, config=value)
            if value is not None
            else None
        )

    def list_capability_configs(self):
        return [
            CapabilityConfigRecord(capability_key=key, config=value)
            for key, value in sorted(self.configs.items())
        ]

    def set_capability_config(self, capability_key, config, *, updated_by=""):
        assert updated_by == "operator:migrate_ai_capability_config"
        self.writes.append(capability_key)
        self.configs[capability_key] = config


def legacy(provider: str = "openai", model: str = "model-1") -> AISelectionRecord:
    return AISelectionRecord(provider=provider, model=model)


def test_migration_dry_run_writes_nothing_and_lists_exact_current_rows() -> None:
    repository = FakeRepository(legacy())
    report = migration.migrate_capability_configs(repository, dry_run=True)
    assert repository.writes == [] and repository.configs == {}
    # Seven configurable capabilities: writing_linguistic is deterministic.
    assert len(report["would_create"]) == 8
    assert not {"reading_evaluator", "speech_asr", "pronunciation_evaluator", "speaking_evaluator"} & set(report["would_create"])


def test_migration_requires_postgresql_backend(monkeypatch) -> None:
    monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
    with pytest.raises(migration.CapabilityMigrationError, match="must be postgresql"):
        migration.require_postgresql_runtime()


def test_preflight_requires_postgresql_backend(monkeypatch) -> None:
    monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
    with pytest.raises(preflight.CapabilityPreflightError, match="must be postgresql"):
        preflight.require_postgresql_runtime()


@pytest.mark.parametrize("selection", [None, legacy("", "model"), legacy("openai", "")])
def test_migration_fails_for_absent_or_malformed_legacy_selection(selection) -> None:
    with pytest.raises(migration.CapabilityMigrationError):
        migration.migrate_capability_configs(FakeRepository(selection), dry_run=False)


def test_migration_is_idempotent_and_does_not_overwrite_existing_rows() -> None:
    repository = FakeRepository(legacy())
    existing = CapabilityConfig(
        enabled=False,
        provider="ollama",
        model="preserved-model",
        fallback_policy=AIFallbackPolicy.NONE,
    )
    repository.configs["writing_evaluator"] = existing
    first = migration.migrate_capability_configs(repository, dry_run=False)
    assert repository.configs["writing_evaluator"] == existing
    assert "writing_evaluator" in first["skipped_existing"]
    assert len(repository.writes) == 7

    second = migration.migrate_capability_configs(repository, dry_run=False)
    assert second["created"] == []
    assert len(second["skipped_existing"]) == 8
    assert len(repository.writes) == 7


def test_migration_seeds_only_approved_fallback_policies() -> None:
    repository = FakeRepository(legacy())
    migration.migrate_capability_configs(repository, dry_run=False)
    fallback = {
        key
        for key, value in repository.configs.items()
        if value.fallback_policy is AIFallbackPolicy.DETERMINISTIC_FALLBACK
    }
    assert fallback == {
        "reading_generator",
        "writing_task_generator",
        "grammar_lesson_generator",
    }
    assert set(repository.configs) - fallback == {
        "writing_evaluator",
        "text_discussion",
        "writing_improver",
        "learner_dictionary",
        "learner_translation",
    }


def test_preflight_requires_every_explicit_row_and_ignores_legacy_selection() -> None:
    repository = FakeRepository(legacy())
    with pytest.raises(preflight.CapabilityPreflightError, match="Missing explicit"):
        preflight.validate_persisted_capabilities(repository)
    migration.migrate_capability_configs(repository, dry_run=False)
    report = preflight.validate_persisted_capabilities(repository)
    # Seven, not eight: writing_linguistic is deterministic and has no row.
    assert report["ok"] is True and report["explicit_row_count"] == 8


@pytest.mark.parametrize(
    "forbidden_key",
    ["reading_evaluator", "speech_asr", "pronunciation_evaluator", "speaking_evaluator"],
)
def test_preflight_rejects_deterministic_and_reserved_rows(forbidden_key: str) -> None:
    repository = FakeRepository(legacy())
    migration.migrate_capability_configs(repository, dry_run=False)
    repository.configs[forbidden_key] = CapabilityConfig(
        enabled=True,
        provider="openai",
        model="model-1",
    )
    with pytest.raises(preflight.CapabilityPreflightError, match="Forbidden"):
        preflight.validate_persisted_capabilities(repository)


def test_migration_and_preflight_never_call_provider_network(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        pytest.fail("operator config tooling attempted provider network access")

    monkeypatch.setattr("requests.get", forbidden)
    monkeypatch.setattr("requests.post", forbidden)
    repository = FakeRepository(legacy())
    migration.migrate_capability_configs(repository, dry_run=False)
    assert preflight.validate_persisted_capabilities(repository)["ok"] is True


def test_operator_output_does_not_expose_environment_secrets_or_database_url(
    monkeypatch, capsys
) -> None:
    repository = FakeRepository(legacy())
    monkeypatch.setenv("OPENAI_API_KEY", "api-secret-value")
    monkeypatch.setenv(
        "POSTGRES_RUNTIME_URL",
        "postgresql+psycopg://db-user:db-secret@example.invalid/becoming",
    )
    monkeypatch.setattr(migration, "postgres_repository", lambda: repository)
    monkeypatch.setattr(sys, "argv", ["migrate_ai_capability_config.py", "--dry-run"])
    migration.main()
    output = capsys.readouterr().out
    assert "api-secret-value" not in output
    assert "db-secret" not in output
    assert "POSTGRES_RUNTIME_URL" not in output

    migration.migrate_capability_configs(repository, dry_run=False)
    monkeypatch.setattr(preflight, "postgres_repository", lambda: repository)
    preflight.main()
    output = capsys.readouterr().out
    assert "api-secret-value" not in output and "db-secret" not in output


@pytest.mark.parametrize(
    "hostile_model",
    [
        "https://user:super-secret@example.invalid/model",
        "token=super-secret",
        "abc?api_key=super-secret",
    ],
)
def test_operator_output_never_echoes_sensitive_legacy_model(
    monkeypatch, capsys, hostile_model: str
) -> None:
    repository = FakeRepository(legacy(model=hostile_model))
    monkeypatch.setattr(migration, "postgres_repository", lambda: repository)
    monkeypatch.setattr(sys, "argv", ["migrate_ai_capability_config.py", "--dry-run"])

    migration.main()

    captured = capsys.readouterr()
    assert "super-secret" not in captured.out
    assert "super-secret" not in captured.err
    assert hostile_model not in captured.out
    assert hostile_model not in captured.err
    assert repository.configs == {}
    report = migration.migrate_capability_configs(repository, dry_run=False)
    assert report["ok"] is True
    assert {item.model for item in repository.configs.values()} == {hostile_model}
