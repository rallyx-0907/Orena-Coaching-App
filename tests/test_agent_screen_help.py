"""F-13: "what is this screen for?" is answered from the screen's context, with no tool offered or run."""

from __future__ import annotations

import json

import pytest

from writing_coach.agent import surfaces
from writing_coach.agent.fake_provider import call_tools, reply
from writing_coach.agent.prompts import SCREEN_HELP
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.screen_help import is_screen_help
from tests.test_agent_turn import VI, hermetic, registry, run, runtime, turn_request  # noqa: F401 - fixture

SCREEN_QUESTIONS = {
    "vi": ["Màn này dùng để làm gì?", "Tôi làm gì ở đây?", "Trang này có chức năng gì?", "man nay dung de lam gi",
           "Orena ơi, màn hình này để làm gì vậy?", "Ở đây mình làm được gì?"],
    "en": ["What is this screen for?", "What can I do here?", "What does this page do?", "how does this page work"],
    "zh": ["这个页面是做什么的？", "我在这里能做什么？", "这个界面有什么用", "这个页面怎么用"],
}
NOT_SCREEN_QUESTIONS = [
    "Màn này dùng để làm gì, và mình nên học gì?", "Hôm nay mình nên học gì?", "Mình hay sai gì nhất?",
    "What should I learn today?", "What is this word?", "这个词是什么意思？", "Lưu từ này", "làm gì bây giờ",
    "Từ này nghĩa là gì?", "Bài này nói về gì?",
]
INTERFACE_LOCALE = {"vi": ("vi", "vi"), "en": ("en", "en"), "zh": ("zh-CN", "zh-CN")}
SURFACES = ["reading.workspace", "vocabulary.word", "writing.workspace", "listening.workspace", "orena.home"]


@pytest.mark.parametrize("message", [m for ms in SCREEN_QUESTIONS.values() for m in ms])
def test_a_question_about_the_screen_is_recognised(message):
    assert is_screen_help(message)


@pytest.mark.parametrize("message", NOT_SCREEN_QUESTIONS)
def test_a_question_that_asks_for_more_than_the_screen_is_not(message):
    assert not is_screen_help(message)


def _request(message, surface, interface):
    body = turn_request(message).model_dump(mode="json", exclude_none=True)
    ui, support = INTERFACE_LOCALE[interface]
    body["context"]["surface"] = surface
    body["context"]["locale"].update({"interface": ui, "support": support})
    body["context"].pop("selected_item", None)
    return TurnRequest.model_validate(body)


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("interface", ["vi", "en", "zh"])
def test_screen_help_is_answered_from_the_screen_with_no_tool_offered(surface, interface):
    seen = []
    rt, provider = runtime([reply("Đây là nơi …")], tools=registry(seen))
    events = run(rt, _request(SCREEN_QUESTIONS[interface][0], surface, interface))
    request = provider.requests[0]
    offered = {spec.name for spec in request.tools}
    assert offered <= {"suggest_next"}, "no read tool, action or note to explain a screen (S1)"
    assert len(provider.requests) == 1, "one provider round, no tool round-trip"
    assert not [e for e in events if e.name in {"tool_call", "tool_result", "evidence", "action"}]
    assert seen == [], "no learner data is read"
    system = [m.content for m in request.messages if m.role == "system"]
    assert SCREEN_HELP in system
    context = json.loads(next(c for c in system if c.startswith("context: "))[len("context: "):])
    ui = INTERFACE_LOCALE[interface][0]
    assert context["screen"]["purpose"] == surfaces.purpose(surface, ui), "the published purpose, as written"
    assert events[-1].name == "done"


def test_the_regression_question_reaches_no_tool_even_when_the_model_asks_for_one():
    """The model calls a read tool anyway: the server does not run what it did not offer."""

    seen = []
    rt, provider = runtime([call_tools(("c1", "get_test_items", {})), reply("Màn này để …")], tools=registry(seen))
    events = run(rt, _request("Màn này dùng để làm gì?", "reading.workspace", "vi"))
    assert seen == []
    assert not [e for e in events if e.name in {"tool_call", "tool_result", "evidence"}]
    assert all({spec.name for spec in r.tools} <= {"suggest_next"} for r in provider.requests)


def test_a_recommendation_question_still_gets_its_tools():
    rt, provider = runtime([reply("Ok.")])
    run(rt, _request("Hôm nay mình nên học gì?", "orena.home", "vi"))
    assert provider.requests[0].tools, "a question that needs learner data is offered the read tools"
    assert SCREEN_HELP not in [m.content for m in provider.requests[0].messages if m.role == "system"]
