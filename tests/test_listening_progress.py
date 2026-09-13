from __future__ import annotations

from fastapi import HTTPException

from writing_coach.listening_api import (
    ListeningProgressIn,
    ShadowingProgressIn,
    configure_listening_progress,
    list_listening_progress,
    list_shadowing_progress,
    save_listening_progress,
    save_shadowing_progress,
)


def test_list_route_is_learner_scoped_and_asset_bounded() -> None:
    class FakeRepository:
        def __init__(self) -> None:
            self.asset = None

        def list_listening_progress_records(self, asset_id: str) -> list[dict]:
            self.asset = asset_id
            return [{"asset_id": asset_id, "segment_id": "segment-1", "presentation": "checked"}]

    repository = FakeRepository()
    configure_listening_progress(repository)
    try:
        result = list_listening_progress(" asset-en ")
        assert repository.asset == "asset-en"
        assert result["items"][0]["asset_id"] == "asset-en"
    finally:
        configure_listening_progress(None)


def test_save_route_forwards_only_bounded_audio_free_progress() -> None:
    class FakeRepository:
        def __init__(self) -> None:
            self.values = None

        def save_listening_progress_record(self, values: dict) -> dict:
            self.values = values
            return {"asset_id": values["asset_id"], "segment_id": values["segment_id"]}

    repository = FakeRepository()
    configure_listening_progress(repository)
    try:
        result = save_listening_progress(ListeningProgressIn(
            asset_id="asset-zh", segment_id="segment-zh-1", presentation="revealed",
            revealed=False, checked_attempt_count=2, best_accuracy_percent=91,
            best_exact=False, last_answer="这是共享的原文字幕。",
        ))
        assert result["item"] == {"asset_id": "asset-zh", "segment_id": "segment-zh-1"}
        assert repository.values["revealed"] is True
        assert repository.values["presentation"] == "revealed"
        assert "audio" not in repository.values
        assert "proficiency" not in repository.values
    finally:
        configure_listening_progress(None)


def test_unconfigured_progress_is_canonical_and_truthful() -> None:
    configure_listening_progress(None)
    try:
        list_listening_progress("asset-en")
    except HTTPException as raised:
        detail = raised.detail
    else:
        raise AssertionError("unconfigured progress must fail closed")
    assert detail["category"] == "listening_progress_unconfigured"
    assert "audio" not in str(detail).lower()


def test_shadowing_progress_is_distinct_and_audio_free() -> None:
    class FakeRepository:
        def __init__(self) -> None:
            self.values = None

        def save_shadowing_progress_record(self, values: dict) -> dict:
            self.values = values
            return {"asset_id": values["asset_id"], "segment_id": values["segment_id"], "completed_rounds": values["completed_rounds"]}

        def list_shadowing_progress_records(self, asset_id: str) -> list[dict]:
            return [{"asset_id": asset_id, "segment_id": "segment-1", "completed_rounds": 2}]

    repository = FakeRepository()
    configure_listening_progress(repository)
    try:
        saved = save_shadowing_progress(ShadowingProgressIn(
            asset_id="asset-en", segment_id="segment-1", completed_rounds=2,
        ))
        assert saved["item"]["completed_rounds"] == 2
        assert repository.values["completed_rounds"] == 2
        assert "audio" not in repository.values
        assert "proficiency" not in repository.values
        assert list_shadowing_progress(" asset-en ")["items"][0]["completed_rounds"] == 2
    finally:
        configure_listening_progress(None)
