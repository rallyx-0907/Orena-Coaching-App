"""Polar: the merchant of record for international cards (proposals/BILLING_GATEWAYS.md; research 2026-10-05).

Polar runs the subscription (renewal, cancel, refund, sales tax) and is the seller of record; Orena learns the
subscription's state from signed webhooks.

Signatures are Standard Webhooks (polar.sh/docs/integrate/webhooks/delivery, read 2026-10-05): headers
`webhook-id`, `webhook-timestamp` (unix seconds) and `webhook-signature` (space-separated `v1,<base64>`), each an
HMAC-SHA256 of `{id}.{timestamp}.{raw body}`. The key is the base64 part of a `whsec_` secret; secrets created
before 2026-09-08 are used as their own UTF-8 bytes instead, so both keys are tried. A timestamp more than five
minutes from server time is refused (replay).

The subscription's own `modified_at` is its revision (gateway.version_of); Orena's account and price travel in
the checkout's `metadata` and come back on the subscription, and the stored provider-subscription mapping
overrules them once it exists.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from writing_coach.billing.gateway import (
    CheckoutIntent,
    GatewayNotConfigured,
    PaymentFact,
    WebhookRejected,
    digest,
    minor_units,
    parse_time,
    version_of,
)

API_BASE = {"production": "https://api.polar.sh", "sandbox": "https://sandbox-api.polar.sh"}
TOLERANCE = timedelta(minutes=5)
# Polar subscription status -> Orena's canonical state (ORENA_COMMERCE_ARCHITECTURE.md §3).
STATES = {"incomplete": "pending", "incomplete_expired": "ended", "trialing": "trialing", "active": "active",
          "past_due": "past_due", "canceled": "ended", "unpaid": "past_due"}  # fmt: skip
SUBSCRIPTION_EVENTS = frozenset({"subscription.created", "subscription.updated", "subscription.active",
                                 "subscription.canceled", "subscription.uncanceled", "subscription.revoked"})  # fmt: skip
REFUND_EVENTS = frozenset({"refund.created", "refund.updated"})


def _keys(secret: str) -> list[bytes]:
    keys = []
    if secret.startswith("whsec_"):
        try:
            keys.append(base64.b64decode(secret[len("whsec_"):], validate=True))
        except (binascii.Error, ValueError):
            pass
    keys.append(secret.encode("utf-8"))
    return keys


def sign(secret_key: bytes, message_id: str, timestamp: str, body: bytes) -> str:
    mac = hmac.new(secret_key, f"{message_id}.{timestamp}.".encode() + body, hashlib.sha256).digest()
    return "v1," + base64.b64encode(mac).decode("ascii")


class PolarGateway:
    name = "polar"
    kind = "merchant_of_record"

    def __init__(self, *, access_token: str, webhook_secret: str, environment: str = "sandbox") -> None:
        if not (access_token and webhook_secret):
            raise GatewayNotConfigured("Polar needs POLAR_ACCESS_TOKEN and POLAR_WEBHOOK_SECRET")
        if environment not in API_BASE:
            raise GatewayNotConfigured("POLAR_ENVIRONMENT is sandbox or production")
        self._token = access_token
        self._secret = webhook_secret
        self.environment = environment

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> PolarGateway:
        return cls(access_token=str(env.get("POLAR_ACCESS_TOKEN", "")).strip(),
                   webhook_secret=str(env.get("POLAR_WEBHOOK_SECRET", "")).strip(),
                   environment=str(env.get("POLAR_ENVIRONMENT", "sandbox")).strip() or "sandbox")  # fmt: skip

    def verify(self, headers: Mapping[str, str], body: bytes, *, now: datetime | None = None) -> PaymentFact:
        lowered = {key.casefold(): value for key, value in headers.items()}
        message_id = str(lowered.get("webhook-id") or "")
        timestamp = str(lowered.get("webhook-timestamp") or "")
        given = str(lowered.get("webhook-signature") or "").split()
        if not (message_id and timestamp.isascii() and timestamp.isdigit() and len(timestamp) <= 12 and given):
            raise WebhookRejected("missing_signature")
        try:
            sent = datetime.fromtimestamp(int(timestamp), UTC)
        except (OverflowError, OSError, ValueError):
            raise WebhookRejected("stale_timestamp") from None
        if abs((now or datetime.now(UTC)) - sent) > TOLERANCE:
            raise WebhookRejected("stale_timestamp")
        expected = {sign(key, message_id, timestamp, body).encode("ascii") for key in _keys(self._secret)}
        offered = [signature.encode("ascii") for signature in given if signature.isascii()]
        if not any(hmac.compare_digest(candidate, signature) for candidate in expected for signature in offered):
            raise WebhookRejected("bad_signature")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WebhookRejected("unreadable_body") from error
        return self._normalize(message_id, payload, digest(body))

    def _normalize(self, message_id: str, payload: Any, body_digest: str) -> PaymentFact:
        kind = str(payload.get("type") or "") if isinstance(payload, dict) else ""
        data = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else {}
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        base = {"gateway": self.name, "event_id": message_id, "payload_digest": body_digest,
                "incarnation_hint": str(metadata.get("orena_incarnation") or "") or None,
                "extra": {"orena_operation": str(metadata.get("orena_operation") or "")}}  # fmt: skip
        if kind in SUBSCRIPTION_EVENTS:
            status = str(data.get("status") or "")
            return PaymentFact(
                **base, kind="subscription", external_reference=str(data.get("id") or "") or None,
                object_version=version_of(parse_time(data.get("modified_at")) or parse_time(data.get("created_at"))),
                state=STATES.get(status, "unknown"), provider_state=status or None,
                plan_id=str(metadata.get("orena_plan") or "") or None,
                external_customer_id=str(data.get("customer_id") or "") or None,
                paid_through=parse_time(data.get("current_period_end")),
                cancel_at_period_end=bool(data.get("cancel_at_period_end")),
            )  # fmt: skip
        if kind in REFUND_EVENTS:
            return PaymentFact(
                **base, kind="refund", external_reference=str(data.get("subscription_id") or data.get("order_id") or "") or None,
                provider_state=str(data.get("status") or "") or None, amount_minor=minor_units(data.get("amount")),
                currency=str(data.get("currency") or "").upper() or None,
            )  # fmt: skip
        return PaymentFact(**base, kind="ignored", external_reference=None, provider_state=kind or None)

    def checkout_request(self, intent: CheckoutIntent) -> dict:
        if not intent.price.external_price_id:
            raise ValueError("a Polar price is a Polar product id")
        body = {
            "products": [intent.price.external_price_id], "success_url": intent.return_url,
            "metadata": {"orena_incarnation": intent.incarnation_id, "orena_plan": intent.price.plan_id,
                         "orena_operation": intent.operation_id},
        }  # fmt: skip
        if intent.customer_email:
            body["customer_email"] = intent.customer_email
        return {"method": "POST", "url": API_BASE[self.environment] + "/v1/checkouts/", "json": body,
                "headers": {"Authorization": f"Bearer {self._token}"}}  # fmt: skip
