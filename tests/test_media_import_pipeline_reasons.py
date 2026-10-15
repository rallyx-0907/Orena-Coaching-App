"""Pipeline side of the import fixes: stored reason code + message, captions_blocked, partial translation."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from tests.test_media_lifecycle import _entry
from writing_coach.admin_content import media_outcome
from writing_coach.media_library_store import FileMediaLibraryStore


class _Ledger:
    def check(self, *_a, **_k):
        return None

    def record(self, *_a, **_k):
        return None

    def ai_usd_per_million_tokens(self):
        return 0.1


def _world(tmp_path, *, lines=5, language="en", **pipeline_kwargs):
    from writing_coach.media_segmentation import Cue
    from writing_coach.media_transcript_pipeline import MediaPipeline, build_transcript, lesson_payload

    store = FileMediaLibraryStore(tmp_path / "index")
    entry = replace(_entry(), language=language, status="processing", processing={"state": "running"})
    cues = [Cue(i * 1000, i * 1000 + 900, f"Line number {i} of the clip.") for i in range(lines)]
    payload = lesson_payload(entry, build_transcript(entry.media_id, language, cues), "fixture", lines * 1000)
    entry = replace(entry, lesson={"lesson_id": entry.media_id, "payload": payload})
    store.upsert(entry)
    return store, entry, MediaPipeline(ledger=_Ledger(), workers=1, **pipeline_kwargs)


def test_translation_that_reaches_some_lines_is_partial_with_counts(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
    store, entry, pipeline = _world(
        tmp_path, meanings=lambda e, t: SimpleNamespace(status="partial", meanings=[object()] * 3, provider_calls=1)
    )
    pipeline._sleep = lambda _seconds: None  # the bounded continuation waits between rounds; this test does not
    assert pipeline._translate(store, entry, "b1", False) == ("partial", {"vi": {"done": 3, "total": 5}})
    pipeline._meanings = lambda e, t: SimpleNamespace(status="unavailable", meanings=[], provider_calls=1)
    assert pipeline._translate(store, entry, "b1", False) == ("failed", {"vi": {"done": 0, "total": 5}})

    def down(e, t):
        raise RuntimeError("provider down")

    pipeline._meanings = down
    assert pipeline._translate(store, entry, "b1", False)[0] == "failed"
    pipeline._meanings = lambda e, t: SimpleNamespace(status="ready", meanings=[object()] * 5, provider_calls=1)
    assert pipeline._translate(store, entry, "b1", False) == ("ready", {"vi": {"done": 5, "total": 5}})


def test_a_stopped_item_stores_its_reason_code_and_message(tmp_path):
    from writing_coach.media_transcript_pipeline import PipelineStop

    store, entry, pipeline = _world(tmp_path)
    pipeline._hold_failed(store, entry.media_id, PipelineStop("audio_unavailable"))
    stored = store.get(entry.media_id)
    assert stored.status == "review"
    assert stored.processing["state"] == "failed" and stored.processing["reason"] == "audio_unavailable"
    assert stored.processing["message"] == "The audio of this source could not be downloaded."
    assert media_outcome(stored)["state"] == "failed"


def test_refused_captions_plus_no_audio_is_captions_blocked_but_plain_no_captions_is_not(tmp_path):
    from writing_coach.media_ingestion import MediaImportCategory, MediaImportError
    from writing_coach.media_transcript_pipeline import PipelineStop

    def broken_audio(*_a, **_k):
        raise RuntimeError("yt-dlp refused")

    def refusing(category):
        class Ingestion:
            def import_media(self, *_a):
                raise MediaImportError(category)

        return Ingestion()

    for category, expected in ((MediaImportCategory.PROVIDER_FAILURE, "captions_blocked"),
                               (MediaImportCategory.MEDIA_UNAVAILABLE, "audio_unavailable")):
        store, entry, pipeline = _world(tmp_path / expected, ingestion=refusing(category), youtube_audio=broken_audio, asr=object())
        youtube = replace(entry, provider="youtube", canonical_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        store.upsert(youtube)
        with pytest.raises(PipelineStop) as stop:
            pipeline._transcript(store, None, youtube, "b1", None)
        assert stop.value.code == expected


def test_rights_unknown_hold_keeps_its_message_and_does_not_publish(tmp_path):
    from writing_coach.media_transcript_pipeline import STATE_READY

    store, entry, pipeline = _world(tmp_path)
    pipeline._write_processing(store, entry, state=STATE_READY, stage="ready", reason="", detail="", status="published")
    held = store.get(entry.media_id)
    assert held.status == "review" and held.processing["state"] == "held"
    assert held.processing["reason"] == "rights_unknown" and held.processing["message"]
