"""The machine-wide live-provider lock, in the format the Grammar Lab lane defined (scripts/agent_live/lock.py)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
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

LANE = "feature/orena-intelligence"


class Clock:
    def __init__(self, now: float = 1_800_000_000.0) -> None:
        self.now = now
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def held(path: Path, clock: Clock, *, lane: str = "grammar-lab", pid: int = 4242, age: float = 0) -> dict:
    record = {
        "lane": lane,
        "pid": pid,
        "acquired_at": datetime.fromtimestamp(clock() - age, UTC).isoformat(),
        "cost_ceiling_usd": 0.2,
    }
    path.write_text(json.dumps(record), encoding="utf-8")
    return record


def take(path: Path, clock: Clock, alive=lambda pid: True, said=None):
    return lock.acquire(LANE, 0.3, path=path, clock=clock, sleep=clock.sleep, alive=alive,
                        say=(said.append if said is not None else lambda _m: None))  # fmt: skip


def on_disk(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_record_is_exactly_the_shared_format(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    taken = take(path, clock)
    record = on_disk(path)
    assert set(record) == {"lane", "pid", "acquired_at", "cost_ceiling_usd"}
    assert record["lane"] == LANE and record["pid"] == os.getpid() and record["cost_ceiling_usd"] == 0.3
    acquired = datetime.fromisoformat(record["acquired_at"])
    assert acquired.utcoffset().total_seconds() == 0 and acquired.timestamp() == clock()
    assert taken.notes == []
    taken.release()
    assert not path.exists()


def test_the_path_is_outside_every_repository(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert lock.lock_path() == tmp_path / ".orena" / "live-provider.lock"


def test_creation_is_exclusive(tmp_path, monkeypatch):
    path, clock = tmp_path / "live-provider.lock", Clock()
    flags = []
    real_open = os.open
    monkeypatch.setattr(lock.os, "open", lambda p, f, *a: flags.append(f) or real_open(p, f, *a))
    take(path, clock)
    assert flags and flags[0] & os.O_CREAT and flags[0] & os.O_EXCL


def test_a_held_lock_is_checked_every_30_seconds_then_taken(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    held(path, clock)

    def sleep(seconds):
        clock.sleep(seconds)
        if len(clock.sleeps) == 3:
            path.unlink()  # the other lane releases it

    taken = lock.acquire(LANE, 0.3, path=path, clock=clock, sleep=sleep, alive=lambda pid: True, say=lambda _m: None)
    assert clock.sleeps == [30, 30, 30]
    assert on_disk(path)["lane"] == LANE
    assert taken.notes == ["waited for the live-provider lock"]


def test_after_30_minutes_it_stops_naming_the_holder_and_leaves_the_lock(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    record = held(path, clock, lane="grammar-lab", pid=4242)
    with pytest.raises(lock.LockTimeout, match="lane=grammar-lab pid=4242"):
        take(path, clock)
    assert sum(clock.sleeps) == 30 * 60 and set(clock.sleeps) == {30}
    assert on_disk(path) == record


def test_a_dead_pid_is_an_orphan_removed_reported_and_retried_at_once(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    held(path, clock, lane="grammar-lab", pid=4242)
    said: list[str] = []
    taken = take(path, clock, alive=lambda pid: pid != 4242, said=said)
    assert clock.sleeps == []  # at once
    assert on_disk(path)["pid"] == os.getpid()
    assert taken.notes == said == ["orphan lock removed: lane=grammar-lab reason=dead-pid"]


def test_a_lock_acquired_over_60_minutes_ago_is_stale(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    held(path, clock, lane="grammar-lab", age=61 * 60)
    taken = take(path, clock)
    assert taken.notes == ["orphan lock removed: lane=grammar-lab reason=stale"]


def test_a_lock_under_60_minutes_with_a_live_pid_is_waited_for(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    held(path, clock, age=59 * 60)
    with pytest.raises(lock.LockTimeout):
        lock.acquire(LANE, 0.3, path=path, clock=clock, sleep=clock.sleep, alive=lambda pid: True,
                     say=lambda _m: None, wait=30)  # fmt: skip


def test_release_removes_only_a_lock_with_this_lane_and_pid(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    taken = take(path, clock)
    path.unlink()
    other = held(path, clock, lane="grammar-lab", pid=os.getpid())  # same pid, other lane
    taken.release()
    assert on_disk(path) == other
    path.unlink()
    other = held(path, clock, lane=LANE, pid=os.getpid() + 1)  # same lane, other pid
    taken.released = False
    taken.release()
    assert on_disk(path) == other


def test_an_orphan_replaced_meanwhile_is_not_removed(tmp_path):
    path, clock = tmp_path / "live-provider.lock", Clock()
    judged = held(path, clock, pid=4242)
    mtime = path.stat().st_mtime
    newer = held(path, clock, pid=os.getpid())
    assert lock._remove_if_unchanged(path, judged, mtime) is False
    assert on_disk(path) == newer


def test_liveness_of_a_real_process():
    assert lock.pid_alive(os.getpid())
    done = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True, text=True)
    assert not lock.pid_alive(int(done.stdout))
    assert not lock.pid_alive(0)


def test_the_runner_holds_it_around_the_sandbox():
    source = (Path(__file__).resolve().parents[1] / "scripts/agent_live/run.py").read_text(encoding="utf-8")
    main = source[source.index("def main()"):source.index("def _add_provider_errors")]
    assert main.index("live_lock.acquire(") < main.index("sandbox.up(")
    assert main.index("sandbox.down()") < main.index("lock.release()")
