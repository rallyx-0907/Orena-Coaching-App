"""What Orena can help with, per surface and language (spec §5-§6, contract §8).

The registry is data: `writing_coach/agent/capabilities/*.json`, one file per
domain. It names no routes. Every surface and action is an id from the
contract's own tables, every evidence source is from contract §5.3, every
language is a target language, and every title is interface copy in each
interface language. A capability serving one target language says why
(`linguistic_reason`).

`status` is `pending` until the tools it names are registered and it has been
verified; an `active` capability whose tools are not all in the tool registry
does not load. Tool names a pending capability lists must be known to the tool
plan (`tool_plan.py`), so a typo cannot hide until the day the tool is built.

`public()` is the contract §8 shape. `contexts`, `tools` and the reason stay
internal.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from writing_coach.agent.contract import ACTIONS, CONTRACT_VERSION, EVIDENCE_SOURCES, SURFACES
from writing_coach.agent.locale import interface_languages, target_languages
from writing_coach.agent.tool_plan import PLANNED_TOOLS
from writing_coach.agent.tools import PARITY_LANGUAGES

REGISTRY_DIR = Path(__file__).with_name("capabilities")
STATUSES = frozenset({"active", "pending"})
CONTEXT_FIELDS = frozenset({"lesson_id", "content_id", "attempt_id", "essay_id", "selected_item", "client_evidence"})
MAX_TITLE_CHARS = 60
_ID = re.compile(r"^[a-z][a-z_]*(\.[a-z][a-z_]*)+$")
_FIELDS = frozenset(
    {
        "id",
        "title",
        "surfaces",
        "status",
        "contexts",
        "actions",
        "languages",
        "evidence_source",
        "tools",
        "linguistic_reason",
    }
)
_REQUIRED = _FIELDS - {"linguistic_reason", "evidence_source"}


class CapabilityRegistryInvalid(ValueError):
    pass


@dataclass(frozen=True)
class CapabilityEntry:
    id: str
    title: Mapping[str, str]
    surfaces: tuple[str, ...]
    status: str
    contexts: tuple[str, ...]
    actions: tuple[str, ...]
    languages: tuple[str, ...]
    evidence_source: str | None
    tools: tuple[str, ...]
    linguistic_reason: str | None = None

    def serves(self, target: str) -> bool:
        return target in self.languages

    def public(self, interface: str) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title[interface],
            "surfaces": list(self.surfaces),
            "actions": list(self.actions),
            "languages": list(self.languages),
            "evidence_source": self.evidence_source,
            "status": self.status,
        }


class CapabilityRegistry:
    def __init__(self, entries: Iterable[CapabilityEntry]) -> None:
        self._entries = tuple(entries)
        self._by_id = MappingProxyType({entry.id: entry for entry in self._entries})

    def __len__(self) -> int:
        return len(self._entries)

    def entries(self) -> tuple[CapabilityEntry, ...]:
        return self._entries

    def get(self, capability_id: str) -> CapabilityEntry | None:
        return self._by_id.get(capability_id)

    def for_surface(self, surface: str | None, target: str) -> tuple[CapabilityEntry, ...]:
        if surface is None:
            return ()
        return tuple(entry for entry in self._entries if surface in entry.surfaces and entry.serves(target))

    def public(self, *, interface: str, target: str) -> dict[str, Any]:
        """Contract §8: the capabilities serving the caller's target language."""

        return {
            "contract_version": CONTRACT_VERSION,
            "capabilities": [entry.public(interface) for entry in self._entries if entry.serves(target)],
        }


def _strings(raw: Any, field: str, where: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(raw, list) or not all(isinstance(item, str) and item for item in raw):
        raise CapabilityRegistryInvalid(f"{where}: {field} must be a list of strings")
    if not raw and not allow_empty:
        raise CapabilityRegistryInvalid(f"{where}: {field} is empty")
    if len(set(raw)) != len(raw):
        raise CapabilityRegistryInvalid(f"{where}: {field} repeats an entry")
    return tuple(raw)


def parse_entry(raw: Any, *, registered_tools: frozenset[str], where: str) -> CapabilityEntry:
    if not isinstance(raw, dict):
        raise CapabilityRegistryInvalid(f"{where}: an entry is an object")
    unknown = set(raw) - _FIELDS
    missing = _REQUIRED - set(raw)
    if unknown or missing:
        raise CapabilityRegistryInvalid(f"{where}: unknown {sorted(unknown)}, missing {sorted(missing)}")
    entry_id = raw["id"]
    if not isinstance(entry_id, str) or not _ID.fullmatch(entry_id):
        raise CapabilityRegistryInvalid(f"{where}: invalid id {entry_id!r}")
    where = f"{where} {entry_id}"

    title = raw["title"]
    if not isinstance(title, dict) or set(title) != interface_languages():
        raise CapabilityRegistryInvalid(f"{where}: title needs exactly {sorted(interface_languages())}")
    if not all(isinstance(text, str) and 0 < len(text) <= MAX_TITLE_CHARS for text in title.values()):
        raise CapabilityRegistryInvalid(f"{where}: a title is 1-{MAX_TITLE_CHARS} characters")

    surfaces = _strings(raw["surfaces"], "surfaces", where)
    if not set(surfaces) <= set(SURFACES):
        raise CapabilityRegistryInvalid(f"{where}: unknown surfaces {sorted(set(surfaces) - set(SURFACES))}")
    status = raw["status"]
    if status not in STATUSES:
        raise CapabilityRegistryInvalid(f"{where}: unknown status {status!r}")
    contexts = _strings(raw["contexts"], "contexts", where, allow_empty=True)
    if not set(contexts) <= CONTEXT_FIELDS:
        raise CapabilityRegistryInvalid(f"{where}: unknown contexts {sorted(set(contexts) - CONTEXT_FIELDS)}")
    actions = _strings(raw["actions"], "actions", where, allow_empty=True)
    if not set(actions) <= set(ACTIONS):
        raise CapabilityRegistryInvalid(f"{where}: unknown actions {sorted(set(actions) - set(ACTIONS))}")

    languages = _strings(raw["languages"], "languages", where)
    if not set(languages) <= target_languages():
        raise CapabilityRegistryInvalid(f"{where}: languages must be target languages")
    reason = raw.get("linguistic_reason")
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        raise CapabilityRegistryInvalid(f"{where}: linguistic_reason is a sentence")
    if not PARITY_LANGUAGES <= set(languages) and reason is None:
        raise CapabilityRegistryInvalid(f"{where}: serves {sorted(languages)} only and gives no linguistic reason")

    evidence_source = raw.get("evidence_source")
    if evidence_source is not None and evidence_source not in EVIDENCE_SOURCES:
        raise CapabilityRegistryInvalid(f"{where}: unknown evidence_source {evidence_source!r}")

    tools = _strings(raw["tools"], "tools", where, allow_empty=True)
    unplanned = set(tools) - set(PLANNED_TOOLS)
    if unplanned:
        raise CapabilityRegistryInvalid(f"{where}: tools not in the tool plan {sorted(unplanned)}")
    if status == "active" and not set(tools) <= registered_tools:
        raise CapabilityRegistryInvalid(f"{where}: active but tools are not registered {sorted(set(tools) - registered_tools)}")

    return CapabilityEntry(
        id=entry_id,
        title=MappingProxyType(dict(title)),
        surfaces=surfaces,
        status=status,
        contexts=contexts,
        actions=actions,
        languages=languages,
        evidence_source=evidence_source,
        tools=tools,
        linguistic_reason=reason,
    )


def load_capability_registry(
    directory: Path = REGISTRY_DIR, *, registered_tools: Iterable[str] = ()
) -> CapabilityRegistry:
    registered = frozenset(registered_tools)
    files = sorted(directory.glob("*.json"))
    if not files:
        raise CapabilityRegistryInvalid(f"no capability files in {directory}")
    entries: list[CapabilityEntry] = []
    seen: set[str] = set()
    for path in files:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CapabilityRegistryInvalid(f"{path.name}: not JSON ({exc.msg})") from exc
        if not isinstance(document, dict) or set(document) != {"capabilities"}:
            raise CapabilityRegistryInvalid(f"{path.name}: a file is {{\"capabilities\": [...]}}")
        items = document["capabilities"]
        if not isinstance(items, list) or not items:
            raise CapabilityRegistryInvalid(f"{path.name}: capabilities is a non-empty list")
        for raw in items:
            entry = parse_entry(raw, registered_tools=registered, where=path.name)
            if entry.id in seen:
                raise CapabilityRegistryInvalid(f"{path.name}: duplicate capability {entry.id}")
            seen.add(entry.id)
            entries.append(entry)
    return CapabilityRegistry(entries)
