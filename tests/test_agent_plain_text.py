"""LEX-006 (UX review 2026-10-05, reopened): a segment's text may use the Markdown subset of contract §5.1 -
headings, bold, italic, lists, quotes, inline code, http(s) links - which the client renders. The server keeps
that subset, takes out what is not in it (an app-command link, label and all; a rule), turns run-together "•"
separators into a list, keeps a reference segment plain, and drops a button offer in the interface language
too. The prompt asks for a short answer, meaning first, grouped one per line, in the support language."""

from __future__ import annotations

import pytest

from tests.test_agent_coaching import _runtime
from writing_coach.agent.fake_provider import reply
from writing_coach.agent.honesty import ClaimGate, offers_a_button, plain_text, strip_markup
from writing_coach.agent.prompts import INSTRUCTION
from writing_coach.agent.provider import TextDelta, ToolCallRequest, TurnFinished
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.tools import LearnerScope

COMMAND = '[Open word](command:navigate?{"intent":"vocabulary.word","text":"花生"})'


@pytest.mark.parametrize(
    "kept",
    ["**花生** nghĩa là hạt lạc.", "### Nghĩa\n", "> 我喜欢吃花生。\n", "- 花生米\n", "1. Câu đầu tiên.",
     "Từ *friend* là bạn.", "Dùng `花生` khi nói về lạc.", "Xem [từ điển](https://example.test/x) nhé.",
     "Giá 3 - 5 tệ."],
)  # fmt: skip
def test_the_contract_subset_reaches_the_client(kept):
    assert strip_markup(kept) == kept


@pytest.mark.parametrize(
    ("written", "shown"),
    [
        (f"Nghĩa là hạt lạc. {COMMAND}", "Nghĩa là hạt lạc. "),  # an app command is never a link
        (f"{COMMAND}Tap Open word", "Tap Open word"),  # label and payload both go
        ("[Mở](orena://vocabulary)", ""),
        ("---\n", "\n"),  # a rule is not in the subset
        ("Từ vựng: 花生 • Pinyin: huāshēng • Ý nghĩa: hạt lạc", "- Từ vựng: 花生\n- Pinyin: huāshēng\n- Ý nghĩa: hạt lạc"),
        ("• Ví dụ một\n", "- Ví dụ một\n"),
    ],
)
def test_what_is_not_in_the_subset_is_taken_out_or_grouped(written, shown):
    assert strip_markup(written) == shown


def test_a_reference_segment_is_plain_text():
    assert plain_text("**我喜欢吃花生。**") == "我喜欢吃花生。"
    assert plain_text("> `花生`") == "花生"


@pytest.mark.parametrize("support", ["vi", "zh-CN"])
def test_a_button_offer_in_the_interface_language_is_the_servers_to_write(support):
    assert offers_a_button("Tap Open word", support, interface="en")
    assert not offers_a_button("Tap Open word", support)  # never another language than the turn's two


def test_the_gate_drops_the_command_link_and_the_models_own_offer():
    gate = ClaimGate(interface="en", support="vi")
    out = gate.feed(f"Nghĩa là hạt lạc.\n{COMMAND}Tap Open word.\n")
    out += gate.finish(None)
    text = "".join(out)
    assert "command:" not in text and "Tap Open word" not in text and "Nghĩa là hạt lạc." in text


def test_a_whole_turn_keeps_the_subset_and_no_command():
    request = TurnRequest.model_validate({
        "contract_version": 5, "trigger": "message", "message": "What does this word mean here?",
        "client": {"ui_version": "t", "supported_actions": ["navigate"], "supported_intents": ["vocabulary.word"]},
        "context": {"surface": "reading.workspace", "locale": {"interface": "en", "support": "vi", "target": "zh-CN"},
                    "selected_item": {"type": "word", "text": "花生", "lang": "zh-CN"}},
    })  # fmt: skip
    rt, _ = _runtime([reply(f"**花生** (huāshēng): hạt lạc.\n- 我喜欢吃花生。\n{COMMAND}Tap Open word")])
    events = list(rt.run(request, LearnerScope(user_key="learner-1", language="zh", interface="en")))
    end = next(e for e in events if e.name == "segment_end")
    assert end.text.startswith("**花生** (huāshēng): hạt lạc.") and "- 我喜欢吃花生。" in end.text
    assert "command:" not in end.text and "Tap Open word" not in end.text
    assert end.text == "".join(e.text_delta for e in events if e.name == "segment_delta")


def test_a_reference_the_model_adds_is_plain():
    rounds = [(TextDelta("Ví dụ:"), ToolCallRequest("c1", "add_reference", {"text": "**我喜欢吃花生。**", "lang": "zh-CN"}),
               TurnFinished(0, 3, "tool_calls"))]  # fmt: skip
    rt, _ = _runtime(rounds)
    from tests.test_agent_coaching import ZH, _request

    events = list(rt.run(_request("Cho mình một ví dụ với 花生"), ZH))
    reference = next(e for e in events if e.name == "segment_end" and e.voice_style == "reference")
    assert reference.text == "我喜欢吃花生。"


def test_the_prompt_follows_the_contract_subset_and_the_support_language():
    assert "§5.1" in INSTRUCTION and "meaning first" in INSTRUCTION
    assert "never write a link" in INSTRUCTION and "support language even when" in INSTRUCTION
    assert "context.selected_item" in INSTRUCTION and "plain text only" not in INSTRUCTION
