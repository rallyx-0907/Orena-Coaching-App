from __future__ import annotations

import pytest
from fastapi import HTTPException

from writing_coach import media_interaction


def _gloss(text: str, context: str, *, source: str = "en", target: str = "vi"):
    return media_interaction.contextual_gloss(
        media_interaction.ContextualGlossIn(
            text=text, context=context, source_language=source, target_language=target
        )
    )


def test_gloss_gives_the_meaning_this_sentence_uses(monkeypatch) -> None:
    observed = {}

    def fake_run(capability_key, *, messages, schema, max_output_tokens):
        observed["capability_key"] = capability_key
        observed["system"] = messages[0]["content"]
        observed["user"] = messages[1]["content"]
        observed["max_output_tokens"] = max_output_tokens
        return {
            "meaning": "tranh cãi",
            "base_form": "dispute",
            "pronunciation": "/dɪˈspjuːt/",
            "part_of_speech": "verb",
        }

    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    monkeypatch.setattr(media_interaction, "_run_structured", fake_run)

    payload = _gloss("disputing", "The Wind and the Sun were disputing which was stronger.")

    assert payload == {
        "available": True,
        "claim": "contextual_gloss",
        "source_language": "en",
        "target_language": "vi",
        "selected_text": "disputing",
        "meaning": "tranh cãi",
        "base_form": "dispute",
        "part_of_speech": "verb",
        "pronunciation": "/dɪˈspjuːt/",
    }
    assert observed["capability_key"] == "learner_dictionary"
    assert "Vietnamese" in observed["system"]
    assert "disputing which was stronger" in observed["user"]
    # A gloss is a short answer; it must not reserve an explanation's budget.
    assert observed["max_output_tokens"] <= 400


def test_gloss_names_the_support_language_from_the_shared_registry(monkeypatch) -> None:
    observed = {}

    def fake_run(capability_key, *, messages, schema, max_output_tokens):
        observed["system"] = messages[0]["content"]
        return {"meaning": "discutían", "base_form": "dispute", "pronunciation": "", "part_of_speech": "verb"}

    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    monkeypatch.setattr(media_interaction, "_run_structured", fake_run)

    _gloss("disputing", "They were disputing it.", target="es")

    assert "Spanish" in observed["system"]


def test_gloss_prefers_the_local_tagger_over_the_model_for_word_class(monkeypatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    monkeypatch.setattr(
        media_interaction,
        "_run_structured",
        lambda *args, **kwargs: {"meaning": "sách", "base_form": "book", "pronunciation": "/bʊk/", "part_of_speech": "verb"},
    )

    payload = _gloss("book", "I really like this book.")

    assert payload["part_of_speech"] == "noun"


def test_gloss_drops_a_word_class_outside_the_product_vocabulary(monkeypatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    monkeypatch.setattr(
        media_interaction,
        "_run_structured",
        lambda *args, **kwargs: {"meaning": "rất thích", "base_form": "really like", "pronunciation": "", "part_of_speech": "verbal phrase"},
    )

    payload = _gloss("really like", "I really like this book.")

    assert payload["part_of_speech"] == ""


def test_gloss_reads_chinese_pinyin_locally_in_context(monkeypatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "zh")
    monkeypatch.setattr(
        media_interaction,
        "_run_structured",
        lambda *args, **kwargs: {"meaning": "trường học", "base_form": "学校", "pronunciation": "xue xiao", "part_of_speech": "noun"},
    )

    payload = _gloss("学校", "我今天在学校学习中文。", source="zh")

    assert payload["pronunciation"] == "xué xiào"
    assert payload["base_form"] == "学校"
    assert payload["part_of_speech"] == "noun"


def test_gloss_must_be_about_words_the_learner_can_see(monkeypatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    called = []
    monkeypatch.setattr(media_interaction, "_run_structured", lambda *a, **k: called.append(1) or {})

    with pytest.raises(HTTPException) as exc:
        _gloss("usually", "I walk to school.")

    assert exc.value.status_code == 422
    assert called == []


def test_gloss_refuses_text_in_another_learning_language(monkeypatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")

    with pytest.raises(HTTPException) as exc:
        _gloss("学校", "我在学校。", source="zh")

    assert exc.value.status_code == 409


def test_an_unavailable_gloss_says_so_and_keeps_what_is_known_locally(monkeypatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "zh")
    monkeypatch.setattr(
        media_interaction,
        "_run_structured",
        lambda *args, **kwargs: (_ for _ in ()).throw(HTTPException(503, "unavailable")),
    )

    payload = _gloss("学校", "我今天在学校学习中文。", source="zh")

    assert payload["available"] is False
    assert payload["claim"] == "contextual_gloss_unavailable"
    assert payload["meaning"] == ""
    assert payload["pronunciation"] == "xué xiào"


def test_a_gloss_without_a_meaning_is_not_presented_as_one(monkeypatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    monkeypatch.setattr(
        media_interaction,
        "_run_structured",
        lambda *args, **kwargs: {"meaning": "   ", "base_form": "book", "pronunciation": "", "part_of_speech": "noun"},
    )

    payload = _gloss("book", "I really like this book.")

    assert payload["available"] is False
    assert payload["claim"] == "contextual_gloss_unavailable"
    assert payload["meaning"] == ""
