"""Operator-safe replay and human-gated live orchestration for Writing benchmarks."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

from writing_coach.languages.chinese.profile import (
    ERROR_CATEGORIES as CHINESE_ERROR_CATEGORIES,
    PROFILE as CHINESE_PROFILE,
)
from writing_coach.languages.english.profile import (
    ERROR_CATEGORIES as ENGLISH_ERROR_CATEGORIES,
    PROFILE as ENGLISH_PROFILE,
)
from writing_coach.writing_evaluation_benchmark import (
    RUBRIC_DIMENSIONS,
    WRITING_BENCHMARK_VERSION,
    WritingBenchmarkCase,
    build_benchmark_report,
    compare_pairwise_results,
    compare_target_level_results,
    evaluate_benchmark_result,
    validate_evaluator_label,
)
from writing_coach.writing_evaluation_benchmark_fixtures import WRITING_BENCHMARK_CASES
from writing_coach.writing_evaluator_contract import SHARED_RESULT_FIELDS


EXIT_SCOPE_PASSED = 0
EXIT_QUALITY_FAILURE = 1
EXIT_INPUT_OR_OPERATOR_ERROR = 2
EXIT_EXECUTION_FAILURE = 3
WRITING_EVALUATOR_CAPABILITY = "writing_evaluator"

LiveWritingEvaluator = Callable[[WritingBenchmarkCase], Mapping[str, Any]]


class BenchmarkRunnerInvalid(ValueError):
    """Replay input or operator selection is malformed."""


@dataclass(frozen=True)
class BenchmarkRunArtifacts:
    report: dict[str, Any]
    replay_capture: dict[str, Any] | None = None


_CORPUS_BY_ID = {case.case_id: case for case in WRITING_BENCHMARK_CASES}
_LANGUAGE_POLICY = {
    "en": {
        "error_categories": ENGLISH_ERROR_CATEGORIES,
        "levels": ENGLISH_PROFILE.levels,
    },
    "zh": {
        "error_categories": CHINESE_ERROR_CATEGORIES,
        "levels": CHINESE_PROFILE.levels,
    },
}
_REPLAY_ROOT_FIELDS = frozenset({"benchmark_version", "evaluator_label", "results"})
_NORMALIZED_RESULT_FIELD_TYPES = {
    "band_status": str,
    "cefr_estimate": str,
    "summary_vi": str,
    "strengths_vi": list,
    "priorities_vi": list,
    "strength_evidence": list,
    "errors": list,
}

if frozenset(_NORMALIZED_RESULT_FIELD_TYPES) != frozenset(SHARED_RESULT_FIELDS):
    raise RuntimeError("Writing benchmark runner normalized-result fields drifted from the shared contract")


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise BenchmarkRunnerInvalid("JSON contains a duplicate object key")
        output[key] = value
    return output


def load_replay_document(path: Path) -> dict[str, Any]:
    """Load UTF-8 replay JSON while rejecting duplicate object keys."""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BenchmarkRunnerInvalid("replay input could not be read") from exc
    try:
        value = json.loads(text, object_pairs_hook=_without_duplicate_keys)
    except (json.JSONDecodeError, BenchmarkRunnerInvalid) as exc:
        raise BenchmarkRunnerInvalid("replay input is not valid duplicate-free JSON") from exc
    if not isinstance(value, dict):
        raise BenchmarkRunnerInvalid("replay input root must be an object")
    return value


def _validate_normalized_result(case_id: str, result: Any) -> Mapping[str, Any]:
    if not isinstance(result, Mapping):
        raise BenchmarkRunnerInvalid("every normalized result must be an object")
    if any(dimension not in result for dimension in RUBRIC_DIMENSIONS):
        raise BenchmarkRunnerInvalid("normalized result is missing required rubric dimensions")
    missing_fields = [field for field in SHARED_RESULT_FIELDS if field not in result]
    if missing_fields:
        raise BenchmarkRunnerInvalid("normalized result is missing required shared fields")
    if any(
        not isinstance(result[field], expected_type)
        for field, expected_type in _NORMALIZED_RESULT_FIELD_TYPES.items()
    ):
        raise BenchmarkRunnerInvalid("normalized result has an invalid shared-field structure")
    if case_id not in _CORPUS_BY_ID:
        raise BenchmarkRunnerInvalid("result refers to an unknown benchmark case")
    return result


def validate_replay_document(document: Mapping[str, Any]) -> tuple[str, dict[str, Mapping[str, Any]]]:
    """Validate the versioned replay envelope without silently skipping data."""

    if set(document) != _REPLAY_ROOT_FIELDS:
        raise BenchmarkRunnerInvalid("replay input must contain only the documented root fields")
    if document.get("benchmark_version") != WRITING_BENCHMARK_VERSION:
        raise BenchmarkRunnerInvalid("replay benchmark_version does not match the current corpus")
    try:
        evaluator_label = validate_evaluator_label(document.get("evaluator_label"))
    except ValueError as exc:
        raise BenchmarkRunnerInvalid("replay evaluator_label is invalid") from exc

    raw_results = document.get("results")
    if not isinstance(raw_results, Mapping) or not raw_results:
        raise BenchmarkRunnerInvalid("replay results must be a non-empty object")
    if any(not isinstance(case_id, str) or case_id not in _CORPUS_BY_ID for case_id in raw_results):
        raise BenchmarkRunnerInvalid("replay input contains unknown benchmark case IDs")

    results = {
        case_id: _validate_normalized_result(case_id, result)
        for case_id, result in raw_results.items()
    }
    return evaluator_label, results


def select_benchmark_cases(
    *,
    available_case_ids: Sequence[str],
    case_ids: Sequence[str] = (),
    language: str | None = None,
) -> tuple[WritingBenchmarkCase, ...]:
    """Select cases deterministically in corpus order."""

    available = set(available_case_ids)
    if any(case_id not in _CORPUS_BY_ID for case_id in available):
        raise BenchmarkRunnerInvalid("available results contain an unknown benchmark case")
    requested = tuple(case_ids)
    if len(requested) != len(set(requested)):
        raise BenchmarkRunnerInvalid("a benchmark case was selected more than once")
    if any(case_id not in _CORPUS_BY_ID for case_id in requested):
        raise BenchmarkRunnerInvalid("an unknown benchmark case was selected")
    if requested and any(case_id not in available for case_id in requested):
        raise BenchmarkRunnerInvalid("a selected benchmark case has no available result")
    if language is not None and language not in _LANGUAGE_POLICY:
        raise BenchmarkRunnerInvalid("language must be en or zh")

    selected_ids = set(requested) if requested else available
    selected = tuple(
        case
        for case in WRITING_BENCHMARK_CASES
        if case.case_id in selected_ids and (language is None or case.language == language)
    )
    if not selected:
        raise BenchmarkRunnerInvalid("benchmark selection is empty")
    return selected


def _comparison_entry(kind: str, comparison: Any) -> dict[str, Any]:
    value = comparison.to_dict()
    return {
        "comparison_id": value["comparison_id"],
        "kind": kind,
        "status": "passed" if value["passed"] else "failed",
        "passed": value["passed"],
        "failed_checks": value["failed_checks"],
        "metrics": value["metrics"],
    }


def _not_executed_comparison(
    *,
    comparison_id: str,
    kind: str,
    missing_case_ids: Sequence[str],
    reason: str,
) -> dict[str, Any]:
    return {
        "comparison_id": comparison_id,
        "kind": kind,
        "status": "not_executed",
        "passed": None,
        "reason": reason,
        "missing_case_ids": list(missing_case_ids),
        "failed_checks": [],
        "metrics": {},
    }


def _run_comparisons(
    *,
    selected_cases: Sequence[WritingBenchmarkCase],
    results: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    selected_ids = {case.case_id for case in selected_cases}
    comparisons: list[dict[str, Any]] = []

    pair_groups: dict[str, list[WritingBenchmarkCase]] = defaultdict(list)
    target_groups: dict[str, list[WritingBenchmarkCase]] = defaultdict(list)
    for case in WRITING_BENCHMARK_CASES:
        if case.comparison_id:
            pair_groups[case.comparison_id].append(case)
        if case.target_pair_id:
            target_groups[case.target_pair_id].append(case)

    for comparison_id, cases in pair_groups.items():
        required_ids = {case.case_id for case in cases}
        if not required_ids.intersection(selected_ids):
            continue
        missing_selected = sorted(required_ids - selected_ids)
        if missing_selected:
            comparisons.append(
                _not_executed_comparison(
                    comparison_id=comparison_id,
                    kind="pairwise",
                    missing_case_ids=missing_selected,
                    reason="comparison pair is outside the selected scope",
                )
            )
            continue
        missing_results = sorted(case_id for case_id in required_ids if case_id not in results)
        if missing_results:
            comparisons.append(
                _not_executed_comparison(
                    comparison_id=comparison_id,
                    kind="pairwise",
                    missing_case_ids=missing_results,
                    reason="comparison result is unavailable",
                )
            )
            continue
        stronger = next(case for case in cases if case.comparison_role == "stronger")
        weaker = next(case for case in cases if case.comparison_role == "weaker")
        comparisons.append(
            _comparison_entry(
                "pairwise",
                compare_pairwise_results(
                    stronger,
                    results[stronger.case_id],
                    weaker,
                    results[weaker.case_id],
                ),
            )
        )

    for comparison_id, cases in target_groups.items():
        required_ids = {case.case_id for case in cases}
        if not required_ids.intersection(selected_ids):
            continue
        missing_selected = sorted(required_ids - selected_ids)
        if missing_selected:
            comparisons.append(
                _not_executed_comparison(
                    comparison_id=comparison_id,
                    kind="target_level",
                    missing_case_ids=missing_selected,
                    reason="target-level pair is outside the selected scope",
                )
            )
            continue
        missing_results = sorted(case_id for case_id in required_ids if case_id not in results)
        if missing_results:
            comparisons.append(
                _not_executed_comparison(
                    comparison_id=comparison_id,
                    kind="target_level",
                    missing_case_ids=missing_results,
                    reason="target-level result is unavailable",
                )
            )
            continue
        first, second = cases
        comparisons.append(
            _comparison_entry(
                "target_level",
                compare_target_level_results(
                    first,
                    results[first.case_id],
                    second,
                    results[second.case_id],
                    declared_levels=_LANGUAGE_POLICY[first.language]["levels"],
                ),
            )
        )
    return comparisons


def _failure_summary(
    cases: Sequence[Mapping[str, Any]],
    comparisons: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for case in cases:
        findings = case.get("findings")
        if isinstance(findings, Mapping):
            for finding in findings.get("failed_checks", []):
                if isinstance(finding, Mapping) and isinstance(finding.get("check"), str):
                    counts[finding["check"]] += 1
    for comparison in comparisons:
        for finding in comparison.get("failed_checks", []):
            if isinstance(finding, Mapping) and isinstance(finding.get("check"), str):
                counts[finding["check"]] += 1
    return dict(sorted(counts.items()))


def evaluate_selected_results(
    *,
    evaluator_label: str,
    mode: str,
    selected_cases: Sequence[WritingBenchmarkCase],
    results: Mapping[str, Mapping[str, Any]],
    timestamp: str | None = None,
    execution_failures: Sequence[Mapping[str, str]] = (),
) -> dict[str, Any]:
    """Evaluate selected normalized results and emit one aggregate report."""

    validate_evaluator_label(evaluator_label)
    run_timestamp = timestamp or _timestamp_now()
    case_reports: list[dict[str, Any]] = []
    for case in selected_cases:
        result = results.get(case.case_id)
        if result is None:
            case_reports.append(
                {
                    "case_id": case.case_id,
                    "language": case.language,
                    "status": "not_executed",
                    "passed": None,
                    "reason": "normalized result is unavailable",
                }
            )
            continue
        policy = _LANGUAGE_POLICY[case.language]
        evaluation = evaluate_benchmark_result(
            case,
            result,
            allowed_error_categories=policy["error_categories"],
        )
        case_report = build_benchmark_report(
            timestamp=run_timestamp,
            evaluator_label=evaluator_label,
            case=case,
            normalized_result=result,
            evaluation=evaluation,
        )
        case_report["status"] = "passed" if evaluation.passed else "failed"
        case_report["passed"] = evaluation.passed
        case_reports.append(case_report)

    comparisons = _run_comparisons(selected_cases=selected_cases, results=results)
    selected_ids = {case.case_id for case in selected_cases}
    full_corpus = selected_ids == set(_CORPUS_BY_ID)
    passed_cases = sum(case.get("passed") is True for case in case_reports)
    failed_cases = sum(case.get("passed") is False for case in case_reports)
    executed_comparisons = [item for item in comparisons if item["status"] != "not_executed"]
    failed_comparisons = sum(item["passed"] is False for item in executed_comparisons)
    execution_failure_count = len(execution_failures)
    passed = failed_cases == 0 and failed_comparisons == 0 and execution_failure_count == 0
    status = (
        "execution_failure"
        if execution_failure_count
        else "passed"
        if passed
        else "quality_failure"
    )
    return {
        "benchmark_version": WRITING_BENCHMARK_VERSION,
        "timestamp": run_timestamp,
        "evaluator_label": evaluator_label,
        "mode": mode,
        "capability": WRITING_EVALUATOR_CAPABILITY,
        "scope": "full" if full_corpus else "partial",
        "corpus_case_count": len(WRITING_BENCHMARK_CASES),
        "selected_case_count": len(selected_cases),
        "missing_case_count": len(WRITING_BENCHMARK_CASES) - len(selected_cases),
        "passed_case_count": passed_cases,
        "failed_case_count": failed_cases,
        "not_executed_case_count": len(selected_cases) - passed_cases - failed_cases,
        "comparison_count": len(executed_comparisons),
        "comparison_total_count": len(comparisons),
        "not_executed_comparison_count": len(comparisons) - len(executed_comparisons),
        "execution_failure_count": execution_failure_count,
        "status": status,
        "passed": passed,
        "full_corpus_certified": bool(full_corpus and passed),
        "quality_failure_counts": _failure_summary(case_reports, comparisons),
        "cases": case_reports,
        "comparisons": comparisons,
        "execution_failures": [dict(item) for item in execution_failures],
    }


def run_replay(
    document: Mapping[str, Any],
    *,
    case_ids: Sequence[str] = (),
    language: str | None = None,
    timestamp: str | None = None,
) -> BenchmarkRunArtifacts:
    evaluator_label, results = validate_replay_document(document)
    selected = select_benchmark_cases(
        available_case_ids=tuple(results),
        case_ids=case_ids,
        language=language,
    )
    return BenchmarkRunArtifacts(
        report=evaluate_selected_results(
            evaluator_label=evaluator_label,
            mode="replay",
            selected_cases=selected,
            results=results,
            timestamp=timestamp,
        )
    )


def run_live_with_evaluator(
    evaluator: LiveWritingEvaluator,
    *,
    evaluator_label: str,
    case_ids: Sequence[str] = (),
    language: str | None = None,
    timestamp: str | None = None,
) -> BenchmarkRunArtifacts:
    """Run each selected case once through one injected product evaluator.

    The caller owns the real application adapter.  This module never imports a
    provider, discovers a model, retries, or falls back to another evaluator.
    """

    validate_evaluator_label(evaluator_label)
    selected = select_benchmark_cases(
        available_case_ids=tuple(_CORPUS_BY_ID),
        case_ids=case_ids,
        language=language,
    )
    results: dict[str, Mapping[str, Any]] = {}
    execution_failures: list[dict[str, str]] = []
    for case in selected:
        try:
            result = evaluator(case)
        except Exception as exc:
            execution_failures.append(
                {
                    "case_id": case.case_id,
                    "failure_kind": "provider_or_execution_failure",
                    "error_class": type(exc).__name__,
                    "message": "Writing evaluator execution failed; no fallback was attempted.",
                }
            )
            break
        try:
            results[case.case_id] = _validate_normalized_result(case.case_id, result)
        except BenchmarkRunnerInvalid:
            execution_failures.append(
                {
                    "case_id": case.case_id,
                    "failure_kind": "malformed_result",
                    "error_class": "BenchmarkRunnerInvalid",
                    "message": "Writing evaluator returned a malformed normalized result.",
                }
            )
            break

    report = evaluate_selected_results(
        evaluator_label=evaluator_label,
        mode="live",
        selected_cases=selected,
        results=results,
        timestamp=timestamp,
        execution_failures=execution_failures,
    )
    captured_results = {
        item["case"]["case_id"]: item["normalized_result"]
        for item in report["cases"]
        if item.get("status") in {"passed", "failed"}
    }
    capture = {
        "benchmark_version": WRITING_BENCHMARK_VERSION,
        "evaluator_label": evaluator_label,
        "results": captured_results,
    }
    return BenchmarkRunArtifacts(report=report, replay_capture=capture)


def write_json_file(path: Path, payload: Mapping[str, Any], *, force: bool) -> None:
    """Write deterministic UTF-8 JSON without implicit overwrite."""

    mode = "w" if force else "x"
    try:
        with path.open(mode, encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise BenchmarkRunnerInvalid("output already exists; use --force to overwrite") from exc
    except OSError as exc:
        raise BenchmarkRunnerInvalid("output file could not be written") from exc


def _ensure_output_available(paths: Sequence[Path | None], *, force: bool) -> None:
    destinations = [path for path in paths if path is not None]
    try:
        resolved = [os.path.normcase(str(path.expanduser().resolve(strict=False))) for path in destinations]
    except OSError as exc:
        raise BenchmarkRunnerInvalid("output destination could not be resolved") from exc
    if len(resolved) != len(set(resolved)):
        raise BenchmarkRunnerInvalid("output and capture must resolve to distinct destinations")
    if not force and any(path.exists() for path in destinations):
        raise BenchmarkRunnerInvalid("output already exists; use --force to overwrite")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay or prepare a human-gated Writing benchmark run.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--input", type=Path, help="Versioned replay JSON input.")
    mode.add_argument("--live", action="store_true", help="Request the human-gated live path.")
    parser.add_argument("--output", type=Path, help="Aggregate report path; stdout when omitted.")
    parser.add_argument("--capture", type=Path, help="Live normalized-result capture for later replay.")
    parser.add_argument("--force", action="store_true", help="Explicitly overwrite output/capture files.")
    parser.add_argument("--case", action="append", default=[], dest="case_ids")
    parser.add_argument("--language", choices=("en", "zh"))
    parser.add_argument("--evaluator-label", help="Safe live evaluator/provider/model identifier.")
    parser.add_argument("--acknowledge-provider-cost", action="store_true")
    parser.add_argument("--yes", action="store_true", help="Final non-interactive live confirmation.")
    return parser


def _operator_error(message: str) -> int:
    print(
        json.dumps(
            {"ok": False, "status": "operator_or_input_error", "message": message},
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    return EXIT_INPUT_OR_OPERATOR_ERROR


def cli_main(
    argv: Sequence[str] | None = None,
    *,
    live_evaluator: LiveWritingEvaluator | None = None,
    timestamp: str | None = None,
) -> int:
    """CLI entry point; a real live adapter must be injected by approved integration."""

    parser = build_argument_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    try:
        if args.input is None and not args.live:
            if args.acknowledge_provider_cost or args.yes:
                return _operator_error("live acknowledgement flags require --live")
            parser.print_usage(sys.stderr)
            return _operator_error("choose replay with --input or explicitly request --live")

        if args.input is not None:
            if args.acknowledge_provider_cost or args.yes or args.evaluator_label or args.capture:
                return _operator_error("live-only flags cannot be used in replay mode")
            _ensure_output_available((args.output,), force=args.force)
            document = load_replay_document(args.input)
            artifacts = run_replay(
                document,
                case_ids=args.case_ids,
                language=args.language,
                timestamp=timestamp,
            )
        else:
            if not args.acknowledge_provider_cost or not args.yes:
                return _operator_error(
                    "live mode requires --live, --acknowledge-provider-cost, and --yes"
                )
            if not args.evaluator_label:
                return _operator_error("live mode requires --evaluator-label")
            try:
                validate_evaluator_label(args.evaluator_label)
            except ValueError:
                return _operator_error("live evaluator label is invalid")
            _ensure_output_available((args.output, args.capture), force=args.force)
            selected = select_benchmark_cases(
                available_case_ids=tuple(_CORPUS_BY_ID),
                case_ids=args.case_ids,
                language=args.language,
            )
            preflight = {
                "mode": "live",
                "scope": "full" if len(selected) == len(WRITING_BENCHMARK_CASES) else "partial",
                "selected_case_count": len(selected),
                "maximum_live_requests": len(selected),
                "capability": WRITING_EVALUATOR_CAPABILITY,
            }
            print(json.dumps(preflight, sort_keys=True), file=sys.stderr)
            if live_evaluator is None:
                return _operator_error(
                    "live evaluator integration is unavailable; no provider request was made"
                )
            artifacts = run_live_with_evaluator(
                live_evaluator,
                evaluator_label=args.evaluator_label,
                case_ids=args.case_ids,
                language=args.language,
                timestamp=timestamp,
            )

        if args.output:
            write_json_file(args.output, artifacts.report, force=args.force)
        else:
            print(json.dumps(artifacts.report, ensure_ascii=False, indent=2, sort_keys=True))
        if args.capture and artifacts.replay_capture is not None:
            write_json_file(args.capture, artifacts.replay_capture, force=args.force)

        if artifacts.report["status"] == "execution_failure":
            return EXIT_EXECUTION_FAILURE
        return EXIT_SCOPE_PASSED if artifacts.report["passed"] else EXIT_QUALITY_FAILURE
    except BenchmarkRunnerInvalid as exc:
        return _operator_error(str(exc))
