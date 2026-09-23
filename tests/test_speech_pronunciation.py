from __future__ import annotations

import base64
import json

import pytest

import requests

from writing_coach.speech_pronunciation import (
    DemoPronunciationProvider,
    SpeechPronunciationNoSpeech,
    SpeechPronunciationRequestFailed,
    SpeechPronunciationTimedOut,
    build_speech_pronunciation_provider,
    AzureSpeechPronunciationProvider,
    SpeechPronunciationMalformed,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


def make_provider(payload, *, enable_prosody=False):
    session = FakeSession(payload)
    provider = AzureSpeechPronunciationProvider(
        "secret",
        "eastus",
        enable_prosody=enable_prosody,
        session=session,
        normalizer=lambda data, **_: b"RIFFxxxxWAVE" + data,
    )
    return provider, session


def test_direct_rest_shape_and_en_us_prosody():
    payload = {
        "DisplayText": "Good morning.",
        "NBest": [{
            "Display": "Good morning.",
            "AccuracyScore": 91,
            "FluencyScore": 82,
            "CompletenessScore": 100,
            "PronScore": 90,
            "ProsodyScore": 78,
            "Words": [{
                "Word": "morning",
                "AccuracyScore": 58,
                "ErrorType": "Mispronunciation",
                "Phonemes": [{"Phoneme": "m", "AccuracyScore": 55}],
            }],
        }],
    }
    provider, session = make_provider(payload, enable_prosody=True)
    result = provider.assess_bytes(
        b"webm",
        filename="take.webm",
        content_type="audio/webm",
        language="en",
        reference_text="Good morning.",
    )
    assert result.locale == "en-US"
    assert result.pron_score == 90.0
    assert result.accuracy_score == 91.0
    assert result.words[0].error_type == "Mispronunciation"

    _, call = session.calls[0]
    assert call["params"] == {"language": "en-US", "format": "detailed"}
    assert call["headers"]["EnableProsodyAssessment"] == "True"
    config = json.loads(base64.b64decode(call["headers"]["Pronunciation-Assessment"]))
    assert config["ReferenceText"] == "Good morning."
    assert config["Granularity"] == "Phoneme"


def test_nested_shape_and_zh_locale():
    payload = {
        "DisplayText": "你好。",
        "NBest": [{
            "Display": "你好。",
            "PronunciationAssessment": {
                "AccuracyScore": 88,
                "FluencyScore": 79,
                "CompletenessScore": 100,
                "PronScore": 87,
            },
            "Words": [{
                "Word": "你好",
                "PronunciationAssessment": {
                    "AccuracyScore": 84,
                    "ErrorType": "None",
                },
                "Phonemes": [{
                    "Phoneme": "n",
                    "PronunciationAssessment": {"AccuracyScore": 81},
                }],
            }],
        }],
    }
    provider, session = make_provider(payload)
    result = provider.assess_bytes(
        b"webm",
        filename="take.webm",
        content_type="audio/webm",
        language="zh",
        reference_text="你好。",
    )
    assert result.locale == "zh-CN"
    assert result.pron_score == 87.0
    assert result.prosody_score is None
    assert result.words[0].accuracy_score == 84.0
    _, call = session.calls[0]
    assert "EnableProsodyAssessment" not in call["headers"]


def test_reference_is_bounded():
    provider, _ = make_provider({"NBest": [{"PronScore": 50}]})
    with pytest.raises(SpeechPronunciationMalformed):
        provider.assess_bytes(
            b"webm",
            filename="take.webm",
            content_type="audio/webm",
            language="en",
            reference_text="x" * 1201,
        )


def test_demo_provider_returns_explicit_synthetic_provenance():
    provider = DemoPronunciationProvider()
    result = provider.assess_bytes(
        b"fake-audio",
        filename="take.webm",
        content_type="audio/webm",
        language="en",
        reference_text="Good morning.",
    )
    assert result.provider == "demo-synthetic"
    assert result.score_kind == "synthetic_demo"
    assert all(word.error_type == "SyntheticDemo" for word in result.words)


def test_demo_provider_is_development_only_and_only_when_asked(monkeypatch):
    # D-066: no fake pronunciation result. The synthetic provider is no longer
    # what an unconfigured development runtime gets; it must be asked for.
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("PRONUNCIATION_PROVIDER", "demo")
    assert isinstance(build_speech_pronunciation_provider(), DemoPronunciationProvider)

    monkeypatch.setenv("APP_ENV", "production")
    assert build_speech_pronunciation_provider() is None


def test_unset_mode_uses_azure_when_credentials_exist_else_none(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("PRONUNCIATION_PROVIDER", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    assert build_speech_pronunciation_provider() is None

    monkeypatch.setenv("AZURE_SPEECH_KEY", "k")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "southeastasia")
    assert isinstance(build_speech_pronunciation_provider(), AzureSpeechPronunciationProvider)


def test_azure_prosody_is_off_by_default():
    payload = {
        "NBest": [{
            "Display": "Good morning.",
            "AccuracyScore": 91,
            "FluencyScore": 82,
            "CompletenessScore": 100,
            "PronScore": 90,
        }],
    }
    provider, session = make_provider(payload)
    result = provider.assess_bytes(
        b"webm",
        filename="take.webm",
        content_type="audio/webm",
        language="en",
        reference_text="Good morning.",
    )
    assert result.score_kind == "measured"
    _, call = session.calls[0]
    assert "EnableProsodyAssessment" not in call["headers"]
    config = json.loads(base64.b64decode(call["headers"]["Pronunciation-Assessment"]))
    assert "EnableProsodyAssessment" not in config


TICKS_PER_MS = 10_000


def test_zh_words_keep_timing_syllables_and_phonemes_without_a_tone_field():
    payload = {
        "RecognitionStatus": "Success",
        "NBest": [{
            "Display": "我们想要。",
            "PronunciationAssessment": {"AccuracyScore": 80, "FluencyScore": 70, "CompletenessScore": 100, "PronScore": 78},
            "Words": [
                {
                    "Word": "我们", "Offset": 5_000_000, "Duration": 4_000_000,
                    "PronunciationAssessment": {"AccuracyScore": 95, "ErrorType": "None"},
                    "Syllables": [
                        {"Syllable": "wo3", "PronunciationAssessment": {"AccuracyScore": 96}},
                        {"Syllable": "men5", "PronunciationAssessment": {"AccuracyScore": 94}},
                    ],
                    "Phonemes": [{"Phoneme": "w", "PronunciationAssessment": {"AccuracyScore": 97}}],
                },
                {
                    "Word": "想", "Offset": 9_500_000, "Duration": 3_000_000,
                    "PronunciationAssessment": {"AccuracyScore": 52, "ErrorType": "Mispronunciation"},
                    "Syllables": [{"Syllable": "xiang3", "PronunciationAssessment": {"AccuracyScore": 52}}],
                },
            ],
        }],
    }
    provider, _ = make_provider(payload)
    result = provider.assess_bytes(b"webm", filename="t.webm", content_type="audio/webm",
                                   language="zh", reference_text="我们想要。")
    first, second = result.words
    assert (first.offset_ms, first.duration_ms) == (500, 400)
    assert (second.offset_ms, second.duration_ms) == (950, 300)
    assert [s.syllable for s in first.syllables] == ["wo3", "men5"]
    assert first.syllables[0].accuracy_score == 96.0
    assert second.error_type == "Mispronunciation"
    # A syllable label is the reference reading; nothing here is a tone measurement.
    assert not any("tone" in field for field in type(first).__dataclass_fields__)


def test_an_omitted_word_is_kept_with_the_providers_flag_and_its_phonemes():
    payload = {
        "NBest": [{
            "PronScore": 70, "AccuracyScore": 72, "FluencyScore": 80, "CompletenessScore": 67,
            "Words": [
                {"Word": "two", "AccuracyScore": 98, "ErrorType": "None"},
                {"Word": "cats", "AccuracyScore": 61, "ErrorType": "None",
                 "Phonemes": [{"Phoneme": "k", "AccuracyScore": 95}, {"Phoneme": "ae", "AccuracyScore": 93},
                              {"Phoneme": "t", "AccuracyScore": 90}, {"Phoneme": "s", "AccuracyScore": 4}]},
                {"Word": "slept", "AccuracyScore": 0, "ErrorType": "Omission"},
            ],
        }],
    }
    provider, _ = make_provider(payload)
    result = provider.assess_bytes(b"webm", filename="t.webm", content_type="audio/webm",
                                   language="en", reference_text="Two cats slept.")
    cats = result.words[1]
    # The word reads whole and is not flagged, but the final /s/ scored 4: the
    # phoneme evidence survives normalization so nothing downstream can call
    # the word "said right" from its text alone.
    assert cats.error_type == "None"
    assert cats.phonemes[-1].phoneme == "s" and cats.phonemes[-1].accuracy_score == 4.0
    assert result.words[2].error_type == "Omission"
    assert result.words[2].offset_ms is None


@pytest.mark.parametrize("status", ["NoMatch", "InitialSilenceTimeout", "BabbleTimeout"])
def test_no_speech_is_its_own_outcome_not_a_provider_failure(status):
    provider, _ = make_provider({"RecognitionStatus": status})
    with pytest.raises(SpeechPronunciationNoSpeech):
        provider.assess_bytes(b"webm", filename="t.webm", content_type="audio/webm",
                              language="en", reference_text="Hello.")


def test_timeout_is_reported_as_timeout():
    class Slow:
        def post(self, *_, **__):
            raise requests.Timeout()

    provider = AzureSpeechPronunciationProvider("secret-key-value", "eastus", session=Slow(),
                                                normalizer=lambda data, **_: data)
    with pytest.raises(SpeechPronunciationTimedOut):
        provider.assess_bytes(b"webm", filename="t.webm", content_type="audio/webm",
                              language="en", reference_text="Hello.")


def test_a_rejected_key_never_appears_in_the_error():
    class Denied:
        def post(self, *_, **__):
            return FakeResponse({"error": {"message": "Access denied due to invalid subscription key."}}, 401)

    provider = AzureSpeechPronunciationProvider("secret-key-value", "eastus", session=Denied(),
                                                normalizer=lambda data, **_: data)
    with pytest.raises(SpeechPronunciationRequestFailed) as caught:
        provider.assess_bytes(b"webm", filename="t.webm", content_type="audio/webm",
                              language="en", reference_text="Hello.")
    assert caught.value.status_code == 401
    assert "secret-key-value" not in str(caught.value)
    assert "secret-key-value" not in repr(caught.value)


def test_a_take_where_every_reference_word_is_omitted_is_no_speech():
    # Measured on real Azure (2026-09-23): 0.8 s of silence comes back as Success with every word
    # Omission and completeness 0. That is "nothing was heard", not a score of 0.
    payload = {
        "RecognitionStatus": "Success",
        "DisplayText": ".",
        "NBest": [{
            "Display": ".",
            "AccuracyScore": 0, "FluencyScore": 0, "CompletenessScore": 0, "PronScore": 0,
            "Words": [
                {"Word": "anna", "AccuracyScore": 0, "ErrorType": "Omission"},
                {"Word": "pen", "AccuracyScore": 0, "ErrorType": "Omission"},
            ],
        }],
    }
    provider, _ = make_provider(payload)
    with pytest.raises(SpeechPronunciationNoSpeech):
        provider.assess_bytes(b"webm", filename="t.webm", content_type="audio/webm",
                              language="en", reference_text="Anna, pen.")


def test_a_take_with_one_word_said_is_still_a_measurement():
    payload = {
        "NBest": [{
            "PronScore": 20, "AccuracyScore": 30, "FluencyScore": 10, "CompletenessScore": 50,
            "Words": [
                {"Word": "anna", "AccuracyScore": 90, "ErrorType": "None"},
                {"Word": "pen", "AccuracyScore": 0, "ErrorType": "Omission"},
            ],
        }],
    }
    provider, _ = make_provider(payload)
    result = provider.assess_bytes(b"webm", filename="t.webm", content_type="audio/webm",
                                   language="en", reference_text="Anna, pen.")
    assert result.words[1].error_type == "Omission"
