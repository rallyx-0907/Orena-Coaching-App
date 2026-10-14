"""Coverage-based automatic level estimate for Reading (reading-level/3, D-199).

Deterministic, offline, no AI. The estimate asks one question of a text: against the
graded word lists, how much of it lies above each band? English is graded against the
CEFR-J Vocabulary Profile (A1-B2) and the Octanove C1/C2 profile; Chinese against the
HSK 3.0 word and character lists, after jieba segmentation. Both read the tables built by
`scripts/build_reading_level_tables.py`.

    band = the lowest band k such that the share of scored tokens ABOVE k is at most TAU

Names, numbers, acronyms and units never count (they are not what a learner must know).
Clause/sentence length is a secondary signal that can move the band by one. The result
carries its own `confidence` and `evidence` (coverage per band and the top words above
the band - never the text), so a reviewer can see why. A reviewer's `reviewed_level`
always wins downstream (D-196); nothing here reads it.

The thresholds are fitted on a small calibration set (tests/fixtures/level_gold, VOA Learning
English and provisional author labels) and are a starting point, not a measurement of
the population: `CALIBRATION` records what they were fitted on.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

EN_BANDS = ("A1", "A2", "B1", "B2", "C1", "C2")
ZH_BANDS = ("HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6")

# Fitted values (scripts/eval_reading_level.py --fit and D-199; fitted on PROVISIONAL labels). TAU is the share of scored tokens a
# text may keep above its band; the length terms move the band by at most one.
TAU = {"en": 0.10, "zh": 0.08}
LONG_SENTENCE = {"en": 20.0, "zh": 14.0}
SHORT_SENTENCE = {"en": 5.0, "zh": 0.0}
MIN_SCORED = 20

_ROOT = Path(__file__).resolve().parent / "languages"
_EN_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_SENTENCE_START = re.compile(r"(?:^|[.!?]+[\"')\]]*\s+|\n\s*)[\"'“‘(]*$")
_HAN = re.compile(r"[㐀-䶿一-鿿]")
_ZH_CLAUSE_END = re.compile(r"[。！？；，、：…]+[」』”）]*")
_ZH_SENTENCE_END = re.compile(r"[。！？；…]+[」』”）]*")
_EN_SENTENCE_END = re.compile(r"[.!?]+[\"')\]]*\s+|[.!?]+[\"')\]]*$")
# jieba.posseg flags that are names, numbers or non-words: they never count.
_ZH_SKIP_FLAGS = ("nr", "ns", "nt", "nz", "nrt", "nrfg", "m", "mq", "eng", "x", "w", "t", "q")

_CONTRACTION_STEMS = frozenset(
    "isn aren wasn weren don doesn didn won wouldn couldn shouldn hasn haven hadn ain mustn needn".split()
)
_IRREGULAR = {
    pair.split(":")[0]: pair.split(":")[1]
    for pair in """
    was:be were:be been:be am:be is:be are:be had:have has:have did:do done:do does:do went:go gone:go
    saw:see seen:see came:come took:take taken:take gave:give given:give made:make said:say told:tell
    got:get gotten:get found:find knew:know known:know thought:think brought:bring bought:buy caught:catch
    taught:teach left:leave felt:feel kept:keep held:hold stood:stand heard:hear met:meet ran:run began:begin
    begun:begin wrote:write written:write spoke:speak spoken:speak ate:eat eaten:eat drank:drink drunk:drink
    drove:drive driven:drive flew:fly flown:fly grew:grow grown:grow threw:throw thrown:throw wore:wear
    worn:wear broke:break broken:break chose:choose chosen:choose rose:rise risen:rise sat:sit slept:sleep
    sent:send spent:spend built:build lost:lose paid:pay sold:sell won:win lay:lie lain:lie sang:sing
    sung:sing swam:swim swum:swim fell:fall fallen:fall forgot:forget forgotten:forget hid:hide hidden:hide
    led:lead read:read understood:understand woke:wake woken:wake shook:shake shaken:shake stole:steal
    stolen:steal drew:draw drawn:draw bit:bite bitten:bite blew:blow blown:blow dug:dig fed:feed fought:fight
    hung:hang hurt:hurt lit:light meant:mean rode:ride ridden:ride rang:ring rung:ring sank:sink shot:shoot
    shut:shut sought:seek swept:sweep taught:teach tore:tear torn:tear wound:wind
    men:man women:woman children:child people:person feet:foot teeth:tooth mice:mouse geese:goose
    better:good best:good worse:bad worst:bad more:much most:much less:little least:little
    """.split()
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _en_ranks() -> dict[str, int]:
    ranks: dict[str, int] = {}
    for name in ("level_words_cefrj.json", "level_words_octanove_c1c2.json"):
        for level, words in _load(_ROOT / "english" / name)["levels"].items():
            rank = EN_BANDS.index(level)
            for word in words.split():
                ranks[word] = min(ranks.get(word, rank), rank)
    return ranks


@lru_cache(maxsize=1)
def _zh_tables() -> tuple[dict[str, int], dict[str, int]]:
    data = _load(_ROOT / "chinese" / "level_words_hsk30.json")
    words: dict[str, int] = {}
    chars: dict[str, int] = {}
    for level, text in data["words"].items():
        for word in text.split():
            words[word] = min(words.get(word, int(level) - 1), int(level) - 1)
    for level, text in data["chars"].items():
        for char in text:
            chars[char] = min(chars.get(char, int(level) - 1), int(level) - 1)
    return words, chars


def _en_candidates(word: str):
    yield word
    if word in _IRREGULAR:
        yield _IRREGULAR[word]
    for suffix, replacements in (
        ("ies", ("y",)), ("es", ("", "e")), ("s", ("",)), ("ied", ("y",)), ("ed", ("", "e")), ("d", ("",)),
        ("ing", ("", "e")), ("ier", ("y",)), ("iest", ("y",)), ("er", ("", "e")), ("est", ("", "e")),
        ("ily", ("y",)), ("ly", ("", "le")), ("ally", ("al", "")), ("ness", ("",)), ("ment", ("",)),
    ):
        if word.endswith(suffix) and len(word) - len(suffix) >= 2:
            stem = word[: -len(suffix)]
            for add in replacements:
                yield stem + add
            if suffix in {"ed", "ing", "er", "est"} and len(stem) >= 3 and stem[-1] == stem[-2]:
                yield stem[:-1]


def _en_rank(word: str) -> int | None:
    ranks = _en_ranks()
    for candidate in _en_candidates(word):
        if candidate in ranks:
            return ranks[candidate]
    return None


def en_tokens(text: str) -> list[tuple[str, bool]]:
    """(lower-case word, opens a sentence with a capital) for each word a level may count.

    Left out: a capitalised word that does not open a sentence (a name or title), an all-capitals
    word (an acronym), a word touching a digit (a unit or a code). A hyphenated compound counts as
    its parts; a contraction keeps its stem (1-2 letter fragments are dropped).
    """
    tokens: list[tuple[str, bool]] = []
    for match in _EN_WORD.finditer(text):
        token = match.group()
        before = text[: match.start()]
        if before[-1:].isdigit() or text[match.end() : match.end() + 1].isdigit():
            continue
        if len(token) > 1 and token.isupper():
            continue
        opens = bool(_SENTENCE_START.search(before))
        if token[0].isupper() and not opens:
            continue
        for part in token.split("-"):
            pieces = re.split(r"[’']", part)
            for piece in pieces:
                if piece and (len(pieces) == 1 or len(piece) > 2):
                    tokens.append((piece.lower(), opens and token[0].isupper()))
    return tokens


def _zh_clause_length(text: str) -> float:
    clauses = [c for c in _ZH_CLAUSE_END.split(text) if _HAN.search(c)]
    if not clauses:
        return 0.0
    return sum(len(_HAN.findall(c)) for c in clauses) / len(clauses)


def _sentence_length(text: str, language: str) -> float:
    if language == "zh":
        return _zh_clause_length(text)
    sentences = [s for s in _EN_SENTENCE_END.split(text) if s and s.strip()]
    words = len(_EN_WORD.findall(text))
    return words / len(sentences) if sentences else 0.0


@lru_cache(maxsize=256)
def _rank_counts_en(text: str) -> tuple[Counter, Counter]:
    """Counter of rank (0-5 known, 6 beyond the lists) and of the unlisted/high words."""
    ranks: Counter = Counter()
    words: Counter = Counter()
    for word, initial_cap in en_tokens(text):
        if word in _CONTRACTION_STEMS:
            ranks[0] += 1
            continue
        rank = _en_rank(word)
        if rank is None:
            if initial_cap:  # an unlisted capitalised word opening a sentence is more likely a name
                continue
            rank = 6
        ranks[rank] += 1
        if rank >= 2:
            words[(word, rank)] += 1
    return ranks, words


@lru_cache(maxsize=256)
def _rank_counts_zh(text: str) -> tuple[Counter, Counter]:
    import jieba.posseg as pseg  # lazy: the library loads its dictionary on first use

    words_table, chars_table = _zh_tables()
    ranks: Counter = Counter()
    words: Counter = Counter()
    for item in pseg.lcut(text):
        word, flag = item.word, item.flag
        if not _HAN.search(word) or flag.startswith(_ZH_SKIP_FLAGS):
            continue
        if word in words_table:
            rank = words_table[word]
        else:
            char_ranks = [chars_table.get(c, 6) for c in word if _HAN.match(c)]
            rank = max(char_ranks) if char_ranks else 6
        rank = 6 if rank > 5 else rank
        ranks[rank] += 1
        if rank >= 2:
            words[(word, rank)] += 1
    return ranks, words


def _band_for(above: list[float], tau: float) -> int:
    for k, share in enumerate(above):
        if share <= tau:
            return k
    return len(above) - 1


def estimate(text: str, language: str) -> dict[str, Any]:
    """Band index (0-5), confidence and evidence for a text, deterministic."""
    zh = language == "zh"
    bands = ZH_BANDS if zh else EN_BANDS
    counts, words = (_rank_counts_zh if zh else _rank_counts_en)(text)
    scored = sum(counts.values())
    total = scored or 1
    cumulative = [sum(counts[r] for r in range(k + 1)) / total for k in range(6)]
    above = [1.0 - c for c in cumulative]
    tau = TAU["zh" if zh else "en"]
    lexical = _band_for(above, tau) if scored else 0
    length = _sentence_length(text, language)
    key = "zh" if zh else "en"
    index = lexical
    if scored and length >= LONG_SENTENCE[key]:
        index = min(5, index + 1)
    elif scored and 0 < length <= SHORT_SENTENCE[key]:
        index = max(0, index - 1)
    # Confidence: how much was scored, discounted when a small change of the threshold moves the band.
    sample = min(1.0, scored / 300.0)
    spread = abs(_band_for(above, tau * 0.7) - _band_for(above, tau * 1.4)) if scored else 2
    confidence = round(sample * (1.0, 0.75, 0.5, 0.5, 0.5, 0.5)[min(spread, 5)], 3)
    top = [
        {"word": word, "band": bands[rank] if rank < 6 else "beyond", "count": count}
        for (word, rank), count in sorted(words.items(), key=lambda kv: (-kv[1], kv[0][0]))
        if rank > index
    ][:8]
    evidence = {
        "scored_tokens": scored,
        "coverage": {bands[k]: round(cumulative[k], 3) for k in range(6)},
        "beyond_lists": round(counts[6] / total, 3),
        "lexical_band": bands[lexical],
        "sentence_length": round(length, 1),
        "top_above_band": top,
    }
    return {"index": index, "confidence": confidence, "evidence": evidence}
