from __future__ import annotations

from pathlib import Path

import httpx

from grammar_lab.pipeline.content_store import load_point
from grammar_lab.pipeline.generate import Generator, _build_check_items, build_rule_table
from grammar_lab.pipeline.llm_client import LLMClient
from grammar_lab.pipeline.validate import validate_lang
from grammar_lab.tests.conftest import Lab

CANNED_BLOCKS = {
    "formula": {"parts": ["He / She / It", "V + s"]},
    "timeline": {"kind": "habit", "relevance": "now"},
    "examples": [
        {
            "text": "She works in a bank.",
            "seg": [["She "], ["works", "target"], [" in a bank."]],
            "tr": {"vi": "Cô ấy làm ở ngân hàng."},
        },
        {
            "text": "He studies every day.",
            "seg": [["He "], ["studies", "target"], [" every day."]],
            "tr": {"vi": "Anh ấy học mỗi ngày."},
        },
    ],
    "contrasts": [],
    "pitfalls": [
        {
            "l1": ["vi"],
            "wrong": "He go to school.",
            "right": "He goes to school.",
            "error_tag": "agreement",
            "why": {"vi": "Ngôi thứ ba số ít cần thêm -s."},
        }
    ],
    "note": None,
}


def canned_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "content": [{"type": "tool_use", "name": "emit_grammar_point_blocks", "input": CANNED_BLOCKS}],
            "usage": {"input_tokens": 500, "output_tokens": 300},
        })
    return httpx.MockTransport(handler)


def make_generator(root: Path, transport: httpx.MockTransport | None = None) -> Generator:
    llm = LLMClient("anthropic", "claude-haiku-4-5-20251001", api_key="test", cache_dir=root / ".cache",
                     transport=transport or canned_transport())
    return Generator(lang="en", l1="vi", llm=llm, root=root)


def test_generate_writes_a_valid_draft_point(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.write()
    generator = make_generator(lab.root)

    outcome = generator.generate("en.alpha")

    assert outcome.status == "written"
    point = load_point("en", "en.alpha", lab.root)
    assert point["status"] == "draft_ai"
    assert point["version"] == 1  # not approved before, no bump
    block_types = [b["type"] for b in point["blocks"]]
    assert block_types.count("example") == 2
    assert block_types.count("pitfall") == 1
    assert "check" in block_types
    # regenerated content must still pass validate
    report = validate_lang("en", lab.root)
    assert report.ok, report.issues


def test_generate_reports_cost_from_llm_usage(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.write()
    outcome = make_generator(lab.root).generate("en.alpha")
    assert outcome.cost_usd is not None
    assert outcome.cost_usd > 0
    assert outcome.cached is False


def test_generate_is_cached_on_second_call_with_the_same_cache_dir(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.write()
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={
            "content": [{"type": "tool_use", "name": "x", "input": CANNED_BLOCKS}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        })

    cache_dir = lab.root / ".cache"
    llm1 = LLMClient("anthropic", "claude-haiku-4-5-20251001", api_key="t", cache_dir=cache_dir,
                      transport=httpx.MockTransport(handler))
    Generator(lang="en", l1="vi", llm=llm1, root=lab.root).generate("en.alpha")
    llm2 = LLMClient("anthropic", "claude-haiku-4-5-20251001", api_key="t", cache_dir=cache_dir,
                      transport=httpx.MockTransport(handler))
    outcome = Generator(lang="en", l1="vi", llm=llm2, root=lab.root).generate("en.alpha")
    assert outcome.cached is True
    assert len(calls) == 1


def test_generate_skips_approved_point_without_regenerate_note(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.points["en.alpha"].update(
        status="approved",
        review={"reviewer": "owner", "reviewed_at": "2026-09-27T00:00:00Z", "seconds": 30},
    )
    lab.write()
    outcome = make_generator(lab.root).generate("en.alpha")
    assert outcome.status == "skipped_approved"
    point = load_point("en", "en.alpha", lab.root)
    assert point["status"] == "approved"  # untouched


def test_generate_bumps_version_when_regenerating_an_approved_point(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.points["en.alpha"].update(
        status="approved",
        review={"reviewer": "owner", "reviewed_at": "2026-09-27T00:00:00Z", "seconds": 30},
    )
    lab.write()
    outcome = make_generator(lab.root).generate("en.alpha", regenerate_note="pitfall was unnatural")
    assert outcome.status == "written"
    point = load_point("en", "en.alpha", lab.root)
    assert point["version"] == 2
    assert point["status"] == "draft_ai"
    assert point["review"] is None


def test_generate_unknown_point_id_errors_instead_of_inventing_metadata(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.write()
    outcome = make_generator(lab.root).generate("en.nonexistent")
    assert outcome.status == "error"


def test_build_rule_table_for_known_point() -> None:
    table = build_rule_table("en.present_simple.third_person_s", ["vi"])
    assert table is not None
    assert table["type"] == "rule_table"
    bases = [row[0] for row in table["rows"]]
    derived = [row[1] for row in table["rows"]]
    assert "work" in bases
    assert "works" in derived


def test_build_rule_table_for_unmapped_point_is_none() -> None:
    assert build_rule_table("en.there_is_are", ["vi"]) is None


def test_build_check_items_uses_single_target_segment_examples_only() -> None:
    examples = [
        {"text": "She works.", "seg": [["She "], ["works", "target"], ["."]], "tr": {"vi": "x"}},
        {  # two target segments -- cannot make a single-blank cloze, must be skipped
            "text": "Have you eaten?",
            "seg": [["Have", "target"], [" you "], ["eaten", "target"], ["?"]],
            "tr": {"vi": "x"},
        },
    ]
    rule_table = {"type": "rule_table", "rows": [["work", "works", {"vi": "x"}]]}
    items = _build_check_items(examples, rule_table, [], ["vi"])
    assert len(items) == 1
    assert items[0]["q"] == "She ___."
    assert items[0]["options"][items[0]["answer"]] == "works"


def test_build_check_items_skips_an_example_with_no_available_distractor() -> None:
    examples = [{"text": "She works.", "seg": [["She "], ["works", "target"]], "tr": {"vi": "x"}}]
    assert _build_check_items(examples, None, [], ["vi"]) == []


def test_build_check_items_options_are_unique() -> None:
    examples = [{"text": "She works.", "seg": [["She "], ["works", "target"]], "tr": {"vi": "x"}}]
    rule_table = {"type": "rule_table", "rows": [["work", "works", {"vi": "x"}]]}
    items = _build_check_items(examples, rule_table, [], ["vi"])
    assert len(items) == 1
    assert len(items[0]["options"]) == len(set(items[0]["options"]))
