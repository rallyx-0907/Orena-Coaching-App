"""PR-MON-8 SePay, hermetic (design revisions 5 + 6): the webhook signature, the normalization and identity, the
server-built VietQR, explicit domestic gateway selection, the grace sentinel, the per-gateway acknowledgement, the
recovery feed's cursor loop, and secrets. No network; the order decisions under lock are proven on PostgreSQL in
tests/test_billing_sepay_postgres.py."""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from writing_coach.billing.gateway import CheckoutIntent, GatewayNotConfigured, Price, WebhookRejected, hmac_sha256_hex
from writing_coach.billing.sepay import SePayGateway, crc16_ccitt_false, parse_transaction_date, vietqr_payload

SECRET = "whsec-test-sepay"
TOKEN = "tok-test-sepay-api"
ACCOUNT = "123456789012"
NOW = datetime(2026, 10, 15, 3, 0, tzinfo=UTC)   # 10:00 in Vietnam


def gateway(**over):
    values = dict(webhook_secret=SECRET, account_number=ACCOUNT, account_name="NGUYEN VAN A", bank_bin="970415",
                  payment_prefix="ORN", api_token=TOKEN, feed_enabled=False)
    values.update(over)
    return SePayGateway(**values)


def payload(**over):
    body = {"id": 92704, "gateway": "VietinBank", "transactionDate": "2026-10-15 09:58:00", "accountNumber": ACCOUNT,
            "subAccount": None, "code": "ORN100001", "content": "SEVQR ORN100001", "transferType": "in",
            "description": "", "transferAmount": 99_000, "accumulated": 0, "referenceCode": "FT26288ABC"}
    body.update(over)
    return json.dumps(body).encode()


def signed(body: bytes, *, at: datetime = NOW, secret: str = SECRET) -> dict[str, str]:
    stamp = str(int(at.timestamp()))
    return {"X-SePay-Signature": "sha256=" + hmac_sha256_hex(secret, stamp.encode() + b"." + body),
            "X-SePay-Timestamp": stamp, "Content-Type": "application/json"}


# ---- signature ------------------------------------------------------------------------------------------------------

def test_a_signed_incoming_transfer_is_a_payment_of_its_order():
    body = payload()
    fact = gateway().verify(signed(body), body, now=NOW)
    assert (fact.kind, fact.gateway, fact.external_reference, fact.amount_minor, fact.currency) == (
        "payment", "sepay", "100001", 99_000, "VND")
    assert fact.event_id == f"sepay:ref:{ACCOUNT}:FT26288ABC"            # the bank reference is the identity
    assert fact.extra["source_id"] == "sepay:wh:92704"
    assert fact.extra["transaction_at"] == "2026-10-15T02:58:00+00:00"   # Vietnam time, as UTC


@pytest.mark.parametrize("case", ["wrong_secret", "tampered", "no_signature", "no_timestamp", "garbled_timestamp",
                                  "unprefixed"])
def test_an_unprovable_webhook_is_rejected_before_parsing(case):
    body = payload()
    headers = signed(body)
    if case == "wrong_secret":
        headers = signed(body, secret="another")
    elif case == "tampered":
        body = payload(transferAmount=1_000)
    elif case == "no_signature":
        headers.pop("X-SePay-Signature")
    elif case == "no_timestamp":
        headers.pop("X-SePay-Timestamp")
    elif case == "garbled_timestamp":
        headers["X-SePay-Timestamp"] = "soon"
    elif case == "unprefixed":
        headers["X-SePay-Signature"] = headers["X-SePay-Signature"].removeprefix("sha256=")
    with pytest.raises(WebhookRejected):
        gateway().verify(headers, body, now=NOW)


@pytest.mark.parametrize(("skew", "accepted"), [(300, True), (-300, True), (301, False), (-301, False)])
def test_the_timestamp_window_is_300_seconds(skew, accepted):
    body = payload()
    headers = signed(body, at=NOW + timedelta(seconds=skew))
    if accepted:
        assert gateway().verify(headers, body, now=NOW).kind == "payment"
    else:
        with pytest.raises(WebhookRejected, match="stale_timestamp"):
            gateway().verify(headers, body, now=NOW)


def test_a_signed_but_unreadable_body_is_rejected():
    body = b"not json"
    with pytest.raises(WebhookRejected, match="unreadable_body"):
        gateway().verify(signed(body), body, now=NOW)


# ---- normalization and identity (§3, §3.1) -----------------------------------------------------------------------

@pytest.mark.parametrize(("over", "kind", "order"), [
    ({"transferType": "out"}, "ignored", None),                 # outgoing money, the operator's own refund included
    ({"accountNumber": "999999999"}, "ignored", None),          # another account the owner linked
    ({"code": None}, "payment", None),                          # no payment code: recorded, never matched by amount
    ({"code": ""}, "payment", None),
    ({"code": "XYZ100001"}, "payment", None),                   # a foreign prefix
    ({"code": "ORN10A001"}, "payment", None),                   # not digits
    ({"code": "orn100001"}, "payment", "100001"),               # the prefix, case-insensitively
    ({"code": "ORN0100001"}, "payment", None),                  # review P1-1: a leading zero is not the code issued
    ({"code": "ORN000100001"}, "payment", None),
    ({"code": "ORN0"}, "payment", None),
])
def test_the_payment_code_alone_names_the_order(over, kind, order):
    body = payload(**over)
    fact = gateway().verify(signed(body), body, now=NOW)
    assert (fact.kind, fact.external_reference) == (kind, order)


def test_without_a_bank_reference_the_source_id_is_the_identity():
    body = payload(referenceCode="")
    fact = gateway().verify(signed(body), body, now=NOW)
    assert fact.event_id == "sepay:wh:92704"


def test_the_webhook_and_the_feed_agree_on_a_referenced_transfer_and_never_on_an_unreferenced_one():
    sepay = gateway()
    hooked = sepay.verify(signed(payload()), payload(), now=NOW)
    row = {"id": "0b9f6c1e-1111-4a8a-9a43-2f3b5f6c7d8e", "transaction_date": "2026-10-15 09:58:00",
           "account_number": ACCOUNT, "transfer_type": "in", "amount_in": 99_000, "reference_number": "FT26288ABC",
           "code": "ORN100001", "webhook_success": 0}
    fed = sepay.to_fact(sepay.feed_transfer(row), payload_digest="d")
    assert fed.event_id == hooked.event_id                       # one transfer, one payment event
    assert fed.extra["source_id"] == f"sepay:v2:{row['id']}" != hooked.extra["source_id"]
    bare = sepay.to_fact(sepay.feed_transfer({**row, "reference_number": ""}), payload_digest="d")
    unreferenced = sepay.verify(signed(payload(referenceCode="")), payload(referenceCode=""), now=NOW)
    assert bare.event_id != unreferenced.event_id                # never equated without a reference


def test_transaction_dates_are_vietnam_time_and_unreadable_ones_are_none():
    assert parse_transaction_date("2026-10-15 09:58:00") == datetime(2026, 10, 15, 2, 58, tzinfo=UTC)
    assert parse_transaction_date("15/10/2026") is None and parse_transaction_date(None) is None


# ---- VietQR (G1) ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("inputs", "expected"), [
    # xuannghia/vietnam-qr-pay README, "VietQR dynamic" (ACB 970416): an independent JS implementation
    (dict(bank_bin="970416", account_number="257678859", amount_minor=10_000, purpose="Chuyen tien"),
     "00020101021238530010A0000007270123000697041601092576788590208QRIBFTTA53037045405100005802VN62150811Chuyen tien"
     "630453E6"),
    # subiz/vietqr Go package, its documented Generate example (VietinBank 970415; the note without diacritics)
    (dict(bank_bin="970415", account_number="0011001932418", amount_minor=120_000, purpose="ung ho lu lut"),
     "00020101021238570010A00000072701270006970415011300110019324180208QRIBFTTA530370454061200005802VN62170813ung "
     "ho lu lut6304C15C"),
])
def test_the_vietqr_matches_published_known_answer_vectors(inputs, expected):
    """Review P2-2: complete payloads published by two independent implementations, not this code's own output."""
    assert vietqr_payload(**inputs) == expected


def test_crc16_ccitt_false_check_value():
    assert crc16_ccitt_false(b"123456789") == 0x29B1   # the published check value of CRC-16/CCITT-FALSE


def _fields(text: str) -> dict[str, str]:
    out, index = {}, 0
    while index < len(text):
        tag, size = text[index:index + 2], int(text[index + 2:index + 4])
        out[tag] = text[index + 4:index + 4 + size]
        index += 4 + size
    return out


def test_the_vietqr_carries_the_bank_account_exact_amount_and_memo_with_a_valid_crc():
    qr = vietqr_payload(bank_bin="970415", account_number=ACCOUNT, amount_minor=99_000, purpose="SEVQR ORN100001")
    fields = _fields(qr)
    assert fields["00"] == "01" and fields["01"] == "12" and fields["53"] == "704" and fields["58"] == "VN"
    assert fields["54"] == "99000"
    merchant = _fields(fields["38"])
    assert merchant["00"] == "A000000727" and merchant["02"] == "QRIBFTTA"
    assert _fields(merchant["01"]) == {"00": "970415", "01": ACCOUNT}
    assert _fields(fields["62"]) == {"08": "SEVQR ORN100001"}
    assert fields["63"] == f"{crc16_ccitt_false(qr[:-4].encode()):04X}"


@pytest.mark.parametrize("bad", [dict(amount_minor=0), dict(amount_minor=1.5), dict(purpose="x" * 26),
                                 dict(bank_bin="97041"), dict(account_number="12ab"),
                                 dict(account_number="12-AB"), dict(account_number="A" * 20)])
def test_a_vietqr_is_never_built_from_bad_input(bad):
    values = dict(bank_bin="970415", account_number=ACCOUNT, amount_minor=99_000, purpose="SEVQR ORN1")
    values.update(bad)
    with pytest.raises(ValueError):
        vietqr_payload(**values)


# ---- revision 7.1 (§13): the QR names a configured virtual account ----------------------------------------------------

VA = "VQRAB12CD34E"


def test_with_a_va_the_qr_and_the_checkout_response_name_it_and_never_the_main_account():
    import binascii

    price = Price(plan_id="plus", period="month", currency="VND", amount_minor=99_000, gateway="sepay")
    intent = CheckoutIntent(operation_id="op", incarnation_id="inc", price=price, return_url="r", cancel_url="c")
    start = gateway(va_number=VA).domestic_checkout(intent, {"order_code": 100001})
    fields = _fields(start["qr"])
    assert _fields(_fields(fields["38"])["01"]) == {"00": "970415", "01": VA}
    assert start["transfer"]["account_number"] == VA
    assert ACCOUNT not in start["qr"] and ACCOUNT not in json.dumps(start)
    assert fields["63"] == format(binascii.crc_hqx(start["qr"][:-4].encode(), 0xFFFF), "04X")   # independent CRC


def test_without_a_va_the_main_account_qr_is_unchanged():
    price = Price(plan_id="plus", period="month", currency="VND", amount_minor=99_000, gateway="sepay")
    intent = CheckoutIntent(operation_id="op", incarnation_id="inc", price=price, return_url="r", cancel_url="c")
    start = gateway().domestic_checkout(intent, {"order_code": 100001})
    assert _fields(_fields(_fields(start["qr"])["38"])["01"])["01"] == ACCOUNT


@pytest.mark.parametrize("bad", ["vqrab12cd34e", "VQR-AB12", "VQR AB12", "A" * 20, "VQRÄB12"])
def test_a_malformed_va_refuses_the_configuration(bad):
    with pytest.raises(GatewayNotConfigured):
        gateway(va_number=bad)


def test_production_sepay_without_a_va_fails_closed():
    sepay_without = gateway()
    closed = service({"sepay": sepay_without}, domestic="sepay", production=True)
    assert "sepay_va_unset" in closed.domestic_blockers()
    assert closed._domestic_sellable("sepay") is False
    assert closed.gateway_report()["sepay"]["virtual_account"] == "unset"
    assert closed.gateway_report()["sepay"]["ready"] is False
    from writing_coach.billing.gateway import Price as P

    priced = service({"sepay": sepay_without}, domestic="sepay", production=True,
                     prices={"plus:month:sepay": P(plan_id="plus", period="month", currency="VND", amount_minor=99_000,
                                                   gateway="sepay")})
    with pytest.raises(LookupError):
        priced.start_checkout(incarnation_id="inc", price_key="plus:month:sepay",
                              operation_id="00000000-0000-4000-8000-000000000001", return_url="r", cancel_url="c",
                              confirmed_amount_minor=99_000, confirmed_currency="VND")


def test_production_sepay_with_a_valid_va_has_no_va_blocker_and_dev_keeps_the_fallback():
    assert "sepay_va_unset" not in service({"sepay": gateway(va_number=VA)}, domestic="sepay",
                                           production=True).domestic_blockers()
    assert service({"sepay": gateway()}, domestic="sepay", production=False).domestic_blockers() == []


def test_a_production_runtime_without_a_va_is_not_billing_ready():
    from writing_coach.billing import readiness

    real = service({"sepay": gateway()}, domestic="sepay", production=True)
    facade = SimpleNamespace(gateway_report=lambda: {"sepay": {"ready": True}}, domestic_blockers=real.domestic_blockers)
    facts = readiness.RuntimeFacts(switch=True, backend="postgresql", backbone="active",
                                   commerce_schema=lambda: "present", orders_schema=lambda: "present",
                                   entitlement_source=lambda: "installed", service=facade,
                                   public_base_url="https://orena.test", production=True)
    report = readiness.report(facts)
    assert report["ready"] is False and "sepay_va_unset" in report["blockers"]


def test_no_full_main_account_or_va_appears_in_repr_or_the_readiness_report():
    sepay = gateway(va_number=VA)
    text = repr(sepay) + json.dumps(service({"sepay": sepay}, domestic="sepay", production=True).gateway_report())
    assert ACCOUNT not in text and VA not in text
    assert "***" + ACCOUNT[-4:] in repr(sepay) and "***" + VA[-4:] in repr(sepay)


def test_receiving_still_needs_the_main_account_even_with_a_va():
    sepay = gateway(va_number=VA)
    main = sepay.verify(signed(payload()), payload(), now=NOW)
    assert (main.kind, main.external_reference) == ("payment", "100001")
    to_va = payload(accountNumber=VA)
    assert sepay.verify(signed(to_va), to_va, now=NOW).kind == "ignored"   # a VA is never a receiving account


def test_a_prefix_that_leaves_no_room_for_the_order_code_is_refused():
    with pytest.raises(GatewayNotConfigured):
        gateway(payment_prefix="ABCDEFGH")


def test_checkout_instructions_need_no_provider_call():
    price = Price(plan_id="plus", period="month", currency="VND", amount_minor=99_000, gateway="sepay")
    intent = CheckoutIntent(operation_id="op", incarnation_id="inc", price=price, return_url="r", cancel_url="c")
    start = gateway().domestic_checkout(intent, {"order_code": 100001})
    assert start["redirect_url"] == "" and start["qr"].startswith("000201")
    assert start["transfer"] == {"bank_bin": "970415", "account_number": ACCOUNT, "account_name": "NGUYEN VAN A",
                                 "amount_minor": 99_000, "currency": "VND", "memo": "SEVQR ORN100001"}


# ---- configuration, feed switch and secrets ---------------------------------------------------------------------

def test_sepay_is_configured_only_with_all_of_its_settings():
    with pytest.raises(GatewayNotConfigured):
        SePayGateway.from_env({"SEPAY_WEBHOOK_SECRET": SECRET})
    env = {"SEPAY_WEBHOOK_SECRET": SECRET, "SEPAY_ACCOUNT_NUMBER": ACCOUNT, "SEPAY_ACCOUNT_NAME": "A",
           "SEPAY_BANK_BIN": "970415", "SEPAY_PAYMENT_PREFIX": "orn"}
    assert SePayGateway.from_env(env).prefix == "ORN"


@pytest.mark.parametrize(("token", "flag", "enabled"), [(TOKEN, "", False), (TOKEN, "false", False), ("", "true", False),
                                                       (TOKEN, "true", True)])
def test_the_feed_needs_its_token_and_its_switch(token, flag, enabled):
    env = {"SEPAY_WEBHOOK_SECRET": SECRET, "SEPAY_ACCOUNT_NUMBER": ACCOUNT, "SEPAY_ACCOUNT_NAME": "A",
           "SEPAY_BANK_BIN": "970415", "SEPAY_PAYMENT_PREFIX": "ORN", "SEPAY_API_TOKEN": token,
           "SEPAY_FEED_ENABLED": flag}
    assert SePayGateway.from_env(env).feed_enabled is enabled


def test_a_token_alone_adds_no_feed_step_to_the_reconciler():
    from writing_coach.billing.reconciler import BillingReconciler
    from writing_coach.billing.sepay_feed import SePayFeed

    feed = SePayFeed(service=None, gateway=gateway(api_token=TOKEN, feed_enabled=False), settings=None, orders=None)
    assert feed.enabled is False
    held = SimpleNamespace(held=True, alive=lambda: True)

    class Lock:
        def __call__(self):
            return self

        def __enter__(self):
            return held

        def __exit__(self, *exc):
            return False

    service = SimpleNamespace(domestic_gateways=lambda: [], credits=None)
    orders = SimpleNamespace(prepaid_gaps=lambda gateway: [], pull_candidates=lambda *a, **k: [],
                             expire_open=lambda **k: 0, expire=lambda **k: 0)
    reconciler = BillingReconciler(service=service, orders=orders, items=SimpleNamespace(open_items=lambda **k: []),
                                   lock=Lock(), lookups={}, feed=feed)
    counts = reconciler.tick() or {}
    assert not any(key.startswith("sepay_feed") for key in counts)


def test_the_feed_names_itself_so_sepays_cloudflare_does_not_refuse_it():
    """SePay test mode, 2026-10-17: Cloudflare in front of SePay's API answers Error 1010 (403) to Python's default
    User-Agent. Every feed and backfill request carries Orena's own User-Agent and asks for JSON."""
    from writing_coach.billing.sepay import USER_AGENT

    headers = gateway().feed_request(since_id=None, date_from=NOW)["headers"]
    assert headers["User-Agent"] == USER_AGENT and not headers["User-Agent"].startswith("Python-urllib")
    assert headers["Accept"] == "application/json" and headers["Authorization"] == f"Bearer {TOKEN}"


def test_no_secret_reaches_a_repr_a_report_a_request_error_or_a_log(caplog):
    from writing_coach.billing.sepay_feed import FeedHTTPError

    sepay = gateway(feed_enabled=True)
    caplog.set_level(logging.DEBUG)
    with pytest.raises(WebhookRejected):
        sepay.verify(signed(payload(), secret="wrong"), payload(), now=NOW)
    text = repr(sepay) + str(FeedHTTPError(401)) + caplog.text
    assert SECRET not in text and TOKEN not in text
    request = sepay.feed_request(since_id=None, date_from=NOW)
    assert TOKEN not in json.dumps(request["params"]) and request["params"]["page"] == "1"


# ---- domestic gateway selection (§5) and the grace sentinel (§4.1) ---------------------------------------------------

def service(gateways, *, domestic=None, production=False, grace=lambda: timedelta(hours=1), **extra):
    from writing_coach.billing.service import BillingService

    extra.setdefault("now", lambda: NOW)
    return BillingService(orders=extra.pop("orders", SimpleNamespace()), commerce=SimpleNamespace(),
                          gateways=gateways, prices=extra.pop("prices", {}), domestic=domestic,
                          production=production, grace=grace, **extra)


def test_the_domestic_gateway_is_explicit_in_production():
    from tests.test_billing import PAYOS

    sepay = gateway()
    assert service({"sepay": sepay}, production=True).domestic_state() == (None, "domestic_gateway_unset")
    assert service({"sepay": sepay}, production=False).domestic_state() == ("sepay", None)   # dev/test only
    assert service({"sepay": sepay, "payos": PAYOS}, production=False).domestic_state() == (None, "domestic_gateway_unset")
    assert service({"payos": PAYOS}, domestic="sepay").domestic_state() == (None, "domestic_gateway_unconfigured")
    assert service({"sepay": sepay, "payos": PAYOS}, domestic="payos", production=True).domestic_state() == ("payos", None)
    # review P1-2: no international-only exception - production without a choice is never ready
    assert service({}, production=True).domestic_state() == (None, "domestic_gateway_unset")
    from tests.test_billing import POLAR

    assert service({"polar": POLAR}, production=True).domestic_blockers() == ["domestic_gateway_unset"]


def test_a_production_runtime_is_not_billing_ready_on_polar_alone_without_the_domestic_choice():
    from tests.test_billing import POLAR
    from writing_coach.billing import readiness

    real = service({"polar": POLAR}, production=True)
    facade = SimpleNamespace(gateway_report=lambda: {"polar": {"ready": True}}, domestic_blockers=real.domestic_blockers)
    facts = readiness.RuntimeFacts(switch=True, backend="postgresql", backbone="active",
                                   commerce_schema=lambda: "present", orders_schema=lambda: "present",
                                   entitlement_source=lambda: "installed", service=facade,
                                   public_base_url="https://orena.test", production=True)
    report = readiness.report(facts)
    assert report["ready"] is False and "domestic_gateway_unset" in report["blockers"]


def test_an_unconfigured_grace_closes_sepay_and_names_the_blocker(monkeypatch):
    from writing_coach import policies
    from writing_coach.billing import service as billing

    for value in (0, -1):
        monkeypatch.setattr(policies, "value_strict", lambda key, value=value, **_: value)
        assert billing.late_payment_grace() is None   # <= 0 is never a grace
    monkeypatch.setattr(policies, "value_strict", lambda key, **_: 1)
    assert billing.late_payment_grace() == timedelta(hours=1)
    closed = service({"sepay": gateway()}, domestic="sepay", grace=lambda: None)
    assert closed.domestic_blockers() == ["late_payment_grace_unset"]
    assert closed.gateway_report()["sepay"]["late_payment_grace"] == "unset"
    assert closed.gateway_report()["sepay"]["ready"] is False


def test_the_grace_policy_defaults_to_the_unconfigured_sentinel():
    from writing_coach import policies

    item = policies.BY_KEY["billing.domestic_late_payment_grace_hours"]
    assert (item.default, item.kind, item.unit, item.low) == (0, "int", "hours", 0)


# ---- the SePay path: outcomes recorded as payment_not_payable + stable reason (§4.3) --------------------------------

class Orders:
    def __init__(self, status):
        self.status = status
        self.calls = []

    def mark_paid_domestic(self, **kwargs):
        self.calls.append(kwargs)
        return {"status": self.status, "order_id": "order-1", "incarnation_id": "inc-1", "product_kind": "plan"}


class Items:
    def __init__(self, fail=False):
        self.rows, self.fail = [], fail

    def record(self, **row):
        if self.fail:
            raise RuntimeError("store down")
        self.rows.append(row)
        return row


@pytest.mark.parametrize(("status", "reason"), [("order_closed", "order_closed"), ("late", "late_payment"),
                                                ("source_ambiguous", "source_ambiguous")])
def test_a_locked_refusal_is_one_existing_kind_with_its_stable_reason_and_the_supported_facts(status, reason):
    orders, items = Orders(status), Items()
    billing = service({"sepay": gateway()}, domestic="sepay", orders=orders, reconciliation=items)
    body = payload()
    outcome = billing.handle_webhook("sepay", signed(body), body)
    assert outcome.status == status
    (item,) = items.rows
    assert {key: item[key] for key in ("kind", "gateway", "dedupe_key", "reason")} == {
        "kind": "payment_not_payable", "gateway": "sepay", "dedupe_key": f"sepay:ref:{ACCOUNT}:FT26288ABC",
        "reason": reason}
    assert item["external_event_id"] == "sepay:wh:92704"
    assert (item["reported_order_code"], item["reported_amount_minor"], item["reported_currency"]) == (100001, 99_000, "VND")
    assert item["provider_state"] == "paid" and item["payload_digest"]
    assert (item["billing_order_id"], item["incarnation_id"]) == ("order-1", "inc-1")
    assert not {"bank_reference", "transaction_at", "transaction_date"} & set(item)   # no such columns


def test_the_late_decision_is_given_the_providers_transaction_time_not_the_arrival_time():
    orders = Orders("late")
    billing = service({"sepay": gateway()}, domestic="sepay", orders=orders, reconciliation=Items(),
                      now=lambda: NOW + timedelta(days=3))
    body = payload()
    billing.handle_webhook("sepay", signed(body, at=NOW + timedelta(days=3)), body)
    (call,) = orders.calls
    assert call["transaction_at"] == datetime(2026, 10, 15, 2, 58, tzinfo=UTC)
    assert call["grace"] == timedelta(hours=1) and call["event_id"] == f"sepay:ref:{ACCOUNT}:FT26288ABC"


def test_an_unconfigured_grace_reaches_the_locked_decision_as_none():
    orders = Orders("late")
    billing = service({"sepay": gateway()}, domestic="sepay", orders=orders, reconciliation=Items(), grace=lambda: None)
    body = payload()
    billing.handle_webhook("sepay", signed(body), body)
    assert orders.calls[0]["grace"] is None


def test_a_transfer_without_an_order_code_is_recorded_and_never_decided():
    orders, items = Orders("applied"), Items()
    billing = service({"sepay": gateway()}, domestic="sepay", orders=orders, reconciliation=items)
    body = payload(code=None)
    assert billing.handle_webhook("sepay", signed(body), body).status == "unknown_order"
    assert orders.calls == [] and items.rows[0]["kind"] == "payment_unknown_order"


# ---- the webhook route: SePay's acknowledgement, and 503 when the item cannot be written --------------------------------

@pytest.fixture
def route():
    """The webhook route around one service; billing_api's module state is restored afterwards."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from writing_coach import billing_api

    names = ("_service", "_backbone", "_admin", "_public_base", "_items", "_reconcile", "_credits", "_sepay_backfill")
    saved = {name: getattr(billing_api, name) for name in names}

    def build(billing):
        billing_api.configure_billing(service=billing, backbone=SimpleNamespace(is_active=True),
                                      admin_guard=lambda request: None, public_base_url="https://orena.test")
        app = FastAPI()
        app.include_router(billing_api.router)
        return TestClient(app)

    yield build
    for name, value in saved.items():
        setattr(billing_api, name, value)


def test_sepay_is_acknowledged_in_its_own_shape_once_recorded(route):
    client = route(service({"sepay": gateway()}, domestic="sepay", orders=Orders("late"), reconciliation=Items(),
                           now=lambda: datetime.now(UTC)))
    body = payload()
    answer = client.post("/api/billing/webhooks/sepay", content=body, headers=signed(body, at=datetime.now(UTC)))
    assert answer.status_code == 200 and answer.json() == {"success": True}


def test_a_failed_item_write_answers_503_and_no_acknowledgement(route):
    client = route(service({"sepay": gateway()}, domestic="sepay", orders=Orders("order_closed"),
                           reconciliation=Items(fail=True), now=lambda: datetime.now(UTC)))
    body = payload()
    answer = client.post("/api/billing/webhooks/sepay", content=body, headers=signed(body, at=datetime.now(UTC)))
    assert answer.status_code == 503 and answer.json() != {"success": True}


# ---- the recovery feed's cursor loop (§6.2, §6.3) ---------------------------------------------------------------

class Settings:
    def __init__(self, value=None):
        self.version = 0
        self.value = value
        self.conflict_next = False
        self.writes = []

    def get_setting(self, key):
        return None if self.value is None else {"value": dict(self.value), "updated_at": str(self.version)}

    def set_setting(self, key, value, *, updated_by="", expected_updated_at=...):
        from writing_coach.persistence.platform_repository import SettingConflict

        current = None if self.value is None else str(self.version)
        if self.conflict_next or expected_updated_at != current:
            raise SettingConflict(key)
        self.version += 1
        self.value = dict(value)
        self.writes.append(dict(value))
        return {"value": value, "updated_at": str(self.version)}


def row(n, *, minutes_ago=120, account=ACCOUNT, webhook_success=0, ref=None):
    from writing_coach.billing.sepay import VIETNAM

    when = (NOW - timedelta(minutes=minutes_ago)).astimezone(VIETNAM).strftime("%Y-%m-%d %H:%M:%S")
    return {"id": f"00000000-0000-4000-8000-{n:012d}", "transaction_date": when, "account_number": account,
            "transfer_type": "in", "amount_in": 99_000, "reference_number": ref if ref is not None else f"FT{n}",
            "code": f"ORN{100000 + n}", "webhook_success": webhook_success}


class Feeder:
    """The feed's transport: answers from the rows after the requested since_id (page 1 only)."""

    def __init__(self, rows):
        self.rows, self.requests = rows, []

    def __call__(self, request):
        self.requests.append(dict(request["params"]))
        assert request["params"]["page"] == "1"
        since = request["params"].get("since_id")
        start = 0 if since is None else next(i for i, r in enumerate(self.rows) if r["id"] == since) + 1
        return {"data": self.rows[start:start + int(request["params"]["per_page"])]}


class Handler:
    def __init__(self, fail_on=None):
        self.facts, self.fail_on = [], fail_on

    def handle_fact(self, fact):
        if self.fail_on is not None and fact.extra["source_id"].endswith(self.fail_on):
            raise RuntimeError("write failed")
        self.facts.append(fact)
        return SimpleNamespace(status="apply")


def feed(rows, *, handler=None, settings=None, iterations=5):
    from writing_coach.billing.sepay_feed import SePayFeed

    return SePayFeed(service=handler or Handler(), gateway=gateway(feed_enabled=True),
                     settings=settings or Settings({"since_id": None, "backfill_from": NOW.isoformat()}),
                     orders=SimpleNamespace(oldest_open_created_at=lambda gateway: NOW - timedelta(days=1)),
                     fetch=Feeder(rows), now=lambda: NOW, max_iterations=iterations)


def test_the_cursor_moves_page_one_at_a_time_and_never_skips_past_a_full_page(monkeypatch):
    from writing_coach.billing import sepay_feed

    monkeypatch.setattr(sepay_feed, "PER_PAGE", 3)
    rows = [row(n) for n in range(1, 8)]
    handler, settings = Handler(), Settings({"since_id": None, "backfill_from": NOW.isoformat()})
    step = feed(rows, handler=handler, settings=settings)
    step.step(Counter())
    assert [f.extra["source_id"][-1] for f in handler.facts] == list("1234567")   # every row, in order, once
    requests = step._fetch.requests
    assert all(r["page"] == "1" for r in requests) and requests[0].get("since_id") is None
    assert [r.get("since_id") for r in requests[1:]] == [rows[2]["id"], rows[5]["id"]]
    assert settings.value["since_id"] == rows[-1]["id"]


def test_the_loop_stops_at_the_settle_delay_and_does_not_pass_it():
    rows = [row(1), row(2, minutes_ago=10), row(3)]
    handler, settings = Handler(), Settings({"since_id": None, "backfill_from": NOW.isoformat()})
    feed(rows, handler=handler, settings=settings).step(Counter())
    assert len(handler.facts) == 1 and settings.value["since_id"] == rows[0]["id"]


def test_a_failure_mid_page_keeps_the_cursor():
    rows = [row(1), row(2), row(3)]
    settings = Settings({"since_id": None, "backfill_from": NOW.isoformat()})
    with pytest.raises(RuntimeError):
        feed(rows, handler=Handler(fail_on="2"), settings=settings).step(Counter())
    assert settings.value["since_id"] is None and settings.writes == []


def test_a_lost_compare_and_set_writes_nothing():
    settings = Settings({"since_id": None, "backfill_from": NOW.isoformat()})
    settings.conflict_next = True
    counts = Counter()
    feed([row(1)], settings=settings).step(counts)
    assert counts["sepay_feed_conflict"] == 1 and settings.writes == []


def test_rows_for_another_account_or_already_delivered_are_skipped_but_counted():
    rows = [row(1, account="999"), row(2, webhook_success=1), row(3)]
    handler, settings = Handler(), Settings({"since_id": None, "backfill_from": NOW.isoformat()})
    counts = Counter()
    feed(rows, handler=handler, settings=settings).step(counts)
    assert [f.extra["source_id"][-1] for f in handler.facts] == ["3"]
    assert counts["sepay_feed_skipped"] == 2 and settings.value["since_id"] == rows[-1]["id"]


def test_the_first_run_backfills_from_the_oldest_open_order():
    settings = Settings()
    step = feed([row(1)], settings=settings)
    step.step(Counter())
    first = step._fetch.requests[0]
    assert "since_id" not in first and first["transaction_date_from"] == "2026-10-14 10:00:00"   # NOW - 1 day, VN time


def _first_run(open_at, first_at):
    from writing_coach.billing.sepay_feed import SePayFeed

    settings = Settings()
    fetch = Feeder([row(1)])
    orders = SimpleNamespace(oldest_open_created_at=lambda gateway: open_at,
                             first_order_created_at=lambda gateway: first_at)
    counts = Counter()
    SePayFeed(service=Handler(), gateway=gateway(feed_enabled=True), settings=settings, orders=orders, fetch=fetch,
              now=lambda: NOW).step(counts)
    return settings, fetch, counts


def test_with_no_open_order_the_first_run_starts_when_sepay_sales_began_never_now():
    from writing_coach.billing.sepay import VIETNAM

    began = NOW - timedelta(days=40)
    _settings, fetch, _counts = _first_run(None, began)
    assert fetch.requests[0]["transaction_date_from"] == began.astimezone(VIETNAM).strftime("%Y-%m-%d %H:%M:%S")


def test_before_sepay_ever_sold_the_feed_does_not_start_its_cursor():
    settings, fetch, counts = _first_run(None, None)
    assert fetch.requests == [] and settings.value is None and counts["sepay_feed_no_orders"] == 1


def test_a_rate_limit_ends_the_step_without_moving_the_cursor():
    from writing_coach.billing.reconciler import RateLimited
    from writing_coach.billing.sepay_feed import SePayFeed

    def limited(_request):
        raise RateLimited(30)

    settings = Settings({"since_id": "c1", "backfill_from": None})
    counts = Counter()
    SePayFeed(service=Handler(), gateway=gateway(feed_enabled=True), settings=settings, orders=None, fetch=limited,
              now=lambda: NOW).step(counts)
    assert counts["sepay_feed_rate_limited"] == 1 and settings.value["since_id"] == "c1"   # the cursor never moved


def test_retry_after_is_honoured_across_ticks_longer_than_the_reconciler_interval():
    """Review P2-1: SePay asks for 600 s and the reconciler ticks every 60 s: no request before the wait ends."""
    from writing_coach.billing.reconciler import RateLimited
    from writing_coach.billing.sepay_feed import SePayFeed

    calls = []
    clock = {"now": NOW}

    def limited(_request):
        calls.append(clock["now"])
        raise RateLimited(600)

    settings = Settings({"since_id": "c1", "backfill_from": None})
    step = SePayFeed(service=Handler(), gateway=gateway(feed_enabled=True), settings=settings, orders=None,
                     fetch=limited, now=lambda: clock["now"])
    step.step(Counter())
    for seconds in (60, 120, 540):
        clock["now"] = NOW + timedelta(seconds=seconds)
        counts = Counter()
        step.step(counts)
        assert counts["sepay_feed_waiting"] == 1
    assert len(calls) == 1 and settings.value["since_id"] == "c1"
    clock["now"] = NOW + timedelta(seconds=601)
    step.step(Counter())
    assert len(calls) == 2   # asked again only once the wait was over


# ---- the operator's date-range backfill (§6.4) ------------------------------------------------------------------

def test_a_backfill_uses_the_same_handling_and_never_touches_the_cursor(monkeypatch):
    from writing_coach.billing import sepay_feed

    monkeypatch.setattr(sepay_feed, "PER_PAGE", 2)
    rows = [row(1), row(2, webhook_success=1), row(3), row(4, account="999"), row(5)]
    handler = Handler()
    settings = Settings({"since_id": "authoritative", "backfill_from": None})
    step = feed(rows, handler=handler, settings=settings)
    result = step.backfill(NOW - timedelta(days=2), NOW)
    assert result["complete"] is True and result["resume_after"] is None
    assert [f.extra["source_id"][-1] for f in handler.facts] == ["1", "3", "5"]   # the same §6.3 rules
    assert result["counts"]["sepay_feed_skipped"] == 2
    assert settings.value == {"since_id": "authoritative", "backfill_from": None} and settings.writes == []
    requests = step._fetch.requests
    assert all(r["page"] == "1" for r in requests) and all("transaction_date_to" in r for r in requests)
    assert requests[0]["transaction_date_from"] and "since_id" not in requests[0]


def test_a_backfill_works_while_the_feed_is_off_but_needs_the_token():
    from writing_coach.billing.sepay_feed import SePayFeed

    off = SePayFeed(service=Handler(), gateway=gateway(feed_enabled=False), settings=Settings(), orders=None,
                    fetch=Feeder([row(1)]), now=lambda: NOW)
    done = off.backfill(NOW - timedelta(days=1), NOW)
    assert off.enabled is False and done["complete"] is True and done["counts"] == {"sepay_feed_apply": 1}
    tokenless = SePayFeed(service=Handler(), gateway=gateway(api_token="", feed_enabled=False), settings=Settings(),
                          orders=None, fetch=Feeder([]), now=lambda: NOW)
    with pytest.raises(PermissionError):
        tokenless.backfill(NOW - timedelta(days=1), NOW)


def _cap_world(monkeypatch, rows, *, fail_at=None):
    """A backfill over `rows` with a page of 2 and a cap of 3 pages; `fail_at` makes that request a 429."""
    from writing_coach.billing import sepay_feed
    from writing_coach.billing.reconciler import RateLimited

    monkeypatch.setattr(sepay_feed, "PER_PAGE", 2)
    monkeypatch.setattr(sepay_feed, "MAX_BACKFILL_PAGES", 3)
    feeder = Feeder(rows)
    calls = {"n": 0}

    def fetch(request):
        calls["n"] += 1
        if fail_at is not None and calls["n"] == fail_at:
            raise RateLimited(30)
        return feeder(request)

    handler = Handler()
    settings = Settings({"since_id": "authoritative", "backfill_from": None})
    step = sepay_feed.SePayFeed(service=handler, gateway=gateway(feed_enabled=False), settings=settings, orders=None,
                                fetch=fetch, now=lambda: NOW)
    return step, handler, settings, calls


def test_a_range_larger_than_the_cap_is_reported_incomplete_and_its_tail_is_recovered_on_resume(monkeypatch):
    """Review P1-1: 7 rows, pages of 2, a cap of 3 pages: the first run handles 6 and says so; the resume recovers
    the 7th; nothing is handled twice and the feed's cursor is untouched."""
    rows = [row(n) for n in range(1, 8)]
    step, handler, settings, _calls = _cap_world(monkeypatch, rows)
    first = step.backfill(NOW - timedelta(days=2), NOW, max_pages=3)
    assert first["complete"] is False and first["reason"] == "page_cap"
    assert first["resume_after"] == rows[5]["id"] and len(handler.facts) == 6
    second = step.backfill(NOW - timedelta(days=2), NOW, resume_after=first["resume_after"], max_pages=3)
    assert second["complete"] is True and second["resume_after"] is None
    handled = [f.extra["source_id"] for f in handler.facts]
    assert handled == [f"sepay:v2:{r['id']}" for r in rows] and len(set(handled)) == 7   # each exactly once
    assert settings.value == {"since_id": "authoritative", "backfill_from": None} and settings.writes == []


def test_a_rate_limit_after_several_pages_is_incomplete_with_its_wait_and_resumes_exactly_once(monkeypatch):
    rows = [row(n) for n in range(1, 6)]
    step, handler, settings, _calls = _cap_world(monkeypatch, rows, fail_at=3)
    first = step.backfill(NOW - timedelta(days=2), NOW, max_pages=3)
    assert first["complete"] is False and first["reason"] == "rate_limited" and first["retry_after"] == 30
    assert first["resume_after"] == rows[3]["id"] and len(handler.facts) == 4
    second = step.backfill(NOW - timedelta(days=2), NOW, resume_after=first["resume_after"], max_pages=3)
    assert second["complete"] is True
    assert [f.extra["source_id"] for f in handler.facts] == [f"sepay:v2:{r['id']}" for r in rows]
    assert settings.writes == []


def test_rows_still_inside_the_settle_delay_leave_the_range_incomplete(monkeypatch):
    rows = [row(1), row(2, minutes_ago=5)]
    step, handler, _settings, _calls = _cap_world(monkeypatch, rows)
    result = step.backfill(NOW - timedelta(days=1), NOW)
    assert result["complete"] is False and result["reason"] == "settle_delay"
    assert result["resume_after"] == rows[0]["id"] and len(handler.facts) == 1


def test_the_route_never_answers_ok_for_an_incomplete_recovery(route_admin):
    client, answers = route_admin
    answers.append({"complete": False, "reason": "page_cap", "resume_after": "row-6", "retry_after": None,
                    "counts": {"sepay_feed_apply": 6}})
    answer = client.post("/api/admin/billing/sepay/backfill",
                         json={"date_from": "2026-10-01T00:00:00+00:00", "date_to": "2026-10-02T00:00:00+00:00"})
    assert answer.status_code == 409 and answer.json()["detail"]["category"] == "backfill_incomplete"
    assert answer.json()["detail"]["context"]["resume_after"] == "row-6"
    answers.append({"complete": False, "reason": "rate_limited", "resume_after": "row-4", "retry_after": 30,
                    "counts": {}})
    limited = client.post("/api/admin/billing/sepay/backfill",
                          json={"date_from": "2026-10-01T00:00:00+00:00", "date_to": "2026-10-02T00:00:00+00:00",
                                "resume_after": "row-2"})
    assert limited.status_code == 429 and limited.json()["detail"]["context"]["retry_after"] == 30
    answers.append({"complete": True, "reason": None, "resume_after": None, "retry_after": None, "counts": {}})
    done = client.post("/api/admin/billing/sepay/backfill",
                       json={"date_from": "2026-10-01T00:00:00+00:00", "date_to": "2026-10-02T00:00:00+00:00",
                             "resume_after": "row-4"})
    assert done.status_code == 200 and done.json()["complete"] is True


@pytest.fixture
def route_admin():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from writing_coach import billing_api

    names = ("_service", "_backbone", "_admin", "_public_base", "_items", "_reconcile", "_credits", "_sepay_backfill")
    saved = {name: getattr(billing_api, name) for name in names}
    answers: list[dict] = []

    def backfill(start, end, *, resume_after=None):
        return answers.pop(0)

    billing_api.configure_billing(service=SimpleNamespace(), backbone=SimpleNamespace(is_active=True),
                                  admin_guard=lambda request: None, public_base_url="https://orena.test",
                                  reconciliation=SimpleNamespace(), sepay_backfill=backfill)
    app = FastAPI()
    app.include_router(billing_api.router)
    yield TestClient(app), answers
    for name, value in saved.items():
        setattr(billing_api, name, value)


@pytest.mark.parametrize(("start", "end"), [(NOW, NOW), (NOW, NOW - timedelta(days=1)),
                                            (NOW - timedelta(days=40), NOW)])
def test_a_backfill_range_is_positive_and_bounded(start, end):
    with pytest.raises(ValueError):
        feed([]).backfill(start, end)
