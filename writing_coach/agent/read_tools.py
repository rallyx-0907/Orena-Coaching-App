"""The Slice 1b read tools: Vocabulary review and the Writing review (spec §8).

Each calls the service that already answers the learner's own screen, for the
authenticated learner and the session's language (the turn runs it inside that
learner's request context), in English and Chinese alike. None writes.

- `get_due_review_summary` - `becoming_library.library_summary`: how many words
  are due now and tomorrow, and the ladder counts.
- `get_due_vocabulary` - `becoming_library.list_library_vocabulary` with
  `status="due"`: the words due, most overdue first.
- `get_current_writing_evaluation` - the stored review of one essay in the
  Writing review contract (`writing_contract.project_review`), read through the
  app's own `essay_review` composition, which is handed in; every issue is
  evidence (`writing.evaluation`) the answer can cite.

Slice 1c adds the rest of the Vocabulary and Writing capabilities:
`get_saved_word_state` and `get_word_detail` (the library's saved state and
the catalogue's entry, no provider call), `get_writing_feedback_items` (one
review's issues by kind) and `get_writing_history_summary` (the app's own
error-memory read, handed in).

Results are bounded to the tool limit by construction, measured in UTF-8
bytes rather than characters, so a Chinese review fits as surely as an English
one: text is clipped, then items are dropped from the end until the result fits.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from writing_coach import becoming_library
from writing_coach.vocabulary_library import normalize_vocabulary_word
from writing_coach.agent.tools import AgentTool, LearnerScope, ToolEvidence, ToolPermission, ToolResult

BOTH = ("en", "zh-CN")
MAX_DUE_WORDS = 10
MAX_ISSUES = 6
# Below the registry's 8 KB tool limit, whatever the script of the text.
RESULT_BUDGET_BYTES = 7 * 1024

WritingReviewReader = Callable[[int], Mapping[str, Any] | None]


# What a result with nothing flagged means - and does not (the evaluator marks what it finds).
NO_MARKED_ERROR = "The evaluator marked no error here. That is not proof there is none; it is not praise."


def _clip(value: object, limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


class NoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DueWordsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=5, ge=1, le=MAX_DUE_WORDS)


class EssayArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    essay_id: str = Field(pattern=r"^[0-9]{1,12}$", description="The essay id in view (context.in_view.essay_id).")


def _due_review_summary(learner: LearnerScope, args: BaseModel) -> ToolResult:
    counts = becoming_library.library_summary().get("summary") or {}
    data = {key: int(counts.get(key) or 0) for key in ("due", "due_next_day", "total", "learning", "mastered")}
    evidence = ToolEvidence(
        id="due",
        source="vocabulary.review",
        ref={"scope": "due"},
        excerpt={"due": data["due"], "due_next_day": data["due_next_day"]},
    )
    return ToolResult(
        summary=f"{data['due']} words due now, {data['due_next_day']} tomorrow",
        data=data,
        evidence=(evidence,),
        count=data["due"],
    )


def _fit(build: Callable[[int], ToolResult], count: int) -> ToolResult:
    """The result with as many of the `count` items as fit the byte budget."""

    for keep in range(count, -1, -1):
        result = build(keep)
        if result.size_bytes() <= RESULT_BUDGET_BYTES:
            return result
    return result


def _due_vocabulary(learner: LearnerScope, args: DueWordsArguments) -> ToolResult:
    page = becoming_library.list_library_vocabulary(limit=args.limit, status="due", order="due")
    items = []
    for row in page.get("items") or ():
        meanings = row.get("short_meanings")
        meaning = meanings[0] if isinstance(meanings, list) and meanings else row.get("definition")
        items.append(
            {
                "word": _clip(row.get("word"), 60),
                "meaning": _clip(meaning, 80),
                "stage": _clip(row.get("stage_label"), 40),
                "lapses": int(row.get("lapse_count") or 0),
                "next_review_at": row.get("next_review_at"),
            }
        )
    total = int(page.get("total") or len(items))

    def build(keep: int) -> ToolResult:
        shown = items[:keep]
        return ToolResult(
            summary=f"{len(shown)} of {total} due words", data={"items": shown, "total": total}, count=total
        )

    return _fit(build, len(items))


def _writing_evaluation(read: WritingReviewReader) -> Callable[[LearnerScope, EssayArguments], ToolResult]:
    def handler(learner: LearnerScope, args: EssayArguments) -> ToolResult:
        review = read(int(args.essay_id))
        if review is None:
            return ToolResult(summary="no such essay for this learner", data={"found": False}, count=0)
        issues = [issue for issue in review.get("issues") or () if isinstance(issue, Mapping)]

        def build(keep: int) -> ToolResult:
            kept = issues[:keep]
            evidence = tuple(
                ToolEvidence(
                    id=f"issue{index}",
                    source="writing.evaluation",
                    ref={"essay_id": args.essay_id, "path": f"issues[{index}]"},
                    excerpt={
                        "fragment": _clip(issue.get("fragment"), 120),
                        "correction": _clip(issue.get("correction"), 120),
                        "kind": _clip(issue.get("kind"), 40),
                    },
                )
                for index, issue in enumerate(kept)
            )
            data = {
                "found": True,
                "essay_id": args.essay_id,
                "summary": _clip(review.get("summary"), 300),
                **({"note": NO_MARKED_ERROR} if not issues else {}),
                "issue_count": len(issues),
                "issues": [
                    {
                        "evidence": f"issues[{index}]",
                        "fragment": _clip(issue.get("fragment"), 120),
                        "correction": _clip(issue.get("correction"), 120),
                        "why": _clip(issue.get("why"), 200),
                        "rule": _clip(issue.get("rule"), 120),
                        "kind": _clip(issue.get("kind"), 40),
                    }
                    for index, issue in enumerate(kept)
                ],
            }
            return ToolResult(
                summary=f"{len(issues)} issues in essay {args.essay_id}, {len(kept)} shown",
                data=data,
                evidence=evidence,
                count=len(issues),
            )

        return _fit(build, min(len(issues), MAX_ISSUES))

    return handler


def read_tools(*, writing_review: WritingReviewReader) -> tuple[AgentTool, ...]:
    return (
        AgentTool(
            name="get_due_review_summary",
            description="How many of the learner's saved words are due for review now and tomorrow.",
            input_model=NoArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.becoming_library:library_summary",
            languages=BOTH,
            label_key="tool.get_due_review_summary",
            handler=_due_review_summary,
        ),
        AgentTool(
            name="get_due_vocabulary",
            description="The learner's words due for review, most overdue first, with meaning and review stage.",
            input_model=DueWordsArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.becoming_library:list_library_vocabulary",
            languages=BOTH,
            label_key="tool.get_due_vocabulary",
            handler=_due_vocabulary,
        ),
        AgentTool(
            name="get_current_writing_evaluation",
            description=(
                "The stored review of one of the learner's essays: summary and issues, each issue with the "
                "fragment, correction, reason and rule. Each issue is evidence you can cite."
            ),
            input_model=EssayArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.persistence.learning_repository:PostgresLearningRepository.get_essay",
            languages=BOTH,
            label_key="tool.get_current_writing_evaluation",
            handler=_writing_evaluation(writing_review),
        ),
    )


# --- Slice 1c: the rest of the Vocabulary and Writing capabilities ---------------------------

WritingHistoryReader = Callable[[], Mapping[str, Any]]
MAX_WORDS = 10
MAX_HISTORY_CATEGORIES = 8
ISSUE_KINDS = ("grammar", "naturalness", "punctuation", "register", "vocabulary")


class WordsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    words: list[str] = Field(min_length=1, max_length=MAX_WORDS, description="Words in the language being learned.")


class WordArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=60, description="One word or phrase in the language being learned.")


class FeedbackArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    essay_id: str = Field(pattern=r"^[0-9]{1,12}$", description="The essay id in view (context.in_view.essay_id).")
    kind: str | None = Field(default=None, description=f"Only issues of this kind: {', '.join(ISSUE_KINDS)}.")


def _state_of(item: Mapping[str, Any] | None) -> dict[str, Any]:
    if not item:
        return {"saved": False}
    return {
        "saved": True,
        "stage": _clip(item.get("stage_label"), 40),
        "due": bool(item.get("due")),
        "lapses": int(item.get("lapse_count") or 0),
        "next_review_at": item.get("next_review_at"),
    }


def _saved_word_state(learner: LearnerScope, args: WordsArguments) -> ToolResult:
    words = [word.strip() for word in args.words if word.strip()]
    states = becoming_library.saved_vocabulary_state(tuple(words))
    rows = []
    for word in words:
        key = normalize_vocabulary_word(word) or word.casefold()
        rows.append({"word": _clip(word, 60), **_state_of(states.get(key))})
    saved = [row for row in rows if row["saved"]]

    def build(keep: int) -> ToolResult:
        shown = saved[:keep]
        return ToolResult(
            summary=f"{len(saved)} of {len(rows)} words saved",
            data={"words": rows},
            evidence=tuple(
                ToolEvidence(
                    id=f"word{index}",
                    source="vocabulary.review",
                    ref={"text": row["word"]},
                    excerpt={"saved": True, "stage": row["stage"], "due": row["due"]},
                )
                for index, row in enumerate(shown)
            ),
            count=len(saved),
        )

    return _fit(build, len(saved))


def _texts(value: object, limit: int, length: int) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        text = item.get("text") if isinstance(item, Mapping) else item
        if isinstance(text, str) and text.strip():
            out.append(_clip(text, length))
        if len(out) >= limit:
            break
    return out


def _word_detail(learner: LearnerScope, args: WordArguments) -> ToolResult:
    word = args.text.strip()
    entry = becoming_library.catalog_entry_for(word) or {}
    state = becoming_library.saved_vocabulary_state((word,))
    saved = state.get(normalize_vocabulary_word(word) or word.casefold())
    translations = entry.get("support_translations") if isinstance(entry.get("support_translations"), Mapping) else {}
    data = {
        "word": _clip(entry.get("word") or word, 60),
        "in_catalog": bool(entry),
        "part_of_speech": _clip(entry.get("part_of_speech"), 40) or None,
        "level": _clip(entry.get("level"), 20) or None,
        # The seed catalogue writes `definition`; the published one (DB) writes `detailed_definitions`.
        "definition": next(iter(_texts(entry.get("definition") or entry.get("detailed_definitions"), 1, 200)), None),
        "translations": {str(code): _clip(text, 120) for code, text in list(translations.items())[:3]},
        "readings": _texts(entry.get("readings") or entry.get("reading") or entry.get("pinyin"), 3, 60),
        "examples": _texts(entry.get("examples"), 2, 160),
        **_state_of(saved),
    }
    return ToolResult(
        summary=f"{data['word']}: {'in' if entry else 'not in'} the catalogue, {'saved' if saved else 'not saved'}",
        data=data,
        count=1 if entry or saved else 0,
    )


def _feedback_items(read: WritingReviewReader) -> Callable[[LearnerScope, FeedbackArguments], ToolResult]:
    def handler(learner: LearnerScope, args: FeedbackArguments) -> ToolResult:
        review = read(int(args.essay_id))
        if review is None:
            return ToolResult(summary="no such essay for this learner", data={"found": False}, count=0)
        issues = [
            (index, issue)
            for index, issue in enumerate(review.get("issues") or ())
            if isinstance(issue, Mapping) and (args.kind is None or issue.get("kind") == args.kind)
        ]
        strengths = _clip(review.get("strengths"), 300)

        def build(keep: int) -> ToolResult:
            kept = issues[:keep]
            return ToolResult(
                summary=f"{len(issues)} {args.kind or 'all'} issues in essay {args.essay_id}",
                data={
                    "found": True,
                    "essay_id": args.essay_id,
                    "kind": args.kind,
                    "strengths": strengths,
                    **({"note": NO_MARKED_ERROR} if not issues else {}),
                    "issues": [
                        {
                            "evidence": f"issues[{index}]",
                            "fragment": _clip(issue.get("fragment"), 120),
                            "correction": _clip(issue.get("correction"), 120),
                            "why": _clip(issue.get("why"), 200),
                            "kind": _clip(issue.get("kind"), 40),
                        }
                        for index, issue in kept
                    ],
                },
                evidence=tuple(
                    ToolEvidence(
                        id=f"issue{index}",
                        source="writing.evaluation",
                        ref={"essay_id": args.essay_id, "path": f"issues[{index}]"},
                        excerpt={
                            "fragment": _clip(issue.get("fragment"), 120),
                            "correction": _clip(issue.get("correction"), 120),
                            "kind": _clip(issue.get("kind"), 40),
                        },
                    )
                    for index, issue in kept
                ),
                count=len(issues),
            )

        return _fit(build, min(len(issues), MAX_ISSUES))

    return handler


def _history_summary(read: WritingHistoryReader) -> Callable[[LearnerScope, BaseModel], ToolResult]:
    def handler(learner: LearnerScope, args: BaseModel) -> ToolResult:
        memory = read() or {}
        categories = [item for item in memory.get("items") or () if isinstance(item, Mapping)]
        categories.sort(key=lambda item: (-int(item.get("total") or 0), str(item.get("category"))))
        rows = [
            {
                "category": _clip(item.get("category"), 40),
                "total": int(item.get("total") or 0),
                "older": int(item.get("older") or 0),
                "newer": int(item.get("newer") or 0),
                "first_seen": _clip(item.get("first_seen"), 10),
                "last_seen": _clip(item.get("last_seen"), 10),
            }
            for item in categories[:MAX_HISTORY_CATEGORIES]
        ]
        revisions = int(memory.get("revision_count") or 0)

        def build(keep: int) -> ToolResult:
            kept = rows[:keep]
            return ToolResult(
                summary=f"{len(categories)} error categories over {revisions} versions",
                data={
                    "revision_count": revisions,
                    "categories": kept,
                    **({"note": NO_MARKED_ERROR} if revisions and not categories else {}),
                },
                evidence=tuple(
                    ToolEvidence(
                        id=f"history{index}",
                        source="writing.evaluation",
                        ref={"scope": "history", "category": row["category"]},
                        excerpt={"total": row["total"], "older": row["older"], "newer": row["newer"]},
                    )
                    for index, row in enumerate(kept)
                ),
                count=len(categories),
            )

        return _fit(build, len(rows))

    return handler


def more_read_tools(*, writing_review: WritingReviewReader, writing_history: WritingHistoryReader) -> tuple[AgentTool, ...]:
    return (
        AgentTool(
            name="get_saved_word_state",
            description="For up to ten words in the language being learned: whether the learner saved each, "
            "its review stage and whether it is due.",
            input_model=WordsArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.becoming_library:saved_vocabulary_state",
            languages=BOTH,
            label_key="tool.get_saved_word_state",
            handler=_saved_word_state,
        ),
        AgentTool(
            name="get_word_detail",
            description="One word from the catalogue: part of speech, level, definition, readings, examples, "
            "and whether the learner saved it.",
            input_model=WordArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.becoming_library:catalog_entry_for",
            languages=BOTH,
            label_key="tool.get_word_detail",
            handler=_word_detail,
        ),
        AgentTool(
            name="get_writing_feedback_items",
            description="The issues of one essay's review, optionally of one kind, with the review's strengths. "
            "Each issue is evidence you can cite.",
            input_model=FeedbackArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.persistence.learning_repository:PostgresLearningRepository.get_essay",
            languages=BOTH,
            label_key="tool.get_writing_feedback_items",
            handler=_feedback_items(writing_review),
        ),
        AgentTool(
            name="get_writing_history_summary",
            description="Across the learner's writing: which error categories recur, how often, and whether they "
            "appear more in older or newer versions. Each category is evidence you can cite.",
            input_model=NoArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.writing_analytics:parse_persisted_error_events",
            languages=BOTH,
            label_key="tool.get_writing_history_summary",
            handler=_history_summary(writing_history),
        ),
    )
