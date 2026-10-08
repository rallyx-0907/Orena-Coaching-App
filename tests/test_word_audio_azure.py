"""Azure neural speech for a word nobody recorded (LEX-010): the reading it is told, the cap, the ledger, the cache.

No network: every test hands the voice a fake transport."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from writing_coach import word_audio_api
from writing_coach.book_asset_store import FilesystemBookAssetStore
from writing_coach.word_audio import WordAudioLibrary
from writing_coach.word_audio_azure import (
    CAPABILITY,
    PER_MILLION_CHARACTERS,
    AzureVoice,
    billed_characters,
    sapi_pinyin,
    ssml_for,
)

MP3 = b"ID3fake-mp3-bytes"


@pytest.mark.parametrize(("reading", "sapi"), [
    ("háng", "hang 2"), ("xíng", "xing 2"),
    ("cháng", "chang 2"), ("zhǎng", "zhang 3"),
    ("le", "le 5"), ("liǎo", "liao 3"),
    ("hái", "hai 2"), ("huán", "huan 2"),
    ("de", "de 5"), ("dé", "de 2"), ("děi", "dei 3"),
    ("huā shēng", "hua 1 sheng 1"), ("lǜ", "lv 4"), ("hua1 sheng1", "hua 1 sheng 1"),
])  # fmt: skip
def test_tone_marked_pinyin_becomes_numbered_pinyin(reading, sapi):
    assert sapi_pinyin(reading) == sapi


@pytest.mark.parametrize(("term", "reading", "ph"), [
    ("行", "háng", "hang 2"), ("行", "xíng", "xing 2"), ("长", "cháng", "chang 2"), ("长", "zhǎng", "zhang 3"),
    ("了", "le", "le 5"), ("了", "liǎo", "liao 3"), ("还", "hái", "hai 2"), ("还", "huán", "huan 2"),
    ("得", "de", "de 5"), ("得", "dé", "de 2"), ("得", "děi", "dei 3"),
])  # fmt: skip
def test_a_chinese_word_is_spoken_at_the_reading_it_means(term, reading, ph):
    ssml = ssml_for(term, "zh", reading)
    assert f'<phoneme alphabet="sapi" ph="{ph}">{term}</phoneme>' in ssml
    assert 'xml:lang="zh-CN"' in ssml and "zh-CN-XiaoxiaoNeural" in ssml


def test_a_reading_that_does_not_match_the_characters_is_not_guessed():
    assert ssml_for("花生", "zh", "huā") is None
    assert ssml_for("行", "zh", "h@ng") is None


def test_markup_in_a_term_is_escaped():
    assert "&lt;b&gt;" in ssml_for("<b>", "en", "")


def test_chinese_characters_are_billed_double():
    assert billed_characters("花生") == 4 and billed_characters("word") == 4


class Wire:
    def __init__(self, *, fail=False, audio=MP3):
        self.calls = []
        self.fail = fail
        self.audio = audio

    def __call__(self, url, body, headers):
        self.calls.append((url, body.decode("utf-8"), headers))
        if self.fail:
            raise OSError("offline")
        return self.audio


def voice(*, wire=None, spent=0.0, cap=5.0, records=None):
    return AzureVoice(key="test-key", region="eastasia", post=wire or Wire(), spent=lambda: spent,
                      record=(records.append if records is not None else (lambda event: None)), cap_usd=cap)  # fmt: skip


def test_a_word_is_synthesised_and_its_cost_recorded():
    wire, records = Wire(), []
    spoken = voice(wire=wire, records=records).speak(term="花生", language="zh", reading="huā shēng", single_reading=False)
    assert spoken.audio == MP3 and spoken.media_type == "audio/mpeg" and spoken.source == "azure-tts"
    assert spoken.licence == "generated" and "generated" in spoken.attribution.lower()
    url, ssml, headers = wire.calls[0]
    assert url == "https://eastasia.tts.speech.microsoft.com/cognitiveservices/v1"
    assert 'ph="hua 1 sheng 1"' in ssml and headers["Content-Type"] == "application/ssml+xml"
    event = records[0]
    assert event["capability"] == CAPABILITY and event["outcome"] == "success" and event["provider"] == "azure-speech"
    assert event["cost"]["amount"] == pytest.approx(4 * PER_MILLION_CHARACTERS / 1_000_000)


def test_at_the_spend_cap_nothing_is_asked_and_the_failure_is_said():
    wire = Wire()
    azure = voice(wire=wire, spent=5.0, cap=5.0)
    assert azure.speak(term="花生", language="zh", reading="huā shēng", single_reading=True) is None
    assert wire.calls == [] and azure.last_failed is True


def test_an_unreadable_ledger_is_a_closed_cap():
    def broken():
        raise NotImplementedError("no ledger")

    azure = AzureVoice(key="k", region="eastasia", post=Wire(), spent=broken, record=lambda e: None, cap_usd=5)
    assert azure.speak(term="花生", language="zh", reading="huā shēng", single_reading=True) is None
    assert azure.last_failed is True


def test_a_provider_failure_is_recorded_unpriced_and_said():
    records = []
    azure = voice(wire=Wire(fail=True), records=records)
    assert azure.speak(term="花生", language="zh", reading="huā shēng", single_reading=True) is None
    assert azure.last_failed is True
    assert records[0]["outcome"] == "provider_error" and records[0]["cost"]["amount"] is None


def test_an_english_word_with_several_readings_is_not_guessed():
    wire = Wire()
    assert voice(wire=wire).speak(term="read", language="en", reading="ɹiːd", single_reading=False) is None
    assert wire.calls == []


def test_unconfigured_it_says_nothing_and_is_not_a_failure():
    azure = AzureVoice(key="", region="", post=Wire(), spent=lambda: 0.0, record=lambda e: None)
    assert azure.speak(term="花生", language="zh", reading="huā shēng", single_reading=True) is None
    assert azure.last_failed is False


def test_the_library_keeps_a_synthesised_word_and_never_asks_again(tmp_path):
    wire = Wire()
    nobody = SimpleNamespace(name="commons", speak=lambda **kw: None)
    library = WordAudioLibrary(FilesystemBookAssetStore(tmp_path / "assets"), (nobody, voice(wire=wire)))
    first = library.pronounce(identity_key="zh:花生", term="花生", language="zh", reading="huā shēng", single_reading=True)
    again = library.pronounce(identity_key="zh:花生", term="花生", language="zh", reading="huā shēng", single_reading=True)
    assert first.key == again.key and first.key.endswith(".mp3") and first.source == "azure-tts"
    assert len(wire.calls) == 1


def test_the_route_says_synthesis_unavailable_when_azure_failed(monkeypatch, tmp_path):
    azure = voice(wire=Wire(fail=True))
    nobody = SimpleNamespace(name="commons", speak=lambda **kw: None)
    library = WordAudioLibrary(FilesystemBookAssetStore(tmp_path / "assets"), (nobody, azure))
    monkeypatch.setattr(word_audio_api, "_shelf", lambda: library)
    monkeypatch.setattr(word_audio_api, "catalog_readings", lambda word: ["huā shēng"])
    monkeypatch.setattr(word_audio_api, "entry_identity_for", lambda *a: {"entry_identity_key": "zh:花生", "reading_key": "huā shēng"})
    monkeypatch.setattr(word_audio_api, "_language", lambda: "zh")
    assert word_audio_api.word_audio("花生", "huā shēng", False)["reason"] == "synthesis_unavailable"
