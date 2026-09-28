"""Agent tools and the registry that admits them (spec §7-§9).

A tool is a named, schema-bound read of an existing service. Its declaration
says what it may do (`permission`), what already does the work (`backed_by`,
"module:attribute", checked to exist when the tool registers), which target
languages it serves (EN and zh-CN both, unless a linguistic reason says why
not - REVIEW_POLICY scores a one-language shared feature P1) and which
interface copy labels it while it runs (`label_key`: a short system status,
D-080; human ruling 2026-09-27).

The registry is the gateway. In V1 it admits only `READ_ONLY` tools, and it
runs every tool for a `LearnerScope` built from the authenticated request -
never from an argument a model produced. An argument that names a learner is
refused before the tool sees it.
"""

from __future__ import annotations

import importlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ValidationError

from writing_coach.agent import learner_copy
from writing_coach.agent.contract import EVIDENCE_SOURCES
from writing_coach.agent.limits import DEFAULT_LIMITS, AgentLimits
from writing_coach.agent.locale import target_languages, to_contract
from writing_coach.core.request_context import current_language_code, current_user_key


class ToolPermission(StrEnum):
    READ_ONLY = "read_only"
    NAVIGATION = "navigation"
    PLAYBACK = "playback"
    USER_MUTATION = "user_mutation"
    HIGH_IMPACT = "high_impact"


# V1: the agent backend only reads (spec D6). Navigation, playback and every
# mutation are client-executed actions (contract §7), not backend tools.
REGISTRABLE_IN_V1 = frozenset({ToolPermission.READ_ONLY})

PARITY_LANGUAGES = frozenset({"en", "zh-CN"})
FORBIDDEN_ARGUMENTS = frozenset(
    {
        "user",
        "user_id",
        "user_key",
        "user_sub",
        "uid",
        "owner",
        "owner_id",
        "account",
        "account_id",
        "learner",
        "learner_id",
        "email",
    }
)
_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
_BACKED_BY = re.compile(r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*:[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


class ToolError(RuntimeError):
    """A tool could not be registered or run."""


class ToolPermissionDenied(ToolError):
    pass


class UnknownTool(ToolError):
    pass


class ToolArgumentsInvalid(ToolError):
    pass


class ToolLanguageUnsupported(ToolError):
    pass


class ToolResultTooLarge(ToolError):
    pass


@dataclass(frozen=True)
class LearnerScope:
    """Who a tool runs for. Built from the authenticated request only."""

    user_key: str
    language: str  # the backend's internal target code ("en", "zh")
    interface: str = "en"  # the learner's interface language: the language of labels a tool hands the model

    @classmethod
    def from_request_context(cls) -> LearnerScope:
        return cls(user_key=current_user_key(), language=current_language_code())

    @property
    def contract_language(self) -> str:
        return to_contract(self.language)


@dataclass(frozen=True)
class ToolEvidence:
    """One learner-evidence item a tool read; becomes an `evidence` event."""

    id: str
    source: str
    ref: Mapping[str, Any]
    excerpt: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.source not in EVIDENCE_SOURCES:
            raise ValueError(f"unknown evidence source {self.source!r}")


@dataclass(frozen=True)
class ToolResult:
    """What a tool read. `summary` and `data` go to the model; the learner sees
    `count` through interface copy (`result.<tool>`), never model-facing text."""

    summary: str
    data: Mapping[str, Any]
    evidence: tuple[ToolEvidence, ...] = ()
    count: int = 0

    def size_bytes(self) -> int:
        body = {
            "summary": self.summary,
            "data": self.data,
            "evidence": [
                {"id": e.id, "source": e.source, "ref": dict(e.ref), "excerpt": dict(e.excerpt)}
                for e in self.evidence
            ],
        }
        return len(json.dumps(body, ensure_ascii=False, default=str).encode("utf-8"))


ToolHandler = Callable[[LearnerScope, BaseModel], ToolResult]


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    input_model: type[BaseModel]
    permission: ToolPermission
    backed_by: str
    languages: tuple[str, ...]
    label_key: str
    handler: ToolHandler = field(repr=False)
    linguistic_reason: str | None = None

    @property
    def input_schema(self) -> dict[str, Any]:
        return self.input_model.model_json_schema()

    def execute(self, learner: LearnerScope, args: Mapping[str, Any]) -> ToolResult:
        try:
            parsed = self.input_model.model_validate(dict(args))
        except ValidationError as exc:
            raise ToolArgumentsInvalid(f"{self.name}: {exc.error_count()} invalid argument(s)") from exc
        return self.handler(learner, parsed)


def resolve_backing(backed_by: str) -> object:
    """Import `module:attribute` and return the attribute; raise if absent."""

    module_name, _, attribute_path = backed_by.partition(":")
    target: object = importlib.import_module(module_name)
    for part in attribute_path.split("."):
        target = getattr(target, part)
    return target


class ToolRegistry:
    def __init__(
        self,
        *,
        limits: AgentLimits = DEFAULT_LIMITS,
        registrable: frozenset[ToolPermission] = REGISTRABLE_IN_V1,
    ) -> None:
        unknown = registrable - frozenset(ToolPermission)
        if unknown:
            raise ValueError(f"unknown permissions {unknown}")
        self._limits = limits
        self._registrable = registrable
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> AgentTool:
        if tool.permission not in self._registrable:
            raise ToolPermissionDenied(f"{tool.name}: {tool.permission} tools are not registrable")
        if not _TOOL_NAME.fullmatch(tool.name):
            raise ToolError(f"invalid tool name {tool.name!r}")
        if tool.name in self._tools:
            raise ToolError(f"tool {tool.name!r} is already registered")
        if not tool.description.strip():
            raise ToolError(f"{tool.name}: a tool describes itself")
        self._check_backing(tool)
        self._check_languages(tool)
        self._check_label(tool)
        self._check_arguments(tool)
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> AgentTool:
        tool = self._tools.get(name)
        if tool is None:
            raise UnknownTool(f"no tool named {name!r}")
        return tool

    def names(self) -> frozenset[str]:
        return frozenset(self._tools)

    def tools(self) -> tuple[AgentTool, ...]:
        return tuple(self._tools.values())

    def invoke(self, name: str, learner: LearnerScope, args: Mapping[str, Any]) -> ToolResult:
        tool = self.get(name)
        if tool.permission not in self._registrable:
            raise ToolPermissionDenied(f"{name}: {tool.permission} tools do not run")
        named = FORBIDDEN_ARGUMENTS & {str(key).casefold() for key in args}
        if named:
            raise ToolArgumentsInvalid(f"{name}: arguments may not name a learner ({sorted(named)})")
        if learner.contract_language not in tool.languages:
            raise ToolLanguageUnsupported(f"{name} does not serve {learner.contract_language}")
        result = tool.execute(learner, args)
        if result.size_bytes() > self._limits.max_tool_result_bytes:
            raise ToolResultTooLarge(f"{name} returned more than {self._limits.max_tool_result_bytes} bytes")
        return result

    # --- registration checks ------------------------------------------------

    @staticmethod
    def _check_backing(tool: AgentTool) -> None:
        if not _BACKED_BY.fullmatch(tool.backed_by or ""):
            raise ToolError(f"{tool.name}: backed_by must be 'module:attribute', got {tool.backed_by!r}")
        try:
            resolve_backing(tool.backed_by)
        except (ImportError, AttributeError) as exc:
            raise ToolError(f"{tool.name}: backed_by {tool.backed_by!r} does not exist") from exc

    @staticmethod
    def _check_languages(tool: AgentTool) -> None:
        languages = frozenset(tool.languages)
        if not languages or not languages <= target_languages():
            raise ToolError(f"{tool.name}: languages must be target languages, got {sorted(languages)}")
        if not PARITY_LANGUAGES <= languages and not (tool.linguistic_reason or "").strip():
            raise ToolError(f"{tool.name}: serves {sorted(languages)} only and gives no linguistic reason")

    @staticmethod
    def _check_label(tool: AgentTool) -> None:
        entry = learner_copy.CATALOG.get(tool.label_key)
        if entry is None or entry.layer is not learner_copy.CopyLayer.INTERFACE:
            raise ToolError(f"{tool.name}: label_key {tool.label_key!r} must be interface-layer copy")

    @staticmethod
    def _check_arguments(tool: AgentTool) -> None:
        if tool.input_model.model_config.get("extra") != "forbid":
            raise ToolError(f"{tool.name}: the input model must forbid unknown arguments")
        named = FORBIDDEN_ARGUMENTS & {name.casefold() for name in tool.input_model.model_fields}
        if named:
            raise ToolError(f"{tool.name}: arguments may not name a learner ({sorted(named)})")
