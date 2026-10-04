"""Speaking, Listening and Reading read tools (Slice 2).

Each reads through what the app already serves, handed in by `app.py` as
callables (`AppReads`), in the learner's session scope - the request context
`learner_context` sets, which the repositories read. The learner records
(speaking attempts, listening progress, reading attempts) exist on PostgreSQL
only; on any other runtime the repository raises and the turn reports the tool
unavailable, never an empty history that is not true.

Speaking (the stored, audio-free attempt records, D-076):
- `get_pronunciation_history` - recent attempts, optionally for one content,
  with the averages the app reports.
- `get_pronunciation_attempt` - one attempt by `attempt_id` (no read-by-id
  exists, N-9: the list, filtered by the content and line the client sent, then
  the id). Each word the provider flagged is evidence: "flagged" is the
  provider's error type being set, never a score threshold (D-084).
- `get_pronunciation_word_detail` - one word of an attempt, with its phonemes.

Listening:
- `get_current_listening_context` - the curated lesson in view, from the
  catalogue (never the lesson route: that one translates missing meanings
  through a provider and writes a cache).
- `get_listening_attempt` - the learner's dictation progress on that lesson,
  one row per line, keyed by the lesson's media asset.

Reading:
- `get_current_reading_context` - the article or book chapter in view: shared
  content, in the learner's language only. Content ids are the new UI's
  (`article:<id>`, `book:<book>:<chapter>`), so a `navigate` can name them.
- `get_reading_progress` - the learner's reading attempts: scores only (not
  `ability()`, which refreshes a stored projection - a write).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from writing_coach.agent.labels import pronunciation_label
from writing_coach.agent.read_tools import BOTH, _clip, _fit
from writing_coach.agent.tools import AgentTool, LearnerScope, ToolEvidence, ToolPermission, ToolResult

SpeakingAttempts = Callable[..., Sequence[Mapping[str, Any]]]  # list_speaking_attempt_records(limit, *, asset_id, segment_id)
SpeakingProgress = Callable[[], Mapping[str, Any]]  # speaking_progress()
ListeningLesson = Callable[[str], Mapping[str, Any] | None]  # lesson_metadata(catalog_lesson(id)) or None
ListeningProgress = Callable[[str], Sequence[Mapping[str, Any]]]  # list_listening_progress_records(asset_id)
ReadingArticle = Callable[[str], Mapping[str, Any] | None]  # get_published_article(uuid)
ReadingChapter = Callable[[str, str], Mapping[str, Any] | None]  # get_chapter(book, chapter)
ReadingEvidence = Callable[[int], Sequence[Mapping[str, Any]]]  # list_evidence(limit)

_ID = r"^[A-Za-z0-9._:\-]{1,128}$"
MAX_ATTEMPTS = 10
MAX_WORDS = 40
MAX_LINES = 40


def _none(*args: Any, **kwargs: Any) -> Any:
    return None


def _empty(*args: Any, **kwargs: Any) -> list:
    return []


def _no_progress() -> dict:
    return {}


def flagged(word: Mapping[str, Any]) -> bool:
    """The provider marked it (D-084): its error type is set. No threshold."""

    return str(word.get("error_type") or "").strip().casefold() not in ("", "none")


def server_scored(row: Mapping[str, Any]) -> bool:
    """A dictation score the server computed (D-103.2). A pre-D4 row, or one that does not say, is the client's
    own number: unverified (D-104 H-14), so it is never stated as a result. Mirrors the repository's default."""

    return str(row.get("score_source") or "client") == "server"


UNVERIFIED_NOTE = (
    "A line with verified false has no score the server could check (written before server scoring): its "
    "accuracy and exact are null. Do not say the learner got it right or wrong; say it is not verified."
)


def _score(value: object) -> float | None:
    return round(float(value), 1) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


# --- Speaking --------------------------------------------------------------------------------


class HistoryArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_id: str | None = Field(default=None, pattern=_ID, description="Only attempts on this content.")
    limit: int = Field(default=5, ge=1, le=MAX_ATTEMPTS)


class AttemptArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attempt_id: str = Field(pattern=_ID, description="context.in_view.attempt_id")
    content_id: str | None = Field(default=None, pattern=_ID, description="context.in_view.content_id")
    item_id: str | None = Field(default=None, pattern=_ID, description="the line: context.selection.id")


class WordArguments(AttemptArguments):
    word: str = Field(min_length=1, max_length=60, description="The word as the attempt lists it.")


def _attempt_summary(row: Mapping[str, Any]) -> dict:
    dimensions = row.get("dimensions") if isinstance(row.get("dimensions"), Mapping) else {}
    return {
        "attempt_id": str(row.get("id")),
        "created_at": _clip(row.get("created_at"), 32),
        "content_id": str(row.get("asset_id") or "") or None,
        "item_id": str(row.get("segment_id") or "") or None,
        "reference_text": _clip(row.get("reference_text"), 200) or None,
        "scores": {key: _score(dimensions.get(key)) for key in ("pronunciation", "fluency", "content_match")},
    }


def _history(attempts: SpeakingAttempts, progress: SpeakingProgress) -> Callable[[LearnerScope, HistoryArguments], ToolResult]:
    def handler(learner: LearnerScope, args: HistoryArguments) -> ToolResult:
        rows = list(attempts(args.limit, asset_id=args.content_id or None, segment_id=None))
        overall = progress() or {}
        summaries = [_attempt_summary(row) for row in rows]

        def build(keep: int) -> ToolResult:
            kept = summaries[:keep]
            return ToolResult(
                summary=f"{len(rows)} recent speaking attempts",
                data={
                    "attempts": kept,
                    "averages_over_recent": {
                        key: _score(overall.get(key))
                        for key in ("average_pronunciation", "average_fluency", "average_content_match")
                    },
                    "attempt_count": int(overall.get("attempt_count") or 0),
                },
                evidence=tuple(
                    ToolEvidence(
                        id=f"attempt{index}",
                        source="speech.pronunciation",
                        ref={"attempt_id": item["attempt_id"]},
                        excerpt={"scores": item["scores"], "reference_text": item["reference_text"]},
                    )
                    for index, item in enumerate(kept)
                ),
                count=len(rows),
            )

        return _fit(build, len(summaries))

    return handler


def _find_attempt(attempts: SpeakingAttempts, args: AttemptArguments) -> Mapping[str, Any] | None:
    rows = attempts(100, asset_id=args.content_id or None, segment_id=args.item_id or None)
    return next((row for row in rows if str(row.get("id")) == args.attempt_id), None)


def _words(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    evidence = row.get("evidence") if isinstance(row.get("evidence"), Mapping) else {}
    pronunciation = evidence.get("pronunciation") if isinstance(evidence.get("pronunciation"), Mapping) else {}
    return [w for w in pronunciation.get("words") or () if isinstance(w, Mapping)]


def _attempt(attempts: SpeakingAttempts) -> Callable[[LearnerScope, AttemptArguments], ToolResult]:
    def handler(learner: LearnerScope, args: AttemptArguments) -> ToolResult:
        row = _find_attempt(attempts, args)
        if row is None:
            return ToolResult(summary="no such attempt for this learner", data={"found": False}, count=0)
        evidence = row.get("evidence") if isinstance(row.get("evidence"), Mapping) else {}
        words = _words(row)
        indexed = [(index, word) for index, word in enumerate(words)]
        marked = [(index, word) for index, word in indexed if flagged(word)]

        def build(keep: int) -> ToolResult:
            shown = indexed[:keep]
            return ToolResult(
                summary=f"attempt {args.attempt_id}: {len(marked)} of {len(words)} words flagged by the provider",
                data={
                    "found": True,
                    **_attempt_summary(row),
                    "recognized_text": _clip(evidence.get("recognized_text") or row.get("transcript_text"), 300),
                    "words": [
                        {
                            "path": f"words[{index}]",
                            "word": _clip(word.get("word"), 60),
                            "accuracy": _score(word.get("accuracy_score")),
                            "flagged": flagged(word),
                            "error": pronunciation_label(word.get("error_type"), learner.interface) if flagged(word) else None,
                        }
                        for index, word in shown
                    ],
                    "flagged_count": len(marked),
                    "note": "Flagged is the provider's own mark. A lower score it did not flag is not an error.",
                },
                evidence=tuple(
                    ToolEvidence(
                        id=f"word{index}",
                        source="speech.pronunciation",
                        ref={"attempt_id": args.attempt_id, "path": f"words[{index}]"},
                        excerpt={
                            "word": _clip(word.get("word"), 60),
                            "accuracy": _score(word.get("accuracy_score")),
                            "error": pronunciation_label(word.get("error_type"), learner.interface),
                        },
                    )
                    for index, word in marked
                    if index < keep
                ),
                count=len(marked),
            )

        return _fit(build, min(len(indexed), MAX_WORDS))

    return handler


def _word_detail(attempts: SpeakingAttempts) -> Callable[[LearnerScope, WordArguments], ToolResult]:
    def handler(learner: LearnerScope, args: WordArguments) -> ToolResult:
        row = _find_attempt(attempts, args)
        if row is None:
            return ToolResult(summary="no such attempt for this learner", data={"found": False}, count=0)
        wanted = args.word.strip().casefold()
        match = next(
            ((index, word) for index, word in enumerate(_words(row)) if str(word.get("word") or "").casefold() == wanted),
            None,
        )
        if match is None:
            return ToolResult(summary="that word is not in this attempt", data={"found": False}, count=0)
        index, word = match
        phonemes = [
            {"phoneme": _clip(p.get("phoneme"), 16), "accuracy": _score(p.get("accuracy_score"))}
            for p in (word.get("phonemes") or ())[:20]
            if isinstance(p, Mapping)
        ]
        data = {
            "found": True,
            "attempt_id": args.attempt_id,
            "path": f"words[{index}]",
            "word": _clip(word.get("word"), 60),
            "accuracy": _score(word.get("accuracy_score")),
            "flagged": flagged(word),
            "error": pronunciation_label(word.get("error_type"), learner.interface) if flagged(word) else None,
            "phonemes": phonemes,
            "note": "Syllables, tones and timings are not stored for an attempt.",
        }
        return ToolResult(
            summary=f"{data['word']} in attempt {args.attempt_id}",
            data=data,
            evidence=(
                ToolEvidence(
                    id="word",
                    source="speech.pronunciation",
                    ref={"attempt_id": args.attempt_id, "path": data["path"]},
                    excerpt={"word": data["word"], "accuracy": data["accuracy"], "flagged": data["flagged"]},
                ),
            ),
            count=1,
        )

    return handler


# --- Listening -------------------------------------------------------------------------------


class ListeningArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_id: str = Field(pattern=_ID, description="The lesson in view: context.in_view.content_id")


def _lesson_in_language(read: ListeningLesson, learner: LearnerScope, content_id: str) -> Mapping[str, Any] | None:
    # Contract §6.1 (F-9): a Listening content id is `media:<id>`; a bare id from an older client is read as is.
    lesson = read(content_id.removeprefix("media:"))
    if not lesson or str(lesson.get("language") or "").casefold().split("-")[0] != learner.language:
        return None
    return lesson


def _listening_context(read: ListeningLesson) -> Callable[[LearnerScope, ListeningArguments], ToolResult]:
    def handler(learner: LearnerScope, args: ListeningArguments) -> ToolResult:
        lesson = _lesson_in_language(read, learner, args.content_id)
        if lesson is None:
            return ToolResult(summary="no such lesson in this language", data={"found": False}, count=0)
        lines = lesson.get("spoken_text_by_segment") if isinstance(lesson.get("spoken_text_by_segment"), Mapping) else {}
        data = {
            "found": True,
            "content_id": args.content_id,
            "title": _clip(lesson.get("title"), 160),
            "level": _clip(lesson.get("level"), 16) or None,
            "topic": _clip(lesson.get("topic"), 60) or None,
            "duration_s": round(int(lesson.get("duration_ms") or 0) / 1000) or None,
            "speech_speed": _clip(lesson.get("speech_speed"), 24) or None,
            "line_count": len(lines),
            "modes": [str(m) for m in (lesson.get("available_modes") or ())][:6],
        }
        return ToolResult(
            summary=f"listening lesson {args.content_id}: {data['title']}",
            data=data,
            evidence=(
                ToolEvidence(
                    id="lesson",
                    source="listening.dictation",
                    ref={"content_id": args.content_id},
                    excerpt={"title": data["title"], "level": data["level"], "line_count": data["line_count"]},
                ),
            ),
            count=1,
        )

    return handler


def _listening_attempt(read: ListeningLesson, progress: ListeningProgress) -> Callable[[LearnerScope, ListeningArguments], ToolResult]:
    def handler(learner: LearnerScope, args: ListeningArguments) -> ToolResult:
        lesson = _lesson_in_language(read, learner, args.content_id)
        if lesson is None:
            return ToolResult(summary="no such lesson in this language", data={"found": False}, count=0)
        asset_id = str(lesson.get("media_object_id") or args.content_id.removeprefix("media:"))  # progress is keyed by the media asset
        rows = [row for row in progress(asset_id) if isinstance(row, Mapping)]
        lines = [
            {
                "item_id": str(row.get("segment_id")),
                "checked": int(row.get("checked_attempt_count") or 0),
                "verified": server_scored(row),
                "best_accuracy": _score(row.get("best_accuracy_percent")) if server_scored(row) else None,
                "exact": bool(row.get("best_exact")) if server_scored(row) else None,
                "revealed": bool(row.get("revealed")),
                "hint_level": int(row.get("last_hint_level") or 0),
            }
            for row in rows
        ]

        def build(keep: int) -> ToolResult:
            kept = lines[:keep]
            return ToolResult(
                summary=f"{len(lines)} lines practised in lesson {args.content_id}",
                data={
                    "found": True,
                    "content_id": args.content_id,
                    "lines": kept,
                    "exact_count": sum(line["exact"] is True for line in lines),
                    "unverified_count": sum(not line["verified"] for line in lines),
                    **({"note": UNVERIFIED_NOTE} if not all(line["verified"] for line in lines) else {}),
                    "revealed_count": sum(line["revealed"] for line in lines),
                },
                evidence=tuple(
                    ToolEvidence(
                        id=f"line{index}",
                        source="listening.dictation",
                        ref={"content_id": args.content_id, "item_id": line["item_id"]},
                        excerpt={"best_accuracy": line["best_accuracy"], "exact": line["exact"], "revealed": line["revealed"]},
                    )
                    for index, line in enumerate(kept)
                ),
                count=len(lines),
            )

        return _fit(build, min(len(lines), MAX_LINES))

    return handler


# --- Reading ---------------------------------------------------------------------------------


class ReadingArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_id: str = Field(pattern=_ID, description="context.in_view.content_id, e.g. article:<id>")


class ProgressArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=5, ge=1, le=MAX_ATTEMPTS)


def _content_parts(content_id: str) -> tuple[str, list[str]]:
    kind, _, rest = content_id.partition(":")
    return (kind, rest.split(":")) if rest else ("article", [kind])


def _reading_context(article: ReadingArticle, chapter: ReadingChapter) -> Callable[[LearnerScope, ReadingArguments], ToolResult]:
    def handler(learner: LearnerScope, args: ReadingArguments) -> ToolResult:
        kind, parts = _content_parts(args.content_id)
        if kind == "article" and len(parts) == 1:
            record = article(parts[0])
            if not record or str(record.get("language") or "").casefold().split("-")[0] != learner.language:
                return ToolResult(summary="no such article in this language", data={"found": False}, count=0)
            data = {
                "found": True,
                "content_id": args.content_id,
                "kind": "article",
                "title": _clip(record.get("title"), 160),
                "level": _clip(record.get("level"), 16) or None,
                "topic": _clip(record.get("topic"), 60) or None,
                "reading_time_s": record.get("reading_time_seconds"),
                "word_count": record.get("word_count"),
                "targets": [
                    {"text": _clip(t.get("text"), 60), "meaning": _clip(t.get("meaning"), 120) or None}
                    for t in (record.get("targets") or ())[:8]
                    if isinstance(t, Mapping)
                ],
            }
        elif kind == "book" and len(parts) == 2:
            record = chapter(parts[0], parts[1])
            if not record or str(record.get("learning_language") or "").casefold().split("-")[0] != learner.language:
                return ToolResult(summary="no such chapter in this language", data={"found": False}, count=0)
            data = {
                "found": True,
                "content_id": args.content_id,
                "kind": "chapter",
                "title": _clip(record.get("title"), 160),
                "book_title": _clip(record.get("book_title"), 160),
                "author": _clip(record.get("author"), 80) or None,
                "position": record.get("position"),
            }
        else:
            return ToolResult(summary="not a reading content id", data={"found": False}, count=0)
        return ToolResult(
            summary=f"reading {data['kind']} {args.content_id}: {data['title']}",
            data=data,
            evidence=(
                ToolEvidence(
                    id="passage",
                    source="reading.comprehension",
                    ref={"content_id": args.content_id},
                    excerpt={"title": data["title"], "kind": data["kind"]},
                ),
            ),
            count=1,
        )

    return handler


def _reading_progress(evidence: ReadingEvidence) -> Callable[[LearnerScope, ProgressArguments], ToolResult]:
    def handler(learner: LearnerScope, args: ProgressArguments) -> ToolResult:
        rows = [row for row in evidence(args.limit) if isinstance(row, Mapping)]
        attempts = [
            {
                "content_id": f"article:{row.get('article_id')}",
                "title": _clip(row.get("title"), 160),
                "correct": int(row.get("correct_count") or 0),
                "total": int(row.get("total") or 0),
                "level": _clip(row.get("passage_level"), 16) or None,
                "created_at": _clip(row.get("created_at"), 32),
            }
            for row in rows
        ]

        def build(keep: int) -> ToolResult:
            kept = attempts[:keep]
            return ToolResult(
                summary=f"{len(attempts)} recent reading attempts",
                data={"attempts": kept},
                evidence=tuple(
                    ToolEvidence(
                        id=f"reading{index}",
                        source="reading.comprehension",
                        ref={"content_id": item["content_id"], "created_at": item["created_at"]},
                        excerpt={"correct": item["correct"], "total": item["total"]},
                    )
                    for index, item in enumerate(kept)
                ),
                count=len(attempts),
            )

        return _fit(build, len(attempts))

    return handler


def skill_tools(
    *,
    speaking_attempts: SpeakingAttempts = _empty,
    speaking_progress: SpeakingProgress = _no_progress,
    listening_lesson: ListeningLesson = _none,
    listening_progress: ListeningProgress = _empty,
    reading_article: ReadingArticle = _none,
    reading_chapter: ReadingChapter = _none,
    reading_evidence: ReadingEvidence = _empty,
) -> tuple[AgentTool, ...]:
    speaking_backing = "writing_coach.persistence.specialized_repository:PostgresSpecializedLearningRepository.list_speaking_attempt_records"
    return (
        AgentTool(
            name="get_pronunciation_history",
            description="The learner's recent speaking attempts (optionally on one content) with their scores, and "
            "the averages the app reports.",
            input_model=HistoryArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by=speaking_backing,
            languages=BOTH,
            label_key="tool.get_pronunciation_history",
            handler=_history(speaking_attempts, speaking_progress),
        ),
        AgentTool(
            name="get_pronunciation_attempt",
            description="One stored speaking attempt by attempt_id: scores, recognised text, and each word with "
            "whether the provider flagged it. Pass the content_id and the line (item_id) in view.",
            input_model=AttemptArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by=speaking_backing,
            languages=BOTH,
            label_key="tool.get_pronunciation_attempt",
            handler=_attempt(speaking_attempts),
        ),
        AgentTool(
            name="get_pronunciation_word_detail",
            description="One word of a stored speaking attempt: its accuracy, whether the provider flagged it, and "
            "its phonemes.",
            input_model=WordArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by=speaking_backing,
            languages=BOTH,
            label_key="tool.get_pronunciation_word_detail",
            handler=_word_detail(speaking_attempts),
        ),
        AgentTool(
            name="get_current_listening_context",
            description="The curated listening lesson in view: title, level, topic, length and number of lines.",
            input_model=ListeningArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.listening_catalog:catalog_lesson",
            languages=BOTH,
            label_key="tool.get_current_listening_context",
            handler=_listening_context(listening_lesson),
        ),
        AgentTool(
            name="get_listening_attempt",
            description="The learner's dictation progress on the lesson in view: per line, checks, best accuracy, "
            "exact, revealed.",
            input_model=ListeningArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.persistence.specialized_repository:PostgresSpecializedLearningRepository.list_listening_progress_records",
            languages=BOTH,
            label_key="tool.get_listening_attempt",
            handler=_listening_attempt(listening_lesson, listening_progress),
        ),
        AgentTool(
            name="get_current_reading_context",
            description="The article or book chapter in view (article:<id> or book:<book>:<chapter>): title, level, "
            "topic and the article's target words.",
            input_model=ReadingArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.persistence.reading_content_repository:ReadingContentRepository.get_published_article",
            languages=BOTH,
            label_key="tool.get_current_reading_context",
            handler=_reading_context(reading_article, reading_chapter),
        ),
        AgentTool(
            name="get_reading_progress",
            description="The learner's recent reading attempts: which article, how many answers were right.",
            input_model=ProgressArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.persistence.reading_evidence_repository:ReadingEvidenceRepository.list_evidence",
            languages=BOTH,
            label_key="tool.get_reading_progress",
            handler=_reading_progress(reading_evidence),
        ),
    )
