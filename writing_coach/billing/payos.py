"""payOS: the domestic VietQR gateway (proposals/BILLING_GATEWAYS.md; research 2026-10-05).

One payment link per order; there is no recurring charge, so Orena sells a prepaid period (billing/prepaid.py).

Signatures, as the official SDK computes them (payos 1.1.0, `payos/_crypto/provider.py`, read 2026-10-05):
- webhook: HMAC-SHA256 hex, keyed by the Checksum Key, of the webhook's `data` object as `key=value` pairs in
  sorted key order joined by `&`; None, "null" and "undefined" are empty, booleans are `true`/`false`, a list is
  compact JSON with each object's keys sorted;
- payment request: the same HMAC of exactly `amount`, `cancelUrl`, `description`, `orderCode`, `returnUrl` in that
  order.
A webhook says nothing about Orena's account: the order code is Orena's own, and the order row names the account.

The payment-request lookup (`GET /v2/payment-requests/{orderCode}`, PR-MON-3 §4.5) is how the reconciler finds a
payment whose webhook never came. Only PAID and CANCELLED are terminal answers; PENDING, PROCESSING and any other
status (EXPIRED included) are not, until the payOS sandbox shows otherwise (R-MON-013). The transaction reference is
read when it is plainly there and never guessed: the order, not the reference, is the unit of payment.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from writing_coach.billing.gateway import (
    CheckoutIntent,
    GatewayNotConfigured,
    PaymentFact,
    WebhookRejected,
    digest,
    hmac_sha256_hex,
    minor_units,
    same,
)

API_BASE = "https://api-merchant.payos.vn"
PAYMENT_REQUESTS = "/v2/payment-requests"
# payOS's own success code, on both the envelope and the data object.
SUCCESS = "00"
# The description shown in the learner's bank app; payOS limits it (9 characters without a linked account).
DESCRIPTION_LIMIT = 9
# The statuses payOS documents for a payment request; only two of them settle an order (R-MON-013).
DOCUMENTED_STATUSES = frozenset({"PAID", "PENDING", "PROCESSING", "CANCELLED"})
TERMINAL_STATUSES = frozenset({"PAID", "CANCELLED"})


@dataclass(frozen=True)
class Lookup:
    """What payOS answered about one payment request. `status` is upper-cased as given; `amount_paid` is None when
    the answer does not carry a whole number; `reference` is the single transaction's reference, or None."""

    status: str
    amount: int | None
    amount_paid: int | None
    payment_link_id: str
    reference: str | None

    @property
    def documented(self) -> bool:
        return self.status in DOCUMENTED_STATUSES


def parse_lookup(answer: Mapping[str, Any]) -> Lookup:
    """A lookup answer, normalized. Raises `ValueError` when it is not a successful answer about a payment request
    (an error code, no data): the caller treats that as no answer, never as a status."""

    data = answer.get("data") if isinstance(answer, Mapping) else None
    if str(answer.get("code") if isinstance(answer, Mapping) else "") != SUCCESS or not isinstance(data, Mapping):
        raise ValueError("payos_lookup_unanswered")
    transactions = data.get("transactions")
    reference = None
    if isinstance(transactions, list) and len(transactions) == 1 and isinstance(transactions[0], Mapping):
        value = transactions[0].get("reference")
        reference = value.strip()[:200] or None if isinstance(value, str) else None
    return Lookup(status=str(data.get("status") or "").strip().upper(), amount=minor_units(data.get("amount")),
                  amount_paid=minor_units(data.get("amountPaid")), payment_link_id=str(data.get("id") or ""),
                  reference=reference)  # fmt: skip


def _value(value: Any) -> str:
    if value is None or (isinstance(value, str) and value in {"undefined", "null"}):
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        items = [dict(sorted(item.items())) if isinstance(item, dict) else item for item in value]
        return json.dumps(items, separators=(",", ":"), ensure_ascii=False)
    return str(value)


def signing_string(data: Mapping[str, Any]) -> str:
    return "&".join(f"{key}={_value(data[key])}" for key in sorted(data))


def payment_request_string(*, amount: int, cancel_url: str, description: str, order_code: int, return_url: str) -> str:
    return f"amount={amount}&cancelUrl={cancel_url}&description={description}&orderCode={order_code}&returnUrl={return_url}"


class PayOSGateway:
    name = "payos"
    kind = "domestic"

    def __init__(self, *, client_id: str, api_key: str, checksum_key: str) -> None:
        if not (client_id and api_key and checksum_key):
            raise GatewayNotConfigured("payOS needs PAYOS_CLIENT_ID, PAYOS_API_KEY and PAYOS_CHECKSUM_KEY")
        self._client_id = client_id
        self._api_key = api_key
        self._checksum_key = checksum_key

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> PayOSGateway:
        return cls(client_id=str(env.get("PAYOS_CLIENT_ID", "")).strip(), api_key=str(env.get("PAYOS_API_KEY", "")).strip(),
                   checksum_key=str(env.get("PAYOS_CHECKSUM_KEY", "")).strip())  # fmt: skip

    def verify(self, headers: Mapping[str, str], body: bytes, *, now: datetime | None = None) -> PaymentFact:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WebhookRejected("unreadable_body") from error
        data = payload.get("data") if isinstance(payload, dict) else None
        signature = payload.get("signature") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or not isinstance(signature, str):
            raise WebhookRejected("missing_signature")
        if not same(hmac_sha256_hex(self._checksum_key, signing_string(data).encode("utf-8")), signature):
            raise WebhookRejected("bad_signature")
        order = data.get("orderCode")
        reference = str(data.get("reference") or data.get("paymentLinkId") or "")
        paid = str(payload.get("code")) == SUCCESS and payload.get("success") is not False and str(data.get("code", SUCCESS)) == SUCCESS
        return PaymentFact(
            gateway=self.name,
            event_id=f"{data.get('paymentLinkId') or ''}:{reference}:{order}",
            kind="payment" if paid and order is not None else "ignored",
            incarnation_hint=None,
            external_reference=str(order) if order is not None else None,
            amount_minor=minor_units(data.get("amount")),
            currency=str(data.get("currency") or "VND").upper(),
            provider_state=str(data.get("code") or payload.get("code") or ""),
            payload_digest=digest(body),
            # The receipt key is (gateway, event id), so the id needs no "payos:" prefix of its own.
            extra={"payment_link_id": str(data.get("paymentLinkId") or ""),
                   "reference": str(data.get("reference") or "")},
        )

    def lookup_request(self, order_code: int) -> dict:
        """The payment-request lookup for one order. Read-only; no signature is needed for it."""

        return {"method": "GET", "url": f"{API_BASE}{PAYMENT_REQUESTS}/{int(order_code)}",
                "headers": {"x-client-id": self._client_id, "x-api-key": self._api_key}}  # fmt: skip

    def checkout_request(self, intent: CheckoutIntent, *, order_code: int, description: str,
                         expires_at: datetime | None = None) -> dict:
        """The payment-request call for one order (`order_code` is the order row's own integer code)."""

        if intent.price.currency != "VND":
            raise ValueError("payOS takes VND only")
        text = description[:DESCRIPTION_LIMIT]
        body = {
            "orderCode": order_code, "amount": intent.price.amount_minor, "description": text,
            "cancelUrl": intent.cancel_url, "returnUrl": intent.return_url,
        }  # fmt: skip
        if expires_at is not None:
            body["expiredAt"] = int(expires_at.timestamp())  # H5: the link ends with the order (Unix seconds)
        body["signature"] = hmac_sha256_hex(self._checksum_key, payment_request_string(
            amount=intent.price.amount_minor, cancel_url=intent.cancel_url, description=text, order_code=order_code,
            return_url=intent.return_url).encode("utf-8"))  # fmt: skip
        return {"method": "POST", "url": API_BASE + PAYMENT_REQUESTS, "json": body,
                "headers": {"x-client-id": self._client_id, "x-api-key": self._api_key}}  # fmt: skip
