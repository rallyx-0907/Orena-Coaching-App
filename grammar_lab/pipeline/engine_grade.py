"""``engine-grade`` (human, 2026-09-29, item 4): grade a level with the writing engine, but only what the
engine is good evidence for -- ``common_mistakes`` (the engine must catch each ``wrong`` under its
``error_tag``, and read each ``right`` clean) and ``quick_practice`` (each option filled into the blank:
the correct one clean, each wrong one caught under the tag it declares).

Run before a reviewed level goes into the app, never during generation, and never without the estimate:
``plan`` counts the engine calls and ``estimate_cost_usd`` prices them (Gemini bills every call the
engine makes for the evaluator).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from grammar_lab.pipeline.evaluator_client import EvaluatorClient
from grammar_lab.pipeline.llm_client import PRICING, LLMUsage
from grammar_lab.pipeline.verify import VerifyReport, _verify_quick_practice_options, verify_common_mistakes

# What one engine call costs, from the sandbox's own token use: about 2 000 tokens in, 500 out.
ENGINE_CALL_TOKENS = (2000, 500)
ENGINE_MODEL = "gemini-3.5-flash-lite"


@dataclass(frozen=True)
class GradePlan:
    points: int
    calls: int
    cost_usd: float | None
    per_point: dict[str, int]


def calls_for(point: dict[str, Any]) -> int:
    mistakes = 2 * len(point.get("common_mistakes", []))  # wrong + right
    options = sum(len(item["options"]) for item in point.get("quick_practice", []) if item["q"].count("___") == 1)
    return mistakes + options


def estimate_cost_usd(calls: int, model: str = ENGINE_MODEL) -> float | None:
    if model not in PRICING:
        return None
    one = LLMUsage(*ENGINE_CALL_TOKENS).cost_usd(model)
    return None if one is None else calls * one


def plan(points: dict[str, dict[str, Any]], model: str = ENGINE_MODEL) -> GradePlan:
    per_point = {point_id: calls_for(point) for point_id, point in points.items()}
    calls = sum(per_point.values())
    return GradePlan(len(points), calls, estimate_cost_usd(calls, model), per_point)


def grade_point(point: dict[str, Any], *, evaluator: EvaluatorClient) -> VerifyReport:
    report = VerifyReport(point_id=point["id"])
    target_cefr = point["level"]["value"] if point["level"]["framework"] == "cefr" else None
    verify_common_mistakes(point, evaluator=evaluator, target_cefr=target_cefr, report=report)
    for index, item in enumerate(point.get("quick_practice", [])):
        report.checked_quick_practice += 1
        _verify_quick_practice_options(
            item, f"quick_practice[{index}]", evaluator=evaluator, target_cefr=target_cefr, report=report,
        )
    return report
