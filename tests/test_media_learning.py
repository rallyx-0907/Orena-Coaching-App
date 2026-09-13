from __future__ import annotations

import inspect
from dataclasses import fields
from pathlib import Path

import pytest

import writing_coach.media_learning as media_learning
from writing_coach.media_learning import (
    MediaLearningAsset,
    MediaLearningContractError,
    MediaLearningObject,
    MediaProcessingState,
    MediaTranscript,
    SegmentTranslation,
    TranscriptSegment,
)


ROOT = Path(__file__).resolve().parents[1]


def _asset(source_language: str = "en", **overrides: object) -> MediaLearningAsset:
    values: dict[str, object] = {
        "asset_id": "asset-001",
        "source_url": "https://media.example.invalid/lessons/one",
        "source_provider": "external-catalog",
        "source_type": "external-url",
        "title": "A reusable media lesson",
        "source_language": source_language,
        "processing_state": MediaProcessingState.READY,
        "duration_ms": 12_000,
        "transcript_available": True,
        "translation_available": True,
    }
    values.update(overrides)
    return MediaLearningAsset(**values)  # type: ignore[arg-type]


def _segments(text: str = "Learning from one shared transcript.") -> tuple[TranscriptSegment, ...]:
    return (
        TranscriptSegment("segment-001", 0, 0, 4_000, text),
        TranscriptSegment("segment-002", 1, 4_000, 8_000, "The next idea follows."),
    )


def _media_object(source_language: str = "en") -> MediaLearningObject:
    transcript = MediaTranscript("asset-001", source_language, _segments())
    translations = (
        SegmentTranslation("segment-001", "vi", "Hoc tu mot ban ghi dung chung."),
        SegmentTranslation("segment-002", "vi", "Y tiep theo noi tiep."),
    )
    return MediaLearningObject(_asset(source_language), transcript, translations)


def test_valid_asset_and_media_learning_object_are_immutable_shared_content() -> None:
    media_object = _media_object()

    assert media_object.asset.processing_state is MediaProcessingState.READY
    assert media_object.transcript is not None
    assert media_object.transcript.segments[0].original_text.startswith("Learning")
    assert media_object.translations[0].segment_id == "segment-001"


@pytest.mark.parametrize(
    ("overrides", "message"),
    (
        ({"asset_id": "has whitespace"}, "stable identifier"),
        ({"source_url": "not-a-url"}, "absolute HTTP"),
        ({"source_url": "https://[invalid-host"}, "absolute HTTP"),
        ({"source_url": "https://user:secret@example.invalid/media"}, "absolute HTTP"),
        ({"source_language": ""}, "explicit language tag"),
        ({"duration_ms": 0}, "positive integer"),
        ({"processing_state": "ready"}, "MediaProcessingState"),
        (
            {"transcript_available": False, "translation_available": True},
            "requires transcript availability",
        ),
    ),
)
def test_invalid_asset_identity_and_availability_states_fail(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(MediaLearningContractError, match=message):
        _asset(**overrides)


@pytest.mark.parametrize(
    ("overrides", "message"),
    (
        ({"segment_id": ""}, "stable identifier"),
        ({"order": -1}, "non-negative integer"),
        ({"start_ms": -1}, "non-negative integer"),
        ({"end_ms": 0}, "greater than start_ms"),
        ({"original_text": "  "}, "non-empty string"),
    ),
)
def test_invalid_transcript_segment_states_fail(
    overrides: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "segment_id": "segment-001",
        "order": 0,
        "start_ms": 0,
        "end_ms": 1_000,
        "original_text": "Original source text.",
    }
    values.update(overrides)

    with pytest.raises(MediaLearningContractError, match=message):
        TranscriptSegment(**values)  # type: ignore[arg-type]


def test_transcript_requires_unique_identity_and_deterministic_order() -> None:
    duplicate_identity = (
        TranscriptSegment("same-segment", 0, 0, 1_000, "One"),
        TranscriptSegment("same-segment", 1, 1_000, 2_000, "Two"),
    )
    with pytest.raises(MediaLearningContractError, match="identities must be unique"):
        MediaTranscript("asset-001", "en", duplicate_identity)

    reversed_order = (
        TranscriptSegment("segment-002", 1, 1_000, 2_000, "Two"),
        TranscriptSegment("segment-001", 0, 0, 1_000, "One"),
    )
    with pytest.raises(MediaLearningContractError, match="deterministic order"):
        MediaTranscript("asset-001", "en", reversed_order)


def test_translation_must_map_existing_segment_and_be_unique_per_language() -> None:
    transcript = MediaTranscript("asset-001", "en", _segments())

    with pytest.raises(MediaLearningContractError, match="existing transcript segment"):
        MediaLearningObject(
            _asset(),
            transcript,
            (SegmentTranslation("missing-segment", "vi", "Khong ton tai."),),
        )

    with pytest.raises(MediaLearningContractError, match="only one translation"):
        MediaLearningObject(
            _asset(),
            transcript,
            (
                SegmentTranslation("segment-001", "vi", "Ban dich mot."),
                SegmentTranslation("segment-001", "VI", "Ban dich hai."),
            ),
        )


def test_listening_and_shadowing_reuse_the_same_canonical_transcript() -> None:
    media_object = _media_object()

    listening_transcript = media_object.transcript
    shadowing_transcript = media_object.transcript

    assert listening_transcript is shadowing_transcript
    assert listening_transcript is not None
    assert listening_transcript.segments is shadowing_transcript.segments


@pytest.mark.parametrize(
    ("source_language", "original_text"),
    (
        ("en", "A shared English media lesson."),
        ("zh", "这是一个共享的中文媒体课程。"),
    ),
)
def test_english_and_chinese_use_the_same_content_contract(
    source_language: str, original_text: str
) -> None:
    segment = TranscriptSegment("segment-001", 0, 0, 1_000, original_text)
    transcript = MediaTranscript("asset-001", source_language, (segment,))
    asset = _asset(
        source_language,
        duration_ms=1_000,
        translation_available=False,
    )

    media_object = MediaLearningObject(asset, transcript)

    assert type(media_object) is MediaLearningObject
    assert media_object.transcript is transcript
    assert media_object.asset.source_language == source_language


def test_reusable_content_contract_contains_no_learner_progress_state() -> None:
    contract_fields = {
        field.name
        for contract_type in (
            MediaLearningAsset,
            TranscriptSegment,
            MediaTranscript,
            SegmentTranslation,
            MediaLearningObject,
        )
        for field in fields(contract_type)
    }

    assert contract_fields.isdisjoint(
        {
            "user_id",
            "learner_id",
            "learning_language",
            "progress",
            "completed",
            "completion_state",
            "practice_attempts",
        }
    )


def test_contract_has_no_network_ai_or_provider_specific_coupling() -> None:
    source = inspect.getsource(media_learning).casefold()

    assert "requests" not in source
    assert "httpx" not in source
    assert "writing_coach.ai" not in source
    assert "youtube" not in source
    assert "pinyin" not in source


def test_governance_records_the_shared_media_learning_direction() -> None:
    project_state = (ROOT / "docs/project/PROJECT_STATE.md").read_text(encoding="utf-8")
    handoff = (ROOT / "docs/project/archive/HANDOFF_BEFORE_PROJECT_MEMORY.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/project/ROADMAP.md").read_text(encoding="utf-8")
    boundaries = (ROOT / "docs/project/DOMAIN_BOUNDARIES.md").read_text(encoding="utf-8")
    decisions = (ROOT / "docs/project/DECISION_LOG.md").read_text(encoding="utf-8")
    normalized_state = " ".join(project_state.split()).casefold()
    normalized_handoff = " ".join(handoff.split()).casefold()

    for slice_name in ("M1.1", "M1.2", "M1.3", "M1.4", "M1.5", "M1.6"):
        assert slice_name in roadmap
    roadmap_m1 = next(
        tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
        for line in roadmap.splitlines()
        if line.lstrip().startswith("|")
        and line.strip().strip("|").split("|")[0].strip() == "M1"
    )
    assert roadmap_m1 == (
        "M1",
        "Media Learning Foundation (cross-cutting)",
        "CLOSED / FOUNDATION COMPLETE",
    )
    assert "M1 — Media Learning Foundation: **CLOSED / FOUNDATION COMPLETE**" in project_state
    assert "m1 is **closed / foundation complete**" in normalized_state
    assert "one imported media source is represented once" in normalized_state
    assert "both listening and speaking shadowing" in normalized_state
    assert "learner progress remains separate" in normalized_handoff

    assert "R2 — AI Capability Control Plane: **HUMAN GATE / READY, NOT PRODUCT-BLOCKING**" in handoff
    assert "## R2 human gate" in handoff
    assert "**YES**" in handoff
    assert "R2 — AI Capability Control Plane: **HUMAN GATE / READY, NOT PRODUCT-BLOCKING**" in project_state
    assert "m1.2 is **closed / approved / merged**" in normalized_handoff
    assert "m1.3 shared media translation is **closed / approved / merged**" in normalized_handoff
    assert "m1.4 listening mvp integration and acceptance is **closed / approved / merged**" in normalized_handoff
    assert "m1.5 active listening is **closed / approved / merged**" in normalized_handoff
    assert "pv-2 / oren-10 internal listening workspace" in normalized_handoff
    assert "pv-3 / oren-11" in normalized_handoff

    listening_row = next(
        tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
        for line in project_state.splitlines()
        if line.lstrip().startswith("|")
        and line.strip().strip("|").split("|")[0].strip().casefold() == "listening"
    )
    assert listening_row == ("Listening", "DEVELOPMENT", "available", "available", "no")
    assert "no current learner skill is public" in normalized_state
    assert "R11 remains the Listening completion and public-release-readiness gate" in roadmap
    assert "Media Learning (shared)" in boundaries
    assert "Listening, Speaking Shadowing, Vocabulary / Library, and Grammar" in boundaries
    assert "## D-014 — Shared Media Learning content" in decisions
    assert "does not make\nListening or Speaking public" in decisions
    assert "does not close R2" in decisions
