"""Learner-pack clearance: which providers may receive the M1 learner pack (ORENA_MEMORY.md §8, G8 - partial).

This is a staged, partial G8. It governs one payload, the M1 learner pack, and nothing else:

- `none`: **not cleared for the learner pack**. It is not a privacy guarantee: a `none` provider still receives
  everything an agent turn sent before M1 (below);
- `learning_profile`: cleared for the learner pack (the learner's profile and learning evidence);
- `full_memory`: defined for Orena Memory proper (notes, inferred and continuity items, session summaries, M2/M3);
  it gates nothing yet.

The learner pack is put into a chat turn or a voice setup only when the conversation's pinned provider is cleared for
`learning_profile`; otherwise the turn is exactly what it was before M1 (no pack, the opening snapshot as before), and
the turn record says the pack was withheld. A provider with no recorded class is `none`.

**Not governed by this gate yet** (`NOT_YET_GOVERNED`): the legacy opening snapshot, the current chat context and
coach notes, the learner's own text in the conversation, and tool results. They reach the pinned provider whatever its
class. Rev 3's full G8 - every learner-derived payload class gated - stays open for M2/M3 and the provider-routing work,
and G8 is not complete until each of those is covered and moved into `GOVERNED_PAYLOADS`.

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
    """How far a provider is cleared. Only the learner pack is checked against it (`GOVERNED_PAYLOADS`)."""

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


PACK_CLASS = DataClass.LEARNING_PROFILE  # what the M1 learner pack carries

# The staged boundary (A1). A payload moves from the second tuple to the first only with the code that gates it.
GOVERNED_PAYLOADS = ("learner_pack",)
NOT_YET_GOVERNED = ("opening_snapshot", "chat_context", "coach_notes", "learner_text", "tool_results")
