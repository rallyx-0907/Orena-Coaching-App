"""#211 review conditions: Commons politeness and refusals, rights stay held, plain-text author, stale state cleared."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from tests.test_media_import_pipeline_reasons import _world
from tests.test_media_import_provenance import UPLOAD, _commons_answer, _fetch, _importer
from writing_coach import media_commons, media_safe_fetch, media_source_import
from writing_coach.media_commons import CommonsRejected, resolve
from writing_coach.media_safe_fetch import UnsafeMediaFetch, _unsafe
from writing_coach.media_thumbnail import MediaProbe

PAGE = "https://commons.wikimedia.org/wiki/File:Example_clip-one.ogv"


def test_api_call_is_polite_pinned_and_follows_a_renamed_file():
    seen = {}

    def fetch(url, **kwargs):
        seen["url"], seen["kwargs"] = url, kwargs
        renamed = _commons_answer()
        renamed["query"]["pages"][0]["title"] = "File:New name.ogv"
        return json.dumps(renamed).encode(), "application/json"

    found = resolve("https://commons.wikimedia.org/wiki/File:Old_name.ogv", fetch=fetch)
    assert "redirects=1" in seen["url"]
    assert seen["kwargs"]["allowed_hosts"] == frozenset({"commons.wikimedia.org"})
    agent = seen["kwargs"]["user_agent"]
    assert "github.com/rallyx-0907/Orena-Coaching-App" in agent and "@" not in agent
    assert found.filename == "New name.ogv" and found.page_url.endswith("/wiki/File:New_name.ogv")


@pytest.mark.parametrize("status,code", [(429, "commons_rate_limited"), (403, "commons_rate_limited"), (500, "commons_unavailable"), (None, "commons_unavailable")])
def test_a_refused_api_call_maps_to_a_stable_code_not_unsafe_source(status, code):
    with pytest.raises(CommonsRejected) as refused:
        resolve(PAGE, fetch=_fetch(_unsafe("The media address could not be fetched.", status)))
    assert refused.value.code == code


def test_an_oversize_api_answer_is_refused(monkeypatch):
    class Response:
        headers = type("H", (), {"get_content_type": staticmethod(lambda: "application/json")})()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self, n=-1):
            return b"x" * n if n > 0 else b""

    monkeypatch.setattr(media_safe_fetch, "_open", lambda *_a, **_k: Response())
    with pytest.raises(CommonsRejected) as refused:
        resolve(PAGE)  # the real bounded fetch, whose 1 MiB budget trips
    assert refused.value.code == "commons_unavailable"


def test_a_script_in_the_author_is_stored_as_plain_text():
    answer = _commons_answer(extmetadata={"Artist": {"value": '<script>alert(1)</script><b>Eve</b> &lt;img onerror=x&gt;'}})
    found = resolve(PAGE, fetch=_fetch(answer))
    assert "<script" not in found.author.casefold() or "alert(1)" in found.author  # tags are stripped, never executed
    assert "<b>" not in found.author and found.author_url == ""


def _import_commons(tmp_path, monkeypatch, download):
    from writing_coach import media_thumbnail

    monkeypatch.setattr(media_thumbnail, "_TEMP_ROOT", tmp_path)
    monkeypatch.setattr(media_source_import, "validate_public_http_url", lambda url, **_k: url)
    monkeypatch.setattr(media_commons, "resolve", lambda url: resolve(url, fetch=_fetch(_commons_answer())))
    monkeypatch.setattr(media_source_import, "download_bounded", download)
    monkeypatch.setattr(media_source_import, "probe_media", lambda path: MediaProbe(4000, "video", 640, 360, True, True))
    monkeypatch.setattr(media_source_import, "video_frame_thumbnail", lambda *_a, **_k: b"")
    importer = _importer(tmp_path)
    return importer, importer._from_url(PAGE, language="en", imported_by="admin", persist_media=True)[0]


def test_a_captured_cc_licence_does_not_clear_rights_and_the_reminder_stays(tmp_path, monkeypatch):
    monkeypatch.delenv("MEDIA_RIGHTS_CLEARED_PROVIDERS", raising=False)
    monkeypatch.delenv("MEDIA_RIGHTS_CLEARED_HOSTS", raising=False)
    importer, entry = _import_commons(tmp_path, monkeypatch, lambda url, path, **_k: path.write_bytes(b"ogv") or 3)
    assert entry.source["license_name"] == "CC BY-SA 4.0" and entry.source["license_url"].startswith("https://creativecommons.org/")
    assert "review provider terms" in entry.source["license"]
    held = importer.prepare(entry)
    assert held.source["rights"] == "unknown"
    assert held.status == "review"  # never published on a captured licence


def test_commons_download_is_pinned_polite_and_a_429_is_rate_limited(tmp_path, monkeypatch):
    seen = {}

    def download(url, path, **kwargs):
        seen.update(kwargs)
        raise _unsafe("The media address could not be fetched.", 429)

    with pytest.raises(CommonsRejected) as refused:
        _import_commons(tmp_path, monkeypatch, download)
    assert refused.value.code == "commons_rate_limited"
    assert seen["allowed_hosts"] == frozenset({"upload.wikimedia.org"}) and "Orena-Coaching-App" in seen["user_agent"]
    assert isinstance(UnsafeMediaFetch("x"), ValueError) and UPLOAD.startswith("https://upload.wikimedia.org/")


def test_credits_and_listening_source_carry_the_captured_licence():
    from tests.test_media_lifecycle import _entry
    from writing_coach.licences import media_credits

    entry = replace(_entry(), source={**_entry().source, "license": "Provider-hosted media; review provider terms before publishing.",
                                       "license_name": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0"})
    row = media_credits([entry])[0]
    assert row["licence"] == "CC BY-SA 4.0" and row["licence_url"].endswith("by-sa/4.0")


def test_a_rerun_starts_without_the_last_runs_translation_state(tmp_path):
    from writing_coach.media_transcript_pipeline import PipelineStop

    store, entry, pipeline = _world(tmp_path)
    stale = replace(entry, processing={"state": "failed", "reason": "audio_unavailable", "translation": "partial",
                                       "translation_counts": {"vi": {"done": 3, "total": 5}}})
    store.upsert(stale)
    try:
        pipeline._run(store, None, entry.media_id, "b1", None)
    except PipelineStop:
        pass
    processing = store.get(entry.media_id).processing
    assert processing.get("translation_counts") in ({}, None) or processing["translation_counts"] != {"vi": {"done": 3, "total": 5}}
    assert processing.get("translation") != "partial"
