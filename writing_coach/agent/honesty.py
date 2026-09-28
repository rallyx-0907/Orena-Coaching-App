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


def _bare(word: str) -> str:
    return word.strip(".,!?;:…").casefold()


def offers_a_button(sentence: str, support: str) -> bool:
    """Whether a sentence offers a button in the model's own words (then it is the server's to write)."""

    if _question(sentence):
        return False  # "Bạn đã bấm Lưu từ chưa?" asks; it offers nothing
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
        if offers_a_button(part, support):
            return True
        if pending:
            return claims_done(part, remembered=remembered, action=action, address=address)
        return claims_acted(part, remembered=remembered, address=address)

    parts = _sentences(text)
    dropped = any(drop(part) for part in parts)
    kept = "".join(part for part in parts if not drop(part)).strip() if dropped else text.strip()
    if offer_text:
        return (kept + _join(kept, offer_text)).strip()
    if dropped and not kept and not pending:
        return nothing if nothing is not None else nothing_done(interface, support)
    return kept


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
        self._partial = ""
        self._held: list[str] = []
        self.sent: list[str] = []

    def feed(self, delta: str) -> list[str]:
        self._partial += delta
        out: list[str] = []
        while (end := _BOUNDARY.search(self._partial)) is not None:
            sentence, self._partial = self._partial[: end.end()], self._partial[end.end() :]
            if (
                self.hold_all
                or self._held
                or claims_done(sentence, address=self.address)
                or offers_a_button(sentence, self._support)
            ):
                self._held.append(sentence)
            else:
                out.append(sentence)
        self.sent.extend(out)
        return out

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

        tail = self._held + ([self._partial] if self._partial else [])
        self._held, self._partial = [], ""
        if replace_with is not None and not self.text:
            tail = [replace_with]
        pending = offer_text is not None if pending is None else pending

        def drop(part: str) -> bool:
            if offers_a_button(part, self._support):
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
