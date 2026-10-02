from types import SimpleNamespace

from writing_coach import word_audio_api


def test_encounter_audio_does_not_require_a_saved_catalog_entry(monkeypatch):
    monkeypatch.setattr(word_audio_api, "catalog_readings", lambda word: [])
    monkeypatch.setattr(word_audio_api, "entry_identity_for", lambda *args: {"entry_identity_key": "", "reading_key": ""})
    monkeypatch.setattr(word_audio_api, "_language", lambda: "zh")
    calls = []

    def pronounce(**args):
        calls.append(args)
        return SimpleNamespace(key="word-audio/fixture.ogg", as_dict=lambda: {"available": True})

    monkeypatch.setattr(word_audio_api, "_shelf", lambda: SimpleNamespace(pronounce=pronounce))
    result = word_audio_api.word_audio("好", "hǎo", True)
    assert result["available"] is True
    assert calls[0]["identity_key"].startswith("encounter-audio:")
    assert calls[0]["single_reading"] is False
    assert calls[0]["reading"] == "hǎo"


def test_chinese_encounter_audio_does_not_guess_a_missing_reading(monkeypatch):
    monkeypatch.setattr(word_audio_api, "catalog_readings", lambda word: [])
    monkeypatch.setattr(word_audio_api, "entry_identity_for", lambda *args: {"entry_identity_key": "", "reading_key": ""})
    monkeypatch.setattr(word_audio_api, "_language", lambda: "zh")
    result = word_audio_api.word_audio("行", "", True)
    assert result == {"available": False, "reason": "reading_ambiguous", "readings": []}


def test_catalog_audio_without_lookup_opt_in_stays_unavailable(monkeypatch):
    monkeypatch.setattr(word_audio_api, "catalog_readings", lambda word: [])
    monkeypatch.setattr(word_audio_api, "entry_identity_for", lambda *args: {"entry_identity_key": "", "reading_key": ""})
    assert word_audio_api.word_audio("unknown", "", False)["reason"] == "no_entry"
