from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "sandbox" / "live_provider_lock.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("live_provider_lock", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses needs the module registered to resolve types
    spec.loader.exec_module(module)
    return module


module = _load_module()


def _spawn_and_wait_for_a_finished_process() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def test_acquire_creates_the_lock_file_with_lane_pid_timestamp_and_ceiling(tmp_path: Path) -> None:
    path = tmp_path / "live-provider.lock"
    info = module.acquire("grammar-lab", 0.05, path=path, pid=4242)
    assert info.lane == "grammar-lab"
    assert info.pid == 4242
    assert info.cost_ceiling_usd == 0.05
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk == {
        "lane": "grammar-lab",
        "pid": 4242,
        "acquired_at": info.acquired_at,
        "cost_ceiling_usd": 0.05,
    }


def test_acquire_times_out_when_another_live_lane_holds_the_lock(tmp_path: Path) -> None:
    path = tmp_path / "live-provider.lock"
    module.acquire("intelligence", 1.0, path=path, pid=os.getpid())  # holder is this live process

    ticks = iter([0, 10, 100])  # start=0, one check at 10s (< 45s budget), next check at 100s (past it)
    slept: list[float] = []
    with pytest.raises(module.LiveProviderLockTimeout) as excinfo:
        module.acquire(
            "grammar-lab",
            0.05,
            path=path,
            pid=99999,
            wait_max_seconds=45,
            poll_seconds=30,
            clock=lambda: next(ticks),
            sleep=slept.append,
        )
    assert excinfo.value.holder.lane == "intelligence"
    assert excinfo.value.holder.pid == os.getpid()
    assert slept == [30]


def test_acquire_removes_an_orphaned_lock_held_by_a_dead_pid(tmp_path: Path) -> None:
    path = tmp_path / "live-provider.lock"
    dead_pid = _spawn_and_wait_for_a_finished_process()
    module.acquire("intelligence", 1.0, path=path, pid=dead_pid)

    removed: list[tuple[str, str]] = []
    info = module.acquire(
        "grammar-lab",
        0.05,
        path=path,
        pid=os.getpid(),
        on_orphan_removed=lambda existing, reason: removed.append((existing.lane, reason)),
    )
    assert info.lane == "grammar-lab"
    assert removed == [("intelligence", "dead-pid")]


def test_acquire_removes_a_lock_older_than_the_stale_window(tmp_path: Path) -> None:
    path = tmp_path / "live-provider.lock"
    module.acquire("intelligence", 1.0, path=path, pid=os.getpid())

    removed: list[str] = []
    info = module.acquire(
        "grammar-lab",
        0.05,
        path=path,
        pid=os.getpid(),
        stale_seconds=0,  # the lock just written is already "older" than a zero-second window
        on_orphan_removed=lambda existing, reason: removed.append(reason),
    )
    assert info.lane == "grammar-lab"
    assert removed == ["stale"]


def test_acquire_never_touches_docker() -> None:
    # The lock is a plain file coordination mechanism. It must not be able to
    # stop another lane's container even by accident -- confirm the module
    # cannot spawn any external process at all (no subprocess/os.system/exec*).
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    for forbidden in ("import subprocess", "os.system", "os.exec", "os.spawn"):
        assert forbidden not in source


def test_release_deletes_the_lock_when_lane_and_pid_match(tmp_path: Path) -> None:
    path = tmp_path / "live-provider.lock"
    module.acquire("grammar-lab", 0.05, path=path, pid=4242)
    released = module.release("grammar-lab", path=path, pid=4242)
    assert released is True
    assert not path.exists()


def test_release_leaves_another_lanes_lock_untouched(tmp_path: Path) -> None:
    path = tmp_path / "live-provider.lock"
    module.acquire("intelligence", 1.0, path=path, pid=555)
    released = module.release("grammar-lab", path=path, pid=4242)
    assert released is False
    assert path.exists()


def test_pid_alive_is_true_for_the_current_process() -> None:
    assert module._pid_alive(os.getpid()) is True


def test_pid_alive_is_false_for_a_finished_process() -> None:
    dead_pid = _spawn_and_wait_for_a_finished_process()
    assert module._pid_alive(dead_pid) is False


def test_main_acquire_then_release_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "live-provider.lock"
    monkeypatch.setattr(module, "default_lock_path", lambda: path)
    code = module.main(["acquire", "--lane", "grammar-lab", "--pid", "4242", "--cost-ceiling-usd", "0.05"])
    assert code == 0
    assert path.exists()
    code = module.main(["release", "--lane", "grammar-lab", "--pid", "4242"])
    assert code == 0
    assert not path.exists()


def test_main_acquire_reports_timeout_and_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "live-provider.lock"
    monkeypatch.setattr(module, "default_lock_path", lambda: path)
    module.acquire("intelligence", 1.0, path=path, pid=os.getpid())
    code = module.main(
        [
            "acquire",
            "--lane",
            "grammar-lab",
            "--pid",
            "99999",
            "--cost-ceiling-usd",
            "0.05",
            "--wait-max-seconds",
            "0",
            "--poll-seconds",
            "0",
        ]
    )
    assert code == 1
    captured = capsys.readouterr()
    assert "intelligence" in captured.out


def test_main_release_reports_when_not_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "live-provider.lock"
    monkeypatch.setattr(module, "default_lock_path", lambda: path)
    module.acquire("intelligence", 1.0, path=path, pid=555)
    code = module.main(["release", "--lane", "grammar-lab", "--pid", "4242"])
    assert code == 0
    assert path.exists()
    captured = capsys.readouterr()
    assert "not" in captured.out.lower()
