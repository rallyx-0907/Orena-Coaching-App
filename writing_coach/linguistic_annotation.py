"""Deterministic word segmentation and part-of-speech tagging.

One implementation, shared by every surface that needs to know what the words in
a piece of text are: the Listening transcript, and the Writing/Review
parts-of-speech lens.

There used to be two. The transcript segmented and tagged locally with jieba and
NLTK, while `becoming_linguistics` asked a language model to do the same job for
2 800 output tokens an essay. The local tagger's label set is a superset of the
eleven labels that prompt asked for -- it also separates `proper_noun`,
`classifier`, `auxiliary` and `interjection`, which the prompt collapsed into
`other` -- so keeping the free one loses nothing and gains precision.

Everything here is a pure function of (language, text). Same input, same
annotations, no provider, no latency, no failure mode beyond the text itself.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import jieba.posseg as pseg
from nltk import pos_tag
from nltk.tokenize import TreebankWordTokenizer
from pypinyin import Style, lazy_pinyin

__all__ = [
    "ALLOWED_POS",
    "annotate",
    "chinese_pos",
    "english_pos",
]


# The full label set. A caller with a narrower vocabulary is responsible for its
# own mapping; nothing here widens or narrows to suit one screen.
ALLOWED_POS = frozenset(
    {
        "noun",
        "verb",
        "adjective",
        "adverb",
        "pronoun",
        "determiner",
        "preposition",
        "conjunction",
        "numeral",
        "particle",
        "auxiliary",
        "interjection",
        "classifier",
        "proper_noun",
        "other",
    }
)

DEFAULT_MAX_ANNOTATIONS = 160

_EN_TOKENIZER = TreebankWordTokenizer()

# Anything with no letter, digit or Han character in it is punctuation as far as
# a learner-facing lens is concerned.
_MEANINGFUL = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFFA-Za-z0-9]")


def english_pos(tag: str) -> str:
    """Map a Penn Treebank tag onto the product's label set."""
    if tag in {"NNP", "NNPS"}:
        return "proper_noun"
    if tag.startswith("NN"):
        return "noun"
    if tag.startswith("VB"):
        return "verb"
    if tag.startswith("JJ"):
        return "adjective"
    if tag.startswith("RB"):
        return "adverb"
    if tag in {"PRP", "PRP$", "WP", "WP$"}:
        return "pronoun"
    if tag in {"DT", "PDT", "WDT"}:
        return "determiner"
    if tag == "IN":
        return "preposition"
    if tag == "CC":
        return "conjunction"
    if tag == "CD":
        return "numeral"
    if tag == "UH":
        return "interjection"
    if tag == "TO":
        return "particle"
    if tag == "MD":
        return "auxiliary"
    return "other"


def chinese_pos(tag: str) -> str:
    """Map a jieba flag onto the product's label set."""
    if tag.startswith(("nr", "ns", "nt", "nz")):
        return "proper_noun"
    if tag.startswith("n"):
        return "noun"
    if tag.startswith("v"):
        return "verb"
    if tag.startswith("a"):
        return "adjective"
    if tag.startswith("d"):
        return "adverb"
    if tag.startswith("r"):
        return "pronoun"
    if tag.startswith("m"):
        return "numeral"
    if tag.startswith("q"):
        return "classifier"
    if tag.startswith("p"):
        return "preposition"
    if tag.startswith("c"):
        return "conjunction"
    if tag.startswith(("u", "y")):
        return "particle"
    if tag.startswith("e"):
        return "interjection"
    return "other"


def _english_lemma(word: str) -> str:
    lower = word.casefold()
    if lower.endswith("ies") and len(lower) > 3:
        return lower[:-3] + "y"
    if lower.endswith("s") and len(lower) > 3 and not lower.endswith("ss"):
        return lower[:-1]
    return lower


# Curly quotes the Treebank tokenizer does not split from a word ("“I" became one token, tagged as an
# adjective). Each is swapped for its straight form, one character for one, so the spans still index `source`.
_STRAIGHT_QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'"})


def _english_annotations(source: str, limit: int) -> list[dict[str, Any]]:
    plain = source.translate(_STRAIGHT_QUOTES)
    spans = list(_EN_TOKENIZER.span_tokenize(plain))[:limit]
    tokens = [plain[start:end] for start, end in spans]
    return [
        {
            "fragment": source[start:end],
            "start": start,
            "end": end,
            "pos": english_pos(tag),
            "pronunciation": "",
            "lemma": _english_lemma(token),
        }
        # tokens is built from spans, so the two are the same length by
        # construction; strict=True says so rather than trusting it.
        for (start, end), (token, tag) in zip(spans, pos_tag(tokens, lang="eng"), strict=True)
        if _MEANINGFUL.search(token)
    ]


def _chinese_annotations(source: str, limit: int) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    cursor = 0
    for item in pseg.cut(source):
        word = str(item.word)
        if not word or word.isspace() or not _MEANINGFUL.search(word):
            continue
        start = source.find(word, cursor)
        if start < 0:
            continue
        end = start + len(word)
        output.append(
            {
                "fragment": word,
                "start": start,
                "end": end,
                "pos": chinese_pos(str(item.flag)),
                "pronunciation": " ".join(lazy_pinyin(word, style=Style.TONE)),
                "lemma": word,
            }
        )
        cursor = end
        if len(output) == limit:
            break
    return output


@lru_cache(maxsize=512)
def _annotate_cached(language: str, source: str, limit: int) -> tuple[dict[str, Any], ...]:
    annotations = (
        _chinese_annotations(source, limit)
        if language == "zh"
        else _english_annotations(source, limit)
    )
    return tuple(annotations)


def annotate(
    language: str,
    text: str,
    *,
    max_annotations: int = DEFAULT_MAX_ANNOTATIONS,
) -> list[dict[str, Any]]:
    """Segment and tag `text`, in reading order, with literal offsets.

    Each annotation carries `fragment`, `start`, `end`, `pos`, `pronunciation`
    (contextual tone-mark pinyin for Chinese, empty for English) and `lemma`.
    Offsets index into `text` exactly, so a caller can slice the source with them
    and get the fragment back.
    """
    source = str(text or "")
    if not source.strip():
        return []
    code = str(language or "en").split("-", 1)[0].strip().casefold()
    limit = max(1, int(max_annotations))
    return [dict(item) for item in _annotate_cached(code, source, limit)]
