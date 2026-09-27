"""The port the agent calls for one model round (`AIOperation.AGENT_TURN`).

A round sends messages and the tool schemas, and streams back text deltas,
tool-call requests and one `TurnFinished` with usage. The real adapter extends
the OpenAI-compatible provider in `writing_coach.ai` with streaming and native
tool calls (human ruling 2026-09-27: the existing chat/completions path, no new
dependency) and routes through that package's configuration and cooldowns; it
is Slice 1b. Tests use `fake_provider.FakeAgentTurnProvider`.

A provider that cannot answer raises `errors.ProviderUnavailable`; the turn ends
with an error event. Nothing here picks another provider (no automatic
provider-to-provider fallback, ARCHITECTURE_INVARIANTS).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from writing_coach.agent.tools import AgentTool


@dataclass(frozen=True)
class ToolCallRequest:
    id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class TurnFinished:
    """The end of a round. A count the provider did not report is None, never 0."""

    input_tokens: int | None
    output_tokens: int | None
    finish_reason: Literal["stop", "tool_calls", "length"]
    cached_input_tokens: int = 0


ProviderEvent = TextDelta | ToolCallRequest | TurnFinished


@dataclass(frozen=True)
class ProviderMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: tuple[ToolCallRequest, ...] = ()
    tool_call_id: str | None = None

    def __post_init__(self) -> None:
        if self.tool_calls and self.role != "assistant":
            raise ValueError("only an assistant message carries tool calls")
        if (self.role == "tool") != (self.tool_call_id is not None):
            raise ValueError("a tool message, and only a tool message, answers a tool call id")


@dataclass(frozen=True)
class ProviderToolSpec:
    name: str
    description: str
    parameters: Mapping[str, Any]

    @classmethod
    def from_tool(cls, tool: AgentTool) -> ProviderToolSpec:
        return cls(name=tool.name, description=tool.description, parameters=tool.input_schema)


@dataclass(frozen=True)
class ProviderTurnRequest:
    messages: tuple[ProviderMessage, ...]
    tools: tuple[ProviderToolSpec, ...] = ()
    max_output_tokens: int = 1024
    temperature: float | None = None
    # What is left of the turn's budget: a provider waits no longer than this
    # for a response or for its next piece.
    timeout_seconds: float | None = None


def never_stop() -> bool:
    return False


class AgentTurnProvider(Protocol):
    """Streams one round. `should_stop` is polled between events (client abort)."""

    def stream(
        self, request: ProviderTurnRequest, *, should_stop: Callable[[], bool] = never_stop
    ) -> Iterator[ProviderEvent]: ...
