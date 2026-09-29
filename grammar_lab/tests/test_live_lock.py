"""live_lock.hold: the provider's quota lock is held for the run, kept fresh, and given back."""

from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from grammar_lab.pipeline import live_lock
from grammar_lab.pipeline.cli import app


def test_deepseek_run_holds_the_deepseek_lock_and_gives_it_back(tmp_path: Path) -> None:
    lock = tmp_path / "live-deepseek.lock"
    with live_lock.hold(["deepseek"], 0.5, directory=tmp_path) as taken:
        assert taken == ["deepseek"]
        held = json.loads(lock.read_text(encoding="utf-8"))
        assert held["lane"] == "grammar-lab" and held["pid"] == os.getpid() and "heartbeat_at" in held
    assert not lock.exists()


def test_providers_without_a_lock_group_run_without_one(tmp_path: Path) -> None:
    with live_lock.hold(["anthropic", "groq"], 0.5, directory=tmp_path) as taken:
        assert taken == []
    assert not list(tmp_path.glob("*.lock"))


def test_the_lock_is_given_back_when_the_run_fails(tmp_path: Path) -> None:
    try:
        with live_lock.hold(["gemini"], 0.5, directory=tmp_path):
            assert (tmp_path / "live-gemini-text.lock").exists()
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert not (tmp_path / "live-gemini-text.lock").exists()


def test_generate_wants_exactly_one_of_ids_and_level() -> None:
    both = CliRunner().invoke(app, ["generate", "--lang", "en", "--ids", "en.a", "--level", "A1"])
    neither = CliRunner().invoke(app, ["generate", "--lang", "en"])
    assert both.exit_code != 0 and neither.exit_code != 0
