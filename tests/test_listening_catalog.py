from __future__ import annotations

import pytest

from writing_coach import listening_api
from writing_coach.listening_api import listening_library, open_listening_library_lesson
from writing_coach.listening_catalog import CATALOG, CATALOG_SOURCES, catalog_lesson, catalog_lessons, lesson_metadata
from writing_coach.media_library_store import FileMediaLibraryStore


@pytest.fixture(autouse=True)
def _curated_catalog_only(tmp_path):
    """Read the curated catalog without whatever this machine has imported.

    The library read now merges persisted imports beside the curated lessons, and
    a curated-catalog test must not be a statement about a developer's sandbox:
    with a populated library the shared items lead the response and the curated
    rails stop being what these assertions are about. The store is pointed at an
    empty directory for the duration and the deployment's own store is put back
    afterwards, so this isolates the test rather than disabling the feature.
    """
    previous = listening_api._media_store
    listening_api.configure_listening_media_library(FileMediaLibraryStore(tmp_path / "media_library"))
    try:
        yield
    finally:
        listening_api.configure_listening_media_library(previous)


def test_library_lists_lightweight_en_and_zh_curated_lessons() -> None:
    assert {lesson.media_object.asset.source_language for lesson in CATALOG} == {"en", "zh"}
    en = listening_library(language="en", level=None, topic=None, tag=None)
    zh = listening_library(language="zh", level=None, topic=None, tag=None)

    assert en["items"] and zh["items"]
    assert "transcript" not in en["items"][0]
    # LISTENING_PRODUCT_SPEC 3.4 rails. `popular` is deliberately not asserted:
    # it is allowed only when real popularity data exists, and none does, so the
    # rail stays empty and is filtered out.
    assert {section["id"] for section in en["sections"]} >= {
        "recommended", "quick-practice", "dictation", "shadowing", "new", "audio-practice"
    }
    assert "popular" not in {section["id"] for section in en["sections"]}
    assert "conversation" in en["tags"]
    assert en["filters"]["tags"] == en["tags"]
    assert en["personalization"] == "deterministic-curation"


def test_topic_and_canonical_level_filters_are_composable() -> None:
    assert [lesson.lesson_id for lesson in catalog_lessons(language="en", level="A1", topic="daily-life")] == [
        "en-daily-pen-in-my-bag"
    ]
    assert [lesson.lesson_id for lesson in catalog_lessons(language="zh", level="HSK1", topic="conversations")] == [
        "zh-daily-what-is-this"
    ]
    assert catalog_lessons(language="en", level="HSK1") == ()


def test_extensible_tag_filter_composes_with_language_and_level() -> None:
    lessons = catalog_lessons(language="zh", level="HSK2", tag="social-life")
    assert [lesson.lesson_id for lesson in lessons] == [
        "zh-culture-nationalities",
        "zh-culture-where-are-you-from",
    ]
    response = listening_library(language="zh", level="HSK2", topic=None, tag="quick-practice")
    assert [item["lesson_id"] for item in response["items"]] == ["zh-culture-where-are-you-from"]


def test_curated_lessons_resolve_to_the_same_media_lesson_contract_with_variable_duration() -> None:
    en = open_listening_library_lesson("en-daily-pen-in-my-bag", "vi")
    zh = open_listening_library_lesson("zh-daily-what-is-this", "en")

    for lesson in (en, zh):
        assert lesson["asset"]["asset_id"] == lesson["transcript"]["asset_id"]
        assert lesson["playback"]["kind"] == "audio"
        assert lesson["catalog"]["media_object_id"] == lesson["asset"]["asset_id"]
        assert lesson["catalog"]["excerpt_end_ms"] <= lesson["asset"]["duration_ms"]
        assert {"listen", "active", "dictation", "shadowing"} <= set(lesson["catalog"]["available_modes"])
        assert lesson["translation"]["source"]["provider"] == "curated-editorial"

    assert en["catalog"]["duration_ms"] != zh["catalog"]["duration_ms"]
    assert zh["catalog"]["pinyin_by_segment"]


def test_one_source_can_publish_multiple_natural_excerpts_without_copying_transcript() -> None:
    first = open_listening_library_lesson("zh-culture-nationalities", "en")
    second = open_listening_library_lesson("zh-culture-where-are-you-from", "en")

    assert first["asset"]["asset_id"] == second["asset"]["asset_id"] == "commons-zh-lesson-1-dialogue-2"
    assert first["catalog"]["lesson_id"] != second["catalog"]["lesson_id"]
    assert first["catalog"]["excerpt_end_ms"] <= second["catalog"]["excerpt_start_ms"]
    assert [segment["segment_id"] for segment in first["transcript"]["segments"]] == [
        "commons-zh-lesson-1-dialogue-2:000",
        "commons-zh-lesson-1-dialogue-2:001",
    ]
    assert [segment["segment_id"] for segment in second["transcript"]["segments"]] == [
        "commons-zh-lesson-1-dialogue-2:002",
        "commons-zh-lesson-1-dialogue-2:003",
        "commons-zh-lesson-1-dialogue-2:004",
    ]


def test_catalog_exposes_reviewed_level_evidence_and_verified_rights() -> None:
    assert len(CATALOG_SOURCES) == 6
    assert len(CATALOG) == 7
    metadata = listening_library(language="en", level="A1", topic=None, tag=None)["items"][0]

    assert metadata["level"] == metadata["reviewed_level"] == "A1"
    assert metadata["estimated_level"] == "A1"
    assert metadata["level_source"] == "editorial-review"
    assert metadata["level_evidence"]["vocabulary_band"] == "foundation"
    assert metadata["source"]["rights_review_status"] == "verified"
    assert metadata["source"]["allowed_usage_type"] == "public-domain"
    assert metadata["source"]["provenance_url"].startswith("https://commons.wikimedia.org/")


def test_real_video_lessons_carry_playable_media_and_a_poster() -> None:
    """Real content means a real file, not a level label over an empty player."""

    for lesson_id, language in (
        ("en-science-cosmic-calendar", "en"),
        ("zh-technology-search-wikipedia", "zh"),
    ):
        lesson = catalog_lesson(lesson_id)
        assert lesson is not None
        metadata = lesson_metadata(lesson)

        assert metadata["playback_kind"] == "video"
        assert metadata["poster_url"].startswith("https://thumb.wikimedia.org/")
        assert lesson.playback.url.startswith("https://upload.wikimedia.org/")
        assert lesson.playback.url.endswith(".webm")

        # Rights ride with the media object, never beside it.
        assert metadata["source"]["rights_review_status"] == "verified"
        assert metadata["source"]["license"]
        assert metadata["source"]["provenance_url"].startswith("https://commons.wikimedia.org/")

        # A real excerpt over a real duration, with a real transcript inside it.
        assert 0 < lesson.excerpt_start_ms < lesson.excerpt_end_ms <= lesson.source.duration_ms
        segments = lesson.media_object.transcript.segments
        assert len(segments) >= 6
        assert all(lesson.excerpt_start_ms <= s.start_ms < s.end_ms <= lesson.excerpt_end_ms for s in segments)
        assert all(s.original_text.strip() for s in segments)

        # Level is an honest estimate until a human reviews it.
        assert metadata["level_source"] == "deterministic-estimate"
        assert metadata["reviewed_level"] is None
        assert lesson.source.language == language
        assert set(lesson.available_modes) == {"listen", "active", "dictation", "shadowing"}


def test_media_and_poster_urls_are_validated_at_the_catalog_boundary() -> None:
    """One provenance rule, enforced where the media object is built.

    The players sanitize at the edge, but an editorial pipeline must not be able
    to introduce a source they would then silently drop.
    """

    from writing_coach.listening_catalog import _load_source

    def source(**overrides: object) -> dict[str, object]:
        base = {
            "source_media_id": "s1", "source_url": "https://commons.wikimedia.org/wiki/File:x",
            "source_provider": "wikimedia-commons", "source_type": "licensed-video",
            "source_title": "t", "source_creator": "c", "language": "en", "duration_ms": 10000,
            "playback": {"provider": "wikimedia-commons", "kind": "video", "url": "https://upload.wikimedia.org/x.webm"},
            "poster_url": "https://upload.wikimedia.org/thumb/x.jpg",
            "rights": {"license_name": "CC BY 3.0", "license_url": "https://creativecommons.org/licenses/by/3.0/",
                       "provenance_url": "https://commons.wikimedia.org/wiki/File:x",
                       "allowed_usage_type": "creative-commons-attribution", "review_status": "verified"},
            "segments": [{"segment_id": "s1:000", "start_ms": 0, "end_ms": 5000, "original_text": "hello"}],
        }
        base.update(overrides)
        return base

    assert _load_source(source()).poster_url.startswith("https://upload.wikimedia.org/")

    hostile = (
        "https://evil.example/x.jpg",
        "http://upload.wikimedia.org/x.jpg",
        # `urlsplit(...).hostname` reports the allowlisted host for both of
        # these, which the web and native clients reject, so the server must
        # name the rules rather than lean on hostname alone.
        "https://user:password@upload.wikimedia.org/x.jpg",
        "https://upload.wikimedia.org:8443/x.jpg",
        "https://upload.wikimedia.org.evil.example/x.jpg",
    )
    for bad_poster in hostile:
        try:
            _load_source(source(poster_url=bad_poster))
        except ValueError as exc:
            assert "poster_url" in str(exc)
        else:
            raise AssertionError(f"poster {bad_poster} must be rejected")

    for bad_url in tuple(item.replace(".jpg", ".webm") for item in hostile):
        try:
            _load_source(source(playback={"provider": "wikimedia-commons", "kind": "video", "url": bad_url}))
        except ValueError as exc:
            assert "playback url" in str(exc)
        else:
            raise AssertionError(f"playback {bad_url} must be rejected")

    # An absent poster stays absent rather than becoming an error.
    assert _load_source(source(poster_url="")).poster_url == ""


def test_discovery_rails_follow_the_product_spec() -> None:
    """LISTENING_PRODUCT_SPEC 3.4/3.5: useful rails, real media leading."""

    from writing_coach.listening_catalog import discovery_rank, discovery_sections, is_real_media

    for language in ("en", "zh"):
        response = listening_library(language=language, level=None, topic=None, tag=None)
        ids = [item["lesson_id"] for item in response["items"]]
        rails = {section["id"]: section["item_ids"] for section in response["sections"]}

        # 3.5: the first lesson offered is real poster-backed video, not seed audio.
        first = catalog_lesson(ids[0])
        assert is_real_media(first), f"{language} discovery must lead with real media"

        # Recommended leads with the same real media rather than seed audio.
        assert rails["recommended"][0] == ids[0]

        # 3.4: topical rails exist and are populated, not just level buckets.
        assert rails.get("science-technology"), f"{language} needs a science/technology rail"
        assert rails.get("audio-practice"), f"{language} seed audio belongs in its own rail"

        # A rail never lists a lesson twice, and never one outside this language.
        for rail, members in rails.items():
            assert len(members) == len(set(members)), f"{rail} repeats a lesson"
            assert set(members) <= set(ids), f"{rail} leaks a lesson from another language"

        # 3.4: `popular` is allowed only with real data, and there is none.
        assert not rails.get("popular"), "popular must stay empty without real popularity data"

    # Ranking is deterministic: same input, same order.
    lessons = [catalog_lesson(i) for i in ("en-science-cosmic-calendar", "en-daily-pen-in-my-bag")]
    assert sorted(lessons, key=discovery_rank)[0].lesson_id == "en-science-cosmic-calendar"

    # Derived membership does not lose an explicitly authored section.
    seeded = catalog_lesson("en-daily-pen-in-my-bag")
    assert set(seeded.sections) - {"popular"} <= set(discovery_sections(seeded))


def test_unknown_curated_lesson_is_not_fabricated() -> None:
    try:
        open_listening_library_lesson("missing", "vi")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("missing lesson must be rejected")


def test_every_lesson_carries_a_type_the_baseline_names_or_none() -> None:
    """ContentCard.type (D-066): derived from playback, topic and tags, never guessed."""
    from writing_coach.listening_catalog import CONTENT_TYPES, content_type

    kinds = {lesson.lesson_id: content_type(lesson) for lesson in CATALOG}
    assert set(kinds.values()) <= {*CONTENT_TYPES, None}
    assert kinds["en-daily-pen-in-my-bag"] == "dialogue"
    assert kinds["en-travel-rainy-day-taxi"] == "dialogue"
    assert kinds["zh-culture-nationalities"] == "culture"
    # Real playable video is a video whatever else its tags say.
    assert kinds["en-science-cosmic-calendar"] == "video"
    assert kinds["zh-technology-search-wikipedia"] == "video"
    for lesson in CATALOG:
        assert lesson_metadata(lesson)["content_type"] == kinds[lesson.lesson_id]
    # The documented set is the baseline's: nothing here is a type the chips do not name.
    assert set(CONTENT_TYPES) == {"video", "interview", "podcast", "speech", "culture", "dialogue", "story", "situation"}
