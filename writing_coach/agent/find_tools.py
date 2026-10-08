"""find_content: listening lessons and reading articles in the learner's language, to open (R29, 2026-10-06).

The human's phone test asked Orena, by voice, to open a video in Listening; nothing could, because no tool found
content. This one lists what the learner's own library pages list - the same compositions, never re-implemented:
the listening library (curated lessons and the media an administrator imported) and the published reading
articles, in the session's learning language only, filtered by level, topic or words of the title. Each item
carries the `content_id` the contract opens it with (§6.1: `media:<id>` in listening.workspace, `article:<id>` in
reading.workspace), so a navigate to it names an id a tool returned, never an invented one.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from writing_coach.agent.tools import AgentTool, LearnerScope, ToolPermission, ToolResult

ListeningLibrary = Callable[[str, str | None, str | None], Sequence[Mapping[str, Any]]]  # (language, level, topic)
ReadingArticles = Callable[[str, str | None, str | None, int], Sequence[Mapping[str, Any]]]  # (..., limit)
BOTH = ("en", "zh-CN")
MAX_ITEMS = 8


def _nothing(*_args: Any) -> list:
    return []


class FindArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["listening", "reading", "any"] = "any"
    level: str | None = Field(default=None, min_length=1, max_length=32)
    topic: str | None = Field(default=None, min_length=1, max_length=64)
    query: str | None = Field(default=None, min_length=1, max_length=80, description="words of the title")
    limit: int = Field(default=5, ge=1, le=MAX_ITEMS)


def _clip(value: Any, size: int) -> str:
    return str(value or "").strip()[:size]


def _matches(query: str | None, *fields: Any) -> bool:
    if not query:
        return True
    wanted = query.casefold().strip()
    return any(wanted in str(field or "").casefold() for field in fields)


def _listening_item(item: Mapping[str, Any]) -> dict[str, Any] | None:
    lesson_id = item.get("lesson_id") or item.get("media_object_id")
    if not lesson_id:
        return None
    duration = item.get("duration_ms")
    return {
        "content_id": f"media:{lesson_id}",
        "kind": "listening",
        "opens": "listening.workspace",
        "title": _clip(item.get("title"), 120),
        "level": _clip(item.get("level"), 20) or None,
        "topic": _clip(item.get("topic"), 60) or None,
        "media_type": item.get("media_type") or None,
        "duration_s": round(duration / 1000) if isinstance(duration, (int, float)) and duration > 0 else None,
    }


def _reading_item(item: Mapping[str, Any]) -> dict[str, Any] | None:
    article_id = item.get("id")
    if not article_id:
        return None
    seconds = item.get("reading_time_seconds")
    return {
        "content_id": f"article:{article_id}",
        "kind": "reading",
        "opens": "reading.workspace",
        "title": _clip(item.get("title"), 120),
        "level": _clip(item.get("level") or item.get("effective_level"), 20) or None,
        "topic": _clip(item.get("topic"), 60) or None,
        "reading_time_s": int(seconds) if isinstance(seconds, (int, float)) else None,
    }


def _find(listening: ListeningLibrary, reading: ReadingArticles) -> Callable[[LearnerScope, FindArguments], ToolResult]:
    def handler(learner: LearnerScope, args: FindArguments) -> ToolResult:
        language = learner.language
        items: list[dict[str, Any]] = []
        if args.kind in ("listening", "any"):
            for raw in listening(language, args.level, args.topic) or ():
                found = _listening_item(raw)
                if found and _matches(args.query, found["title"], found["topic"]):
                    items.append(found)
        if args.kind in ("reading", "any"):
            for raw in reading(language, args.level, args.topic, MAX_ITEMS * 3) or ():
                found = _reading_item(raw)
                if found and _matches(args.query, found["title"], found["topic"]):
                    items.append(found)
        shown = items[: args.limit]
        return ToolResult(
            summary=f"{len(shown)} of {len(items)} items to open in this language" if items else
            "nothing found in this language with these filters",
            data={"found": len(items), "items": shown},
            count=len(shown),
        )  # fmt: skip

    return handler


def find_tools(*, listening_library: ListeningLibrary = _nothing,
               reading_articles: ReadingArticles = _nothing) -> tuple[AgentTool, ...]:  # fmt: skip
    return (
        AgentTool(
            name="find_content",
            description="Find listening lessons (audio, video) and reading articles in the learner's language to "
            "open, by kind, level, topic or words of the title. Each item has the content_id to open it with.",
            input_model=FindArguments,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.listening_api:listening_library",
            languages=BOTH,
            label_key="tool.find_content",
            handler=_find(listening_library, reading_articles),
        ),
    )
