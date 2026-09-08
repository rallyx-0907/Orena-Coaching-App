"""Curated transcripts are acquired at ingestion and never re-acquired at runtime.

The product rule, and it is permanent:

    A learner opening a curated lesson must NEVER need the YouTube transcript
    API, Supadata, or any other transcript provider. Provider calls belong to
    INGESTION time.

This matters for latency, for cost, and for truth. A curated lesson whose
transcript is already persisted should be READY the instant it opens — never
"Preparing transcript…", which is a My Media state, not a library state.

These tests fail loudly if a future refactor moves transcript acquisition back
into the learner hot path. They do it by making the provider clients explode:
any call at all, from anywhere under the request, is a test failure rather than
a slow test.

My Media is deliberately NOT covered by this rule and keeps its async recovery.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app as orena_app
from writing_coach.listening_catalog import (
    TRANSCRIPT_ORIGIN_GENERATED_ASR,
    TRANSCRIPT_ORIGIN_PROVIDER_CAPTION,
    TRANSCRIPT_ORIGIN_UNSPECIFIED,
    TRANSCRIPT_QUALITY_GENERATED_UNREVIEWED,
    TRANSCRIPT_QUALITY_PROVIDER_CAPTION,
    TRANSCRIPT_QUALITY_UNSPECIFIED,
    load_catalog,
)


class ProviderContacted(AssertionError):
    """Raised the moment any transcript provider is touched at runtime."""


def _explode(name: str):
    def boom(*args, **kwargs):
        raise ProviderContacted(
            f"{name} was called while opening a curated lesson. Curated "
            "transcripts are persisted at ingestion; the learner hot path must "
            "not contact a transcript provider.")
    return boom


@pytest.fixture
def no_transcript_providers(monkeypatch):
    """Make every TRANSCRIPT provider fatal for the duration of a request.

    Deliberately not "no network at all". Translation is a different contract:
    it is allowed to be lazy and live, so a blanket requests ban would fail on
    an uncached support language and would be testing the wrong rule. Transcript
    is eager and persisted; meaning is lazy and cached. See the pair of
    translation tests at the bottom, which pin that difference in both
    directions.
    """

    import writing_coach.media_providers.youtube as youtube
    import writing_coach.media_providers.supadata as supadata

    monkeypatch.setattr(youtube.PublicYouTubeCaptionClient, "fetch_track",
                        _explode("PublicYouTubeCaptionClient.fetch_track"))
    monkeypatch.setattr(youtube.YouTubeMediaProviderAdapter, "acquire",
                        _explode("YouTubeMediaProviderAdapter.acquire"))
    for attribute in ("start", "poll", "fetch_transcript"):
        if hasattr(supadata.SupadataTranscriptClient, attribute):
            monkeypatch.setattr(supadata.SupadataTranscriptClient, attribute,
                                _explode(f"SupadataTranscriptClient.{attribute}"))


@pytest.fixture
def no_network_at_all(no_transcript_providers, monkeypatch):
    """The strictest guard: not one outbound request, by any route.

    Used with a support language the lesson already pre-authors, where nothing
    at all should leave the process.
    """

    import requests
    monkeypatch.setattr(requests.Session, "request", _explode("requests.Session.request"))
    monkeypatch.setattr(requests, "get", _explode("requests.get"))
    monkeypatch.setattr(requests, "post", _explode("requests.post"))


@pytest.fixture
def client():
    return TestClient(orena_app.app)


def curated_lessons():
    """One real EN and one real ZH curated lesson from the shipped catalog."""

    _sources, lessons = load_catalog()
    found: dict[str, str] = {}
    for lesson in lessons:
        language = lesson.source.language.strip().casefold()[:2]
        if language in {"en", "zh"} and lesson.source.segments and language not in found:
            found[language] = lesson.lesson_id
    return found


# --- the contract ------------------------------------------------------------

@pytest.mark.parametrize("language", ["en", "zh"])
def test_opening_a_curated_lesson_contacts_no_transcript_provider(
    client, no_network_at_all, language
) -> None:
    """With a pre-authored support language, nothing leaves the process at all."""

    lessons = curated_lessons()
    lesson_id = lessons.get(language)
    assert lesson_id, f"the catalog must ship a real {language.upper()} lesson to prove this"

    response = client.get(f"/api/listening/library/{lesson_id}",
                          params={"target_language": "vi"})
    assert response.status_code == 200, response.text

    payload = response.json()
    segments = payload["transcript"]["segments"]
    assert segments, "the transcript must arrive with the lesson, from storage"
    assert all(segment["original_text"].strip() for segment in segments)

    # Timing came from the persisted artifact, not from anything invented now.
    assert all(segment["end_ms"] > segment["start_ms"] for segment in segments)


def test_the_library_listing_contacts_no_transcript_provider(
    client, no_network_at_all
) -> None:
    response = client.get("/api/listening/library")
    assert response.status_code == 200, response.text
    assert response.json()["items"], "the library must render from persisted data alone"


def test_a_curated_lesson_reports_transcript_ready_on_open(client, no_network_at_all) -> None:
    """UX rule: a curated lesson never shows "Preparing transcript…"."""

    for lesson_id in curated_lessons().values():
        payload = client.get(f"/api/listening/library/{lesson_id}").json()
        catalog = payload["catalog"]
        assert catalog["transcript_state"] == "ready"
        assert payload["asset"]["transcript_available"] is True
        # Nothing in the payload asks the learner to wait for a transcript.
        assert catalog.get("processing_state", "ready") != "pending"


def test_repeated_opens_stay_provider_free(client, no_network_at_all) -> None:
    """Not a cache warm-up trick: it is provider-free every single time."""

    lesson_id = next(iter(curated_lessons().values()))
    for _ in range(3):
        assert client.get(f"/api/listening/library/{lesson_id}").status_code == 200


def test_the_guard_itself_actually_bites(no_network_at_all) -> None:
    """A watchdog that cannot bark proves nothing.

    If the patching above ever stopped taking effect, every test in this file
    would pass while the hot path quietly called a provider. So: prove a call
    really does fail.
    """

    from writing_coach.media_providers.youtube import PublicYouTubeCaptionClient

    with pytest.raises(ProviderContacted):
        PublicYouTubeCaptionClient().fetch_track("dQw4w9WgXcQ", "en")

    import requests
    with pytest.raises(ProviderContacted):
        requests.get("https://example.invalid")


# --- provenance travels with the persisted transcript ------------------------

def test_every_curated_source_declares_its_transcript_provenance() -> None:
    sources, _lessons = load_catalog()
    for source in sources.values():
        assert source.transcript_origin in {
            TRANSCRIPT_ORIGIN_PROVIDER_CAPTION,
            TRANSCRIPT_ORIGIN_GENERATED_ASR,
            TRANSCRIPT_ORIGIN_UNSPECIFIED,
        }
        assert source.transcript_revision >= 1
        # Generated text is never described as the provider's own captions.
        if source.transcript_origin == TRANSCRIPT_ORIGIN_GENERATED_ASR:
            assert source.transcript_quality_state == TRANSCRIPT_QUALITY_GENERATED_UNREVIEWED
            assert not source.transcript_is_reviewed


def test_an_unknown_provenance_defaults_to_unspecified_not_to_official() -> None:
    """Backward compatibility must be truthful, not flattering.

    Lessons written before provenance existed have an unknown origin. Defaulting
    them to "provider_caption" would silently promote unknown text to official
    captions, so they default to UNSPECIFIED instead.
    """

    from writing_coach.listening_catalog import _transcript_provenance

    assert _transcript_provenance(None, "s1", "en") == {"transcript_language": "en"}

    sources, _lessons = load_catalog()
    source = next(iter(sources.values()))
    if source.transcript_origin == TRANSCRIPT_ORIGIN_UNSPECIFIED:
        assert source.transcript_quality_state == TRANSCRIPT_QUALITY_UNSPECIFIED
        assert not source.transcript_is_reviewed
        assert not source.transcript_is_generated


def test_generated_asr_cannot_be_labelled_provider_captions() -> None:
    from writing_coach.listening_catalog import _transcript_provenance

    with pytest.raises(ValueError, match="generated ASR as provider captions"):
        _transcript_provenance(
            {"origin": "generated_asr", "quality_state": "provider_caption"}, "s1", "zh")

    for bad in ({"origin": "official"}, {"quality_state": "perfect"}, {"revision": 0}):
        with pytest.raises(ValueError):
            _transcript_provenance(bad, "s1", "en")

    good = _transcript_provenance(
        {"origin": "generated_asr", "quality_state": "generated_unreviewed",
         "revision": 2, "language": "zh", "provider": "supadata"}, "s1", "zh")
    assert good["transcript_revision"] == 2
    assert good["transcript_quality_state"] == TRANSCRIPT_QUALITY_GENERATED_UNREVIEWED


def test_the_importer_records_generated_transcripts_as_generated() -> None:
    """Ingestion is where provenance is decided, so it must decide correctly."""

    from writing_coach.listening_source_import import _transcript_provenance_for

    class Asset:
        source_language = "zh"
        source_provider = "youtube"

    class Acquisition:
        def __init__(self, status):
            self.transcript_status = status
            self.media_object = type("M", (), {"asset": Asset()})()

    native = _transcript_provenance_for(Acquisition("native"), "zh")
    assert native["origin"] == TRANSCRIPT_ORIGIN_PROVIDER_CAPTION
    assert native["quality_state"] == TRANSCRIPT_QUALITY_PROVIDER_CAPTION

    generated = _transcript_provenance_for(Acquisition("generated"), "zh")
    assert generated["origin"] == TRANSCRIPT_ORIGIN_GENERATED_ASR
    assert generated["quality_state"] == TRANSCRIPT_QUALITY_GENERATED_UNREVIEWED


# --- transcript is eager, meaning is lazy: the difference is intentional ------

def test_an_uncached_support_language_still_never_touches_a_transcript_provider(
    client, no_transcript_providers
) -> None:
    """The distinction CI caught, now pinned.

    Asking for a support language the lesson does not pre-author MAY call the
    translation provider - meaning is lazy and cached by design. It must still
    never call a TRANSCRIPT provider: the transcript is already persisted.
    """

    lesson_id = curated_lessons()["en"]
    response = client.get(f"/api/listening/library/{lesson_id}",
                          params={"target_language": "ja"})
    assert response.status_code == 200, response.text

    payload = response.json()
    # The transcript arrived from storage regardless of the translation outcome.
    assert payload["transcript"]["segments"]
    assert payload["catalog"]["transcript_state"] == "ready"
    # And translation reports itself honestly either way.
    assert payload["translation"]["status"] in {"ready", "unavailable", "not_required"}


def test_a_preauthored_support_language_costs_no_provider_call(
    client, no_network_at_all
) -> None:
    """The other half: an editorial language spends nothing at all."""

    lesson_id = curated_lessons()["en"]
    payload = client.get(f"/api/listening/library/{lesson_id}",
                         params={"target_language": "vi"}).json()
    assert payload["translation"]["source"]["request_count"] == 0
    assert payload["translation"]["status"] in {"ready", "not_required"}
