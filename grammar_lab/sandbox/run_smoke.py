"""Persistent, lock-aware runner for the evaluator sandbox (sandbox/README.md).

Supersedes an ad-hoc shell script: every live run against the :8020 sandbox -- including
a smoke test -- goes through here so the quota-group locks (live_provider_lock.py) and
the check for another lane's live session are never skipped or reimplemented by hand.

Usage::

    python sandbox/run_smoke.py --dotenv <path to .env> \\
        --ids en.plural_nouns.regular,en.there_is_are \\
        --generate-provider deepseek --generate-model deepseek-flash \\
        --blind-provider groq --blind-model openai/gpt-oss-120b \\
        [--deepseek-thinking off] [--cost-ceiling-usd 0.05]

Order of operations, with guaranteed cleanup (docker compose down, then the lock release)
even if a step raises or the process is interrupted:

1. Hold the quota-group locks this run uses (live_provider_lock.py): always gemini-text,
   since the sandbox's evaluator engine is a Gemini text model, plus deepseek when DeepSeek
   generates or blind-solves. Groq has no lock yet. AND confirm no ``orena-agent-live-*``
   container is running. If one is: release the locks, wait, retry, up to 30 minutes, with
   no need to prompt anyone (message to the human, 2026-09-28). Giving up after that raises
   and is reported.
2. Bring the :8020 sandbox up, select Gemini as its provider.
3. Run generate (--with-story optional) -> validate -> verify for the given point ids.
4. Print the sandbox's own AI-operations telemetry, if any.
5. Tear down: ``docker compose down``, then release the locks -- always, in that order.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

SANDBOX_DIR = Path(__file__).resolve().parent
LAB_ROOT = SANDBOX_DIR.parent
COMPOSE_FILE = SANDBOX_DIR / "docker-compose.yml"
COMPOSE_PROJECT = "grammar-lab-eval"
SANDBOX_URL = "http://localhost:8020"


def _load_sibling(name: str):
    spec = importlib.util.spec_from_file_location(name, SANDBOX_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


live_provider_lock = _load_sibling("live_provider_lock")
with_env_from_dotenv = _load_sibling("with_env_from_dotenv")


class LiveLaneStillRunning(RuntimeError):
    def __init__(self, waited_seconds: float) -> None:
        self.waited_seconds = waited_seconds
        super().__init__(
            f"gave up after {waited_seconds:.0f}s: another lane's orena-agent-live-* "
            "container is still running"
        )


def _other_lane_is_live(container_names: list[str]) -> bool:
    return any(name.startswith("orena-agent-live") for name in container_names)


def _docker_ps_names() -> list[str]:
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, check=True
    )
    return [line for line in result.stdout.splitlines() if line]


_PROVIDER_QUOTA_GROUP = {"gemini": "gemini-text", "deepseek": "deepseek"}


def quota_groups(generate_provider: str, blind_provider: str) -> list[str]:
    """The lock groups a run draws on: the engine's Gemini text quota always, plus whichever
    of generate/blind-solve maps to a locked group (Groq and others have no lock)."""
    used = {"gemini-text"}
    used.update(_PROVIDER_QUOTA_GROUP[p] for p in (generate_provider, blind_provider) if p in _PROVIDER_QUOTA_GROUP)
    return [group for group in live_provider_lock.GROUP_ORDER if group in used]


def _report_orphan(existing: Any, reason: str, lock: Path) -> None:
    print(f"orphan lock removed: lane={existing.lane} reason={reason} pid={existing.pid} lock={lock.name}")


def wait_for_clear_to_run(
    lane: str,
    cost_ceiling_usd: float,
    groups: list[str],
    *,
    list_containers: Callable[[], list[str]] = _docker_ps_names,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    poll_seconds: float = 30.0,
    wait_max_seconds: float = 1800.0,
    directory: Path | None = None,
    pid: int | None = None,
) -> list[str]:
    """Hold the run's quota-group locks AND confirm no other lane's live container is running.

    Message to the human, 2026-09-28: "Lane intelligence co the chua dung khoa. Truoc khi
    dung sandbox: giu khoa, VA kiem docker ps khong co orena-agent-live-*. Co thi nha khoa,
    cho 30 giay roi thu lai (toi da 30 phut), khong can bao toi." -- the retries here are
    silent by design; only giving up after the full budget raises.
    """
    start = clock()
    while True:
        taken = live_provider_lock.acquire_groups(
            lane, cost_ceiling_usd, groups, directory=directory, pid=pid,
            wait_max_seconds=max(0.0, wait_max_seconds - (clock() - start)), poll_seconds=poll_seconds,
            clock=clock, sleep=sleep, on_orphan_removed=_report_orphan,
        )
        if not _other_lane_is_live(list_containers()):
            return taken
        live_provider_lock.release_groups(lane, taken, directory=directory, pid=pid)
        if clock() - start >= wait_max_seconds:
            raise LiveLaneStillRunning(clock() - start)
        sleep(poll_seconds)


def _run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    print(f"=== {' '.join(command)} ===")
    return subprocess.run(command, check=True, **kwargs)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dotenv", required=True, help="Path to the .env holding the provider API keys.")
    parser.add_argument("--lang", default="en")
    parser.add_argument("--ids", required=True, help="Comma-separated point ids.")
    parser.add_argument("--generate-provider", required=True)
    parser.add_argument("--generate-model", required=True)
    parser.add_argument("--generate-api-key-name", default=None, help="Default: <PROVIDER>_API_KEY.")
    parser.add_argument("--blind-provider", required=True)
    parser.add_argument("--blind-model", required=True)
    parser.add_argument("--blind-api-key-name", default=None, help="Default: <PROVIDER>_API_KEY.")
    parser.add_argument("--gemini-api-key-name", default="GEMINI_API_KEY", help="For the sandbox's own engine.")
    parser.add_argument("--with-story", action="store_true")
    parser.add_argument("--deepseek-thinking", default="off")
    parser.add_argument("--story-mode", default="everyday")
    parser.add_argument("--lane", default="grammar-lab")
    parser.add_argument("--cost-ceiling-usd", type=float, default=0.05)
    parser.add_argument("--wait-max-seconds", type=float, default=1800.0)
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    args = parser.parse_args(argv)

    venv_py = sys.executable
    pid = os.getpid()
    generate_key_name = args.generate_api_key_name or f"{args.generate_provider.upper()}_API_KEY"
    blind_key_name = args.blind_api_key_name or f"{args.blind_provider.upper()}_API_KEY"

    groups = quota_groups(args.generate_provider, args.blind_provider)
    print(f"=== acquiring quota-group locks: {','.join(groups)} ===")
    taken = wait_for_clear_to_run(
        args.lane, args.cost_ceiling_usd, groups,
        pid=pid, wait_max_seconds=args.wait_max_seconds, poll_seconds=args.poll_seconds,
    )

    def cleanup() -> None:
        print("=== tearing down sandbox ===")
        try:
            _run([
                venv_py, str(SANDBOX_DIR / "with_env_from_dotenv.py"), args.dotenv, args.gemini_api_key_name,
                "--", "docker", "compose", "-p", COMPOSE_PROJECT, "-f", str(COMPOSE_FILE), "down",
            ])
        finally:
            released = live_provider_lock.release_groups(args.lane, taken, pid=pid)
            print(f"=== released quota-group locks: {','.join(released) or '(none)'} ===")

    try:
        _run([
            venv_py, str(SANDBOX_DIR / "with_env_from_dotenv.py"), args.dotenv, args.gemini_api_key_name,
            "--", "docker", "compose", "-p", COMPOSE_PROJECT, "-f", str(COMPOSE_FILE), "up", "-d",
        ])
        time.sleep(3)

        httpx.put(
            f"{SANDBOX_URL}/api/admin/ai/config", json={"provider": "gemini", "model": "gemini-3.5-flash-lite"}
        ).raise_for_status()
        print(httpx.get(f"{SANDBOX_URL}/api/health").json())

        generate_command = [
            venv_py, str(SANDBOX_DIR / "with_env_from_dotenv.py"), args.dotenv, generate_key_name,
            "--", venv_py, "-m", "grammar_lab.pipeline.cli", "generate", "--lang", args.lang,
            "--ids", args.ids, "--provider", args.generate_provider, "--model", args.generate_model,
            "--deepseek-thinking", args.deepseek_thinking,
        ]
        if args.with_story:
            generate_command += ["--with-story", "--story-mode", args.story_mode]
        _run(generate_command, cwd=LAB_ROOT)

        _run([venv_py, "-m", "grammar_lab.pipeline.cli", "validate", "--lang", args.lang], cwd=LAB_ROOT)

        _run([
            venv_py, str(SANDBOX_DIR / "with_env_from_dotenv.py"), args.dotenv, blind_key_name,
            "--", venv_py, "-m", "grammar_lab.pipeline.cli", "verify", "--lang", args.lang,
            "--evaluator-url", SANDBOX_URL, "--blind-provider", args.blind_provider,
            "--blind-model", args.blind_model, "--ids", args.ids,
        ], cwd=LAB_ROOT)

        print("=== engine telemetry (admin/ai/operations) ===")
        print(httpx.get(f"{SANDBOX_URL}/api/admin/ai/operations").json())
    finally:
        cleanup()

    print("=== run_smoke finished ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
