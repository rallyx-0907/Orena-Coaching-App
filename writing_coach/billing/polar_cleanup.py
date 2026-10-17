"""Polar customer clean-up of a deleted account (PR-MON-10 §4.8, design revision 3.1).

Orena's incarnation is Polar's `external_customer_id` (owner Q4). When an incarnation is deleted, its Polar customer
must be deleted and anonymized: no further charge, no benefit, no personal data. The clean-up is an obligation of
the **deleted incarnation**, never of a subscription:

* **Discovery is derived, so it cannot be lost.** Every incarnation with `status = 'deleted'` and no `complete`
  marker is an obligation - with no condition on Polar orders or mappings, which a restore to an older backup can
  drop (review P1 of b99715c4). The deletion journal reapplies a deletion before anything is served (D-054), and this
  rule finds the obligation again. An incarnation that never used Polar costs one DELETE answered 404.
* **Completion is a separate durable marker**, one `platform_settings` row per incarnation
  (`billing.polar.customer_cleanup.<id>`, compare-and-set like the SePay feed cursor), written `complete` only on 204
  or 404 and never inferred from a commerce state. A lost marker only re-runs the DELETE, which answers 404.
* **Retry and escalation.** Any other answer, or a timeout, keeps the marker `pending` with a back-off; past
  `ESCALATE_AFTER` from the first attempt one operator item is raised (`event_undecided`, reason
  `polar_customer_cleanup_failed`) and the retries continue. The item is resolved when the marker completes.
* **Without Polar** (no token) nothing is called; the obligations stay pending, counted and not escalated.

The marker holds no personal data and no Polar response body.
"""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

_log = logging.getLogger(__name__)
KEY_PREFIX = "billing.polar.customer_cleanup."
ESCALATE_AFTER = timedelta(hours=24)
MAX_BACKOFF = timedelta(hours=6)
BATCH = 20
REASON = "polar_customer_cleanup_failed"


def marker_key(incarnation_id: str) -> str:
    return f"{KEY_PREFIX}{incarnation_id}"


def http_status(request: Mapping[str, Any]) -> int:
    """Send one bodyless provider request and answer its HTTP status (a 4xx/5xx is a status, not an exception)."""

    call = urllib.request.Request(str(request["url"]), method=str(request["method"]),
                                  headers={"Accept": "application/json", "User-Agent": "Orena-Billing/1.0",
                                           **request["headers"]})  # fmt: skip
    try:
        with urllib.request.urlopen(call, timeout=20) as response:  # noqa: S310 - the fixed Polar API host
            return int(response.status)
    except urllib.error.HTTPError as error:
        return int(error.code)


class PostgresDeletedIncarnations:
    """The derived obligation: deleted incarnations without a `complete` marker (§4.8 discovery)."""

    _PENDING = (
        "FROM account_incarnations ai LEFT JOIN platform_settings ps ON ps.key = :prefix || ai.id::text "
        "WHERE ai.status = 'deleted' AND (ps.key IS NULL OR COALESCE(ps.value->>'state', '') <> 'complete')"
    )

    def __init__(self, engine: Any) -> None:
        self._engine = engine

    def due(self, now: datetime, limit: int) -> list[str]:
        """Pending obligations whose back-off has passed, oldest deletion first."""

        with self._engine.connect() as connection:
            rows = connection.execute(text(
                f"SELECT ai.id::text {self._PENDING} AND (ps.key IS NULL OR ps.value->>'next_attempt_at' IS NULL "
                "OR (ps.value->>'next_attempt_at')::timestamptz <= :now) ORDER BY ai.deleted_at, ai.id LIMIT :limit"),
                {"prefix": KEY_PREFIX, "now": now, "limit": limit}).scalars().all()  # fmt: skip
        return [str(row) for row in rows]

    def counts(self, now: datetime) -> dict[str, int]:
        with self._engine.connect() as connection:
            row = connection.execute(text(
                "SELECT COUNT(*) AS pending, COUNT(*) FILTER (WHERE ps.value->>'first_attempt_at' IS NOT NULL "
                f"AND (ps.value->>'first_attempt_at')::timestamptz <= :cutoff) AS escalated {self._PENDING}"),
                {"prefix": KEY_PREFIX, "cutoff": now - ESCALATE_AFTER}).mappings().one()  # fmt: skip
        return {"pending": int(row["pending"]), "escalated": int(row["escalated"])}

    def pending_of_same_account(self, incarnation_id: str) -> list[str]:
        """The pending obligations of the account this incarnation belongs to (a re-registration's predecessors)."""

        with self._engine.connect() as connection:
            rows = connection.execute(text(
                f"SELECT ai.id::text {self._PENDING} AND ai.user_id = "
                "(SELECT user_id FROM account_incarnations WHERE id = CAST(:incarnation AS uuid)) "
                "AND ai.id <> CAST(:incarnation AS uuid) ORDER BY ai.deleted_at"),
                {"prefix": KEY_PREFIX, "incarnation": incarnation_id}).scalars().all()  # fmt: skip
        return [str(row) for row in rows]


class PolarCustomerCleanup:
    def __init__(self, *, gateway: Any, incarnations: Any, settings: Any, items: Any,
                 call: Callable[[Mapping[str, Any]], int] = http_status,
                 now: Callable[[], datetime] = lambda: datetime.now(UTC), batch: int = BATCH) -> None:
        self._gateway = gateway  # the PolarGateway, or None when Polar is not configured
        self._incarnations = incarnations
        self._settings = settings
        self._items = items
        self._call = call
        self._now = now
        self._batch = batch

    @property
    def configured(self) -> bool:
        return self._gateway is not None

    def counts(self) -> dict[str, int]:
        """For readiness: pending and escalated obligations. Never blocks another account's checkout."""

        return self._incarnations.counts(self._now())

    def step(self, counts: Counter[str], lock: Any = None) -> None:
        """The reconciler's step: the due obligations, oldest first, a bounded number per tick."""

        if not self.configured:
            return
        for incarnation in self._incarnations.due(self._now(), self._batch):
            if lock is not None and not lock.alive():
                return
            counts[f"polar_cleanup_{self.clean(incarnation)}"] += 1

    def run(self, limit: int = BATCH) -> dict[str, int]:
        """The operator's on-demand run (admin route): the same step, answering counts only."""

        counts: Counter[str] = Counter()
        if self.configured:
            for incarnation in self._incarnations.due(self._now(), limit):
                counts[self.clean(incarnation)] += 1
        return {"complete": counts["complete"], "pending": counts["pending"], "conflict": counts["conflict"],
                "configured": self.configured, **{f"total_{k}": v for k, v in self.counts().items()}}  # fmt: skip

    def settle_account_of(self, incarnation_id: str) -> bool:
        """Before a re-registered account's Polar checkout: its predecessors' clean-up, run inline once. True when
        none is left pending (the checkout may continue)."""

        pending = self._incarnations.pending_of_same_account(incarnation_id)
        if not pending:
            return True
        if not self.configured:
            return False
        return all(self.clean(previous) == "complete" for previous in pending)

    def clean(self, incarnation_id: str) -> str:
        """One DELETE of the incarnation's Polar customer: `complete` | `pending` | `conflict` (another writer)."""

        from writing_coach.persistence.platform_repository import SettingConflict

        stored = self._settings.get_setting(marker_key(incarnation_id))
        value = dict(stored["value"]) if stored and isinstance(stored.get("value"), dict) else {}
        version = stored["updated_at"] if stored else None
        if value.get("state") == "complete":
            return "complete"
        now = self._now()
        try:
            status = int(self._call(self._gateway.customer_delete_request(incarnation_id)))
        except Exception:  # noqa: BLE001 - a timeout or a refused connection is a retry, never a completion
            _log.warning("billing: Polar customer clean-up could not reach Polar; retried", exc_info=True)
            status = 0
        attempts = int(value.get("attempts") or 0) + 1
        first = value.get("first_attempt_at") or now.isoformat()
        if status in (204, 404):
            # 204: deleted now (subscriptions cancelled, benefits revoked, personal data anonymized); 404: none, or
            # already deleted. Only these two answers complete the obligation.
            document = {"state": "complete", "attempts": attempts, "first_attempt_at": first,
                        "last_status": status, "completed_at": now.isoformat()}  # fmt: skip
        else:
            backoff = min(timedelta(minutes=2 ** min(attempts, 10)), MAX_BACKOFF)
            document = {"state": "pending", "attempts": attempts, "first_attempt_at": first, "last_status": status,
                        "next_attempt_at": (now + backoff).isoformat(),
                        "escalated": bool(value.get("escalated"))}  # fmt: skip
        try:
            self._settings.set_setting(marker_key(incarnation_id), document, updated_by="billing-reconciler",
                                       expected_updated_at=version)  # fmt: skip
        except SettingConflict:
            return "conflict"
        if document["state"] == "complete":
            if value.get("escalated") and self._items is not None:
                self._items.auto_resolve(kind="event_undecided", gateway="polar", dedupe_key=self._dedupe(incarnation_id),
                                         outcome="recorded", note="the Polar customer clean-up completed",
                                         now=now)  # fmt: skip
            return "complete"
        if not document["escalated"] and now - datetime.fromisoformat(first) >= ESCALATE_AFTER:
            self._escalate(incarnation_id, status, now)
        return "pending"

    def _escalate(self, incarnation_id: str, status: int, now: datetime) -> None:
        from writing_coach.persistence.platform_repository import SettingConflict

        if self._items is None:
            return
        self._items.record(kind="event_undecided", gateway="polar", dedupe_key=self._dedupe(incarnation_id),
                           reason=f"{REASON} (last answer {status or 'unreachable'})", incarnation_id=incarnation_id,
                           now=now)  # fmt: skip
        stored = self._settings.get_setting(marker_key(incarnation_id)) or {}
        value = dict(stored.get("value") or {})
        try:
            self._settings.set_setting(marker_key(incarnation_id), {**value, "escalated": True},
                                       updated_by="billing-reconciler", expected_updated_at=stored.get("updated_at"))
        except SettingConflict:
            pass  # the next tick sees the item already open (record() dedupes on its key)

    @staticmethod
    def _dedupe(incarnation_id: str) -> str:
        return f"{REASON}:{incarnation_id}"
