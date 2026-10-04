"""Voice interfaces (spec §33, contract §9): shapes only, no vendor."""

from __future__ import annotations

import pytest

from writing_coach.agent import voice
from writing_coach.agent.errors import ERROR_KINDS, VoiceUnavailable
from writing_coach.speech_asr import GroqSpeechAsrProvider, SpeechAsrProvider
from writing_coach.word_audio import Voice


def test_existing_adapters_are_reused_not_redefined():
    assert voice.SpeechRecognitionProvider is SpeechAsrProvider
    assert voice.ReferencePronunciationProvider is Voice
    assert callable(GroqSpeechAsrProvider.transcribe_bytes)


def test_a_failed_voice_session_continues_in_text_never_another_vendor():
    assert voice.VOICE_FAILURE_FALLBACK == "text_only"
    assert ERROR_KINDS[VoiceUnavailable.error_class].fallback == "text_only"


def test_the_ephemeral_token_never_prints():
    connect = voice.VoiceConnect(url="wss://example.invalid/s", ephemeral_token="secret-token", expires_at="2026-09-27T12:15:00Z")
    handle = voice.SessionHandle(voice_session_id="v1", mode="s2s", transport="websocket", connect=connect)
    assert "secret-token" not in repr(handle)


def test_audio_chunks_use_the_contract_format():
    assert voice.AudioChunk(index=0, data=b"\x00\x01").format == "pcm16_24k"
    with pytest.raises(ValueError):
        voice.AudioChunk(index=0, data=b"", format="mp3")
    assert "\\x00" not in repr(voice.AudioChunk(index=0, data=b"\x00"))


def test_session_protocol_names_the_spec_operations():
    for method in ("open", "push_text_segments", "interrupt", "close"):
        assert hasattr(voice.ConversationalSpeechSession, method)
    for method in ("get", "put"):
        assert hasattr(voice.PrerenderedSpeechCache, method)
