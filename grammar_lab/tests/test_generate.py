from __future__ import annotations

from pathlib import Path

import httpx

import json

from grammar_lab.pipeline.content_store import load_point
from grammar_lab.pipeline.generate import (
    Generator,
    _build_check_items,
    _normalize_seg,
    _story_generation_schema,
    build_rule_table,
)
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


CANNED_STORY = {
    "characters": ["Alex", "Sam"],
    "hook": {"hook_type": "insider", "text": {"vi": (
        "Người bản xứ nghe 'I live here for three days' là thấy lệch ngay, dù không phải lúc nào "
        "cũng nói được chính xác vì sao."
    )}},
    "scene": {"vi": (
        "Alex vừa chuyển đến một căn hộ mới gần trung tâm thành phố được vài hôm. Sáng thứ hai, Alex "
        "đứng trong bếp trống, nhìn tủ lạnh trống không, và nhận ra mình chưa mua thức ăn cho cả tuần. "
        "Ngoài cửa sổ, khu chợ nhỏ đầu phố vừa mở cửa, người bán hàng bắt đầu bày rau củ tươi ra sạp."
    )},
    "need": {"vi": (
        "Alex cần nói với Sam, người bạn cùng phòng, rằng mình đã sống ở căn hộ này được vài ngày rồi, "
        "không phải chỉ mới hôm nay, để Sam hiểu đúng tình hình mà rủ nhau đi chợ mua đồ ăn chung cho "
        "cả tuần."
    )},
    "form_in_action": {
        "sentences": ["I have lived here for three days."],
        "slots": [{"role": "person", "value": "I", "constraint": "a personal pronoun"}],
    },
    "alternatives": [
        {
            "sentence": "I live here for three days.",
            "error_tags": ["agreement"],
            "consequence": {"vi": (
                "Sam sẽ hiểu sai rằng đây là một thói quen lặp lại, chẳng hạn sống ba ngày mỗi tuần, chứ "
                "không phải một khoảng thời gian liên tục đã kéo dài đến tận bây giờ, nên có thể hỏi lại "
                "cho rõ."
            )},
            "short": {"vi": "Sam hiểu nhầm thành thói quen lặp lại."},
            "slots": [],
        },
    ],
    "reveal": {"vi": (
        "Tiếng Việt không có thì hoàn thành: 'đã' chỉ nói việc từng xảy ra, không nói việc đó còn kéo "
        "dài đến bây giờ. Vì vậy người Việt phải học thêm một trục thời gian hoàn toàn mới, không phải "
        "chỉ thêm một từ vào câu."
    )},
    "reveal_short": {"vi": "Tiếng Việt không có thì hoàn thành -- đây là một trục thời gian mới."},
    "teaser": {"vi": "Vậy vì sao thêm đúng một trợ động từ lại đổi cả câu chuyện?"},
}


CANNED_V04 = {
    "when_to_use": [{"vi": "Khi chủ ngữ là he/she/it."}, {"vi": "Nói về thói quen."}],
    "pattern": {
        "parts": [{"text": "He / She / It", "role": "subject"}, {"text": "works", "role": "verb"}],
        "illustration_kind": "timeline",
        "timeline_shape": "habit",
    },
    "examples": [
        {
            "text": "She works in a bank.",
            "spans": [{"start": 4, "end": 9, "role": "verb"}],
            "annotation": {"vi": "ngôi thứ ba số ít: +s"},
            "translation": {"vi": "Cô ấy làm ở ngân hàng."},
        },
        {
            "text": "He studies every day.",
            "spans": [{"start": 3, "end": 10, "role": "verb"}],
            "annotation": {"vi": "phụ âm + y: -ies"},
            "translation": {"vi": "Anh ấy học mỗi ngày."},
        },
    ],
    "compare": [],
    "common_mistakes": [
        {
            "wrong": "He go to school.", "right": "He goes to school.",
            "reason": {"vi": "Ngôi thứ ba số ít cần thêm -s."},
            "error_tag": "agreement", "l1": ["vi"],
        },
    ],
    "quick_practice": [
        {"q": "He ___ to school.", "options": ["go", "goes"], "answer": 1, "explain": {"vi": "Thêm -s."}},
        {"q": "She ___ a book.", "options": ["read", "reads"], "answer": 1, "explain": {"vi": "Thêm -s."}},
        {"q": "It ___ every morning.", "options": ["rain", "rains"], "answer": 1, "explain": {"vi": "Thêm -s."}},
    ],
}


def canned_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        sent = json.loads(request.content)
        tool_name = sent["tool_choice"]["name"]
        if tool_name == "emit_story":
            return httpx.Response(200, json={
                "content": [{"type": "tool_use", "name": "emit_story", "input": CANNED_STORY}],
                "usage": {"input_tokens": 400, "output_tokens": 250},
            })
        if tool_name == "emit_grammar_point_v04":
            return httpx.Response(200, json={
                "content": [{"type": "tool_use", "name": "emit_grammar_point_v04", "input": CANNED_V04}],
                "usage": {"input_tokens": 500, "output_tokens": 300},
            })
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


# --- story (schema v0.3, STORY_SPEC.md) ------------------------------------------------

def test_with_story_adds_a_story_block_and_bumps_schema_version(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.write()
    outcome = make_generator(lab.root, canned_transport()).generate("en.alpha", with_story=True)
    assert outcome.status == "written"
    point = load_point("en", "en.alpha", lab.root)
    assert point["schema_version"] == "0.3"
    story_blocks = [b for b in point["blocks"] if b["type"] == "story"]
    assert len(story_blocks) == 1
    assert story_blocks[0]["theme"] == "daily"
    assert story_blocks[0]["characters"] == ["Alex", "Sam"]
    # still a fully valid point under v0.3 (needs the daily story, has it)
    report = validate_lang("en", lab.root)
    assert report.ok, report.issues


def test_without_with_story_keeps_schema_version_0_2(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.write()
    outcome = make_generator(lab.root, canned_transport()).generate("en.alpha")
    assert outcome.status == "written"
    point = load_point("en", "en.alpha", lab.root)
    assert point["schema_version"] == "0.2"
    assert not any(b["type"] == "story" for b in point["blocks"])


def test_with_story_sums_cost_of_both_calls(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.write()
    without_story = make_generator(lab.root, canned_transport()).generate("en.alpha")
    lab2 = Lab(tmp_path.parent / (tmp_path.name + "-2"), "en")
    lab2.write()
    with_story = make_generator(lab2.root, canned_transport()).generate("en.alpha", with_story=True)
    assert with_story.cost_usd > without_story.cost_usd


def test_story_generation_schema_constrains_characters_to_the_cast() -> None:
    schema = _story_generation_schema(locales=["vi"], error_tags=["agreement"], cast_names=["Alex", "Sam"])
    assert schema["properties"]["characters"]["items"] == {"enum": ["Alex", "Sam"]}


def test_generate_v04_writes_the_six_fixed_content_blocks(tmp_path: Path) -> None:
    """GRAMMAR_CONTENT_CONTRACT.md: a point already on schema_version 0.4 regenerates
    through the new when_to_use/pattern/examples/compare/common_mistakes/quick_practice
    path, not the old free-form blocks[] one."""
    lab = Lab(tmp_path, "en")
    lab.points["en.alpha"]["schema_version"] = "0.4"
    lab.points["en.alpha"].pop("blocks", None)
    lab.write()

    outcome = make_generator(lab.root, canned_transport()).generate("en.alpha")

    assert outcome.status == "written"
    point = load_point("en", "en.alpha", lab.root)
    assert point["schema_version"] == "0.4"
    assert "blocks" not in point
    assert point["when_to_use"] == CANNED_V04["when_to_use"]
    assert point["pattern"]["illustration"] == {"kind": "timeline", "timeline": {"shape": "habit"}}
    assert len(point["examples"]) == 2
    assert len(point["common_mistakes"]) == 1
    assert len(point["quick_practice"]) == 3
    report = validate_lang("en", lab.root)
    assert report.ok, report.issues


def test_generate_v04_illustration_drops_timeline_when_kind_is_not_timeline(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.points["en.alpha"]["schema_version"] = "0.4"
    lab.points["en.alpha"].pop("blocks", None)
    lab.write()
    canned = {**CANNED_V04, "pattern": {**CANNED_V04["pattern"], "illustration_kind": "none"}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "content": [{"type": "tool_use", "name": "emit_grammar_point_v04", "input": canned}],
            "usage": {"input_tokens": 500, "output_tokens": 300},
        })

    outcome = make_generator(lab.root, httpx.MockTransport(handler)).generate("en.alpha")
    assert outcome.status == "written"
    point = load_point("en", "en.alpha", lab.root)
    assert point["pattern"]["illustration"] == {"kind": "none"}


def test_generate_v04_rejects_with_story(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.points["en.alpha"]["schema_version"] = "0.4"
    lab.points["en.alpha"].pop("blocks", None)
    lab.write()
    try:
        make_generator(lab.root, canned_transport()).generate("en.alpha", with_story=True)
    except ValueError as exc:
        assert "0.4" in str(exc)
    else:
        raise AssertionError("expected a ValueError")


def test_story_generation_schema_bounds_alternatives_to_one_per_error_tag() -> None:
    schema = _story_generation_schema(locales=["vi"], error_tags=["agreement", "tense"], cast_names=["Alex"])
    alternatives = schema["properties"]["alternatives"]
    assert alternatives["minItems"] == alternatives["maxItems"] == 2


# --- seg normalization (DeepSeek json_object mode, live finding 2026-09-28) -----------

def test_normalize_seg_drops_a_null_label() -> None:
    seg = [["She "], ["works", None], [" today."]]
    assert _normalize_seg(seg) == [["She "], ["works"], [" today."]]


def test_normalize_seg_keeps_a_real_label() -> None:
    seg = [["She "], ["works", "target"], [" today."]]
    assert _normalize_seg(seg) == [["She "], ["works", "target"], [" today."]]


def test_normalize_seg_leaves_single_element_segments_alone() -> None:
    seg = [["She "], ["works"]]
    assert _normalize_seg(seg) == [["She "], ["works"]]


def test_generate_normalizes_a_null_label_before_saving(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.write()
    blocks_with_null_label = dict(CANNED_BLOCKS)
    blocks_with_null_label["examples"] = [
        {
            "text": "She works in a bank.",
            # "works" keeps a real target label; " in a bank" carries DeepSeek's stray
            # null instead of being omitted -- exactly the live-found shape.
            "seg": [["She "], ["works", "target"], [" in a bank", None], ["."]],
            "tr": {"vi": "x"},
        },
        CANNED_BLOCKS["examples"][1],
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "content": [{"type": "tool_use", "name": "emit_grammar_point_blocks", "input": blocks_with_null_label}],
            "usage": {"input_tokens": 500, "output_tokens": 300},
        })

    outcome = make_generator(lab.root, httpx.MockTransport(handler)).generate("en.alpha")
    assert outcome.status == "written"
    point = load_point("en", "en.alpha", lab.root)
    example = next(b for b in point["blocks"] if b["type"] == "example" and b["text"] == "She works in a bank.")
    assert example["seg"] == [["She "], ["works", "target"], [" in a bank"], ["."]]
    report = validate_lang("en", lab.root)
    assert report.ok, report.issues
