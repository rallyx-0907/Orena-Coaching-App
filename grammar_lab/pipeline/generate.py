"""``generate`` step (SPEC §5.1): deterministic blocks from rules/, LLM for
natural-language blocks, templated check items.

Operates on points that already exist under ``content/<lang>/`` -- their
``id``/``target_lang``/``function``/``level``/``prereqs``/``contrasts``/
``error_tags``/``source_refs`` are structural metadata that comes from the
inventory (SPEC §4), not something this step invents. What ``generate``
(re)writes is the point's ``blocks``: the deterministic ``rule_table`` (code,
via ``rules/``), the LLM-authored blocks (``formula``, ``timeline``,
``example``, ``contrast``, ``pitfall``, ``note``), and the ``check`` items
(code, built from the examples the LLM just wrote).

SPEC's "don't overwrite an approved point" rule (§5.1) only applies once a
point has been approved: an unreviewed draft can be regenerated freely, in
place, at the same version. Regenerating an *approved* point requires
``--regenerate-note`` and bumps ``version`` -- SPEC §6's admin "request
regenerate" action.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from grammar_lab.pipeline.content_store import (
    LAB_ROOT,
    load_cast,
    load_functions,
    load_manifest,
    load_point,
    next_draft_version,
    save_point,
)
from grammar_lab.pipeline.jsonio import read_json
from grammar_lab.pipeline.llm_client import LLMClient
from grammar_lab.pipeline.r5_source import DEFAULT_R5_ROOT, R5SourceError, load_r5, r5_source_text
from grammar_lab.pipeline.validate import (
    _HAN,
    ERROR_TAGS_PATH,
    ILLUSTRATION_FOR_POINT_TYPE,
    QUICK_PRACTICE_BLANK,
    ZH_HANS,
)
from grammar_lab.rules import en_morphology

PROMPT_VERSION = "generate_point.v1"
PROMPT_PATH = LAB_ROOT / "prompts" / "generate_point.md"
PROMPT_VERSION_V04 = "generate_point_v04.v9"
PROMPT_PATH_V04 = LAB_ROOT / "prompts" / "generate_point_v04.md"
STORY_PROMPT_VERSION = "generate_story.v2"
# grammar_set.schema.json's story_mode allows "history" too (VOICE.md), but generate.py
# does not offer it yet: a "history" story may only state a fact from a vetted source, and
# no such source exists in this repo yet. Wire it in once one does, rather than letting the
# model invent historical/etymological claims it cannot be checked against.
STORY_MODES = {"everyday"}
STORY_PROMPT_PATH = LAB_ROOT / "prompts" / "generate_story.md"

# point id -> (rule label, vocabulary the rule table is built from)
_EN_RULE_TABLES: dict[str, tuple[str, list[str]]] = {
    "en.present_simple.third_person_s": ("third_person_singular", ["work", "study", "go", "have", "watch"]),
    "en.plural_nouns.regular": ("plural_noun", ["cat", "box", "city", "knife", "bus"]),
    "en.past_simple": ("past_simple", ["work", "study", "stop", "go", "have"]),
    "en.present_continuous.now": ("present_participle", ["work", "make", "run", "study", "write"]),
    "en.comparatives": ("comparative", ["cheap", "big", "nice", "happy", "good"]),
    "en.present_perfect.experience": ("past_participle", ["go", "see", "eat", "do", "visit"]),
}
_RULE_FUNCTIONS = {
    "third_person_singular": en_morphology.third_person_singular,
    "plural_noun": en_morphology.plural_noun,
    "past_simple": en_morphology.past_simple,
    "present_participle": en_morphology.present_participle,
    "comparative": en_morphology.comparative,
    "past_participle": en_morphology.past_participle,
}


@dataclass
class GenerateOutcome:
    point_id: str
    status: str  # "written" | "skipped_approved" | "error"
    reason: str = ""
    cost_usd: float | None = None
    cached: bool = False


def build_rule_table(point_id: str, locales: list[str]) -> dict[str, Any] | None:
    """The deterministic ``rule_table`` block for ``point_id``, or ``None`` if this
    point has no mechanical spelling rule (e.g. ``there_is_are``, articles)."""
    entry = _EN_RULE_TABLES.get(point_id)
    if entry is None:
        return None
    rule_name, words = entry
    fn = _RULE_FUNCTIONS[rule_name]
    rows: list[list[Any]] = []
    for word in words:
        derived = fn(word)
        if derived is None:
            continue
        note = {locale: f"{word} -> {derived}" for locale in locales}
        rows.append([word, derived, note])
    return {"type": "rule_table", "rows": rows} if rows else None


def _rule_table_summary(rule_table: dict[str, Any] | None) -> str:
    if rule_table is None:
        return "(none -- no mechanical spelling rule applies to this point)"
    return "; ".join(f"{base} -> {derived}" for base, derived, _ in rule_table["rows"])


def _normalize_seg(seg: list[list[Any]]) -> list[list[Any]]:
    """``example.seg`` items are ``[text]`` or ``[text, label]`` -- the label is
    genuinely optional (SPEC §3), not nullable. A provider with no real schema
    enforcement (DeepSeek's json_object mode; live testing 2026-09-28) reached
    for the more common JSON convention instead and sent ``[text, null]`` for
    an unlabelled segment rather than omitting the second element. Providers
    with real structured-output enforcement (Gemini, OpenAI, Groq, Anthropic
    tool-use) never produce this -- the schema itself forbids it -- so this is
    a no-op for them."""
    return [segment[:1] if len(segment) > 1 and segment[1] is None else segment for segment in seg]


def _locale_map_schema(locales: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(locales),
        "properties": {locale: {"type": "string", "minLength": 1} for locale in locales},
    }


def _generation_schema(*, locales: list[str], l1s: list[str], error_tags: list[str],
                        contrast_with: list[str], num_examples: int) -> dict[str, Any]:
    locale_map = _locale_map_schema(locales)
    example = {
        "type": "object",
        "additionalProperties": False,
        "required": ["text", "seg", "tr"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "seg": {
                "type": "array", "minItems": 1,
                "items": {
                    "type": "array", "minItems": 1, "maxItems": 2,
                    "prefixItems": [{"type": "string", "minLength": 1}, {"type": "string"}],
                },
            },
            "tr": locale_map,
        },
    }
    contrast = {
        "type": "object",
        "additionalProperties": False,
        "required": ["with", "pairs", "explain"],
        "properties": {
            "with": {"enum": contrast_with} if contrast_with else {"type": "string"},
            "pairs": {
                "type": "array", "minItems": 1,
                "items": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "string", "minLength": 1}},
            },
            "explain": locale_map,
        },
    }
    pitfall = {
        "type": "object",
        "additionalProperties": False,
        "required": ["l1", "wrong", "right", "error_tag", "why"],
        "properties": {
            "l1": {"type": "array", "minItems": 1, "items": {"enum": l1s} if l1s else {"type": "string"}},
            "wrong": {"type": "string", "minLength": 1},
            "right": {"type": "string", "minLength": 1},
            "error_tag": {"enum": error_tags} if error_tags else {"type": "string"},
            "why": locale_map,
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["formula", "timeline", "examples", "contrasts", "pitfalls", "note"],
        "properties": {
            "formula": {
                "type": "object", "additionalProperties": False, "required": ["parts"],
                "properties": {"parts": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}}},
            },
            "timeline": {
                "type": ["object", "null"], "additionalProperties": False, "required": ["kind"],
                "properties": {
                    "kind": {"enum": [
                        "point_past", "ongoing_now", "unspecified_past", "habit",
                        "future_condition", "future_plan", "past_ongoing",
                    ]},
                    "relevance": {"type": "string"},
                },
            },
            "examples": {"type": "array", "minItems": num_examples, "maxItems": num_examples, "items": example},
            "contrasts": {"type": "array", "minItems": len(contrast_with), "maxItems": len(contrast_with), "items": contrast},
            "pitfalls": {"type": "array", "minItems": len(error_tags), "maxItems": len(error_tags), "items": pitfall},
            "note": {"type": ["object", "null"], "additionalProperties": False, "required": ["text"],
                      "properties": {"text": locale_map}},
        },
    }


_PATTERN_ROLES = [
    "subject", "verb", "aux", "object", "complement", "time", "place", "marker", "particle", "connector", "other",
]
_TIMELINE_SHAPES = [
    "point_past", "ongoing_now", "unspecified_past", "habit", "future_condition", "future_plan", "past_ongoing",
]


V04_EXAMPLES = 3
V04_MAX_TOKENS = 8192  # zh output carries per-character pinyin on every string
# Whitespace touching a Han character or the blank (what validate's zh.whitespace reports).
_ZH_SPACE_RUN = re.compile(
    rf"\s+(?={_HAN.pattern}|{QUICK_PRACTICE_BLANK})|(?<={_HAN.pattern})\s+|(?<={QUICK_PRACTICE_BLANK})\s+"
)


def _generation_schema_v04(*, locales: list[str], l1s: list[str], error_tags: list[str], engine_tags: list[str],
                            contrast_with: list[str], point_type: str, zh: bool,
                            r5_ids: list[str] | None = None) -> dict[str, Any]:
    """GRAMMAR_CONTENT_CONTRACT.md: the model's output for a schema_version 0.4 point.

    Built per point, so nothing here needs if/then (not every provider's structured-output
    dialect supports it): the illustration kind is fixed by point_type in code, and only
    the data that kind needs is asked for. Things the model is bad at are moved to code:
    spans are given as the substring and resolved to offsets by generate.py; zh pinyin is
    given as [character, syllable] pairs so the alignment is explicit; and with a single
    explanation locale every explanation field is a plain string that generate.py files
    under that locale (live DeepSeek runs kept malforming one-key locale objects inside
    arrays -- `[ "vi": "..." ]`)."""
    locale_map = {"type": "string", "minLength": 1} if len(locales) == 1 else _locale_map_schema(locales)
    pinyin_pairs = {
        "type": "array",
        "items": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "string"}},
    }

    def with_pinyin(schema: dict[str, Any], *fields: str) -> dict[str, Any]:
        if zh:
            for name in fields:
                schema["properties"][name] = pinyin_pairs
                schema["required"].append(name)
        return schema

    slot_option = with_pinyin({
        "type": "object", "additionalProperties": False, "required": ["text"],
        "properties": {"text": {"type": "string", "minLength": 1}},
    }, "pinyin_pairs")
    slot = with_pinyin({
        "type": "object", "additionalProperties": False, "required": ["text", "role", "label", "optional", "options"],
        "properties": {
            "text": {"type": "string", "minLength": 1}, "role": {"enum": _PATTERN_ROLES},
            "label": locale_map, "optional": {"type": "boolean"},
            "options": {"type": "array", "items": slot_option},
        },
    }, "pinyin_pairs")
    span = {
        "type": "object", "additionalProperties": False, "required": ["text", "role"],
        "properties": {"text": {"type": "string", "minLength": 1}, "role": {"enum": _PATTERN_ROLES}},
    }
    example = with_pinyin({
        "type": "object", "additionalProperties": False,
        "required": ["text", "form", "spans", "annotation", "translation"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "form": {"enum": ["affirmative", "negative", "question"]},
            "spans": {"type": "array", "minItems": 1, "items": span},
            "annotation": locale_map,
            "translation": locale_map,
        },
    }, "pinyin_pairs")
    compare_item = {
        "type": "object", "additionalProperties": False,
        "required": ["with", "this_meaning", "this_example", "other_meaning", "other_example"],
        "properties": {
            "with": {"enum": contrast_with} if contrast_with else {"type": "string"},
            "this_meaning": locale_map, "this_example": {"type": "string", "minLength": 1},
            "other_meaning": locale_map, "other_example": {"type": "string", "minLength": 1},
        },
    }
    common_mistake = with_pinyin({
        "type": "object", "additionalProperties": False,
        "required": ["wrong", "right", "reason", "error_tag", "l1"],
        "properties": {
            "wrong": {"type": "string", "minLength": 1}, "right": {"type": "string", "minLength": 1},
            "reason": locale_map,
            "error_tag": {"enum": error_tags} if error_tags else {"type": "string"},
            "l1": {"type": "array", "minItems": 1, "items": {"enum": l1s} if l1s else {"type": "string"}},
        },
    }, "wrong_pinyin_pairs", "right_pinyin_pairs")
    option = {
        "type": "object", "additionalProperties": False, "required": ["text", "error_tag"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "error_tag": {"enum": [*engine_tags, None]} if engine_tags else {"type": ["string", "null"]},
        },
    }
    quick_practice_item = {
        "type": "object", "additionalProperties": False, "required": ["q", "options", "answer", "explain"],
        "properties": {
            "q": {"type": "string", "minLength": 1},
            "options": {"type": "array", "minItems": 2, "maxItems": 3, "items": option},
            "answer": {"type": "integer", "minimum": 0, "maximum": 2},
            "explain": locale_map,
        },
    }
    formula = {"type": "array", "minItems": 1, "items": slot}
    mistake_count = max(1, len(error_tags))
    properties: dict[str, Any] = {
        "summary": locale_map,
        "when_to_use": {"type": "array", "minItems": 2, "maxItems": 4, "items": locale_map},
        "formula": formula,
        "negative": {"type": "array", "items": slot},
        "question": {"type": "array", "items": slot},
        "examples": {"type": "array", "minItems": V04_EXAMPLES, "maxItems": V04_EXAMPLES, "items": example},
        "compare": {"type": "array", "minItems": len(contrast_with), "maxItems": len(contrast_with), "items": compare_item},
        "common_mistakes": {"type": "array", "minItems": mistake_count, "maxItems": mistake_count, "items": common_mistake},
        "quick_practice": {"type": "array", "minItems": 3, "maxItems": 3, "items": quick_practice_item},
    }
    if point_type == "tense_aspect":
        properties["timeline_shape"] = {"enum": _TIMELINE_SHAPES}
    elif point_type == "morphology":
        properties["morphology"] = {
            "type": "array", "minItems": 1, "maxItems": 4,
            "items": {
                "type": "object", "additionalProperties": False, "required": ["base", "affix", "result"],
                "properties": {
                    "base": {"type": "string", "minLength": 1}, "affix": {"type": "string", "minLength": 1},
                    "result": {"type": "string", "minLength": 1},
                },
            },
        }
    if r5_ids:
        # Conversion mode: the model says what it corrected in the R5 source, so verify can have
        # the other-family model confirm it and the human learns where R5 was wrong.
        properties["r5_corrections"] = {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False, "required": ["r5_id", "issue", "fix"],
                "properties": {
                    "r5_id": {"enum": list(r5_ids)},
                    "issue": {"type": "string", "minLength": 1},
                    "fix": {"type": "string", "minLength": 1},
                },
            },
        }
    return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}


# Conversion mode (human, 2026-09-28): R5 is raw material, not discarded.
_R5_INSTRUCTION = """
## Converting from R5

The user message carries the app's current lesson(s) for this point ("R5"). Use them as raw
material: keep what is right (a good example, a real learner mistake, a clear rule), restructure
it into this schema, **correct** anything wrong (a wrong rule, an ungrammatical example, a
mistake that is not one, a level-inappropriate word) and **add** what is missing (the formula,
the variants, spans, the comparison, the quick check). Do not carry an error over. List every
correction you made to R5's content in `r5_corrections` (which lesson, what was wrong, what you
wrote instead) -- another model checks each one; leave it empty if R5 needed none. Scope stays
this point's: if an R5 lesson covers more than this point, take only this point's part.
"""

_ILLUSTRATION_INSTRUCTIONS = {
    "tense_aspect": (
        "This point is about *when* things happen, so the app draws a timeline: fill `timeline_shape` "
        "with the one shape from the closed list that matches it."
    ),
    "word_order": (
        "This point is about the *order* of the parts, so the app draws the formula slots themselves as "
        "ordered boxes -- make the formula's slot order exactly the order a sentence follows. No extra data."
    ),
    "morphology": (
        "This point is about how a *word changes form*, so the app draws base + affix -> result: fill "
        "`morphology` with 1-4 items (e.g. book + -s -> books, city + -ies -> cities), covering the "
        "spelling cases a learner actually meets. If the formula keeps the base and the affix as "
        "separate slots (`N` + `-s/-es`), span them separately in every example, in order: the base "
        "(`book`), then the affix alone (`s`). An irregular form with no separable affix (children) "
        "does not fit such a formula -- use regular forms in the examples."
    ),
    "other": "No illustration for this point -- the formula carries it.",
}

_PINYIN_INSTRUCTION = """
## Pinyin (zh-Hans)

Every Chinese string you write -- each formula slot's `text`, each example's `text`, each common
mistake's `wrong` and `right` -- gets its pinyin as `[character, syllable]` pairs: one pair per
character, in order, with the **tone mark** on the syllable (`wǒ`, `bǎ`, `shū`; neutral tone
unmarked: `le`, `men`). Never tone numbers (`wo3`). A character that is not a Han character
(punctuation, a Latin letter, a space, `+`) still gets its own pair, with syllable `""`. Read each
character in context: 了 is `le` after a verb, 过 is `guo` as an aspect marker.
"""


def _header_metadata(existing: dict[str, Any], locales: list[str]) -> dict[str, Any]:
    """title/native_title/level: structural metadata, carried over, never generated. A point
    still on the first v0.4 shape keeps them in a top-level title instead of a header."""
    if "header" in existing:
        header = existing["header"]
        return {"title": header["title"], "native_title": header["native_title"], "level": dict(existing["level"])}
    title = existing["title"]
    native = title.get(existing["target_lang"]) or title.get("en") or title["vi"]
    return {
        "title": {locale: title[locale] for locale in locales if locale in title} or {"vi": title["vi"]},
        "native_title": native,
        "level": dict(existing["level"]),
    }


def resolve_spans(text: str, spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn model-given span substrings into character offsets. Spans are listed in sentence
    order, so each is looked for first after the previous one (which is what lets a base and
    its affix be spanned separately: `book`, then the `s` right after it), then anywhere it
    does not overlap a span already placed. A substring that is not in the sentence is
    dropped -- validate then flags the formula role it was meant to cover, rather than
    generate inventing an offset."""
    placed: list[dict[str, Any]] = []
    cursor = 0

    def free(start: int, end: int) -> bool:
        return all(end <= other["start"] or start >= other["end"] for other in placed)

    for span in spans:
        needle = span["text"]
        found = None
        for origin in (cursor, 0):
            start = text.find(needle, origin)
            while start != -1 and not free(start, start + len(needle)):
                start = text.find(needle, start + 1)
            if start != -1:
                found = start
                break
        if found is not None:
            placed.append({"start": found, "end": found + len(needle), "role": span["role"]})
            cursor = found + len(needle)
    return sorted(placed, key=lambda s: s["start"])


def pinyin_from_pairs(pairs: list[list[str]]) -> list[str]:
    """[[character, syllable], ...] -> [syllable, ...]; a multi-character pair is kept as one
    entry so validate reports the misalignment instead of generate guessing a split."""
    return [syllable for _, syllable in pairs]


def zh_unspaced(text: str) -> str:
    """Chinese is written without spaces; DeepSeek put one on each side of every quick-practice
    blank in the first zh v0.4 run. Only the question is repaired here -- it carries no pinyin;
    a spaced example would misalign its pinyin, so validate (zh.whitespace) reports that one."""
    return _ZH_SPACE_RUN.sub("", text)


def _as_locale_map(value: Any, locales: list[str]) -> Any:
    """A provider with no schema enforcement (DeepSeek's json_object mode, live 2026-09-28)
    sometimes returns a locale field as a bare string. With a single declared locale that
    string can only mean that locale; with several it is left as-is for validate to flag."""
    if isinstance(value, str) and len(locales) == 1:
        return {locales[0]: value}
    return value


def _slots(raw: list[dict[str, Any]], zh: bool, locales: list[str]) -> list[dict[str, Any]]:
    out = []
    for slot in raw:
        item: dict[str, Any] = {"text": slot["text"], "role": slot["role"], "label": _as_locale_map(slot["label"], locales)}
        if slot.get("optional"):
            item["optional"] = True
        options = [
            {"text": option["text"], **({"pinyin": pinyin_from_pairs(option["pinyin_pairs"])} if zh else {})}
            for option in slot.get("options") or []
        ]
        if len(options) >= 2:  # one "option" is not a choice; the slot text already says it
            item["options"] = options
        if zh:
            item["pinyin"] = pinyin_from_pairs(slot["pinyin_pairs"])
        out.append(item)
    return out


def _story_generation_schema(*, locales: list[str], error_tags: list[str], cast_names: list[str]) -> dict[str, Any]:
    """STORY_SPEC.md §2: the LLM writes everything except ``type``/``theme`` (code sets
    those). One alternative per error_tag, same bounded-count pattern as pitfalls."""
    locale_map = _locale_map_schema(locales)
    slot = {
        "type": "object", "additionalProperties": False,
        "required": ["role", "value", "constraint"],
        "properties": {
            "role": {"enum": ["person", "place", "action", "object"]},
            "value": {"type": "string", "minLength": 1},
            "constraint": {"type": "string", "minLength": 1},
        },
    }
    beat = {
        "type": "object", "additionalProperties": False,
        "required": ["sentences", "slots"],
        "properties": {
            "sentences": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
            "slots": {"type": "array", "items": slot},
        },
    }
    alternative = {
        "type": "object", "additionalProperties": False,
        "required": ["sentence", "error_tags", "consequence", "short", "slots"],
        "properties": {
            "sentence": {"type": "string", "minLength": 1},
            "error_tags": {
                "type": "array", "minItems": 1, "uniqueItems": True,
                "items": {"enum": error_tags} if error_tags else {"type": "string"},
            },
            "consequence": locale_map,
            "short": locale_map,
            "slots": {"type": "array", "items": slot},
        },
    }
    hook = {
        "type": "object", "additionalProperties": False,
        "required": ["hook_type", "text"],
        "properties": {
            "hook_type": {"enum": ["stakes", "insider", "myth-bust"]},
            "text": locale_map,
        },
    }
    alternative_count = max(1, len(error_tags))
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "characters", "hook", "scene", "need", "form_in_action", "alternatives", "reveal", "reveal_short", "teaser"
        ],
        "properties": {
            "characters": {
                "type": "array", "minItems": 1, "uniqueItems": True,
                "items": {"enum": cast_names} if cast_names else {"type": "string"},
            },
            "hook": hook,
            "scene": locale_map,
            "need": locale_map,
            "form_in_action": beat,
            "alternatives": {"type": "array", "minItems": alternative_count, "maxItems": alternative_count, "items": alternative},
            "reveal": locale_map,
            "reveal_short": locale_map,
            "teaser": locale_map,
        },
    }


def _build_check_items(examples: list[dict[str, Any]], rule_table: dict[str, Any] | None,
                        pitfalls: list[dict[str, Any]], locales: list[str], max_items: int = 3) -> list[dict[str, Any]]:
    """Cloze questions built from the examples the LLM just wrote (SPEC §5.1 step 3):
    blank out the ``target`` segment, offer the base form and a pitfall's wrong form
    as distractors. Deterministic -- no LLM call."""
    rows_by_derived = {row[1]: row[0] for row in (rule_table or {}).get("rows", [])}
    pitfalls_by_tag = {p["error_tag"]: p for p in pitfalls}
    generic_explain = {locale: "See the rule and examples above." for locale in locales}

    items: list[dict[str, Any]] = []
    for example in examples:
        target_segments = [seg for seg in example["seg"] if len(seg) > 1 and seg[1] == "target"]
        if len(target_segments) != 1:
            continue  # a clean single-blank cloze needs exactly one target segment
        target_text = target_segments[0][0]
        blanked = "".join(seg[0] if not (len(seg) > 1 and seg[1] == "target") else "___" for seg in example["seg"])
        options = [target_text]
        base = rows_by_derived.get(target_text.strip())
        if base and base not in options:
            options.append(base)
        for pitfall in pitfalls:
            wrong_words = set(pitfall["wrong"].split())
            candidate = next((w for w in wrong_words if w not in target_text and len(options) < max_items), None)
            if candidate and candidate not in options:
                options.append(candidate)
                break
        if len(options) < 2:
            continue
        explain = next(
            (p["why"] for p in pitfalls_by_tag.values() if p["right"].strip() == target_text.strip()),
            generic_explain,
        )
        items.append({"q": blanked, "options": options, "answer": 0, "explain": explain})
        if len(items) >= max_items:
            break
    return items


@dataclass
class Generator:
    lang: str
    l1: str
    llm: LLMClient
    root: Path = LAB_ROOT
    num_examples: int = 2
    r5_root: Path | None = None  # the app's grammar data (r5_source.DEFAULT_R5_ROOT when None)

    def generate(
        self, point_id: str, *, regenerate_note: str | None = None, with_story: bool = False, story_mode: str = "everyday"
    ) -> GenerateOutcome:
        if story_mode not in STORY_MODES:
            raise ValueError(f"story_mode must be one of {sorted(STORY_MODES)}, got {story_mode!r}")
        existing = load_point(self.lang, point_id, self.root)
        if existing is None:
            return GenerateOutcome(point_id, "error", reason="point metadata does not exist yet; seed it from the inventory first")
        if existing["status"] == "approved" and not regenerate_note:
            return GenerateOutcome(point_id, "skipped_approved", reason="pass --regenerate-note to regenerate an approved point")

        manifest = load_manifest(self.lang, self.root)
        locales: list[str] = manifest["explanation_locales"]
        l1s: list[str] = manifest["l1"]
        functions = load_functions(self.root)["functions"]
        function = next(f for f in functions if f["id"] == existing["function"])

        if existing.get("schema_version") == "0.4":
            if with_story:
                raise ValueError("--with-story is not wired into schema_version 0.4 generation yet (story is paused this round)")
            return self._generate_v04(
                existing, locales=locales, l1s=l1s, function=function, regenerate_note=regenerate_note,
            )

        rule_table = build_rule_table(point_id, locales)
        schema = _generation_schema(
            locales=locales, l1s=l1s, error_tags=existing["error_tags"],
            contrast_with=existing["contrasts"], num_examples=self.num_examples,
        )
        system = PROMPT_PATH.read_text(encoding="utf-8").format(
            point_id=point_id, target_lang=existing["target_lang"],
            level_framework=existing["level"]["framework"], level_value=existing["level"]["value"],
            function_title=function["title"].get("en", function["title"].get("vi", "")),
            function_id=function["id"], locales=", ".join(locales), l1s=", ".join(l1s),
            contrast_with_ids=", ".join(existing["contrasts"]) or "(none)",
            error_tags=", ".join(existing["error_tags"]) or "(none)",
            rule_table_summary=_rule_table_summary(rule_table),
        )
        user = f"Write the grammar point {point_id} now, matching the structured output schema."
        note_suffix = f" Admin regenerate note: {regenerate_note}" if regenerate_note else ""
        result = self.llm.complete(system=system, user=user + note_suffix, json_schema=schema, schema_name="grammar_point_blocks")
        for example in result.data["examples"]:
            example["seg"] = _normalize_seg(example["seg"])

        blocks: list[dict[str, Any]] = [{"type": "formula", **result.data["formula"]}]
        if result.data.get("timeline"):
            blocks.append({"type": "timeline", **result.data["timeline"]})
        if rule_table is not None:
            blocks.append(rule_table)
        examples = [{"type": "example", **example} for example in result.data["examples"]]
        blocks.extend(examples)
        blocks.extend({"type": "contrast", **contrast} for contrast in result.data["contrasts"])
        pitfalls = [{"type": "pitfall", **pitfall} for pitfall in result.data["pitfalls"]]
        blocks.extend(pitfalls)
        if result.data.get("note"):
            blocks.append({"type": "note", **result.data["note"]})
        check_items = _build_check_items(result.data["examples"], rule_table, result.data["pitfalls"], locales)
        if check_items:
            blocks.append({"type": "check", "items": check_items})

        cost = result.usage.cost_usd(result.model) or 0.0
        cached = result.cached
        prompt_version = PROMPT_VERSION
        schema_version = existing.get("schema_version", "0.2")
        if with_story:
            story_result, story_block = self._generate_story(existing, locales, mode=story_mode)
            blocks.append(story_block)
            story_cost = story_result.usage.cost_usd(story_result.model)
            cost = (cost + story_cost) if story_cost is not None else cost
            cached = cached and story_result.cached
            prompt_version = f"{PROMPT_VERSION}+{STORY_PROMPT_VERSION}"
            schema_version = "0.3"

        version = next_draft_version(existing) if regenerate_note and existing["status"] == "approved" else existing["version"]
        point = {
            **existing,
            "schema_version": schema_version,
            "version": version,
            "blocks": blocks,
            "status": "draft_ai",
            "flags": [],
            "provenance": {
                "model": f"{result.provider}:{result.model}",
                "prompt_version": prompt_version,
                "run_id": f"generate.{int(time.time())}",
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            "review": None,
        }
        save_point(self.lang, point, self.root)
        return GenerateOutcome(point_id, "written", cost_usd=cost or None, cached=cached)

    def _generate_v04(
        self, existing: dict[str, Any], *, locales: list[str], l1s: list[str], function: dict[str, Any],
        regenerate_note: str | None = None,
    ) -> GenerateOutcome:
        """GRAMMAR_CONTENT_CONTRACT.md: header + the fixed content blocks, generated fresh.

        Structural metadata (id, level, point_type, error_tags, contrasts, the title and its
        target-language name) comes from the existing point, as with every generate step;
        everything a learner reads under the header is written by the model."""
        point_id = existing["id"]
        point_type = existing.get("point_type")
        if point_type not in ILLUSTRATION_FOR_POINT_TYPE:
            return GenerateOutcome(point_id, "error", reason="schema_version 0.4 point needs point_type metadata first")
        zh = existing["target_lang"] == ZH_HANS
        r5_ids: list[str] = list((existing.get("source_refs") or {}).get("r5", []))
        r5_records: list[dict[str, Any]] = []
        if r5_ids:
            try:
                available = load_r5(self.lang, self.r5_root or DEFAULT_R5_ROOT)
            except R5SourceError as exc:
                return GenerateOutcome(point_id, "error", reason=str(exc))
            unknown = [r5_id for r5_id in r5_ids if r5_id not in available]
            if unknown:
                return GenerateOutcome(point_id, "error", reason=f"source_refs.r5 names unknown R5 lesson(s): {unknown}")
            r5_records = [available[r5_id] for r5_id in r5_ids]
        header = _header_metadata(existing, locales)
        engine_tags = read_json(self.root / ERROR_TAGS_PATH)["languages"][existing["target_lang"]]["tags"]
        schema = _generation_schema_v04(
            locales=locales, l1s=l1s, error_tags=existing["error_tags"], engine_tags=engine_tags,
            contrast_with=existing["contrasts"], point_type=point_type, zh=zh, r5_ids=r5_ids,
        )
        system = PROMPT_PATH_V04.read_text(encoding="utf-8").format(
            point_id=point_id, target_lang=existing["target_lang"],
            level_framework=existing["level"]["framework"], level_value=existing["level"]["value"],
            title=header["title"].get("vi", header["native_title"]), native_title=header["native_title"],
            function_title=function["title"].get("en", function["title"].get("vi", "")),
            function_id=function["id"], locales=", ".join(locales), l1s=", ".join(l1s),
            contrast_with_ids=", ".join(existing["contrasts"]) or "(none)",
            error_tags=", ".join(existing["error_tags"]) or "(none)",
            engine_tags=", ".join(engine_tags),
            illustration_instruction=_ILLUSTRATION_INSTRUCTIONS[point_type],
            locale_format=(
                f"a plain string written in `{locales[0]}` (not an object)."
                if len(locales) == 1 else
                "an object keyed by locale, with every one of these locales: " + ", ".join(locales) + "."
            ),
            pinyin_instruction=_PINYIN_INSTRUCTION if zh else "",
            r5_instruction=_R5_INSTRUCTION if r5_records else "",
            num_examples=V04_EXAMPLES,
        )
        user = f"Write the grammar point {point_id} now, matching the structured output schema."
        if regenerate_note:
            user += f" Admin regenerate note: {regenerate_note}"
        if r5_records:
            user += "\n\nR5 source lesson(s) for this point (restructure, correct, complete):\n" + r5_source_text(r5_records)
        result = self.llm.complete(
            system=system, user=user, json_schema=schema, schema_name="grammar_point_v04", max_tokens=V04_MAX_TOKENS,
        )
        data = result.data

        illustration: dict[str, Any] = {"kind": ILLUSTRATION_FOR_POINT_TYPE[point_type]}
        if point_type == "tense_aspect":
            illustration["timeline"] = {"shape": data["timeline_shape"]}
        elif point_type == "morphology":
            illustration["morphology"] = data["morphology"]
        def loc(value: Any) -> Any:
            return _as_locale_map(value, locales)

        pattern: dict[str, Any] = {"formula": _slots(data["formula"], zh, locales)}
        variants = {name: _slots(data[name], zh, locales) for name in ("negative", "question") if data.get(name)}
        if variants:
            pattern["variants"] = variants
        pattern["illustration"] = illustration

        examples = []
        for raw in data["examples"]:
            example = {
                "text": raw["text"], "form": raw["form"], "spans": resolve_spans(raw["text"], raw["spans"]),
                "annotation": loc(raw["annotation"]), "translation": loc(raw["translation"]),
            }
            if zh:
                example["pinyin"] = pinyin_from_pairs(raw["pinyin_pairs"])
            examples.append(example)
        compare = [
            {**item, "this_meaning": loc(item["this_meaning"]), "other_meaning": loc(item["other_meaning"])}
            for item in data["compare"]
        ]
        quick_practice = [
            {**item, "q": zh_unspaced(item["q"]) if zh else item["q"], "explain": loc(item["explain"])}
            for item in data["quick_practice"]
        ]
        mistakes = []
        for raw in data["common_mistakes"]:
            mistake = {key: raw[key] for key in ("wrong", "right", "reason", "error_tag", "l1")}
            mistake["reason"] = loc(mistake["reason"])
            if zh:
                mistake["wrong_pinyin"] = pinyin_from_pairs(raw["wrong_pinyin_pairs"])
                mistake["right_pinyin"] = pinyin_from_pairs(raw["right_pinyin_pairs"])
            mistakes.append(mistake)

        point = {
            **{key: existing[key] for key in (
                "id", "version", "target_lang", "function", "level", "prereqs", "contrasts", "error_tags", "source_refs",
            )},
            "schema_version": "0.4",
            "point_type": point_type,
            "header": {**header, "summary": loc(data["summary"])},
            "when_to_use": [loc(item) for item in data["when_to_use"]],
            "pattern": pattern,
            "examples": examples,
            "compare": compare,
            "common_mistakes": mistakes,
            "quick_practice": quick_practice,
            "status": "draft_ai",
            "flags": [],
            "provenance": {
                "model": f"{result.provider}:{result.model}",
                "prompt_version": PROMPT_VERSION_V04,
                "run_id": f"generate.{int(time.time())}",
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            "review": None,
        }
        if r5_records:
            point["provenance"]["r5_source"] = {
                "ids": r5_ids,
                "content_version": max(record["content_version"] for record in r5_records),
                "corrections": data.get("r5_corrections", []),
            }
        if existing.get("blocks"):
            point["blocks"] = existing["blocks"]  # only a secondary story can live here on v0.4
        point = {"schema_version": point.pop("schema_version"), **point}
        save_point(self.lang, point, self.root)
        return GenerateOutcome(point_id, "written", cost_usd=result.usage.cost_usd(result.model) or None, cached=result.cached)

    def _generate_story(self, existing: dict[str, Any], locales: list[str], *, mode: str = "everyday") -> tuple[Any, dict[str, Any]]:
        """STORY_SPEC.md + VOICE.md: a dedicated call for the point's daily-theme story block."""
        cast = load_cast(self.root)
        cast_names = [member["name"] for member in cast]
        cast_list = "\n".join(f"- {member['name']}: {member['personality'].get('vi', '')}" for member in cast)
        schema = _story_generation_schema(locales=locales, error_tags=existing["error_tags"], cast_names=cast_names)
        system = STORY_PROMPT_PATH.read_text(encoding="utf-8").format(
            point_id=existing["id"], target_lang=existing["target_lang"],
            level_framework=existing["level"]["framework"], level_value=existing["level"]["value"],
            locales=", ".join(locales), error_tags=", ".join(existing["error_tags"]) or "(none)",
            cast_list=cast_list,
        )
        user = f"Write the daily-theme story for {existing['id']} now, matching the structured output schema."
        result = self.llm.complete(system=system, user=user, json_schema=schema, schema_name="story")
        return result, {"type": "story", "theme": "daily", "mode": mode, **result.data}
