"""The operator data CLIs (PR BU): dry run writes nothing, `--apply` writes through the application function with the
actor, refusals are clean. Nothing here reaches a network, a downloader or a recogniser."""
from __future__ import annotations

import json
import uuid
from dataclasses import replace

import pytest

pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from scripts import media_reprocess, reading_relevel, reading_source_admin, vocab_correct_example  # noqa: E402
from scripts.operator_cli import OperatorRefused  # noqa: E402
from writing_coach.persistence.admin_repository import AdminConsoleRepository  # noqa: E402
from writing_coach.persistence.models import AuditLog, Base, ReadingReviewEvent  # noqa: E402
from writing_coach.persistence.reading_content_repository import ReadingContentRepository  # noqa: E402
from writing_coach.reading_processing import EN_LEVEL_BANDS, LEVEL_VERSION, analyze_article  # noqa: E402

ACTOR = "hermes-for-owner"


def _engine():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return engine


def _audit(engine, action):
    with Session(engine) as session:
        return [row.payload for row in session.scalars(select(AuditLog).where(AuditLog.action == action))]


# -- media_reprocess ------------------------------------------------------------------------------------------------


@pytest.fixture()
def inline(monkeypatch):
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "")


def _media(tmp_path, *entries):
    from writing_coach.media_library_store import FileMediaLibraryStore

    store = FileMediaLibraryStore(tmp_path / "index")
    for entry in entries:
        store.upsert(entry)
    return store


def _passport(media_id="youtube-ZncA70OAgPw", **overrides):
    from tests.test_media_caption_timing import _passport_entry

    entry = _passport_entry()
    return replace(entry, media_id=media_id, lesson={**entry.lesson, "lesson_id": media_id}, duration_ms=60_000, **overrides)


class _NoAudio:
    """The recogniser and the downloader: any call fails the test."""

    def __call__(self, *_a, **_k):
        raise AssertionError("audio was downloaded or recognised")

    transcribe = __call__


def _pipeline(ingestion):
    from tests.test_media_import_pipeline_reasons import _Ledger
    from writing_coach import media_transcript_pipeline as mtp

    return mtp.MediaPipeline(ledger=_Ledger(), workers=1, ingestion=ingestion, asr=_NoAudio(), youtube_audio=_NoAudio())


def _limits():
    from writing_coach.media_caption_timing import thresholds

    return thresholds()


def _rolling_ingestion():
    from tests.test_media_caption_timing import _Ingestion, _raw_cues
    from writing_coach.media_caption_timing import KIND_UNKNOWN

    return _Ingestion(_raw_cues(), {"caption_kind": KIND_UNKNOWN, "caption_provider": "supadata", "caption_language": "en"})


class _Recorder:
    def __init__(self):
        self.events = []

    def __call__(self, action, **kwargs):
        self.events.append((action, kwargs))


def test_media_dry_run_writes_nothing_and_reports_the_current_timing(tmp_path):
    store = _media(tmp_path, _passport())
    before = (tmp_path / "index" / "index.json").read_bytes()
    report, code = media_reprocess.run(["youtube-ZncA70OAgPw"], store=store, apply=False, actor=ACTOR, limits=_limits(),
                                       quota=lambda: (3, 100))
    assert code == 0 and report["mode"] == "dry_run" and report["eligible"] == 1 and report["reprocessed"] == 0
    assert report["items"][0]["outcome"] == "would_reprocess" and report["items"][0]["timing_now"]["pass"] is False
    assert report["caption_quota"] == {"used_today": 3, "cap": 100}
    assert (tmp_path / "index" / "index.json").read_bytes() == before


def test_media_apply_re_times_one_at_a_time_records_the_actor_and_passes(tmp_path, inline):
    store = _media(tmp_path, _passport())
    pipeline, recorder, calls = _pipeline(_rolling_ingestion()), _Recorder(), []

    def retry(media_id):
        calls.append(media_id)
        return pipeline.retry(store, None, media_id)

    report, code = media_reprocess.run(["youtube-ZncA70OAgPw"], store=store, apply=True, actor=ACTOR, limits=_limits(),
                                       retry=retry, record_event=recorder, quota=lambda: (0, 100))
    assert code == 0, report
    assert calls == ["youtube-ZncA70OAgPw"] and report["reprocessed"] == 1 and report["passed"] == 1
    assert report["items"][0]["timing_pass"] is True and report["items"][0]["outcome"] == "ok"
    action, kwargs = recorder.events[0]
    assert action == "admin.content.reprocess" and kwargs["actor_key"] == ACTOR
    assert kwargs["payload"]["via"] == media_reprocess.SCRIPT and kwargs["payload"]["outcome"] == "ok"


def test_media_apply_stops_at_the_first_anomaly_and_touches_nothing_after_it(tmp_path, inline):
    # The second item is a personal one: not eligible. The third is never looked at.
    second = _passport("youtube-second", library="personal")
    store = _media(tmp_path, _passport(), second, _passport("youtube-third"))
    pipeline, calls = _pipeline(_rolling_ingestion()), []

    def retry(media_id):
        calls.append(media_id)
        return pipeline.retry(store, None, media_id)

    third_before = store.get("youtube-third")
    report, code = media_reprocess.run(["youtube-ZncA70OAgPw", "youtube-second", "youtube-third"], store=store, apply=True,
                                       actor=ACTOR, limits=_limits(), retry=retry, record_event=_Recorder())
    assert code == 1 and calls == ["youtube-ZncA70OAgPw"]
    assert report["stopped_at"] == {"media_id": "youtube-second", "anomaly": "ineligible:not_shared"}
    assert report["not_reached"] == 1 and store.get("youtube-third") == third_before


def test_media_a_failed_re_run_is_restored_and_stops_the_run(tmp_path, inline):
    from tests.test_media_caption_timing import _Ingestion

    store = _media(tmp_path, _passport(), _passport("youtube-next"))
    before = store.get("youtube-ZncA70OAgPw")
    no_captions = _Ingestion([], {"caption_status": "unavailable", "caption_error": "captions_unavailable"})
    pipeline, calls = _pipeline(no_captions), []

    def retry(media_id):
        calls.append(media_id)
        return pipeline.retry(store, None, media_id)

    recorder = _Recorder()
    report, code = media_reprocess.run(["youtube-ZncA70OAgPw", "youtube-next"], store=store, apply=True, actor=ACTOR,
                                       limits=_limits(), retry=retry, record_event=recorder)
    assert code == 1 and calls == ["youtube-ZncA70OAgPw"]
    assert report["stopped_at"]["anomaly"].startswith("restored:")
    after = store.get("youtube-ZncA70OAgPw")
    assert after.status == before.status and after.lesson["payload"] == before.lesson["payload"]
    assert recorder.events[0][1]["payload"]["outcome"] == "failed"


def test_media_stops_before_an_item_when_the_caption_cap_is_reached(tmp_path, inline):
    store = _media(tmp_path, _passport())
    report, code = media_reprocess.run(["youtube-ZncA70OAgPw"], store=store, apply=True, actor=ACTOR, limits=_limits(),
                                       retry=lambda _m: pytest.fail("no call over the cap"), record_event=_Recorder(),
                                       quota=lambda: (50, 50))
    assert code == 1 and report["stopped_at"]["anomaly"] == "caption_quota" and report["reprocessed"] == 0


def test_media_refuses_without_an_actor_and_reads_failing_ids_from_a_scan(tmp_path, capsys):
    assert media_reprocess.main(["--id", "youtube-x"]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "actor_required"
    scan = tmp_path / "scan.json"
    scan.write_text(json.dumps({"items": [{"media_id": "a", "pass": False}, {"media_id": "b", "pass": True},
                                          {"media_id": "c", "pass": False}]}), encoding="utf-8")
    assert media_reprocess.ids_from_scan(scan) == ["a", "c"]
    assert media_reprocess.main(["--from-scan", str(scan), "--actor", ACTOR, "--root", str(tmp_path / "none")]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "dry_run" and report["requested"] == 2 and report["items"][0]["outcome"] == "ineligible:not_found"


# -- reading_relevel ------------------------------------------------------------------------------------------------


BODY = ("Rain returned to the valley this week after a long dry season. Farmers said the water would help the young "
        "rice plants, and children played in the puddles near the school.")


@pytest.fixture()
def reading(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'content.db'}")
    Base.metadata.create_all(engine)
    repository = ReadingContentRepository(engine)
    repository.ensure_built_in_sources()
    return engine, repository


def _reading_article(repository, *, title, body=BODY):
    stale = next(band for band in EN_LEVEL_BANDS if band != analyze_article(body, "en").estimated_level)
    snapshot = repository.record_source_item(
        source_id=repository.built_in_source_id("manual"), source_native_id=title, canonical_url="", title=title,
        author="M. Tran", published_at=None, language="en", body=body, content_hash=f"{abs(hash(title)):064x}"[:64],
        metadata={"input_kind": "text"}, rights={"can_republish": True})
    return repository.create_article(
        source_item_id=snapshot["id"], title=title, body=body, excerpt=body[:120], language="en", topic="",
        estimated_level=stale, estimated_confidence=0.5, word_count=30, reading_time_seconds=90,
        analysis={"level_version": "old"}, targets=[])


def _events(engine, action):
    with Session(engine) as session:
        return list(session.scalars(select(ReadingReviewEvent).where(ReadingReviewEvent.action == action)))


def test_relevel_dry_run_lists_the_report_articles_and_writes_nothing(reading):
    engine, repository = reading
    article = _reading_article(repository, title="Rain returns")
    report, code = reading_relevel.run(engine, apply=False, actor=ACTOR, sets=[], reason="r")
    assert code == 1 and report["mode"] == "dry_run" and report["would_change"] == 1 and report["changed"] == 0
    assert report["items"][0]["id"] == article["id"] and report["items"][0]["new"] == analyze_article(BODY, "en").estimated_level
    assert repository.get_article(article["id"])["estimated_level"] == article["estimated_level"]
    assert _events(engine, "level_reestimated") == []


def test_relevel_apply_writes_the_estimate_and_version_keeps_a_reviewed_level(reading):
    engine, repository = reading
    plain = _reading_article(repository, title="Rain returns")
    reviewed = _reading_article(repository, title="Reviewed one", body=BODY + " The end.")
    repository.update_article(reviewed["id"], actor="admin", reviewed_level="C1")
    report, code = reading_relevel.run(engine, apply=True, actor=ACTOR, sets=[], reason="D-198 delegated",
                                       record_event=AdminConsoleRepository(engine).record_event)
    assert code == 0 and report["changed"] == 2 and report["reviewed_kept"] == 1
    fresh = repository.get_article(plain["id"])
    assert fresh["estimated_level"] == analyze_article(BODY, "en").estimated_level
    assert fresh["analysis"]["level_version"] == LEVEL_VERSION
    assert fresh["content_revision"] == plain["content_revision"] + 1
    kept = repository.get_article(reviewed["id"])
    assert kept["reviewed_level"] == "C1" and kept["effective_level"] == "C1"
    events = _events(engine, "level_reestimated")
    assert len(events) == 2 and {event.actor for event in events} == {ACTOR}
    audit = _audit(engine, "admin.reading_level_reestimate")
    assert len(audit) == 2 and {row["actor"] for row in audit} == {ACTOR}
    assert {row["level_version"] for row in audit} == {LEVEL_VERSION}
    assert {row["to"] for row in audit} == {analyze_article(BODY, "en").estimated_level,
                                            analyze_article(BODY + " The end.", "en").estimated_level}
    assert reading_relevel.run(engine, apply=True, actor=ACTOR, sets=[], reason="r",
                               record_event=AdminConsoleRepository(engine).record_event)[0]["changed"] == 0   # idempotent
    assert len(_audit(engine, "admin.reading_level_reestimate")) == 2
    with pytest.raises(OperatorRefused) as no_audit:
        reading_relevel.run(engine, apply=True, actor=ACTOR, sets=[], reason="r")
    assert no_audit.value.code == "audit_unavailable"


def test_relevel_set_names_an_article_by_title_and_refuses_unknown_or_bad_levels(reading):
    engine, repository = reading
    article = _reading_article(repository, title="The Ants and the Grasshopper")
    sets = reading_relevel.parse_sets(["The Ants and the Grasshopper=A2"])
    report, _ = reading_relevel.run(engine, apply=False, actor=ACTOR, sets=sets, reason="r")
    assert report["sets"][0]["outcome"] == "would_set" and repository.get_article(article["id"])["reviewed_level"] in (None, "")
    record = AdminConsoleRepository(engine).record_event
    report, code = reading_relevel.run(engine, apply=True, actor=ACTOR, sets=sets, reason="r", record_event=record)
    assert code == 0 and report["reviewed_set"] == 1
    override = _audit(engine, "admin.reading_level_override")
    assert len(override) == 1 and override[0]["actor"] == ACTOR and override[0]["reviewed_level"] == "A2"
    assert repository.get_article(article["id"])["reviewed_level"] == "A2"
    assert [event.actor for event in _events(engine, "level_override")] == [ACTOR]
    with pytest.raises(OperatorRefused) as missing:
        reading_relevel.run(engine, apply=True, actor=ACTOR, sets=[("No such title", "A2")], reason="r", record_event=record)
    assert missing.value.code == "article_not_found"
    with pytest.raises(OperatorRefused) as bad:
        reading_relevel.run(engine, apply=True, actor=ACTOR, sets=[(article["id"], "HSK3")], reason="r", record_event=record)
    assert bad.value.code == "level_invalid"
    with pytest.raises(OperatorRefused):
        reading_relevel.parse_sets(["no-level"])


# -- reading_source_admin -------------------------------------------------------------------------------------------


def _reading_source(repository, slug="sample-voa-learning-english"):
    return repository.create_source(
        slug=slug, name="[Mẫu kiểm thử] VOA Learning English", source_type="rss", base_url="https://example.org/feed",
        languages=["en"], rights={"automation_allowed": False, "can_republish": True, "can_adapt": False,
                                  "attribution_required": True, "license_note": "test"}, created_by="admin")


def test_source_dry_run_writes_nothing(reading):
    engine, repository = reading
    source = _reading_source(repository)
    report, code = reading_source_admin.run(repository, source_key=source["slug"], public_name="VOA Learning English",
                                            archive=True, apply=False, actor=ACTOR)
    assert code == 1 and report["changes"] == 2 and report["written"] == 0
    assert repository.get_source(source["id"]) == source


def test_source_apply_renames_and_archives_through_the_route_functions_with_the_actor(reading):
    engine, repository = reading
    source = _reading_source(repository)
    record = AdminConsoleRepository(engine).record_event
    report, code = reading_source_admin.run(repository, source_key=source["slug"], public_name="VOA Learning English",
                                            archive=True, apply=True, actor=ACTOR, record_event=record)
    assert code == 0 and report["written"] == 2
    after = repository.get_source(source["id"])
    assert after["public_name"] == "VOA Learning English" and after["state"] == "archived"
    assert after["name"] == source["name"] and not after["polling_enabled"]   # archived, not deleted
    assert _audit(engine, "admin.reading_source_public_name")[0]["actor"] == ACTOR
    assert _audit(engine, "admin.reading_source_state")[0] == {"state": "archived", "via": reading_source_admin.SCRIPT,
                                                               "actor": ACTOR}
    again, _ = reading_source_admin.run(repository, source_key=source["id"], public_name="VOA Learning English",
                                        archive=True, apply=True, actor=ACTOR, record_event=record)
    assert again["changes"] == 0 and len(_audit(engine, "admin.reading_source_state")) == 1   # nothing to do, no record


def test_source_unknown_errors_cleanly(reading, capsys, tmp_path):
    engine, repository = reading
    with pytest.raises(OperatorRefused) as missing:
        reading_source_admin.run(repository, source_key="nowhere", public_name="X", archive=False, apply=False, actor=ACTOR)
    assert missing.value.code == "source_not_found"
    url = f"sqlite+pysqlite:///{tmp_path / 'content.db'}"
    assert reading_source_admin.main(["--source", "nowhere", "--archive", "--actor", ACTOR, "--url", url]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["error"] == "source_not_found" and url not in json.dumps(out)


# -- vocab_correct_example ------------------------------------------------------------------------------------------


@pytest.fixture()
def vocab(tmp_path):
    from tests.test_admin_cue_corrections import _published_idiom
    from writing_coach.persistence.vocabulary_repository import SQLAlchemyVocabularyRepository, sqlite_vocabulary_repository

    repository = sqlite_vocabulary_repository(tmp_path / "vocab.db")
    repository.initialize()
    Base.metadata.create_all(repository.engine)   # audit_logs beside the vocabulary tables

    def repository_for(bind):
        return SQLAlchemyVocabularyRepository(bind, allow_sqlite_initialize=True)

    return repository, _published_idiom(repository), repository_for


def _correction(entry, **changes):
    from tests.test_admin_cue_corrections import GOOD, QUOTED

    item = {"collection": "idioms", "entry": entry, "index": 1, "text": GOOD["text"], "reading": GOOD["reading"],
            "translations": GOOD["translations"], "explanations": GOOD["explanations"], "label": {"en": "Comment", "zh": "评论"},
            "expect_from": QUOTED}
    item.update(changes)
    return item


def test_vocab_dry_run_runs_the_real_function_and_rolls_back(vocab):
    from tests.test_admin_cue_corrections import EXAMPLES, _snapshot, _stored

    repository, entry_id, repository_for = vocab
    report, code = vocab_correct_example.run(repository.engine, [_correction(entry_id)], reason="PRE-201 F3", apply=False,
                                             actor=ACTOR, repository_for=repository_for)
    assert code == 1 and report["changed"] == 1 and report["written"] == 0 and report["items"][0]["outcome"] == "would_write"
    assert _stored(repository, entry_id)[0] == EXAMPLES and _snapshot(repository, "idioms", entry_id) == EXAMPLES
    assert "example_corrections" not in (_stored(repository, entry_id)[1] or {})


def test_vocab_apply_writes_through_the_function_with_the_actor_and_label(vocab):
    from tests.test_admin_cue_corrections import NEW, _stored

    repository, entry_id, repository_for = vocab
    record = AdminConsoleRepository(repository.engine).record_event
    report, code = vocab_correct_example.run(repository.engine, [_correction("画蛇添足")], reason="PRE-201 F3", apply=True,
                                             actor=ACTOR, repository_for=repository_for, record_event=record)
    assert code == 0 and report["written"] == 1 and report["items"][0]["entry_id"] == entry_id
    examples, provenance = _stored(repository, entry_id)
    # Merged by language: the old VI label stays, EN and ZH are added.
    assert examples[1]["text"] == NEW and examples[1]["label"] == {"vi": "Làm vị ngữ", "en": "Comment", "zh": "评论"}
    history = provenance["example_corrections"][0]
    assert history["actor"] == ACTOR and history["label_languages"] == ["en", "zh"]
    vocab_correct_example.run(repository.engine, [_correction(entry_id, label={"vi": "Nhận xét"}, expect_from="")],
                              reason="r", apply=True, actor=ACTOR, repository_for=repository_for, record_event=record)
    assert _stored(repository, entry_id)[0][1]["label"] == {"vi": "Nhận xét", "en": "Comment", "zh": "评论"}
    audit = _audit(repository.engine, "admin.content.vocabulary_example")
    assert len(audit) == 2 and audit[0]["via"] == vocab_correct_example.SCRIPT and audit[0]["index"] == 1
    assert {row["actor"] for row in audit} == {ACTOR}


def test_vocab_a_bad_correction_in_a_file_writes_none_of_them(vocab, tmp_path):
    from tests.test_admin_cue_corrections import EXAMPLES, _stored

    repository, entry_id, repository_for = vocab
    record = _Recorder()
    good, stale = _correction(entry_id), _correction(entry_id, index=2, translations={"vi": "x"}, expect_from="")
    with pytest.raises(OperatorRefused) as refused:
        vocab_correct_example.run(repository.engine, [good, stale], reason="r", apply=True, actor=ACTOR,
                                  repository_for=repository_for, record_event=record)
    assert refused.value.code == "example_invalid" and "en" in refused.value.detail
    assert _stored(repository, entry_id)[0] == EXAMPLES and record.events == []
    for bad, code in ((_correction(entry_id, expect_from="another sentence"), "example_mismatch"),
                      (_correction(str(uuid.uuid4())), "entry_not_found"),
                      (_correction(entry_id, headword="一石二鸟"), "headword_mismatch"),
                      (_correction(entry_id, translations={"xx": "x"}), "example_invalid")):
        with pytest.raises(OperatorRefused) as error:
            vocab_correct_example.run(repository.engine, [bad], reason="r", apply=True, actor=ACTOR,
                                      repository_for=repository_for, record_event=record)
        assert error.value.code == code
    with pytest.raises(OperatorRefused) as no_reason:
        vocab_correct_example.run(repository.engine, [good], reason=" ", apply=True, actor=ACTOR,
                                  repository_for=repository_for, record_event=record)
    assert no_reason.value.code == "reason_required"
    assert _stored(repository, entry_id)[0] == EXAMPLES


def test_the_f3_file_is_complete_for_the_three_pilot_idioms():
    from pathlib import Path

    data = json.loads((Path(__file__).resolve().parents[1] / "scripts" / "data" / "pilot_zh_idioms_f3_examples.json")
                      .read_text(encoding="utf-8"))
    assert data["collection"] == "pilot-zh-idioms" and data["reason"]
    assert [item["headword"] for item in data["corrections"]] == ["守株待兔", "自作聪明", "装模作样"]
    for item in data["corrections"]:
        uuid.UUID(item["entry"])
        assert item["index"] == 0 and item["headword"] in item["text"] and item["expect_from"]
        assert set(item["translations"]) == {"vi", "en"} and item["reading"] and item["explanations"]["vi"]
        assert set(item["label"]) == {"vi", "en", "zh"} and all(item["label"].values())
