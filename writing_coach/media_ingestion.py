"""Provider-neutral orchestration for external Media Learning acquisition."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from urllib.parse import urlsplit

from writing_coach.core.support_languages import (
    UnsupportedSupportLanguage,
    normalize_support_language,
)
from writing_coach.media_learning import MediaLearningObject


class MediaImportCategory(str, Enum):
    """Stable learner-safe categories for media import failures."""

    MALFORMED_URL = "malformed_url"
    UNSUPPORTED_PROVIDER = "unsupported_provider"
    MEDIA_UNAVAILABLE = "media_unavailable"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_FAILURE = "provider_failure"
    MALFORMED_TRANSCRIPT = "malformed_transcript"
    UNSUPPORTED_SOURCE_LANGUAGE = "unsupported_source_language"
    INVALID_TARGET_LANGUAGE = "invalid_target_language"


_LEARNER_MESSAGES = {
    MediaImportCategory.MALFORMED_URL: "Enter a valid public media URL.",
    MediaImportCategory.UNSUPPORTED_PROVIDER: "This media provider is not supported yet.",
    MediaImportCategory.MEDIA_UNAVAILABLE: "This media is private or unavailable.",
    MediaImportCategory.PROVIDER_TIMEOUT: (
        "The media provider did not respond in time. Please try again."
    ),
    MediaImportCategory.PROVIDER_FAILURE: (
        "The media provider could not complete this request. Please try again."
    ),
    MediaImportCategory.MALFORMED_TRANSCRIPT: (
        "The provider returned captions that could not be used safely."
    ),
    MediaImportCategory.UNSUPPORTED_SOURCE_LANGUAGE: (
        "This media language is not supported yet."
    ),
    MediaImportCategory.INVALID_TARGET_LANGUAGE: "Choose a valid support language.",
}


class MediaImportError(Exception):
    """A categorized failure safe to map onto a learner API response."""

    def __init__(self, category: MediaImportCategory) -> None:
        self.category = category
        self.learner_message = _LEARNER_MESSAGES[category]
        super().__init__(self.learner_message)


class ProviderSourceUnavailable(Exception):
    """The provider reports that the source cannot be accessed."""


class ProviderUrlMalformed(Exception):
    """A recognized provider URL does not identify a supported media source."""


class ProviderTimedOut(Exception):
    """The provider did not respond before its bounded timeout."""


class ProviderRequestFailed(Exception):
    """The provider request failed without safe learner-facing detail."""


class ProviderTranscriptMalformed(Exception):
    """Provider caption data could not satisfy the M1.1 transcript contract."""


@dataclass(frozen=True)
class MediaPlayback:
    """A safe public playback reference; media remains provider-hosted."""

    provider: str
    kind: str
    url: str


@dataclass(frozen=True)
class MediaAcquisition:
    """One acquired M1.1 object plus its provider-hosted playback reference."""

    media_object: MediaLearningObject
    playback: MediaPlayback
    # Why the transcript is what it is. "" keeps every existing constructor
    # working; the adapter fills it in. The distinction that matters is between
    # a source that genuinely has no captions and one whose caption request
    # failed - deferral must not turn the second into the first.
    transcript_status: str = ""


class MediaProviderAdapter(Protocol):
    """Provider-specific network behavior behind a provider-neutral boundary."""

    provider_id: str

    def recognizes(self, source_url: str) -> bool: ...

    def acquire(
        self,
        source_url: str,
        source_language: str,
    ) -> MediaAcquisition: ...


_LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


def primary_language(language_tag: str) -> str:
    """Return the primary language subtag used by the learner-language registry."""
    return language_tag.split("-", 1)[0].casefold()


class MediaIngestionService:
    """Resolve an external URL and acquire one reusable Media Learning Object."""

    def __init__(
        self,
        adapters: Sequence[MediaProviderAdapter],
        source_language_supported: Callable[[str], bool],
    ) -> None:
        if not adapters:
            raise ValueError("At least one media provider adapter is required.")
        self._adapters = tuple(adapters)
        self._source_language_supported = source_language_supported

    def import_media(
        self,
        source_url: str,
        target_language: str,
        source_language: str,
    ) -> MediaAcquisition:
        self._validate_source_url(source_url)
        try:
            normalize_support_language(target_language)
        except UnsupportedSupportLanguage:
            raise MediaImportError(MediaImportCategory.INVALID_TARGET_LANGUAGE)
        if (
            not isinstance(source_language, str)
            or not _LANGUAGE_TAG.fullmatch(source_language)
            or not self._source_language_supported(primary_language(source_language))
        ):
            raise MediaImportError(MediaImportCategory.UNSUPPORTED_SOURCE_LANGUAGE)
        expected_source_language = primary_language(source_language)

        adapter = next(
            (candidate for candidate in self._adapters if candidate.recognizes(source_url)),
            None,
        )
        if adapter is None:
            raise MediaImportError(MediaImportCategory.UNSUPPORTED_PROVIDER)

        try:
            acquisition = adapter.acquire(source_url, expected_source_language)
        except ProviderUrlMalformed as exc:
            raise MediaImportError(MediaImportCategory.MALFORMED_URL) from exc
        except ProviderSourceUnavailable as exc:
            raise MediaImportError(MediaImportCategory.MEDIA_UNAVAILABLE) from exc
        except ProviderTimedOut as exc:
            raise MediaImportError(MediaImportCategory.PROVIDER_TIMEOUT) from exc
        except ProviderTranscriptMalformed as exc:
            raise MediaImportError(MediaImportCategory.MALFORMED_TRANSCRIPT) from exc
        except ProviderRequestFailed as exc:
            raise MediaImportError(MediaImportCategory.PROVIDER_FAILURE) from exc
        except MediaImportError:
            raise
        except Exception as exc:
            raise MediaImportError(MediaImportCategory.PROVIDER_FAILURE) from exc

        acquired_source_language = acquisition.media_object.asset.source_language
        if (
            acquired_source_language.casefold() != "und"
            and not self._source_language_supported(
                primary_language(acquired_source_language)
            )
        ):
            raise MediaImportError(MediaImportCategory.UNSUPPORTED_SOURCE_LANGUAGE)
        if (
            acquired_source_language.casefold() != "und"
            and primary_language(acquired_source_language) != expected_source_language
        ):
            raise MediaImportError(MediaImportCategory.UNSUPPORTED_SOURCE_LANGUAGE)
        return acquisition

    @staticmethod
    def _validate_source_url(source_url: str) -> None:
        if not isinstance(source_url, str) or source_url != source_url.strip():
            raise MediaImportError(MediaImportCategory.MALFORMED_URL)
        try:
            parsed = urlsplit(source_url)
            hostname = parsed.hostname
            parsed.port
        except ValueError as exc:
            raise MediaImportError(MediaImportCategory.MALFORMED_URL) from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise MediaImportError(MediaImportCategory.MALFORMED_URL)
