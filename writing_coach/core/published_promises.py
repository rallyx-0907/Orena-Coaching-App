"""What the published policies promise must be in force on a public runtime (PRE-502 R1/R2, #369).

- **Bounded AI spend** (PRE-502 R2 as restated by D-251, owner 2026-10-21: no app-wide cap, only a cap per learner by
  plan). Two things must be in force: every plan's per-learner daily AI cost cap (ai/learner_cost.py, policies
  `ai.learner_cost.*`) and the system monitor's alert threshold (`AI_DAILY_SPEND_CEILING_USD`, ai/spend_gate.py), which
  alerts and never refuses. Neither is a published legal promise; this is the operating rule that no public runtime
  runs with paid AI unbounded per learner.
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
- Every public runtime refuses to start without the per-learner caps and the monitor's threshold in the environment
  (review of #428: the pilot runs like production). An Admin threshold (`ai.daily_spend_ceiling_usd`) can only lower it
  and never counts as the environment's.

The sweeps are logged rather than refused. Each is an Admin policy its variable can pin (D-172, BQ), so this reads the
variable when it is set and the policy otherwise. On a public runtime a promised sweep is ON by default and Admin can
never turn it off (policies.py `promise`, `default_for`), so only an explicit `off` pin leaves one off - an environment
decision, logged here as an ERROR. Admin's readiness summary shows the same list (`unmet_promises`). Development says nothing. No value is printed, only the names.
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


def _sweep_on(values: Mapping[str, str], policy: Callable[[str], Any], name: str, key: str) -> bool:
    """A sweep that is a policy its variable pins (BQ): the variable when it is set, else the policy's value - the
    precedence `policies.value` applies, read from the environment this check was given."""
    if str(values.get(name, "")).strip():
        return _switch_on(values, name)
    return _policy_on(policy, key)


def _ceiling_in_force(values: Mapping[str, str], policy: Callable[[str], Any]) -> bool:
    """The monitor's threshold is the environment's (review of #428): Admin's `ai.daily_spend_ceiling_usd` can only lower
    it and can be cleared at any time, so an Admin value alone never counts."""
    return _ceiling_set(values)


def _learner_caps_missing(policy: Callable[[str], Any]) -> list[str]:
    """The plans (or the hard ratio) without a usable per-learner daily AI cost cap (D-251)."""
    from writing_coach.ai.learner_cost import configured_problems

    try:
        return configured_problems(policy)
    except Exception:  # noqa: BLE001 - unreadable is not configured
        return ["unreadable"]


def unmet_promises(values: Mapping[str, str], policy: Callable[[str], Any]) -> list[UnmetPromise]:
    """The published promises not in force with this environment and these policy values (`policy(key)`)."""

    from writing_coach.agent.api import agent_enabled
    from writing_coach.agent.memory_runtime import MEMORY_SWEEP_SWITCH

    problems: list[UnmetPromise] = []
    if not _ceiling_in_force(values, policy):
        problems.append(UnmetPromise("spend_ceiling_unset",
                                     "AI_DAILY_SPEND_CEILING_USD is not set: the system daily AI spend monitor has no"
                                     " alert threshold"))
    missing = _learner_caps_missing(policy)
    if missing:
        problems.append(UnmetPromise("learner_cost_caps_unset",
                                     "no per-learner daily AI cost cap for: " + ", ".join(missing)))
    from writing_coach.account_backbone import requested as backbone_requested

    # Orena Memory exists only with its keys and the account backbone (MemoryRuntime.from_env); not otherwise.
    memory = bool(str(values.get("AGENT_MEMORY_HMAC_KEYS", "")).strip()) and backbone_requested(values)
    if memory and not _sweep_on(values, policy, MEMORY_SWEEP_SWITCH, "agent.memory_retention_sweep"):
        problems.append(UnmetPromise("memory_retention_sweep_off",
                                     f"{MEMORY_SWEEP_SWITCH} is off: unused Orena Memory notes are hidden after 180 days"
                                     " but not deleted, as the Privacy Policy states"))
    if agent_enabled(values) and not _policy_on(policy, "agent.turn_retention_sweep"):
        problems.append(UnmetPromise("agent_turn_retention_sweep_off",
                                     "agent.turn_retention_sweep is off: agent activity is kept past the 90 days the"
                                     " Privacy Policy states"))
    from writing_coach.persistence.retention_sweeps import ADMIN_AUDIT_SWEEP_SWITCH, USAGE_SWEEP_SWITCH

    if not _sweep_on(values, policy, USAGE_SWEEP_SWITCH, "usage.retention_sweep"):
        problems.append(UnmetPromise("usage_retention_sweep_off",
                                     f"{USAGE_SWEEP_SWITCH} is off: usage counts are kept past the 12 months the Privacy"
                                     " Policy states"))
    if not _sweep_on(values, policy, ADMIN_AUDIT_SWEEP_SWITCH, "admin_audit.retention_sweep"):
        problems.append(UnmetPromise("admin_audit_retention_sweep_off",
                                     f"{ADMIN_AUDIT_SWEEP_SWITCH} is off: records of administrative actions are kept past"
                                     " the 24 months the Privacy Policy states"))
    if not _policy_on(policy, "feedback.retention_sweep"):
        problems.append(UnmetPromise("feedback_retention_sweep_off",
                                     "feedback.retention_sweep is off: feedback is kept past the 24 months the Privacy"
                                     " Policy states"))
    return problems


def enforce_at_start(values: Mapping[str, str], policy: Callable[[str], Any]) -> list[UnmetPromise]:
    """At start. A public runtime logs each unmet promise as an ERROR and refuses to start without the per-learner AI
    cost caps and the environment's monitor threshold (production and staging alike, D-251). Development returns nothing
    and logs nothing."""

    app_env = environment_name(values.get("APP_ENV", "development"))
    if not is_public_environment(app_env):
        return []
    problems = unmet_promises(values, policy)
    for problem in problems:
        _log.error("published promise not in force (%s): %s", problem.code, problem.message)
    missing = _learner_caps_missing(policy)
    if missing:  # D-251: never a public runtime with paid AI unbounded per learner
        raise RuntimeError(f"A per-learner daily AI cost cap is required for every plan when APP_ENV={app_env} "
                           f"(D-251, PRE-502 R2); missing: {', '.join(missing)}.")
    if not _ceiling_set(values):  # the monitor's threshold, whatever Admin holds; staging runs like production
        raise RuntimeError(f"AI_DAILY_SPEND_CEILING_USD (the spend monitor's alert threshold) is required when "
                           f"APP_ENV={app_env} (D-251, PRE-502 R2).")
    return problems
