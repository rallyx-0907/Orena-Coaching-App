"""An account's role and plan, set by hand by a platform administrator (human, 2026-10-09, D-154).

1. **Role** (`users.role`): `user` (learner) or `admin` (Platform Admin). Guards: an administrator never changes their
   own role (no self-lockout), and an address in `PLATFORM_ADMIN_EMAILS` cannot be made a learner here - sign-in would
   make it an administrator again, so the change would not hold.
2. **Plan**: a `manual` subscription (`provider="manual"`, status `active`) on the account's subscription row, optionally
   until a date; when the date passes the account reads as Free again, with nothing to run. Setting Free removes the
   manual subscription. A subscription another provider owns (billing) is never overwritten by hand.

Both apply from the moment they are saved and each change writes an audit row. No new table: the existing `users`,
`subscriptions` and `plans` rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from writing_coach.product.catalog import PLANS

MANUAL_PROVIDER = "manual"
ROLES: tuple[str, ...] = ("user", "admin")


class MembershipInvalid(ValueError):
    """An administrator's change that cannot be applied (HTTP 422)."""


class MembershipConflict(ValueError):
    """A change the account's current state refuses (HTTP 409)."""


class MembershipStore(Protocol):
    def account_membership(self, user_id: str) -> dict | None: ...
    def apply_membership(self, user_id: str, *, role: str | None = None, plan: object = ..., until: datetime | None = None,
                         audit: dict | None = None) -> None: ...


def parse_until(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise MembershipInvalid("The end date must be an ISO date or date-time.") from error
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    if moment <= datetime.now(timezone.utc):
        raise MembershipInvalid("The end date must be in the future.")
    return moment


def manual_expired(subscription: object, *, now: datetime | None = None) -> bool:
    """A manual subscription whose end date has passed (the account reads as Free)."""
    if str(getattr(subscription, "provider", "") or "") != MANUAL_PROVIDER:
        return False
    raw = str(getattr(subscription, "current_period_end", "") or "")
    if not raw:
        return False
    try:
        end = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return end <= (now or datetime.now(timezone.utc))


def validate_role(role: object) -> str:
    value = str(role or "").strip().casefold()
    if value not in ROLES:
        raise MembershipInvalid(f"Unknown role {value!r}.")
    return value


def validate_plan(plan_id: object) -> str:
    value = str(plan_id or "").strip().casefold()
    if value not in PLANS:
        raise MembershipInvalid(f"Unknown plan {value!r}.")
    return value


def apply_change(
    store: MembershipStore,
    user_id: str,
    change: dict,
    *,
    actor_key: str,
    protected_emails: set[str],
) -> dict:
    """Validate and apply {role?, plan_id?, until?} to one account; returns the account's membership after it."""
    account = store.account_membership(user_id)
    if account is None:
        raise LookupError("No account has this identifier.")
    if not isinstance(change, dict):
        raise MembershipInvalid("The change must be an object.")
    # Everything is checked before anything is written: a refused change leaves the account exactly as it was.
    role = None
    if "role" in change:
        role = validate_role(change.get("role"))
        if role == account["role"]:
            role = None
        elif account["user_key"] == actor_key:
            raise MembershipConflict("You cannot change your own role.")
        elif role != "admin" and str(account.get("email") or "").casefold() in protected_emails:
            raise MembershipConflict("This address is a configured platform administrator; it stays an administrator.")
    plan_id = until = None
    set_plan = "plan_id" in change
    if set_plan:
        plan_id = validate_plan(change.get("plan_id"))
        provider = str(account.get("provider") or "")
        if provider and provider != MANUAL_PROVIDER and account.get("status") in {"active", "trialing"}:
            raise MembershipConflict("This account's plan is managed by billing; it cannot be set by hand.")
        until = None if plan_id == "free" else parse_until(change.get("until"))
    applied: dict = {}
    if role is not None:
        applied["role"] = role
    if set_plan:
        applied["plan_id"] = plan_id
        applied["until"] = until.isoformat() if until else None
    if applied:
        # One transaction: role, plan and the audit row commit together; the store re-checks billing under its lock.
        store.apply_membership(
            user_id, role=role, plan=(None if plan_id == "free" else plan_id) if set_plan else ..., until=until,
            audit={"action": "product.account.membership", "actor": actor_key, "entity_type": "account",
                   "entity_id": str(user_id), "payload": applied},
        )
    return {"applied": applied, "account": store.account_membership(user_id)}
