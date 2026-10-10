"""Supadata transcript fallback for public media URLs.

Provider-specific acquisition lives here. Core Media Learning keeps using the
existing canonical timestamped transcript contract.
"""

from __future__ import annotations

import math
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import requests

_ENDPOINT = "https://api.supadata.ai/v1/transcript"


class SupadataTranscriptError(Exception):
    pass


class SupadataTranscriptTimedOut(SupadataTranscriptError):
    pass


class SupadataTranscriptRequestFailed(SupadataTranscriptError):
    pass


class SupadataTranscriptMalformed(SupadataTranscriptError):
    pass


@dataclass(frozen=True)
class SupadataTranscriptChunk:
    text: str
    offset_ms: int
    duration_ms: int
    language: str | None = None


@dataclass(frozen=True)
class SupadataTranscript:
    language: str
    chunks: tuple[SupadataTranscriptChunk, ...]


@dataclass(frozen=True)
class SupadataTranscriptJob:
    """One provider-side async transcript job."""

    job_id: str
    status: str = "queued"


@dataclass(frozen=True)
class SupadataTranscriptJobResult:
    """One non-blocking provider job status check."""

    status: str
    transcript: SupadataTranscript | None = None


def _primary_language(value: str) -> str:
    return value.split("-", 1)[0].casefold()


class SupadataTranscriptClient:
    """Bounded REST client for dev/beta media imports."""

    def __init__(
        self,
        api_key: str,
        *,
        request_timeout_seconds: float = 20.0,
        max_wait_seconds: float = 150.0,
        poll_interval_seconds: float = 1.0,
        session: requests.Session | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Supadata API key is required.")
        if request_timeout_seconds <= 0 or max_wait_seconds <= 0 or poll_interval_seconds <= 0:
            raise ValueError("Supadata timeouts must be positive.")
        self._api_key = api_key.strip()
        self._request_timeout_seconds = float(request_timeout_seconds)
        self._max_wait_seconds = float(max_wait_seconds)
        self._poll_interval_seconds = float(poll_interval_seconds)
        self._session = session or requests.Session()

    @classmethod
    def from_env(cls) -> "SupadataTranscriptClient | None":
        api_key = os.getenv("SUPADATA_API_KEY", "").strip()
        if not api_key:
            return None
        return cls(
            api_key,
            request_timeout_seconds=float(
                os.getenv("SUPADATA_REQUEST_TIMEOUT_SECONDS", "20")
            ),
            max_wait_seconds=float(
                os.getenv("SUPADATA_MAX_WAIT_SECONDS", "150")
            ),
            poll_interval_seconds=float(
                os.getenv("SUPADATA_POLL_INTERVAL_SECONDS", "1")
            ),
        )

    def start(
        self,
        source_url: str,
        preferred_language: str,
        *,
        mode: str = "auto",
    ) -> SupadataTranscript | SupadataTranscriptJob | None:
        """Start one transcript request without waiting for provider async work."""
        if mode not in {"auto", "generate", "native"}:
            raise ValueError("Unsupported Supadata transcript mode.")

        deadline = time.monotonic() + self._request_timeout_seconds
        payload = self._get(
            _ENDPOINT,
            params={
                "url": source_url,
                "lang": preferred_language,
                "text": "false",
                "mode": mode,
            },
            deadline=deadline,
            allow_206=True,
        )
        if payload is None:
            return None

        job_id = payload.get("jobId")
        if isinstance(job_id, str) and job_id.strip():
            return SupadataTranscriptJob(job_id=job_id.strip(), status="queued")
        return self._parse_transcript(payload, preferred_language)

    def poll(
        self,
        job_id: str,
        preferred_language: str,
    ) -> SupadataTranscriptJobResult:
        """Check one provider job exactly once; never sleep or loop here."""
        normalized_job_id = str(job_id or "").strip()
        if (
            not normalized_job_id
            or len(normalized_job_id) > 200
            or re.fullmatch(r"[A-Za-z0-9._:-]+", normalized_job_id) is None
        ):
            raise ValueError("Invalid Supadata transcript job id.")

        deadline = time.monotonic() + self._request_timeout_seconds
        payload = self._get(
            f"{_ENDPOINT}/{normalized_job_id}",
            params=None,
            deadline=deadline,
            allow_206=False,
        )
        if payload is None:
            raise SupadataTranscriptRequestFailed()

        status = str(payload.get("status") or "").casefold()
        if status in {"queued", "active", "processing", "pending"}:
            return SupadataTranscriptJobResult(status=status)
        if status == "failed":
            return SupadataTranscriptJobResult(status="failed")
        if status == "completed":
            result = payload.get("result")
            transcript_payload = result if isinstance(result, dict) else payload
            transcript = self._parse_transcript(
                transcript_payload,
                preferred_language,
            )
            return SupadataTranscriptJobResult(
                status="completed",
                transcript=transcript,
            )

        if "content" in payload:
            transcript = self._parse_transcript(payload, preferred_language)
            return SupadataTranscriptJobResult(
                status="completed",
                transcript=transcript,
            )
        raise SupadataTranscriptMalformed()

    def fetch(
        self,
        source_url: str,
        preferred_language: str,
        *,
        mode: str = "auto",
    ) -> SupadataTranscript | None:
        if mode not in {"auto", "generate", "native"}:
            raise ValueError("Unsupported Supadata transcript mode.")

        deadline = time.monotonic() + self._max_wait_seconds
        payload = self._get(
            _ENDPOINT,
            params={
                "url": source_url,
                "lang": preferred_language,
                "text": "false",
                "mode": mode,
            },
            deadline=deadline,
            allow_206=True,
        )
        if payload is None:
            return None

        job_id = payload.get("jobId")
        if isinstance(job_id, str) and job_id.strip():
            payload = self._poll_job(job_id.strip(), deadline)

        return self._parse_transcript(payload, preferred_language)

    def _poll_job(self, job_id: str, deadline: float) -> dict[str, Any]:
        url = f"{_ENDPOINT}/{job_id}"
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SupadataTranscriptTimedOut()
            time.sleep(min(self._poll_interval_seconds, remaining))
            payload = self._get(
                url,
                params=None,
                deadline=deadline,
                allow_206=False,
            )
            if payload is None:
                raise SupadataTranscriptRequestFailed()

            status = str(payload.get("status") or "").casefold()
            if status in {"queued", "active", "processing", "pending"}:
                continue
            if status == "failed":
                raise SupadataTranscriptRequestFailed()
            if status == "completed":
                result = payload.get("result")
                return result if isinstance(result, dict) else payload
            if "content" in payload:
                return payload
            raise SupadataTranscriptMalformed()

    def _get(
        self,
        url: str,
        *,
        params: dict[str, str] | None,
        deadline: float,
        allow_206: bool,
    ) -> dict[str, Any] | None:
        """One Supadata request. The request that starts a transcript (it carries parameters) is one row in the AI
        cost ledger - provider, model, outcome, latency; Supadata reports no usage and the repository holds no
        price for it, so its cost is said as unpriced, never zero. A poll of a job already started is not counted
        again."""
        if params is None:
            return self._request(url, params=params, deadline=deadline, allow_206=allow_206)
        from writing_coach.ai.audio_telemetry import record_audio_operation

        started = time.perf_counter()
        try:
            payload = self._request(url, params=params, deadline=deadline, allow_206=allow_206)
        except Exception as exc:
            record_audio_operation("media_transcript_fallback", provider="supadata", model="transcript",
                                   outcome="failure", latency_ms=int((time.perf_counter() - started) * 1000),
                                   audio_seconds=None, error=exc)
            raise
        record_audio_operation("media_transcript_fallback", provider="supadata", model="transcript",
                               outcome="success", latency_ms=int((time.perf_counter() - started) * 1000),
                               audio_seconds=None)
        return payload

    def _request(
        self,
        url: str,
        *,
        params: dict[str, str] | None,
        deadline: float,
        allow_206: bool,
    ) -> dict[str, Any] | None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SupadataTranscriptTimedOut()
        timeout = min(self._request_timeout_seconds, remaining)
        try:
            response = self._session.get(
                url,
                params=params,
                headers={"x-api-key": self._api_key},
                timeout=timeout,
            )
        except requests.Timeout as exc:
            raise SupadataTranscriptTimedOut() from exc
        except requests.RequestException as exc:
            raise SupadataTranscriptRequestFailed() from exc

        if response.status_code == 206:
            # Do not silently degrade generated-transcript failure into transcript=None.
            raise SupadataTranscriptRequestFailed()
        if response.status_code in {401, 402, 403, 404, 409, 422, 429}:
            raise SupadataTranscriptRequestFailed()
        if response.status_code >= 500:
            raise SupadataTranscriptRequestFailed()
        if response.status_code not in {200, 202}:
            raise SupadataTranscriptRequestFailed()

        try:
            payload = response.json()
        except ValueError as exc:
            raise SupadataTranscriptMalformed() from exc
        if not isinstance(payload, dict):
            raise SupadataTranscriptMalformed()
        return payload

    def _parse_transcript(
        self,
        payload: dict[str, Any],
        preferred_language: str,
    ) -> SupadataTranscript | None:
        nested = payload.get("result")
        if isinstance(nested, dict) and "content" not in payload:
            payload = nested

        language = payload.get("lang")
        if not isinstance(language, str) or not language.strip():
            raise SupadataTranscriptMalformed()
        language = language.strip()
        if _primary_language(language) != _primary_language(preferred_language):
            raise SupadataTranscriptMalformed()

        content = payload.get("content")
        if content == []:
            return None
        if not isinstance(content, list):
            raise SupadataTranscriptMalformed()

        chunks: list[SupadataTranscriptChunk] = []
        for item in content:
            if not isinstance(item, dict):
                raise SupadataTranscriptMalformed()
            text = " ".join(str(item.get("text") or "").split())
            if not text:
                continue
            offset = item.get("offset")
            duration = item.get("duration")
            if (
                not isinstance(offset, (int, float))
                or isinstance(offset, bool)
                or not isinstance(duration, (int, float))
                or isinstance(duration, bool)
                or not math.isfinite(offset)
                or not math.isfinite(duration)
            ):
                raise SupadataTranscriptMalformed()
            offset_ms = round(float(offset))
            duration_ms = round(float(duration))
            if offset_ms < 0 or duration_ms <= 0:
                raise SupadataTranscriptMalformed()
            chunk_language = item.get("lang")
            if chunk_language is not None and not isinstance(chunk_language, str):
                raise SupadataTranscriptMalformed()
            chunks.append(
                SupadataTranscriptChunk(
                    text=text,
                    offset_ms=offset_ms,
                    duration_ms=duration_ms,
                    language=chunk_language,
                )
            )

        if not chunks:
            return None
        return SupadataTranscript(language=language, chunks=tuple(chunks))
