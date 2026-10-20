"""Provider-neutral speech ASR boundary with a Groq adapter."""

from __future__ import annotations

import math
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import requests
from urllib.parse import urlsplit


_ASR_PROMPT_MAX_BYTES = 224


def _utf8_prefix(value: str, budget: int) -> str:
    """Return a codepoint-safe prefix that fits the byte budget."""
    pieces: list[str] = []
    used = 0
    for character in value:
        size = len(character.encode("utf-8"))
        if used + size > budget:
            break
        pieces.append(character)
        used += size
    return "".join(pieces)


def build_asr_prompt(title: str, description: str, *, language: str | None) -> str:
    """Build a small same-language Whisper vocabulary hint from source metadata.

    Groq caps Whisper prompts at 224 tokens. A conservative character limit keeps
    even Han-heavy metadata bounded; titles take priority and descriptions fill
    only the remaining space. No metadata means no prompt.
    """
    lang = (language or "").casefold().split("-", 1)[0]
    title_text = " ".join(str(title or "").split())
    description_text = " ".join(str(description or "").split())
    if not title_text and not description_text:
        return ""
    if lang == "zh":
        prefix, title_label, description_label = "相关视频标题：", "。", "视频简介："
    else:
        prefix, title_label, description_label = "Video title: ", ". ", "Description: "
    prompt = prefix
    if title_text:
        room = _ASR_PROMPT_MAX_BYTES - len(prompt.encode("utf-8")) - len(title_label.encode("utf-8"))
        prompt += _utf8_prefix(title_text, max(0, room)) + title_label
    if description_text and len(prompt.encode("utf-8")) < _ASR_PROMPT_MAX_BYTES:
        room = _ASR_PROMPT_MAX_BYTES - len(prompt.encode("utf-8")) - len(description_label.encode("utf-8"))
        if room > 0:
            prompt += description_label + _utf8_prefix(description_text, room)
    return _utf8_prefix(prompt, _ASR_PROMPT_MAX_BYTES)


# The title prompt is evidence-bounded (2026-10-17 live trial): it fixed the title idiom on 47-78 s clips, and cost a
# 282 s story 18 % of its Han text plus full-width junk. It is therefore sent only for audio up to this length, and a
# prompted chunk that shows the junk signature below is transcribed again without the prompt.
ASR_PROMPT_MAX_SECONDS = 120.0
# Full-width digits, comparison signs and Latin letters (U+FF10-FF19, FF1C-FF1E, FF20-FF5A): Whisper emits them as garbage
# in place of punctuation under a prompt. Full-width sentence punctuation (，。！？：；（）) is not in the set.
_ASR_JUNK = re.compile("[０-９＜-＞＠-ｚ]")


def asr_text_has_junk(text: str) -> bool:
    """Whether recognised text carries the full-width digit/symbol junk signature of a misled prompt."""
    return bool(_ASR_JUNK.search(text or ""))


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
    # The recogniser's own confidence in the segment (Whisper verbose_json), None when the provider omits it.
    no_speech_prob: float | None = None
    avg_logprob: float | None = None
    compression_ratio: float | None = None


@dataclass(frozen=True)
class SpeechAsrResult:
    provider: str
    model: str
    language: str
    text: str
    segments: tuple[SpeechAsrSegment, ...]
    words: tuple[SpeechAsrWord, ...]
    # The audio's length as the provider reported it, else the last timed segment's end; None when unknown.
    duration_seconds: float | None = None


class SpeechAsrProvider(Protocol):
    provider_id: str

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        *,
        filename: str,
        content_type: str,
        language: str | None,
        prompt: str | None = None,
    ) -> SpeechAsrResult: ...


def _seconds_to_ms(value: Any) -> int:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
    ):
        raise SpeechAsrMalformed()
    return max(0, round(float(value) * 1000))


def _signal(value: Any) -> float | None:
    if type(value) in {int, float} and math.isfinite(value):
        return float(value)
    return None


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
                    no_speech_prob=_signal(item.get("no_speech_prob")),
                    avg_logprob=_signal(item.get("avg_logprob")),
                    compression_ratio=_signal(item.get("compression_ratio")),
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

    duration = payload.get("duration")
    if not (type(duration) in {int, float} and duration >= 0):
        ends = [segment.end_ms for segment in segments] + [word.end_ms for word in words]
        duration = max(ends) / 1000 if ends else None
    return SpeechAsrResult(
        provider=provider,
        model=model,
        language=detected_language.strip(),
        text=text.strip(),
        segments=tuple(segments),
        words=tuple(words),
        duration_seconds=float(duration) if duration is not None else None,
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
        key_source: Callable[[], str] | None = None,
    ) -> None:
        self._key_source = key_source
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

    def _bearer(self) -> str:
        """The key of this request: `key_source` (the Admin-stored key first, then the environment: D-224) when it
        answers a usable one, else the key the provider was built with. Read per request, never logged."""
        if self._key_source is not None:
            try:
                key = str(self._key_source() or "").strip()
            except Exception:  # noqa: BLE001 - an unreadable store keeps the built-in key
                key = ""
            if key and re.fullmatch(r"[!-~]+", key):
                return key
        return self._api_key

    @property
    def model(self) -> str:
        return self._model

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    def transcribe_bytes(self, *args: Any, **kwargs: Any) -> SpeechAsrResult:
        return self._metered(self._transcribe_bytes, *args, **kwargs)

    def transcribe_url(self, *args: Any, **kwargs: Any) -> SpeechAsrResult:
        return self._metered(self._transcribe_url, *args, **kwargs)

    def _metered(self, call: Callable[..., SpeechAsrResult], *args: Any, **kwargs: Any) -> SpeechAsrResult:
        """Every Groq request, from any caller, in the shared AI ledger (ai/audio_telemetry.py). I-1's backstop runs
        first: without live funding (a learner admission or SystemFunding) the request is not sent once
        FUNDING_ENFORCEMENT is `enforce` (PR-MON-6 §2)."""
        from writing_coach.billing.funding_context import require_paid

        from writing_coach.ai.spend_gate import observe

        observe()  # the system's daily AI spend monitor (D-250): it alerts, it never refuses
        require_paid(capability="speech_asr", provider=str(getattr(self, "provider_id", "") or "groq"),
                     timeout_seconds=self._timeout_seconds)   # the timeout every Groq request uses

        from writing_coach.ai.audio_telemetry import attempt_sent, provider_attempt, record_audio_operation

        started = time.perf_counter()
        with provider_attempt():
            try:
                result = call(*args, **kwargs)
            except Exception as exc:
                # billable only when the request reached the transport (empty or oversize audio never does)
                record_audio_operation("speech_asr", provider=self.provider_id, model=self.model, outcome="failure",
                                       latency_ms=int((time.perf_counter() - started) * 1000), audio_seconds=None,
                                       error=exc, billable_attempt=attempt_sent())  # fmt: skip
                raise
        record_audio_operation("speech_asr", provider=self.provider_id, model=self.model, outcome="success",
                               latency_ms=int((time.perf_counter() - started) * 1000),
                               audio_seconds=result.duration_seconds, billable_attempt=True)  # fmt: skip
        return result

    @classmethod
    def from_env(cls, key_source: Callable[[], str] | None = None) -> GroqSpeechAsrProvider | None:
        """Built when the process has a Groq key at start: `GROQ_API_KEY`, else (with `key_source`) the one saved in
        Admin. `key_source` is then read at every request, so the Admin key wins and a rotated key needs no restart; a key
        saved only after a start with none needs one (the provider does not exist yet)."""
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if key_source is not None:
            try:
                api_key = str(key_source() or "").strip() or api_key
            except Exception:  # noqa: BLE001
                pass
        if not api_key:
            return None
        return cls(
            api_key,
            key_source=key_source,
            model=os.getenv("GROQ_ASR_MODEL", "whisper-large-v3-turbo"),
            timeout_seconds=float(os.getenv("GROQ_ASR_TIMEOUT_SECONDS", "120")),
            max_bytes=int(os.getenv("GROQ_ASR_MAX_BYTES", str(24 * 1024 * 1024))),
        )

    def _transcribe_bytes(
        self,
        audio_bytes: bytes,
        *,
        filename: str,
        content_type: str,
        language: str | None,
        prompt: str | None = None,
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
        if prompt and prompt.strip():
            fields.append(("prompt", _utf8_prefix(prompt, _ASR_PROMPT_MAX_BYTES)))

        try:
            from writing_coach.ai.audio_telemetry import mark_sent

            mark_sent()   # the transport boundary: from here the request is a billable attempt
            response = self._session.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._bearer()}"},
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

    def _transcribe_url(
        self,
        audio_url: str,
        *,
        language: str | None,
        prompt: str | None = None,
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
        if prompt and prompt.strip():
            fields.append(("prompt", _utf8_prefix(prompt, _ASR_PROMPT_MAX_BYTES)))

        try:
            from writing_coach.ai.audio_telemetry import mark_sent

            mark_sent()   # the transport boundary: from here the request is a billable attempt
            response = self._session.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._bearer()}"},
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
