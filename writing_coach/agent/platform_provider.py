"""The agent's model provider over `writing_coach.ai` (Slice 1b).

Converts a `ProviderTurnRequest` into the OpenAI-compatible wire shape -
messages with assistant tool calls and tool answers, the tool list as
functions - and streams it through `writing_coach.ai.platform.stream_agent_turn`,
which chooses the provider (the legacy active selection), refuses a local
model and records telemetry. Every provider failure becomes
`ProviderUnavailable`; its text never reaches the learner, whose error
message is copy.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from typing import Any

from writing_coach.agent.errors import ProviderUnavailable
from writing_coach.agent.provider import (
    ProviderEvent,
    ProviderMessage,
    ProviderToolSpec,
    ProviderTurnRequest,
    TextDelta,
    ToolCallRequest,
    TurnFinished,
    never_stop,
)
from writing_coach.ai.base import AICapabilityError, AIProviderError, ChatFinished, ChatTextDelta, ChatToolCall

_log = logging.getLogger(__name__)
_FINISH = {"stop": "stop", "tool_calls": "tool_calls", "length": "length"}


def wire_message(message: ProviderMessage) -> dict[str, Any]:
    if message.role == "tool":
        return {"role": "tool", "tool_call_id": message.tool_call_id, "content": message.content}
    wired: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        wired["content"] = message.content or None
        wired["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(dict(call.arguments), ensure_ascii=False)},
            }
            for call in message.tool_calls
        ]
    return wired


def wire_tool(spec: ProviderToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {"name": spec.name, "description": spec.description, "parameters": dict(spec.parameters)},
    }


def parse_arguments(text: str) -> dict[str, Any]:
    """A tool call's arguments; anything but a JSON object reads as none."""

    if not text.strip():
        return {}
    try:
        parsed = json.loads(text)
    except ValueError:
        _log.info("agent tool call arrived with malformed arguments")
        return {}
    return parsed if isinstance(parsed, dict) else {}


class PlatformAgentTurnProvider:
    def __init__(self, stream_turn: Callable[..., Iterator[Any]] | None = None) -> None:
        if stream_turn is None:
            from writing_coach.ai.platform import stream_agent_turn

            stream_turn = stream_agent_turn
        self._stream_turn = stream_turn

    def stream(
        self, request: ProviderTurnRequest, *, should_stop: Callable[[], bool] = never_stop
    ) -> Iterator[ProviderEvent]:
        try:
            events = self._stream_turn(
                messages=[wire_message(message) for message in request.messages],
                tools=[wire_tool(spec) for spec in request.tools],
                max_output_tokens=request.max_output_tokens,
                temperature=request.temperature,
                should_stop=should_stop,
                timeout_seconds=request.timeout_seconds,
            )
        except (AIProviderError, AICapabilityError) as exc:
            raise ProviderUnavailable("the provider did not start") from exc
        return self._convert(events)

    @staticmethod
    def _convert(events: Iterator[Any]) -> Iterator[ProviderEvent]:
        try:
            for event in events:
                if isinstance(event, ChatTextDelta):
                    yield TextDelta(event.text)
                elif isinstance(event, ChatToolCall):
                    yield ToolCallRequest(id=event.id, name=event.name, arguments=parse_arguments(event.arguments))
                elif isinstance(event, ChatFinished):
                    yield TurnFinished(
                        input_tokens=event.prompt_tokens,
                        output_tokens=event.completion_tokens,
                        finish_reason=_FINISH.get(event.finish_reason, "stop"),
                        cached_input_tokens=event.cached_tokens or 0,
                    )
        except (AIProviderError, AICapabilityError) as exc:
            raise ProviderUnavailable("the provider stopped") from exc
