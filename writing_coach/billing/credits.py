"""Prepaid credits (PR-MON-4, D-MON-002, D-MON-019..021): the service over the credit ledger.

Off unless `CREDITS_ENABLED` is on, and even then every operation is refused while the database connection could
defeat the ledger's write boundary (`credit_runtime_privileges`, design §2.1): a superuser, a role with BYPASSRLS, an
owner of the credit tables or schema, a member of `orena_credit_owner`, or any role holding a privilege that would
let it rewrite a balance or history. The runtime must connect as a non-superuser member of `orena_credit_runtime`
before credits are enabled (a deployment gate).

There is no conversion to money, no meter price, no Free allowance and no auto top-up here (human gates), and no
provider is called. Top-up from a payment is PR-MON-5; consumption (reserve, dispatch, settle) is PR-MON-6.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from typing import Any

from writing_coach.persistence.credit_repository import CreditOutcome

_log = logging.getLogger(__name__)
_ON = frozenset({"1", "true", "yes", "on"})
PRIVILEGE_CACHE_SECONDS = 60.0


def credits_enabled(env: Mapping[str, str]) -> bool:
    return str(env.get("CREDITS_ENABLED", "")).strip().casefold() in _ON


class CreditService:
    def __init__(self, repository: Any, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._repository = repository
        self._clock = clock
        self._checked: tuple[float, list[str]] | None = None

    @property
    def repository(self) -> Any:
        return self._repository

    def privilege_violations(self) -> list[str]:
        """The connected role's boundary-defeating privileges (empty = safe), kept a minute; unreadable = unsafe."""

        now = self._clock()
        if self._checked is not None and self._checked[0] > now:
            return self._checked[1]
        try:
            violations = list(self._repository.runtime_privilege_violations())
        except Exception:  # noqa: BLE001 - a boundary that cannot be checked is not a boundary
            _log.warning("credits: the runtime privilege check failed; credits are refused", exc_info=True)
            violations = ["privilege_check_failed"]
        self._checked = (now + PRIVILEGE_CACHE_SECONDS, violations)
        if violations:
            _log.warning("credits refused: the database role can defeat the ledger boundary (%s)", ", ".join(violations))
        return violations

    def status(self) -> dict[str, Any]:
        violations = self.privilege_violations()
        return {"runtime_privileges": "ok" if not violations else "privileged", "violations": violations,
                "ready": not violations}

    def _guarded(self, operation: str, *args: Any, **kwargs: Any) -> CreditOutcome:
        if self.privilege_violations():
            return CreditOutcome("credits_runtime_privileged")
        return getattr(self._repository, operation)(*args, **kwargs)

    # ---- the operations (each one transaction in the repository) ---------------------------------------------

    def ensure_account(self, incarnation_id: str) -> dict[str, Any] | None:
        if self.privilege_violations():
            return None
        return self._repository.ensure_account(incarnation_id)

    def topup(self, incarnation_id: str, **kwargs: Any) -> CreditOutcome:
        return self._guarded("topup", incarnation_id, **kwargs)

    def reserve(self, incarnation_id: str, **kwargs: Any) -> CreditOutcome:
        return self._guarded("reserve", incarnation_id, **kwargs)

    def settle(self, incarnation_id: str, **kwargs: Any) -> CreditOutcome:
        return self._guarded("settle", incarnation_id, **kwargs)

    def release(self, incarnation_id: str, **kwargs: Any) -> CreditOutcome:
        return self._guarded("release", incarnation_id, **kwargs)

    def refund(self, incarnation_id: str, **kwargs: Any) -> CreditOutcome:
        return self._guarded("refund", incarnation_id, **kwargs)

    def reverse(self, incarnation_id: str, **kwargs: Any) -> CreditOutcome:
        return self._guarded("reverse", incarnation_id, **kwargs)

    def adjust(self, incarnation_id: str, **kwargs: Any) -> CreditOutcome:
        return self._guarded("adjust", incarnation_id, **kwargs)

    def balance(self, incarnation_id: str) -> dict[str, Any] | None:
        return self._repository.account(incarnation_id)

    def entries(self, incarnation_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        return self._repository.entries(incarnation_id, **kwargs)

    # ---- the reconciler's step (PR-MON-3's tick, its lock, short transactions) ---------------------------------

    def reconcile(self, *, items: Any, now: Any, limit: int = 200) -> dict[str, int]:
        """Close holds past their `expires_at` (and every hold of a deleted account), record the liability of a
        deleted account's credit (C1), and detect drift - an incident, never repaired by hand."""

        counts = {"holds_closed": 0, "deletion_liabilities": 0, "drift": 0, "drift_resolved": 0}
        if self.privilege_violations():
            counts["refused_privileged"] = 1
            return counts
        for hold in self._repository.holds_to_close(now=now, limit=limit):
            outcome = self._repository.expire_reserve(hold["incarnation_id"], reserve_entry_id=hold["reserve_entry_id"])
            counts["holds_closed"] += int(outcome.status == "applied")
        for row in self._repository.deleted_with_balance(limit=limit):
            self._repository.record_deletion_liability(row)
            counts["deletion_liabilities"] += 1
        drifting = self._repository.drift()
        for row in drifting:
            self._repository.record_drift(row)
            counts["drift"] += 1
        still = {str(row["credit_account_id"]) for row in drifting}
        for account_id in self._repository.open_drift_accounts():
            if account_id not in still and items.auto_resolve(
                    kind="credit_balance_drift", gateway="credits", dedupe_key=account_id,
                    outcome="balance_consistent", note="the snapshot equals the ledger again"):
                counts["drift_resolved"] += 1
        return counts
