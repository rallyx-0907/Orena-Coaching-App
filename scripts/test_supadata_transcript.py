"""Dependency-light smoke for Supadata transcript parsing."""
from __future__ import annotations

import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests = types.ModuleType("requests")
    class RequestException(Exception):
        pass
    class Timeout(RequestException):
        pass
    class Session:
        pass
    requests.RequestException = RequestException
    requests.Timeout = Timeout
    requests.Session = Session
    sys.modules["requests"] = requests

from writing_coach.media_providers.supadata import (
    SupadataTranscriptClient,
    SupadataTranscriptMalformed,
)


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


session = FakeSession([
    FakeResponse(200, {
        "lang": "en",
        "content": [
            {"text": "Hello world", "offset": 1200, "duration": 1800, "lang": "en"},
            {"text": "How are you?", "offset": 3000, "duration": 1400, "lang": "en"},
        ],
    })
])
client = SupadataTranscriptClient("test", session=session, max_wait_seconds=2)
result = client.fetch("https://www.youtube.com/watch?v=abcdefghijk", "en")
assert result is not None
assert [(x.offset_ms, x.duration_ms, x.text) for x in result.chunks] == [
    (1200, 1800, "Hello world"),
    (3000, 1400, "How are you?"),
]
# A YouTube URL is asked in native mode only, never `auto`/`generate` (D-244, amended 2026-10-20).
assert session.calls[0][1]["params"]["mode"] == "native"

wrong = FakeSession([
    FakeResponse(200, {
        "lang": "en",
        "content": [{"text": "Hello", "offset": 0, "duration": 1000, "lang": "en"}],
    })
])
try:
    SupadataTranscriptClient("test", session=wrong).fetch(
        "https://www.youtube.com/watch?v=abcdefghijk",
        "zh",
    )
except SupadataTranscriptMalformed:
    pass
else:
    raise AssertionError("Language mismatch must be rejected.")

print("Supadata transcript smoke: PASS")
