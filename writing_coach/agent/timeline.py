"""One turn's timing and shape, for the latency and cost baseline (dogfood phase, 2026-10-04).

A turn notes when each step happened, relative to the moment its request arrived:
context built, each provider round's start and first event, each tool's start and
end, the final answer ready, and the first learner-visible segment the server
sent. With it go the facts that sort turns into kinds - opening, screen help, the
tools read, the actions and suggestions offered, the rounds and the tokens - and
nothing a learner wrote: no message, no answer, no selection text, no address.

It is recorded once per turn through the runtime's `record_turn` sink, which the
app writes as an `agent.turn` row beside the per-round `ai.operation` rows. The
per-round rows carry the provider's latency and the priced cost; this one carries
where the rest of the turn's time went.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

TIMELINE_VERSION = "agent-turn-timeline/1"


@dataclass
class TurnTimeline:
    clock: Callable[[], float]
    started: float = field(init=False)
    marks: list[tuple[str, int]] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)
    tools: list[str] = field(default_factory=list)
    rounds: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.started = self.clock()

    def now_ms(self) -> int:
        return int(round((self.clock() - self.started) * 1000))

    def mark(self, name: str) -> None:
        self.marks.append((name, self.now_ms()))

    def first(self, name: str) -> int | None:
        return next((at for mark, at in self.marks if mark == name), None)

    def mark_once(self, name: str) -> None:
        if self.first(name) is None:
            self.mark(name)

    def round_started(self) -> None:
        self.rounds.append({"start_ms": self.now_ms(), "first_event_ms": None, "end_ms": None,
                            "input_tokens": None, "output_tokens": None, "cached_input_tokens": 0, "tool_calls": 0})

    def round_event(self) -> None:
        if self.rounds and self.rounds[-1]["first_event_ms"] is None:
            self.rounds[-1]["first_event_ms"] = self.now_ms()

    def round_finished(self, *, input_tokens: int | None, output_tokens: int | None, cached: int, tool_calls: int) -> None:
        if self.rounds:
            self.rounds[-1].update(end_ms=self.now_ms(), input_tokens=input_tokens, output_tokens=output_tokens,
                                   cached_input_tokens=cached, tool_calls=tool_calls)

    def record(self, *, trace_id: str, outcome: str) -> dict[str, Any]:
        return {
            "version": TIMELINE_VERSION,
            "trace_id": trace_id,
            "outcome": outcome,
            "total_ms": self.now_ms(),
            "first_visible_ms": self.first("first_visible"),
            "context_built_ms": self.first("context_built"),
            "final_ready_ms": self.first("final_ready"),
            "marks": [{"name": name, "at_ms": at} for name, at in self.marks],
            "rounds": self.rounds,
            "tools": list(self.tools),
            **self.facts,
        }
