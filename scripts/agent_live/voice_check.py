"""The live voice check (R28, mode A): the real /api/agent/voice/* against Gemini Live, under the human's cap.

    python scripts/agent_live/voice_check.py --approved --cap-usd 0.80 --gemini-env <.env holding GEMINI_*> \
        --out <scratch dir>/voice.json [--only vi-name,vi-word-here]

It holds the Gemini Live quota group's lock (live-gemini-live.lock) for the whole run, starts compose.yaml's
throwaway sandbox with AGENT_VOICE_ENABLED on (only GEMINI_* is read from the env file; the key is never printed),
runs voice_client.py inside the app image - a client that holds no key, only the token the server gives it - and
takes the sandbox down and releases the lock however the run ends. The client stops before the next scenario could
pass the cap. Results and the WAV files of Orena's speech go next to --out.
"""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lock as live_lock  # noqa: E402
import run  # noqa: E402  (the text runner's sandbox, ports and env, reused as they are)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gemini-env", help="a .env file to take GEMINI_* from")
    parser.add_argument("--cap-usd", type=float)
    parser.add_argument("--approved", action="store_true", help="the human approved this run and its cap")
    parser.add_argument("--out", required=True)
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    if not args.approved or args.cap_usd is None or not 0 < args.cap_usd <= 1.0:
        sys.exit("refusing: needs --approved and a --cap-usd within the approved 1.00 USD a day")
    for name in ("SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), run._stop_on_signal)
    try:
        lock = live_lock.acquire(run._lane() + ":voice-check", args.cap_usd, group="gemini-live").start_heartbeat()
    except live_lock.LockTimeout as error:
        print(f"stopping: {error}")
        return 3
    try:
        port = next((p for p in sorted(run.SANDBOX_PORTS) if run._port_free(p)), None)
        if port is None:
            print(f"refusing: {sorted(run.SANDBOX_PORTS)} are all taken")
            return 1
        env = run._compose_env(args.gemini_env, port)
        env["AGENT_VOICE_ENABLED"] = "true"
        sandbox = run.Sandbox(env)
        sandbox._compose("down", "--remove-orphans", check=False)
        try:
            base = f"http://127.0.0.1:{port}"
            sandbox.up(base)
            with urllib.request.urlopen(base + "/api/readiness", timeout=10) as response:
                if b'"development"' not in response.read():
                    sys.exit("refusing: the server reports production")
            out = Path(args.out).resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            command = [
                "docker", "run", "--rm", "--add-host", "host.docker.internal:host-gateway",
                "-v", f"{HERE}:/check:ro", "-v", f"{out.parent}:/out",
                "ai-writing-coach:local", "python", "/check/voice_client.py",
                "--base", f"http://host.docker.internal:{port}", "--cap-usd", str(args.cap_usd),
                "--out", f"/out/{out.name}", "--only", args.only,
            ]  # fmt: skip
            return subprocess.run(command, check=False).returncode
        finally:
            sandbox.down()
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
