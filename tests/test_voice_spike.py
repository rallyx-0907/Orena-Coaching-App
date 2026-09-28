"""Track 0 voice spike server (scripts/voice_spike/server.py): the key never leaves the process."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("voice_spike_server", ROOT / "scripts/voice_spike/server.py")
server = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("voice_spike_server", server)
_SPEC.loader.exec_module(server)

KEY = "AIza-test-key-not-real"


class Answer(io.BytesIO):
    def __init__(self, body: dict, status: int = 200) -> None:
        super().__init__(json.dumps(body).encode())
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def recording(body: dict, status: int = 200):
    seen = []

    def opener(request, timeout=None):
        seen.append(request)
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "err", {}, io.BytesIO(json.dumps(body).encode()))
        return Answer(body, status)

    return opener, seen


def test_the_key_goes_in_a_header_never_the_url_or_the_answer():
    opener, seen = recording({"name": "auth_tokens/abc"})
    status, answer = server.ephemeral_token(KEY, now=datetime(2026, 9, 28, 8, 0, tzinfo=UTC), opener=opener)
    request = seen[0]
    assert status == 200 and answer == {"token": "auth_tokens/abc", "expires_at": "2026-09-28T08:30:00Z"}
    assert request.full_url == "https://generativelanguage.googleapis.com/v1beta/auth_tokens"
    assert request.get_header("X-goog-api-key") == KEY and KEY not in request.full_url
    body = json.loads(request.data)
    assert body == {"uses": 1, "expireTime": "2026-09-28T08:30:00Z", "newSessionExpireTime": "2026-09-28T08:01:00Z"}
    assert KEY not in json.dumps(answer)


def test_a_provider_error_never_echoes_the_key():
    opener, _ = recording({"error": {"message": f"API key {KEY} not valid"}}, status=400)
    status, answer = server.ephemeral_token(KEY, opener=opener)
    assert status == 400 and KEY not in json.dumps(answer) and "<key>" in answer["error"]


def test_only_live_models_are_listed():
    opener, _ = recording({"models": [
        {"name": "models/gemini-3.8-live", "supportedGenerationMethods": ["bidiGenerateContent"]},
        {"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-2.5-flash-native-audio-preview-12-2025", "supportedGenerationMethods": ["bidiGenerateContent", "countTokens"]},
    ]})  # fmt: skip
    assert server.live_models(KEY, opener=opener) == (
        200, {"models": ["gemini-2.5-flash-native-audio-preview-12-2025", "gemini-3.8-live"]}
    )


def test_only_the_api_key_is_read_from_the_env_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text("OTHER=1\nGEMINI_API_KEY='abc'\nGEMINI_MODELS=x\n", encoding="utf-8")
    assert server.read_key(str(env)) == "abc"


def test_the_page_never_holds_the_key_and_opens_the_constrained_endpoint():
    page = "".join((ROOT / "scripts/voice_spike" / name).read_text(encoding="utf-8") for name in ("index.html", "app.js"))
    assert "?access_token=" in page  # the one-use token, not the key
    assert "BidiGenerateContentConstrained" in page and "x-goog-api-key" not in page and "key=" not in page
