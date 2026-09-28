"""An action is offered, never reported as done (human review of the live run, 2026-09-28).

An action is a button the learner taps; until then nothing has happened. The
model writes its answer and proposes the action in the same round, so it never
reads that the learner has not tapped yet - and the live run showed it writing
"Từ 我 đã được lưu" beside a "Lưu từ" button. The instruction says not to;
this is the guarantee. When a turn carries an action and its answer states a
completion, the sentences that state it are replaced by an offer of the button,
in the support language.

The patterns are for the three support languages and name the completion
verbs of the action allowlist (save, add, remove, open, start). A sentence that
only says what the button will do ("Bấm Lưu từ để lưu 我") is not a claim.
"""

from __future__ import annotations

import re

from writing_coach.agent import learner_copy

# Vietnamese: Orena's or the system's completion - passive ("đã được lưu"), "mình/Orena đã lưu", a sentence
# that opens "Đã lưu…", "lưu xong" - never the learner's own past ("các từ bạn đã lưu").
_VI_DONE = r"(?:lưu|thêm|xóa|xoá|bỏ lưu|mở|chuyển|bắt đầu)"
_CLAIMS = re.compile(
    r"(?im)"
    rf"\bđã\s+được\s+{_VI_DONE}"
    rf"|\b(?:mình|orena)\s+(?:vừa\s+)?(?:đã\s+)?{_VI_DONE}\s+(?:xong|rồi)"
    rf"|\b(?:mình|orena)\s+(?:vừa\s+)?đã\s+{_VI_DONE}"
    rf"|^\W*đã\s+{_VI_DONE}"
    r"|\b(?:lưu|thêm|xóa|xoá)\s+xong\b"
    r"|\b(?:has|have|had)\s+been\s+(?:saved|added|removed|deleted|opened|started)\b"
    r"|\bI(?:'ve|\s+have)?\s+(?:just\s+)?(?:saved|added|removed|deleted|opened|started)\b"
    r"|\bis\s+now\s+(?:saved|in\s+your)\b"
    r"|已(?:经)?(?:被|为你|帮你)?(?:保存|添加|加入|删除|移除|收藏|打开|开始)"
    r"|(?:保存|添加|收藏|删除)(?:好|成功)了"
)
_SENTENCE = re.compile(r"[^.!?。！？\n]+[.!?。！？]*\s*|\n+")


_BOUNDARY = re.compile(r"[.!?。！？]+[\"'”’)\]]*\s*|\n+")


def claims_done(text: str) -> bool:
    return bool(_CLAIMS.search(text))


class ClaimGate:
    """Streams an answer a sentence at a time, and holds it from its first completion claim on.

    Every chunk it lets out is final: the segment's text is exactly what was streamed
    (the stream's own invariant). At the turn's end, with an action proposed, the
    held claims are dropped and the button is offered instead; with none, the held
    text goes out as written, in order.
    """

    def __init__(self, *, passthrough: bool = False) -> None:
        # A client that declared no action can be offered none: nothing to hold, every delta goes out as it comes.
        self._passthrough = passthrough
        self._partial = ""
        self._held: list[str] = []
        self.sent: list[str] = []

    def feed(self, delta: str) -> list[str]:
        if self._passthrough:
            self.sent.append(delta)
            return [delta]
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
        if offer is not None and any(claims_done(part) for part in tail):
            kept = "".join(part for part in tail if not claims_done(part))
            before = "".join(self.sent) + kept
            chunk = kept + ("" if not before or before.endswith((" ", "\n")) else " ") + offer
        else:
            chunk = "".join(tail)
        if chunk:
            self.sent.append(chunk)
            return [chunk]
        return []

    @property
    def text(self) -> str:
        return "".join(self.sent)


def offer_instead(text: str, label: str, *, interface: str, support: str) -> str:
    """The answer without its completion claims, and the button offered by its label."""

    if not claims_done(text):
        return text
    kept = "".join(part for part in _SENTENCE.findall(text) if not claims_done(part)).strip()
    offer = learner_copy.text("offer.action", interface=interface, support=support, label=label)[1]
    return f"{kept} {offer}".strip() if kept else offer
