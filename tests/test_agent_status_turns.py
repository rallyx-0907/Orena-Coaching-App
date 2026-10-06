"""LEX-006 (retest at b33283e, tutor accuracy): asked "Mở từ này trong My Library." about 我, the reply answered the
status and then explained 我 with an invented contrast ("not the speaker pronoun here, part of a quotation"). A
status or navigation question about a word in view is answered with the status only; no explanation of the word
is added, and none may invent a contrast about it."""

from __future__ import annotations

import pytest

from tests.test_agent_coaching import _runtime
from writing_coach.agent.fake_provider import reply
from writing_coach.agent.prompts import INSTRUCTION
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.tools import LearnerScope
from writing_coach.agent.turn import STATUS_ONLY

LEARNER = LearnerScope(user_key="learner-1", language="zh", interface="vi")


def _turn(message, selected=None):
    context = {"surface": "reading.workspace", "locale": {"interface": "vi", "support": "vi", "target": "zh-CN"}}
    if selected is not None:
        context["selected_item"] = selected
    return TurnRequest.model_validate({
        "contract_version": 5, "trigger": "message", "message": message, "context": context,
        "client": {"ui_version": "t", "supported_actions": ["save_word", "navigate"], "supported_intents": []},
    })  # fmt: skip


WORD = {"type": "word", "text": "我", "lang": "zh-CN", "sentence": "我说：“好。”"}


def _systems(provider):
    return [m.content for m in provider.requests[0].messages if m.role == "system"]


@pytest.mark.parametrize("message", ["Mở từ này trong My Library.", "Từ này mình lưu chưa?", "Is this word saved?",
                                     "Open this word", "打开这个词"])  # fmt: skip
def test_a_status_or_navigation_question_on_a_word_is_answered_with_the_status_only(message):
    rt, provider = _runtime([reply("Từ này hiện chưa có trong thư viện của bạn.")])
    list(rt.run(_turn(message, WORD), LEARNER))
    systems = _systems(provider)
    assert STATUS_ONLY in systems
    # said next to the learner's words, after the selection line
    assert systems.index(STATUS_ONLY) > next(i for i, s in enumerate(systems) if s.startswith("The learner has selected"))


@pytest.mark.parametrize(("message", "selected"), [
    ("Từ này nghĩa là gì ở đây?", WORD),  # a meaning question: explained as before
    ("Mở thư viện của mình", None),  # nothing in view
])  # fmt: skip
def test_other_turns_are_not_status_only(message, selected):
    rt, provider = _runtime([reply("Ok.")])
    list(rt.run(_turn(message, selected), LEARNER))
    assert STATUS_ONLY not in _systems(provider)


def test_the_prompt_forbids_an_invented_contrast():
    flat = " ".join(INSTRUCTION.split())
    assert "never invent a contrast" in flat and "我 in 我说" in flat
