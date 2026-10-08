"""Source preparation belongs to admission, never a lesson read."""
from dataclasses import replace

import pytest

from tests.test_media_lifecycle import _entry
from tests.test_media_meaning_cache import MemoryCache
from writing_coach import listening_api
from writing_coach import media_library_api
from writing_coach.media_segmentation import Cue
from writing_coach.media_transcript_pipeline import build_transcript, lesson_payload


def test_saved_source_resolution_is_read_only_and_owner_scoped(monkeypatch):
    from fastapi import HTTPException
    from types import SimpleNamespace
    from writing_coach.media_library_store import OWNER_FIELD, owner_token

    entry = replace(_entry(), library="personal", provider="youtube", provider_media_id="NkYwdZhkHF0",
                    canonical_url="https://www.youtube.com/watch?v=NkYwdZhkHF0",
                    source={OWNER_FIELD: owner_token("owner")}, processing={"state": "ready"})
    monkeypatch.setattr(media_library_api, "_installed", lambda: (SimpleNamespace(list=lambda **_: [entry]), None, None))
    monkeypatch.setattr(media_library_api, "current_language_code", lambda: "en")
    monkeypatch.setattr(media_library_api, "current_user_key", lambda: "owner")
    monkeypatch.setattr(media_library_api, "_learner_payload", lambda _id, _target: {"prepared": True})
    assert media_library_api.read_prepared_source("https://youtu.be/NkYwdZhkHF0", "vi")["prepared"]
    monkeypatch.setattr(media_library_api, "current_user_key", lambda: "other")
    with pytest.raises(HTTPException) as refused:
        media_library_api.read_prepared_source("https://youtu.be/NkYwdZhkHF0", "vi")
    assert refused.value.status_code == 404
    with pytest.raises(HTTPException) as malformed:
        media_library_api.read_prepared_source("https://www.youtube.com/watch?v=bad", "vi")
    assert malformed.value.status_code == 404


def test_pipeline_ipa_lookup_cannot_call_ai_or_store_dictionary(monkeypatch):
    import app as runtime

    calls = []
    monkeypatch.setattr(runtime._learning_cache, "get_dictionary", lambda _word: None)
    monkeypatch.setattr(runtime._learning_cache, "put_dictionary", lambda *_: calls.append("store"))
    monkeypatch.setattr(runtime.requests, "get", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(runtime, "dictionary_ai_fallback", lambda *_: calls.append("paid"))
    assert runtime._media_pipeline._english_reading("hello") == ""
    assert calls == []


def test_legacy_ipa_reuses_only_persisted_dictionary(monkeypatch):
    from types import SimpleNamespace

    calls = []
    monkeypatch.setattr(listening_api, "_translation_cache", SimpleNamespace(get_dictionary=lambda word: calls.append(word) or {"payload_json": '{"phonetic":"/həˈləʊ/"}'}))
    segment = SimpleNamespace(segment_id="s", original_text="Hello hello.")
    result = listening_api._cached_source_readings([segment])
    assert len(result["s"]) == 2
    assert calls == ["hello"]
    monkeypatch.setattr(listening_api, "_translation_cache", SimpleNamespace(get_dictionary=lambda _: (_ for _ in ()).throw(RuntimeError("unavailable cache"))))
    assert listening_api._cached_source_readings([segment]) == {"s": []}


def test_source_ipa_is_materialized_once_per_distinct_word(monkeypatch):
    entry = replace(_entry(), language="en")
    transcript = build_transcript(entry.media_id, "en", [Cue(0, 1000, "Hello hello.")])
    calls = []
    payload = lesson_payload(entry, transcript, "fixture", 1000,
                             english_reading=lambda word: calls.append(word) or "/həˈləʊ/")
    readings = payload["catalog"]["readings_by_segment"][transcript.segments[0].segment_id]
    assert [item["reading"] for item in readings] == ["/həˈləʊ/", "/həˈləʊ/"]
    assert calls == ["Hello"]
    entry = replace(entry, lesson={"payload": payload})
    monkeypatch.setattr(listening_api, "stored_media_entry", lambda _id: entry)
    assert listening_api.stored_media_payload(entry.media_id, "en")["catalog"]["readings_by_segment"] == payload["catalog"]["readings_by_segment"]


@pytest.mark.parametrize("language,text", [("en", "Hello there."), ("zh", "你好。")])
def test_preparation_then_navigation_reads_persisted_meaning(monkeypatch, language, text):
    entry = replace(_entry(), language=language, processing={"state": "ready"})
    payload = lesson_payload(entry, build_transcript(entry.media_id, language, [Cue(0, 1000, text)]), "fixture", 1000)
    entry = replace(entry, lesson={"payload": payload})
    cache = MemoryCache()
    calls = []
    monkeypatch.setattr(listening_api, "_translation_cache", cache)
    monkeypatch.setattr(listening_api, "_translation_provider_model", lambda: "test:revision1")
    monkeypatch.setattr(listening_api, "_curated_translator", lambda _media: lambda segments, target: (
        calls.append((target, len(segments))) or {s.segment_id: "Xin chào." for s in segments}
    ))
    monkeypatch.setattr(listening_api, "stored_media_entry", lambda _id: entry)
    monkeypatch.setattr(listening_api, "get_learner_profile", lambda: {"native_language": "vi"})
    # Even an uncached lesson read must not start work.
    cold = listening_api.stored_media_payload(entry.media_id, "vi")
    assert cold["translations"] == []
    assert calls == []
    prepared = listening_api.prepare_media_meanings(entry, "vi")
    assert prepared.status == "ready"
    assert len(calls) == 1
    listening_api.prepare_media_meanings(entry, "vi")
    for _capability in ["Listening", "Dictation", "Shadowing", "Respond", "reopen"]:
        response = listening_api.stored_media_payload(entry.media_id, "vi")
        assert response["translations"][0]["translated_meaning"] == "Xin chào."
        assert response["translation"]["source"]["request_count"] == 0
    assert len(calls) == 1


def test_curated_open_does_not_translate_missing_language(monkeypatch):
    monkeypatch.setattr(listening_api, "_translation_cache", MemoryCache())
    calls = []
    monkeypatch.setattr(listening_api, "_curated_translator", lambda _media: lambda *_: calls.append("paid"))
    # The shipped catalogue is real domain data; its missing locale must stay
    # unavailable until content preparation, without a provider on this GET.
    lesson = next(iter(listening_api.catalog_lessons()))
    monkeypatch.setattr(listening_api, "catalog_lesson", lambda _id: lesson)
    monkeypatch.setattr(listening_api, "get_learner_profile", lambda: {"native_language": "ja"})
    listening_api.open_listening_library_lesson(lesson.lesson_id, "ja")
    assert calls == []
