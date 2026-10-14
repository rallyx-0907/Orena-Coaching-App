"""Explicit PostgreSQL-only migration from the legacy global AI selection."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from writing_coach.ai.capabilities import (  # noqa: E402
    AIFallbackPolicy,
    activation_capabilities,
)
from writing_coach.ai.config import CapabilityConfig, validate_capability_config  # noqa: E402
from writing_coach.persistence.config import create_runtime_engine  # noqa: E402
from writing_coach.persistence.platform_repository import (  # noqa: E402
    PlatformRepository,
    PostgresPlatformRepository,
)


class CapabilityMigrationError(RuntimeError):
    pass


def require_postgresql_runtime() -> None:
    backend = os.getenv("PERSISTENCE_BACKEND", "").strip().casefold()
    if backend != "postgresql":
        raise CapabilityMigrationError(
            "PERSISTENCE_BACKEND must be postgresql for AI capability migration."
        )


def postgres_repository() -> PostgresPlatformRepository:
    require_postgresql_runtime()
    try:
        return PostgresPlatformRepository(create_runtime_engine())
    except Exception as exc:
        raise CapabilityMigrationError(
            "Could not create the PostgreSQL runtime repository."
        ) from exc


def _seed_config(capability_key: str, provider: str, model: str) -> CapabilityConfig:
    fallback = (
        AIFallbackPolicy.DETERMINISTIC_FALLBACK
        if capability_key
        in {"reading_generator", "writing_task_generator", "grammar_lesson_generator"}
        else AIFallbackPolicy.NONE
    )
    config = CapabilityConfig(
        enabled=True,
        provider=provider,
        model=model,
        fallback_policy=fallback,
    )
    validate_capability_config(capability_key, config)
    return config


def migrate_capability_configs(
    repository: PlatformRepository,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    """Create only missing explicit rows; never invent a legacy selection."""

    legacy = repository.get_ai_selection()
    if legacy is None:
        raise CapabilityMigrationError("Persisted ai.active_selection is absent.")
    provider = str(legacy.provider or "").strip().casefold()
    model = str(legacy.model or "").strip()
    if not provider or not model:
        raise CapabilityMigrationError("Persisted ai.active_selection is malformed.")

    created: list[str] = []
    skipped: list[str] = []
    for definition in activation_capabilities():
        config = _seed_config(definition.key, provider, model)
        if repository.get_capability_config(definition.key) is not None:
            skipped.append(definition.key)
            continue
        created.append(definition.key)
        if not dry_run:
            repository.set_capability_config(
                definition.key,
                config,
                updated_by="operator:migrate_ai_capability_config",
            )

    return {
        "ok": True,
        "backend": "postgresql",
        "dry_run": dry_run,
        "provider": provider,
        "would_create" if dry_run else "created": created,
        "skipped_existing": skipped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create explicit PostgreSQL AI capability settings from ai.active_selection."
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        repository = postgres_repository()
        report = migrate_capability_configs(repository, dry_run=args.dry_run)
    except CapabilityMigrationError as exc:
        print(json.dumps({"ok": False, "backend": "postgresql", "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "backend": "postgresql",
                    "error": "PostgreSQL AI capability migration failed.",
                },
                indent=2,
            )
        )
        raise SystemExit(1) from exc
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
