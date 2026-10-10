"""Gemini Live one-use tokens for Orena's voice (agent/voice_session.py; R28, mode A).

The network side of a voice session, kept in the AI layer like every provider adapter: the agent package never
opens a socket or reads a key. A token is minted with the session's whole setup locked in (model, voice,
instruction, tools - `bidiGenerateContentSetup`), so the client that opens the Live socket with it cannot change
any of it (verified live 2026-10-06). The key is sent in a header, never in a URL, and no answer body is ever
repeated in an error: it may echo what was sent.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

TOKEN_URL = "https://generativelanguage.googleapis.com/v1alpha/auth_tokens"
LIVE_SOCKET = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained"
)
OPEN_WITHIN_SECONDS = 60  # the token must open its one session within this


class VoiceUnavailable(RuntimeError):
    """The voice provider could not open a session (no key, or the token was refused)."""


Post = Callable[[str, Mapping[str, str], bytes], tuple[int, bytes]]


def _post(url: str, headers: Mapping[str, str], body: bytes) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, method="POST", headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read() or b""
    except (urllib.error.URLError, OSError):
        return 502, b""


@dataclass(frozen=True)
class GeminiLiveTokens:
    """Mints a one-use Gemini Live token with the setup locked in (the key stays in this process)."""

    key: Callable[[], str]
    post: Post = _post
    socket_url: str = LIVE_SOCKET

    def mint(self, setup: Mapping[str, Any], *, now: datetime, seconds: int) -> tuple[str, str]:
        """`seconds` is the token's whole life (`expireTime`): the session's cap, whatever the learner's allowance
        buys (agent/voice_session.py). Whether the vendor also closes a socket that is already open when it passes
        has not been verified live; the client ends the session at the cap and the server settles what was reserved."""
        key = self.key()
        if not key:
            raise VoiceUnavailable("no Gemini key is configured")
        iso = "%Y-%m-%dT%H:%M:%SZ"
        expires = (now + timedelta(seconds=seconds)).strftime(iso)
        body = {
            "uses": 1,
            "expireTime": expires,
            # The token is spent at `expireTime` whether or not it opened: a session cut short by the learner's
            # remaining allowance (D-169) must still be opened within its own life.
            "newSessionExpireTime": (now + timedelta(seconds=min(OPEN_WITHIN_SECONDS, seconds))).strftime(iso),
            "bidiGenerateContentSetup": dict(setup),
        }
        status, raw = self.post(TOKEN_URL, {"x-goog-api-key": key, "Content-Type": "application/json"},
                                json.dumps(body).encode())  # fmt: skip
        if status != 200:
            raise VoiceUnavailable(f"the voice token was refused ({status})")
        try:
            name = json.loads(raw or b"{}").get("name")
        except ValueError:
            name = None
        if not isinstance(name, str) or not name:
            raise VoiceUnavailable("the voice token answer had no token")
        return name, expires
