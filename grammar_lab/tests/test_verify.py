from __future__ import annotations

import json
from pathlib import Path

import httpx

from grammar_lab.pipeline.evaluator_client import EvaluatorClient
from grammar_lab.pipeline.llm_client import LLMClient
from grammar_lab.pipeline.verify import verify_point
from grammar_lab.tests.conftest import en_point


def alpha_point() -> dict:
    # en_point() already carries one pitfall (agreement, "He go to school." / "He goes to school.")
    # and one check item (options=["go", "goes"], answer=1) -- see conftest.py.
    return en_point("en.alpha", "A1", 1)


def evaluator_transport(tagged: dict[str, list[str]]) -> httpx.MockTransport:
    """``tagged``: exact sentence text -> list of error categories the fake engine returns."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        categories = tagged.get(body["text"], [])
        errors = [{"category": c, "fragment": body["text"]} for c in categories]
        return httpx.Response(200, json={"errors": errors})

    return httpx.MockTransport(handler)


def blind_solve_transport(answer_index: int) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({"answer_index": answer_index})}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        })
    return httpx.MockTransport(handler)


def make_evaluator(tagged: dict[str, list[str]]) -> EvaluatorClient:
    return EvaluatorClient("http://sandbox.test", transport=evaluator_transport(tagged))


def make_blind_solver(tmp_path: Path, answer_index: int) -> LLMClient:
    return LLMClient("openai", "gpt-6-luna", api_key="k", cache_dir=tmp_path,
                      transport=blind_solve_transport(answer_index))


def test_all_checks_pass_produces_no_flags(tmp_path: Path) -> None:
    point = alpha_point()
    tagged = {
        "He go to school.": ["agreement"],
        "He goes to school.": [],
        "She works in a bank.": [],
    }
    report = verify_point(point, evaluator=make_evaluator(tagged), blind_solver=make_blind_solver(tmp_path, 1))
    assert report.ok, report.flags
    assert report.checked_pitfalls == 1
    assert report.checked_examples == 1
    assert report.checked_checks == 1


def test_pitfall_not_caught_is_flagged(tmp_path: Path) -> None:
    point = alpha_point()
    tagged = {"He go to school.": [], "He goes to school.": [], "She works in a bank.": []}
    report = verify_point(point, evaluator=make_evaluator(tagged), blind_solver=make_blind_solver(tmp_path, 1))
    assert "pitfall_not_caught" in report.codes()


def test_right_sentence_flagged_by_engine_is_a_verify_issue(tmp_path: Path) -> None:
    point = alpha_point()
    tagged = {
        "He go to school.": ["agreement"],
        "He goes to school.": ["punctuation"],  # engine still unhappy with the "corrected" sentence
        "She works in a bank.": [],
    }
    report = verify_point(point, evaluator=make_evaluator(tagged), blind_solver=make_blind_solver(tmp_path, 1))
    assert "pitfall_right_flagged" in report.codes()


def test_dirty_example_is_flagged(tmp_path: Path) -> None:
    point = alpha_point()
    tagged = {
        "He go to school.": ["agreement"],
        "He goes to school.": [],
        "She works in a bank.": ["word_choice"],
    }
    report = verify_point(point, evaluator=make_evaluator(tagged), blind_solver=make_blind_solver(tmp_path, 1))
    assert "example_not_clean" in report.codes()


def test_blind_solve_wrong_answer_is_flagged(tmp_path: Path) -> None:
    point = alpha_point()
    tagged = {"He go to school.": ["agreement"], "He goes to school.": [], "She works in a bank.": []}
    report = verify_point(point, evaluator=make_evaluator(tagged), blind_solver=make_blind_solver(tmp_path, 0))
    assert "blind_solve_wrong" in report.codes()


def test_blind_solve_ambiguous_is_flagged(tmp_path: Path) -> None:
    point = alpha_point()
    tagged = {"He go to school.": ["agreement"], "He goes to school.": [], "She works in a bank.": []}
    report = verify_point(point, evaluator=make_evaluator(tagged), blind_solver=make_blind_solver(tmp_path, -1))
    assert "blind_solve_ambiguous" in report.codes()


def test_evaluator_connection_failure_is_flagged_not_raised(tmp_path: Path) -> None:
    point = alpha_point()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    evaluator = EvaluatorClient("http://sandbox.test", transport=httpx.MockTransport(handler))
    report = verify_point(point, evaluator=evaluator, blind_solver=make_blind_solver(tmp_path, 1))
    assert "evaluator_error" in report.codes()
    assert not report.ok


def test_contrast_pair_sentences_are_checked_too(tmp_path: Path) -> None:
    point = alpha_point()
    point["blocks"].append({
        "type": "contrast", "with": "en.beta",
        "pairs": [["She works every day.", "She worked yesterday."]],
        "explain": {"vi": "x"},
    })
    tagged = {
        "He go to school.": ["agreement"],
        "He goes to school.": [],
        "She works in a bank.": [],
        "She works every day.": [],
        "She worked yesterday.": ["tense"],
    }
    report = verify_point(point, evaluator=make_evaluator(tagged), blind_solver=make_blind_solver(tmp_path, 1))
    assert report.checked_examples == 3  # 1 example + 2 contrast-pair sentences
    assert "example_not_clean" in report.codes()
