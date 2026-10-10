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


def _payload_keys(cell: str) -> set[str]:
    """The top-level keys of the payload object(s) in a §7 table cell."""

    cell = re.sub(r'"[^"]*"', "", cell)
    keys, depth = set(), 0
    for token in re.findall(r"[{}]|[a-z_]+", cell):
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
        elif depth == 1:
            keys.add(token)
    return keys


def _payload_cell(action: str) -> str:
    return re.search(rf"^\| `{action}` \| (.*?) \| (?:LOW|CONFIRM) \|", _section("## 7."), re.M).group(1)


@pytest.mark.parametrize("action", sorted(set(contract.ACTIONS) - {"navigate"}))
def test_action_payload_keys_match_the_table(action):
    spec = contract.ACTIONS[action]
    keys = set().union(*(shape.required | shape.optional for shape in spec.shapes))
    assert _payload_keys(_payload_cell(action)) == keys


def test_action_value_sets_match_the_table():
    assert '`{ scope: "due" }` or `{ scope: "word", text, lang }`' in _payload_cell("start_review")
    assert contract.ACTIONS["start_review"].values["scope"] == {"due", "word"}
    assert set(re.findall(r'"([a-z]+)"', _payload_cell("start_targeted_drill"))) == contract.ACTIONS[
        "start_targeted_drill"
    ].values["focus"]
    assert set(re.findall(r'"([a-z]+)"', _payload_cell("add_word_to_collection"))) == contract.COLLECTION_SYSTEMS


def test_version_one_clients_get_only_what_version_two_left_unchanged():
    assert "sends none of the changed actions" in CONTRACT
    assert contract.V1_ACTIONS == {"navigate", "play_model", "start_targeted_drill"}
    assert contract.V1_ACTIONS <= set(contract.ACTIONS)
    assert "orena.home" not in contract.V1_SURFACES
    assert contract.actions_for_version(1) == contract.V1_ACTIONS
    assert contract.actions_for_version(2) == set(contract.ACTIONS)


def test_version_two_rules():
    assert re.search(r"`trigger` ∈ `message` .*\| `open`", CONTRACT)
    assert contract.TRIGGERS == {"message", "open"}
    assert "≤ 240 characters" in _section("### 3.2") and contract.OPENING_MAX_CHARS == 240
    assert "×(1-5)" in _section("### 3.2") and contract.OPENING_MAX_SUGGESTIONS == 5
    assert "×(0-2)" in _section("### 3.2") and contract.OPENING_MAX_ACTIONS == 2
    assert "≤ 90 characters" in _section("### 5.5") and contract.MAX_DISPLAY_REASON_CHARS == 90
    kinds = re.search(r'"kind": "([^"]+)"', _section("### 5.5")).group(1)
    assert {kind.strip() for kind in kinds.split("|")} == contract.DISPLAY_KINDS
    assert "(`content_id`, `grammar_id`, `essay_id`, `target.id`) come from tool reads" in _section("## 7.")


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
    assert _enum_after("`selected_item`: `type` ∈") == contract.SELECTED_ITEM_TYPES
    assert '"kind": "preference | goal | plan"' in CONTRACT
    assert contract.COACH_NOTE_KINDS == {"preference", "goal", "plan"}
    # v5 (D-096): the address note is a kind of its own, never sent in coach_notes.
    assert "Kinds are `preference | goal | plan`, plus `address` (§5.6)" in CONTRACT
    assert "the `address` note is never among them (§5.6)" in CONTRACT
    assert contract.NOTE_KINDS == contract.COACH_NOTE_KINDS | {"address"}
    assert "send at most 20, most weighted first, total ≤ 2 KB" in CONTRACT
    assert (contract.MAX_COACH_NOTES, contract.MAX_COACH_NOTES_BYTES) == (20, 2048)
    # v3 (D-094): an action's label is interface copy, which ruling R12 already served.
    assert "`label` is in the `interface` language (`context.locale.interface`), ≤ 24 characters" in CONTRACT
    assert contract.MAX_ACTION_LABEL_CHARS == 24
    assert 'format: "pcm16_24k"' in CONTRACT and contract.AUDIO_FORMATS == {"pcm16_24k"}


def test_action_labels_are_interface_copy():
    from writing_coach.agent.learner_copy import CATALOG, CopyLayer

    for key, entry in CATALOG.items():
        if key.startswith(("action.", "navigate.", "prompt.")):
            assert entry.layer is CopyLayer.INTERFACE, key


def test_suggestion_intents_are_prompt_intents():
    from writing_coach.agent.outputs import PROMPT_INTENTS

    section_4 = CONTRACT[CONTRACT.index("## 4.") : CONTRACT.index("## 5.")]  # with its subsections
    assert "in the `prompt.` namespace" in section_4
    assert contract.PROMPT_NAMESPACE == "prompt."
    fixtures = set(re.findall(r"suggestion\{\"[^\"]*\", ([a-z_.]+)\}", CONTRACT))
    assert fixtures == {"prompt.review_due"}
    assert fixtures <= set(PROMPT_INTENTS)
    assert all(i.startswith("prompt.") and i not in contract.SURFACES for i in PROMPT_INTENTS)


def test_negotiated_version_never_exceeds_the_client():
    assert contract.negotiated_version(1) == 1
    assert contract.negotiated_version(contract.CONTRACT_VERSION + 1) == contract.CONTRACT_VERSION
    with pytest.raises(ValueError):
        contract.negotiated_version(0)


# --- v4 (D-095): §2.1 HTTP statuses and §4.1 error classes ------------------------------


def _table_rows(heading: str) -> list[list[str]]:
    rows = re.findall(r"^\|(.+)\|\s*$", _section(heading), re.M)
    cells = [[cell.strip() for cell in row.split("|")] for row in rows]
    return [row for row in cells[2:]]  # the header and its rule are not rows


def test_the_error_classes_are_the_contracts():
    from writing_coach.agent.errors import ERROR_KINDS

    rows = [r for r in _table_rows("### 4.1") if len(r) == 3 and r[0].startswith("`") and r[1].startswith("`")]
    by_class = {row[0].strip("`"): row[1].strip("`") for row in rows if row[1].strip("`") in contract.ERROR_FALLBACKS}
    assert by_class == {kind.error_class: kind.fallback for kind in ERROR_KINDS.values()}
    fallbacks = {row[0].strip("`") for row in _table_rows("### 4.1") if len(row) == 2}
    assert fallbacks == contract.ERROR_FALLBACKS
    assert "`transport`" in _section("### 4.1") and "transport" not in ERROR_KINDS  # the client's own, never sent


def test_the_http_statuses_are_the_contracts():
    rows = [(row[0].strip("`"), row[1]) for row in _table_rows("### 2.1") if row[0].startswith("`")]
    assert [status for status, _ in rows] == ["200", "401", "404", "409", "422", "429", "429", "409", "403", "503"]
    statuses = {}
    for status, body in rows:  # the first row of a status is the plain-string one; v7 adds object-bodied rows after
        statuses.setdefault(status, body)
    assert '`{"detail": "Not Found"}`' in statuses["404"]
    assert '`{"detail": "target_language_mismatch"}`' in statuses["409"]
    assert '`{"detail": "rate_limited"}`' in statuses["429"] and "Retry-After" in statuses["429"]
    assert "only a refused `rate_limited` `429` does not" in CONTRACT


def test_v7_the_plan_limit_statuses_headers_and_voice_refusal_are_in_the_contract():
    """D-164: every category the quota gate can answer on `/api/agent/*` is a row of section 2.1, the two request
    headers are in section 3, and the voice refusal is in section 9 (the Intelligence lane builds against this file)."""

    source = (ROOT / "writing_coach/product/quota.py").read_text(encoding="utf-8")
    answered = set(re.findall(r'orena_http_error\(\s*\d+,\s*"([a-z_]+)"', source)) | {"quota_exhausted"}
    assert {"quota_unavailable", "account_deleted", "feature_not_in_plan", "operation_in_progress",
            "operation_finished", "operation_conflict", "quota_exhausted"} <= answered
    table = _section("### 2.1")
    for category in answered:
        assert category in table, f"section 2.1 does not name {category}"
    assert "`rate_limited`" in table and "object with a `category`" in table
    assert "`Idempotency-Key:" in _section("## 3.") and "`X-Orena-Timezone:" in _section("## 3.")
    assert "neither require nor read it" in _section("## 3.")  # voice/turn and voice/tool keep their `utterance` token
    voice = _section("## 9.")
    # v8 (D-16T): the voice session is charged by duration. Its refusals are the quota gate's own categories, already
    # asserted above as section 2.1 rows; section 9 names the two it adds to the session, and v7's interim is gone.
    assert "429 `quota_exhausted`" in voice and "503 `quota_unavailable`" in voice and "`max_seconds`" in voice
    assert "503 `quota_voice_not_metered`" not in voice
    for path in ("writing_coach/agent/api.py", "writing_coach/product/quota.py", "writing_coach/agent/voice_session.py"):
        assert "quota_voice_not_metered" not in (ROOT / path).read_text(encoding="utf-8"), path
