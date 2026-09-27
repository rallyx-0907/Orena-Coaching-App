"""Tool permissions and the registry that admits tools (spec §7-§9)."""

from __future__ import annotations

from types import MappingProxyType

import pytest
from pydantic import BaseModel, ConfigDict

from writing_coach.agent import learner_copy
from writing_coach.agent.limits import AgentLimits
from writing_coach.agent.tools import (
    REGISTRABLE_IN_V1,
    AgentTool,
    LearnerScope,
    ToolArgumentsInvalid,
    ToolError,
    ToolEvidence,
    ToolLanguageUnsupported,
    ToolPermission,
    ToolPermissionDenied,
    ToolRegistry,
    ToolResult,
    ToolResultTooLarge,
    UnknownTool,
)
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX

LABEL = "tool.test_label"


@pytest.fixture(autouse=True)
def test_label(monkeypatch):
    catalog = dict(learner_copy.CATALOG)
    catalog[LABEL] = learner_copy._entry(
        learner_copy.CopyLayer.INTERFACE, {"en": "Looking", "vi": "Đang xem", "zh-CN": "正在查看"}
    )
    catalog["tool.support_label"] = learner_copy._entry(
        learner_copy.CopyLayer.SUPPORT, {"en": "Look", "vi": "Xem", "zh-CN": "查看"}
    )
    monkeypatch.setattr(learner_copy, "CATALOG", MappingProxyType(catalog))


class WordArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    word: str


class LooseArgs(BaseModel):
    word: str


class NamingArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str


def tool(name="get_saved_word_state", **overrides):
    seen = overrides.pop("seen", None)

    def handler(learner, args):
        if seen is not None:
            seen.append((learner, args))
        return ToolResult(summary="1 word", data={"word": args.word, "saved": True})

    fields = dict(
        name=name,
        description="Whether a word is saved.",
        input_model=WordArgs,
        permission=ToolPermission.READ_ONLY,
        backed_by="writing_coach.becoming_library:saved_vocabulary_state",
        languages=("en", "zh-CN"),
        label_key=LABEL,
        handler=handler,
    )
    fields.update(overrides)
    return AgentTool(**fields)


EN = LearnerScope(user_key="u1", language="en")
ZH = LearnerScope(user_key="u1", language="zh")


def test_permission_vocabulary_is_complete_and_v1_reads_only():
    assert {p.name for p in ToolPermission} == {"READ_ONLY", "NAVIGATION", "PLAYBACK", "USER_MUTATION", "HIGH_IMPACT"}
    assert REGISTRABLE_IN_V1 == {ToolPermission.READ_ONLY}


def test_a_read_only_tool_registers():
    registry = ToolRegistry()
    registry.register(tool())
    assert registry.names() == {"get_saved_word_state"}
    assert all(t.permission is ToolPermission.READ_ONLY for t in registry.tools())


@pytest.mark.parametrize("permission", [p for p in ToolPermission if p is not ToolPermission.READ_ONLY])
def test_every_other_permission_is_refused_in_v1(permission):
    with pytest.raises(ToolPermissionDenied):
        ToolRegistry().register(tool(permission=permission))


def test_registrable_permissions_must_be_known():
    with pytest.raises(ValueError):
        ToolRegistry(registrable=frozenset({"root"}))


@pytest.mark.parametrize(
    "backed_by",
    [
        "",
        "saved_vocabulary_state",
        "writing_coach.becoming_library",
        "writing_coach.becoming_library:no_such_function",
        "writing_coach.no_such_module:thing",
    ],
)
def test_backed_by_must_name_an_existing_callable(backed_by):
    with pytest.raises(ToolError):
        ToolRegistry().register(tool(backed_by=backed_by))


def test_class_methods_resolve_as_backing():
    ToolRegistry().register(
        tool(backed_by="writing_coach.persistence.specialized_repository:PostgresSpecializedLearningRepository.speaking_progress")
    )


def test_names_are_unique():
    registry = ToolRegistry()
    registry.register(tool())
    with pytest.raises(ToolError):
        registry.register(tool())


def test_en_and_zh_both_unless_a_linguistic_reason():
    with pytest.raises(ToolError, match="linguistic reason"):
        ToolRegistry().register(tool(languages=("en",)))
    ToolRegistry().register(tool(languages=("zh-CN",), linguistic_reason="Tone is a Chinese property."))
    with pytest.raises(ToolError):
        ToolRegistry().register(tool(languages=("en", "zh-CN", "ja")))
    with pytest.raises(ToolError):
        ToolRegistry().register(tool(languages=("en", "zh")))


def test_the_label_is_interface_layer_copy():
    with pytest.raises(ToolError):
        ToolRegistry().register(tool(label_key="tool.missing"))
    with pytest.raises(ToolError, match="interface"):
        ToolRegistry().register(tool(label_key="tool.support_label"))


def test_arguments_are_closed_and_never_name_a_learner():
    with pytest.raises(ToolError, match="forbid"):
        ToolRegistry().register(tool(input_model=LooseArgs))
    with pytest.raises(ToolError, match="name a learner"):
        ToolRegistry().register(tool(input_model=NamingArgs))


def test_invoke_runs_for_the_authenticated_learner_only():
    seen = []
    registry = ToolRegistry()
    registry.register(tool(seen=seen))
    result = registry.invoke("get_saved_word_state", ZH, {"word": "我"})
    assert result.data == {"word": "我", "saved": True}
    assert seen[0][0] is ZH
    for key in ("user_id", "USER_KEY", "email", "learner_id"):
        with pytest.raises(ToolArgumentsInvalid, match="name a learner"):
            registry.invoke("get_saved_word_state", EN, {"word": "x", key: "someone-else"})


def test_invoke_validates_arguments():
    registry = ToolRegistry()
    registry.register(tool())
    for args in ({}, {"word": 3}, {"word": "x", "extra": 1}):
        with pytest.raises(ToolArgumentsInvalid):
            registry.invoke("get_saved_word_state", EN, args)
    with pytest.raises(UnknownTool):
        registry.invoke("get_everything", EN, {})


def test_invoke_respects_the_tools_languages():
    registry = ToolRegistry()
    registry.register(tool(languages=("zh-CN",), linguistic_reason="Tone is a Chinese property."))
    with pytest.raises(ToolLanguageUnsupported):
        registry.invoke("get_saved_word_state", EN, {"word": "tone"})
    registry.invoke("get_saved_word_state", ZH, {"word": "是"})


def test_results_are_bounded():
    def big(learner, args):
        return ToolResult(summary="big", data={"blob": "x" * 9000})

    registry = ToolRegistry()
    registry.register(tool(handler=big))
    with pytest.raises(ToolResultTooLarge):
        registry.invoke("get_saved_word_state", EN, {"word": "x"})
    roomy = ToolRegistry(limits=AgentLimits(max_tool_result_bytes=20_000))
    roomy.register(tool(handler=big))
    assert roomy.invoke("get_saved_word_state", EN, {"word": "x"}).summary == "big"


def test_the_input_schema_comes_from_the_model():
    schema = tool().input_schema
    assert schema["properties"]["word"]["type"] == "string"
    assert schema.get("additionalProperties") is False


def test_learner_scope_comes_from_the_request_context():
    user_token = USER_KEY_CTX.set("learner-7")
    language_token = LANGUAGE_CODE_CTX.set("zh")
    try:
        scope = LearnerScope.from_request_context()
    finally:
        USER_KEY_CTX.reset(user_token)
        LANGUAGE_CODE_CTX.reset(language_token)
    assert scope == LearnerScope(user_key="learner-7", language="zh")
    assert scope.contract_language == "zh-CN"


def test_evidence_sources_are_the_contracts():
    ToolEvidence(id="e1", source="vocabulary.review", ref={"word": "我"}, excerpt={"stage": 2})
    with pytest.raises(ValueError):
        ToolEvidence(id="e1", source="vocabulary.guess", ref={}, excerpt={})


def test_limits_are_positive():
    AgentLimits()
    for field in ("max_tool_iterations_per_turn", "max_tool_result_bytes", "turn_timeout_seconds"):
        with pytest.raises(ValueError):
            AgentLimits(**{field: 0})
    assert AgentLimits().max_tool_iterations_per_turn == 4
    assert AgentLimits().max_tool_result_bytes == 8192
    assert AgentLimits().voice_session_cap_seconds == 900
