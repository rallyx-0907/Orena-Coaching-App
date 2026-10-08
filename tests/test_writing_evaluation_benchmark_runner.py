from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

import pytest
import requests

from writing_coach.ai import providers as provider_module
from writing_coach.writing_evaluation_benchmark import WRITING_BENCHMARK_VERSION
from writing_coach.writing_evaluation_benchmark_fixtures import (
    WRITING_BENCHMARK_CASES,
    benchmark_case,
    known_failing_result,
    known_passing_result,
)
from writing_coach.writing_evaluation_benchmark_runner import (
    EXIT_EXECUTION_FAILURE,
    EXIT_INPUT_OR_OPERATOR_ERROR,
    EXIT_QUALITY_FAILURE,
    EXIT_SCOPE_PASSED,
    WRITING_EVALUATOR_CAPABILITY,
    BenchmarkRunnerInvalid,
    cli_main,
    load_replay_document,
    run_live_with_evaluator,
    run_replay,
)


TIMESTAMP = "2026-08-14T00:00:00Z"
RUNBOOK = Path(__file__).resolve().parents[1] / "docs" / "operations" / "WRITING_EVALUATION_BENCHMARK.md"


def _document(*, case_ids=None, failing_case_id=None, evaluator_label="fixture:model-v1"):
    selected_ids = case_ids or [case.case_id for case in WRITING_BENCHMARK_CASES]
    results = {}
    for case_id in selected_ids:
        case = benchmark_case(case_id)
        results[case_id] = (
            known_failing_result(case)
            if case_id == failing_case_id
            else known_passing_result(case)
        )
    return {
        "benchmark_version": WRITING_BENCHMARK_VERSION,
        "evaluator_label": evaluator_label,
        "results": results,
    }


def _write_document(path: Path, document) -> Path:
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def _stdout_json(capsys):
    output = capsys.readouterr()
    return json.loads(output.out), output


def test_full_valid_replay_runs_all_cases_and_comparisons():
    artifacts = run_replay(_document(), timestamp=TIMESTAMP)
    report = artifacts.report

    assert report["mode"] == "replay"
    assert report["scope"] == "full"
    assert report["selected_case_count"] == 26
    assert report["missing_case_count"] == 0
    assert report["passed_case_count"] == 26
    assert report["failed_case_count"] == 0
    assert report["comparison_count"] == 4
    assert report["not_executed_comparison_count"] == 0
    assert report["passed"] is True
    assert report["full_corpus_certified"] is True
    assert json.loads(json.dumps(report, ensure_ascii=False)) == report


def test_known_failing_fixture_is_a_quality_failure_not_execution_failure():
    artifacts = run_replay(
        _document(case_ids=["en-evidence-integrity"], failing_case_id="en-evidence-integrity"),
        timestamp=TIMESTAMP,
    )
    report = artifacts.report
    assert report["status"] == "quality_failure"
    assert report["failed_case_count"] == 1
    assert report["execution_failure_count"] == 0
    assert report["quality_failure_counts"]["evidence_precision"] >= 1


@pytest.mark.parametrize(
    ("case_id", "foreign_category"),
    [
        ("en-task-one-reason", "word_order"),
        ("zh-task-one-reason", "agreement"),
    ],
)
def test_replay_uses_each_language_declared_error_taxonomy(case_id, foreign_category):
    document = _document(case_ids=[case_id])
    case = benchmark_case(case_id)
    document["results"][case_id]["errors"] = [
        {
            "category": foreign_category,
            "fragment": case.learner_text,
            "explanation_vi": "Phân loại không thuộc ngôn ngữ này.",
            "suggestion": f"Revised: {case.learner_text}",
            "mini_rule_vi": "Dùng đúng hệ phân loại.",
            "confidence": 0.9,
        }
    ]

    report = run_replay(document, timestamp=TIMESTAMP).report
    assert report["passed"] is False
    assert report["quality_failure_counts"]["category_validity"] == 1


def test_replay_rejects_version_mismatch_unknown_case_and_malformed_result():
    version_mismatch = _document(case_ids=["en-clean-agreement"])
    version_mismatch["benchmark_version"] = 999
    with pytest.raises(BenchmarkRunnerInvalid, match="benchmark_version"):
        run_replay(version_mismatch)

    unknown = _document(case_ids=["en-clean-agreement"])
    unknown["results"]["unknown-case"] = unknown["results"].pop("en-clean-agreement")
    with pytest.raises(BenchmarkRunnerInvalid, match="unknown benchmark case"):
        run_replay(unknown)

    malformed = _document(case_ids=["en-clean-agreement"])
    malformed["results"]["en-clean-agreement"] = {"grammar": 80}
    with pytest.raises(BenchmarkRunnerInvalid, match="rubric dimensions"):
        run_replay(malformed)


def test_structurally_incomplete_replay_is_input_error_not_quality_failure(tmp_path, capsys):
    document = _document(case_ids=["en-clean-agreement"])
    del document["results"]["en-clean-agreement"]["summary_vi"]
    input_path = _write_document(tmp_path / "incomplete.json", document)

    with pytest.raises(BenchmarkRunnerInvalid, match="required shared fields"):
        run_replay(document)
    code = cli_main(["--input", str(input_path)], timestamp=TIMESTAMP)
    output = capsys.readouterr()

    assert code == EXIT_INPUT_OR_OPERATOR_ERROR
    failure = json.loads(output.err)
    assert failure["status"] == "operator_or_input_error"
    assert "quality_failure" not in output.err


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("cefr_estimate", []),
        ("summary_vi", []),
        ("strengths_vi", "not-a-list"),
        ("priorities_vi", "not-a-list"),
        ("strength_evidence", "not-a-list"),
        ("errors", "not-a-list"),
    ],
)
def test_replay_rejects_invalid_shared_field_structure(field, invalid_value):
    document = _document(case_ids=["en-clean-agreement"])
    document["results"]["en-clean-agreement"][field] = invalid_value

    with pytest.raises(BenchmarkRunnerInvalid, match="invalid shared-field structure"):
        run_replay(document)


def test_replay_loader_rejects_duplicate_case_ids(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text(
        '{"benchmark_version":1,"evaluator_label":"fixture:v1","results":'
        '{"en-clean-agreement":{},"en-clean-agreement":{}}}',
        encoding="utf-8",
    )
    with pytest.raises(BenchmarkRunnerInvalid, match="duplicate-free"):
        load_replay_document(path)


def test_partial_case_selection_is_explicit_and_missing_pair_is_not_pass():
    report = run_replay(
        _document(),
        case_ids=["en-clean-agreement"],
        timestamp=TIMESTAMP,
    ).report

    assert report["scope"] == "partial"
    assert report["selected_case_count"] == 1
    assert report["missing_case_count"] == 25
    assert report["passed"] is True
    assert report["full_corpus_certified"] is False
    assert report["comparison_total_count"] == 1
    comparison = report["comparisons"][0]
    assert comparison["status"] == "not_executed"
    assert comparison["passed"] is None
    assert comparison["missing_case_ids"] == ["en-obvious-agreement"]


def test_language_selection_is_partial_and_never_full_certification():
    report = run_replay(_document(), language="zh", timestamp=TIMESTAMP).report
    assert report["scope"] == "partial"
    assert report["selected_case_count"] == 13
    assert report["missing_case_count"] == 13
    assert report["passed"] is True
    assert report["full_corpus_certified"] is False


def test_cli_exit_codes_distinguish_pass_quality_and_input_failure(tmp_path, capsys):
    passing_path = _write_document(
        tmp_path / "passing.json",
        _document(case_ids=["en-evidence-integrity"]),
    )
    failing_path = _write_document(
        tmp_path / "failing.json",
        _document(
            case_ids=["en-evidence-integrity"],
            failing_case_id="en-evidence-integrity",
        ),
    )
    malformed_path = _write_document(
        tmp_path / "malformed.json",
        {
            "benchmark_version": 1,
            "evaluator_label": "fixture:model-v1",
            "results": {"en-clean-agreement": "not-an-object"},
        },
    )

    assert cli_main(["--input", str(passing_path)], timestamp=TIMESTAMP) == EXIT_SCOPE_PASSED
    capsys.readouterr()
    assert cli_main(["--input", str(failing_path)], timestamp=TIMESTAMP) == EXIT_QUALITY_FAILURE
    capsys.readouterr()
    assert cli_main(["--input", str(malformed_path)], timestamp=TIMESTAMP) == EXIT_INPUT_OR_OPERATOR_ERROR


def test_report_excludes_arbitrary_secret_shaped_input_fields():
    document = _document(case_ids=["en-evidence-integrity"])
    document["results"]["en-evidence-integrity"].update(
        {"api_key": "super-secret", "authorization": "Bearer super-secret"}
    )
    report = run_replay(document, timestamp=TIMESTAMP).report
    encoded = json.dumps(report, ensure_ascii=False)
    assert "api_key" not in encoded
    assert "authorization" not in encoded.casefold()
    assert "super-secret" not in encoded


def test_output_does_not_overwrite_without_force_and_force_is_explicit(tmp_path, capsys):
    input_path = _write_document(
        tmp_path / "input.json",
        _document(case_ids=["en-evidence-integrity"]),
    )
    output_path = tmp_path / "report.json"
    output_path.write_text("operator-owned", encoding="utf-8")

    code = cli_main(
        ["--input", str(input_path), "--output", str(output_path)],
        timestamp=TIMESTAMP,
    )
    assert code == EXIT_INPUT_OR_OPERATOR_ERROR
    assert output_path.read_text(encoding="utf-8") == "operator-owned"
    capsys.readouterr()

    code = cli_main(
        ["--input", str(input_path), "--output", str(output_path), "--force"],
        timestamp=TIMESTAMP,
    )
    assert code == EXIT_SCOPE_PASSED
    assert json.loads(output_path.read_text(encoding="utf-8"))["status"] == "passed"


@pytest.mark.parametrize("force", [False, True])
def test_output_capture_collision_fails_before_live_calls_without_mutation(tmp_path, capsys, force):
    alias_parent = tmp_path / "alias"
    alias_parent.mkdir()
    output_path = tmp_path / "artifact.json"
    capture_alias = alias_parent / ".." / "artifact.json"
    evaluator = FakeEvaluator()
    arguments = [
        "--live",
        "--acknowledge-provider-cost",
        "--yes",
        "--evaluator-label",
        "fixture:model-v1",
        "--case",
        "en-clean-agreement",
        "--output",
        str(output_path),
        "--capture",
        str(capture_alias),
    ]
    if force:
        arguments.append("--force")

    code = cli_main(arguments, live_evaluator=evaluator, timestamp=TIMESTAMP)
    output = capsys.readouterr()

    assert code == EXIT_INPUT_OR_OPERATOR_ERROR
    assert evaluator.calls == []
    assert not output_path.exists()
    assert "distinct destinations" in output.err


def test_distinct_output_and_capture_paths_receive_intended_live_artifacts(tmp_path, capsys):
    output_path = tmp_path / "report.json"
    capture_path = tmp_path / "capture.json"
    evaluator = FakeEvaluator()
    code = cli_main(
        [
            "--live",
            "--acknowledge-provider-cost",
            "--yes",
            "--evaluator-label",
            "fixture:model-v1",
            "--case",
            "en-clean-agreement",
            "--output",
            str(output_path),
            "--capture",
            str(capture_path),
        ],
        live_evaluator=evaluator,
        timestamp=TIMESTAMP,
    )
    capsys.readouterr()

    report = json.loads(output_path.read_text(encoding="utf-8"))
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    assert code == EXIT_SCOPE_PASSED
    assert [case.case_id for case in evaluator.calls] == ["en-clean-agreement"]
    assert report["mode"] == "live"
    assert report["status"] == "passed"
    assert set(capture) == {"benchmark_version", "evaluator_label", "results"}
    assert set(capture["results"]) == {"en-clean-agreement"}


class FakeEvaluator:
    def __init__(self):
        self.calls = []

    def __call__(self, case):
        self.calls.append(case)
        return known_passing_result(case)


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--live", "--evaluator-label", "fixture:model-v1"],
        ["--acknowledge-provider-cost"],
        ["--live", "--acknowledge-provider-cost", "--evaluator-label", "fixture:model-v1"],
    ],
)
def test_live_safety_flags_are_fail_closed_and_make_zero_calls(arguments, capsys):
    evaluator = FakeEvaluator()
    assert cli_main(arguments, live_evaluator=evaluator, timestamp=TIMESTAMP) == EXIT_INPUT_OR_OPERATOR_ERROR
    assert evaluator.calls == []
    capsys.readouterr()


def test_standalone_live_path_has_no_implicit_real_integration(capsys):
    code = cli_main(
        [
            "--live",
            "--acknowledge-provider-cost",
            "--yes",
            "--evaluator-label",
            "fixture:model-v1",
            "--case",
            "en-clean-agreement",
        ],
        timestamp=TIMESTAMP,
    )
    assert code == EXIT_INPUT_OR_OPERATOR_ERROR
    output = capsys.readouterr()
    assert "no provider request was made" in output.err


def test_fully_confirmed_live_fake_calls_once_per_case_and_reuses_results(capsys):
    evaluator = FakeEvaluator()
    case_ids = [
        "en-clean-agreement",
        "en-obvious-agreement",
        "en-target-a2",
        "en-target-c1",
    ]
    arguments = [
        "--live",
        "--acknowledge-provider-cost",
        "--yes",
        "--evaluator-label",
        "fixture:model-v1",
    ]
    for case_id in case_ids:
        arguments.extend(["--case", case_id])

    assert cli_main(arguments, live_evaluator=evaluator, timestamp=TIMESTAMP) == EXIT_SCOPE_PASSED
    report, output = _stdout_json(capsys)
    preflight = json.loads(output.err)
    assert preflight["selected_case_count"] == 4
    assert preflight["scope"] == "partial"
    assert preflight["maximum_live_requests"] == 4
    assert preflight["capability"] == "writing_evaluator"
    assert [case.case_id for case in evaluator.calls] == case_ids
    assert report["comparison_count"] == 2
    assert {item["kind"] for item in report["comparisons"]} == {"pairwise", "target_level"}
    assert report["passed"] is True


def test_live_execution_failure_is_separate_secret_safe_and_never_falls_back(capsys):
    class FailingEvaluator:
        def __init__(self):
            self.calls = 0
            self.fallback_calls = 0

        def __call__(self, _case):
            self.calls += 1
            raise RuntimeError("provider URL token=super-secret")

        def fallback(self, _case):
            self.fallback_calls += 1

    evaluator = FailingEvaluator()
    code = cli_main(
        [
            "--live",
            "--acknowledge-provider-cost",
            "--yes",
            "--evaluator-label",
            "fixture:model-v1",
            "--case",
            "en-clean-agreement",
        ],
        live_evaluator=evaluator,
        timestamp=TIMESTAMP,
    )
    assert code == EXIT_EXECUTION_FAILURE
    report, _output = _stdout_json(capsys)
    assert evaluator.calls == 1
    assert evaluator.fallback_calls == 0
    assert report["status"] == "execution_failure"
    assert report["failed_case_count"] == 0
    assert report["execution_failure_count"] == 1
    assert report["execution_failures"][0]["failure_kind"] == "provider_or_execution_failure"
    assert "super-secret" not in json.dumps(report)


def test_live_malformed_result_is_execution_failure_not_quality_failure():
    incomplete = known_passing_result(benchmark_case("en-clean-agreement"))
    del incomplete["errors"]
    artifacts = run_live_with_evaluator(
        lambda _case: incomplete,
        evaluator_label="fixture:model-v1",
        case_ids=["en-clean-agreement"],
        timestamp=TIMESTAMP,
    )
    assert artifacts.report["status"] == "execution_failure"
    assert artifacts.report["execution_failures"][0]["failure_kind"] == "malformed_result"
    assert artifacts.report["failed_case_count"] == 0
    assert artifacts.report["quality_failure_counts"] == {}


def test_one_live_evaluator_abstraction_serves_en_and_zh_without_network(monkeypatch):
    network_calls = Counter()

    def unexpected(*_args, **_kwargs):
        network_calls["network_or_discovery"] += 1
        raise AssertionError("network/provider discovery must not run")

    monkeypatch.setattr(requests, "get", unexpected)
    monkeypatch.setattr(requests, "post", unexpected)
    monkeypatch.setattr(provider_module, "build_providers", unexpected)
    evaluator = FakeEvaluator()

    artifacts = run_live_with_evaluator(
        evaluator,
        evaluator_label="fixture:model-v1",
        case_ids=["en-beginner-clear", "zh-beginner-clear"],
        timestamp=TIMESTAMP,
    )

    assert [case.language for case in evaluator.calls] == ["en", "zh"]
    assert network_calls == Counter()
    assert artifacts.report["capability"] == WRITING_EVALUATOR_CAPABILITY == "writing_evaluator"
    assert artifacts.report["passed"] is True


def test_live_capture_uses_replay_format_and_can_be_replayed():
    evaluator = FakeEvaluator()
    artifacts = run_live_with_evaluator(
        evaluator,
        evaluator_label="fixture:model-v1",
        case_ids=["en-beginner-clear", "zh-beginner-clear"],
        timestamp=TIMESTAMP,
    )
    capture = artifacts.replay_capture
    assert capture is not None
    assert set(capture) == {"benchmark_version", "evaluator_label", "results"}
    assert run_replay(capture, timestamp=TIMESTAMP).report["passed"] is True


def test_runbook_documents_human_gate_single_capability_and_failure_taxonomy():
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "--live --acknowledge-provider-cost --yes --evaluator-label" in text
    assert "maximum_live_requests" in text
    assert "writing_evaluator" in text
    assert "writing_evaluator_en" not in text
    assert "writing_evaluator_zh" not in text
    assert "no provider-to-provider fallback" in text.casefold()
    assert "execution failure" in text.casefold()
    assert "quality failure" in text.casefold()
    assert "does not authorize" in text.casefold()
