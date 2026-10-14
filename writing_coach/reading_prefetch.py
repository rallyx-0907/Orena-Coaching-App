"""Translate ahead when a Reading article opens (D-199, an amendment to D-195).

The first tap on a word the deterministic layers cannot answer waits for the `word_translation` router, which can
take longer than the tap's budget; the answer then only helps the *second* tap. When a learner opens a published
article this module has the server translate the article's hard words in the background, into the router's shared
result cache, so the first tap is a cache hit.

What it is, deliberately small:

- **Word only.** It sends exactly what a tap sends: one word, the two languages. Never a sentence, never the article.
- **Deterministic layers first.** A word the catalogue, CC-CEDICT (English support language) or a held translation
  already answers is skipped and never reaches AI (`ReadingLookupService.has_local_meaning`).
- **Bounded.** At most `MAX_WORDS_PER_ARTICLE` words per article, `WORKERS` calls at once, `MAX_QUEUED_ARTICLES` waiting
  jobs, and the router-side budget in `ai.router.tap` (a day's calls, and a pause after the pool reports itself
  unavailable). It uses its own budget, never a learner's brake and never a tap's gate.
- **Once per article.** An in-process marker (article, revision, languages) with a TTL stops a second learner's open
  from repeating the work; the router's cache (180 days) is what actually holds the answers. The marker is dropped
  when a batch is stopped early so a later open can finish it.
- **Never in the way.** `schedule()` only enqueues and returns; it never raises and never delays the article response.
- **Counts only.** Telemetry is the router's rollup counters (`prefetch_articles`, `prefetch_requested`,
  `prefetch_served`, `prefetch_skipped`, `prefetch_failed`); no word, no article id.

Which words: English words that are not on the common-word list, not a name (capitalised away from a sentence start),
not an acronym, not touching a digit, not a contraction or a hyphenated compound, and at least four letters; ordered
longer (rarer) first, then by order of appearance. Chinese words of two or more Han characters that the tagger marks
as a noun, verb, adjective or adverb, in order of appearance. The level estimator keeps no per-word difficulty, so
length and the common-word lists are the difficulty signal.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from writing_coach.reading_processing import _EN_COMMON, _EN_WORD, _FUNCTION_WORDS, _SENTENCE_START, _ZH_COMMON

_log = logging.getLogger("orena.prefetch")

MAX_WORDS_PER_ARTICLE = 40
WORKERS = 2
MAX_QUEUED_ARTICLES = 8
MARKER_TTL_SECONDS = 6 * 3600.0
_MARKERS_MAX = 2000
MIN_EN_LETTERS = 4
MAX_CONSECUTIVE_FAILURES = 3
# Only the start of a long article is planned: the words a learner meets first are the ones they tap first.
_PLAN_CHARS = 6000
_ZH_CHUNK = 400
_HAN_WORD = re.compile(r"^[㐀-䶿一-鿿]{2,}$")
_ZH_CONTENT_POS = frozenset({"noun", "verb", "adjective", "adverb"})
_SUPPORTED_SOURCES = ("en", "zh")


def _en_words(body: str) -> list[str]:
    seen: dict[str, tuple[int, str, bool]] = {}  # folded -> (first position, written form, has a lowercase form)
    for match in _EN_WORD.finditer(body):
        token = match.group()
        before = body[: match.start()]
        after = body[match.end() : match.end() + 1]
        if before[-1:].isdigit() or after.isdigit() or "'" in token or "’" in token or "-" in token:
            continue
        if len(token) < MIN_EN_LETTERS or (len(token) > 1 and token.isupper()):
            continue
        folded = token.casefold()
        if folded in _EN_COMMON or folded in _FUNCTION_WORDS:
            continue
        opens_sentence = bool(_SENTENCE_START.search(before))
        if token[0].isupper() and not opens_sentence:
            continue  # a name or a title
        held = seen.get(folded)
        lower = token == folded
        if held is None:
            seen[folded] = (match.start(), token, lower)
        elif lower and not held[2]:
            seen[folded] = (held[0], token, True)  # the form a learner meets mid-sentence is the one they will tap
    ordered = sorted(seen.values(), key=lambda item: item[0])
    # Rarer first: longer words, in three bands, each in order of appearance.
    ranked = sorted(ordered, key=lambda item: -(3 if len(item[1]) >= 8 else 2 if len(item[1]) >= 6 else 1))
    return [form for _, form, _ in ranked]


def _zh_tokens(chunk: str) -> list[dict[str, Any]]:
    from writing_coach.linguistic_annotation import annotate

    return annotate("zh", chunk, max_annotations=400)


def _zh_words(body: str) -> list[str]:
    words: list[str] = []
    seen: set[str] = set()
    chunks = [body[i : i + _ZH_CHUNK] for i in range(0, len(body), _ZH_CHUNK)]
    for chunk in chunks:
        try:
            tokens = _zh_tokens(chunk)
        except Exception:  # noqa: BLE001 - the tagger is an aid; a failure plans nothing more
            break
        for token in tokens:
            word = str(token.get("fragment") or "")
            if (
                word in seen
                or not _HAN_WORD.match(word)
                or token.get("pos") not in _ZH_CONTENT_POS
                or all(char in _ZH_COMMON for char in word)
            ):
                continue
            seen.add(word)
            words.append(word)
    return words


def plan_words(body: str, language: str, limit: int = MAX_WORDS_PER_ARTICLE) -> list[str]:
    """The words worth translating ahead for this article, at most `limit`, most useful first."""

    text = (body or "")[:_PLAN_CHARS]
    code = (language or "").split("-", 1)[0].casefold()
    if code == "en":
        words = _en_words(text)
    elif code == "zh":
        words = _zh_words(text)
    else:
        words = []
    return words[: max(0, int(limit))]


class Prefetcher:
    """Schedules and runs article prefetches. One per process; `schedule()` is the only thing a request calls."""

    def __init__(
        self,
        meaning: Callable[[str, str, str], str],
        *,
        enabled: Callable[[], bool],
        paused: Callable[[], bool],
        count: Callable[[str, int], None],
        clock: Callable[[], float] = time.monotonic,
        executor: ThreadPoolExecutor | None = None,
        planner: Callable[[str, str], list[str]] = plan_words,
    ) -> None:
        self._meaning = meaning
        self._enabled = enabled
        self._paused = paused
        self._count = count
        self._clock = clock
        self._planner = planner
        self._executor = executor or ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="reading-prefetch")
        self._lock = threading.Lock()
        self._markers: OrderedDict[tuple[str, str, str, str], float] = OrderedDict()
        self._queued = 0

    def _claim(self, marker: tuple[str, str, str, str]) -> str:
        """"ok" (claimed), "already" (done or running within the TTL) or "queue_full"."""

        now = self._clock()
        with self._lock:
            until = self._markers.get(marker)
            if until is not None and until > now:
                return "already"
            if self._queued >= MAX_QUEUED_ARTICLES:
                return "queue_full"
            self._markers[marker] = now + MARKER_TTL_SECONDS
            self._markers.move_to_end(marker)
            while len(self._markers) > _MARKERS_MAX:
                self._markers.popitem(last=False)
            self._queued += 1
            return "ok"

    def _release(self, marker: tuple[str, str, str, str], *, keep: bool) -> None:
        with self._lock:
            self._queued = max(0, self._queued - 1)
            if not keep:
                self._markers.pop(marker, None)

    def schedule(self, article_id: str, revision: Any, body: str, language: str, target: str) -> str:
        """Enqueue this article's prefetch and return at once: "scheduled", or why not. Never raises."""

        try:
            source = (language or "").split("-", 1)[0].casefold()
            target = (target or "").strip().casefold()
            if source not in _SUPPORTED_SOURCES or not target or target == source or not body:
                return "unsupported"
            if not self._enabled():
                return "disabled"
            if self._paused():
                return "paused"
            marker = (str(article_id), str(revision), source, target)
            claimed = self._claim(marker)
            if claimed != "ok":
                return claimed
            try:
                self._executor.submit(self._run, marker, body, source, target)
            except Exception:  # noqa: BLE001 - e.g. a pool shut down
                self._release(marker, keep=False)
                return "unavailable"
            return "scheduled"
        except Exception:  # noqa: BLE001 - opening an article never depends on this
            _log.warning("reading prefetch could not be scheduled")
            return "unavailable"

    def _run(self, marker: tuple[str, str, str, str], body: str, source: str, target: str) -> None:
        finished = True
        try:
            words = self._planner(body, source)
            self._count("prefetch_articles", 1)
            failures = 0
            for index, word in enumerate(words):
                if self._paused() or not self._enabled():
                    finished = False
                    self._count("prefetch_skipped", len(words) - index)
                    break
                outcome = self._meaning(word, source, target)
                if outcome in ("served", "empty", "failed", "stop"):
                    self._count("prefetch_requested", 1)
                rest = len(words) - index - 1
                if outcome == "served":
                    self._count("prefetch_served", 1)
                    failures = 0
                elif outcome in ("empty", "failed"):
                    self._count("prefetch_failed", 1)
                    failures += 1
                elif outcome == "stop":  # the provider side is unavailable, paused or over budget: ask nobody more
                    self._count("prefetch_failed", 1)
                    self._count("prefetch_skipped", rest)
                    finished = False
                    break
                else:  # deterministic, joined, cooldown, busy: this word needs nothing from us
                    self._count("prefetch_skipped", 1)
                    if outcome == "disabled":
                        self._count("prefetch_skipped", rest)
                        finished = False
                        break
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    self._count("prefetch_skipped", rest)
                    finished = False
                    break
        except Exception:  # noqa: BLE001 - a background job never raises into the pool
            finished = False
            _log.warning("reading prefetch stopped on an error")
        finally:
            self._release(marker, keep=finished)
