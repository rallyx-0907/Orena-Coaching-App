"""Hold the cross-lane quota lock while a live provider run is going (human, 2026-09-29, item 6).

The lock file format and the orphan / heartbeat rules live in ``sandbox/live_provider_lock.py`` (shared with the
Orena Intelligence lane); this only loads that module and wraps "take the lock for the provider I am about to
call, keep it fresh, give it back" so ``generate`` and the other live commands cannot forget any of the three.
A provider with no lock group (Groq, Anthropic, OpenAI) runs without one.
"""

from __future__ import annotations

import contextlib
import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

from grammar_lab.pipeline.validate import LAB_ROOT

GROUP_BY_PROVIDER = {"deepseek": "deepseek", "gemini": "gemini-text"}
LANE = "grammar-lab"
_module: ModuleType | None = None


def lock_module() -> ModuleType:
    global _module
    if _module is None:
        path = LAB_ROOT / "sandbox" / "live_provider_lock.py"
        spec = importlib.util.spec_from_file_location("live_provider_lock", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module  # the dataclass needs the module registered to resolve its types
        spec.loader.exec_module(module)
        _module = module
    return _module


@contextlib.contextmanager
def hold(
    providers: list[str], cost_ceiling_usd: float, *, directory: Path | None = None, pid: int | None = None,
    wait_max_seconds: float = 1800.0, poll_seconds: float = 30.0, heartbeat_seconds: float | None = None,
) -> Iterator[list[str]]:
    """Take the lock group of every provider that has one (fixed order), heartbeat while inside, release after."""
    groups = sorted({GROUP_BY_PROVIDER[p] for p in providers if p in GROUP_BY_PROVIDER})
    if not groups:
        yield []
        return
    module = lock_module()
    taken = module.acquire_groups(
        LANE, cost_ceiling_usd, groups, directory=directory, pid=pid, wait_max_seconds=wait_max_seconds,
        poll_seconds=poll_seconds,
    )
    heartbeat = module.Heartbeat(
        LANE, taken, directory=directory, pid=pid, **({"interval": heartbeat_seconds} if heartbeat_seconds else {}),
    ).start()
    try:
        yield taken
    finally:
        heartbeat.stop()
        module.release_groups(LANE, taken, directory=directory, pid=pid)
