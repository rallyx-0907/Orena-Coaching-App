"""Provider throttling must never be recorded as a verdict about a source.

The real L3 run proved why this matters. A 200-source burst got rate-limited by
YouTube; the caption requests failed, and because deferred recovery treats a
missing transcript as non-fatal, 54 sources that genuinely HAD captions in their
own language were written into the report as sources without captions. Left
alone, that would have silently deleted them from the development catalog on the
strength of a network error.

So: a failed probe is UNRESOLVED and gets retried; anything actually learned
about a source is final and is not retried.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from writing_coach.media_ingestion import MediaAcquisition, MediaPlayback
from writing_coach.media_learning import (
    MediaLearningAsset,
    MediaLearningObject,
    MediaProcessingState,
    MediaTranscript,
    TranscriptSegment,
)
from writing_coach.listening_source_import import (
    ACCEPTED,
    MISSING_TRANSCRIPT,
    RECOVERY_REQUIRED,
    SourceCandidate,
)

ROOT = Path(__file__).resolve().parents[1]


def _script():
    spec = importlib.util.spec_from_file_location(
        "build_listening_dev_catalog", ROOT / "scripts/build_listening_dev_catalog.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD = _script()

VIDEOS = {
    "en-001": "https://www.youtube.com/watch?v=aaaaaaaaaaa",
    "en-002": "https://www.youtube.com/watch?v=bbbbbbbbbbb",
    "en-003": "https://www.youtube.com/watch?v=ccccccccccc",
}


def candidate(candidate_id: str) -> SourceCandidate:
    return SourceCandidate(
        candidate_id=candidate_id, language="en", category="conversation",
        source_family="Test", title="A lesson", source_url=VIDEOS[candidate_id],
        desired_excerpt_count=3, min_excerpt_seconds=20, max_excerpt_seconds=90,
        preferred_modes=("listen",), level_hint="", notes="",
    )


def acquisition(video_id: str, *, status: str, with_transcript: bool) -> MediaAcquisition:
    asset = MediaLearningAsset(
        asset_id=f"youtube:{video_id}", source_url=f"https://www.youtube.com/watch?v={video_id}",
        source_provider="youtube", source_type="external-video", title="A lesson",
        source_language="en", processing_state=MediaProcessingState.READY,
        transcript_available=with_transcript,
    )
    transcript = None
    if with_transcript:
        transcript = MediaTranscript(
            asset_id=asset.asset_id, source_language="en",
            segments=tuple(
                TranscriptSegment(f"s:{i:03d}", i, i * 5000, (i + 1) * 5000,
                                  "a line of clear speech for the learner")
                for i in range(30)))
    return MediaAcquisition(
        media_object=MediaLearningObject(asset=asset, transcript=transcript),
        playback=MediaPlayback(provider="youtube", kind="embed",
                               url=f"https://www.youtube-nocookie.com/embed/{video_id}"),
        transcript_status=status,
    )


class ThrottledAdapter:
    """Fails caption probes until the given pass, as a throttled provider does."""

    def __init__(self, succeed_from_pass: int, outcomes: dict[str, bool]) -> None:
        self.pass_number = 0
        self.succeed_from_pass = succeed_from_pass
        self.outcomes = outcomes
        self.seen: list[tuple[int, str]] = []

    def new_pass(self):
        self.pass_number += 1
        return self

    def acquire(self, url, language):
        video_id = url.rsplit("=", 1)[-1]
        self.seen.append((self.pass_number, video_id))
        if self.pass_number < self.succeed_from_pass:
            return acquisition(video_id, status="probe_failed", with_transcript=False)
        has_captions = self.outcomes[video_id]
        return acquisition(
            video_id,
            status="native" if has_captions else "absent",
            with_transcript=has_captions)

    def fetch_metadata(self, url):
        class Meta:
            author_name = "A channel"
            thumbnail_url = "https://i.ytimg.com/vi/x/hqdefault.jpg"
        return Meta()


def run(adapter, passes: int):
    slept: list[float] = []
    manifest, report = BUILD._run_with_retries(
        [candidate(cid) for cid in VIDEOS],
        pause_seconds=0,
        retry_passes=passes,
        retry_backoff=42,
        adapter_factory=adapter.new_pass,
        sleep=slept.append,
    )
    return manifest, report.as_dict(), slept


def test_a_throttled_first_pass_is_retried_and_then_succeeds() -> None:
    adapter = ThrottledAdapter(
        succeed_from_pass=2,
        outcomes={"aaaaaaaaaaa": True, "bbbbbbbbbbb": True, "ccccccccccc": False})
    manifest, summary, slept = run(adapter, passes=3)

    assert summary[ACCEPTED] == 2, "sources with captions must survive a throttled pass"
    assert summary[RECOVERY_REQUIRED] == 1, "the genuinely caption-less one is still that"
    assert summary[MISSING_TRANSCRIPT] == 0, "nothing is left unresolved"
    assert summary["TOTAL_OUTCOMES"] == 3, "one final outcome per candidate, not one per attempt"
    assert len(summary["entries"]) == 3
    assert slept == [42], "exactly one backoff, before the single retry pass needed"


def test_a_resolved_candidate_is_not_re_fetched() -> None:
    """Retry is for the unknown, not a second full run: it costs provider calls."""

    adapter = ThrottledAdapter(
        succeed_from_pass=1,
        outcomes={"aaaaaaaaaaa": True, "bbbbbbbbbbb": False, "ccccccccccc": False})
    _, summary, slept = run(adapter, passes=3)

    assert summary["TOTAL_OUTCOMES"] == 3
    assert [video for _, video in adapter.seen].count("aaaaaaaaaaa") == 1
    assert slept == [], "nothing was unresolved, so no retry pass ran at all"


def test_giving_up_reports_unresolved_truthfully_rather_than_guessing() -> None:
    """When retries run out the report says "unresolved", never "no captions"."""

    adapter = ThrottledAdapter(
        succeed_from_pass=99,
        outcomes={k: True for k in ("aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc")})
    _, summary, slept = run(adapter, passes=2)

    assert summary[MISSING_TRANSCRIPT] == 3
    assert summary[RECOVERY_REQUIRED] == 0, \
        "a source we never managed to probe must not be called caption-less"
    assert summary[ACCEPTED] == 0
    assert all("retry" in entry["detail"] for entry in summary["entries"])
    assert len(slept) == 2, "both permitted retry passes were used"


def test_merging_passes_keeps_one_entry_per_stable_id() -> None:
    base = {"sources": [{"source_media_id": "s1", "language": "en"}],
            "lessons": [{"lesson_id": "l1", "source_media_id": "s1"}]}
    extra = {"sources": [{"source_media_id": "s1", "language": "en", "v": 2},
                         {"source_media_id": "s2", "language": "zh"}],
             "lessons": [{"lesson_id": "l1", "source_media_id": "s1", "v": 2},
                         {"lesson_id": "l2", "source_media_id": "s2"}]}
    merged = BUILD._merge(base, extra)

    assert [s["source_media_id"] for s in merged["sources"]] == ["s1", "s2"]
    assert [le["lesson_id"] for le in merged["lessons"]] == ["l1", "l2"]
    # The later pass wins: it is the more recent observation of the same source.
    assert merged["sources"][0]["v"] == 2
    assert merged["lessons"][0]["v"] == 2


def test_the_merged_report_counts_lessons_per_language_once() -> None:
    adapter = ThrottledAdapter(
        succeed_from_pass=2,
        outcomes={"aaaaaaaaaaa": True, "bbbbbbbbbbb": True, "ccccccccccc": False})
    manifest, summary, _ = run(adapter, passes=2)

    assert summary["GENERATED_SOURCES"] == len(manifest["sources"]) == 2
    assert summary["GENERATED_LESSONS"] == len(manifest["lessons"])
    assert summary["generated_by_language"]["en"] == len(manifest["lessons"])
    assert sum(summary["excerpts_per_source"].values()) == 2


# --- offline ingestion handoff ----------------------------------------------

def test_offline_transcripts_build_a_catalog_with_no_provider_at_all() -> None:
    """One machine acquires, another builds. Same pipeline, no network.

    This is the practical answer to an IP-blocked build host: acquisition and
    catalog building do not have to happen in the same place.
    """

    from writing_coach.listening_source_import import (
        ImportReport, OfflineTranscriptAdapter, build_dev_catalog,
    )

    payload = {
        "aaaaaaaaaaa": {
            "language": "en",
            "origin": "provider_caption",
            "title": "An acquired lesson",
            "segments": [
                {"start_ms": i * 5000, "end_ms": (i + 1) * 5000,
                 "original_text": "a clear line of recorded speech"}
                for i in range(30)
            ],
        },
    }

    class Exploding:
        def acquire(self, *a, **k):
            raise AssertionError("the offline path must not contact a provider")

        def fetch_metadata(self, *a, **k):
            raise AssertionError("the offline path must not contact a provider")

    adapter = OfflineTranscriptAdapter(payload)
    manifest, report = build_dev_catalog([candidate("en-001")], adapter, ImportReport())
    summary = report.as_dict()

    assert summary[ACCEPTED] == 1
    assert manifest["lessons"], "offline transcripts must produce real lessons"
    source = manifest["sources"][0]
    assert len(source["segments"]) == 30
    # Provenance survives the handoff rather than being reset to a guess.
    assert source["transcript"]["origin"] == "provider_caption"

    # And an entry that does not say it was captions is not promoted to captions.
    payload["aaaaaaaaaaa"]["origin"] = "generated_asr"
    manifest2, _ = build_dev_catalog(
        [candidate("en-001")], OfflineTranscriptAdapter(payload), ImportReport())
    assert manifest2["sources"][0]["transcript"]["origin"] == "generated_asr"
    assert manifest2["sources"][0]["transcript"]["quality_state"] == "generated_unreviewed"

    # Excerpt timing came from the handed-over transcript, never invented.
    starts = {s["start_ms"] for s in manifest["sources"][0]["segments"]}
    ends = {s["end_ms"] for s in manifest["sources"][0]["segments"]}
    for lesson in manifest["lessons"]:
        assert lesson["excerpt_start_ms"] in starts
        assert lesson["excerpt_end_ms"] in ends


def test_an_unknown_source_falls_through_to_the_live_adapter() -> None:
    """A partial handoff file is useful, not all-or-nothing."""

    from writing_coach.listening_source_import import (
        ImportReport, OfflineTranscriptAdapter, build_dev_catalog,
    )

    live = ThrottledAdapter(succeed_from_pass=1, outcomes={"bbbbbbbbbbb": True}).new_pass()
    adapter = OfflineTranscriptAdapter({}, live)
    _, report = build_dev_catalog([candidate("en-002")], adapter, ImportReport())
    assert report.as_dict()[ACCEPTED] == 1
    assert [video for _, video in live.seen] == ["bbbbbbbbbbb"]
