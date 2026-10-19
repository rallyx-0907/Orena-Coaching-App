"""BQ (owner, 2026-10-20): operators tune settings in Admin, so moving from test to production is easy, and the pilot
runs like production. docs/operations/SETTINGS_REFERENCE.md is the reference.

Proved here:

  1. the env-only tunables are policies (range, audit, the variable still pins them):
     AI_DAILY_SPEND_WARN_RATIO, BILLING_PAST_DUE_GRACE_HOURS, READING_SOURCE_POLL_INTERVAL_SECONDS (re-read every tick),
     BILLING_NEW_SALES (danger: confirmed);
  2. safety fuses Admin may only tighten:
     - the system ceiling is min(AI_DAILY_SPEND_CEILING_USD, Admin), and a value above the environment is refused;
     - a retention sweep a published promise requires can be turned on, never off, on staging and production;
     - quota enforcement cannot be switched off (nor a meter dropped) on staging and production, and the environment's
       meters are a floor the setting can add to;
  3. the published promises (start and Admin's readiness summary) read the effective values.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from policy_support import MemoryPolicyStore, installed
from writing_coach import policies
from writing_coach.ai import spend_gate
from writing_coach.core.published_promises import enforce_at_start, unmet_promises

NEW = {
    # key: (env, default, low, high, danger)
    "ai.daily_spend_warn_ratio": ("AI_DAILY_SPEND_WARN_RATIO", 0.8, 0.05, 1, ""),
    "billing.past_due_grace_hours": ("BILLING_PAST_DUE_GRACE_HOURS", 48, 0, 336, "charging"),
    "reading.source_poll_interval_seconds": ("READING_SOURCE_POLL_INTERVAL_SECONDS", 900, 0, 86_400, ""),
    "billing.new_sales": ("BILLING_NEW_SALES", True, None, None, "charging"),
    "agent.memory_retention_sweep": ("AGENT_MEMORY_RETENTION_SWEEP", False, None, None, "delete"),
    "usage.retention_sweep": ("USAGE_RETENTION_SWEEP", False, None, None, "delete"),
    "admin_audit.retention_sweep": ("ADMIN_AUDIT_RETENTION_SWEEP", False, None, None, "delete"),
}
SWEEPS = ("feedback.retention_sweep", "agent.turn_retention_sweep", "agent.memory_retention_sweep",
          "usage.retention_sweep", "admin_audit.retention_sweep")


def save(change, **kw):
    return policies.save(change, updated_by="admin@x.test", actor="admin-sub", **kw)


# ============================================================================================ 1. the new policies ==

@pytest.mark.parametrize("key", sorted(NEW))
def test_each_new_policy_is_declared_with_its_range_default_and_pin(key):
    env, default, low, high, danger = NEW[key]
    item = policies.BY_KEY[key]
    assert (item.env, item.default, item.low, item.high, item.danger) == (env, default, low, high, danger)
    with installed(MemoryPolicyStore()):
        assert policies.value(key) == default, "nothing stored: the default the code carried"


@pytest.mark.parametrize("key, raw, expected", [
    ("ai.daily_spend_warn_ratio", "0.7", 0.7),
    ("billing.past_due_grace_hours", "24", 24),
    ("reading.source_poll_interval_seconds", "0", 0),
    ("reading.source_poll_interval_seconds", "abc", 900),
    ("billing.new_sales", "off", False),
    ("billing.new_sales", "on", True),
    ("usage.retention_sweep", "on", True),
])
def test_the_variable_still_pins_the_policy_and_locks_the_field(key, raw, expected):
    env_name = policies.BY_KEY[key].env
    with installed(MemoryPolicyStore(), env={env_name: raw}):
        assert policies.value(key) == expected
        assert policies.is_pinned(key)
        row = {item["key"]: item for item in policies.snapshot()["policies"]}[key]
        assert row["locked"] and row["source"] == "env"
        with pytest.raises(policies.PolicyInvalid, match="locked by the environment"):
            save({"set": {key: policies.BY_KEY[key].default}, "confirm": {key: True}})


@pytest.mark.parametrize("key, bad", [
    ("ai.daily_spend_warn_ratio", 0), ("ai.daily_spend_warn_ratio", 1.5),
    ("billing.past_due_grace_hours", 337), ("billing.past_due_grace_hours", -1),
    ("reading.source_poll_interval_seconds", 86_401), ("billing.new_sales", "off"),
])
def test_a_value_out_of_range_is_refused(key, bad):
    with installed(MemoryPolicyStore()) as store:
        with pytest.raises(policies.PolicyInvalid):
            save({"set": {key: bad}, "confirm": {key: True}})
        assert store.rows == {} and store.audits == []


def test_a_change_is_audited_and_a_dangerous_one_needs_its_confirmation():
    with installed(MemoryPolicyStore()) as store:
        save({"set": {"ai.daily_spend_warn_ratio": 0.7, "reading.source_poll_interval_seconds": 1800}})
        assert store.audits[-1]["payload"]["changes"]["ai.daily_spend_warn_ratio"] == {"from": 0.8, "to": 0.7,
                                                                                         "reset": False}
        for key, value in (("billing.new_sales", False), ("billing.past_due_grace_hours", 24)):
            with pytest.raises(policies.PolicyConfirmationRequired):
                save({"set": {key: value}})
            save({"set": {key: value}, "confirm": {key: True}})
            assert policies.value(key) == value
            assert store.audits[-1]["payload"]["confirmed"] == [key]


def test_the_consumers_read_the_policy_when_they_act(monkeypatch):
    from writing_coach.billing import readiness
    from writing_coach.product import billing_grace
    from writing_coach.reading_source_poller import ReadingSourcePoller, configured_interval

    monkeypatch.delenv(billing_grace.ENV, raising=False)
    monkeypatch.delenv("READING_SOURCE_POLL_INTERVAL_SECONDS", raising=False)
    with installed(MemoryPolicyStore({"billing.past_due_grace_hours": 24, "reading.source_poll_interval_seconds": 60,
                                      "billing.new_sales": False})):
        assert billing_grace.past_due_hours() == 24
        assert billing_grace.current().window("polar", "past_due") == timedelta(hours=24)
        assert billing_grace.past_due_hours({}) == 48, "an explicit environment is read alone, as before"
        poller = ReadingSourcePoller(content=None, jobs=None, engine=None, interval_seconds=configured_interval)
        assert poller.interval == timedelta(seconds=60)
        facts = readiness.RuntimeFacts(switch=True, backend="postgresql", backbone="active",
                                       commerce_schema=lambda: "present", orders_schema=lambda: "present",
                                       entitlement_source=lambda: "installed", service=None,
                                       public_base_url="https://x.test", production=False,
                                       new_sales=readiness.policy_new_sales)
        report = readiness.report(facts)
        assert report["checks"]["new_sales"] == "paused" and "new_sales_paused" in report["blockers"]
        save({"set": {"billing.new_sales": True}, "confirm": {"billing.new_sales": True}})
        assert readiness.report(facts)["checks"]["new_sales"] == "on", "a pause lifts without a restart"


def test_an_unreadable_store_keeps_new_sales_closed():
    """Review of #428 P2-2: a store this process never read means paused, never "on by default"."""
    from writing_coach.billing import readiness

    facts = readiness.RuntimeFacts(switch=True, backend="postgresql", backbone="active",
                                   commerce_schema=lambda: "present", orders_schema=lambda: "present",
                                   entitlement_source=lambda: "installed", service=None,
                                   public_base_url="https://x.test", production=False,
                                   new_sales=readiness.policy_new_sales)
    with installed(MemoryPolicyStore(fail_reads=True)):
        report = readiness.report(facts)
        assert report["checks"]["new_sales"] == "paused" and "new_sales_paused" in report["blockers"]
    store = MemoryPolicyStore({"billing.new_sales": False})
    with installed(store):
        assert readiness.report(facts)["checks"]["new_sales"] == "paused"
        store.fail_reads = True
        policies.clear_cache()
        assert readiness.report(facts)["checks"]["new_sales"] == "paused", "a later failure keeps the pause read"
    with installed(MemoryPolicyStore()):
        assert readiness.report(facts)["checks"]["new_sales"] == "on", "a readable store with nothing saved: on"


def test_the_poller_reads_its_interval_every_tick_and_zero_skips_the_poll(monkeypatch):
    from writing_coach import reading_source_poller as module

    seconds = [0]
    polled = []
    poller = module.ReadingSourcePoller(content=None, jobs=None, engine=None, interval_seconds=lambda: seconds[0])
    poller.poll_due = lambda **kw: polled.append(True) or []
    ticks = iter([True, True, False])
    monkeypatch.setattr(module.time, "sleep", lambda s: seconds.__setitem__(0, 600))  # Admin raises it between ticks
    poller.run_forever(should_run=lambda: next(ticks), tick=0)
    assert polled == [True], "the first tick saw 0 (off); the second saw 600 and polled"


def test_the_memory_sweep_follows_its_live_switch():
    from writing_coach.agent.memory_runtime import ExpiredMemorySweep

    calls = []
    on = [False]
    sweep = ExpiredMemorySweep(lambda now, batch: calls.append(batch) or 0, clock=lambda: datetime(2026, 10, 20, tzinfo=UTC),
                               run=lambda work: work(), enabled=lambda: on[0])
    assert sweep.maybe_sweep() is None and calls == [], "off: nothing is deleted"
    on[0] = True
    assert sweep.maybe_sweep() == 0 and calls == [500], "switched on in Admin: it runs, no restart"


# =============================================================================================== 2. safety fuses ==

def test_the_system_ceiling_is_the_lower_of_the_environment_and_admin():
    key = "ai.daily_spend_ceiling_usd"
    env = {"AI_DAILY_SPEND_CEILING_USD": "5"}
    with installed(MemoryPolicyStore(), env=env) as store:
        assert policies.value(key) == 5.0, "nothing in Admin: the environment's ceiling"
        row = {item["key"]: item for item in policies.snapshot()["policies"]}[key]
        assert not row["locked"] and row["high"] == 5.0 and row["env_max"] == "AI_DAILY_SPEND_CEILING_USD"
        save({"set": {key: 2.0}})
        assert policies.value(key) == 2.0, "Admin lowered it"
        with pytest.raises(policies.PolicyInvalid, match="can only be lowered"):
            save({"set": {key: 6.0}, "confirm": {key: True}})
        assert policies.value(key) == 2.0 and len(store.audits) == 1, "the refused raise wrote nothing"
        save({"reset": [key], "confirm": {key: True}})  # empty (no Admin ceiling) is confirmed, like "no cap"
        assert policies.value(key) == 5.0, "a reset returns to the environment's ceiling, never above it"
    with installed(MemoryPolicyStore({key: 2.0}), env={}):
        assert policies.value(key) == 2.0, "no environment ceiling: Admin's applies (tighter than none)"
    with installed(MemoryPolicyStore({key: 9.0}), env=env):
        assert policies.value(key) == 5.0, "a stored value above a later, lower environment ceiling is capped"


def test_the_ceiling_gate_applies_an_admin_change_without_a_restart():
    key = "ai.daily_spend_ceiling_usd"
    try:
        with installed(MemoryPolicyStore(), env={"AI_DAILY_SPEND_CEILING_USD": "5"}):
            spend_gate.configure_ceiling(spend_gate.live_ceiling, read=lambda since: (1.5, 0),
                                         warn_ratio=spend_gate.live_warn_ratio)
            assert spend_gate.ceiling_usd() == 5.0 and not spend_gate.ceiling_reached(mark=False)
            save({"set": {key: 1.0, "ai.daily_spend_warn_ratio": 0.5}})
            assert spend_gate.ceiling_usd() == 1.0 and spend_gate.ceiling_reached(mark=False)
            assert spend_gate.ceiling_status()["ceiling_usd"] == 1.0
    finally:
        spend_gate.configure_ceiling(None, read=None)


PUBLIC_ALIASES = ("staging", "production", "stage", "prod", "public", "Production", " STAGING ")


@pytest.mark.parametrize("app_env", PUBLIC_ALIASES)
@pytest.mark.parametrize("key", SWEEPS)
def test_a_promised_sweep_is_on_and_cannot_be_turned_off_on_a_public_runtime(key, app_env):
    """Review of #428: every APP_ENV alias the deployment guard treats as public, any letter case."""
    with installed(MemoryPolicyStore(), env={"APP_ENV": app_env}) as store:
        assert policies.value(key) is True, "on by default: removing a pin keeps the promise"
        assert policies.value_strict(key) is True
        with pytest.raises(policies.PolicyInvalid, match="never off"):
            save({"set": {key: False}, "confirm": {key: True}})
        save({"set": {key: True}, "confirm": {key: True}})
        with pytest.raises(policies.PolicyInvalid, match="never off"):
            save({"set": {key: False}, "confirm": {key: True}})
        save({"reset": [key], "confirm": {key: True}})  # back to the public default: still on
        assert policies.value(key) is True and store.audits
    with installed(MemoryPolicyStore({key: False}), env={"APP_ENV": app_env}):
        assert policies.value(key) is True, "a false stored before the rule (or elsewhere) never switches it off"
        row = {item["key"]: item for item in policies.snapshot()["policies"]}[key]
        assert row["value"] is True and row["default"] is True
    env_name = policies.BY_KEY[key].env
    with installed(MemoryPolicyStore(), env={"APP_ENV": app_env, env_name: "off"}):
        assert policies.value(key) is False, "only an explicit environment pin can (startup logs it as an ERROR)"


@pytest.mark.parametrize("key", SWEEPS)
def test_development_keeps_the_sweeps_off_by_default_and_editable(key):
    with installed(MemoryPolicyStore({key: True}), env={"APP_ENV": "development"}):
        save({"set": {key: False}, "confirm": {key: True}})
        assert policies.value(key) is False, "development may switch a sweep off"
    with installed(MemoryPolicyStore(), env={}):
        assert policies.value(key) is False


def test_an_unpinned_promised_sweep_keeps_the_promise_at_start_on_a_public_runtime(caplog):
    """Review of #428 P2-3: removing an env pin no longer turns a promised sweep off on staging or production."""
    import logging

    env = {"APP_ENV": "staging", "AI_DAILY_SPEND_CEILING_USD": "2", "AGENT_MEMORY_HMAC_KEYS": "v1:" + "k" * 40,
           "ORENA_ACCOUNT_BACKBONE": "on", "AGENT_ENABLED": "true"}
    with installed(MemoryPolicyStore(), env=env), caplog.at_level(logging.ERROR):
        assert enforce_at_start(env, policies.value) == []
    with installed(MemoryPolicyStore(), env={**env, "USAGE_RETENTION_SWEEP": "off"}):
        assert [p.code for p in enforce_at_start({**env, "USAGE_RETENTION_SWEEP": "off"}, policies.value)] == \
            ["usage_retention_sweep_off"]


def _quota_settings(rows=None):
    from test_quota_gate import MemorySettings

    return MemorySettings(rows)


@pytest.mark.parametrize("app_env", PUBLIC_ALIASES)
def test_quota_enforcement_cannot_be_switched_off_on_staging_or_production(app_env):
    from writing_coach.product import quota

    previous = quota.runtime()
    try:
        settings = _quota_settings()
        quota.configure_quota(settings=settings, env={"APP_ENV": app_env})
        with pytest.raises(ValueError, match="cannot be switched off"):
            quota.save_switch({"enabled": False, "meters": []})
        quota.save_switch({"enabled": True, "meters": ["writing.review"]})
        quota.save_switch({"enabled": True, "meters": ["writing.review", "orena.message"]})  # adding is tightening
        with pytest.raises(ValueError, match="cannot be removed"):
            quota.save_switch({"enabled": True, "meters": ["orena.message"]})
        assert settings.rows[quota.SETTING_KEY]["value"]["meters"] == ["writing.review", "orena.message"]
        quota.configure_quota(settings=_quota_settings(), env={"APP_ENV": "development"})
        quota.save_switch({"enabled": False, "meters": []})  # development may switch it off
    finally:
        quota.configure_quota(**{field: getattr(previous, field) for field in
                                 ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})


def test_the_environment_meters_are_a_floor_the_setting_adds_to():
    from writing_coach.product import quota

    previous = quota.runtime()
    try:
        on = {"value": {"enabled": True, "meters": ["orena.message"]}, "updated_at": "x", "updated_by": "a"}
        env = {quota.FLAG: "on", quota.METERS_FLAG: "writing.review"}
        quota.configure_quota(settings=_quota_settings({quota.SETTING_KEY: on}), env=env)
        assert quota.switch()["meters"] == ["writing.review", "orena.message"]
        off = {**on, "value": {"enabled": False, "meters": ["orena.message"]}}
        quota.configure_quota(settings=_quota_settings({quota.SETTING_KEY: off}), env=env)
        assert quota.switch()["meters"] == ["writing.review"], "a setting switched off adds nothing, removes nothing"
        quota.configure_quota(settings=_quota_settings({quota.SETTING_KEY: on}), env={quota.FLAG: "off"})
        assert quota.switch()["state"] == "off", "the environment's off still wins where it is pinned"
    finally:
        quota.configure_quota(**{field: getattr(previous, field) for field in
                                 ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})


# ==================================================================================== 3. the published promises ==

KEYS = {"AGENT_MEMORY_HMAC_KEYS": "v1:" + "k" * 40, "ORENA_ACCOUNT_BACKBONE": "on", "AGENT_ENABLED": "true"}
ALL_ON = {**{key: True for key in SWEEPS}, "ai.daily_spend_ceiling_usd": None}


def policy(values):
    return lambda key: values[key]


def test_a_sweep_left_to_admin_is_read_from_its_policy():
    assert unmet_promises({**KEYS, "AI_DAILY_SPEND_CEILING_USD": "2"}, policy(ALL_ON)) == []
    for key, code in (("agent.memory_retention_sweep", "memory_retention_sweep_off"),
                      ("usage.retention_sweep", "usage_retention_sweep_off"),
                      ("admin_audit.retention_sweep", "admin_audit_retention_sweep_off")):
        assert [p.code for p in unmet_promises({**KEYS, "AI_DAILY_SPEND_CEILING_USD": "2"},
                                               policy({**ALL_ON, key: False}))] == [code]
    pinned_off = {**KEYS, "AI_DAILY_SPEND_CEILING_USD": "2", "USAGE_RETENTION_SWEEP": "off"}
    assert [p.code for p in unmet_promises(pinned_off, policy(ALL_ON))] == ["usage_retention_sweep_off"], \
        "a variable that pins the sweep off wins over Admin"


def test_an_admin_ceiling_never_counts_as_the_promise():
    """Review of #428 P2-1: an Admin ceiling can be cleared at any time, so only the environment's keeps the promise,
    and every public runtime refuses to start without it."""
    with_admin = policy({**ALL_ON, "ai.daily_spend_ceiling_usd": 2.0})
    assert [p.code for p in unmet_promises(KEYS, with_admin)] == ["spend_ceiling_unset"]
    for app_env in PUBLIC_ALIASES:
        with pytest.raises(RuntimeError, match="AI_DAILY_SPEND_CEILING_USD"):
            enforce_at_start({**KEYS, "APP_ENV": app_env}, with_admin)
    assert enforce_at_start({**KEYS, "APP_ENV": "staging", "AI_DAILY_SPEND_CEILING_USD": "2"}, with_admin) == []


def test_admin_readiness_reports_the_effective_values(monkeypatch):
    from fastapi.testclient import TestClient

    import app as app_module

    monkeypatch.setattr(app_module, "require_admin", lambda request: {"google_sub": "admin-1", "role": "admin"})
    for name in ("AI_DAILY_SPEND_CEILING_USD", "USAGE_RETENTION_SWEEP", "ADMIN_AUDIT_RETENTION_SWEEP"):
        monkeypatch.delenv(name, raising=False)
    client = TestClient(app_module.app)
    with installed(MemoryPolicyStore()):
        codes = {p["code"] for p in client.get("/api/admin/readiness-summary").json()["unmet_promises"]}
        assert {"spend_ceiling_unset", "usage_retention_sweep_off", "admin_audit_retention_sweep_off"} <= codes
    with installed(MemoryPolicyStore({"ai.daily_spend_ceiling_usd": 2.0, "usage.retention_sweep": True,
                                      "admin_audit.retention_sweep": True})):
        codes = {p["code"] for p in client.get("/api/admin/readiness-summary").json()["unmet_promises"]}
        assert not codes & {"usage_retention_sweep_off", "admin_audit_retention_sweep_off"}
        assert "spend_ceiling_unset" in codes, "an Admin ceiling alone is not the promise"
    monkeypatch.setenv("AI_DAILY_SPEND_CEILING_USD", "2")
    with installed(MemoryPolicyStore()):
        codes = {p["code"] for p in client.get("/api/admin/readiness-summary").json()["unmet_promises"]}
        assert "spend_ceiling_unset" not in codes
