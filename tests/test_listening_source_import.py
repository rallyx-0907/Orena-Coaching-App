"""Batch L2: the development curated source importer.

LISTENING_PRODUCT_SPEC 5-7. These use a fake provider adapter deliberately: the
importer's contract is what it does with what the adapter returns, and a test
that needed the network could not assert determinism or failure handling.
"""

from __future__ import annotations

import json
from pathlib import Path

from writing_coach.listening_catalog import (
    EN_LEVELS,
    ZH_LEVELS,
    dev_catalog_enabled,
    load_catalog,
    load_catalog_manifest,
)
from writing_coach.listening_source_import import (
    SourceCandidate,
    build_dev_catalog,
    lesson_id_for,
    plan_excerpts,
    read_source_candidates,
    source_media_id,
    write_manifest,
)
from writing_coach.media_ingestion import (
    MediaAcquisition,
    MediaPlayback,
    ProviderRequestFailed,
    ProviderTranscriptMalformed,
)
from writing_coach.media_learning import (
    MediaLearningAsset,
    MediaLearningObject,
    MediaProcessingState,
    MediaTranscript,
    TranscriptSegment,
)

REPO = Path(__file__).resolve().parents[1]
CONTENT = REPO / "writing_coach/content"


def _write(manifest, path: Path) -> None:
    """Write a manifest the way the generator does, recording its inputs."""

    from writing_coach.listening_dev_artifact import EXPECTED_SOURCE_LISTS

    write_manifest(manifest, path, source_lists=[CONTENT / name for name in EXPECTED_SOURCE_LISTS])


def _segments(asset_id: str, count: int, seconds: int = 6) -> tuple[TranscriptSegment, ...]:
    return tuple(
        TranscriptSegment(f"{asset_id}:{index:03d}", index, index * seconds * 1000,
                          (index + 1) * seconds * 1000, f"line {index}")
        for index in range(count)
    )


class FakeAdapter:
    """Returns a real MediaLearningObject; raises for the URLs a test names."""

    def __init__(self, *, malformed: set[str] | None = None, unavailable: set[str] | None = None,
                 exploding: set[str] | None = None, segment_count: int = 40) -> None:
        self.malformed = malformed or set()
        self.unavailable = unavailable or set()
        self.exploding = exploding or set()
        self.segment_count = segment_count
        self.calls: list[tuple[str, str]] = []

    def acquire(self, source_url: str, source_language: str) -> MediaAcquisition:
        self.calls.append((source_url, source_language))
        video_id = source_url.rsplit("=", 1)[-1]
        if video_id in self.malformed:
            raise ProviderTranscriptMalformed()
        if video_id in self.unavailable:
            raise ProviderRequestFailed()
        if video_id in self.exploding:
            raise RuntimeError("provider exploded in an unexpected way")
        asset_id = f"youtube:{video_id}"
        segments = _segments(asset_id, self.segment_count)
        asset = MediaLearningAsset(
            asset_id=asset_id, source_url=source_url, source_provider="youtube",
            source_type="external-video", title=f"Title {video_id}",
            source_language=source_language, processing_state=MediaProcessingState.READY,
            duration_ms=None, transcript_available=bool(segments), translation_available=False,
        )
        return MediaAcquisition(
            media_object=MediaLearningObject(
                asset=asset,
                transcript=MediaTranscript(asset_id, source_language, segments) if segments else None,
            ),
            playback=MediaPlayback(provider="youtube", kind="embed",
                                   url=f"https://www.youtube-nocookie.com/embed/{video_id}"),
        )


def candidate(**over) -> SourceCandidate:
    base = dict(
        candidate_id="en-001", language="en", category="conversation",
        source_family="BBC Learning English", title="How to introduce yourself",
        source_url="https://www.youtube.com/watch?v=I_tRSrPru94",
        desired_excerpt_count=3, min_excerpt_seconds=20, max_excerpt_seconds=90,
        preferred_modes=("listen", "dictation", "shadowing"), level_hint="", notes="",
    )
    base.update(over)
    return SourceCandidate(**base)


# --- the shipped source lists parse, both languages -------------------------

def test_the_human_source_csvs_parse_into_candidates() -> None:
    for name, language, expected in (
        ("listening_sources_en_dev_100.csv", "en", 100),
        ("listening_sources_zh_dev_100.csv", "zh", 100),
    ):
        rows = read_source_candidates(REPO / "writing_coach/content" / name)
        assert len(rows) == expected
        assert {row.language for row in rows} == {language}
        assert all(row.source_url.startswith("https://www.youtube.com/") for row in rows)
        # The BOM must not leak into the first column name.
        assert all(row.candidate_id and not row.candidate_id.startswith("﻿") for row in rows)
        assert all(row.max_excerpt_seconds >= row.min_excerpt_seconds > 0 for row in rows)


# --- watch and Shorts both resolve to the same pipeline ---------------------

def test_watch_and_shorts_urls_are_both_imported() -> None:
    adapter = FakeAdapter()
    manifest, report = build_dev_catalog([
        candidate(candidate_id="watch", source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        candidate(candidate_id="shorts", source_url="https://www.youtube.com/shorts/aBcDeFgHiJk"),
    ], adapter)

    assert report.as_dict()["ACCEPTED"] == 2
    ids = {source["source_media_id"] for source in manifest["sources"]}
    assert ids == {"youtube-dQw4w9WgXcQ", "youtube-aBcDeFgHiJk"}
    # A Shorts URL is canonicalised before acquisition, so one identity per video.
    assert all(url.startswith("https://www.youtube.com/watch?v=") for url, _ in adapter.calls)


# --- one source, several excerpts, only on real boundaries ------------------

def test_one_source_yields_multiple_excerpts_on_real_boundaries() -> None:
    adapter = FakeAdapter(segment_count=60)  # 6 minutes of 6s segments
    manifest, report = build_dev_catalog([candidate(desired_excerpt_count=3)], adapter)

    lessons = manifest["lessons"]
    assert len(lessons) == 3, "a long source should produce several excerpts"
    assert report.as_dict()["GENERATED_SOURCES"] == 1
    assert report.as_dict()["GENERATED_LESSONS"] == 3

    boundaries = {int(s["start_ms"]) for s in manifest["sources"][0]["segments"]}
    ends = {int(s["end_ms"]) for s in manifest["sources"][0]["segments"]}
    for lesson in lessons:
        # Spec 6: never fabricate excerpt timestamps.
        assert lesson["excerpt_start_ms"] in boundaries
        assert lesson["excerpt_end_ms"] in ends
        length = lesson["excerpt_end_ms"] - lesson["excerpt_start_ms"]
        assert 20_000 <= length <= 90_000, f"excerpt of {length}ms outside the editor's range"

    # Excerpts do not all come from the opening of the video.
    assert len({lesson["excerpt_start_ms"] for lesson in lessons}) == 3


def test_excerpt_planning_never_invents_a_boundary() -> None:
    segments = [{"start_ms": i * 5000, "end_ms": (i + 1) * 5000} for i in range(20)]
    windows = plan_excerpts(segments, min_seconds=20, max_seconds=30, limit=5)
    assert windows, "a 100s transcript must yield at least one 20-30s window"
    starts = {s["start_ms"] for s in segments}
    for start, end in windows:
        assert start in starts and end in {s["end_ms"] for s in segments}
        assert 20_000 <= end - start <= 30_000

    # Too short to reach the minimum: produce nothing rather than pad.
    assert plan_excerpts(segments[:2], min_seconds=60, max_seconds=90, limit=3) == []
    assert plan_excerpts([], min_seconds=20, max_seconds=90, limit=3) == []


# --- deterministic identities, stable across reruns -------------------------

def test_identities_are_deterministic_and_survive_a_rerun() -> None:
    rows = [candidate(), candidate(candidate_id="en-002",
                                   source_url="https://www.youtube.com/watch?v=31y2Bq1RYQA")]
    first, _ = build_dev_catalog(rows, FakeAdapter())
    second, _ = build_dev_catalog(rows, FakeAdapter())

    assert first == second, "re-running the importer must not change the manifest"
    assert source_media_id("dQw4w9WgXcQ") == "youtube-dQw4w9WgXcQ"
    # Anchored on excerpt start time, not a segment ordinal: a window that still
    # begins at the same second keeps its id when captions are re-segmented.
    assert lesson_id_for("en", "dQw4w9WgXcQ", 42_000) == "dev-en-dQw4w9WgXcQ-t00042"
    assert lesson_id_for("en", "dQw4w9WgXcQ", 42_400) == lesson_id_for("en", "dQw4w9WgXcQ", 42_000)

    # Segment identities come from the provider and stay attached.
    segment_ids = [s["segment_id"] for s in first["sources"][0]["segments"]]
    assert segment_ids == sorted(segment_ids)
    assert all(sid.startswith("youtube:") for sid in segment_ids)

    # Dropping the second row does not renumber the first row's lessons.
    trimmed, _ = build_dev_catalog(rows[:1], FakeAdapter())
    kept = {lesson["lesson_id"] for lesson in trimmed["lessons"]}
    assert kept <= {lesson["lesson_id"] for lesson in first["lessons"]}


# --- failures are reported, never fatal -------------------------------------

def test_generated_content_never_claims_review_it_has_not_had() -> None:
    """P1: unreviewed development content must not label itself verified."""

    manifest, _ = build_dev_catalog([candidate()], FakeAdapter())

    source = manifest["sources"][0]
    assert source["rights"]["review_status"] == "rights_review"
    assert source["rights"]["review_status"] != "verified"
    assert source["rights"]["allowed_usage_type"] == "development-embed-only"

    for lesson in manifest["lessons"]:
        assert lesson["status"] == "DEV_CANDIDATE"
        assert lesson["status"] != "PUBLISHED"
        assert lesson["curation_state"] == "proposed"
        assert lesson["reviewed_level"] is None


def test_the_base_loader_refuses_the_development_lifecycle(tmp_path: Path) -> None:
    """The strict loader stays strict; only the overlay may carry candidates."""

    manifest, _ = build_dev_catalog([candidate()], FakeAdapter())
    dev_path = tmp_path / "dev.json"
    _write(manifest, dev_path)

    try:
        load_catalog_manifest(dev_path)
    except ValueError as exc:
        assert "rights review" in str(exc).casefold()
    else:
        raise AssertionError("the base loader must refuse an unreviewed dev source")

    # The same file is acceptable when the dev lifecycle is explicitly allowed.
    sources, lessons = load_catalog_manifest(dev_path, allow_dev=True)
    assert sources and lessons
    assert all(item.content_status == "DEV_CANDIDATE" for item in lessons)
    assert all(item.curation_state == "proposed" for item in lessons)


def test_a_generator_cannot_promote_its_own_excerpt(tmp_path: Path) -> None:
    """P1/P2: curation is a human act, not something output asserts."""

    manifest, _ = build_dev_catalog([candidate()], FakeAdapter())
    manifest["lessons"][0]["curation_state"] = "reviewed"
    dev_path = tmp_path / "dev.json"
    _write(manifest, dev_path)

    try:
        load_catalog_manifest(dev_path, allow_dev=True)
    except ValueError as exc:
        assert "curation" in str(exc).casefold()
    else:
        raise AssertionError("a DEV_CANDIDATE must not self-declare curation review")


def test_an_invalid_human_row_is_reported_not_generated() -> None:
    """P1: a bad CSV field costs one candidate, never the whole overlay."""

    rows = [
        candidate(candidate_id="bad-level", level_hint="HSK5"),          # ZH level on an EN row
        candidate(candidate_id="bad-level-2", language="zh", level_hint="B2"),
        candidate(candidate_id="bad-mode", preferred_modes=("listen", "karaoke")),
        candidate(candidate_id="inverted-range", min_excerpt_seconds=90, max_excerpt_seconds=20),
        candidate(candidate_id="absurd-range", min_excerpt_seconds=1, max_excerpt_seconds=99999),
        candidate(candidate_id="good", source_url="https://www.youtube.com/watch?v=ggggggggggg"),
    ]
    manifest, report = build_dev_catalog(rows, FakeAdapter())
    summary = report.as_dict()

    assert summary["ACCEPTED"] == 1, "only the valid row generates"
    assert summary["SKIPPED"] == 5
    assert summary["GENERATED_SOURCES"] == 1

    outcomes = {entry["candidate_id"]: entry for entry in summary["entries"]}
    assert "level_hint" in outcomes["bad-level"]["detail"]
    assert "level_hint" in outcomes["bad-level-2"]["detail"]
    assert "preferred_modes" in outcomes["bad-mode"]["detail"]
    assert "range" in outcomes["inverted-range"]["detail"]
    assert outcomes["good"]["outcome"] == "ACCEPTED"

    # The surviving manifest is loadable: a bad row never poisons the overlay.
    for lesson in manifest["lessons"]:
        # L3 replaced the blanket B1/HSK3 fallback with a transcript-based
        # estimate, so the assertion is now the language's own ladder.
        assert lesson["estimated_level"] in EN_LEVELS | ZH_LEVELS
        assert lesson["reviewed_level"] is None
        assert set(lesson["available_modes"]) <= {"listen", "active", "dictation", "shadowing"}


def test_provider_metadata_outranks_the_editor_hint() -> None:
    """P2: the channel is the source's identity; the CSV is a fallback."""

    class MetadataAdapter(FakeAdapter):
        def __init__(self) -> None:
            super().__init__()
            self._metadata_client = self

        def fetch_metadata(self, canonical_url: str):
            from writing_coach.media_providers.youtube import YouTubeSourceMetadata
            return YouTubeSourceMetadata(
                title="Provider title",
                author_name="BBC Learning English (official channel)",
                thumbnail_url="https://i.ytimg.com/vi/custom/maxresdefault.jpg",
            )

    manifest, _ = build_dev_catalog(
        [candidate(source_family="editor guess")], MetadataAdapter())
    source = manifest["sources"][0]
    assert source["source_creator"] == "BBC Learning English (official channel)"
    assert source["poster_url"] == "https://i.ytimg.com/vi/custom/maxresdefault.jpg"

    # Without provider metadata the editor hint still fills the gap.
    fallback, _ = build_dev_catalog([candidate(source_family="editor guess")], FakeAdapter())
    assert fallback["sources"][0]["source_creator"] == "editor guess"
    assert fallback["sources"][0]["poster_url"].startswith("https://i.ytimg.com/vi/")


def test_one_metadata_request_per_accepted_source() -> None:
    """P1/P2: acquire() and the importer must share one oEmbed response.

    Counted at the HTTP session, not at the client, because the client is where
    the duplicate used to hide: fetch_title() and fetch_metadata() each issued
    their own request for the same URL.
    """

    from writing_coach.media_providers.youtube import RequestsYouTubeMetadataClient

    class CountingSession:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def get(self, endpoint, params=None, timeout=None):
            self.urls.append((params or {}).get("url", ""))

            class Response:
                status_code = 200

                @staticmethod
                def raise_for_status() -> None: ...

                @staticmethod
                def json() -> dict:
                    return {"title": "A title", "author_name": "A channel",
                            "thumbnail_url": "https://i.ytimg.com/vi/x/hqdefault.jpg"}

            return Response()

    session = CountingSession()
    client = RequestsYouTubeMetadataClient(session=session)

    url = "https://www.youtube.com/watch?v=aaaaaaaaaaa"
    assert client.fetch_title(url) == "A title"
    meta = client.fetch_metadata(url)
    assert (meta.author_name, meta.thumbnail_url) == (
        "A channel", "https://i.ytimg.com/vi/x/hqdefault.jpg")
    assert len(session.urls) == 1, f"one source must cost one oEmbed request, got {session.urls}"

    # A different source is a new request, not a stale cached answer.
    other = "https://www.youtube.com/watch?v=bbbbbbbbbbb"
    client.fetch_metadata(other)
    assert session.urls == [url, other]

    # And through the importer: one accepted candidate, one metadata request.
    class CountingAdapter(FakeAdapter):
        def __init__(self, metadata_client) -> None:
            super().__init__()
            self._metadata_client = metadata_client

        def acquire(self, source_url: str, source_language: str):
            # Mirrors the real adapter: acquire() reads the title itself.
            self._metadata_client.fetch_title(source_url)
            return super().acquire(source_url, source_language)

    session = CountingSession()
    adapter = CountingAdapter(RequestsYouTubeMetadataClient(session=session))
    _, report = build_dev_catalog([
        candidate(candidate_id="one", source_url="https://www.youtube.com/watch?v=ccccccccccc"),
        candidate(candidate_id="two", source_url="https://www.youtube.com/watch?v=ddddddddddd"),
    ], adapter)

    assert report.as_dict()["ACCEPTED"] == 2
    assert len(session.urls) == 2, f"two sources must cost two requests, got {session.urls}"
    assert len(set(session.urls)) == 2


def test_a_failing_candidate_does_not_break_the_batch() -> None:
    rows = [
        candidate(candidate_id="ok", source_url="https://www.youtube.com/watch?v=aaaaaaaaaaa"),
        candidate(candidate_id="dupe", source_url="https://www.youtube.com/watch?v=aaaaaaaaaaa"),
        candidate(candidate_id="no-transcript", source_url="https://www.youtube.com/watch?v=bbbbbbbbbbb"),
        candidate(candidate_id="unavailable", source_url="https://www.youtube.com/watch?v=ccccccccccc"),
        candidate(candidate_id="boom", source_url="https://www.youtube.com/watch?v=ddddddddddd"),
        candidate(candidate_id="other-language", language="fr"),
        candidate(candidate_id="not-a-provider", source_url="https://vimeo.com/12345"),
        candidate(candidate_id="last", source_url="https://www.youtube.com/watch?v=eeeeeeeeeee"),
    ]
    adapter = FakeAdapter(malformed={"bbbbbbbbbbb"}, unavailable={"ccccccccccc"},
                          exploding={"ddddddddddd"})
    manifest, report = build_dev_catalog(rows, adapter)
    summary = report.as_dict()

    assert summary["ACCEPTED"] == 2, "the batch continues past every failure"
    assert summary["DUPLICATE"] == 1
    assert summary["MISSING_TRANSCRIPT"] == 1
    assert summary["MEDIA_UNAVAILABLE"] == 1
    assert summary["FAILED"] == 1, "an unexpected provider error is caught, not raised"
    assert summary["UNSUPPORTED_LANGUAGE"] == 1
    assert summary["SKIPPED"] == 1
    assert summary["GENERATED_SOURCES"] == 2

    outcomes = {entry["candidate_id"]: entry["outcome"] for entry in summary["entries"]}
    assert outcomes["last"] == "ACCEPTED", "a later candidate still runs after an exception"
    assert outcomes["dupe"] == "DUPLICATE"


# --- EN and ZH run the identical pipeline -----------------------------------

def test_en_and_zh_use_the_same_pipeline() -> None:
    adapter = FakeAdapter()
    manifest, report = build_dev_catalog([
        candidate(candidate_id="en-001", language="en",
                  source_url="https://www.youtube.com/watch?v=eeeeeeeeeee"),
        candidate(candidate_id="zh-001", language="zh", category="street-interview",
                  source_url="https://www.youtube.com/watch?v=zzzzzzzzzzz"),
    ], adapter)

    assert report.as_dict()["ACCEPTED"] == 2
    languages = {source["language"] for source in manifest["sources"]}
    assert languages == {"en", "zh"}
    # The transcript language reaches the adapter, not a hardcoded default.
    assert {lang for _, lang in adapter.calls} == {"en", "zh"}
    # Each language is estimated on its own ladder, never the other's.
    en_levels = {lesson["estimated_level"] for lesson in manifest["lessons"]
                 if lesson["lesson_id"].startswith("dev-en-")}
    zh_levels = {lesson["estimated_level"] for lesson in manifest["lessons"]
                 if lesson["lesson_id"].startswith("dev-zh-")}
    assert en_levels and en_levels <= EN_LEVELS
    assert zh_levels and zh_levels <= ZH_LEVELS
    assert all(lesson["reviewed_level"] is None for lesson in manifest["lessons"])


# --- the generated manifest loads through the canonical catalog -------------

def test_generated_manifest_loads_as_a_dev_overlay(tmp_path: Path) -> None:
    manifest, _ = build_dev_catalog([candidate()], FakeAdapter())
    dev_path = tmp_path / "listening_catalog.dev.generated.json"
    _write(manifest, dev_path)

    written = json.loads(dev_path.read_text(encoding="utf-8"))
    assert "Edit the source CSV" in written["do_not_edit"]

    base_only, base_lessons = load_catalog(dev_path=dev_path, env={})
    with_dev, dev_lessons = load_catalog(
        dev_path=dev_path, env={"ENABLE_DEV_LISTENING_CATALOG": "1"})

    assert len(dev_lessons) > len(base_lessons), "the overlay adds lessons"
    assert set(base_only) <= set(with_dev), "the overlay never removes a base source"
    generated = {lesson.lesson_id for lesson in dev_lessons} - {lesson.lesson_id for lesson in base_lessons}
    assert generated and all(lesson_id.startswith("dev-") for lesson_id in generated)

    # The generated lesson is a real, playable, poster-backed catalog entry.
    lesson = next(item for item in dev_lessons if item.lesson_id in generated)
    assert lesson.content_status == "DEV_CANDIDATE"
    assert lesson.curation_state == "proposed"
    assert lesson.playback.kind == "embed"
    assert lesson.source.poster_url.startswith("https://i.ytimg.com/")
    assert lesson.excerpt_end_ms > lesson.excerpt_start_ms


# --- the overlay is off unless a developer opts in --------------------------

def test_the_generated_artifact_is_reproducible_and_tamper_evident(tmp_path: Path) -> None:
    """P1: the artifact is committed, so it must survive review and edits."""

    from writing_coach.listening_dev_artifact import (
        EXPECTED_SOURCE_LISTS,
        manifest_content_hash,
        verify_manifest_integrity,
    )

    manifest, _ = build_dev_catalog([candidate()], FakeAdapter())
    dev_path = tmp_path / "dev.json"
    _write(manifest, dev_path)

    written = json.loads(dev_path.read_text(encoding="utf-8"))
    assert written["generated_by"].endswith("build_listening_dev_catalog.py")
    assert written["do_not_edit"]
    # Provenance: a reviewer can tell which source list produced this snapshot.
    assert {entry["name"] for entry in written["source_lists"]} == set(EXPECTED_SOURCE_LISTS)
    assert all(len(entry["sha256"]) == 64 for entry in written["source_lists"])
    assert verify_manifest_integrity(written) == ""

    # Regenerating the same input reproduces the same fingerprint.
    again, _ = build_dev_catalog([candidate()], FakeAdapter())
    regenerated = tmp_path / "again.json"
    _write(again, regenerated)
    assert json.loads(regenerated.read_text(encoding="utf-8"))["content_hash"] == written["content_hash"]
    assert manifest_content_hash(written) == written["content_hash"]

    # A hand edit is detected rather than silently loaded.
    tampered = dict(written)
    tampered["lessons"] = [dict(tampered["lessons"][0], title="hand edited")]
    assert "edited by hand" in verify_manifest_integrity(tampered)
    missing = {key: value for key, value in written.items() if key != "content_hash"}
    assert "no content_hash" in verify_manifest_integrity(missing)


def test_a_tampered_artifact_is_refused_by_the_overlay(tmp_path: Path) -> None:
    manifest, _ = build_dev_catalog([candidate()], FakeAdapter())
    dev_path = tmp_path / "dev.json"
    _write(manifest, dev_path)

    payload = json.loads(dev_path.read_text(encoding="utf-8"))
    payload["lessons"][0]["title"] = "quietly changed by a human"
    dev_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        load_catalog(dev_path=dev_path, env={"ENABLE_DEV_LISTENING_CATALOG": "1"})
    except ValueError as exc:
        assert "edited by hand" in str(exc)
    else:
        raise AssertionError("a hand-edited development catalog must be refused")


def test_snapshot_mode_and_the_repository_artifact_agree() -> None:
    """The committed-snapshot contract, enforced rather than described.

    While SNAPSHOT_REQUIRED is False the artifact is legitimately absent and the
    offline check must not report integrity PASS for a missing file. The moment
    L3 flips it True the artifact has to exist here and be valid, so the flag
    cannot be turned on without the snapshot it promises.
    """

    from writing_coach.listening_catalog import DEV_CATALOG_MANIFEST
    from writing_coach.listening_dev_artifact import (
        EXPECTED_SOURCE_LISTS,
        SNAPSHOT_REQUIRED,
        verify_manifest_integrity,
    )

    content_dir = REPO / "writing_coach/content"
    for name in EXPECTED_SOURCE_LISTS:
        assert (content_dir / name).is_file(), f"declared source list {name} is missing"

    # The invariant runs BOTH ways. Enforcing only "flag implies artifact" left a
    # third state reachable: L3 commits the snapshot but forgets the flag, CI
    # still passes, and if the artifact later disappears the check silently falls
    # back to SKIP instead of failing. There are exactly two legal states.
    assert DEV_CATALOG_MANIFEST.is_file() == SNAPSHOT_REQUIRED, (
        f"SNAPSHOT_REQUIRED is {SNAPSHOT_REQUIRED} but the committed catalog "
        f"{'exists' if DEV_CATALOG_MANIFEST.is_file() else 'is absent'} at "
        f"{DEV_CATALOG_MANIFEST}. L2 state is absent+False; L3 state is "
        "present+True; there is no third state."
    )

    if DEV_CATALOG_MANIFEST.is_file():
        # Present either way, it must be valid against the CURRENT source lists.
        problem = verify_manifest_integrity(
            json.loads(DEV_CATALOG_MANIFEST.read_text(encoding="utf-8")),
            content_dir=content_dir,
        )
        assert problem == "", problem


def test_the_snapshot_invariant_rejects_both_illegal_states() -> None:
    """The pairing rule itself, tested without needing to move the real file."""

    def legal(artifact_exists: bool, flag: bool) -> bool:
        return artifact_exists == flag

    assert legal(False, False), "L2: no snapshot, flag off"
    assert legal(True, True), "L3: snapshot committed, flag on"
    # Snapshot committed but the flag left off: CI would pass, and a later
    # disappearance would degrade to SKIP unnoticed.
    assert not legal(True, False)
    # Flag on with nothing behind it: the check would fail for a missing file.
    assert not legal(False, True)


def test_a_stale_snapshot_is_detected_when_a_source_list_changes(tmp_path: Path) -> None:
    """P2: the digests must be verified, not merely recorded."""

    from writing_coach.listening_dev_artifact import verify_manifest_integrity

    content_dir = tmp_path / "content"
    content_dir.mkdir()
    for name in ("listening_sources_en_dev_100.csv", "listening_sources_zh_dev_100.csv"):
        (content_dir / name).write_text("candidate_id,source_url\nen-001,x\n", encoding="utf-8")

    manifest, _ = build_dev_catalog([candidate()], FakeAdapter())
    dev_path = tmp_path / "dev.json"
    write_manifest(manifest, dev_path, source_lists=sorted(content_dir.iterdir()))
    written = json.loads(dev_path.read_text(encoding="utf-8"))
    assert verify_manifest_integrity(written, content_dir=content_dir) == ""

    # An editor changes a source list and forgets to regenerate.
    (content_dir / "listening_sources_en_dev_100.csv").write_text(
        "candidate_id,source_url\nen-001,x\nen-002,y\n", encoding="utf-8")
    problem = verify_manifest_integrity(written, content_dir=content_dir)
    assert "changed since the catalog was generated" in problem

    # A deleted source list is caught too.
    (content_dir / "listening_sources_en_dev_100.csv").unlink()
    assert "no longer exists" in verify_manifest_integrity(written, content_dir=content_dir)


def test_provenance_header_must_match_this_generator() -> None:
    from writing_coach.listening_dev_artifact import verify_manifest_integrity

    manifest, _ = build_dev_catalog([candidate()], FakeAdapter())

    import writing_coach.listening_dev_artifact as artifact
    good = {
        **manifest,
        "generated_by": artifact.GENERATOR,
        "generator_version": artifact.GENERATOR_VERSION,
        "source_lists": [{"name": name, "sha256": "x"} for name in artifact.EXPECTED_SOURCE_LISTS],
    }
    good["content_hash"] = artifact.manifest_content_hash(good)
    assert verify_manifest_integrity(good) == ""

    assert "unexpected generator" in verify_manifest_integrity({**good, "generated_by": "hand"})
    assert "generator version" in verify_manifest_integrity({**good, "generator_version": "0"})
    # A manifest that genuinely records no source lists: rehash it the way the
    # generator would, so the name check is what fires rather than the hash.
    bare = {**good, "source_lists": []}
    bare["content_hash"] = artifact.manifest_content_hash(bare)
    assert "does not record source lists" in verify_manifest_integrity(bare)

    # Rewriting source_lists without regenerating is caught by the fingerprint.
    assert "edited by hand" in verify_manifest_integrity({**good, "source_lists": []})


def test_the_fingerprint_binds_provenance_to_the_catalog_body(tmp_path: Path) -> None:
    """P2: a stale body must not be pairable with fresh source-list digests.

    When the hash covered only sources and lessons, someone could regenerate the
    digests by hand after editing a CSV, leave the catalog body untouched, and
    the fingerprint would not move. Binding both halves into one value closes
    that pairing.
    """

    from writing_coach.listening_dev_artifact import (
        FINGERPRINTED_FIELDS,
        manifest_content_hash,
        verify_manifest_integrity,
    )

    manifest, _ = build_dev_catalog([candidate()], FakeAdapter())
    dev_path = tmp_path / "dev.json"
    _write(manifest, dev_path)
    written = json.loads(dev_path.read_text(encoding="utf-8"))
    assert verify_manifest_integrity(written) == ""

    # Every field the review named is inside the fingerprint, and only the hash
    # itself is outside it.
    assert set(FINGERPRINTED_FIELDS) == {
        "schema_version", "generated_by", "generator_version",
        "source_lists", "sources", "lessons",
    }
    for field in FINGERPRINTED_FIELDS:
        drifted = {**written, field: "tampered"}
        assert manifest_content_hash(drifted) != written["content_hash"], (
            f"{field} must be covered by the fingerprint"
        )

    # The exact pairing the old hash allowed: body untouched, digests rewritten.
    paired = {**written, "source_lists": [
        {"name": entry["name"], "sha256": "0" * 64} for entry in written["source_lists"]
    ]}
    assert "edited by hand" in verify_manifest_integrity(paired)


def test_dev_overlay_defaults_off_and_is_refused_in_production(tmp_path: Path) -> None:
    assert dev_catalog_enabled({}) is False, "no flag means no overlay"
    assert dev_catalog_enabled({"ENABLE_DEV_LISTENING_CATALOG": "0"}) is False
    assert dev_catalog_enabled({"ENABLE_DEV_LISTENING_CATALOG": ""}) is False
    assert dev_catalog_enabled({"ENABLE_DEV_LISTENING_CATALOG": "1"}) is True
    assert dev_catalog_enabled({"ENABLE_DEV_LISTENING_CATALOG": "true"}) is True

    # Spec 7: production must not be one environment variable away from serving
    # generated development content.
    for flag in ("1", "true", "yes", "on"):
        assert dev_catalog_enabled({
            "ENABLE_DEV_LISTENING_CATALOG": flag, "APP_ENV": "production",
        }) is False

    manifest, _ = build_dev_catalog([candidate()], FakeAdapter())
    dev_path = tmp_path / "dev.json"
    _write(manifest, dev_path)
    _, production_lessons = load_catalog(
        dev_path=dev_path,
        env={"ENABLE_DEV_LISTENING_CATALOG": "1", "APP_ENV": "production"},
    )
    assert not [item for item in production_lessons if item.lesson_id.startswith("dev-")]


def test_dev_overlay_cannot_redefine_a_reviewed_base_lesson(tmp_path: Path) -> None:
    manifest, _ = build_dev_catalog([candidate()], FakeAdapter())
    # A hostile or careless generated file claiming a base lesson id.
    manifest["lessons"][0]["lesson_id"] = "en-science-cosmic-calendar"
    dev_path = tmp_path / "dev.json"
    _write(manifest, dev_path)

    _, lessons = load_catalog(dev_path=dev_path, env={"ENABLE_DEV_LISTENING_CATALOG": "1"})
    clash = [item for item in lessons if item.lesson_id == "en-science-cosmic-calendar"]
    assert len(clash) == 1
    assert clash[0].source.source_provider == "wikimedia-commons", "the reviewed lesson wins"
