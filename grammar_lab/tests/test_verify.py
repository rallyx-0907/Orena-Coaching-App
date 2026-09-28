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


# --- v0.4 fixed content blocks (GRAMMAR_CONTENT_CONTRACT.md) -----------------------------

def v04_point() -> dict:
    point = alpha_point()
    point["schema_version"] = "0.4"
    point.pop("blocks", None)
    point["examples"] = [{
        "text": "She works in a bank.",
        "spans": [{"start": 4, "end": 9, "role": "verb"}],
        "annotation": {"vi": "ngôi thứ ba số ít"},
        "translation": {"vi": "Cô ấy làm ở ngân hàng."},
    }]
    point["compare"] = []
    point["common_mistakes"] = [{
        "wrong": "He go to school.", "right": "He goes to school.",
        "reason": {"vi": "Ngôi thứ ba số ít cần thêm -s."},
        "error_tag": "agreement", "l1": ["vi"],
    }]
    point["quick_practice"] = [{
        "q": "She ___ in a bank.",
        "options": [{"text": "work", "error_tag": "agreement"}, {"text": "works", "error_tag": None}],
        "answer": 1, "explain": {"vi": "Thêm -s."},
    }]
    return point


V04_CLEAN_TAGS = {
    "He go to school.": ["agreement"], "He goes to school.": [],
    "She works in a bank.": [], "She work in a bank.": ["agreement"],
}


def test_v04_all_checks_pass_produces_no_flags(tmp_path: Path) -> None:
    point = v04_point()
    report = verify_point(point, evaluator=make_evaluator(V04_CLEAN_TAGS), blind_solver=make_blind_solver(tmp_path, 1))
    assert report.ok, report.flags
    assert report.checked_examples == 1
    assert report.checked_common_mistakes == 1
    assert report.checked_quick_practice == 1


def test_v04_quick_practice_distractor_must_be_caught_as_its_declared_error(tmp_path: Path) -> None:
    point = v04_point()
    tagged = {**V04_CLEAN_TAGS, "She work in a bank.": ["spelling"]}  # engine sees a different error
    report = verify_point(point, evaluator=make_evaluator(tagged), blind_solver=make_blind_solver(tmp_path, 1))
    assert "quick_practice_distractor_not_caught" in report.codes()


def test_v04_quick_practice_answer_must_read_clean(tmp_path: Path) -> None:
    point = v04_point()
    tagged = {**V04_CLEAN_TAGS, "She works in a bank.": ["punctuation"]}
    report = verify_point(point, evaluator=make_evaluator(tagged), blind_solver=make_blind_solver(tmp_path, 1))
    assert "quick_practice_answer_not_clean" in report.codes()


def test_v04_common_mistake_not_caught_is_flagged(tmp_path: Path) -> None:
    point = v04_point()
    tagged = {"He go to school.": [], "He goes to school.": [], "She works in a bank.": []}
    report = verify_point(point, evaluator=make_evaluator(tagged), blind_solver=make_blind_solver(tmp_path, 1))
    assert "common_mistake_not_caught" in report.codes()


def test_v04_common_mistake_right_flagged_by_engine(tmp_path: Path) -> None:
    point = v04_point()
    tagged = {"He go to school.": ["agreement"], "He goes to school.": ["punctuation"], "She works in a bank.": []}
    report = verify_point(point, evaluator=make_evaluator(tagged), blind_solver=make_blind_solver(tmp_path, 1))
    assert "common_mistake_right_flagged" in report.codes()


def test_v04_quick_practice_wrong_answer_is_flagged(tmp_path: Path) -> None:
    point = v04_point()
    tagged = {"He go to school.": ["agreement"], "He goes to school.": [], "She works in a bank.": []}
    report = verify_point(point, evaluator=make_evaluator(tagged), blind_solver=make_blind_solver(tmp_path, 0))
    assert "blind_solve_wrong" in report.codes()


def test_v04_text_too_short_for_the_engine_is_unverified_not_failed_or_passed(tmp_path: Path) -> None:
    # D7 (human, 2026-09-28): a zh sentence under the engine's 10-character minimum is
    # "not verifiable by the engine" -- no flag, and not counted as a pass either.
    point = v04_point()
    point["examples"][0]["text"] = "She works."
    point["examples"][0]["spans"] = [{"start": 4, "end": 9, "role": "verb"}]
    point["examples"].append({**point["examples"][0], "text": "我们吃了饭。", "spans": [{"start": 2, "end": 3, "role": "verb"}]})
    tagged = {**V04_CLEAN_TAGS, "She works.": []}
    report = verify_point(point, evaluator=make_evaluator(tagged), blind_solver=make_blind_solver(tmp_path, 1))
    assert report.ok, report.flags
    assert report.unverified == ["examples[1] '我们吃了饭。'"]
    assert report.checked_examples == 1


def v04_point_with_formula(title: str, slots: list[dict]) -> dict:
    point = v04_point()
    point["header"] = {
        "title": {"vi": title}, "native_title": title, "level": point["level"], "summary": {"vi": "Tóm tắt."},
    }
    point["pattern"] = {"formula": slots, "illustration": {"kind": "none"}}
    return point


def _formula_solver(tmp_path: Path, coverage: dict) -> LLMClient:
    return LLMClient("openai", "gpt-6-luna", api_key="k", cache_dir=tmp_path, transport=multi_blind_solve_transport(
        {"blind_solve": {"answer_index": 1}, "formula_coverage": coverage,
         "distractor_plausibility": {"judgements": []}},
    ))


def test_v04_formula_missing_a_form_the_title_names_is_flagged(tmp_path: Path) -> None:
    point = v04_point_with_formula("There is / There are", [
        {"text": "There", "role": "marker", "label": {"vi": "there"}},
        {"text": "is", "role": "verb", "label": {"vi": "be"}},
    ])
    sent: list[dict] = []
    solver = _formula_solver(tmp_path, {"covers_all_forms": False, "missing_forms": ["are"]})
    original = solver._client.send

    def spy(request, *args, **kwargs):
        sent.append(json.loads(request.content))
        return original(request, *args, **kwargs)

    solver._client.send = spy
    report = verify_point(point, evaluator=make_evaluator(V04_CLEAN_TAGS), blind_solver=solver)
    assert "formula_incomplete" in report.codes()
    assert report.checked_formula
    formula_call = next(s for s in sent if s["response_format"]["json_schema"]["name"] == "formula_coverage")
    system = formula_call["messages"][0]["content"]
    assert "There is / There are" in system and "There + is" in system


def test_v04_formula_options_reach_the_checker_and_full_coverage_passes(tmp_path: Path) -> None:
    point = v04_point_with_formula("There is / There are", [
        {"text": "There", "role": "marker", "label": {"vi": "there"}},
        {"text": "be", "role": "verb", "label": {"vi": "be"}, "options": [{"text": "is"}, {"text": "are"}]},
    ])
    report = verify_point(point, evaluator=make_evaluator(V04_CLEAN_TAGS),
                          blind_solver=_formula_solver(tmp_path, {"covers_all_forms": True, "missing_forms": []}))
    assert "formula_incomplete" not in report.codes()
    assert report.checked_formula


def _solver(tmp_path: Path, responses: dict) -> LLMClient:
    return LLMClient("openai", "gpt-6-luna", api_key="k", cache_dir=tmp_path,
                     transport=multi_blind_solve_transport({"blind_solve": {"answer_index": 1}, **responses}))


def test_v04_invented_distractor_is_flagged_even_when_tagged_as_a_grammar_error(tmp_path: Path) -> None:
    point = v04_point_with_formula("Plural nouns", [{"text": "N", "role": "object", "label": {"vi": "danh từ"}}])
    point["quick_practice"][0]["options"].append({"text": "worksed", "error_tag": "agreement"})
    responses = {
        "formula_coverage": {"covers_all_forms": True, "missing_forms": []},
        "distractor_plausibility": {"judgements": [
            {"question": 0, "option": 0, "plausible": True, "reason": "real bare-verb mistake"},
            {"question": 0, "option": 2, "plausible": False, "reason": "invented form"},
            {"question": 0, "option": 1, "plausible": False, "reason": "the correct option is never judged"},
        ]},
    }
    report = verify_point(point, evaluator=make_evaluator({**V04_CLEAN_TAGS, "She worksed in a bank.": ["agreement"]}),
                          blind_solver=_solver(tmp_path, responses))
    implausible = [f for f in report.flags if f.code == "quick_practice_distractor_implausible"]
    assert len(implausible) == 1
    assert "worksed" in implausible[0].detail


def test_formula_text_shows_options_and_optional_slots() -> None:
    from grammar_lab.pipeline.verify import _formula_text
    assert _formula_text([
        {"text": "There", "role": "marker"},
        {"text": "be", "role": "verb", "options": [{"text": "is"}, {"text": "are"}]},
        {"text": "place", "role": "place", "optional": True},
    ]) == "There + be (is | are) + place [optional]"


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
        "type": "story", "theme": "daily", "mode": "everyday", "characters": ["Alex"],
        "hook": {"hook_type": "insider", "text": {"vi": "..."}},
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
        "reveal": {"vi": "..."}, "reveal_short": {"vi": "..."},
        "teaser": {"vi": "..."},
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
    "rubric": {
        "vivid": 0.8, "correct_when_to_use": 0.8, "concise": 0.8,
        "adult_appropriate": 0.8, "no_forbidden_pattern": 0.8,
    },
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
    responses = {**CLEAN_STORY_RESPONSES, "rubric": {
        "vivid": 0.2, "correct_when_to_use": 0.8, "concise": 0.8,
        "adult_appropriate": 0.8, "no_forbidden_pattern": 0.8,
    }}
    report = verify_point(point, evaluator=make_evaluator(tagged),
                           blind_solver=make_multi_blind_solver(tmp_path, responses))
    assert "story_rubric_low" in report.codes()


def test_low_adult_appropriate_score_is_flagged(tmp_path: Path) -> None:
    # VOICE.md: a story that reads like a children's fairy tale must be caught by the
    # rubric even when the other four criteria score well.
    point = alpha_point()
    point["blocks"].append(story_block())
    tagged = {**clean_engine_tagged(), "I live here for three days.": ["agreement"]}
    responses = {**CLEAN_STORY_RESPONSES, "rubric": {
        "vivid": 0.8, "correct_when_to_use": 0.8, "concise": 0.8,
        "adult_appropriate": 0.1, "no_forbidden_pattern": 0.8,
    }}
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


def test_v04_r5_corrections_confirmed_by_the_other_model_are_reported_not_flagged(tmp_path: Path) -> None:
    # C5 (human, 2026-09-28): when the conversion found R5 wrong, record it for the human.
    point = v04_point()
    point["provenance"]["r5_source"] = {"ids": ["a1-alpha"], "content_version": 2, "corrections": [
        {"r5_id": "a1-alpha", "issue": "R5 example 'He go school.' is wrong.", "fix": "He goes to school."},
        {"r5_id": "a1-alpha", "issue": "R5 calls -s plural.", "fix": "It is third person."},
    ]}
    responses = {
        "blind_solve": {"answer_index": 1},
        "formula_coverage": {"covers_all_forms": True, "missing_forms": []},
        "distractor_plausibility": {"judgements": []},
        "r5_corrections": {"judgements": [
            {"index": 0, "r5_was_wrong": True, "note": "missing -es and 'to'"},
            {"index": 1, "r5_was_wrong": False, "note": "R5 did not say that"},
        ]},
    }
    solver = LLMClient("openai", "gpt-6-luna", api_key="k", cache_dir=tmp_path, transport=multi_blind_solve_transport(responses))
    report = verify_point(point, evaluator=make_evaluator(V04_CLEAN_TAGS), blind_solver=solver)
    assert report.ok, report.flags
    assert report.r5_source_errors == ["a1-alpha: R5 example 'He go school.' is wrong. -> He goes to school. (missing -es and 'to')"]
