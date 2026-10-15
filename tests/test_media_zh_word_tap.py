"""The word a learner taps in a new Chinese import (Video PR-C, P1-5).

A new ZH item stores about 81% of its `words` as single characters, but the Listening player never reads
those for a tap: it draws one Han character per column and widens the tap with the local tagger over the
line's text (`widenHanTap`, #209). So grouping depends on the text being unspaced and the tagger's spans
indexing it exactly. `tests/fixtures/zh_trial_tap_lines.json` holds lines shaped like the trial's new
items; `scripts/test_orena_reader_tap_word.mjs` replays its spans through the real widening code.
"""
from __future__ import annotations

import json
from pathlib import Path

from writing_coach.linguistic_annotation import annotate

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "zh_trial_tap_lines.json").read_text(encoding="utf-8"))
LINES = FIXTURE["lines"]


def test_fixture_is_shaped_like_a_new_item():
    singles = sum(len(line["text"].replace(" ", "")) == len(line["words"]) for line in LINES)
    assert singles == len(LINES), "the stored word arrays are one entry per character"
    assert all(not line["text"].startswith(" ") and line["text"] == line["text"].strip() for line in LINES)


def test_the_fixture_spans_are_what_the_tagger_answers_now():
    for line in LINES:
        assert [[a["start"], a["end"]] for a in annotate("zh", line["text"])] == line["spans"]


def test_the_tagger_groups_an_unspaced_line_into_words():
    grouped = total = 0
    for line in LINES:
        text = line["text"]
        for start, end in line["spans"]:
            assert text[start:end].strip() == text[start:end] and end > start
        han = [(s, e) for s, e in line["spans"] if any("一" <= ch <= "鿿" for ch in text[s:e])]
        total += sum(e - s for s, e in han)
        grouped += sum(e - s for s, e in han if e - s > 1)
    assert grouped / total >= 0.6, (grouped, total)
    words = {line["text"][s:e] for line in LINES for s, e in line["spans"]}
    assert {"中国", "政策", "洗手", "肥皂", "我们", "市场", "神龙", "北京"} <= words
