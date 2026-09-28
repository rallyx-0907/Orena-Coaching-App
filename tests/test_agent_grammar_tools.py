"""Grammar read tools (Slice 2): through the app's own R5 composition, in EN and ZH."""

from __future__ import annotations

import pytest

from writing_coach.agent.grammar_tools import COMPLETION_CLAIM
from writing_coach.agent.runtime import AppReads, build_tool_registry
from writing_coach.agent.tools import LearnerScope, ToolArgumentsInvalid
from writing_coach.agent.turn import learner_context

EN = LearnerScope(user_key="grammar-learner", language="en")
ZH = LearnerScope(user_key="grammar-learner", language="zh")


@pytest.fixture(scope="module")
def app_module():
    import app

    return app


def tools(app_module):
    return build_tool_registry(
        writing_review=lambda essay_id: None,
        reads=AppReads(
            grammar_library=lambda: app_module.api_grammar_library(),
            grammar_lesson=lambda grammar_id: app_module._agent_grammar_lesson(grammar_id),
        ),
    )


@pytest.mark.parametrize(
    ("learner", "grammar_id", "level"),
    [(EN, "a1-complete-sentences-and-basic-word-order", "A1"), (ZH, "zh-hsk1-1-svo-c-b-n", "HSK1")],
)
def test_a_point_is_read_from_r5_in_the_session_language(app_module, learner, grammar_id, level):
    with learner_context(learner):
        app_module.init_db()
        result = tools(app_module).invoke("get_grammar_point", learner, {"grammar_id": grammar_id})
    assert result.data["found"] is True and result.data["level"] == level
    assert result.data["summary_vi"] and result.data["examples"] and len(result.data["examples"]) <= 3
    assert result.data["completion_claim"] == COMPLETION_CLAIM
    assert [e.ref for e in result.evidence] == [{"grammar_id": grammar_id}]
    assert result.evidence[0].source == "grammar.catalog"


def test_a_point_of_the_other_language_is_not_found(app_module):
    with learner_context(ZH):
        app_module.init_db()
        result = tools(app_module).invoke("get_grammar_point", ZH, {"grammar_id": "a1-complete-sentences-and-basic-word-order"})
    assert result.data == {"found": False} and result.count == 0


def test_search_finds_points_by_name_and_level(app_module):
    with learner_context(ZH):
        app_module.init_db()
        found = tools(app_module).invoke("search_grammar_points", ZH, {"query": "svo", "level": "HSK1"})
        nothing = tools(app_module).invoke("search_grammar_points", ZH, {"query": "zzzz-no-such"})
    assert found.count >= 1 and all(p["level"] == "HSK1" for p in found.data["points"])
    assert "zh-hsk1-1-svo-c-b-n" in {p["grammar_id"] for p in found.data["points"]}
    assert nothing.count == 0 and nothing.data["points"] == []
    with pytest.raises(ToolArgumentsInvalid):
        tools(app_module).invoke("search_grammar_points", ZH, {"query": "", "limit": 3})


def test_a_found_point_can_be_named_by_a_navigate():
    """The grammar_id a tool returns is what contract §7 lets an action name."""

    from writing_coach.agent.outputs import ReplyOutputs
    from writing_coach.agent.schemas import ClientInfo

    reads = AppReads(grammar_library=lambda: {"lessons": [{"id": "zh-hsk1-1-svo-c-b-n", "title": "SVO", "level": "HSK1"}]})
    result = build_tool_registry(writing_review=lambda i: None, reads=reads).invoke(
        "search_grammar_points", ZH, {"query": "svo"}
    )
    client = ClientInfo.model_validate(
        {"ui_version": "t", "supported_actions": ["navigate"], "supported_intents": ["grammar.point"]}
    )
    outputs = ReplyOutputs(client=client, interface="vi", support="vi", target="zh-CN", version=4)
    outputs.learn_from(result.data)
    payload = {"intent": "grammar.point", "grammar_id": "zh-hsk1-1-svo-c-b-n"}
    assert outputs.handle("propose_action", {"type": "navigate", "payload": payload}, known_evidence=frozenset()).startswith("accepted")


def test_the_app_hands_in_the_grammar_routes(app_module):
    source = __import__("pathlib").Path(app_module.__file__).read_text(encoding="utf-8")
    assert "grammar_library=lambda: api_grammar_library()" in source
    assert "grammar_lesson=lambda grammar_id: _agent_grammar_lesson(grammar_id)" in source
