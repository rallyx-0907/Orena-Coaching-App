"""Assemble the agent the app serves (Slice 1b): tools, registry, provider, sessions.

`app.py` calls `build_agent_runtime` once, only when the agent is enabled, and
hands in what belongs to the app: the Writing review read it already serves
and the usage store it already meters with. Everything else is the agent's own.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from writing_coach.agent.capability_registry import load_capability_registry
from writing_coach.agent.coaching import (
    CrossSkillCueReader,
    LearnerSummaryReader,
    ListeningRecent,
    _no_cue,
    _unavailable_summary,
    coaching_tools,
)
from writing_coach.agent.find_tools import ListeningLibrary, ReadingArticles, _nothing, find_tools
from writing_coach.agent.grammar_tools import (
    GrammarLessonReader,
    GrammarLibraryReader,
    _no_lesson,
    _no_library,
    grammar_tools,
)
from writing_coach.agent.limits import DEFAULT_LIMITS, AgentLimits
from writing_coach.agent.platform_provider import PlatformAgentTurnProvider
from writing_coach.agent.provider import AgentTurnProvider
from writing_coach.agent.read_tools import WritingHistoryReader, WritingReviewReader, more_read_tools, read_tools
from writing_coach.agent.session import SessionCache
from writing_coach.agent.skill_tools import (
    ListeningLesson,
    ListeningProgress,
    ReadingArticle,
    ReadingChapter,
    ReadingEvidence,
    SpeakingAttempts,
    SpeakingProgress,
    _empty,
    _no_progress,
    _none,
    skill_tools,
)
from writing_coach.agent.tools import ToolRegistry
from writing_coach.agent.turn import AgentRuntime

RecordUsage = Callable[..., None]  # ProductRepository.record_usage(*, user_key, feature, amount, request_id)


def _no_history() -> dict:
    return {"items": [], "revision_count": 0}


@dataclass(frozen=True)
class AppReads:
    """The app's own read compositions the tools go through - its routes' code, never re-implemented.

    Each defaults to "nothing there", so a test or a runtime that does not hand one in gets
    empty answers from that tool, never a guess.
    """

    grammar_library: GrammarLibraryReader = _no_library
    grammar_lesson: GrammarLessonReader = _no_lesson
    speaking_attempts: SpeakingAttempts = _empty
    speaking_progress: SpeakingProgress = _no_progress
    listening_lesson: ListeningLesson = _none
    listening_progress: ListeningProgress = _empty
    reading_article: ReadingArticle = _none
    reading_chapter: ReadingChapter = _none
    reading_evidence: ReadingEvidence = _empty
    learner_summary: LearnerSummaryReader = _unavailable_summary
    cross_skill_cue: CrossSkillCueReader = _no_cue
    listening_recent: ListeningRecent = _empty
    listening_library: ListeningLibrary = _nothing  # find_content (R29)
    reading_articles: ReadingArticles = _nothing


def build_tool_registry(
    *,
    writing_review: WritingReviewReader,
    writing_history: WritingHistoryReader = _no_history,
    reads: AppReads = AppReads(),
    limits: AgentLimits = DEFAULT_LIMITS,
) -> ToolRegistry:
    registry = ToolRegistry(limits=limits)
    for tool in (
        *read_tools(writing_review=writing_review),
        *more_read_tools(writing_review=writing_review, writing_history=writing_history),
        *grammar_tools(library=reads.grammar_library, lesson=reads.grammar_lesson),
        *skill_tools(
            speaking_attempts=reads.speaking_attempts,
            speaking_progress=reads.speaking_progress,
            listening_lesson=reads.listening_lesson,
            listening_progress=reads.listening_progress,
            reading_article=reads.reading_article,
            reading_chapter=reads.reading_chapter,
            reading_evidence=reads.reading_evidence,
        ),
        *coaching_tools(
            learner_summary=reads.learner_summary,
            cross_skill_cue=reads.cross_skill_cue,
            writing_history=writing_history,
            speaking_attempts=reads.speaking_attempts,
            listening_recent=reads.listening_recent,
            reading_evidence=reads.reading_evidence,
        ),
        *find_tools(listening_library=reads.listening_library, reading_articles=reads.reading_articles),
    ):
        registry.register(tool)
    return registry


def build_agent_runtime(
    *,
    writing_review: WritingReviewReader,
    record_usage: RecordUsage | None,
    writing_history: WritingHistoryReader = _no_history,
    reads: AppReads = AppReads(),
    provider: AgentTurnProvider | None = None,
    limits: AgentLimits = DEFAULT_LIMITS,
    record_turn: Callable[[str, dict], None] | None = None,
    record_summary: Callable[[str, dict], None] | None = None,
    price_summary: Callable[[int, int], dict] | None = None,
    spend_guard: Callable[[], float | None] | None = None,
) -> AgentRuntime:
    tools = build_tool_registry(
        writing_review=writing_review, writing_history=writing_history, reads=reads, limits=limits
    )

    def meter(user_key: str, feature: str, amount: int, request_id: str) -> None:
        if record_usage is not None:
            record_usage(user_key=user_key, feature=feature, amount=amount, request_id=request_id)

    return AgentRuntime(
        provider=provider or PlatformAgentTurnProvider(),
        tools=tools,
        capabilities=load_capability_registry(registered_tools=tools.names()),
        sessions=SessionCache(limits=limits),
        limits=limits,
        meter=meter,
        record_turn=record_turn,
        record_summary=record_summary,
        price_summary=price_summary,
        spend_guard=spend_guard,
    )
