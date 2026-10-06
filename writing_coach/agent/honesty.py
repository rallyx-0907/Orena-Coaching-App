"""Nothing is reported as done (human review of the live run, 2026-09-28; adversarial review).

The backend changes nothing (D6): an action is a button the learner taps, and
until then nothing has happened. The model writes its answer and proposes the
action in the same round, so it never reads that the learner has not tapped -
the live run showed "Từ 我 đã được lưu" beside a "Lưu từ" button. The
instruction says not to; this is the guarantee.

Two kinds of sentence are claims:
- Orena saying it acted ("Mình đã lưu…", "Mình lưu 是 cho bạn rồi", "I've
  saved it", "Saved!", "我帮你保存了"). Always false: dropped in every turn.
- A completion stated without an actor ("Từ 我 đã được lưu", "It has been
  saved", "已保存"). False while a button is pending; otherwise it is usually
  a state a tool read ("already in your library"), so it stays.
With a button, the dropped sentences are replaced by an offer of it ("Bấm
“Lưu từ” nếu bạn muốn."); without one, by nothing - or, when nothing would be
left, by "Mình chưa thay đổi gì cả." A question ("Đã mở phần Ngữ pháp chưa?")
is never a claim, nor is what the button will do ("Bấm Lưu từ để lưu 我") or
the learner's own past ("các từ bạn đã lưu").

The patterns cover the three support languages and the completion verbs of the
action allowlist (save, add, remove, open, start).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from writing_coach.agent import learner_copy

_VI_ACT = "lưu|thêm|xóa|xoá|bỏ lưu|mở|chuyển|bắt đầu"
_VI_MEMORY = "ghi nhớ|ghi lại"  # what a memory_update does: true when the turn carries one (contract v5 B1)
_EN_DONE = r"(?:saved|added|removed|deleted|opened|started)"
_ZH_ACT = "保存|添加|加入|删除|移除|收藏|打开|开始"
_ZH_MEMORY = "记录|记下"
# What the app itself saves, opens or starts: the objects that make "我…了" a claim, not a lesson sentence.
_ZH_APP_OBJECT = "它|这个词|这个字|该词|设置|页面|复习|词库|生词本|收藏夹|笔记|练习|课程|你的"


# Who Orena is and who the learner is, in a claim: the defaults, plus the learner's own address (contract v5
# §5.6) - "Chị lưu 我 cho em nhé" is as much a claim as "Mình lưu 我 cho bạn nhé" (the old S5 line).
_VI_SELF, _VI_USER = ("mình", "orena", "tôi"), ("bạn",)
_ZH_SELF, _ZH_USER = ("我",), ("你", "您")


def _alternation(words) -> str:
    return "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True))


def _patterns(
    vi_done: str,
    zh_done: str,
    vi_self: tuple[str, ...] = _VI_SELF,
    vi_user: tuple[str, ...] = _VI_USER,
    zh_self: tuple[str, ...] = _ZH_SELF,
    zh_user: tuple[str, ...] = _ZH_USER,
) -> tuple[re.Pattern[str], re.Pattern[str]]:
    vi, zh = f"(?:{vi_done})", f"(?:{zh_done})"
    me, you = f"(?:{_alternation(vi_self)})", f"(?:{_alternation(vi_user)})"
    zme, zyou = f"(?:{_alternation(zh_self)})", f"(?:{_alternation(zh_user)})"
    # Orena (or an implied Orena: a sentence that opens with the verb) says it acted.
    acted = re.compile(
        r"(?im)"
        rf"\b{me}\s+(?:vừa\s+|đã\s+|vừa\s+đã\s+)?{vi}\b[^.!?\n]{{0,60}}?\b(?:rồi|xong)\b"
        rf"|\b{me}\s+(?:vừa\s+)?đã\s+{vi}\b"
        rf"|\b{me}\s+vừa\s+{vi}\b"
        rf"|\b{me}\s+(?:sẽ\s+)?{vi}\b[^.!?\n]{{0,40}}?\bcho\s+{you}\b"
        rf"|^\W*đã\s+{vi}\b"
        rf"|\b(?:lưu|thêm|xóa|xoá)\s+xong\b"
        rf"|\bI(?:'ve|\s+have)?\s+(?:just\s+)?{_EN_DONE}\b"
        rf"|^\W*(?:done[,!.]?\s*)?{_EN_DONE}\b"
        rf"|(?:{zme}|已经)?(?:帮|为|给){zyou}{zh}(?:下来?|好)?了"
        rf"|(?:帮|为|给){zyou}{zh}好"
        rf"|(?:保存|添加|收藏|删除)(?:好|成功)了"
        # Dogfood gate 3.5: forms the audit found getting through.
        # Past only (đã/vừa): "Mình đưa bạn đến phần Ôn tập nhé?" is an offer, not a claim (review P2-4).
        rf"|\b{me}\s+(?:vừa|đã|vừa\s+đã)\s+(?:đưa|dẫn)\s+{you}\s+(?:tới|đến|sang|vào)\b"
        r"|\bI(?:'ve|\s+have)?\s+(?:just\s+)?(?:moved|taken|brought|sent|switched|navigated)\s+you\b"
        rf"|\bI(?:'ve|\s+have)?\s+gone\s+ahead\s+and\s+{_EN_DONE}\b"
        # A bare gerund only with an app object: "Adding a comma now makes it correct" is grammar (review P2-3).
        r"|^\W*(?:opening|saving|adding)\s+(?:it|that|this\s+word|the\s+(?:page|review|word|lesson|section)|your)\b"
        r"[^.!?\n]{0,30}?\bnow\b"
        r"|^\W*(?:moving|taking)\s+you\b[^.!?\n]{0,40}?\bnow\b"
        rf"|已(?:经)?(?:帮|为|给){zyou}(?:{zh})"
        # "我打开了门", "我收藏了很多书" are lesson sentences: only the app's own objects make it a claim (P2-2).
        rf"|{zme}(?:已经|已)?(?:{zh})了(?:{_ZH_APP_OBJECT})"
        # "我已经保存了。" alone: done, with nothing after it that makes it a lesson sentence.
        rf"|{zme}(?:已经|已)(?:{zh})了(?=[。！!.\s]*$)"
        rf"|{zme}(?:已经|已)?把(?:{_ZH_APP_OBJECT})[^。！？\n]{{0,12}}?(?:{zh})[^。！？\n]{{0,10}}?(?:了(?!解)|好)"
    )
    # A completion with no actor: false only beside a pending button.
    stated = re.compile(
        r"(?i)"
        rf"\bđã\s+được\s+{vi}\b"
        rf"|\b(?:has|have|had)\s+been\s+{_EN_DONE}\b"
        r"|\bis\s+now\s+(?:saved|in\s+your)\b"
        rf"|已(?:经)?(?:被)?{zh}"
    )
    return acted, stated


_SELF, _STATE = _patterns(f"{_VI_ACT}|{_VI_MEMORY}", f"{_ZH_ACT}|{_ZH_MEMORY}")
_SELF_ACT, _STATE_ACT = _patterns(_VI_ACT, _ZH_ACT)  # when the turn kept a note, remembering is not a claim


def _addressed(self_term: str | None, user_term: str | None, remembered: bool) -> tuple[re.Pattern[str], re.Pattern[str]]:
    """The claim patterns with the learner's address added to the defaults. Built per call, never cached: the terms
    may carry the learner's name and belong to this turn only (contract v5 §5.6, §10)."""

    extra_self = (self_term,) if self_term else ()
    extra_user = (user_term,) if user_term else ()
    vi_done, zh_done = (_VI_ACT, _ZH_ACT) if remembered else (f"{_VI_ACT}|{_VI_MEMORY}", f"{_ZH_ACT}|{_ZH_MEMORY}")
    return _patterns(vi_done, zh_done, _VI_SELF + extra_self, _VI_USER + extra_user, _ZH_SELF + extra_self,
                     _ZH_USER + extra_user)  # fmt: skip


def _claim_patterns(remembered: bool, address: object) -> tuple[re.Pattern[str], re.Pattern[str]]:
    self_term, user_term = getattr(address, "self_term", None), getattr(address, "user_term", None)
    if not getattr(address, "chosen", False) or not (self_term or user_term):
        return (_SELF_ACT, _STATE_ACT) if remembered else (_SELF, _STATE)
    return _addressed(self_term, user_term, remembered)

# A completion with no actor is false only when it is what the pending button would do: beside "Ôn từ đến
# hạn", "Từ 朋友 đã được lưu" is a state a tool read, not a claim (live run 2026-09-28).
_ACTION_VERBS: dict[str, tuple[str, str, str]] = {
    "save_word": ("lưu|thêm", "saved|added", "保存|添加|加入|收藏"),
    "add_word_to_collection": ("lưu|thêm", "saved|added", "保存|添加|加入|收藏"),
    "unsave_word": ("xóa|xoá|bỏ lưu", "removed|deleted", "删除|移除"),
    "navigate": ("mở|chuyển", "opened", "打开"),
    "start_review": ("bắt đầu|mở", "started|opened", "开始|打开"),
    "start_targeted_drill": ("bắt đầu|mở", "started|opened", "开始|打开"),
}


def _stated_for(action: str) -> re.Pattern[str] | None:
    verbs = _ACTION_VERBS.get(action)
    if verbs is None:
        return None
    vi, en, zh = verbs
    return re.compile(
        r"(?i)"
        rf"\bđã\s+được\s+(?:{vi})\b"
        rf"|\b(?:has|have|had)\s+been\s+(?:{en})\b"
        + (r"|\bis\s+now\s+(?:saved|in\s+your)\b" if "saved" in en else "")
        + rf"|已(?:经)?(?:被)?(?:{zh})"
    )


_STATED_FOR = {action: _stated_for(action) for action in _ACTION_VERBS}
_SENTENCE = re.compile(r"[^.!?。！？\n]+[.!?。！？]*\s*|\n+")
_BOUNDARY = re.compile(r"[.!?。！？]+[\"'”’)\]]*\s*|\n+")


def _question(sentence: str) -> bool:
    stripped = sentence.strip().rstrip("\"'”’)] ")
    return stripped.endswith(("?", "？")) or bool(re.search(r"(?i)\bchưa\s*[?？]?$", stripped))


def claims_acted(sentence: str, *, remembered: bool = False, address: object = None) -> bool:
    acted, _ = _claim_patterns(remembered, address)
    return not _question(sentence) and bool(acted.search(sentence))


def claims_done(sentence: str, *, remembered: bool = False, action: str | None = None, address: object = None) -> bool:
    """Either kind of claim, in a sentence that is not a question. With the pending button's `action`, a
    completion without an actor counts only when it is that button's own (an action with no verbs here: all).
    `address` is the turn's (§5.6): its terms name Orena and the learner too."""

    acted, stated = _claim_patterns(remembered, address)
    if action is not None and _STATED_FOR.get(action) is not None:
        stated = _STATED_FOR[action]
    return not _question(sentence) and bool(acted.search(sentence) or stated.search(sentence))


# The model never offers a button in its own words; the server does, once (human direction 2026-09-28: the
# live run showed "Bấm Ôn tập từ vựng…" with no button, and "nút bên dưới", "below", "下方的按钮"). Read in the
# support language only, so a target-language word ("click", "点击") being explained is never taken for one.
# A tapping verb alone is not an offer ("Nhấn mạnh vào thanh điệu", "Nhấn để xem thêm câu tiếp theo", "Press to
# continue", "tap water", "点击率"). After the verb and its small words (the/a/on, vào/cái/ngay…), what comes first
# must name a button - a label (a capital, a quote, markup), or "here"/"đây" -, or a button word (nút/button/按钮)
# must follow within a few words ("Tap the Save word button", "Bấm vào cái nút Lưu từ"). "vào để…" ("tap on it
# to…") points at the screen; a bare "để…"/"to…" does not (review 2026-09-28).
_OFFER_VERB = MappingProxyType(
    {
        "vi": re.compile(
            r"(?i)(?:^\W*(?:(?:bạn|em|anh|chị|cậu|cháu|con)\s+)?|\b(?:hãy|có thể|cứ|chỉ cần|vui lòng)\s+)"
            r"(?:bấm|nhấn|chạm|nhấp)(?=\s)"
        ),
        "en": re.compile(r"(?i)(?:^\W*(?:(?:you|just|simply|please)\s+)?|\b(?:can|just|please|simply)\s+)(?:tap|click|press)\b"),
        "zh-CN": re.compile(r"(?:^\W*|你可以|您可以|可以|请|直接|只要)(?:点击|点一下|轻点|点按|按一下)"),
    }
)
_OPENING_MARKS = "\"“«'*[`(「『"
_FILLERS = MappingProxyType({"vi": ("vào", "lên", "ngay", "luôn", "cái", "thử"), "en": ("on", "the", "a", "an", "that", "this")})
_POINTING = MappingProxyType({"vi": ("vào", "lên"), "en": ("on",)})  # "vào để…": tap on it, in order to…
_HERE = MappingProxyType({"vi": ("đây",), "en": ("here", "below")})
_BUTTON = MappingProxyType({"vi": ("nút",), "en": ("button", "buttons")})
_PURPOSE = MappingProxyType({"vi": "để", "en": "to"})
_WINDOW = 5  # how many words after the verb a button word may come
_ZH_BUTTON = re.compile(r"^\s*(?:[“「『\"]|.{0,6}?(?:按钮|按键|这里|下方|上方|下面|上面))")
_WORD = re.compile(r"\S+")


# The model never writes button syntax; an action is the server's (live run 2026-09-28: "[START_REVIEW
# scope=due]Ôn ngay[/START_REVIEW]"). A leftover tag is removed - bracketed upper-case tags and action/button
# markup - never the words around it.
_MARKUP = re.compile(r"\[/?[A-Z][A-Z0-9_]{2,}(?:[ =][^\]\n]*)?\]|(?i:</?(?:button|action|btn)\b[^>\n]*>)")


# Markdown in a segment (contract §5.1, LEX-006 reopened): the client renders a subset - headings, bold, italic,
# lists, `> ` quotes, inline code, http(s) links - so that subset is kept. What is not in it goes: a link to
# anything but the web (an app command, "[Open word](command:navigate?…)"), label and all - going somewhere is an
# action, never a link; and a rule. Run-together "•" separators become a list, one item a line. Line marks are read
# at the start of a line: the gate cuts at every line break, so a line's mark is at the start of what it is given.
_NON_WEB_LINK = re.compile(r"\[[^\]\n]*\]\((?!https?://)[^)\n]*\)")
_RULE = re.compile(r"(?m)^[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*$")
_BULLET = re.compile(r"[ \t]*•[ \t]*")


def _grouped(line: str) -> str:
    """"a • b • c" (or a "• a" line) as list items, one a line; any other line as it is."""

    if line.lstrip().startswith("•") or line.count("•") >= 2:
        items = [item.strip() for item in _BULLET.split(line) if item.strip()]
        return "\n".join(f"- {item}" for item in items)
    return line


def strip_markup(text: str) -> str:
    cleaned = _RULE.sub("", _NON_WEB_LINK.sub("", _MARKUP.sub("", text)))
    if "•" in cleaned:
        cleaned = "".join(_grouped(line[:-1]) + "\n" if line.endswith("\n") else _grouped(line)
                          for line in cleaned.splitlines(keepends=True))  # fmt: skip
    return re.sub(r"[ \t]{2,}", " ", cleaned) if cleaned != text else text


# A `reference` segment is plain text (§5.1): the target-language words to be heard, with no mark at all.
_PLAIN = (
    (re.compile(r"(?m)^[ \t]*#{1,6}[ \t]+"), ""),  # heading
    (re.compile(r"(?m)^[ \t]*>[ \t]?"), ""),  # quote
    (re.compile(r"(?m)^[ \t]*(?:[-*+•]|\d+\.)[ \t]+"), ""),  # list item
    (re.compile(r"\[([^\]\n]+)\]\([^)\s]+\)"), r"\1"),  # link: its words
    (re.compile(r"\*\*|__|`+"), ""),  # strong, code
    (re.compile(r"(?<=[^\s\d])\*|\*(?=[^\s\d])"), ""),  # emphasis ("是*热闹*的"; "3 * 4" keeps its star)
)


# A link not yet closed on its line: "[label" or "[label](payload". A full stop inside it ("command:navigate?
# {…vocabulary.word…}") is no sentence end - the link is cut only whole, so it can be judged whole.
_OPEN_LINK = re.compile(r"\[[^\]\n]*$|\[[^\]\n]*\]\([^)\n]*$")


def _sentence_end(text: str) -> int | None:
    """Where the first whole sentence of `text` ends, never inside an open link; None while there is none."""

    for found in _BOUNDARY.finditer(text):
        if not _OPEN_LINK.search(text[: found.start()]):
            return found.end()
    return None


def plain_text(text: str) -> str:
    for pattern, replacement in _PLAIN:
        text = pattern.sub(replacement, text)
    return _RULE.sub("", text).strip()


def _bare(word: str) -> str:
    return word.strip(".,!?;:…").casefold()


def offers_a_button(sentence: str, support: str, *, interface: str | None = None) -> bool:
    """Whether a sentence offers a button in the model's own words (then it is the server's to write) - in the
    support language or the interface one, where a button's label lives ("Tap Open word", LEX-006). Never in a
    third language: an English example sentence for a learner of English is not an offer."""

    if _question(sentence):
        return False  # "Bạn đã bấm Lưu từ chưa?" asks; it offers nothing
    languages = dict.fromkeys(lang for lang in (support, interface) if lang)
    return any(_offers_in(sentence, lang) for lang in languages)


def _offers_in(sentence: str, support: str) -> bool:
    pattern = _OFFER_VERB.get(support, _OFFER_VERB["en"])
    lang = support if support in _FILLERS else "en"
    for found in pattern.finditer(sentence):
        rest = sentence[found.end():]
        if support == "zh-CN":
            if _ZH_BUTTON.match(rest):
                return True
            continue
        words = _WORD.findall(rest)
        if any(_bare(w) in _BUTTON[lang] for w in words[:_WINDOW]):
            return True  # "Tap the Save word button", "Bấm vào cái nút Lưu từ"
        index, pointed = 0, False
        while index < len(words) and _bare(words[index]) in _FILLERS[lang]:
            pointed = pointed or _bare(words[index]) in _POINTING[lang]
            index += 1
        if index == len(words):
            continue
        first = words[index]
        if first[0] in _OPENING_MARKS or first[0].isupper() or _bare(first) in _HERE[lang]:
            return True  # a label, or a place on the screen
        if pointed and _bare(first) == _PURPOSE[lang]:
            return True  # "Bấm vào để xem thêm"
    return False


def _sentences(text: str) -> list[str]:
    return _SENTENCE.findall(text)


def nothing_done(interface: str, support: str, address: object = None) -> str:
    return learner_copy.text("honesty.nothing_done", interface=interface, support=support, address=address)[1]


def offer(
    action_type: str,
    label: str,
    payload: Mapping[str, Any],
    *,
    interface: str,
    support: str,
    address: object = None,
) -> tuple[str, str]:
    """(language, sentence) offering this button, in the interface layer and - when that is the language of the
    learner's address - their address pair: "Bấm Lưu từ để thêm 我 vào từ vựng của bạn."."""

    key = f"offer.{action_type}"
    text = str(payload.get("text") or "")
    if key not in learner_copy.CATALOG or ("{text}" in learner_copy.CATALOG[key].texts.get("en", "") and not text):
        key = "offer.action"
    return learner_copy.text(key, interface=interface, support=support, address=address, label=label, text=text)


def offer_for(action_type: str, label: str, payload: Mapping[str, Any], *, interface: str, support: str, **kw: Any) -> str:
    return offer(action_type, label, payload, interface=interface, support=support, **kw)[1]


def _join(before: str, addition: str) -> str:
    if not addition:
        return ""
    return addition if not before or before.endswith((" ", "\n")) else " " + addition


def offer_instead(
    text: str,
    offer_text: str | None,
    *,
    interface: str,
    support: str,
    pending: bool | None = None,
    remembered: bool = False,
    action: str | None = None,
    nothing: str | None = None,
    address: object = None,
) -> str:
    """The whole answer at once (an opening greeting): claims and the model's own offers out, the server's
    offer in when there is one. `pending` is whether a button is proposed (the offer may be sent apart)."""

    pending = offer_text is not None if pending is None else pending

    def drop(part: str) -> bool:
        if offers_a_button(part, support, interface=interface):
            return True
        if pending:
            return claims_done(part, remembered=remembered, action=action, address=address)
        return claims_acted(part, remembered=remembered, address=address)

    text = strip_markup(text)
    parts = _sentences(text)
    dropped = any(drop(part) for part in parts)
    kept = "".join(part for part in parts if not drop(part)).strip() if dropped else text.strip()
    if offer_text:
        return (kept + _join(kept, offer_text)).strip()
    if dropped and not kept and not pending:
        return nothing if nothing is not None else nothing_done(interface, support)
    return kept


# An offer of more (LEX-006 retest): "do you want more examples, or a review?" With something in view the answer is
# about that; optional depth is the learner's to ask for, so such an offer is dropped (agent/turn.py `focused`).
# A question that asks what the learner meant ("Bạn muốn hỏi nghĩa hay cách dùng?") offers nothing and stays.
_MORE = "thêm|ôn|luyện|tìm hiểu|ví dụ|giải thích|xem|học tiếp"
_OFFERS_MORE = MappingProxyType(
    {
        "vi": re.compile(
            rf"(?i)^\W*(?:\w+\s+)?có\s+muốn\b.*?(?:{_MORE}).*?\b(?:không|chứ)\b\W*$"
            r"|^\W*nếu\s+\w+(?:\s+\w+)?\s+muốn\b"
        ),
        "en": re.compile(
            r"(?i)^\W*(?:would you like|do you want|want)\b.*\?\W*$"
            r"|^\W*(?:if you(?:'d| would)? like|if you want|let me know if|feel free to ask)\b"
        ),
        "zh-CN": re.compile(
            r"^\W*(?:你|您)?(?:想|要|需要)(?:我)?(?:再|继续|多)?.{0,30}(?:吗|么)[？?]\W*$"
            r"|^\W*要不要.{0,30}[？?]\W*$|^\W*如果(?:你|您)(?:想|需要)"
        ),
    }
)


# The learner's own status - saved, in their list, due, to review (LEX-006 readiness check): a word read from their
# records leaked into an answer about its meaning here ("Từ này … đã lưu của bạn và đến hạn ôn tập đấy!"). A
# status keyword alone is no status statement - "复习 nghĩa là ôn tập" is a meaning - so it takes the learner too.
_STATUS = MappingProxyType(
    {
        "vi": (re.compile(r"(?i)đã lưu|đã được lưu|danh sách từ|từ vựng đã lưu|thư viện|đến hạn|ôn tập|lịch ôn"),
               re.compile(r"(?i)\b(?:của bạn|bạn đã|bạn có|bạn đang)\b")),
        "en": (re.compile(r"(?i)\b(?:saved|due|review|word ?list|your words|library)\b"),
               re.compile(r"(?i)\b(?:your|you've|you have|you're)\b")),
        "zh-CN": (re.compile(r"已保存|已收藏|收藏|生词本|到期|复习"), re.compile(r"你的|您的|你已|您已|你今天|你还")),
    }
)


# ... and about the word itself: "this word", or the word as selected. "Màn này giữ các từ bạn đã lưu" describes
# a screen, not the word's status.
_THIS_WORD = re.compile(r"(?i)\b(?:từ này|this word)\b|这个词|该词|此词")


def states_status(sentence: str, support: str, word: str | None = None) -> bool:
    """Whether a sentence tells the learner this word's status in their records (saved, due, to review)."""

    patterns = _STATUS.get(support)
    if not patterns:
        return False
    keyword, learner = patterns
    about_word = bool(_THIS_WORD.search(sentence)) or bool(word and word in sentence)
    return about_word and bool(keyword.search(sentence) and learner.search(sentence))


# A learner who asks for a heading ("tiêu đề", "heading", "标题") gets one: a first line the model wrote in bold
# alone becomes a "### " heading (LEX-006: bold on its own line is not a heading).
_ASKS_HEADING = re.compile(r"(?i)\b(?:tiêu đề|đề mục|heading|title)\b|标题")
_BOLD_LINE = re.compile(r"^[ \t]*\*\*([^*\n]+?)\*\*[ \t]*:?[ \t]*(\n?)$")


def asks_for_heading(message: str | None) -> bool:
    return bool(message) and bool(_ASKS_HEADING.search(message))


def offers_more(sentence: str, support: str) -> bool:
    """Whether a sentence offers the learner more (examples, a review, more explanation) they did not ask for."""

    pattern = _OFFERS_MORE.get(support)
    return bool(pattern and pattern.search(strip_markup(sentence).strip()))


class ClaimGate:
    """Streams an answer a sentence at a time, and holds it from its first possible claim or button offer on.

    Every chunk it lets out is final: the segment's text is exactly what was streamed
    (the stream's own invariant). At the turn's end the model's own button offers are
    dropped, and so are the held claims - with a pending button, both kinds; without one,
    only Orena's claims to have acted. Whatever else was held goes out as written, in
    order, then the server's one offer when there is a button. `hold_all` holds the
    whole answer (a turn that may be asked again, agent/notes.py).
    """

    def __init__(self, *, interface: str = "en", support: str = "en", hold_all: bool = False) -> None:
        self._interface, self._support = interface, support
        self.hold_all = hold_all
        self.address: object = None  # the turn's address (§5.6), set once the request is read
        self.drop_more_offers = False  # something is in view: no offer of more (LEX-006), set per turn
        self.drop_status = False  # ... and no saved/due/review status of the selected word unless asked
        self.status_word: str | None = None  # that word, as selected
        self.heading_asked = False  # the learner asked for a heading: a first bold-only line becomes one
        self._heading_done = False
        self._partial = ""
        self._held: list[str] = []
        self.sent: list[str] = []

    def feed(self, delta: str) -> list[str]:
        self._partial += delta
        out: list[str] = []
        while (end := _sentence_end(self._partial)) is not None:
            sentence, self._partial = self._partial[:end], self._partial[end:]
            sentence = self._headed(strip_markup(sentence))
            if not sentence.strip():
                continue
            if (
                self.hold_all
                or self._held
                or claims_done(sentence, address=self.address)
                or offers_a_button(sentence, self._support, interface=self._interface)
                or self._unasked(sentence)
            ):
                self._held.append(sentence)
            else:
                out.append(sentence)
        self.sent.extend(out)
        return out

    def _unasked(self, sentence: str) -> bool:
        """What the learner did not ask for while something is in view: an offer of more, their records' status."""

        return (self.drop_more_offers and offers_more(sentence, self._support)) or (
            self.drop_status and states_status(sentence, self._support, self.status_word)
        )

    def _headed(self, sentence: str) -> str:
        if self.heading_asked and not self._heading_done:
            if sentence.lstrip().startswith("#"):
                self._heading_done = True
            elif found := _BOLD_LINE.match(sentence):
                self._heading_done = True
                return f"### {found.group(1).strip()}\n"
        return sentence

    def discard(self) -> None:
        """Drops what is held and not yet sent (an answer that will be written again)."""

        self._held, self._partial = [], ""

    def finish(
        self,
        offer_text: str | None,
        *,
        pending: bool | None = None,
        remembered: bool = False,
        action: str | None = None,
        nothing: str | None = None,
        replace_with: str | None = None,
    ) -> list[str]:
        """The rest of the answer. `replace_with`: the whole held answer is set aside for this (nothing of it
        was sent)."""

        tail = self._held + ([strip_markup(self._partial)] if self._partial else [])
        self._held, self._partial = [], ""
        if replace_with is not None and not self.text:
            tail = [replace_with]
        else:  # an offer of more or a status line is not a claim: dropping it says nothing in its place
            tail = [part for part in tail if not self._unasked(part)]
        pending = offer_text is not None if pending is None else pending

        def drop(part: str) -> bool:
            if offers_a_button(part, self._support, interface=self._interface):
                return True
            if pending:
                return claims_done(part, remembered=remembered, action=action, address=self.address)
            return claims_acted(part, remembered=remembered, address=self.address)

        dropped = any(drop(part) for part in tail)
        kept = "".join(part for part in tail if not drop(part))
        if dropped and not self.text.strip():
            kept = kept.lstrip()  # a dropped sentence opened the answer: no stray space before the rest
        before = self.text + kept
        if offer_text is not None:
            addition = _join(before, offer_text)
        elif dropped and not before.strip() and not pending:
            addition = nothing if nothing is not None else nothing_done(self._interface, self._support, self.address)
        else:
            addition = ""
        chunk = kept + addition
        if chunk:
            self.sent.append(chunk)
            return [chunk]
        return []

    @property
    def text(self) -> str:
        return "".join(self.sent)
