"""PR-MON-9: an existing Polar subscriber's plan changes, cancellation, resumption and invoices, in the app through
Polar's API (D-MON-033; `docs/billing/PR-MON-9_DESIGN.md` revision 3.1).

Truth sources are never mixed:
* Polar is the truth for payment (total, tax, card, a charge's outcome);
* Orena's webhook-fed commerce record is the truth for access. Nothing here grants: a route only asks Polar, and the
  subscription webhook (PR-MON-10) moves the record.

Every Polar write (`change`, `cancel`, `resume`) goes through the **operation journal** (§4.2.1). One
`platform_settings` document per client `operation_id`, written with compare-and-set:
* the operation is persisted `pending`, with a lease, **before** any Polar call;
* its owner marks it `sent` (CAS on version and owner) and only then sends the PATCH: **at most one PATCH per
  operation, ever**;
* an ambiguous answer (timeout, 5xx, broken connection) is `provider_unknown`, reconciled by GET only;
* a stale `pending` (never sent) may be claimed within `CLAIM_WINDOW` and sends the first PATCH; later it is
  `not_applied`; a stale `sent` is reconciled by GET only and never resent.

Scheduled changes (`next_period`) are **off** until the sandbox proves their exits (§3.6.1): with them off a downgrade
or period-down is refused (`change_unavailable`) and no account enters `active+pending`. The proration preview is
case B (no amount) until the sandbox proves an authoritative preview (§3.3).
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

from sqlalchemy import text

_log = logging.getLogger(__name__)

# §3.6.1 / §3.3: switched on only by the sandbox proof recorded in PR-MON-9_E2E_EVIDENCE.md, never by a client.
SCHEDULED_CHANGES = False
PRORATION_PREVIEW = False

OP_PREFIX = "billing.polar.op."
INVOICE_PREFIX = "billing.polar.invoice_asked."
LEASE = timedelta(seconds=30)
CLAIM_WINDOW = timedelta(minutes=10)
UNKNOWN_SETTLE = timedelta(minutes=15)
RETENTION = timedelta(days=90)
ESCALATE_AFTER = timedelta(hours=24)
ENRICHMENT_SECONDS = 30.0
TIERS = {"free": 0, "plus": 1, "pro": 2}
PERIODS = {"month": 0, "year": 1}
# §4.3: the design's reason chips -> Polar's `customer_cancellation_reason` (closed list; no free-text comment).
REASONS = {"too_expensive": "too_expensive", "not_using": "unused", "missing_feature": "missing_features",
           "taking_a_break": "other"}
TERMINAL = ("done", "refused", "not_applied")


class SubscriptionRefused(Exception):
    """A request this account's subscription cannot take (an HTTP 4xx with a stable code)."""

    def __init__(self, code: str, status: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


def classify(current: tuple[str, str], target: tuple[str, str]) -> dict[str, str]:
    """§3.5, the canonical matrix: **the feature tier wins over the billing period**.

    Returns {kind, proration, effect}: kind is upgrade | downgrade | period_up | period_down | none."""

    (tier, period), (to_tier, to_period) = current, target
    if TIERS[to_tier] > TIERS[tier]:
        return {"kind": "upgrade", "proration": "invoice", "effect": "now"}
    if TIERS[to_tier] < TIERS[tier]:
        return {"kind": "downgrade", "proration": "next_period", "effect": "renewal"}
    if PERIODS[to_period] > PERIODS[period]:
        return {"kind": "period_up", "proration": "invoice", "effect": "now"}
    if PERIODS[to_period] < PERIODS[period]:
        return {"kind": "period_down", "proration": "next_period", "effect": "renewal"}
    return {"kind": "none", "proration": "", "effect": ""}


def _digest(request: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def polar_call(request: Mapping[str, Any]) -> tuple[int, Any]:
    """Send one Polar request; answer (status, parsed body or None). Raises only for a transport failure (timeout,
    refused connection): the caller reads that as an ambiguous outcome."""

    data = json.dumps(request["json"]).encode() if "json" in request else None
    call = urllib.request.Request(str(request["url"]), data=data, method=str(request["method"]),
                                  headers={"Content-Type": "application/json", "Accept": "application/json",
                                           "User-Agent": "Orena-Billing/1.0", **request["headers"]})  # fmt: skip
    try:
        with urllib.request.urlopen(call, timeout=20) as response:  # noqa: S310 - the fixed Polar API host
            raw = response.read(1_000_000)
            return int(response.status), (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        return int(error.code), None


class PolarSubscriptions:
    def __init__(self, *, gateway: Any, commerce: Any, prices: Mapping[str, Any], settings: Any, items: Any = None,
                 call: Callable[[Mapping[str, Any]], tuple[int, Any]] = polar_call,
                 now: Callable[[], datetime] = lambda: datetime.now(UTC),
                 scheduled_changes: bool | None = None, proration_preview: bool | None = None,
                 index: Any = None) -> None:
        self._index = index  # lists and deletes journal keys (PostgresOperationIndex); None: no retention pass
        self._gateway = gateway  # the PolarGateway (None: Polar is not configured)
        self._commerce = commerce
        self._prices = dict(prices)
        self._settings = settings
        self._items = items
        self._call = call
        self._now = now
        self._scheduled = SCHEDULED_CHANGES if scheduled_changes is None else scheduled_changes
        self._preview = PRORATION_PREVIEW if proration_preview is None else proration_preview
        self._enrichment: dict[str, tuple[datetime, dict[str, Any]]] = {}

    # ---- Polar requests ------------------------------------------------------------------------------------

    def _request(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._gateway.api_request(method, path, body)

    def _read(self, path: str) -> Any:
        status, body = self._call(self._request("GET", path))
        if status != 200:
            raise RuntimeError(f"polar_read_{status}")
        return body

    # ---- whose subscription ---------------------------------------------------------------------------------

    def _mine(self, incarnation_id: str) -> dict[str, Any]:
        if self._gateway is None:
            raise SubscriptionRefused("polar_unavailable", 503)
        current = self._commerce.get_subscription(incarnation_id)
        if not current or current.get("provider") != "polar" or not current.get("external_subscription_id"):
            raise SubscriptionRefused("no_subscription", 404)
        return current

    def _plan_of(self, product_id: str) -> tuple[str, str] | None:
        found = {(p.plan_id, p.period) for p in self._prices.values()
                 if p.gateway == "polar" and p.external_price_id == product_id}  # fmt: skip
        return found.pop() if len(found) == 1 else None

    def _live(self, subscription_id: str) -> dict[str, Any]:
        return self._read(f"/v1/subscriptions/{quote(subscription_id, safe='')}")

    # ---- §4.1 the subscription view -------------------------------------------------------------------------

    def view(self, incarnation_id: str) -> dict[str, Any]:
        """The local record, fresh on every call (access truth), plus Polar enrichment cached ENRICHMENT_SECONDS."""

        current = self._commerce.get_subscription(incarnation_id) or {}
        paid_through = current.get("paid_through")
        answer: dict[str, Any] = {
            "plan": current.get("plan_id") or "free", "status": current.get("state") or "none",
            "provider": current.get("provider"),
            "renews_at": paid_through.isoformat() if paid_through else None,
            "cancel_at_period_end": bool(current.get("cancel_at_period_end")),
        }
        if current.get("provider") != "polar" or not current.get("external_subscription_id") or self._gateway is None:
            return {**answer, "period": None, "pending_change": None, "payment_method": None,
                    "billing_email": None, "enrichment": "none"}  # fmt: skip
        try:
            answer.update(self._enriched(incarnation_id, str(current["external_subscription_id"])))
            answer["enrichment"] = "live"
        except Exception:  # noqa: BLE001 - the local fields stand alone
            _log.warning("billing: Polar enrichment unavailable", exc_info=True)
            answer.update(period=None, pending_change=None, payment_method=None, billing_email=None,
                          enrichment="unavailable")
        return answer

    def _enriched(self, incarnation_id: str, subscription_id: str) -> dict[str, Any]:
        cached = self._enrichment.get(incarnation_id)
        if cached is not None and cached[0] > self._now():
            return cached[1]
        live = self._live(subscription_id)
        pending = live.get("pending_update") if isinstance(live.get("pending_update"), dict) else None
        target = self._plan_of(str(pending.get("product_id") or "")) if pending else None
        customer = live.get("customer") if isinstance(live.get("customer"), dict) else {}
        value = {
            "period": live.get("recurring_interval"),
            "pending_change": ({"plan": target[0], "period": target[1],
                                "applies_at": pending.get("applies_at") or live.get("current_period_end")}
                               if target else None),
            # §4.4 (proved on the sandbox, 2026-10-18): brand, last4 and expiry only - never more of the card
            "payment_method": self._card(str(live.get("customer_id") or "")),
            "billing_email": customer.get("email") or None,
        }  # fmt: skip
        self._enrichment[incarnation_id] = (self._now() + timedelta(seconds=ENRICHMENT_SECONDS), value)
        return value

    def _card(self, customer_id: str) -> dict[str, Any] | None:
        """The default card's summary (`GET /v1/customers/{id}/payment-methods`), or None when unreadable."""

        if not customer_id:
            return None
        try:
            status, body = self._call(self._request("GET", f"/v1/customers/{quote(customer_id, safe='')}/payment-methods"))
        except Exception:  # noqa: BLE001 - the row then reads "Card on file"
            return None
        items = (body or {}).get("items") if isinstance(body, dict) else body
        if status != 200 or not isinstance(items, list) or not items:
            return None
        chosen = next((m for m in items if isinstance(m, dict) and m.get("is_default")), items[0])
        card = chosen.get("method_metadata") if isinstance(chosen, dict) else None
        if not isinstance(card, dict) or not card.get("last4"):
            return None
        return {"brand": str(card.get("brand") or ""), "last4": str(card["last4"])[-4:],
                "exp_month": card.get("exp_month"), "exp_year": card.get("exp_year")}

    def forget(self, incarnation_id: str) -> None:
        """Drop the enrichment (a route of this account changed the subscription, or its webhook arrived)."""

        self._enrichment.pop(incarnation_id, None)

    # ---- §4.2 plan change -----------------------------------------------------------------------------------

    def preview(self, incarnation_id: str, price_key: str) -> dict[str, Any]:
        mine = self._mine(incarnation_id)
        _, change = self._target(mine, price_key)
        answer = {"kind": change["kind"], "takes_effect": change["effect"]}
        if not self._preview:
            answer["due_today"] = None  # case B: Polar computes the proration; Orena shows no number
        return answer

    def _target(self, mine: Mapping[str, Any], price_key: str) -> tuple[Any, dict[str, str]]:
        price = self._prices.get(price_key)
        if price is None or price.gateway != "polar":
            raise SubscriptionRefused("price_not_offered", 404)
        if mine.get("state") not in ("active", "trialing", "past_due"):
            raise SubscriptionRefused("no_subscription", 404)
        if mine.get("cancel_at_period_end"):
            raise SubscriptionRefused("cancelling")  # Resume first (§3.6)
        live = self._live(str(mine["external_subscription_id"]))
        here = self._plan_of(str(live.get("product_id") or ""))
        if here is None:
            raise SubscriptionRefused("unknown_product", 409)
        change = classify(here, (price.plan_id, price.period))
        if change["kind"] == "none":
            raise SubscriptionRefused("no_change")
        if live.get("pending_update"):
            if change["effect"] == "renewal":
                raise SubscriptionRefused("change_pending")  # one scheduled change at a time
        if change["effect"] == "renewal" and not self._scheduled:
            raise SubscriptionRefused("change_unavailable")  # §3.6.1 fail-closed
        return price, change

    def change(self, incarnation_id: str, price_key: str, operation_id: str) -> dict[str, Any]:
        mine = self._mine(incarnation_id)

        def build() -> tuple[dict[str, Any], dict[str, Any]]:
            price, change = self._target(mine, price_key)
            return ({"product_id": price.external_price_id, "proration_behavior": change["proration"]},
                    {"product_id": price.external_price_id})

        return self._run(incarnation_id, operation_id, "change", str(mine["external_subscription_id"]),
                         {"price": price_key}, build)

    # ---- §4.3 cancel and resume ------------------------------------------------------------------------------

    def cancel(self, incarnation_id: str, reason: str | None, operation_id: str) -> dict[str, Any]:
        if reason is not None and reason not in REASONS:
            raise SubscriptionRefused("reason_invalid", 422)
        mine = self._mine(incarnation_id)

        def build() -> tuple[dict[str, Any], dict[str, Any]]:
            if mine.get("state") not in ("active", "trialing", "past_due") or mine.get("cancel_at_period_end"):
                raise SubscriptionRefused("not_cancellable")
            body: dict[str, Any] = {"cancel_at_period_end": True}
            if reason is not None:
                body["customer_cancellation_reason"] = REASONS[reason]
            return body, {"cancel_at_period_end": True}

        return self._run(incarnation_id, operation_id, "cancel", str(mine["external_subscription_id"]),
                         {"reason": reason}, build)

    def resume(self, incarnation_id: str, operation_id: str) -> dict[str, Any]:
        mine = self._mine(incarnation_id)

        def build() -> tuple[dict[str, Any], dict[str, Any]]:
            if not mine.get("cancel_at_period_end"):
                raise SubscriptionRefused("not_cancelling")
            return {"cancel_at_period_end": False}, {"cancel_at_period_end": False}

        return self._run(incarnation_id, operation_id, "resume", str(mine["external_subscription_id"]), {}, build)

    # ---- §4.2.1 the operation journal ------------------------------------------------------------------------

    @staticmethod
    def _key(operation_id: str) -> str:
        return f"{OP_PREFIX}{operation_id}"

    def _load(self, operation_id: str) -> tuple[dict[str, Any] | None, Any]:
        stored = self._settings.get_setting(self._key(operation_id))
        if not stored:
            return None, None
        return dict(stored.get("value") or {}), stored.get("updated_at")

    def _write(self, operation_id: str, value: Mapping[str, Any], version: Any) -> Any:
        """CAS write; None when another writer moved the document (nothing written)."""

        from writing_coach.persistence.platform_repository import SettingConflict

        try:
            return self._settings.set_setting(self._key(operation_id), dict(value), updated_by="billing-polar-op",
                                              expected_updated_at=version)["updated_at"]  # fmt: skip
        except SettingConflict:
            return None

    def _run(self, incarnation_id: str, operation_id: str, action: str, subscription: str,
             asked: Mapping[str, Any], build: Callable[[], tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
        """The journal FIRST: a repeat of the same operation answers from it (never re-validated, never re-sent); a
        different request under the same id conflicts. Only a new operation is validated (`build`) and written."""

        digest = _digest({"action": action, "subscription": subscription, "asked": dict(asked)})
        doc, version = self._load(operation_id)
        if doc is not None:
            if doc.get("incarnation") != incarnation_id or doc.get("request_digest") != digest:
                raise SubscriptionRefused("operation_conflict")
            return self._resume_existing(operation_id, doc, version)
        body, expect = build()
        request = {"action": action, "subscription": subscription, "body": body}
        now = self._now()
        owner = secrets.token_hex(16)
        doc = {"incarnation": incarnation_id, "action": action, "request_digest": digest, "request": request,
               "expect": dict(expect), "state": "pending", "owner": owner,
               "lease_until": (now + LEASE).isoformat(), "created_at": now.isoformat(),
               "updated_at": now.isoformat()}  # fmt: skip
        version = self._write(operation_id, doc, None)
        if version is None:  # a concurrent identical request created it first
            doc, version = self._load(operation_id)
            if doc is None or doc.get("request_digest") != digest or doc.get("incarnation") != incarnation_id:
                raise SubscriptionRefused("operation_conflict")
            return self._resume_existing(operation_id, doc, version)
        return self._send(operation_id, doc, version, owner)

    def _send(self, operation_id: str, doc: dict[str, Any], version: Any, owner: str) -> dict[str, Any]:
        """Mark `sent` (CAS on version AND owner), then the operation's only PATCH."""

        if doc.get("owner") != owner or doc.get("state") != "pending":
            return self._answer(doc)
        sent = {**doc, "state": "sent", "sent_at": self._now().isoformat(), "updated_at": self._now().isoformat()}
        version = self._write(operation_id, sent, version)
        if version is None:
            current, _ = self._load(operation_id)
            return self._answer(current or doc)
        request = sent["request"]
        try:
            status, _body = self._call(self._request("PATCH", f"/v1/subscriptions/{quote(request['subscription'], safe='')}",
                                                     request["body"]))
        except Exception:  # noqa: BLE001 - a timeout or a broken connection: the outcome is unknown
            _log.warning("billing: Polar %s outcome unknown; reconciled by reads only", sent["action"], exc_info=True)
            status = 0
        self.forget(str(sent["incarnation"]))
        if 200 <= status < 300:
            final = {**sent, "state": "done", "status": status}
        elif status in (400, 402, 403, 404, 409, 422):
            final = {**sent, "state": "refused", "status": status}
        else:
            final = {**sent, "state": "provider_unknown", "status": status}
        final["updated_at"] = self._now().isoformat()
        if self._write(operation_id, final, version) is None:
            current, _ = self._load(operation_id)
            return self._answer(current or final)
        if final["state"] == "provider_unknown":
            return self._reconcile(operation_id)
        return self._answer(final)

    def _resume_existing(self, operation_id: str, doc: dict[str, Any], version: Any) -> dict[str, Any]:
        """A repeat of the same operation: never a second PATCH. A stale `pending` within CLAIM_WINDOW is claimed
        and sends the first PATCH; a stale `sent` / `provider_unknown` is reconciled by GET only."""

        state = doc.get("state")
        if state in TERMINAL:
            return self._answer(doc)
        if state == "pending":
            return self._claim(operation_id, doc, version)
        return self._reconcile(operation_id)

    def _claim(self, operation_id: str, doc: dict[str, Any], version: Any) -> dict[str, Any]:
        now = self._now()
        if datetime.fromisoformat(doc["lease_until"]) > now:
            return self._answer(doc)  # its owner is working
        if now - datetime.fromisoformat(doc["created_at"]) >= CLAIM_WINDOW:
            final = {**doc, "state": "not_applied", "updated_at": now.isoformat()}
            self._write(operation_id, final, version)  # no PATCH was ever sent; a lost race changes nothing
            current, _ = self._load(operation_id)
            return self._answer(current or final)
        owner = secrets.token_hex(16)
        claimed = {**doc, "owner": owner, "lease_until": (now + LEASE).isoformat(), "updated_at": now.isoformat()}
        version = self._write(operation_id, claimed, version)
        if version is None:  # another claimer won: this one sends nothing
            current, _ = self._load(operation_id)
            return self._answer(current or doc)
        return self._send(operation_id, claimed, version, owner)

    def _reconcile(self, operation_id: str) -> dict[str, Any]:
        """`sent` or `provider_unknown`: reads only. The effect visible on Polar -> done; none, and Polar's own
        revision has not moved for UNKNOWN_SETTLE -> not_applied. Never a second PATCH."""

        doc, version = self._load(operation_id)
        if doc is None or doc.get("state") in TERMINAL or doc.get("state") == "pending":
            return self._answer(doc or {})
        now = self._now()
        sent_at = datetime.fromisoformat(doc.get("sent_at") or doc["created_at"])
        if doc.get("state") == "sent" and now - sent_at < LEASE:
            return self._answer(doc)  # its PATCH may still be in flight: in progress, nothing written
        try:
            live = self._live(doc["request"]["subscription"])
        except Exception:  # noqa: BLE001 - still unknown; asked again later
            return self._answer({**doc, "state": "provider_unknown"})
        expect = doc.get("expect") or {}
        seen = all(self._shows(live, key, value) for key, value in expect.items())
        if seen:
            final = {**doc, "state": "done", "updated_at": now.isoformat()}
        elif now - sent_at >= UNKNOWN_SETTLE:
            final = {**doc, "state": "not_applied", "updated_at": now.isoformat()}
        else:
            final = {**doc, "state": "provider_unknown", "updated_at": now.isoformat()}
        if final["state"] != doc.get("state"):
            self._write(operation_id, final, version)
        return self._answer(final)

    @staticmethod
    def _shows(live: Mapping[str, Any], key: str, value: Any) -> bool:
        if key == "product_id":
            pending = live.get("pending_update") if isinstance(live.get("pending_update"), dict) else {}
            return live.get("product_id") == value or pending.get("product_id") == value
        return live.get(key) == value

    @staticmethod
    def _answer(doc: Mapping[str, Any]) -> dict[str, Any]:
        state = str(doc.get("state") or "unknown")
        return {"state": state, "action": doc.get("action"), "status": doc.get("status")}

    def operation(self, incarnation_id: str, operation_id: str) -> dict[str, Any]:
        doc, version = self._load(operation_id)
        if doc is None or doc.get("incarnation") != incarnation_id:
            raise SubscriptionRefused("operation_not_found", 404)
        return self._resume_existing(operation_id, doc, version) if doc.get("state") != "pending" else self._answer(doc)

    # ---- the reconciler's step: stale operations and retention ------------------------------------------------

    def step(self, counts: Counter[str], lock: Any = None) -> None:
        """Stale `pending` (claim or not_applied), `sent` / `provider_unknown` (GET only), terminal documents past
        RETENTION deleted, unresolved ones older than ESCALATE_AFTER escalated once; invoice-request markers older
        than a day deleted."""

        if self._gateway is None or self._index is None:
            return
        now = self._now()
        for key in self._index.keys(INVOICE_PREFIX):
            asked = (self._settings.get_setting(key) or {}).get("value") or {}
            if asked.get("at") and now - datetime.fromisoformat(asked["at"]) >= timedelta(days=1):
                self._index.delete(key)
        for key in self._index.keys(OP_PREFIX):
            operation_id = key[len(OP_PREFIX):]
            if lock is not None and not lock.alive():
                return
            doc, version = self._load(operation_id)
            if doc is None:
                continue
            state = doc.get("state")
            if state in TERMINAL:
                if now - datetime.fromisoformat(doc["updated_at"]) >= RETENTION:
                    self._index.delete(self._key(operation_id))
                    counts["polar_op_expired"] += 1
                continue
            if state == "pending":
                counts[f"polar_op_{self._claim(operation_id, doc, version)['state']}"] += 1
            else:
                counts[f"polar_op_{self._reconcile(operation_id)['state']}"] += 1
            doc, _ = self._load(operation_id)
            if (doc and doc.get("state") not in TERMINAL and not doc.get("escalated") and self._items is not None
                    and now - datetime.fromisoformat(doc["created_at"]) >= ESCALATE_AFTER):
                self._items.record(kind="event_undecided", gateway="polar", dedupe_key=f"polar_op_unresolved:{operation_id}",
                                   reason=f"polar_op_unresolved {doc.get('action')}", incarnation_id=doc.get("incarnation"),
                                   now=now)  # fmt: skip
                self._write(operation_id, {**doc, "escalated": True}, self._load(operation_id)[1])

    # ---- §4.3 invoices --------------------------------------------------------------------------------------

    def _customer_id(self, incarnation_id: str) -> str:
        if self._gateway is None:
            raise SubscriptionRefused("polar_unavailable", 503)
        status, body = self._call(self._request("GET", f"/v1/customers/external/{quote(incarnation_id, safe='')}"))
        if status == 404:
            raise SubscriptionRefused("no_customer", 404)
        if status != 200 or not isinstance(body, dict) or not body.get("id"):
            raise RuntimeError(f"polar_read_{status}")
        return str(body["id"])

    def invoices(self, incarnation_id: str, page: int = 1) -> dict[str, Any]:
        try:
            customer = self._customer_id(incarnation_id)
        except SubscriptionRefused as refused:
            if refused.code == "no_customer":
                return {"items": [], "page": page, "has_more": False}
            raise
        body = self._read(f"/v1/orders/?customer_id={quote(customer, safe='')}&page={int(page)}&limit=20"
                          "&sorting=-created_at")
        items = []
        for order in (body or {}).get("items", []):
            plan = self._plan_of(str(order.get("product_id") or ""))
            items.append({"id": order.get("id"), "created_at": order.get("created_at"),
                          "plan": plan[0] if plan else None, "period": plan[1] if plan else None,
                          "amount_minor": order.get("total_amount"),
                          "currency": str(order.get("currency") or "").upper() or None,
                          "status": order.get("status")})  # fmt: skip
        pagination = (body or {}).get("pagination") or {}
        return {"items": items, "page": page, "has_more": int(pagination.get("max_page") or 1) > page}

    def invoice(self, incarnation_id: str, order_id: str) -> dict[str, Any]:
        """§4.3: a direct ownership check (the order fetched by id, its customer compared), then GET; when Polar has
        not generated it, ask once per minute per order and answer `preparing`."""

        customer = self._customer_id(incarnation_id)
        status, order = self._call(self._request("GET", f"/v1/orders/{quote(order_id, safe='')}"))
        if status != 200 or not isinstance(order, dict) or str(order.get("customer_id")) != customer:
            raise SubscriptionRefused("order_not_found", 404)
        status, body = self._call(self._request("GET", f"/v1/orders/{quote(order_id, safe='')}/invoice"))
        if status == 200 and isinstance(body, dict) and str(body.get("url") or "").startswith("https://"):
            return {"state": "ready", "url": body["url"]}
        if status != 404:
            raise RuntimeError(f"polar_read_{status}")
        key = f"{INVOICE_PREFIX}{order_id}"
        asked = self._settings.get_setting(key)
        last = (asked or {}).get("value", {}).get("at")
        if last is None or self._now() - datetime.fromisoformat(last) >= timedelta(minutes=1):
            self._call(self._request("POST", f"/v1/orders/{quote(order_id, safe='')}/invoice"))
            from writing_coach.persistence.platform_repository import SettingConflict

            try:
                self._settings.set_setting(key, {"at": self._now().isoformat()}, updated_by="billing-polar-op",
                                           expected_updated_at=(asked or {}).get("updated_at"))  # fmt: skip
            except SettingConflict:
                pass
        return {"state": "preparing"}


class PostgresOperationIndex:
    """Lists and deletes this module's `platform_settings` keys (retention, §4.2.1). Reads keys only, never values."""

    def __init__(self, engine: Any) -> None:
        self._engine = engine

    def keys(self, prefix: str, limit: int = 500) -> list[str]:
        with self._engine.connect() as connection:
            rows = connection.execute(text("SELECT key FROM platform_settings WHERE key LIKE :p ORDER BY updated_at "
                                           "LIMIT :n"), {"p": prefix.replace("%", "") + "%", "n": limit}).scalars().all()
        return [str(row) for row in rows]

    def delete(self, key: str) -> None:
        if not key.startswith((OP_PREFIX, INVOICE_PREFIX)):
            raise ValueError("only billing operation keys are deleted here")
        with self._engine.begin() as connection:
            connection.execute(text("DELETE FROM platform_settings WHERE key = :k"), {"k": key})
