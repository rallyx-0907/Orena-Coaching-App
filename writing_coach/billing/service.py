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

PR-MON-5 (design revision 3, D-MON-022): a **credit pack** (`BILLING_CREDIT_PACKS_FILE`, a human gate - no file, no
packs) is sold through the same payOS checkout as a `credit_pack` order that snapshots its units. Its payment is
recorded by the same `record_payment` (webhook or lookup); the paid order, not the event, is the source of truth, and
its credit is the ledger's exact top-up `billing_order / payos:<code>`. A full refund takes the credit back through a
ledger reversal (C5). Credit packs are sold only while credits are ready, and never while a credit gap is critical.

A verified money event is acknowledged only once it is durable (PR-MON-3, D-MON-004): as the order, a receipt, or a
reconciliation item (`persistence/billing_reconciliation_repository.py`). A business anomaly - an unknown order, a
mismatch, a payment for a deleted account, an undecidable subscription event, a refund - is recorded as an item and
then acknowledged; when that record cannot be written the call raises, and the route answers 503 so the provider
retries. An open critical item (paid without access, paid but unrecorded) closes new checkouts on its gateway.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from writing_coach.billing.gateway import (
    CheckoutIntent,
    GatewayNotConfigured,
    PaymentFact,
    Price,
    WebhookRejected,
    parse_time,
)
from writing_coach.billing.price_integrity import MINOR_EXPONENT, PriceCheck, blocked_gateways, check_prices
from writing_coach.product.catalog import DEFAULT_PLAN_ID, PLANS, CatalogUnavailable, current_plans

_log = logging.getLogger(__name__)
_ON = frozenset({"1", "true", "yes", "on"})
# Which currency each gateway takes, and whether it needs the gateway's own price id.
_GATEWAY_RULES = {"payos": ({"VND"}, False), "sepay": ({"VND"}, False), "polar": (None, True)}
# The domestic gateways a deployment may choose between (PR-MON-8 §5): exactly one is active, by explicit choice.
DOMESTIC_GATEWAYS = ("payos", "sepay")
# D-MON-032 (PR-MON-8 §14.2): plans are card subscriptions sold by Polar only. A domestic gateway tops up Credits.
PLAN_GATEWAYS = ("polar",)
DOMESTIC_SWITCH = "BILLING_DOMESTIC_GATEWAY"
# PR-MON-8 §4.3 (revision 6): the SePay locked outcomes are kept as the existing kind `payment_not_payable`, told apart
# by these machine-stable reasons. Business logic branches on the locked outcome, never on this text.
REASON_ORDER_CLOSED = "order_closed"
REASON_LATE_PAYMENT = "late_payment"
REASON_SOURCE_AMBIGUOUS = "source_ambiguous"
_LOCKED_REASONS = {"order_closed": REASON_ORDER_CLOSED, "late": REASON_LATE_PAYMENT,
                   "source_ambiguous": REASON_SOURCE_AMBIGUOUS}
GRACE_POLICY = "billing.domestic_late_payment_grace_hours"
# What a prices file may sell: a paid plan of the catalogue, by its own id (not a legacy alias).
_SELLABLE_PLANS = frozenset(plan_id for plan_id in PLANS if plan_id != DEFAULT_PLAN_ID)
_LIVE = frozenset({"active", "trialing", "past_due", "paused", "pending"})
# A payment Orena cannot apply, and the reconciliation item it is kept as (PR-MON-3 §4.2).
_PAYMENT_ANOMALY = {"unknown_order": "payment_unknown_order", "mismatch": "payment_mismatch",
                    "not_payable": "payment_not_payable"}
# A credit-pack price key: `credits:<pack_id>:payos`.
CREDIT_PREFIX = "credits:"
_PACK_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
# The credit gaps that close credit-pack checkouts (§6.2, §7.1); they never close plan checkouts.
CREDIT_CHECKOUT_BLOCKERS = ("credit_topup_unapplied", "credit_reversal_unapplied")
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
        if str(item["gateway"]) not in PLAN_GATEWAYS:
            raise ValueError("Plans are sold by Polar only (D-MON-032)")
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


@dataclass(frozen=True)
class CreditPack:
    """One pack of credits for sale (K1: the numbers are the human's, in the packs file, never a default here)."""

    pack_id: str
    credit_units: int
    currency: str
    amount_minor: int
    gateway: str

    @property
    def key(self) -> str:
        return f"{CREDIT_PREFIX}{self.pack_id}:{self.gateway}"


def load_credit_packs(env: Mapping[str, str]) -> dict[str, CreditPack]:
    """The credit packs on sale, keyed `credits:<pack_id>:<gateway>`. No file, no packs: nothing is sold (K1)."""

    path = str(env.get("BILLING_CREDIT_PACKS_FILE", "")).strip()
    if not path:
        return {}
    packs: dict[str, CreditPack] = {}
    for item in json.loads(Path(path).read_text(encoding="utf-8")):
        units, amount = item["credit_units"], item["amount_minor"]
        if type(units) is not int or units <= 0 or type(amount) is not int or amount <= 0:
            raise ValueError("a credit pack has positive integer units and a positive integer amount")
        if not _PACK_ID.match(str(item["pack_id"])):
            raise ValueError("a credit pack id is lower-case letters, digits, '-' or '_' (at most 40)")
        if str(item["gateway"]) not in DOMESTIC_GATEWAYS or str(item["currency"]).upper() != "VND":
            raise ValueError("credit packs are sold through a domestic gateway (payOS or SePay) in VND (D-MON-002)")
        pack = CreditPack(pack_id=str(item["pack_id"]), credit_units=units, currency="VND", amount_minor=amount,
                          gateway=str(item["gateway"]))  # fmt: skip
        if pack.key in packs:
            raise ValueError(f"{pack.key} is listed twice")
        packs[pack.key] = pack
    return packs


def build_gateways(env: Mapping[str, str]) -> dict[str, Any]:
    from writing_coach.billing.payos import PayOSGateway
    from writing_coach.billing.polar import PolarGateway
    from writing_coach.billing.sepay import SePayGateway

    gateways: dict[str, Any] = {}
    for factory in (PayOSGateway, SePayGateway, PolarGateway):
        try:
            gateway = factory.from_env(env)
        except GatewayNotConfigured:
            continue
        gateways[gateway.name] = gateway
    return gateways


def domestic_choice(env: Mapping[str, str]) -> str | None:
    """`BILLING_DOMESTIC_GATEWAY` as written (None when unset); validated against the configured gateways later."""

    value = str(env.get(DOMESTIC_SWITCH, "")).strip().casefold()
    return value or None


def late_payment_grace() -> timedelta | None:
    """The configured late-payment grace (PR-MON-8 §4.1). `<= 0` is the UNCONFIGURED sentinel, never a grace of zero;
    an unreadable policy is unconfigured too. None means no payment can be timely: every one fails closed."""

    from writing_coach import policies

    try:
        hours = policies.value_strict(GRACE_POLICY)
    except Exception:  # noqa: BLE001 - an unreadable grace is no grace: fail closed
        return None
    if type(hours) is not int or hours <= 0:
        return None
    return timedelta(hours=hours)


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
                 reconciliation: Any = None, credit_packs: Mapping[str, CreditPack] | None = None,
                 credits: Any = None, domestic: str | None = None, production: bool = False,
                 grace: Callable[[], timedelta | None] = late_payment_grace) -> None:
        self._orders = orders
        # PR-MON-8 §5: the explicitly chosen domestic gateway (`BILLING_DOMESTIC_GATEWAY`), and whether this runtime is
        # production (only outside production may a single configured domestic gateway be inferred).
        self._domestic_choice = (domestic or "").strip().casefold() or None
        self._production = production
        self._grace = grace
        self._credit_packs = dict(credit_packs or {})
        self._credits = credits  # the CreditService (PR-MON-4), only where credits are enabled
        # The reconciliation items (PR-MON-3). Without them no anomaly can be recorded, so none is acknowledged.
        self._items = reconciliation
        self._commerce = commerce
        self._gateways = dict(gateways)
        self._prices = dict(prices)
        # The catalogue in force, read strictly: a catalogue that cannot be read sells nothing.
        self._catalog = catalog
        self._send = send
        self._now = now
        # PR-MON-6 §8: the cost gate per pack. It can only remove a pack from sale (K1, K5); None = not attached.
        self._pack_gate: Any = None

    def attach_credits(self, credits: Any) -> None:
        self._credits = credits

    def attach_pack_gate(self, sellable: Any) -> None:
        """`sellable(pack_key) -> bool` (PR-MON-6 §8): a pack failing the cost gate is not offered and not sold."""
        self._pack_gate = sellable

    @property
    def credit_packs(self) -> Mapping[str, CreditPack]:
        return dict(self._credit_packs)

    def _pack_sellable(self, key: str) -> bool:
        if self._pack_gate is None:
            return True
        try:
            return bool(self._pack_gate(key))
        except Exception:  # noqa: BLE001 - an unreadable gate sells nothing
            return False

    @property
    def credits(self) -> Any:
        return self._credits

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

    def domestic_state(self) -> tuple[str | None, str | None]:
        """(the active domestic gateway, or None; the blocker when there is none but one is needed). A credential
        that appears or disappears never changes the choice (PR-MON-8 §5)."""

        configured = self.domestic_gateways()
        if self._domestic_choice is not None:
            if self._domestic_choice not in DOMESTIC_GATEWAYS or self._domestic_choice not in configured:
                return None, "domestic_gateway_unconfigured"
            return self._domestic_choice, None
        if self._production:
            # Approved §5: with billing on in production the choice is required, whatever is configured. There is no
            # international-only exception (review P1-2); that would be its own design delta.
            return None, "domestic_gateway_unset"
        if len(configured) == 1:
            return configured[0], None  # development / test convenience only
        return None, "domestic_gateway_unset" if configured else None

    def active_domestic(self) -> str | None:
        return self.domestic_state()[0]

    def domestic_blockers(self) -> list[str]:
        """What keeps domestic sales closed, for readiness: the gateway choice, and SePay's late-payment grace."""

        active, blocker = self.domestic_state()
        blockers = [blocker] if blocker else []
        if active == "sepay" and self._grace() is None:
            blockers.append("late_payment_grace_unset")
        if active == "sepay" and self._production and not getattr(self._gateways.get("sepay"), "has_va", False):
            # D-MON-030 / §13.3: production never shows a learner the main account - no VA, no SePay checkout
            blockers.append("sepay_va_unset")
        return blockers

    def _domestic_sellable(self, gateway_name: str) -> bool:
        """A domestic gateway sells only when it is the active one and, for SePay, its grace is configured."""

        if gateway_name not in DOMESTIC_GATEWAYS:
            return True
        return self.active_domestic() == gateway_name and not self.domestic_blockers()

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
                if price.gateway in PLAN_GATEWAYS and price.gateway in self._gateways
                and price.gateway not in blocked | critical}  # fmt: skip

    def offered(self) -> list[dict[str, Any]]:
        try:
            checks = self.price_checks()
        except CatalogUnavailable:
            _log.warning("billing: the plan catalogue cannot be read; nothing is offered", exc_info=True)
            return []
        return [{"key": key, "plan_id": price.plan_id, "period": price.period, "currency": price.currency,
                 "amount_minor": price.amount_minor, "gateway": price.gateway}
                for key, price in self._sellable(checks).items()]  # fmt: skip

    def credits_ready(self) -> bool:
        if self._credits is None:
            return False
        try:
            return bool(self._credits.status()["ready"])
        except Exception:  # noqa: BLE001 - a readiness that cannot be read is not ready
            return False

    def _credit_checkout_blocked(self) -> bool:
        """A critical payOS item, or an open credit gap (§6.2, §7.1), closes credit-pack checkouts; unreadable
        reconciliation state closes them too."""

        critical = self._critical_blocked()
        active = self.active_domestic()
        if critical is None or active is None or active in critical:
            return True
        try:
            open_by_kind = self._items.summary()["open_by_kind"] if self._items is not None else {}
        except Exception:  # noqa: BLE001
            return True
        return any(open_by_kind.get(kind, 0) for kind in CREDIT_CHECKOUT_BLOCKERS)

    def credit_offers(self) -> list[dict[str, Any]]:
        """The credit packs on sale now: none unless packs are configured, the active domestic gateway has its keys,
        credits are ready and no credit gap is critical (K5). A pack sells only through the active domestic gateway."""

        active = self.active_domestic()
        if not self._credit_packs or active is None or not self._domestic_sellable(active) or not self.credits_ready():
            return []
        if self._credit_checkout_blocked():
            return []
        return [{"key": pack.key, "pack_id": pack.pack_id, "credit_units": pack.credit_units, "currency": pack.currency,
                 "amount_minor": pack.amount_minor, "gateway": pack.gateway} for pack in self._credit_packs.values()
                if pack.gateway == active and self._pack_sellable(pack.key)]

    # ---- readiness per capability (PR-MON-8 §14.4) -------------------------------------------------------------

    def credits_configured(self) -> bool:
        """The Credits capability is in use: packs are configured, or credits are enabled (§14.3). Only then does the
        domestic gateway (its choice, its grace, its VA) block anything."""

        return bool(self._credit_packs) or self._credits is not None

    def plans_capability(self, report: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
        """Plans are sold by Polar only: configured, priced, every price the catalogue's, no critical item on it."""

        entry = (report if report is not None else self.gateway_report()).get("polar", {})
        blockers: list[str] = []
        if not entry.get("configured"):
            blockers.append("polar_unconfigured")
        if entry.get("catalog") == "unavailable":
            blockers.append("catalog_unavailable")
        elif not entry.get("prices"):
            blockers.append("no_polar_price")
        elif not all(check.get("status") == "match" for check in entry["prices"]):
            blockers.append("price_mismatch")
        if entry.get("reconciliation") == "unavailable":
            blockers.append("reconciliation_unavailable")
        elif entry.get("reconciliation_critical"):
            blockers.append("reconciliation_critical")
        return {"ready": not blockers, "blockers": blockers}

    def credits_capability(self) -> dict[str, Any]:
        """Credits top-up through the active domestic gateway: packs, credits ready, the gateway chosen and sellable
        (grace, VA in production), no critical item on it and no open credit gap."""

        if not self.credits_configured():
            return {"ready": False, "blockers": ["credits_not_configured"]}
        blockers: list[str] = []
        if not self._credit_packs:
            blockers.append("no_credit_pack")
        if not self.credits_ready():
            blockers.append("credits_not_ready")
        blockers.extend(self.domestic_blockers())
        critical = self._critical_blocked()
        active = self.active_domestic()
        if critical is None:
            blockers.append("reconciliation_unavailable")
        elif active is not None and active in critical:
            blockers.append("reconciliation_critical")
        else:
            try:
                open_by_kind = self._items.summary()["open_by_kind"] if self._items is not None else {}
            except Exception:  # noqa: BLE001 - unreadable reconciliation state sells nothing
                open_by_kind = None
            if open_by_kind is None:
                blockers.append("reconciliation_unavailable")
            elif any(open_by_kind.get(kind, 0) for kind in CREDIT_CHECKOUT_BLOCKERS):
                blockers.append("credit_gap_open")
        if not blockers and not self.credit_offers():
            blockers.append("no_sellable_pack")
        return {"ready": not blockers, "blockers": blockers}

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
            if name in DOMESTIC_GATEWAYS:
                entry["active_domestic"] = self.active_domestic() == name
                if not self._domestic_sellable(name):
                    entry["ready"] = False
            if name == "sepay" and gateway is not None:
                entry["late_payment_grace"] = "set" if self._grace() is not None else "unset"
                entry["virtual_account"] = "set" if getattr(gateway, "has_va", False) else "unset"
                entry["feed"] = "enabled" if getattr(gateway, "feed_enabled", False) else "disabled"
            if gateway is not None and getattr(gateway, "environment", None):
                entry["environment"] = gateway.environment
            if checks is None:
                entry["catalog"] = "unavailable"
            report[name] = entry
        return report

    # ---- checkout -----------------------------------------------------------------------------------------

    def start_checkout(self, *, incarnation_id: str, price_key: str, operation_id: str, return_url: str,
                       cancel_url: str, confirmed_amount_minor: int | None, confirmed_currency: str | None,
                       customer_email: str = "", confirmed_credit_units: int | None = None) -> dict[str, Any]:
        """`confirmed_*` is the price the learner saw and confirmed. It is never charged - the server's price is -
        but a checkout whose confirmed price is not the server's does not start (`price_changed`)."""

        if price_key.startswith(CREDIT_PREFIX):
            return self._start_credit_checkout(incarnation_id=incarnation_id, pack_key=price_key,
                                               operation_id=operation_id, return_url=return_url, cancel_url=cancel_url,
                                               amount=confirmed_amount_minor, currency=confirmed_currency,
                                               units=confirmed_credit_units)  # fmt: skip
        price = self._prices.get(price_key)
        gateway = self._gateways.get(price.gateway) if price else None
        # D-MON-032: a plan is sold by Polar only, whatever price reached this service (a second guard after
        # `load_prices`).
        if price is None or gateway is None or price.gateway not in PLAN_GATEWAYS:
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
            return self._open_domestic_link(gateway, intent, order, price.gateway)
        else:
            answer = self._send(gateway.checkout_request(intent))
            reference, url, qr = str(answer.get("id") or ""), str(answer.get("url") or ""), ""
        if not url:
            raise RuntimeError("gateway_checkout_failed")
        if reference:
            self._orders.set_reference(order["id"], reference)
        return {"redirect_url": url, "qr": qr, "order_code": int(order["order_code"]), "gateway": price.gateway}

    def _open_domestic_link(self, gateway: Any, intent: CheckoutIntent, order: Mapping[str, Any],
                            gateway_name: str) -> dict[str, Any]:
        """The payment instructions for a committed order: SePay's are built here (no provider call, PR-MON-8 G1);
        payOS's link is requested from payOS. No transaction or lock is held while a provider is called."""

        build = getattr(gateway, "domestic_checkout", None)
        if build is not None:
            start = build(intent, order)
            self._orders.mark_started(order["id"], now=self._now())
            return {**start, "order_code": int(order["order_code"]), "gateway": gateway_name}

        request = gateway.checkout_request(intent, order_code=int(order["order_code"]),
                                           description=f"OR{order['order_code']}",
                                           expires_at=order.get("expires_at"))  # fmt: skip
        data = self._send(request).get("data") or {}
        reference, url, qr = str(data.get("paymentLinkId") or ""), str(data.get("checkoutUrl") or ""), str(data.get("qrCode") or "")
        if not url:
            raise RuntimeError("gateway_checkout_failed")
        if reference:
            self._orders.set_reference(order["id"], reference)
        return {"redirect_url": url, "qr": qr, "order_code": int(order["order_code"]), "gateway": gateway_name}

    def _start_credit_checkout(self, *, incarnation_id: str, pack_key: str, operation_id: str, return_url: str,
                               cancel_url: str, amount: int | None, currency: str | None,
                               units: int | None) -> dict[str, Any]:
        """A credit pack, sold only at its configured amount and units, as confirmed by the learner, and only while
        credits are ready (§5). The order snapshots the pack; the browser's numbers are never charged or credited."""

        pack = self._credit_packs.get(pack_key)
        gateway = self._gateways.get(pack.gateway) if pack else None
        if (pack is None or gateway is None or not self._pack_sellable(pack.key)
                or pack.gateway != self.active_domestic() or not self._domestic_sellable(pack.gateway)):
            raise LookupError("price_not_offered")
        uuid.UUID(operation_id)
        if amount is None or not currency or units is None:
            raise CheckoutRefused("price_unconfirmed")
        if (type(amount) is not int or amount != pack.amount_minor or str(currency).strip().upper() != pack.currency
                or type(units) is not int or units != pack.credit_units):
            raise CheckoutRefused("price_changed")
        if not self.credits_ready() or self._credits.ensure_account(incarnation_id) is None:
            raise CheckoutRefused("credits_not_ready")
        if self._credit_checkout_blocked():
            raise CheckoutRefused("reconciliation_critical")
        order = self._orders.create_order(operation_id=operation_id, incarnation_id=incarnation_id, gateway=pack.gateway,
                                          plan_id=None, period=None, currency=pack.currency,
                                          amount_minor=pack.amount_minor, product_kind="credit_pack",
                                          credit_pack_id=pack.pack_id, credit_units=pack.credit_units)  # fmt: skip
        if order["conflict"]:
            raise CheckoutRefused("operation_conflict")
        if order["state"] != "created":
            raise CheckoutRefused("checkout_already_started" if order["state"] == "pending" else "order_closed")
        # The payment request needs only the amount and currency; the pack rides as the price's plan id.
        carrier = Price(plan_id=pack.pack_id, period="month", currency=pack.currency, amount_minor=pack.amount_minor,
                        gateway=pack.gateway)  # fmt: skip
        intent = CheckoutIntent(operation_id=operation_id, incarnation_id=incarnation_id, price=carrier,
                                return_url=return_url, cancel_url=cancel_url)  # fmt: skip
        return self._open_domestic_link(gateway, intent, order, pack.gateway)

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
            if getattr(gateway, "domestic_checkout", None) is not None:
                return self._domestic_payment(fact)  # PR-MON-8: decided under the order's lock
            return self._prepaid_payment(fact)
        if fact.kind == "subscription":
            return self._subscription(fact)
        if fact.kind == "refund":
            return self._refund(fact)
        # other verified events move no money: logged, no effect.
        _log.info("billing event from %s: %s %s", gateway_name, fact.kind, fact.provider_state)
        return WebhookOutcome("ignored", fact.kind)

    def handle_fact(self, fact: PaymentFact) -> WebhookOutcome:
        """A fact a recovery source normalized itself (the SePay feed, PR-MON-8 §6.3): the same decision path as a
        verified webhook's payment. Only a domestic gateway's payments are accepted here."""

        gateway = self._gateways.get(fact.gateway)
        if gateway is None or getattr(gateway, "domestic_checkout", None) is None:
            raise ValueError(f"{fact.gateway} has no recovery path")
        if fact.kind != "payment":
            return WebhookOutcome("ignored", fact.kind)
        return self._domestic_payment(fact)

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
        if fact.gateway in PLAN_GATEWAYS:
            # PR-MON-10 §4.5: the subscription's product is the source of truth for its plan, on every event (a plan
            # or period changed in Polar's portal arrives as a new product). An unknown or unpriced product changes
            # nothing: an operator item, never a fallback to the previous plan or to the checkout's metadata.
            product = str((fact.extra or {}).get("product_id") or "")
            plan = self._plan_for_product(product)
            if plan is None:
                self._item("event_undecided", fact.gateway, fact.event_id, external_event_id=fact.event_id,
                           provider_state=fact.provider_state, payload_digest=fact.payload_digest or None,
                           reason=f"unknown_product {product or '(none)'} on subscription {fact.external_reference}",
                           incarnation_id=incarnation)  # fmt: skip
                return WebhookOutcome("unknown", "unknown_product")
            sold = order["plan_id"] if order is not None and str(order["incarnation_id"]) == incarnation else None
            if sold is not None and sold != plan:
                _log.warning("billing: %s subscription %s is on plan %s, its checkout sold %s (portal change?)",
                             fact.gateway, fact.external_reference, plan, sold)  # fmt: skip
        else:
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

    def _plan_for_product(self, product_id: str) -> str | None:
        """The plan a Polar product is priced as (`external_price_id` in the prices file), or None."""

        if not product_id:
            return None
        plans = {price.plan_id for price in self._prices.values()
                 if price.gateway in PLAN_GATEWAYS and price.external_price_id == product_id}  # fmt: skip
        return plans.pop() if len(plans) == 1 else None

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

    def _domestic_payment(self, fact: PaymentFact) -> WebhookOutcome:
        """A SePay transfer (PR-MON-8 §4.1-§4.3). Eligibility and the transition to `paid` are one locked operation
        (`mark_paid_domestic`); every outcome that moves no order is recorded before this returns, so the webhook is
        acknowledged only once the money is accounted for. A failure to record raises, and the route answers 503."""

        extra = fact.extra or {}
        source_id = extra.get("source_id") or fact.event_id
        facts = {"external_event_id": source_id, "reported_amount_minor": fact.amount_minor,
                 "reported_currency": fact.currency, "provider_state": fact.provider_state,
                 "payload_digest": fact.payload_digest or None}  # fmt: skip
        if fact.external_reference is None:
            # Verified incoming money with no (or a foreign) payment code: recorded, never matched by amount (Q4).
            self._item("payment_unknown_order", fact.gateway, fact.event_id, reason="no readable order code", **facts)
            return WebhookOutcome("unknown_order", "no_order_code")
        order_code = int(fact.external_reference)
        transaction_at = parse_time(extra.get("transaction_at"))
        marked = self._orders.mark_paid_domestic(order_code=order_code, event_id=fact.event_id,
                                                 amount_minor=fact.amount_minor, currency=fact.currency,
                                                 transaction_at=transaction_at, grace=self._grace(),
                                                 paid_reference=extra.get("bank_reference") or None, now=self._now())
        status = marked["status"]
        facts = {**facts, "reported_order_code": order_code, "billing_order_id": marked.get("order_id"),
                 "incarnation_id": marked.get("incarnation_id")}
        if status in _LOCKED_REASONS:
            self._item("payment_not_payable", fact.gateway, fact.event_id, reason=_LOCKED_REASONS[status], **facts)
            return WebhookOutcome(status)
        if status == "paid_deleted_account":
            self._item("paid_deleted_account", fact.gateway, str(order_code), reason="paid after the account was "
                       "deleted; nothing granted, a refund is owed", **facts)  # fmt: skip
            return WebhookOutcome("paid_deleted_account")
        if status in _PAYMENT_ANOMALY:
            self._item(_PAYMENT_ANOMALY[status], fact.gateway, fact.event_id, reason=status, **facts)
            return WebhookOutcome(status)
        if status not in ("applied", "duplicate"):
            raise RuntimeError(f"unexpected domestic payment status {status!r}")
        if marked.get("product_kind") == "credit_pack":
            return self.apply_credit_topup(order_code, gateway=fact.gateway, facts=facts)
        return self.sync_prepaid(marked["incarnation_id"], fact.gateway, event_id=f"{fact.gateway}:paid:{order_code}")

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
        if marked.get("product_kind") == "credit_pack":
            return self.apply_credit_topup(order_code, gateway=gateway, facts=facts)
        return self.sync_prepaid(marked["incarnation_id"], gateway, event_id=f"{gateway}:paid:{order_code}")

    def apply_credit_topup(self, order_code: int, *, gateway: str = "payos",
                           facts: Mapping[str, Any] | None = None) -> WebhookOutcome:
        """Credit a paid credit-pack order (§6). A database error raises (the webhook answers 503 and payOS
        redelivers); a business refusal is answered once its obligation is durable or derivable: the paid order and
        its gap, which the reconciler repairs or escalates."""

        if self._credits is None:
            return WebhookOutcome("credit_pending", "credits_not_configured")
        outcome = self._credits.apply_credit_topup(order_code)
        if outcome.status == "applied":
            return WebhookOutcome("apply", "credit_topup")
        if outcome.status == "duplicate":
            return WebhookOutcome("duplicate", "credit_topup")
        if outcome.status == "account_deleted":
            order = self._orders.order(order_code=order_code) or {}
            # C1: no credit on a deleted account; the money is owed back through the existing money path
            self._item("paid_deleted_account", gateway, str(order_code),
                       reason="paid credit pack; the account was deleted before its credit; a refund is owed",
                       **{**(facts or {}), "billing_order_id": order.get("id"),
                          "incarnation_id": order.get("incarnation_id")})  # fmt: skip
            return WebhookOutcome("paid_deleted_account")
        if outcome.status == "order_refunded":
            return WebhookOutcome("refunded", "credit_not_given")
        return WebhookOutcome("credit_pending", outcome.status)

    def reverse_credit_topup(self, order_code: int, *, reason: str, actor: str = "system") -> WebhookOutcome:
        if self._credits is None:
            return WebhookOutcome("credit_pending", "credits_not_configured")
        outcome = self._credits.reverse_credit_topup(order_code, actor=actor, reason=reason)
        if outcome.status in ("applied", "duplicate"):
            return WebhookOutcome("apply" if outcome.status == "applied" else "duplicate", "credit_reversal")
        if outcome.status == "not_credited":
            return WebhookOutcome("refunded", "no_credit_to_reverse")
        return WebhookOutcome("credit_pending", outcome.status)

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
        if order.get("product_kind") == "credit_pack":
            # K2: a full refund takes back the full credit_units, C5 deciding what can be; also when already refunded
            return self.reverse_credit_topup(order_code, reason=f"payment refunded: {note}"[:400], actor="operator")
        # Also when already refunded: syncing again repairs a crash between the refund and the access record.
        return self.sync_prepaid(marked["incarnation_id"], order["gateway"], event_id=f"{order['gateway']}:refund:{order_code}")

    # ---- PR-MON-5: the reconciler's credit-order step (§6.2, §7.1) ----------------------------------------------------

    def reconcile_credit_orders(self, *, limit: int = 100) -> dict[str, int]:
        """Repair credit-pack gaps, escalate the ones that survive, and close a gap only on the fact its outcome names.
        Each write is its own short transaction; no provider is called."""

        counts = {"credit_topup_repaired": 0, "credit_topup_unapplied": 0, "credit_reversal_repaired": 0,
                  "credit_reversal_unapplied": 0, "credit_gap_resolved": 0, "credit_gap_unrecordable": 0,
                  "credit_gap_failed": 0}
        if self._credits is None:
            return counts
        repository = self._credits.repository
        # Not ready (a privileged or unreadable role): nothing is repaired, every gap is still escalated.
        repair = self.credits_ready()

        def each(gaps: list[dict[str, Any]], step: Callable[[dict[str, Any]], None]) -> None:
            for gap in gaps:
                try:
                    step(gap)
                except Exception:  # noqa: BLE001 - one gap never stops the others; it is retried next tick
                    _log.warning("credit gap %s could not be reconciled", gap.get("order_code"), exc_info=True)
                    counts["credit_gap_failed"] += 1

        def topup_gap(gap: dict[str, Any]) -> None:
            outcome = (self.apply_credit_topup(int(gap["order_code"]), gateway=gap["gateway"]) if repair
                       else WebhookOutcome("credit_pending", "credits_not_ready"))  # fmt: skip
            state = repository.credit_order_state(int(gap["order_code"])) or {}
            if state.get("credited"):
                counts["credit_topup_repaired"] += 1
            elif state.get("state") == "paid" and outcome.status != "paid_deleted_account":
                recorded = repository.record_credit_gap(kind="credit_topup_unapplied", order=gap,
                                                        reason=f"paid, not credited: {outcome.detail or outcome.status}")
                counts["credit_topup_unapplied" if recorded else "credit_gap_unrecordable"] += 1

        def reversal_gap(gap: dict[str, Any]) -> None:
            if repair:
                self.reverse_credit_topup(int(gap["order_code"]), reason="refund recorded; reversal repaired",
                                          actor="reconciler")  # fmt: skip
            state = repository.credit_order_state(int(gap["order_code"])) or {}
            if state.get("reversed"):
                counts["credit_reversal_repaired"] += 1
            else:
                topup = repository.entries_by_source("billing_order", f"{gap['gateway']}:{gap['order_code']}")
                recorded = repository.record_credit_gap(kind="credit_reversal_unapplied", order=gap,
                                                        reason="refunded; the credit reversal is not complete",
                                                        topup_entry_id=topup)  # fmt: skip
                counts["credit_reversal_unapplied" if recorded else "credit_gap_unrecordable"] += 1

        def close_topup_gap(gap: dict[str, Any]) -> None:
            state = repository.credit_order_state(int(gap["order_code"])) or {}
            outcome = ("credit_applied" if state.get("credited")
                       else "payment_refunded" if state.get("state") == "refunded"
                       else "refund_obligation_recorded" if repository.refund_obligation_recorded(state.get("id"))
                       else None)  # fmt: skip
            if outcome and self._items.auto_resolve(kind="credit_topup_unapplied", gateway="credits",
                                                    dedupe_key=gap["dedupe_key"], outcome=outcome,
                                                    note=f"closed by the reconciler: {outcome}", now=self._now()):
                counts["credit_gap_resolved"] += 1

        def close_reversal_gap(gap: dict[str, Any]) -> None:
            state = repository.credit_order_state(int(gap["order_code"])) or {}
            if state.get("reversed") and self._items.auto_resolve(
                    kind="credit_reversal_unapplied", gateway="credits", dedupe_key=gap["dedupe_key"],
                    outcome="credit_reversed", note="the complete reversal exists", now=self._now()):
                counts["credit_gap_resolved"] += 1

        each(repository.credit_topup_gaps(limit=limit), topup_gap)
        each(repository.credit_reversal_gaps(limit=limit), reversal_gap)
        each(repository.open_credit_gaps("credit_topup_unapplied"), close_topup_gap)
        each(repository.open_credit_gaps("credit_reversal_unapplied"), close_reversal_gap)
        return counts
