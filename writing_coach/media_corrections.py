"""Manual corrections to a published media item's transcript cue and its stored meanings.

Admin-only, no provider is ever called, no AI, $0. A cue's stored translation lives in the learning cache under a key
that carries a fingerprint of the cue text (`media_meaning.cache_key`), so changing the text would otherwise make the
learner read path miss and ask a provider again. `rekey_cue` therefore copies every stored meaning of the cue, under
every identity the read path or an export may look under, to the key of the new text first.

Word timing: a cue's `words` are kept (their text replaced, timing untouched) only when the new text has the same
number of whitespace-separated tokens as there are words; otherwise the cue's word-level timing is dropped, because
it cannot be re-aligned without a recogniser. Readings derived from the old text (`catalog` readings / pinyin for
that segment) are dropped for the same reason. The cue's own start/end time is never changed.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from writing_coach.core.support_languages import all_support_languages
from writing_coach.media_meaning import IMPORTED_IDENTITY, cache_key
from writing_coach.media_pack import KNOWN_IDENTITY_CLASSES

PROVENANCE_MANUAL = "manual_correction"
MAX_CUE_CHARS = 2000
MAX_TRANSLATION_CHARS = 4000
_DERIVED_BY_SEGMENT = ("readings_by_segment", "pinyin_by_segment", "pinyin_chars_by_segment")


class CorrectionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def support_codes() -> list[str]:
    return [definition.code for definition in all_support_languages()]


def identities(read_identity: str, provider_models: Sequence[str]) -> list[str]:
    """Every identity a meaning of this cue may be stored under, the read path's own first."""
    return list(dict.fromkeys([
        *([read_identity] if read_identity else []), *provider_models,
        *(f"{cls}:default" for cls in KNOWN_IDENTITY_CLASSES), IMPORTED_IDENTITY]))


def write_identities(read_identity: str) -> list[str]:
    """Where a corrected translation is written: what the read path looks under, and the pack-import identity."""
    return list(dict.fromkeys([*([read_identity] if read_identity else []), IMPORTED_IDENTITY]))


def payload_of(lesson: Mapping[str, Any] | None) -> Mapping[str, Any]:
    payload = lesson.get("payload") if isinstance(lesson, Mapping) else None
    return payload if isinstance(payload, Mapping) else {}


def asset_id_of(media_id: str, lesson: Mapping[str, Any] | None) -> str:
    return str((payload_of(lesson).get("asset") or {}).get("asset_id") or media_id)


def find_segment(lesson: Mapping[str, Any] | None, segment_id: str) -> Mapping[str, Any] | None:
    for seg in (payload_of(lesson).get("transcript") or {}).get("segments") or []:
        if isinstance(seg, Mapping) and str(seg.get("segment_id")) == segment_id:
            return seg
    return None


def with_revision(lesson: dict[str, Any]) -> dict[str, Any]:
    """Bump the lesson's content revision so a cache keyed on it refreshes."""
    try:
        current = int(lesson.get("content_revision") or 0)
    except (TypeError, ValueError):
        current = 0
    return {**lesson, "content_revision": current + 1}


def etag(media_id: str, lesson: Mapping[str, Any] | None) -> str:
    return f'"{media_id}-r{(lesson or {}).get("content_revision") or 0}"'


def corrected_lesson_text(lesson: Mapping[str, Any], segment_id: str, text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """The lesson with one cue's text replaced, and what happened to its word timing and derived readings."""
    payload = dict(payload_of(lesson))
    transcript = dict(payload.get("transcript") or {})
    segments, outcome = [], {"words": "none", "readings_dropped": False}
    for seg in transcript.get("segments") or []:
        if not (isinstance(seg, Mapping) and str(seg.get("segment_id")) == segment_id):
            segments.append(seg)
            continue
        new = {**seg, "original_text": text}
        words = [w for w in (seg.get("words") or []) if isinstance(w, Mapping)]
        if words:
            tokens = text.split()
            if len(tokens) == len(words):
                new["words"] = [{**w, "text": token} for w, token in zip(words, tokens, strict=True)]
                outcome["words"] = "retexted"
            else:
                new["words"] = []
                outcome["words"] = "dropped"
        segments.append(new)
    transcript["segments"] = segments
    payload["transcript"] = transcript
    catalog = payload.get("catalog")
    if isinstance(catalog, Mapping):
        trimmed = dict(catalog)
        for name in _DERIVED_BY_SEGMENT:
            held = trimmed.get(name)
            if isinstance(held, Mapping) and segment_id in held:
                trimmed[name] = {k: v for k, v in held.items() if k != segment_id}
                outcome["readings_dropped"] = True
        payload["catalog"] = trimmed
    return {**lesson, "payload": payload}, outcome


def with_editorial_translation(lesson: Mapping[str, Any], segment_id: str, language: str, text: str,
                               ) -> tuple[dict[str, Any], bool]:
    """If the lesson carries a pre-authored meaning for this cue and language, it shadows the cache: correct it too."""
    payload = dict(payload_of(lesson))
    rows, touched = [], False
    for row in payload.get("translations") or []:
        if (isinstance(row, Mapping) and str(row.get("segment_id")) == segment_id
                and str(row.get("target_language") or "").casefold() == language):
            row = {**row, "translated_meaning": text}
            touched = True
        rows.append(row)
    if touched:
        payload["translations"] = rows
    return {**lesson, "payload": payload}, touched


def rekey_cue(cache: Any, *, asset_id: str, segment_id: str, old_text: str, new_text: str, source_language: str,
              models: Sequence[str], supplied: Mapping[str, str], write_models: Sequence[str], stamp: str,
              ) -> dict[str, int]:
    """Carry every stored meaning of a cue to the key of its corrected text; a supplied translation replaces it.

    Reads and writes the cache only; the old rows stay (their key no longer matches any text, so they are never served)."""
    carried = supplied_written = 0
    for code in support_codes():
        if code == source_language:
            continue
        for model in models:
            hit = cache.get_media_translation(cache_key(asset_id, segment_id, old_text, code, model))
            if hit and str(hit.get("translated_text") or "").strip():
                cache.put_media_translation(
                    cache_key(asset_id, segment_id, new_text, code, model),
                    str(hit["translated_text"]), str(hit.get("provenance") or "generated"),
                    str(hit.get("generated_at") or stamp))
                carried += 1
        if code in supplied:
            for model in write_models:
                cache.put_media_translation(cache_key(asset_id, segment_id, new_text, code, model),
                                            supplied[code], PROVENANCE_MANUAL, stamp)
            supplied_written += 1
    return {"carried": carried, "supplied": supplied_written}


def put_translation(cache: Any, *, asset_id: str, segment_id: str, source_text: str, translation: str, language: str,
                    write_models: Sequence[str], stamp: str) -> None:
    """Store a hand-written meaning of the cue `source_text` under each write identity."""
    for model in write_models:
        cache.put_media_translation(cache_key(asset_id, segment_id, source_text, language, model),
                                    translation.strip(), PROVENANCE_MANUAL, stamp)


def now_stamp() -> str:
    return datetime.now(UTC).isoformat()

