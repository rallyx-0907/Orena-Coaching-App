"""D-203: an administrator can hide code-owned built-in lessons from learners, and every learner path honours it."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from tests.policy_support import MemoryPolicyStore
from writing_coach import content_visibility, listening_api, speaking_library, word_clips
from writing_coach.collection_api import catalog_lesson_resolver
from writing_coach import listening_catalog
from writing_coach.listening_catalog import catalog_lesson, catalog_lessons
from writing_coach.media_library_store import FileMediaLibraryStore
from writing_coach.persistence.platform_repository import SettingConflict

# The shipped built-in Listening catalogue is empty since D-245; this module exercises catalogue lessons on the
# fixture-local copy of the retired manifest (conftest.fixture_listening_catalog).
pytestmark = pytest.mark.usefixtures("fixture_listening_catalog")

PEN = "en-daily-pen-in-my-bag"


@pytest.fixture()
def store(tmp_path):
    memory = MemoryPolicyStore()
    previous = content_visibility._store
    content_visibility.configure(memory)
    previous_media = listening_api._media_store
    # Only the curated catalogue: a developer's imported library is not what these assertions are about.
    listening_api.configure_listening_media_library(FileMediaLibraryStore(tmp_path / "media_library"))
    try:
        yield memory
    finally:
        listening_api.configure_listening_media_library(previous_media)
        content_visibility.configure(previous)


def _hide(store, item=PEN):
    return content_visibility.set_hidden("listening", item, True, updated_by="admin@example.com", actor="sub-admin")


def test_everything_is_visible_by_default_and_without_a_store():
    content_visibility.configure(None)
    assert content_visibility.hidden_ids("listening") == frozenset()
    assert {lesson.lesson_id for lesson in catalog_lessons()} == {
        lesson.lesson_id for lesson in listening_catalog.CATALOG if lesson.content_status == "PUBLISHED"
    }


def test_a_hidden_lesson_is_absent_from_every_learner_list_and_open_route(store):
    assert catalog_lesson(PEN) is not None
    assert word_clips.word_clips("pen", 6)["total"] >= 1
    assert "media:" + PEN in {item["id"] for item in speaking_library.speaking_library("en")}
    assert PEN in {item["lesson_id"] for item in listening_api.listening_library(language="en", level=None, topic=None, tag=None)["items"]}
    assert catalog_lesson_resolver()("commons-voa-anna-pen", listening_catalog.CATALOG[0].source.segments[0]["segment_id"]) is not None

    assert _hide(store)["changed"] is True

    assert catalog_lesson(PEN) is None
    assert PEN not in {lesson.lesson_id for lesson in catalog_lessons()}
    assert PEN not in {lesson.lesson_id for lesson in catalog_lessons(language="en", level="A1", topic="daily-life")}
    library = listening_api.listening_library(language="en", level=None, topic=None, tag=None)
    assert PEN not in {item["lesson_id"] for item in library["items"]}
    assert all(PEN not in section["item_ids"] for section in library["sections"])
    with pytest.raises(HTTPException) as missing:
        listening_api.open_listening_library_lesson(PEN, "vi")
    assert missing.value.status_code == 404
    # Speaking offers the same lessons for shadowing; the word clips and the model lines come from the same catalogue.
    assert "media:" + PEN not in {item["id"] for item in speaking_library.speaking_library("en")}
    assert word_clips.word_clips("pen", 6)["total"] == 0
    with pytest.raises(LookupError):
        speaking_library._resolve_model_line(PEN, listening_catalog.CATALOG[0].media_object.transcript.segments[0].segment_id)
    # A progress row for it can no longer be written or resolved, and a stored one is "unavailable" with no title.
    assert listening_api.resolve_progress_line("commons-voa-anna-pen", listening_catalog.CATALOG[0].source.segments[0]["segment_id"]) is None
    assert catalog_lesson_resolver()("commons-voa-anna-pen", listening_catalog.CATALOG[0].source.segments[0]["segment_id"]) is None
    # The other lessons are untouched.
    assert catalog_lesson("zh-daily-what-is-this") is not None


def test_showing_a_hidden_lesson_again_restores_it_and_the_catalogue_is_never_written(store):
    before = [lesson.lesson_id for lesson in listening_catalog.CATALOG]
    _hide(store)
    assert content_visibility.set_hidden("listening", PEN, False, updated_by="a", actor="sub-admin")["changed"] is True
    assert catalog_lesson(PEN) is not None
    assert [lesson.lesson_id for lesson in listening_catalog.CATALOG] == before


def test_each_change_is_audited_with_actor_item_and_both_states(store):
    _hide(store)
    content_visibility.set_hidden("listening", PEN, False, updated_by="admin@example.com", actor="sub-admin")
    assert [(audit["action"], audit["actor"], audit["entity_id"], audit["payload"]["from"], audit["payload"]["to"])
            for audit in store.audits] == [
        ("admin.content.visibility", "sub-admin", PEN, "visible", "hidden"),
        ("admin.content.visibility", "sub-admin", PEN, "hidden", "visible"),
    ]
    assert store.rows[content_visibility.SETTING_KEY]["updated_by"] == "admin@example.com"


def test_setting_the_state_an_item_already_has_writes_nothing(store):
    assert content_visibility.set_hidden("listening", PEN, False, updated_by="a", actor="x")["changed"] is False
    _hide(store)
    assert _hide(store)["changed"] is False
    assert len(store.audits) == 1


def test_a_concurrent_change_is_a_conflict_not_an_overwrite(store, monkeypatch):
    _hide(store)
    original = store.set_setting

    def raced(key, value, **kwargs):
        store.rows[key] = {**store.rows[key], "updated_at": "someone-else"}
        return original(key, value, **kwargs)

    monkeypatch.setattr(store, "set_setting", raced)
    with pytest.raises(SettingConflict):
        content_visibility.set_hidden("listening", "zh-daily-what-is-this", True, updated_by="a", actor="x")


def test_an_unreadable_store_keeps_the_last_value_and_never_raises(store, monkeypatch):
    _hide(store)
    assert catalog_lesson(PEN) is None
    content_visibility.clear_cache()
    store.fail_reads = True
    assert catalog_lesson(PEN) is None  # last good value, not a sudden reappearance
    assert catalog_lesson("zh-daily-what-is-this") is not None


def test_a_malformed_document_hides_nothing_and_does_not_raise(store):
    store.rows[content_visibility.SETTING_KEY] = {"value": {"hidden": {"listening": "oops", "other": [PEN]}},
                                                  "updated_at": "t", "updated_by": "x"}
    content_visibility.clear_cache()
    assert catalog_lesson(PEN) is not None


def test_only_known_kinds_can_be_hidden_so_reading_articles_are_out_of_reach(store):
    with pytest.raises(content_visibility.VisibilityInvalid):
        content_visibility.set_hidden("reading", "any-article-id", True)
    assert content_visibility.KINDS == ("listening",)
    import pathlib
    reading_sources = [path for path in pathlib.Path(content_visibility.__file__).parent.glob("reading*.py")]
    assert reading_sources
    assert not [path.name for path in reading_sources if "content_visibility" in path.read_text(encoding="utf-8")]


def test_a_store_that_was_never_readable_fails_closed_and_logs_once_per_window(store, caplog):
    """Test content must not reach production on a guess (D-203 item 5)."""
    store.fail_reads = True
    content_visibility.configure(store)  # a fresh process: nothing has been read yet
    with caplog.at_level("WARNING", logger=content_visibility.__name__):
        assert catalog_lessons() == ()
        assert catalog_lesson(PEN) is None
        assert content_visibility.is_hidden("listening", "anything")
        assert listening_api.listening_library(language="en", level=None, topic=None, tag=None)["items"] == []
    assert store.reads == 1  # the failure is cached for the window, not retried on every call
    assert len([r for r in caplog.records if r.levelname == "WARNING"]) == 1
    # Once the store answers, the library is back.
    store.fail_reads = False
    content_visibility.clear_cache()
    assert catalog_lesson(PEN) is not None


def test_a_hidden_lesson_is_gone_from_the_agent_tool_and_the_licences_page(store):
    import app as application
    from fastapi import Response

    def credits():
        return str(application.orena_licences(Response()))

    assert application._agent_listening_lesson(PEN) is not None
    assert "Anna, do you have a pen?" in credits()
    _hide(store)
    assert application._agent_listening_lesson(PEN) is None
    assert "Anna, do you have a pen?" not in credits()
