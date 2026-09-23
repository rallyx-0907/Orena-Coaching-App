"""An import that fails says why, and the server keeps the traceback.

A YouTube import in the sandbox reported `This source failed (OSError).` and
wrote nothing to the log. Three different things could have caused it - the URL
routed to the file reader, a missing provider tool, or the source being
unreachable - and the operator was given the name of an exception class instead
of any of them. It was in fact a fourth: the media index could not be written.

These hold the reporting contract: a categorized provider failure reports its
own sentence, a filesystem failure says it was the library that could not be
written and which errno it was, and everything unexpected is logged with its
traceback rather than reduced to a class name in silence.
"""
from __future__ import annotations

import logging

import pytest

from writing_coach.media_ingestion import MediaImportCategory, MediaImportError
from writing_coach.media_source_import import MediaSourceImporter


class _Store:
    """A library index that refuses to be written, as a read-only mount does."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.saved: list[object] = []

    def upsert(self, entry):  # noqa: ANN001
        if self.error is not None:
            raise self.error
        self.saved.append(entry)
        return entry


def _importer(store, acquire):
    importer = MediaSourceImporter.__new__(MediaSourceImporter)
    importer._store = store
    importer._ingestion = None
    importer._asset_store = None
    importer._from_url = acquire
    return importer


def _refuse(exc):
    def acquire(url, *, language, imported_by, persist_media):  # noqa: ANN001
        raise exc
    return acquire


def test_a_categorized_provider_failure_reports_its_own_sentence():
    importer = _importer(_Store(), _refuse(MediaImportError(MediaImportCategory.MEDIA_UNAVAILABLE)))
    report = importer.import_urls([{"url": "https://www.youtube.com/watch?v=x"}],
                                  language="en", imported_by="admin")
    item = report.items[0]
    assert item.status == "error"
    assert item.detail == "This media is private or unavailable."
    assert "MediaImportError" not in item.detail


def test_a_library_that_cannot_be_written_says_so_and_names_the_errno():
    """The operator needs the difference between "the source is broken" and
    "this deployment cannot store it"; only one of them is theirs to fix."""
    refusal = OSError(30, "Read-only file system")
    refusal.filename = "/workspace/data/media_library"
    importer = _importer(_Store(refusal), _refuse(refusal))
    report = importer.import_urls([{"url": "https://www.youtube.com/watch?v=x"}],
                                  language="en", imported_by="admin")
    detail = report.items[0].detail
    assert "media library" in detail.lower()
    assert "Read-only file system" in detail
    assert "OSError" not in detail


def test_an_unexpected_failure_is_logged_with_its_traceback(caplog):
    importer = _importer(_Store(), _refuse(RuntimeError("something specific")))
    with caplog.at_level(logging.ERROR, logger="writing_coach.media_source_import"):
        report = importer.import_urls([{"url": "https://example.com/clip.mp3"}],
                                      language="en", imported_by="admin")
    assert report.items[0].status == "error"
    # The operator gets a sentence; the server keeps the whole thing.
    assert any(record.exc_info for record in caplog.records), "the traceback is logged"
    assert "something specific" in caplog.text


def test_one_bad_source_is_still_one_row_not_a_lost_batch():
    calls = []

    def acquire(url, *, language, imported_by, persist_media):  # noqa: ANN001
        calls.append(url)
        if url.endswith("bad"):
            raise MediaImportError(MediaImportCategory.PROVIDER_TIMEOUT)
        raise MediaImportError(MediaImportCategory.MEDIA_UNAVAILABLE)

    importer = _importer(_Store(), acquire)
    report = importer.import_urls(
        [{"url": "https://example.com/bad"}, {"url": "https://example.com/other"}],
        language="en", imported_by="admin",
    )
    assert [item.status for item in report.items] == ["error", "error"]
    assert len(calls) == 2


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
])
def test_a_youtube_url_never_reaches_the_file_reader(url):
    """The first hypothesis for the sandbox failure, held as a test so it
    cannot quietly become true later."""
    taken = []

    def youtube(self, url, *, language, imported_by):  # noqa: ANN001
        taken.append("youtube")
        raise MediaImportError(MediaImportCategory.PROVIDER_FAILURE)

    def direct(self, url, *, language, imported_by, persist_media):  # noqa: ANN001
        taken.append("direct")
        raise AssertionError("a YouTube URL was routed to the file reader")

    importer = MediaSourceImporter.__new__(MediaSourceImporter)
    importer._store = _Store()
    importer._from_youtube = youtube.__get__(importer, MediaSourceImporter)
    importer._from_direct_url = direct.__get__(importer, MediaSourceImporter)
    with pytest.raises(MediaImportError):
        importer._from_url(url, language="en", imported_by="admin", persist_media=True)
    assert taken == ["youtube"]
