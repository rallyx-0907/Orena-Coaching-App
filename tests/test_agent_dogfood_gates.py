"""Dogfood correctness gates (2026-10-04): target-language switch (3.3) and account isolation (3.4)."""

from __future__ import annotations

from writing_coach.agent.fake_provider import call_tools, reply
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.tools import LearnerScope
from tests.test_agent_turn import hermetic, registry, runtime, turn_request  # noqa: F401 - fixture

EN = LearnerScope(user_key="learner-1", language="en")
ZH = LearnerScope(user_key="learner-1", language="zh")
OTHER = LearnerScope(user_key="learner-2", language="en")


def _request(target, *, session_id=None, selected=None):
    body = turn_request("Từ này dùng thế nào?").model_dump(mode="json", exclude_none=True)
    body["context"]["locale"].update({"target": target, "content": target})
    body["context"]["surface"] = "vocabulary.word"
    if selected is None:
        body["context"].pop("selected_item", None)
    else:
        body["context"]["selected_item"] = selected
    if session_id:
        body["session_id"] = session_id
    return TurnRequest.model_validate(body)


def _provider_text(request) -> str:
    return "\n".join(str(m.content) for m in request.messages)


def _first_turn(rt, learner):
    events = list(rt.run(_request("en", selected={"type": "word", "text": "ephemeral", "lang": "en"}), learner))
    return next(e for e in events if e.name == "session").session_id


def test_after_a_switch_to_chinese_nothing_of_the_english_context_reaches_the_provider():
    seen = []
    rt, provider = runtime(
        [call_tools(("c1", "get_test_items", {})), reply("Ephemeral nghĩa là ngắn ngủi."), reply("Mình chưa thấy từ nào.")],
        tools=registry(seen),
    )
    session_id = _first_turn(rt, EN)
    english = _provider_text(provider.requests[-1])
    assert "ephemeral" in english and "two flagged syllables" in english, "the English turn had its context"

    list(rt.run(_request("zh-CN", session_id=session_id), ZH))
    chinese = _provider_text(provider.requests[-1])
    assert "ephemeral" not in chinese, "no stale English selection"
    assert "two flagged syllables" not in chinese, "no English tool result in earlier_in_session"


def test_the_same_target_keeps_its_selection_for_a_follow_up():
    rt, provider = runtime([reply("Ok."), reply("Ok.")])
    session_id = _first_turn(rt, EN)
    list(rt.run(_request("en", session_id=session_id), EN))
    assert "ephemeral" in _provider_text(provider.requests[-1])


def test_another_account_never_sees_the_first_ones_session():
    seen = []
    rt, provider = runtime(
        [call_tools(("c1", "get_test_items", {})), reply("Ok."), reply("Ok.")], tools=registry(seen)
    )
    session_id = _first_turn(rt, EN)
    events = list(rt.run(_request("en", session_id=session_id), OTHER))
    other_text = _provider_text(provider.requests[-1])
    assert "ephemeral" not in other_text and "two flagged syllables" not in other_text
    assert next(e for e in events if e.name == "session").session_id != session_id, "a foreign id opens a new session"
    assert {learner.user_key for learner, _, _ in seen} == {"learner-1"}, "the tool read only the first learner"
