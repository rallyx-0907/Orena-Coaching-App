"""Video PR-A: an oversize Commons file says "too large", and a transcoded upload.wikimedia.org URL is a direct file."""
from __future__ import annotations

import pytest

from tests.test_media_import_provenance import UPLOAD, _importer
from tests.test_media_import_review_fixes import PAGE, _import_commons
from writing_coach import media_commons, media_safe_fetch, media_source_import
from writing_coach.media_safe_fetch import UnsafeMediaFetch
from writing_coach.media_source_import import failure_reason
from writing_coach.media_thumbnail import MediaProbe

TRANSCODED = "https://upload.wikimedia.org/wikipedia/commons/transcoded/a/ab/Example_clip-one.ogv/Example_clip-one.ogv.360p.webm"


def _too_large(*_a, **_k):
    # The byte budget raising mid-download, exactly as `download_bounded` does for any host.
    raise media_safe_fetch._unsafe(media_safe_fetch.TOO_LARGE_MESSAGE, too_large=True)


def test_an_oversize_commons_file_gets_the_direct_files_too_large_reason(tmp_path, monkeypatch):
    with pytest.raises(UnsafeMediaFetch) as refused:
        _import_commons(tmp_path, monkeypatch, _too_large)
    commons_code, commons_message = failure_reason(refused.value)
    assert commons_code == "media_too_large" and "too large" in commons_message.casefold()
    # The same failure from a plain direct file answers with the very same code and copy.
    assert failure_reason(media_safe_fetch._unsafe(media_safe_fetch.TOO_LARGE_MESSAGE, too_large=True)) == (commons_code, commons_message)


def test_a_commons_outage_is_still_unavailable(tmp_path, monkeypatch):
    def down(*_a, **_k):
        raise media_safe_fetch._unsafe("The media address could not be fetched.", 500)

    with pytest.raises(media_commons.CommonsRejected) as refused:
        _import_commons(tmp_path, monkeypatch, down)
    assert refused.value.code == "commons_unavailable"


def test_the_cap_is_not_raised():
    assert media_safe_fetch.MAX_MEDIA_BYTES == 64 * 1024 * 1024
    assert isinstance(UnsafeMediaFetch("x"), ValueError)


def test_a_transcoded_upload_url_is_a_direct_file_not_a_commons_lookup(tmp_path, monkeypatch):
    from writing_coach import media_thumbnail

    monkeypatch.setattr(media_thumbnail, "_TEMP_ROOT", tmp_path)
    monkeypatch.setattr(media_source_import, "validate_public_http_url", lambda url, **_k: url)

    def no_lookup(url):  # pragma: no cover - the assertion is that this is never reached
        raise AssertionError("a transcoded file must not go through the Commons File lookup")

    monkeypatch.setattr(media_commons, "resolve", no_lookup)
    seen = {}

    def download(url, path, **kwargs):
        seen.update(kwargs, url=url)
        path.write_bytes(b"webm")
        return 4

    monkeypatch.setattr(media_source_import, "download_bounded", download)
    monkeypatch.setattr(media_source_import, "probe_media", lambda path: MediaProbe(4000, "video", 640, 360, True, True))
    monkeypatch.setattr(media_source_import, "video_frame_thumbnail", lambda *_a, **_k: b"")
    entry = _importer(tmp_path)._from_url(TRANSCODED, language="en", imported_by="admin", persist_media=True)[0]
    assert entry.provider == "direct" and entry.canonical_url == TRANSCODED
    assert seen["url"] == TRANSCODED
    # Host pinning and the polite User-Agent are kept.
    assert seen["allowed_hosts"] == frozenset({"upload.wikimedia.org"}) and "Orena-Coaching-App" in seen["user_agent"]


def test_original_uploads_and_file_pages_still_resolve_through_commons():
    assert not media_commons.is_derivative_upload(UPLOAD)
    assert not media_commons.is_derivative_upload(PAGE)
    assert media_commons.is_derivative_upload(TRANSCODED)
    assert not media_commons.is_derivative_upload("https://example.com/wikipedia/commons/transcoded/a/b/c.webm/c.webm")
