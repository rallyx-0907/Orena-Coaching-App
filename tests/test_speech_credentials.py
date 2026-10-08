"""A speech provider's key never travels in an error.

The Azure Speech key was once printed because a value read from a Windows ``.env`` ended in "\\r":
``requests`` refused the header and quoted its value in the exception. The adapters now refuse a
key that cannot be a header, by a message that never repeats it, and a transport failure is raised
with no cause or context attached, so a logged traceback has nothing to print.
"""
from __future__ import annotations

import traceback

import pytest
import requests

from writing_coach.speech_asr import GroqSpeechAsrProvider, SpeechAsrRequestFailed, SpeechAsrTimedOut

KEY = "gsk-secret-key-value"


class Leaky:
    """A transport that fails the way requests does on a bad header: quoting it."""

    def post(self, *_, headers=None, **__):
        raise requests.exceptions.InvalidHeader(f"Invalid header value {headers['Authorization']!r}")


def _printed(error: BaseException) -> str:
    return "".join(traceback.format_exception(error))


def test_groq_key_with_a_line_ending_is_sent_without_it():
    sent = {}

    class Capture:
        def post(self, *_, headers=None, **__):
            sent.update(headers)
            raise requests.Timeout()

    provider = GroqSpeechAsrProvider(KEY + "\r\n", session=Capture())  # type: ignore[arg-type]
    with pytest.raises(SpeechAsrTimedOut):
        provider.transcribe_bytes(b"webm", filename="t.webm", content_type="audio/webm", language="en")
    assert sent["Authorization"] == f"Bearer {KEY}"


@pytest.mark.parametrize("bad", ["gsk secret", "gsk\nsecret", "gsk\tsecret", "gsk-sécret"])
def test_groq_key_that_cannot_be_a_header_is_refused_without_echoing_it(bad):
    with pytest.raises(ValueError) as caught:
        GroqSpeechAsrProvider(bad)
    assert bad.strip() not in str(caught.value)


def test_groq_transport_error_does_not_carry_the_key_further():
    provider = GroqSpeechAsrProvider(KEY, session=Leaky())  # type: ignore[arg-type]
    with pytest.raises(SpeechAsrRequestFailed) as caught:
        provider.transcribe_bytes(b"webm", filename="t.webm", content_type="audio/webm", language="en")
    assert KEY not in _printed(caught.value)
    assert caught.value.__cause__ is None and caught.value.__context__ is None

    with pytest.raises(SpeechAsrRequestFailed) as caught:
        provider.transcribe_url("https://media.example.test/a.m4a", language="en")
    assert KEY not in _printed(caught.value)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
