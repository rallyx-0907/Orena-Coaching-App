"""D-204: media import never looks a word up over the network; English reading is local CMUdict, empty on a miss."""
import socket
from dataclasses import replace

from tests.test_media_lifecycle import _entry
from writing_coach.languages.english.ipa import ipa_for
from writing_coach.media_segmentation import Cue
from writing_coach.media_transcript_pipeline import build_transcript, lesson_payload


def _forbid_network(monkeypatch):
    import app as runtime
    import requests

    attempts = []

    def refuse(*args, **kwargs):
        attempts.append(args[:1])
        raise AssertionError("media import must not make a network call")

    monkeypatch.setattr(requests, "get", refuse)
    monkeypatch.setattr(requests.sessions.Session, "request", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(runtime, "lookup_dictionary", refuse)
    monkeypatch.setattr(runtime, "dictionary_ai_fallback", refuse)
    return runtime, attempts


def test_import_wires_the_local_reading_not_the_dictionary():
    import app as runtime

    assert runtime._media_pipeline._english_reading is ipa_for


def test_lesson_payload_for_a_long_transcript_makes_zero_network_calls(monkeypatch):
    runtime, attempts = _forbid_network(monkeypatch)
    entry = replace(_entry(), language="en")
    # Many distinct words, including ones CMUdict does not hold: each would have been a network call before.
    words = [f"word{i}x" for i in range(300)] + ["hello", "infrastructure", "qzxvbn"]
    cues = [Cue(i * 1000, i * 1000 + 900, " ".join(words[i * 10:(i + 1) * 10])) for i in range(31)]
    transcript = build_transcript(entry.media_id, "en", cues)
    payload = lesson_payload(entry, transcript, "fixture", 40000, english_reading=runtime._media_pipeline._english_reading)
    assert attempts == []
    readings = [item for items in payload["catalog"]["readings_by_segment"].values() for item in items]
    by_text = {item["text"]: item["reading"] for item in readings}
    assert by_text["hello"] == ipa_for("hello") and by_text["hello"]
    assert by_text["infrastructure"] == ipa_for("infrastructure")
    assert "qzxvbn" not in by_text  # a miss is empty and the word carries no reading


def test_learner_tap_lookup_still_uses_the_dictionary(monkeypatch):
    import app as runtime

    seen = []

    class _Response:
        ok = False
        status_code = 404

    monkeypatch.setattr(runtime._learning_cache, "get_dictionary", lambda _w: None)
    monkeypatch.setattr(runtime.requests, "get", lambda url, **_k: seen.append(url) or _Response())
    runtime.lookup_dictionary("hello", language="en", allow_ai=False, persist=False)
    assert seen and "dictionaryapi.dev" in seen[0]
