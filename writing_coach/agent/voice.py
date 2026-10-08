"""Voice interfaces for Orena Intelligence (spec §33, contract §9). Interfaces only.

Voice is not a dependency of the agent core: a voice session delegates to the
same turn and tools, and every action still reaches the client as a contract
event. No vendor is wired here. Live speech-to-speech, TTS, ephemeral tokens
and any new SDK wait for the human's credential decision (2026-09-27 ruling);
the adapters will route through `writing_coach.ai` under the
`CONVERSATIONAL_SPEECH` and `TEXT_TO_SPEECH` operations.

When a speech-to-speech session fails, the conversation continues in text
(`error.fallback = "text_only"`). It never cascades to another vendor
(ARCHITECTURE_INVARIANTS: no provider-to-provider fallback). A cascade session
is a mode the server may open deliberately, not a rescue for a failed one.

Recognition and reference audio already exist and are reused as they are:
`speech_asr.SpeechAsrProvider` and `word_audio.Voice`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

from writing_coach.agent.contract import AUDIO_FORMATS
from writing_coach.agent.locale import InternalLocale
from writing_coach.agent.schemas import CoachNote
from writing_coach.speech_asr import SpeechAsrProvider
from writing_coach.word_audio import Voice

SessionMode = Literal["s2s", "cascade"]
Transport = Literal["webrtc", "websocket"]
VOICE_FAILURE_FALLBACK = "text_only"

# The existing adapters, under the names the spec gives their roles.
SpeechRecognitionProvider = SpeechAsrProvider
ReferencePronunciationProvider = Voice


@dataclass(frozen=True)
class SpeakerProfile:
    """Orena's one voice, per vendor: pre-rendered and live speech sound alike."""

    profile_id: str
    vendor_voice_map: Mapping[str, str]


@dataclass(frozen=True)
class VoiceConnect:
    """What the client connects with. The token is short-lived and never a key."""

    url: str
    ephemeral_token: str = field(repr=False)
    expires_at: str


@dataclass(frozen=True)
class SessionHandle:
    voice_session_id: str
    mode: SessionMode
    transport: Transport
    connect: VoiceConnect


@dataclass(frozen=True)
class AudioChunk:
    index: int
    data: bytes = field(repr=False)
    format: str = "pcm16_24k"

    def __post_init__(self) -> None:
        if self.format not in AUDIO_FORMATS:
            raise ValueError(f"unknown audio format {self.format!r}")


@dataclass(frozen=True)
class VoiceUsage:
    audio_seconds_in: float = 0.0
    audio_seconds_out: float = 0.0
    interruptions: int = 0


@dataclass(frozen=True)
class TextSegment:
    lang: str
    text: str
    voice_style: str


Delegate = Callable[[str], None]


class ConversationalSpeechSession(Protocol):
    """One capped voice session (contract §9: 15 minutes by default)."""

    mode: SessionMode

    def open(
        self,
        speaker_profile: SpeakerProfile,
        locale: InternalLocale,
        instructions: str,
        coach_notes: Sequence[CoachNote],
        on_delegation: Delegate,
    ) -> SessionHandle: ...

    def push_text_segments(self, segments: Sequence[TextSegment]) -> AsyncIterator[AudioChunk]: ...

    def interrupt(self) -> None: ...

    def close(self) -> VoiceUsage: ...


class PrerenderedSpeechCache(Protocol):
    """Short lines rendered ahead in Orena's voice (`TEXT_TO_SPEECH`)."""

    def get(self, *, text: str, lang: str, voice_style: str) -> AudioChunk | None: ...

    def put(self, *, text: str, lang: str, voice_style: str, audio: AudioChunk) -> None: ...
