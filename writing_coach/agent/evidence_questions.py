"""Does the learner ask for a conclusion about their own learning? (dogfood gate 3.1)

"Hôm nay mình nên học gì?", "Mình hay sai gì nhất?", "Mình yếu phần nào?" ask for
a conclusion that only the learner's records can support. Such a turn must read
them before it answers: if the model answers without a read, it is asked once to
read; if it still has read nothing, the answer is replaced by a plain statement
that there is not enough to go on - never a weakness or a plan made up from nothing.

Matched anywhere in the message (unlike the whole-message identity and screen
gates): a longer question that contains one of these still needs the records.
"""

from __future__ import annotations

import re
import unicodedata

_VI = (
    r"nên (?:học|ôn|luyện|làm) (?:gì|cái gì|phần nào|gì tiếp|gì trước)",
    r"(?:hay|thường|hay bị|thường bị) (?:sai|nhầm|mắc lỗi|quên) (?:gì|cái gì|chỗ nào|ở đâu|nhất)",
    r"lỗi (?:nào|gì) (?:hay|thường|nhiều nhất)",
    r"(?:yếu|kém) (?:phần|chỗ|ở|mặt|kỹ năng) (?:nào|gì|đâu)",
    r"(?:điểm|phần|chỗ|kỹ năng) yếu",
    r"(?:mình|tôi|em|tớ) (?:đang )?(?:tiến bộ|tiến triển) (?:thế nào|ra sao|không)",
)
_EN = (
    r"what should i (?:learn|study|practi[cs]e|review|work on|do next|focus on)",
    r"what do i (?:get wrong|struggle with|keep getting wrong|need to work on|mess up)",
    r"(?:my|the) (?:weak(?:est)?|common|biggest|most common) (?:areas?|points?|spots?|skills?|mistakes?|errors?)",
    r"where am i weak|what am i (?:bad|weak) at|my weakness(?:es)?",
    r"how am i (?:doing|progressing)",
)
_ZH = (
    r"(?:我)?(?:应该|该|要)(?:学|复习|练|练习)(?:什么|哪些|啥)",
    r"(?:我)?(?:经常|常常|总是|老是)?(?:犯|错|出错)(?:什么|哪些|最多)",
    r"(?:我的)?(?:弱点|薄弱|不足|短板)",
    r"(?:我)?哪(?:方面|部分|里)(?:弱|不好|差)",
    r"(?:我)?(?:进步|学得)(?:怎么样|如何)",
)

_PATTERN = re.compile("|".join((*_VI, *_EN)), re.IGNORECASE)
_ZH_PATTERN = re.compile("|".join(_ZH))


def needs_learner_evidence(message: str | None) -> bool:
    if not message:
        return False
    text = unicodedata.normalize("NFC", unicodedata.normalize("NFKC", message).casefold())
    return bool(_PATTERN.search(text)) or bool(_ZH_PATTERN.search(text.replace(" ", "")))
