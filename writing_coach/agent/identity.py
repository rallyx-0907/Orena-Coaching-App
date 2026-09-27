"""Is the learner asking who Orena is? (spec §35, contract §10)

A learner who asks who they are talking to, or which model answers them, gets
the same answer every time: Orena, the app's learning assistant and coach,
never a provider or model name. The turn answers it from copy before any model
is asked, so no model can name itself.

The gate prefers precision. A message counts only when the whole of it, once
greetings, punctuation and case are set aside, is one of the questions below -
so "Who are you going to meet?", "“bạn là ai” nghĩa là gì?" or "你是谁 dịch là
gì?" go to the model like any other message, and the model's instruction still
makes it answer as Orena.

Vietnamese is matched with its diacritics. A letter typed without its mark
still matches ("ban là ai"), a letter with a different mark does not: "Câu là
gì?" (what is a sentence), "Bàn là gì?" and "Máy là gì?" are not questions about
Orena. A message typed wholly without diacritics matches only the rules whose
bare form cannot mean anything else: "ban la ai" does, "cau la gi", "ban la gi"
and "may la gi" do not - each could be about a word - so they go to the model.
The rules cover the three languages a learner writes to Orena in: English,
Vietnamese and Chinese.
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum


class IdentityQuestion(StrEnum):
    WHO = "who"  # who or what Orena is, who made it
    MODEL = "model"  # which model or provider answers


MAX_IDENTITY_MESSAGE_CHARS = 120

WHO, MODEL = IdentityQuestion.WHO, IdentityQuestion.MODEL

_BRANDS = (
    r"(?:chat ?gpt|gpt ?\w*|openai|gemini|google|bard|claude|anthropic|deepseek|llama|meta ai|qwen|mistral|copilot)"
)
_ZH_BRANDS = r"(?:chatgpt|gpt\w*|openai|gemini|google|claude|anthropic|deepseek|llama|qwen|kimi|文心一言|通义千问|豆包)"

_ENGLISH: tuple[tuple[IdentityQuestion, str], ...] = (
    (WHO, r"(?:who|what) (?:are|r) (?:you|u)(?: really| exactly| actually)?"),
    (WHO, r"who am i (?:talking|speaking|chatting) (?:to|with)"),
    (WHO, r"what(?: is| s)? your name"),
    (WHO, r"(?:tell me about|introduce) yourself"),
    (WHO, r"who (?:made|built|created|developed|trained|makes|owns) you"),
    (WHO, r"are you (?:an? )?(?:ai|bot|robot|chatbot|human|person|real person|machine)"),
    (
        MODEL,
        r"(?:what|which) (?:ai |language |llm )?model (?:are you|is this|do you use|are you using|"
        r"powers you|runs you|is behind you|are you based on)",
    ),
    (MODEL, r"(?:what|which) (?:llm|ai) (?:are you|is this|do you use|are you using|powers you)"),
    (MODEL, rf"(?:are you|is this) (?:using |based on |built on |powered by )?{_BRANDS}"),
)

# Vietnamese, written with its diacritics. The flag says whether the rule may
# match a message typed wholly without them: only when that bare form is unambiguous.
_VI_END = r"(?: (?:vậy|thế|đấy|à|hả|nhỉ|nhé|chứ|đi))?"
_VI_YOU = r"(?:bạn|cậu|em|mày)"  # the ways a learner addresses Orena
_VIETNAMESE: tuple[tuple[IdentityQuestion, str, bool], ...] = (
    (WHO, rf"{_VI_YOU} là ai{_VI_END}", True),
    # "câu/bàn/máy là gì" is a question about a word: never matched bare.
    (WHO, rf"{_VI_YOU} là (?:gì|cái gì|con gì){_VI_END}", False),
    (WHO, rf"(?:{_VI_YOU} tên (?:là )?gì|tên (?:của )?{_VI_YOU} là gì){_VI_END}", True),
    # "ai tạo ra bàn" is a question about a table: never matched bare.
    (
        WHO,
        rf"(?:ai (?:tạo ra|làm ra|phát triển|xây dựng|huấn luyện) {_VI_YOU}|"
        rf"{_VI_YOU} (?:do )?ai (?:tạo ra|làm ra|phát triển)){_VI_END}",
        False,
    ),
    (
        WHO,
        rf"{_VI_YOU} (?:có )?(?:phải )?là (?:bot|robot|chatbot|người thật|người|máy)"
        r"(?: (?:à|hả|không|phải không|hay người|hay máy))?(?: vậy)?",
        True,
    ),
    (WHO, rf"giới thiệu (?:về )?(?:bản thân|{_VI_YOU})(?: đi)?", True),
    (
        MODEL,
        rf"{_VI_YOU} (?:dùng|sử dụng|chạy trên|dựa trên|được xây dựng trên) (?:mô hình|model|ai|llm) (?:gì|nào){_VI_END}",
        True,
    ),
    (MODEL, rf"{_VI_YOU} là (?:mô hình|model) (?:gì|nào){_VI_END}", True),
    # "Mô hình (AI) là gì?" asks what a model is; only "…của bạn…" asks about Orena.
    (MODEL, rf"(?:mô hình|model) (?:ai )?của {_VI_YOU} là (?:gì|cái nào){_VI_END}", True),
    (MODEL, rf"{_VI_YOU} (?:có )?(?:phải )?là {_BRANDS}(?: (?:à|hả|không|phải không|đó à))?", True),
)

# Chinese, matched with the spaces removed.
_ZH_END = r"[呀啊呢啦]?"
_ZH_YOU = r"[你您]"
_CHINESE: tuple[tuple[IdentityQuestion, str], ...] = (
    (WHO, rf"{_ZH_YOU}(?:到底)?是(?:谁|什么){_ZH_END}"),
    (WHO, rf"(?:{_ZH_YOU}叫什么(?:名字)?|{_ZH_YOU}的名字是什么){_ZH_END}"),
    (WHO, rf"(?:谁(?:创造|开发|制作|训练|做)了{_ZH_YOU}|{_ZH_YOU}是(?:由)?谁(?:开发|创造|制作|训练|做)的){_ZH_END}"),
    (WHO, rf"{_ZH_YOU}是(?:机器人|人工智能|ai|真人|人)(?:吗|还是人){_ZH_END}"),
    (WHO, rf"(?:介绍一下|介绍){_ZH_YOU}自己{_ZH_END}"),
    (MODEL, rf"{_ZH_YOU}(?:是|用的是|使用的是|基于|是基于|用)(?:什么|哪个|哪一个|哪种)(?:ai|大|语言)?模型{_ZH_END}"),
    (MODEL, rf"{_ZH_YOU}(?:是|是不是|用的是|基于){_ZH_BRANDS}(?:吗)?{_ZH_END}"),
)


def _bare(text: str) -> str:
    """The text without Vietnamese diacritics (đ -> d); other scripts unchanged."""

    text = text.replace("đ", "d").replace("Đ", "D")
    stripped = "".join(ch for ch in unicodedata.normalize("NFD", text) if not unicodedata.combining(ch))
    return unicodedata.normalize("NFC", stripped)


def _lenient(rule: str) -> str:
    """Each marked letter of a rule matches itself or its bare letter, never another mark."""

    return "".join(f"[{_bare(ch)}{ch}]" if _bare(ch) != ch else ch for ch in unicodedata.normalize("NFC", rule))


_WORD_PATTERNS: tuple[tuple[IdentityQuestion, re.Pattern[str], bool], ...] = (
    *((kind, re.compile(rule), True) for kind, rule in _ENGLISH),
    *((kind, re.compile(_lenient(rule)), bare_ok) for kind, rule, bare_ok in _VIETNAMESE),
)
_ZH_PATTERNS = tuple((kind, re.compile(rule)) for kind, rule in _CHINESE)

# Said before the question: a greeting, or Orena's name.
_LEADING = re.compile(_lenient(r"^(?:(?:hi|hello|hey|xin chào|chào|orena|ơi|你好|您好|请问|嗨|哈喽)\s+)+"))
_ZH_LEADING = re.compile(r"^(?:你好|您好|请问|嗨|哈喽|orena)+")


def _normalize(message: str) -> str:
    """Casefolded, NFKC then NFC, punctuation as spaces; diacritics kept."""

    text = unicodedata.normalize("NFC", unicodedata.normalize("NFKC", message).casefold())
    text = re.sub(r"[^\w\s]|_", " ", text)
    return " ".join(text.split())


def identity_question(message: str | None) -> IdentityQuestion | None:
    """Which identity question the message is, when the whole message is one."""

    if not message or len(message) > MAX_IDENTITY_MESSAGE_CHARS:
        return None
    words = _normalize(message)
    typed_bare = _bare(words) == words
    stripped = _LEADING.sub("", words + " ").strip()
    for kind, pattern, bare_ok in _WORD_PATTERNS:
        if (bare_ok or not typed_bare) and pattern.fullmatch(stripped):
            return kind
    compact = _ZH_LEADING.sub("", words.replace(" ", ""))
    for kind, pattern in _ZH_PATTERNS:
        if pattern.fullmatch(compact):
            return kind
    return None
