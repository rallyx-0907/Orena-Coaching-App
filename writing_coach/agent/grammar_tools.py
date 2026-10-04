"""Grammar read tools (Slice 2): R5 is the only source.

Both tools read through the app's own `/api/library/grammar*` composition - the
course, the static knowledge base keyed by Concept ID (the lesson id, which is
the contract's `grammar_id`) and the learner's completion - handed in by
`app.py` as callables, exactly as the routes serve them. No second catalogue,
no second search index, no write (completing a lesson is the learner's POST,
never a tool).

Completion is what the learner did, not what they know: the tools say so
(`completion_claim`), as the route does.

- `get_grammar_point` - one point by `grammar_id`: title, level, the quick
  reference (summary, restrictions, traps), up to three examples, completion.
- `search_grammar_points` - points whose title, id, module or objective
  contains the query, optionally at one level; each with its `grammar_id`,
  which a `navigate` to `grammar.point` may then name (contract §7).

The knowledge base explains in Vietnamese (`*_vi`); the model answers in the
support language from it, as it does from any tool result.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from writing_coach.agent.read_tools import BOTH, _clip, _texts
from writing_coach.agent.tools import AgentTool, LearnerScope, ToolEvidence, ToolPermission, ToolResult

GrammarLibraryReader = Callable[[], Mapping[str, Any]]  # app.api_grammar_library
GrammarLessonReader = Callable[[str], Mapping[str, Any] | None]  # app.api_grammar_lesson; None when not found

MAX_EXAMPLES = 3
MAX_RESULTS = 10
COMPLETION_CLAIM = "Completed means the learner finished the lesson's activity, not that they have mastered the point."


def _no_library() -> Mapping[str, Any]:
    return {"lessons": []}


def _no_lesson(grammar_id: str) -> Mapping[str, Any] | None:
    return None


class GrammarPointArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    grammar_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,95}$", description="The point's grammar_id.")


class GrammarSearchArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=60, description="Words from the point's name or purpose.")
    level: str | None = Field(default=None, max_length=12, description="Only this level, e.g. A2 or HSK3.")
    limit: int = Field(default=5, ge=1, le=MAX_RESULTS)


def _point(read: GrammarLessonReader) -> Callable[[LearnerScope, GrammarPointArguments], ToolResult]:
    def handler(learner: LearnerScope, args: GrammarPointArguments) -> ToolResult:
        lesson = read(args.grammar_id)
        if not lesson:
            return ToolResult(summary="no such grammar point in this language", data={"found": False}, count=0)
        reference = lesson.get("quick_reference") if isinstance(lesson.get("quick_reference"), Mapping) else {}
        examples = [
            {
                "target": _clip(example.get("target"), 160),
                "pinyin": _clip(example.get("pinyin"), 160) or None,
                "meaning_vi": _clip(example.get("meaning_vi") or example.get("vi"), 160) or None,
            }
            for example in (lesson.get("examples") or ())[:MAX_EXAMPLES]
            if isinstance(example, Mapping) and example.get("target")
        ]
        data = {
            "found": True,
            "grammar_id": args.grammar_id,
            "title": _clip(lesson.get("title"), 120),
            "level": _clip(lesson.get("level"), 12),
            "summary_vi": _clip(reference.get("summary_vi"), 400),
            "restrictions_vi": _texts(reference.get("restrictions"), 3, 200),
            "common_traps_vi": _texts(reference.get("common_traps"), 3, 200),
            "examples": examples,
            "completed": bool(lesson.get("completed")),
            "completion_claim": COMPLETION_CLAIM,
        }
        return ToolResult(
            summary=f"grammar point {args.grammar_id}: {data['title']} ({data['level']})",
            data=data,
            evidence=(
                ToolEvidence(
                    id="grammar",
                    source="grammar.catalog",
                    ref={"grammar_id": args.grammar_id},
                    excerpt={"title": data["title"], "level": data["level"], "completed": data["completed"]},
                ),
            ),
            count=1,
        )

    return handler


def _search(read: GrammarLibraryReader) -> Callable[[LearnerScope, GrammarSearchArguments], ToolResult]:
    def handler(learner: LearnerScope, args: GrammarSearchArguments) -> ToolResult:
        query = args.query.strip().casefold()
        level = args.level.strip().casefold() if args.level else None
        matches = []
        for lesson in read().get("lessons") or ():
            if not isinstance(lesson, Mapping):
                continue
            if level and str(lesson.get("level") or "").casefold() != level:
                continue
            haystack = " ".join(
                str(lesson.get(key) or "") for key in ("title", "id", "module", "category", "objective_vi")
            ).casefold()
            if query in haystack:
                matches.append(lesson)
        shown = matches[: args.limit]
        return ToolResult(
            summary=f"{len(matches)} grammar points match, {len(shown)} shown",
            data={
                "points": [
                    {
                        "grammar_id": str(lesson.get("id")),
                        "title": _clip(lesson.get("title"), 120),
                        "level": _clip(lesson.get("level"), 12),
                        "completed": bool(lesson.get("completed")),
                    }
                    for lesson in shown
                ],
                "total": len(matches),
                "completion_claim": COMPLETION_CLAIM,
            },
            count=len(matches),
        )

    return handler


def grammar_tools(*, library: GrammarLibraryReader = _no_library, lesson: GrammarLessonReader = _no_lesson) -> tuple[AgentTool, ...]:
    return (
        AgentTool(
            name="get_grammar_point",
            description="One grammar point by grammar_id: its summary, restrictions, common traps, examples, "
            "and whether the learner completed its lesson (activity, not mastery).",
            input_model=GrammarPointArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.languages.runtime:active_grammar_by_id",
            languages=BOTH,
            label_key="tool.get_grammar_point",
            handler=_point(lesson),
        ),
        AgentTool(
            name="search_grammar_points",
            description="Find grammar points in the language being learned by words from their name or purpose, "
            "optionally at one level; returns each point's grammar_id.",
            input_model=GrammarSearchArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.languages.runtime:active_grammar_course",
            languages=BOTH,
            label_key="tool.search_grammar_points",
            handler=_search(library),
        ),
    )
