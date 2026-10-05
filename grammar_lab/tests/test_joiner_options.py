import copy
import json
from pathlib import Path

from grammar_lab.pipeline.generate import (
    assemble_generated_example,
    normalize_generated_common_prefix_options,
    normalize_generated_structure,
)


def candidate():
    return {
        "formula": [
            {"text": "S", "role": "subject"},
            {"text": "complement", "role": "complement", "options": [{"text": "on + V-ing"}]},
            {"text": "time", "role": "time"},
        ],
        "examples": [{"form": "affirmative", "text": "They insist on reviewing it today.",
                      "annotation": {}, "translation": {},
                      "bindings": [{"slot_index": 0, "text": "They"},
                                   {"slot_index": 1, "text": "on reviewing it"},
                                   {"slot_index": 2, "text": "today"}]}],
        "personal_production": {"target_form": "affirmative", "pattern_rule": {"slots": [
            {"slot_index": 1, "any_of": ["on reviewing it"], "regex": ""},
            {"slot_index": 2, "any_of": ["today"], "regex": ""}]}},
    }


def test_safe_sequence_and_production_remapping():
    data = candidate()
    original = copy.deepcopy(data)
    out = normalize_generated_common_prefix_options(data, False)
    assert [slot["text"] for slot in out["formula"]] == ["S", "on", "complement", "time"]
    assert out["formula"][2]["options"] == [{"text": "V-ing"}]
    assert out["personal_production"]["pattern_rule"]["slots"] == [
        {"slot_index": 1, "any_of": ["on"], "regex": ""},
        {"slot_index": 2, "any_of": ["reviewing it"], "regex": ""},
        {"slot_index": 3, "any_of": ["today"], "regex": ""}]
    assert out["examples"][0]["text"] == data["examples"][0]["text"]
    assert data == original
    assert normalize_generated_common_prefix_options(out, False) == out


def test_example_bindings_remap_and_assemble():
    out = normalize_generated_structure(candidate(), False)
    assert out["examples"][0]["bindings"] == [
        {"slot_index": 0, "text": "They"}, {"slot_index": 1, "text": "on"},
        {"slot_index": 2, "text": "reviewing it"}, {"slot_index": 3, "text": "today"}]
    _, problems = assemble_generated_example(out["examples"][0], {"formula": out["formula"]},
                                              False, lambda value: value, 0)
    assert not problems


def test_incompatible_or_ambiguous_routes_stay_unchanged():
    for option in ("NP + to-infinitive", "from + V-ing", "V-ing"):
        data = candidate()
        data["formula"][1]["options"].append({"text": option})
        assert normalize_generated_common_prefix_options(data, False) == data
    data = candidate()
    data["examples"][0]["bindings"][1]["text"] = "on something"
    assert normalize_generated_common_prefix_options(data, False) == data
    data = candidate()
    data["personal_production"]["pattern_rule"]["slots"][0]["regex"] = ".+"
    assert normalize_generated_common_prefix_options(data, False) == data


def test_cached_incompatible_candidate_is_not_rewritten():
    cache = Path(__file__).resolve().parents[1] / ".cache/llm/deepseek/c094e55175cccdb1fd1f2991195da218211fd41a767aa4113e7f3cf161c19f68.json"
    data = json.loads(cache.read_text(encoding="utf-8"))["data"]
    assert normalize_generated_structure(data, False) == data
    assert sum("+" in option["text"] for option in data["formula"][2]["options"]) == 3
