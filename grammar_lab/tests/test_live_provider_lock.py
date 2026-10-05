from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
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


def _hold(directory: Path, group: str, lane: str, pid: int) -> Path:
    """Another lane's lock, written the same way that lane would write it."""
    path = module.lock_path(group, directory=directory)
    module.acquire(lane, 1.0, path=path, pid=pid)
    return path


# --- one lock file ---------------------------------------------------------------------

def test_acquire_creates_the_lock_file_with_lane_pid_timestamp_and_ceiling(tmp_path: Path) -> None:
    path = tmp_path / "live-deepseek.lock"
    info = module.acquire("grammar-lab", 0.05, path=path, pid=4242)
    assert (info.lane, info.pid, info.cost_ceiling_usd) == ("grammar-lab", 4242, 0.05)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "lane": "grammar-lab", "pid": 4242, "acquired_at": info.acquired_at, "cost_ceiling_usd": 0.05,
        "heartbeat_at": info.heartbeat_at,
    }
    assert info.heartbeat_at == info.acquired_at


def test_acquire_times_out_and_names_the_holder_and_the_lock(tmp_path: Path) -> None:
    path = _hold(tmp_path, "deepseek", "intelligence", os.getpid())
    ticks = iter([0, 10, 100])  # start=0, one check at 10s (< 45s budget), next at 100s (past it)
    slept: list[float] = []
    with pytest.raises(module.LiveProviderLockTimeout) as excinfo:
        module.acquire(
            "grammar-lab", 0.05, path=path, pid=99999, wait_max_seconds=45, poll_seconds=30,
            clock=lambda: next(ticks), sleep=slept.append,
        )
    assert excinfo.value.holder.lane == "intelligence"
    assert excinfo.value.holder.pid == os.getpid()
    assert excinfo.value.lock_name == "live-deepseek.lock"
    assert "lane=intelligence" in str(excinfo.value)
    assert f"pid={os.getpid()}" in str(excinfo.value)
    assert slept == [30]


def _write_lock(path: Path, lane: str, pid: int, *, heartbeat_age: float | None, acquired_age: float = 0.0) -> None:
    """A lock as any lane writes it; ``heartbeat_age=None`` writes the old format (no heartbeat_at)."""
    now = datetime.now(UTC)
    payload = {
        "lane": lane, "pid": pid, "acquired_at": (now - timedelta(seconds=acquired_age)).isoformat(),
        "cost_ceiling_usd": 1.0,
    }
    if heartbeat_age is not None:
        payload["heartbeat_at"] = (now - timedelta(seconds=heartbeat_age)).isoformat()
    path.write_text(json.dumps(payload), encoding="utf-8")


def _take(path: Path, lane: str = "grammar-lab") -> tuple[object, list[tuple[str, str]]]:
    removed: list[tuple[str, str]] = []
    info = module.acquire(
        lane, 0.05, path=path, pid=os.getpid(), wait_max_seconds=0, poll_seconds=0,
        on_orphan_removed=lambda existing, reason, lock: removed.append((existing.lane, reason)),
    )
    return info, removed


def test_own_lock_with_a_dead_pid_is_an_orphan(tmp_path: Path) -> None:
    path = tmp_path / "live-deepseek.lock"
    _write_lock(path, "grammar-lab", _spawn_and_wait_for_a_finished_process(), heartbeat_age=1)
    info, removed = _take(path)
    assert info.lane == "grammar-lab"
    assert removed == [("grammar-lab", "dead-pid")]


def test_own_lock_with_a_stale_heartbeat_is_an_orphan_even_if_the_pid_lives(tmp_path: Path) -> None:
    path = tmp_path / "live-deepseek.lock"
    _write_lock(path, "grammar-lab", os.getpid(), heartbeat_age=601)
    _, removed = _take(path)
    assert removed == [("grammar-lab", "stale")]


def test_other_lanes_lock_with_an_uncheckable_pid_survives_while_the_heartbeat_is_fresh(tmp_path: Path) -> None:
    # The bug this fixes: another lane's PID cannot be checked from here (it read "dead" for a live
    # holder and its lock was deleted). A fresh heartbeat must protect it whatever the PID looks like.
    path = tmp_path / "live-deepseek.lock"
    _write_lock(path, "intelligence", _spawn_and_wait_for_a_finished_process(), heartbeat_age=5)
    with pytest.raises(module.LiveProviderLockTimeout):
        _take(path)
    assert json.loads(path.read_text(encoding="utf-8"))["lane"] == "intelligence"


def test_other_lanes_pid_is_never_looked_up(tmp_path: Path) -> None:
    path = tmp_path / "live-deepseek.lock"
    _write_lock(path, "intelligence", 4242, heartbeat_age=5)
    looked_up: list[int] = []

    def pid_alive(pid: int) -> bool:
        looked_up.append(pid)
        return False

    with pytest.raises(module.LiveProviderLockTimeout):
        module.acquire("grammar-lab", 0.05, path=path, pid=1, wait_max_seconds=0, poll_seconds=0, pid_alive=pid_alive)
    assert looked_up == []


def test_other_lanes_lock_with_a_stale_heartbeat_is_an_orphan(tmp_path: Path) -> None:
    path = tmp_path / "live-deepseek.lock"
    _write_lock(path, "intelligence", os.getpid(), heartbeat_age=601)
    info, removed = _take(path)
    assert info.lane == "grammar-lab"
    assert removed == [("intelligence", "stale")]


def test_old_format_lock_falls_back_to_acquired_at_with_the_sixty_minute_window(tmp_path: Path) -> None:
    path = tmp_path / "live-deepseek.lock"
    _write_lock(path, "intelligence", os.getpid(), heartbeat_age=None, acquired_age=3500)
    with pytest.raises(module.LiveProviderLockTimeout):  # 58 min: still inside the window
        _take(path)
    _write_lock(path, "intelligence", os.getpid(), heartbeat_age=None, acquired_age=3700)
    _, removed = _take(path)
    assert removed == [("intelligence", "stale")]


def test_old_format_lock_of_another_lane_is_not_removed_by_pid(tmp_path: Path) -> None:
    path = tmp_path / "live-deepseek.lock"
    _write_lock(path, "intelligence", _spawn_and_wait_for_a_finished_process(), heartbeat_age=None, acquired_age=10)
    with pytest.raises(module.LiveProviderLockTimeout):
        _take(path)


def test_refresh_heartbeat_updates_only_the_owners_lock(tmp_path: Path) -> None:
    path = tmp_path / "live-deepseek.lock"
    _write_lock(path, "grammar-lab", 4242, heartbeat_age=300)
    before = json.loads(path.read_text(encoding="utf-8"))
    assert module.refresh_heartbeat("intelligence", path=path, pid=4242) is False
    assert module.refresh_heartbeat("grammar-lab", path=path, pid=999) is False
    assert json.loads(path.read_text(encoding="utf-8")) == before
    assert module.refresh_heartbeat("grammar-lab", path=path, pid=4242) is True
    after = json.loads(path.read_text(encoding="utf-8"))
    assert after["heartbeat_at"] > before["heartbeat_at"]
    assert {k: v for k, v in after.items() if k != "heartbeat_at"} == {
        k: v for k, v in before.items() if k != "heartbeat_at"
    }
    assert module.refresh_heartbeat("grammar-lab", path=tmp_path / "missing.lock", pid=4242) is False


def test_heartbeat_thread_keeps_the_lock_fresh_and_stops(tmp_path: Path) -> None:
    path = tmp_path / "live-deepseek.lock"
    _write_lock(path, "grammar-lab", 4242, heartbeat_age=500)

    def heartbeat_at() -> str:
        info = module._read_lock(path)
        assert info is not None and info.heartbeat_at is not None
        return info.heartbeat_at

    stale = heartbeat_at()
    beater = module.Heartbeat("grammar-lab", ["deepseek"], directory=tmp_path, pid=4242, interval=0.01).start()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and heartbeat_at() == stale:
        time.sleep(0.01)
    beater.stop()
    assert heartbeat_at() > stale


def test_acquire_groups_heartbeats_locks_already_taken_while_waiting(tmp_path: Path) -> None:
    _write_lock(tmp_path / "live-deepseek.lock", "intelligence", 555, heartbeat_age=1)
    gemini = tmp_path / "live-gemini-text.lock"
    seen: list[str] = []

    def sleep(_: float) -> None:
        seen.append(json.loads(gemini.read_text(encoding="utf-8"))["heartbeat_at"])

    ticks = iter([0, 0, 0, 0, 0, 10, 100])
    with pytest.raises(module.LiveProviderLockTimeout):
        module.acquire_groups(
            "grammar-lab", 0.05, ["gemini-text", "deepseek"], directory=tmp_path, pid=4242,
            wait_max_seconds=50, poll_seconds=30, clock=lambda: next(ticks), sleep=sleep,
        )
    assert seen  # the held gemini-text lock was stamped on the poll, not left to age
    assert not gemini.exists()  # and given back on timeout


def test_heartbeat_cli_once_reports_whether_the_lock_is_still_ours(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "lock_dir", lambda: tmp_path)
    args = ["heartbeat", "--lane", "grammar-lab", "--pid", "4242", "--groups", "deepseek", "--once"]
    assert module.main(args) == 1  # nothing held
    module.acquire_groups("grammar-lab", 0.05, ["deepseek"], directory=tmp_path, pid=4242)
    assert module.main(args) == 0


def test_acquire_removes_a_lock_older_than_the_stale_window(tmp_path: Path) -> None:
    path = _hold(tmp_path, "deepseek", "intelligence", os.getpid())
    removed: list[str] = []
    info = module.acquire(
        "grammar-lab", 0.05, path=path, pid=os.getpid(),
        stale_seconds=0,  # the lock just written is already "older" than a zero-second window
        on_orphan_removed=lambda existing, reason, lock: removed.append(reason),
    )
    assert info.lane == "grammar-lab"
    assert removed == ["stale"]


def test_release_deletes_the_lock_when_lane_and_pid_match(tmp_path: Path) -> None:
    path = tmp_path / "live-deepseek.lock"
    module.acquire("grammar-lab", 0.05, path=path, pid=4242)
    assert module.release("grammar-lab", path=path, pid=4242) is True
    assert not path.exists()


def test_release_leaves_another_lanes_lock_untouched(tmp_path: Path) -> None:
    path = _hold(tmp_path, "deepseek", "intelligence", 555)
    assert module.release("grammar-lab", path=path, pid=4242) is False
    assert path.exists()


def test_windows_pid_alive_checks_exit_code_not_only_open_process(monkeypatch: pytest.MonkeyPatch) -> None:
    class Kernel32:
        def __init__(self, exit_code: int) -> None:
            self.exit_code = exit_code
            self.closed: list[int] = []

        def OpenProcess(self, access: int, inherit: bool, pid: int) -> int:
            assert access == 0x1000 and inherit is False and pid == 4242
            return 123

        def GetExitCodeProcess(self, handle: int, out) -> int:
            assert handle == 123
            out._obj.value = self.exit_code
            return 1

        def CloseHandle(self, handle: int) -> None:
            self.closed.append(handle)

    class Windll:
        def __init__(self, kernel32: Kernel32) -> None:
            self.kernel32 = kernel32

    monkeypatch.setattr(module.sys, "platform", "win32")

    dead = Kernel32(0)
    monkeypatch.setattr(module.ctypes, "windll", Windll(dead), raising=False)
    assert module._pid_alive(4242) is False
    assert dead.closed == [123]

    live = Kernel32(259)
    monkeypatch.setattr(module.ctypes, "windll", Windll(live), raising=False)
    assert module._pid_alive(4242) is True
    assert live.closed == [123]


def test_windows_pid_alive_fails_closed_when_exit_state_cannot_be_queried(monkeypatch: pytest.MonkeyPatch) -> None:
    class Kernel32:
        def OpenProcess(self, access: int, inherit: bool, pid: int) -> int:
            return 123

        def GetExitCodeProcess(self, handle: int, out) -> int:
            return 0

        def CloseHandle(self, handle: int) -> None:
            pass

    class Windll:
        kernel32 = Kernel32()

    monkeypatch.setattr(module.sys, "platform", "win32")
    monkeypatch.setattr(module.ctypes, "windll", Windll(), raising=False)
    assert module._pid_alive(4242) is True


def test_pid_alive_is_true_for_the_current_process() -> None:
    assert module._pid_alive(os.getpid()) is True


def test_pid_alive_is_false_for_a_finished_process() -> None:
    assert module._pid_alive(_spawn_and_wait_for_a_finished_process()) is False


# --- one lock per quota group ------------------------------------------------------------

def test_each_quota_group_has_its_own_lock_file(tmp_path: Path) -> None:
    assert module.lock_path("gemini-text", directory=tmp_path) == tmp_path / "live-gemini-text.lock"
    assert module.lock_path("gemini-live", directory=tmp_path) == tmp_path / "live-gemini-live.lock"
    assert module.lock_path("deepseek", directory=tmp_path) == tmp_path / "live-deepseek.lock"


def test_default_lock_dir_is_userprofile_dot_orena(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert module.lock_dir() == tmp_path / ".orena"


def test_unknown_group_is_rejected(tmp_path: Path) -> None:
    for group in ("groq", "provider"):  # groq has no lock yet; the old single lock is gone
        with pytest.raises(ValueError):
            module.acquire_groups("grammar-lab", 0.05, [group], directory=tmp_path, pid=4242)


def test_acquire_groups_takes_locks_in_the_fixed_order(tmp_path: Path) -> None:
    taken = module.acquire_groups("grammar-lab", 0.05, ["deepseek", "gemini-text"], directory=tmp_path, pid=4242)
    assert taken == ["gemini-text", "deepseek"]  # gemini-text -> gemini-live -> deepseek, whatever the input order
    assert (tmp_path / "live-gemini-text.lock").exists()
    assert (tmp_path / "live-deepseek.lock").exists()
    assert not (tmp_path / "live-gemini-live.lock").exists()  # only the groups actually used


def test_acquire_groups_gives_back_what_it_took_when_a_later_lock_is_held(tmp_path: Path) -> None:
    held = _hold(tmp_path, "deepseek", "intelligence", os.getpid())
    with pytest.raises(module.LiveProviderLockTimeout) as excinfo:
        module.acquire_groups(
            "grammar-lab", 0.05, ["gemini-text", "deepseek"], directory=tmp_path, pid=4242,
            wait_max_seconds=0, poll_seconds=0,
        )
    assert excinfo.value.lock_name == "live-deepseek.lock"
    assert excinfo.value.holder.lane == "intelligence"
    assert not (tmp_path / "live-gemini-text.lock").exists()  # returned, not left dangling
    assert json.loads(held.read_text(encoding="utf-8"))["lane"] == "intelligence"  # theirs, untouched


def test_release_groups_goes_in_reverse_order_and_only_touches_own_locks(tmp_path: Path) -> None:
    module.acquire_groups("grammar-lab", 0.05, ["gemini-text", "deepseek"], directory=tmp_path, pid=4242)
    theirs = _hold(tmp_path, "gemini-live", "intelligence", 555)
    released = module.release_groups(
        "grammar-lab", ["gemini-text", "gemini-live", "deepseek"], directory=tmp_path, pid=4242,
    )
    assert released == ["deepseek", "gemini-text"]
    assert theirs.exists()


# --- module guarantees -----------------------------------------------------------------

def test_module_never_touches_docker() -> None:
    # A lock is a plain file. The module must not be able to stop another lane's container,
    # even by accident -- it cannot spawn any external process at all.
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    for forbidden in ("import subprocess", "os.system", "os.exec", "os.spawn"):
        assert forbidden not in source


def test_old_single_lock_path_is_gone() -> None:
    assert "live-provider.lock" not in SCRIPT_PATH.read_text(encoding="utf-8")


# --- CLI ---------------------------------------------------------------------------------

def test_main_acquire_then_release_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "lock_dir", lambda: tmp_path)
    common = ["--lane", "grammar-lab", "--pid", "4242", "--groups", "deepseek,gemini-text"]
    assert module.main(["acquire", *common, "--cost-ceiling-usd", "0.05"]) == 0
    assert (tmp_path / "live-gemini-text.lock").exists()
    assert (tmp_path / "live-deepseek.lock").exists()
    assert module.main(["release", *common]) == 0
    assert not list(tmp_path.glob("*.lock"))


def test_main_acquire_reports_the_holder_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(module, "lock_dir", lambda: tmp_path)
    _hold(tmp_path, "gemini-text", "intelligence", os.getpid())
    code = module.main([
        "acquire", "--lane", "grammar-lab", "--pid", "99999", "--groups", "gemini-text,deepseek",
        "--cost-ceiling-usd", "0.05", "--wait-max-seconds", "0", "--poll-seconds", "0",
    ])
    assert code == 1
    out = capsys.readouterr().out
    assert "lane=intelligence" in out and "live-gemini-text.lock" in out
    assert not (tmp_path / "live-deepseek.lock").exists()  # never reached, never taken


def test_main_prints_the_shared_orphan_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(module, "lock_dir", lambda: tmp_path)
    _write_lock(
        tmp_path / "live-deepseek.lock", "grammar-lab", _spawn_and_wait_for_a_finished_process(), heartbeat_age=1,
    )
    code = module.main([
        "acquire", "--lane", "grammar-lab", "--pid", "4242", "--groups", "deepseek", "--cost-ceiling-usd", "0.05",
    ])
    assert code == 0
    assert "orphan lock removed: lane=grammar-lab reason=dead-pid" in capsys.readouterr().out
