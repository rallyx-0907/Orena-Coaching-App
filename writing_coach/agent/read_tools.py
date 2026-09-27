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

Results are bounded to the tool limit by construction, measured in UTF-8
bytes rather than characters, so a Chinese review fits as surely as an English
one: text is clipped, then items are dropped from the end until the result fits.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from writing_coach import becoming_library
from writing_coach.agent.tools import AgentTool, LearnerScope, ToolEvidence, ToolPermission, ToolResult

BOTH = ("en", "zh-CN")
MAX_DUE_WORDS = 10
MAX_ISSUES = 6
# Below the registry's 8 KB tool limit, whatever the script of the text.
RESULT_BUDGET_BYTES = 7 * 1024

WritingReviewReader = Callable[[int], Mapping[str, Any] | None]


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
