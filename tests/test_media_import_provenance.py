"""Import-side provenance and reasons: who made a source and where it came from, Commons pages and .ogv, a
specific reason for every rejection, stable reason codes with messages stored on the item, and partial translation."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from tests.test_media_ingestion import FakeCaptionClient, _track
from tests.test_media_lifecycle import _entry
from writing_coach import media_commons, media_source_import
from writing_coach.admin_content import media_outcome, media_record
from writing_coach.book_asset_store import FilesystemBookAssetStore
from writing_coach.media_commons import CommonsRejected, resolve
from writing_coach.media_ingestion import MediaIngestionService
from writing_coach.media_library_store import FileMediaLibraryStore
from writing_coach.media_providers.youtube import YouTubeMediaProviderAdapter, YouTubeSourceMetadata
from writing_coach.media_safe_fetch import UnsafeMediaFetch
from writing_coach.media_source_import import MediaSourceImporter, failure_reason
from writing_coach.media_thumbnail import MediaProbe

VIDEO_ID = "dQw4w9WgXcQ"
UPLOAD = "https://upload.wikimedia.org/wikipedia/commons/a/ab/Example_clip-one.ogv"


class _Metadata:
    def fetch_metadata(self, url):
        return YouTubeSourceMetadata(
            title="A lesson", author_name="  The  Channel ", author_url="https://www.youtube.com/@thechannel",
            thumbnail_url="",
        )

    def fetch_title(self, url):
        return "A lesson"


def _youtube_service():
    adapter = YouTubeMediaProviderAdapter(metadata_client=_Metadata(), caption_client=FakeCaptionClient(_track()))
    return MediaIngestionService(adapters=(adapter,), source_language_supported=lambda code: code in {"en", "zh"})


def _importer(tmp_path, ingestion=None):
    return MediaSourceImporter(ingestion, FileMediaLibraryStore(tmp_path / "index"), FilesystemBookAssetStore(tmp_path / "assets"))


def test_youtube_import_stores_channel_and_provenance(tmp_path):
    importer = _importer(tmp_path, _youtube_service())
    entry = importer._from_youtube(f"https://youtu.be/{VIDEO_ID}", language="en", imported_by="admin")
    assert entry.creator == "The Channel"
    assert entry.source["creator"] == "The  Channel"
    assert entry.source["creator_url"] == "https://www.youtube.com/@thechannel"
    assert entry.source["platform"] == "YouTube"
    assert entry.source["original_url"] == f"https://www.youtube.com/watch?v={VIDEO_ID}"
    importer._store.upsert(entry)  # the index accepts it (strings only, required keys kept)
    assert media_source_import.source_label(entry) == "YouTube"
    assert media_record(entry)["subtitle"] == "YouTube · The Channel"


def _commons_answer(**info):
    base = {
        "url": UPLOAD, "mime": "video/ogg",
        "extmetadata": {
            "ObjectName": {"value": "Example clip: one"},
            "Artist": {"value": '<a href="//commons.wikimedia.org/wiki/User:Jane" title="User:Jane">Jane Doe</a> &amp; co'},
            "LicenseShortName": {"value": "CC BY-SA 4.0"},
            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"},
        },
    }
    base.update(info)
    return {"query": {"pages": [{"title": "File:Example clip-one.ogv", "imageinfo": [base]}]}}


def _fetch(answer, seen=None):
    def fetch(url, **_kwargs):
        if seen is not None:
            seen.append(url)
        if isinstance(answer, Exception):
            raise answer
        return json.dumps(answer).encode(), "application/json"
    return fetch


def test_commons_file_page_resolves_to_media_url_author_and_licence():
    seen = []
    found = resolve("https://commons.wikimedia.org/wiki/File:Example_clip-one.ogv", fetch=_fetch(_commons_answer(), seen))
    assert found.media_url == UPLOAD
    assert found.title == "Example clip: one"  # the page's own name, not the filename stem
    assert found.author == "Jane Doe & co"
    assert found.author_url == "https://commons.wikimedia.org/wiki/User:Jane"
    assert (found.licence, found.licence_url) == ("CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0")
    assert found.page_url == "https://commons.wikimedia.org/wiki/File:Example_clip-one.ogv"
    assert "titles=File%3AExample%20clip-one.ogv" in seen[0] and seen[0].startswith("https://commons.wikimedia.org/w/api.php")


def test_commons_title_falls_back_to_a_readable_filename_stem():
    answer = _commons_answer(extmetadata={})
    found = resolve("https://commons.wikimedia.org/wiki/File:Example_clip-one.ogv", fetch=_fetch(answer))
    assert found.title == "Example clip-one"
    assert found.author == "" and found.licence == ""


@pytest.mark.parametrize("url", [
    UPLOAD,
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Example_clip-one.ogv/320px-Example_clip-one.ogv.jpg",
])
def test_commons_direct_upload_urls_resolve_through_the_api(url):
    seen = []
    found = resolve(url, fetch=_fetch(_commons_answer(), seen))
    assert found.media_url == UPLOAD
    assert "Example%20clip-one.ogv" in seen[0]


@pytest.mark.parametrize("url,answer,code", [
    ("https://commons.wikimedia.org/wiki/Category:Videos", _commons_answer(), "commons_not_a_file"),
    ("https://upload.wikimedia.org/wikipedia/en/a/ab/X.ogv", _commons_answer(), "commons_not_commons"),
    ("https://commons.wikimedia.org/wiki/File:Gone.ogv", {"query": {"pages": [{"title": "File:Gone.ogv", "missing": True}]}}, "commons_file_missing"),
    ("https://commons.wikimedia.org/wiki/File:Pic.jpg", _commons_answer(mime="image/jpeg"), "commons_not_media"),
    ("https://commons.wikimedia.org/wiki/File:X.ogv", UnsafeMediaFetch("down"), "commons_unavailable"),
    ("https://commons.wikimedia.org/wiki/File:X.ogv", _commons_answer(url="https://evil.example/x.ogv"), "commons_unavailable"),
])
def test_commons_rejections_give_a_specific_code_and_sentence(url, answer, code):
    with pytest.raises(CommonsRejected) as refused:
        resolve(url, fetch=_fetch(answer))
    assert refused.value.code == code
    category, detail = failure_reason(refused.value)
    assert category == code and detail and detail != "This source could not be imported. The server log has the details."


def test_commons_import_stores_readable_title_author_licence_and_the_page(tmp_path, monkeypatch):
    from writing_coach import media_thumbnail

    monkeypatch.setattr(media_thumbnail, "_TEMP_ROOT", tmp_path)
    monkeypatch.setattr(media_source_import, "validate_public_http_url", lambda url, **_k: url)
    monkeypatch.setattr(media_source_import, "download_bounded", lambda url, path, **_k: path.write_bytes(b"ogv") or 3)
    monkeypatch.setattr(media_source_import, "probe_media", lambda path: MediaProbe(4000, "video", 640, 360, True, True))
    monkeypatch.setattr(media_source_import, "video_frame_thumbnail", lambda *_a, **_k: b"")
    monkeypatch.setattr(media_commons, "resolve", lambda url: _resolve_with_fake(url))
    importer = _importer(tmp_path)
    entry, _ = importer._from_url("https://commons.wikimedia.org/wiki/File:Example_clip-one.ogv", language="en", imported_by="admin", persist_media=True)
    assert entry.title == "Example clip: one"
    assert entry.creator == "Jane Doe & co"
    assert entry.canonical_url == UPLOAD
    assert entry.source["original_url"].endswith("/wiki/File:Example_clip-one.ogv")
    assert entry.source["platform"] == "Wikimedia Commons"
    assert entry.source["license_name"] == "CC BY-SA 4.0"
    assert entry.source["license_url"].startswith("https://creativecommons.org/")
    importer._store.upsert(entry)
    assert media_source_import.source_label(entry) == "Wikimedia Commons"


def _resolve_with_fake(url):
    return resolve(url, fetch=_fetch(_commons_answer()))


def test_ogv_is_a_direct_media_suffix_and_an_unreadable_file_says_so(tmp_path, monkeypatch):
    from writing_coach import media_thumbnail

    monkeypatch.setattr(media_thumbnail, "_TEMP_ROOT", tmp_path)
    assert ".ogv" in media_source_import.DIRECT_MEDIA_SUFFIXES
    monkeypatch.setattr(media_source_import, "validate_public_http_url", lambda url, **_k: url)
    monkeypatch.setattr(media_source_import, "download_bounded", lambda url, path, **_k: path.write_bytes(b"x") or 1)

    def unreadable(_path):
        raise ValueError("The media file could not be read.")

    monkeypatch.setattr(media_source_import, "probe_media", unreadable)
    with pytest.raises(media_source_import.UnsupportedMediaAddress) as refused:
        _importer(tmp_path)._from_direct_url("https://example.org/a.ogv", language="en", imported_by="admin", persist_media=False)
    assert failure_reason(refused.value)[0] == "media_unreadable"
    with pytest.raises(media_source_import.UnsupportedMediaAddress) as page:
        _importer(tmp_path)._from_direct_url("https://example.org/page.html", language="en", imported_by="admin", persist_media=False)
    category, detail = failure_reason(page.value)
    assert category == "unsupported_media_type" and ".html" in detail


def test_preview_rejection_carries_the_category_not_the_generic_source_error():
    from writing_coach import media_library_api

    class Importer:
        def preview(self, url, *, language):
            raise CommonsRejected("commons_file_missing", "This file does not exist on Wikimedia Commons.")

    row = media_library_api._preview_one(Importer(), "https://commons.wikimedia.org/wiki/File:X.ogv", "en")
    assert row["status"] == "error" and row["category"] == "commons_file_missing"
    assert "Commons" in row["detail"]


# -- processing outcome, reason codes, partial translation -----------------------------------------------------

def test_every_reason_the_pipeline_can_stop_with_has_a_stored_message(tmp_path):
    import re
    from pathlib import Path

    from writing_coach import media_transcript_pipeline as pipeline
    from writing_coach.media_segmentation import REASON_BY_CHECK

    source = Path(pipeline.__file__).read_text(encoding="utf-8")
    raised = set(re.findall(r'PipelineStop\("([a-z_]+)"', source)) - {"cancelled"}
    raised |= set(REASON_BY_CHECK.values()) | {"asr_rate_limited", "asr_auth", "asr_failed", "rights_unknown"}
    assert not {code for code in raised if not pipeline.reason_message(code)}


def test_outcome_tells_processing_held_failed_and_ready_apart_and_keeps_partial_translation_out_of_failed():
    def state(**processing):
        return media_outcome(replace(_entry(), processing=processing))

    assert state(state="running", stage="segment")["state"] == "processing"
    held = state(state="held", reason="rights_unknown")
    assert held["state"] == "held" and held["reason"] == "rights_unknown" and held["message"]
    failed = state(state="failed", reason="audio_unavailable")
    assert failed["state"] == "failed" and failed["message"] == "The audio of this source could not be downloaded."
    partial = state(state="held", reason="rights_unknown", translation="partial",
                    translation_counts={"vi": {"done": 48, "total": 113}})
    assert partial["state"] == "held" and partial["translation"] == {"state": "partial", "counts": {"vi": {"done": 48, "total": 113}}}
    stored = state(state="failed", reason="captions_blocked", message="kept as stored")
    assert stored["message"] == "kept as stored"


def test_partial_meaning_outcome_is_not_a_failure():
    from tests.test_media_meaning_cache import MemoryCache, _resolve

    outcome = _resolve(cache=MemoryCache(), translate=lambda segments, target: {segments[0].segment_id: "one"})
    assert outcome.status == "partial" and len(outcome.meanings) == 1
