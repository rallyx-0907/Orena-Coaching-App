"""`/api/library/vocabulary/{word}/deep` — one word, opened all the way.

What the canonical Vocabulary frames "Vocabulary card deep", "Vocabulary card
deep scrolled" and "Vocabulary deep desktop" draw, and nothing else. Each
section of those frames has one source here, and a section whose source is
empty is **absent from the answer** rather than filled in: the room draws what
it is given, so an empty section simply is not drawn (rule 4's honesty, applied
to a list rather than a metric).

Where each section comes from:

- senses (NHIỀU NGHĨA · TỪ LOẠI), the gloss and the examples — the catalogue
  entry, deterministic, no provider;
- combinations (KẾT HỢP) and related expressions (CỤM LIÊN QUAN) — the
  catalogue itself: an entry that contains this word and is longer than it is
  a combination of it, and it is a word an admitted collection already carries
  rather than one a model offered;
- the mental model, the contrast and the common mistake — the explanation
  capability, asked once per (entry identity, reading, support language) and
  **cached in the asset store**, because a learner opening the same word twice
  must not wait for the model twice and must not be told two different things;
- where the learner met it (LẤY TỪ ĐÂU) — the provenance the saved word
  carries, which is what the app actually knows;
- the learner's own sentences (CÂU CỦA BẠN) — their essays that use the word.

The cache lives in a `BookAssetStore`, exactly as per-word audio does, so this
adds no table and no column: the key is a digest of what the explanation is an
explanation *of*, so a changed reading is a different cache entry and can never
be served for the wrong one.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from writing_coach import media_interaction
from writing_coach.becoming_library import (
    catalog_entry_for,
    catalog_neighbours,
    catalog_readings,
    entry_identity_for,
    saved_vocabulary_state,
)
from writing_coach.book_asset_store import AssetNotFound, BookAssetStore, InvalidAssetKey
from writing_coach.core.errors import orena_http_error
from writing_coach.core.request_context import current_language_code
from writing_coach.vocabulary_library import normalize_vocabulary_word

router = APIRouter(prefix="/api/library", tags=["vocabulary-deep"])

# How many of each list the frames draw. The frames are the reason for the
# numbers: four chips of combinations, three related rows, two sources, two of
# the learner's own sentences. Reading more than is drawn costs the learner
# time for nothing.
COMBINATIONS = 8
RELATED = 6
SOURCES = 6
LEARNER_SENTENCES = 4

_store: Callable[[], BookAssetStore | None] | None = None
_sentences: Callable[[str, str, int], list[dict[str, Any]]] | None = None


def configure_word_deep(
    *,
    store: Callable[[], BookAssetStore | None] | None = None,
    learner_sentences: Callable[[str, str, int], list[dict[str, Any]]] | None = None,
) -> None:
    """Where the explanation cache lives, and who can find the learner's own
    sentences. Both are optional: without a store the explanation is fetched
    each time, without a sentence reader that section is simply empty."""

    global _store, _sentences
    _store = store
    _sentences = learner_sentences


def _text(value: object) -> str:
    return str(value or "").strip()


def _first(values: object) -> str:
    if isinstance(values, str):
        return _text(values)
    if isinstance(values, Sequence):
        for value in values:
            if isinstance(value, Mapping):
                found = _text(value.get("text") or value.get("meaning") or value.get("definition"))
            else:
                found = _text(value)
            if found:
                return found
    return ""


def _meaning_texts(entry: Mapping[str, Any], field: str) -> list[str]:
    out: list[str] = []
    for value in entry.get(field) or ():
        text = _text(value.get("text") if isinstance(value, Mapping) else value)
        if text and text not in out:
            out.append(text)
    return out


def senses_of(entry: Mapping[str, Any]) -> list[dict[str, str]]:
    """NHIỀU NGHĨA · TỪ LOẠI: each sense with its part of speech and an example.

    A sense's part of speech is the entry's when the sense does not carry one
    of its own — a dictionary that names the part of speech once for a word
    with three senses is saying it applies to all three, not to none.
    """

    fallback_pos = _text(entry.get("part_of_speech"))
    examples = [
        _text(item.get("text") if isinstance(item, Mapping) else item)
        for item in entry.get("examples") or ()
    ]
    examples = [text for text in examples if text]
    senses: list[dict[str, str]] = []
    detailed = entry.get("detailed_definitions") or ()
    for index, item in enumerate(detailed):
        meaning = _text(item.get("text") if isinstance(item, Mapping) else item)
        if not meaning:
            continue
        pos = _text(item.get("part_of_speech") if isinstance(item, Mapping) else "") or fallback_pos
        example = _text(item.get("example") if isinstance(item, Mapping) else "")
        if not example and index < len(examples):
            example = examples[index]
        senses.append({"pos": pos, "meaning": meaning, "example": example})
    if senses:
        return senses
    # No detailed definitions: the short meanings are the senses the catalogue
    # has, and they share the entry's part of speech.
    return [
        {"pos": fallback_pos, "meaning": meaning, "example": examples[index] if index < len(examples) else ""}
        for index, meaning in enumerate(_meaning_texts(entry, "short_meanings"))
    ]


def _neighbour_rows(word: str, limit: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for entry in catalog_neighbours(word, limit=limit):
        term = _text(entry.get("term"))
        if not term:
            continue
        rows.append(
            {
                "term": term,
                "reading": _first(entry.get("readings")),
                "note": _first(entry.get("short_meanings")) or _first(entry.get("detailed_definitions")),
            }
        )
    return rows


def _sources_of(item: Mapping[str, Any]) -> list[dict[str, str]]:
    """LẤY TỪ ĐÂU: where the learner met this word.

    What the app knows is what was recorded when the word was kept: which
    capability the learner was in, and the fragment they were reading or
    hearing. That is one place, so the list has one row — an honest one,
    rather than a list padded to the length the frame's sample content has.
    """

    kind = _text(item.get("source_kind")) or "manual"
    fragment = _text(item.get("source_fragment"))
    if kind == "manual" and not fragment:
        return []
    return [
        {
            "kind": kind,
            "title": fragment,
            "at": "",
            "id": _text(item.get("source_essay_id")),
        }
    ]


def _learner_sentences(word: str, language: str) -> list[dict[str, str]]:
    if _sentences is None:
        return []
    try:
        rows = _sentences(word, language, LEARNER_SENTENCES)
    except Exception:
        # A learner's own sentences are a section of the screen, never the
        # screen: a failure here costs the section.
        return []
    out: list[dict[str, str]] = []
    for row in rows or ():
        text = _text(row.get("text"))
        if not text:
            continue
        out.append(
            {
                "text": text,
                "writtenOn": _text(row.get("written_on")),
                "checked": bool(row.get("checked")),
            }
        )
    return out[:LEARNER_SENTENCES]


def cache_key(identity_key: str, reading: str, support: str) -> str:
    """Which explanation this is an explanation of.

    Digest rather than the word itself, for the same reason per-word audio
    uses one: a key is a path segment, and a Chinese word is not. The reading
    is part of it, so 行 xíng and 行 háng can never share an explanation.
    """

    raw = "\x1f".join((identity_key, reading, support)).encode("utf-8")
    return f"word-deep/{hashlib.blake2s(raw, digest_size=20).hexdigest()}.json"


def _cached(key: str) -> dict[str, Any] | None:
    store = _store() if _store is not None else None
    if store is None:
        return None
    try:
        return json.loads(store.get(key).decode("utf-8"))
    except (AssetNotFound, InvalidAssetKey, KeyError, ValueError, UnicodeDecodeError, OSError):
        return None


def _remember(key: str, payload: Mapping[str, Any]) -> None:
    store = _store() if _store is not None else None
    if store is None:
        return
    try:
        store.put(key, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    except (InvalidAssetKey, OSError):
        # Not being able to remember an explanation is not a reason to withhold
        # it; the next open simply asks again.
        return


def explained(raw: Mapping[str, Any]) -> dict[str, Any]:
    """The explanation's deep layer, kept to the sections the frames draw."""

    return {
        "mentalModel": _text(raw.get("mental_model")) or _text(raw.get("core_idea")),
        "commonMistake": _text(raw.get("common_mistake")),
        "contrast": [
            {"term": _text(row.get("term")), "note": _text(row.get("note"))}
            for row in raw.get("contrast") or ()
            if _text(row.get("term"))
        ],
    }


def _deep_layer(*, word: str, context: str, language: str, support: str, identity: str, reading: str) -> dict[str, Any]:
    """The explained sections, from the cache when it has them."""

    key = cache_key(identity or word, reading, support) if (identity or word) else ""
    if key:
        remembered = _cached(key)
        if remembered is not None:
            return remembered
    if not context:
        # The explanation capability is contextual by contract: without a
        # sentence to explain the word in, it is not asked.
        return {}
    try:
        raw = media_interaction.explain_media_text(
            media_interaction.MediaExplainIn(
                text=word, context=context, source_language=language, target_language=support
            )
        )
    except HTTPException as error:
        if error.status_code in {502, 503}:
            return {}
        raise
    if not _text(raw.get("summary")):
        return {}
    layer = explained(raw)
    if key and any(layer.values()):
        _remember(key, layer)
    return layer


def project_word_deep(
    *,
    word: str,
    entry: Mapping[str, Any] | None,
    saved: Mapping[str, Any] | None,
    neighbours: Sequence[Mapping[str, Any]],
    layer: Mapping[str, Any],
    sentences: Sequence[Mapping[str, Any]],
    readings: Sequence[str],
    reading: str,
    parts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The whole screen, as a value. Pure, so the frames' contract is testable
    without a database, a provider or a store."""

    entry = entry or {}
    saved = saved or {}
    senses = senses_of(entry)
    orthography = entry.get("orthography") if isinstance(entry.get("orthography"), Mapping) else None
    if parts:
        # What a character is made of, from curated content with its own
        # provenance. The stroke capability refuses to infer this, so it is
        # carried beside what the entry already has rather than mixed into it.
        orthography = {**(orthography or {}), "parts": dict(parts)}
    gloss = " · ".join(_meaning_texts(entry, "short_meanings")[:3]) or _first(
        [sense["meaning"] for sense in senses]
    )
    combinations = [
        {"term": row["term"], "reading": row["reading"]}
        for row in neighbours[:COMBINATIONS]
    ]
    related = [row for row in neighbours[:RELATED] if row["note"]]
    usage = _meaning_texts(entry, "usage_notes")
    return {
        "headword": _text(entry.get("term")) or _text(word),
        "reading": _text(reading) or _first(entry.get("readings")) or _text(saved.get("phonetic")),
        "readings": list(readings),
        "script": "hanzi" if _text(entry.get("language_code") or "").startswith("zh") else "latin",
        "gloss": gloss,
        "senses": senses,
        "combinations": combinations,
        "related": related,
        # The catalogue's own usage note is the common mistake when it has one;
        # the explanation only answers where the catalogue is silent.
        "commonMistake": usage[0] if usage else _text(layer.get("commonMistake")),
        "mentalModel": _text(layer.get("mentalModel")),
        "contrast": list(layer.get("contrast") or ()),
        "sources": _sources_of(saved),
        "learnerSentences": list(sentences),
        "saved": bool(saved),
        "level": _text(entry.get("level")),
        "orthography": orthography,
    }


@router.get("/vocabulary/{word}/deep", name="orena_word_deep")
def word_deep(word: str, reading: str = Query("", max_length=240)) -> dict[str, Any]:
    """One word, opened all the way, for the deep frames."""

    term = _text(word)
    if not term:
        raise orena_http_error(422, "word_required", "Ask about a word.")
    language = current_language_code().strip().casefold()
    entry = catalog_entry_for(term)
    readings = catalog_readings(term)
    identity = entry_identity_for(term, reading)
    normalized = normalize_vocabulary_word(term) or term.casefold()
    try:
        saved = saved_vocabulary_state((term,)).get(normalized)
    except Exception:
        saved = None
    support = _support()
    context = ""
    for candidate in (entry or {}).get("examples") or ():
        context = _text(candidate.get("text") if isinstance(candidate, Mapping) else candidate)
        if context:
            break
    if not context and saved:
        context = _text(saved.get("source_fragment"))
    layer = _deep_layer(
        word=term,
        context=context,
        language=language,
        support=support,
        identity=identity["entry_identity_key"],
        reading=identity["reading_key"],
    )
    return project_word_deep(
        word=term,
        entry=entry,
        saved=saved,
        neighbours=_neighbour_rows(term, max(COMBINATIONS, RELATED)),
        layer=layer,
        sentences=_learner_sentences(term, language),
        readings=readings,
        reading=identity["reading_key"] or _text(reading),
        parts=_character_parts(term, support),
    )


def _character_parts(word: str, support: str) -> dict[str, Any]:
    """The radical and components of each character, when the content has them.

    Chinese only, because only Han script has them; everything else answers
    with nothing rather than an empty shape.
    """

    try:
        from writing_coach.languages.chinese import character_parts

        return character_parts.facts_for_word(word, support=(support or "en").split("-")[0])
    except Exception:
        return {}


def _support() -> str:
    """The learner's support language, read where every other surface reads it
    so the explanation arrives in the language the rest of the screen is in."""

    from writing_coach.becoming_memory import get_learner_profile

    try:
        return str(get_learner_profile().get("support_language") or "").strip().casefold()
    except Exception:
        return ""
