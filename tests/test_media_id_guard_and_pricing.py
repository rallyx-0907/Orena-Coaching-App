"""YouTube ids that start with "-", ids validated before any paid call, a caption reject that names its check, and media AI
spend rated per model (D-218, PROPOSED).

Trial evidence (2026-10-15 sitting 2): `-anLfV9mZJY` ended `import_failed` with `provider_media_id is invalid` after the
Supadata request was spent; `captions_unusable` (242 cues fetched) named no reason; the ledger booked every
`qwen/qwen3.8-27b` event at $0. Fakes only; nothing reaches a network."""
from __future__ import annotations


import pytest

from tests.test_media_caption_only import _first_import
from tests.test_media_caption_path import Ingestion
from tests.test_media_caption_source import FakeSupadata, client_for, transcript
from tests.test_media_lifecycle import _entry
from writing_coach import media_transcript_pipeline as mtp
from writing_coach import policies
from writing_coach.admin_content import media_outcome
from writing_coach.media_ingestion import ProviderUrlMalformed
from writing_coach.media_library_store import validate_entry, valid_provider_media_id
from writing_coach.media_providers.youtube import (
    canonical_youtube_url, is_youtube_video_id, parse_youtube_video_id,
)
from writing_coach.media_providers.youtube_audio import probe_youtube_duration
from writing_coach.media_segmentation import Cue

DASH_ID = "-anLfV9mZJY"


# ---- 2. ids -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("video_id", [DASH_ID, "_abcdefghij", "-----------", "abc-DEF_123", "dQw4w9WgXcQ"])
def test_a_real_youtube_id_is_accepted_everywhere_including_a_leading_dash(video_id):
    assert is_youtube_video_id(video_id)
    assert parse_youtube_video_id(f"https://www.youtube.com/watch?v={video_id}") == video_id
    assert parse_youtube_video_id(f"https://youtu.be/{video_id}") == video_id
    entry = _entry(media_id=f"youtube-{video_id}", provider="youtube", provider_media_id=video_id, media_type="video")
    assert validate_entry(entry).provider_media_id == video_id


@pytest.mark.parametrize("bad", ["", "short", "twelve_chars!", "has space1234", "a" * 12, "ab/cdefghij", "ab.cdefghij", "-" * 12])
def test_what_is_not_a_youtube_id_is_still_refused(bad):
    assert not is_youtube_video_id(bad)
    with pytest.raises(ProviderUrlMalformed):
        parse_youtube_video_id(f"https://www.youtube.com/watch?v={bad}")


def test_only_a_youtube_row_may_start_with_a_dash_and_the_other_ids_keep_their_shape():
    assert valid_provider_media_id("youtube", DASH_ID)
    assert not valid_provider_media_id("upload", DASH_ID)
    assert not valid_provider_media_id("upload", "_x")
    assert valid_provider_media_id("upload", "sample-one")
    with pytest.raises(ValueError, match="provider_media_id is invalid"):
        validate_entry(_entry(provider_media_id=DASH_ID))
    with pytest.raises(ValueError, match="media_id is invalid"):
        validate_entry(_entry(media_id="-x", provider="youtube", provider_media_id=DASH_ID))


def test_a_leading_dash_never_reaches_a_downloader_as_an_option():
    """yt-dlp is driven as a library with a full URL, never with the bare id; the URL starts with a scheme."""
    url = canonical_youtube_url(DASH_ID)
    assert url == f"https://www.youtube.com/watch?v={DASH_ID}" and not url.startswith("-")
    seen: list[str] = []

    class Ydl:
        def __init__(self, options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def extract_info(self, source, download=False):
            seen.append(source)
            return {"duration": 61}

    assert probe_youtube_duration(url, ydl_factory=Ydl) == 61.0
    assert seen == [url]


def test_an_id_the_library_would_refuse_is_refused_before_a_supadata_request_is_reserved(tmp_path):
    for bad in ("short", "bad id with spaces", "../etc/passwd", "a" * 12):
        supadata = FakeSupadata(transcript())
        client, _youtube, ledger = client_for(tmp_path / bad.replace("/", "_").replace(" ", "_"), "supadata_native", supadata=supadata)
        with pytest.raises(ProviderUrlMalformed):
            client.fetch_track(bad, "en")
        assert supadata.calls == [] and ledger.requests_today() == 0   # no request sent, none counted against the day


def test_a_leading_dash_id_reserves_and_asks_with_the_full_url(tmp_path):
    supadata = FakeSupadata(transcript())
    client, _youtube, ledger = client_for(tmp_path, "supadata_native", supadata=supadata)
    track = client.fetch_track(DASH_ID, "en")
    assert track is not None and ledger.requests_today() == 1
    assert supadata.calls[0][0] == f"https://www.youtube.com/watch?v={DASH_ID}"


# ---- 3. a caption reject names its check -------------------------------------------------------------------------------

def _many_fast_cues(count=242):
    # Every cue is far too many characters for its time: the `segments` check refuses it, after 242 cues were fetched.
    return [Cue(i * 1000, i * 1000 + 100, "this is a rather long line of caption text that cannot be read in a tenth of a second") for i in range(count)]


def test_captions_unusable_records_the_failing_check_and_its_counts(tmp_path):
    store, entry, pipeline, audio, ledger = _first_import(
        tmp_path, Ingestion(cues=_many_fast_cues()), policy=mtp.POLICY_CAPTIONS_ONLY)
    pipeline._run(store, None, entry.media_id, "b1", None)
    stored = store.get(entry.media_id)
    assert stored.processing["reason"] == "captions_unusable"
    detail = stored.processing["detail"]
    assert detail.startswith("segments:") and "242 captions" in detail and "lines" in detail
    shown = media_outcome(stored)
    assert shown["reason"] == "captions_unusable" and shown["detail"] == detail   # the admin's existing reason line carries it
    assert audio.calls == 0 and ledger.recorded == []


def test_a_detail_is_only_shown_for_the_reason_that_has_one(tmp_path):
    store, entry, pipeline, _audio, _ledger = _first_import(
        tmp_path, Ingestion(cues=None), policy=mtp.POLICY_CAPTIONS_ONLY)
    pipeline._run(store, None, entry.media_id, "b1", None)
    shown = media_outcome(store.get(entry.media_id))
    assert shown["reason"] == "captions_unavailable" and shown["detail"] == ""


def test_the_check_detail_is_ids_and_numbers_only():
    checks = [{"id": "non_empty", "pass": True, "detail": "9 units"}, {"id": "coverage", "pass": False, "detail": "0.12"},
              {"id": "segments", "pass": False, "detail": "5 lines"}]
    assert mtp.caption_check_detail(checks, 5, 5) == "coverage: 0.12; 5 captions, 5 lines"
    assert mtp.caption_check_detail([{"id": "x", "pass": True, "detail": ""}], 1, 1) == ""


# ---- 4. media AI spend is rated per model ------------------------------------------------------------------------------

def _pipeline(tmp_path):
    from tests.test_media_import_pipeline_reasons import _world
    from writing_coach.media_spend import SpendLedger

    _store, _entry_, pipeline = _world(tmp_path)
    pipeline._ledger = SpendLedger(tmp_path / "spend.json")
    return pipeline


def test_qwen_is_rated_at_its_published_price_not_zero(tmp_path):
    pipeline = _pipeline(tmp_path)
    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}
    assert pipeline._ai_cost("qwen/qwen3.8-27b", usage) == pytest.approx(0.80 + 4.00)
    small = pipeline._ai_cost("qwen/qwen3.8-27b", {"prompt_tokens": 383, "completion_tokens": 596})
    assert small == pytest.approx((383 * 0.80 + 596 * 4.00) / 1_000_000) and small > 0
    assert policies.media_ai_model_rate("qwen/qwen3.8-27b") == (0.80, 4.00)


def test_other_models_keep_their_catalogue_price_and_an_unlisted_one_gets_the_flat_default_never_zero(tmp_path):
    pipeline = _pipeline(tmp_path)
    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}
    assert pipeline._ai_cost("openai/gpt-oss-120b", usage) == pytest.approx(0.15 + 0.60)
    flat = float(policies.value("media.ai_usd_per_million_tokens"))
    assert flat > 0
    assert pipeline._ai_cost("some/unlisted-model", usage) == pytest.approx(2_000_000 / 1_000_000 * flat)
    # A catalogue entry recorded at zero (a free-plan fact for another capability) does not zero the media ledger.
    assert pipeline._ai_cost("llama-3.1-8b-instant", usage) == pytest.approx(2.0 * flat)


def test_a_qwen_call_counts_against_the_cap(tmp_path):
    from writing_coach.media_spend import KIND_AI, SpendCapReached

    pipeline = _pipeline(tmp_path)
    cost = pipeline._ai_cost("qwen/qwen3.8-27b", {"prompt_tokens": 400, "completion_tokens": 650})
    assert cost > 0
    pipeline._ledger.record(KIND_AI, cost, batch_id="b1", units=1, provider="groq")
    with pytest.raises(SpendCapReached):
        pipeline._ledger.check(KIND_AI, "b1", pipeline._ledger.limits()[KIND_AI])
