from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path

import pytest
import requests
from fastapi import HTTPException, Request

import auth_support
import writing_coach.media_api as media_api
import writing_coach.media_ingestion as media_ingestion
import writing_coach.media_learning as media_learning
import writing_coach.media_providers.youtube as youtube_provider
from writing_coach.core.request_context import LANGUAGE_CODE_CTX
from writing_coach.media_api import MediaImportIn, serialize_media_acquisition
from writing_coach.media_ingestion import (
    MediaImportCategory,
    MediaImportError,
    MediaIngestionService,
    ProviderRequestFailed,
    ProviderSourceUnavailable,
    ProviderTimedOut,
)
from writing_coach.media_providers.youtube import (
    BoundedYouTubeSession,
    PublicYouTubeCaptionClient,
    YouTubeCaptionSnippet,
    YouTubeCaptionTrack,
    YouTubeMediaProviderAdapter,
    normalize_youtube_transcript,
)
from writing_coach.media_providers.supadata import (
    SupadataTranscript,
    SupadataTranscriptChunk,
)
from writing_coach.media_translation import (
    MediaTranslationResult,
    MediaTranslationStatus,
)


VIDEO_ID = "dQw4w9WgXcQ"
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_live_provider_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPADATA_API_KEY", raising=False)

    def fail_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("M1.2 unit tests must not access the network")

    monkeypatch.setattr(requests.sessions.Session, "request", fail_network)


class FakeMetadataClient:
    def __init__(self, title: str = "A public media lesson", error: Exception | None = None) -> None:
        self.title = title
        self.error = error
        self.calls: list[str] = []

    def fetch_title(self, canonical_source_url: str) -> str:
        self.calls.append(canonical_source_url)
        if self.error is not None:
            raise self.error
        return self.title


class FakeCaptionClient:
    def __init__(
        self,
        track: YouTubeCaptionTrack | None,
        error: Exception | None = None,
    ) -> None:
        self.track = track
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def fetch_track(
        self,
        video_id: str,
        source_language: str,
    ) -> YouTubeCaptionTrack | None:
        self.calls.append((video_id, source_language))
        if self.error is not None:
            raise self.error
        return self.track


def _track(language: str = "en") -> YouTubeCaptionTrack:
    return YouTubeCaptionTrack(
        source_language=language,
        snippets=(
            YouTubeCaptionSnippet("Second caption", 1.5, 0.5),
            YouTubeCaptionSnippet("First caption", 0.0, 1.25),
        ),
    )


def _service(
    track: YouTubeCaptionTrack | None = None,
    *,
    caption_error: Exception | None = None,
    metadata_error: Exception | None = None,
) -> tuple[MediaIngestionService, FakeMetadataClient, FakeCaptionClient]:
    metadata = FakeMetadataClient(error=metadata_error)
    captions = FakeCaptionClient(_track() if track is None else track, error=caption_error)
    adapter = YouTubeMediaProviderAdapter(metadata_client=metadata, caption_client=captions)
    service = MediaIngestionService(
        adapters=(adapter,),
        source_language_supported=lambda code: code in {"en", "zh"},
    )
    return service, metadata, captions


@pytest.mark.parametrize(
    "source_url",
    (
        f"https://www.youtube.com/watch?v={VIDEO_ID}",
        f"https://youtu.be/{VIDEO_ID}",
        f"https://youtube.com/shorts/{VIDEO_ID}",
    ),
)
def test_supported_youtube_urls_share_one_canonical_acquisition(source_url: str) -> None:
    service, metadata, captions = _service()

    acquisition = service.import_media(source_url, "vi", "en")

    assert acquisition.media_object.asset.asset_id == f"youtube:{VIDEO_ID}"
    assert acquisition.media_object.asset.source_url == (
        f"https://www.youtube.com/watch?v={VIDEO_ID}"
    )
    assert metadata.calls == [f"https://www.youtube.com/watch?v={VIDEO_ID}"]
    assert captions.calls == [(VIDEO_ID, "en")]


@pytest.mark.parametrize(
    ("source_url", "category"),
    (
        ("not-a-url", MediaImportCategory.MALFORMED_URL),
        (
            f"https://user:secret@www.youtube.com/watch?v={VIDEO_ID}",
            MediaImportCategory.MALFORMED_URL,
        ),
        ("https://www.youtube.com/watch", MediaImportCategory.MALFORMED_URL),
        ("https://example.invalid/video", MediaImportCategory.UNSUPPORTED_PROVIDER),
    ),
)
def test_malformed_and_unsupported_urls_fail_safely(
    source_url: str,
    category: MediaImportCategory,
) -> None:
    service, _metadata, captions = _service()

    with pytest.raises(MediaImportError) as caught:
        service.import_media(source_url, "vi", "en")

    assert caught.value.category is category
    assert captions.calls == []
    assert source_url not in caught.value.learner_message


def test_playback_and_transcript_serialize_to_the_agreed_frontend_dto() -> None:
    service, _metadata, _captions = _service()

    response = serialize_media_acquisition(
        service.import_media(f"https://youtu.be/{VIDEO_ID}", "vi", "en")
    )

    assert response["playback"] == {
        "provider": "youtube",
        "kind": "embed",
        "url": f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}",
    }
    assert response["asset"]["source_provider"] == "youtube"
    assert response["asset"]["source_type"] == "external-video"
    assert response["asset"]["transcript_available"] is True
    assert response["asset"]["translation_available"] is False
    assert response["translations"] == []

    transcript = response["transcript"]
    assert transcript is not None
    assert transcript["source_language"] == "en"
    assert [segment["original_text"] for segment in transcript["segments"]] == [
        "First caption",
        "Second caption",
    ]
    assert [segment["order"] for segment in transcript["segments"]] == [0, 1]
    segment_ids = [segment["segment_id"] for segment in transcript["segments"]]
    assert len(segment_ids) == len(set(segment_ids)) == 2
    assert all(
        segment_id.startswith(f"youtube:{VIDEO_ID}:segment:")
        for segment_id in segment_ids
    )
    assert [(segment["start_ms"], segment["end_ms"]) for segment in transcript["segments"]] == [
        (0, 1250),
        (1500, 2000),
    ]


def test_caption_unavailable_returns_truthful_transcript_null_state() -> None:
    metadata = FakeMetadataClient()
    captions = FakeCaptionClient(None)
    service = MediaIngestionService(
        adapters=(YouTubeMediaProviderAdapter(metadata, captions),),
        source_language_supported=lambda code: code in {"en", "zh"},
    )

    response = serialize_media_acquisition(
        service.import_media(f"https://youtu.be/{VIDEO_ID}", "vi", "en")
    )

    assert response["asset"]["source_language"] == "und"
    assert response["asset"]["transcript_available"] is False
    assert response["asset"]["translation_available"] is False
    assert response["transcript"] is None
    assert response["translations"] == []



class FakeFallbackTranscriptClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def fetch(
        self,
        source_url: str,
        preferred_language: str,
        *,
        mode: str = "auto",
    ) -> SupadataTranscript:
        self.calls.append((source_url, preferred_language, mode))
        return SupadataTranscript(
            language=preferred_language,
            chunks=(
                SupadataTranscriptChunk(
                    text="Recovered caption",
                    offset_ms=0,
                    duration_ms=1200,
                    language=preferred_language,
                ),
            ),
        )


@pytest.mark.parametrize("native_error", (ProviderTimedOut(), ProviderRequestFailed()))
def test_recoverable_native_caption_failure_uses_supadata(native_error: Exception) -> None:
    metadata = FakeMetadataClient()
    captions = FakeCaptionClient(None, error=native_error)
    fallback = FakeFallbackTranscriptClient()
    adapter = YouTubeMediaProviderAdapter(
        metadata_client=metadata,
        caption_client=captions,
        fallback_transcript_client=fallback,
    )

    acquisition = adapter.acquire(f"https://youtu.be/{VIDEO_ID}", "en")

    transcript = acquisition.media_object.transcript
    assert transcript is not None
    assert transcript.segments[0].original_text == "Recovered caption"
    assert fallback.calls == [
        (f"https://www.youtube.com/watch?v={VIDEO_ID}", "en", "auto")
    ]



@pytest.mark.parametrize(
    ("error", "category"),
    (
        (ProviderSourceUnavailable(), MediaImportCategory.MEDIA_UNAVAILABLE),
        (ProviderTimedOut(), MediaImportCategory.PROVIDER_TIMEOUT),
        (ProviderRequestFailed(), MediaImportCategory.PROVIDER_FAILURE),
    ),
)
def test_provider_failures_use_learner_safe_categories(
    error: Exception,
    category: MediaImportCategory,
) -> None:
    service, _metadata, _captions = _service(caption_error=error)

    with pytest.raises(MediaImportError) as caught:
        service.import_media(f"https://youtu.be/{VIDEO_ID}", "vi", "en")

    assert caught.value.category is category
    assert VIDEO_ID not in caught.value.learner_message


@pytest.mark.parametrize(
    "track",
    (
        YouTubeCaptionTrack("en", ()),
        YouTubeCaptionTrack(
            "en",
            (YouTubeCaptionSnippet("Invalid time", -0.5, 1.0),),
        ),
        YouTubeCaptionTrack(
            "en",
            (YouTubeCaptionSnippet(" ", 0.0, 1.0),),
        ),
    ),
)
def test_malformed_provider_captions_fail_the_m1_contract(
    track: YouTubeCaptionTrack,
) -> None:
    service, _metadata, _captions = _service(track)

    with pytest.raises(MediaImportError) as caught:
        service.import_media(f"https://youtu.be/{VIDEO_ID}", "vi", "en")

    assert caught.value.category is MediaImportCategory.MALFORMED_TRANSCRIPT


@pytest.mark.parametrize(
    ("source_language", "text"),
    (
        ("en", "A shared English caption."),
        ("zh", "这是一个共享的中文字幕。"),
    ),
)
def test_english_and_chinese_use_the_same_ingestion_pipeline(
    source_language: str,
    text: str,
) -> None:
    track = YouTubeCaptionTrack(
        source_language,
        (YouTubeCaptionSnippet(text, 0.0, 1.0),),
    )
    service, _metadata, captions = _service(track)

    acquisition = service.import_media(
        f"https://youtu.be/{VIDEO_ID}", "vi", source_language
    )

    assert type(acquisition.media_object) is media_learning.MediaLearningObject
    assert acquisition.media_object.asset.source_language == source_language
    assert acquisition.media_object.transcript is not None
    assert acquisition.media_object.transcript.segments[0].original_text == text
    assert captions.calls == [(VIDEO_ID, source_language)]


def test_unsupported_source_language_fails_at_the_application_boundary() -> None:
    service, _metadata, _captions = _service(
        YouTubeCaptionTrack("fr", (YouTubeCaptionSnippet("Bonjour", 0.0, 1.0),))
    )

    with pytest.raises(MediaImportError) as caught:
        service.import_media(f"https://youtu.be/{VIDEO_ID}", "vi", "en")

    assert caught.value.category is MediaImportCategory.UNSUPPORTED_SOURCE_LANGUAGE


def test_api_maps_safe_error_category_without_provider_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _metadata, _captions = _service(caption_error=ProviderTimedOut())
    monkeypatch.setattr(media_api, "_media_ingestion_service", service)

    with pytest.raises(HTTPException) as caught:
        media_api.import_media(
            MediaImportIn(
                source_url=f"https://youtu.be/{VIDEO_ID}",
                target_language="vi",
            )
        )

    assert caught.value.status_code == 504
    # The canonical envelope, spec 2.6: a stable category, the learner message,
    # and an explicit answer to whether retrying is worth anything. A provider
    # timeout is one of the few failures where it is.
    assert caught.value.detail == {
            "category": "provider_timeout",
            "message": "The media provider did not respond in time. Please try again.",
            "retryable": True,
            "context": {},
    }


def test_media_import_api_is_protected_by_current_learner_auth_middleware(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _metadata, captions = _service()
    monkeypatch.setattr(media_api, "_media_ingestion_service", service)
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    middleware = auth_support.UserIsolationMiddleware(app=lambda *_args: None)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/media-learning/import",
            "raw_path": b"/api/media-learning/import",
            "query_string": b"",
            "headers": [],
            "scheme": "http",
            "server": ("test", 80),
            "client": ("test", 123),
            "session": {},
        }
    )

    async def fail_if_routed(_request: Request) -> None:
        raise AssertionError("Unauthenticated media import reached the provider route")

    response = asyncio.run(middleware.dispatch(request, fail_if_routed))

    assert response.status_code == 401
    assert json.loads(response.body) == {"detail": "Authentication required"}
    assert captions.calls == []


def test_provider_network_and_product_side_effects_remain_isolated() -> None:
    core_source = inspect.getsource(media_ingestion).casefold()
    domain_source = inspect.getsource(media_learning).casefold()
    api_source = inspect.getsource(media_api).casefold()
    combined = core_source + api_source

    assert "youtube" not in core_source
    assert "youtube" not in domain_source
    assert "requests" not in combined
    assert "writing_coach.ai" not in combined
    assert "sqlite" not in combined
    assert "sqlalchemy" not in combined
    assert "generate_structured" not in combined
    assert "speech_asr" not in combined
    assert "learner_translation" not in combined
    assert "yt_dlp" not in combined


@pytest.mark.parametrize("raw_language", (" vi ", " EN ", " Zh "))
def test_request_dto_normalizes_current_support_languages_without_translation(
    raw_language: str,
) -> None:
    payload = MediaImportIn(
        source_url=f"https://youtu.be/{VIDEO_ID}",
        target_language=raw_language,
    )

    assert payload.target_language == raw_language.strip().casefold()


@pytest.mark.parametrize(
    ("source_language", "selected_language", "expected_text"),
    (
        ("en", "en", "Manual English"),
        ("zh", "zh-Hans", "Generated Chinese"),
    ),
)
def test_public_caption_selection_is_language_explicit_and_order_independent(
    monkeypatch: pytest.MonkeyPatch,
    source_language: str,
    selected_language: str,
    expected_text: str,
) -> None:
    class FakeNoTranscriptFound(Exception):
        pass

    monkeypatch.setattr(youtube_provider, "NoTranscriptFound", FakeNoTranscriptFound)

    class FakeSnippet:
        start = 0.25
        duration = 1.5

        def __init__(self, text: str) -> None:
            self.text = text

    class FakeFetchedTranscript:
        def __init__(self, language_code: str, text: str) -> None:
            self.language_code = language_code
            self._snippet = FakeSnippet(text)

        def __iter__(self):
            return iter((self._snippet,))

    class FakeTranscript:
        def __init__(self, language_code: str, text: str, *, generated: bool) -> None:
            self.language_code = language_code
            self.text = text
            self.is_generated = generated

        def fetch(self) -> FakeFetchedTranscript:
            return FakeFetchedTranscript(self.language_code, self.text)

    class FakeTranscriptList:
        def __init__(self) -> None:
            # Deliberately place unrelated and generated tracks before the preferred
            # manual English track. Selection must never use iterable position.
            self.tracks = (
                FakeTranscript("fr", "Manual French", generated=False),
                FakeTranscript("zh-Hans", "Generated Chinese", generated=True),
                FakeTranscript("en", "Generated English", generated=True),
                FakeTranscript("en", "Manual English", generated=False),
            )
            self.selection_calls: list[tuple[str, tuple[str, ...]]] = []

        def __iter__(self):
            return iter(self.tracks)

        def _find(self, languages: list[str], *, generated: bool) -> FakeTranscript:
            kind = "generated" if generated else "manual"
            self.selection_calls.append((kind, tuple(languages)))
            for track in self.tracks:
                if track.language_code in languages and track.is_generated is generated:
                    return track
            raise FakeNoTranscriptFound()

        def find_manually_created_transcript(
            self, languages: list[str]
        ) -> FakeTranscript:
            return self._find(languages, generated=False)

        def find_generated_transcript(self, languages: list[str]) -> FakeTranscript:
            return self._find(languages, generated=True)

    transcript_list = FakeTranscriptList()

    class FakeTranscriptApi:
        def list(self, video_id: str) -> FakeTranscriptList:
            assert video_id == VIDEO_ID
            return transcript_list

    client = PublicYouTubeCaptionClient(api=FakeTranscriptApi())  # type: ignore[arg-type]

    track = client.fetch_track(VIDEO_ID, source_language)

    assert track == YouTubeCaptionTrack(
        source_language=selected_language,
        snippets=(YouTubeCaptionSnippet(expected_text, 0.25, 1.5),),
    )
    assert transcript_list.selection_calls[0] == ("manual", (selected_language,))
    if source_language == "en":
        assert transcript_list.selection_calls == [("manual", ("en",))]
    else:
        assert transcript_list.selection_calls == [
            ("manual", ("zh-Hans",)),
            ("generated", ("zh-Hans",)),
        ]


def test_active_learning_language_reaches_the_provider_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _metadata, captions = _service(
        YouTubeCaptionTrack(
            "zh",
            (YouTubeCaptionSnippet("Chinese learning caption", 0.0, 1.0),),
        )
    )
    monkeypatch.setattr(media_api, "_media_ingestion_service", service)

    class NoopTranslationService:
        @staticmethod
        def translate(media_object, target_language):
            return MediaTranslationResult(
                media_object=media_object,
                status=MediaTranslationStatus.NOT_REQUIRED,
                target_language=target_language,
            )

    monkeypatch.setattr(
        media_api,
        "_media_translation_service",
        NoopTranslationService(),
    )
    token = LANGUAGE_CODE_CTX.set("zh")
    try:
        media_api.import_media(
            MediaImportIn(
                source_url=f"https://youtu.be/{VIDEO_ID}",
                target_language="vi",
            )
        )
    finally:
        LANGUAGE_CODE_CTX.reset(token)

    assert captions.calls == [(VIDEO_ID, "zh")]


def test_unrequested_language_tracks_do_not_become_canonical_source_text() -> None:
    class UnsupportedTranscript:
        language_code = "fr"

        def fetch(self) -> None:
            raise AssertionError("An unsupported-language transcript was fetched")

    class UnsupportedOnlyTranscriptList:
        def __iter__(self):
            return iter((UnsupportedTranscript(),))

        def find_manually_created_transcript(self, _languages: list[str]) -> None:
            raise AssertionError("No unsupported track should reach selection")

        def find_generated_transcript(self, _languages: list[str]) -> None:
            raise AssertionError("No unsupported track should reach selection")

    class FakeTranscriptApi:
        def list(self, video_id: str) -> UnsupportedOnlyTranscriptList:
            assert video_id == VIDEO_ID
            return UnsupportedOnlyTranscriptList()

    client = PublicYouTubeCaptionClient(api=FakeTranscriptApi())  # type: ignore[arg-type]

    assert client.fetch_track(VIDEO_ID, "en") is None


def test_segment_identity_is_stable_across_reacquisition_and_earlier_insertion() -> None:
    base = YouTubeCaptionTrack(
        "en",
        (
            YouTubeCaptionSnippet("First stable caption", 1.0, 0.5),
            YouTubeCaptionSnippet("Second stable caption", 2.0, 0.5),
        ),
    )
    inserted = YouTubeCaptionTrack(
        "en",
        (YouTubeCaptionSnippet("Unrelated earlier caption", 0.0, 0.5), *base.snippets),
    )

    first = normalize_youtube_transcript(f"youtube:{VIDEO_ID}", base)
    reacquired = normalize_youtube_transcript(f"youtube:{VIDEO_ID}", base)
    with_insertion = normalize_youtube_transcript(f"youtube:{VIDEO_ID}", inserted)

    assert [segment.segment_id for segment in first.segments] == [
        segment.segment_id for segment in reacquired.segments
    ]
    original_ids = {
        segment.original_text: segment.segment_id for segment in first.segments
    }
    inserted_ids = {
        segment.original_text: segment.segment_id for segment in with_insertion.segments
    }
    assert inserted_ids["First stable caption"] == original_ids["First stable caption"]
    assert inserted_ids["Second stable caption"] == original_ids["Second stable caption"]


def test_changed_caption_content_changes_identity_and_duplicates_stay_unique() -> None:
    original = normalize_youtube_transcript(
        f"youtube:{VIDEO_ID}",
        YouTubeCaptionTrack(
            "en", (YouTubeCaptionSnippet("Original caption", 1.0, 0.5),)
        ),
    )
    changed = normalize_youtube_transcript(
        f"youtube:{VIDEO_ID}",
        YouTubeCaptionTrack(
            "en", (YouTubeCaptionSnippet("Changed caption", 1.0, 0.5),)
        ),
    )
    retimed = normalize_youtube_transcript(
        f"youtube:{VIDEO_ID}",
        YouTubeCaptionTrack(
            "en", (YouTubeCaptionSnippet("Original caption", 1.25, 0.5),)
        ),
    )
    duplicates = normalize_youtube_transcript(
        f"youtube:{VIDEO_ID}",
        YouTubeCaptionTrack(
            "en",
            (
                YouTubeCaptionSnippet("Repeated caption", 3.0, 0.5),
                YouTubeCaptionSnippet("Repeated caption", 3.0, 0.5),
            ),
        ),
    )

    assert original.segments[0].segment_id != changed.segments[0].segment_id
    assert original.segments[0].segment_id != retimed.segments[0].segment_id
    duplicate_ids = [segment.segment_id for segment in duplicates.segments]
    assert len(duplicate_ids) == len(set(duplicate_ids)) == 2


def test_caption_http_boundary_applies_a_bounded_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_request(
        _session: requests.Session,
        method: str,
        url: str,
        **kwargs: object,
    ) -> requests.Response:
        captured.update({"method": method, "url": url, **kwargs})
        return requests.Response()

    monkeypatch.setattr(requests.Session, "request", fake_request)
    session = BoundedYouTubeSession(timeout_seconds=7)

    session.get("https://provider.example.invalid/captions")

    assert captured["method"] == "GET"
    assert captured["url"] == "https://provider.example.invalid/captions"
    assert captured["allow_redirects"] is True
    assert captured["timeout"] == 7


def test_application_registers_the_agreed_authenticated_import_route() -> None:
    from app import app

    registered_routes = list(app.routes)
    for route in app.routes:
        included_router = getattr(route, "original_router", None)
        if included_router is not None:
            registered_routes.extend(included_router.routes)
    matching_routes = [
        route
        for route in registered_routes
        if getattr(route, "path", None) == "/api/media-learning/import"
    ]

    assert len(matching_routes) == 1
    assert matching_routes[0].methods == {"POST"}


def test_canonical_state_marks_m15_and_m16_closed() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = (ROOT / "docs/project/archive/HANDOFF_BEFORE_PROJECT_MEMORY.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8")
    normalized_state = " ".join(project_state.split()).casefold()
    normalized_handoff = " ".join(handoff.split()).casefold()
    normalized_roadmap = " ".join(roadmap.split()).casefold()

    assert "m1.1 is **closed / approved / merged**" in normalized_state
    assert "m1.2 is **closed / approved / merged**" in normalized_state
    assert "m1.3 is **closed / approved / merged**" in normalized_state
    assert "m1.4 is **closed / approved / merged**" in normalized_state
    assert "m1.5 is **closed / approved / merged**" in normalized_state
    assert "m1.1 is **closed / approved / merged**" in normalized_handoff
    assert "m1.2 is **closed / approved / merged**" in normalized_handoff
    assert "m1.3 shared media translation is **closed / approved / merged**" in normalized_handoff
    assert "m1.4 listening mvp integration and acceptance is **closed / approved / merged**" in normalized_handoff
    assert "m1.5 active listening is **closed / approved / merged**" in normalized_handoff
    assert "m1.1 — media object and segment contracts: **closed / merged**" in normalized_roadmap
    assert "m1.2 — media ingestion and transcript acquisition: **closed / merged**" in normalized_roadmap
    assert "m1.3 — shared media translation: **closed / merged**" in normalized_roadmap
    assert "m1.4 — listening mvp integration and acceptance: **closed / merged**" in normalized_roadmap
    assert "m1.5 — active listening: **closed / merged**" in normalized_roadmap
    assert "m1.6 — shadowing integration: **closed / merged**" in normalized_roadmap
    assert "pv-2 / oren-10" in normalized_handoff
    assert "pv-3 / oren-11" in normalized_handoff

    assert "R2 — AI Capability Control Plane: **HUMAN GATE / READY, NOT PRODUCT-BLOCKING**" in handoff
    listening_row = next(
        tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
        for line in project_state.splitlines()
        if line.lstrip().startswith("|")
        and line.strip().strip("|").split("|")[0].strip().casefold() == "listening"
    )
    assert listening_row == ("Listening", "DEVELOPMENT", "available", "available", "no")
    assert "listening and speaking remain non-public" in normalized_handoff
