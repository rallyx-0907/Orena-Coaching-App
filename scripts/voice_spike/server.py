"""Track 0 voice spike: a local page that talks to the Gemini Live API (human direction 2026-09-28).

A spike, apart from the agent: nothing here is imported by writing_coach. The
server serves the page and mints one-use ephemeral tokens; the API key stays in
this process - it is read from the named env file (GEMINI_API_KEY only), never
sent to the browser, never printed, never logged. The browser opens the Live
WebSocket with the token (BidiGenerateContentConstrained). Nothing is stored:
no audio, no transcript; the page can export its own measurements as JSON.

    python scripts/voice_spike/server.py --gemini-env <.env holding GEMINI_API_KEY>
    open http://127.0.0.1:8790

It holds the Gemini Live quota group's lock (live-gemini-live.lock, scripts/agent_live/lock.py) while it runs -
only that one: text runs do not wait for it. Stop it (Ctrl+C) when the session is done.
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "https://generativelanguage.googleapis.com/v1beta"
HOST, PORT = "127.0.0.1", 8790
STATIC = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/capture.js": ("capture.js", "text/javascript; charset=utf-8")}  # fmt: skip
TOKEN_MINUTES = 30  # messages may flow for this long
NEW_SESSION_SECONDS = 60  # the token must open its one session within this


def read_key(env_file: str | None) -> str:
    """GEMINI_API_KEY from the env file (nothing else is read from it), or this process's environment."""

    import os

    if env_file:
        for line in Path(env_file).read_text(encoding="utf-8").splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() == "GEMINI_API_KEY":
                return value.strip().strip("'\"")
        return ""
    return os.environ.get("GEMINI_API_KEY", "")


def _call(method: str, url: str, key: str, body: dict | None = None, opener=urllib.request.urlopen) -> tuple[int, dict]:
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method)
    request.add_header("x-goog-api-key", key)  # a header, never the URL: nothing of it can reach a log line
    request.add_header("Content-Type", "application/json")
    try:
        with opener(request, timeout=20) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read() or b"{}")
        except ValueError:
            detail = {}
        message = (detail.get("error") or {}).get("message") if isinstance(detail, dict) else None
        return error.code, {"error": _clean(str(message or error.reason), key)}
    except (urllib.error.URLError, OSError) as error:
        return 502, {"error": _clean(str(error), key)}


def _clean(text: str, key: str) -> str:
    return text.replace(key, "<key>") if key else text


def live_models(key: str, opener=urllib.request.urlopen) -> tuple[int, dict]:
    """The models this key may open a Live session with (supportedGenerationMethods has bidiGenerateContent)."""

    status, body = _call("GET", f"{API}/models?pageSize=1000", key, opener=opener)
    if status != 200:
        return status, body
    names = [
        m["name"].removeprefix("models/")
        for m in body.get("models", [])
        if "bidiGenerateContent" in (m.get("supportedGenerationMethods") or [])
    ]
    return 200, {"models": sorted(names)}


def ephemeral_token(key: str, now: datetime | None = None, opener=urllib.request.urlopen) -> tuple[int, dict]:
    """One use, a minute to open the session, thirty to talk (v1beta auth_tokens)."""

    now = now or datetime.now(UTC)
    body = {
        "uses": 1,
        "expireTime": (now + timedelta(minutes=TOKEN_MINUTES)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "newSessionExpireTime": (now + timedelta(seconds=NEW_SESSION_SECONDS)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    status, answer = _call("POST", f"{API}/auth_tokens", key, body, opener=opener)
    if status != 200:
        return status, answer
    return 200, {"token": answer.get("name"), "expires_at": body["expireTime"]}


def handler_for(key: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # noqa: ANN001 - only method and path; never a token or a body
            sys.stderr.write(f"{self.command} {self.path.split('?')[0]}\n")

        def _send(self, status: int, body: bytes, kind: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, body: dict) -> None:
            self._send(status, json.dumps(body, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802 - http.server's name
            path = self.path.split("?")[0]
            if path in STATIC:
                name, kind = STATIC[path]
                self._send(200, (HERE / name).read_bytes(), kind)
            elif path == "/api/models":
                self._json(*live_models(key))
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path.split("?")[0] == "/api/token":
                self._json(*ephemeral_token(key))
            else:
                self._json(404, {"error": "not found"})

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gemini-env", help="a .env file to take GEMINI_API_KEY from (default: this environment)")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    key = read_key(args.gemini_env)
    if not key:
        print("no GEMINI_API_KEY found")
        return 1
    sys.path.insert(0, str(HERE.parent / "agent_live"))
    import lock as live_lock  # the quota-group locks lanes queue on before a real provider call

    try:
        held = live_lock.acquire("feature/orena-intelligence:voice-spike", 0.0, group="gemini-live").start_heartbeat()
    except live_lock.LockTimeout as error:
        print(f"stopping: {error}")
        return 3
    server = ThreadingHTTPServer((HOST, args.port), handler_for(key))
    print(f"voice spike on http://{HOST}:{args.port}  (Ctrl+C to stop and release the lock)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        held.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
