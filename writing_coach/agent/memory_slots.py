"""What a learner says about themselves, read by rule into closed codes (ORENA_MEMORY.md rev 4.1 §3.3, §3.4; D-222).

Continuity items hold a code, never free text: each slot has a closed list, and no list holds an excluded category
(health, religion, finances, ...), so none can be stored. The matcher reads one learner-authored message - the text
the learner typed or said, never pasted or selected text, a tool result or Orena's reply; the caller passes only
that - and yields (slot, code) pairs. It is conservative by design: it needs the learner speaking of themselves
("tôi là", "I'm", "我是") and the code's word within a few words after it, and it reads no negation as a statement.
A miss costs only an earlier expiry; a false match would put a wrong fact in front of every model.

The same matcher grounds a summariser's `useful_context` (§3.4): a (slot, code) is materialised only if it matches a
learner message of that session (`grounded`). `explanation_language_request` is the only signal of the
`explanation_language/1` rule: an explicit request, never the language the learner writes in.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from types import MappingProxyType

OCCUPATIONS = ("engineering", "it", "business", "education", "hospitality", "manufacturing", "design", "student")
TOPICS = ("sport", "work", "travel", "food", "technology", "music", "film", "games")
PURPOSES = ("job_interview", "exam", "work", "travel", "study", "everyday")  # first match wins: interview before work

SLOTS: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "occupation": OCCUPATIONS,
    "learning_purpose": PURPOSES,
    "interest": TOPICS,
    "example_domain": TOPICS,
})
SINGLE_VALUED = frozenset({"occupation", "learning_purpose"})

# The code's words in EN, VI and ZH. Matched case-insensitively on NFC text.
_WORDS: Mapping[str, Mapping[str, str]] = MappingProxyType({
    "occupation": {
        "engineering": r"kỹ sư|kĩ sư|engineer|工程师",
        "it": r"lập trình viên|lập trình|developer|programmer|software|程序员|软件|开发",
        "business": r"kinh doanh|bán hàng|sales|marketing|business|销售|市场|商务",
        "education": r"giáo viên|giảng viên|teacher|lecturer|老师|教师",
        "hospitality": r"khách sạn|nhà hàng|hotel|restaurant|酒店|餐厅|饭店",
        "manufacturing": r"nhà máy|sản xuất|factory|manufacturing|工厂|制造",
        "design": r"thiết kế|designer|设计",
        "student": r"sinh viên|học sinh|student|学生|大学生",
    },
    "learning_purpose": {
        "job_interview": r"phỏng vấn|interview|面试",
        "exam": r"kỳ thi|kì thi|thi|hsk\d?|ielts|toeic|toefl|exam|考试",
        "work": r"công việc|đi làm|làm việc|work|job|工作",
        "travel": r"du lịch|travel|旅游|旅行",
        "study": r"du học|đại học|study abroad|university|留学|大学",
        "everyday": r"giao tiếp|hằng ngày|hàng ngày|everyday|daily|conversation|日常|交流",
    },
    "topic": {
        "sport": r"bóng đá|bóng rổ|thể thao|football|soccer|basketball|sports?|足球|篮球|运动|体育",
        "work": r"công việc|văn phòng|work|office|工作|办公",
        "travel": r"du lịch|travel\w*|旅游|旅行",
        "food": r"ẩm thực|nấu ăn|đồ ăn|cooking|food|美食|做饭|烹饪",
        "technology": r"công nghệ|technology|tech|科技|技术",
        "music": r"âm nhạc|nhạc|music|音乐",
        "film": r"phim|movies?|films?|电影",
        "games": r"trò chơi|game|games|gaming|游戏",
    },
})

_SELF_VI = r"(?:tôi|mình|em|tớ)"
_SELF_EN = r"\bi"
# Each cue ends where the code's words may start. A negation never matches a cue ("tôi không thích", "I don't
# like", "我不喜欢"), so it is not read as a statement.
_CUES: Mapping[str, str] = MappingProxyType({
    "occupation": (
        rf"\b{_SELF_VI} (?:là|làm|đang làm|làm nghề|làm việc (?:ở|tại|trong))\b"
        rf"|{_SELF_EN}(?:'m| am| work as| work in| work at)\b"
        r"|我(?:是|在|当|做|从事)"
    ),
    "learning_purpose": (
        rf"\b{_SELF_VI} học(?: tiếng \w+)? (?:để|vì|cho)\b|\bmục (?:tiêu|đích) (?:của {_SELF_VI} )?(?:là )?"
        rf"|{_SELF_EN}(?:'m| am)? (?:learning|studying)(?: \w+)? (?:to|for|because)\b"
        r"|\bmy (?:goal|aim|purpose) is\b"
        r"|我学(?:中文|汉语|英语|英文)?(?:是)?(?:为了|因为)|我的目标是"
    ),
    "interest": (
        rf"\b{_SELF_VI} (?:rất |cũng )?(?:thích|mê|yêu thích|quan tâm(?: đến)?)\b"
        rf"|{_SELF_EN}(?: really| also)? (?:like|love|enjoy)\b|{_SELF_EN}(?:'m| am) (?:into|interested in|a fan of)\b"
        r"|我(?:很|特别|非常|也)?(?:喜欢|爱|热爱|对)"
    ),
    "example_domain": (
        r"\bví dụ (?:về|liên quan (?:đến|tới)|trong)\b"
        r"|\bexamples? (?:about|on|from|related to|with)\b"
        r"|(?:关于|有关)"
    ),
})
# Words between the cue and the code that turn a statement about oneself into talk about learning a word
# ("I'm learning engineering vocabulary"): such a statement says nothing about the learner.
_LEARNING = re.compile(r"(?i)\b(?:learning|studying|practising|practicing|học|luyện)\b|学|练")
_WINDOW_WORDS = 4  # words after the cue the code's word must start in
_WINDOW_CJK = 8  # characters, for text without spaces
_CJK = re.compile(r"[㐀-鿿]")

_EXPLAIN = re.compile(
    r"(?i)\bgiải thích (?:lại )?(?:bằng|sang) tiếng (?P<vi>việt|anh|trung)\b"
    r"|\bexplain(?: it| that| this)?(?: again)? in (?P<en>english|vietnamese|chinese|mandarin)\b"
    r"|用(?P<zh>中文|汉语|英文|英语|越南语)(?:来)?(?:解释|讲|说)"
)
_LANGUAGE = MappingProxyType({
    "việt": "vi", "anh": "en", "trung": "zh",
    "english": "en", "vietnamese": "vi", "chinese": "zh", "mandarin": "zh",
    "中文": "zh", "汉语": "zh", "英文": "en", "英语": "en", "越南语": "vi",
})


def _compiled(pattern: str) -> re.Pattern[str]:
    return re.compile(rf"(?i)(?:{pattern})")


def _whole_words(words: str) -> re.Pattern[str]:
    """A latin word matches only as a whole word ("thi" is not in "thiết kế"); Chinese has no spaces to bound it."""

    parts = [part if _CJK.search(part) else rf"\b{part}\b" for part in words.split("|")]
    return _compiled("|".join(parts))


_CUE_RE = {slot: _compiled(cue) for slot, cue in _CUES.items()}
_WORD_RE = {
    group: {code: _whole_words(words) for code, words in codes.items()} for group, codes in _WORDS.items()
}
# Chinese puts the topic before 例子: 用足球的例子, 举工作的例子, 给我旅游的例句.
_ZH_EXAMPLES = re.compile(r"(?:用|举|给我|请用|多用)(?P<topic>[^，。！？,.!?]{1,6}?)的?例[子句]")


def _words_for(slot: str) -> dict[str, re.Pattern[str]]:
    return _WORD_RE["topic" if slot in ("interest", "example_domain") else slot]


def _window(text: str, start: int) -> str:
    """The few words after a cue (or, in Chinese, the few characters), up to the end of the sentence."""

    rest = re.split(r"[.!?;。！？；\n]", text[start:], maxsplit=1)[0]
    if _CJK.match(rest.lstrip()[:1] or " "):
        return rest.lstrip()[:_WINDOW_CJK]
    return " ".join(rest.split()[:_WINDOW_WORDS])


def _codes_in(slot: str, window: str) -> list[str]:
    found = []
    for code in SLOTS[slot]:
        hit = _words_for(slot)[code].search(window)
        if hit and not _LEARNING.search(window[: hit.start()]):
            found.append(code)
    return found


def statements(message: str | None) -> set[tuple[str, str]]:
    """The (slot, code) pairs one learner message states about the learner."""

    text = unicodedata.normalize("NFC", message or "")
    pairs: set[tuple[str, str]] = set()
    for slot, cue in _CUE_RE.items():
        for hit in cue.finditer(text):
            codes = _codes_in(slot, _window(text, hit.end()))
            if slot in SINGLE_VALUED:
                codes = codes[:1]
            pairs.update((slot, code) for code in codes)
    for hit in _ZH_EXAMPLES.finditer(text):
        pairs.update(("example_domain", code) for code in _codes_in("example_domain", hit["topic"]))
    return pairs


def grounded(slot: str, code: str, learner_messages: Iterable[str]) -> bool:
    """A summariser's (slot, code) is stored only if a learner message of that session states it (§3.4)."""

    if code not in SLOTS.get(slot, ()):
        return False
    return any((slot, code) in statements(message) for message in learner_messages)


def explanation_language_request(message: str | None) -> str | None:
    """The language an explicit request asks the explanation in ("giải thích bằng tiếng Việt", "explain in
    English", "用中文解释"), else None. Writing in a language is never a request."""

    hit = _EXPLAIN.search(unicodedata.normalize("NFC", message or ""))
    if not hit:
        return None
    word = next(value for value in hit.groupdict().values() if value)
    return _LANGUAGE[word.casefold()]
