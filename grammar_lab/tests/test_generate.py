from __future__ import annotations

import copy
import re
from pathlib import Path

import httpx

import json

from grammar_lab.pipeline.content_store import load_point
from grammar_lab.pipeline.generate import (
    Generator,
    PERSONAL_PRODUCTION_MAX_ANY_OF,
    PERSONAL_PRODUCTION_MAX_SLOTS,
    PROMPT_PATH_V04,
    _build_check_items,
    _generation_schema_v04,
    _normalize_seg,
    _story_generation_schema,
    build_rule_table,
    complete_literal_example_spans,
    pinyin_from_pairs,
    resolve_spans,
    semantic_repair_hints,
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
    "contrasts": [{"with": "en.beta", "pairs": [["She works.", "She is working."]], "explain": {"vi": "Thói quen và việc đang xảy ra."}}],
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


def _canned_slot(text: str, role: str, label: str, pairs: list[list[str]] | None = None) -> dict:
    slot = {"text": text, "role": role, "label": {"vi": label}, "optional": False}
    if pairs is not None:
        slot["pinyin_pairs"] = pairs
    return slot


_ZH_CHAR_PINYIN = {
    "我": "wǒ", "吃": "chī", "饭": "fàn", "了": "le", "着": "zhe", "过": "guo", "他": "tā", "走": "zǒu",
    "在": "zài", "你": "nǐ", "吗": "ma", "动": "dòng", "态": "tài", "助": "zhù", "词": "cí",
}


def _pairs(text: str) -> list[list[str]]:
    return [[char, _ZH_CHAR_PINYIN.get(char, "")] for char in text]


def _canned_qp(q: str, right: str, wrongs: list[tuple[str, str]], zh: bool = False) -> dict:
    options = [{"text": right, "error_tag": None}, *({"text": t, "error_tag": tag} for t, tag in wrongs)]
    if zh:
        options = [{**option, "pinyin_pairs": _pairs(option["text"])} for option in options]
    item = {"q": q, "options": options, "answer": 0, "explain": {"vi": "Giải thích."}}
    if zh:
        item["q_pinyin_pairs"] = _pairs(q)
    return item


# en.alpha as a morphology point (third person -s): what the model returns for schema v0.4.
CANNED_V04 = {
    "summary": {"vi": "He/she/it ở hiện tại đơn: động từ thêm -s."},
    "sub": {"vi": "he / she / it"},
    "personal_production": {
        "prompt": {"vi": "Viết một câu về thói quen của một người."}, "placeholder": "She ... every day.",
        "target_form": "affirmative",
        "pattern_rule": {"ordered": True, "slots": [{"role": "verb", "any_of": [], "regex": r"\b\w+(?:s|es)\b"}]},
        "sample": "She reads a book.",
    },
    "when_to_use": [{"vi": "Khi chủ ngữ là he/she/it."}, {"vi": "Nói về thói quen."}],
    "formula": [_canned_slot("He / She / It", "subject", "chủ ngữ ngôi ba"), _canned_slot("V-s", "verb", "động từ thêm -s")],
    "negative": [
        _canned_slot("He / She / It", "subject", "chủ ngữ ngôi ba"), _canned_slot("doesn't", "aux", "trợ động từ phủ định"),
        _canned_slot("V", "verb", "động từ nguyên mẫu"),
    ],
    "question": [],
    "morphology": [{"base": "work", "affix": "-s", "result": "works"}, {"base": "study", "affix": "-ies", "result": "studies"}],
    "examples": [
        {
            "text": "She works in a bank.", "form": "affirmative",
            "spans": [{"text": "She", "role": "subject"}, {"text": "works", "role": "verb"}],
            "annotation": {"vi": "ngôi ba số ít: +s"}, "translation": {"vi": "Cô ấy làm ở ngân hàng."},
        },
        {
            "text": "He studies every day.", "form": "affirmative",
            "spans": [{"text": "He", "role": "subject"}, {"text": "studies", "role": "verb"}],
            "annotation": {"vi": "phụ âm + y: -ies"}, "translation": {"vi": "Anh ấy học mỗi ngày."},
        },
        {
            "text": "He doesn't like tea.", "form": "negative",
            "spans": [
                {"text": "He", "role": "subject"}, {"text": "doesn't", "role": "aux"}, {"text": "like", "role": "verb"},
            ],
            "annotation": {"vi": "phủ định: doesn't + V"}, "translation": {"vi": "Anh ấy không thích trà."},
        },
    ],
    "compare": [{
        "with": "en.beta", "this_meaning": {"vi": "Thói quen."}, "this_example": "She works in a bank.",
        "other_meaning": {"vi": "Việc đã xong."}, "other_example": "She worked in a bank.",
    }],
    "common_mistakes": [
        {
            "wrong": "He go to school.", "right": "He goes to school.",
            "reason": {"vi": "Ngôi thứ ba số ít cần thêm -s."}, "error_tag": "agreement", "l1": ["vi"],
        },
    ],
    "quick_practice": [
        _canned_qp("He ___ to school.", "goes", [("go", "agreement"), ("going", "tense")]),
        _canned_qp("She ___ a book every week.", "reads", [("read", "agreement"), ("is read", "tense")]),
        _canned_qp("It ___ every morning.", "rains", [("rain", "agreement"), ("raining", "tense")]),
    ],
}

_ZH_TEXT_PAIRS = {
    "我们吃了饭。": [["我", "wǒ"], ["们", "men"], ["吃", "chī"], ["了", "le"], ["饭", "fàn"], ["。", ""]],
    "他买了书。": [["他", "tā"], ["买", "mǎi"], ["了", "le"], ["书", "shū"], ["。", ""]],
    "她来了。": [["她", "tā"], ["来", "lái"], ["了", "le"], ["。", ""]],
    "我昨天吃饭。": [["我", "wǒ"], ["昨", "zuó"], ["天", "tiān"], ["吃", "chī"], ["饭", "fàn"], ["。", ""]],
    "我昨天吃了饭。": [["我", "wǒ"], ["昨", "zuó"], ["天", "tiān"], ["吃", "chī"], ["了", "le"], ["饭", "fàn"], ["。", ""]],
}


def _zh_example(text: str, verb: str) -> dict:
    return {
        "text": text, "form": "affirmative",
        "spans": [{"text": verb, "role": "verb"}, {"text": "了", "role": "particle"}],
        "annotation": {"vi": "đã xong"}, "translation": {"vi": "Bản dịch."}, "pinyin_pairs": _ZH_TEXT_PAIRS[text],
    }


# zh.le_completion as a tense_aspect point.
CANNED_V04_ZH = {
    "sub": {"vi": "hoàn thành"},
    "personal_production": {
        "prompt": {"vi": "Viết một câu về việc đã làm xong."}, "placeholder": "我吃了……",
        "placeholder_pinyin_pairs": _pairs("我吃了……"), "target_form": "affirmative",
        "pattern_rule": {"ordered": True, "slots": [{"role": "particle", "any_of": ["了"], "regex": ""}]},
        "sample": "我吃了饭。", "sample_pinyin_pairs": _pairs("我吃了饭。"),
    },
    "native_title_pinyin_pairs": _pairs("动态助词“了”"),
    "summary": {"vi": "了 sau động từ: hành động đã xong."},
    "when_to_use": [{"vi": "Hành động đã xong."}, {"vi": "Có mốc thời gian cụ thể."}],
    "formula": [
        _canned_slot("动词", "verb", "động từ", [["动", "dòng"], ["词", "cí"]]),
        _canned_slot("了", "particle", "trợ từ hoàn thành", [["了", "le"]]),
    ],
    "negative": [],
    "question": [],
    "timeline_shape": "point_past",
    "examples": [_zh_example("我们吃了饭。", "吃"), _zh_example("他买了书。", "买"), _zh_example("她来了。", "来")],
    "compare": [],
    "common_mistakes": [{
        "wrong": "我昨天吃饭。", "right": "我昨天吃了饭。", "reason": {"vi": "Đã xong cần 了."},
        "error_tag": "aspect", "l1": ["vi"],
        "wrong_pinyin_pairs": _ZH_TEXT_PAIRS["我昨天吃饭。"], "right_pinyin_pairs": _ZH_TEXT_PAIRS["我昨天吃了饭。"],
    }],
    "quick_practice": [
        _canned_qp("我吃___饭。", "了", [("着", "aspect"), ("过", "aspect")], zh=True),
        _canned_qp("他走___。", "了", [("着", "aspect"), ("在", "aspect")], zh=True),
        _canned_qp("你吃___吗？", "了", [("着", "aspect"), ("在", "aspect")], zh=True),
    ],
}


def _one_locale(node):
    """With a single explanation locale the v0.4 schema asks for plain strings, not {"vi": ...} objects
    (generate.py files them under the locale); the canned answers below are written as objects."""
    if isinstance(node, dict):
        if set(node) == {"vi"}:
            return node["vi"]
        return {key: _one_locale(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_one_locale(value) for value in node]
    return node


def _answer(payload: dict) -> dict:
    """What a schema-obeying model would send for ``payload``: plain strings for a single locale, and
    ``options`` on every formula slot (the schema requires it, [] when the slot is not a choice).
    Every answer is checked against the real schema now (llm_client.schema_problems)."""
    def slots(node):
        if isinstance(node, dict):
            if {"role", "label"} <= set(node):
                node = {**node, "options": node.get("options", [])}
            return {key: slots(value) for key, value in node.items()}
        if isinstance(node, list):
            return [slots(value) for value in node]
        return node

    return slots(_one_locale(payload))


def v04_transport(payload: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "content": [{"type": "tool_use", "name": "emit_grammar_point_v04", "input": _answer(payload)}],
            "usage": {"input_tokens": 500, "output_tokens": 300},
        })
    return httpx.MockTransport(handler)


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
                "content": [{"type": "tool_use", "name": "emit_grammar_point_v04", "input": _answer(CANNED_V04)}],
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


def _v04_lab(tmp_path: Path, lang: str = "en", point_type: str = "morphology") -> Lab:
    """A lab whose one point is on schema_version 0.4 in metadata only (legacy top-level
    title, no content yet) -- the state a point is in before its first v0.4 generate."""
    lab = Lab(tmp_path, lang)
    point_id = "en.alpha" if lang == "en" else "zh.le_completion"
    point = lab.points[point_id]
    point["schema_version"] = "0.4"
    point["point_type"] = point_type
    point.pop("blocks", None)
    return lab


def test_generate_v04_writes_header_and_the_fixed_content_blocks(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path)
    lab.write()

    outcome = make_generator(lab.root, v04_transport(CANNED_V04)).generate("en.alpha")

    assert outcome.status == "written", outcome.reason
    point = load_point("en", "en.alpha", lab.root)
    assert point["schema_version"] == "0.4"
    assert "blocks" not in point and "title" not in point and "summary" not in point
    assert point["header"] == {
        "title": {"vi": "Tiêu đề"}, "native_title": "Title", "level": point["level"], "summary": CANNED_V04["summary"],
        "sub": CANNED_V04["sub"],
    }
    assert point["personal_production"]["sample"] == {"text": "She reads a book."}
    assert point["personal_production"]["pattern_rule"]["slots"] == [{"role": "verb", "regex": r"\b\w+(?:s|es)\b"}]  # the empty any_of is dropped
    assert [slot["text"] for slot in point["pattern"]["formula"]] == ["He / She / It", "V-s"]
    assert "question" not in point["pattern"]["variants"]  # empty variants are dropped
    assert point["pattern"]["illustration"] == {"kind": "morphology", "morphology": CANNED_V04["morphology"]}
    assert len(point["quick_practice"]) == 3
    report = validate_lang("en", lab.root)
    assert report.ok, report.issues


def test_generate_v04_retries_semantic_validation_with_feedback(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path)
    lab.write()
    bad = copy.deepcopy(CANNED_V04)
    bad["personal_production"]["pattern_rule"]["slots"][0]["regex"] = r"\bNEVER\b"
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent = json.loads(request.content)
        calls.append(sent)
        payload = bad if len(calls) == 1 else CANNED_V04
        return httpx.Response(200, json={
            "content": [{"type": "tool_use", "name": sent["tool_choice"]["name"], "input": _answer(payload)}],
            "usage": {"input_tokens": 500, "output_tokens": 300},
        })

    outcome = make_generator(lab.root, httpx.MockTransport(handler)).generate("en.alpha")
    assert outcome.status == "written", outcome.reason
    assert len(calls) == 2
    assert "failed deterministic validation" in calls[1]["messages"][0]["content"]
    assert validate_lang("en", lab.root).ok


def test_generate_v04_does_not_persist_after_three_semantic_failures(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path)
    lab.write()
    path = lab.root / "content" / "en" / "en.alpha.json"
    before = path.read_text(encoding="utf-8")
    bad = copy.deepcopy(CANNED_V04)
    bad["personal_production"]["pattern_rule"]["slots"][0]["regex"] = r"\bNEVER\b"
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        sent = json.loads(request.content)
        return httpx.Response(200, json={
            "content": [{"type": "tool_use", "name": sent["tool_choice"]["name"], "input": _answer(bad)}],
            "usage": {"input_tokens": 500, "output_tokens": 300},
        })

    outcome = make_generator(lab.root, httpx.MockTransport(handler)).generate("en.alpha")
    assert outcome.status == "error"
    assert "semantic validation failed after 3 attempts" in outcome.reason
    assert len(calls) == 3
    assert path.read_text(encoding="utf-8") == before

    second = make_generator(lab.root, httpx.MockTransport(handler)).generate("en.alpha")
    assert second.status == "error"
    assert len(calls) == 6  # semantic-invalid cache entries were evicted, so retry is genuinely fresh
    assert path.read_text(encoding="utf-8") == before

def test_semantic_repair_hints_are_targeted_by_failure_family() -> None:
    class I:
        def __init__(self, code: str) -> None:
            self.code = code
    text = semantic_repair_hints([I("example.formula_role_missing"), I("personal_production.rule_rejects_sample")])
    assert "Collapse alternative surface forms" in text
    assert "one representative route" in text
    assert "at most 4" in text and "at most 8" in text
    assert "Never enumerate open-class vocabulary" in text
    assert "left-to-right" in text
    assert "pinyin" not in text.lower()


def test_generate_v04_resolves_span_substrings_to_offsets(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path)
    lab.write()
    make_generator(lab.root, v04_transport(CANNED_V04)).generate("en.alpha")
    negative = load_point("en", "en.alpha", lab.root)["examples"][2]
    text = negative["text"]
    assert [(text[s["start"]:s["end"]], s["role"]) for s in negative["spans"]] == [
        ("He", "subject"), ("doesn't", "aux"), ("like", "verb"),
    ]


def test_generate_v04_illustration_follows_point_type_not_the_model(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path, point_type="other")
    lab.write()
    canned = {key: value for key, value in CANNED_V04.items() if key != "morphology"}  # a type-other point asks for none
    make_generator(lab.root, v04_transport(canned)).generate("en.alpha")
    assert load_point("en", "en.alpha", lab.root)["pattern"]["illustration"] == {"kind": "none"}


def test_pinyin_alignment_is_code_derived_and_model_hints_only_override_valid_han() -> None:
    # Missing punctuation/blanks are filled deterministically; a valid contextual
    # polyphonic reading from the model can still override pypinyin.
    assert pinyin_from_pairs("我___吃饭。", [["我", "wǒ"], ["_", "bad"], ["吃", "chī"], ["饭", "fàn"]]) == [
        "wǒ", "", "", "", "chī", "fàn", ""
    ]
    bank = pinyin_from_pairs("银行", [["行", "háng"]])
    assert bank == ["yín", "háng"]


def test_generate_v04_zh_turns_pinyin_pairs_into_per_character_pinyin(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path, "zh", point_type="tense_aspect")
    lab.write()
    llm = LLMClient("anthropic", "claude-haiku-4-5-20251001", api_key="test", cache_dir=lab.root / ".cache",
                     transport=v04_transport(CANNED_V04_ZH))
    outcome = Generator(lang="zh", l1="vi", llm=llm, root=lab.root).generate("zh.le_completion")
    assert outcome.status == "written", outcome.reason
    point = load_point("zh", "zh.le_completion", lab.root)
    assert point["header"]["native_title"] == "动态助词“了”"
    assert point["examples"][0]["pinyin"] == ["wǒ", "men", "chī", "le", "fàn", ""]
    assert point["pattern"]["formula"][0]["pinyin"] == ["dòng", "cí"]
    assert point["common_mistakes"][0]["right_pinyin"][4] == "le"
    assert point["pattern"]["illustration"] == {"kind": "timeline", "timeline": {"shape": "point_past"}}
    report = validate_lang("zh", lab.root)
    assert report.ok, report.issues


def test_generate_v04_zh_normalizes_spaces_in_target_text_before_pinyin(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path, "zh", point_type="tense_aspect")
    lab.write()
    canned = copy.deepcopy(CANNED_V04_ZH)
    canned["examples"][0]["text"] = "我们 吃了饭。"
    canned["examples"][0]["spans"][0]["text"] = "我们"
    canned["examples"][0].pop("pinyin_pairs", None)
    llm = LLMClient("anthropic", "claude-haiku-4-5-20251001", api_key="test", cache_dir=lab.root / ".cache",
                     transport=v04_transport(canned))
    outcome = Generator(lang="zh", l1="vi", llm=llm, root=lab.root).generate("zh.le_completion")
    assert outcome.status == "written", outcome.reason
    point = load_point("zh", "zh.le_completion", lab.root)
    assert point["examples"][0]["text"] == "我们吃了饭。"
    assert len(point["examples"][0]["pinyin"]) == len(point["examples"][0]["text"])


def test_literal_span_recovery_does_not_match_inside_larger_latin_word() -> None:
    pattern = {"formula": [
        {"text": "be", "role": "aux", "label": {"vi": "trợ động từ"}},
        {"text": "V", "role": "verb", "label": {"vi": "động từ"}},
    ]}
    examples = [{"text": "Because things change.", "form": "affirmative", "spans": [
        {"start": 15, "end": 21, "role": "verb"},
    ]}]
    complete_literal_example_spans(examples, pattern)
    assert not any(span["role"] == "aux" for span in examples[0]["spans"])


def test_complete_literal_example_spans_only_recovers_formula_literals() -> None:
    pattern = {"formula": [
        {"text": "S", "role": "subject", "label": {"vi": "chủ ngữ"}},
        {"text": "have/has", "role": "aux", "label": {"vi": "trợ động từ"}},
        {"text": "V3", "role": "verb", "label": {"vi": "phân từ"}},
    ]}
    examples = [{"text": "She has finished.", "form": "affirmative", "spans": [
        {"start": 0, "end": 3, "role": "subject"},
        {"start": 8, "end": 16, "role": "verb"},
    ]}]
    complete_literal_example_spans(examples, pattern)
    spans = {(examples[0]["text"][x["start"]:x["end"]], x["role"]) for x in examples[0]["spans"]}
    assert ("has", "aux") in spans
    assert len([x for x in examples[0]["spans"] if x["role"] == "subject"]) == 1


def test_generate_v04_drops_extra_visual_span_roles_but_keeps_required_role_failures(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path)
    lab.write()
    canned = copy.deepcopy(CANNED_V04)
    canned["examples"][0]["spans"].append({"text": "bank", "role": "place"})
    outcome = make_generator(lab.root, v04_transport(canned)).generate("en.alpha")
    assert outcome.status == "written", outcome.reason
    point = load_point("en", "en.alpha", lab.root)
    assert "place" not in {span["role"] for span in point["examples"][0]["spans"]}


def test_generate_v04_zh_removes_spaces_the_model_puts_around_the_blank(tmp_path: Path) -> None:
    # DeepSeek wrote every zh question of the first v0.4 run as "他 ___ 吃过越南菜。".
    lab = _v04_lab(tmp_path, "zh", point_type="tense_aspect")
    lab.write()
    spaced = _canned_qp("我 ___ 饭。", "了", [("着", "aspect"), ("过", "aspect")], zh=True)
    canned = {**CANNED_V04_ZH, "quick_practice": [spaced, *CANNED_V04_ZH["quick_practice"][1:]]}
    llm = LLMClient("anthropic", "claude-haiku-4-5-20251001", api_key="test", cache_dir=lab.root / ".cache",
                     transport=v04_transport(canned))
    Generator(lang="zh", l1="vi", llm=llm, root=lab.root).generate("zh.le_completion")
    point = load_point("zh", "zh.le_completion", lab.root)
    assert point["quick_practice"][0]["q"] == "我___饭。"
    assert validate_lang("zh", lab.root).ok


def test_generate_v04_wraps_bare_string_locale_fields_when_there_is_one_locale(tmp_path: Path) -> None:
    # DeepSeek's json_object mode (no schema enforcement) returned these as bare strings live.
    lab = _v04_lab(tmp_path)
    lab.write()
    canned = {**CANNED_V04, "summary": "Tóm tắt.", "when_to_use": ["Ý một.", "Ý hai."]}
    make_generator(lab.root, v04_transport(canned)).generate("en.alpha")
    point = load_point("en", "en.alpha", lab.root)
    assert point["header"]["summary"] == {"vi": "Tóm tắt."}
    assert point["when_to_use"] == [{"vi": "Ý một."}, {"vi": "Ý hai."}]
    assert validate_lang("en", lab.root).ok


def test_generate_v04_passes_a_regenerate_note_to_the_model(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path)
    lab.write()
    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={
            "content": [{"type": "tool_use", "name": "emit_grammar_point_v04", "input": _answer(CANNED_V04)}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        })

    make_generator(lab.root, httpx.MockTransport(handler)).generate("en.alpha", regenerate_note="span the base and -s apart")
    assert "span the base and -s apart" in sent[0]["messages"][0]["content"]


def test_generate_v04_keeps_slot_options_and_drops_a_single_one(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path)
    lab.write()
    formula = [
        {**CANNED_V04["formula"][0], "options": [{"text": "He"}, {"text": "She"}, {"text": "It"}]},
        {**CANNED_V04["formula"][1], "options": [{"text": "works"}]},  # one form is not a choice
    ]
    make_generator(lab.root, v04_transport({**CANNED_V04, "formula": formula})).generate("en.alpha")
    slots = load_point("en", "en.alpha", lab.root)["pattern"]["formula"]
    assert slots[0]["options"] == [{"text": "He"}, {"text": "She"}, {"text": "It"}]
    assert "options" not in slots[1]
    assert validate_lang("en", lab.root).ok


def test_generate_v04_needs_point_type(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path)
    lab.points["en.alpha"].pop("point_type")
    lab.write()
    outcome = make_generator(lab.root, v04_transport(CANNED_V04)).generate("en.alpha")
    assert outcome.status == "error"
    assert "point_type" in outcome.reason


def test_resolve_spans_takes_the_next_free_occurrence_and_drops_what_is_absent() -> None:
    text = "The cat saw the other cat."
    spans = resolve_spans(text, [
        {"text": "cat", "role": "subject"}, {"text": "cat", "role": "object"}, {"text": "dog", "role": "other"},
    ])
    assert [(text[s["start"]:s["end"]], s["start"], s["role"]) for s in spans] == [
        ("cat", 4, "subject"), ("cat", 22, "object"),
    ]


def test_resolve_spans_follows_sentence_order_so_an_affix_lands_after_its_base() -> None:
    text = "She sells two books."
    spans = resolve_spans(text, [{"text": "book", "role": "object"}, {"text": "s", "role": "other"}])
    assert [(text[s["start"]:s["end"]], s["start"]) for s in spans] == [("book", 14), ("s", 18)]


def test_generation_schema_v04_asks_only_for_the_illustration_data_the_point_type_needs() -> None:
    common = {"locales": ["vi"], "l1s": ["vi"], "error_tags": ["agreement"], "engine_tags": ["agreement"],
              "contrast_with": [], "zh": False}
    morph = _generation_schema_v04(point_type="morphology", **common)["properties"]
    tense = _generation_schema_v04(point_type="tense_aspect", **common)["properties"]
    other = _generation_schema_v04(point_type="other", **common)["properties"]
    assert "morphology" in morph and "timeline_shape" not in morph
    assert "timeline_shape" in tense and "morphology" not in tense
    assert "timeline_shape" not in other and "morphology" not in other
    # one explanation locale -> plain strings (generate.py files them under it); several -> locale maps
    assert morph["summary"] == {"type": "string", "minLength": 1}
    two = _generation_schema_v04(point_type="other", **{**common, "locales": ["vi", "en"]})["properties"]
    assert two["summary"]["type"] == "object"


def test_generation_schema_v04_bounds_personal_production_rule_size() -> None:
    schema = _generation_schema_v04(
        locales=["vi"], l1s=["vi"], error_tags=["agreement"], engine_tags=["agreement"],
        contrast_with=[], point_type="other", zh=False,
    )
    rule = schema["properties"]["personal_production"]["properties"]["pattern_rule"]["properties"]
    assert rule["slots"]["maxItems"] == PERSONAL_PRODUCTION_MAX_SLOTS == 4
    assert rule["slots"]["items"]["properties"]["any_of"]["maxItems"] == PERSONAL_PRODUCTION_MAX_ANY_OF == 8


def test_v04_prompt_forbids_open_class_vocabulary_enumeration() -> None:
    prompt = PROMPT_PATH_V04.read_text(encoding="utf-8")
    assert "Never enumerate open-class vocabulary" in prompt
    assert "1-4 rule slots total" in prompt
    assert "at most 8 literals" in prompt
    assert "simulate the highlighted spans from left to" in prompt


def test_generate_v04_rejects_with_story(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path)
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


# --- conversion mode: R5 lesson(s) as input (human, 2026-09-28) --------------------------

def _capturing_v04_transport(payload: dict, sent: list[dict]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={
            "content": [{"type": "tool_use", "name": "emit_grammar_point_v04", "input": _answer(payload)}],
            "usage": {"input_tokens": 500, "output_tokens": 300},
        })
    return httpx.MockTransport(handler)


def test_generate_v04_converts_from_r5_and_records_the_source_in_provenance(tmp_path: Path) -> None:
    from grammar_lab.tests.test_r5_source import write_fake_r5

    lab = _v04_lab(tmp_path)
    lab.points["en.alpha"]["source_refs"] = {"r5": ["a1-alpha"]}
    lab.write()
    r5_root = write_fake_r5(tmp_path / "r5")
    correction = {"r5_id": "a1-alpha", "issue": "R5 rule omits -es.", "fix": "Added -es after s/sh/ch/x."}
    sent: list[dict] = []
    llm = LLMClient("anthropic", "claude-haiku-4-5-20251001", api_key="test", cache_dir=lab.root / ".cache",
                     transport=_capturing_v04_transport({**CANNED_V04, "r5_corrections": [correction]}, sent))
    outcome = Generator(lang="en", l1="vi", llm=llm, root=lab.root, r5_root=r5_root).generate("en.alpha")

    assert outcome.status == "written", outcome.reason
    user_text = json.dumps(sent[0]["messages"], ensure_ascii=False)
    assert "Giải thích." in user_text and "He go." in user_text  # the R5 lesson reached the model
    assert "r5_corrections" in json.dumps(sent[0]["tools"])       # and it was asked to report corrections
    point = load_point("en", "en.alpha", lab.root)
    r5_source = point["provenance"]["r5_source"]
    assert re.fullmatch(r"[0-9a-f]{64}", r5_source.pop("content_hash"))  # which R5 text the model was given
    assert r5_source == {"ids": ["a1-alpha"], "content_version": 2, "corrections": [correction]}
    assert validate_lang("en", lab.root).ok


def test_generate_v04_without_r5_refs_asks_for_no_corrections(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path)
    lab.write()
    sent: list[dict] = []
    llm = LLMClient("anthropic", "claude-haiku-4-5-20251001", api_key="test", cache_dir=lab.root / ".cache",
                     transport=_capturing_v04_transport(CANNED_V04, sent))
    Generator(lang="en", l1="vi", llm=llm, root=lab.root).generate("en.alpha")
    assert "r5_corrections" not in json.dumps(sent[0]["tools"])
    assert "r5_source" not in load_point("en", "en.alpha", lab.root)["provenance"]


def test_generate_v04_unknown_r5_id_is_an_error_before_any_call(tmp_path: Path) -> None:
    from grammar_lab.tests.test_r5_source import write_fake_r5

    lab = _v04_lab(tmp_path)
    lab.points["en.alpha"]["source_refs"] = {"r5": ["a1-missing"]}
    lab.write()
    sent: list[dict] = []
    llm = LLMClient("anthropic", "claude-haiku-4-5-20251001", api_key="test", cache_dir=lab.root / ".cache",
                     transport=_capturing_v04_transport(CANNED_V04, sent))
    outcome = Generator(lang="en", l1="vi", llm=llm, root=lab.root, r5_root=write_fake_r5(tmp_path / "r5")).generate("en.alpha")
    assert outcome.status == "error" and "a1-missing" in outcome.reason
    assert sent == []
