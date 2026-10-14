"""PR-MON-1 / D-MON-006 against real PostgreSQL: a billing event recorded through the commerce repository changes the
effective plan that the Plan screen, quota admission and the Admin guard read - through the production wiring
(`CommerceEntitlementSource` over `PostgresCommerceRepository.subscription_for_account`).

Skips unless `ORENA_TEST_POSTGRES_URL` names a THROWAWAY database (the fixture upgrades it to head, like
`tests/test_quota_gate_postgres.py`). CI has no PostgreSQL service, so these run locally.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")

from sqlalchemy import create_engine, text  # noqa: E402

from writing_coach.persistence.commerce_repository import PostgresCommerceRepository, SubscriptionUpdate  # noqa: E402
from writing_coach.persistence.ids import stable_uuid  # noqa: E402
from writing_coach.persistence.incarnation_repository import PostgresIncarnationRepository  # noqa: E402
from writing_coach.persistence.product_repository import PostgresProductRepository  # noqa: E402
from writing_coach.product import catalog, quota  # noqa: E402
from writing_coach.product.api import billing_aware_membership  # noqa: E402
from writing_coach.product.entitlement import CommerceEntitlementSource  # noqa: E402
from writing_coach.product.membership import MembershipConflict, apply_change  # noqa: E402
from writing_coach.product.service import ProductService  # noqa: E402

URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")


@pytest.fixture(scope="module")
def engine():
    from alembic import command

    from writing_coach.persistence.runtime import _runtime_alembic_config

    cfg = _runtime_alembic_config()
    cfg.set_main_option("sqlalchemy.url", URL.replace("%", "%%"))
    command.upgrade(cfg, "head")
    engine = create_engine(URL, future=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def world(engine):
    key = f"entitlement-{uuid.uuid4()}"
    account = stable_uuid("user", key)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (id, user_key, email, name, picture, role, created_at) "
                 "VALUES (:id, :key, '', '', '', 'user', :now)"),
            {"id": account, "key": key, "now": datetime.now(UTC)},
        )
    incarnations = PostgresIncarnationRepository(engine)
    incarnation = incarnations.ensure_active(str(account))
    commerce = PostgresCommerceRepository(engine)
    products = PostgresProductRepository(engine)
    service = ProductService(products, billing=CommerceEntitlementSource(commerce))
    catalog.configure_plan_store(None)
    return {"key": key, "account": str(account), "incarnation": incarnation, "commerce": commerce,
            "polar": f"sub_polar_{uuid.uuid4().hex[:12]}",
            "products": products, "service": service, "incarnations": incarnations}


def record(world, *, version, state="active", plan="plus", paid_through=None, provider="payos", external=None):
    external = external or f"prepaid:{world['incarnation']}"
    outcome = world["commerce"].record_event(
        incarnation_id=world["incarnation"], provider=provider, external_event_id=f"{provider}:{uuid.uuid4()}",
        event_object_version=version, external_object_reference=external,
        update=SubscriptionUpdate(state=state, plan_id=plan, external_customer_id=None, external_subscription_id=external,
                                  paid_through=paid_through, cancel_at_period_end=provider == "payos",
                                  provider_state="prepaid" if provider == "payos" else state),
    )
    assert outcome["status"] == "apply", outcome
    return outcome


def test_no_billing_record_is_the_legacy_answer(world):
    assert world["commerce"].subscription_for_account(world["account"]) is None
    assert world["service"].plan_for_user(world["key"]).id == "free"
    assert world["service"].account_state(world["key"])["subscription"] == {"state": "inactive", "status": "inactive"}


def test_a_recorded_prepaid_payment_is_the_effective_plan_everywhere(world, monkeypatch):
    record(world, version=1, plan="plus", paid_through=datetime.now(UTC) + timedelta(days=30))
    service = world["service"]
    assert service.entitlement(world["key"]).source == "billing"
    assert service.plan_for_user(world["key"], strict=True).id == "plus"
    assert service.account_state(world["key"])["plan"]["id"] == "plus"
    previous = quota.runtime()
    try:
        quota.configure_quota(repository=object(), incarnations=world["incarnations"], plan_for=service.plan_for_user,
                              settings=None, env={})
        from writing_coach.product import language_limit

        assert language_limit._limit(world["key"])[1] == "plus", "the language limit reads the same plan"
    finally:
        quota.configure_quota(**{f: getattr(previous, f) for f in
                                 ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})


def test_a_refunded_prepaid_purchase_reads_free(world):
    record(world, version=1, plan="plus", paid_through=datetime.now(UTC) + timedelta(days=30))
    record(world, version=2, state="ended", plan="plus", paid_through=datetime.now(UTC))
    assert world["service"].plan_for_user(world["key"]).id == "free"
    assert world["service"].account_state(world["key"])["subscription"]["status"] == "ended"


def test_a_polar_subscription_is_the_effective_plan(world):
    record(world, version=1, plan="pro", provider="polar", external=world["polar"],
           paid_through=datetime.now(UTC) + timedelta(days=30))
    assert world["service"].plan_for_user(world["key"]).id == "pro"


def test_a_polar_past_due_keeps_the_plan_for_the_grace_from_the_last_paid_end(world):
    """A past-due event that carries no paid-through keeps the stored end of the last paid period (the commerce
    record's own rule), and the 2-day grace (D-MON-011) counts from it."""
    paid_end = datetime.now(UTC) - timedelta(hours=6)
    record(world, version=1, plan="pro", provider="polar", external=world["polar"], paid_through=paid_end)
    record(world, version=2, state="past_due", plan="pro", provider="polar", external=world["polar"], paid_through=None)
    stored = world["commerce"].subscription_for_account(world["account"])
    assert (stored["state"], stored["paid_through"]) == ("past_due", paid_end)
    effective = world["service"].entitlement(world["key"])
    assert (effective.plan_id, effective.status, effective.valid_until) == ("pro", "past_due", paid_end + timedelta(hours=48))
    record(world, version=3, state="past_due", plan="pro", provider="polar", external=world["polar"],
           paid_through=datetime.now(UTC) - timedelta(days=3))
    assert world["service"].plan_for_user(world["key"]).id == "free", "the grace ended"
    record(world, version=4, state="active", plan="pro", provider="polar", external=world["polar"],
           paid_through=datetime.now(UTC) + timedelta(days=30))
    assert world["service"].plan_for_user(world["key"]).id == "pro", "a recovered payment restores the plan"


def test_a_live_billing_relationship_suppresses_an_existing_manual_grant(world):
    """Review P1-1 on PostgreSQL: a manual Pro granted before the purchase never shows through while billing owns the
    account (past due outside the grace); it applies again only once billing has ended."""
    world["products"].apply_membership(world["account"], plan="pro", until=datetime.now(UTC) + timedelta(days=60))
    record(world, version=1, plan="plus", provider="polar", external=world["polar"],
           paid_through=datetime.now(UTC) + timedelta(days=30))
    assert world["service"].plan_for_user(world["key"]).id == "plus"
    record(world, version=2, state="past_due", plan="plus", provider="polar", external=world["polar"],
           paid_through=datetime.now(UTC) - timedelta(days=3))
    effective = world["service"].entitlement(world["key"])
    assert (effective.plan_id, effective.status, effective.billing_live) == ("free", "past_due", True)
    record(world, version=3, state="ended", plan="plus", provider="polar", external=world["polar"],
           paid_through=datetime.now(UTC) - timedelta(days=1))
    assert world["service"].entitlement(world["key"]).source == "manual", "ended billing releases the earlier manual grant"


def test_a_manual_write_after_billing_took_ownership_is_refused_inside_its_transaction(world):
    """Review P1-2, step 3: the Admin pre-check saw no billing, then the payment committed. The write itself must
    refuse and create no manual row - calling the store directly is that write without the pre-check."""
    record(world, version=1, plan="plus", paid_through=datetime.now(UTC) + timedelta(days=30))
    with pytest.raises(MembershipConflict):
        world["products"].apply_membership(world["account"], plan="pro", until=None,
                                           audit={"action": "product.account.membership", "actor": "admin",
                                                  "entity_type": "account", "entity_id": world["account"], "payload": {}})
    assert world["products"].get_subscription(world["key"]) is None, "no latent manual grant"
    with world["commerce"]._engine.connect() as connection:
        audits = connection.execute(text("SELECT count(*) FROM audit_logs WHERE entity_id = :id"),
                                    {"id": world["account"]}).scalar_one()
    assert audits == 0, "the refused change wrote no audit row either"


def test_a_payment_in_flight_serializes_the_manual_write_and_leaves_no_latent_grant(world, engine):
    """Review P1-2 race: a provider event holds the incarnation FOR SHARE (as `record_event` does) while it makes
    billing the owner; the Admin write blocks on the incarnation lock, then sees the committed billing and refuses.
    When billing later ends, no stale manual plan appears."""
    webhook = engine.connect()
    transaction = webhook.begin()
    webhook.execute(text("SELECT status FROM account_incarnations WHERE id = :inc FOR SHARE"), {"inc": world["incarnation"]})
    webhook.execute(text(
        "INSERT INTO commerce_subscriptions (id, incarnation_id, provider, plan_id, state, paid_through, created_at, "
        "updated_at) VALUES (:id, :inc, 'payos', 'plus', 'active', :until, :now, :now)"),
        {"id": uuid.uuid4(), "inc": world["incarnation"], "until": datetime.now(UTC) + timedelta(days=30),
         "now": datetime.now(UTC)})
    outcome: dict = {}

    def admin_write():
        try:
            world["products"].apply_membership(world["account"], plan="pro", until=None)
            outcome["result"] = "written"
        except MembershipConflict:
            outcome["result"] = "refused"
        except Exception as error:  # noqa: BLE001 - reported below
            outcome["result"] = repr(error)

    writer = threading.Thread(target=admin_write)
    writer.start()
    time.sleep(1.0)
    assert writer.is_alive(), "the Admin write waits for the in-flight billing event"
    transaction.commit()
    webhook.close()
    writer.join(timeout=15)
    assert outcome.get("result") == "refused", outcome
    assert world["products"].get_subscription(world["key"]) is None, "no latent manual grant"
    with engine.begin() as connection:
        connection.execute(text("UPDATE commerce_subscriptions SET state = 'ended', paid_through = :past "
                                "WHERE incarnation_id = :inc"),
                           {"past": datetime.now(UTC) - timedelta(minutes=1), "inc": world["incarnation"]})
    assert world["service"].plan_for_user(world["key"]).id == "free", "billing ended: Free, not a stale manual Pro"


def test_a_manual_write_that_commits_first_is_not_blocked_by_a_later_payment(world):
    """The other order: the Admin decision committed before billing existed. It is a real grant (not a race), it
    is shadowed while billing owns the account, and applies again only when billing ends - the existing policy."""
    world["products"].apply_membership(world["account"], plan="pro", until=datetime.now(UTC) + timedelta(days=60))
    record(world, version=1, plan="plus", paid_through=datetime.now(UTC) + timedelta(days=30))
    assert world["service"].plan_for_user(world["key"]).id == "plus"


def test_a_deleted_incarnations_billing_record_is_not_the_accounts(world):
    record(world, version=1, plan="pro", paid_through=datetime.now(UTC) + timedelta(days=30))
    world["incarnations"].mark_deleted(world["incarnation"])
    assert world["commerce"].subscription_for_account(world["account"]) is None
    assert world["service"].plan_for_user(world["key"]).id == "free"


def test_an_admin_cannot_hand_set_a_plan_billing_owns(world):
    record(world, version=1, plan="plus", paid_through=datetime.now(UTC) + timedelta(days=30))
    store = billing_aware_membership(world["products"], world["service"])
    with pytest.raises(MembershipConflict):
        apply_change(store, world["account"], {"plan_id": "pro"}, actor_key="admin", protected_emails=set())
    assert world["products"].get_subscription(world["key"]) is None, "nothing was written"
    account = store.account_membership(world["account"])
    assert (account["plan_id"], account["status"], account["billing_owned"]) == ("plus", "active", True)


def test_a_committed_payos_payment_not_yet_synced_refuses_a_manual_write():
    """Re-verification of P1-2: payOS commits the payment (`mark_paid`) and records the access in a second
    transaction (`sync_prepaid`). An Admin plan write in between must not leave a latent manual grant.

    Runs in its own schema at head plus the proposed `billing_orders` (0027) and its PR-MON-3 follow-up (0031), as
    `tests/test_billing.py` does."""
    from urllib.parse import quote

    from alembic import command
    from alembic.config import Config
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    from tests.test_billing import BILLING_BASE, PAYOS, _proposed
    from writing_coach.billing.service import BillingService
    from writing_coach.persistence.billing_repository import PostgresBillingRepository

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema = f"entitle_{uuid.uuid4().hex[:10]}"
    separator = "&" if "?" in URL else "?"
    schema_url = f"{URL}{separator}options={quote(f'-csearch_path={schema}')}"
    admin = create_engine(URL, future=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        cfg = Config(os.path.join(root, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(root, "migrations"))
        cfg.set_main_option("path_separator", "os")
        cfg.set_main_option("sqlalchemy.url", schema_url.replace("%", "%%"))
        command.upgrade(cfg, BILLING_BASE)
        engine = create_engine(schema_url, future=True)
        try:
            with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
                _proposed("20261005_0027_billing_orders").upgrade()
                _proposed("20261014_0031_billing_reconciliation").upgrade()
                _proposed("20261014_0032_credit_ledger").upgrade()
                _proposed("20261015_0033_credit_topup_orders").upgrade()
            key = f"entitlement-sync-{uuid.uuid4()}"
            account = stable_uuid("user", key)
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO users (id, user_key, email, name, picture, role, created_at) "
                                        "VALUES (:id, :key, '', '', '', 'user', :now)"),
                                   {"id": account, "key": key, "now": datetime.now(UTC)})
            incarnation = PostgresIncarnationRepository(engine).ensure_active(str(account))
            orders, commerce = PostgresBillingRepository(engine), PostgresCommerceRepository(engine)
            products = PostgresProductRepository(engine)
            service = ProductService(products, billing=CommerceEntitlementSource(commerce))
            billing = BillingService(orders=orders, commerce=commerce, gateways={"payos": PAYOS}, prices={})
            order = orders.create_order(operation_id=str(uuid.uuid4()), incarnation_id=incarnation, gateway="payos",
                                        plan_id="plus", period="month", currency="VND", amount_minor=99_000)

            # 1. a valid payOS payment commits; 2. sync_prepaid has not run yet
            paid = orders.mark_paid(order_code=int(order["order_code"]), event_id="payos:evt-1", amount_minor=99_000,
                                    currency="VND")
            assert paid["status"] == "applied"
            assert commerce.subscription_for_account(str(account)) is None, "the access is not recorded yet"
            # 3-4. the Admin plan write in that window is refused and writes nothing
            with pytest.raises(MembershipConflict):
                products.apply_membership(str(account), plan="pro", until=None)
            assert products.get_subscription(key) is None, "no latent manual grant"
            # 5. the sync completes: billing owns the account
            assert billing.sync_prepaid(incarnation, "payos", event_id=f"payos:paid:{order['order_code']}").status == "apply"
            assert service.plan_for_user(key).id == "plus"
            with pytest.raises(MembershipConflict):
                products.apply_membership(str(account), plan="pro", until=None)
            # 6. billing ends later: the refund commits to the orders first, its access sync second - the same window
            assert orders.mark_refunded(order_code=int(order["order_code"]), note="returned")["status"] == "applied"
            with pytest.raises(MembershipConflict):
                products.apply_membership(str(account), plan="pro", until=None)
            assert products.get_subscription(key) is None, "no grant slips in before the refund is synced"
            assert billing.sync_prepaid(incarnation, "payos", event_id=f"payos:refund:{order['order_code']}").status == "apply"
            # 7. no unexpected manual plan appears, and the account is released to Admin again
            assert service.entitlement(key).source in ("none", "billing")
            assert service.plan_for_user(key).id == "free"
            assert products.get_subscription(key) is None
            products.apply_membership(str(account), plan="pro", until=None)
            assert service.plan_for_user(key).id == "pro", "after billing ended, a NEW Admin decision applies"
        finally:
            engine.dispose()
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()

