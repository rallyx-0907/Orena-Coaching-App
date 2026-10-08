"""Hard limits for one agent turn, one session and one learner (spec §11, §20, §22, contract §9).

Values the spec states are used as stated (4 tool iterations, 8 KB per tool
result, 15-minute voice sessions); the rest are conservative defaults. They are
configuration passed in, not constants read at call sites, so a test or a
later operator setting can change them without editing the code that obeys
them.
"""

from __future__ import annotations

from dataclasses import dataclass, fields


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

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"{field.name} must be a positive number")


DEFAULT_LIMITS = AgentLimits()
