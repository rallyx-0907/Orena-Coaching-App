"""A published media item can be taken back without being destroyed.

Until now the only lifecycle a shared media item had was "imported", and
`media_record` reported every one of them as published because that is what
being in the shared index meant. An operator who needed one off the shelf had
nothing to press, and the only way out was deleting the row - which loses the
transcript, the provenance and the audit trail with it.

These hold the states that replace that: published, unpublished, archived, and
back again. `delete` still exists for a genuine mistake; it is not part of this
flow.
"""
from __future__ import annotations

import pytest

from writing_coach.media_library_store import (
    FileMediaLibraryStore,
    MediaLibraryEntry,
    validate_entry,
)


def _entry(media_id: str = "sample-one", **overrides) -> MediaLibraryEntry:
    fields = dict(
        media_id=media_id, media_type="audio", provider="upload", provider_media_id=media_id,
        canonical_url="",
        playback={"provider": "orena", "kind": "audio", "url": f"/api/media/files/media/{media_id}/original.wav"},
        title=media_id, thumbnail={"kind": "none", "ref": ""}, duration_ms=1000, language="en",
        level="", creator="",
        source={"provider": "upload", "type": "upload", "provenance_url": "", "license": "",
                "review_status": "", "imported_by": "admin"},
        library="shared", created_at="2026-09-18T00:00:00+00:00", lesson=None,
    )
    fields.update(overrides)
    return MediaLibraryEntry(**fields)


@pytest.fixture()
def store(tmp_path):
    return FileMediaLibraryStore(tmp_path)


def test_an_entry_written_before_the_state_existed_is_published(store):
    """Every row already in an index was, by being there, published."""
    store.upsert(_entry())
    assert store.get("sample-one").status == "published"


def test_only_the_three_states_are_accepted():
    with pytest.raises(ValueError, match="status"):
        validate_entry(_entry(status="deleted"))
    for state in ("published", "unpublished", "archived"):
        assert validate_entry(_entry(status=state)).status == state


def test_a_learner_listing_carries_only_what_is_published(store):
    store.upsert(_entry("shown"))
    store.upsert(_entry("taken-back", status="unpublished"))
    store.upsert(_entry("retired", status="archived"))
    assert [item.media_id for item in store.list(language="en")] == ["shown"]


def test_an_operator_listing_can_ask_for_everything(store):
    store.upsert(_entry("shown"))
    store.upsert(_entry("retired", status="archived"))
    seen = {item.media_id: item.status for item in store.list(language="en", status=None)}
    assert seen == {"shown": "published", "retired": "archived"}


def test_taking_an_item_back_keeps_everything_it_carried(store):
    """Unpublishing is a state, not a deletion: the bytes, the provenance and
    the transcript are all still there to publish again."""
    store.upsert(_entry(lesson={"topic": "weather", "segments": [{"text": "hello"}]}))
    before = store.get("sample-one")
    store.upsert(_entry(status="unpublished", lesson=before.lesson))
    after = store.get("sample-one")
    assert after.status == "unpublished"
    assert after.lesson == before.lesson
    assert after.source == before.source
    assert store.list(language="en") == []
    store.upsert(_entry(status="published", lesson=before.lesson))
    assert [item.media_id for item in store.list(language="en")] == ["sample-one"]


# ---- the route an operator presses -----------------------------------------

def test_the_console_reports_the_state_and_the_actions_that_fit_it():
    """A drawer offers what can be done from where the item is, not a fixed
    pair of buttons that may do nothing."""
    from writing_coach.admin_content import media_record

    published = media_record(_entry())
    assert published["status"] == "published"
    assert {"unpublish", "archive"} <= set(published["actions"])
    assert "delete" not in published["actions"]

    unpublished = media_record(_entry(status="unpublished"))
    assert unpublished["status"] == "unpublished"
    assert "republish" in unpublished["actions"]
    assert "unpublish" not in unpublished["actions"]

    archived = media_record(_entry(status="archived"))
    assert archived["status"] == "archived"
    assert "restore" in archived["actions"]
