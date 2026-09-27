"""Who Orena is, answered by rule before any model (spec §35, contract §10)."""

from __future__ import annotations

import pytest

from writing_coach.agent import learner_copy
from writing_coach.agent.identity import MAX_IDENTITY_MESSAGE_CHARS, IdentityQuestion, identity_question

WHO, MODEL = IdentityQuestion.WHO, IdentityQuestion.MODEL


@pytest.mark.parametrize(
    ("message", "kind"),
    [
        ("Who are you?", WHO),
        ("hi, who are you really?", WHO),
        ("Orena, what's your name?", WHO),
        ("Who am I talking to?", WHO),
        ("Who made you?", WHO),
        ("Are you a bot?", WHO),
        ("Tell me about yourself.", WHO),
        ("What model are you?", MODEL),
        ("Which AI model do you use?", MODEL),
        ("Are you ChatGPT?", MODEL),
        ("are you gpt-4o", MODEL),
        ("Is this Gemini?", MODEL),
        ("Bạn là ai?", WHO),
        ("ban la ai", WHO),
        ("Orena ơi, bạn là ai vậy?", WHO),
        ("Chào, cậu tên là gì thế?", WHO),
        ("Tên bạn là gì?", WHO),
        ("Ai tạo ra bạn?", WHO),
        ("Bạn là người hay máy?", WHO),
        ("Bạn có phải là robot không?", WHO),
        ("Giới thiệu bản thân đi", WHO),
        ("Bạn dùng mô hình gì?", MODEL),
        ("Bạn là model nào vậy?", MODEL),
        ("Mô hình AI của bạn là gì?", MODEL),
        ("Bạn có phải là ChatGPT không?", MODEL),
        ("你是谁？", WHO),
        ("你好，你是谁呀", WHO),
        ("您叫什么名字？", WHO),
        ("谁开发了你？", WHO),
        ("你是机器人吗？", WHO),
        ("介绍一下你自己", WHO),
        ("你是什么模型？", MODEL),
        ("你用的是哪个大模型", MODEL),
        ("你是ChatGPT吗？", MODEL),
        ("你是不是 Gemini", MODEL),
    ],
)
def test_the_identity_questions_in_three_languages(message, kind):
    assert identity_question(message) is kind


@pytest.mark.parametrize(
    "message",
    [
        None,
        "",
        "Who are you going to meet tomorrow?",
        'What does "who are you" mean?',
        "“Bạn là ai” nghĩa là gì?",
        "Dịch giúp mình: bạn là ai",
        "你是谁 dịch là gì?",
        "我不知道你是谁",
        "What model sentence should I use?",
        "Is this sentence correct?",
        "Anh ấy là ai?",
        "Tại sao tôi cứ sai từ này?",
        "Hôm nay tôi nên học gì?",
        "Who are you? " * 20,
    ],
)
def test_anything_else_goes_to_the_model(message):
    assert identity_question(message) is None


def test_a_long_message_is_never_one():
    assert identity_question("Who are you?" + " " * MAX_IDENTITY_MESSAGE_CHARS) is None


@pytest.mark.parametrize("kind", list(IdentityQuestion))
def test_the_answer_is_orena_in_every_support_language_and_names_no_provider(kind):
    entry = learner_copy.CATALOG[f"identity.{kind.value}"]
    assert entry.layer is learner_copy.CopyLayer.SUPPORT
    assert set(entry.texts) == {"en", "vi", "zh-CN"}
    for words in entry.texts.values():
        assert "Orena" in words
        lowered = words.casefold()
        for vendor in ("openai", "gpt", "gemini", "google", "claude", "anthropic", "deepseek", "ollama", "llama"):
            assert vendor not in lowered, (vendor, words)
