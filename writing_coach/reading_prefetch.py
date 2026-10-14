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
  Everything that reads a database (the capability's configuration, the learner's support language) runs on the worker,
  inside a copy of the request's context.
- **Gentle on the provider.** A pause of `PACE_SECONDS` follows every call that reached the provider, so a free tier's
  rate limit is not burned in a burst, and the router calls run on a private health tracker (see `ai.router.tap`).
- **Counts only.** Telemetry is the router's rollup counters (`prefetch_articles`, `prefetch_requested`,
  `prefetch_served`, `prefetch_skipped`, `prefetch_failed`); no word, no article id.

Which words: English words that are not on the common-word list, not a name (capitalised away from a sentence start),
not an acronym, not touching a digit, not a contraction or a hyphenated compound, and at least four letters. Chinese
words of two or more Han characters that the tagger marks as a noun, verb, adjective or adverb. Both are ordered by the
level estimator's own word lists (`reading_level.word_rank`: CEFR-J / Octanove, HSK 3.0), hardest first, then by length
and order of appearance; an A1 / HSK1 word is never planned.
"""

from __future__ import annotations

import contextvars
import logging
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from writing_coach.reading_level import _SENTENCE_START, word_rank
from writing_coach.reading_processing import _EN_COMMON, _EN_WORD, _FUNCTION_WORDS

_log = logging.getLogger("orena.prefetch")
# The server's root logger is at WARNING, so this logger speaks at INFO on its own handler (counts only, never a word):
# 'did it run?' needs an answer in the log. Installed by `install_log_handler()` at app start, not at import.
_log.propagate = False


def install_log_handler() -> None:
    if not _log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
        _log.addHandler(handler)
    _log.setLevel(logging.INFO)


# The hardest words only (D-199 word rank); fewer if fewer qualify. Sized for an unfunded OpenRouter free tier (about 50
# requests a day for the account, see `ai.router.tap.PREFETCH_DAILY_CALLS`); a funded account can raise it.
MAX_WORDS_PER_ARTICLE = 8
WORKERS = 2
MAX_QUEUED_ARTICLES = 8
MARKER_TTL_SECONDS = 6 * 3600.0
# A batch that stopped early (the pool was unavailable, three bad answers, over budget) is not retried for this long, so
# re-opening an article in a loop cannot drain the day's budget.
RETRY_AFTER_SECONDS = 600.0
# Opening the same article again within this long coalesces into the job already queued or just run.
_COALESCE_SECONDS = 30.0
# A pause after every call that reached the provider (per worker): a free tier is not burned in a burst.
PACE_SECONDS = 0.5
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
    ranked: list[tuple[int, int, int, str]] = []
    for position, form, _lower in ordered:
        rank = word_rank(form, "en")
        if rank == 0:
            continue  # A1: a learner of any level knows it
        ranked.append((-rank, -min(len(form), 12), position, form))
    ranked.sort()
    return [form for _, _, _, form in ranked]


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
            ):
                continue
            seen.add(word)
            words.append(word)
    ranked = sorted(
        ((-word_rank(word, "zh"), index, word) for index, word in enumerate(words)),
    )
    return [word for rank, _, word in ranked if rank != 0]  # HSK1 (rank 0) is never planned


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
        sleep: Callable[[float], None] = time.sleep,
        executor: ThreadPoolExecutor | None = None,
        planner: Callable[[str, str], list[str]] = plan_words,
    ) -> None:
        self._meaning = meaning
        self._enabled = enabled
        self._paused = paused
        self._count = count
        self._clock = clock
        self._sleep = sleep
        self._planner = planner
        self._executor = executor or ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="reading-prefetch")
        self._lock = threading.Lock()
        self._markers: OrderedDict[tuple[str, str, str, str], float] = OrderedDict()
        self._recent: OrderedDict[tuple[str, str, str], float] = OrderedDict()
        self._queued = 0

    def shutdown(self) -> None:
        """Stop taking work and drop what has not started (app shutdown); a running call finishes on its own."""

        self._executor.shutdown(wait=False, cancel_futures=True)

    def _mark(self, marker: tuple[str, str, str, str], seconds: float) -> None:
        with self._lock:
            self._markers[marker] = self._clock() + seconds
            self._markers.move_to_end(marker)
            while len(self._markers) > _MARKERS_MAX:
                self._markers.popitem(last=False)

    def schedule(
        self, article_id: str, revision: Any, body: str, language: str, target: str | Callable[[], str]
    ) -> str:
        """Enqueue this article's prefetch and return at once: "scheduled", or why not. Never raises, reads nothing
        from a database. `target` may be a callable (the learner's support language); it runs on the worker, inside
        a copy of this request's context."""

        try:
            source = (language or "").split("-", 1)[0].casefold()
            if source not in _SUPPORTED_SOURCES or not body:
                _log.info("reading prefetch not scheduled: unsupported language=%s", source or "-")
                return "unsupported"
            if self._paused():
                _log.info("reading prefetch not scheduled: paused language=%s", source)
                return "paused"
            key = (str(article_id), str(revision), source)
            now = self._clock()
            with self._lock:
                until = self._recent.get(key)
                if until is not None and until > now:
                    return "already"
                if self._queued >= MAX_QUEUED_ARTICLES:
                    _log.info("reading prefetch not scheduled: queue_full language=%s", source)
                    return "queue_full"
                self._recent[key] = now + _COALESCE_SECONDS
                self._recent.move_to_end(key)
                while len(self._recent) > _MARKERS_MAX:
                    self._recent.popitem(last=False)
                self._queued += 1
            context = contextvars.copy_context()
            try:
                self._executor.submit(context.run, self.run, article_id, revision, body, source, target)
            except Exception:  # noqa: BLE001 - e.g. a pool shut down
                with self._lock:
                    self._queued = max(0, self._queued - 1)
                    self._recent.pop(key, None)
                return "unavailable"
            _log.info("reading prefetch scheduled language=%s", source)
            return "scheduled"
        except Exception:  # noqa: BLE001 - opening an article never depends on this
            _log.warning("reading prefetch could not be scheduled")
            return "unavailable"

    def run(self, article_id: str, revision: Any, body: str, source: str, target: str | Callable[[], str]) -> str:
        """The job: resolve the support language, claim the article, translate its words one at a time. Returns what
        happened ("done", "stopped", "already", "disabled", "paused", "unsupported"); never raises."""

        tally = {"planned": 0, "requested": 0, "served": 0, "failed": 0, "skipped": 0}
        outcome = "stopped"
        try:
            outcome = self._run(article_id, revision, body, source, target, tally)
            return outcome
        except Exception:  # noqa: BLE001 - a background job never raises into the pool
            _log.warning("reading prefetch stopped on an error")
            return "stopped"
        finally:
            with self._lock:
                self._queued = max(0, self._queued - 1) if self._queued else 0
            # One line per job, counts only: no word, no article id. This is how an operator sees that it ran.
            _log.info(
                "reading prefetch %s language=%s planned=%d requested=%d served=%d failed=%d skipped=%d",
                outcome, source, tally["planned"], tally["requested"], tally["served"], tally["failed"],
                tally["skipped"],
            )

    def _run(
        self, article_id: str, revision: Any, body: str, source: str, target: str | Callable[[], str],
        tally: dict[str, int] | None = None,
    ) -> str:
        tally = tally if tally is not None else {}
        counted = self._count

        def count(name: str, amount: int) -> None:
            key = name.removeprefix("prefetch_")
            if key in ("requested", "served", "failed", "skipped"):
                tally[key] = tally.get(key, 0) + amount
            counted(name, amount)

        resolved = (target() if callable(target) else target) or ""
        target = str(resolved).strip().casefold()
        if not target or target == source:
            return "unsupported"
        if not self._enabled():
            return "disabled"
        if self._paused():
            return "paused"
        marker = (str(article_id), str(revision), source, target)
        now = self._clock()
        with self._lock:
            until = self._markers.get(marker)
            if until is not None and until > now:
                return "already"
        self._mark(marker, MARKER_TTL_SECONDS)
        words = self._planner(body, source)
        tally["planned"] = len(words)
        count("prefetch_articles", 1)
        failures = 0
        for index, word in enumerate(words):
            if self._paused() or not self._enabled():
                count("prefetch_skipped", len(words) - index)
                self._mark(marker, RETRY_AFTER_SECONDS)
                return "stopped"
            outcome = self._meaning(word, source, target)
            reached_provider = outcome in ("served", "empty", "failed", "stop")
            if reached_provider:
                count("prefetch_requested", 1)
            rest = len(words) - index - 1
            if outcome == "served":
                count("prefetch_served", 1)
                failures = 0
            elif outcome in ("empty", "failed"):
                count("prefetch_failed", 1)
                failures += 1
            elif outcome == "stop":  # the provider side is unavailable, paused or over budget: ask nobody more
                count("prefetch_failed", 1)
                count("prefetch_skipped", rest)
                self._mark(marker, RETRY_AFTER_SECONDS)
                return "stopped"
            else:  # deterministic, joined, cooldown, busy: this word needs nothing from us
                count("prefetch_skipped", 1)
                if outcome == "disabled":
                    count("prefetch_skipped", rest)
                    self._mark(marker, RETRY_AFTER_SECONDS)
                    return "stopped"
            if failures >= MAX_CONSECUTIVE_FAILURES:
                count("prefetch_skipped", rest)
                self._mark(marker, RETRY_AFTER_SECONDS)
                return "stopped"
            if reached_provider and rest:
                self._sleep(PACE_SECONDS)
        return "done"
