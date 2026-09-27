"""The agent's contract tables match docs/project/AGENT_CONTRACT.md itself.

The contract is edited only on codex/work and reaches this lane by merge. These
tests read the file, so a bump that changes a vocabulary fails here until the
code follows it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from writing_coach.agent import contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (ROOT / "docs/project/AGENT_CONTRACT.md").read_text(encoding="utf-8")


def _section(heading: str) -> str:
    start = CONTRACT.index(heading)
    following = re.search(r"\n#{2,3} ", CONTRACT[start + len(heading) :])
    end = start + len(heading) + following.start() if following else len(CONTRACT)
    return CONTRACT[start:end]


def _first_code_block(text: str) -> str:
    return re.search(r"```text\n(.*?)```", text, re.S).group(1)


def _enum_after(label: str) -> set[str]:
    """The `a | b | c` list in the first backticks after `label ∈`."""

    line = next(line for line in CONTRACT.splitlines() if label in line)
    listed = re.search(r"`([^`]+)`", line.split("∈", 1)[1]).group(1)
    return {item.strip() for item in listed.split("|")}


def _quoted(pattern: str) -> set[str]:
    return set(re.findall(r'"([a-z_]+)"', re.search(pattern, CONTRACT).group(1)))


def test_contract_version_matches_the_file():
    declared = re.search(r"`contract_version: (\d+)`", CONTRACT)
    assert declared and int(declared.group(1)) == contract.CONTRACT_VERSION


def test_surface_ids_and_their_parameters():
    block = _first_code_block(_section("### 6.1"))
    parsed: dict[str, tuple[str, ...]] = {}
    for token in re.findall(r"[a-z_]+(?:\.[a-z_]+)*(?:\{[^}]*\})?", block):
        name, _, params = token.partition("{")
        parsed[name] = tuple(p.strip() for p in params.rstrip("}").split(",") if p.strip())
    as_sets = {name: frozenset(params) for name, params in parsed.items()}
    assert as_sets == {name: frozenset(params) for name, params in contract.SURFACES.items()}


def test_action_allowlist_and_risk():
    rows = re.findall(r"^\| `([a-z_]+)` \| (.*?) \| (LOW|CONFIRM) \|", _section("## 7."), re.M)
    assert {name: risk for name, _, risk in rows} == {
        name: spec.risk.value for name, spec in contract.ACTIONS.items()
    }


@pytest.mark.parametrize(
    "action, payload_cell_keys",
    [
        ("play_model", {"content_id", "item_id"}),
        ("play_user", {"attempt_id", "item_id"}),
        ("say_again", {"attempt_id", "content_id", "item_id"}),
        ("compare_with_model", {"attempt_id", "item_id"}),
        ("save_word", {"word_id", "text", "lang"}),
        ("add_word_to_collection", {"word_id", "collection_id"}),
        ("start_review", {"scope", "word_id"}),
        ("start_targeted_drill", {"focus", "item_ids"}),
        ("unsave_word", {"word_id"}),
    ],
)
def test_action_payload_keys_match_the_table(action, payload_cell_keys):
    cell = re.search(rf"^\| `{action}` \| `(.*?)` \|", _section("## 7."), re.M).group(1)
    assert set(re.findall(r"[a-z_]+", re.sub(r'"[^"]*"', "", cell))) == payload_cell_keys
    spec = contract.ACTIONS[action]
    keys = set().union(*(shape.required | shape.optional for shape in spec.shapes))
    assert keys == payload_cell_keys


def test_event_names():
    block = _first_code_block(_section("## 4. Events"))
    names = {line.split()[0] for line in block.splitlines() if line.strip()}
    assert names == contract.EVENT_NAMES


def test_voice_styles():
    block = _first_code_block(_section("### 5.2"))
    assert set(block.replace("|", " ").split()) == contract.VOICE_STYLES


def test_evidence_sources():
    assert _enum_after("`source` ∈") == contract.EVIDENCE_SOURCES


def test_activity_types():
    assert _enum_after("`activity_type` ∈") == contract.ACTIVITY_TYPES


def test_small_enumerations():
    assert _quoted(r"voice_state\s+\{(.*?)\}") == contract.VOICE_STATES
    assert _quoted(r"metered\s+\{(.*?)\}") == contract.BUDGET_STATES
    assert _quoted(r"error\s+\{(.*?)\}\n") == contract.ERROR_FALLBACKS
    assert _quoted(r"memory_update\s+\{(.*?)\}") == contract.MEMORY_OPS
    assert '"type": "word | sentence | feedback_item | grammar_point"' in CONTRACT
    assert contract.SELECTED_ITEM_TYPES == {"word", "sentence", "feedback_item", "grammar_point"}
    assert '"kind": "preference | goal | plan"' in CONTRACT
    assert contract.COACH_NOTE_KINDS == {"preference", "goal", "plan"}
    assert "send at most 20, most weighted first, total ≤ 2 KB" in CONTRACT
    assert (contract.MAX_COACH_NOTES, contract.MAX_COACH_NOTES_BYTES) == (20, 2048)
    assert "`label` is in the `support` language, ≤ 24 characters" in CONTRACT
    assert contract.MAX_ACTION_LABEL_CHARS == 24
    assert 'format: "pcm16_24k"' in CONTRACT and contract.AUDIO_FORMATS == {"pcm16_24k"}


def test_negotiated_version_never_exceeds_the_client():
    assert contract.negotiated_version(1) == 1
    assert contract.negotiated_version(contract.CONTRACT_VERSION + 1) == contract.CONTRACT_VERSION
    with pytest.raises(ValueError):
        contract.negotiated_version(0)
