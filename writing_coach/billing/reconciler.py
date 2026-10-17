"""The billing reconciler (PR-MON-3 §4.4-4.5): it finds and repairs what a lost or failed webhook left behind.

Each tick, under one PostgreSQL session-level advisory lock held on its own connection (P1-4):

1. **Entitlement gaps.** An account whose paid orders are ahead of the access recorded for it (a crash between
   `mark_paid` and `sync_prepaid`, R-MON-002) is synced again; the sync is idempotent. A gap that survives that
   repair opens a critical `entitlement_unsynced` item, which closes new checkouts on its gateway, and the
   reconciler alone resolves it once access is really granted.
2. **payOS lookups.** payOS documents no webhook retry, so every payOS order whose outcome is not settled is asked
   about: an unpaid one (a locally expired one too), and a webhook-paid one once, to confirm it. Only a successful
   lookup that says PAID with the order's amount, or CANCELLED with nothing paid, settles an order; anything else
   is asked again later, with backoff, and past the horizon the order opens an item and is still asked daily.
   Rate limiting and transport errors are retried and never open a money item.
3. **Abandoned orders.** An unpaid order past its expiry becomes `expired` - locally only (step 2 keeps asking).

Lock scope: the lock's connection holds no transaction (the implicit one the lock's SELECT opens is committed at
once); every write is its own short transaction in the repositories; no transaction or row lock is open while
payOS is called. If the lock's connection is lost, the tick stops. Idempotency (one payment per payOS order) is the
last line of defence when a webhook and a lookup race.

Off unless the billing service exists (`BILLING_ENABLED`, PostgreSQL, the backbone); lookups need payOS keys.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from writing_coach.billing.payos import TERMINAL_STATUSES, Lookup, parse_lookup

_log = logging.getLogger(__name__)

LOCK_KEY = 7_301_202_610_140_031  # this reconciler's advisory lock, distinct from any other in the database
LOOKUP_TIMEOUT_SECONDS = 5.0
LOOKUP_LEASE = timedelta(minutes=5)
MAX_BACKOFF = timedelta(hours=6)
HORIZON_CADENCE = timedelta(days=1)


class RateLimited(Exception):
    """The provider said 429: stop asking this tick; `retry_after` is its own wait, when it gave one."""

    def __init__(self, retry_after: float | None = None) -> None:
        super().__init__("rate_limited")
        self.retry_after = retry_after


@dataclass(frozen=True)
class Settings:
    interval: float = 60.0
    pull_after: timedelta = timedelta(minutes=2)
    per_tick: int = 20
    horizon: timedelta = timedelta(days=14)

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Settings:
        def number(name: str, default: float, minimum: float) -> float:
            try:
                value = float(str(env.get(name, "")).strip() or default)
            except ValueError:
                _log.warning("billing: %s is not a number; using %s", name, default)
                return default
            return max(minimum, value)

        return cls(interval=number("BILLING_RECONCILE_INTERVAL_SECONDS", 60, 5),
                   pull_after=timedelta(seconds=number("BILLING_PULL_AFTER_SECONDS", 120, 0)),
                   per_tick=int(number("BILLING_PULL_PER_TICK", 20, 1)),
                   horizon=timedelta(days=number("BILLING_PULL_HORIZON_DAYS", 14, 1)))  # fmt: skip


def get_json(request: Mapping[str, Any], *, timeout: float = LOOKUP_TIMEOUT_SECONDS) -> dict:
    """A provider GET. A 429 is `RateLimited`; any other failure raises as itself."""

    call = urllib.request.Request(request["url"], method="GET", headers=dict(request["headers"]))
    try:
        with urllib.request.urlopen(call, timeout=timeout) as response:  # noqa: S310 - fixed https gateway hosts
            return json.loads(response.read(1_000_000).decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 429:
            try:
                wait = float(error.headers.get("Retry-After") or "")
            except ValueError:
                wait = None
            raise RateLimited(wait) from None
        raise


def build_lookups(gateways: Mapping[str, Any], *, fetch: Callable[[Mapping[str, Any]], dict] = get_json
                  ) -> dict[str, Callable[[int], Lookup]]:
    """The lookup of each configured gateway that has one (payOS)."""

    lookups: dict[str, Callable[[int], Lookup]] = {}
    payos = gateways.get("payos")
    if payos is not None and hasattr(payos, "lookup_request"):
        lookups["payos"] = lambda order_code: parse_lookup(fetch(payos.lookup_request(order_code)))
    return lookups


class _LockHandle:
    def __init__(self, connection: Any) -> None:
        self.connection = connection
        self.held = False

    def alive(self) -> bool:
        try:
            self.connection.execute(text("SELECT 1"))
            self.connection.commit()
            return True
        except Exception:  # noqa: BLE001 - a lost connection has lost the lock with it
            return False


class PostgresTickLock:
    """One tick at a time across every process: a session-level advisory lock on a dedicated connection."""

    def __init__(self, engine: Any, key: int = LOCK_KEY) -> None:
        self._engine = engine
        self._key = key

    @contextmanager
    def __call__(self) -> Iterator[_LockHandle]:
        connection = self._engine.connect()
        handle = _LockHandle(connection)
        try:
            handle.held = bool(connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": self._key}).scalar())
            connection.commit()  # end the implicit transaction; the session lock stays with the connection
            yield handle
        finally:
            try:
                if handle.held:
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": self._key})
                    connection.commit()
            except Exception:  # noqa: BLE001 - never return a connection that may still hold the lock to the pool
                _log.warning("billing reconciler: lock release failed; discarding its connection", exc_info=True)
                connection.invalidate()
            finally:
                connection.close()


class BillingReconciler:
    def __init__(self, *, service: Any, orders: Any, items: Any, lock: Callable[[], Any],
                 lookups: Mapping[str, Callable[[int], Lookup]], settings: Settings = Settings(),
                 now: Callable[[], datetime] = lambda: datetime.now(UTC), credits: Any = None,
                 feed: Any = None, polar_cleanup: Any = None) -> None:
        self._service = service
        self._polar_cleanup = polar_cleanup  # PR-MON-10 §4.8: the Polar customer clean-up of deleted incarnations
        self._feed = feed  # PR-MON-8: the SePay recovery feed, which runs only when switched on (sepay_feed.py)
        self._credits = credits  # PR-MON-4: the credit ledger's step, when credits are enabled
        self._orders = orders
        self._items = items
        self._lock = lock
        self._lookups = dict(lookups)
        self._settings = settings
        self._now = now

    def tick(self) -> dict[str, int] | None:
        """One reconciliation pass. None when another process holds the tick; otherwise what it did."""

        with self._lock() as lock:
            if not lock.held:
                return None
            counts: Counter[str] = Counter()
            steps = [("gaps", self._gaps), ("pull", self._pull), ("expire", self._expire)]
            if self._credits is not None:
                steps.append(("credits", self._credit_step))
            if getattr(self._service, "credits", None) is not None:
                steps.append(("credit_orders", self._credit_order_step))
            if self._feed is not None and self._feed.enabled:
                steps.append(("sepay_feed", self._feed.step))
            if self._polar_cleanup is not None and self._polar_cleanup.configured:
                steps.append(("polar_cleanup", self._polar_cleanup.step))
            for name, step in steps:
                if not lock.alive():
                    counts["lock_lost"] += 1
                    _log.warning("billing reconciler: the lock's connection was lost; tick stopped")
                    break
                try:
                    step(counts, lock)
                except Exception:  # noqa: BLE001 - one failed step never stops the others; retried next tick
                    counts[f"{name}_failed"] += 1
                    _log.warning("billing reconciler: %s failed; retried at the next tick", name, exc_info=True)
            return dict(counts)

    # ---- 1. entitlement gaps (§4.4) -----------------------------------------------------------------------

    def _gaps(self, counts: Counter[str], lock: Any) -> None:
        for gateway in self._service.domestic_gateways():
            attempted: dict[str, int] = {}
            for gap in self._orders.prepaid_gaps(gateway):
                incarnation, version = gap["incarnation_id"], gap["version"]
                attempted[incarnation] = version
                try:
                    self._service.sync_prepaid(incarnation, gateway, event_id=f"{gateway}:reconcile:{incarnation}:{version}")
                    counts["gap_repaired"] += 1
                except Exception:  # noqa: BLE001 - the gap stays, and is recorded below
                    _log.warning("billing reconciler: sync of %s failed", incarnation, exc_info=True)
            remaining = {gap["incarnation_id"]: gap for gap in self._orders.prepaid_gaps(gateway)}
            for incarnation, gap in remaining.items():
                # Only a gap that survived its own repair: a payment that arrived meanwhile is repaired next tick.
                if attempted.get(incarnation) == gap["version"]:
                    self._items.record(kind="entitlement_unsynced", gateway=gateway,
                                       dedupe_key=f"{incarnation}:{gap['version']}", incarnation_id=incarnation,
                                       reason=f"paid orders at version {gap['version']}, access at {gap['applied']}",
                                       now=self._now())  # fmt: skip
                    counts["entitlement_unsynced"] += 1
            for item in self._items.open_items(kind="entitlement_unsynced"):
                if item["gateway"] != gateway:
                    continue
                incarnation, _, version = str(item["dedupe_key"]).rpartition(":")
                gap = remaining.get(incarnation)
                if gap is None or (gap["applied"] is not None and gap["applied"] >= int(version)):
                    self._items.auto_resolve(kind="entitlement_unsynced", gateway=gateway, dedupe_key=item["dedupe_key"],
                                             outcome="entitlement_synced", note="access granted for every paid order",
                                             now=self._now())  # fmt: skip
                    counts["entitlement_synced"] += 1

    # ---- 2. provider lookups (§4.5) -----------------------------------------------------------------------

    def _pull(self, counts: Counter[str], lock: Any) -> None:
        lookup = self._lookups.get("payos")
        if lookup is None:
            return
        now = self._now()
        candidates = self._orders.pull_candidates("payos", now=now, limit=self._settings.per_tick,
                                                  min_age=self._settings.pull_after)  # fmt: skip
        for order in candidates:
            if not lock.alive():
                counts["lock_lost"] += 1
                return
            if not self._orders.claim_lookup(order["id"], now=now, lease=LOOKUP_LEASE):
                continue
            try:
                answer = lookup(int(order["order_code"]))  # no transaction and no row lock is open here
            except RateLimited as limited:
                wait = timedelta(seconds=limited.retry_after) if limited.retry_after else self._backoff(order, now)
                self._orders.record_lookup(order["id"], status="RATE_LIMITED", now=now, next_at=now + wait, settled=False)
                counts["rate_limited"] += 1
                return  # ask nothing more this tick
            except Exception:  # noqa: BLE001 - no answer is not an answer: asked again later
                _log.info("billing reconciler: payOS lookup of %s failed", order["order_code"], exc_info=True)
                self._orders.record_lookup(order["id"], status="NO_ANSWER", now=now,
                                           next_at=now + self._backoff(order, now), settled=False)  # fmt: skip
                counts["lookup_failed"] += 1
                continue
            counts["looked_up"] += 1
            self._settle(order, answer, now, counts)

    def _backoff(self, order: Mapping[str, Any], now: datetime) -> timedelta:
        if self._past_horizon(order, now):
            return HORIZON_CADENCE
        return min(timedelta(seconds=60 * 2 ** min(int(order.get("lookup_attempts") or 0), 20)), MAX_BACKOFF)

    def _past_horizon(self, order: Mapping[str, Any], now: datetime) -> bool:
        return now - order["created_at"] > self._settings.horizon

    def _settle(self, claimed: Mapping[str, Any], answer: Lookup, now: datetime, counts: Counter[str]) -> None:
        code, amount, gateway = int(claimed["order_code"]), int(claimed["amount_minor"]), "payos"
        # Decided on the order as it is now, not as it was before the provider call: a webhook or a refund may have
        # changed it meanwhile (review P1-3).
        order = self._orders.order(order_code=code) or claimed
        if order.get("provider_settled_at") is not None:
            # Settled while payOS was being asked (claimed unsettled): an administrator's disposition answered it.
            # This answer is stale: it reopens nothing and records nothing (focused review, P1-2 race).
            _log.info("billing reconciler: order %s was settled during its lookup; the answer is not applied", code)
            counts["stale_lookup"] += 1
            return
        recorded = order["state"] in ("paid", "refunded")
        facts = {"reported_order_code": code, "reported_amount_minor": answer.amount_paid, "reported_currency": order["currency"],
                 "provider_state": answer.status or None, "billing_order_id": order["id"],
                 "incarnation_id": str(order["incarnation_id"])}  # fmt: skip

        def keep_asking(status: str) -> None:
            self._orders.record_lookup(order["id"], status=status, now=now, next_at=now + self._backoff(order, now),
                                       settled=False)  # fmt: skip

        def settle(status: str) -> None:
            self._orders.record_lookup(order["id"], status=status, now=now, next_at=None, settled=True)

        if answer.status == "PAID" and answer.amount_paid == amount:
            if not recorded:
                self._service.record_payment(order_code=code, gateway=gateway, event_id=f"payos:order:{code}",
                                             amount_minor=answer.amount_paid, currency=order["currency"],
                                             payment_link_id=answer.payment_link_id, paid_reference=answer.reference,
                                             settled=True, provider_state="PAID")  # fmt: skip
            if (self._orders.order(order_code=code) or {}).get("state") in ("paid", "refunded"):
                settle("PAID")
                if self._items.auto_resolve(kind="provider_paid_unrecorded", gateway=gateway, dedupe_key=str(code),
                                            outcome="payment_recorded", note="the payment is recorded on its order",
                                            now=now):  # fmt: skip
                    counts["paid_unrecorded_resolved"] += 1
                counts["paid_confirmed" if recorded else "paid_recovered"] += 1
            else:
                # payOS says paid and Orena holds no payment for it: critical until it is recorded or refunded.
                self._items.record(kind="provider_paid_unrecorded", gateway=gateway, dedupe_key=str(code),
                                   reason="payOS reports this order paid; no payment is recorded", now=now, **facts)
                keep_asking("PAID")
                counts["paid_unrecorded"] += 1
            return
        if answer.status in TERMINAL_STATUSES and answer.amount_paid not in (None, 0) and answer.amount_paid != amount:
            # Settled with money that is not the order's amount (an overpayment of a paid order included): kept as
            # a money anomaly. A partial amount on a request still PENDING is not terminal and is asked again.
            self._items.record(kind="payment_mismatch", gateway=gateway, dedupe_key=f"pull:{code}",
                               reason=f"payOS reports {answer.amount_paid} paid for an order of {amount}", now=now,
                               **facts)  # fmt: skip
            settle(answer.status or "UNKNOWN")
            counts["payment_mismatch"] += 1
            return
        if answer.status == "CANCELLED" and not answer.amount_paid:
            # Cancelled only if the order is still unpaid when it is written (a conditional update).
            if not recorded and self._orders.mark_cancelled(order["id"], now=now):
                settle("CANCELLED")
                counts["cancelled"] += 1
            else:
                self._items.record(kind="provider_state_unresolved", gateway=gateway, dedupe_key=str(code),
                                   reason="payOS reports cancelled for an order Orena recorded paid", now=now, **facts)
                keep_asking("CANCELLED")
            return
        # Not terminal: PENDING, PROCESSING, PAID without a readable amount, or a status payOS does not document.
        keep_asking(answer.status or "UNKNOWN")
        if not answer.documented or self._past_horizon(order, now):
            reason = (f"payOS status {answer.status or '(none)'} is not documented" if not answer.documented
                      else "no terminal payOS answer within the reconciliation horizon")  # fmt: skip
            self._items.record(kind="provider_state_unresolved", gateway=gateway, dedupe_key=str(code), reason=reason,
                               now=now, **facts)  # fmt: skip
            counts["unresolved"] += 1

    # ---- 3. abandoned orders ------------------------------------------------------------------------------

    def _credit_step(self, counts: Counter[str], lock: Any) -> None:
        """PR-MON-4 §7: close holds past their TTL (`reserve_expire`, never purchased credit), record a deleted
        account's credit as a liability, and detect drift. Each write is its own short transaction."""

        for name, value in self._credits.reconcile(items=self._items, now=self._now()).items():
            counts[f"credit_{name}"] += value

    def _credit_order_step(self, counts: Counter[str], lock: Any) -> None:
        """PR-MON-5 §6.2, §7.1: credit-pack orders paid without their exact top-up, and refunded without their complete
        reversal - repaired, escalated, and closed only on their outcome's fact."""

        for name, value in self._service.reconcile_credit_orders().items():
            counts[name] += value

    def _expire(self, counts: Counter[str], lock: Any) -> None:
        counts["expired"] += self._orders.expire_abandoned(now=self._now())


class BillingReconcileSchedule:
    """At start and then every `interval` seconds, on its own daemon thread (the quota reconciler's pattern)."""

    def __init__(self, reconciler: BillingReconciler, *, interval: float) -> None:
        self._reconciler = reconciler
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def tick(self) -> dict[str, int] | None:
        try:
            return self._reconciler.tick()
        except Exception:  # noqa: BLE001 - e.g. the database is down: retried at the next tick
            _log.warning("billing reconciler failed; retried at the next tick", exc_info=True)
            return None

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.tick()
            self._stop.wait(self._interval)

    def start(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="billing-reconciler", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
