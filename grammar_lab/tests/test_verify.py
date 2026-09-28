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


# --- story (schema v0.3, STORY_SPEC.md §6) ---------------------------------------------

def story_block() -> dict:
    return {
        "type": "story", "theme": "daily", "characters": ["Alex"],
        "scene": {"vi": "..."}, "need": {"vi": "..."},
        "form_in_action": {
            "sentences": ["I have lived here for three days."],
            "slots": [{"role": "person", "value": "I", "constraint": "a personal pronoun"}],
        },
        "alternatives": [
            {
                "sentence": "I live here for three days.",
                "error_tags": ["agreement"],  # matches alpha_point()'s error_tags
                "consequence": {"vi": "Sam sẽ hiểu nhầm thành thói quen."},
                "short": {"vi": "Hiểu nhầm thành thói quen."},
                "slots": [],
            },
        ],
        "anchor": {"vi": "..."}, "anchor_short": {"vi": "..."},
    }


def multi_blind_solve_transport(responses: dict[str, dict]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        sent = json.loads(request.content)
        name = sent["response_format"]["json_schema"]["name"]
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(responses[name])}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        })
    return httpx.MockTransport(handler)


CLEAN_STORY_RESPONSES = {
    "blind_solve": {"answer_index": 1},
    "meaning_match": {"implied_meaning": "a repeated habit, not a state since three days ago",
                       "matches_declared_consequence": True},
    "historical_claim": {"makes_historical_claim": False},
    "rubric": {"vivid": 0.8, "correct_when_to_use": 0.8, "concise": 0.8},
}


def make_multi_blind_solver(tmp_path: Path, responses: dict[str, dict]) -> LLMClient:
    return LLMClient("openai", "gpt-6-luna", api_key="k", cache_dir=tmp_path,
                      transport=multi_blind_solve_transport(responses))


def clean_engine_tagged() -> dict[str, list[str]]:
    return {
        "He go to school.": ["agreement"],
        "He goes to school.": [],
        "She works in a bank.": [],
        "I have lived here for three days.": [],
    }


def test_clean_story_produces_no_flags(tmp_path: Path) -> None:
    point = alpha_point()
    point["blocks"].append(story_block())
    tagged = {**clean_engine_tagged(), "I live here for three days.": ["agreement"]}
    report = verify_point(point, evaluator=make_evaluator(tagged),
                           blind_solver=make_multi_blind_solver(tmp_path, CLEAN_STORY_RESPONSES))
    assert report.ok, report.flags
    assert report.checked_story_sentences == 2  # form_in_action + 1 alternative


def test_dirty_form_in_action_is_flagged(tmp_path: Path) -> None:
    point = alpha_point()
    point["blocks"].append(story_block())
    tagged = {**clean_engine_tagged(), "I have lived here for three days.": ["punctuation"],
              "I live here for three days.": ["agreement"]}
    report = verify_point(point, evaluator=make_evaluator(tagged),
                           blind_solver=make_multi_blind_solver(tmp_path, CLEAN_STORY_RESPONSES))
    assert "story_form_not_clean" in report.codes()


def test_alternative_flagged_with_wrong_tag_is_reported(tmp_path: Path) -> None:
    point = alpha_point()
    point["blocks"].append(story_block())
    # engine catches something, but not the declared "agreement" tag
    tagged = {**clean_engine_tagged(), "I live here for three days.": ["punctuation"]}
    report = verify_point(point, evaluator=make_evaluator(tagged),
                           blind_solver=make_multi_blind_solver(tmp_path, CLEAN_STORY_RESPONSES))
    assert "story_alternative_tag_not_caught" in report.codes()


def test_alternative_matching_declared_tag_is_not_flagged(tmp_path: Path) -> None:
    point = alpha_point()
    point["blocks"].append(story_block())
    tagged = {**clean_engine_tagged(), "I live here for three days.": ["agreement"]}
    report = verify_point(point, evaluator=make_evaluator(tagged),
                           blind_solver=make_multi_blind_solver(tmp_path, CLEAN_STORY_RESPONSES))
    assert "story_alternative_tag_not_caught" not in report.codes()
    assert "story_alternative_meaning_mismatch" not in report.codes()


def test_grammatical_alternative_goes_to_meaning_match_and_can_mismatch(tmp_path: Path) -> None:
    point = alpha_point()
    point["blocks"].append(story_block())
    # engine finds nothing wrong with the alternative -> grammatical, meaning-match path
    tagged = {**clean_engine_tagged(), "I live here for three days.": []}
    responses = {**CLEAN_STORY_RESPONSES, "meaning_match": {
        "implied_meaning": "exactly the same as the main sentence", "matches_declared_consequence": False,
    }}
    report = verify_point(point, evaluator=make_evaluator(tagged),
                           blind_solver=make_multi_blind_solver(tmp_path, responses))
    assert "story_alternative_meaning_mismatch" in report.codes()
    assert "story_alternative_tag_not_caught" not in report.codes()  # not the ungrammatical path


def test_historical_claim_is_flagged(tmp_path: Path) -> None:
    point = alpha_point()
    point["blocks"].append(story_block())
    tagged = {**clean_engine_tagged(), "I live here for three days.": ["agreement"]}
    responses = {**CLEAN_STORY_RESPONSES, "historical_claim": {
        "makes_historical_claim": True, "quote": "this form comes from Old English",
    }}
    report = verify_point(point, evaluator=make_evaluator(tagged),
                           blind_solver=make_multi_blind_solver(tmp_path, responses))
    assert "story_historical_claim" in report.codes()


def test_low_rubric_score_is_flagged(tmp_path: Path) -> None:
    point = alpha_point()
    point["blocks"].append(story_block())
    tagged = {**clean_engine_tagged(), "I live here for three days.": ["agreement"]}
    responses = {**CLEAN_STORY_RESPONSES, "rubric": {"vivid": 0.2, "correct_when_to_use": 0.8, "concise": 0.8}}
    report = verify_point(point, evaluator=make_evaluator(tagged),
                           blind_solver=make_multi_blind_solver(tmp_path, responses))
    assert "story_rubric_low" in report.codes()


def test_high_rubric_score_is_not_flagged(tmp_path: Path) -> None:
    point = alpha_point()
    point["blocks"].append(story_block())
    tagged = {**clean_engine_tagged(), "I live here for three days.": ["agreement"]}
    report = verify_point(point, evaluator=make_evaluator(tagged),
                           blind_solver=make_multi_blind_solver(tmp_path, CLEAN_STORY_RESPONSES))
    assert "story_rubric_low" not in report.codes()
