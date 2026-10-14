"""Read-only, static pre-activation gate for capability learner routing."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_ai_capability_control_plane import (  # noqa: E402
    CapabilityPreflightError,
    postgres_repository,
    require_postgresql_runtime,
    validate_persisted_capabilities,
)
from writing_coach.ai.base import AICapabilityError  # noqa: E402
from writing_coach.ai.capabilities import (  # noqa: E402
    AIFallbackPolicy,
    activation_capabilities,
)
from writing_coach.ai.platform import AIRuntimeMode, runtime_mode  # noqa: E402
from writing_coach.persistence.platform_repository import (  # noqa: E402
    CapabilityConfigRecord,
    PlatformRepository,
)

_GATE = "ai-capability-runtime-activation"
_DETERMINISTIC_FALLBACK_CAPABILITIES = frozenset(
    {"reading_generator", "writing_task_generator", "grammar_lesson_generator"}
)


class ActivationReadinessError(RuntimeError):
    """A safe, actionable failure of the static activation-readiness contract."""


class _CapabilitySnapshot:
    """Expose one immutable repository read to the existing static preflight."""

    def __init__(self, records: list[CapabilityConfigRecord]) -> None:
        self.records = records

    def list_capability_configs(self) -> list[CapabilityConfigRecord]:
        return list(self.records)


def validate_activation_readiness(repository: PlatformRepository) -> dict[str, Any]:
    """Validate pre-activation state without writes, provider construction, or network."""

    require_postgresql_runtime()
    try:
        mode = runtime_mode()
    except AICapabilityError as exc:
        raise ActivationReadinessError("Current AI runtime mode is invalid.") from exc
    if mode is not AIRuntimeMode.LEGACY:
        raise ActivationReadinessError(
            "Pre-activation readiness requires current AI runtime mode legacy."
        )

    try:
        records = repository.list_capability_configs()
        preflight = validate_persisted_capabilities(_CapabilitySnapshot(records))
    except CapabilityPreflightError as exc:
        raise ActivationReadinessError(str(exc)) from exc
    except AICapabilityError as exc:
        raise ActivationReadinessError("AI capability configuration is invalid.") from exc

    required = {definition.key for definition in activation_capabilities()}
    # Opt-in capabilities (word_translation) ship disabled and are not part of this gate.
    gated = [record for record in records if record.capability_key in required]
    disabled = sorted(record.capability_key for record in gated if not record.config.enabled)
    if disabled:
        raise ActivationReadinessError(
            f"Disabled AI capability settings prevent activation: {disabled!r}."
        )

    fallback = {
        record.capability_key
        for record in gated
        if record.config.fallback_policy is AIFallbackPolicy.DETERMINISTIC_FALLBACK
    }
    if fallback != _DETERMINISTIC_FALLBACK_CAPABILITIES:
        raise ActivationReadinessError(
            "Deterministic fallback policy must match the approved capability set."
        )

    return {
        "ok": True,
        "gate": _GATE,
        "current_mode": AIRuntimeMode.LEGACY.value,
        "target_mode": AIRuntimeMode.CAPABILITY.value,
        "rollback_mode": AIRuntimeMode.LEGACY.value,
        "backend": preflight["backend"],
        "validated_capabilities": sorted(required),
        "capability_count": len(required),
        "static_validation": "pass",
        "live_validation": "not_executed",
        "requires_human_activation": True,
        "rollback_preserves_capability_config": True,
    }


def main() -> None:
    try:
        report = validate_activation_readiness(postgres_repository())
    except (ActivationReadinessError, CapabilityPreflightError) as exc:
        print(json.dumps({"ok": False, "gate": _GATE, "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "gate": _GATE,
                    "error": "AI runtime activation readiness validation failed.",
                },
                indent=2,
            )
        )
        raise SystemExit(1) from exc
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
