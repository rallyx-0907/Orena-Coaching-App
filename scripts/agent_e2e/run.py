"""The agent's E2E on a throwaway stack (INTELLIGENCE_RECONCILIATION_D4.md section 5), with no provider.

Three stacks, one after another, each taken down whatever happens:
  1. agent on, account backbone off (the compose default)  - the in-container harness, then the UI's own client
  2. agent on, account backbone on                          - the same, to show the agent's reads do not depend on it
  3. agent off                                              - capabilities 404, a turn is "absent"

    python scripts/agent_e2e/run.py [--out <file outside the repository>]

Writes one JSON with every result; exit 0 only when every check of every pass passed. Standard library only.
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "scripts/agent_e2e/compose.yaml"
PROJECT = "orena-agent-e2e"
PORTS = (8016, 8017)  # never 8000, 8010-8013, 8015, 8021


def compose(env: dict, *args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    command = ["docker", "compose", "-p", PROJECT, "-f", str(COMPOSE), *args]
    return subprocess.run(command, env=env, check=check, capture_output=capture, text=capture, encoding="utf-8" if capture else None)


def free(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def down(env: dict) -> None:
    compose(env, "down", "--remove-orphans", check=False)


def wait_ready(url: str, seconds: float = 180) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url + "/api/readiness", timeout=3) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(2)
    raise RuntimeError("the stack did not become ready")


def last_json(text_: str) -> dict:
    for line in reversed((text_ or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    return {"error": "no JSON from the pass", "tail": (text_ or "")[-1500:]}


def run_pass(name: str, base_env: dict, port: int, *, backbone: str, agent: bool) -> dict:
    env = {**base_env, "AGENT_E2E_PORT": str(port), "ORENA_ACCOUNT_BACKBONE": backbone, "AGENT_ENABLED": "true" if agent else "false"}
    down(env)  # leftovers of a run killed outright
    result: dict = {"pass": name, "backbone": backbone or "off", "agent": agent}
    try:
        compose(env, "up", "-d")
        url = f"http://127.0.0.1:{port}"
        wait_ready(url)
        if agent:
            harness = compose(env, "exec", "-T", "web", "python", "scripts/agent_e2e/harness.py", check=False, capture=True)
            result["harness"] = last_json(harness.stdout)
            result["harness_exit"] = harness.returncode
            if harness.returncode not in (0, 1):
                result["harness_stderr"] = (harness.stderr or "")[-2000:]
            # a fresh stack state for the UI client: the harness used up the learner's turn budget (its 429 check)
            compose(env, "restart", "web")
            wait_ready(url)
        node = subprocess.run(
            ["node", str(ROOT / "scripts/agent_e2e/transport_check.mjs"), url, *([] if agent else ["--agent-off"])],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        result["transport"] = last_json(node.stdout)
        result["transport_exit"] = node.returncode
    except Exception as exc:  # recorded; the stack still comes down
        result["error"] = repr(exc)
    finally:
        down(env)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "orena-agent-e2e.json"))
    args = parser.parse_args()
    port = next((p for p in PORTS if free(p)), None)
    if port is None:
        print(f"refusing: {PORTS} are taken")
        return 1
    base_env = {k: v for k, v in os.environ.items() if not k.startswith(("COMPOSE_", "GEMINI_", "AGENT_", "ORENA_"))}
    atexit.register(down, {**base_env, "AGENT_E2E_PORT": str(port)})
    for name in ("SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lambda signum, frame: (_ for _ in ()).throw(SystemExit(128 + signum)))
    passes = [
        run_pass("agent on, backbone off", base_env, port, backbone="", agent=True),
        run_pass("agent on, backbone on", base_env, port, backbone="on", agent=True),
        run_pass("agent off", base_env, port, backbone="", agent=False),
    ]
    ok = all(
        p.get("harness_exit", 0) == 0 and p.get("transport_exit") == 0 and "error" not in p for p in passes
    )
    Path(args.out).write_text(json.dumps({"ok": ok, "passes": passes}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    for p in passes:
        failed = (p.get("harness") or {}).get("failed", []) + (p.get("transport") or {}).get("failed", [])
        print(f"{p['pass']:26} harness={p.get('harness_exit')} transport={p.get('transport_exit')} "
              f"error={p.get('error')} failed={failed}")  # fmt: skip
    print(f"results: {args.out}  ok={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
