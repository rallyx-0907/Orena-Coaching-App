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

from writing_coach.agent.errors import ProviderOutOfService, ProviderUnavailable
from writing_coach.agent.provider import (
    ModelRoute,
    ProviderEvent,
    ProviderMessage,
    ProviderToolSpec,
    ProviderTurnRequest,
    TextDelta,
    ToolCallRequest,
    TurnFinished,
    never_stop,
)
from writing_coach.ai.base import (
    AICapabilityError,
    AIProviderError,
    AIProviderNotConfigured,
    ChatFinished,
    ChatTextDelta,
    ChatToolCall,
)

_log = logging.getLogger(__name__)
_FINISH = {"stop": "stop", "tool_calls": "tool_calls", "length": "length"}
# A provider's own words for "the money or the quota is spent", which a short wait does not cure (#438). A per-minute
# rate limit ("rate limit", "too many requests") is not among them: that one passes.
_SPENT = ("spending cap", "spend cap", "billing", "insufficient_quota", "insufficient credit", "credit balance",
          "payment required", "out of credits")


def _unavailable(exc: Exception, message: str) -> ProviderUnavailable:
    """The agent error for a provider failure: out of service when waiting will not help, else unavailable."""

    status = getattr(exc, "status_code", None)
    text = str(exc).casefold()
    if (isinstance(exc, AIProviderNotConfigured) or status in (401, 402, 403)
            or (status == 429 and any(word in text for word in _SPENT))):
        return ProviderOutOfService(message)
    return ProviderUnavailable(message)


def _finish(reason: object) -> str:
    """The round's end as the agent knows it. An unknown or missing reason (a safety stop, a stream cut short) is
    never read as a normal stop: the round fails closed (independent review 2026-10-04)."""

    known = _FINISH.get(str(reason or ""))
    if known is None:
        # For the operator (and the live runner): "missing" means the stream ended with no reason at all.
        _log.warning("agent provider round ended abnormally: %s", reason or "missing")
        raise ProviderUnavailable(f"the provider round ended with an unknown reason {reason!r}")
    return known


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
                **({"extra_content": dict(call.echo)} if call.echo else {}),
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
                **({"route": (request.route.provider, request.route.model)} if request.route is not None else {}),
                **({"tool_choice": request.tool_choice} if request.tool_choice is not None and request.tools else {}),
            )
        except (AIProviderError, AICapabilityError) as exc:
            # For the operator only: the learner is told `provider_unavailable`, never this.
            _log.warning("agent provider round did not start: %s", exc)
            raise _unavailable(exc, "the provider did not start") from exc
        return self._convert(events)

    @staticmethod
    def _convert(events: Iterator[Any]) -> Iterator[ProviderEvent]:
        try:
            for event in events:
                if isinstance(event, ChatTextDelta):
                    yield TextDelta(event.text)
                elif isinstance(event, ChatToolCall):
                    yield ToolCallRequest(
                        id=event.id, name=event.name, arguments=parse_arguments(event.arguments), echo=event.extra
                    )
                elif isinstance(event, ChatFinished):
                    yield TurnFinished(
                        input_tokens=event.prompt_tokens,
                        output_tokens=event.completion_tokens,
                        finish_reason=_finish(event.finish_reason),
                        cached_input_tokens=event.cached_tokens or 0,
                    )
        except (AIProviderError, AICapabilityError) as exc:
            _log.warning("agent provider round stopped: %s", exc)
            raise _unavailable(exc, "the provider stopped") from exc


class PlatformModelRouter:
    """Pins a conversation to a model (ORENA_MEMORY.md §7.2, M0): the active selection when the conversation opens,
    kept for every round after, so an Admin change applies to new conversations only."""

    def __init__(self, current: Callable[[], tuple[str, str] | None] | None = None,
                 usable: Callable[[tuple[str, str]], bool] | None = None) -> None:
        if current is None or usable is None:
            from writing_coach.ai.platform import agent_current_route, agent_route_usable

            current = current or agent_current_route
            usable = usable or agent_route_usable
        self._current = current
        self._usable = usable

    def current(self) -> ModelRoute | None:
        route = self._current()
        return ModelRoute(provider=route[0], model=route[1]) if route else None

    def usable(self, route: ModelRoute) -> bool:
        try:
            return bool(self._usable((route.provider, route.model)))
        except Exception:  # noqa: BLE001 - an unreadable configuration is not a usable route
            _log.warning("agent route check failed", exc_info=True)
            return False
