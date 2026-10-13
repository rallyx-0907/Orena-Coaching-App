"""Host-side assertion of the REAL Docker publish address of the app port (issue #140, follow-up of #137).

The app infers "this request is local" from variables, and a container cannot see where Docker publishes its host
port. An operator who hand-edits the publish to 0.0.0.0, :: or another address while the env still declares loopback
defeats that inference. This script runs on the host, after an official launcher started the app container, reads only
the port fields Docker reports and refuses the lane (stopping the container) when any binding of the app port is not
loopback.

    python scripts/assert_published_loopback.py --container <name-or-id> [--port 8000] [--lan-opt-in --probe-url URL]

Exit 0: every binding of the app port is loopback (or the explicit LAN opt-in is on and the app answers 401, sign-in on).
Exit 2: refused; the container was stopped. Exit 3: Docker could not be read; refused the same way (fail closed).
Exit 4: refused, and the stop itself failed or timed out (the container may still be running).

It never dumps the container config: the only Docker reads are the two port-field templates below. It reads no
environment and prints no secret. Stdlib only, so a launcher can run it with the host Python."""

from __future__ import annotations

import argparse
import ipaddress
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterable

# The only Docker reads. Never `docker inspect` without --format and never the environment.
PORT_TEMPLATES = ("{{json .NetworkSettings.Ports}}", "{{json .HostConfig.PortBindings}}")


def is_loopback_host(host: object) -> bool:
    """The loopback rule of writing_coach.core.deployment.is_loopback_host: localhost, 127.0.0.0/8, ::1, ::ffff:127.x.

    Duplicated on purpose: this script must run on the host without the project's dependencies. A test keeps the two
    in agreement. Empty means all interfaces to Docker, and is not loopback."""
    text = str(host or "").strip().casefold().rstrip(".")
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    if text == "localhost":
        return True
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return False
    mapped = getattr(address, "ipv4_mapped", None)
    return (mapped or address).is_loopback


def bindings_of(ports: object, port: int) -> list[str] | None:
    """The host addresses Docker publishes the container's tcp `port` on, from one `Ports`/`PortBindings` JSON value.

    Returns None when that value says the port is not published at all (null, empty, no entry, or an entry with no
    binding). An empty or missing HostIp is returned as "" (Docker's "all interfaces")."""
    if not isinstance(ports, dict):
        return None
    found: list[str] = []
    published = False
    for key, entries in ports.items():
        if str(key).split("/")[0] != str(port) or str(key).partition("/")[2] not in ("", "tcp"):
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries:
            published = True
            found.append(str(entry.get("HostIp") or "") if isinstance(entry, dict) else "")
    return found if published else None


def evaluate(documents: Iterable[object], port: int = 8000) -> tuple[bool, list[str], str]:
    """Decide from the JSON values Docker returned (parsed). Returns (loopback_only, addresses, reason).

    Every binding of the app port, in every document, must be loopback. A port published nowhere is a refusal too:
    an official launcher publishes the app port, so its absence means the read cannot be trusted."""
    addresses: list[str] = []
    for document in documents:
        bound = bindings_of(document, port)
        if bound:
            addresses.extend(bound)
    if not addresses:
        return False, [], f"port {port}/tcp is not published (nothing to verify)"
    offending = sorted({a for a in addresses if not is_loopback_host(a)})
    if offending:
        shown = ", ".join(repr(a) if a else "'' (all interfaces)" for a in offending)
        return False, addresses, f"port {port}/tcp is published on a non-loopback address: {shown}"
    return True, addresses, f"port {port}/tcp is published on loopback only: {', '.join(sorted(set(addresses)))}"


def read_ports(container: str) -> list[object]:
    """Docker's port fields for one container; raises RuntimeError when Docker cannot answer."""
    documents: list[object] = []
    for template in PORT_TEMPLATES:
        done = subprocess.run(["docker", "inspect", container, "--format", template],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=60)
        if done.returncode != 0:
            raise RuntimeError(f"docker could not report the ports of {container}")
        try:
            documents.append(json.loads(done.stdout.strip() or "null"))
        except ValueError as exc:
            raise RuntimeError(f"docker returned unreadable port data for {container}") from exc
    return documents


def signed_in_required(probe_url: str, wait_seconds: float = 60.0) -> bool:
    """True when the app answers the unauthenticated probe with 401: sign-in is on. Anything else, or no answer, is False."""
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            with urllib.request.urlopen(probe_url, timeout=3) as response:
                return response.status == 401
        except urllib.error.HTTPError as error:
            return error.code == 401
        except (urllib.error.URLError, OSError):
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(1)


def stop(container: str) -> str:
    """Stop the container; returns "" on success, else why it did not stop."""
    try:
        done = subprocess.run(["docker", "stop", container], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", check=False, timeout=120)
    except subprocess.TimeoutExpired:
        return "docker stop timed out"
    except OSError as exc:
        return f"docker could not be run ({exc.__class__.__name__})"
    return "" if done.returncode == 0 else f"docker stop exited {done.returncode}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--container", required=True, help="container name or id of the app")
    parser.add_argument("--port", type=int, default=8000, help="the app's container port (default 8000)")
    parser.add_argument("--lan-opt-in", action="store_true",
                        help="the operator set ORENA_INSECURE_DEV_LAN_BIND_HOST: allow non-loopback only if sign-in is on")
    parser.add_argument("--probe-url", default="", help="with --lan-opt-in: an unauthenticated URL that answers 401 when sign-in is on")
    parser.add_argument("--no-stop", action="store_true", help="read-only: report and exit non-zero, never stop the container")
    args = parser.parse_args(argv)

    try:
        ok, addresses, reason = evaluate(read_ports(args.container), args.port)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        ok, addresses, reason = False, [], str(exc)
        code = 3
    else:
        code = 2

    if not ok and code == 2 and addresses and args.lan_opt_in:
        if args.probe_url and signed_in_required(args.probe_url):
            print(f"published-address check: {args.container}: {reason}; allowed by the explicit LAN opt-in "
                  "because the app answers signed-in only (401).")
            return 0
        reason += "; the LAN opt-in needs Google sign-in on and the app did not answer 401"

    if ok:
        print(f"published-address check: {args.container}: {reason}")
        return 0
    print(f"REFUSED: container {args.container}: {reason}. An official launcher publishes the app on loopback only "
          "(docs/SECURITY_BOUNDARY.md).", file=sys.stderr)
    if not args.no_stop:
        failed = stop(args.container)
        if failed:
            print(f"STOP FAILED for container {args.container}: {failed}. It may still be publishing on a "
                  "non-loopback address; stop it by hand.", file=sys.stderr)
            return 4
        print(f"Stopped container {args.container}.", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
