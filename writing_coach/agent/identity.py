"""Is the learner asking who Orena is? (spec §35, contract §10)

A learner who asks who they are talking to, or which model answers them, gets
the same answer every time: Orena, the app's learning assistant and coach,
never a provider or model name. The turn answers it from copy before any model
is asked, so no model can name itself.

The rules are strict on purpose. A message counts only when the whole of it,
once greetings, punctuation, case and Vietnamese diacritics are set aside, is
one of the questions below - so "Who are you going to meet?", "“bạn là ai”
nghĩa là gì?" or "你是谁 dịch là gì?" go to the model like any other message.
They are written for the three languages a learner writes to Orena in: English,
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

_BRANDS = (
    r"(?:chat ?gpt|gpt ?\w*|openai|gemini|google|bard|claude|anthropic|deepseek|llama|meta ai|qwen|mistral|copilot)"
)
_ZH_BRANDS = r"(?:chatgpt|gpt\w*|openai|gemini|google|claude|anthropic|deepseek|llama|qwen|kimi|文心一言|通义千问|豆包)"

# English and Vietnamese, matched on words separated by single spaces.
_VI_END = r"(?: (?:vay|the|day|a|ha|nhi|nhe|chu|di))?"
_VI_YOU = r"(?:ban|cau|em|may)"  # the ways a learner addresses Orena
_WORD_RULES: tuple[tuple[IdentityQuestion, str], ...] = (
    # English
    (IdentityQuestion.WHO, r"(?:who|what) (?:are|r) (?:you|u)(?: really| exactly| actually)?"),
    (IdentityQuestion.WHO, r"who am i (?:talking|speaking|chatting) (?:to|with)"),
    (IdentityQuestion.WHO, r"what(?: is| s)? your name"),
    (IdentityQuestion.WHO, r"(?:tell me about|introduce) yourself"),
    (IdentityQuestion.WHO, r"who (?:made|built|created|developed|trained|makes|owns) you"),
    (IdentityQuestion.WHO, r"are you (?:an? )?(?:ai|bot|robot|chatbot|human|person|real person|machine)"),
    (
        IdentityQuestion.MODEL,
        r"(?:what|which) (?:ai |language |llm )?model (?:are you|is this|do you use|are you using|"
        r"powers you|runs you|is behind you|are you based on)",
    ),
    (IdentityQuestion.MODEL, r"(?:what|which) (?:llm|ai) (?:are you|is this|do you use|are you using|powers you)"),
    (IdentityQuestion.MODEL, rf"(?:are you|is this) (?:using |based on |built on |powered by )?{_BRANDS}"),
    # Vietnamese, diacritics removed ("bạn là ai" and "ban la ai" alike)
    (IdentityQuestion.WHO, rf"{_VI_YOU} la ai{_VI_END}"),
    (IdentityQuestion.WHO, rf"{_VI_YOU} la (?:gi|cai gi|con gi){_VI_END}"),
    (IdentityQuestion.WHO, rf"(?:{_VI_YOU} ten (?:la )?gi|ten (?:cua )?{_VI_YOU} la gi){_VI_END}"),
    (
        IdentityQuestion.WHO,
        rf"(?:ai (?:tao ra|lam ra|phat trien|xay dung|huan luyen) {_VI_YOU}|"
        rf"{_VI_YOU} (?:do )?ai (?:tao ra|lam ra|phat trien)){_VI_END}",
    ),
    (
        IdentityQuestion.WHO,
        rf"{_VI_YOU} (?:co )?(?:phai )?la (?:ai|bot|robot|chatbot|nguoi|nguoi that|may)"
        r"(?: (?:a|ha|khong|phai khong|hay nguoi|hay may))?(?: vay)?",
    ),
    (IdentityQuestion.WHO, rf"gioi thieu (?:ve )?(?:ban than|{_VI_YOU})(?: di)?"),
    (
        IdentityQuestion.MODEL,
        rf"{_VI_YOU} (?:dung|su dung|chay tren|dua tren|duoc xay dung tren) (?:mo hinh|model|ai|llm) (?:gi|nao){_VI_END}",
    ),
    (IdentityQuestion.MODEL, rf"{_VI_YOU} la (?:mo hinh|model) (?:gi|nao){_VI_END}"),
    (IdentityQuestion.MODEL, rf"(?:mo hinh|model) (?:ai )?(?:cua {_VI_YOU} )?la (?:gi|cai nao){_VI_END}"),
    (
        IdentityQuestion.MODEL,
        rf"{_VI_YOU} (?:co )?(?:phai )?la {_BRANDS}(?: (?:a|ha|khong|phai khong|do a))?",
    ),
)

# Chinese, matched with the spaces removed.
_ZH_END = r"[呀啊呢啦]?"
_ZH_YOU = r"[你您]"
_ZH_RULES: tuple[tuple[IdentityQuestion, str], ...] = (
    (IdentityQuestion.WHO, rf"{_ZH_YOU}(?:到底)?是(?:谁|什么){_ZH_END}"),
    (IdentityQuestion.WHO, rf"(?:{_ZH_YOU}叫什么(?:名字)?|{_ZH_YOU}的名字是什么){_ZH_END}"),
    (IdentityQuestion.WHO, rf"(?:谁(?:创造|开发|制作|训练|做)了{_ZH_YOU}|{_ZH_YOU}是(?:由)?谁(?:开发|创造|制作|训练|做)的){_ZH_END}"),
    (IdentityQuestion.WHO, rf"{_ZH_YOU}是(?:机器人|人工智能|ai|真人|人)(?:吗|还是人){_ZH_END}"),
    (IdentityQuestion.WHO, rf"(?:介绍一下|介绍){_ZH_YOU}自己{_ZH_END}"),
    (
        IdentityQuestion.MODEL,
        rf"{_ZH_YOU}(?:是|用的是|使用的是|基于|是基于|用)(?:什么|哪个|哪一个|哪种)(?:ai|大|语言)?模型{_ZH_END}",
    ),
    (IdentityQuestion.MODEL, rf"{_ZH_YOU}(?:是|是不是|用的是|基于){_ZH_BRANDS}(?:吗)?{_ZH_END}"),
)

_WORD_PATTERNS = tuple((kind, re.compile(rule)) for kind, rule in _WORD_RULES)
_ZH_PATTERNS = tuple((kind, re.compile(rule)) for kind, rule in _ZH_RULES)

# Said before the question: a greeting, or Orena's name.
_LEADING = re.compile(r"^(?:(?:hi|hello|hey|chao|xin chao|orena|oi|你好|您好|请问|嗨|哈喽)\s+)+")
_ZH_LEADING = re.compile(r"^(?:你好|您好|请问|嗨|哈喽|orena)+")


def _normalize(message: str) -> str:
    """Casefolded, NFKC, Vietnamese diacritics removed, punctuation as spaces."""

    text = unicodedata.normalize("NFKC", message).casefold().replace("đ", "d")
    text = "".join(ch for ch in unicodedata.normalize("NFD", text) if not unicodedata.combining(ch))
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[^\w\s]|_", " ", text)
    return " ".join(text.split())


def identity_question(message: str | None) -> IdentityQuestion | None:
    """Which identity question the message is, when the whole message is one."""

    if not message or len(message) > MAX_IDENTITY_MESSAGE_CHARS:
        return None
    words = _normalize(message)
    stripped = _LEADING.sub("", words + " ").strip()
    for kind, pattern in _WORD_PATTERNS:
        if pattern.fullmatch(stripped):
            return kind
    compact = _ZH_LEADING.sub("", words.replace(" ", ""))
    for kind, pattern in _ZH_PATTERNS:
        if pattern.fullmatch(compact):
            return kind
    return None
