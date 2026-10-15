"""The caption path keeps what it was given (D-213, PROPOSED).

Evidence: the 2026-10-15 EN caption batch. Eight YouTube items first imported on the provider-caption path at $0; translation
ended `rate_limited`, the only way on was `reprocess`, and reprocess re-ran the transcript step, fell back to Groq Whisper without
saying so, and replaced the human captions on all eight. A failed reprocess also turned an item with a good transcript `failed`.
Providers here are fakes; nothing reaches a network, a downloader or a speech recogniser."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from tests.test_media_import_pipeline_reasons import _Ledger
from tests.test_media_ingestion import VIDEO_ID, _service, _track
from tests.test_media_lifecycle import _entry
from writing_coach import media_transcript_pipeline as mtp
from writing_coach.admin_content import media_outcome
from writing_coach.listening_api import translation_source_provider
from writing_coach.media_ingestion import MediaImportCategory, MediaImportError
from writing_coach.media_library_store import FileMediaLibraryStore
from writing_coach.media_meaning import (
    PROVENANCE_CACHED_GENERATED,
    PROVENANCE_EDITORIAL,
    PROVENANCE_GENERATED,
    MeaningOutcome,
    SegmentMeaning,
    TranslatedLines,
    resolve_segment_meanings,
)
from writing_coach.media_segmentation import Cue
from writing_coach.media_transcript_pipeline import (
    ORIGIN_ASR,
    ORIGIN_CAPTION,
    PipelineStop,
    build_transcript,
    lesson_payload,
    lines_from_payload,
)

URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
LINES = 8
SPOKEN = [
    "Good morning and welcome to the show.", "Today we are talking about how bees make honey.",
    "A single bee visits many flowers each day.", "The nectar is carried back to the hive.",
    "Other bees fan it with their wings until it thickens.", "The honey is then sealed in wax cells.",
    "Winter comes and the colony lives on that store.", "Thank you for watching and see you next time.",
]


def _cues() -> list[Cue]:
    return [Cue(i * 3000, i * 3000 + 2500, SPOKEN[i]) for i in range(LINES)]


class Ingestion:
    """A caption client that answers with cues, with `error` (a refused provider) or with nothing."""

    def __init__(self, *, cues=None, error=None, provenance=None):
        self.cues, self.error, self.provenance, self.calls = cues, error, dict(provenance or {}), 0

    def import_media(self, *_args):
        self.calls += 1
        if self.error is not None:
            raise self.error
        transcript = None
        if self.cues is not None:
            transcript = SimpleNamespace(segments=[SimpleNamespace(start_ms=c.start_ms, end_ms=c.end_ms, original_text=c.text) for c in self.cues])
        return SimpleNamespace(media_object=SimpleNamespace(transcript=transcript), provenance=self.provenance)


class Asr:
    """Speech recognition that must not be reached."""

    def __getattr__(self, name):
        raise AssertionError("speech recognition was used")


def _world(tmp_path, *, origin=ORIGIN_CAPTION, state="held", ingestion=None, meanings=None, **kwargs):
    """A youtube item that finished a run: a transcript of `origin`, translated, held for rights."""
    store = FileMediaLibraryStore(tmp_path / "index")
    base = replace(_entry(), media_type="video", provider="youtube", provider_media_id=VIDEO_ID, canonical_url=URL,
                   duration_ms=LINES * 3000, status="review" if state == "held" else "published",
                   source={**_entry().source, "provider": "youtube", "rights": "unknown", "caption_kind": "manual"})
    payload = lesson_payload(base, build_transcript(base.media_id, "en", _cues()), origin, LINES * 3000)
    processing = {"state": state, "stage": "ready", "reason": "rights_unknown" if state == "held" else "", "origin": origin,
                  "batch_id": "b1", "attempts": 1, "translation": "partial", "translation_counts": {"vi": {"done": 3, "total": LINES}},
                  "translation_reason": "rate_limited", "caption_kind": "manual" if origin == ORIGIN_CAPTION else "",
                  "checks": [{"id": "coverage", "pass": True}], "rights": "unknown"}
    entry = replace(base, lesson={"lesson_id": base.media_id, "payload": payload, "status": "NEEDS_REVIEW"}, processing=processing)
    store.upsert(entry)
    pipeline = mtp.MediaPipeline(ledger=_Ledger(), workers=1, ingestion=ingestion, asr=kwargs.pop("asr", Asr()),
                                 meanings=meanings, **kwargs)
    return store, store.get(entry.media_id), pipeline


@pytest.fixture(autouse=True)
def inline(monkeypatch):
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")


# -- 1. reprocess keeps the captions it was given ---------------------------------------------------------------


@pytest.mark.parametrize("failure", ["refused", "deferred"])
def test_a_reprocess_whose_caption_fetch_fails_keeps_the_caption_transcript_and_never_runs_asr(tmp_path, failure):
    # "refused": the importer raises the provider's category. "deferred": the production adapter does not raise, it returns
    # no transcript and says in its provenance that the provider refused (D-213).
    ingestion = (Ingestion(error=MediaImportError(MediaImportCategory.PROVIDER_FAILURE)) if failure == "refused"
                 else Ingestion(provenance={"caption_status": "unavailable"}))
    store, before, pipeline = _world(tmp_path, ingestion=ingestion)
    assert pipeline.retry(store, None, before.media_id)
    after = store.get(before.media_id)
    assert after.lesson == before.lesson  # the captions are exactly as they were
    assert after.lesson["payload"]["transcript_origin"] == ORIGIN_CAPTION
    processing = after.processing
    assert processing["state"] == "held" and processing["reason"] == "rights_unknown" and after.status == "review"
    assert processing["origin"] == ORIGIN_CAPTION and processing["caption_kind"] == "manual"
    assert processing["reprocess_reason"] == "captions_unavailable" and processing["reprocess_message"]
    assert processing["translation_counts"] == {"vi": {"done": 3, "total": LINES}}  # the translation is as it was
    assert not processing.get("previous")
    shown = media_outcome(after)
    assert shown["state"] == "held" and shown["transcript"]["reprocess_reason"] == "captions_unavailable"


def test_a_reprocess_that_finds_no_captions_track_keeps_them_too(tmp_path):
    store, before, pipeline = _world(tmp_path, ingestion=Ingestion(cues=None))
    pipeline.retry(store, None, before.media_id)
    after = store.get(before.media_id)
    assert after.lesson == before.lesson and after.processing["reprocess_reason"] == "captions_unavailable"


def test_a_reprocess_that_gets_working_captions_replaces_them_and_clears_the_note(tmp_path):
    fresh = [Cue(i * 3000, i * 3000 + 2500, text) for i, text in enumerate(reversed(SPOKEN))]
    store, before, pipeline = _world(tmp_path, ingestion=Ingestion(cues=fresh, provenance={"caption_kind": "auto"}))
    pipeline.retry(store, None, before.media_id)
    after = store.get(before.media_id)
    assert after.lesson != before.lesson and after.lesson["payload"]["transcript_origin"] == ORIGIN_CAPTION
    assert after.processing["caption_kind"] == "auto" and not after.processing.get("reprocess_reason")
    assert not after.processing.get("previous") and after.processing["state"] == "held"


def test_asr_fallback_for_an_item_that_never_had_captions_stays_as_it_was(tmp_path):
    # The item was made by speech recognition: a reprocess may use it again (nothing to protect).
    store, before, pipeline = _world(tmp_path, origin=ORIGIN_ASR, ingestion=Ingestion(cues=None), asr=object())
    asr_cues = [Cue(i * 3000, i * 3000 + 2500, text) for i, text in enumerate(SPOKEN)]
    used = []

    def speech(*_a):
        used.append(True)
        return asr_cues, [], "en", 0.001, 8.0, {"filtered": 0, "flagged": 0}

    pipeline._speech = speech
    pipeline.retry(store, None, before.media_id)
    assert used == [True]
    assert store.get(before.media_id).lesson["payload"]["transcript_origin"] == ORIGIN_ASR


# -- 2. the caption to ASR fallback on a first import is visible -------------------------------------------------


def _first_import(tmp_path, ingestion, **entry_source):
    store, entry, pipeline = _world(tmp_path, ingestion=ingestion)
    first = replace(entry, status="processing", processing={"state": "running"}, source={**entry.source, **entry_source})
    store.upsert(first)
    asr_cues = [Cue(i * 3000, i * 3000 + 2500, text) for i, text in enumerate(SPOKEN)]
    pipeline._speech = lambda *_a: (asr_cues, [], "en", 0.002, 8.0, {"filtered": 0, "flagged": 0})
    return store, first, pipeline


@pytest.mark.parametrize("ingestion, source, expected", [
    (Ingestion(error=MediaImportError(MediaImportCategory.PROVIDER_FAILURE)), {}, "captions_unavailable"),
    (Ingestion(cues=None), {"caption_status": "unavailable"}, "captions_unavailable"),  # the importer was refused earlier
    (Ingestion(cues=[Cue(0, 900, "Hi.")]), {}, "captions_unusable"),  # fetched, but not enough of the recording
])
def test_the_caption_to_asr_fallback_on_first_import_is_recorded_with_a_stable_reason(tmp_path, ingestion, source, expected):
    store, entry, pipeline = _first_import(tmp_path, ingestion, **source)
    lines, origin, cost, *_ = pipeline._transcript(store, None, entry, "b1", None)
    assert origin == ORIGIN_ASR and cost > 0
    processing = store.get(entry.media_id).processing
    assert processing["caption_fallback"] == expected and processing["caption_kind"] == ""
    shown = media_outcome(store.get(entry.media_id))["transcript"]
    assert shown["caption_fallback"] == expected and shown["caption_fallback_message"]


def test_a_source_with_simply_no_captions_records_no_fallback(tmp_path):
    store, entry, pipeline = _first_import(tmp_path, Ingestion(cues=None))
    pipeline._transcript(store, None, entry, "b1", None)
    assert store.get(entry.media_id).processing["caption_fallback"] == ""


def test_the_whole_first_run_stores_the_fallback_beside_the_origin(tmp_path):
    store, entry, pipeline = _first_import(tmp_path, Ingestion(error=MediaImportError(MediaImportCategory.PROVIDER_TIMEOUT)))
    pipeline._run(store, None, entry.media_id, "b1", None)
    processing = store.get(entry.media_id).processing
    assert processing["origin"] == ORIGIN_ASR and processing["caption_fallback"] == "captions_unavailable"
    assert store.get(entry.media_id).lesson["payload"]["transcript_origin"] == ORIGIN_ASR


# -- 3. manual versus auto captions are recorded; the payload origin is the real one ----------------------------------


def test_the_provider_adapter_says_whether_the_track_is_manual_or_auto():
    for kind in ("manual", "auto"):
        track = replace(_track(), kind=kind)
        service, _metadata, _captions = _service(track)
        acquisition = service.import_media(URL, "vi", "en")
        assert acquisition.provenance["caption_kind"] == kind
        assert "caption_status" not in acquisition.provenance


def test_a_refused_caption_fetch_is_reported_as_unavailable_when_recovery_is_deferred():
    from writing_coach.media_ingestion import MediaIngestionService, ProviderRequestFailed
    from writing_coach.media_providers.youtube import YouTubeMediaProviderAdapter
    from tests.test_media_ingestion import FakeCaptionClient, FakeMetadataClient

    adapter = YouTubeMediaProviderAdapter(metadata_client=FakeMetadataClient(),
                                          caption_client=FakeCaptionClient(None, error=ProviderRequestFailed()),
                                          enable_fallback=False, defer_transcript_recovery=True)
    service = MediaIngestionService(adapters=(adapter,), source_language_supported=lambda code: code in {"en", "zh"})
    acquisition = service.import_media(URL, "vi", "en")
    assert acquisition.media_object.transcript is None
    assert acquisition.provenance["caption_status"] == "unavailable" and "caption_kind" not in acquisition.provenance


def test_the_public_client_prefers_manual_and_marks_auto_when_only_auto_exists():
    from tests.test_media_ingestion import ROOT  # noqa: F401  (module import keeps the fixtures local)
    from writing_coach.media_providers.youtube import PublicYouTubeCaptionClient
    from youtube_transcript_api import NoTranscriptFound

    class Fetched(list):
        language_code = "en"

    class Track:
        language_code = "en"

        def __init__(self, text):
            self.text = text

        def fetch(self):
            return Fetched([SimpleNamespace(text=self.text, start=0.0, duration=1.0)])

    class Listing:
        def __init__(self, manual, generated):
            self.manual, self.generated = manual, generated

        def __iter__(self):
            return iter([t for t in (self.manual, self.generated) if t])

        def find_manually_created_transcript(self, codes):
            if self.manual is None:
                raise NoTranscriptFound(VIDEO_ID, codes, [])
            return self.manual

        def find_generated_transcript(self, codes):
            if self.generated is None:
                raise NoTranscriptFound(VIDEO_ID, codes, [])
            return self.generated

    def client(listing):
        return PublicYouTubeCaptionClient(api=SimpleNamespace(list=lambda _vid: listing))

    both = client(Listing(Track("by a person"), Track("by a machine"))).fetch_track(VIDEO_ID, "en")
    assert both.kind == "manual" and both.snippets[0].text == "by a person"
    only_auto = client(Listing(None, Track("by a machine"))).fetch_track(VIDEO_ID, "en")
    assert only_auto.kind == "auto" and only_auto.snippets[0].text == "by a machine"


def test_the_caption_kind_reaches_the_item_from_the_import(tmp_path):
    from writing_coach.media_source_import import MediaSourceImporter

    service, _metadata, _captions = _service(replace(_track(), kind="auto"))
    importer = MediaSourceImporter(service, FileMediaLibraryStore(tmp_path / "idx"), None)
    entry = importer._from_youtube(URL, language="en", imported_by="admin")
    assert entry.source["caption_kind"] == "auto"
    # and the run records it when the candidate cues are used (no second fetch)
    store, world_entry, pipeline = _world(tmp_path / "w", ingestion=Ingestion())
    first = replace(world_entry, processing={"state": "running"}, source={**world_entry.source, "caption_kind": "auto"})
    store.upsert(first)
    lines, origin, *_ = pipeline._transcript(store, None, first, "b1", mtp.Candidate(cues=tuple(_cues())))
    assert origin == ORIGIN_CAPTION and store.get(first.media_id).processing["caption_kind"] == "auto"
    assert pipeline._ingestion.calls == 0


def test_the_stored_payload_origin_and_the_processing_origin_never_disagree(tmp_path):
    # The processing origin used to be written at the very end of a run, the payload when the lesson was stored: a run that
    # ended between them (a failure, a restart) left `provider_caption` beside a `generated_asr` payload, and the player
    # header read "automatic transcript" for what was a human caption.
    store, entry, pipeline = _world(tmp_path, ingestion=Ingestion())
    running = replace(entry, processing={**entry.processing, "state": "running"})
    store.upsert(running)
    cues = [Cue(i * 3000, i * 3000 + 2500, text) for i, text in enumerate(SPOKEN)]
    stored = pipeline._store_lesson(store, running, cues, ORIGIN_ASR, LINES * 3000, status="processing")
    assert stored.lesson["payload"]["transcript_origin"] == ORIGIN_ASR and stored.processing["origin"] == ORIGIN_ASR
    again = pipeline._store_lesson(store, stored, cues, ORIGIN_CAPTION, LINES * 3000, status="processing")
    assert again.lesson["payload"]["transcript_origin"] == again.processing["origin"] == ORIGIN_CAPTION
    from writing_coach.listening_api import _stored_acquisition_response

    assert _stored_acquisition_response(again, again.lesson["payload"])["transcript_origin"] == ORIGIN_CAPTION


# -- 4. a failed reprocess does not destroy a good item ---------------------------------------------------------------


@pytest.mark.parametrize("breakage", ["audio", "crash", "unusable"])
def test_a_failed_reprocess_keeps_the_good_transcript_and_translation(tmp_path, breakage):
    store, before, pipeline = _world(tmp_path, origin=ORIGIN_ASR, ingestion=Ingestion(cues=None), asr=object())
    if breakage == "audio":
        def speech(*_a):
            raise PipelineStop("audio_unavailable")
    elif breakage == "crash":
        def speech(*_a):
            raise RuntimeError("boom")
    else:
        # A transcript is made and fails its checks: it must not replace the one that passed them.
        def speech(*_a):
            return [Cue(0, 500, "Hmm.")], [], "en", 0.001, 1.0, {"filtered": 0, "flagged": 0}
    pipeline._speech = speech
    pipeline.retry(store, None, before.media_id)
    after = store.get(before.media_id)
    expected = {"audio": "audio_unavailable", "crash": "pipeline_error", "unusable": "empty_transcript"}[breakage]
    assert after.lesson == before.lesson
    assert after.processing["state"] == "held" and after.status == "review"  # not `failed`
    assert after.processing["reprocess_reason"] and after.processing["translation_counts"] == before.processing["translation_counts"]
    if breakage != "unusable":
        assert after.processing["reprocess_reason"] == expected


def test_a_first_import_that_fails_is_still_failed(tmp_path):
    store, entry, pipeline = _first_import(tmp_path, Ingestion(cues=None))
    pipeline._speech = lambda *_a: (_ for _ in ()).throw(PipelineStop("audio_unavailable"))
    pipeline._job(store, None, entry.media_id, "b1", None)
    assert store.get(entry.media_id).processing["state"] == "failed"
    assert store.get(entry.media_id).processing["reason"] == "audio_unavailable"


def test_an_item_failed_before_the_rerun_has_no_good_item_to_restore(tmp_path):
    store, entry, pipeline = _world(tmp_path, ingestion=Ingestion(error=MediaImportError(MediaImportCategory.PROVIDER_FAILURE)))
    store.upsert(replace(entry, processing={**entry.processing, "state": "failed", "reason": "audio_unavailable"}, status="review"))
    pipeline._youtube_audio = None
    pipeline.retry(store, None, entry.media_id)
    assert store.get(entry.media_id).processing["state"] == "failed"  # nothing was good: behaviour as before


# -- 5. translate-only retry -----------------------------------------------------------------------------------------


class Cache:
    def __init__(self):
        self.rows = {}

    def get_media_translation(self, key):
        return self.rows.get(key)

    def put_media_translation(self, key, text, provenance, stamp):
        self.rows[key] = {"translated_text": text, "provenance": provenance, "created_at": stamp}


def _translation_world(tmp_path, *, cached: int):
    cache, asked = Cache(), []

    def translate(missing, target):
        asked.append([segment.original_text for segment in missing])
        return TranslatedLines({segment.segment_id: f"vi: {segment.original_text}" for segment in missing})

    def meanings(entry, target):
        transcript = build_transcript(entry.media_id, entry.language, lines_from_payload(entry.lesson["payload"]))
        return resolve_segment_meanings(asset_id=entry.media_id, segments=transcript.segments, support_language=target,
                                        source_language=entry.language, cache=cache, translate=translate, provider_model="m")

    store, entry, pipeline = _world(tmp_path, ingestion=Ingestion(), meanings=meanings)
    first = [seg for seg in build_transcript(entry.media_id, "en", lines_from_payload(entry.lesson["payload"])).segments][:cached]
    from writing_coach.media_meaning import cache_key

    for seg in first:
        cache.put_media_translation(cache_key(entry.media_id, seg.segment_id, seg.original_text, "vi", "m"), f"vi: {seg.original_text}", PROVENANCE_GENERATED, "t")
    return store, entry, pipeline, asked


def test_translate_only_requests_just_the_missing_lines_and_never_touches_the_transcript(tmp_path):
    store, before, pipeline, asked = _translation_world(tmp_path, cached=3)
    pipeline._asr = Asr()
    pipeline._ingestion = Ingestion(error=AssertionError("captions were fetched"))
    assert pipeline.retry_translation(store, before.media_id) == "queued"
    assert asked == [SPOKEN[3:]]  # five lines, the five without a meaning
    after = store.get(before.media_id)
    assert after.lesson == before.lesson and after.status == before.status and after.duration_ms == before.duration_ms
    processing = after.processing
    assert processing["state"] == "held" and processing["reason"] == "rights_unknown" and processing["origin"] == ORIGIN_CAPTION
    assert processing["translation"] == "ready" and processing["translation_counts"] == {"vi": {"done": LINES, "total": LINES}}
    assert processing["translation_continuation"] == {} and processing["caption_kind"] == "manual"


def test_translate_only_asks_again_after_the_automatic_continuation_ended(tmp_path):
    store, before, pipeline, asked = _translation_world(tmp_path, cached=2)
    store.update_if_present(before.media_id, lambda e: replace(e, processing={**e.processing, "translation": "failed", "translation_reason": "rate_limited", "translation_continuation": {}}))
    assert pipeline.retry_translation(store, before.media_id) == "queued"
    assert len(asked) == 1 and len(asked[0]) == LINES - 2


def test_translate_only_refuses_a_busy_missing_or_transcriptless_item(tmp_path):
    store, entry, pipeline, asked = _translation_world(tmp_path, cached=3)
    store.update_if_present(entry.media_id, lambda e: replace(e, processing={**e.processing, "state": "running"}))
    assert pipeline.retry_translation(store, entry.media_id) == "busy"
    assert pipeline.retry_translation(store, "no-such-item") == "missing"
    store.update_if_present(entry.media_id, lambda e: replace(e, processing={**e.processing, "state": "held"}, lesson=None))
    assert pipeline.retry_translation(store, entry.media_id) == "no_transcript"
    assert asked == []


def test_translate_only_stays_under_the_spend_cap(tmp_path):
    from writing_coach.media_spend import SpendCapReached

    store, entry, pipeline, asked = _translation_world(tmp_path, cached=3)

    class Capped(_Ledger):
        def check(self, *_a, **_k):
            raise SpendCapReached("spend_cap_batch_ai", limit=1.0, spent=1.0, scope="batch")

    pipeline._ledger = Capped()
    pipeline.retry_translation(store, entry.media_id)
    assert asked == [] and store.get(entry.media_id).processing["translation_reason"] == "spend_cap"
    assert store.get(entry.media_id).processing["state"] == "held"


def test_the_reprocess_route_takes_a_translation_scope(monkeypatch):
    from fastapi.testclient import TestClient  # noqa: F401  (the route is exercised through its function)
    from writing_coach import admin_console_api, media_library_api

    seen = []
    monkeypatch.setattr(media_library_api, "retry_translation", lambda media_id: seen.append(media_id) or "busy")
    monkeypatch.setattr(admin_console_api, "_admin", lambda request: SimpleNamespace(user_key="a"))
    monkeypatch.setattr(admin_console_api, "_same_origin", lambda request: None)
    monkeypatch.setattr(admin_console_api, "_no_store", lambda response: None)
    entry = replace(_entry("m1"), library="shared")
    monkeypatch.setattr(admin_console_api._state, "media_store", SimpleNamespace(get=lambda media_id: entry), raising=False)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as busy:
        admin_console_api.reprocess_media("m1", SimpleNamespace(), SimpleNamespace(), scope="translation")
    assert busy.value.status_code == 409 and seen == ["m1"]
    with pytest.raises(HTTPException) as bad:
        admin_console_api.reprocess_media("m1", SimpleNamespace(), SimpleNamespace(), scope="everything")
    assert bad.value.status_code == 422


# -- 6. the translation source label ------------------------------------------------------------------------------------


def _outcome(*provenances, calls=0):
    meanings = tuple(SegmentMeaning(f"s{i}", "vi", "x", p) for i, p in enumerate(provenances))
    return MeaningOutcome(meanings, "ready", calls)


def test_the_translation_source_is_the_real_one():
    assert translation_source_provider(_outcome(PROVENANCE_EDITORIAL, PROVENANCE_EDITORIAL)) == "curated-editorial"
    assert translation_source_provider(_outcome(PROVENANCE_GENERATED, calls=1)) == "media-translation"
    # Generated earlier and read from the cache: no call now, still not editorial.
    assert translation_source_provider(_outcome(PROVENANCE_CACHED_GENERATED, PROVENANCE_CACHED_GENERATED)) == "media-translation"
    assert translation_source_provider(_outcome(PROVENANCE_EDITORIAL, PROVENANCE_CACHED_GENERATED)) == "media-translation"


# -- review of #226: P2-1 re-arm after a restore, P2-3 stale snapshot, funding of the continuation -------------------------


def test_a_restore_re_arms_the_translation_continuation_it_brings_back(tmp_path):
    store, before, pipeline = _world(tmp_path, origin=ORIGIN_ASR, ingestion=Ingestion(cues=None), asr=object())
    record = {"attempt": 1, "max_attempts": 6, "next_at": "2026-10-15T00:00:00Z", "deadline": "2026-10-16T00:00:00Z"}
    store.update_if_present(before.media_id, lambda e: replace(e, processing={**e.processing, "translation": "deferred", "translation_continuation": record}))
    scheduled = []
    pipeline._schedule = lambda delay, callback: scheduled.append((delay, callback))
    pipeline._speech = lambda *_a: (_ for _ in ()).throw(PipelineStop("audio_unavailable"))
    pipeline.retry(store, None, before.media_id)
    after = store.get(before.media_id)
    assert after.processing["translation_continuation"] == record and after.processing["reprocess_reason"] == "audio_unavailable"
    assert len(scheduled) == 1  # the restored record has a timer again


def test_a_run_cancelled_by_archive_leaves_no_snapshot_behind(tmp_path):
    store, before, pipeline = _world(tmp_path, ingestion=Ingestion(error=MediaImportError(MediaImportCategory.PROVIDER_FAILURE)))
    pipeline._remember_previous(store, before)
    assert store.get(before.media_id).processing.get("previous")
    store.update_if_present(before.media_id, lambda e: replace(e, status="archived", processing={**e.processing, "state": "cancelled"}))
    pipeline._hold_failed(store, before.media_id, PipelineStop("cancelled"))
    assert not store.get(before.media_id).processing.get("previous")


def test_the_deferred_continuation_runs_under_the_media_pipeline_funding(tmp_path, monkeypatch):
    from contextlib import contextmanager

    active = []

    @contextmanager
    def funding(name):
        active.append(name)
        try:
            yield
        finally:
            active.pop()

    seen = []

    def meanings(entry, target):
        seen.append(list(active))
        return SimpleNamespace(status="ready", meanings=[object()] * LINES, provider_calls=1, reason="", retry_after=0.0)

    monkeypatch.setattr(mtp, "system_funding", funding)
    store, entry, pipeline = _world(tmp_path, ingestion=Ingestion(), meanings=meanings)
    store.update_if_present(entry.media_id, lambda e: replace(e, processing={**e.processing, "translation": "deferred", "translation_continuation": {
        "attempt": 1, "max_attempts": 6, "next_at": "2026-10-15T00:00:00Z", "deadline": "2999-01-01T00:00:00Z"}}))
    pipeline._continuation_job(store, entry.media_id)
    assert seen and all(names == ["media_pipeline"] for names in seen)
