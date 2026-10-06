"""UX review LEX-006 / LEX-022 (live retest on :8021, 2026-10-05): a turn about what is in view answers about it,
in the support language, with no study routing nobody asked for.

- A starter the learner tapped is written in the interface language; the model is given it in the support
  language, so it answers in that language.
- With a selection or a feedback item in view, no review button or "review due" suggestion is offered unless the
  learner asks about review.
- "Why was this feedback given?" on an essay reads that essay first.
"""

from __future__ import annotations

import pytest

from tests.test_agent_coaching import _runtime
from writing_coach.agent import learner_copy
from writing_coach.agent.fake_provider import reply
from writing_coach.agent.outputs import PROPOSE_ACTION, SUGGEST_NEXT, ClientInfo, ReplyOutputs
from writing_coach.agent.prompts import INSTRUCTION
from writing_coach.agent.provider import TextDelta, ToolCallRequest, TurnFinished
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.tools import LearnerScope

LEARNER = LearnerScope(user_key="learner-1", language="zh", interface="en")


def _turn(message, *, interface="en", support="vi", surface="reading.workspace", selected=None, essay_id=None):
    context = {"surface": surface, "locale": {"interface": interface, "support": support, "target": "zh-CN"}}
    if selected:
        context["selected_item"] = selected
    if essay_id:
        context["essay_id"] = essay_id
    return TurnRequest.model_validate({
        "contract_version": 5, "trigger": "message", "message": message, "context": context,
        "client": {"ui_version": "t", "supported_actions": ["start_review", "navigate"], "supported_intents": []},
    })  # fmt: skip


def _learner_message(provider):
    return [m.content for m in provider.requests[0].messages if m.role == "user"][-1]


WORD = {"type": "word", "text": "花生", "lang": "zh-CN"}


@pytest.mark.parametrize(("interface", "support", "tapped", "given"), [
    ("en", "vi", "What does this word mean here?", "Từ này nghĩa là gì ở đây?"),
    ("vi", "en", "Câu này nghĩa là gì?", "What does this sentence mean?"),
    ("en", "zh-CN", "Explain this part in the sentence", "解释这部分在句中的意思"),
])  # fmt: skip
def test_a_tapped_starter_reaches_the_model_in_the_support_language(interface, support, tapped, given):
    rt, provider = _runtime([reply("Ok.")])
    list(rt.run(_turn(tapped, interface=interface, support=support, selected=WORD), LEARNER))
    assert _learner_message(provider) == given


def test_a_message_the_learner_typed_reaches_the_model_as_typed():
    rt, provider = _runtime([reply("Ok.")])
    list(rt.run(_turn("What does this word mean here, in English please?", selected=WORD), LEARNER))
    assert _learner_message(provider) == "What does this word mean here, in English please?"


def test_every_server_starter_has_a_support_language_form():
    for key in learner_copy.CATALOG:
        if key.startswith("prompt."):
            for interface in learner_copy.PACK_LANGUAGES:
                label = learner_copy.CATALOG[key].texts[interface]
                assert learner_copy.prompt_in_support(label, interface=interface, support="vi") == \
                    learner_copy.CATALOG[key].texts["vi"]  # fmt: skip


def _outputs(**kwargs):
    client = ClientInfo.model_validate({"ui_version": "t", "supported_actions": ["start_review", "navigate"]})
    return ReplyOutputs(client=client, interface="en", support="vi", target="zh-CN", **kwargs)


def test_with_a_selection_in_view_no_review_is_offered_unasked():
    out = _outputs(focused=True, learner_words="What does this word mean here?")
    answer = out.handle(PROPOSE_ACTION, {"type": "start_review", "payload": {"scope": "due"}}, known_evidence=frozenset())
    assert answer.startswith("refused: the learner asks about what is in view") and out.actions == []
    suggested = out.handle(SUGGEST_NEXT, {"intent": "prompt.review_due"}, known_evidence=frozenset())
    assert suggested.startswith("refused: the learner asks about what is in view") and out.suggestions == []


@pytest.mark.parametrize("message", ["Mình muốn ôn từ đến hạn", "Can I review my due words?", "我想复习"])
def test_review_is_offered_when_the_learner_asks_for_it(message):
    out = _outputs(focused=True, learner_words=message)
    answer = out.handle(PROPOSE_ACTION, {"type": "start_review", "payload": {"scope": "due"}}, known_evidence=frozenset())
    assert answer.startswith("accepted")


def test_without_anything_in_view_review_may_be_offered():
    out = _outputs(focused=False, learner_words="Hôm nay mình nên học gì?")
    answer = out.handle(PROPOSE_ACTION, {"type": "start_review", "payload": {"scope": "due"}}, known_evidence=frozenset())
    assert answer.startswith("accepted")


FEEDBACK = {"type": "feedback_item", "text": "Dùng cấu trúc 不在……，而在…… để nhấn mạnh."}


def test_why_this_feedback_reads_the_essay_before_answering():
    rounds = [
        (TextDelta("Bạn có 12 từ đến hạn ôn."), TurnFinished(0, 3, "stop")),  # answered without reading: set aside
        (ToolCallRequest("c1", "get_writing_feedback_items", {"essay_id": "e-7"}), TurnFinished(0, 3, "tool_calls")),
        (TextDelta("Nhận xét này đến từ câu thứ hai của bài."), TurnFinished(0, 3, "stop")),
    ]  # fmt: skip
    rt, provider = _runtime(rounds)
    events = list(rt.run(_turn("Vì sao nhận xét này được đưa ra?", interface="vi", surface="writing.review",
                                selected=FEEDBACK, essay_id="e-7"), LEARNER))  # fmt: skip
    nudge = [m.content for m in provider.requests[1].messages if m.role == "user"][-1]
    assert "e-7" in nudge and "get_writing_feedback_items" in nudge
    text = next(e.text for e in events if e.name == "segment_end")
    assert "đến hạn" not in text


def test_the_prompt_asks_for_real_headings_and_no_unasked_routing():
    assert "### " in INSTRUCTION and "feedback_item" in INSTRUCTION
    assert "no review" in INSTRUCTION.casefold() or "never offer review" in INSTRUCTION.casefold()
