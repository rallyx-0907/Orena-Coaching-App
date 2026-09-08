"""Progress belongs to a lesson, not to the media it was cut from.

One source can carry several curated excerpts:

    source movie-X
      lesson A  00:30-01:05
      lesson B  02:10-02:55

Keyed by asset_id, finishing lesson A made lesson B look already started, and
the two shared a row wherever they shared a segment. That is a data-integrity
bug about a learner's real work, so the fix is tested from both directions: A
keeps its progress, and B inherits nothing.

Shared media identity and learner progress identity are different things. The
asset stays as provenance; the lesson owns the progress.
"""

from __future__ import annotations

import pytest

from writing_coach.listening_api import resolve_progress_lesson
from writing_coach.persistence.models import ListeningProgress, ShadowingProgress


# --- the durable schema says lesson, and keeps asset provenance -------------

def test_progress_tables_are_unique_per_lesson_not_per_asset() -> None:
    for model, name in ((ListeningProgress, "listening"), (ShadowingProgress, "shadowing")):
        uniques = {
            tuple(column.name for column in constraint.columns)
            for constraint in model.__table__.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        assert ("user_id", "language_code", "lesson_id", "segment_id") in uniques, name
        assert ("user_id", "language_code", "asset_id", "segment_id") not in uniques, (
            f"{name} progress must no longer be identified by the media asset")
        # Provenance is kept, not traded away for the fix.
        assert "asset_id" in model.__table__.columns
        assert "lesson_id" in model.__table__.columns


def test_the_migration_backfills_only_unambiguous_assets() -> None:
    """The rule that protects real learner history from a guess."""

    import importlib.util
    from pathlib import Path

    path = (Path(__file__).resolve().parents[1]
            / "migrations/versions/20260903_0005_lesson_scoped_progress.py")
    spec = importlib.util.spec_from_file_location("lesson_scoped_progress", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    mapping = module._unambiguous_asset_lessons()

    from writing_coach.listening_catalog import load_catalog
    _sources, lessons = load_catalog()
    by_asset: dict[str, list[str]] = {}
    for lesson in lessons:
        by_asset.setdefault(lesson.source.source_media_id, []).append(lesson.lesson_id)

    for asset, found in by_asset.items():
        if len(found) == 1:
            assert mapping[asset] == found[0]
        else:
            assert asset not in mapping, (
                f"{asset} has {len(found)} lessons and must not be backfilled to one")

    assert module.down_revision == "20260828_0004"
    source = path.read_text(encoding="utf-8")
    for banned in ("ORDER BY", "LIMIT 1", "first", "latest"):
        assert f"{banned} lesson" not in source.lower()


# --- the API refuses to write progress against the wrong lesson -------------

class FakeSegment:
    def __init__(self, segment_id: str) -> None:
        self.segment_id = segment_id


class FakeTranscript:
    def __init__(self, ids) -> None:
        self.segments = tuple(FakeSegment(i) for i in ids)


class FakeLesson:
    def __init__(self, lesson_id: str, asset_id: str, segment_ids, language="en") -> None:
        self.lesson_id = lesson_id
        self.source = type("S", (), {"source_media_id": asset_id, "language": language})()
        self.media_object = type("M", (), {"transcript": FakeTranscript(segment_ids)})()


ASSET = "movie-X"
LESSON_A = FakeLesson("movie-x-excerpt-a", ASSET, ["movie-X:001", "movie-X:002"])
LESSON_B = FakeLesson("movie-x-excerpt-b", ASSET, ["movie-X:040", "movie-X:041"])


@pytest.fixture
def two_excerpts(monkeypatch):
    import writing_coach.listening_api as api
    monkeypatch.setattr(api, "catalog_lessons", lambda **kwargs: (LESSON_A, LESSON_B))
    monkeypatch.setattr(api, "current_language_code", lambda: "en")
    monkeypatch.setattr(api, "preview_visible", lambda request: False)


@pytest.fixture
def one_excerpt(monkeypatch):
    import writing_coach.listening_api as api
    monkeypatch.setattr(api, "catalog_lessons", lambda **kwargs: (LESSON_A,))
    monkeypatch.setattr(api, "current_language_code", lambda: "en")
    monkeypatch.setattr(api, "preview_visible", lambda request: False)


def test_a_valid_lesson_and_segment_resolve(two_excerpts) -> None:
    assert resolve_progress_lesson(
        asset_id=ASSET, lesson_id="movie-x-excerpt-b",
        segment_id="movie-X:040") == "movie-x-excerpt-b"


def test_a_segment_from_another_lesson_is_refused(two_excerpts) -> None:
    """lesson A + a segment that lives in lesson B must not write a row."""

    with pytest.raises(Exception) as caught:
        resolve_progress_lesson(
            asset_id=ASSET, lesson_id="movie-x-excerpt-a", segment_id="movie-X:040")
    assert "segment" in repr(caught.value).lower()


def test_an_unknown_lesson_is_refused(two_excerpts) -> None:
    with pytest.raises(Exception):
        resolve_progress_lesson(
            asset_id=ASSET, lesson_id="not-a-lesson", segment_id="movie-X:001")


def test_a_lesson_from_another_asset_is_refused(two_excerpts) -> None:
    with pytest.raises(Exception):
        resolve_progress_lesson(
            asset_id="some-other-asset", lesson_id="movie-x-excerpt-a",
            segment_id="movie-X:001")


def test_a_legacy_client_resolves_only_when_unambiguous(one_excerpt) -> None:
    """Backward compatibility, but never by choosing between candidates."""

    assert resolve_progress_lesson(
        asset_id=ASSET, lesson_id="", segment_id="movie-X:001") == "movie-x-excerpt-a"


def test_a_legacy_client_fails_truthfully_when_ambiguous(two_excerpts) -> None:
    with pytest.raises(Exception) as caught:
        resolve_progress_lesson(asset_id=ASSET, lesson_id="", segment_id="movie-X:001")
    assert "lesson" in repr(caught.value).lower()


def test_an_asset_with_no_lessons_stays_legacy_rather_than_inventing_one(monkeypatch) -> None:
    import writing_coach.listening_api as api
    monkeypatch.setattr(api, "catalog_lessons", lambda **kwargs: ())
    monkeypatch.setattr(api, "current_language_code", lambda: "en")
    monkeypatch.setattr(api, "preview_visible", lambda request: False)

    assert resolve_progress_lesson(
        asset_id="my-media-upload", lesson_id="", segment_id="x:001") == ""


# --- the repository keys rows by lesson -------------------------------------

def test_listening_and_shadowing_rows_are_keyed_by_lesson() -> None:
    """Two excerpts of one source must produce two rows, not one."""

    from writing_coach.persistence.ids import stable_uuid

    a = stable_uuid("listening-progress", "user", "en", "movie-x-excerpt-a", "movie-X:001")
    b = stable_uuid("listening-progress", "user", "en", "movie-x-excerpt-b", "movie-X:001")
    assert a != b, "the same segment id in two lessons must not collide"

    sa = stable_uuid("shadowing-progress", "user", "en", "movie-x-excerpt-a", "movie-X:001")
    sb = stable_uuid("shadowing-progress", "user", "en", "movie-x-excerpt-b", "movie-X:001")
    assert sa != sb

    from pathlib import Path
    source = (Path(__file__).resolve().parents[1]
              / "writing_coach/persistence/specialized_repository.py").read_text(encoding="utf-8")
    assert 'stable_uuid(\n            "listening-progress", self._key(), lang, lesson_id, segment_id)' in source
    assert 'stable_uuid(\n            "shadowing-progress", self._key(), lang, lesson_id, segment_id)' in source


def test_reads_can_be_scoped_to_one_lesson() -> None:
    from writing_coach.persistence.specialized_repository import (
        PostgresSpecializedLearningRepository,
    )
    import inspect

    for name in ("list_listening_progress_records", "list_shadowing_progress_records"):
        signature = inspect.signature(
            getattr(PostgresSpecializedLearningRepository, name))
        assert "lesson_id" in signature.parameters, name


# --- P1-B: Continue Learning comes from real progress ------------------------

class FakeRepository:
    """Only what Continue Learning reads. Records are what PostgreSQL returned."""

    def __init__(self, records, *, unavailable: bool = False) -> None:
        self.records = records
        self.unavailable = unavailable
        self.calls = 0

    def list_recent_listening_progress_records(self, limit: int = 20):
        self.calls += 1
        if self.unavailable:
            raise RuntimeError("Durable Active Listening progress requires PostgreSQL.")
        return self.records[:limit]


def record(lesson_id, segment_id, updated_at, **extra):
    return {"lesson_id": lesson_id, "segment_id": segment_id,
            "updated_at": updated_at, "presentation": "checked",
            "checked_attempt_count": 2, "best_exact": False, **extra}


@pytest.fixture
def repository(monkeypatch):
    import writing_coach.listening_api as api

    def install(records, **kwargs):
        repo = FakeRepository(records, **kwargs)
        monkeypatch.setattr(api, "_repository", repo)
        return repo
    return install


def continue_learning(lessons, language="en"):
    from writing_coach.listening_api import continue_learning_lessons
    return continue_learning_lessons(lessons, language=language)


def test_continue_learning_is_ordered_by_real_recency(repository) -> None:
    repository([
        record("movie-x-excerpt-b", "movie-X:040", "2026-09-03T10:00:00+00:00"),
        record("movie-x-excerpt-a", "movie-X:001", "2026-09-02T10:00:00+00:00"),
    ])
    ordered, resume = continue_learning([LESSON_A, LESSON_B])

    assert ordered == ["movie-x-excerpt-b", "movie-x-excerpt-a"], "most recent first"
    assert resume["movie-x-excerpt-b"]["segment_id"] == "movie-X:040"
    assert resume["movie-x-excerpt-a"]["asset_id"] == ASSET


def test_a_lesson_with_no_progress_never_appears(repository) -> None:
    """No fabrication: the rail is progress, not recommendation."""

    repository([record("movie-x-excerpt-a", "movie-X:001", "2026-09-03T10:00:00+00:00")])
    ordered, _ = continue_learning([LESSON_A, LESSON_B])
    assert ordered == ["movie-x-excerpt-a"]


def test_progress_for_an_invisible_lesson_is_not_surfaced(repository) -> None:
    """The visibility boundary is the same one discovery uses.

    A learner who may not see preview content must not have a preview lesson
    reappear through their own progress - the server joins against the catalog
    the caller can actually see.
    """

    repository([record("preview-only-lesson", "p:001", "2026-09-03T10:00:00+00:00")])
    ordered, resume = continue_learning([LESSON_A, LESSON_B])
    assert ordered == [] and resume == {}


def test_progress_from_another_learning_language_is_excluded(repository) -> None:
    zh_lesson = FakeLesson("zh-lesson", "zh-asset", ["zh:001"], language="zh")
    repository([record("zh-lesson", "zh:001", "2026-09-03T10:00:00+00:00")])

    ordered, _ = continue_learning([LESSON_A, zh_lesson], language="en")
    assert ordered == [], "EN discovery must not resume a ZH lesson"

    ordered_zh, _ = continue_learning([LESSON_A, zh_lesson], language="zh")
    assert ordered_zh == ["zh-lesson"], "and ZH must resume its own"


def test_legacy_progress_without_a_lesson_is_skipped(repository) -> None:
    """An unassigned legacy row has nothing truthful to resume."""

    repository([record("", "movie-X:001", "2026-09-03T10:00:00+00:00")])
    ordered, _ = continue_learning([LESSON_A, LESSON_B])
    assert ordered == []


def test_a_removed_segment_resumes_at_the_lesson_start(repository) -> None:
    """Content was revised; do not seek to a segment that no longer exists."""

    repository([record("movie-x-excerpt-a", "movie-X:999", "2026-09-03T10:00:00+00:00")])
    ordered, resume = continue_learning([LESSON_A, LESSON_B])

    assert ordered == ["movie-x-excerpt-a"], "the lesson still resumes"
    assert resume["movie-x-excerpt-a"]["segment_id"] == "", "no phantom segment"


def test_one_lesson_appears_once_however_many_segments_have_progress(repository) -> None:
    repository([
        record("movie-x-excerpt-a", "movie-X:002", "2026-09-03T10:00:00+00:00"),
        record("movie-x-excerpt-a", "movie-X:001", "2026-09-02T10:00:00+00:00"),
    ])
    ordered, resume = continue_learning([LESSON_A, LESSON_B])
    assert ordered == ["movie-x-excerpt-a"]
    # The most recent segment is the one to resume at.
    assert resume["movie-x-excerpt-a"]["segment_id"] == "movie-X:002"


def test_the_rail_is_bounded(repository) -> None:
    from writing_coach.listening_api import CONTINUE_LEARNING_LIMIT

    lessons = [FakeLesson(f"lesson-{i}", ASSET, [f"movie-X:{i:03d}"]) for i in range(20)]
    repository([record(f"lesson-{i}", f"movie-X:{i:03d}",
                       f"2026-09-{(i % 28) + 1:02d}T10:00:00+00:00") for i in range(20)])

    ordered, _ = continue_learning(lessons)
    assert len(ordered) == CONTINUE_LEARNING_LIMIT


def test_discovery_still_renders_when_progress_is_unavailable(repository) -> None:
    """A SQLite runtime has no durable progress; the library must not break."""

    repository([], unavailable=True)
    ordered, resume = continue_learning([LESSON_A, LESSON_B])
    assert ordered == [] and resume == {}


def test_continue_learning_is_not_client_reconstructed() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1]
              / "writing_coach/listening_api.py").read_text(encoding="utf-8")
    assert "continue_learning_lessons(ranked, language=selected_language)" in source
    assert "list_recent_listening_progress_records" in source
