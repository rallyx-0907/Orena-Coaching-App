import re
from pathlib import Path

from writing_coach.core.platform_api import api_platform_skills
from writing_coach.core.skill_registry import (
    SkillAudience,
    SkillReleaseState,
    all_skills,
    skill,
    skills_for,
)


ROOT = Path(__file__).resolve().parents[1]


def test_central_registry_represents_required_truthful_states() -> None:
    items = {item.key: item for item in all_skills()}
    assert set(items) == {"writing", "speaking", "reading", "listening"}
    assert {item.release_state for item in items.values()} >= {
        SkillReleaseState.BETA,
        SkillReleaseState.DEVELOPMENT,
    }
    assert SkillReleaseState.HIDDEN.value == "hidden"

    assert items["writing"].release_state is SkillReleaseState.BETA
    assert items["writing"].source_available is True
    assert items["writing"].available_to(SkillAudience.PUBLIC) is False
    assert items["writing"].available_to(SkillAudience.INTERNAL) is True
    assert items["reading"].available_to(SkillAudience.PUBLIC) is False
    assert items["reading"].available_to(SkillAudience.INTERNAL) is True
    assert items["speaking"].release_state is SkillReleaseState.DEVELOPMENT
    assert items["speaking"].source_available is True
    assert items["speaking"].available_to(SkillAudience.INTERNAL) is True
    assert items["speaking"].available_to(SkillAudience.PUBLIC) is False
    assert items["listening"].release_state is SkillReleaseState.DEVELOPMENT
    assert items["listening"].source_available is True
    assert items["listening"].available_to(SkillAudience.INTERNAL) is True
    assert items["listening"].available_to(SkillAudience.PUBLIC) is False
    assert skills_for(SkillAudience.PUBLIC) == ()
    assert skill("READING") is items["reading"]


def test_platform_contract_is_one_language_wide_release_matrix() -> None:
    payload = api_platform_skills()
    assert payload["policy"] == "language-wide"
    assert payload["language_scope"] == ["en", "zh"]
    assert [item["key"] for item in payload["skills"]] == [
        "writing",
        "speaking",
        "reading",
        "listening",
    ]
    assert all("language" not in item and "languages" not in item for item in payload["skills"])
    for profile in ("english", "chinese"):
        source = (ROOT / f"writing_coach/languages/{profile}/profile.py").read_text(encoding="utf-8")
        assert "release_state" not in source


def test_new_navigation_is_independent_of_historical_skill_hierarchy() -> None:
    source = (ROOT / 'static/orena/app.js').read_text(encoding='utf-8')
    # The gate itself is the contract, not the source formatting around it.
    assert re.search(r"if\s*\(\s*!\s*user\.is_admin\s*\)", source)  # internal review remains gated
    assert 'applySkillNavigation' not in source
    assert 'routeAvailable' not in source
    assert not (ROOT / 'static/becoming').exists()


def test_reading_implementation_and_release_versions_remain_intact() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert (ROOT / "writing_coach/becoming_reading.py").is_file()
    assert (ROOT / "static/orena/ui/encounter.js").is_file()
    for route in (
        '@app.get("/api/reading/sessions"',
        '@app.get("/api/reading/session/{session_id}"',
        '@app.post("/api/reading/session"',
        '@app.post("/api/reading/session/{session_id}/answer"',
    ):
        assert route in app
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "1.4.0"
