"""The machine-wide live-provider lock the live runner takes (scripts/agent_live/lock.py)."""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "agent_live_lock", Path(__file__).resolve().parents[1] / "scripts/agent_live/lock.py"
)
lock = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("agent_live_lock", lock)  # dataclasses look their module up
_SPEC.loader.exec_module(lock)


class Clock:
    def __init__(self, now: float = 1_800_000_000.0) -> None:
        self.now = now
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def held(path: Path, clock: Clock, *, pid: int = 4242, host: str | None = None, age: float = 0) -> dict:
    record = {
        "lane": "grammar-lab",
        "pid": pid,
        "host": host or socket.gethostname(),
        "started_at": datetime.fromtimestamp(clock() - age, UTC).isoformat(),
        "cap_usd": 0.2,
        "purpose": "eval",
    }
    path.write_text(json.dumps(record), encoding="utf-8")
    return record


def take(path: Path, clock: Clock, alive=lambda pid: True, **kw):
    return lock.acquire("feature/orena-intelligence", 0.3, path=path, clock=clock, sleep=clock.sleep, alive=alive,
                        say=lambda _m: None, **kw)  # fmt: skip


def test_a_free_lock_is_taken_with_its_record_and_released(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    taken = take(path, clock)
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["lane"] == "feature/orena-intelligence" and record["pid"] == os.getpid()
    assert record["cap_usd"] == 0.3 and record["host"] == socket.gethostname()
    assert datetime.fromisoformat(record["started_at"]).timestamp() == clock()
    assert taken.notes == []
    taken.release()
    assert not path.exists()


def test_the_default_path_is_outside_every_repository(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert lock.lock_path() == tmp_path / ".orena" / "live-provider.lock"


def test_a_held_lock_is_waited_for_every_30_seconds_then_taken(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    held(path, clock)
    released_after = 3

    def sleep(seconds):
        clock.sleep(seconds)
        if len(clock.sleeps) == released_after:
            path.unlink()

    taken = lock.acquire("me", 0.3, path=path, clock=clock, sleep=sleep, alive=lambda pid: True, say=lambda _m: None)
    assert clock.sleeps == [30] * released_after
    assert json.loads(path.read_text(encoding="utf-8"))["lane"] == "me"
    assert taken.notes == ["waited for the live-provider lock"]


def test_a_lock_held_past_30_minutes_of_waiting_stops_the_run_and_is_left_alone(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    record = held(path, clock)
    with pytest.raises(lock.LockTimeout, match="ask the human"):
        take(path, clock)
    assert sum(clock.sleeps) == 30 * 60
    assert json.loads(path.read_text(encoding="utf-8")) == record  # never removed


def test_a_lock_whose_holder_is_gone_is_an_orphan_removed_and_reported(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    held(path, clock, pid=4242)
    taken = take(path, clock, alive=lambda pid: pid != 4242)
    assert clock.sleeps == []
    assert json.loads(path.read_text(encoding="utf-8"))["pid"] == os.getpid()
    assert len(taken.notes) == 1 and "process 4242 is no longer running" in taken.notes[0]


def test_a_lock_held_over_60_minutes_is_an_orphan(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    held(path, clock, age=61 * 60)
    taken = take(path, clock)
    assert "held for more than 60 min" in taken.notes[0]


def test_a_holder_on_another_host_is_not_judged_by_its_pid(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    held(path, clock, host="another-machine")
    with pytest.raises(lock.LockTimeout):
        take(path, clock, alive=lambda pid: False)


def test_release_never_removes_someone_elses_lock(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    taken = take(path, clock)
    path.unlink()
    other = held(path, clock)  # another lane took it meanwhile
    taken.release()
    assert json.loads(path.read_text(encoding="utf-8")) == other


def test_an_orphan_replaced_meanwhile_is_not_removed(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    judged = held(path, clock, pid=4242)
    mtime = path.stat().st_mtime
    newer = held(path, clock, pid=os.getpid())
    assert lock._remove_if_unchanged(path, judged, mtime) is False
    assert json.loads(path.read_text(encoding="utf-8")) == newer


def test_this_process_is_alive_and_a_finished_one_is_not():
    import subprocess

    assert lock.pid_alive(os.getpid())
    done = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True, text=True)
    assert not lock.pid_alive(int(done.stdout))
    assert not lock.pid_alive(0)
