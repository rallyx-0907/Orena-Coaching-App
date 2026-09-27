from __future__ import annotations

from pathlib import Path

import pytest

from grammar_lab.pipeline.run_context import NoRunError, read_step, resolve_run_id, write_step


def test_resolve_latest_with_no_run_yet_raises(tmp_path: Path) -> None:
    with pytest.raises(NoRunError):
        resolve_run_id(tmp_path, "latest")


def test_write_step_then_resolve_latest(tmp_path: Path) -> None:
    write_step(tmp_path, "20260927T000000Z", "verify", {"lang": "en"})
    assert resolve_run_id(tmp_path, "latest") == "20260927T000000Z"


def test_read_step_returns_none_when_missing(tmp_path: Path) -> None:
    assert read_step(tmp_path, "20260927T000000Z", "route") is None


def test_read_step_round_trips(tmp_path: Path) -> None:
    write_step(tmp_path, "run1", "generate", {"outcomes": [1, 2, 3]})
    assert read_step(tmp_path, "run1", "generate") == {"outcomes": [1, 2, 3]}


def test_resolve_explicit_run_id_that_does_not_exist_raises(tmp_path: Path) -> None:
    with pytest.raises(NoRunError):
        resolve_run_id(tmp_path, "does-not-exist")


def test_latest_pointer_tracks_the_most_recent_write(tmp_path: Path) -> None:
    write_step(tmp_path, "run1", "verify", {})
    write_step(tmp_path, "run2", "route", {})
    assert resolve_run_id(tmp_path, "latest") == "run2"
