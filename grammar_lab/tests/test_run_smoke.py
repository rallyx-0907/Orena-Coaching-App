from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "sandbox" / "run_smoke.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_smoke", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


module = _load_module()


def _fake_clock(start: float = 0.0, step: float = 1.0):
    """A clock that advances by ``step`` seconds on every read -- avoids hand-counting
    exactly how many times the code under test happens to call it."""
    state = {"t": start}

    def clock() -> float:
        value = state["t"]
        state["t"] += step
        return value

    return clock


def test_other_lane_is_live_true_for_a_matching_container_name() -> None:
    assert module._other_lane_is_live(["orena-agent-live-web-1", "postgres:17"]) is True


def test_other_lane_is_live_false_when_no_container_matches() -> None:
    assert module._other_lane_is_live(["ai-writing-coach-writing-coach-1", "postgres:17"]) is False


def test_wait_for_clear_to_run_proceeds_immediately_when_nothing_is_live(tmp_path: Path) -> None:
    path = tmp_path / "live-provider.lock"
    slept: list[float] = []
    info = module.wait_for_clear_to_run(
        "grammar-lab", 0.05,
        list_containers=lambda: ["ai-writing-coach-writing-coach-1"],
        sleep=slept.append,
        clock=_fake_clock(),
        path=path,
        pid=4242,
    )
    assert info.lane == "grammar-lab"
    assert path.exists()
    assert slept == []


def test_wait_for_clear_to_run_releases_and_retries_while_another_lane_is_live(tmp_path: Path) -> None:
    path = tmp_path / "live-provider.lock"
    containers = iter([["orena-agent-live-web-1"], ["ai-writing-coach-writing-coach-1"]])
    slept: list[float] = []
    info = module.wait_for_clear_to_run(
        "grammar-lab", 0.05,
        list_containers=lambda: next(containers),
        sleep=slept.append,
        clock=_fake_clock(step=1.0),  # tiny steps: nowhere near the 1800s budget
        poll_seconds=30,
        wait_max_seconds=1800,
        path=path,
        pid=4242,
    )
    assert info.lane == "grammar-lab"
    assert path.exists()  # the final, successful acquire is left in place
    assert slept == [30]  # released once, waited the poll interval, retried, then succeeded


def test_wait_for_clear_to_run_gives_up_and_releases_the_lock(tmp_path: Path) -> None:
    path = tmp_path / "live-provider.lock"
    slept: list[float] = []
    with pytest.raises(module.LiveLaneStillRunning):
        module.wait_for_clear_to_run(
            "grammar-lab", 0.05,
            list_containers=lambda: ["orena-agent-live-web-1"],  # never clears
            sleep=slept.append,
            clock=_fake_clock(step=1.0),
            poll_seconds=2,
            wait_max_seconds=5,
            path=path,
            pid=4242,
        )
    assert not path.exists()  # never left holding the lock when giving up
    assert slept  # it waited at least once before giving up


def test_run_smoke_never_stops_a_container() -> None:
    # This runner only ever reads docker state (docker ps) to decide whether to wait; it
    # must never be able to stop or kill another lane's container, even by accident.
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    for forbidden in ("docker stop", "docker kill", "docker rm", "compose down -v", "-v\""):
        assert forbidden not in source
