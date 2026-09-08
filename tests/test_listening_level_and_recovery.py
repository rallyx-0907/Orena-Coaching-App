"""L3 importer: no-caption classification and the development level estimate.

Two things this protects.

A playable source that simply has no captions is VALID MEDIA. Before L3 it was
counted as MISSING_TRANSCRIPT, which reads in a report as "this source is no
good" — the same mistake D-042 corrected in the product, resurfacing in the
importer's vocabulary. It must be RECOVERY_REQUIRED, and it must not cost paid
provider quota during a bulk run.

And a catalog where every EN lesson is B1 and every ZH lesson is HSK3 is not a
levelled catalog; it is one fallback repeated. The estimator has to actually
separate easy media from hard media, using only evidence the transcript really
carries.
"""

from __future__ import annotations

from writing_coach.listening_source_import import (
    ACCEPTED,
    MEDIA_UNAVAILABLE,
    MISSING_TRANSCRIPT,
    RECOVERY_REQUIRED,
    ImportReport,
    SourceCandidate,
    build_dev_catalog,
    estimate_level,
)
from writing_coach.media_ingestion import (
    MediaAcquisition,
    MediaPlayback,
    ProviderSourceUnavailable,
)
from writing_coach.media_learning import (
    MediaLearningAsset,
    MediaLearningObject,
    MediaProcessingState,
    MediaTranscript,
    TranscriptSegment,
)

VIDEO = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def candidate(**over) -> SourceCandidate:
    base = dict(
        candidate_id="en-001", language="en", category="conversation",
        source_family="Test", title="A lesson", source_url=VIDEO,
        desired_excerpt_count=3, min_excerpt_seconds=20, max_excerpt_seconds=90,
        preferred_modes=("listen", "dictation"), level_hint="", notes="",
    )
    base.update(over)
    return SourceCandidate(**base)


def acquisition(segments, *, playable: bool = True,
                transcript_status: str = "") -> MediaAcquisition:
    asset = MediaLearningAsset(
        asset_id="youtube:dQw4w9WgXcQ", source_url=VIDEO, source_provider="youtube",
        source_type="external-video", title="A lesson", source_language="en",
        processing_state=MediaProcessingState.READY,
        transcript_available=bool(segments),
    )
    transcript = None
    if segments:
        transcript = MediaTranscript(
            asset_id=asset.asset_id, source_language="en", segments=tuple(segments))
    return MediaAcquisition(
        media_object=MediaLearningObject(asset=asset, transcript=transcript),
        playback=MediaPlayback(
            provider="youtube", kind="embed",
            url="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ" if playable else "",
        ),
        transcript_status=transcript_status or ("native" if segments else "absent"),
    )


class Adapter:
    """Counts everything it is asked to do, so paid work is visible."""

    def __init__(self, result) -> None:
        self.result = result
        self.acquire_calls = 0
        self.recovery_calls = 0

    def acquire(self, url, language):
        self.acquire_calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def fetch_metadata(self, url):
        class Meta:
            author_name = "A channel"
            thumbnail_url = "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
        return Meta()

    def recover_transcript(self, *args, **kwargs):  # pragma: no cover - must not run
        self.recovery_calls += 1
        raise AssertionError("bulk import must not start paid transcript recovery")


def segments(count: int, *, words: str = "this is a simple line of speech",
             seconds: int = 5) -> list[TranscriptSegment]:
    return [
        TranscriptSegment(f"s:{i:03d}", i, i * seconds * 1000, (i + 1) * seconds * 1000, words)
        for i in range(count)
    ]


def rows(*args, **kwargs) -> list[dict]:
    """The dict shape `_segments_of()` hands the estimator inside the pipeline."""

    return [
        {"segment_id": s.segment_id, "order": s.order, "start_ms": s.start_ms,
         "end_ms": s.end_ms, "original_text": s.original_text}
        for s in segments(*args, **kwargs)
    ]


# --- a playable source with no captions is valid media -----------------------

def test_playable_source_without_captions_is_recovery_required() -> None:
    adapter = Adapter(acquisition([], playable=True))
    report = ImportReport()
    manifest, report = build_dev_catalog([candidate()], adapter, report)
    summary = report.as_dict()

    assert summary[RECOVERY_REQUIRED] == 1, "playable, caption-less media is not a failure"
    assert summary[MISSING_TRANSCRIPT] == 0
    assert summary[MEDIA_UNAVAILABLE] == 0, "the media is available; only the transcript is not"

    detail = summary["entries"][0]["detail"].lower()
    assert "recovery" in detail
    for forbidden in ("unsupported", "invalid", "unavailable"):
        assert forbidden not in detail, f"a caption-less source must not be called {forbidden}"

    # And crucially it cost nothing: no paid recovery was started for it.
    assert adapter.recovery_calls == 0


def test_no_playback_and_no_transcript_stays_missing_transcript() -> None:
    """The distinction is real, not a rename: unplayable media is still not valid."""

    adapter = Adapter(acquisition([], playable=False))
    _, report = build_dev_catalog([candidate()], adapter, ImportReport())
    summary = report.as_dict()
    assert summary[MISSING_TRANSCRIPT] == 1
    assert summary[RECOVERY_REQUIRED] == 0


def test_unavailable_media_is_still_media_unavailable() -> None:
    adapter = Adapter(ProviderSourceUnavailable())
    _, report = build_dev_catalog([candidate()], adapter, ImportReport())
    summary = report.as_dict()
    assert summary[MEDIA_UNAVAILABLE] == 1
    assert summary[RECOVERY_REQUIRED] == 0


def test_every_candidate_is_accounted_for() -> None:
    """No silent drops: the outcome total equals the input count."""

    adapter = Adapter(acquisition(segments(30)))
    candidates = [candidate(candidate_id=f"en-{i:03d}") for i in range(5)]
    _, report = build_dev_catalog(candidates, adapter, ImportReport())
    summary = report.as_dict()
    assert summary["TOTAL_OUTCOMES"] == len(candidates)
    assert len(summary["entries"]) == len(candidates)
    assert all(entry["language"] == "en" for entry in summary["entries"])


# --- the level estimate separates easy media from hard media ----------------

def test_slow_simple_speech_estimates_lower_than_dense_fast_speech() -> None:
    easy = rows(20, words="I like cats. Do you like cats?", seconds=10)
    hard = rows(20, words=(
        "Consequently the administration's unprecedented reallocation of "
        "infrastructural expenditure demonstrably exacerbated macroeconomic "
        "volatility throughout successive parliamentary deliberations"), seconds=4)

    easy_level, easy_evidence = estimate_level(candidate(), easy, 200_000)
    hard_level, hard_evidence = estimate_level(candidate(), hard, 80_000)

    ladder = ("A1", "A2", "B1", "B2", "C1", "C2")
    assert ladder.index(easy_level) < ladder.index(hard_level), (
        f"the estimator must separate these: {easy_level} vs {hard_level}")

    # The evidence is real numbers a reviewer can check, not a bare label.
    assert easy_evidence["source"] == "importer-heuristic-v1"
    assert set(easy_evidence["signals"]) == {
        "words_per_minute", "words_per_segment", "long_word_ratio"}
    assert easy_evidence["signals"]["words_per_minute"] > 0
    assert hard_evidence["signals"]["long_word_ratio"] > \
        easy_evidence["signals"]["long_word_ratio"]


def test_chinese_uses_hanzi_evidence_and_the_hsk_ladder() -> None:
    zh = candidate(candidate_id="zh-001", language="zh")
    easy_level, evidence = estimate_level(zh, rows(20, words="我很好。你呢？", seconds=10), 200_000)
    hard_level, _ = estimate_level(
        zh,
        rows(20, words="随着城市化进程不断推进，基础设施投资结构性失衡问题日益凸显", seconds=4),
        80_000)

    ladder = ("HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6", "HSK7-9")
    assert easy_level in ladder and hard_level in ladder
    assert ladder.index(easy_level) < ladder.index(hard_level)
    assert set(evidence["signals"]) == {
        "characters_per_minute", "characters_per_segment", "distinct_character_ratio"}


def test_the_estimate_never_claims_to_be_reviewed() -> None:
    adapter = Adapter(acquisition(segments(30)))
    manifest, _ = build_dev_catalog([candidate()], adapter, ImportReport())

    for lesson in manifest["lessons"]:
        assert lesson["reviewed_level"] is None, "nothing here has been reviewed"
        assert lesson["estimated_level"]
        evidence = lesson["level_evidence"]
        assert evidence["confidence"] == "low"
        assert "not reviewed" in evidence["review_note"]


def test_a_human_level_hint_wins_over_the_estimate() -> None:
    level, evidence = estimate_level(candidate(level_hint="C1"), rows(20), 200_000)
    assert level == "C1"
    assert evidence["source"] == "human-source-list"


def test_a_transcript_with_no_usable_text_says_it_is_a_fallback() -> None:
    """The fallback still exists — it just has to admit what it is.

    A real case: a row declared `zh` whose captions came back in Latin script,
    so there is no Hanzi to measure. The estimator must not pretend to have
    measured something.
    """

    zh = candidate(candidate_id="zh-009", language="zh")
    level, evidence = estimate_level(zh, rows(5, words="no hanzi here at all"), 60_000)
    assert level == "HSK3"
    assert evidence["source"] == "fallback"
    assert "not a measurement" in evidence["review_note"]
    assert "signals" not in evidence, "a fallback must not present fabricated evidence"


def test_the_estimate_is_deterministic() -> None:
    """Re-running the importer must not churn levels."""

    text = rows(20, words="A moderately complicated sentence about weather patterns")
    first = estimate_level(candidate(), text, 120_000)
    second = estimate_level(candidate(), text, 120_000)
    assert first == second


def test_the_report_counts_levels_and_topics_per_language() -> None:
    adapter = Adapter(acquisition(segments(30)))
    _, report = build_dev_catalog([candidate()], adapter, ImportReport())
    summary = report.as_dict()

    assert summary[ACCEPTED] == 1
    assert summary["generated_by_language"]["en"] == summary["GENERATED_LESSONS"]
    assert sum(summary["levels_by_language"]["en"].values()) == summary["GENERATED_LESSONS"]
    assert sum(summary["topics_by_language"]["en"].values()) == summary["GENERATED_LESSONS"]
    assert sum(summary["excerpts_per_source"].values()) == 1


# --- a failed caption request is not a source without captions ---------------

def test_a_failed_caption_probe_is_not_reported_as_having_no_captions() -> None:
    """The defect this caught in the real L3 run.

    Deferred recovery means a missing transcript is not fatal. It swallowed a
    failed caption REQUEST too, so a provider throttling a 200-source burst
    produced 54 sources labelled "no captions" that in fact had captions in the
    right language. Those sources would have been dropped from the catalog on
    the strength of a network error.
    """

    adapter = Adapter(acquisition([], playable=True, transcript_status="probe_failed"))
    _, report = build_dev_catalog([candidate()], adapter, ImportReport())
    summary = report.as_dict()

    assert summary[RECOVERY_REQUIRED] == 0,         "a throttled request must not be recorded as a source with no captions"
    assert summary[MISSING_TRANSCRIPT] == 1
    detail = summary["entries"][0]["detail"]
    assert "retry" in detail, "the report must say this is unresolved, not decided"


def test_a_genuinely_captionless_source_is_still_recovery_required() -> None:
    """The two cases must stay distinguishable in both directions."""

    adapter = Adapter(acquisition([], playable=True, transcript_status="absent"))
    _, report = build_dev_catalog([candidate()], adapter, ImportReport())
    summary = report.as_dict()
    assert summary[RECOVERY_REQUIRED] == 1
    assert summary[MISSING_TRANSCRIPT] == 0
