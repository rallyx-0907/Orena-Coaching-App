"""D-16S review follow-ups (architecture review of 5ce3567e): the restart / deferred-settlement lifecycle in the way the
application really starts and runs, the reconciler's backstop respecting what an import decided, the paid routes left
open, and the smaller guards. Hermetic, on the harness of `tests/test_quota_media_import.py`.
"""
# Fixtures imported from the sibling module are used by name as arguments.
# ruff: noqa: F811
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from test_quota_media_import import (  # noqa: F401
    ENV,
    METER,
    FakeAsr,
    World,
    _isolated,  # autouse fixture
    media,
)

from test_quota_gate import enforced_runtime  # noqa: E402

from writing_coach import media_api, media_quota  # noqa: E402
from writing_coach.ai import platform as ai_platform  # noqa: E402
from writing_coach.ai.audio_telemetry import record_audio_operation  # noqa: E402
from writing_coach.ai.base import sanitize_telemetry  # noqa: E402
from writing_coach.product import quota  # noqa: E402
from writing_coach.speech_asr import SpeechAsrRequestFailed  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]




def idle(world: World, monkeypatch) -> None:
    """A process that queues the job and dies before it runs."""
    monkeypatch.setattr(world.pipeline, "_pool", type("Idle", (), {"submit": lambda *_a, **_k: None})())
    monkeypatch.delenv("MEDIA_PIPELINE_INLINE")


def unconfigured() -> None:
    """The moment of `app.py` before the quota runtime is wired: no store at all."""
    quota.configure_quota(repository=None, incarnations=None, plan_for=None, settings=None, env=ENV, reason="starting")


def never_sleep(monkeypatch) -> None:
    def refuse(_seconds):
        raise AssertionError("slept against a store that does not exist")

    monkeypatch.setattr(media_quota.time, "sleep", refuse)


def old(world: World, hours: float = 7) -> datetime:
    when = datetime.now(UTC) - timedelta(hours=hours)
    for row in world.repo.reservations.values():
        row["updated_at"] = when
    return datetime.now(UTC)


# ================================================================================================ P1-1 startup ==

def test_the_application_recovers_media_only_after_the_quota_runtime_is_configured():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    configured = source.index("_quota.configure_quota(")
    assert source.index("_media_pipeline.recover(") > configured, "recover() must not run before the quota runtime exists"
    assert source.index("_quota.configure_async_decision(") > configured
    assert source.count("_media_pipeline.recover(") == 1


def test_recover_waits_for_the_quota_store_and_then_takes_the_import_up(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    idle(world, monkeypatch)
    assert world.upload(media(120, 118.5)).status_code == 200
    (entry,) = world.entries()
    operation = entry.source[media_quota.SOURCE_OP]
    # A restart, at the point of app.py before the quota runtime is wired.
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    unconfigured()
    never_sleep(monkeypatch)
    assert world.new_pipeline().recover(world.store, world.assets) == 0, "nothing re-queued against no store"
    assert world.asr.calls == 0 and world.repo.settled == []
    assert world.store.get(entry.media_id).processing["state"] == "queued", "the import is not failed by the early start"
    # The runtime is configured; the same recover() now takes it up.
    enforced_runtime(repository=world.repo, env=ENV)
    assert world.new_pipeline().recover(world.store, world.assets) == 1
    assert world.repo.settled == [(operation, 119, "completed:generated_asr")]


def test_a_deferred_settlement_is_not_attempted_or_slept_on_before_the_store_exists(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    world.repo.fail_settle = 99
    monkeypatch.setattr(media_quota.time, "sleep", lambda _s: None)
    assert world.upload(media(60)).status_code == 200
    (entry,) = world.entries()
    assert media_quota.decode_intent(entry.source[media_quota.SOURCE_SETTLE]) == (60, "completed:generated_asr")
    unconfigured()
    never_sleep(monkeypatch)
    world.new_pipeline().recover(world.store, world.assets)
    assert world.new_pipeline().settle_pending(world.store) == 0
    assert media_quota.decode_intent(world.store.get(entry.media_id).source[media_quota.SOURCE_SETTLE]) is not None
    world.repo.fail_settle = 0
    enforced_runtime(repository=world.repo, env=ENV)
    world.new_pipeline().recover(world.store, world.assets)
    assert world.repo.settled == [(entry.source[media_quota.SOURCE_OP], 60, "completed:generated_asr")]


# ==================================================================================== P1-2 deferred settlements ==

def test_a_process_that_stays_up_writes_the_deferred_settlement_on_its_timer(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    world.asr.error = SpeechAsrRequestFailed(500)
    world.repo.fail_settle = 99
    monkeypatch.setattr(media_quota.time, "sleep", lambda _s: None)
    assert world.upload(media(60)).status_code == 200
    (entry,) = world.entries()
    operation = entry.source[media_quota.SOURCE_OP]
    assert media_quota.decode_intent(entry.source[media_quota.SOURCE_SETTLE]) == (0, "failed:asr_failed")
    assert world.bucket()["reserved"] == 60
    world.repo.fail_settle = 0  # the store is back; the process never restarted
    schedule = media_quota.IntentSchedule(lambda: world.pipeline.settle_pending(world.store), interval=3600)
    assert schedule.tick() == 1
    assert world.repo.settled == [(operation, 0, "failed:asr_failed")]
    assert (world.bucket()["consumed"], world.bucket()["reserved"]) == (0, 0)
    assert schedule.tick() == 0, "settled once, never again"
    # Hours later the reconciler finds nothing to charge.
    now = old(world)
    assert quota.reconcile_once(world.repo, now=now) == {"settled": 0, "released": 0}
    assert world.bucket()["consumed"] == 0


def test_the_backstop_settles_what_the_import_decided_not_the_full_reservation(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    quota.configure_async_decision(lambda op: media_quota.decide(world.store, op))
    world.asr.error = SpeechAsrRequestFailed(500)
    world.repo.fail_settle = 99
    monkeypatch.setattr(media_quota.time, "sleep", lambda _s: None)
    world.upload(media(60, tag="failed"))
    world.asr.error = None
    world.upload(media(90, tag="done"))
    failed, done = sorted(world.entries(), key=lambda e: e.source[media_quota.SOURCE_UNITS])
    assert world.bucket()["reserved"] == 150
    world.repo.fail_settle = 0
    now = old(world, hours=7)
    assert quota.reconcile_once(world.repo, now=now + quota.ASYNC_RECONCILE_AFTER) == {"settled": 2, "released": 0}
    by_operation = {op: (units, ref) for op, units, ref in world.repo.settled}
    assert by_operation[failed.source[media_quota.SOURCE_OP]] == (0, "reconciled:failed:asr_failed")
    assert by_operation[done.source[media_quota.SOURCE_OP]] == (90, "reconciled:completed:generated_asr")
    assert (world.bucket()["consumed"], world.bucket()["reserved"]) == (90, 0)


def test_the_backstop_charges_nothing_for_an_import_that_is_gone_and_leaves_an_unreadable_index_alone(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    idle(world, monkeypatch)
    world.upload(media(60))
    (entry,) = world.entries()
    quota.configure_async_decision(lambda op: media_quota.decide(world.store, op))
    operation = entry.source[media_quota.SOURCE_OP]
    quota.dispatch_operation(operation, media_quota.DISPATCH_REF)
    now = old(world)
    # Still queued on a live entry: in play, so settled as admitted.
    assert media_quota.decide(world.store, operation) is None
    # The index cannot be read: not knowing is not a decision, nothing is settled this tick.
    monkeypatch.setattr(world.store, "list", lambda **_k: [])
    monkeypatch.setattr(world.store, "last_read_issue", "index_corrupt", raising=False)
    assert quota.reconcile_once(world.repo, now=now + quota.ASYNC_RECONCILE_AFTER) == {"settled": 0, "released": 0}
    monkeypatch.setattr(world.store, "last_read_issue", "", raising=False)
    # The entry was removed: it produced nothing for the learner.
    assert quota.reconcile_once(world.repo, now=now + quota.ASYNC_RECONCILE_AFTER) == {"settled": 1, "released": 0}
    assert world.repo.settled[-1] == (operation, 0, "reconciled:no-entry")


def test_a_job_still_running_is_settled_as_admitted_by_the_backstop(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    idle(world, monkeypatch)
    world.upload(media(60))
    (entry,) = world.entries()
    quota.configure_async_decision(lambda op: media_quota.decide(world.store, op))
    quota.dispatch_operation(entry.source[media_quota.SOURCE_OP], media_quota.DISPATCH_REF)
    now = old(world)
    assert quota.reconcile_once(world.repo, now=now + quota.ASYNC_RECONCILE_AFTER)["settled"] == 1
    assert world.repo.settled[-1][1:] == (60, "reconciled:abandoned")


def test_a_failing_sweep_does_not_stop_its_timer():
    calls = []

    def sweep():
        calls.append(1)
        raise RuntimeError("index unreadable")

    assert media_quota.IntentSchedule(sweep, interval=3600).tick() is None and calls == [1]


# ===================================================================================== P2-1 the other paid route ==

TRANSLATE = {
    "target_language": "vi",
    "asset": {"asset_id": "a1", "source_url": "https://example.com/v", "source_provider": "youtube",
              "source_type": "external-video", "title": "T", "source_language": "en", "processing_state": "ready",
              "duration_ms": 10000, "transcript_available": True},
    "transcript": {"asset_id": "a1", "source_language": "en",
                   "segments": [{"segment_id": "s1", "order": 0, "start_ms": 0, "end_ms": 4000, "original_text": "Hello there."}]},
}


def test_the_translation_route_is_refused_while_the_meter_is_enforced(world: World, monkeypatch):
    class Counting:
        calls = 0

        def translate(self, *_a, **_k):
            Counting.calls += 1
            raise AssertionError("the paid provider must not be reached")

    monkeypatch.setattr(media_api, "_media_translation_service", Counting())
    refused = world.client.post("/api/media-learning/translate", json=TRANSLATE)
    assert refused.status_code == 503
    assert refused.json()["detail"]["category"] == "quota_media_import_not_metered" and Counting.calls == 0
    enforced_runtime(repository=world.repo, env={quota.FLAG: "off"})
    monkeypatch.setattr(media_api, "_media_translation_service", None)
    off = world.client.post("/api/media-learning/translate", json=TRANSLATE)
    assert "quota_media_import_not_metered" not in off.text, "unchanged when not enforced"


@pytest.fixture()
def world(tmp_path, monkeypatch) -> World:
    return World(tmp_path, monkeypatch)


# ========================================================================================================== P3 ==

def test_a_settled_import_is_not_run_again_without_a_new_admission(world: World):
    assert world.upload(media(60)).status_code == 200
    (entry,) = world.entries()
    assert media_quota.is_settled_import(world.store.get(entry.media_id))
    calls = world.asr.calls
    assert world.pipeline.retry(world.store, world.assets, entry.media_id) is False
    assert world.asr.calls == calls, "no Whisper without a reservation"
    # An administrator's shared item is not a metered learner import: still retried as before.
    shared = world.importer.import_upload(_file(world, media(60, tag="shared")), filename="s.mp3", language="en",
                                          imported_by="admin", library="shared")
    assert world.pipeline.retry(world.store, world.assets, shared.media_id) is True


def _file(world: World, data: bytes) -> Path:
    path = world.tmp / f"in-{abs(hash(data))}.mp3"
    path.write_bytes(data)
    return path


def test_an_entry_that_was_stored_but_never_queued_is_not_an_import_the_learner_already_has(world: World):
    assert world.upload(media(60, tag="crash")).status_code == 200
    (entry,) = world.entries()
    world.store.update_if_present(entry.media_id, lambda e: dataclasses.replace(e, processing=None, status="processing"))
    again = world.upload(media(60, tag="crash"))
    assert again.status_code == 200 and again.json()["media_id"] != entry.media_id
    assert len(world.entries()) == 2
    # A published entry with no pipeline state (finished without one) still is.
    world.store.update_if_present(entry.media_id, lambda e: dataclasses.replace(e, processing=None, status="published"))
    assert media_quota.existing_import(world.store, owner_key="learner-1", language="en",
                                       source_key=entry.source[media_quota.SOURCE_KEY]) is not None


def test_an_operators_import_is_recorded_without_the_learner_origin(world: World, monkeypatch):
    rows: list[dict[str, Any]] = []
    monkeypatch.setattr(ai_platform, "_persist_operation_telemetry", lambda event: rows.append(sanitize_telemetry(event)))

    class Recording(FakeAsr):
        def transcribe_bytes(self, body, **kwargs):
            result = super().transcribe_bytes(body, **kwargs)
            record_audio_operation("speech_asr", provider="groq", model="whisper-large-v3-turbo", outcome="success",
                                   latency_ms=1, audio_seconds=result.duration_seconds)
            return result

    world.asr = Recording()
    world.pipeline = world.new_pipeline()
    world.importer.pipeline = world.pipeline
    world.importer.import_upload(_file(world, media(60, tag="op")), filename="s.mp3", language="en",
                                 imported_by="admin", library="shared")
    world.importer.import_upload(_file(world, media(60, tag="learner")), filename="l.mp3", language="en",
                                 imported_by="learner", library="personal", owner_key="learner-1")
    assert [row["origin"] for row in rows] == [None, "learner"]
