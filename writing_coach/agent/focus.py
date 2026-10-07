"""What "that", "it" and "the paragraph" refer to (ORENA_INTELLIGENCE_ARCHITECTURE §6).

A small, factual state beside the conversation: the active topic (the word, sentence or item the talk is about) and
its referents (the current word, the sentence it sits in, the content in view, a long text the learner pasted). It
is taken from what the runtime knows - a selection, a word a tool read, a word an action names, a message's length -
and never from parsing the learner's words: understanding "từ đó" or "đoạn thứ 3" is the model's, reading this state
with the recent turns. A turn that names nothing new leaves it as it was; a newer fact replaces the older one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

PASTE_MIN_CHARS = 1500  # a message this long is a pasted text, not a question
PASTE_HEAD_CHARS = 80
# Tools whose argument names the word the learner is asking about -> that argument ("words" is a list).
WORD_LOOKUP_ARGS: Mapping[str, str] = {"get_word_detail": "text", "get_saved_word_state": "words"}


@dataclass(frozen=True)
class Focus:
    topic: Mapping[str, Any] | None = None  # {"type": "word", "value": "mitigate", "lang": "en"}
    referents: Mapping[str, Any] = field(default_factory=dict)
    pasted: str | None = None  # the long text itself, kept for the turns after it (a session limit, like the rest)
    selection_key: str | None = None  # the last selection applied, so a selection that stays does not keep winning

    def to_context(self) -> dict[str, Any] | None:
        """The model's view: the topic and referents, and what a pasted text is (its text is sent apart)."""

        referents = dict(self.referents)
        if self.pasted:
            referents["pasted_text"] = {"chars": len(self.pasted), "starts": self.pasted[:PASTE_HEAD_CHARS]}
        if self.topic is None and not referents:
            return None
        return {"active_topic": dict(self.topic) if self.topic else None, "referents": referents}


def _with_word(focus: Focus, value: str, lang: str | None) -> Focus:
    topic = {"type": "word", "value": value, **({"lang": lang} if lang else {})}
    return replace(focus, topic=topic, referents={**focus.referents, "current_word": value})


def focus_after(
    prev: Focus,
    *,
    selected: Any = None,
    word: tuple[str, str | None] | None = None,
    ids: Mapping[str, str] | None = None,
    pasted: str | None = None,
    pasted_cap: int = 20_000,
) -> Focus:
    """`prev` as this turn's facts change it: the selection first, then the word the turn looked up or offered."""

    focus = prev
    if selected is not None:
        key = f"{selected.type}|{selected.id}|{selected.text}|{getattr(selected, 'sentence', None)}"
        if key != prev.selection_key:  # a selection that stays on screen does not keep taking the topic back
            focus = replace(focus, selection_key=key)
            sentence = getattr(selected, "sentence", None)
            if selected.type == "word" and selected.text:
                focus = _with_word(focus, selected.text, getattr(selected, "lang", None))
                if sentence:
                    focus = replace(focus, referents={**focus.referents, "current_sentence": sentence})
            elif selected.type == "sentence" and selected.text:
                focus = replace(focus, topic={"type": "sentence", "value": selected.text},
                                referents={**focus.referents, "current_sentence": selected.text})
            else:
                item = {k: v for k, v in (("id", selected.id), ("text", selected.text)) if v}
                focus = replace(focus, topic={"type": selected.type, **item},
                                referents={**focus.referents, "current_item": {"type": selected.type, **item}})
    if word is not None and word[0]:
        focus = _with_word(focus, word[0], word[1])
    if ids:
        focus = replace(focus, referents={**focus.referents, "in_view": dict(ids)})
    if pasted and len(pasted) >= PASTE_MIN_CHARS:
        focus = replace(focus, pasted=pasted[:pasted_cap])
    return focus
