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


@pytest.mark.parametrize(("declared", "rights"), [(True, "cleared"), (None, "unknown")])
def test_an_upload_carries_the_operators_rights_declaration(tmp_path, monkeypatch, declared, rights):
    """D-111: a shared upload is cleared only when the operator says so at import; otherwise it waits for review."""

    from writing_coach import media_thumbnail
    monkeypatch.setattr(media_thumbnail, "_TEMP_ROOT", tmp_path)
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    monkeypatch.delenv("MEDIA_RIGHTS_CLEARED_PROVIDERS", raising=False)
    store = FileMediaLibraryStore(tmp_path / "index")
    importer = MediaSourceImporter(None, store, FilesystemBookAssetStore(tmp_path / "assets"),
                                   pipeline=MediaPipeline(ledger=SpendLedger(tmp_path / "spend.json")))  # fmt: skip
    path = tmp_path / "voice.wav"
    path.write_bytes(_tone())
    entry = importer.import_upload(path, filename=path.name, language="en", imported_by="admin", rights_cleared=declared)
    assert store.get(entry.media_id).source["rights"] == rights


def test_zh_asr_output_is_cleaned_before_it_becomes_lesson_lines(tmp_path, monkeypatch):
    from writing_coach import media_thumbnail
    from writing_coach.speech_asr import SpeechAsrResult, SpeechAsrSegment, SpeechAsrWord
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    monkeypatch.setattr(media_thumbnail, "_TEMP_ROOT", tmp_path)
    spoken = "每天 早上 我 都 去 市场 买菜 你 呢"
    words = tuple(SpeechAsrWord(text, 6000 + index * 400, 6000 + index * 400 + 300) for index, text in enumerate(spoken.split()))
    class Asr:
        def transcribe_bytes(self, body, **kwargs):
            return SpeechAsrResult("test", "fixture", "zh", spoken, (SpeechAsrSegment(spoken, 0, 9500),), words)
    store = FileMediaLibraryStore(tmp_path / "index")
    assets = FilesystemBookAssetStore(tmp_path / "assets")
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / "spend.json"), asr=Asr())
    importer = MediaSourceImporter(None, store, assets, pipeline=pipeline)
    path = tmp_path / "voice.wav"
    path.write_bytes(_tone(10))
    entry = importer.import_upload(path, filename=path.name, language="zh", imported_by="learner", library="personal", owner_key="learner-a")
    segments = store.get(entry.media_id).lesson["payload"]["transcript"]["segments"]
    text = "".join(segment["original_text"] for segment in segments)
    assert " " not in text and text.endswith("？")
    assert segments[0]["start_ms"] == 6000


def test_zh_asr_is_one_script_and_hallucinations_are_filtered_and_counted(tmp_path, monkeypatch):
    from writing_coach import media_thumbnail
    from writing_coach.speech_asr import SpeechAsrResult, SpeechAsrSegment, SpeechAsrWord
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    monkeypatch.setattr(media_thumbnail, "_TEMP_ROOT", tmp_path)
    spoken = "這是 第一次 我 去 市场 买菜"
    words = tuple(SpeechAsrWord(text, 500 + index * 400, 500 + index * 400 + 300) for index, text in enumerate(spoken.split()))
    segments = (SpeechAsrSegment(spoken, 0, 3500), SpeechAsrSegment("优优独播剧场", 4000, 9000))
    class Asr:
        def transcribe_bytes(self, body, **kwargs):
            return SpeechAsrResult("test", "fixture", "zh", spoken, segments, words)
    store = FileMediaLibraryStore(tmp_path / "index")
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / "spend.json"), asr=Asr())
    importer = MediaSourceImporter(None, store, FilesystemBookAssetStore(tmp_path / "assets"), pipeline=pipeline)
    path = tmp_path / "voice.wav"
    path.write_bytes(_tone(10))
    entry = importer.import_upload(path, filename=path.name, language="zh", imported_by="learner", library="personal", owner_key="learner-a")
    stored = store.get(entry.media_id)
    text = "".join(segment["original_text"] for segment in stored.lesson["payload"]["transcript"]["segments"])
    assert "這" not in text and "这是第一次" in text and "独播" not in text
    assert stored.processing["asr_filtered"] == 1 and stored.processing["asr_flagged"] == 0


def test_admin_media_corrections_keep_raw_and_flag_each_changed_timed_cue(tmp_path):
    from dataclasses import replace
    from tests.test_media_lifecycle import _entry
    from writing_coach import media_transcript_pipeline as pipeline_module
    from writing_coach.media_segmentation import Cue

    cues = tuple(Cue(index * 3000, index * 3000 + 2500, text) for index, text in enumerate((
        "Hello world and welcome back to forest.", "The second sentence contains enough words to stand alone.",
        "The third sentence contains enough words to stand alone.", "The fourth sentence contains enough words to stand alone.",
        "The fifth sentence contains enough words to stand alone.", "The sixth sentence contains enough words to stand alone.",
        "The seventh sentence contains enough words to stand alone.", "The final sentence contains enough words to stand alone.",
    )))

    class Corrector:
        provider = "groq"
        model = "configured-text-model"

        def __init__(self):
            self.calls = []

        def correct(self, *, language, cues, title, description):
            self.calls.append((language, cues, title, description))
            return {
                "texts": ["Hello, world and welcome back to forest.", *(cue.text for cue in cues[1:])],
                "reasons": ["Inserted a comma after the greeting.", *("No change." for _ in cues[1:])],
                "provider": self.provider,
                "model": self.model,
            }

    corrector = Corrector()
    source = {**_entry().source, "provider": "youtube", "type": "video",
              "provenance_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
              "description": "A short nature film"}
    entry = replace(
        _entry("youtube-dQw4w9WgXcQ", provider="youtube", provider_media_id="dQw4w9WgXcQ",
               canonical_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ", duration_ms=24000,
               language="en", title="Honey bees", source=source,
               status="processing", lesson={"status": "PUBLISHED", "payload": {}},
               processing={"state": "running", "transcript_correction_eligibility": "new_admin_import"}),
    )
    store = FileMediaLibraryStore(tmp_path / "index")
    store.upsert(entry)
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / "spend.json"), corrector=corrector)
    result = pipeline._transcript(
        store, None, entry, "batch-1", pipeline_module.Candidate(cues=cues)
    )

    lines = result[0]
    assert len(lines) == len(cues)
    assert [(line.start_ms, line.end_ms) for line in lines] == [(cue.start_ms, cue.end_ms) for cue in cues]
    assert lines[0].text == "Hello, world and welcome back to forest."
    assert corrector.calls[0][0] == "en"
    assert corrector.calls[0][2:] == ("Honey bees", "A short nature film")
    stored = store.get(entry.media_id)
    assert stored.processing["transcript_corrections"] == [{
        "index": 0, "start_ms": cues[0].start_ms, "end_ms": cues[0].end_ms,
        "before": "Hello world and welcome back to forest.", "after": "Hello, world and welcome back to forest.", "reason": "Inserted a comma after the greeting.",
        "provider": "groq", "model": "configured-text-model",
    }]


@pytest.mark.parametrize("library,status", [("personal", "processing"), ("shared", "published")])
def test_transcript_correction_never_runs_for_learner_owned_or_previously_published_media(tmp_path, library, status):
    from dataclasses import replace
    from tests.test_media_lifecycle import _entry
    from writing_coach import media_transcript_pipeline as pipeline_module
    from writing_coach.media_segmentation import Cue

    class Corrector:
        def __init__(self):
            self.calls = 0

        def correct(self, **_kwargs):
            self.calls += 1
            raise AssertionError("correction is limited to held admin-owned media")

    corrector = Corrector()
    entry = replace(
        _entry("youtube-dQw4w9WgXcQ", provider="youtube", provider_media_id="dQw4w9WgXcQ",
               canonical_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ", duration_ms=24000,
        language="en", library=library, status=status,
               processing={"state": "running" if status == "processing" else "ready",
                           **({"previous": {"status": "published"}} if status == "published" else {})}),
    )
    store = FileMediaLibraryStore(tmp_path / f"index-{library}-{status}")
    store.upsert(entry)
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / f"spend-{library}-{status}.json"), corrector=corrector)
    cues = tuple(Cue(index * 3000, index * 3000 + 2500,
                     f"Sentence {index} is ready and waiting for another careful review.") for index in range(8))

    result = pipeline._transcript(store, None, entry, "batch-1", pipeline_module.Candidate(cues=cues))

    assert corrector.calls == 0
    assert [line.text for line in result[0]] == [cue.text for cue in cues]


@pytest.mark.parametrize("status", ["unpublished", "review"])
def test_legacy_published_lesson_without_new_import_admission_is_not_corrected(tmp_path, status):
    from dataclasses import replace
    from tests.test_media_lifecycle import _entry
    from writing_coach import media_transcript_pipeline as pipeline_module
    from writing_coach.media_segmentation import Cue

    class Corrector:
        calls = 0

        def correct(self, **_kwargs):
            self.calls += 1
            raise AssertionError("legacy published transcript must be left alone")

    entry = replace(_entry(
        "youtube-legacy", provider="youtube", provider_media_id="legacy", canonical_url="https://www.youtube.com/watch?v=legacy",
        duration_ms=24000, language="en", status=status, lesson={"status": "PUBLISHED", "payload": {}},
        processing={"state": "held"},
    ))
    store = FileMediaLibraryStore(tmp_path / f"legacy-{status}")
    store.upsert(entry)
    corrector = Corrector()
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / f"legacy-spend-{status}.json"), corrector=corrector)
    cues = tuple(Cue(index * 3000, index * 3000 + 2500,
                     f"Sentence {index} gives a complete and sufficiently detailed spoken example.") for index in range(8))

    pipeline._transcript(store, None, entry, "batch-legacy", pipeline_module.Candidate(cues=cues))

    assert corrector.calls == 0


@pytest.mark.parametrize("current_status,previous", [
    ("review", {"_status": "unpublished", "lesson": {"status": "PUBLISHED"}}),
    ("unpublished", {"_status": "published"}),
])
def test_published_history_blocks_correction_even_if_new_admission_marker_is_present(
    tmp_path, current_status, previous
):
    from dataclasses import replace
    from tests.test_media_lifecycle import _entry
    from writing_coach import media_transcript_pipeline as pipeline_module
    from writing_coach.media_segmentation import Cue

    class Corrector:
        calls = 0

        def correct(self, **_kwargs):
            self.calls += 1
            raise AssertionError("published history must fail closed")

    entry = replace(_entry(
        "youtube-published-history", provider="youtube", provider_media_id="history",
        canonical_url="https://www.youtube.com/watch?v=history", duration_ms=24000, language="en",
        status=current_status, lesson={"status": "NEEDS_REVIEW", "payload": {}},
        processing={"state": "running", "transcript_correction_eligibility": "new_admin_import",
                    "previous": previous},
    ))
    store = FileMediaLibraryStore(tmp_path / f"history-{current_status}")
    store.upsert(entry)
    corrector = Corrector()
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / f"history-spend-{current_status}.json"), corrector=corrector)
    cues = tuple(Cue(index * 3000, index * 3000 + 2500,
                     f"Sentence {index} gives a complete and sufficiently detailed spoken example.") for index in range(8))

    pipeline._transcript(store, None, entry, "batch-history", pipeline_module.Candidate(cues=cues))

    assert corrector.calls == 0


@pytest.mark.parametrize("before,after", [
    ("Beyoncé sings softly", "Beyonc sings softly"),
    ("cafe\u0301 au lait is ready", "cafe au lait is ready"),
    ("we say 你好 today", "we say 你 today"),
])
def test_english_correction_lexical_guard_preserves_unicode_tokens(tmp_path, before, after):
    from dataclasses import replace
    from tests.test_media_lifecycle import _entry
    from writing_coach import media_transcript_pipeline as pipeline_module
    from writing_coach.media_segmentation import Cue

    class Corrector:
        model = "configured-text-model"

        def correct(self, **_kwargs):
            return {"texts": [after], "reasons": ["Changed a word."], "provider": "groq", "model": self.model}

    base = _entry("unicode-guard", language="en")
    entry = replace(base, status="processing", processing={
        "state": "running", "transcript_correction_eligibility": "new_admin_import",
    })
    store = FileMediaLibraryStore(tmp_path / f"unicode-{len(before)}")
    store.upsert(entry)
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / f"unicode-spend-{len(before)}.json"), corrector=Corrector())

    result, metadata = pipeline._correct_transcript(
        store, entry, "batch-unicode", [Cue(0, 2000, before)], origin=pipeline_module.ORIGIN_CAPTION,
    )

    assert result[0].text == before
    assert metadata["transcript_correction_state"] == "failed"
    assert metadata["transcript_correction_detail"] == "lexemes_changed"


def test_noise_only_english_cue_is_held_instead_of_claiming_empty_correction(tmp_path):
    from dataclasses import replace
    from tests.test_media_lifecycle import _entry
    from writing_coach import media_transcript_pipeline as pipeline_module
    from writing_coach.media_segmentation import Cue

    class Corrector:
        calls = 0

        def correct(self, **_kwargs):
            self.calls += 1
            raise AssertionError("empty cleaned cues are rejected before a provider call")

    entry = replace(_entry("noise-only", language="en"), status="processing", processing={
        "state": "running", "transcript_correction_eligibility": "new_admin_import",
    })
    store = FileMediaLibraryStore(tmp_path / "noise-only")
    store.upsert(entry)
    corrector = Corrector()
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / "noise-only-spend.json"), corrector=corrector)
    raw = [Cue(0, 1000, ">>")]

    result, metadata = pipeline._correct_transcript(store, entry, "batch-noise", raw,
                                                    origin=pipeline_module.ORIGIN_CAPTION)

    assert result == raw
    assert corrector.calls == 0
    assert metadata["transcript_correction_state"] == "failed"
    assert metadata["transcript_correction_detail"] == "empty_cue"


def test_chinese_caption_is_never_llm_corrected_but_chinese_asr_is_eligible(tmp_path):
    from dataclasses import replace
    from tests.test_media_lifecycle import _entry
    from writing_coach import media_transcript_pipeline as pipeline_module
    from writing_coach.media_segmentation import Cue

    class Corrector:
        model = "configured-text-model"

        def __init__(self):
            self.calls = 0

        def correct(self, *, cues, **_kwargs):
            self.calls += 1
            return {"texts": [cue.text for cue in cues], "reasons": ["No change." for _ in cues],
                    "provider": "groq", "model": self.model}

    source = {**_entry().source, "provider": "youtube", "type": "video"}
    entry = replace(_entry(
        "youtube-zh", provider="youtube", provider_media_id="zh", canonical_url="https://www.youtube.com/watch?v=zh",
        duration_ms=24000, language="zh", source=source, status="processing",
        processing={"state": "running", "transcript_correction_eligibility": "new_admin_import"},
    ))
    store = FileMediaLibraryStore(tmp_path / "zh-caption")
    store.upsert(entry)
    corrector = Corrector()
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / "zh-caption-spend.json"), corrector=corrector)
    cues = tuple(Cue(index * 3000, index * 3000 + 2500, f"第{index}段内容清楚完整我们继续学习。") for index in range(8))

    caption_result = pipeline._transcript(store, None, entry, "batch-zh-caption", pipeline_module.Candidate(cues=cues))
    asr_lines, asr_meta = pipeline._correct_transcript(store, entry, "batch-zh-asr", list(caption_result[0]), origin=pipeline_module.ORIGIN_ASR)
    unchanged, _ = pipeline._correct_transcript(store, entry, "batch-zh-provider-caption", list(caption_result[0]), origin=pipeline_module.ORIGIN_CAPTION)

    assert corrector.calls == 1
    assert [line.text for line in unchanged] == [line.text for line in caption_result[0]]
    assert [line.text for line in asr_lines] == [line.text for line in caption_result[0]]
    assert asr_meta["transcript_correction_state"] == "applied"


def test_only_a_genuinely_new_shared_admin_import_gets_correction_admission(tmp_path):
    from dataclasses import replace
    from tests.test_media_lifecycle import _entry
    from writing_coach.media_source_import import MediaSourceImporter

    class StubPipeline:
        @staticmethod
        def new_batch():
            return "batch-new"

        def enqueue(self, *_args, **_kwargs):
            return None

    store = FileMediaLibraryStore(tmp_path / "admission-index")
    importer = MediaSourceImporter(
        None, store, FilesystemBookAssetStore(tmp_path / "admission-assets"), pipeline=StubPipeline()
    )
    source = {**_entry().source, "provider": "youtube", "type": "video", "imported_by": "admin"}
    new_entry = replace(_entry(
        "youtube-new", provider="youtube", provider_media_id="new", canonical_url="https://www.youtube.com/watch?v=new",
        source=source, lesson={"status": "PUBLISHED", "payload": {}}, status="review", processing={},
    ))
    prepared = importer.prepare(new_entry, declared=True)
    assert prepared.lesson["status"] == "PUBLISHED"
    assert prepared.processing["transcript_correction_eligibility"] == "new_admin_import"

    existing_source = {**source, "imported_by": "admin"}
    existing = replace(_entry("youtube-existing", provider="youtube", provider_media_id="existing",
                              canonical_url="https://www.youtube.com/watch?v=existing", source=existing_source,
                              lesson={"status": "PUBLISHED", "payload": {}}, status="review", processing={"state": "held"}))
    store.upsert(existing)
    prepared_existing = importer.prepare(existing, declared=True)
    assert "transcript_correction_eligibility" not in prepared_existing.processing


def test_retry_clears_admission_but_recovery_keeps_it_for_unfinished_new_import(tmp_path, monkeypatch):
    from dataclasses import replace
    from tests.test_media_lifecycle import _entry
    from writing_coach.media_segmentation import Cue
    from writing_coach.media_transcript_pipeline import build_transcript, lesson_payload

    marker = "new_admin_import"
    base = _entry("retry-admitted")
    transcript = build_transcript(base.media_id, "en", [Cue(0, 9000, "This complete sentence is long enough for review.")])
    lesson = {"payload": lesson_payload(base, transcript, "provider_caption", 9000)}
    retry_entry = replace(base, lesson=lesson, status="review",
                          processing={"state": "held", "transcript_correction_eligibility": marker})
    store = FileMediaLibraryStore(tmp_path / "retry-admission-index")
    store.upsert(retry_entry)
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / "retry-admission-spend.json"))
    observed = []
    monkeypatch.setattr(pipeline, "enqueue", lambda target, _assets, media_id, **_kwargs:
                        observed.append(dict(target.get(media_id).processing)))

    assert pipeline.retry(store, None, retry_entry.media_id, batch_id="manual-retry")
    assert "transcript_correction_eligibility" not in observed[-1]

    recovery_entry = replace(_entry("recover-admitted"), status="processing",
                             processing={"state": "running", "attempts": 1, "batch_id": "interrupted",
                                         "transcript_correction_eligibility": marker})
    store.upsert(recovery_entry)
    assert pipeline.recover(store, None) == 1
    assert observed[-1]["transcript_correction_eligibility"] == marker


@pytest.mark.parametrize("failure", ["provider_error", "malformed_result", "spend_cap", "unconfigured"])
def test_failed_correction_keeps_raw_transcript_held_even_when_rights_are_cleared(tmp_path, failure):
    from dataclasses import replace
    from tests.test_media_lifecycle import _entry
    from writing_coach import media_transcript_pipeline as pipeline_module
    from writing_coach.media_segmentation import Cue
    from writing_coach.media_spend import SpendCapReached

    cues = tuple(Cue(index * 3000, index * 3000 + 2500,
                     f"Sentence {index} is ready and waiting for another careful review.") for index in range(8))
    source = {**_entry().source, "provider": "youtube", "type": "video", "rights": "cleared"}

    class Corrector:
        model = "configured-text-model"
        configured = failure != "unconfigured"

        def correct(self, **_kwargs):
            if failure == "unconfigured":
                raise AssertionError("unconfigured corrector must not be called")
            if failure == "provider_error":
                raise RuntimeError("provider unavailable")
            if failure == "malformed_result":
                return {"texts": ["bad shape"]}
            raise AssertionError("spend cap must stop before the provider call")

    entry = replace(_entry(
        "youtube-failure", provider="youtube", provider_media_id="failure", canonical_url="https://www.youtube.com/watch?v=failure",
        duration_ms=24000, language="en", title="A title", source=source, status="processing",
        processing={"state": "running", "transcript_correction_eligibility": "new_admin_import"},
    ))
    store = FileMediaLibraryStore(tmp_path / f"failure-{failure}")
    store.upsert(entry)
    ledger = SpendLedger(tmp_path / f"spend-failure-{failure}.json")
    if failure == "spend_cap":
        ledger.check = lambda *_args: (_ for _ in ()).throw(SpendCapReached("spend_cap_batch_ai", limit=0, spent=0, scope="batch"))
    pipeline = MediaPipeline(ledger=ledger, corrector=Corrector())

    pipeline._run(store, None, entry.media_id, "batch-1", pipeline_module.Candidate(cues=cues))

    stored = store.get(entry.media_id)
    saved = stored.lesson["payload"]["transcript"]["segments"]
    assert stored.status == "review"
    assert stored.processing["state"] == "held"
    assert stored.processing["transcript_correction_state"] == ("unavailable" if failure == "unconfigured" else "failed")
    assert [segment["original_text"] for segment in saved] == [cue.text for cue in cues]


def test_transcript_correction_chunks_a_valid_long_video_into_bounded_calls(tmp_path):
    from dataclasses import replace
    from tests.test_media_lifecycle import _entry
    from writing_coach import media_transcript_pipeline as pipeline_module
    from writing_coach.media_segmentation import Cue

    cues = tuple(Cue(index * 3000, index * 3000 + 2500,
                     f"Sentence {index} gives a complete and sufficiently detailed spoken example.") for index in range(26))
    source = {**_entry().source, "provider": "youtube", "type": "video"}

    class Corrector:
        model = "configured-text-model"

        def __init__(self):
            self.calls = []

        def correct(self, *, language, cues, title, description):
            self.calls.append(tuple(cues))
            return {"texts": [cue.text for cue in cues], "reasons": ["No change." for _ in cues],
                    "provider": "groq", "model": self.model}

    corrector = Corrector()
    entry = replace(_entry(
        "youtube-long", provider="youtube", provider_media_id="long", canonical_url="https://www.youtube.com/watch?v=long",
        duration_ms=80000, language="en", source=source, status="processing",
        processing={"state": "running", "transcript_correction_eligibility": "new_admin_import"},
    ))
    store = FileMediaLibraryStore(tmp_path / "long-index")
    store.upsert(entry)
    pipeline = MediaPipeline(ledger=SpendLedger(tmp_path / "long-spend.json"), corrector=corrector)

    result = pipeline._transcript(store, None, entry, "batch-long", pipeline_module.Candidate(cues=cues))

    assert len(corrector.calls) == 2
    assert [len(batch) for batch in corrector.calls] == [24, 2]
    assert [line.text for line in result[0]] == [cue.text for cue in cues]


@pytest.mark.parametrize("failure", ["provider_error", "spend_cap"])
def test_transcript_correction_stops_before_calling_later_batches(tmp_path, failure):
    from dataclasses import replace
    from tests.test_media_lifecycle import _entry
    from writing_coach import media_transcript_pipeline as pipeline_module
    from writing_coach.media_segmentation import Cue
    from writing_coach.media_spend import SpendCapReached

    cues = tuple(Cue(index * 3000, index * 3000 + 2500,
                     f"Sentence {index} gives a complete and sufficiently detailed spoken example.") for index in range(26))
    source = {**_entry().source, "provider": "youtube", "type": "video"}

    class Corrector:
        model = "configured-text-model"

        def __init__(self):
            self.calls = 0

        def correct(self, *, cues, **_kwargs):
            self.calls += 1
            if failure == "provider_error" and self.calls == 2:
                raise RuntimeError("provider unavailable")
            return {"texts": [cue.text for cue in cues], "reasons": ["No change." for cue in cues],
                    "provider": "groq", "model": self.model}

    corrector = Corrector()
    entry = replace(_entry(
        "youtube-stop", provider="youtube", provider_media_id="stop", canonical_url="https://www.youtube.com/watch?v=stop",
        duration_ms=80000, language="en", source=source, status="processing",
        processing={"state": "running", "transcript_correction_eligibility": "new_admin_import"},
    ))
    store = FileMediaLibraryStore(tmp_path / f"stop-index-{failure}")
    store.upsert(entry)
    ledger = SpendLedger(tmp_path / f"stop-spend-{failure}.json")
    if failure == "spend_cap":
        checks = 0

        def check(*_args):
            nonlocal checks
            checks += 1
            if checks == 2:
                raise SpendCapReached("spend_cap_batch_ai", limit=0, spent=0, scope="batch")

        ledger.check = check
    pipeline = MediaPipeline(ledger=ledger, corrector=corrector)

    result = pipeline._transcript(store, None, entry, "batch-stop", pipeline_module.Candidate(cues=cues))

    assert corrector.calls == (2 if failure == "provider_error" else 1)
    assert result[-1]["transcript_correction_state"] == "failed"
    assert [line.text for line in result[0]] == [cue.text for cue in cues]
