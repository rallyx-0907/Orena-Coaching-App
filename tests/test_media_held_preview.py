"""An administrator can open a held, unpublished import in the real learner player (Video PR-C).

The review gate asks an operator to judge a transcript before confirming rights, so the operator
needs the player. The learner routes keep answering 404 for anything not published; the admin
route answers the same payload shape, to an administrator only, and changes nothing it reads.
"""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from tests.test_admin_authorization_matrix import ADMIN, LEARNER, _request, secured  # noqa: F401
from tests.test_media_lifecycle import _entry
from writing_coach import admin_console_api, listening_api, media_library_api
from writing_coach.book_asset_store import FilesystemBookAssetStore
from writing_coach.media_library_store import FileMediaLibraryStore
from writing_coach.media_segmentation import Cue
from writing_coach.media_transcript_pipeline import build_transcript, lesson_payload

HELD = "held-preview-one"
LINE = "Today we are walking through the city."


def _held(media_id: str = HELD, **overrides):
    entry = replace(
        _entry(media_id),
        status="review",
        processing={"state": "held", "reason": "rights_unknown"},
        source={"provider": "upload", "type": "upload", "provenance_url": "", "license": "",
                "review_status": "", "imported_by": "admin", "rights": "unknown"},
        **overrides,
    )
    transcript = build_transcript(entry.media_id, "en", [Cue(0, 4000, LINE)])
    return replace(entry, lesson={"payload": lesson_payload(entry, transcript, "generated_asr", 4000)})


@pytest.fixture()
def held(secured, monkeypatch, tmp_path):  # noqa: F811
    store = FileMediaLibraryStore(tmp_path / "index")
    assets = FilesystemBookAssetStore(tmp_path / "assets")
    store.upsert(_held())
    personal = replace(_held("upload-someone-elses"), library="personal", status="published",
                       source={"provider": "upload", "type": "upload", "provenance_url": "", "license": "", "review_status": "", "imported_by": "x", "owner": "somebody-else"})
    store.upsert(personal)
    monkeypatch.setattr(media_library_api, "_store", store)
    monkeypatch.setattr(media_library_api, "_asset_store", assets)
    monkeypatch.setattr(listening_api, "_media_store", store)
    monkeypatch.setattr(admin_console_api._state, "media_store", store)
    monkeypatch.setattr(listening_api, "get_learner_profile", lambda: {"native_language": "en"})
    return secured, store, assets


def _get(app, path, who):
    return _request(app, "GET", path, {}, who)


def test_an_administrator_opens_a_held_item_with_the_learner_payload_shape(held):
    app, store, _ = held
    response = _get(app, f"/api/media/admin/player/{HELD}", ADMIN)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["asset"]["asset_id"] and body["playback"] and body["catalog"]
    assert body["transcript"]["segments"][0]["original_text"] == LINE
    assert body["asset"]["transcript_available"] is True


def test_nobody_and_a_learner_cannot_open_it(held):
    app, _, _ = held
    assert _get(app, f"/api/media/admin/player/{HELD}", None).status_code == 401
    refused = _get(app, f"/api/media/admin/player/{HELD}", LEARNER)
    assert refused.status_code == 403
    assert LINE not in json.dumps(refused.json())


def test_the_learner_routes_still_answer_404_for_the_held_item_even_to_an_administrator(held):
    app, _, _ = held
    for who in (None, LEARNER, ADMIN):
        assert _get(app, f"/api/listening/library/{HELD}", who).status_code in {401, 404}
        assert _get(app, f"/api/media/my/{HELD}", who).status_code in {401, 404}


def test_the_held_item_is_in_no_learner_listing(held):
    app, store, _ = held
    listing = _get(app, "/api/listening/library?language=en", LEARNER)
    assert listing.status_code == 200, listing.text
    assert HELD not in json.dumps(listing.json())
    assert media_library_api.shared_browse_items("en") == []


def test_previewing_changes_neither_publish_nor_rights_state(held):
    app, store, _ = held
    before = store.get(HELD)
    assert _get(app, f"/api/media/admin/player/{HELD}", ADMIN).status_code == 200
    after = store.get(HELD)
    assert after == before
    assert (after.status, after.processing["state"], after.source["rights"]) == ("review", "held", "unknown")


def test_an_unknown_id_and_another_learners_personal_file_are_404(held):
    app, _, _ = held
    assert _get(app, "/api/media/admin/player/not-there", ADMIN).status_code == 404
    assert _get(app, "/api/media/admin/player/upload-someone-elses", ADMIN).status_code == 404


def test_the_held_items_own_file_plays_for_an_administrator_only(held):
    app, store, assets = held
    store.upsert(_held("upload-held-file"))
    assets.put("media/held-file/original.wav", b"RIFFxxxx")
    path = "/api/media/files/media/held-file/original.wav"
    assert _get(app, path, LEARNER).status_code == 404
    assert _get(app, path, None).status_code in {401, 404}
    served = _get(app, path, ADMIN)
    assert served.status_code == 200 and served.content == b"RIFFxxxx"


def test_the_admin_item_page_carries_every_transcript_segment(held):
    app, store, _ = held
    cues = [Cue(i * 3000, i * 3000 + 2500, f"Line number {i} of the transcript.") for i in range(40)]
    entry = _held("long-transcript")
    transcript = build_transcript(entry.media_id, "en", cues)
    store.upsert(replace(entry, lesson={"payload": lesson_payload(entry, transcript, "generated_asr", 120000)}))
    detail = _get(app, "/api/admin/console/content/media/long-transcript", ADMIN)
    assert detail.status_code == 200, detail.text
    body = detail.json()["transcript"]
    assert body["segment_count"] == len(body["segments"]) > 12
