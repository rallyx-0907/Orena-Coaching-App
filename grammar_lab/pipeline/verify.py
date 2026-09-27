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

FLAG_PREFIX = "verify:"


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

    return report
