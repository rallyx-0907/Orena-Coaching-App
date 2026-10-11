"""D-172: the operational policies an administrator edits in Platform Admin (`writing_coach/policies.py`).

What is proved here, in the order the human's requirement ("changing something must never require touching code")
needs it:

  1. the registry: typed, ranged, every default is the value the code carried before, and an empty document is the
     defaults (so a deployment that never opens the page behaves exactly as it did);
  2. the precedence environment > Admin > default, an environment-pinned policy refused by the editor;
  3. the save: validation (unknown keys, types, ranges), compare-and-set (409), the audit row in the same transaction,
     the confirmation of dangerous changes and its record;
  4. fail-safe reads: a store that cannot be read never raises into a request; the quota switch keeps its own
     fail-closed rule (D-161);
  5. one test per consumer group: each reads the effective value when it acts, not when the process started;
  6. the HTTP routes.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
import sqlalchemy as sa  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from policy_support import MemoryPolicyStore, installed  # noqa: E402
from test_quota_orena_message import _isolated  # noqa: E402,F401  (autouse fixture: the quota runtime is put back)
from test_speech_transcribe_guard import needs_ffmpeg, room, silent_wav  # noqa: E402,F401  (`room` is a fixture)

from writing_coach import policies, speech_api  # noqa: E402
from writing_coach.persistence.models import AuditLog, Base, PlatformSetting, User  # noqa: E402
from writing_coach.persistence.platform_repository import PostgresPlatformRepository, SettingConflict  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def save(change, store, **kw):
    return policies.save(change, updated_by="admin@x.test", actor="admin-sub", **kw)


# ======================================================================================================= 1. registry ==

def test_every_policy_is_typed_ranged_and_its_default_is_inside_its_range():
    assert len({item.key for item in policies.POLICIES}) == len(policies.POLICIES)
    for item in policies.POLICIES:
        assert item.group in policies.GROUPS and item.kind in {"int", "float", "bool", "enum"}, item.key
        if item.kind in {"int", "float"}:
            assert item.low is not None and item.high is not None and item.low < item.high, item.key
            if item.default is not None:
                assert item.low <= item.default <= item.high, f"{item.key}: the default must be a value the editor accepts"
                assert policies.check(item, item.default) == item.default
            else:
                assert item.nullable, f"{item.key}: only a nullable policy defaults to nothing"
        if item.kind == "enum":
            assert item.default in item.choices, item.key
        if item.danger:
            assert item.danger in {"delete", "charging"}, item.key
        if item.danger == "delete" and item.key.endswith("_days"):
            # a retention period can only be shortened below what the published legal text states
            assert item.high == item.default, f"{item.key}: Admin may shorten retention, never lengthen it"
    assert set(policies.GROUPS) == {item.group for item in policies.POLICIES} | {"quota"}


def test_the_defaults_are_the_values_the_code_carried_before():
    """The numbers below are the constants that used to be written in the modules; none of them may drift."""
    from writing_coach import feedback, speech_api
    from writing_coach.agent import limits as agent_limits
    from writing_coach.agent import retention as agent_retention
    from writing_coach.agent import voice_session
    from writing_coach.ai import account_costs
    from writing_coach.core import http_security
    from writing_coach.product import quota
    from writing_coach.word_audio_azure import DEFAULT_CAP_USD

    base = agent_limits.DEFAULT_LIMITS
    for name in agent_limits.OPERATOR_FIELDS:
        assert policies.default(f"agent.{name}") == getattr(base, name), name
    assert tuple(agent_limits.OPERATOR_FIELDS) == tuple(policies.AGENT_LIMIT_FIELDS)
    assert policies.default("voice.session_cap_seconds") == voice_session.SESSION_SECONDS == 900
    assert policies.default("voice.chunk_units") == voice_session.VOICE_CHUNK_UNITS == 2
    assert "voice.enabled" not in policies.BY_KEY, "paid live voice is the human's activation gate: environment only"
    assert policies.default("voice.resumption") is True
    assert policies.default("speech.take_max_seconds") == speech_api.TRANSCRIBE_MAX_SECONDS == 300
    assert policies.default("speech.asr_daily_seconds") == speech_api.TRANSCRIBE_DAILY_SECONDS == 3600
    assert policies.default("speech.pronunciation_max_concurrent") == speech_api.DEFAULT_PRONUNCIATION_WORKERS == 8
    assert policies.default("speech.no_speech_charged") is speech_api.NO_SPEECH_CHARGED is True
    assert policies.default("feedback.daily_limit") == feedback.DAILY_LIMIT == 10
    assert policies.default("feedback.retention_days") == feedback.FEEDBACK_RETENTION_DAYS == 730
    assert policies.default("agent.turn_retention_days") == agent_retention.TURN_RETENTION_DAYS == 90
    assert policies.default("ai_costs.retention_days") == account_costs.RETENTION_DAYS == 396
    assert policies.default("feedback.retention_sweep") is False and policies.default("agent.turn_retention_sweep") is False
    assert policies.default("quota.abandoned_settles") == quota.ABANDONED_SETTLES == "admitted"
    assert policies.default("word_tts.spend_cap_usd") == DEFAULT_CAP_USD == 5.0
    assert policies.default("agent.daily_spend_cap_usd") is None, "no cap unless one is set"
    assert (policies.default("media.batch_cap_asr_usd"), policies.default("media.batch_cap_ai_usd"),
            policies.default("media.daily_cap_usd")) == (5.0, 10.0, 25.0)
    assert (policies.default("media.asr_usd_per_hour"), policies.default("media.ai_usd_per_million_tokens")) == (0.04, 1.0)
    assert policies.default("media.asr_max_seconds") == 5400 and policies.default("media.model_clips_enabled") is True
    assert policies.default("media.model_clip_max_lines") == 500
    for group, key in http_security.RATE_POLICY_KEYS.items():
        table = {name: limit for name, _prefixes, limit, _window in http_security.RATE_GROUPS}
        assert policies.default(key) == table[group], group


def test_an_empty_or_missing_document_is_the_defaults():
    for store in (MemoryPolicyStore(), MemoryPolicyStore({})):
        with installed(store):
            view = policies.snapshot()
            assert view["source"] == ("default" if not store.rows else "stored")
            for row in view["policies"]:
                assert row["source"] == "default" and row["value"] == row["default"] and not row["locked"], row["key"]
                assert policies.value(row["key"]) == row["default"]
    with installed():  # no store at all (a process whose persistence runtime has none)
        policies.configure(None, env={})
        assert policies.effective() == {item.key: item.default for item in policies.POLICIES}


# =================================================================================================== 2. precedence ==

def test_environment_beats_admin_beats_default():
    with installed(MemoryPolicyStore({"speech.asr_daily_seconds": 7200})) as store:
        assert policies.value("speech.asr_daily_seconds") == 7200, "Admin over the default"
        assert policies.value("speech.asr_daily_seconds", env={"SPEECH_ASR_DAILY_SECONDS": "1800"}) == 1800, "env over Admin"
        assert policies.value("speech.asr_daily_seconds", env={"SPEECH_ASR_DAILY_SECONDS": ""}) == 7200, "empty = not set"
        assert policies.value("speech.take_max_seconds") == 300, "nothing set: the default"
        assert store.reads >= 1


def test_the_snapshot_says_where_each_value_comes_from_and_which_are_locked():
    env = {"MEDIA_DAILY_CAP_USD": "40", "AGENT_VOICE_RESUMPTION": "false"}
    with installed(MemoryPolicyStore({"media.daily_cap_usd": 99.0, "feedback.daily_limit": 3}), env=env):
        rows = {row["key"]: row for row in policies.snapshot()["policies"]}
        assert (rows["media.daily_cap_usd"]["source"], rows["media.daily_cap_usd"]["value"]) == ("env", 40.0)
        assert rows["media.daily_cap_usd"]["locked"] and rows["media.daily_cap_usd"]["env"] == "MEDIA_DAILY_CAP_USD"
        assert rows["media.daily_cap_usd"]["admin"] == 99.0, "what Admin chose is still shown beneath the pin"
        assert (rows["voice.resumption"]["source"], rows["voice.resumption"]["value"]) == ("env", False)
        assert (rows["feedback.daily_limit"]["source"], rows["feedback.daily_limit"]["value"]) == ("admin", 3)
        assert rows["feedback.daily_limit"]["has_admin"] and not rows["feedback.daily_limit"]["locked"]
        assert (rows["speech.take_max_seconds"]["source"], rows["speech.take_max_seconds"]["value"]) == ("default", 300)


@pytest.mark.parametrize("key, env, expected", [
    ("voice.resumption", {"AGENT_VOICE_RESUMPTION": "false"}, False),
    ("voice.resumption", {"AGENT_VOICE_RESUMPTION": "garbage"}, True),     # the old reading: only an off value turns it off
    ("media.model_clips_enabled", {"MEDIA_MODEL_CLIPS": "0"}, False),
    ("media.asr_max_seconds", {"MEDIA_ASR_MAX_SECONDS": "17"}, 17),
    ("media.asr_max_seconds", {"MEDIA_ASR_MAX_SECONDS": "0"}, 5400),       # not positive: the default, as before
    ("media.asr_max_seconds", {"MEDIA_ASR_MAX_SECONDS": "abc"}, 5400),
    ("media.batch_cap_asr_usd", {"MEDIA_ASR_BATCH_CAP_USD": "-1"}, 5.0),   # negative: the default, as before
    ("media.batch_cap_asr_usd", {"MEDIA_ASR_BATCH_CAP_USD": "0"}, 0.0),    # zero is a cap
    ("agent.daily_spend_cap_usd", {"AGENT_DAILY_SPEND_CAP_USD": "1"}, 1.0),
    ("agent.daily_spend_cap_usd", {}, None),
    ("speech.pronunciation_max_concurrent", {"PRONUNCIATION_MAX_CONCURRENT": "3"}, 3),
    ("feedback.retention_sweep", {"FEEDBACK_RETENTION_SWEEP": "yes"}, True),
    ("agent.turn_retention_sweep", {"AGENT_TURN_RETENTION_SWEEP": "no"}, False),
    ("word_tts.spend_cap_usd", {"WORD_TTS_SPEND_CAP_USD": "12.5"}, 12.5),
])
def test_an_environment_variable_reads_as_it_always_did(key, env, expected):
    with installed(MemoryPolicyStore()):
        assert policies.value(key, env=env) == expected


def test_the_editor_refuses_a_policy_the_environment_pins():
    with installed(MemoryPolicyStore(), env={"MEDIA_DAILY_CAP_USD": "40"}) as store:
        with pytest.raises(policies.PolicyInvalid, match="locked by the environment"):
            save({"set": {"media.daily_cap_usd": 60}}, store)
        assert store.rows == {}, "nothing was written"
        save({"set": {"feedback.daily_limit": 4}}, store)  # the unpinned ones stay editable


# ======================================================================================================== 3. saving ==

@pytest.mark.parametrize("change, message", [
    ({"set": {"no.such.policy": 1}}, "Unknown policy"),
    ({"reset": ["no.such.policy"]}, "Unknown policy"),
    ({"set": {"feedback.daily_limit": "5"}}, "must be a number"),
    ({"set": {"feedback.daily_limit": True}}, "must be a number"),
    ({"set": {"feedback.daily_limit": 2.5}}, "whole number"),
    ({"set": {"feedback.daily_limit": 0}}, "between"),
    ({"set": {"feedback.daily_limit": 101}}, "between"),
    ({"set": {"feedback.daily_limit": None}}, "needs a value"),
    ({"set": {"voice.enabled": True}}, "Unknown policy"),                  # not a policy: environment only
    ({"set": {"media.asr_usd_per_hour": 0}}, "between"),                   # a free estimate would disable the caps
    ({"set": {"media.ai_usd_per_million_tokens": 0}}, "between"),
    ({"set": {"feedback.retention_days": 731}}, "between"),                # never longer than the published 24 months
    ({"set": {"agent.turn_retention_days": 91}}, "between"),
    ({"set": {"ai_costs.retention_days": 397}}, "between"),
    ({"set": {"quota.abandoned_settles": "free"}}, "one of"),
    ({"set": {"media.daily_cap_usd": float("inf")}}, "must be a number"),
    ({"set": {"agent.daily_spend_cap_usd": 0}}, "between"),
    ({"set": []}, "`set` must be an object"),
    ({"reset": {"a": 1}}, "`reset` a list"),
    ({"values": {"feedback.daily_limit": 5}}, "Unknown field"),
    ([], "must be an object"),
])
def test_a_save_rejects_unknown_keys_wrong_types_and_out_of_range_values(change, message):
    with installed(MemoryPolicyStore()) as store:
        with pytest.raises(policies.PolicyInvalid, match=message):
            save(change, store)
        assert store.rows == {} and store.audits == [], "a refused change writes nothing and audits nothing"


def test_a_save_stores_only_what_was_chosen_and_a_reset_returns_to_the_default():
    with installed(MemoryPolicyStore()) as store:
        view = save({"set": {"feedback.daily_limit": 4, "agent.daily_spend_cap_usd": 2.5}, "expected_updated_at": None}, store)
        row = store.rows[policies.SETTING_KEY]
        assert row["value"] == {"version": 1, "values": {"agent.daily_spend_cap_usd": 2.5, "feedback.daily_limit": 4}}
        assert row["updated_by"] == "admin@x.test"
        assert view["updated_by"] == "admin@x.test" and view["source"] == "stored" and view["updated_at"]
        by_key = {item["key"]: item for item in view["policies"]}
        assert by_key["feedback.daily_limit"]["source"] == "admin" and by_key["speech.take_max_seconds"]["source"] == "default"
        view = save({"reset": ["feedback.daily_limit"], "expected_updated_at": row["updated_at"]}, store)
        assert store.rows[policies.SETTING_KEY]["value"]["values"] == {"agent.daily_spend_cap_usd": 2.5}
        assert {item["key"]: item for item in view["policies"]}["feedback.daily_limit"]["value"] == 10


def test_a_change_applies_at_once_in_the_process_that_saved_it():
    with installed(MemoryPolicyStore()) as store:
        assert policies.value("feedback.daily_limit") == 10  # read and cached
        save({"set": {"feedback.daily_limit": 2}}, store)
        assert policies.value("feedback.daily_limit") == 2, "no five-second wait in the worker that saved"


def test_another_worker_sees_a_change_within_the_cache_window(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(policies.time, "monotonic", lambda: clock[0])
    store = MemoryPolicyStore()
    with installed(store):
        assert policies.value("feedback.daily_limit") == 10
        store.set_setting(policies.SETTING_KEY, {"version": 1, "values": {"feedback.daily_limit": 6}})  # another worker
        assert policies.value("feedback.daily_limit") == 10, "still inside the cache window"
        clock[0] += policies.CACHE_SECONDS + 0.1
        assert policies.value("feedback.daily_limit") == 6, "and after it"


def test_a_stale_save_is_a_conflict_and_changes_nothing():
    with installed(MemoryPolicyStore()) as store:
        first = save({"set": {"feedback.daily_limit": 4}, "expected_updated_at": None}, store)
        loaded = first["updated_at"]
        save({"set": {"feedback.daily_limit": 5}, "expected_updated_at": loaded}, store)  # someone else saves
        with pytest.raises(SettingConflict):
            save({"set": {"feedback.daily_limit": 6}, "expected_updated_at": loaded}, store)
        assert store.rows[policies.SETTING_KEY]["value"]["values"]["feedback.daily_limit"] == 5
        assert len(store.audits) == 2, "the refused save left no audit row"
        with pytest.raises(SettingConflict):  # "nothing stored yet" is also a version
            save({"set": {"feedback.daily_limit": 7}, "expected_updated_at": None}, store)


def test_the_audit_row_commits_in_the_same_transaction_as_the_change(tmp_path, monkeypatch):
    """The real platform repository on a SQLAlchemy engine: the row and its audit are one commit."""
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'p.db'}", future=True)
    Base.metadata.create_all(engine, tables=[User.__table__, AuditLog.__table__, PlatformSetting.__table__])
    repository = PostgresPlatformRepository(engine=engine)
    with installed(repository):
        save({"set": {"feedback.daily_limit": 4, "speech.take_max_seconds": 120}, "expected_updated_at": None}, repository)
        with Session(engine) as session:
            rows = session.query(AuditLog).filter(AuditLog.action == "platform.policies.update").all()
            assert len(rows) == 1 and rows[0].entity_id == policies.SETTING_KEY
            payload = rows[0].payload
            assert payload["changes"]["feedback.daily_limit"] == {"from": 10, "to": 4, "reset": False}
            assert payload["changes"]["speech.take_max_seconds"]["to"] == 120
            assert payload["actor"] == "admin-sub" and payload["confirmed"] == []
        with pytest.raises(SettingConflict):
            save({"set": {"feedback.daily_limit": 9}, "expected_updated_at": None}, repository)
        from writing_coach.persistence import platform_repository as platform

        def broken(session, audit, now):
            raise RuntimeError("audit store down")

        monkeypatch.setattr(platform, "_add_audit", broken)
        with pytest.raises(RuntimeError):
            save({"set": {"feedback.daily_limit": 8}}, repository)
        assert repository.get_setting(policies.SETTING_KEY)["value"]["values"]["feedback.daily_limit"] == 4, "no unaudited change"
        with Session(engine) as session:
            assert session.query(AuditLog).filter(AuditLog.action == "platform.policies.update").count() == 1


@pytest.mark.parametrize("change, keys", [
    ({"set": {"feedback.retention_sweep": True}}, ["feedback.retention_sweep"]),
    ({"set": {"agent.turn_retention_sweep": True}}, ["agent.turn_retention_sweep"]),
    ({"set": {"feedback.retention_days": 365}}, ["feedback.retention_days"]),
    ({"set": {"quota.abandoned_settles": "zero"}}, ["quota.abandoned_settles"]),   # charging rules the human decided
    ({"set": {"speech.no_speech_charged": False}}, ["speech.no_speech_charged"]),
    ({"set": {"voice.chunk_units": 5}}, ["voice.chunk_units"]),
    ({"set": {"ai_costs.retention_days": 120}}, ["ai_costs.retention_days"]),
    ({"set": {"media.daily_cap_usd": 500}}, ["media.daily_cap_usd"]),          # past its sane maximum (250)
    ({"set": {"word_tts.spend_cap_usd": 60}}, ["word_tts.spend_cap_usd"]),
    ({"set": {"agent.daily_spend_cap_usd": 51}}, ["agent.daily_spend_cap_usd"]),
    ({"set": {"feedback.retention_sweep": True, "feedback.retention_days": 90}}, ["feedback.retention_days", "feedback.retention_sweep"]),
])
def test_a_dangerous_change_needs_an_explicit_confirmation_and_the_audit_records_it(change, keys):
    with installed(MemoryPolicyStore()) as store:
        with pytest.raises(policies.PolicyConfirmationRequired) as refused:
            save(dict(change), store)
        assert refused.value.keys == keys and store.rows == {}, "nothing is saved until it is confirmed"
        with pytest.raises(policies.PolicyConfirmationRequired):  # a confirmation that is not a literal true does not count
            save({**change, "confirm": {key: "yes" for key in keys}}, store)
        save({**change, "confirm": {key: True for key in keys}}, store)
        assert store.audits[-1]["payload"]["confirmed"] == keys


def test_a_change_that_is_not_dangerous_needs_no_confirmation():
    with installed(MemoryPolicyStore()) as store:
        save({"set": {"media.daily_cap_usd": 100, "agent.daily_spend_cap_usd": 5, "feedback.retention_sweep": False,
                      "feedback.retention_days": 730}}, store)  # lower caps, the default period, a switch left off
        # Removing a cap altogether is past any maximum, and so is putting it back to nothing:
        with pytest.raises(policies.PolicyConfirmationRequired) as refused:
            save({"set": {"agent.daily_spend_cap_usd": None}}, store)
        assert refused.value.keys == ["agent.daily_spend_cap_usd"]
        save({"reset": ["agent.daily_spend_cap_usd"], "confirm": {"agent.daily_spend_cap_usd": True}}, store)
        assert "agent.daily_spend_cap_usd" not in store.rows[policies.SETTING_KEY]["value"]["values"]


def test_turning_a_deleting_switch_back_off_is_a_change_that_is_confirmed_too():
    with installed(MemoryPolicyStore({"feedback.retention_sweep": True})) as store:
        with pytest.raises(policies.PolicyConfirmationRequired):
            save({"set": {"feedback.retention_sweep": False}}, store)
        with pytest.raises(policies.PolicyConfirmationRequired):
            save({"reset": ["feedback.retention_sweep"]}, store)


def test_saving_what_is_already_stored_writes_nothing():
    with installed(MemoryPolicyStore({"feedback.daily_limit": 4})) as store:
        stamp = store.rows[policies.SETTING_KEY]["updated_at"]
        save({"set": {"feedback.daily_limit": 4}}, store)
        assert store.rows[policies.SETTING_KEY]["updated_at"] == stamp and store.audits == []


# ============================================================================================ 4. fail-safe reads ==

def test_an_unreadable_store_never_raises_into_a_request_and_is_logged(caplog):
    store = MemoryPolicyStore(fail_reads=True)
    with installed(store):
        with caplog.at_level(logging.WARNING, logger="writing_coach.policies"):
            assert policies.value("feedback.daily_limit") == 10, "never read: the defaults"
            assert policies.effective()["media.daily_cap_usd"] == 25.0
        assert "unreadable" in caplog.text
        assert policies.snapshot()["state"] == "unreadable"


def test_an_unreadable_store_keeps_what_this_process_last_read(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(policies.time, "monotonic", lambda: clock[0])
    store = MemoryPolicyStore({"agent.daily_spend_cap_usd": 1.0})
    with installed(store):
        assert policies.value("agent.daily_spend_cap_usd") == 1.0
        store.fail_reads = True
        clock[0] += policies.CACHE_SECONDS + 1
        assert policies.value("agent.daily_spend_cap_usd") == 1.0, "a blip must not lift the spend cap back to none"
        assert policies.snapshot()["state"] == "stale"
        store.fail_reads = False
        clock[0] += policies.CACHE_SECONDS + 1
        assert policies.snapshot()["state"] == "stored"


def test_a_failed_read_is_not_asked_again_on_every_request():
    store = MemoryPolicyStore(fail_reads=True)
    with installed(store):
        for _ in range(50):
            policies.value("feedback.daily_limit")
        assert store.reads == 1, "a down store is asked once per cache window, not once per request"


def test_a_stored_value_that_is_not_valid_now_is_ignored_not_half_applied(caplog):
    """A newer build may have stored a key this one does not know, or a range may have narrowed."""
    store = MemoryPolicyStore({"feedback.daily_limit": 999, "from.the.future": 1, "speech.take_max_seconds": 120})
    with installed(store), caplog.at_level(logging.WARNING, logger="writing_coach.policies"):
        assert policies.value("feedback.daily_limit") == 10, "out of range: the default"
        assert policies.value("speech.take_max_seconds") == 120, "the valid ones still apply"
        assert "from.the.future" in caplog.text


def test_a_garbled_document_is_the_defaults():
    store = MemoryPolicyStore()
    store.rows[policies.SETTING_KEY] = {"value": ["not", "a", "document"], "updated_at": "x", "updated_by": "y"}
    with installed(store):
        assert policies.effective() == {item.key: item.default for item in policies.POLICIES}


def test_the_quota_switch_keeps_its_own_fail_closed_rule_when_the_policies_are_unreadable():
    """The switch is not a policy of this document (D-161): a policies store that is down changes nothing about it."""
    from test_quota_gate import FakeIncarnations, FakeQuotaRepository, MemorySettings

    from writing_coach.product import catalog, quota

    previous = quota.runtime()
    try:
        quota.configure_quota(repository=FakeQuotaRepository(), incarnations=FakeIncarnations(),
                              plan_for=lambda *a, **k: catalog.FREE, settings=MemorySettings(fail=True), env={})
        with installed(MemoryPolicyStore(fail_reads=True)):
            state = quota.switch()
            assert state["state"] == "unavailable" and state["reason"] == "switch_unreadable", "still fails closed"
    finally:
        quota.configure_quota(**{f: getattr(previous, f) for f in
                                 ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})


# ================================================================================================ 5. the consumers ==

def test_agent_limits_are_read_when_a_turn_is_judged_not_when_the_process_started():
    from writing_coach.agent.limits import DEFAULT_LIMITS, LiveAgentLimits
    from writing_coach.agent.ratelimit import SlidingWindowLimiter

    live = LiveAgentLimits(DEFAULT_LIMITS, policies.effective_agent_limits)
    with installed(MemoryPolicyStore()) as store:
        for name in ("turns_per_window", "rate_window_seconds", "max_input_tokens_per_turn", "opening_max_output_tokens",
                     "max_tool_iterations_per_turn", "max_history_chars", "session_ttl_seconds"):
            assert getattr(live, name) == getattr(DEFAULT_LIMITS, name), f"{name}: an empty document changes nothing"
        turns = SlidingWindowLimiter(lambda: live.turns_per_window, lambda: live.rate_window_seconds)
        assert [turns.check("a") for _ in range(12)] == [None] * 12 and turns.check("a") is not None
        save({"set": {"agent.turns_per_window": 2, "agent.max_input_tokens_per_turn": 9000,
                      "agent.opening_max_output_tokens": 80, "agent.rate_window_seconds": 30}}, store)
        assert (live.turns_per_window, live.max_input_tokens_per_turn, live.opening_max_output_tokens) == (2, 9000, 80)
        assert live.max_tool_iterations_per_turn == 4, "a safety bound is not an operator policy and stays the code's"
        assert turns.limit == 2 and turns.window_seconds == 30
        fresh = SlidingWindowLimiter(lambda: live.turns_per_window, lambda: live.rate_window_seconds)
        assert [fresh.check("b") for _ in range(2)] == [None, None] and fresh.check("b") is not None


def test_the_agent_runtime_builds_its_limiters_on_the_live_limits():
    from writing_coach.agent.capability_registry import load_capability_registry
    from writing_coach.agent.fake_provider import FakeAgentTurnProvider
    from writing_coach.agent.limits import DEFAULT_LIMITS, LiveAgentLimits
    from writing_coach.agent.runtime import AppReads, build_tool_registry
    from writing_coach.agent.session import SessionCache
    from writing_coach.agent.turn import AgentRuntime

    live = LiveAgentLimits(DEFAULT_LIMITS, policies.effective_agent_limits)
    tools = build_tool_registry(writing_review=lambda i: None, reads=AppReads())
    runtime = AgentRuntime(provider=FakeAgentTurnProvider([]), tools=tools, sessions=SessionCache(), limits=live,
                           capabilities=load_capability_registry(registered_tools=tools.names()))
    with installed(MemoryPolicyStore()) as store:
        assert (runtime.turn_limiter.limit, runtime.read_limiter.limit, runtime.opening_limiter.limit) == (12, 60, 1)
        save({"set": {"agent.turns_per_window": 3, "agent.capability_reads_per_window": 7,
                      "agent.model_openings_per_window": 2}}, store)
        assert (runtime.turn_limiter.limit, runtime.read_limiter.limit, runtime.opening_limiter.limit) == (3, 7, 2)
        assert [runtime.turn_limiter.check("learner") for _ in range(3)] == [None] * 3
        assert runtime.turn_limiter.check("learner") is not None


def test_the_daily_spend_cap_follows_the_policy_and_no_cap_allows_every_turn():
    from writing_coach.agent.budget import LiveSpendGuard

    spent = {"usd": 0.0}
    guard = LiveSpendGuard(lambda: policies.value("agent.daily_spend_cap_usd"), lambda since: (spent["usd"], 0))
    with installed(MemoryPolicyStore()) as store:
        spent["usd"] = 1000.0
        assert guard() is None, "no cap: a turn may run, exactly as when no guard was built"
        save({"set": {"agent.daily_spend_cap_usd": 5.0}}, store)
        assert guard() is not None and guard() > 0, "over the cap now: refused until the next UTC midnight"
        save({"set": {"agent.daily_spend_cap_usd": 5000.0}, "confirm": {"agent.daily_spend_cap_usd": True}}, store)
        assert guard() is None, "a raised cap is read at the next turn, not cached for the old number"
    with installed(MemoryPolicyStore(), env={"AGENT_DAILY_SPEND_CAP_USD": "1"}):
        assert guard() is not None, "the environment pin is the cap, whatever Admin says"
    assert LiveSpendGuard(lambda: 5.0, None)() == 3600.0, "a cap with no ledger to read refuses (fails closed)"


def test_voice_is_switched_and_shaped_by_the_policies_at_the_moment_of_use():
    from writing_coach.agent.voice_session import SESSION_SECONDS, VOICE_CHUNK_UNITS, VoiceService

    bare = VoiceService(runtime=None, tokens=None)
    assert (bare.is_enabled(), bare._session_seconds(), bare._chunk_units(), bare._resumes()) == (
        True, SESSION_SECONDS, VOICE_CHUNK_UNITS, True), "a service built without policies keeps the constants"
    service = VoiceService(runtime=None, tokens=None, policy=policies.value)
    with installed(MemoryPolicyStore()) as store:
        assert (service._session_seconds(), service._chunk_units(), service._resumes()) == (900, 2, True)
        save({"set": {"voice.session_cap_seconds": 300, "voice.chunk_units": 1, "voice.resumption": False},
              "confirm": {"voice.chunk_units": True}}, store)
        assert (service._session_seconds(), service._chunk_units(), service._resumes()) == (300, 1, False)


def test_switching_voice_off_stops_new_sessions_but_not_the_ones_in_flight():
    from test_quota_orena_message import Rig
    from test_agent_voice_session import Post, _body, _service, Clock

    state = {"on": True}
    billed = []
    clock = Clock()
    service = _service(Post(), clock=clock, billed=billed)
    service.enabled = lambda: state["on"]
    rig = Rig([], voice=service)
    headers = {"x-test-user": "learner-1"}
    opened = rig.client.post("/api/agent/voice/session", json=_body(target="en"), headers=headers)
    assert opened.status_code == 200
    state["on"] = False
    assert rig.client.post("/api/agent/voice/session", json=_body(target="en"), headers=headers).status_code == 404, \
        "off: a new session is refused"
    assert rig.client.get("/api/agent/voice/voices", headers=headers).status_code == 404, "and so is the voice list"
    clock.t += 30
    ended = rig.client.post("/api/agent/voice/end", json={"voice_session_id": opened.json()["voice_session_id"]},
                            headers=headers)
    assert ended.status_code == 200, "a session already open can still be ended, so its time reaches the ledger"
    assert [k["audio_seconds"] for _, k in billed] == [30.0]


def test_an_unmetered_session_is_billed_for_at_most_the_seconds_it_was_minted_for():
    from writing_coach.agent.voice_session import VoiceService, VoiceSession

    seen = []
    service = VoiceService(runtime=None, tokens=None, policy=policies.value,
                           record_audio=lambda *a, **k: seen.append(k["audio_seconds"]))
    class Sessions:
        clock = staticmethod(lambda: 2000.0)
    service.sessions = Sessions()
    session = VoiceSession.__new__(VoiceSession)
    session.opened, session.minted_seconds, session.model = 0.0, 900, "m"
    with installed(MemoryPolicyStore({"voice.session_cap_seconds": 60})):  # lowered after the token was minted
        assert service._bill(session) == 900.0 and seen == [900.0], "billed at the old grant, not the new cap"


def test_a_metered_voice_session_uses_the_policy_cap_and_chunk_size():
    import test_quota_voice as voice_suite

    voice_suite.enforced_runtime(env=voice_suite.ENV)
    voice = voice_suite.Voice()
    voice.service.policy = policies.value
    with installed(MemoryPolicyStore()) as store:
        body = voice.open().json()
        assert (body["max_seconds"], body["session_max_seconds"]) == (120, 900), "an empty document: D-169 exactly"
        save({"set": {"voice.session_cap_seconds": 600, "voice.chunk_units": 5}, "confirm": {"voice.chunk_units": True}}, store)
        other = voice_suite.Voice()
        other.service.policy = policies.value
        answer = other.open(user="learner-2").json()
        assert answer["session_max_seconds"] == 600
        assert answer["max_seconds"] == 300, "five messages of voice (5 x 60 s) are one chunk"


@needs_ffmpeg
def test_the_speech_take_cap_and_daily_seconds_follow_the_policies(room):  # noqa: F811 - the imported fixture
    provider, send = room
    with installed(MemoryPolicyStore()) as store:
        assert send(silent_wav(200)).status_code == 200, "an empty document keeps the five-minute take"
        speech_api.reset_transcribe_brake()
        save({"set": {"speech.take_max_seconds": 30, "speech.asr_daily_seconds": 60}}, store)
        too_long = send(silent_wav(45))
        assert too_long.status_code == 413 and "30 seconds" in too_long.json()["detail"]["message"]
        assert send(silent_wav(25)).status_code == 200 and send(silent_wav(25), user="learner-3").status_code == 200
        assert send(silent_wav(25)).status_code == 200  # 50 s of this account's 60 s
        third = send(silent_wav(25))
        assert third.status_code == 429 and third.json()["detail"]["category"] == "speech_asr_daily_limit"
        save({"set": {"speech.asr_daily_seconds": 3600}}, store)
        assert send(silent_wav(25)).status_code == 200, "a raised ceiling applies to the next take"


def test_pronunciation_concurrency_and_the_silent_take_charge_follow_the_policies():
    import asyncio

    from writing_coach.speech_pronunciation import SpeechPronunciationNoSpeech

    async def limiter_sizes():
        with installed(MemoryPolicyStore()):
            first = speech_api._pronunciation_limiter().total_tokens
        with installed(MemoryPolicyStore({"speech.pronunciation_max_concurrent": 3})):
            second = speech_api._pronunciation_limiter().total_tokens
        return first, second

    first, second = asyncio.run(limiter_sizes())
    assert (first, second) == (8, 3), "the same loop's limiter is resized, not replaced"
    error = SpeechPronunciationNoSpeech()
    error.billed_seconds = 3.2
    with installed(MemoryPolicyStore()):
        assert speech_api._charged_units(error, 4, None) == 4, "the beta decision: processed seconds are charged"
    with installed(MemoryPolicyStore({"speech.no_speech_charged": False})):
        assert speech_api._charged_units(error, 4, None) == 0


def test_media_import_limits_and_spend_caps_follow_the_policies(tmp_path):
    from writing_coach.media_spend import KIND_ASR, SpendCapReached, SpendLedger
    from writing_coach.media_transcript_pipeline import max_asr_seconds

    ledger = SpendLedger(tmp_path / "spend.json")
    with installed(MemoryPolicyStore()) as store:
        assert max_asr_seconds() == 5400
        assert ledger.limits() == {"asr": 5.0, "ai": 10.0, "day": 25.0}
        assert ledger.asr_usd_per_hour() == 0.04 and ledger.ai_usd_per_million_tokens() == 1.0
        save({"set": {"media.asr_max_seconds": 600, "media.batch_cap_asr_usd": 0.5, "media.daily_cap_usd": 2,
                      "media.asr_usd_per_hour": 0.36}}, store)
        assert max_asr_seconds() == 600
        assert ledger.limits() == {"asr": 0.5, "ai": 10.0, "day": 2.0}
        ledger.check(KIND_ASR, "batch-1", 0.4)
        with pytest.raises(SpendCapReached) as reached:
            ledger.check(KIND_ASR, "batch-1", 0.6)
        assert reached.value.limit == 0.5
        assert ledger.asr_estimate(3600) == pytest.approx(0.36)
    with installed(MemoryPolicyStore({"media.batch_cap_asr_usd": 0.5}), env={"MEDIA_ASR_BATCH_CAP_USD": "9"}):
        assert ledger.limits()["asr"] == 9.0, "the environment still pins the cap"
    # An explicit environment mapping given to the ledger (its old constructor argument) is the pin as before.
    pinned = SpendLedger(tmp_path / "spend2.json", env={"MEDIA_DAILY_CAP_USD": "3"})
    with installed(MemoryPolicyStore({"media.daily_cap_usd": 99})):
        assert pinned.limits()["day"] == 3.0


def test_model_clip_switch_follows_the_policy(caplog):
    from writing_coach import media_transcript_pipeline as pipeline

    import types

    entry = types.SimpleNamespace(media_id="m-1")
    pipe = pipeline.MediaPipeline.__new__(pipeline.MediaPipeline)
    # An entry that cannot be prepared is logged by the (enabled) preparation and never reached when it is switched off.
    with installed(MemoryPolicyStore({"media.model_clips_enabled": False})):
        with caplog.at_level(logging.WARNING):
            assert pipe._prepare_model_clips(object(), entry) is None
        assert "model clips could not be prepared" not in caplog.text, "switched off: preparation never began"
    with installed(MemoryPolicyStore()):
        with caplog.at_level(logging.WARNING):
            pipe._prepare_model_clips(object(), entry)
        assert "model clips could not be prepared" in caplog.text, "on by default, as before"


def test_the_word_tts_lifetime_cap_follows_the_policy():
    from test_word_audio_azure import MP3, Wire

    from writing_coach.word_audio_azure import AzureVoice

    wire = Wire()
    azure = AzureVoice(key="k", region="eastasia", post=wire, spent=lambda: 7.0, record=lambda e: None)
    ask = {"term": "花生", "language": "zh", "reading": "huā shēng", "single_reading": True}
    with installed(MemoryPolicyStore()) as store:
        assert azure.speak(**ask) is None and azure.last_failed, "7 USD spent is past the default 5 USD"
        save({"set": {"word_tts.spend_cap_usd": 10}}, store)
        assert azure.speak(**ask).audio == MP3, "the cap is read at each synthesis"
    explicit = AzureVoice(key="k", region="eastasia", post=Wire(), spent=lambda: 7.0, record=lambda e: None, cap_usd=5)
    with installed(MemoryPolicyStore({"word_tts.spend_cap_usd": 100})):
        assert explicit.speak(**ask) is None, "a cap given to the constructor is the caller's decision"


def test_feedback_daily_limit_follows_the_policy():
    from writing_coach import feedback

    class Store:
        def __init__(self):
            self.sent = 0

        def count_feedback_since(self, user_key, since):
            return self.sent

        def record_feedback(self, user_key, review):
            self.sent += 1
            return {"id": self.sent}

    store = Store()
    body = {"stars": 5, "areas": [], "text": "good"}
    with installed(MemoryPolicyStore()) as backing:
        for _ in range(10):
            feedback.submit(store, "u", body)
        with pytest.raises(OverflowError):
            feedback.submit(store, "u", body)
        save({"set": {"feedback.daily_limit": 12}}, backing)
        feedback.submit(store, "u", body)
        save({"set": {"feedback.daily_limit": 1}}, backing)
        with pytest.raises(OverflowError):
            feedback.submit(store, "u", body)
        assert feedback.submit(Store(), "u", body, limit=3), "an explicit limit is still honoured"


def test_retention_switches_and_periods_follow_the_policies():
    from writing_coach.agent.retention import TurnTelemetryRetention
    from writing_coach.ai.account_costs import AccountCostRecorder

    noon = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
    cuts = []
    turn_sweep = TurnTelemetryRetention(
        lambda before, limit: cuts.append(before) or 0, now=lambda: noon, run=lambda work: work(),
        days=lambda: policies.value("agent.turn_retention_days"),
        enabled=lambda: policies.value("agent.turn_retention_sweep"))
    ran = []

    class Costs:
        def delete_ai_costs_before(self, before, limit):
            ran.append(before)
            return 0

    recorder = AccountCostRecorder(Costs(), now=lambda: noon, run=lambda work: work(),
                                   days=lambda: policies.value("ai_costs.retention_days"))
    with installed(MemoryPolicyStore()) as store:
        assert turn_sweep.maybe_sweep() is None and cuts == [], "the default is off: nothing is deleted, nothing claimed"
        recorder.maybe_sweep()
        assert ran == [noon - timedelta(days=396)], "the AI cost sweep has no switch; its period is the default"
        save({"set": {"agent.turn_retention_sweep": True, "agent.turn_retention_days": 30},
              "confirm": {"agent.turn_retention_sweep": True, "agent.turn_retention_days": True}}, store)
        assert turn_sweep.maybe_sweep() == 0
        assert cuts == [noon - timedelta(days=30)], "switched on and shortened in Admin, with no restart"
        save({"set": {"ai_costs.retention_days": 200}, "confirm": {"ai_costs.retention_days": True}}, store)
        later = AccountCostRecorder(Costs(), now=lambda: noon, run=lambda work: work(),
                                    days=lambda: policies.value("ai_costs.retention_days"))
        later.maybe_sweep()
        assert ran[-1] == noon - timedelta(days=200)


def test_request_rates_follow_the_policies():
    from writing_coach.core.http_security import RATE_GROUPS, rate_group

    with installed(MemoryPolicyStore()) as store:
        assert rate_group("POST", "/api/speech/transcribe") == ("speech_ai", 60, 600)
        assert rate_group("POST", "/api/evaluate") == ("writing_ai", 30, 600)
        assert rate_group("GET", "/api/evaluate") is None
        save({"set": {"rate.speech_ai_per_10min": 7, "rate.media_learning_per_hour": 3}}, store)
        assert rate_group("POST", "/api/speech/pronunciation") == ("speech_ai", 7, 600)
        assert rate_group("POST", "/api/media-learning/upload") == ("media_learning", 3, 3600)
        assert rate_group("POST", "/api/essays/1/review") == ("essay_ai", 30, 600)
    assert {name for name, *_ in RATE_GROUPS} >= {"writing_ai", "speech_ai", "media_learning"}


def test_the_abandoned_reservation_charge_follows_the_policy():
    from writing_coach.product import quota

    with installed(MemoryPolicyStore()) as store:
        assert quota.abandoned_settles() == "admitted"
        save({"set": {"quota.abandoned_settles": "zero"}, "confirm": {"quota.abandoned_settles": True}}, store)
        assert quota.abandoned_settles() == "zero"


def test_every_policy_has_a_consumer_in_the_code():
    """A policy nothing reads would be a switch on the Admin page that does nothing; a key is named where it is used."""
    sources = {path: path.read_text(encoding="utf-8", errors="ignore")
               for path in [*(ROOT / "writing_coach").rglob("*.py"), ROOT / "app.py"] if path.name != "policies.py"}
    joined = "\n".join(sources.values())
    for item in policies.POLICIES:
        named = f'"{item.key}"' in joined or f"'{item.key}'" in joined
        if item.key.startswith("agent.") and item.key.split(".", 1)[1] in policies.AGENT_LIMIT_FIELDS:
            named = True  # read through LiveAgentLimits / effective_agent_limits
        assert named, f"{item.key} is on the Admin page but nothing reads it"


# ======================================================================================================== 6. routes ==

@pytest.fixture()
def api(monkeypatch):
    import writing_coach.product.api as product_api

    monkeypatch.setattr(product_api, "require_admin", lambda request: {"google_sub": "admin-sub", "email": "a@x.test"})
    app = FastAPI()
    app.include_router(product_api.router)
    with installed(MemoryPolicyStore()) as store:
        yield TestClient(app), store


def test_the_policies_routes_read_save_conflict_and_confirm(api):
    client, store = api
    page = client.get("/api/product/admin/policies").json()
    assert page["source"] == "default" and page["updated_at"] is None
    assert {row["key"] for row in page["policies"]} == {item.key for item in policies.POLICIES}
    assert all(row["source"] == "default" for row in page["policies"])

    saved = client.put("/api/product/admin/policies",
                       json={"set": {"feedback.daily_limit": 4}, "expected_updated_at": None})
    assert saved.status_code == 200 and saved.json()["updated_by"] == "a@x.test"
    stamp = saved.json()["updated_at"]
    assert store.audits[-1]["action"] == "platform.policies.update" and store.audits[-1]["actor"] == "admin-sub"

    stale = client.put("/api/product/admin/policies", json={"set": {"feedback.daily_limit": 5}, "expected_updated_at": None})
    assert stale.status_code == 409, "the page was opened before someone saved"
    assert client.put("/api/product/admin/policies", json={"set": {"nope": 5}}).status_code == 422
    assert client.put("/api/product/admin/policies", content=b"not json").status_code == 400
    assert client.put("/api/product/admin/policies", json=[1]).status_code == 422

    needs = client.put("/api/product/admin/policies",
                       json={"set": {"feedback.retention_sweep": True}, "expected_updated_at": stamp})
    assert needs.status_code == 422
    detail = needs.json()["detail"]
    assert detail["code"] == "confirmation_required" and detail["keys"] == ["feedback.retention_sweep"]
    ok = client.put("/api/product/admin/policies", json={
        "set": {"feedback.retention_sweep": True}, "expected_updated_at": stamp, "confirm": {"feedback.retention_sweep": True}})
    assert ok.status_code == 200
    assert store.audits[-1]["payload"]["confirmed"] == ["feedback.retention_sweep"]


def test_the_quota_route_reports_who_and_when_and_takes_a_stale_check(api):
    from test_quota_gate import FakeIncarnations, FakeQuotaRepository

    from writing_coach.product import catalog, quota

    client, _ = api
    previous = quota.runtime()
    settings = MemoryPolicyStore()
    quota.configure_quota(repository=FakeQuotaRepository(), incarnations=FakeIncarnations(),
                          plan_for=lambda *a, **k: catalog.FREE, settings=settings, env={})
    try:
        before = client.get("/api/product/admin/quota").json()
        assert before["updated_at"] is None and before["updated_by"] is None and before["state"] == "off"
        done = client.put("/api/product/admin/quota",
                          json={"enabled": True, "meters": ["writing.review"], "expected_updated_at": None})
        assert done.status_code == 200 and done.json()["state"] == "enforced" and done.json()["updated_by"] == "a@x.test"
        assert done.json()["updated_at"]
        assert settings.rows[quota.SETTING_KEY]["value"] == {"enabled": True, "meters": ["writing.review"]}
        assert settings.audits[-1]["payload"] == {"enabled": True, "meters": ["writing.review"]}
        stale = client.put("/api/product/admin/quota",
                           json={"enabled": False, "meters": [], "expected_updated_at": None})
        assert stale.status_code == 409, "the page was opened before someone saved"
        assert client.get("/api/product/admin/quota").json()["state"] == "enforced", "the stale save changed nothing"
        # without the check the endpoint behaves exactly as before (D-161)
        assert client.put("/api/product/admin/quota", json={"enabled": False, "meters": []}).status_code == 200
    finally:
        quota.configure_quota(**{f: getattr(previous, f) for f in
                                 ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})


# ==================================================================================== review of b962e957 (P1, P3) ==

def test_the_spend_cap_read_is_strict_a_cold_worker_with_an_unreadable_store_refuses_turns(monkeypatch):
    """P1-1: "unknown" must never read as "no cap" for the one policy whose default is no cap."""
    from writing_coach.agent.budget import LiveSpendGuard

    clock = [1000.0]
    monkeypatch.setattr(policies.time, "monotonic", lambda: clock[0])
    store = MemoryPolicyStore({"agent.daily_spend_cap_usd": 1.0}, fail_reads=True)
    guard = LiveSpendGuard(lambda: policies.value_strict("agent.daily_spend_cap_usd"), lambda since: (0.0, 0))
    with installed(store):
        with pytest.raises(policies.PolicyUnavailable):
            policies.value_strict("agent.daily_spend_cap_usd")
        assert policies.value("agent.daily_spend_cap_usd") is None, "the lenient read still says the default"
        wait = guard()
        assert wait is not None and wait > 0, "a cold worker whose store is down refuses the turn (fails closed)"
        store.fail_reads = False
        clock[0] += policies.CACHE_SECONDS + 1
        assert policies.value_strict("agent.daily_spend_cap_usd") == 1.0
        assert guard() is None, "and carries on once the store answers (spend 0 of 1 USD)"
        store.fail_reads = True
        clock[0] += policies.CACHE_SECONDS + 1
        assert policies.value_strict("agent.daily_spend_cap_usd") == 1.0, "after one good read a blip keeps the cap"
    with installed(MemoryPolicyStore(fail_reads=True), env={"AGENT_DAILY_SPEND_CAP_USD": "2"}):
        assert policies.value_strict("agent.daily_spend_cap_usd") == 2.0, "an environment pin needs no store"


def test_a_stored_cap_that_no_longer_validates_refuses_turns_instead_of_lifting_the_cap():
    from writing_coach.agent.budget import LiveSpendGuard

    guard = LiveSpendGuard(lambda: policies.value_strict("agent.daily_spend_cap_usd"), lambda since: (0.0, 0))
    with installed(MemoryPolicyStore({"agent.daily_spend_cap_usd": 99999.0})):  # a later build tightened the range
        assert policies.value("agent.daily_spend_cap_usd") is None
        with pytest.raises(policies.PolicyUnavailable):
            policies.value_strict("agent.daily_spend_cap_usd")
        assert guard() is not None
    with installed():  # nothing stored, a working store: genuinely no cap
        assert policies.value_strict("agent.daily_spend_cap_usd") is None and guard() is None
    with installed():
        policies.configure(None, env={})  # no store at all (a process without persistence): the default applies
        assert policies.value_strict("agent.daily_spend_cap_usd") is None


def test_the_app_builds_the_spend_guard_on_the_strict_read():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '_policies.value_strict("agent.daily_spend_cap_usd")' in source


def test_a_save_without_the_loaded_version_is_still_a_compare_and_set():
    """P1-2: an omitted `expected_updated_at` must not let a merge overwrite a concurrent change."""
    class Racing(MemoryPolicyStore):
        """Another administrator commits between this save's read and its write."""
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.before_return = None

        def get_setting(self, key):
            row = super().get_setting(key)
            if self.before_return is not None:
                hook, self.before_return = self.before_return, None
                hook()
            return row

    store = Racing({"feedback.retention_sweep": True, "feedback.daily_limit": 5})
    with installed(store):
        store.before_return = lambda: store.set_setting(policies.SETTING_KEY, {"version": 1, "values": {
            "feedback.retention_sweep": False, "feedback.daily_limit": 5}}, updated_by="B")
        with pytest.raises(SettingConflict):
            save({"set": {"feedback.daily_limit": 6}}, store)  # no expected_updated_at: A read before B's commit
        assert store.rows[policies.SETTING_KEY]["value"]["values"]["feedback.retention_sweep"] is False, \
            "B's switch-off was not reverted"
        assert store.audits == [], "the refused save left no audit row"
        save({"set": {"feedback.daily_limit": 6}}, store)  # a fresh read goes through
        assert store.rows[policies.SETTING_KEY]["value"]["values"] == {"feedback.retention_sweep": False,
                                                                         "feedback.daily_limit": 6}
    with installed(Racing()) as empty:  # nothing stored yet: "None" is the version, so a first-save race is a conflict
        empty.before_return = lambda: empty.set_setting(policies.SETTING_KEY, {"version": 1, "values": {}}, updated_by="B")
        with pytest.raises(SettingConflict):
            save({"set": {"feedback.daily_limit": 6}}, empty)


def test_a_store_that_cannot_be_read_during_a_save_is_a_503_not_a_500(api):
    client, store = api
    store.fail_reads = True
    answer = client.put("/api/product/admin/policies", json={"set": {"feedback.daily_limit": 4}})
    assert answer.status_code == 503 and store.rows == {}
