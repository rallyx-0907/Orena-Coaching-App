"""Assemble the agent the app serves (Slice 1b): tools, registry, provider, sessions.

`app.py` calls `build_agent_runtime` once, only when the agent is enabled, and
hands in what belongs to the app: the Writing review read it already serves
and the usage store it already meters with. Everything else is the agent's own.
"""

from __future__ import annotations

from collections.abc import Callable

from writing_coach.agent.capability_registry import load_capability_registry
from writing_coach.agent.limits import DEFAULT_LIMITS, AgentLimits
from writing_coach.agent.platform_provider import PlatformAgentTurnProvider
from writing_coach.agent.provider import AgentTurnProvider
from writing_coach.agent.read_tools import WritingHistoryReader, WritingReviewReader, more_read_tools, read_tools
from writing_coach.agent.session import SessionCache
from writing_coach.agent.tools import ToolRegistry
from writing_coach.agent.turn import AgentRuntime

RecordUsage = Callable[..., None]  # ProductRepository.record_usage(*, user_key, feature, amount, request_id)


def _no_history() -> dict:
    return {"items": [], "revision_count": 0}


def build_tool_registry(
    *,
    writing_review: WritingReviewReader,
    writing_history: WritingHistoryReader = _no_history,
    limits: AgentLimits = DEFAULT_LIMITS,
) -> ToolRegistry:
    registry = ToolRegistry(limits=limits)
    for tool in (
        *read_tools(writing_review=writing_review),
        *more_read_tools(writing_review=writing_review, writing_history=writing_history),
    ):
        registry.register(tool)
    return registry


def build_agent_runtime(
    *,
    writing_review: WritingReviewReader,
    record_usage: RecordUsage | None,
    writing_history: WritingHistoryReader = _no_history,
    provider: AgentTurnProvider | None = None,
    limits: AgentLimits = DEFAULT_LIMITS,
) -> AgentRuntime:
    tools = build_tool_registry(writing_review=writing_review, writing_history=writing_history, limits=limits)

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
    )
