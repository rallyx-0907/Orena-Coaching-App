"""Non-LLM word/phrase lookup for Reading.

A learner tapping a word wants a fast, deterministic answer. The real order is:
the shared local tagger (class, reading), the vocabulary catalogue, the
dictionary senses (English: a monolingual API; Chinese: the vendored CC-CEDICT
pack), the local machine translation (only if the Reading engine is the free
local one), the `word_translation` seam (D-195: the AI Cost Router, bounded by
the tap budget, admitted through a bounded gate, the word only), and finally
"unavailable". Only that seam can be a language model, and only when the
operator has enabled the capability; Explain (`POST /api/dictionary/contextual`)
is the only way a sentence reaches AI, and it is a separate, explicit request.
"""

from __future__ import annotations

import contextvars
import hashlib
import logging
import re
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeout
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from writing_coach.core.support_languages import normalize_support_language
from writing_coach.languages.chinese import lexicon as chinese_lexicon
from writing_coach.languages.chinese import structural_particle
from writing_coach.gloss_guard import is_function_word, neighbours, pos_disagrees, withhold_reason
from writing_coach.languages.english.ipa import ipa_for as _local_english_ipa
from writing_coach.linguistic_annotation import annotate
from writing_coach.media_ingestion import primary_language
from writing_coach.persistence.vocabulary_repository import VocabularyContentUnavailable
from writing_coach.reading_cache_scope import learner_scope, scope_for
from writing_coach.reading_translation import (
    ReadingTranslationService,
    ReadingTranslationStatus,
    TextSegment,
)
from writing_coach.tap_sense import (
    canonical_pos,
    catalogue_tie_texts,
    catalogue_ties,
    definition_ties,
    definitions_by_pos,
    pick_catalogue_entry,
    pick_chinese_entry,
    sentence_around,
)
from writing_coach.vocabulary_library import normalize_vocabulary_word

_log = logging.getLogger("orena.lookup")
_MAX_DICTIONARY_DEFINITIONS = 3
_HAN = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
_LATIN = re.compile(r"[A-Za-zÀ-ɏ]")

# A basic tap answers within this budget (seconds) whatever its services do: the external dictionary is asked with a
# shorter timeout of its own, the local translator gets what is left, and a miss falls back to the deterministic answer.
TAP_BUDGET_SECONDS = 2.0
_MIN_TRANSLATION_WAIT = 0.25
# The word_translation seam always gets at least this long (D-200 amendment). The deterministic layers before it
# (the external dictionary, up to its own 1.0 s timeout, is the slow one) used to leave it 0.25-0.5 s of the 2.0 s
# budget, while a free model answers in 0.7-1.7 s: every rare word - the ones the dictionary cannot answer, and so the
# ones that reach the seam - timed out. Worst case for a tap that reaches the seam: ~1.0 s dictionary + 1.8 s here.
SEAM_MIN_WAIT_SECONDS = 1.8
# The local translator on the tap path is bounded three ways: the call itself is cut off at a short timeout (the
# provider's own 90 s stays for every other caller), at most _MT_SLOTS calls run at once with no queue behind them
# (a full house skips the translation and the raw definition stands), and a request already running for the same
# word is joined, not repeated. A failure is remembered briefly so repeated taps on a missing word cost nothing.
_MT_CALL_TIMEOUT = 1.5
_MT_SLOTS = 4
_MT_FAILURE_SECONDS = 60.0
_translation_pool = ThreadPoolExecutor(max_workers=_MT_SLOTS, thread_name_prefix="lookup-mt")
# The word_translation seam (D-195) is admitted through a gate, never a queue: at most _SEAM_SLOTS calls exist at once
# (running or waiting), a request that finds the gate full is a miss at once, a request already running for the same
# word is joined, a request that overruns the tap budget is cancelled if it never started, and a word whose call
# raised is not asked again for _SEAM_FAILURE_SECONDS.
_SEAM_SLOTS = 2
_SEAM_FAILURE_SECONDS = 60.0
_LOG_EVERY_SECONDS = 60.0
_seam_pool = ThreadPoolExecutor(max_workers=_SEAM_SLOTS, thread_name_prefix="lookup-seam")
_seam_slots = threading.BoundedSemaphore(_SEAM_SLOTS)
# The translate-ahead prefetch (D-199) has its own gate, so it can never take a tap's slot: its calls run on the
# prefetch scheduler's own worker threads, and a tap that meets one of them in flight joins it like any other call.
PREFETCH_SLOTS = 2
_prefetch_slots = threading.BoundedSemaphore(PREFETCH_SLOTS)
_seam_lock = threading.RLock()
_seam_inflight: dict[tuple[str, str, str], Future] = {}
_seam_failed: dict[tuple[str, str, str], float] = {}
_seam_clock = time.monotonic
_last_logged: dict[str, float] = {}
_mt_slots = threading.BoundedSemaphore(_MT_SLOTS)
_mt_lock = threading.Lock()
_mt_inflight: dict[tuple[str, str, str], Future] = {}
_mt_failed: dict[tuple[str, str, str], float] = {}


def _log_layer(layer: str, outcome: str, *, language: str, error: BaseException | None = None) -> None:
    """One warning per layer and outcome a minute, naming the layer, the language and the exception TYPE only:
    never the exception text, the word or the sentence (a provider error can echo what it was sent)."""

    key = f"{layer}:{outcome}"
    now = _seam_clock()
    with _seam_lock:
        if now - _last_logged.get(key, -_LOG_EVERY_SECONDS) < _LOG_EVERY_SECONDS:
            return
        _last_logged[key] = now
    _log.warning(
        "lookup layer=%s %s language=%s%s; treated as a miss", layer, outcome, language,
        f" error={type(error).__name__}" if error is not None else "",
    )


def lexical_language(selection: str, fallback: str) -> str:
    """The language a selection's words belong to, by script, whatever language the text around it is in.

    Any Han character -> Chinese (a Han word tapped in English text is looked up as Chinese, CC-CEDICT and the
    Chinese pipeline); otherwise Latin letters -> English (a Latin word tapped in Chinese text is English). A
    genuinely mixed selection ("AI技术", "Wi-Fi密码") is Chinese: its Han part is what needs the Chinese dictionary,
    and CC-CEDICT also holds such mixed entries. Any other script (Cyrillic, Hangul, kana, Arabic, digits only) has
    no local dictionary: the result is "" (unsupported), never the surrounding text's language."""
    if _HAN.search(selection or ""):
        return "zh"
    if _LATIN.search(selection or ""):
        return "en"
    return ""


# (selection, sentence, dictionary definitions, source language, support language) -> a short meaning, or None.
# The one place the `word_translation` capability plugs in (D-195).
WordTranslationSeam = Callable[[str, str, list[str], str, str], "str | None"]
# (selection, source language, support language) -> a short meaning, or None; raises when the provider side failed.
# The translate-ahead variant (D-199): the word only, no learner, no sentence.
WordTranslationPrefetchSeam = Callable[[str, str, str], "str | None"]
# (word, its sentence, the tied stored senses, source language, support language, whether the sentence is shared
# published content) -> the index of the sense the sentence means, or None. D-228: asked only on a tie.
SenseChoiceSeam = Callable[[str, str, list[str], str, str, bool], "int | None"]
# The sense choice waits at least this long (it is the last step; an overrun is a miss and the call still fills the
# router's cache for the next tap).
SENSE_MIN_WAIT_SECONDS = 1.5


class VocabularyLookup(Protocol):
    def find_entry(self, language_code: str, normalized_term: str) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class LookupMeaning:
    text: str
    source: str


@dataclass(frozen=True)
class LookupDefinition:
    part_of_speech: str
    definition: str


@dataclass(frozen=True)
class LookupResult:
    selected_text: str
    source_language: str
    target_language: str
    base_form: str
    part_of_speech: str
    pronunciation: str
    audio_url: str
    meanings: tuple[LookupMeaning, ...]
    definitions: tuple[LookupDefinition, ...]

    @property
    def available(self) -> bool:
        return bool(self.meanings or self.definitions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_text": self.selected_text,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "base_form": self.base_form,
            "part_of_speech": self.part_of_speech,
            "pronunciation": self.pronunciation,
            "audio_url": self.audio_url,
            "meanings": [{"text": item.text, "source": item.source} for item in self.meanings],
            "definitions": [
                {"part_of_speech": item.part_of_speech, "definition": item.definition}
                for item in self.definitions
            ],
            "available": self.available,
            "claim": "reading_lookup" if self.available else "reading_lookup_unavailable",
        }


def _find_selection(context: str, selection: str) -> re.Match[str] | None:
    """Where the tapped word stands in its sentence. A Latin word is matched on word boundaries, never inside a longer
    word ("the" in "other"); Chinese has no word boundary to respect."""

    pattern = re.escape(selection)
    if selection[:1].isalnum() and not _HAN.search(selection):
        pattern = rf"(?<!\w){pattern}(?!\w)"
    return re.search(pattern, context, flags=re.IGNORECASE)


def _local_token_facts(language: str, context: str, selection: str) -> dict[str, str]:
    """What the shared tagger knows about the selection where it stands.

    Tagged in its sentence rather than alone, because a word's class is a fact
    about its use. `lemma` is kept separately from `base_form`: the catalog
    fallback lookup wants a lemma in any language, while `base_form` is only
    ever surfaced from the tagger for Chinese (`ARCHITECTURE_INVARIANTS.md`).
    """

    found = _find_selection(context, selection)
    if found is None:
        return {"part_of_speech": "", "pronunciation": "", "base_form": "", "lemma": ""}
    start, end = found.span()
    tokens = [
        token
        for token in annotate(language, context)
        if token["start"] < end and token["end"] > start
    ]
    if not tokens:
        return {"part_of_speech": "", "pronunciation": "", "base_form": "", "lemma": ""}
    single = len(tokens) == 1 and tokens[0]["start"] == start and tokens[0]["end"] == end
    lemma = tokens[0]["lemma"] if single else ""
    return {
        "part_of_speech": tokens[0]["pos"] if single else "",
        "pronunciation": " ".join(
            part for part in (_selected_reading(token, start, end) for token in tokens) if part
        ),
        "base_form": lemma if single and language == "zh" else "",
        "lemma": lemma,
    }


def _gloss_withheld(language: str, context: str, selection: str, tagged_pos: str, lemma: str = "") -> str:
    """Why the headword gloss of `selection` must not be shown where it stands (`gloss_guard`), or ``""``.

    The function-word list needs no tagging; the neighbours (a phrasal verb's particle, a name's other words, a period
    word) come from the shared tagger on the sentence. A tagger that fails leaves only the list and the tagged class."""

    if not selection or len(selection.split()) != 1:
        return ""
    if is_function_word(language, selection):
        return "function_word"
    previous = following = None
    found = _find_selection(context, selection)
    if found is not None:
        try:
            previous, following = neighbours(annotate(language, context), found.start(), found.end())
        except Exception as exc:  # noqa: BLE001 - the guard is an aid; its absence never fails the tap
            _log_layer("tagger", "failed", language=language, error=exc)
    return withhold_reason(language, selection, tagged_pos, previous, following, lemma)


def _selected_reading(token: Mapping[str, Any], start: int, end: int) -> str:
    """The reading of the part of `token` the learner selected.

    A selection inside a longer word reads only its own characters (LEX-030: 科 in
    维基百科 is kē, not wéi jī bǎi kē). Chinese readings have one syllable per
    character, so the selected characters' syllables are taken by position; when
    the count does not line up, no reading is given rather than a wrong one.
    """
    reading = str(token.get("pronunciation") or "")
    t_start, t_end = int(token["start"]), int(token["end"])
    if not reading or (start <= t_start and t_end <= end):
        return reading
    syllables = reading.split()
    if len(syllables) != t_end - t_start:
        return ""
    return " ".join(syllables[max(start, t_start) - t_start : min(end, t_end) - t_start])


def _catalog_candidates(selection: str, lemma: str) -> list[str]:
    primary = normalize_vocabulary_word(selection)
    candidates = [primary] if primary else []
    secondary = normalize_vocabulary_word(lemma)
    if secondary and secondary != primary:
        candidates.append(secondary)
    return candidates


def _safe_find_entry(
    repository: VocabularyLookup, language: str, normalized_term: str
) -> dict[str, Any] | None:
    # Any failure of the catalogue is a miss: the dictionary and translation layers below can still answer.
    try:
        return repository.find_entry(language, normalized_term)
    except VocabularyContentUnavailable:
        return None
    except Exception as exc:  # noqa: BLE001
        _log_layer("catalogue", "failed", language=language, error=exc)
        return None


def _safe_find_entries(
    repository: VocabularyLookup, language: str, normalized_term: str
) -> list[dict[str, Any]]:
    """Every published sense of the term when the repository can list them, else the one `find_entry` gives."""

    finder = getattr(repository, "find_entries", None)
    if not callable(finder):
        one = _safe_find_entry(repository, language, normalized_term)
        return [one] if one is not None else []
    try:
        return [item for item in finder(language, normalized_term) if isinstance(item, dict)]
    except VocabularyContentUnavailable:
        return []
    except Exception as exc:  # noqa: BLE001
        _log_layer("catalogue", "failed", language=language, error=exc)
        return []


def _safe_chinese_senses(word: str, reading: str = "") -> tuple[str, ...]:
    """CC-CEDICT's senses for `word`: the entry that has the reading the tagger gave it in its sentence, else the
    first entry that has any sense."""

    try:
        entries = [entry for entry in chinese_lexicon.lookup(word) if chinese_lexicon.meaning_senses(entry)]
        picked = pick_chinese_entry(entries, reading)
        if picked is not None:
            return chinese_lexicon.meaning_senses(picked)
    except chinese_lexicon.LexiconUnavailable:
        return ()
    return ()


def _is_polyphone(char: str) -> bool:
    try:
        from pypinyin import Style, pinyin

        return len({r for group in pinyin(char, style=Style.TONE, heteronym=True) for r in group}) > 1
    except Exception:  # noqa: BLE001
        return False


def _chinese_reading(word: str) -> str:
    """Tone-marked pinyin of exactly `word`, from deterministic sources only: the vendored CC-CEDICT reading, else pypinyin.

    The pronunciation of a Chinese word does not depend on which layer gave its meaning (the sentence tagger, the
    catalogue, a translation or the `word_translation` seam), so it is filled here when none of them gave one."""
    if len(word) == 1 and _is_polyphone(word):
        # One character with several readings (了, 重, 行, 长, 还...) is read by its sentence; without the tagger's
        # contextual reading, no reading is shown rather than a confident, possibly wrong one.
        return ""
    try:
        reading = chinese_lexicon.reading(word)
    except chinese_lexicon.LexiconUnavailable:
        reading = ""
    if reading:
        return reading
    if not word or not all("\u4e00" <= char <= "\u9fff" for char in word):
        return ""
    try:
        from pypinyin import Style, lazy_pinyin

        return " ".join(lazy_pinyin(word, style=Style.TONE)).strip()
    except Exception:  # noqa: BLE001 - a reading is an aid; its absence never fails the tap
        return ""


def _reconciled_part_of_speech(tagged: str, definitions: list[LookupDefinition]) -> str:
    """The tagger's class for the word where it stands, unless the dictionary says the word is never that.

    The tagger reads the sentence; the dictionary knows which classes a word can have at all. A tagger label the
    dictionary does not list for the word is a tagger error - "lonely" tagged as an adverb in "I'm lonely",
    where the dictionary knows it only as an adjective (LEX-026) - and the dictionary's first class stands.
    With no dictionary classes, the tagger's answer stands."""

    listed = [item.part_of_speech.strip().casefold() for item in definitions if item.part_of_speech.strip()]
    if not listed or not tagged or tagged.casefold() in listed:
        return tagged
    return listed[0]


def _safe_english_dictionary(
    lookup: Callable[[str], dict[str, Any] | None], word: str
) -> dict[str, Any] | None:
    try:
        payload = lookup(word)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _start_local_translation(service, source, target, segments, text, scope) -> Future | None:
    """The in-flight local translation for this word (started if none), or None when it should not run now."""
    key = (source, target, " ".join(text.casefold().split()))
    with _mt_lock:
        if _mt_failed.get(key, 0.0) > time.monotonic():
            return None
        running = _mt_inflight.get(key)
        if running is not None:
            return running
        if not _mt_slots.acquire(blocking=False):
            return None  # every slot is busy: skip, the raw definition stands

        def job():
            try:
                result = service.translate(source, target, segments, scope=scope, provider_timeout=_MT_CALL_TIMEOUT)
                if result.status is not ReadingTranslationStatus.READY:
                    _mt_failed[key] = time.monotonic() + _MT_FAILURE_SECONDS
                return result
            except Exception:
                _mt_failed[key] = time.monotonic() + _MT_FAILURE_SECONDS
                raise
            finally:
                with _mt_lock:
                    _mt_inflight.pop(key, None)
                    _mt_slots.release()
                    if len(_mt_failed) > 2000:
                        _mt_failed.clear()

        try:
            future = _translation_pool.submit(job)
        except Exception:
            _mt_slots.release()
            return None
        _mt_inflight[key] = future
        return future


def _safe_machine_translation(
    service: ReadingTranslationService, source: str, target: str, text: str, wait: float | None = None,
    *, cached_only: bool = False,
) -> str | None:
    segments = [TextSegment("selection", text)]
    # A tap carries no verified source: the learner's own scope (it still reads the shared, published entries).
    # Resolved here, on the request's thread - the local-engine worker thread has no request identity.
    scope = learner_scope()
    try:
        # An existing cached translation is used whatever engine is configured now.
        reader = getattr(service, "cached", None)
        held = reader(source, target, segments, scope=scope) if reader else None
        if held is not None:
            return held.translations[0][1] if held.translations else None
        if cached_only:
            return None
        if getattr(service, "uses_ai", False) or getattr(service, "uses_paid_provider", False):
            # A word's meaning in its sentence is /word-detail's; a basic tap never creates a translation with the
            # AI platform or any paid service. Only the free local engine (Marian) may create one here.
            return None
        if wait is None:
            result = service.translate(source, target, segments, scope=scope)
        else:
            future = _start_local_translation(service, source, target, segments, text, scope)
            if future is None:
                return None
            result = future.result(timeout=wait)
    except (FutureTimeout, Exception):
        return None
    if result.status is not ReadingTranslationStatus.READY or not result.translations:
        return None
    return result.translations[0][1]


def sentence_key(sentence: str) -> str:
    return hashlib.sha256(" ".join(sentence.casefold().split()).encode("utf-8")).hexdigest()[:24]


def reset_seam_gate() -> None:
    """Forget in-flight calls and cool-downs and start a fresh gate (tests; a running call finishes harmlessly)."""

    global _seam_slots, _prefetch_slots
    with _seam_lock:
        _seam_slots = threading.BoundedSemaphore(_SEAM_SLOTS)
        _prefetch_slots = threading.BoundedSemaphore(PREFETCH_SLOTS)
        _seam_inflight.clear()
        _seam_failed.clear()
        _last_logged.clear()


def _seam_settle(key: tuple[str, str, str], finished: Future) -> None:
    """Once per call, as soon as it is over (from the worker's callback or the waiting tap, whichever is first): forget it
    as in flight, cool the word down if it raised, and give the gate slot back."""

    with _seam_lock:
        if getattr(finished, "_gate_settled", False) or not finished.done():
            return
        finished._gate_settled = True  # type: ignore[attr-defined]
        slots = getattr(finished, "_gate_slots", _seam_slots)
        if _seam_inflight.get(key) is finished:
            del _seam_inflight[key]
        # A translate-ahead failure is the background's own (it has its own pause and budget): it must never make a
        # learner's tap on the same word answer "nothing" instantly for a minute (D-200 amendment).
        background = getattr(finished, "_background", False)
        if not background and not finished.cancelled() and finished.exception() is not None:
            if len(_seam_failed) > 2000:
                _seam_failed.clear()
            _seam_failed[key] = _seam_clock() + _SEAM_FAILURE_SECONDS
    slots.release()


def _ask_word_translation(seam, selection, context, definitions, source, target, wait: float) -> str | None:
    """The `word_translation` seam behind its gate; every refusal, overrun and failure is a miss (None)."""

    key = (source, target, " ".join(selection.casefold().split()))
    return _ask_gated(key, seam, (selection, context, definitions, source, target), wait, "word_translation", source)


def _ask_gated(key, call, args, wait: float, layer: str, language: str):
    """One AI seam call behind the shared gate: bounded admission, joined when already running for the same key, a
    cool-down after a failure, never a queue. Every refusal, overrun and failure is a miss (None)."""

    with _seam_lock:
        if _seam_failed.get(key, 0.0) > _seam_clock():
            return None  # it raised a moment ago: not asked again yet
        future = _seam_inflight.get(key)
        if future is None:
            if not _seam_slots.acquire(blocking=False):
                return None  # the gate is full: a miss now, never a queue behind it
            ctx = contextvars.copy_context()  # the request's account rides along (cost, brake)
            try:
                future = _seam_pool.submit(ctx.run, call, *args)
            except Exception:  # noqa: BLE001 - e.g. a pool shut down
                _seam_slots.release()
                return None
            _seam_inflight[key] = future
            future._gate_slots = _seam_slots  # type: ignore[attr-defined]  (the gate this call was admitted by)

            def done(finished: Future, key=key) -> None:
                _seam_settle(key, finished)

            future.add_done_callback(done)
    try:
        answer = future.result(timeout=wait)
        _seam_settle(key, future)  # do not rely on the callback having run yet
        return answer
    except FutureTimeout:
        future.cancel()  # queued work never runs late; a running call finishes and fills the router's cache
        _log_layer(layer, "timed out", language=language)
    except Exception as exc:  # noqa: BLE001 - a failing fallback is a miss, never a blank sheet
        _seam_settle(key, future)
        _log_layer(layer, "failed", language=language, error=exc)
    return None


def _prefetch_word_translation(seam: WordTranslationPrefetchSeam, selection: str, source: str, target: str) -> str:
    """Ask the router for one word ahead of any tap, on the calling (scheduler) thread, and publish the call so a tap
    on the same word joins it instead of asking again. Returns the outcome: "served", "empty", "joined", "cooldown",
    "busy", "stop" (the provider side is unavailable: the caller stops its batch) or "failed". Never raises."""

    key = (source, target, " ".join(selection.casefold().split()))
    with _seam_lock:
        if _seam_failed.get(key, 0.0) > _seam_clock():
            return "cooldown"
        if key in _seam_inflight:
            return "joined"  # a tap (or another prefetch) is already asking
        slots = _prefetch_slots
        if not slots.acquire(blocking=False):
            return "busy"
        future: Future = Future()
        future.set_running_or_notify_cancel()  # running from the start: a tap's timeout can never cancel it
        future._gate_slots = slots  # type: ignore[attr-defined]
        future._background = True  # type: ignore[attr-defined]
        _seam_inflight[key] = future
    try:
        answer = seam(selection, source, target)
        future.set_result(answer)
    except BaseException as exc:  # noqa: BLE001 - published to the joined taps, classified below
        future.set_exception(exc)
        answer = None
        failure: BaseException | None = exc
    else:
        failure = None
    finally:
        _seam_settle(key, future)
    if failure is None:
        return "served" if answer and str(answer).strip() else "empty"
    from writing_coach.ai.router.tap import prefetch_should_stop  # local: the lookup module stays AI-free at import

    return "stop" if prefetch_should_stop(failure) else "failed"


class ReadingLookupService:
    """Dictionary-first, translation-last word/phrase lookup. AI only through the `word_translation` seam (D-195)."""

    def __init__(
        self,
        vocabulary_repository: VocabularyLookup | None,
        english_dictionary: Callable[[str], dict[str, Any] | None],
        translation_service: ReadingTranslationService,
        english_dictionary_cached: Callable[[str], dict[str, Any] | None] | None = None,
        *,
        budget_seconds: float | None = None,
        word_translation: WordTranslationSeam | None = None,
        word_translation_prefetch: WordTranslationPrefetchSeam | None = None,
        sense_choice: SenseChoiceSeam | None = None,
        sense_choice_enabled: Callable[[], bool] | None = None,
    ) -> None:
        self._sense_choice = sense_choice
        self._sense_choice_enabled = sense_choice_enabled
        self._word_translation = word_translation
        self._word_translation_prefetch = word_translation_prefetch
        self._english_dictionary_cached = english_dictionary_cached
        self._budget = budget_seconds
        self._vocabulary_repository = vocabulary_repository
        self._english_dictionary = english_dictionary
        self._translation_service = translation_service

    def has_local_meaning(self, selection: str, source: str, target: str) -> bool:
        """Whether a deterministic layer already gives `selection` a meaning in `target` - the catalogue, CC-CEDICT
        for an English support language, or a translation already held. Never the network, never a new translation,
        never AI: it decides whether a word is worth translating ahead (D-199). A function word has no headword gloss
        to show (`gloss_guard`) and is never worth a translation: it counts as answered."""

        if is_function_word(source, selection):
            return True
        if self._vocabulary_repository is not None:
            for normalized in _catalog_candidates(selection, ""):
                entry = _safe_find_entry(self._vocabulary_repository, source, normalized)
                if entry is None:
                    continue
                for item in entry.get("short_meanings") or []:
                    if (
                        isinstance(item, dict)
                        and str(item.get("language") or "").strip().casefold() == target
                        and str(item.get("text") or "").strip()
                    ):
                        return True
                break
        if source == "zh" and target == "en" and _safe_chinese_senses(selection):
            return True
        return _safe_machine_translation(self._translation_service, source, target, selection, None, cached_only=True) is not None

    def prefetch_meaning(self, selection: str, source: str, target: str) -> str:
        """Translate one word ahead of a tap (D-199): "deterministic" when a layer already answers it, "disabled" when
        no prefetch seam is wired, otherwise the outcome of `_prefetch_word_translation`."""

        if self._word_translation_prefetch is None or not selection or source == target:
            return "disabled"
        if self.has_local_meaning(selection, source, target):
            return "deterministic"
        return _prefetch_word_translation(self._word_translation_prefetch, selection, source, target)

    def _choose_among_ties(
        self, selection, context, source, target, part_of_speech, found, meanings, definitions, content_id, started,
    ):
        """D-228: the zero-cost rules tied between stored senses; ask the sense-choice seam once and apply its index.

        The model can only name one of the stored senses, so what is shown is always stored text. No tie, no sentence,
        a miss, a refusal or any failure leaves the neutral sense exactly as the zero-cost layers left it."""

        group: list[Any] = []
        texts: list[str] = []
        if meanings and meanings[0].source == "collection":
            group = catalogue_ties(found, part_of_speech, target)
            texts = catalogue_tie_texts(group, target) if group else []
        elif not meanings and target == "en":
            group = definition_ties(definitions, part_of_speech)
            texts = [str(item.definition).strip() for item in group]
        if not group:
            return meanings, definitions
        if self._sense_choice_enabled is not None and not self._sense_choice_enabled():
            return meanings, definitions  # off: no article read, no worker hop
        sentence = sentence_around(context, selection)
        if not sentence:
            return meanings, definitions
        try:
            shared = scope_for(content_id, [context]).shared
        except Exception:  # noqa: BLE001 - unverifiable content is the learner's own
            shared = False
        if not shared:
            return meanings, definitions  # a learner's own sentence reaches no AI (D-228)
        remaining = max(
            SENSE_MIN_WAIT_SECONDS,
            (self._budget if self._budget is not None else TAP_BUDGET_SECONDS) - (time.monotonic() - started),
        )
        key = ("sense", source, target, " ".join(selection.casefold().split()), sentence_key(sentence), shared)
        index = _ask_gated(
            key, self._sense_choice, (selection, sentence, texts, source, target, shared), remaining, "sense_choice",
            source,
        )
        if type(index) is not int or not 0 < index < len(group):
            return meanings, definitions  # no answer, or the neutral sense itself: nothing changes
        if meanings and meanings[0].source == "collection":
            return [LookupMeaning(texts[index], "collection"), *meanings[1:]], definitions
        chosen = group[index]
        return meanings, [chosen] + [item for item in definitions if item is not chosen]

    def lookup(
        self, text: str, context: str, source_language: str, target_language: str,
        content_id: str | None = None,
    ) -> LookupResult:
        started = time.monotonic()
        selection = text.strip()
        # The lexical language flows through every layer below: the tagger, the catalogue, the dictionary, the reading,
        # the translation cache key and the original definition. The text's own language only frames the sentence.
        surrounding = primary_language(source_language)
        source = lexical_language(selection, surrounding)
        target = normalize_support_language(target_language)
        if not source:
            # Neither Han nor Latin (Cyrillic, Hangul, kana, Arabic, digits only): no local dictionary exists for it, so
            # the answer is "unavailable" at once - no dictionary request, no translator, no AI.
            return LookupResult(
                selected_text=selection, source_language=surrounding, target_language=target, base_form="",
                part_of_speech="", pronunciation="", audio_url="", meanings=(), definitions=(),
            )

        try:
            local = _local_token_facts(source, context if source == surrounding else selection, selection)
        except Exception as exc:  # noqa: BLE001 - the tagger is an aid; the dictionary layers below do not depend on it
            _log_layer("tagger", "failed", language=source, error=exc)
            local = {"part_of_speech": "", "pronunciation": "", "base_form": "", "lemma": ""}
        part_of_speech = local["part_of_speech"]
        pronunciation = local["pronunciation"]
        base_form = local["base_form"]
        # PRE-202: a gloss of the headword is shown only where the headword's sense is the sentence's. For a function
        # word, a proper name or part of a phrasal verb / fixed phrase / period it cannot be confirmed: no layer below
        # offers a word-alone meaning, and the tap keeps its non-committal state (the learner can ask Orena).
        withheld = _gloss_withheld(
            source, context if source == surrounding else selection, selection, part_of_speech, local["lemma"]
        )
        # PRE-105: 底 read de by the shared tagger is the old written form of the particle 的, not "bottom" (the Chinese
        # adapter owns the rule and the gloss); it is a function word that is nonetheless glossed, and no pack or
        # dictionary sense of the lexical 底 may reach it.
        structural = source == "zh" and structural_particle.is_structural_reading(selection, pronunciation)
        if structural:
            withheld = ""
        audio_url = ""
        meanings: list[LookupMeaning] = []
        definitions: list[LookupDefinition] = []

        entry = None
        pack_class_differs = False
        tagged_pos = part_of_speech
        found: list[dict[str, Any]] = []
        if self._vocabulary_repository is not None and not structural:
            for normalized in _catalog_candidates(selection, local["lemma"]):
                # Zero-cost sense choice (refs #194): among the word's authored senses, the one with a meaning in the
                # support language and the class the word has in this sentence; never AI, never the network.
                found = _safe_find_entries(self._vocabulary_repository, source, normalized)
                entry = pick_catalogue_entry(found, part_of_speech, target)
                if entry is not None:
                    break
        if entry is not None:
            # A pack sense of another lexical class than the word has here is dropped later, once the dictionary has
            # confirmed a sense of the in-context class (a tagger error on a one-sense word must not empty the sheet).
            pack_class_differs = pos_disagrees(str(entry.get("part_of_speech") or ""), part_of_speech)
            for item in [] if withheld else entry.get("short_meanings") or []:
                if not isinstance(item, dict):
                    continue
                if str(item.get("language") or "").strip().casefold() != target:
                    continue
                value = str(item.get("text") or "").strip()
                if value:
                    meanings.append(LookupMeaning(value, "collection"))
                    break
            if not pronunciation:
                pronunciation = str(entry.get("phonetic") or "").strip()
            if not part_of_speech:
                part_of_speech = str(entry.get("part_of_speech") or "").strip()
            if not base_form:
                base_form = str(entry.get("term") or "").strip()

        if source == "zh" and selection:
            # The vendored CC-CEDICT pack: dictionary senses for a Chinese word
            # without a provider (AI cost reduction plan P1). English is its
            # own language, so for an English support language the first
            # senses are the meaning; any other language still goes to the
            # translation engine below, with these senses on the sheet.
            if structural:
                meaning, note = structural_particle.gloss(target)
                meanings.append(LookupMeaning(meaning, "dictionary"))
                definitions.append(LookupDefinition("", note))
                entry_senses: tuple[str, ...] = ()
            else:
                entry_senses = () if withheld else _safe_chinese_senses(selection, pronunciation)
            definitions.extend(
                LookupDefinition("", sense) for sense in entry_senses[:_MAX_DICTIONARY_DEFINITIONS]
            )
            if not meanings and target == "en" and entry_senses:
                meanings.append(LookupMeaning("; ".join(entry_senses[:_MAX_DICTIONARY_DEFINITIONS]), "dictionary"))
            if not base_form and entry_senses:
                base_form = selection
            if not pronunciation:
                pronunciation = _chinese_reading(selection)

        is_single_word = bool(selection) and len(selection.split()) == 1
        if source == "en" and is_single_word:
            # A meaning already in hand (catalogue / localization) is not held up by the network: the external
            # dictionary then only fills secondary data (reading, original definition) from what is already cached.
            ask = self._english_dictionary
            if meanings and self._english_dictionary_cached is not None:
                ask = self._english_dictionary_cached
            payload = _safe_english_dictionary(ask, selection)
            if payload is not None:
                for item in [] if withheld else (payload.get("definitions") or [])[:_MAX_DICTIONARY_DEFINITIONS]:
                    if not isinstance(item, dict):
                        continue
                    definition_text = str(item.get("definition") or "").strip()
                    if not definition_text:
                        continue
                    definitions.append(
                        LookupDefinition(str(item.get("part_of_speech") or "").strip(), definition_text)
                    )
                if not pronunciation:
                    pronunciation = str(payload.get("phonetic") or "").strip()
                if not audio_url:
                    audio_url = str(payload.get("audio") or "").strip()
                if pack_class_differs and meanings and meanings[0].source == "collection":
                    # The pack's only sense is of another class and the dictionary confirms a sense of the class the
                    # word has here: the pack gloss is not the sentence's, the dictionary's sense is shown instead.
                    wanted = canonical_pos(tagged_pos)
                    if any(canonical_pos(item.part_of_speech) == wanted for item in definitions):
                        meanings = []
                part_of_speech = _reconciled_part_of_speech(part_of_speech, definitions)
                # The dictionary's sense for the class the word has here comes first, so a plain "plan" in "we plan
                # to leave" is not shown as the architectural drawing (refs #194).
                definitions = definitions_by_pos(definitions, part_of_speech)
            if not pronunciation:
                # Catalogue, then the online dictionary, then local CMUdict (D-202): a free, offline reading
                # that is there when the dictionary timed out or has no phonetic for the word.
                pronunciation = _local_english_ipa(selection)
            if payload is not None and entry is None and not definitions and not pronunciation and part_of_speech != "proper_noun":
                # Nothing knows this word - no catalogue sense, a dictionary that answered with no entry, no pronunciation.
                # A dictionary that timed out or was offline says nothing about the word, so its tagger class stays. The
                # tagger still returns a class for any string (its fallback for an unseen word is a noun), but
                # that is a guess about spelling, not a fact about the word: show no class (PRE D6).
                part_of_speech = ""

        if not meanings and target != source and not withheld:
            wait = None
            if self._budget is not None:
                wait = max(_MIN_TRANSLATION_WAIT, self._budget - (time.monotonic() - started))
            translated = _safe_machine_translation(self._translation_service, source, target, selection, wait)
            if translated:
                meanings.append(LookupMeaning(translated, "machine_translation"))

        if not meanings and target != source and not withheld and self._word_translation is not None:
            # The `word_translation` seam (D-195, the AI Cost Router): last, after every deterministic layer missed.
            # `context` and `definitions` are offered to any implementation; the router's adapter sends the word only.
            remaining = max(
                SEAM_MIN_WAIT_SECONDS,
                (self._budget if self._budget is not None else TAP_BUDGET_SECONDS) - (time.monotonic() - started),
            )
            # Bounded by what is left of the tap budget: an overrun is a miss and never holds the tap.
            seamed = _ask_word_translation(
                self._word_translation, selection, context, [item.definition for item in definitions], source, target,
                remaining,
            )
            if seamed and str(seamed).strip():
                meanings.append(LookupMeaning(str(seamed).strip(), "word_translation"))

        if self._sense_choice is not None and source == surrounding and not withheld:
            # A withheld gloss has nothing to choose among: the (paid) sense-choice seam is never reached (D-228).
            meanings, definitions = self._choose_among_ties(
                selection, context, source, target, part_of_speech, found, meanings, definitions, content_id, started,
            )

        return LookupResult(
            selected_text=selection,
            source_language=source,
            target_language=target,
            base_form=base_form,
            part_of_speech=part_of_speech,
            pronunciation=pronunciation,
            audio_url=audio_url,
            meanings=tuple(meanings),
            definitions=tuple(definitions),
        )
