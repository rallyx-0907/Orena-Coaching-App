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
from typing import Any

from writing_coach.agent import learner_copy

_VI_DONE = r"(?:lưu|thêm|xóa|xoá|bỏ lưu|mở|chuyển|bắt đầu|ghi nhớ|ghi lại)"
_EN_DONE = r"(?:saved|added|removed|deleted|opened|started)"
_ZH_DONE = r"(?:保存|添加|加入|删除|移除|收藏|打开|开始|记录|记下)"

# Orena (or an implied Orena: a sentence that opens with the verb) says it acted.
_SELF = re.compile(
    r"(?im)"
    rf"\b(?:mình|orena)\s+(?:vừa\s+|đã\s+|vừa\s+đã\s+)?{_VI_DONE}\b[^.!?\n]{{0,60}}?\b(?:rồi|xong)\b"
    rf"|\b(?:mình|orena)\s+(?:vừa\s+)?đã\s+{_VI_DONE}\b"
    rf"|\b(?:mình|orena)\s+vừa\s+{_VI_DONE}\b"
    rf"|\b(?:mình|orena)\s+(?:sẽ\s+)?{_VI_DONE}\b[^.!?\n]{{0,40}}?\bcho\s+bạn\b"
    rf"|^\W*đã\s+{_VI_DONE}\b"
    rf"|\b(?:lưu|thêm|xóa|xoá)\s+xong\b"
    rf"|\bI(?:'ve|\s+have)?\s+(?:just\s+)?{_EN_DONE}\b"
    rf"|^\W*(?:done[,!.]?\s*)?{_EN_DONE}\b"
    rf"|(?:我|已经)?(?:帮你|为你|给你){_ZH_DONE}(?:下来?|好)?了"
    rf"|(?:帮你|为你|给你){_ZH_DONE}好"
    rf"|(?:保存|添加|收藏|删除)(?:好|成功)了"
)
# A completion with no actor: false only beside a pending button.
_STATE = re.compile(
    r"(?i)"
    rf"\bđã\s+được\s+{_VI_DONE}\b"
    rf"|\b(?:has|have|had)\s+been\s+{_EN_DONE}\b"
    r"|\bis\s+now\s+(?:saved|in\s+your)\b"
    rf"|已(?:经)?(?:被)?{_ZH_DONE}"
)
_SENTENCE = re.compile(r"[^.!?。！？\n]+[.!?。！？]*\s*|\n+")
_BOUNDARY = re.compile(r"[.!?。！？]+[\"'”’)\]]*\s*|\n+")


def _question(sentence: str) -> bool:
    stripped = sentence.strip().rstrip("\"'”’)] ")
    return stripped.endswith(("?", "？")) or bool(re.search(r"(?i)\bchưa\s*[?？]?$", stripped))


def claims_acted(sentence: str) -> bool:
    return not _question(sentence) and bool(_SELF.search(sentence))


def claims_done(sentence: str) -> bool:
    """Either kind of claim, in a sentence that is not a question."""

    return not _question(sentence) and bool(_SELF.search(sentence) or _STATE.search(sentence))


def _sentences(text: str) -> list[str]:
    return _SENTENCE.findall(text)


def _nothing_done(interface: str, support: str) -> str:
    return learner_copy.text("honesty.nothing_done", interface=interface, support=support)[1]


def offer_for(action_type: str, label: str, payload: Mapping[str, Any], *, interface: str, support: str) -> str:
    """The sentence that offers this button, built from it: "Bấm Lưu từ để thêm 我 vào từ vựng của bạn."."""

    key = f"offer.{action_type}"
    text = str(payload.get("text") or "")
    if key not in learner_copy.CATALOG or ("{text}" in learner_copy.CATALOG[key].texts.get("en", "") and not text):
        key = "offer.action"
    return learner_copy.text(key, interface=interface, support=support, label=label, text=text)[1]


def offer_instead(text: str, offer: str | None, *, interface: str, support: str) -> str:
    """The whole answer at once (an opening greeting): claims out, the button offered when there is one."""

    claim = claims_done if offer else claims_acted
    parts = _sentences(text)
    if not any(claim(part) for part in parts):
        return text
    kept = "".join(part for part in parts if not claim(part)).strip()
    if offer:
        return f"{kept} {offer}".strip() if kept else offer
    return kept or _nothing_done(interface, support)


class ClaimGate:
    """Streams an answer a sentence at a time, and holds it from its first possible claim on.

    Every chunk it lets out is final: the segment's text is exactly what was streamed
    (the stream's own invariant). At the turn's end the held claims are dropped - with
    a pending button, both kinds, and the button is offered; without one, only Orena's
    claims to have acted. Whatever else was held goes out as written, in order.
    """

    def __init__(self, *, interface: str = "en", support: str = "en") -> None:
        self._interface, self._support = interface, support
        self._partial = ""
        self._held: list[str] = []
        self.sent: list[str] = []

    def feed(self, delta: str) -> list[str]:
        self._partial += delta
        out: list[str] = []
        while (end := _BOUNDARY.search(self._partial)) is not None:
            sentence, self._partial = self._partial[: end.end()], self._partial[end.end() :]
            if self._held or claims_done(sentence):
                self._held.append(sentence)
            else:
                out.append(sentence)
        self.sent.extend(out)
        return out

    def finish(self, offer: str | None) -> list[str]:
        tail = self._held + ([self._partial] if self._partial else [])
        self._held, self._partial = [], ""
        claim = claims_done if offer is not None else claims_acted
        if any(claim(part) for part in tail):
            kept = "".join(part for part in tail if not claim(part))
            if not self.text.strip():
                kept = kept.lstrip()  # the claim opened the answer: no stray space or blank line before the rest
            before = "".join(self.sent) + kept
            addition = offer if offer is not None else ("" if before.strip() else self._nothing())
            joiner = "" if not addition or not before or before.endswith((" ", "\n")) else " "
            chunk = kept + joiner + addition
        else:
            chunk = "".join(tail)
        if offer is not None and not (self.text + chunk).strip():
            chunk = offer  # the model proposed the button and said nothing: the offer is the answer
        if chunk:
            self.sent.append(chunk)
            return [chunk]
        return []

    def _nothing(self) -> str:
        return _nothing_done(self._interface, self._support)

    @property
    def text(self) -> str:
        return "".join(self.sent)
