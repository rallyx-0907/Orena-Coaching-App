"""Billing: checkout, webhooks, cancel and an operator's refund record, over any gateway (BILLING_GATEWAYS.md).

Off unless `BILLING_ENABLED` is on - and even then a gateway without its keys, or a plan without an approved
price, is simply not offered. Prices come from the file `BILLING_PRICES_FILE` names (the human's decision,
never a default in code).

Access changes only through the commerce repository (`record_event`), from a verified gateway event:
- a merchant-of-record subscription event is recorded as the subscription's own state and revision;
- a domestic payment marks its order paid, and the account's prepaid state - replayed from its orders - is
  recorded as a `prepaid:<incarnation>` subscription whose version is the order count.
A checkout return URL grants nothing.
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

_log = logging.getLogger(__name__)
_ON = frozenset({"1", "true", "yes", "on"})
# Which currency each gateway takes, and whether it needs the gateway's own price id.
_GATEWAY_RULES = {"payos": ({"VND"}, False), "polar": (None, True)}
_LIVE = frozenset({"active", "trialing", "past_due", "paused", "pending"})


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
        currencies, needs_id = _GATEWAY_RULES.get(str(item["gateway"]), (None, False))
        if currencies is not None and str(item["currency"]).upper() not in currencies:
            raise ValueError(f"{item['gateway']} takes {', '.join(sorted(currencies))} only")
        if needs_id and not item.get("external_price_id"):
            raise ValueError(f"a {item['gateway']} price names the gateway's own price id")
        price = Price(plan_id=str(item["plan_id"]), period=item["period"], currency=str(item["currency"]).upper(),
                      amount_minor=amount, gateway=str(item["gateway"]),
                      external_price_id=str(item.get("external_price_id") or ""))  # fmt: skip
        prices[f"{price.plan_id}:{price.period}:{price.gateway}"] = price
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
                 send: Callable[[dict], dict] = _send, now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._orders = orders
        self._commerce = commerce
        self._gateways = dict(gateways)
        self._prices = dict(prices)
        self._send = send
        self._now = now

    def offered(self) -> list[dict[str, Any]]:
        return [{"key": key, "plan_id": price.plan_id, "period": price.period, "currency": price.currency,
                 "amount_minor": price.amount_minor, "gateway": price.gateway}
                for key, price in self._prices.items() if price.gateway in self._gateways]  # fmt: skip

    # ---- checkout -----------------------------------------------------------------------------------------

    def start_checkout(self, *, incarnation_id: str, price_key: str, operation_id: str, return_url: str,
                       cancel_url: str, customer_email: str = "") -> dict[str, Any]:
        price = self._prices.get(price_key)
        gateway = self._gateways.get(price.gateway) if price else None
        if price is None or gateway is None:
            raise LookupError("price_not_offered")
        uuid.UUID(operation_id)  # an operation id is the client's own UUID: a retry reuses it
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
                                               description=f"OR{order['order_code']}")  # fmt: skip
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
        # refunds and other verified events: logged; access follows the subscription's own events.
        _log.info("billing event from %s: %s %s", gateway_name, fact.kind, fact.provider_state)
        return WebhookOutcome("ignored", fact.kind)

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
            _log.warning("billing: %s subscription %s names no checkout of Orena", fact.gateway, fact.external_reference)
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
        return self._outcome(outcome, f"{fact.gateway} subscription {fact.external_reference}")

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
            return WebhookOutcome("ignored", "no_order_code")
        marked = self._orders.mark_paid(order_code=code, event_id=fact.event_id, amount_minor=fact.amount_minor,
                                        currency=fact.currency, payment_link_id=(fact.extra or {}).get("payment_link_id", ""),
                                        now=self._now())  # fmt: skip
        if marked["status"] == "paid_deleted_account":
            _log.error("billing: order %s was paid for a deleted account; nothing granted, refund it", code)
            return WebhookOutcome("paid_deleted_account")
        if marked["status"] not in ("applied", "duplicate"):
            _log.warning("billing payment for order %s not applied: %s", code, marked["status"])
            return WebhookOutcome(marked["status"])
        return self.sync_prepaid(marked["incarnation_id"], fact.gateway, event_id=f"{fact.gateway}:paid:{code}")

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
