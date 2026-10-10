"""Target languages: a count cap enforced where an account gets one (D-16R).

`languages.target` is an entitlement of the plan catalogue (catalogue v2: Free / Plus / Pro 1 / 2 / 2, editable by an
administrator), not a bucket: it has no window, no reservation and nothing to settle. The rule, on the server only:

  * An account HOLDS the target languages `writing_coach.persistence.language_ownership` finds in its data: its stored
    learning language and every row it owns that is scoped to a language. A client never declares it.
  * ADDING a language the account does not hold, when it already holds the plan's limit or more, is refused:
    403 `language_limit_reached` with the limit, how many it holds, the plan and the way to the plans. Nothing is
    stored; the session language is not changed.
  * SWITCHING to a language the account already holds is always allowed - after a downgrade from 2 to 1 both
    languages stay switchable, and nothing is ever deleted. Only adding a third is refused.
  * The limit is read at the moment of the mutation from the catalogue (strict) and the account's effective plan, so an
    administrator's plan or catalogue change applies at once (the catalogue's own 5 s cache, `CACHE_SECONDS`, is the
    only delay). When the catalogue or the plan cannot be read, ADDING fails closed (503 `quota_unavailable`);
    switching to a language the account holds needs neither and still works.
  * When the store that holds the account's data cannot answer (no PostgreSQL, the switch unreadable), the server
    cannot tell a language the account holds from a new one, so it fails closed for every selection (503), like
    every other enforced entitlement.
  * The check and the write happen in one transaction with the account row locked
    (`PostgresAuthRepository.update_account_settings(guard=...)`), so two concurrent additions of different new
    languages at limit - 1 admit one and refuse the other.

Off (the default; see `quota.switch()`), or `languages.target` not listed: nothing here runs and the routes behave as they
did before.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

from writing_coach.core.errors import error_detail
from writing_coach.core.language_registry import is_enabled
from writing_coach.product import quota
from writing_coach.product.catalog import CatalogUnavailable, current_catalog

_log = logging.getLogger(__name__)

ENTITLEMENT = "languages.target"
CATEGORY = "language_limit_reached"
UPGRADE_HREF = quota.UPGRADE_HREF

_ownership: Any | None = None   # PostgresLanguageOwnership: held(user_key) -> set[str]


def configure(ownership: Any | None) -> None:
    """Installed by the app when the runtime is PostgreSQL with the quota store; None elsewhere (enforcement then
    answers 503, never "unlimited")."""
    global _ownership
    _ownership = ownership


class EntitlementRefusal(HTTPException):
    """A refusal of the target-language entitlement (403 / 503), distinguishable from the routes' own conflicts."""


def _refusal(error: HTTPException) -> EntitlementRefusal:
    return EntitlementRefusal(error.status_code, detail=error.detail, headers=error.headers)


def enforced() -> bool:
    return quota.enforces(ENTITLEMENT)


def _unavailable(reason: str) -> EntitlementRefusal:
    return _refusal(quota._unavailable(reason))


def held_by(user_key: str) -> set[str]:
    """The enabled target languages the account holds (unlocked read; Plan & usage and the switch's pre-check)."""
    if _ownership is None:
        raise RuntimeError("No language ownership store on this deployment.")
    return _enabled(_ownership.held(user_key))


def _enabled(codes: set[str]) -> set[str]:
    """Only languages the product offers count: a code the registry no longer enables cannot be learned."""
    return {code for code in codes if is_enabled(code)}


def _limit(user_key: str) -> tuple[int | None, str]:
    """(limit, plan id) from the strict catalogue and the account's effective plan, or the 403 / 503 of the gate."""
    runtime = quota.runtime()
    try:
        plans, _revision = current_catalog(strict=True)
        plan = plans.get(runtime.plan_for(user_key, strict=True).id)
        if plan is None:
            raise CatalogUnavailable("the effective plan is not in the catalogue snapshot")
    except CatalogUnavailable as error:
        raise _unavailable("catalogue") from error
    except HTTPException:
        raise
    except Exception as error:
        raise _unavailable("subscription") from error
    entitlement = plan.entitlement_map().get(ENTITLEMENT)
    if entitlement is None or not entitlement.enabled:
        raise EntitlementRefusal(403, detail=error_detail(
            "feature_not_in_plan", "This feature is not part of your plan.", retryable=False,
            context={"feature": ENTITLEMENT, "plan": plan.id, "upgrade": UPGRADE_HREF}))
    return entitlement.limit, plan.id


class Adoption:
    """One account's attempt to take `target` as its learning language, under an enforced entitlement.

    The plan's limit is read when the adoption is made - before the account row is locked, so no pooled connection is
    taken for the catalogue or the subscription while it is (review F6). A failed read is kept and raised only if the
    write turns out to ADD a language: switching to one the account holds needs no limit."""

    def __init__(self, target: str, user_key: str) -> None:
        self.target = target
        self.user_key = user_key
        self._limit: tuple[int | None, str] | None = None
        self._unreadable: HTTPException | None = None
        try:
            self._limit = _limit(user_key)
        except HTTPException as error:
            self._unreadable = error

    def holds(self) -> bool:
        """True when the account already holds the target (an unlocked read; the guard re-judges under the lock)."""
        try:
            return self.target in held_by(self.user_key)
        except Exception as error:
            raise _unavailable("store") from error

    def guard(self, owned: set[str]) -> None:
        """Judge the write, inside its transaction, against the languages the account holds."""
        held = _enabled(owned)
        if self.target in held:
            return                      # switching among languages already held: always allowed
        if self._limit is None:
            raise self._unreadable
        limit, plan_id = self._limit
        if limit is None or len(held) < limit:
            return
        raise EntitlementRefusal(403, detail=error_detail(
            CATEGORY,
            f"Your plan includes {limit} target language{'s' if limit != 1 else ''}, and you already learn "
            f"{len(held)}. Choose one you already learn, or see the plans.",
            retryable=False,
            context={"feature": ENTITLEMENT, "limit": limit, "owned": len(held), "languages": sorted(held),
                     "plan": plan_id, "upgrade": UPGRADE_HREF}))


def adoption(target: str, user_key: str) -> Adoption | None:
    """None when the entitlement is not enforced (the caller proceeds exactly as before). Otherwise the adoption to
    judge; 503 `quota_unavailable` right here when enforcement cannot run at all (no store, switch unreadable)."""
    state = quota.switch()
    if ENTITLEMENT not in state["meters"]:
        return None
    if state["state"] == "unavailable" or _ownership is None:
        raise _unavailable(state["reason"] or "store")
    return Adoption(target, user_key)

