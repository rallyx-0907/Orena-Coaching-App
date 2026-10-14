"""Billing: checkout, webhooks, cancel and an operator's refund record, over any gateway (BILLING_GATEWAYS.md).

Off unless `BILLING_ENABLED` is on - and even then a gateway without its keys, or a plan without an approved
price, is simply not offered. Prices come from the file `BILLING_PRICES_FILE` names (the human's decision,
never a default in code), and a price is sold only while it is exactly the catalogue's: one that is not blocks its
whole gateway (`price_integrity`, D-MON-005, D-MON-015).

Access changes only through the commerce repository (`record_event`), from a verified gateway event:
- a merchant-of-record subscription event is recorded as the subscription's own state and revision;
- a domestic payment marks its order paid, and the account's prepaid state - replayed from its orders - is
  recorded as a `prepaid:<incarnation>` subscription whose version is the order count.
A checkout return URL grants nothing.

A verified money event is acknowledged only once it is durable (PR-MON-3, D-MON-004): as the order, a receipt, or a
reconciliation item (`persistence/billing_reconciliation_repository.py`). A business anomaly - an unknown order, a
mismatch, a payment for a deleted account, an undecidable subscription event, a refund - is recorded as an item and
then acknowledged; when that record cannot be written the call raises, and the route answers 503 so the provider
retries. An open critical item (paid without access, paid but unrecorded) closes new checkouts on its gateway.
"""

from __future__ import annotations

import json
import logging
import urllib.request
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from writing_coach.billing.gateway import CheckoutIntent, GatewayNotConfigured, PaymentFact, Price, WebhookRejected
from writing_coach.billing.price_integrity import MINOR_EXPONENT, PriceCheck, blocked_gateways, check_prices
from writing_coach.product.catalog import DEFAULT_PLAN_ID, PLANS, CatalogUnavailable, current_plans

_log = logging.getLogger(__name__)
_ON = frozenset({"1", "true", "yes", "on"})
# Which currency each gateway takes, and whether it needs the gateway's own price id.
_GATEWAY_RULES = {"payos": ({"VND"}, False), "polar": (None, True)}
# What a prices file may sell: a paid plan of the catalogue, by its own id (not a legacy alias).
_SELLABLE_PLANS = frozenset(plan_id for plan_id in PLANS if plan_id != DEFAULT_PLAN_ID)
_LIVE = frozenset({"active", "trialing", "past_due", "paused", "pending"})
# A payment Orena cannot apply, and the reconciliation item it is kept as (PR-MON-3 §4.2).
_PAYMENT_ANOMALY = {"unknown_order": "payment_unknown_order", "mismatch": "payment_mismatch",
                    "not_payable": "payment_not_payable"}
# A subscription event the commerce record could not decide.
_UNDECIDED = frozenset({"unknown", "foreign_incarnation", "payload_conflict", "rejected"})


class CheckoutRefused(Exception):
    """A checkout that must not start: `code` is said to the learner's client as is."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def billing_enabled(env: Mapping[str, str]) -> bool:
    return str(env.get("BILLING_ENABLED", "")).strip().casefold() in _ON


def load_prices(env: Mapping[str, str]) -> dict[str, Price]:
    """Approved prices, keyed `plan:period:gateway`. No file, no prices: nothing is for sale."""

    path = str(env.get("BILLING_PRICES_FILE", "")).strip()
    if not path:
        return {}
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    prices: dict[str, Price] = {}
    for item in items:
        amount = item["amount_minor"]
        if type(amount) is not int or amount <= 0:
            raise ValueError("a price is a positive integer of minor units")
        if item["period"] not in ("month", "year"):
            raise ValueError("a price period is month or year")
        if str(item["plan_id"]) not in _SELLABLE_PLANS:
            raise ValueError(f"a price names a paid plan of the catalogue: {', '.join(sorted(_SELLABLE_PLANS))}")
        if str(item["currency"]).upper() not in MINOR_EXPONENT:
            raise ValueError(f"a price is in a currency the catalogue prices in: {', '.join(sorted(MINOR_EXPONENT))}")
        if str(item["gateway"]) not in _GATEWAY_RULES:
            raise ValueError(f"unknown gateway {item['gateway']!r}")
        currencies, needs_id = _GATEWAY_RULES[str(item["gateway"])]
        if currencies is not None and str(item["currency"]).upper() not in currencies:
            raise ValueError(f"{item['gateway']} takes {', '.join(sorted(currencies))} only")
        if needs_id and not item.get("external_price_id"):
            raise ValueError(f"a {item['gateway']} price names the gateway's own price id")
        price = Price(plan_id=str(item["plan_id"]), period=item["period"], currency=str(item["currency"]).upper(),
                      amount_minor=amount, gateway=str(item["gateway"]),
                      external_price_id=str(item.get("external_price_id") or ""))  # fmt: skip
        key = f"{price.plan_id}:{price.period}:{price.gateway}"
        if key in prices:
            raise ValueError(f"{key} is priced twice")
        prices[key] = price
    return prices


def build_gateways(env: Mapping[str, str]) -> dict[str, Any]:
    from writing_coach.billing.payos import PayOSGateway
    from writing_coach.billing.polar import PolarGateway

    gateways: dict[str, Any] = {}
    for factory in (PayOSGateway, PolarGateway):
        try:
            gateway = factory.from_env(env)
        except GatewayNotConfigured:
            continue
        gateways[gateway.name] = gateway
    return gateways


def _send(request: dict) -> dict:
    body = json.dumps(request["json"]).encode("utf-8")
    call = urllib.request.Request(request["url"], data=body, method=request["method"],
                                  headers={"Content-Type": "application/json", **request["headers"]})  # fmt: skip
    with urllib.request.urlopen(call, timeout=20) as response:  # noqa: S310 - fixed https gateway hosts
        return json.loads(response.read(1_000_000).decode("utf-8"))


@dataclass
class WebhookOutcome:
    status: str  # applied | duplicate | ignored | stale | unknown | rejected | mismatch | ...
    detail: str = ""


class BillingService:
    def __init__(self, *, orders: Any, commerce: Any, gateways: Mapping[str, Any], prices: Mapping[str, Price],
                 catalog: Callable[[], Mapping[str, Any]] = lambda: current_plans(strict=True),
                 send: Callable[[dict], dict] = _send, now: Callable[[], datetime] = lambda: datetime.now(UTC),
                 reconciliation: Any = None) -> None:
        self._orders = orders
        # The reconciliation items (PR-MON-3). Without them no anomaly can be recorded, so none is acknowledged.
        self._items = reconciliation
        self._commerce = commerce
        self._gateways = dict(gateways)
        self._prices = dict(prices)
        # The catalogue in force, read strictly: a catalogue that cannot be read sells nothing.
        self._catalog = catalog
        self._send = send
        self._now = now

    @property
    def orders(self) -> Any:
        return self._orders

    @property
    def reconciliation(self) -> Any:
        return self._items

    @property
    def gateways(self) -> Mapping[str, Any]:
        return dict(self._gateways)

    def domestic_gateways(self) -> list[str]:
        """The configured gateways that sell prepaid periods (their orders are the payment record)."""

        return [name for name, gateway in self._gateways.items() if getattr(gateway, "kind", "") == "domestic"]

    # ---- price integrity (D-MON-005, D-MON-015) -----------------------------------------------------------

    def price_checks(self) -> dict[str, PriceCheck]:
        """Every approved price against the catalogue in force now. Raises `CatalogUnavailable`."""

        return check_prices(self._prices, self._catalog())

    def critical_by_gateway(self) -> Mapping[str, int]:
        """Open critical reconciliation items per gateway (PR-MON-3 §4.2). Raises when they cannot be read."""

        return self._items.critical_by_gateway() if self._items is not None else {}

    def reconciliation_summary(self) -> dict[str, Any] | str:
        """Open items per kind and the critical ones per gateway, for the readiness report; never raises."""

        if self._items is None:
            return "not_configured"  # a service built without items (tests); the running app always has them
        try:
            return self._items.summary()
        except Exception:  # noqa: BLE001 - reported, never a failed report
            return "unavailable"

    def _critical_blocked(self) -> set[str] | None:
        """Gateways an open critical item closes; None when that cannot be read (every gateway is then closed)."""

        try:
            return {gateway for gateway, count in self.critical_by_gateway().items() if count > 0}
        except Exception:  # noqa: BLE001 - unreadable reconciliation state sells nothing
            _log.warning("billing: reconciliation state cannot be read; nothing is sold", exc_info=True)
            return None

    def _sellable(self, checks: Mapping[str, PriceCheck]) -> dict[str, Price]:
        blocked = blocked_gateways(checks.values())
        critical = self._critical_blocked()
        if critical is None:
            return {}
        return {key: price for key, price in self._prices.items()
                if price.gateway in self._gateways and price.gateway not in blocked | critical}  # fmt: skip

    def offered(self) -> list[dict[str, Any]]:
        try:
            checks = self.price_checks()
        except CatalogUnavailable:
            _log.warning("billing: the plan catalogue cannot be read; nothing is offered", exc_info=True)
            return []
        return [{"key": key, "plan_id": price.plan_id, "period": price.period, "currency": price.currency,
                 "amount_minor": price.amount_minor, "gateway": price.gateway}
                for key, price in self._sellable(checks).items()]  # fmt: skip

    def gateway_report(self) -> dict[str, dict[str, Any]]:
        """Per gateway: configured (its keys, and so its webhook verification), its prices against the catalogue, and
        ready - configured, priced, every price the catalogue's. No secret, no key material."""

        try:
            checks: Mapping[str, PriceCheck] | None = self.price_checks()
        except CatalogUnavailable:
            checks = None
        try:
            critical: Mapping[str, int] | None = self.critical_by_gateway()
        except Exception:  # noqa: BLE001 - reported as unavailable, and nothing is ready
            critical = None
        report: dict[str, dict[str, Any]] = {}
        for name in _GATEWAY_RULES:
            gateway = self._gateways.get(name)
            mine = [check for check in (checks or {}).values() if check.gateway == name]
            entry: dict[str, Any] = {
                "configured": gateway is not None,
                "webhook_verification": gateway is not None,
                "prices": [check.as_dict() for check in mine],
                "ready": gateway is not None and checks is not None and bool(mine) and all(c.matches for c in mine),
            }
            if critical is None:
                entry["reconciliation"] = "unavailable"
                entry["ready"] = False
            elif critical.get(name, 0) > 0:
                entry["reconciliation_critical"] = int(critical[name])
                entry["ready"] = False
            if gateway is not None and getattr(gateway, "environment", None):
                entry["environment"] = gateway.environment
            if checks is None:
                entry["catalog"] = "unavailable"
            report[name] = entry
        return report

    # ---- checkout -----------------------------------------------------------------------------------------

    def start_checkout(self, *, incarnation_id: str, price_key: str, operation_id: str, return_url: str,
                       cancel_url: str, confirmed_amount_minor: int | None, confirmed_currency: str | None,
                       customer_email: str = "") -> dict[str, Any]:
        """`confirmed_*` is the price the learner saw and confirmed. It is never charged - the server's price is -
        but a checkout whose confirmed price is not the server's does not start (`price_changed`)."""

        price = self._prices.get(price_key)
        gateway = self._gateways.get(price.gateway) if price else None
        if price is None or gateway is None:
            raise LookupError("price_not_offered")
        uuid.UUID(operation_id)  # an operation id is the client's own UUID: a retry reuses it
        self._refuse_unverified_price(price_key, price, confirmed_amount_minor, confirmed_currency)
        critical = self._critical_blocked()
        if critical is None or price.gateway in critical:
            raise CheckoutRefused("reconciliation_critical")
        self._refuse_second_subscription(incarnation_id, price, gateway)
        order = self._orders.create_order(operation_id=operation_id, incarnation_id=incarnation_id,
                                          gateway=price.gateway, plan_id=price.plan_id, period=price.period,
                                          currency=price.currency, amount_minor=price.amount_minor)  # fmt: skip
        if order["conflict"]:
            raise CheckoutRefused("operation_conflict")
        if order["state"] != "created":
            # Started (its link exists) or finished: a new attempt is a new operation id, never a second link for
            # this order, and never a link to pay an order that is already paid or refunded.
            raise CheckoutRefused("checkout_already_started" if order["state"] == "pending" else "order_closed")
        intent = CheckoutIntent(operation_id=operation_id, incarnation_id=incarnation_id, price=price,
                                return_url=return_url, cancel_url=cancel_url, customer_email=customer_email)  # fmt: skip
        if gateway.kind == "domestic":
            request = gateway.checkout_request(intent, order_code=int(order["order_code"]),
                                               description=f"OR{order['order_code']}",
                                               expires_at=order.get("expires_at"))  # fmt: skip
            answer = self._send(request)
            data = answer.get("data") or {}
            reference, url, qr = str(data.get("paymentLinkId") or ""), str(data.get("checkoutUrl") or ""), str(data.get("qrCode") or "")
        else:
            answer = self._send(gateway.checkout_request(intent))
            reference, url, qr = str(answer.get("id") or ""), str(answer.get("url") or ""), ""
        if not url:
            raise RuntimeError("gateway_checkout_failed")
        if reference:
            self._orders.set_reference(order["id"], reference)
        return {"redirect_url": url, "qr": qr, "order_code": int(order["order_code"]), "gateway": price.gateway}

    def _refuse_unverified_price(self, key: str, price: Price, amount: int | None, currency: str | None) -> None:
        try:
            checks = self.price_checks()
        except CatalogUnavailable:
            _log.warning("billing: checkout of %s refused, the plan catalogue cannot be read", key, exc_info=True)
            raise CheckoutRefused("catalog_unavailable") from None
        if price.gateway in blocked_gateways(checks.values()):
            _log.warning("billing: checkout of %s refused, a %s price is not the catalogue's", key, price.gateway)
            raise CheckoutRefused("price_mismatch")
        if amount is None or not currency:
            raise CheckoutRefused("price_unconfirmed")
        if type(amount) is not int or amount != price.amount_minor or str(currency).strip().upper() != price.currency:
            raise CheckoutRefused("price_changed")

    def _refuse_second_subscription(self, incarnation_id: str, price: Price, gateway: Any) -> None:
        """One live subscription per account: a card subscription while prepaid access lasts (or the reverse)
        would leave the commerce record undecided ('two live ones are unknown') after the money is taken.
        Renewing prepaid access with the same gateway is not a second subscription."""

        current = self._commerce.get_subscription(incarnation_id)
        if not current or current.get("state") not in _LIVE:
            return
        paid_through = current.get("paid_through")
        if paid_through is not None and paid_through <= self._now():
            return
        same_prepaid = (gateway.kind == "domestic" and current.get("provider") == price.gateway
                        and current.get("external_subscription_id") == f"prepaid:{incarnation_id}")  # fmt: skip
        if not same_prepaid:
            raise CheckoutRefused("subscription_live")

    # ---- webhooks -----------------------------------------------------------------------------------------

    def handle_webhook(self, gateway_name: str, headers: Mapping[str, str], body: bytes) -> WebhookOutcome:
        gateway = self._gateways.get(gateway_name)
        if gateway is None:
            return WebhookOutcome("not_configured")
        try:
            fact = gateway.verify(headers, body, now=self._now())
        except WebhookRejected as rejected:
            _log.warning("billing webhook from %s rejected: %s", gateway_name, rejected.reason)
            return WebhookOutcome("rejected", rejected.reason)
        if fact.kind == "payment":
            return self._prepaid_payment(fact)
        if fact.kind == "subscription":
            return self._subscription(fact)
        if fact.kind == "refund":
            return self._refund(fact)
        # other verified events move no money: logged, no effect.
        _log.info("billing event from %s: %s %s", gateway_name, fact.kind, fact.provider_state)
        return WebhookOutcome("ignored", fact.kind)

    def _item(self, kind: str, gateway: str, dedupe_key: str, **facts: Any) -> dict[str, Any]:
        """Record one anomaly durably, before it is acknowledged. Raises when it cannot be recorded."""

        if self._items is None:
            raise RuntimeError("billing reconciliation items are not configured; the anomaly cannot be recorded")
        item = self._items.record(kind=kind, gateway=gateway, dedupe_key=dedupe_key, now=self._now(), **facts)
        _log.warning("billing: %s on %s recorded for reconciliation (%s)", kind, gateway, dedupe_key)
        return item

    def _refund(self, fact: PaymentFact) -> WebhookOutcome:
        """A provider's refund is recorded, matched to an account only through its subscription's committed mapping
        (§4.6). It never changes access: the subscription's own lifecycle events do (H4)."""

        extra = fact.extra or {}
        refund_id = extra.get("refund_id") or fact.event_id
        subscription = extra.get("subscription_id") or ""
        mapped = self._commerce.get_provider_subscription(fact.gateway, subscription) if subscription else None
        incarnation = str(mapped["incarnation_id"]) if mapped else None
        self._item("provider_refund", fact.gateway, refund_id, external_event_id=fact.event_id,
                   reported_amount_minor=fact.amount_minor, reported_currency=fact.currency,
                   provider_state=fact.provider_state, payload_digest=fact.payload_digest or None,
                   reason=f"subscription {subscription}" if subscription else f"order {extra.get('order_id') or ''}",
                   incarnation_id=incarnation)  # fmt: skip
        if incarnation is not None and self._items.auto_resolve(
                kind="provider_refund", gateway=fact.gateway, dedupe_key=refund_id, outcome="recorded",
                note="matched to its subscription's account; access follows subscription events", now=self._now()):
            return WebhookOutcome("recorded", "refund_matched")
        return WebhookOutcome("recorded", "refund_matched" if incarnation else "refund_unmatched")

    def _subscription(self, fact: PaymentFact) -> WebhookOutcome:
        from writing_coach.persistence.commerce_repository import SubscriptionUpdate

        incarnation = None
        if fact.external_reference:
            mapped = self._commerce.get_provider_subscription(fact.gateway, fact.external_reference)
            incarnation = str(mapped["incarnation_id"]) if mapped else None
        operation = fact.extra.get("orena_operation") if fact.extra else ""
        order = self._orders.order(operation_id=operation) if operation else None
        if incarnation is None:
            incarnation = self._known_checkout(fact, order)
        if incarnation is None:
            self._item("event_undecided", fact.gateway, fact.event_id, external_event_id=fact.event_id,
                       provider_state=fact.provider_state, payload_digest=fact.payload_digest or None,
                       reason=f"subscription {fact.external_reference} names no checkout of Orena")  # fmt: skip
            return WebhookOutcome("unknown", "no_checkout_for_subscription")
        # The plan is the one Orena's own order sold, when the order is this account's; signed metadata otherwise.
        plan = order["plan_id"] if order is not None and str(order["incarnation_id"]) == incarnation else fact.plan_id
        update = SubscriptionUpdate(state=fact.state or "unknown", plan_id=plan or "free",
                                    external_customer_id=fact.external_customer_id,
                                    external_subscription_id=fact.external_reference,
                                    paid_through=fact.paid_through, cancel_at_period_end=fact.cancel_at_period_end,
                                    provider_state=fact.provider_state)  # fmt: skip
        outcome = self._commerce.record_event(incarnation_id=incarnation, provider=fact.gateway,
                                              external_event_id=fact.event_id, event_object_version=fact.object_version,
                                              update=update, external_object_reference=fact.external_reference,
                                              payload_digest=fact.payload_digest)  # fmt: skip
        result = self._outcome(outcome, f"{fact.gateway} subscription {fact.external_reference}")
        if result.status in _UNDECIDED:
            self._item("event_undecided", fact.gateway, fact.event_id, external_event_id=fact.event_id,
                       provider_state=fact.provider_state, payload_digest=fact.payload_digest or None,
                       reason=f"{result.status} {result.detail}".strip(),
                       # `rejected` is an account the commerce record does not know: nothing to link to.
                       incarnation_id=None if result.status == "rejected" else incarnation)  # fmt: skip
        return result

    @staticmethod
    def _outcome(outcome: Mapping[str, Any], what: str) -> WebhookOutcome:
        status = str(outcome.get("status"))
        if status == "unknown":
            # Verified but undecidable: kept as a received receipt; an operator must look (it may be money taken).
            _log.warning("billing: %s left undecided (%s); an operator must reconcile it", what, outcome.get("reason"))
        return WebhookOutcome(status, str(outcome.get("reason") or ""))

    def _known_checkout(self, fact: PaymentFact, order: Mapping[str, Any] | None) -> str | None:
        """A first event for a subscription: its account is the one Orena's own checkout named, and only if an
        order for that account exists - signed metadata alone does not attach a subscription to an account."""

        hint = fact.incarnation_hint
        if not hint:
            return None
        if order is None or str(order["incarnation_id"]) != hint or order["gateway"] != fact.gateway:
            return None
        return hint

    def _prepaid_payment(self, fact: PaymentFact) -> WebhookOutcome:
        try:
            code = int(fact.external_reference or "")
        except ValueError:
            # Verified, says paid, names no order Orena can read: money may have moved, so it is recorded.
            self._item("payment_unknown_order", fact.gateway, fact.event_id, external_event_id=fact.event_id,
                       reported_amount_minor=fact.amount_minor, reported_currency=fact.currency,
                       provider_state=fact.provider_state, payload_digest=fact.payload_digest or None,
                       reason="no readable order code")  # fmt: skip
            return WebhookOutcome("unknown_order", "no_order_code")
        extra = fact.extra or {}
        return self.record_payment(order_code=code, gateway=fact.gateway, event_id=fact.event_id,
                                   amount_minor=fact.amount_minor, currency=fact.currency,
                                   payment_link_id=extra.get("payment_link_id", ""),
                                   paid_reference=extra.get("reference") or None, provider_state=fact.provider_state,
                                   payload_digest=fact.payload_digest or None)  # fmt: skip

    def record_payment(self, *, order_code: int, gateway: str, event_id: str, amount_minor: int | None,
                       currency: str | None, payment_link_id: str = "", paid_reference: str | None = None,
                       settled: bool = False, provider_state: str | None = None,
                       payload_digest: str | None = None) -> WebhookOutcome:
        """One verified payment of one domestic order, from its webhook or from the reconciler's lookup: the order is
        marked paid and the account's access synced; an anomaly is recorded before this returns."""

        marked = self._orders.mark_paid(order_code=order_code, event_id=event_id, amount_minor=amount_minor,
                                        currency=currency, payment_link_id=payment_link_id,
                                        paid_reference=paid_reference, settled=settled, now=self._now())  # fmt: skip
        status = marked["status"]
        facts = {"external_event_id": event_id, "reported_order_code": order_code,
                 "reported_amount_minor": amount_minor, "reported_currency": currency,
                 "provider_state": provider_state, "payload_digest": payload_digest,
                 "billing_order_id": marked.get("order_id"), "incarnation_id": marked.get("incarnation_id")}  # fmt: skip
        if status == "paid_deleted_account":
            self._item("paid_deleted_account", gateway, str(order_code), reason="paid after the account was deleted; "
                       "nothing granted, a refund is owed", **facts)  # fmt: skip
            return WebhookOutcome("paid_deleted_account")
        if status in _PAYMENT_ANOMALY:
            self._item(_PAYMENT_ANOMALY[status], gateway, event_id, reason=status, **facts)
            return WebhookOutcome(status)
        if status not in ("applied", "duplicate"):
            raise RuntimeError(f"unexpected payment status {status!r}")
        return self.sync_prepaid(marked["incarnation_id"], gateway, event_id=f"{gateway}:paid:{order_code}")

    def sync_prepaid(self, incarnation_id: str, gateway: str, *, event_id: str) -> WebhookOutcome:
        """Record the account's prepaid state, replayed from its orders, as its prepaid subscription. Safe to
        repeat: the same state under the same event id is a duplicate."""

        from writing_coach.persistence.commerce_repository import SubscriptionUpdate

        state = self._orders.prepaid_state(incarnation_id, gateway)
        active = state["paid_through"] is not None and state["paid_through"] > self._now()
        update = SubscriptionUpdate(state="active" if active else "ended", plan_id=state["plan_id"] or "free",
                                    external_customer_id=None, external_subscription_id=f"prepaid:{incarnation_id}",
                                    # nothing left (all refunded): access ends now, never "keep the old end"
                                    paid_through=state["paid_through"] or self._now(), cancel_at_period_end=True,
                                    provider_state="prepaid")  # fmt: skip
        outcome = self._commerce.record_event(incarnation_id=incarnation_id, provider=gateway, external_event_id=event_id,
                                              event_object_version=state["version"], update=update,
                                              external_object_reference=f"prepaid:{incarnation_id}")  # fmt: skip
        return self._outcome(outcome, f"{gateway} prepaid access of {incarnation_id}")

    def record_refund(self, *, order_code: int, note: str) -> WebhookOutcome:
        order = self._orders.order(order_code=order_code)
        if order is None:
            return WebhookOutcome("unknown_order")
        marked = self._orders.mark_refunded(order_code=order_code, note=note, now=self._now())
        if marked["status"] not in ("applied", "already_refunded"):
            return WebhookOutcome(marked["status"])
        # Also when already refunded: syncing again repairs a crash between the refund and the access record.
        return self.sync_prepaid(marked["incarnation_id"], order["gateway"], event_id=f"{order['gateway']}:refund:{order_code}")
