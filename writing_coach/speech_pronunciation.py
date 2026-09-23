"""Provider-neutral pronunciation assessment with an Azure Speech adapter."""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import requests


class SpeechPronunciationError(Exception):
    pass


class SpeechPronunciationTimedOut(SpeechPronunciationError):
    pass


class SpeechPronunciationRequestFailed(SpeechPronunciationError):
    def __init__(self, status_code: int | None = None, provider_message: str = "") -> None:
        super().__init__(provider_message or "Pronunciation provider request failed.")
        self.status_code = status_code
        self.provider_message = provider_message


class SpeechPronunciationMalformed(SpeechPronunciationError):
    pass


class SpeechPronunciationPayloadTooLarge(SpeechPronunciationError):
    pass


class SpeechPronunciationConversionFailed(SpeechPronunciationError):
    pass


class SpeechPronunciationNoSpeech(SpeechPronunciationError):
    """The provider heard no speech in the take: a learner outcome, not a failure."""


@dataclass(frozen=True)
class PronunciationPhoneme:
    phoneme: str
    accuracy_score: float | None


@dataclass(frozen=True)
class PronunciationSyllable:
    """A syllable of the reference as the provider labels it (for zh-CN, the
    pinyin of the reference with its tone digit). The label is what was
    expected, never a measurement of the tone the learner produced."""

    syllable: str
    accuracy_score: float | None


@dataclass(frozen=True)
class PronunciationWord:
    word: str
    accuracy_score: float | None
    # The provider's own miscue verdict ("None", "Mispronunciation",
    # "Omission", "Insertion", ...). Orena sets no threshold of its own.
    error_type: str
    phonemes: tuple[PronunciationPhoneme, ...]
    syllables: tuple[PronunciationSyllable, ...] = ()
    # Where the word sits in the take; absent for a word that was not said.
    offset_ms: int | None = None
    duration_ms: int | None = None


@dataclass(frozen=True)
class SpeechPronunciationResult:
    """One provider-neutral assessment. ``score_kind`` is ``measured`` for an
    acoustic measurement and ``synthetic_demo`` for the development stand-in,
    which a learner surface never draws as a score."""

    provider: str
    score_kind: str
    locale: str
    recognized_text: str
    pron_score: float | None
    accuracy_score: float | None
    fluency_score: float | None
    completeness_score: float | None
    prosody_score: float | None
    words: tuple[PronunciationWord, ...]


class SpeechPronunciationProvider(Protocol):
    provider_id: str

    @property
    def max_bytes(self) -> int: ...

    @property
    def max_reference_chars(self) -> int: ...

    def assess_bytes(
        self,
        audio_bytes: bytes,
        *,
        filename: str,
        content_type: str,
        language: str,
        reference_text: str,
    ) -> SpeechPronunciationResult: ...


def normalize_audio_to_pcm16_wav(
    audio_bytes: bytes,
    *,
    timeout_seconds: float = 20.0,
    max_duration_seconds: int = 60,
) -> bytes:
    if not audio_bytes:
        raise SpeechPronunciationMalformed()
    if timeout_seconds <= 0 or max_duration_seconds <= 0:
        raise ValueError("Audio normalization limits must be positive.")

    try:
        with tempfile.TemporaryDirectory(prefix="orena-pronunciation-") as tmp:
            input_path = Path(tmp) / "input.audio"
            output_path = Path(tmp) / "output.wav"
            input_path.write_bytes(audio_bytes)
            completed = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-nostdin",
                    "-y",
                    "-i",
                    str(input_path),
                    "-t",
                    str(max_duration_seconds),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-c:a",
                    "pcm_s16le",
                    str(output_path),
                ],
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
            if completed.returncode != 0 or not output_path.is_file():
                raise SpeechPronunciationConversionFailed()
            normalized = output_path.read_bytes()
    except subprocess.TimeoutExpired as exc:
        raise SpeechPronunciationTimedOut() from exc
    except FileNotFoundError as exc:
        raise SpeechPronunciationConversionFailed() from exc

    if len(normalized) < 44 or normalized[:4] != b"RIFF" or normalized[8:12] != b"WAVE":
        raise SpeechPronunciationConversionFailed()
    return normalized


def _score(mapping: dict[str, Any], key: str) -> float | None:
    value = mapping.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return round(max(0.0, min(100.0, float(value))), 1)


# Azure reports offsets and durations in 100-nanosecond ticks.
_TICKS_PER_MS = 10_000


def _ticks_ms(value: Any) -> int | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        return None
    return int(round(float(value) / _TICKS_PER_MS))


_NO_SPEECH_STATUSES = frozenset({"nomatch", "initialsilencetimeout", "babbletimeout"})


def _assessment(mapping: dict[str, Any]) -> dict[str, Any]:
    nested = mapping.get("PronunciationAssessment")
    if isinstance(nested, dict):
        return nested
    return mapping


class AzureSpeechPronunciationProvider:
    provider_id = "azure-speech"
    _REGION_RE = re.compile(r"^[a-z0-9-]+$")

    def __init__(
        self,
        api_key: str,
        region: str,
        *,
        en_locale: str = "en-US",
        zh_locale: str = "zh-CN",
        enable_prosody: bool = False,
        timeout_seconds: float = 30.0,
        max_bytes: int = 8 * 1024 * 1024,
        max_reference_chars: int = 1200,
        normalizer: Callable[..., bytes] = normalize_audio_to_pcm16_wav,
        session: requests.Session | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Azure Speech key is required.")
        normalized_region = str(region or "").strip().lower()
        if not self._REGION_RE.fullmatch(normalized_region):
            raise ValueError("Azure Speech region is invalid.")
        if timeout_seconds <= 0 or max_bytes <= 0 or max_reference_chars <= 0:
            raise ValueError("Azure pronunciation limits must be positive.")
        self._api_key = api_key.strip()
        self._region = normalized_region
        self._en_locale = str(en_locale or "en-US").strip() or "en-US"
        self._zh_locale = str(zh_locale or "zh-CN").strip() or "zh-CN"
        self._enable_prosody = bool(enable_prosody)
        self._timeout_seconds = float(timeout_seconds)
        self._max_bytes = int(max_bytes)
        self._max_reference_chars = int(max_reference_chars)
        self._normalizer = normalizer
        self._session = session or requests.Session()

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    @property
    def max_reference_chars(self) -> int:
        return self._max_reference_chars

    @classmethod
    def from_env(cls) -> "AzureSpeechPronunciationProvider | None":
        api_key = os.getenv("AZURE_SPEECH_KEY", "").strip()
        region = os.getenv("AZURE_SPEECH_REGION", "").strip()
        if not api_key or not region:
            return None
        return cls(
            api_key,
            region,
            en_locale=os.getenv("AZURE_PRONUNCIATION_EN_LOCALE", "en-US"),
            zh_locale=os.getenv("AZURE_PRONUNCIATION_ZH_LOCALE", "zh-CN"),
            enable_prosody=os.getenv(
                "AZURE_PRONUNCIATION_ENABLE_PROSODY", "false"
            ).strip().casefold() in {"1", "true", "yes", "on"},
            timeout_seconds=float(os.getenv("AZURE_PRONUNCIATION_TIMEOUT_SECONDS", "30")),
            max_bytes=int(os.getenv("AZURE_PRONUNCIATION_MAX_BYTES", str(8 * 1024 * 1024))),
            max_reference_chars=int(os.getenv("AZURE_PRONUNCIATION_MAX_REFERENCE_CHARS", "1200")),
        )

    def _locale(self, language: str) -> str:
        if language == "en":
            return self._en_locale
        if language == "zh":
            return self._zh_locale
        raise SpeechPronunciationMalformed()

    def assess_bytes(
        self,
        audio_bytes: bytes,
        *,
        filename: str,
        content_type: str,
        language: str,
        reference_text: str,
    ) -> SpeechPronunciationResult:
        del filename, content_type
        if not audio_bytes:
            raise SpeechPronunciationMalformed()
        if len(audio_bytes) > self._max_bytes:
            raise SpeechPronunciationPayloadTooLarge()

        reference = str(reference_text or "").strip()
        if not reference or len(reference) > self._max_reference_chars:
            raise SpeechPronunciationMalformed()

        locale = self._locale(language)
        normalized = self._normalizer(
            audio_bytes,
            timeout_seconds=min(self._timeout_seconds, 20.0),
        )

        config: dict[str, Any] = {
            "ReferenceText": reference,
            "GradingSystem": "HundredMark",
            "Granularity": "Phoneme",
            "Dimension": "Comprehensive",
            "EnableMiscue": True,
        }
        if locale.casefold() == "en-us" and self._enable_prosody:
            config["EnableProsodyAssessment"] = True

        pronunciation_header = base64.b64encode(
            json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")

        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key,
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
            "Accept": "application/json",
            "Pronunciation-Assessment": pronunciation_header,
        }
        if locale.casefold() == "en-us" and self._enable_prosody:
            headers["EnableProsodyAssessment"] = "True"

        try:
            response = self._session.post(
                f"https://{self._region}.stt.speech.microsoft.com/"
                "speech/recognition/conversation/cognitiveservices/v1",
                params={"language": locale, "format": "detailed"},
                headers=headers,
                data=normalized,
                timeout=self._timeout_seconds,
            )
        except requests.Timeout as exc:
            raise SpeechPronunciationTimedOut() from exc
        except requests.RequestException as exc:
            raise SpeechPronunciationRequestFailed() from exc

        if response.status_code == 413:
            raise SpeechPronunciationPayloadTooLarge()
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
                    elif isinstance(error_payload.get("message"), str):
                        provider_message = str(error_payload.get("message") or "")
            except ValueError:
                provider_message = ""
            raise SpeechPronunciationRequestFailed(
                status_code=response.status_code,
                provider_message=provider_message[:500],
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise SpeechPronunciationMalformed() from exc
        if not isinstance(payload, dict):
            raise SpeechPronunciationMalformed()
        status = str(payload.get("RecognitionStatus") or "").strip().casefold()
        if status in _NO_SPEECH_STATUSES:
            raise SpeechPronunciationNoSpeech()

        nbest = payload.get("NBest")
        if not isinstance(nbest, list) or not nbest or not isinstance(nbest[0], dict):
            raise SpeechPronunciationMalformed()
        best = nbest[0]
        overall = _assessment(best)

        accuracy_score = _score(overall, "AccuracyScore")
        fluency_score = _score(overall, "FluencyScore")
        completeness_score = _score(overall, "CompletenessScore")
        pron_score = _score(overall, "PronScore")
        prosody_score = _score(overall, "ProsodyScore")
        if all(
            value is None
            for value in (
                accuracy_score,
                fluency_score,
                completeness_score,
                pron_score,
                prosody_score,
            )
        ):
            raise SpeechPronunciationMalformed()

        words: list[PronunciationWord] = []
        raw_words = best.get("Words")
        if isinstance(raw_words, list):
            for item in raw_words:
                if not isinstance(item, dict):
                    continue
                word = str(item.get("Word") or "").strip()
                if not word:
                    continue
                assessment = _assessment(item)
                accuracy = _score(assessment, "AccuracyScore")
                error_type = str(
                    assessment.get("ErrorType")
                    or item.get("ErrorType")
                    or "None"
                ).strip() or "None"
                phonemes: list[PronunciationPhoneme] = []
                raw_phonemes = item.get("Phonemes")
                if isinstance(raw_phonemes, list):
                    for phoneme_item in raw_phonemes:
                        if not isinstance(phoneme_item, dict):
                            continue
                        phoneme = str(phoneme_item.get("Phoneme") or "").strip()
                        if not phoneme:
                            continue
                        phoneme_assessment = _assessment(phoneme_item)
                        phonemes.append(
                            PronunciationPhoneme(
                                phoneme=phoneme,
                                accuracy_score=_score(phoneme_assessment, "AccuracyScore"),
                            )
                        )
                syllables: list[PronunciationSyllable] = []
                raw_syllables = item.get("Syllables")
                if isinstance(raw_syllables, list):
                    for syllable_item in raw_syllables:
                        if not isinstance(syllable_item, dict):
                            continue
                        label = str(syllable_item.get("Syllable") or "").strip()
                        if not label:
                            continue
                        syllables.append(
                            PronunciationSyllable(
                                syllable=label,
                                accuracy_score=_score(_assessment(syllable_item), "AccuracyScore"),
                            )
                        )
                said = error_type.casefold() != "omission"
                words.append(
                    PronunciationWord(
                        word=word,
                        accuracy_score=accuracy,
                        error_type=error_type,
                        phonemes=tuple(phonemes),
                        syllables=tuple(syllables),
                        offset_ms=_ticks_ms(item.get("Offset")) if said else None,
                        duration_ms=_ticks_ms(item.get("Duration")) if said else None,
                    )
                )

        recognized_text = str(
            best.get("Display")
            or payload.get("DisplayText")
            or best.get("Lexical")
            or ""
        ).strip()

        return SpeechPronunciationResult(
            provider=self.provider_id,
            score_kind="measured",
            locale=locale,
            recognized_text=recognized_text,
            pron_score=pron_score,
            accuracy_score=accuracy_score,
            fluency_score=fluency_score,
            completeness_score=completeness_score,
            prosody_score=prosody_score,
            words=tuple(words),
        )

class DemoPronunciationProvider:
    provider_id = "demo-synthetic"

    def __init__(
        self,
        *,
        max_bytes: int = 8 * 1024 * 1024,
        max_reference_chars: int = 1200,
    ) -> None:
        self._max_bytes = int(max_bytes)
        self._max_reference_chars = int(max_reference_chars)

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    @property
    def max_reference_chars(self) -> int:
        return self._max_reference_chars

    def assess_bytes(
        self,
        audio_bytes: bytes,
        *,
        filename: str,
        content_type: str,
        language: str,
        reference_text: str,
    ) -> SpeechPronunciationResult:
        del filename, content_type
        if not audio_bytes:
            raise SpeechPronunciationMalformed()
        if len(audio_bytes) > self._max_bytes:
            raise SpeechPronunciationPayloadTooLarge()

        reference = str(reference_text or "").strip()
        if not reference or len(reference) > self._max_reference_chars:
            raise SpeechPronunciationMalformed()
        if language not in {"en", "zh"}:
            raise SpeechPronunciationMalformed()

        if language == "zh":
            tokens = re.findall(r"[\u3400-\u9fff]", reference)
            locale = "zh-CN"
        else:
            tokens = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", reference)
            locale = "en-US"

        words: list[PronunciationWord] = []
        for index, token in enumerate(tokens[:16]):
            # Deterministic display-only variation; not acoustic scoring.
            score = float(62 + ((sum(ord(ch) for ch in token) + index * 11) % 34))
            words.append(
                PronunciationWord(
                    word=token,
                    accuracy_score=score,
                    error_type="SyntheticDemo",
                    phonemes=(),
                )
            )

        return SpeechPronunciationResult(
            provider=self.provider_id,
            score_kind="synthetic_demo",
            locale=locale,
            recognized_text=reference,
            pron_score=76.0,
            accuracy_score=74.0,
            fluency_score=78.0,
            completeness_score=100.0,
            prosody_score=None,
            words=tuple(words),
        )


def build_speech_pronunciation_provider() -> SpeechPronunciationProvider | None:
    """The one place a pronunciation provider is chosen.

    ``PRONUNCIATION_PROVIDER`` names it (``azure``, ``demo``, ``none``). Unset,
    Azure is used when its key and region are configured and nothing otherwise:
    an unconfigured runtime says so rather than serving synthetic scores (D-066,
    no fake pronunciation result). A second provider (for example a
    Mandarin-tone specialist) is one more branch here and one more class
    implementing ``SpeechPronunciationProvider``; no learner surface changes.
    """
    app_env = os.getenv("APP_ENV", "development").strip().casefold()
    configured = os.getenv("PRONUNCIATION_PROVIDER", "").strip().casefold()
    azure_ready = bool(
        os.getenv("AZURE_SPEECH_KEY", "").strip() and os.getenv("AZURE_SPEECH_REGION", "").strip()
    )
    mode = configured or ("azure" if azure_ready else "none")

    if mode in {"", "none", "off", "disabled"}:
        return None
    if mode in {"demo", "synthetic", "demo-synthetic"}:
        # Fail closed: synthetic scores are never served in production.
        if app_env not in {"development", "test"}:
            return None
        return DemoPronunciationProvider(
            max_bytes=int(
                os.getenv("DEMO_PRONUNCIATION_MAX_BYTES", str(8 * 1024 * 1024))
            ),
            max_reference_chars=int(
                os.getenv("DEMO_PRONUNCIATION_MAX_REFERENCE_CHARS", "1200")
            ),
        )
    if mode == "azure":
        return AzureSpeechPronunciationProvider.from_env()
    raise ValueError(f"Unsupported PRONUNCIATION_PROVIDER: {mode}")
