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

import hashlib
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from writing_coach.agent.tools import AgentTool


@dataclass(frozen=True)
class ToolCallRequest:
    id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    # The provider's own data for this call, sent back verbatim with it next round (Gemini's
    # thought signature). Opaque: the turn never reads it, the learner never sees it.
    echo: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class TurnFinished:
    """The end of a round. A count the provider did not report is None, never 0."""

    input_tokens: int | None
    output_tokens: int | None
    finish_reason: Literal["stop", "tool_calls", "length"]  # anything else is refused at the adapter (fail closed)
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
class ModelRoute:
    """The provider and model a conversation is pinned to (ORENA_MEMORY.md §7.2, M0). Infrastructure only: never
    shown to the learner (contract §10)."""

    provider: str
    model: str

    def public(self) -> dict[str, str]:
        return {"provider": self.provider, "model": self.model}


@dataclass(frozen=True)
class ProviderTurnRequest:
    messages: tuple[ProviderMessage, ...]
    tools: tuple[ProviderToolSpec, ...] = ()
    max_output_tokens: int = 1024
    temperature: float | None = None
    # What is left of the turn's budget: a provider waits no longer than this
    # for a response or for its next piece.
    timeout_seconds: float | None = None
    # "none": the tools are listed (so the request keeps the same prefix) but the model may not call one this round.
    # None leaves it to the provider's default.
    tool_choice: Literal["none"] | None = None
    # The conversation's pinned model; None is the legacy active selection, read each round.
    route: ModelRoute | None = None


def tools_digest(tools: Sequence[ProviderToolSpec]) -> str | None:
    """A short fingerprint of the tool list as sent, in order: two requests with the same digest share that part of
    their prefix (telemetry for the cache benchmark). None for no tools."""

    if not tools:
        return None
    wired = [[t.name, t.description, t.parameters] for t in tools]
    return hashlib.sha256(json.dumps(wired, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def never_stop() -> bool:
    return False


class AgentTurnProvider(Protocol):
    """Streams one round. `should_stop` is polled between events (client abort)."""

    def stream(
        self, request: ProviderTurnRequest, *, should_stop: Callable[[], bool] = never_stop
    ) -> Iterator[ProviderEvent]: ...


# A round is an answer only when it ended normally; "length" (cut off) or any other end is a failure, never an
# answer (independent review 2026-10-04).
NORMAL_FINISH = frozenset({"stop", "tool_calls"})
