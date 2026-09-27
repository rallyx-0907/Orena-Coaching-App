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
from writing_coach.agent.read_tools import WritingReviewReader, read_tools
from writing_coach.agent.session import SessionCache
from writing_coach.agent.tools import ToolRegistry
from writing_coach.agent.turn import AgentRuntime

RecordUsage = Callable[..., None]  # ProductRepository.record_usage(*, user_key, feature, amount, request_id)


def build_tool_registry(*, writing_review: WritingReviewReader, limits: AgentLimits = DEFAULT_LIMITS) -> ToolRegistry:
    registry = ToolRegistry(limits=limits)
    for tool in read_tools(writing_review=writing_review):
        registry.register(tool)
    return registry


def build_agent_runtime(
    *,
    writing_review: WritingReviewReader,
    record_usage: RecordUsage | None,
    provider: AgentTurnProvider | None = None,
    limits: AgentLimits = DEFAULT_LIMITS,
) -> AgentRuntime:
    tools = build_tool_registry(writing_review=writing_review, limits=limits)

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
