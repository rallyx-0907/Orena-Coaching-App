"""PR-MON-8 SePay on PostgreSQL (`ORENA_TEST_POSTGRES_URL`, throwaway database only; design revisions 5 + 6).

The locked payment decision (`mark_paid_domestic`) against the real `billing_orders`, account lock, reconciliation
items and credit ledger: a real race with a cancellation, the locked `expires_at`, every late-payment case,
cross-source exactly-once with and without a bank reference, and the grant / top-up happening once. SePay itself is
signed fixtures; nothing is called."""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests.test_credit_ledger_postgres import URL, ledger_world, no_drift
from tests.test_credit_topup_migration_postgres import ALL
from writing_coach.billing.gateway import hmac_sha256_hex
from writing_coach.billing.sepay import VIETNAM, SePayGateway

pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")

SECRET = "whsec-sepay-pg"
ACCOUNT = "123456789012"
GRACE = timedelta(hours=1)
PACK = {"pack_id": "starter", "credit_units": 500, "currency": "VND", "amount_minor": 50_000, "gateway": "sepay"}
# Production runs require a VA (§13.3, D-MON-030); receiving still uses the main account.
SEPAY = SePayGateway(webhook_secret=SECRET, account_number=ACCOUNT, account_name="A", bank_bin="970415",
                     payment_prefix="ORN", va_number="VQRAB12CD34E")


@pytest.fixture
def shop(tmp_path):
    from writing_coach.billing.service import BillingService, load_credit_packs
    from writing_coach.persistence.billing_reconciliation_repository import PostgresReconciliationRepository
    from writing_coach.persistence.billing_repository import PostgresBillingRepository
    from writing_coach.persistence.commerce_repository import PostgresCommerceRepository

    for world in ledger_world(ALL):
        path = tmp_path / "packs.json"
        path.write_text(json.dumps([PACK]))
        world.grace = GRACE

        def build(world=world, path=path):
            return BillingService(orders=PostgresBillingRepository(world.runtime),
                                  commerce=PostgresCommerceRepository(world.runtime), gateways={"sepay": SEPAY},
                                  prices={}, reconciliation=PostgresReconciliationRepository(world.runtime),
                                  credit_packs=load_credit_packs({"BILLING_CREDIT_PACKS_FILE": str(path)}),
                                  credits=world.service, domestic="sepay", production=True,
                                  grace=lambda: world.grace)  # fmt: skip

        world.billing = build()
        yield world


def checkout(shop, incarnation):
    started = shop.billing.start_checkout(
        incarnation_id=incarnation, price_key="credits:starter:sepay", operation_id=str(uuid.uuid4()),
        return_url="https://o/r", cancel_url="https://o/c", confirmed_amount_minor=50_000, confirmed_currency="VND",
        confirmed_credit_units=500)
    assert started["redirect_url"] == "" and started["transfer"]["memo"] == f"SEVQR ORN{started['order_code']}"
    return started["order_code"]


def set_order(shop, code, **values):
    assignments = ", ".join(f"{name} = :{name}" for name in values)
    shop.sql(f"UPDATE billing_orders SET {assignments} WHERE order_code = :code", code=code, **values)


def order(shop, code):
    return dict(shop.sql("SELECT state, paid_event_id, expires_at FROM billing_orders WHERE order_code = :c", c=code)[0])


def body(code, *, at, reference="FT1", amount=50_000, webhook_id=None):
    return json.dumps({"id": webhook_id or int(time.time_ns() % 10**9), "gateway": "VietinBank",
                       "transactionDate": at.astimezone(VIETNAM).strftime("%Y-%m-%d %H:%M:%S"),
                       "accountNumber": ACCOUNT, "subAccount": None, "code": f"ORN{code}",
                       "content": f"SEVQR ORN{code}", "transferType": "in", "description": "",
                       "transferAmount": amount, "accumulated": 0, "referenceCode": reference}).encode()


def deliver(shop, raw):
    stamp = str(int(datetime.now(UTC).timestamp()))
    headers = {"X-SePay-Signature": "sha256=" + hmac_sha256_hex(SECRET, stamp.encode() + b"." + raw),
               "X-SePay-Timestamp": stamp}
    return shop.billing.handle_webhook("sepay", headers, raw).status


def pay(shop, code, *, at=None, **kwargs):
    return deliver(shop, body(code, at=at or datetime.now(UTC), **kwargs))


def from_feed(shop, code, *, at=None, reference="FT1"):
    row = {"id": str(uuid.uuid4()), "transaction_date": (at or datetime.now(UTC)).astimezone(VIETNAM)
           .strftime("%Y-%m-%d %H:%M:%S"), "account_number": ACCOUNT, "transfer_type": "in", "amount_in": 50_000,
           "reference_number": reference, "code": f"ORN{code}", "webhook_success": 0}
    fact = SEPAY.to_fact(SEPAY.feed_transfer(row), payload_digest=SEPAY.feed_row_digest(row))
    return shop.billing.handle_fact(fact).status, row["id"]


def topups(shop):
    return shop.sql("SELECT count(*) AS n FROM credit_ledger WHERE kind = 'topup'")[0]["n"]


def items(shop):
    return [dict(r) for r in shop.sql("SELECT kind, reason, dedupe_key, external_event_id, reported_order_code, "
                                      "reported_amount_minor, reported_currency, provider_state, payload_digest, "
                                      "billing_order_id, incarnation_id FROM billing_reconciliation_items "
                                      "WHERE gateway = 'sepay' ORDER BY first_seen_at")]


# ---- exactly once ---------------------------------------------------------------------------------------------------

def test_a_referenced_transfer_credits_once_from_the_webhook_its_replay_and_the_feed(shop):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    raw = body(code, at=datetime.now(UTC), reference="FT9001", webhook_id=777)
    assert deliver(shop, raw) == "apply" and shop.balance(incarnation)["posted"] == 500
    assert deliver(shop, raw) == "duplicate"                          # SePay's retry or manual replay
    assert from_feed(shop, code, reference="FT9001")[0] == "duplicate"   # the same transfer, from the other source
    assert topups(shop) == 1 and items(shop) == []
    assert order(shop, code)["paid_event_id"] == f"sepay:ref:{ACCOUNT}:FT9001"
    no_drift(shop)


def test_without_a_bank_reference_a_second_source_is_ambiguous_never_a_second_payment(shop):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    assert pay(shop, code, reference="", webhook_id=778) == "apply"
    status, feed_id = from_feed(shop, code, reference="")
    assert status == "source_ambiguous" and topups(shop) == 1
    (item,) = items(shop)
    assert (item["kind"], item["reason"], item["external_event_id"]) == (
        "payment_not_payable", "source_ambiguous", f"sepay:v2:{feed_id}")
    assert item["dedupe_key"] == f"sepay:v2:{feed_id}"


def test_two_different_bank_references_are_a_real_second_transfer(shop):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    assert pay(shop, code, reference="FTA") == "apply"
    assert pay(shop, code, reference="FTB") == "not_payable" and topups(shop) == 1
    assert items(shop)[0]["kind"] == "payment_not_payable" and items(shop)[0]["reason"] == "not_payable"


def test_a_timely_payment_grants_the_plan_once(shop):
    from writing_coach.persistence.commerce_repository import PostgresCommerceRepository

    incarnation = shop.account()
    made = shop.billing.orders.create_order(operation_id=str(uuid.uuid4()), incarnation_id=incarnation, gateway="sepay",
                                            plan_id="plus", period="month", currency="VND", amount_minor=99_000)
    code = int(made["order_code"])
    raw = body(code, at=datetime.now(UTC), amount=99_000, reference="FTP1")
    assert deliver(shop, raw) in {"apply", "applied"} and deliver(shop, raw) == "duplicate"
    access = PostgresCommerceRepository(shop.runtime).get_subscription(incarnation)
    assert access["state"] == "active" and access["plan_id"] == "plus"
    assert shop.sql("SELECT count(*) AS n FROM billing_orders WHERE state = 'paid'")[0]["n"] == 1


# ---- late payments, decided on the provider's transaction time under the lock --------------------------------------

@pytest.mark.parametrize(("state", "minutes_after_expiry", "expected"), [
    ("pending", 61, "late"),              # past expires_at + grace, though the expiry worker never ran
    ("created", 61, "late"),
    ("expired", 61, "late"),
    ("pending", 30, "apply"),             # the webhook arrives long after, the transfer itself was timely
    ("expired", 30, "apply"),             # expired by timeout, paid inside the grace
    ("cancelled", 30, "order_closed"),    # ended on purpose: never auto-granted, inside the grace or not
    ("cancelled", 61, "order_closed"),
])
def test_late_payment_eligibility_is_the_transfer_time_whatever_the_stored_state(shop, state, minutes_after_expiry,
                                                                                 expected):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    expired_at = datetime.now(UTC) - timedelta(hours=3)
    set_order(shop, code, state=state, expires_at=expired_at)
    outcome = pay(shop, code, at=expired_at + timedelta(minutes=minutes_after_expiry))
    assert outcome == expected
    if expected == "apply":
        assert order(shop, code)["state"] == "paid" and topups(shop) == 1 and items(shop) == []
        return
    assert order(shop, code)["state"] == state and topups(shop) == 0   # no paid transition, no top-up
    (item,) = items(shop)
    assert item["kind"] == "payment_not_payable"
    assert item["reason"] == ("late_payment" if expected == "late" else "order_closed")
    assert (item["reported_order_code"], item["reported_amount_minor"], item["reported_currency"]) == (code, 50_000, "VND")
    assert item["incarnation_id"] is not None and item["billing_order_id"] is not None and item["payload_digest"]


def test_a_refunded_order_is_closed_whatever_the_time(shop):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    assert pay(shop, code, reference="FTR1") == "apply"
    shop.billing.record_refund(order_code=code, note="operator transfer back")   # the operator's own refund
    assert order(shop, code)["state"] == "refunded"
    assert pay(shop, code, reference="FTR2") == "order_closed"   # a new transfer for a refunded order
    closed = [item for item in items(shop) if item["reason"] == "order_closed"]
    assert len(closed) == 1 and shop.balance(incarnation)["posted"] == 0


def test_an_unconfigured_grace_fails_closed(shop):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    shop.grace = None
    assert pay(shop, code) == "late" and topups(shop) == 0 and order(shop, code)["state"] == "pending"
    assert items(shop)[0]["reason"] == "late_payment"


# ---- the race: a cancellation between the service's start and the locked operation ---------------------------------

def test_a_cancellation_committed_while_the_payment_waits_for_the_lock_wins(shop):
    """The payment starts while the order is pending, then waits for the order's lock while another transaction
    holds it and cancels the order; once that commits, the payment decides on the cancelled row."""

    incarnation = shop.account()
    code = checkout(shop, incarnation)
    about_to_lock = threading.Event()
    shop.billing.orders.pause_before_lock = about_to_lock.set
    result: dict = {}
    with shop.owner.connect() as other:
        transaction = other.begin()
        other.execute(shop.text("SELECT id FROM billing_orders WHERE order_code = :c FOR UPDATE"), {"c": code})
        other.execute(shop.text("UPDATE billing_orders SET state = 'cancelled' WHERE order_code = :c"), {"c": code})
        worker = threading.Thread(target=lambda: result.setdefault("status", pay(shop, code)))
        worker.start()
        assert about_to_lock.wait(10)
        time.sleep(0.5)
        assert worker.is_alive()          # blocked on the order's row lock, not decided on a stale read
        transaction.commit()
    worker.join(20)
    assert result["status"] == "order_closed"
    assert order(shop, code)["state"] == "cancelled" and topups(shop) == 0
    assert shop.balance(incarnation)["posted"] == 0
    assert items(shop)[0]["reason"] == "order_closed"


def test_a_cancellation_committed_while_the_payment_is_paused_before_the_lock_wins(shop):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    paused, resume = threading.Event(), threading.Event()

    def pause():
        paused.set()
        assert resume.wait(10)

    shop.billing.orders.pause_before_lock = pause
    result: dict = {}
    worker = threading.Thread(target=lambda: result.setdefault("status", pay(shop, code)))
    worker.start()
    assert paused.wait(10)
    set_order(shop, code, state="cancelled")   # another transaction, committed
    resume.set()
    worker.join(20)
    assert result["status"] == "order_closed" and order(shop, code)["state"] == "cancelled" and topups(shop) == 0


def test_the_grace_decision_uses_the_expires_at_read_under_the_lock(shop):
    """The transfer is timely against the expiry the order had when the payment started; the expiry is moved
    earlier before the lock. The decision follows the locked value: late, nothing granted."""

    incarnation = shop.account()
    code = checkout(shop, incarnation)
    start = datetime.now(UTC)
    set_order(shop, code, expires_at=start + timedelta(minutes=30))

    def move_expiry():
        set_order(shop, code, expires_at=start - timedelta(hours=3))

    shop.billing.orders.pause_before_lock = move_expiry
    assert pay(shop, code, at=start) == "late" and topups(shop) == 0
    assert order(shop, code)["state"] == "pending" and items(shop)[0]["reason"] == "late_payment"


# ---- review of 10471923 ---------------------------------------------------------------------------------------------

def test_a_leading_zero_order_code_is_never_the_order_from_the_webhook_or_the_feed(shop):
    """Review P1-1: `ORN0<code>` names no order, even when the amount matches an open one."""
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    padded = json.loads(body(code, at=datetime.now(UTC), reference="FTZ1"))
    padded["code"] = f"ORN0{code}"
    assert deliver(shop, json.dumps(padded).encode()) == "unknown_order"
    row = {"id": str(uuid.uuid4()), "transaction_date": datetime.now(UTC).astimezone(VIETNAM).strftime("%Y-%m-%d %H:%M:%S"),
           "account_number": ACCOUNT, "transfer_type": "in", "amount_in": 50_000, "reference_number": "FTZ2",
           "code": f"ORN00{code}", "webhook_success": 0}
    fact = SEPAY.to_fact(SEPAY.feed_transfer(row), payload_digest=SEPAY.feed_row_digest(row))
    assert shop.billing.handle_fact(fact).status == "unknown_order"
    assert topups(shop) == 0 and order(shop, code)["state"] == "pending"
    assert [item["kind"] for item in items(shop)] == ["payment_unknown_order", "payment_unknown_order"]


def test_an_operator_backfill_replays_idempotently_and_leaves_the_cursor_alone(shop):
    from writing_coach.billing.sepay_feed import CURSOR_KEY, SePayFeed

    incarnation = shop.account()
    code = checkout(shop, incarnation)
    paid_at = datetime.now(UTC) - timedelta(hours=2)
    set_order(shop, code, expires_at=paid_at + timedelta(minutes=10))
    rows = [{"id": str(uuid.uuid4()), "transaction_date": paid_at.astimezone(VIETNAM).strftime("%Y-%m-%d %H:%M:%S"),
             "account_number": ACCOUNT, "transfer_type": "in", "amount_in": 50_000, "reference_number": "FTBF1",
             "code": f"ORN{code}", "webhook_success": 0}]

    class Store:   # the platform settings; the cursor must never be read or written by a backfill
        def get_setting(self, key):
            raise AssertionError(f"a backfill read {key}")

        def set_setting(self, key, *a, **k):
            raise AssertionError(f"a backfill wrote {key}")

    feed = SePayFeed(service=shop.billing, gateway=SePayGateway(webhook_secret=SECRET, account_number=ACCOUNT,
                     account_name="A", bank_bin="970415", payment_prefix="ORN", api_token="t"), settings=Store(),
                     orders=shop.billing.orders, fetch=lambda request: {"data": rows})
    window = (datetime.now(UTC) - timedelta(days=1), datetime.now(UTC))
    first = feed.backfill(*window)
    assert first["complete"] is True and first["counts"] == {"sepay_feed_apply": 1}
    again = feed.backfill(*window)   # a replay of the same range changes nothing
    assert again["complete"] is True and again["counts"] == {"sepay_feed_duplicate": 1}
    assert topups(shop) == 1 and shop.balance(incarnation)["posted"] == 500
    assert CURSOR_KEY == "billing.sepay.feed_cursor"


def test_an_incomplete_backfill_resumes_exactly_once_on_the_real_ledger(shop, monkeypatch):
    """Review P1-1 of 851f4bb9: two paid packs, a page of one row and a cap of one page. The first run recovers the
    first and reports incomplete; the resume recovers the second; a full replay changes nothing."""
    from writing_coach.billing import sepay_feed

    monkeypatch.setattr(sepay_feed, "PER_PAGE", 1)
    paid_at = datetime.now(UTC) - timedelta(hours=2)
    rows = []
    for index in range(2):
        incarnation = shop.account()
        code = checkout(shop, incarnation)
        set_order(shop, code, expires_at=paid_at + timedelta(minutes=10))
        rows.append({"id": str(uuid.uuid4()), "transaction_date": paid_at.astimezone(VIETNAM).strftime(
            "%Y-%m-%d %H:%M:%S"), "account_number": ACCOUNT, "transfer_type": "in", "amount_in": 50_000,
            "reference_number": f"FTRS{index}", "code": f"ORN{code}", "webhook_success": 0})

    def fetch(request):
        since = request["params"].get("since_id")
        start = 0 if since is None else [r["id"] for r in rows].index(since) + 1
        return {"data": rows[start:start + 1]}

    feed = sepay_feed.SePayFeed(service=shop.billing, gateway=SePayGateway(
        webhook_secret=SECRET, account_number=ACCOUNT, account_name="A", bank_bin="970415", payment_prefix="ORN",
        api_token="t"), settings=None, orders=shop.billing.orders, fetch=fetch)
    window = (datetime.now(UTC) - timedelta(days=1), datetime.now(UTC))
    first = feed.backfill(*window, max_pages=1)
    assert first["complete"] is False and first["reason"] == "page_cap" and topups(shop) == 1
    second = feed.backfill(*window, resume_after=first["resume_after"], max_pages=1)
    assert second["counts"] == {"sepay_feed_apply": 1} and topups(shop) == 2
    boundary = None
    for _ in range(5):   # the whole range again, to its end: only duplicates
        replay = feed.backfill(*window, resume_after=boundary, max_pages=1)
        assert "sepay_feed_apply" not in replay["counts"]
        if replay["complete"]:
            break
        boundary = replay["resume_after"]
    assert replay["complete"] is True
    assert topups(shop) == 2 and items(shop) == []

