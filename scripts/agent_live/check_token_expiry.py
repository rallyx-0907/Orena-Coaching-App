#!/usr/bin/env python3
"""ONE bounded live check: does Gemini Live close an already-open socket when the ephemeral token's `expireTime` passes?

This is the precondition of the chunked voice tokens (D-16T): each token is minted for a short chunk, and the server relies
on the vendor ending the socket when the token dies. It is a PAID call (Gemini Live) - the human runs it, under the
live-provider lock `%USERPROFILE%\\.orena\\live-gemini-live.lock`. Nothing here takes or releases that lock.

What it does (standard library only, no `websockets` needed):
  1. POST <base>/api/agent/voice/session on the QA app (:8021, voice on, orena.message enforced so a token lives one
     chunk, normally 120 s). It REFUSES to open the socket when the token lives longer than --max-token (default 150 s):
     a longer wait would be a longer paid session. Run it with a learner whose day still has messages.
  2. Opens the Gemini Live socket with the token, sends the locked setup, waits for `setupComplete`.
  3. Sends ONE short text turn ("Reply with one word."), so the session has been active, then stays silent (no audio in).
     When the app enforces orena.message, the token's locked setup carries `sessionResumption: {}`, so reaching
     `setupComplete` is also the connect-time check that the vendor accepts that field in an ephemeral token. The socket
     reports resumption handles (`sessionResumptionUpdate.newHandle`).
  3b. About `renew_in` seconds in (and at least 15 s after opening, at least 20 s before expiry) it asks
     `POST /api/agent/voice/extend` for chunk 1 CARRYING the latest handle, connects to that second token, waits for
     `setupComplete`, and closes it at once (no conversation). This charges the QA learner one more chunk (2 messages) and
     checks the renewal-with-a-handle connect. `--no-renewal` skips it.
  4. Reads frames until the vendor closes the socket, or until the token's `expires_at` + --grace seconds (default 30),
     then closes it itself.
  5. POST /api/agent/voice/end, and prints one JSON line:
       {"token_life_s", "closed_by": "vendor" | "check", "closed_after_s", "after_expiry_s", "close_code",
        "close_reason", "goaway_s", "verdict": ...}
     verdict "vendor_enforces_expiry"  = the vendor closed the socket within --grace of expires_at (the scheme holds);
     verdict "vendor_closed_early"     = it closed well before expires_at (inactivity or a session limit: read the reason);
     verdict "NOT_ENFORCED"            = the socket was still open --grace seconds after expires_at (do NOT go live with
                                         per-chunk tokens alone: only a server-proxied socket can bound usage).
     Also in the JSON: first_socket.connect_ok (accepted with sessionResumption in the setup), renewal_with_handle
     {extend_status, handle_sent, connect_ok, close_code, close_reason, handles_seen} (the handle on a reconnect).
     Exit code 0 only when the vendor enforces expiry AND the renewal connected.

Usage:
    python check_token_expiry.py --base http://127.0.0.1:8021 [--cookie "session=..."] [--learning en] [--max-token 150]

Cost: one text turn and a few seconds of one short answer, one more connect, then silence: well under a cent. Upper bound if the vendor
never closes it: token life + grace (about 150 s) of an idle session.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import ssl
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime


def call(base: str, path: str, body: dict, cookie: str) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json", "X-Orena-Timezone": "UTC"}
    if cookie:
        headers["Cookie"] = cookie
    request = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.loads(error.read() or b"{}")
        except ValueError:
            return error.code, {}


# --- a minimal WebSocket client (RFC 6455), enough for one Gemini Live socket -------------------------------------

def ws_open(url: str) -> ssl.SSLSocket:
    parts = urllib.parse.urlsplit(url)
    host, port = parts.hostname, parts.port or 443
    path = parts.path + ("?" + parts.query if parts.query else "")
    raw = socket.create_connection((host, port), timeout=15)
    tls = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
    key = base64.b64encode(os.urandom(16)).decode()
    tls.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                 f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    head = b""
    while b"\r\n\r\n" not in head:
        chunk = tls.recv(4096)
        if not chunk:
            raise RuntimeError("closed during the handshake")
        head += chunk
    if b" 101 " not in head.split(b"\r\n", 1)[0]:
        raise RuntimeError("handshake refused: " + head.split(b"\r\n", 1)[0].decode("latin-1"))
    tls.settimeout(None)
    tls._leftover = head.split(b"\r\n\r\n", 1)[1]  # type: ignore[attr-defined]
    return tls


def _read(tls: ssl.SSLSocket, count: int, deadline: float) -> bytes:
    data = getattr(tls, "_leftover", b"")
    out = data[:count]
    tls._leftover = data[count:]  # type: ignore[attr-defined]
    while len(out) < count:
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError
        tls.settimeout(left)
        chunk = tls.recv(count - len(out))
        if not chunk:
            raise ConnectionError("closed")
        out += chunk
    return out


def ws_send_text(tls: ssl.SSLSocket, text: str) -> None:
    payload = text.encode()
    mask = os.urandom(4)
    header = bytes([0x81])
    if len(payload) < 126:
        header += bytes([0x80 | len(payload)])
    elif len(payload) < 65536:
        header += bytes([0x80 | 126]) + struct.pack(">H", len(payload))
    else:
        header += bytes([0x80 | 127]) + struct.pack(">Q", len(payload))
    tls.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))


def ws_recv(tls: ssl.SSLSocket, deadline: float):
    """(opcode, payload) of the next data or close frame; pings are answered. Raises TimeoutError at the deadline."""
    while True:
        first, second = _read(tls, 2, deadline)
        opcode, length = first & 0x0F, second & 0x7F
        if length == 126:
            length = struct.unpack(">H", _read(tls, 2, deadline))[0]
        elif length == 127:
            length = struct.unpack(">Q", _read(tls, 8, deadline))[0]
        payload = _read(tls, length, deadline) if length else b""
        if opcode == 0x9:  # ping -> pong
            tls.sendall(bytes([0x8A, 0x80 | len(payload)]) + b"\x00\x00\x00\x00" + payload[:125])
            continue
        if opcode == 0xA:
            continue
        return opcode, payload


def watch(connect: dict, expiry_mono: float, grace: int, out: dict, handles: list, start: float) -> None:
    """Socket 1: open, set up, one short text turn, then silence until the vendor closes it or expiry + grace."""
    deadline = expiry_mono + grace
    goaway = None
    closed_by, code, reason = "check", None, ""
    tls = None
    try:
        tls = ws_open(f"{connect['url']}?access_token={urllib.parse.quote(connect['ephemeral_token'], safe='')}")
        ws_send_text(tls, json.dumps(connect["setup"]))
        setup_deadline = time.monotonic() + 15
        ready = False
        while True:
            try:
                opcode, payload = ws_recv(tls, setup_deadline if not ready else deadline)
            except TimeoutError:
                break
            except (ConnectionError, OSError):
                closed_by = "vendor"
                break
            if opcode == 0x8:
                closed_by = "vendor"
                code = struct.unpack(">H", payload[:2])[0] if len(payload) >= 2 else None
                reason = payload[2:].decode("utf-8", "replace")[:300]
                break
            try:
                message = json.loads(payload)
            except ValueError:
                continue
            if "setupComplete" in message and not ready:
                ready = True
                out["connect_ok"] = True
                out["setup_complete_s"] = round(time.monotonic() - start, 1)
                ws_send_text(tls, json.dumps({"clientContent": {"turns": [{"role": "user", "parts": [
                    {"text": "Reply with one word."}]}], "turnComplete": True}}))
            update = message.get("sessionResumptionUpdate")
            if update and update.get("newHandle"):
                handles.append(update["newHandle"])
            if "goAway" in message and goaway is None:
                goaway = round(time.monotonic() - start, 1)
                out["goaway_time_left"] = message["goAway"].get("timeLeft")
        out.setdefault("connect_ok", False)
    except Exception as error:  # report, never hide
        out["error"] = f"{type(error).__name__}: {str(error)[:200]}"
    finally:
        if tls is not None:
            try:
                tls.close()
            except OSError:
                pass
    ended = time.monotonic() - start
    out.update(closed_by=closed_by, closed_after_s=round(ended, 1), after_expiry_s=round(ended - (expiry_mono - start), 1),
               close_code=code, close_reason=reason, goaway_s=goaway)


def renew_with_handle(base: str, cookie: str, sid: str, handle: str | None) -> dict:
    """The one renewal: ask for chunk 1 carrying the handle the first socket reported, connect to its token, wait for
    setupComplete, then close at once (no text turn: no billable conversation)."""
    body = {"voice_session_id": sid, "chunk": 1}
    if handle:
        body["resumption"] = handle
    status, answer = call(base, "/api/agent/voice/extend", body, cookie)
    report: dict = {"extend_status": status, "handle_sent": bool(handle)}
    if status != 200:
        report["detail"] = answer.get("detail")
        return report
    connect = answer["connect"]
    report["token_life_s"] = answer.get("max_seconds")
    tls = None
    try:
        tls = ws_open(f"{connect['url']}?access_token={urllib.parse.quote(connect['ephemeral_token'], safe='')}")
        ws_send_text(tls, json.dumps(connect["setup"]))
        deadline = time.monotonic() + 15
        report["connect_ok"] = False
        while True:
            opcode, payload = ws_recv(tls, deadline)
            if opcode == 0x8:
                report["close_code"] = struct.unpack(">H", payload[:2])[0] if len(payload) >= 2 else None
                report["close_reason"] = payload[2:].decode("utf-8", "replace")[:300]
                break
            try:
                if "setupComplete" in json.loads(payload):
                    report["connect_ok"] = True
                    break
            except ValueError:
                continue
    except TimeoutError:
        report["error"] = "no setupComplete within 15 s"
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {str(error)[:200]}"
    finally:
        if tls is not None:
            try:
                tls.close()
            except OSError:
                pass
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="http://127.0.0.1:8021")
    parser.add_argument("--cookie", default="", help='the QA session cookie, e.g. "orena_session=..." (if the app needs one)')
    parser.add_argument("--learning", default="en", choices=("en", "zh"))
    parser.add_argument("--max-token", type=int, default=150, help="refuse to open the socket for a longer token (seconds)")
    parser.add_argument("--grace", type=int, default=30, help="how long past expires_at to wait for the vendor to close")
    parser.add_argument("--no-renewal", action="store_true", help="skip the renewal-with-a-handle check")
    args = parser.parse_args()

    target = {"en": "en", "zh": "zh-CN"}[args.learning]
    body = {"contract_version": 8, "client": {"ui_version": "token-expiry-check", "supported_actions": ["navigate"],
                                              "supported_intents": ["home", "orena.home"]},
            "context": {"surface": "orena.home", "activity_type": "reading",
                        "locale": {"interface": "en", "support": "en", "target": target, "content": target}}}
    status, opened = call(args.base, "/api/agent/voice/session", body, args.cookie)
    if status != 200:
        print(json.dumps({"verdict": "no_session", "status": status, "detail": opened.get("detail")}))
        return 2
    sid, connect = opened["voice_session_id"], opened["connect"]
    life = int(opened["max_seconds"])
    result: dict = {"token_life_s": life, "chunk": opened.get("chunk"), "expires_at": connect["expires_at"],
                    "renewable": opened.get("renew_in") is not None}
    if life > args.max_token:
        call(args.base, "/api/agent/voice/end", {"voice_session_id": sid}, args.cookie)
        result["verdict"] = "refused_token_too_long"
        result["note"] = f"the token lives {life} s > --max-token {args.max_token}; no socket was opened (only a token was minted)"
        print(json.dumps(result))
        return 3
    expires = datetime.fromisoformat(connect["expires_at"].replace("Z", "+00:00")).astimezone(UTC).timestamp()
    start = time.monotonic()
    expiry_mono = start + (expires - time.time())
    first: dict = {}
    handles: list = []
    reader = threading.Thread(target=watch, args=(connect, expiry_mono, args.grace, first, handles, start), daemon=True)
    reader.start()
    renewal = None
    if not args.no_renewal and result["renewable"]:
        # When the client would renew, but not before the first socket is up and has said something (a handle).
        time.sleep(max(15.0, min(float(opened["renew_in"]), life - 20.0)))
        renewal = renew_with_handle(args.base, args.cookie, sid, handles[-1] if handles else None)
        renewal["handles_seen"] = len(handles)
    reader.join(timeout=life + args.grace + 30)
    result["first_socket"] = first
    if renewal is not None:
        result["renewal_with_handle"] = renewal
    # A metered session's token locks `sessionResumption` into its setup: a socket that reached setupComplete on such a
    # token shows the vendor accepts the field at connect time.
    result["resumption_in_setup"] = result["renewable"]
    if first.get("closed_by") == "check":
        result["verdict"] = "NOT_ENFORCED" if first.get("connect_ok") and "error" not in first else "inconclusive"
    elif first.get("closed_after_s", 0.0) < life - 5:
        result["verdict"] = "vendor_closed_early"
    else:
        result["verdict"] = "vendor_enforces_expiry"
    result["after_expiry_s"] = first.get("after_expiry_s")
    call(args.base, "/api/agent/voice/end", {"voice_session_id": sid}, args.cookie)
    print(json.dumps(result))
    renewed_ok = renewal is None or bool(renewal.get("connect_ok"))
    return 0 if result["verdict"] == "vendor_enforces_expiry" and renewed_ok else 1


if __name__ == "__main__":
    sys.exit(main())
