"""Turn request (contract §3) and the language codes at the agent's edge."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from writing_coach.agent import locale
from writing_coach.agent.schemas import TurnRequest


def request(**overrides):
    body = {
        "contract_version": 1,
        "message": "Tại sao tôi cứ sai từ này?",
        "client": {
            "ui_version": "next-1",
            "supported_actions": ["navigate", "play_model", "save_word"],
            "supported_intents": ["vocabulary.review_due", "speaking.workspace"],
        },
        "context": {
            "surface": "speaking.workspace",
            "activity_type": "pronunciation_practice",
            "locale": {"interface": "vi", "support": "vi", "target": "zh-CN", "content": "zh-CN"},
            "attempt_id": "att-1",
            "selected_item": {"type": "word", "id": "w1", "text": "我"},
        },
        "coach_notes": [
            {
                "id": "n1",
                "kind": "preference",
                "text": "Giải thích ngắn.",
                "weight": 0.7,
                "last_reinforced": "2026-09-27T08:00:00Z",
                "expires_at": None,
            }
        ],
    }
    for key, value in overrides.items():
        body[key] = value
    return body


def test_the_contract_example_is_accepted():
    turn = TurnRequest.model_validate(request())
    assert turn.version == 1
    assert turn.context.known_surface == "speaking.workspace"
    assert turn.context.locale.internal().target == "zh"


@pytest.mark.parametrize("target, internal", [("en", "en"), ("zh-CN", "zh")])
def test_both_first_class_targets_map_to_the_backend_codes(target, internal):
    body = request()
    body["context"]["locale"].update(target=target, content=target)
    assert TurnRequest.model_validate(body).context.locale.internal().target == internal


def test_chinese_is_zh_cn_only():
    body = request()
    body["context"]["locale"]["target"] = "zh"
    with pytest.raises(ValidationError):
        TurnRequest.model_validate(body)
    body["context"]["locale"]["target"] = "zh-TW"
    with pytest.raises(ValidationError):
        TurnRequest.model_validate(body)


def test_each_layer_is_checked_against_its_own_registry():
    body = request()
    body["context"]["locale"]["interface"] = "ja"  # a support language, not an interface one
    with pytest.raises(ValidationError):
        TurnRequest.model_validate(body)
    body = request()
    body["context"]["locale"]["support"] = "ja"  # Orena explains in Japanese
    assert TurnRequest.model_validate(body).context.locale.support == "ja"
    body["context"]["locale"]["target"] = "ja"  # but does not teach it
    with pytest.raises(ValidationError):
        TurnRequest.model_validate(body)


def test_layer_sets_come_from_the_registries():
    assert locale.target_languages() == {"en", "zh-CN"}
    assert locale.interface_languages() == {"en", "vi", "zh-CN"}
    assert {"en", "vi", "zh-CN"} <= locale.support_languages()
    assert "zh" not in locale.content_languages()
    assert locale.to_contract("zh") == "zh-CN" and locale.to_internal("zh-CN") == "zh"
    assert locale.to_contract("en") == "en" and locale.to_internal("vi") == "vi"
    with pytest.raises(locale.UnsupportedLanguage):
        locale.to_internal("zh")


def test_unknown_request_fields_are_ignored_for_a_newer_client():
    body = request(trigger="open", display={"x": 1})
    body["context"]["new_field"] = "v2"
    body["client"]["new_field"] = True
    assert TurnRequest.model_validate(body).message


def test_a_newer_contract_version_is_answered_in_this_one():
    turn = TurnRequest.model_validate(request(contract_version=2))
    assert turn.version == 1
    with pytest.raises(ValidationError):
        TurnRequest.model_validate(request(contract_version=0))


def test_an_unknown_surface_degrades_to_no_surface():
    body = request()
    body["context"]["surface"] = "orena.home"
    turn = TurnRequest.model_validate(body)
    assert turn.context.surface == "orena.home"
    assert turn.context.known_surface is None


def test_closed_vocabularies_are_enforced():
    for path, value in (
        (("context", "activity_type"), "gaming"),
        (("context", "selected_item", "type"), "paragraph"),
        (("coach_notes", 0, "kind"), "mood"),
        (("coach_notes", 0, "weight"), 1.5),
    ):
        body = request()
        target = body
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        with pytest.raises(ValidationError):
            TurnRequest.model_validate(body)


def test_a_selection_needs_an_id_or_a_text():
    body = request()
    body["context"]["selected_item"] = {"type": "word"}
    with pytest.raises(ValidationError):
        TurnRequest.model_validate(body)


def test_a_version_one_turn_carries_a_message():
    for message in ("", "   "):
        with pytest.raises(ValidationError):
            TurnRequest.model_validate(request(message=message))
    body = request()
    del body["message"]
    with pytest.raises(ValidationError):
        TurnRequest.model_validate(body)


def test_coach_notes_budget():
    note = request()["coach_notes"][0]
    ten = [dict(note, id=f"n{i}") for i in range(10)]
    assert len(TurnRequest.model_validate(request(coach_notes=ten)).coach_notes) == 10
    tiny = [dict(note, id=f"n{i}", kind="goal", text="x") for i in range(21)]
    with pytest.raises(ValidationError, match="at most 20"):
        TurnRequest.model_validate(request(coach_notes=tiny))
    heavy = [dict(note, id=f"n{i}", text="x" * 380) for i in range(6)]
    with pytest.raises(ValidationError, match="2048 bytes"):
        TurnRequest.model_validate(request(coach_notes=heavy))


def test_request_size_ceilings():
    from writing_coach.agent.schemas import MAX_MESSAGE_CHARS

    assert TurnRequest.model_validate(request(message="字" * MAX_MESSAGE_CHARS)).message
    with pytest.raises(ValidationError):
        TurnRequest.model_validate(request(message="字" * (MAX_MESSAGE_CHARS + 1)))
    essay = "Đây là bài của tôi. " * 600  # a pasted essay is not refused
    assert TurnRequest.model_validate(request(message=essay)).message == essay
    body = request()
    body["client"]["supported_actions"] = ["navigate"] * 65
    with pytest.raises(ValidationError):
        TurnRequest.model_validate(body)
    body = request()
    body["client"]["supported_intents"] = ["home"] * 129
    with pytest.raises(ValidationError):
        TurnRequest.model_validate(body)


def test_ids_are_bounded_tokens():
    body = request()
    body["context"]["attempt_id"] = "../../etc/passwd"
    with pytest.raises(ValidationError):
        TurnRequest.model_validate(body)


def test_client_declarations_are_intersected_with_the_contract():
    body = copy.deepcopy(request())
    body["client"]["supported_actions"] = ["navigate", "delete_collection", "save_word"]
    body["client"]["supported_intents"] = ["vocabulary.review_due", "admin.users"]
    client = TurnRequest.model_validate(body).client
    assert client.allowed_actions == {"navigate", "save_word"}
    assert client.allowed_intents == {"vocabulary.review_due"}
