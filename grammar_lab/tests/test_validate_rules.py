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
    ok("schema.invalid", "approved with review", lambda lab: (
        _all_locales(lab, ["vi", "en"]), alpha(lab).update(
            status="approved", review={"reviewer": "owner", "reviewed_at": "2026-09-26T10:00:00+07:00", "seconds": 42}))),
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
        beta(lab).update(contrasts=["en.gamma"]), alpha(lab).update(contrasts=[]),
        block(beta(lab), "contrast").update(**{"with": "en.gamma"}))),
    ok("ref.contrast_block_unlisted", "baseline", nothing),
    fail("ref.contrast_block_unlisted", "with not in contrasts", lambda lab: (beta(lab).update(contrasts=[]), alpha(lab).update(contrasts=[]))),
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
    fail("locale.missing", "example translation lacks en on an approved point", lambda lab: (
        _all_locales(lab, ["vi", "en"]), _approve(alpha(lab)), block(alpha(lab), "example")["tr"].pop("en"))),
    ok("locale.missing", "a draft point may lack en", lambda lab: (
        _all_locales(lab, ["vi", "en"]), block(alpha(lab), "example")["tr"].pop("en"))),
    fail("locale.missing", "a draft point still needs vi", lambda lab: (
        _all_locales(lab, ["vi", "en"]), block(alpha(lab), "example")["tr"].pop("vi"))),
    fail("locale.missing", "rule_table note lacks a locale", lambda lab: (
        _all_locales(lab, ["vi", "en"]), block(alpha(lab), "rule_table")["rows"][0][2].pop("vi"))),
    fail("locale.missing", "function title lacks a locale", lambda lab: (
        _all_locales(lab, ["vi", "en"]), lab.functions["functions"][0]["title"].pop("en"))),
    ok("locale.l1_undeclared", "declared second L1", lambda lab: (
        lab.manifest.update(l1=["vi", "zh"]), block(alpha(lab), "pitfall").update(l1=["vi", "zh"]))),
    fail("locale.l1_undeclared", "pitfall for undeclared L1", lambda lab: block(alpha(lab), "pitfall").update(l1=["vi", "zh"])),
    # --- v0.4 patch: sub, sequence, personal_production, pinyin scope, contrasts, aliases ------------
    ok("header.sub_missing", "approved with sub", lambda lab: _approved_v04(lab, sub=True)),
    fail("header.sub_missing", "approved without sub", lambda lab: _approved_v04(lab, sub=False, sequence=True)),
    ok("point.sequence_missing", "approved with sequence", lambda lab: _approved_v04(lab, sub=True, sequence=True)),
    fail("point.sequence_missing", "approved without sequence", lambda lab: _approved_v04(lab, sub=True, sequence=False)),
    ok("personal_production.rule_invalid", "a valid rule", lambda lab: _with_production(lab)),
    fail("personal_production.rule_invalid", "a slot with both any_of and regex", lambda lab: _with_production(
        lab, slots=[{"role": "marker", "any_of": ["two"], "regex": "two"}])),
    fail("personal_production.rule_invalid", "a regex that does not compile", lambda lab: _with_production(
        lab, slots=[{"role": "marker", "regex": "("}])),
    ok("personal_production.rule_role_not_in_formula", "roles of the formula", lambda lab: _with_production(lab)),
    fail("personal_production.rule_role_not_in_formula", "a role the formula lacks", lambda lab: _with_production(
        lab, slots=[{"role": "aux", "any_of": ["have"]}])),
    ok("personal_production.rule_rejects_sample", "the rule matches the sample", lambda lab: _with_production(lab)),
    fail("personal_production.rule_rejects_sample", "the rule misses the sample", lambda lab: _with_production(
        lab, sample="I have a cat.", slots=[{"role": "marker", "any_of": ["two", "three"]}])),
    ok("personal_production.rule_rejects_example", "the rule matches the example", lambda lab: _with_production(lab)),
    fail("personal_production.rule_rejects_example", "the rule is stricter than the example", lambda lab: _with_production(
        lab, sample="I have ten cats.", slots=[{"role": "marker", "any_of": ["ten"]}])),
    ok("zh.pinyin_field_unlisted", "Han in an explanation is not scanned", lambda lab: (
        point := _with_v04_zh(lab), point["common_mistakes"][0].update(reason={"vi": "Bổ ngữ như 完, 好 cần 了."})),
        lang="zh"),
    fail("zh.pinyin_field_unlisted", "a flat field outside the pinyin table with Han", lambda lab: (
        point := _with_v04_zh(lab), point.update(zh_note="含汉字"),
        setattr(lab, "schema_patch", lambda schema: schema["$defs"]["grammar_point"]["properties"].update(
            zh_note={"type": "string"}))), lang="zh"),
    ok("anchors.missing", "unanchored is a valid answer", lambda lab: _with_v04(alpha(lab))),
    fail("anchors.missing", "no source_anchors on a v0.4 point", lambda lab: _with_v04(alpha(lab)).pop("source_anchors")),
    ok("contrasts.asymmetric", "both directions listed", nothing),
    fail("contrasts.asymmetric", "only one direction listed", lambda lab: alpha(lab).update(contrasts=[])),
    ok("aliases.duplicate", "distinct R5 ids", lambda lab: (
        alpha(lab).update(aliases=["a1-x"]), beta(lab).update(aliases=["a1-y"]))),
    fail("aliases.duplicate", "one R5 id on two points", lambda lab: (
        alpha(lab).update(aliases=["a1-x"]), beta(lab).update(aliases=["a1-x"]))),
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
        story.update(scene={"vi": "Ngắn."}, need={"vi": "Ngắn."}, reveal={"vi": "Ngắn."}, teaser={"vi": "Ngắn."}),
        story["hook"].update(text={"vi": "Ngắn."}),
        story["alternatives"][0].update(consequence={"vi": "Ngắn."}))),
    ok("story.reveal_short_too_long", "reveal_short at or under 20 words", lambda lab: _with_story(alpha(lab))),
    fail("story.reveal_short_too_long", "reveal_short over 20 words", lambda lab: _with_story(alpha(lab)).update(
        reveal_short={"vi": " ".join(["từ"] * 21)})),
    ok("story.short_not_one_line", "short forms have no newline", lambda lab: _with_story(alpha(lab))),
    fail("story.short_not_one_line", "alternative short has a newline", lambda lab: (
        story := _with_story(alpha(lab)), story["alternatives"][0]["short"].update(vi="dòng một\ndòng hai"))),
    fail("story.short_not_one_line", "reveal_short has a newline",
         lambda lab: _with_story(alpha(lab)).update(reveal_short={"vi": "dòng một\ndòng hai"})),
    ok("story.forbidden_phrase", "no banned phrase", lambda lab: _with_story(alpha(lab))),
    fail("story.forbidden_phrase", "fairy-tale opener in scene", lambda lab: (
        story := _with_story(alpha(lab)),
        story["scene"].update(vi="Ngày xửa ngày xưa. " + story["scene"]["vi"]))),
    # --- v0.4 fixed content blocks (GRAMMAR_CONTENT_CONTRACT.md) -----------------------
    ok("header.level_mismatch", "header level equals the point level", lambda lab: _with_v04(alpha(lab))),
    fail("header.level_mismatch", "header level differs", lambda lab: (
        point := _with_v04(alpha(lab)), point["header"]["level"].update(value="A2", rank=2))),
    ok("illustration.kind_mismatch", "morphology point, morphology illustration", lambda lab: _with_v04(alpha(lab))),
    fail("illustration.kind_mismatch", "tense_aspect point drawn as morphology", lambda lab: (
        point := _with_v04(alpha(lab)), point.update(point_type="tense_aspect"))),
    fail("schema.invalid", "morphology illustration without items", lambda lab: (
        point := _with_v04(alpha(lab)), point["pattern"]["illustration"].pop("morphology"))),
    fail("schema.invalid", "v0.4 point keeps a top-level title", lambda lab: (
        point := _with_v04(alpha(lab)), point.update(title={"vi": "Tiêu đề"}))),
    ok("example.span_invalid", "span within text bounds", lambda lab: _with_v04(alpha(lab))),
    fail("example.span_invalid", "span end beyond text length", lambda lab: (
        point := _with_v04(alpha(lab)), point["examples"][0]["spans"][0].update(end=999))),
    fail("example.span_invalid", "span start >= end", lambda lab: (
        point := _with_v04(alpha(lab)), point["examples"][0]["spans"][0].update(start=5, end=5))),
    ok("example.form_without_variant", "affirmative example", lambda lab: _with_v04(alpha(lab))),
    fail("example.form_without_variant", "negative example with no negative formula", lambda lab: (
        point := _with_v04(alpha(lab)), point["examples"][0].update(form="negative"))),
    ok("example.formula_role_missing", "every required role spanned", lambda lab: _with_v04(alpha(lab))),
    ok("example.formula_role_missing", "an optional slot may go unspanned", lambda lab: (
        point := _with_v04(alpha(lab)),
        point["pattern"]["formula"].append(_slot("in the house", "place", "nơi chốn", optional=True)))),
    fail("example.formula_role_missing", "marker slot not spanned", lambda lab: (
        point := _with_v04(alpha(lab)), point["examples"][0]["spans"].pop(0))),
    ok("example.span_role_not_in_formula", "span roles all in the formula", lambda lab: _with_v04(alpha(lab))),
    fail("example.span_role_not_in_formula", "extra span role outside the formula", lambda lab: (
        point := _with_v04(alpha(lab)), point["examples"][0]["spans"].append({"start": 0, "end": 1, "role": "subject"}))),
    ok("zh.pinyin_invalid", "per-character toned pinyin everywhere", lambda lab: _with_v04_zh(lab), lang="zh"),
    fail("zh.pinyin_invalid", "example pinyin shorter than text", lambda lab: (
        point := _with_v04_zh(lab), point["examples"][0].update(pinyin=["wǒ"])), lang="zh"),
    fail("zh.pinyin_invalid", "tone number instead of tone mark", lambda lab: (
        point := _with_v04_zh(lab), point["examples"][0]["pinyin"].__setitem__(0, "wo3")), lang="zh"),
    fail("zh.pinyin_invalid", "punctuation given a syllable", lambda lab: (
        point := _with_v04_zh(lab), point["examples"][0]["pinyin"].__setitem__(5, "ju")), lang="zh"),
    fail("zh.pinyin_invalid", "formula slot without pinyin", lambda lab: (
        point := _with_v04_zh(lab), point["pattern"]["formula"][0].pop("pinyin")), lang="zh"),
    fail("zh.pinyin_invalid", "common mistake without pinyin", lambda lab: (
        point := _with_v04_zh(lab), point["common_mistakes"][0].pop("wrong_pinyin")), lang="zh"),
    ok("quick_practice.blank_invalid", "one blank per question", lambda lab: _with_v04(alpha(lab))),
    fail("quick_practice.blank_invalid", "no blank", lambda lab: (
        point := _with_v04(alpha(lab)), point["quick_practice"][0].update(q="I have two cats."))),
    ok("quick_practice.answer_tagged", "correct option untagged", lambda lab: _with_v04(alpha(lab))),
    fail("quick_practice.answer_tagged", "correct option carries a tag", lambda lab: (
        point := _with_v04(alpha(lab)), point["quick_practice"][0]["options"][1].update(error_tag="agreement"))),
    ok("quick_practice.distractor_untagged", "every wrong option tagged", lambda lab: _with_v04(alpha(lab))),
    fail("quick_practice.distractor_untagged", "wrong option with no learner error", lambda lab: (
        point := _with_v04(alpha(lab)), point["quick_practice"][0]["options"][0].update(error_tag=None))),
    ok("quick_practice.distractor_misspelling", "distractors are grammar mistakes", lambda lab: _with_v04(alpha(lab))),
    fail("quick_practice.distractor_misspelling", "a distractor that is only a misspelling", lambda lab: (
        point := _with_v04(alpha(lab)),
        point["quick_practice"][0]["options"][0].update(text="cates", error_tag="spelling"),
        lab.error_tags["languages"]["en"]["tags"].append("spelling"))),
    ok("formula.option_duplicate", "a slot with distinct options", lambda lab: (
        point := _with_v04(alpha(lab)),
        point["pattern"]["formula"][0].update(options=[{"text": "two"}, {"text": "many"}]))),
    fail("formula.option_duplicate", "the same option twice", lambda lab: (
        point := _with_v04(alpha(lab)),
        point["pattern"]["formula"][0].update(options=[{"text": "two"}, {"text": "Two"}]))),
    fail("formula.slot_has_joiner", "an option carrying '+'", lambda lab: (
        point := _with_v04(alpha(lab)),
        point["pattern"]["formula"][0].update(options=[{"text": "two"}, {"text": "a + few"}]))),
    fail("zh.pinyin_invalid", "a zh slot option without pinyin", lambda lab: (
        point := _with_v04_zh(lab),
        point["pattern"]["formula"][1].update(options=[{"text": "了", "pinyin": ["le"]}, {"text": "过"}])), lang="zh"),
    ok("zh.whitespace", "zh text written without spaces", lambda lab: _with_v04_zh(lab), lang="zh"),
    fail("zh.whitespace", "spaces around the blank in a zh question", lambda lab: (
        point := _with_v04_zh(lab),
        point["quick_practice"][0].update(q="我 ___ 饭。", q_pinyin=["wǒ", "", "", "", "", "", "fàn", ""])),
        lang="zh"),
    fail("zh.whitespace", "a space between Han characters in a zh example", lambda lab: (
        point := _with_v04_zh(lab),
        point["examples"][0].update(text="我们 吃了饭。", pinyin=["wǒ", "men", "", "chī", "le", "fàn", ""])),
        lang="zh"),
    ok("formula.slot_has_joiner", "slots without '+'", lambda lab: _with_v04(alpha(lab))),
    fail("formula.slot_has_joiner", "a slot carrying its own '+'", lambda lab: (
        point := _with_v04(alpha(lab)), point["pattern"]["formula"][1].update(text="+ -s"))),
    fail("error_tag.unknown", "distractor tag not an engine label", lambda lab: (
        point := _with_v04(alpha(lab)), point["quick_practice"][0]["options"][0].update(error_tag="spelling_x"))),
    ok("common_mistake.same_wrong_right", "wrong differs from right", lambda lab: _with_v04(alpha(lab))),
    fail("common_mistake.same_wrong_right", "wrong equals right", lambda lab: (
        point := _with_v04(alpha(lab)), point["common_mistakes"][0].update(right="I have two cat."))),
    ok("error_tag.common_mistake_unlisted", "error_tag listed on the point", lambda lab: _with_v04(alpha(lab))),
    fail("error_tag.common_mistake_unlisted", "error_tag not on the point", lambda lab: (
        point := _with_v04(alpha(lab)), point["common_mistakes"][0].update(error_tag="tense"))),
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
    """A schema-valid story block, inside STORY_SPEC.md/VOICE.md's 150-250 word (vi) range."""
    return {
        "type": "story",
        "theme": "daily",
        "mode": "everyday",
        "characters": ["Alex", "Sam"],
        "hook": {"hook_type": "insider", "text": {"vi": (
            "Người bản xứ nghe 'I live here for three days' là thấy lệch ngay, dù không phải "
            "lúc nào cũng nói được chính xác vì sao."
        )}},
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
        "reveal": {"vi": (
            "Tiếng Việt không có thì hoàn thành: 'đã' chỉ nói việc từng xảy ra, không nói việc đó "
            "còn kéo dài đến bây giờ. Vì vậy người Việt phải học thêm một trục thời gian hoàn toàn "
            "mới, không phải chỉ thêm một từ vào câu."
        )},
        "reveal_short": {"vi": "Tiếng Việt không có thì hoàn thành -- đây là một trục thời gian mới."},
        "teaser": {"vi": "Vậy vì sao thêm đúng một trợ động từ lại đổi cả câu chuyện?"},
    }


def _with_story(point: dict) -> dict:
    """Bump ``point`` to schema_version 0.3 and append a valid story block; returns the block."""
    point["schema_version"] = "0.3"
    story = _valid_story()
    point["blocks"].append(story)
    return story


def _slot(text: str, role: str, label: str, **extra: object) -> dict:
    return {"text": text, "role": role, "label": {"vi": label}, **extra}


def _qp(q: str, right: str, wrong: str, tag: str) -> dict:
    return {
        "q": q,
        "options": [{"text": wrong, "error_tag": tag}, {"text": right, "error_tag": None}],
        "answer": 1,
        "explain": {"vi": "Giải thích."},
    }


_ZH_OPTION_PINYIN = {"了": ["le"], "着": ["zhe"], "过": ["guo"]}


def _qp_zh(q: str, q_pinyin: list[str], right: str, wrong: str, tag: str) -> dict:
    item = _qp(q, right, wrong, tag)
    item["q_pinyin"] = q_pinyin
    for option in item["options"]:
        option["pinyin"] = _ZH_OPTION_PINYIN[option["text"]]
    return item


def _approve(point: dict) -> None:
    point.update(status="approved", review={"reviewer": "owner", "reviewed_at": "2026-09-26T10:00:00+07:00", "seconds": 42})


def _approved_v04(lab: Lab, *, sub: bool, sequence: bool = True) -> None:
    """en.alpha as an approved v0.4 point with every locale filled, optionally lacking sub / sequence."""
    point = _with_v04(alpha(lab))
    _approve(point)
    if sub:
        point["header"]["sub"] = {"vi": "số nhiều", "en": "plurals"}
    if sequence:
        point["sequence"] = 1
    _all_locales(lab, ["vi", "en"])


def _with_production(lab: Lab, *, sample: str = "I have three cats.", slots: list | None = None) -> None:
    point = _with_v04(alpha(lab))
    point["personal_production"] = {
        "prompt": {"vi": "Viết một câu về thú cưng."},
        "placeholder": "I have two ...",
        "target_form": "affirmative",
        "pattern_rule": {
            "ordered": True,
            "slots": slots if slots is not None else [
                {"role": "marker", "any_of": ["two", "three", "four"]}, {"role": "object", "regex": r"\b\w+s\b"},
            ],
        },
        "sample": {"text": sample},
    }


def _v04_fields(point: dict) -> dict:
    """A schema-valid set of the v0.4 fields for en.alpha (GRAMMAR_CONTENT_CONTRACT.md)."""
    text = "I have two cats."
    return {
        "point_type": "morphology",
        "source_anchors": {"status": "unanchored", "items": []},
        "header": {
            "title": {"vi": "Danh từ số nhiều"}, "native_title": "Plural nouns",
            "level": dict(point["level"]), "summary": {"vi": "Từ hai trở lên thì thêm -s."},
        },
        "when_to_use": [{"vi": "Khi có từ hai trở lên."}, {"vi": "Khi đếm được."}],
        "pattern": {
            "formula": [_slot("two / many", "marker", "từ chỉ số lượng"), _slot("N-s", "object", "danh từ số nhiều")],
            "illustration": {"kind": "morphology", "morphology": [{"base": "cat", "affix": "-s", "result": "cats"}]},
        },
        "examples": [{
            "text": text, "form": "affirmative",
            "spans": [
                {"start": text.index("two"), "end": text.index("two") + 3, "role": "marker"},
                {"start": text.index("cats"), "end": text.index("cats") + 4, "role": "object"},
            ],
            "annotation": {"vi": "số nhiều"}, "translation": {"vi": "Tôi có hai con mèo."},
        }],
        "compare": [],
        "common_mistakes": [{
            "wrong": "I have two cat.", "right": "I have two cats.",
            "reason": {"vi": "Đếm được, từ hai trở lên phải thêm -s."}, "error_tag": "agreement", "l1": ["vi"],
        }],
        "quick_practice": [
            _qp("I have two ___.", "cats", "cat", "agreement"),
            _qp("She has three ___.", "books", "book", "agreement"),
            _qp("There are five ___.", "boxes", "box", "agreement"),
        ],
    }


def _with_v04(point: dict) -> dict:
    """Bump ``point`` to a valid schema_version 0.4 point; returns it."""
    point["schema_version"] = "0.4"
    for key in ("blocks", "title", "summary"):
        point.pop(key, None)
    point.update(_v04_fields(point))
    return point


def _with_v04_zh(lab: Lab) -> dict:
    """A schema-valid v0.4 zh.le_completion point (zh-Hans: pinyin everywhere)."""
    point = lab.points["zh.le_completion"]
    point["schema_version"] = "0.4"
    for key in ("blocks", "title", "summary"):
        point.pop(key, None)
    text = "我们吃了饭。"
    point.update({
        "point_type": "tense_aspect",
        "source_anchors": {"status": "unanchored", "items": []},
        "header": {
            "title": {"vi": "Trợ từ 了"}, "native_title": "动态助词了",
            "native_title_pinyin": ["dòng", "tài", "zhù", "cí", "le"],
            "level": dict(point["level"]), "summary": {"vi": "了 sau động từ: hành động đã xong."},
        },
        "when_to_use": [{"vi": "Hành động đã xong."}, {"vi": "Có mốc thời gian cụ thể."}],
        "pattern": {
            "formula": [
                _slot("动词", "verb", "động từ", pinyin=["dòng", "cí"]),
                _slot("了", "particle", "trợ từ hoàn thành", pinyin=["le"]),
            ],
            "illustration": {"kind": "timeline", "timeline": {"shape": "point_past"}},
        },
        "examples": [{
            "text": text, "form": "affirmative",
            "spans": [{"start": 2, "end": 3, "role": "verb"}, {"start": 3, "end": 4, "role": "particle"}],
            "annotation": {"vi": "đã hoàn thành"}, "translation": {"vi": "Chúng tôi đã ăn cơm."},
            "pinyin": ["wǒ", "men", "chī", "le", "fàn", ""],
        }],
        "compare": [],
        "common_mistakes": [{
            "wrong": "我昨天吃饭。", "right": "我昨天吃了饭。",
            "reason": {"vi": "Hành động đã xong cần 了."}, "error_tag": "aspect", "l1": ["vi"],
            "wrong_pinyin": ["wǒ", "zuó", "tiān", "chī", "fàn", ""],
            "right_pinyin": ["wǒ", "zuó", "tiān", "chī", "le", "fàn", ""],
        }],
        "quick_practice": [
            _qp_zh("我吃___饭。", ["wǒ", "chī", "", "", "", "fàn", ""], "了", "着", "aspect"),
            _qp_zh("他走___。", ["tā", "zǒu", "", "", "", ""], "了", "过", "aspect"),
            _qp_zh("你吃___吗？", ["nǐ", "chī", "", "", "", "ma", ""], "了", "着", "aspect"),
        ],
    })
    return point


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
