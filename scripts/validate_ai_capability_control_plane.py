"""Read-only Slice 2 preflight for explicit AI capability configuration."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from writing_coach.ai.capabilities import (  # noqa: E402
    activation_capabilities,
    get_capability,
)
from writing_coach.ai.config import validate_capability_config  # noqa: E402
from writing_coach.persistence.config import create_runtime_engine  # noqa: E402
from writing_coach.persistence.platform_repository import (  # noqa: E402
    PlatformRepository,
    PostgresPlatformRepository,
)


class CapabilityPreflightError(RuntimeError):
    pass


def require_postgresql_runtime() -> None:
    backend = os.getenv("PERSISTENCE_BACKEND", "").strip().casefold()
    if backend != "postgresql":
        raise CapabilityPreflightError(
            "PERSISTENCE_BACKEND must be postgresql for AI capability preflight."
        )


def postgres_repository() -> PostgresPlatformRepository:
    require_postgresql_runtime()
    try:
        return PostgresPlatformRepository(create_runtime_engine())
    except Exception as exc:
        raise CapabilityPreflightError(
            "Could not create the PostgreSQL runtime repository."
        ) from exc


def validate_persisted_capabilities(repository: PlatformRepository) -> dict[str, Any]:
    """Validate explicit rows only; ai.active_selection is intentionally ignored."""

    records = repository.list_capability_configs()
    by_key = {record.capability_key: record for record in records}
    if len(by_key) != len(records):
        raise CapabilityPreflightError("Duplicate AI capability settings were returned.")

    required = {definition.key for definition in activation_capabilities()}
    missing = sorted(required - set(by_key))
    if missing:
        raise CapabilityPreflightError(
            f"Missing explicit AI capability settings: {missing!r}."
        )

    forbidden: list[str] = []
    for key, record in by_key.items():
        definition = get_capability(key)
        if (
            definition is None
            or not definition.implemented
            or not definition.provider_backed
            or not definition.configurable
        ):
            forbidden.append(key)
            continue
        validate_capability_config(key, record.config)
    if forbidden:
        raise CapabilityPreflightError(
            f"Forbidden AI capability settings are present: {sorted(forbidden)!r}."
        )

    return {
        "ok": True,
        "backend": "postgresql",
        "validated_capabilities": sorted(required),
        "explicit_row_count": len(records),
        "legacy_selection_role": "live-routing-until-later-activation; not used by this preflight",
    }


def main() -> None:
    try:
        report = validate_persisted_capabilities(postgres_repository())
    except CapabilityPreflightError as exc:
        print(json.dumps({"ok": False, "backend": "postgresql", "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "backend": "postgresql",
                    "error": "PostgreSQL AI capability preflight failed.",
                },
                indent=2,
            )
        )
        raise SystemExit(1) from exc
    print(json.dumps(report, indent=2))
    print("AI capability configuration preflight PASS")


if __name__ == "__main__":
    main()
