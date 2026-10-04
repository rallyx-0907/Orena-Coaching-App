"""The common payment layer: what every gateway adapter gives Orena, whichever company is behind it.

Completion plan item 4 (proposals/BILLING_GATEWAYS.md). Two kinds of gateway sit behind it:

- a **merchant of record** for international cards, which runs the subscription itself (renewal, cancel,
  refund, tax) and tells Orena about it with signed subscription events;
- a **domestic** QR / bank-transfer gateway, which takes one payment at a time. Orena sells a prepaid period
  with it (one month, one year); a renewal is a new payment that extends the period, never an automatic charge.

An adapter only *verifies* and *normalizes*. It turns a provider's signed webhook into a `PaymentFact`, and a
checkout intent into the provider's request. It decides nothing about access: that is the commerce
repository's (`persistence/commerce_repository.py`, `reference_backbone.subscription_event_decision`), and a
checkout return URL never grants anything (ORENA_COMMERCE_ARCHITECTURE.md §3).

Nothing here is active: no route accepts a payment until `BILLING_ENABLED` is on and the gateway's keys are
configured - both human gates.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Protocol

FactKind = Literal["subscription", "payment", "refund", "ignored"]


class WebhookRejected(Exception):
    """The webhook is not provably from the gateway (bad or missing signature, stale timestamp, unreadable body).

    The route answers 401 and stores nothing: an unverified body is never a receipt."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class GatewayNotConfigured(Exception):
    """The gateway's keys are not in the environment (a human gate)."""


@dataclass(frozen=True)
class Price:
    """One approved price of one plan on one gateway. Money is an integer of the currency's minor unit (VND has
    none, so it is whole dong); never a float, never inferred from a label."""

    plan_id: str
    period: Literal["month", "year"]
    currency: str
    amount_minor: int
    gateway: str
    external_price_id: str = ""  # the merchant of record's own price id; empty for a domestic gateway


@dataclass(frozen=True)
class CheckoutIntent:
    """What a signed-in learner asked to buy. `operation_id` is unique per attempt (a retry reuses it)."""

    operation_id: str
    incarnation_id: str
    price: Price
    return_url: str
    cancel_url: str
    customer_email: str = ""


@dataclass(frozen=True)
class CheckoutStart:
    """Where to send the learner, and the gateway's reference for the attempt."""

    gateway: str
    redirect_url: str
    external_reference: str
    qr_payload: str = ""  # a domestic gateway's VietQR string, when it gives one


@dataclass(frozen=True)
class PaymentFact:
    """One verified gateway event, normalized.

    - `subscription`: a merchant-of-record subscription's current state (`state`, `paid_through`,
      `cancel_at_period_end`, `object_version` = the provider's own revision of that subscription).
    - `payment`: a domestic one-off payment for a prepaid period (`external_reference` = the order).
    - `refund`: money returned for a payment or a subscription.
    - `ignored`: verified but not about a subscription or payment Orena sold (logged, receipted, no effect).
    `incarnation_hint` is what Orena put in the checkout; the commerce repository's stored mapping overrules it.
    """

    gateway: str
    event_id: str
    kind: FactKind
    incarnation_hint: str | None
    external_reference: str | None
    object_version: int | None = None
    state: str | None = None
    provider_state: str | None = None
    plan_id: str | None = None
    external_customer_id: str | None = None
    paid_through: datetime | None = None
    cancel_at_period_end: bool = False
    amount_minor: int | None = None
    currency: str | None = None
    payload_digest: str = ""
    extra: Mapping[str, str] = field(default_factory=dict)


class Gateway(Protocol):
    name: str
    kind: Literal["merchant_of_record", "domestic"]

    def verify(self, headers: Mapping[str, str], body: bytes, *, now: datetime | None = None) -> PaymentFact: ...

    def checkout_request(self, intent: CheckoutIntent) -> dict: ...


# ---- shared helpers -----------------------------------------------------------------------------------------

def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def hmac_sha256_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def same(expected: str, given: str) -> bool:
    """Constant-time comparison of two hex signatures, case-insensitive."""

    if not isinstance(given, str) or not given or not given.isascii():
        return False
    return hmac.compare_digest(expected.casefold().encode("ascii"), given.strip().casefold().encode("ascii"))


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def version_of(value: datetime | None) -> int | None:
    """A provider object's own last-change time, in microseconds, as its revision: the provider's statement of
    when *that object* changed, not when Orena received the event (§3 forbids arrival time)."""

    return int(value.timestamp() * 1_000_000) if value is not None else None


def minor_units(amount: object) -> int | None:
    """A provider's integer or decimal-string amount in minor units, or None when it is not a whole number."""

    try:
        value = Decimal(str(amount))
        if not value.is_finite() or abs(value) > 10**15:
            return None
        return int(value) if value == value.to_integral_value() else None
    except Exception:  # noqa: BLE001 - not a number: no amount
        return None
