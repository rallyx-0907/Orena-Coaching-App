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
from writing_coach.linguistic_annotation import annotate
from writing_coach.media_ingestion import primary_language
from writing_coach.persistence.vocabulary_repository import VocabularyContentUnavailable
from writing_coach.reading_translation import (
    ReadingTranslationService,
    ReadingTranslationStatus,
    TextSegment,
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
# The one place the future `word_translation` capability plugs in; nothing is wired to it yet.
WordTranslationSeam = Callable[[str, str, list[str], str, str], "str | None"]


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


def _local_token_facts(language: str, context: str, selection: str) -> dict[str, str]:
    """What the shared tagger knows about the selection where it stands.

    Tagged in its sentence rather than alone, because a word's class is a fact
    about its use. `lemma` is kept separately from `base_form`: the catalog
    fallback lookup wants a lemma in any language, while `base_form` is only
    ever surfaced from the tagger for Chinese (`ARCHITECTURE_INVARIANTS.md`).
    """

    found = re.search(re.escape(selection), context, flags=re.IGNORECASE)
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


def _safe_chinese_senses(word: str) -> tuple[str, ...]:
    try:
        for entry in chinese_lexicon.lookup(word):
            senses = chinese_lexicon.meaning_senses(entry)
            if senses:
                return senses
    except chinese_lexicon.LexiconUnavailable:
        return ()
    return ()


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


def _start_local_translation(service, source, target, segments, text) -> Future | None:
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
                result = service.translate(source, target, segments, provider_timeout=_MT_CALL_TIMEOUT)
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
    service: ReadingTranslationService, source: str, target: str, text: str, wait: float | None = None
) -> str | None:
    segments = [TextSegment("selection", text)]
    try:
        # An existing cached translation is used whatever engine is configured now.
        reader = getattr(service, "cached", None)
        held = reader(source, target, segments) if reader else None
        if held is not None:
            return held.translations[0][1] if held.translations else None
        if getattr(service, "uses_ai", False) or getattr(service, "uses_paid_provider", False):
            # A word's meaning in its sentence is /word-detail's; a basic tap never creates a translation with the
            # AI platform or any paid service. Only the free local engine (Marian) may create one here.
            return None
        if wait is None:
            result = service.translate(source, target, segments)
        else:
            future = _start_local_translation(service, source, target, segments, text)
            if future is None:
                return None
            result = future.result(timeout=wait)
    except (FutureTimeout, Exception):
        return None
    if result.status is not ReadingTranslationStatus.READY or not result.translations:
        return None
    return result.translations[0][1]


def reset_seam_gate() -> None:
    """Forget in-flight calls and cool-downs and start a fresh gate (tests; a running call finishes harmlessly)."""

    global _seam_slots
    with _seam_lock:
        _seam_slots = threading.BoundedSemaphore(_SEAM_SLOTS)
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
        if not finished.cancelled() and finished.exception() is not None:
            if len(_seam_failed) > 2000:
                _seam_failed.clear()
            _seam_failed[key] = _seam_clock() + _SEAM_FAILURE_SECONDS
    slots.release()


def _ask_word_translation(seam, selection, context, definitions, source, target, wait: float) -> str | None:
    """The `word_translation` seam behind its gate; every refusal, overrun and failure is a miss (None)."""

    key = (source, target, " ".join(selection.casefold().split()))
    with _seam_lock:
        if _seam_failed.get(key, 0.0) > _seam_clock():
            return None  # it raised a moment ago: not asked again yet
        future = _seam_inflight.get(key)
        if future is None:
            if not _seam_slots.acquire(blocking=False):
                return None  # the gate is full: a miss now, never a queue behind it
            ctx = contextvars.copy_context()  # the request's account rides along (cost, brake)
            try:
                future = _seam_pool.submit(ctx.run, seam, selection, context, definitions, source, target)
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
        _log_layer("word_translation", "timed out", language=source)
    except Exception as exc:  # noqa: BLE001 - a failing fallback is a miss, never a blank sheet
        _seam_settle(key, future)
        _log_layer("word_translation", "failed", language=source, error=exc)
    return None


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
    ) -> None:
        self._word_translation = word_translation
        self._english_dictionary_cached = english_dictionary_cached
        self._budget = budget_seconds
        self._vocabulary_repository = vocabulary_repository
        self._english_dictionary = english_dictionary
        self._translation_service = translation_service

    def lookup(
        self, text: str, context: str, source_language: str, target_language: str
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
        audio_url = ""
        meanings: list[LookupMeaning] = []
        definitions: list[LookupDefinition] = []

        entry = None
        if self._vocabulary_repository is not None:
            for normalized in _catalog_candidates(selection, local["lemma"]):
                entry = _safe_find_entry(self._vocabulary_repository, source, normalized)
                if entry is not None:
                    break
        if entry is not None:
            for item in entry.get("short_meanings") or []:
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
            entry_senses = _safe_chinese_senses(selection)
            definitions.extend(
                LookupDefinition("", sense) for sense in entry_senses[:_MAX_DICTIONARY_DEFINITIONS]
            )
            if not meanings and target == "en" and entry_senses:
                meanings.append(LookupMeaning("; ".join(entry_senses[:_MAX_DICTIONARY_DEFINITIONS]), "dictionary"))
            if not base_form and entry_senses:
                base_form = selection

        is_single_word = bool(selection) and len(selection.split()) == 1
        if source == "en" and is_single_word:
            # A meaning already in hand (catalogue / localization) is not held up by the network: the external
            # dictionary then only fills secondary data (reading, original definition) from what is already cached.
            ask = self._english_dictionary
            if meanings and self._english_dictionary_cached is not None:
                ask = self._english_dictionary_cached
            payload = _safe_english_dictionary(ask, selection)
            if payload is not None:
                for item in (payload.get("definitions") or [])[:_MAX_DICTIONARY_DEFINITIONS]:
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
                part_of_speech = _reconciled_part_of_speech(part_of_speech, definitions)

        if not meanings and target != source:
            wait = None
            if self._budget is not None:
                wait = max(_MIN_TRANSLATION_WAIT, self._budget - (time.monotonic() - started))
            translated = _safe_machine_translation(self._translation_service, source, target, selection, wait)
            if translated:
                meanings.append(LookupMeaning(translated, "machine_translation"))

        if not meanings and target != source and self._word_translation is not None:
            # The `word_translation` seam (D-195, the AI Cost Router): last, after every deterministic layer missed.
            # `context` and `definitions` are offered to any implementation; the router's adapter sends the word only.
            remaining = max(
                _MIN_TRANSLATION_WAIT, (self._budget if self._budget is not None else TAP_BUDGET_SECONDS) - (time.monotonic() - started)
            )
            # Bounded by what is left of the tap budget: an overrun is a miss and never holds the tap.
            seamed = _ask_word_translation(
                self._word_translation, selection, context, [item.definition for item in definitions], source, target,
                remaining,
            )
            if seamed and str(seamed).strip():
                meanings.append(LookupMeaning(str(seamed).strip(), "word_translation"))

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
