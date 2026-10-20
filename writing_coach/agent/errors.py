"""The ways a turn can fail, as the learner is told about them (contract §4 `error`).

There is no automatic switch to another provider (ARCHITECTURE_INVARIANTS: no
provider-to-provider fallback; human ruling 2026-09-27). A failed provider ends
the turn with an error whose `fallback` tells the client what it may do next:
`retry` the same turn, or continue `text_only` when a voice session failed. The
message is layered copy in the support language; it never names a provider,
a key, a region or carries raw provider output.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from writing_coach.agent.contract import ERROR_FALLBACKS


@dataclass(frozen=True)
class ErrorKind:
    error_class: str
    copy_key: str
    fallback: str

    def __post_init__(self) -> None:
        if self.fallback not in ERROR_FALLBACKS:
            raise ValueError(f"unknown fallback {self.fallback!r}")


ERROR_KINDS: Mapping[str, ErrorKind] = MappingProxyType(
    {
        kind.error_class: kind
        for kind in (
            ErrorKind("provider_unavailable", "error.provider_unavailable", "retry"),
            ErrorKind("voice_unavailable", "error.voice_unavailable", "text_only"),
            ErrorKind("internal_error", "error.internal", "retry"),
        )
    }
)


class AgentError(Exception):
    """Raised inside a turn; the stream turns it into one `error` event."""

    error_class = "internal_error"
    # The learner copy for this failure when it is not its kind's own (`ERROR_KINDS[...].copy_key`): the same
    # class and fallback (contract §4.1), only a truer sentence.
    copy_key: str | None = None


class ProviderUnavailable(AgentError):
    """The configured provider did not answer usably (down, timed out, malformed)."""

    error_class = "provider_unavailable"


class ProviderOutOfService(ProviderUnavailable):
    """The provider refused for a reason a short wait does not cure (#438): its spending cap, quota or credit is
    spent, or its credential is rejected or missing. Still `provider_unavailable` with `retry` (contract §4.1), but
    the learner is not told that Orena is merely busy."""

    copy_key = "error.provider_out_of_service"


class ProviderNotCleared(ProviderUnavailable):
    """The conversation's provider is not cleared for the learner data the conversation already carries (G8,
    ORENA_MEMORY.md §8 c): it is not sent there, and the learner is told what any unavailable provider tells them.
    Not a provider failure: the route is not marked failed."""


class VoiceUnavailable(AgentError):
    """A speech-to-speech session failed; the conversation continues in text."""

    error_class = "voice_unavailable"
