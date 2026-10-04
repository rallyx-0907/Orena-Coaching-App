"""Normal import must prepare a transcript before becoming a learner lesson."""
import pytest

from writing_coach.book_asset_store import FilesystemBookAssetStore
from writing_coach.media_library_store import FileMediaLibraryStore
from writing_coach.media_source_import import MediaSourceImporter
from writing_coach.media_spend import SpendLedger
from writing_coach.media_transcript_pipeline import MediaPipeline
from tests.test_media_learner_upload import _tone


@pytest.mark.parametrize("language", ["en", "zh"])
def test_upload_without_asr_is_held_and_reports_why(tmp_path, monkeypatch, language):
    from writing_coach import media_thumbnail
    monkeypatch.setattr(media_thumbnail, "_TEMP_ROOT", tmp_path)
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    store = FileMediaLibraryStore(tmp_path / "index")
    assets = FilesystemBookAssetStore(tmp_path / "assets")
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / "spend.json"))
    importer = MediaSourceImporter(None, store, assets, pipeline=pipeline)
    path = tmp_path / "voice.wav"
    path.write_bytes(_tone())
    entry = importer.import_upload(path, filename=path.name, language=language, imported_by="admin")
    actual = store.get(entry.media_id)
    assert actual.status == "review"
    assert actual.processing["reason"] == "asr_unconfigured"
    assert store.list(language=language) == []


def test_operator_cannot_publish_a_source_without_a_transcript():
    from writing_coach.admin_content import media_record
    from tests.test_media_lifecycle import _entry
    record = media_record(_entry(status="review", processing={"state": "failed", "reason": "asr_unconfigured"}))
    assert "republish" not in record["actions"]
    assert "reprocess" in record["actions"]
    assert record["processing"]["reason"] == "asr_unconfigured"


def test_prepared_import_has_the_same_learning_modes_as_a_curated_transcript():
    from tests.test_media_lifecycle import _entry
    from writing_coach.listening_api import stored_media_metadata
    from writing_coach.media_transcript_pipeline import build_transcript, lesson_payload
    from writing_coach.media_segmentation import Cue
    entry = _entry()
    transcript = build_transcript(entry.media_id, "en", [Cue(0, 4000, "Today we are walking through the city.")])
    from dataclasses import replace
    entry = replace(entry, lesson={"payload": lesson_payload(entry, transcript, "generated_asr", 4000)})
    assert {"listen", "active", "dictation", "shadowing"} <= set(stored_media_metadata(entry)["available_modes"])


@pytest.mark.parametrize("language,text", [("en", "Today we are walking through the city."), ("zh", "每天早上我都去附近的市场买菜。")])
def test_manually_published_held_transcript_opens_for_learner(monkeypatch, language, text):
    from dataclasses import replace
    from tests.test_media_lifecycle import _entry
    from writing_coach import listening_api
    from writing_coach.media_transcript_pipeline import build_transcript, lesson_payload
    from writing_coach.media_segmentation import Cue
    entry = replace(_entry(), language=language, status="published", processing={"state": "held"})
    transcript = build_transcript(entry.media_id, language, [Cue(0, 4000, text)])
    entry = replace(entry, lesson={"payload": lesson_payload(entry, transcript, "generated_asr", 4000)})
    monkeypatch.setattr(listening_api, "stored_media_entry", lambda _id: entry)
    monkeypatch.setattr(listening_api, "get_learner_profile", lambda: {"native_language": language})
    result = listening_api.stored_media_payload(entry.media_id, language)
    assert result["transcript"]["segments"][0]["original_text"] == text
    assert result["asset"]["transcript_available"] is True


def test_generated_lesson_keeps_provider_word_timestamps():
    from tests.test_media_lifecycle import _entry
    from writing_coach.media_transcript_pipeline import build_transcript, lesson_payload
    from writing_coach.media_segmentation import Cue
    from writing_coach.speech_asr import SpeechAsrWord
    entry = _entry()
    transcript = build_transcript(entry.media_id, "en", [Cue(0, 4000, "Hello there.")])
    payload = lesson_payload(entry, transcript, "generated_asr", 4000,
                             words=[SpeechAsrWord("Hello", 100, 600), SpeechAsrWord("there", 800, 1400)])
    assert payload["transcript"]["segments"][0]["words"] == [
        {"text": "Hello", "start_ms": 100, "end_ms": 600},
        {"text": "there", "start_ms": 800, "end_ms": 1400},
    ]


@pytest.mark.parametrize("language,text", [("en", "Every morning I walk to the market. The vegetables are fresh."), ("zh", "每天早上我都去附近的市场买菜。阿姨总是很热情。")])
def test_real_pipeline_builds_private_timed_lesson_from_asr(tmp_path, monkeypatch, language, text):
    from writing_coach import media_thumbnail
    from writing_coach.speech_asr import SpeechAsrResult, SpeechAsrSegment
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    monkeypatch.setattr(media_thumbnail, "_TEMP_ROOT", tmp_path)
    class Asr:
        def transcribe_bytes(self, body, **kwargs):
            assert body and kwargs["language"] == language
            return SpeechAsrResult("test", "fixture", language, text, (SpeechAsrSegment(text, 0, 9000),), ())
    store = FileMediaLibraryStore(tmp_path / "index")
    assets = FilesystemBookAssetStore(tmp_path / "assets")
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / "spend.json"), asr=Asr())
    importer = MediaSourceImporter(None, store, assets, pipeline=pipeline)
    path = tmp_path / "voice.wav"
    path.write_bytes(_tone(10))
    entry = importer.import_upload(path, filename=path.name, language=language, imported_by="learner", library="personal", owner_key="learner-a")
    actual = store.get(entry.media_id)
    assert actual.status == "published"
    assert actual.processing["state"] == "ready"
    assert actual.lesson["payload"]["transcript_origin"] == "generated_asr"
    assert actual.lesson["payload"]["transcript"]["segments"]
    assert store.list(language=language) == []

@pytest.mark.parametrize("action", ["delete", "archive"])
def test_inflight_processing_never_restores_removed_content(tmp_path, monkeypatch, action):
    from dataclasses import replace
    from writing_coach import media_thumbnail
    from writing_coach.speech_asr import SpeechAsrResult, SpeechAsrSegment
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    monkeypatch.setattr(media_thumbnail, "_TEMP_ROOT", tmp_path)
    store = FileMediaLibraryStore(tmp_path / "index")
    class Asr:
        def transcribe_bytes(self, body, **kwargs):
            entry = store.list(library="personal", status=None)[0]
            if action == "delete":
                store.delete(entry.media_id)
            else:
                store.upsert(replace(entry, status="archived"))
            text = "Every morning I walk to the market and buy fresh vegetables."
            return SpeechAsrResult("test", "fixture", "en", text, (SpeechAsrSegment(text, 0, 9000),), ())
    assets = FilesystemBookAssetStore(tmp_path / "assets")
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / "spend.json"), asr=Asr())
    importer = MediaSourceImporter(None, store, assets, pipeline=pipeline)
    path = tmp_path / "voice.wav"
    path.write_bytes(_tone(10))
    importer.import_upload(path, filename=path.name, language="en", imported_by="learner", library="personal", owner_key="a")
    entries = store.list(library="personal", status=None)
    assert entries == [] if action == "delete" else entries[0].status == "archived"


@pytest.mark.parametrize("status", ["review", "processing", "unpublished", "archived"])
def test_shared_media_must_be_published_for_direct_learner_access(status):
    from tests.test_media_lifecycle import _entry
    from writing_coach.media_library_store import visible_to
    assert not visible_to(_entry(status=status), user_key="learner", language="en")
