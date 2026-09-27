"""Capability registry (spec §5-§6, contract §8) and the tool plan behind it (spec §8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from writing_coach.agent.capability_registry import (
    CapabilityRegistryInvalid,
    load_capability_registry,
)
from writing_coach.agent.contract import ACTIONS, EVIDENCE_SOURCES, SURFACES
from writing_coach.agent.tool_plan import PLANNED_TOOLS, PlannedTool, gaps
from writing_coach.agent.tools import resolve_backing

ROOT = Path(__file__).resolve().parents[1]
GAPS_DOC = (ROOT / "docs/project/UI_BACKEND_GAPS.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def registry():
    from writing_coach.agent.runtime import build_tool_registry

    return load_capability_registry(registered_tools=build_tool_registry(writing_review=lambda i: None).names())


def test_every_v1_domain_is_known(registry):
    ids = {entry.id for entry in registry.entries()}
    for expected in (
        "home.overview",
        "library.find",
        "reading.passage",
        "listening.dictation",
        "speaking.pronunciation.line",
        "speaking.free_talk",
        "writing.review",
        "grammar.point",
        "vocabulary.words",
        "review.due",
        "progress.overview",
        "preferences.agent_memory",
    ):
        assert expected in ids


def test_vocabulary_and_writing_are_active_and_everything_else_pending(registry):
    active = {entry.id for entry in registry.entries() if entry.status == "active"}
    assert active == {"vocabulary.words", "review.due", "writing.review"}
    assert {entry.status for entry in registry.entries() if entry.id not in active} == {"pending"}


def test_the_registry_does_not_load_without_the_active_capabilities_tools():
    with pytest.raises(CapabilityRegistryInvalid, match="not registered"):
        load_capability_registry()


def test_entries_use_only_contract_ids(registry):
    for entry in registry.entries():
        assert set(entry.surfaces) <= set(SURFACES), entry.id
        assert set(entry.actions) <= set(ACTIONS), entry.id
        assert entry.evidence_source is None or entry.evidence_source in EVIDENCE_SOURCES, entry.id
        assert set(entry.tools) <= set(PLANNED_TOOLS), entry.id


def test_every_surface_the_contract_names_is_covered(registry):
    covered = {surface for entry in registry.entries() for surface in entry.surfaces}
    assert covered == set(SURFACES)


def test_en_and_zh_parity_or_a_reason(registry):
    for entry in registry.entries():
        if set(entry.languages) != {"en", "zh-CN"}:
            assert entry.linguistic_reason, entry.id
    assert registry.get("speaking.pronunciation.tone").languages == ("zh-CN",)
    assert registry.get("speaking.pronunciation.stress").languages == ("en",)


def test_public_shape_is_the_contracts(registry):
    body = registry.public(interface="vi", target="zh-CN")
    assert body["contract_version"] == 2
    first = body["capabilities"][0]
    assert set(first) == {"id", "title", "surfaces", "actions", "languages", "evidence_source", "status"}
    ids = {item["id"] for item in body["capabilities"]}
    assert "speaking.pronunciation.tone" in ids and "speaking.pronunciation.stress" not in ids
    english = {item["id"] for item in registry.public(interface="en", target="en")["capabilities"]}
    assert "speaking.pronunciation.stress" in english and "speaking.pronunciation.tone" not in english


def test_titles_are_interface_copy_in_every_interface_language(registry):
    for entry in registry.entries():
        assert set(entry.title) == {"en", "vi", "zh-CN"}, entry.id
    assert registry.get("preferences.agent_memory").public("vi")["title"] == "Những gì Orena ghi nhớ"


def test_for_surface_is_deterministic_and_language_aware(registry):
    zh = [e.id for e in registry.for_surface("speaking.workspace", "zh-CN")]
    en = [e.id for e in registry.for_surface("speaking.workspace", "en")]
    assert "speaking.pronunciation.tone" in zh and "speaking.pronunciation.tone" not in en
    assert zh == [e.id for e in registry.for_surface("speaking.workspace", "zh-CN")]
    assert registry.for_surface(None, "en") == ()
    assert registry.for_surface("atlas.home", "en") == ()
    assert "home.overview" in {e.id for e in registry.for_surface("orena.home", "en")}


# --- loader refusals -----------------------------------------------------------


def good_entry(**overrides):
    entry = {
        "id": "test.capability",
        "title": {"en": "Test", "vi": "Thử", "zh-CN": "测试"},
        "surfaces": ["home"],
        "status": "pending",
        "contexts": [],
        "actions": ["navigate"],
        "languages": ["en", "zh-CN"],
        "evidence_source": None,
        "tools": ["get_learning_overview"],
    }
    entry.update(overrides)
    return entry


def load_one(tmp_path, entry, **kwargs):
    (tmp_path / "one.json").write_text(json.dumps({"capabilities": [entry]}), encoding="utf-8")
    return load_capability_registry(tmp_path, **kwargs)


def test_a_good_entry_loads(tmp_path):
    assert len(load_one(tmp_path, good_entry())) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"surfaces": ["reading.page"]},
        {"surfaces": []},
        {"actions": ["delete_collection"]},
        {"evidence_source": "speech.guess"},
        {"languages": ["en", "zh"]},
        {"languages": ["en"]},
        {"languages": ["ja"], "linguistic_reason": "Pitch accent."},
        {"status": "live"},
        {"tools": ["get_everything"]},
        {"contexts": ["page_html"]},
        {"title": {"en": "Test", "vi": "Thử"}},
        {"title": {"en": "x" * 61, "vi": "Thử", "zh-CN": "测试"}},
        {"id": "Test"},
        {"route": "/#/vocabulary"},
        {"surfaces": ["home", "home"]},
    ],
)
def test_bad_entries_do_not_load(tmp_path, overrides):
    with pytest.raises(CapabilityRegistryInvalid):
        load_one(tmp_path, good_entry(**overrides))


def test_an_active_capability_needs_its_tools_registered(tmp_path):
    with pytest.raises(CapabilityRegistryInvalid, match="not registered"):
        load_one(tmp_path, good_entry(status="active"))
    assert len(load_one(tmp_path, good_entry(status="active"), registered_tools={"get_learning_overview"})) == 1


def test_duplicate_ids_and_bad_files_do_not_load(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"capabilities": [good_entry()]}), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps({"capabilities": [good_entry()]}), encoding="utf-8")
    with pytest.raises(CapabilityRegistryInvalid, match="duplicate"):
        load_capability_registry(tmp_path)
    (tmp_path / "b.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(CapabilityRegistryInvalid):
        load_capability_registry(tmp_path)
    with pytest.raises(CapabilityRegistryInvalid):
        load_capability_registry(tmp_path / "empty")


# --- the tool plan ---------------------------------------------------------------


def test_the_plan_covers_the_specs_v1_tool_set():
    spec_tools = {
        "get_app_context", "get_current_selection", "get_current_learning_activity",
        "get_learning_overview", "get_skill_progress", "get_recent_learning_activity",
        "get_due_review_summary", "get_due_vocabulary", "get_word_detail", "get_saved_word_state",
        "get_pronunciation_attempt", "get_pronunciation_history",
        "get_pronunciation_word_detail", "get_tone_analysis", "get_stress_analysis",
        "get_current_writing_evaluation", "get_writing_feedback_items", "get_writing_history_summary",
        "get_grammar_point", "search_grammar_points", "get_grammar_mistakes_summary",
        "get_current_reading_context", "get_reading_progress", "get_reading_mistakes", "get_word_context_in_reading",
        "get_current_listening_context", "get_listening_attempt", "get_listening_mistakes",
        "build_learning_snapshot", "get_learning_weaknesses", "get_recommended_next_activities",
    }  # fmt: skip
    assert set(PLANNED_TOOLS) == spec_tools


@pytest.mark.parametrize("name", sorted(t.name for t in PLANNED_TOOLS.values() if t.verdict != "gap"))
def test_every_planned_backing_exists(name):
    tool = PLANNED_TOOLS[name]
    for reference in (tool.backed_by, *tool.composes):
        assert callable(resolve_backing(reference)), reference


@pytest.mark.parametrize("name", sorted(t.name for t in gaps()))
def test_every_gap_is_recorded_in_the_one_tracker(name):
    assert f"`{name}`" in GAPS_DOC


def test_the_plan_never_backs_a_tool_with_a_write_or_a_provider_call():
    forbidden = (
        "save_speaking_attempt",
        "create_speaking_attempt_record",
        "save_listening_progress",
        "word_detail:word_detail",
        "ReadingEvidenceRepository.ability",
        "open_listening_library_lesson",
        "product_activity",
        "readiness_summary",
        "becoming_reading",
    )
    for tool in PLANNED_TOOLS.values():
        for reference in filter(None, (tool.backed_by, *tool.composes)):
            assert not any(word in reference for word in forbidden), (tool.name, reference)


def test_a_plan_entry_is_consistent_with_itself():
    with pytest.raises(ValueError):
        PlannedTool("x_tool", "gap", "writing_coach.learner_summary:learner_summary", "gap with backing")
    with pytest.raises(ValueError):
        PlannedTool("x_tool", "backed", None, "backing missing")
    with pytest.raises(ValueError):
        PlannedTool("x_tool", "backed", "a:b", "n", languages=("en",))
    with pytest.raises(ValueError):
        PlannedTool("x_tool", "backed", "a:b", "n", evidence_source="speech.guess")
