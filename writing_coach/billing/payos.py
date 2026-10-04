"""payOS: the domestic VietQR gateway (proposals/BILLING_GATEWAYS.md; research 2026-10-05).

One payment link per order; there is no recurring charge, so Orena sells a prepaid period (billing/prepaid.py).

Signatures, as the official SDK computes them (payos 1.1.0, `payos/_crypto/provider.py`, read 2026-10-05):
- webhook: HMAC-SHA256 hex, keyed by the Checksum Key, of the webhook's `data` object as `key=value` pairs in
  sorted key order joined by `&`; None, "null" and "undefined" are empty, booleans are `true`/`false`, a list is
  compact JSON with each object's keys sorted;
- payment request: the same HMAC of exactly `amount`, `cancelUrl`, `description`, `orderCode`, `returnUrl` in that
  order.
A webhook says nothing about Orena's account: the order code is Orena's own, and the order row names the account.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
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
            extra={"payment_link_id": str(data.get("paymentLinkId") or "")},
        )

    def checkout_request(self, intent: CheckoutIntent, *, order_code: int, description: str) -> dict:
        """The payment-request call for one order (`order_code` is the order row's own integer code)."""

        if intent.price.currency != "VND":
            raise ValueError("payOS takes VND only")
        text = description[:DESCRIPTION_LIMIT]
        body = {
            "orderCode": order_code, "amount": intent.price.amount_minor, "description": text,
            "cancelUrl": intent.cancel_url, "returnUrl": intent.return_url,
        }  # fmt: skip
        body["signature"] = hmac_sha256_hex(self._checksum_key, payment_request_string(
            amount=intent.price.amount_minor, cancel_url=intent.cancel_url, description=text, order_code=order_code,
            return_url=intent.return_url).encode("utf-8"))  # fmt: skip
        return {"method": "POST", "url": API_BASE + PAYMENT_REQUESTS, "json": body,
                "headers": {"x-client-id": self._client_id, "x-api-key": self._api_key}}  # fmt: skip
