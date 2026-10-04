"""Is the learner asking what the current screen is for? (F-13, contract v5 §6.2)

"Màn này dùng để làm gì?", "What can I do here?", "这个页面是做什么的？" ask about the
place, not about the learner. Such a turn is answered from the screen's published
purpose and the capabilities registered for it (context.screen, context.capabilities_here),
and the server withholds every tool for it: no learner data is read to explain a
screen, and no lesson is recommended unless the learner asks for one. The boundary is
the server's - which tools are offered - not a sentence in the prompt.

Like the identity gate (`identity.py`), it prefers precision: a message counts only
when the whole of it, greetings, punctuation and case set aside, is one of the
questions below. "Màn này dùng để làm gì, và mình nên học gì?" asks for more than the
screen and goes to the model with its tools, which still sees the screen's purpose.
"""

from __future__ import annotations

import re

from writing_coach.agent.identity import _LEADING, _ZH_LEADING, _lenient, _normalize

MAX_SCREEN_HELP_MESSAGE_CHARS = 120

# English: "this screen/page/place/section", and "here".
_EN_PLACE = r"(?:this|the) (?:screen|page|place|section|view|tab|part)"
_ENGLISH = (
    rf"what(?: is| s)? {_EN_PLACE}(?: for| about| used for)?",
    rf"what does {_EN_PLACE} do",
    rf"what (?:can|do|should|could) i do (?:here|on {_EN_PLACE}|in {_EN_PLACE})",
    rf"how does {_EN_PLACE} work",
    rf"what is (?:here|on {_EN_PLACE})",
    rf"what can {_EN_PLACE} do",
)

# Vietnamese, with diacritics (a bare letter matches its marked one, as in identity.py).
_VI_PLACE = r"(?:màn hình|màn|trang|phần|mục|chỗ|tab|giao diện)"
_VI_THIS = rf"{_VI_PLACE} (?:này|nay)"
_VI_ME = r"(?:tôi|mình|em|anh|chị|tớ|con|cháu)"
_VI_END = r"(?: (?:vậy|thế|đấy|à|hả|nhỉ|nhé|đó))?"
_VIETNAMESE = (
    rf"{_VI_THIS} (?:dùng )?(?:để )?(?:làm gì|làm chi|dùng làm gì){_VI_END}",
    rf"{_VI_THIS} (?:có|có những) (?:chức năng|tác dụng|công dụng|tính năng) gì{_VI_END}",
    rf"{_VI_THIS} (?:là gì|là để làm gì|là cái gì){_VI_END}",
    rf"(?:{_VI_ME} )?(?:có thể |được )?làm (?:được )?(?:gì|những gì) (?:ở|trong|trên) (?:đây|{_VI_THIS}){_VI_END}",
    rf"(?:ở|trong|trên) (?:đây|{_VI_THIS}) (?:{_VI_ME} )?(?:có thể |được )?làm (?:được )?(?:gì|những gì){_VI_END}",
    rf"(?:chức năng|tác dụng|công dụng) (?:của )?{_VI_THIS} là gì{_VI_END}",
    rf"{_VI_THIS} (?:hoạt động|dùng) (?:như thế nào|thế nào|ra sao){_VI_END}",
)

# Chinese, with spaces removed.
_ZH_PLACE = r"(?:这个|这)(?:页面|页|界面|屏幕|画面|地方|部分|功能)"
_ZH_END = r"[呀啊呢啦吗]?"
_CHINESE = (
    rf"{_ZH_PLACE}(?:是)?(?:用来)?(?:做什么|干什么|干嘛)的?{_ZH_END}",
    rf"{_ZH_PLACE}(?:有什么|有啥)(?:用|用处|作用|功能){_ZH_END}",
    rf"{_ZH_PLACE}(?:是什么){_ZH_END}",
    rf"(?:我)?(?:在)?(?:这里|这儿|这边|{_ZH_PLACE})(?:能|可以|该|要)?(?:做|干)(?:什么|些什么|啥){_ZH_END}",
    rf"(?:我)?(?:能|可以|该)在(?:这里|这儿|{_ZH_PLACE})(?:做|干)(?:什么|些什么|啥){_ZH_END}",
    rf"{_ZH_PLACE}怎么用{_ZH_END}",
)

_WORD_PATTERNS = (
    *(re.compile(rule) for rule in _ENGLISH),
    *(re.compile(_lenient(rule)) for rule in _VIETNAMESE),
)
_ZH_PATTERNS = tuple(re.compile(rule) for rule in _CHINESE)


def is_screen_help(message: str | None) -> bool:
    """True when the whole message asks what this screen is for or what can be done here."""

    if not message or len(message) > MAX_SCREEN_HELP_MESSAGE_CHARS:
        return False
    words = _normalize(message)
    stripped = _LEADING.sub("", words + " ").strip()
    if any(pattern.fullmatch(stripped) for pattern in _WORD_PATTERNS):
        return True
    compact = _ZH_LEADING.sub("", words.replace(" ", ""))
    return any(pattern.fullmatch(compact) for pattern in _ZH_PATTERNS)
