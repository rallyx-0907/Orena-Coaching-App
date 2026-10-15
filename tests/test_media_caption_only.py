"""Caption-only imports never fall back to ASR; the continuation arms on the ASR path (D-214, PROPOSED).

Evidence: the 2026-10-15 EN caption batch, attempt 2. The caption fetch of `youtube-LlhdnpsADZs` was refused (HTTP 429), the
importer fell back to Groq Whisper on its own and the operator had no way to refuse that. After ASR the translation ended
`partial 72/114 rate_limited` and `translation_continuation` stayed `{}`: the provider's 429 asked for 521 s and D-211 never
scheduled a wait over 300 s, though the continuation's own budget is 30 minutes.
Providers here are fakes; nothing reaches a network, a downloader or a speech recogniser."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from tests.test_media_caption_path import Asr, Ingestion, _cues, _world
from writing_coach import media_transcript_pipeline as mtp
from writing_coach.media_ingestion import MediaImportCategory, MediaImportError
from writing_coach.media_library_api import MediaImportIn, MediaImportItemIn
from writing_coach.media_segmentation import Cue
from writing_coach.media_source_import import MediaSourceImporter


class SpyLedger:
    """Records every spend; a caption-only stop must record none."""

    def __init__(self):
        self.recorded: list[tuple] = []
        self.checked: list[tuple] = []

    def check(self, *args, **_kwargs):
        self.checked.append(args)

    def record(self, *args, **kwargs):
        self.recorded.append((args, kwargs))

    def asr_estimate(self, _seconds):
        return 0.01

    def ai_usd_per_million_tokens(self):
        return 0.1


class Audio:
    """The yt-dlp audio download: counted, and it fails like a throttled provider."""

    def __init__(self):
        self.calls = 0

    def __call__(self, *_args, **_kwargs):
        self.calls += 1
        raise RuntimeError("audio refused")


def _first_import(tmp_path, ingestion, *, policy=None, state_source=None, asr=None, meanings=None):
    store, entry, pipeline = _world(tmp_path, ingestion=ingestion, asr=asr if asr is not None else Asr(), meanings=meanings)
    audio, ledger = Audio(), SpyLedger()
    pipeline._youtube_audio, pipeline._ledger = audio, ledger
    source = {**entry.source, **(state_source or {})}
    if policy:
        source[mtp.SOURCE_TRANSCRIPT_POLICY] = policy
    first = replace(entry, status="processing", processing={"state": "running"}, source=source, lesson=None)
    store.upsert(first)
    return store, first, pipeline, audio, ledger


# -- 1. captions_only ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("ingestion, source, expected", [
    (Ingestion(error=MediaImportError(MediaImportCategory.PROVIDER_FAILURE)), {}, "captions_unavailable"),  # the 429
    (Ingestion(error=MediaImportError(MediaImportCategory.PROVIDER_TIMEOUT)), {}, "captions_unavailable"),
    (Ingestion(cues=None), {"caption_status": "unavailable"}, "captions_unavailable"),  # the importer was refused earlier
    (Ingestion(cues=None), {}, "captions_unavailable"),  # the video has no track
    (Ingestion(cues=[Cue(0, 900, "Hi.")]), {}, "captions_unusable"),  # fetched, but not enough of the recording
])
def test_captions_only_stops_before_any_audio_or_asr_and_spends_nothing(tmp_path, ingestion, source, expected):
    store, entry, pipeline, audio, ledger = _first_import(
        tmp_path, ingestion, policy=mtp.POLICY_CAPTIONS_ONLY, state_source=source)
    pipeline._run(store, None, entry.media_id, "b1", None)
    stored = store.get(entry.media_id)
    assert stored.processing["state"] == "failed" and stored.processing["reason"] == expected
    assert stored.processing["message"] and stored.status == "review"  # honest, visible, retryable by reprocess
    assert audio.calls == 0 and ledger.recorded == [] and ledger.checked == []
    assert stored.lesson is None  # no transcript was made


def test_captions_only_does_not_touch_the_audio_for_model_clips_when_the_transcript_step_fails(tmp_path, monkeypatch):
    # A cleared or personal item cuts model clips from the audio after readiness; a stopped transcript never reaches it.
    store, entry, pipeline, audio, _ledger = _first_import(
        tmp_path, Ingestion(error=MediaImportError(MediaImportCategory.PROVIDER_FAILURE)), policy=mtp.POLICY_CAPTIONS_ONLY,
        state_source={"rights": "cleared"})
    pipeline._run(store, None, entry.media_id, "b1", None)
    assert store.get(entry.media_id).processing["state"] == "failed" and audio.calls == 0


def test_captions_only_with_good_captions_is_the_normal_caption_import(tmp_path):
    store, entry, pipeline, audio, ledger = _first_import(
        tmp_path, Ingestion(cues=_cues(), provenance={"caption_kind": "manual"}), policy=mtp.POLICY_CAPTIONS_ONLY)
    pipeline._run(store, None, entry.media_id, "b1", None)
    processing = store.get(entry.media_id).processing
    assert processing["origin"] == mtp.ORIGIN_CAPTION and processing["state"] == "held"
    assert audio.calls == 0 and ledger.recorded == []


def test_the_default_policy_still_falls_back_to_asr_and_says_so(tmp_path):
    asr_cues = [Cue(i * 3000, i * 3000 + 2500, text) for i, text in enumerate(t.text for t in _cues())]
    for policy in (None, mtp.POLICY_DEFAULT):
        store, entry, pipeline, audio, _ledger = _first_import(
            tmp_path / str(policy), Ingestion(error=MediaImportError(MediaImportCategory.PROVIDER_FAILURE)), policy=policy)
        pipeline._speech = lambda *_a: (asr_cues, [], "en", 0.002, 8.0, {"filtered": 0, "flagged": 0})
        pipeline._run(store, None, entry.media_id, "b1", None)
        processing = store.get(entry.media_id).processing
        assert processing["origin"] == mtp.ORIGIN_ASR and processing["caption_fallback"] == "captions_unavailable"


def test_captions_only_is_kept_when_the_item_is_reprocessed(tmp_path):
    store, entry, pipeline, audio, _ledger = _first_import(
        tmp_path, Ingestion(error=MediaImportError(MediaImportCategory.PROVIDER_FAILURE)), policy=mtp.POLICY_CAPTIONS_ONLY)
    pipeline._run(store, None, entry.media_id, "b1", None)
    pipeline._run(store, None, entry.media_id, "b2", None)  # a re-run reads the item's own policy
    assert store.get(entry.media_id).processing["reason"] == "captions_unavailable" and audio.calls == 0


# -- 1b. the API carries the option ----------------------------------------------------------------------------------


def test_the_import_models_take_the_policy_and_refuse_an_unknown_one():
    assert MediaImportItemIn(url="https://x.test/a").transcript_policy is None
    assert MediaImportIn(items=[]).transcript_policy is None
    assert MediaImportIn(transcript_policy="captions_only", items=[]).transcript_policy == "captions_only"
    with pytest.raises(ValidationError):
        MediaImportIn(transcript_policy="whatever", items=[])
    with pytest.raises(ValidationError):
        MediaImportItemIn(url="https://x.test/a", transcript_policy="asr_only")


def test_the_importer_stores_the_policy_on_a_youtube_item_only_and_an_item_overrides_the_batch(tmp_path):
    store, entry, _pipeline = _world(tmp_path)
    importer = MediaSourceImporter.__new__(MediaSourceImporter)
    bare = replace(entry, source={k: v for k, v in entry.source.items() if k != mtp.SOURCE_TRANSCRIPT_POLICY})
    stored = importer._apply_overrides(bare, {"transcript_policy": "captions_only"})
    assert stored.source[mtp.SOURCE_TRANSCRIPT_POLICY] == "captions_only"
    unchanged = importer._apply_overrides(bare, {})
    assert mtp.SOURCE_TRANSCRIPT_POLICY not in unchanged.source  # absent means the default
    upload = replace(bare, provider="upload")
    assert mtp.SOURCE_TRANSCRIPT_POLICY not in importer._apply_overrides(upload, {"transcript_policy": "captions_only"}).source

    from writing_coach.media_library_api import _items_with_policy

    items = _items_with_policy(MediaImportIn(transcript_policy="captions_only", items=[
        {"url": "https://a.test/1"}, {"url": "https://a.test/2", "transcript_policy": "captions_or_asr"}]))
    assert [item["transcript_policy"] for item in items] == ["captions_only", "captions_or_asr"]
    assert _items_with_policy(MediaImportIn(items=[{"url": "https://a.test/1"}]))[0]["transcript_policy"] is None


# -- 2. the continuation arms on the ASR-fallback path ---------------------------------------------------------------


def test_a_rate_limited_translation_whose_429_asks_for_521_seconds_arms_the_continuation_on_the_asr_path(tmp_path, monkeypatch):
    """The exact shape of youtube-LlhdnpsADZs: caption fetch refused, ASR fallback, 72 of 114 translated, Retry-After 521 s."""
    total, calls = 114, {"n": 0}

    def meanings(_entry, _target):  # about 63% of the stored lines, as 72 of 114 was
        calls["n"] += 1
        stored = len(mtp.lines_from_payload((_entry.lesson or {}).get("payload")))
        return SimpleNamespace(status="partial", meanings=[object()] * (stored * 72 // total), provider_calls=1,
                               reason="rate_limited", retry_after=521.0)

    store, entry, pipeline, audio, _ledger = _first_import(
        tmp_path, Ingestion(error=MediaImportError(MediaImportCategory.PROVIDER_FAILURE)), meanings=meanings)
    asr_cues = [Cue(i * 3000, i * 3000 + 2500, f"Spoken sentence number {i} of the recording.") for i in range(total)]
    pipeline._speech = lambda *_a: (asr_cues, [], "en", 0.0066, 594.8, {"filtered": 0, "flagged": 0})
    pipeline._sleep = lambda _s: None
    scheduled: list[tuple[float, object]] = []
    pipeline._schedule = lambda delay, callback: scheduled.append((delay, callback))
    pipeline._clock = lambda: 1_000_000.0
    pipeline._run(store, None, entry.media_id, "b1", None)
    stored = store.get(entry.media_id).processing
    assert stored["origin"] == mtp.ORIGIN_ASR and stored["caption_fallback"] == "captions_unavailable"
    assert stored["state"] == "held"  # the item itself is untouched
    assert stored["translation"] == "deferred" and stored["translation_reason"] == "rate_limited"
    assert stored["translation_continuation"]["attempt"] == 1 and stored["translation_continuation"]["retry_after"] == 521.0
    assert 521.0 <= mtp.CONTINUATION_MAX_DELAY
    assert [delay for delay, _ in scheduled] == [521.0]  # the provider's own wait, inside CONTINUATION_MAX_DELAY and the 30 minute budget
