"""`/api/library/vocabulary/{word}/audio` - how a saved word sounds.

Two routes: one that says whether there is a pronunciation for this word at
this reading and under what terms it may be played, and one that serves the
bytes. They add nothing to the Vocabulary or My Library contracts - no table,
no column, no change to what either of those answers - and a word with no
audio is simply one the first route answers `available: false` about.

Which reading is asked for is decided exactly where a saved word's link is
decided (`becoming_library.entry_identity_for`, D-074), so a word too ambiguous
to link is also too ambiguous to speak, and neither decision can drift from the
other.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any
import hashlib

from fastapi import APIRouter, Query, Response

from writing_coach.becoming_library import catalog_readings, entry_identity_for
from writing_coach.book_asset_store import AssetNotFound, InvalidAssetKey
from writing_coach.core.errors import orena_http_error
from writing_coach.word_audio import WordAudioLibrary

router = APIRouter(prefix="/api/library", tags=["vocabulary-audio"])

_library: Callable[[], WordAudioLibrary | None] | None = None


def configure_word_audio(factory: Callable[[], WordAudioLibrary | None] | None) -> None:
    global _library
    _library = factory


def _shelf() -> WordAudioLibrary:
    shelf = _library() if _library is not None else None
    if shelf is None:
        raise orena_http_error(
            503, "word_audio_unavailable", "Pronunciation storage is not configured."
        )
    return shelf


@router.get("/vocabulary/{word}/audio", name="orena_word_audio")
def word_audio(word: str, reading: str = Query("", max_length=240), lookup: bool = Query(False)) -> dict[str, Any]:
    """Is there a pronunciation of this word, at this reading, and whose is it?

    `reason` is a stable key a surface can say rather than guess at:
    `reading_ambiguous` (the entry has several readings and none was named),
    `no_entry` (the catalogue does not have this word, so there is no identity
    to key audio by) or `not_found` (nobody has a recording of it).
    """

    readings = catalog_readings(word)
    identity = entry_identity_for(word, reading)
    lookup_audio = lookup is True and not readings and not identity["entry_identity_key"]
    if lookup_audio:
        # A pronunciation cache key for an encountered term is not a catalogue
        # entry, a saved vocabulary identity or a learner-owned record.
        term = word.strip()
        language = _language()
        if not term or len(term) > 80 or not all(ch.isalpha() or ch in " '-" for ch in term):
            return {"available": False, "reason": "no_entry", "readings": []}
        if language == "zh" and not str(reading).strip():
            return {"available": False, "reason": "reading_ambiguous", "readings": []}
        digest = hashlib.sha256(f"{language}\0{term}\0{reading}".encode()).hexdigest()
        identity = {"entry_identity_key": f"encounter-audio:{digest}", "reading_key": str(reading).strip()}
    if not identity["entry_identity_key"]:
        # The same two cases the link decision has, told apart so the surface
        # can say which: a word the catalogue does not know, and a word it
        # knows too many readings of.
        reason = "reading_ambiguous" if len(readings) > 1 else "no_entry"
        return {"available": False, "reason": reason, "readings": readings}
    shelf = _shelf()  # one library for the request: its voices remember whether synthesis failed
    found = shelf.pronounce(
        identity_key=identity["entry_identity_key"],
        term=word,
        language=_language(),
        reading=identity["reading_key"],
        single_reading=(len(readings) <= 1) if not lookup_audio else _language() != "zh",
    )
    if found is None:
        # `synthesis_unavailable`: nobody recorded it and the synthesising voice failed, is offline or is at its
        # spend cap - the surface may then use the device's own voice and say so (LEX-010).
        reason = "synthesis_unavailable" if shelf.synthesis_failed() else "not_found"
        return {"available": False, "reason": reason, "readings": readings}
    payload = found.as_dict()
    # The key is what the second route serves; the surface builds its own URL
    # from it rather than being handed a provider's.
    payload["url"] = f"/api/library/audio/{found.key}"
    return {"available": True, **payload, "readings": readings}


@router.get("/audio/{key:path}", name="orena_word_audio_bytes")
def word_audio_bytes(key: str) -> Response:
    try:
        data = _shelf().audio_bytes(key)
    except (AssetNotFound, KeyError) as error:
        raise orena_http_error(404, "audio_missing", "No audio is stored under that key.") from error
    except InvalidAssetKey as error:
        raise orena_http_error(422, "audio_key_invalid", "That is not an audio key.") from error
    media = "audio/ogg"
    for extension, mime in (("mp3", "audio/mpeg"), ("wav", "audio/wav"), ("flac", "audio/flac"), ("m4a", "audio/mp4")):
        if key.endswith(f".{extension}"):
            media = mime
            break
    # A pronunciation does not change once fetched, and the key is a digest of
    # what it is a pronunciation of, so it can be held for a long time.
    return Response(content=data, media_type=media, headers={"Cache-Control": "public, max-age=604800"})


def _language() -> str:
    from writing_coach.core.request_context import current_language_code

    return current_language_code().strip().casefold()
