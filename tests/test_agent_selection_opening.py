"""LEX-008 (UX review 2026-10-05): Orena opened on a selection greets about that selection, not with a generic
review reminder and "What is this screen for?". Contract §3.2: one segment, at least one suggestion, read-only."""

from __future__ import annotations

import pytest

from tests.test_agent_coaching import ZH, _runtime
from writing_coach.agent.fake_provider import reply
from writing_coach.agent.schemas import TurnRequest


def _open(selected, *, interface="vi", support="vi", surface="reading.workspace", address=None):
    context = {"surface": surface, "activity_type": "reading",
               "locale": {"interface": interface, "support": support, "target": "zh-CN", "content": "zh-CN"},
               }  # fmt: skip
    if selected:
        context["selected_item"] = selected
    if address:
        context["address"] = address
    return TurnRequest.model_validate({
        "contract_version": 5, "trigger": "open", "context": context,
        "client": {"ui_version": "t", "supported_actions": ["save_word"], "supported_intents": []},
    })  # fmt: skip


def _shown(events):
    text = next(e.text for e in events if e.name == "segment_end")
    return text, [(e.label, e.intent) for e in events if e.name == "suggestion"]


SENTENCE = {"type": "sentence", "id": "s-12", "text": "这里很热闹。", "lang": "zh-CN"}
WORD = {"type": "word", "text": "花生", "lang": "zh-CN"}


def test_an_opening_on_a_sentence_asks_about_that_sentence_with_no_model_call():
    rt, provider = _runtime([reply("Chào bạn! Hôm nay bạn có 5 từ đến hạn ôn.")])
    events = list(rt.run(_open(SENTENCE), ZH))
    text, suggestions = _shown(events)
    assert text == "Bạn muốn biết gì về câu này?"
    assert suggestions == [("Câu này nghĩa là gì?", "prompt.sentence_meaning"),
                           ("Giải thích ngữ pháp câu này", "prompt.sentence_grammar")]  # fmt: skip
    assert provider.requests == []  # no generic greeting written, no tokens spent
    assert not [e for e in events if e.name in ("action", "memory_update", "tool_call")]
    done = events[-1]
    assert done.name == "done" and done.usage.input_tokens == 0


def test_an_opening_on_a_word_asks_about_that_word():
    rt, _ = _runtime([])
    text, suggestions = _shown(list(rt.run(_open(WORD), ZH)))
    assert text == "Bạn muốn biết gì về từ này?"
    assert [intent for _, intent in suggestions] == ["prompt.word_meaning", "prompt.word_usage"]
    assert ("What is this screen for?", "prompt.app_help") not in suggestions


@pytest.mark.parametrize(("interface", "support", "text", "label"), [
    ("en", "en", "What would you like to know about this sentence?", "What does this sentence mean?"),
    ("zh-CN", "zh-CN", "你想了解这句话的什么？", "这句话是什么意思？"),
    ("en", "vi", "Bạn muốn biết gì về câu này?", "What does this sentence mean?"),  # a label is interface layer
])
def test_the_selection_opening_follows_the_layers(interface, support, text, label):
    rt, _ = _runtime([])
    shown, suggestions = _shown(list(rt.run(_open(SENTENCE, interface=interface, support=support), ZH)))
    assert shown == text and suggestions[0][0] == label


def test_the_selection_opening_uses_the_learners_address():
    rt, _ = _runtime([])
    address = {"self": "chị", "user": "em", "lang": "vi"}
    text, _ = _shown(list(rt.run(_open(SENTENCE, address=address), ZH)))
    assert text == "Em muốn biết gì về câu này?"


def test_another_selected_kind_gets_a_general_question():
    rt, _ = _runtime([])
    text, suggestions = _shown(list(rt.run(_open({"type": "grammar_point", "id": "g-1", "text": "了"}), ZH)))
    assert text == "Bạn muốn biết gì về phần này?" and [i for _, i in suggestions] == ["prompt.explain_selection"]


def test_an_opening_with_nothing_selected_is_unchanged():
    rt, provider = _runtime([reply("Chào bạn! Hôm nay bạn có 5 từ đến hạn ôn.")])
    list(rt.run(_open(None), ZH))
    assert len(provider.requests) == 1  # the snapshot greeting (S13) still asks the model
