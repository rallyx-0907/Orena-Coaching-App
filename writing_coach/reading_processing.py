"""Deterministic stage of the Reading Content Engine - no AI, no network, no DB.

Everything a machine can decide by counting runs here, before a model is asked
anything: markup cleaning, URL canonicalization, the content fingerprint dedupe
is built on, language validation, the measurements a level estimate rests on,
and a first pass of learning-target candidates. A model is expensive,
non-deterministic and sometimes wrong; a word count is none of those. The
engine therefore treats this module's output as fact and lets the optional AI
stage refine only what genuinely needs judgement (topic, pedagogical value,
CEFR nuance, collocation quality).

Two honest limits, stated rather than hidden:

- The level estimate is a coarse readability band, not a CEFR assessment. It
  reports its own `confidence`, which falls for short texts, and an admin's
  `reviewed_level` always wins over it downstream. `estimated_level` is never
  overwritten once stored.
- `suggest_targets` ranks by frequency and form, not by meaning. It exists so
  an article arrives at review with something to react to; the AI stage and the
  admin are what make the final list good.

Both languages are first-class here. English counts words and Chinese counts
characters because that is what a word is in each writing system - not because
one is the default and the other an adapter.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Markup that is never article text, whatever it contains.
_DROPPED_ELEMENTS = frozenset(
    {
        # Executable or presentational, never prose.
        "script", "style", "noscript", "template", "svg",
        # Document metadata: `<title>` is the page's title, extracted by the
        # adapter as a title - it is not the article's first sentence.
        "head", "title",
        # Page chrome that surrounds an article without being one.
        "nav", "header", "footer", "aside", "form",
    }
)
# Elements whose end is a paragraph boundary rather than a space.
_BLOCK_ELEMENTS = frozenset(
    {
        "p", "div", "section", "article", "main", "br", "hr", "li", "ul", "ol", "tr", "td", "th",
        "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "figcaption", "table",
    }
)

# Query parameters that identify a campaign, not a document.
_TRACKING_PARAMS = frozenset(
    {
        "fbclid", "gclid", "dclid", "msclkid", "igshid", "mc_cid", "mc_eid", "spm", "ref",
        "ref_src", "ref_url", "source", "yclid", "_ga", "_gl", "vero_id", "wickedid",
    }
)
_TRACKING_PREFIXES = ("utm_", "pk_", "piwik_", "at_", "hsa_")
_ALLOWED_SCHEMES = frozenset({"http", "https"})

_CJK = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
_EN_SENTENCE_END = re.compile(r"[.!?]+[\"')\]]*\s+|[.!?]+[\"')\]]*$")
_ZH_SENTENCE_END = re.compile(r"[。！？；…]+[」』”）]*")
_EN_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_WHITESPACE = re.compile(r"[^\S\n]+")
_BLANK_LINES = re.compile(r"\n{3,}")

# Reading pace for a *learner*, not a native skimmer. Deliberately slower than
# the 240 wpm / 400 cpm figures quoted for native adults: the number drives the
# "reading_time" a learner sees before opening an article, and an optimistic
# estimate is a worse failure than a generous one.
EN_WORDS_PER_MINUTE = 180
ZH_CHARS_PER_MINUTE = 260

MIN_ARTICLE_WORDS = 60
MAX_ARTICLE_WORDS = 4000

EN_LEVEL_BANDS = ("A1", "A2", "B1", "B2", "C1", "C2")
ZH_LEVEL_BANDS = ("HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6")

# The English words a learner meets in week one. Used to *exclude* candidates,
# never to teach: a target drawn from this list would waste a review slot.
_EN_COMMON = frozenset(
    """
    a about after all also am an and any are as at back be because been before being but by call
    can come could day did do does down each even find first for from get give go good great had
    has have he her here him his how i if in into is it its just know like little long look made
    make man many may me more most much must my never new no not now of off old on one only or
    other our out over own people said same say see she should so some take than that the their
    them then there these they thing think this those time to too two up us use very want was way
    we well went were what when where which who will with work would year you your
    """.split()
)
# The Chinese characters that carry grammar rather than content.
_ZH_COMMON = frozenset("的了是在我有和就不人都一个上也很到说要去你会着没有看好这那他她们与及为以于")

# Particles that turn a plain verb into a phrasal verb.
_PARTICLES = frozenset(
    """
    about after along around away back by down for in into off on out over through
    together up upon with
    """.split()
)
# Words that are grammar on their own: never the verb half of a phrasal verb.
_FUNCTION_WORDS = frozenset(
    """
    a an and as at be been being but by for from he her here him his i if in into is it its
    me my no not of off on or our out over she so that the their them then there these they
    this those to too up us was we were what when where which who will with you your
    """.split()
)


class _TextExtractor(HTMLParser):
    """Markup in, plain text out - never markup out.

    The output of this class is what an admin reviews and what a learner
    eventually reads, and the learner surface renders it as text. Dropping
    every tag here (rather than sanitizing an allow-list of them) is what
    makes an injected `<img onerror=...>` in a fetched page a non-event: there
    is no path by which source markup reaches a page as markup.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._suppressed = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _DROPPED_ELEMENTS:
            self._suppressed += 1
        elif tag in _BLOCK_ELEMENTS:
            self._parts.append("\n\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _BLOCK_ELEMENTS:
            self._parts.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _DROPPED_ELEMENTS:
            self._suppressed = max(0, self._suppressed - 1)
        elif tag in _BLOCK_ELEMENTS:
            self._parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if not self._suppressed:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def clean_source_text(raw: str) -> str:
    """Plain article text from markup or from a paste, never markup."""
    if not raw:
        return ""
    extractor = _TextExtractor()
    extractor.feed(raw)
    extractor.close()
    text = unescape(extractor.text())
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = _WHITESPACE.sub(" ", text)
    lines = [line.strip() for line in text.split("\n")]
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def normalize_url(url: str) -> str:
    """One canonical spelling per document, so dedupe sees one URL.

    Returns `""` for anything this engine will not fetch - a non-http scheme
    (`javascript:`, `file:`, `data:`), a missing host, or a string that is not
    a URL at all. The caller treats the empty string as "not a usable URL"
    rather than fetching something it did not recognise.
    """
    candidate = (url or "").strip()
    if not candidate:
        return ""
    try:
        parts = urlsplit(candidate)
    except ValueError:
        return ""
    if parts.scheme.lower() not in _ALLOWED_SCHEMES or not parts.hostname:
        return ""
    scheme = parts.scheme.lower()
    host = parts.hostname.lower()
    if host.startswith("www."):
        host = host[4:]
    netloc = host
    if parts.port and not (
        (scheme == "http" and parts.port == 80) or (scheme == "https" and parts.port == 443)
    ):
        netloc = f"{host}:{parts.port}"
    query = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMS
        and not key.lower().startswith(_TRACKING_PREFIXES)
    )
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, urlencode(query), ""))


def content_fingerprint(text: str) -> str:
    """SHA-256 of the normalized text - the dedupe key, stable across reflow.

    Whitespace and Unicode form are normalized first so a source that
    re-wraps its paragraphs does not read as new content; anything that
    changes a character does.
    """
    normalized = " ".join(unicodedata.normalize("NFC", text or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def detect_language(text: str) -> tuple[str, float]:
    """`(language, confidence)`, or `("", 0.0)` when there is nothing to read.

    Deliberately narrow: this validates that a source produced one of Orena's
    two first-class languages. It is not a general language identifier, and it
    answers `""` rather than guessing - an unknown language is a review
    decision, not something to paper over with a default.
    """
    body = text or ""
    cjk = len(_CJK.findall(body))
    latin_words = _EN_WORD.findall(body)
    total = cjk + len(latin_words)
    if total < 3:
        return ("", 0.0)
    cjk_share = cjk / total
    if cjk_share >= 0.2:
        return ("zh", round(min(1.0, 0.5 + cjk_share / 2), 3))
    common_hits = sum(1 for word in latin_words if word.lower() in _EN_COMMON)
    common_share = common_hits / len(latin_words) if latin_words else 0.0
    if len(latin_words) < 3 or common_share < 0.08:
        return ("", 0.0)
    return ("en", round(min(1.0, 0.45 + common_share), 3))


@dataclass(frozen=True)
class TextAnalysis:
    language: str
    word_count: int
    sentence_count: int
    average_sentence_length: float
    long_word_ratio: float
    distinct_word_ratio: float
    reading_time_seconds: int
    estimated_level: str
    confidence: float


@dataclass(frozen=True)
class TargetSuggestion:
    text: str
    canonical_form: str
    target_type: str
    context: str
    estimated_level: str
    rank: int
    machine_suggested: bool = True


def _sentences(body: str, language: str) -> list[str]:
    text = (body or "").strip()
    if not text:
        return []
    if language == "zh":
        pieces = [piece.strip() for piece in _ZH_SENTENCE_END.split(text) if piece.strip()]
        return pieces or [text]
    pieces = [piece.strip() for piece in _EN_SENTENCE_END.split(text) if piece and piece.strip()]
    return pieces or [text]


def _zh_characters(body: str) -> list[str]:
    return _CJK.findall(body or "")


def analyze_article(body: str, language: str) -> TextAnalysis:
    """Counted facts plus a coarse level band, with the band's own confidence."""
    text = (body or "").strip()
    sentences = _sentences(text, language)
    if language == "zh":
        units = _zh_characters(text)
        word_count = len(units)
        long_ratio = 0.0
        per_minute = ZH_CHARS_PER_MINUTE
        bands = ZH_LEVEL_BANDS
    else:
        units = [word.lower() for word in _EN_WORD.findall(text)]
        word_count = len(units)
        long_ratio = (
            sum(1 for word in units if len(word) >= 8) / word_count if word_count else 0.0
        )
        per_minute = EN_WORDS_PER_MINUTE
        bands = EN_LEVEL_BANDS
    sentence_count = len(sentences)
    average = word_count / sentence_count if sentence_count else 0.0
    distinct_ratio = len(set(units)) / word_count if word_count else 0.0
    reading_time = int(round(word_count / per_minute * 60)) if word_count else 0

    # A two-signal band: how long the average sentence is, and how much of the
    # text is outside the words a beginner already has. Neither signal is
    # CEFR; together they order texts the way a teacher would skim them.
    if language == "zh":
        uncommon = (
            sum(1 for char in units if char not in _ZH_COMMON) / word_count if word_count else 0.0
        )
        score = min(average / 24.0, 1.0) * 0.5 + min(uncommon / 0.75, 1.0) * 0.5
    else:
        uncommon = (
            sum(1 for word in units if word not in _EN_COMMON) / word_count if word_count else 0.0
        )
        score = (
            min(average / 26.0, 1.0) * 0.4
            + min(uncommon / 0.72, 1.0) * 0.3
            + min(long_ratio / 0.22, 1.0) * 0.3
        )
    index = min(int(score * len(bands)), len(bands) - 1)

    # Confidence is about how much text the band was computed from, not about
    # how sure the heuristic feels. A three-word paste cannot support a level.
    confidence = round(min(1.0, word_count / 400.0) * 0.8 + (0.2 if sentence_count >= 5 else 0.0), 3)
    return TextAnalysis(
        language=language,
        word_count=word_count,
        sentence_count=sentence_count,
        average_sentence_length=round(average, 2),
        long_word_ratio=round(long_ratio, 3),
        distinct_word_ratio=round(distinct_ratio, 3),
        reading_time_seconds=reading_time,
        estimated_level=bands[index],
        confidence=confidence,
    )


def quality_issues(body: str, language: str) -> list[str]:
    """Machine-checkable reasons a text is not ready for review.

    Every issue is a fact about the text, never a judgement about its value -
    "is this worth publishing" belongs to the admin, and "is this the language
    it claims to be, and is there an article here at all" belongs here.
    """
    issues: list[str] = []
    analysis = analyze_article(body, language)
    if analysis.word_count < MIN_ARTICLE_WORDS:
        issues.append("too_short")
    if analysis.word_count > MAX_ARTICLE_WORDS:
        issues.append("too_long")
    detected, _ = detect_language(body)
    if detected and detected != language:
        issues.append("language_mismatch")
    elif not detected and analysis.word_count >= MIN_ARTICLE_WORDS:
        issues.append("language_unclear")
    sentences = _sentences(body, language)
    if len(sentences) >= 8:
        unique = len({sentence.strip().lower() for sentence in sentences})
        if unique / len(sentences) < 0.5:
            issues.append("repetitive")
    return issues


def _is_learnable_phrase(parts: list[str]) -> bool:
    """Whether a repeated word sequence is worth a review slot.

    A phrase made only of words the learner already has is usually noise
    ("in the", "of a") - with one important exception: a phrasal verb is
    *made* of common words, and "look after" or "carry out" is exactly the
    kind of thing a learner needs and a dictionary lookup of either word
    alone will not give them. So a two-word sequence survives when its second
    word is a particle and its first is not itself a function word.
    """
    if not parts or not all(parts):
        return False
    if any(word not in _EN_COMMON for word in parts):
        return True
    return len(parts) == 2 and parts[1] in _PARTICLES and parts[0] not in _FUNCTION_WORDS


def _context_for(sentences: list[str], needle: str) -> str:
    lowered = needle.lower()
    for sentence in sentences:
        if lowered in sentence.lower():
            return sentence if len(sentence) <= 300 else sentence[:297] + "…"
    return ""


def _en_candidates(body: str, sentences: list[str]) -> list[tuple[float, str, str, str]]:
    words = _EN_WORD.findall(body)
    lowered = [word.lower().strip("'’-") for word in words]
    counts = Counter(word for word in lowered if word and word not in _EN_COMMON and len(word) > 2)
    candidates: list[tuple[float, str, str, str]] = []

    # Repeated multi-word forms first: a phrase a writer used twice is more
    # likely to be worth learning than a long word used once.
    bigrams: Counter[str] = Counter()
    trigrams: Counter[str] = Counter()
    for index in range(len(lowered) - 1):
        first, second = lowered[index], lowered[index + 1]
        if not first or not second:
            continue
        bigrams[f"{first} {second}"] += 1
        if index < len(lowered) - 2 and lowered[index + 2]:
            trigrams[f"{first} {second} {lowered[index + 2]}"] += 1
    for phrase, count in list(trigrams.items()) + list(bigrams.items()):
        if count < 2 or not _is_learnable_phrase(phrase.split(" ")):
            continue
        parts = phrase.split(" ")
        kind = "phrasal_verb" if len(parts) == 2 and parts[1] in _PARTICLES else "phrase"
        candidates.append((count * 2.0 + len(parts), phrase, kind, phrase))
    for word, count in counts.items():
        if count < 1:
            continue
        weight = count + min(len(word), 12) / 6.0
        candidates.append((weight, word, "word", word))
    return candidates


def _zh_candidates(body: str, sentences: list[str]) -> list[tuple[float, str, str, str]]:
    text = "".join(_zh_characters(body))
    counts: Counter[str] = Counter()
    for size in (4, 3, 2):
        for index in range(len(text) - size + 1):
            piece = text[index : index + size]
            if all(char in _ZH_COMMON for char in piece):
                continue
            counts[piece] += 1
    candidates: list[tuple[float, str, str, str]] = []
    for piece, count in counts.items():
        if count < 2:
            continue
        # A longer repeated sequence beats the shorter ones inside it.
        candidates.append((count * 2.0 + len(piece) * 1.5, piece, "phrase" if len(piece) > 2 else "word", piece))
    return candidates


def suggest_targets(body: str, language: str, *, limit: int = 8) -> list[TargetSuggestion]:
    """Up to `limit` candidate learning targets, ranked, each with its sentence.

    Frequency and form only - this stage has no idea what a phrase *means*.
    Its job is to hand the review queue a starting list that is never empty
    for a real article and never full of words the learner already knows;
    `machine_suggested` marks every row so an admin's approval remains a
    separate, recorded fact.
    """
    text = (body or "").strip()
    if not text or limit <= 0:
        return []
    sentences = _sentences(text, language)
    raw = _zh_candidates(text, sentences) if language == "zh" else _en_candidates(text, sentences)
    if not raw:
        return []
    # Deterministic order: weight first, then the form itself, so two runs over
    # the same body always produce the same list in the same order.
    ordered = sorted(raw, key=lambda item: (-item[0], item[1]))
    chosen: list[TargetSuggestion] = []
    taken: set[str] = set()
    for _weight, form, kind, canonical in ordered:
        if len(chosen) >= limit:
            break
        if canonical in taken:
            continue
        # Skip a form already covered by a longer one that was chosen first.
        if any(canonical in existing and canonical != existing for existing in taken):
            continue
        context = _context_for(sentences, form)
        if not context:
            continue
        taken.add(canonical)
        chosen.append(
            TargetSuggestion(
                text=form,
                canonical_form=canonical,
                target_type=kind,
                context=context,
                estimated_level="",
                rank=len(chosen),
            )
        )
    return chosen
