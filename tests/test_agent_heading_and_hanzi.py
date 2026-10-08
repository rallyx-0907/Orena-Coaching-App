"""LEX-006 (retest at b42d4d2): a heading asked for is a heading even when the model wrote its first line plainly,
and a Chinese example never carries an English function word between its characters ("我们可以用花生做 and 汤。")."""

from __future__ import annotations

import pytest

from writing_coach.agent.honesty import ClaimGate, plain_text, strip_markup
from writing_coach.agent.prompts import INSTRUCTION


def _headed(text):
    gate = ClaimGate(interface="vi", support="vi")
    gate.heading_asked = True
    return "".join(gate.feed(text) + gate.finish(None))


@pytest.mark.parametrize(("written", "shown"), [
    ("Từ vựng: 花生\n**Nghĩa chính:** hạt lạc.\n", "### Từ vựng: 花生\n**Nghĩa chính:** hạt lạc.\n"),
    ("**花生 trong câu này**\nNghĩa: lạc.\n", "### 花生 trong câu này\nNghĩa: lạc.\n"),
    ("## 花生\nNghĩa: lạc.\n", "## 花生\nNghĩa: lạc.\n"),  # already a heading
])  # fmt: skip
def test_a_requested_heading_is_the_first_short_line(written, shown):
    assert _headed(written) == shown


@pytest.mark.parametrize("written", [
    "花生 là hạt lạc, loại hạt các con trong bài rất thích ăn.\n",  # a sentence, not a title
    "- 花生米\n- 花生油\n",  # a list item
])  # fmt: skip
def test_a_sentence_or_a_list_item_is_never_made_a_heading(written):
    assert _headed(written) == written


def test_only_the_first_line_is_ever_a_heading():
    assert _headed("Từ vựng: 花生\nVí dụ\n") == "### Từ vựng: 花生\nVí dụ\n"


@pytest.mark.parametrize(("written", "shown"), [
    ("1. 我们可以用花生做 and 汤。\n", "1. 我们可以用花生做汤。\n"),
    ("- **Hanzi:** 我喜欢 the 花生。\n", "- **Hanzi:** 我喜欢花生。\n"),
    ("他买了 or 卖了花生。", "他买了卖了花生。"),
])  # fmt: skip
def test_an_english_function_word_inside_a_chinese_example_is_taken_out(written, shown):
    assert strip_markup(written) == shown


@pytest.mark.parametrize("kept", ["我买了一部iPhone手机。", "用 Python 写程序。", "Pinyin: wǒ xǐhuan and nǐ",
                                  "花生 and 豆子 are both nuts."])  # fmt: skip
def test_other_latin_words_are_left_alone(kept):
    # a name or a term inside Chinese, and English prose that merely mentions Chinese words, stay as written
    assert strip_markup(kept) == kept


def test_a_reference_is_repaired_too():
    assert plain_text("我们可以用花生做 and 汤。") == "我们可以用花生做汤。"


def test_the_prompt_starts_a_requested_heading_with_a_heading_line():
    flat = " ".join(INSTRUCTION.split())
    assert 'start the answer with a "### " line' in flat and "no English word between its characters" in flat
