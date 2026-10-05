"""LEX-006 (UX review 2026-10-05): an answer segment is plain text - spoken and shown as it is (contract §3) -
so the server takes Markdown out of the model's words, and asks for a short, question-first answer."""

from __future__ import annotations

import pytest

from writing_coach.agent.fake_provider import reply
from writing_coach.agent.honesty import ClaimGate, strip_markup
from writing_coach.agent.prompts import INSTRUCTION


@pytest.mark.parametrize(
    ("written", "plain"),
    [
        ("**热闹** nghĩa là đông vui.", "热闹 nghĩa là đông vui."),
        ("### Vì sao tương phản\n", "Vì sao tương phản\n"),
        ("---\n", "\n"),
        ("> 我的朋友住在北京。\n", "我的朋友住在北京。\n"),
        ("- Ví dụ một\n", "• Ví dụ một\n"),
        ("* Ví dụ hai\n", "• Ví dụ hai\n"),
        ("Từ *friend* là bạn.", "Từ friend là bạn."),
        ("Dùng `花生` khi nói về lạc.", "Dùng 花生 khi nói về lạc."),
        ("Xem [từ điển](https://example.test/x) nhé.", "Xem từ điển nhé."),
        ("__Chú ý__: nhẹ giọng.", "Chú ý: nhẹ giọng."),
        ("1. Câu đầu tiên.", "1. Câu đầu tiên."),  # a numbered line reads as text
        ("Giá 3 - 5 tệ.", "Giá 3 - 5 tệ."),  # a dash inside a line is a dash
    ],
)
def test_markdown_is_taken_out_of_an_answer(written, plain):
    assert strip_markup(written) == plain


def test_the_streamed_segment_has_no_markdown_and_equals_its_deltas():
    gate = ClaimGate(interface="vi", support="vi")
    deltas = gate.feed("### Giải thích\n**热闹** là *đông vui*.\n---\n> 这里很热闹。\n")
    deltas += gate.finish(None)
    text = "".join(deltas)
    for marker in ("**", "###", "---", "> ", "*"):
        assert marker not in text
    assert text == gate.text and "热闹 là đông vui." in text and "这里很热闹。" in text


def test_a_whole_turn_reaches_the_learner_without_markdown():
    from tests.test_agent_coaching import ZH, _runtime, _request

    rt, _ = _runtime([reply("### Nghĩa\n**花生** là *hạt lạc*.\n> 我喜欢吃花生。")])
    events = list(rt.run(_request("花生 từ này dùng thế nào?"), ZH))
    end = next(e for e in events if e.name == "segment_end")
    assert "**" not in end.text and "###" not in end.text and ">" not in end.text
    assert end.text == "".join(e.text_delta for e in events if e.name == "segment_delta")


def test_the_prompt_asks_for_plain_short_answers_about_the_selection():
    assert "plain text" in INSTRUCTION and "Markdown" in INSTRUCTION
    assert "context.selected_item" in INSTRUCTION and "add_reference" in INSTRUCTION

