"""Hard limits for one agent turn, one session and one learner (spec §11, §20, §22, contract §9).

Values the spec states are used as stated (4 tool iterations, 8 KB per tool
result, 15-minute voice sessions); the rest are conservative defaults. They are
configuration passed in, not constants read at call sites, so a test or a
later operator setting can change them without editing the code that obeys
them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields
from typing import Any


@dataclass(frozen=True)
class AgentLimits:
    max_tool_iterations_per_turn: int = 4
    max_tool_result_bytes: int = 8 * 1024
    turn_timeout_seconds: float = 60.0
    max_input_tokens_per_turn: int = 48_000
    session_ttl_seconds: float = 30 * 60
    max_sessions: int = 10_000
    max_recent_tool_results: int = 8
    # The conversation the model is shown (architecture target §5): turns, characters in all, characters in one.
    max_recent_turns: int = 20
    max_history_chars: int = 36_000
    max_turn_chars: int = 20_000
    # The soft budget (agent/summary.py): past either, the oldest turns are folded into a rolling summary and the
    # last `keep_verbatim_turns` stay word for word. The hard bound above remains the limit if a summary fails.
    compact_after_turns: int = 14
    compact_after_chars: int = 16_000
    keep_verbatim_turns: int = 6
    max_summary_chars: int = 2_400
    voice_session_cap_seconds: float = 15 * 60
    # Requests one learner may make in a sliding window (spec §22), per process.
    rate_window_seconds: float = 60.0
    turns_per_window: int = 12
    capability_reads_per_window: int = 60
    rate_limited_learners: int = 10_000  # learners remembered, least recently seen forgotten first
    # The opening greeting (D-163) costs the learner no quota, so the model writes at most this many per account in the
    # window (per process); past it the greeting is built from the snapshot with no model, and is never refused. A
    # greeting's model round is capped at `opening_max_output_tokens` (240 characters and a few suggestions).
    model_openings_per_window: int = 1
    opening_window_seconds: float = 30 * 60
    opening_max_output_tokens: int = 200

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"{field.name} must be a positive number")


DEFAULT_LIMITS = AgentLimits()


# The limits an operator tunes in Platform Admin (writing_coach/policies.py, D-17P). Everything else on `AgentLimits` is
# a safety or context-design bound (the spec's tool iterations and result size, the history window) and stays in code.
OPERATOR_FIELDS: tuple[str, ...] = (
    "turns_per_window", "capability_reads_per_window", "rate_window_seconds", "max_input_tokens_per_turn",
    "model_openings_per_window", "opening_window_seconds", "opening_max_output_tokens",
)


class LiveAgentLimits:
    """`AgentLimits` whose operator-tunable fields are read from `overrides()` each time they are used.

    `overrides` returns `{field: value}` for the fields it knows; a field it does not name, or names with an unusable
    value, keeps the base value. The agent package reads no environment and no store itself: the application hands it
    this callable (app.py), so a change saved in Admin applies to the next turn with no restart."""

    def __init__(self, base: AgentLimits, overrides: Callable[[], Mapping[str, Any]]) -> None:
        self._base = base
        self._overrides = overrides

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in OPERATOR_FIELDS:
            try:
                value = self._overrides().get(name)
            except Exception:  # noqa: BLE001 - a limit read never fails a turn
                value = None
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                return value
        return getattr(self._base, name)
