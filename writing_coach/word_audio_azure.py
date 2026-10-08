"""Azure neural text-to-speech for a word nobody has recorded (UX review LEX-010; human decision 2026-10-05).

Commons recordings come first. When none binds to the word's reading, this voice speaks it once; the word-audio
library keeps the bytes under the same (identity, reading) key, so the next learner hears the stored file and Azure
is never asked again for that reading.

Chinese is spoken from its reading, not from the characters alone: the dictionary's tone-marked pinyin becomes an
SSML `<phoneme alphabet="sapi">` with numbered tones (háng → "hang 2"), so a character with several readings
(行, 长, 了, 还, 得) is said the way this entry means it. A multi-character reading whose syllables do not match the
characters one to one is not guessed at: the word is then spoken only when it has a single reading.

Spending is capped: `WORD_TTS_SPEND_CAP_USD` (default 5) is the total for this capability over all time, read from
the AI ledger (the same `ai.operation` rows the cost report shows). At the cap - or with the ledger unreadable - the
voice answers nothing and says so (`last_failed`), so the surface can fall back to the device's own voice.

Every call is recorded in the ledger as `word_tts`, priced at Azure's list rate per character (to be checked against
the bill, like the pronunciation rate).
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from collections.abc import Callable
from xml.sax.saxutils import escape, quoteattr

from writing_coach.word_audio import MAX_AUDIO_BYTES, REQUEST_TIMEOUT, USER_AGENT, Spoken

_log = logging.getLogger(__name__)

CAPABILITY = "word_tts"
PROVIDER = "azure-speech"
MODEL = "neural-tts"
# Azure neural TTS list price, USD per 1,000,000 billed characters (read 2026-10-05; to be checked against the bill).
PER_MILLION_CHARACTERS = 16.0
DEFAULT_CAP_USD = 5.0
VOICES = {"en": ("en-US", "en-US-JennyNeural"), "zh": ("zh-CN", "zh-CN-XiaoxiaoNeural")}
OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"

_TONE_MARKS = {
    "ā": ("a", 1), "á": ("a", 2), "ǎ": ("a", 3), "à": ("a", 4),
    "ē": ("e", 1), "é": ("e", 2), "ě": ("e", 3), "è": ("e", 4),
    "ī": ("i", 1), "í": ("i", 2), "ǐ": ("i", 3), "ì": ("i", 4),
    "ō": ("o", 1), "ó": ("o", 2), "ǒ": ("o", 3), "ò": ("o", 4),
    "ū": ("u", 1), "ú": ("u", 2), "ǔ": ("u", 3), "ù": ("u", 4),
    "ǖ": ("v", 1), "ǘ": ("v", 2), "ǚ": ("v", 3), "ǜ": ("v", 4), "ü": ("v", 0),
}
_HAN = re.compile(r"[㐀-鿿豈-﫿]")
_SYLLABLE = re.compile(r"^[a-zv]+[1-5]$")


def sapi_pinyin(reading: str) -> str:
    """Tone-marked pinyin ("huā shēng") → Microsoft's numbered-tone pinyin ("hua 1 sheng 1"); '' if unreadable.

    Syllables are the reading's own space-separated parts; a syllable without a tone mark is the neutral tone (5).
    Numbered input ("hua1 sheng1") is accepted too."""

    parts = [part for part in re.split(r"[\s'·-]+", unicodedata.normalize("NFC", str(reading or "").strip().lower())) if part]
    syllables: list[str] = []
    for part in parts:
        numbered = re.fullmatch(r"([a-zü]+)([1-5])", part)
        if numbered:
            syllables.append(f"{numbered.group(1).replace('ü', 'v')} {numbered.group(2)}")
            continue
        tone = 5
        letters = []
        for ch in part:
            if ch in _TONE_MARKS:
                base, mark = _TONE_MARKS[ch]
                letters.append(base)
                if mark:
                    tone = mark
            elif "a" <= ch <= "z":
                letters.append(ch)
            else:
                return ""
        syllable = "".join(letters)
        if not syllable:
            return ""
        syllables.append(f"{syllable} {tone}")
    return " ".join(syllables)


def ssml_for(term: str, language: str, reading: str) -> str | None:
    """The SSML that says `term` at `reading`, or None when the reading cannot be given to the voice faithfully."""

    locale, voice = VOICES.get(language, VOICES["en"])
    text = escape(term)
    if language == "zh" and reading:
        phonemes = sapi_pinyin(reading)
        han = _HAN.findall(term)
        if not phonemes or (han and len(phonemes.split(" ")) // 2 != len(han)):
            return None
        text = f"<phoneme alphabet=\"sapi\" ph={quoteattr(phonemes)}>{escape(term)}</phoneme>"
    return (
        f"<speak version=\"1.0\" xmlns=\"http://www.w3.org/2001/10/synthesis\" xml:lang={quoteattr(locale)}>"
        f"<voice name={quoteattr(voice)}>{text}</voice></speak>"
    )


def billed_characters(term: str) -> int:
    """Azure counts a Chinese character as two; markup in the request is not billed."""

    return sum(2 if _HAN.match(ch) else 1 for ch in term)


class AzureVoice:
    name = "azure"

    def __init__(
        self,
        *,
        key: str | None = None,
        region: str | None = None,
        post: Callable[[str, bytes, dict[str, str]], bytes] | None = None,
        spent: Callable[[], float] | None = None,
        record: Callable[[dict], None] | None = None,
        cap_usd: float | None = None,
    ) -> None:
        if key is None or region is None:
            key, region = _credentials()
        self._key = str(key or "").strip()
        self._region = str(region or "").strip().lower()
        self._post = post or self._request
        self._spent = spent or _ledger_spent
        self._record = record or _record_operation
        cap = cap_usd if cap_usd is not None else os.getenv("WORD_TTS_SPEND_CAP_USD", "")
        try:
            self._cap = float(cap) if str(cap).strip() else DEFAULT_CAP_USD
        except ValueError:
            self._cap = DEFAULT_CAP_USD
        self._state = threading.local()

    @property
    def configured(self) -> bool:
        return bool(self._key) and bool(re.fullmatch(r"[a-z0-9]{2,40}", self._region or ""))

    @property
    def last_failed(self) -> bool:
        """True when this voice was asked on this thread and could not answer (error, offline, cap)."""

        return bool(getattr(self._state, "failed", False))

    def _request(self, url: str, body: bytes, headers: dict[str, str]) -> bytes:
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:  # noqa: S310 - fixed Azure host
            return response.read(MAX_AUDIO_BYTES + 1)

    def speak(self, *, term: str, language: str, reading: str, single_reading: bool) -> Spoken | None:
        self._state.failed = False
        if not self.configured:
            return None
        if language != "zh" and not single_reading:
            return None  # an English word with several readings: no phoneme set is wired for it, so no guess
        ssml = ssml_for(term, language, reading if language == "zh" else "")
        if ssml is None:
            if not single_reading:
                return None  # a reading the voice cannot be told: no guess
            ssml = ssml_for(term, language, "")
        try:
            spent = float(self._spent())
        except Exception:  # noqa: BLE001 - an unreadable ledger is a closed cap, never "nothing spent"
            _log.warning("word TTS: spend ledger unreadable; not synthesising")
            self._state.failed = True
            return None
        if spent >= self._cap:
            _log.warning("word TTS: spend cap reached (%.4f of %.2f USD)", spent, self._cap)
            self._state.failed = True
            return None
        url = f"https://{self._region}.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": self._key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": OUTPUT_FORMAT,
            "User-Agent": USER_AGENT,
        }
        started = time.monotonic()
        try:
            audio = self._post(url, ssml.encode("utf-8"), headers)
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError, TimeoutError) as error:
            _log.info("word TTS unavailable: %s", type(error).__name__)
            self._state.failed = True
            self._record(_event("provider_error", None, int((time.monotonic() - started) * 1000), type(error).__name__))
            return None
        latency = int((time.monotonic() - started) * 1000)
        if not audio or len(audio) > MAX_AUDIO_BYTES:
            self._state.failed = True
            self._record(_event("provider_error", None, latency, "empty_audio"))
            return None
        self._record(_event("success", billed_characters(term), latency, None))
        return Spoken(
            audio=audio,
            media_type="audio/mpeg",
            source="azure-tts",
            # Generated, not licensed: there is no author to credit, and a surface says it is a synthesized voice.
            licence="generated",
            attribution="Azure neural voice (generated)",
            voice=VOICES.get(language, VOICES["en"])[1],
        )


def _event(outcome: str, characters: int | None, latency_ms: int, error_class: str | None) -> dict:
    cost = (
        {"state": "estimated", "currency": "USD", "amount": round(characters * PER_MILLION_CHARACTERS / 1_000_000, 8),
         "provenance": {"provider": PROVIDER, "model": MODEL, "per_million_characters": PER_MILLION_CHARACTERS,
                        "characters": characters}}
        if outcome == "success" and characters is not None
        else {"state": "unknown", "currency": None, "amount": None,
              "provenance": {"provider": PROVIDER, "model": MODEL, "reason": "request_failed"}}
    )  # fmt: skip
    return {
        "capability": CAPABILITY, "origin": "learner", "provider": PROVIDER, "model": MODEL, "model_redacted": False,
        "outcome": outcome, "error_class": (error_class or "")[:80] or None, "latency_ms": latency_ms,
        "usage": {"characters": characters} if characters is not None else {}, "rate_limit": {}, "cost": cost,
        "quota_available": "unknown",
    }  # fmt: skip


def _record_operation(event: dict) -> None:
    try:
        from writing_coach.ai.platform import _persist_operation_telemetry

        _persist_operation_telemetry(event)
    except Exception:  # noqa: BLE001 - telemetry never costs the learner the audio
        _log.warning("word TTS telemetry not recorded", exc_info=True)


def _ledger_spent() -> float:
    from writing_coach.ai.platform import _installed_platform_repository

    return float(_installed_platform_repository().ai_spend_for_capability(CAPABILITY))


def _credentials() -> tuple[str, str]:
    """The same Azure Speech key the pronunciation check uses: a stored credential first, else the environment."""

    key = os.getenv("AZURE_SPEECH_KEY", "").strip()
    region = os.getenv("AZURE_SPEECH_REGION", "").strip()
    try:
        from writing_coach.ai.azure import speech_region
        from writing_coach.ai.platform import _stored_provider_credentials

        stored = _stored_provider_credentials("azure-speech")
        if stored:
            key, region = stored["api_key"], speech_region(stored["base_url"])
    except Exception:  # noqa: BLE001 - an unreadable stored credential leaves the environment's
        pass
    return key, region
