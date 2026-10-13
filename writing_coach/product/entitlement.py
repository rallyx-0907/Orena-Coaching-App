"""The account's effective entitlement: one decision every reader of "which plan is this account on" derives from
(PR-MON-1, D-MON-006).

Two records can name a plan:

* **billing** - `commerce_subscriptions`, written only from verified provider events (`writing_coach.billing`,
  `persistence/commerce_repository.record_event`): a Polar subscription or the payOS prepaid state
  `prepaid:<incarnation>`;
* **manual / legacy** - the `subscriptions` row: a plan an administrator set by hand (`provider="manual"`, D-154) or
  an older provider row.

Precedence, explicit and tested (`tests/test_effective_entitlement.py`):

1. a **valid billing grant**: state `active` or `trialing`, and `paid_through` absent or still in the future. The
   commerce architecture (§3) makes a verified grant usable only until its explicit validity boundary, so a passed
   `paid_through` reads as `ended`; outages do not extend it.
2. a **valid manual / legacy subscription**: active or trialing, and not a manual grant past its end date - the rule
   that applied before this module, unchanged.
3. **Free**.

Billing outranks a manual grant because D-154 says a subscription billing owns is never overridden by hand; no Admin
override of a paid entitlement exists (a future support override is a separate break-glass mechanism, D-MON-010).

A billing subscription in a recoverable state keeps its plan only inside the grace the policy gives that provider and
state, counted from its `paid_through` (D-MON-011: Polar `past_due`, 2 days). Outside it - and for `paused`,
`pending`, `unknown`, which have no approved policy (§3: missing policy blocks paid admissions) - it grants nothing
and falls through to 2. The reported status stays the billing one, so the account does not read as "no
subscription", and the account stays billing-owned. A past-due subscription with no `paid_through` has no anchor, so
no grace. The placeholder row `state='none'`, placed before any event is decided, is no subscription at all.

`resolve` is pure: the two rows, the clock and the grace policy in, the decision out; it knows no grace number
(`writing_coach.product.billing_grace` does). `ProductService` does the reads.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from collections.abc import Mapping
from typing import Any, Protocol

from writing_coach.product.billing_grace import NO_GRACE, GracePolicy
from writing_coach.product.catalog import DEFAULT_PLAN_ID, Plan, known_plan_id, plan_by_id
from writing_coach.product.membership import manual_expired

GRANTING = frozenset({"active", "trialing"})
# A billing subscription that still owns the account (an Admin cannot set its plan by hand), as the billing service
# counts "one live subscription per account" (`writing_coach.billing.service._LIVE`).
LIVE = frozenset({"active", "trialing", "past_due", "paused", "pending"})
_ABSENT = "none"


class BillingEntitlementSource(Protocol):
    def subscription_for_user(self, user_key: str) -> Mapping[str, Any] | None:
        """The account's current `commerce_subscriptions` row (its active incarnation's), or None."""


class CommerceEntitlementSource:
    """The billing record on PostgreSQL: the account's (`stable_uuid("user", user_key)`, as quota keys it) active
    incarnation's `commerce_subscriptions` row, one query (`PostgresCommerceRepository.subscription_for_account`)."""

    def __init__(self, commerce: Any) -> None:
        self._commerce = commerce

    def subscription_for_user(self, user_key: str) -> Mapping[str, Any] | None:
        if not user_key:
            return None
        from writing_coach.persistence.ids import stable_uuid

        return self._commerce.subscription_for_account(str(stable_uuid("user", user_key)))


@dataclass(frozen=True)
class EffectiveEntitlement:
    """`plan_id` is the deciding record's plan as stored (casefolded), `free` when nothing grants. `source` is
    `billing`, `manual`, `legacy` or `none`. `status` is what the Plan screen reports. `billing_live`: a billing
    subscription owns the account, whether or not it grants a plan right now."""

    plan_id: str
    source: str
    status: str
    active: bool
    billing_live: bool = False
    valid_until: datetime | None = None
    reconciliation: str = "none"

    @property
    def plan_known(self) -> bool:
        return known_plan_id(self.plan_id)

    def plan(self, *, strict: bool = False) -> Plan:
        """The catalogue plan this entitlement admits as; an unknown plan id admits as Free."""
        return plan_by_id(self.plan_id if self.active else DEFAULT_PLAN_ID, strict=strict)


def _text(value: Any) -> str:
    return str(value or "").strip().casefold()


def _moment(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        moment = value
    else:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _billing_grant(row: Mapping[str, Any], now: datetime, grace: GracePolicy) -> tuple[str, datetime | None, bool]:
    """(effective state, valid until, grants now). A granting state past its `paid_through` has ended; a recoverable
    state grants until `paid_through` + its grace, and only with a `paid_through` to count from."""
    state = _text(row.get("state")) or "unknown"
    until = _moment(row.get("paid_through"))
    if state in GRANTING:
        if until is not None and until <= now:
            return "ended", until, False
        return state, until, True
    window = grace.window(_text(row.get("provider")), state)
    if window is not None and until is not None:
        grace_end = until + window
        return state, grace_end, grace_end > now
    return state, until, False


def resolve(*, legacy: object | None, billing: Mapping[str, Any] | None, now: datetime,
            grace: GracePolicy = NO_GRACE) -> EffectiveEntitlement:
    """The effective entitlement from the legacy row, the billing row, the clock and the grace policy (module
    docstring). Without a grace policy no recoverable state grants."""
    billing_status = None
    billing_live = False
    if billing is not None and _text(billing.get("state")) != _ABSENT:
        state, until, grants = _billing_grant(billing, now, grace)
        billing_live = state in LIVE
        reconciliation = _text(billing.get("reconciliation_state")) or "current"
        if grants:
            return EffectiveEntitlement(_text(billing.get("plan_id")) or DEFAULT_PLAN_ID, "billing", state, True,
                                        billing_live=True, valid_until=until, reconciliation=reconciliation)
        billing_status = state

    if legacy is not None:
        status = _text(getattr(legacy, "status", ""))
        if status in GRANTING and not manual_expired(legacy, now=now):
            source = "manual" if str(getattr(legacy, "provider", "") or "") == "manual" else "legacy"
            return EffectiveEntitlement(_text(getattr(legacy, "plan_id", "")) or DEFAULT_PLAN_ID, source, status, True,
                                        billing_live=billing_live, valid_until=_moment(getattr(legacy, "current_period_end", None)))
        legacy_status = status or "unknown"
    else:
        legacy_status = "inactive"
    return EffectiveEntitlement(DEFAULT_PLAN_ID, "none", billing_status or legacy_status, False, billing_live=billing_live)
