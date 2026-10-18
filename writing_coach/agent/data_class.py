"""Provider data classes: which learner data each provider may receive (ORENA_MEMORY.md §8, G8 - partial, staged).

The gate governs four payloads (`GOVERNED_PAYLOADS`) and only while it is on - the learner pack is on and a record
exists (§8 a; from M2 also the memory switch), so switching the policy on never makes a working provider
"unavailable" for learners with no pack:

- `none`: cleared for none of them. It is not a privacy guarantee: a `none` provider still receives what is not
  governed yet (below);
- `learning_profile`: the learner pack (profile and learning evidence) and the chat context's learning evidence;
- `full_memory`: that, and device coach notes (§8 b) - and, from M2/M3, Orena Memory proper (explicit, inferred and
  continuity items, session summaries, the summariser's turns; a memory-bearing pack, `pack_class`).

- **The learner pack** reaches a chat turn or a voice setup only when the provider is cleared for `learning_profile`;
  otherwise the turn is what it was before M1 (no pack, the opening snapshot as before), and the record says so.
- **Coach notes** reach a provider only when it is cleared for `full_memory`. Below it the notes are not sent, and no
  note can be kept, changed or forgotten (the note tools are not offered and are refused): a learner who asks is told
  so plainly (owner, 2026-10-18).
- **The chat context**: its state carried from earlier in the session (`earlier_in_session`, `conversation_focus`, a
  reused selection; agent/context_gate.py) only to `learning_profile`, and sending it raises the conversation's
  class; the rest is the request's own content.
- **The conversation's history** (§8 c): a conversation that has sent a class of data is never continued on a
  provider cleared for less - its turns, rolling summary and answers may carry that data. The check runs before a
  route is pinned, so a refused route is never kept; the turn answers the unavailable path (`ProviderNotCleared`);
  voice does not open (`VoiceUnavailable`).

A provider with no recorded class is `none`. **Not governed by this gate yet** (`NOT_YET_GOVERNED`): the legacy
opening snapshot, the learner's own text and the results of tools the model calls in the turn. G8 is not complete
until each of those is covered and moved into `GOVERNED_PAYLOADS`.

The classes are configuration, read once at start, never guessed: `AGENT_PROVIDER_DATA_CLASSES` lists
`provider=class` or `provider:model=class` entries separated by commas (a model entry wins over its provider's). An
entry that does not parse refuses to start. Where the owner records the classes in Admin is a UI-lane question
(the provider catalogue); until then this configuration is the record.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum
from types import MappingProxyType
from typing import Any


class DataClass(IntEnum):
    """How far a provider is cleared. Only `GOVERNED_PAYLOADS` are checked against it."""

    NONE = 0
    LEARNING_PROFILE = 1
    FULL_MEMORY = 2

    @property
    def label(self) -> str:
        return self.name.lower()

    @classmethod
    def parse(cls, text: str) -> DataClass:
        try:
            return cls[text.strip().upper()]
        except KeyError:
            raise ValueError(f"unknown data class {text.strip()!r}: none, learning_profile or full_memory") from None


@dataclass(frozen=True)
class ProviderDataClasses:
    """The owner's record: `provider` or `provider:model` -> class. Empty means every provider is `none`."""

    classes: Mapping[str, DataClass] = field(default_factory=lambda: MappingProxyType({}))

    def of(self, provider: str | None, model: str | None = None) -> DataClass:
        if not provider:
            return DataClass.NONE  # a call whose provider is not known is cleared for nothing
        if model and f"{provider}:{model}" in self.classes:
            return self.classes[f"{provider}:{model}"]
        return self.classes.get(provider, DataClass.NONE)

    def cleared(self, provider: str | None, model: str | None, needed: DataClass) -> bool:
        return self.of(provider, model) >= needed

    def public(self) -> dict[str, str]:
        return {key: value.label for key, value in sorted(self.classes.items())}

    @classmethod
    def parse(cls, text: str | None) -> ProviderDataClasses:
        classes: dict[str, DataClass] = {}
        for entry in (text or "").split(","):
            if not entry.strip():
                continue
            key, sep, value = entry.partition("=")
            key = key.strip()
            if not sep or not key or key.startswith(":") or key.endswith(":"):
                raise ValueError(f"AGENT_PROVIDER_DATA_CLASSES entry {entry.strip()!r} is not provider[:model]=class")
            if key in classes:
                raise ValueError(f"AGENT_PROVIDER_DATA_CLASSES names {key!r} twice")
            classes[key] = DataClass.parse(value)
        return cls(MappingProxyType(classes))

    @classmethod
    def from_env(cls, environ: Mapping[str, Any]) -> ProviderDataClasses:
        return cls.parse(environ.get("AGENT_PROVIDER_DATA_CLASSES"))


PACK_CLASS = DataClass.LEARNING_PROFILE  # what the M1 learner pack carries (profile and evidence)
NOTES_CLASS = DataClass.FULL_MEMORY  # device coach notes (§8 b)
# The chat context's state carried from earlier in the session (agent/context_gate.py): `earlier_in_session` (what
# tools read for the learner), `conversation_focus` (earlier topics and referents, a pasted text) and an earlier
# selection reused. The rest of the context is the request's own content and the conversation's mechanics.
CONTEXT_EVIDENCE_CLASS = DataClass.LEARNING_PROFILE

# The staged boundary (A1, M2-prep 2b). A payload moves from the second tuple to the first only with the code that
# gates it.
GOVERNED_PAYLOADS = ("learner_pack", "coach_notes", "conversation_history", "chat_context")
NOT_YET_GOVERNED = ("opening_snapshot", "learner_text", "tool_results")


def pack_class(*, with_memory: bool) -> DataClass:
    """What a pack needs: `learning_profile` for profile and evidence (M1); `full_memory` once it carries Orena Memory
    (orena-pack/2, §5.1). The M2 wiring builds a memory-bearing pack only for a model cleared for it."""

    return DataClass.FULL_MEMORY if with_memory else PACK_CLASS


def gating_on(pack_builder: Any, classes: ProviderDataClasses | None, *, memory_on: bool = False) -> bool:
    """The gate applies only with a record and the learner pack on - or, from M2, Orena Memory on this server (§8 a):
    callers pass `memory_on` whenever the server has memory, whatever the pack flag, so a note or memory sent with the
    pack off still raises the conversation's class and blocks a lower provider."""

    return classes is not None and (bool(getattr(pack_builder, "enabled", False)) or memory_on)
