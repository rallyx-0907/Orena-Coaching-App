"""A deterministic stand-in for the agent's model provider (spec D14).

Every automated agent test runs on this; none calls a real provider. It plays
a script of rounds in order - each round is what the model "says" after the
messages it was given: text, tool calls, or a failure - and records every
request so a test can assert what the agent sent. Same script, same output,
every run. It imports nothing that can reach a network.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any

from writing_coach.agent.errors import AgentError
from writing_coach.agent.provider import (
    ProviderEvent,
    ProviderTurnRequest,
    TextDelta,
    ToolCallRequest,
    TurnFinished,
    never_stop,
)

FakeStep = ProviderEvent | AgentError
FakeRound = tuple[FakeStep, ...]
RoundSource = FakeRound | Callable[[ProviderTurnRequest], FakeRound]


class FakeScriptExhausted(AssertionError):
    """The agent asked for more rounds than the test scripted."""


def _tokens(text: str) -> int:
    # Deterministic and roughly proportional; not a tokenizer.
    return max(1, (len(text) + 3) // 4)


def _input_tokens(request: ProviderTurnRequest) -> int:
    return sum(_tokens(message.content) for message in request.messages)


def reply(text: str, *, chunk: int = 12) -> FakeRound:
    """A round that streams `text` in fixed-size deltas, then finishes."""

    if not text:
        raise ValueError("a reply has text")
    deltas = tuple(TextDelta(text[start : start + chunk]) for start in range(0, len(text), chunk))
    return (*deltas, TurnFinished(input_tokens=0, output_tokens=_tokens(text), finish_reason="stop"))


def call_tools(*calls: tuple[str, str, Mapping[str, Any]]) -> FakeRound:
    """A round that asks for tools: `(call_id, tool_name, arguments)` each."""

    if not calls:
        raise ValueError("a tool round calls at least one tool")
    requests = tuple(ToolCallRequest(id=call_id, name=name, arguments=dict(args)) for call_id, name, args in calls)
    return (*requests, TurnFinished(input_tokens=0, output_tokens=8 * len(calls), finish_reason="tool_calls"))


def fail(error: AgentError) -> FakeRound:
    """A round that fails before saying anything."""

    return (error,)


class FakeAgentTurnProvider:
    provider_id = "fake"

    def __init__(self, rounds: Sequence[RoundSource]) -> None:
        self._rounds = list(rounds)
        self.requests: list[ProviderTurnRequest] = []

    @property
    def remaining(self) -> int:
        return len(self._rounds)

    def stream(
        self, request: ProviderTurnRequest, *, should_stop: Callable[[], bool] = never_stop
    ) -> Iterator[ProviderEvent]:
        self.requests.append(request)
        if not self._rounds:
            raise FakeScriptExhausted(f"round {len(self.requests)} was not scripted")
        source = self._rounds.pop(0)
        steps = source(request) if callable(source) else source
        return self._play(steps, _input_tokens(request), should_stop)

    @staticmethod
    def _play(steps: FakeRound, input_tokens: int, should_stop: Callable[[], bool]) -> Iterator[ProviderEvent]:
        for step in steps:
            if should_stop():
                return
            if isinstance(step, AgentError):
                raise step
            if isinstance(step, TurnFinished):
                step = TurnFinished(
                    input_tokens=input_tokens,
                    output_tokens=step.output_tokens,
                    finish_reason=step.finish_reason,
                    cached_input_tokens=step.cached_input_tokens,
                )
            yield step
