"""What the published policies promise must be in force on a public runtime (PRE-502 R1/R2, #369).

- **The system daily AI spend ceiling** (owner, 2026-10-18: $5 a day, ai/spend_gate.py). Unset means no ceiling at all,
  so paid AI spend is unbounded.
- **The retention sweeps behind the periods the Privacy Policy states** (docs/legal/public/privacy.en.json, facts.json):
  - Orena Memory: unused notes deleted after 180 days (`AGENT_MEMORY_RETENTION_SWEEP`);
  - agent activity: 90 days (`agent.turn_retention_sweep`);
  - feedback: 24 months (`feedback.retention_sweep`);
  - usage counts: 12 months (`USAGE_RETENTION_SWEEP`); records of administrative actions: 24 months
    (`ADMIN_AUDIT_RETENTION_SWEEP`) (PRE-502 R8).
  Each is deletion, so each defaults off and is switched on by the owner (D-172). While one is off, the stated period
  is not kept.

A promise about data the runtime does not keep is not unmet: no memory keys means no Orena Memory, and the agent off
means no agent.turn row. (Memory is counted when its keys are set and the backbone is
requested; a backbone that then fails to start makes the item an over-report, never a miss.)

`enforce_at_start`:
- On a public runtime (staging, production), it logs each unmet promise as an ERROR.
- Production also refuses to start without a ceiling.

The sweeps are logged rather than refused (two are Admin-tunable at runtime, D-172; the others are env-only). Admin's readiness summary shows the
same list (`unmet_promises`). Development says nothing. No value is printed, only the names.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from writing_coach.core.deployment import environment_name, is_public_environment

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class UnmetPromise:
    code: str
    message: str


def _ceiling_set(values: Mapping[str, str]) -> bool:
    from writing_coach.ai.spend_gate import ceiling_from_env

    try:
        return ceiling_from_env(values) is not None
    except ValueError:  # an unparseable value is no ceiling (the app also refuses it where it installs it)
        return False


def _switch_on(values: Mapping[str, str], name: str) -> bool:
    from writing_coach.agent.retention import sweep_enabled

    try:
        return sweep_enabled(values, name)
    except ValueError:  # unclear: not on (the app refuses it where it reads it)
        return False


def _policy_on(policy: Callable[[str], Any], key: str) -> bool:
    try:
        return policy(key) is True
    except Exception:  # noqa: BLE001 - a policy that cannot be read is not known to be on
        return False


def unmet_promises(values: Mapping[str, str], policy: Callable[[str], Any]) -> list[UnmetPromise]:
    """The published promises not in force with this environment and these policy values (`policy(key)`)."""

    from writing_coach.agent.api import agent_enabled
    from writing_coach.agent.memory_runtime import MEMORY_SWEEP_SWITCH

    problems: list[UnmetPromise] = []
    if not _ceiling_set(values):
        problems.append(UnmetPromise("spend_ceiling_unset",
                                     "AI_DAILY_SPEND_CEILING_USD is not set: there is no system daily AI spend ceiling"))
    from writing_coach.account_backbone import requested as backbone_requested

    # Orena Memory exists only with its keys and the account backbone (MemoryRuntime.from_env); not otherwise.
    memory = bool(str(values.get("AGENT_MEMORY_HMAC_KEYS", "")).strip()) and backbone_requested(values)
    if memory and not _switch_on(values, MEMORY_SWEEP_SWITCH):
        problems.append(UnmetPromise("memory_retention_sweep_off",
                                     f"{MEMORY_SWEEP_SWITCH} is off: unused Orena Memory notes are hidden after 180 days"
                                     " but not deleted, as the Privacy Policy states"))
    if agent_enabled(values) and not _policy_on(policy, "agent.turn_retention_sweep"):
        problems.append(UnmetPromise("agent_turn_retention_sweep_off",
                                     "agent.turn_retention_sweep is off: agent activity is kept past the 90 days the"
                                     " Privacy Policy states"))
    from writing_coach.persistence.retention_sweeps import ADMIN_AUDIT_SWEEP_SWITCH, USAGE_SWEEP_SWITCH

    if not _switch_on(values, USAGE_SWEEP_SWITCH):
        problems.append(UnmetPromise("usage_retention_sweep_off",
                                     f"{USAGE_SWEEP_SWITCH} is off: usage counts are kept past the 12 months the Privacy"
                                     " Policy states"))
    if not _switch_on(values, ADMIN_AUDIT_SWEEP_SWITCH):
        problems.append(UnmetPromise("admin_audit_retention_sweep_off",
                                     f"{ADMIN_AUDIT_SWEEP_SWITCH} is off: records of administrative actions are kept past"
                                     " the 24 months the Privacy Policy states"))
    if not _policy_on(policy, "feedback.retention_sweep"):
        problems.append(UnmetPromise("feedback_retention_sweep_off",
                                     "feedback.retention_sweep is off: feedback is kept past the 24 months the Privacy"
                                     " Policy states"))
    return problems


def enforce_at_start(values: Mapping[str, str], policy: Callable[[str], Any]) -> list[UnmetPromise]:
    """At start. A public runtime logs each unmet promise as an ERROR, and production refuses to start without a
    ceiling. Development returns nothing and logs nothing."""

    app_env = environment_name(values.get("APP_ENV", "development"))
    if not is_public_environment(app_env):
        return []
    problems = unmet_promises(values, policy)
    for problem in problems:
        _log.error("published promise not in force (%s): %s", problem.code, problem.message)
    if app_env == "production" and any(p.code == "spend_ceiling_unset" for p in problems):
        raise RuntimeError("AI_DAILY_SPEND_CEILING_USD is required when APP_ENV=production (PRE-502 R2).")
    return problems
