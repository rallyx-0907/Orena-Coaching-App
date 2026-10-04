"""Does the learner ask for a conclusion about their own learning? (dogfood gate 3.1)

"Hôm nay mình nên học gì?", "Mình hay sai gì nhất?", "Mình yếu phần nào?" ask for
a conclusion that only the learner's records can support. Such a turn must read
them before it answers: if the model answers without a read, it is asked once to
read; if it still has read nothing, the answer is a plain statement that there is
not enough to go on - never a weakness or a plan made up from nothing.

The gate is for the learner's learning as a whole, so it is narrow (independent
review 2026-10-04, P1): a first-person question about what to study, what goes
wrong, where they are weak, how they are doing. A question about what is in view -
"this sentence", "câu này", "这句话", or any turn that carries a selection, essay,
content, lesson or attempt - is about that thing, not the records, and is left to
the model as before.
"""

from __future__ import annotations

import re
import unicodedata

_VI_ME = r"(?:mình|tôi|em|tớ|con|cháu)"
_VI = (
    rf"(?:{_VI_ME} )?nên (?:học|ôn|luyện|luyện tập) (?:gì|cái gì|phần nào|những gì)",
    rf"hôm nay {_VI_ME}? ?(?:nên )?(?:học|ôn|luyện) (?:gì|cái gì)",
    r"(?:hay|thường|hay bị|thường bị|hay mắc|thường mắc) (?:sai|nhầm|mắc lỗi|lỗi) (?:gì|cái gì|chỗ nào|ở đâu|nhất|nhiều nhất)",
    r"(?:mắc|sai|gặp) (?:lỗi )?(?:gì|nào) nhiều nhất",
    r"sai nhiều nhất (?:ở )?(?:đâu|chỗ nào|phần nào)",
    rf"{_VI_ME} (?:yếu|kém) (?:phần|chỗ|mặt|kỹ năng|ở) (?:nào|gì|đâu)",
    rf"{_VI_ME} (?:yếu|kém) (?:gì|nhất)",
    rf"điểm yếu (?:của )?{_VI_ME}",
    rf"{_VI_ME} (?:đang )?(?:tiến bộ|tiến triển) (?:thế nào|ra sao|đến đâu)",
)
_EN = (
    r"what should i (?:learn|study|practi[cs]e|review|work on)(?: today| next| now)?\??$",
    r"what do i (?:usually |often |always |most often |keep )?(?:get wrong|getting wrong|struggle with)\??$",
    r"\bmy (?:weak(?:est)?|biggest) (?:areas?|points?|spots?|skills?)\b",
    r"\bmy (?:most )?common (?:mistakes|errors)\b",
    r"\bmy weakness(?:es)?\b",
    r"what am i (?:worst|weakest|bad|weak) at",
    r"how am i (?:doing|progressing)(?: overall| so far| with my (?:english|chinese|learning))\??$",
)
_ZH = (
    r"我(?:今天)?(?:应该|该)(?:学|复习|练|练习)(?:什么|哪些|啥)",
    r"我(?:经常|常常|总是|老是|最常)(?:犯|错|出错)(?:什么|哪些)",
    r"我(?:的)?(?:弱点|短板|薄弱环节|薄弱的地方)",
    r"我哪(?:方面|部分|里)(?:比较)?(?:弱|不好|差)",
    r"我最弱的",
    r"我(?:的)?(?:学习|进步)(?:怎么样|如何)",
)
# Something in view: the question is about it, not about the learner's records.
_IN_VIEW = re.compile(
    r"\b(?:this|that) (?:passage|sentence|essay|text|word|paragraph|line|article|draft)\b"
    r"|\b(?:câu|bài|đoạn|từ|chữ|dòng) (?:này|đó|ấy)\b"
    r"|(?:这|那)(?:句|段|篇|个词|个字|行|首)"
)

_PATTERN = re.compile("|".join((*_VI, *_EN)))
_ZH_PATTERN = re.compile("|".join(_ZH))


def needs_learner_evidence(message: str | None, *, in_view: bool = False) -> bool:
    """True for a first-person question about the learner's learning as a whole.

    `in_view` is true when the turn carries something on screen (a selection, an essay, content, a lesson or an
    attempt): the question is then about that, and this gate stays out of it."""

    if not message or in_view:
        return False
    text = unicodedata.normalize("NFC", unicodedata.normalize("NFKC", message).casefold()).strip()
    if _IN_VIEW.search(text):
        return False
    return bool(_PATTERN.search(text)) or bool(_ZH_PATTERN.search(text.replace(" ", "")))
