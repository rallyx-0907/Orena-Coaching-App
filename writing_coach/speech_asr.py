"""Provider-neutral speech ASR boundary with a Groq adapter."""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

import requests
from urllib.parse import urlsplit


class SpeechAsrError(Exception):
    pass


class SpeechAsrTimedOut(SpeechAsrError):
    pass


class SpeechAsrRequestFailed(SpeechAsrError):
    def __init__(self, status_code: int | None = None, provider_message: str = "") -> None:
        super().__init__(provider_message or "Speech ASR provider request failed.")
        self.status_code = status_code
        self.provider_message = provider_message


class SpeechAsrMalformed(SpeechAsrError):
    pass


class SpeechAsrPayloadTooLarge(SpeechAsrError):
    pass


@dataclass(frozen=True)
class SpeechAsrWord:
    word: str
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class SpeechAsrSegment:
    text: str
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class SpeechAsrResult:
    provider: str
    model: str
    language: str
    text: str
    segments: tuple[SpeechAsrSegment, ...]
    words: tuple[SpeechAsrWord, ...]


class SpeechAsrProvider(Protocol):
    provider_id: str

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        *,
        filename: str,
        content_type: str,
        language: str | None,
    ) -> SpeechAsrResult: ...


def _seconds_to_ms(value: Any) -> int:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
    ):
        raise SpeechAsrMalformed()
    return max(0, round(float(value) * 1000))


def _parse_transcription_response(
    response: requests.Response,
    *,
    language: str | None,
    provider: str,
    model: str,
) -> SpeechAsrResult:
    if response.status_code == 413:
        raise SpeechAsrPayloadTooLarge()
    if response.status_code != 200:
        provider_message = ""
        try:
            error_payload = response.json()
            if isinstance(error_payload, dict):
                error_value = error_payload.get("error")
                if isinstance(error_value, dict):
                    provider_message = str(error_value.get("message") or "")
                elif isinstance(error_value, str):
                    provider_message = error_value
        except ValueError:
            provider_message = ""
        raise SpeechAsrRequestFailed(
            status_code=response.status_code,
            provider_message=provider_message[:500],
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise SpeechAsrMalformed() from exc
    if not isinstance(payload, dict):
        raise SpeechAsrMalformed()

    text = payload.get("text")
    if not isinstance(text, str):
        raise SpeechAsrMalformed()

    detected_language = payload.get("language")
    if not isinstance(detected_language, str) or not detected_language.strip():
        detected_language = language or "und"

    segments: list[SpeechAsrSegment] = []
    raw_segments = payload.get("segments")
    if isinstance(raw_segments, list):
        for item in raw_segments:
            if not isinstance(item, dict):
                continue
            segment_text = str(item.get("text") or "").strip()
            if not segment_text:
                continue
            start_ms = _seconds_to_ms(item.get("start"))
            end_ms = _seconds_to_ms(item.get("end"))
            if end_ms <= start_ms:
                continue
            segments.append(
                SpeechAsrSegment(
                    text=segment_text,
                    start_ms=start_ms,
                    end_ms=end_ms,
                )
            )

    words: list[SpeechAsrWord] = []
    raw_words = payload.get("words")
    if isinstance(raw_words, list):
        for item in raw_words:
            if not isinstance(item, dict):
                continue
            word = str(item.get("word") or "").strip()
            if not word:
                continue
            start_ms = _seconds_to_ms(item.get("start"))
            end_ms = _seconds_to_ms(item.get("end"))
            if end_ms <= start_ms:
                continue
            words.append(SpeechAsrWord(word=word, start_ms=start_ms, end_ms=end_ms))

    return SpeechAsrResult(
        provider=provider,
        model=model,
        language=detected_language.strip(),
        text=text.strip(),
        segments=tuple(segments),
        words=tuple(words),
    )


class GroqSpeechAsrProvider:
    provider_id = "groq"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "whisper-large-v3-turbo",
        timeout_seconds: float = 120.0,
        max_bytes: int = 24 * 1024 * 1024,
        session: requests.Session | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Groq API key is required.")
        # The key goes into a header: printable ASCII with no space, refused otherwise by a message
        # that never repeats it (a transport library would echo it in its own error).
        if not re.fullmatch(r"[!-~]+", api_key.strip()):
            raise ValueError("Groq API key has characters a request header cannot carry.")
        if timeout_seconds <= 0 or max_bytes <= 0:
            raise ValueError("Groq ASR limits must be positive.")
        self._api_key = api_key.strip()
        self._model = model.strip() or "whisper-large-v3-turbo"
        self._timeout_seconds = float(timeout_seconds)
        self._max_bytes = int(max_bytes)
        self._session = session or requests.Session()

    @property
    def model(self) -> str:
        return self._model

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    @classmethod
    def from_env(cls) -> "GroqSpeechAsrProvider | None":
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            return None
        return cls(
            api_key,
            model=os.getenv("GROQ_ASR_MODEL", "whisper-large-v3-turbo"),
            timeout_seconds=float(os.getenv("GROQ_ASR_TIMEOUT_SECONDS", "120")),
            max_bytes=int(os.getenv("GROQ_ASR_MAX_BYTES", str(24 * 1024 * 1024))),
        )

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        *,
        filename: str,
        content_type: str,
        language: str | None,
    ) -> SpeechAsrResult:
        if not audio_bytes:
            raise SpeechAsrMalformed()
        if len(audio_bytes) > self._max_bytes:
            raise SpeechAsrPayloadTooLarge()

        fields: list[tuple[str, str]] = [
            ("model", self._model),
            ("response_format", "verbose_json"),
            ("temperature", "0"),
            ("timestamp_granularities[]", "segment"),
            ("timestamp_granularities[]", "word"),
        ]
        if language:
            fields.append(("language", language))

        try:
            response = self._session.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                files={
                    "file": (
                        filename or "recording.webm",
                        audio_bytes,
                        content_type or "application/octet-stream",
                    )
                },
                data=fields,
                timeout=self._timeout_seconds,
            )
        except requests.Timeout as exc:
            raise SpeechAsrTimedOut() from exc
        except requests.RequestException:
            # Raised below, outside this block, so it carries no cause or context: some transport
            # errors quote the request's headers, the key among them.
            response = None
        if response is None:
            raise SpeechAsrRequestFailed()

        return _parse_transcription_response(
            response,
            language=language,
            provider=self.provider_id,
            model=self._model,
        )

    def transcribe_url(
        self,
        audio_url: str,
        *,
        language: str | None,
    ) -> SpeechAsrResult:
        """Transcribe one public media-file URL without proxying bytes through Orena."""
        try:
            parsed = urlsplit(audio_url)
            hostname = parsed.hostname
        except ValueError as exc:
            raise SpeechAsrMalformed() from exc
        if (
            parsed.scheme != "https"
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise SpeechAsrMalformed()

        fields: list[tuple[str, str]] = [
            ("model", self._model),
            ("response_format", "verbose_json"),
            ("temperature", "0"),
            ("timestamp_granularities[]", "segment"),
            ("timestamp_granularities[]", "word"),
        ]
        if language:
            fields.append(("language", language))

        try:
            response = self._session.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                files={"url": (None, audio_url)},
                data=fields,
                timeout=self._timeout_seconds,
            )
        except requests.Timeout as exc:
            raise SpeechAsrTimedOut() from exc
        except requests.RequestException:
            # Raised below, outside this block, so it carries no cause or context: some transport
            # errors quote the request's headers, the key among them.
            response = None
        if response is None:
            raise SpeechAsrRequestFailed()

        return _parse_transcription_response(
            response,
            language=language,
            provider=self.provider_id,
            model=self._model,
        )
