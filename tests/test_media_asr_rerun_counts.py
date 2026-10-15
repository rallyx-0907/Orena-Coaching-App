"""A run starts with no ASR screen counts, so a re-run that stops early or takes captions keeps none stale (D-208)."""

from tests.test_media_learner_upload import _tone
from writing_coach import media_thumbnail
from writing_coach.book_asset_store import FilesystemBookAssetStore
from writing_coach.media_library_store import FileMediaLibraryStore
from writing_coach.media_source_import import MediaSourceImporter
from writing_coach.media_spend import SpendLedger
from writing_coach.media_transcript_pipeline import MediaPipeline
from writing_coach.speech_asr import SpeechAsrResult, SpeechAsrSegment


def test_rerun_clears_stale_asr_screen_counts(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    monkeypatch.setattr(media_thumbnail, "_TEMP_ROOT", tmp_path)

    class Asr:
        def transcribe_bytes(self, body, **kwargs):
            return SpeechAsrResult("t", "m", "en", "x", (SpeechAsrSegment("Subtitles by the volunteers", 0, 3000), SpeechAsrSegment("A real sentence about bread and butter today.", 4000, 9000)), ())

    store = FileMediaLibraryStore(tmp_path / "index")
    assets = FilesystemBookAssetStore(tmp_path / "assets")
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / "spend.json"), asr=Asr())
    importer = MediaSourceImporter(None, store, assets, pipeline=pipeline)
    path = tmp_path / "voice.wav"
    path.write_bytes(_tone(10))
    entry = importer.import_upload(path, filename=path.name, language="en", imported_by="learner", library="personal", owner_key="learner-a")
    assert store.get(entry.media_id).processing["asr_filtered"] == 1
    # Second run: the audio route is unavailable, so the run stops before the screen.
    pipeline._asr = None
    pipeline._run(store, assets, entry.media_id, "second", None)
    processing = store.get(entry.media_id).processing
    assert processing.get("reason") == "asr_unconfigured"
    assert not processing.get("asr_filtered") and not processing.get("asr_flagged")
