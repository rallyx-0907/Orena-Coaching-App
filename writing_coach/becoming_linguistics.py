from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any


from writing_coach.linguistic_annotation import ALLOWED_POS, annotate
from writing_coach.persistence.specialized_repository import SpecializedLearningRepository

_repository: SpecializedLearningRepository | None = None

MAX_ANNOTATED_CHARS = 6000
MAX_ANNOTATIONS = 220
CACHE_KEY = "linguistic_annotations_v1"


def configure_becoming_linguistics(repository: SpecializedLearningRepository) -> None:
    global _repository
    _repository = repository


def _repo() -> SpecializedLearningRepository:
    if _repository is None:
        raise RuntimeError("BECOMING linguistics repository is not installed")
    return _repository

def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _hash_text(language: str, text: str) -> str:
    payload = f"{language}\0{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _safe_module_data(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _validated_annotations(
    source: str,
    raw: Any,
) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    output: list[dict[str, Any]] = []
    cursor = 0

    for item in raw[:MAX_ANNOTATIONS]:
        if not isinstance(item, dict):
            continue

        fragment = str(item.get("fragment") or "")
        pos = str(item.get("pos") or "other").strip().lower()

        if pos not in ALLOWED_POS:
            pos = "other"
        if not fragment or fragment.isspace():
            continue

        # Cached payloads already contain validated offsets. Re-check them first.
        try:
            cached_start = int(item.get("start"))
            cached_end = int(item.get("end"))
        except (TypeError, ValueError):
            cached_start = -1
            cached_end = -1

        if (
            cached_start >= cursor
            and cached_end > cached_start
            and cached_end <= len(source)
            and source[cached_start:cached_end] == fragment
        ):
            start = cached_start
            end = cached_end
        else:
            # Generation returns ordered literal fragments; the service owns offsets.
            start = source.find(fragment, cursor)
            if start < 0:
                continue
            end = start + len(fragment)

        output.append(
            {
                "fragment": fragment,
                "start": start,
                "end": end,
                "pos": pos,
            }
        )
        cursor = end

    return output


def _public_payload(
    essay_id: int,
    *,
    language: str,
    annotations: list[dict[str, Any]],
    cached: bool,
    truncated: bool,
) -> dict[str, Any]:
    return {
        "found": True,
        "essay_id": essay_id,
        "language_code": language,
        "annotations": annotations,
        "cached": cached,
        "truncated": truncated,
        "claim": "parts_of_speech_learning_aid",
    }


def linguistic_annotations_for_essay(essay_id: int) -> dict[str, Any]:
    row = _repo().get_linguistic_essay(essay_id)
    if not row:
        return {"found": False, "essay_id": essay_id, "annotations": []}
    full_text = str(row["text"] or ""); language = str(row["language_code"] or "en")
    source = full_text[:MAX_ANNOTATED_CHARS]; truncated = len(full_text) > len(source); digest = _hash_text(language, source)
    module_data = _safe_module_data(row["module_data_json"]); cached = module_data.get(CACHE_KEY)
    if isinstance(cached, dict) and cached.get("hash") == digest and cached.get("language_code") == language and isinstance(cached.get("annotations"), list):
        annotations = _validated_annotations(source, cached.get("annotations"))
        return _public_payload(essay_id, language=language, annotations=annotations, cached=True, truncated=bool(cached.get("truncated", truncated)))

    # Segmentation and tagging are deterministic, so this is a local computation
    # rather than a provider call. The result still goes through the same
    # validation as a cached payload: literal fragments, ordered, offsets that
    # index back into the source.
    annotations = _validated_annotations(
        source, annotate(language, source, max_annotations=MAX_ANNOTATIONS)
    )

    cache_payload = {
        "hash": digest,
        "language_code": language,
        "annotations": annotations,
        "truncated": truncated,
        "generated_at": _now(),
    }

    # A key-level merge under the essay's row lock: a review refresh and this cache write must not
    # erase each other (D4 I19), which the read-modify-write of the whole bag could.
    _repo().merge_essay_module_data(essay_id, CACHE_KEY, cache_payload)


    return _public_payload(
        essay_id,
        language=language,
        annotations=annotations,
        cached=False,
        truncated=truncated,
    )
