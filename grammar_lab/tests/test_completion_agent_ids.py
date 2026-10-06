from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPLETION = REPO_ROOT / "scripts" / "grammar_completion_agent.ps1"
RESCUE = REPO_ROOT / "scripts" / "grammar_rescue_agent.ps1"


def _completion_pattern() -> str:
    text = COMPLETION.read_text(encoding="utf-8")
    match = re.search(r"(?m)^\$PointIdPattern = '([^']+)'$", text)
    assert match is not None, "completion agent must define one generic point-id pattern"
    return match.group(1)


def _rescue_pattern() -> str:
    text = RESCUE.read_text(encoding="utf-8")
    match = re.search(r"\[ValidatePattern\('([^']+)'\)\]", text)
    assert match is not None, "rescue agent must validate point ids"
    return match.group(1)


def test_completion_agent_parses_real_grammar_point_ids() -> None:
    pattern = _completion_pattern()
    output = "written              zh.modal.hui                                     cached\n"
    match = re.search(
        rf"(?m)^(?:written|error|blocked_metadata)\s+({pattern})\s+",
        output,
    )
    assert match is not None
    assert match.group(1) == "zh.modal.hui"
    assert re.fullmatch(pattern, "en.past_simple")
    assert re.fullmatch(pattern, "en.canon.c2.015")
    assert not re.fullmatch(pattern, "fr.modal.hui")


def test_completion_and_rescue_share_generic_id_contract() -> None:
    completion_pattern = _completion_pattern()
    rescue_pattern = _rescue_pattern()
    completion = COMPLETION.read_text(encoding="utf-8")
    assert '($PointIdPattern)\\s+' in completion
    assert '^written\\s+$PointIdPattern\\s+' in completion
    for point_id in ("zh.modal.hui", "en.past_simple", "en.canon.c2.015"):
        assert re.fullmatch(completion_pattern, point_id)
        assert re.fullmatch(rescue_pattern, point_id)
    assert not re.fullmatch(rescue_pattern, "fr.modal.hui")
