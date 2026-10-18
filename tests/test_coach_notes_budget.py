"""The client's coach_notes byte budget agrees with the server's (PR #279 / D-225).

`tests/fixtures/coach_notes_budget.json` is written by the Node agent gate (`scripts/test_orena_agent.mjs`): the
notes `memory.requestNotes()` builds for near-limit lists (English, Vietnamese, Chinese, long text, whole-number
weights, expiring notes), with the size the client measured. The server's `coach_notes_bytes` must accept every
list and must measure no more than the client did, or a turn the client thought fitted is refused whole (422).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from writing_coach.agent.contract import MAX_COACH_NOTES, MAX_COACH_NOTES_BYTES
from writing_coach.agent.schemas import CoachNote, coach_notes_bytes

CASES = json.loads((Path(__file__).parent / "fixtures" / "coach_notes_budget.json").read_text(encoding="utf-8"))["cases"]


def test_the_fixture_has_the_cases():
    assert {case["name"] for case in CASES} >= {"en", "vi", "zh"}


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_a_client_built_list_passes_the_server_measure(case):
    notes = [CoachNote.model_validate(note) for note in case["notes"]]
    measured = coach_notes_bytes(notes)
    assert len(notes) <= MAX_COACH_NOTES
    assert measured <= MAX_COACH_NOTES_BYTES
    assert case["client_bytes"] >= measured, "the client measure must never be below the server's"
    assert case["client_bytes"] <= MAX_COACH_NOTES_BYTES + 1
