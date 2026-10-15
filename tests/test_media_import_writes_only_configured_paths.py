"""A guard: an import writes nothing under the repository, in any language (D-216).

Background: on 2026-10-15 a first Chinese YouTube import was reported as `media_library_write_failed` ("Read-only file
system"), and a language-specific write under the repository (read-only in the worker) was suspected. This is a
regression guard against that class of defect, not a proof of what happened in production: the import and its transcript
pipeline run for `en` and `zh` with the library, assets and spend ledger in a temporary directory, and any attempt to
write under the repository fails as a read-only mount would. It passes today for both languages. (The reported request
is not in the :8021 access log; the likely cause is that it went to a read-only review container.)"""
from __future__ import annotations

import errno
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_media_lifecycle import _entry
from writing_coach.book_asset_store import FilesystemBookAssetStore
from writing_coach.media_library_store import FileMediaLibraryStore
from writing_coach.media_segmentation import Cue
from writing_coach.media_source_import import MediaSourceImporter
from writing_coach.media_spend import SpendLedger
from writing_coach.media_transcript_pipeline import MediaPipeline, build_transcript, lesson_payload

REPOSITORY = Path(__file__).resolve().parents[1]
_WRITE_MODES = ("w", "a", "x", "+")
_state = {"armed": False, "refused": []}


def _under_repository(raw: object) -> bool:
    try:
        path = Path(str(raw)).resolve()
    except (OSError, ValueError):
        return False
    return REPOSITORY in path.parents and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts


def _hook(event: str, args: tuple) -> None:
    if not _state["armed"]:
        return
    wrote = False
    target: object = ""
    if event == "open" and len(args) >= 2 and isinstance(args[1], str) and any(m in args[1] for m in _WRITE_MODES):
        wrote, target = True, args[0]
    elif event in {"os.mkdir", "os.remove", "os.rmdir"}:
        wrote, target = True, args[0]
    elif event == "os.rename":
        wrote, target = True, args[1]
    if wrote and isinstance(target, (str, bytes, Path)) and _under_repository(target):
        _state["refused"].append((event, str(target)))
        raise OSError(errno.EROFS, "Read-only file system", str(target))


sys.addaudithook(_hook)  # audit hooks cannot be removed; it is inert unless a test arms it


@pytest.mark.parametrize("language,text", [
    ("en", "Every morning I walk to the market. The vegetables are fresh."),
    ("zh", "每天早上我都去附近的市场买菜。阿姨总是很热情。"),
])
def test_an_import_writes_nothing_under_the_repository(tmp_path, monkeypatch, language, text):
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
    store = FileMediaLibraryStore(tmp_path / "index")
    assets = FilesystemBookAssetStore(tmp_path / "assets")
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / "spend.json"), workers=1)
    importer = MediaSourceImporter(None, store, assets, pipeline=pipeline)

    entry = replace(_entry(), media_id=f"youtube-{language}x", provider="youtube", provider_media_id=f"{language}x",
                    language=language, library="shared", status="published")
    transcript = build_transcript(entry.media_id, language, [Cue(0, 4500, text), Cue(4500, 9000, text)])
    entry = replace(entry, lesson={"lesson_id": entry.media_id,
                                   "payload": lesson_payload(entry, transcript, "provider_caption", 9000)})
    importer._from_url = lambda url, **_kw: (entry, None)

    _state["refused"].clear()
    _state["armed"] = True
    try:
        report = importer.import_urls([{"url": "https://www.youtube.com/watch?v=abcdefghijk"}],
                                      language=language, imported_by="admin")
    finally:
        _state["armed"] = False

    assert _state["refused"] == []
    item = report.items[0]
    assert (item.status, item.category) == ("ok", "ok"), item.detail
    assert store.get(entry.media_id).processing["state"] in {"held", "ready"}


def test_the_guard_itself_refuses_a_write_under_the_repository():
    _state["refused"].clear()
    _state["armed"] = True
    try:
        with pytest.raises(OSError) as raised:
            open(REPOSITORY / "data" / "never-written.tmp", "w")  # noqa: SIM115
    finally:
        _state["armed"] = False
    assert raised.value.errno == errno.EROFS and len(_state["refused"]) == 1
    _state["refused"].clear()
