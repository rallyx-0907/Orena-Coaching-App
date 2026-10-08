"""A text's summary, generated only when a learner opens Summary, once, and kept (proposals/READING_ON_DEMAND.md).

The design says "Generated on request": opening an article never reaches this module. The key is the normalized
text and the languages, so a summary is shared by every learner who opens the same text (published text only; a
learner's own imported text is cached in this process alone, `reading_derived.py`).

Capability: `text_discussion` (the learner's questions about a whole text). Adding a `reading_summary` capability
would need an explicit configuration row in every runtime before `scripts/validate_ai_capability_control_plane.py`
passes there, for no gain: it is the same tutor-grade provider choice.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from writing_coach.core.support_languages import normalize_support_language, support_language
from writing_coach.media_ingestion import primary_language
from writing_coach.reading_derived import (
    KIND_SUMMARY,
    DerivedCache,
    content_key,
    normalize_text,
)

SUMMARY_BULLETS = 5
# A long chapter is summarised from its opening: bounded input, bounded cost.
MAX_SUMMARY_SOURCE_CHARS = 12_000
MAX_BULLET_CHARS = 240

SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"bullets": {"type": "array", "maxItems": 6, "items": {"type": "string"}}},
    "required": ["bullets"],
}


class SummaryUnavailable(RuntimeError):
    """The provider could not produce a summary; asking again may work."""


def _platform_generate(**kwargs: Any) -> dict[str, Any]:
    from writing_coach.ai.base import AICapabilityError, AIProviderError
    from writing_coach.ai.platform import generate_structured

    try:
        result = generate_structured(capability_key="text_discussion", temperature=0.2, seed=42, **kwargs)
    except (AIProviderError, AICapabilityError) as exc:
        raise SummaryUnavailable(type(exc).__name__) from exc
    return result.data if isinstance(result.data, dict) else {}


class ReadingSummaryService:
    def __init__(self, cache: DerivedCache, generate: Callable[..., dict[str, Any]] = _platform_generate) -> None:
        self._cache = cache
        self._generate = generate

    def summarize(self, text: str, source_language: str, target_language: str, *, persist: bool) -> list[str]:
        source = primary_language(source_language)
        target = normalize_support_language(target_language)
        body = normalize_text(text)[:MAX_SUMMARY_SOURCE_CHARS]
        key = content_key(KIND_SUMMARY, source, body)
        hit = self._cache.get(KIND_SUMMARY, target, key, persist=persist)
        if hit and hit.get("bullets"):
            return [str(item) for item in hit["bullets"]]
        source_label = (support_language(source) or support_language("en")).translation_label  # type: ignore[union-attr]
        target_label = (support_language(target)).translation_label  # type: ignore[union-attr]
        raw = self._generate(
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You summarise a {source_label} text for a language learner, in {target_label}. Give "
                        f"{SUMMARY_BULLETS} bullets, each one short line (under 20 words) stating a main point "
                        "in the order the text makes them. Use only what the text says. No heading, no "
                        "numbering, no commentary."
                    ),
                },
                {"role": "user", "content": body},
            ],
            schema=SUMMARY_SCHEMA,
            max_output_tokens=500,
        )
        bullets = [
            normalize_text(item)[:MAX_BULLET_CHARS]
            for item in (raw.get("bullets") if isinstance(raw.get("bullets"), list) else [])
            if normalize_text(str(item or ""))
        ][: SUMMARY_BULLETS + 1]
        if not bullets:
            raise SummaryUnavailable("empty summary")
        self._cache.put_many(KIND_SUMMARY, target, source, [(key, {"bullets": bullets})], persist=persist)
        return bullets
