"""``verify`` step (SPEC §5.3): engine pitfall match, clean examples, blind solve.

Vocabulary-level and back-translation (SPEC §5.3's other two checks) are
deferred to phase 3: SPEC §7 explicitly allows shortening phase 1 to these
three ("có thể để sang giai đoạn 3 nếu cần rút ngắn giai đoạn 1"), and the
phase 1 brief asked for exactly this set.

Every flag is a :class:`VerifyFlag` whose ``code`` matches the
``verify:<code>`` flags SPEC §5.4 routes on. A point that could not be
checked at all (evaluator unreachable, blind-solve model errored) is flagged
rather than silently passed -- an unverifiable point is not a verified one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from grammar_lab.pipeline.evaluator_client import EvaluatorClient, EvaluatorClientError
from grammar_lab.pipeline.llm_client import LLMClient, LLMError

PROMPT_VERSION = "blind_solve.v1"
PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "blind_solve.md"
STORY_PROMPT_VERSION = "verify_story.v1"
STORY_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "verify_story.md"

FLAG_PREFIX = "verify:"

# STORY_SPEC.md §6: "Rubric... Low score → flagged." No number was given; this is a starting
# threshold to calibrate against a gold set, the same way route.py's 0.8 is (SPEC §5.4).
STORY_RUBRIC_THRESHOLD = 0.6


@dataclass(frozen=True)
class VerifyFlag:
    code: str
    detail: str

    @property
    def reason(self) -> str:
        return FLAG_PREFIX + self.code


@dataclass
class VerifyReport:
    point_id: str
    flags: list[VerifyFlag] = field(default_factory=list)
    checked_pitfalls: int = 0
    checked_examples: int = 0
    checked_checks: int = 0
    checked_story_sentences: int = 0

    @property
    def ok(self) -> bool:
        return not self.flags

    def codes(self) -> set[str]:
        return {flag.code for flag in self.flags}


_BLIND_SOLVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer_index"],
    "properties": {
        # -1 means "ambiguous / none is clearly correct", never a forced guess.
        "answer_index": {"type": "integer", "minimum": -1},
    },
}

_MEANING_MATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["implied_meaning", "matches_declared_consequence"],
    "properties": {
        "implied_meaning": {"type": "string", "minLength": 1},
        "matches_declared_consequence": {"type": "boolean"},
    },
}

_HISTORICAL_CLAIM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["makes_historical_claim"],
    "properties": {
        "makes_historical_claim": {"type": "boolean"},
        "quote": {"type": "string"},
    },
}

_RUBRIC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["vivid", "correct_when_to_use", "concise"],
    "properties": {
        "vivid": {"type": "number", "minimum": 0, "maximum": 1},
        "correct_when_to_use": {"type": "number", "minimum": 0, "maximum": 1},
        "concise": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


def _read_prompt_section(path: Path, name: str) -> str:
    """The text under ``## {name}`` up to the next ``## `` heading (or EOF)."""
    text = path.read_text(encoding="utf-8")
    marker = f"## {name}\n"
    start = text.index(marker) + len(marker)
    end = text.find("\n## ", start)
    return text[start:] if end == -1 else text[start:end]


def _story_text(block: dict[str, Any]) -> str:
    """Every explanation-locale prose field, concatenated, for the historical-claim and
    rubric checks (STORY_SPEC.md §6) -- both judge the whole story, not one sentence."""
    parts = [block["scene"].get("vi", ""), block["need"].get("vi", ""), block["anchor"].get("vi", "")]
    parts.extend(alt["consequence"].get("vi", "") for alt in block["alternatives"])
    return "\n".join(part for part in parts if part)


def _flatten_example_texts(point: dict[str, Any]) -> list[tuple[str, str]]:
    """(label, text) for every sentence the "clean examples" check must send."""
    texts: list[tuple[str, str]] = []
    for index, block in enumerate(point["blocks"]):
        if block["type"] == "example":
            texts.append((f"blocks[{index}] example", block["text"]))
        elif block["type"] == "contrast":
            for pair_index, pair in enumerate(block["pairs"]):
                for side_index, sentence in enumerate(pair):
                    texts.append((f"blocks[{index}] contrast.pairs[{pair_index}][{side_index}]", sentence))
    return texts


def verify_point(
    point: dict[str, Any],
    *,
    evaluator: EvaluatorClient,
    blind_solver: LLMClient,
) -> VerifyReport:
    report = VerifyReport(point_id=point["id"])
    target_cefr = point["level"]["value"] if point["level"]["framework"] == "cefr" else None

    for index, block in enumerate(point["blocks"]):
        if block["type"] != "pitfall":
            continue
        report.checked_pitfalls += 1
        label = f"blocks[{index}] pitfall"
        try:
            wrong_result = evaluator.evaluate(block["wrong"], target_cefr=target_cefr)
        except EvaluatorClientError as exc:
            report.flags.append(VerifyFlag("evaluator_error", f"{label} wrong: {exc}"))
            continue
        if block["error_tag"] not in wrong_result.categories():
            report.flags.append(VerifyFlag(
                "pitfall_not_caught",
                f"{label}: engine did not tag {block['error_tag']!r} for {block['wrong']!r} "
                f"(got {sorted(wrong_result.categories())})",
            ))
        try:
            right_result = evaluator.evaluate(block["right"], target_cefr=target_cefr)
        except EvaluatorClientError as exc:
            report.flags.append(VerifyFlag("evaluator_error", f"{label} right: {exc}"))
            continue
        if right_result.errors:
            report.flags.append(VerifyFlag(
                "pitfall_right_flagged",
                f"{label}: engine found errors in the corrected sentence {block['right']!r} "
                f"({sorted(right_result.categories())})",
            ))

    for label, text in _flatten_example_texts(point):
        report.checked_examples += 1
        try:
            result = evaluator.evaluate(text, target_cefr=target_cefr)
        except EvaluatorClientError as exc:
            report.flags.append(VerifyFlag("evaluator_error", f"{label}: {exc}"))
            continue
        if result.errors:
            report.flags.append(VerifyFlag(
                "example_not_clean",
                f"{label} {text!r}: engine found errors ({sorted(result.categories())})",
            ))

    for index, block in enumerate(point["blocks"]):
        if block["type"] != "check":
            continue
        for item_index, item in enumerate(block["items"]):
            report.checked_checks += 1
            label = f"blocks[{index}].items[{item_index}]"
            system = PROMPT_PATH.read_text(encoding="utf-8").format(
                level_framework=point["level"]["framework"], level_value=point["level"]["value"],
                target_lang=point["target_lang"], question=item["q"],
                options="\n".join(f"{i}: {opt}" for i, opt in enumerate(item["options"])),
            )
            try:
                result = blind_solver.complete(
                    system=system, user="Answer now.", json_schema=_BLIND_SOLVE_SCHEMA, schema_name="blind_solve",
                )
            except LLMError as exc:
                report.flags.append(VerifyFlag("blind_solve_error", f"{label}: {exc}"))
                continue
            answer_index = result.data["answer_index"]
            if answer_index == -1:
                report.flags.append(VerifyFlag("blind_solve_ambiguous", f"{label}: blind solver found no single correct option"))
            elif answer_index != item["answer"]:
                report.flags.append(VerifyFlag(
                    "blind_solve_wrong",
                    f"{label}: blind solver picked {answer_index} ({item['options'][answer_index] if 0 <= answer_index < len(item['options']) else '?'}), expected {item['answer']}",
                ))

    for index, block in enumerate(point["blocks"]):
        if block["type"] == "story":
            _verify_story(point, index, block, evaluator=evaluator, blind_solver=blind_solver,
                          target_cefr=target_cefr, report=report)

    return report


def _verify_story(
    point: dict[str, Any], index: int, block: dict[str, Any], *,
    evaluator: EvaluatorClient, blind_solver: LLMClient, target_cefr: str | None, report: VerifyReport,
) -> None:
    """STORY_SPEC.md §6: form_in_action must be clean; each alternative is either caught by
    the engine with its declared error_tags, or (the engine finds nothing) grammatical but
    implies something else, which the blind-solve model's reading must match; no historical/
    etymology claim anywhere; rubric judged by the (different-family) blind-solve model."""
    label = f"blocks[{index}] story"

    for sent_index, sentence in enumerate(block["form_in_action"]["sentences"]):
        report.checked_story_sentences += 1
        try:
            result = evaluator.evaluate(sentence, target_cefr=target_cefr)
        except EvaluatorClientError as exc:
            report.flags.append(VerifyFlag("evaluator_error", f"{label}.form_in_action.sentences[{sent_index}]: {exc}"))
            continue
        if result.errors:
            report.flags.append(VerifyFlag(
                "story_form_not_clean",
                f"{label}.form_in_action.sentences[{sent_index}] {sentence!r}: "
                f"engine found errors ({sorted(result.categories())})",
            ))

    for alt_index, alt in enumerate(block["alternatives"]):
        report.checked_story_sentences += 1
        alt_label = f"{label}.alternatives[{alt_index}]"
        try:
            result = evaluator.evaluate(alt["sentence"], target_cefr=target_cefr)
        except EvaluatorClientError as exc:
            report.flags.append(VerifyFlag("evaluator_error", f"{alt_label}: {exc}"))
            continue
        if result.errors:
            if not set(alt["error_tags"]) & result.categories():
                report.flags.append(VerifyFlag(
                    "story_alternative_tag_not_caught",
                    f"{alt_label}: engine tagged {sorted(result.categories())}, expected one of {alt['error_tags']}",
                ))
        else:
            _verify_story_meaning(point, block, alt, alt_label, blind_solver, report)

    _verify_story_no_historical_claim(point, block, label, blind_solver, report)
    _verify_story_rubric(point, block, label, blind_solver, report)


def _verify_story_meaning(
    point: dict[str, Any], block: dict[str, Any], alt: dict[str, Any], label: str,
    blind_solver: LLMClient, report: VerifyReport,
) -> None:
    system = _read_prompt_section(STORY_PROMPT_PATH, "meaning_match").format(
        scene=block["scene"].get("vi", ""), sentence=alt["sentence"], consequence=alt["consequence"].get("vi", ""),
    )
    try:
        result = blind_solver.complete(system=system, user="Answer now.", json_schema=_MEANING_MATCH_SCHEMA,
                                        schema_name="meaning_match")
    except LLMError as exc:
        report.flags.append(VerifyFlag("blind_solve_error", f"{label}: {exc}"))
        return
    if not result.data["matches_declared_consequence"]:
        report.flags.append(VerifyFlag(
            "story_alternative_meaning_mismatch",
            f"{label}: blind solver read {result.data['implied_meaning']!r}, "
            f"which does not match the declared consequence",
        ))


def _verify_story_no_historical_claim(
    point: dict[str, Any], block: dict[str, Any], label: str, blind_solver: LLMClient, report: VerifyReport,
) -> None:
    system = _read_prompt_section(STORY_PROMPT_PATH, "no_historical_claim").format(story_text=_story_text(block))
    try:
        result = blind_solver.complete(system=system, user="Answer now.", json_schema=_HISTORICAL_CLAIM_SCHEMA,
                                        schema_name="historical_claim")
    except LLMError as exc:
        report.flags.append(VerifyFlag("blind_solve_error", f"{label}: {exc}"))
        return
    if result.data["makes_historical_claim"]:
        report.flags.append(VerifyFlag(
            "story_historical_claim", f"{label}: {result.data.get('quote', '(no quote given)')!r}",
        ))


def _verify_story_rubric(
    point: dict[str, Any], block: dict[str, Any], label: str, blind_solver: LLMClient, report: VerifyReport,
) -> None:
    system = _read_prompt_section(STORY_PROMPT_PATH, "rubric").format(story_text=_story_text(block))
    try:
        result = blind_solver.complete(system=system, user="Answer now.", json_schema=_RUBRIC_SCHEMA, schema_name="rubric")
    except LLMError as exc:
        report.flags.append(VerifyFlag("blind_solve_error", f"{label}: {exc}"))
        return
    low = {name: score for name, score in result.data.items() if score < STORY_RUBRIC_THRESHOLD}
    if low:
        report.flags.append(VerifyFlag("story_rubric_low", f"{label}: below {STORY_RUBRIC_THRESHOLD} on {low}"))
