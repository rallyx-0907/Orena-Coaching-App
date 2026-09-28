"""One passing and at least one failing case per validate rule (SPEC §5.2).

Each case mutates a known-good lab. Passing cases must produce no issue at
all; failing cases must produce exactly the expected codes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest

from grammar_lab.tests.conftest import Lab


@dataclass(frozen=True)
class Case:
    rule: str
    name: str
    mutate: Callable[[Lab], None]
    expected: frozenset[str] = frozenset()  # empty = must pass cleanly
    lang: str = "en"

    @property
    def id(self) -> str:
        return f"{self.rule}:{'fail' if self.expected else 'pass'}:{self.name}"


def fail(rule: str, name: str, mutate: Callable[[Lab], None], *extra: str, lang: str = "en") -> Case:
    return Case(rule, name, mutate, frozenset({rule, *extra}), lang)


def ok(rule: str, name: str, mutate: Callable[[Lab], None], lang: str = "en") -> Case:
    return Case(rule, name, mutate, frozenset(), lang)


def alpha(lab: Lab) -> dict:
    return lab.points["en.alpha"]


def beta(lab: Lab) -> dict:
    return lab.points["en.beta"]


def block(point: dict, kind: str, nth: int = 0) -> dict:
    return [b for b in point["blocks"] if b["type"] == kind][nth]


def zh(lab: Lab) -> dict:
    return lab.points["zh.le_completion"]


def set_level(point: dict, value: str, rank: int) -> None:
    point["level"].update(value=value, rank=rank)


def nothing(lab: Lab) -> None:
    return None


CASES = [
    # --- JSON Schema v0.2 ---------------------------------------------------------------
    ok("schema.invalid", "baseline", nothing),
    ok("schema.invalid", "timeline future_plan", lambda lab: block(alpha(lab), "timeline").update(kind="future_plan")),
    ok("schema.invalid", "approved with review", lambda lab: alpha(lab).update(
        status="approved", review={"reviewer": "owner", "reviewed_at": "2026-09-26T10:00:00+07:00", "seconds": 42})),
    fail("schema.invalid", "timeline kind outside enum", lambda lab: block(alpha(lab), "timeline").update(kind="future_perfect")),
    fail("schema.invalid", "pitfall l1 as string", lambda lab: block(alpha(lab), "pitfall").update(l1="vi")),
    fail("schema.invalid", "pitfall without error_tag", lambda lab: block(alpha(lab), "pitfall").pop("error_tag")),
    fail("schema.invalid", "stored bridge block", lambda lab: alpha(lab)["blocks"].append(
        {"type": "bridge", "l1": "vi", "realization_id": "zh.le_completion"})),
    fail("schema.invalid", "en point on jlpt scale", lambda lab: alpha(lab).update(
        level={"framework": "jlpt", "value": "N5", "rank": 1})),
    fail("schema.invalid", "level value outside cefr", lambda lab: set_level(alpha(lab), "A3", 1)),
    fail("schema.invalid", "locale key zh instead of zh-Hans", lambda lab: alpha(lab)["summary"].update(zh="语法")),
    fail("schema.invalid", "missing version", lambda lab: alpha(lab).pop("version")),
    fail("schema.invalid", "missing provenance", lambda lab: alpha(lab).pop("provenance")),
    fail("schema.invalid", "approved without review", lambda lab: alpha(lab).update(status="approved")),
    fail("schema.invalid", "rejected without reason", lambda lab: alpha(lab).update(
        status="rejected", review={"reviewer": "owner", "reviewed_at": "2026-09-26T10:00:00Z", "seconds": 5})),
    fail("schema.invalid", "dotted error tag", lambda lab: alpha(lab).update(error_tags=["grammar.sva.x"])),
    fail("schema.invalid", "function file entry without title",
         lambda lab: lab.functions["functions"][0].pop("title")),
    # --- files ------------------------------------------------------------------------
    ok("file.invalid_json", "baseline", nothing),
    fail("file.invalid_json", "broken point file", lambda lab: lab.raw_files.update({"en.gamma.json": "{not json"})),
    ok("file.missing_manifest", "baseline", nothing),
    fail("file.missing_manifest", "no _set.json", lambda lab: setattr(lab, "manifest", None)),
    ok("file.id_mismatch", "baseline", nothing),
    fail("file.id_mismatch", "file named after another id", lambda lab: lab.file_names.update({"en.alpha": "en.other.json"})),
    ok("file.lang_mismatch", "inventory item of the right language", lambda lab: setattr(lab, "inventory", [
        {"inv_id": "en.inv.0001", "label": "x", "level": {"framework": "cefr", "value": "A1"},
         "function": "fn.alpha", "sources": {"egp": ["E1"]}, "maps_to": ["en.alpha"], "status": "approved"}])),
    fail("file.lang_mismatch", "manifest of another language", lambda lab: lab.manifest.update(target_lang="ja")),
    fail("file.lang_mismatch", "zh inventory item in en.yaml", lambda lab: setattr(lab, "inventory", [
        {"inv_id": "zh.inv.0001", "label": "x", "level": {"framework": "hsk3", "value": "1"},
         "function": "fn.alpha", "sources": {"hsk3": ["H1"]}, "maps_to": [], "status": "proposed"}])),
    # --- level ------------------------------------------------------------------------
    ok("level.rank_mismatch", "B2 has rank 4", lambda lab: set_level(beta(lab), "B2", 4)),
    fail("level.rank_mismatch", "A1 with rank 2", lambda lab: set_level(alpha(lab), "A1", 2)),
    ok("level.rank_mismatch", "hsk3 level 3 has rank 3", lambda lab: set_level(zh(lab), "3", 3), lang="zh"),
    fail("level.rank_mismatch", "hsk3 level 3 with rank 1", lambda lab: set_level(zh(lab), "3", 1), lang="zh"),
    # --- example ----------------------------------------------------------------------
    ok("example.seg_text_mismatch", "many segments", lambda lab: block(alpha(lab), "example").update(
        text="She works in a bank.", seg=[["She"], [" "], ["works", "target"], [" in"], [" a bank."]])),
    fail("example.seg_text_mismatch", "text differs", lambda lab: block(alpha(lab), "example").update(text="She works at a bank.")),
    fail("example.seg_text_mismatch", "missing space", lambda lab: block(alpha(lab), "example").update(
        seg=[["She"], ["works", "target"], [" in a bank."]])),
    ok("example.no_target", "target on last segment", lambda lab: block(alpha(lab), "example").update(
        text="She works.", seg=[["She "], ["works.", "target"]])),
    fail("example.no_target", "no label", lambda lab: block(alpha(lab), "example").update(
        seg=[["She "], ["works"], [" in a bank."]])),
    fail("example.no_target", "other label only", lambda lab: block(alpha(lab), "example").update(
        seg=[["She ", "subject"], ["works"], [" in a bank."]])),
    ok("example.ruby_length", "ruby parallel to seg", nothing, lang="zh"),
    fail("example.ruby_length", "ruby too short", lambda lab: block(zh(lab), "example").update(ruby=["wǒmen", "chī le"]), lang="zh"),
    # --- check ------------------------------------------------------------------------
    ok("check.answer_out_of_range", "answer is last index", lambda lab: block(alpha(lab), "check")["items"][0].update(
        options=["go", "goes", "going"], answer=2)),
    fail("check.answer_out_of_range", "answer past the end", lambda lab: block(alpha(lab), "check")["items"][0].update(answer=2)),
    ok("check.duplicate_options", "distinct options", lambda lab: block(alpha(lab), "check")["items"][0].update(
        options=["go", "goes", "gone"])),
    fail("check.duplicate_options", "same option twice", lambda lab: block(alpha(lab), "check")["items"][0].update(
        options=["go", "goes", "go"])),
    fail("check.duplicate_options", "differs only by case and spacing", lambda lab: block(alpha(lab), "check")["items"][0].update(
        options=["goes", "go", " Goes "], answer=0)),
    # --- pitfall ----------------------------------------------------------------------
    ok("pitfall.same_wrong_right", "one letter apart", lambda lab: block(alpha(lab), "pitfall").update(
        wrong="He go.", right="He goes.")),
    fail("pitfall.same_wrong_right", "identical", lambda lab: block(alpha(lab), "pitfall").update(
        wrong="He goes.", right="He goes.")),
    # --- references -------------------------------------------------------------------
    ok("ref.unknown_function", "baseline", nothing),
    fail("ref.unknown_function", "point function missing", lambda lab: alpha(lab).update(function="fn.missing")),
    fail("ref.unknown_function", "inventory function missing", lambda lab: setattr(lab, "inventory", [
        {"inv_id": "en.inv.0001", "label": "x", "level": {"framework": "cefr", "value": "A1"},
         "function": "fn.missing", "sources": {"egp": ["E1"]}, "maps_to": [], "status": "proposed"}])),
    ok("ref.unknown_prereq", "baseline", nothing),
    fail("ref.unknown_prereq", "prereq missing", lambda lab: beta(lab).update(prereqs=["en.alpha", "en.gamma"])),
    ok("ref.unknown_contrast", "baseline", nothing),
    fail("ref.unknown_contrast", "contrasts entry missing", lambda lab: beta(lab).update(contrasts=["en.alpha", "en.gamma"])),
    fail("ref.unknown_contrast", "contrast block with missing point", lambda lab: (
        beta(lab).update(contrasts=["en.gamma"]), block(beta(lab), "contrast").update(**{"with": "en.gamma"}))),
    ok("ref.contrast_block_unlisted", "baseline", nothing),
    fail("ref.contrast_block_unlisted", "with not in contrasts", lambda lab: beta(lab).update(contrasts=[])),
    ok("ref.prereq_cycle", "chain without cycle", nothing),
    fail("ref.prereq_cycle", "two-point cycle", lambda lab: (
        set_level(alpha(lab), "A2", 2), alpha(lab).update(prereqs=["en.beta"]))),
    fail("ref.prereq_cycle", "self prereq", lambda lab: alpha(lab).update(prereqs=["en.alpha"])),
    ok("ref.prereq_level", "prereq at the same level", lambda lab: set_level(alpha(lab), "A2", 2)),
    fail("ref.prereq_level", "prereq above the point", lambda lab: set_level(alpha(lab), "B1", 3)),
    ok("ref.realization_missing", "baseline", nothing),
    fail("ref.realization_missing", "function forgets the point",
         lambda lab: lab.functions["functions"][0]["realizations"].update(en=["en.alpha"])),
    ok("ref.unknown_realization", "planned points are not checked",
       lambda lab: lab.functions["functions"][0].update(planned={"en": ["en.gamma"], "ja": ["ja.ta_form"]})),
    fail("ref.unknown_realization", "realization missing",
         lambda lab: lab.functions["functions"][0]["realizations"]["en"].append("en.gamma")),
    # --- error tags -------------------------------------------------------------------
    ok("error_tag.list_missing", "baseline", nothing),
    fail("error_tag.list_missing", "no error_tags.json", lambda lab: setattr(lab, "error_tags", None)),
    fail("error_tag.list_missing", "no list for the language", lambda lab: lab.error_tags["languages"].pop("en")),
    ok("error_tag.unknown", "several engine tags", lambda lab: alpha(lab).update(error_tags=["agreement", "article", "other"])),
    fail("error_tag.unknown", "point tag not in engine list", lambda lab: alpha(lab).update(error_tags=["agreement", "sva_3sg"])),
    fail("error_tag.unknown", "pitfall tag not in engine list", lambda lab: (
        alpha(lab).update(error_tags=["sva_3sg"]), block(alpha(lab), "pitfall").update(error_tag="sva_3sg"))),
    ok("error_tag.pitfall_unlisted", "pitfall tag listed", lambda lab: (
        alpha(lab).update(error_tags=["agreement", "tense"]), block(alpha(lab), "pitfall").update(error_tag="tense"))),
    fail("error_tag.pitfall_unlisted", "pitfall tag not on the point", lambda lab: block(alpha(lab), "pitfall").update(error_tag="tense")),
    # --- locales ----------------------------------------------------------------------
    ok("locale.missing", "two declared locales, all present", lambda lab: _all_locales(lab, ["vi", "en"])),
    fail("locale.missing", "example translation lacks a locale", lambda lab: (
        _all_locales(lab, ["vi", "en"]), block(alpha(lab), "example")["tr"].pop("en"))),
    fail("locale.missing", "rule_table note lacks a locale", lambda lab: (
        _all_locales(lab, ["vi", "en"]), block(alpha(lab), "rule_table")["rows"][0][2].pop("vi"))),
    fail("locale.missing", "function title lacks a locale", lambda lab: (
        _all_locales(lab, ["vi", "en"]), lab.functions["functions"][0]["title"].pop("en"))),
    ok("locale.l1_undeclared", "declared second L1", lambda lab: (
        lab.manifest.update(l1=["vi", "zh"]), block(alpha(lab), "pitfall").update(l1=["vi", "zh"]))),
    fail("locale.l1_undeclared", "pitfall for undeclared L1", lambda lab: block(alpha(lab), "pitfall").update(l1=["vi", "zh"])),
    # --- simplified Chinese only ------------------------------------------------------
    ok("zh.traditional_char", "simplified content with 乾/於", lambda lab: block(zh(lab), "pitfall").update(
        wrong="他於昨天吃饭。", right="他于昨天吃了饼乾。"), lang="zh"),
    fail("zh.traditional_char", "traditional in example", lambda lab: block(zh(lab), "example").update(
        text="我們吃了飯。", seg=[["我們"], ["吃了", "target"], ["飯"], ["。"]]), lang="zh"),
    fail("zh.traditional_char", "traditional in check option", lambda lab: block(zh(lab), "check")["items"][0].update(
        options=["吃了", "吃過"]), lang="zh"),
    fail("zh.traditional_char", "traditional in zh-Hans title", lambda lab: zh(lab)["title"].update(
        {"zh-Hans": "動態助詞“了”"}), lang="zh"),
    ok("zh.traditional_char", "zh-Hans explanation of an en point", lambda lab: _zh_explanations(lab, "这是现在时。")),
    fail("zh.traditional_char", "traditional zh-Hans explanation of an en point",
         lambda lab: _zh_explanations(lab, "這是現在時。")),
    fail("zh.traditional_char", "traditional zh-Hans function title",
         lambda lab: lab.functions["functions"][0]["title"].update({"zh-Hans": "習慣"})),
    # --- inventory --------------------------------------------------------------------
    ok("inventory.duplicate_id", "distinct ids", lambda lab: setattr(lab, "inventory", [_inv("en.inv.0001"), _inv("en.inv.0002")])),
    fail("inventory.duplicate_id", "same id twice", lambda lab: setattr(lab, "inventory", [_inv("en.inv.0001"), _inv("en.inv.0001")])),
    ok("schema.invalid", "inventory out_of_scope with reason", lambda lab: setattr(lab, "inventory", [
        {**_inv("en.inv.0001"), "status": "out_of_scope", "reason": "covered by en.alpha"}])),
    fail("schema.invalid", "inventory out_of_scope without reason", lambda lab: setattr(lab, "inventory", [
        {**_inv("en.inv.0001"), "status": "out_of_scope"}])),
    fail("schema.invalid", "inventory level on wrong scale", lambda lab: setattr(lab, "inventory", [
        {**_inv("en.inv.0001"), "level": {"framework": "cefr", "value": "N5"}}])),
    # --- story (schema v0.3, STORY_SPEC.md) --------------------------------------------
    ok("story.character_unknown", "characters drawn from the cast", lambda lab: _with_story(alpha(lab))),
    fail("story.character_unknown", "character not in cast/cast.yaml", lambda lab: (
        story := _with_story(alpha(lab)), story.update(characters=["NotInCast"]))),
    ok("error_tag.story_alternative_unlisted", "alternative tag listed on the point",
       lambda lab: _with_story(alpha(lab))),
    fail("error_tag.story_alternative_unlisted", "alternative tag not on the point", lambda lab: (
        story := _with_story(alpha(lab)), story["alternatives"][0].update(error_tags=["tense"]))),
    ok("story.length_out_of_range", "150-250 words vi", lambda lab: _with_story(alpha(lab))),
    fail("story.length_out_of_range", "too short", lambda lab: (
        story := _with_story(alpha(lab)),
        story.update(scene={"vi": "Ngắn."}, need={"vi": "Ngắn."}, anchor={"vi": "Ngắn."}),
        story["alternatives"][0].update(consequence={"vi": "Ngắn."}))),
    ok("story.anchor_short_too_long", "anchor_short at or under 20 words", lambda lab: _with_story(alpha(lab))),
    fail("story.anchor_short_too_long", "anchor_short over 20 words", lambda lab: _with_story(alpha(lab)).update(
        anchor_short={"vi": " ".join(["từ"] * 21)})),
    ok("story.short_not_one_line", "short forms have no newline", lambda lab: _with_story(alpha(lab))),
    fail("story.short_not_one_line", "alternative short has a newline", lambda lab: (
        story := _with_story(alpha(lab)), story["alternatives"][0]["short"].update(vi="dòng một\ndòng hai"))),
    fail("story.short_not_one_line", "anchor_short has a newline",
         lambda lab: _with_story(alpha(lab)).update(anchor_short={"vi": "dòng một\ndòng hai"})),
]


def _inv(inv_id: str) -> dict:
    return {"inv_id": inv_id, "label": "Third person -s", "level": {"framework": "cefr", "value": "A1"},
            "function": "fn.alpha", "sources": {"egp": ["E1"]}, "maps_to": ["en.alpha"], "status": "approved"}


def _all_locales(lab: Lab, locales: list[str]) -> None:
    """Declare ``locales`` and fill every localized field of every point with them."""
    from grammar_lab.pipeline.validate import _locale_maps

    lab.manifest["explanation_locales"] = locales
    for point in lab.points.values():
        for _, mapping in list(_locale_maps(point)):
            for locale in locales:
                mapping.setdefault(locale, f"text {locale}")
    for function in lab.functions["functions"]:
        for locale in locales:
            function["title"].setdefault(locale, f"title {locale}")


def _zh_explanations(lab: Lab, text: str) -> None:
    _all_locales(lab, ["vi", "zh-Hans"])
    alpha(lab)["summary"]["zh-Hans"] = text
    lab.functions["functions"][0]["title"]["zh-Hans"] = "习惯"


def _valid_story() -> dict:
    """A schema-valid story block, ~180 words (vi) -- inside STORY_SPEC.md's 150-250 range."""
    return {
        "type": "story",
        "theme": "daily",
        "characters": ["Alex", "Sam"],
        "scene": {"vi": (
            "Alex vừa chuyển đến một căn hộ mới gần trung tâm thành phố được vài hôm. Sáng thứ hai, "
            "Alex đứng trong bếp trống, nhìn tủ lạnh trống không, và nhận ra mình chưa mua thức ăn cho "
            "cả tuần. Ngoài cửa sổ, khu chợ nhỏ đầu phố vừa mở cửa, người bán hàng bắt đầu bày rau củ "
            "tươi ra sạp."
        )},
        "need": {"vi": (
            "Alex cần nói với người bạn cùng phòng, Sam, rằng mình đã sống ở căn hộ này được vài ngày "
            "rồi, không phải chỉ mới hôm nay, để Sam hiểu đúng tình hình mà rủ nhau đi chợ mua đồ ăn "
            "chung cho cả tuần."
        )},
        "form_in_action": {
            "sentences": ["I have lived here for three days."],
            "slots": [
                {"role": "person", "value": "I", "constraint": "a personal pronoun or proper noun"},
                {"role": "place", "value": "here", "constraint": "a place reference"},
            ],
        },
        "alternatives": [
            {
                "sentence": "I live here for three days.",
                "error_tags": ["agreement"],
                "consequence": {"vi": (
                    "Nếu nói sai thì Sam sẽ hiểu rằng Alex chỉ mới chuyển đến đúng vào lúc đó, chứ không "
                    "phải đã ở đây một khoảng thời gian, nên có thể ngạc nhiên khi thấy bếp đã bừa bộn "
                    "như vậy."
                )},
                "short": {"vi": "Sam tưởng Alex vừa mới chuyển đến."},
                "slots": [{"role": "person", "value": "I", "constraint": "a personal pronoun or proper noun"}],
            },
        ],
        "anchor": {"vi": (
            "Hãy nghĩ đến một sợi dây nối liền từ quá khứ đến hiện tại: hành động hay trạng thái bắt "
            "đầu trước đó và vẫn còn đúng ngay lúc này, chưa hề kết thúc."
        )},
        "anchor_short": {"vi": "Một sợi dây nối quá khứ với hiện tại, chưa đứt."},
    }


def _with_story(point: dict) -> dict:
    """Bump ``point`` to schema_version 0.3 and append a valid story block; returns the block."""
    point["schema_version"] = "0.3"
    story = _valid_story()
    point["blocks"].append(story)
    return story


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_rule(case: Case, tmp_path) -> None:
    lab = Lab(tmp_path, case.lang)
    case.mutate(lab)
    report = lab.validate()
    assert report.codes() == set(case.expected), [issue.to_dict() for issue in report.issues]
    for issue in report.issues:
        assert issue.reason == f"validate:{issue.code}"


def test_every_documented_rule_has_a_passing_and_a_failing_case() -> None:
    from grammar_lab.pipeline import validate

    documented = {
        line.split()[0] for line in validate.__doc__.splitlines() if line[:1].isalpha() and "." in line.split()[0]
    }
    failing = {code for case in CASES for code in case.expected}
    passing = {case.rule for case in CASES if not case.expected}
    assert documented, "rule table missing from validate.__doc__"
    assert documented <= failing, sorted(documented - failing)
    assert documented <= passing, sorted(documented - passing)
