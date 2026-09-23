from __future__ import annotations

import pytest
from fastapi import HTTPException

from writing_coach import media_interaction


def test_validated_annotations_preserve_literal_order_and_offsets() -> None:
    source = "我今天在学校学习中文。"
    raw = [
        {"fragment": "我", "pos": "pronoun", "pronunciation": "wǒ", "lemma": "我"},
        {"fragment": "今天", "pos": "noun", "pronunciation": "jīntiān", "lemma": "今天"},
        {"fragment": "学校", "pos": "noun", "pronunciation": "xuéxiào", "lemma": "学校"},
        {"fragment": "学习", "pos": "verb", "pronunciation": "xuéxí", "lemma": "学习"},
        {"fragment": "中文", "pos": "noun", "pronunciation": "Zhōngwén", "lemma": "中文"},
    ]

    annotations = media_interaction._validated_annotations(source, raw)

    assert [item["fragment"] for item in annotations] == [
        "我",
        "今天",
        "学校",
        "学习",
        "中文",
    ]
    assert all(source[item["start"] : item["end"]] == item["fragment"] for item in annotations)
    assert annotations[1]["start"] == source.index("今天")
    assert annotations[-1]["end"] == source.index("中文") + len("中文")


def test_validated_annotations_drop_hallucinated_or_out_of_order_fragments() -> None:
    source = "I really like this book."
    raw = [
        {"fragment": "I", "pos": "pronoun", "pronunciation": "", "lemma": "I"},
        {"fragment": "book", "pos": "noun", "pronunciation": "", "lemma": "book"},
        {"fragment": "like", "pos": "verb", "pronunciation": "", "lemma": "like"},
        {"fragment": "missing", "pos": "noun", "pronunciation": "", "lemma": "missing"},
    ]

    annotations = media_interaction._validated_annotations(source, raw)

    assert [item["fragment"] for item in annotations] == ["I", "book"]


def test_annotate_media_text_uses_local_chinese_segmentation_and_pinyin(monkeypatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "zh")

    payload = media_interaction.annotate_media_text(
        media_interaction.MediaAnnotateIn(
            text="我在葡萄牙工作。",
            source_language="zh-CN",
        )
    )

    assert payload["source_language"] == "zh"
    assert payload["reading_aid"] == "pinyin"
    annotations = payload["annotations"]
    assert "葡萄牙" in [item["fragment"] for item in annotations]
    assert "工作" in [item["fragment"] for item in annotations]
    assert next(item for item in annotations if item["fragment"] == "工作")["pos"] == "verb"
    assert next(item for item in annotations if item["fragment"] == "葡萄牙")["pronunciation"]
    assert all(payload["text"][item["start"] : item["end"]] == item["fragment"] for item in annotations)


def test_annotate_media_text_is_local_deterministic_and_cached(monkeypatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    calls = 0

    def fail_if_called(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("annotation must not call AI")

    monkeypatch.setattr(media_interaction, "generate_structured", fail_if_called)
    request = media_interaction.MediaAnnotateIn(
        text="The curious students quickly study books.", source_language="en"
    )

    first = media_interaction.annotate_media_text(request)
    second = media_interaction.annotate_media_text(request)

    assert calls == 0
    assert first == second
    assert [item["pos"] for item in first["annotations"]] == [
        "determiner", "adjective", "noun", "adverb", "verb", "noun"
    ]
    assert all(first["text"][item["start"] : item["end"]] == item["fragment"] for item in first["annotations"])


def test_english_annotations_use_contextual_local_pos_tags(monkeypatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    payload = media_interaction.annotate_media_text(
        media_interaction.MediaAnnotateIn(
            text="They can fish near the light.", source_language="en"
        )
    )
    tags = {item["fragment"]: item["pos"] for item in payload["annotations"]}

    assert tags == {"They": "pronoun", "can": "auxiliary", "fish": "verb", "near": "preposition", "the": "determiner", "light": "noun"}


def test_media_interaction_rejects_cross_language_annotation(monkeypatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")

    with pytest.raises(HTTPException) as exc:
        media_interaction.annotate_media_text(
            media_interaction.MediaAnnotateIn(
                text="你好",
                source_language="zh",
            )
        )

    assert exc.value.status_code == 409


def test_explain_media_text_uses_requested_support_language(monkeypatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    observed = {}

    def fake_run(capability_key, *, messages, schema, max_output_tokens):
        observed["capability_key"] = capability_key
        observed["system"] = messages[0]["content"]
        observed["user"] = messages[1]["content"]
        return {
            "summary": "Cụm này diễn tả một thói quen.",
            "natural_translation": "Tôi thường đi bộ đến trường.",
            "grammar_notes": ["usually đứng trước động từ thường."],
            "vocabulary": [
                {
                    "fragment": "usually",
                    "meaning": "thường",
                    "pos": "adverb",
                    "pronunciation": "",
                }
            ],
            "usage_note": "Dùng cho hành động xảy ra thường xuyên.",
        }

    monkeypatch.setattr(media_interaction, "_run_structured", fake_run)

    payload = media_interaction.explain_media_text(
        media_interaction.MediaExplainIn(
            text="I usually walk to school.",
            source_language="en",
            target_language="vi",
            context="On weekdays, I usually walk to school.",
        )
    )

    assert observed["capability_key"] == "learner_dictionary"
    assert "Explain in Vietnamese" in observed["system"]
    assert payload["target_language"] == "vi"
    assert payload["vocabulary"][0]["fragment"] == "usually"
    # The last message names the answer language too, and names the fields a model
    # otherwise leaves in the language of the text (the verdict's reason, the follow-ups).
    assert "second person" in observed["system"] and "the learner'" in observed["system"]
    assert observed["user"].rstrip().splitlines()[-1].startswith("Write every explanation in Vietnamese")
    assert "judgement_reason" in observed["user"] and "follow_ups" in observed["user"]


def test_contextual_dictionary_requires_visible_context_and_returns_grounded_claim(monkeypatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    monkeypatch.setattr(media_interaction, "_run_structured", lambda *args, **kwargs: {
        "summary": "A repeated weekday habit.",
        "natural_translation": "Tôi thường đi bộ.",
        "grammar_notes": [], "vocabulary": [], "usage_note": "",
    })
    payload = media_interaction.contextual_dictionary(
        media_interaction.ContextualDictionaryIn(
            text="usually", context="I usually walk to school.", source_language="en", target_language="vi"
        )
    )
    assert payload["available"] is True
    assert payload["claim"] == "contextual_dictionary"
    assert payload["selected_text"] == "usually"

    with pytest.raises(HTTPException) as exc:
        media_interaction.contextual_dictionary(
            media_interaction.ContextualDictionaryIn(
                text="usually", context="I walk to school.", source_language="en", target_language="vi"
            )
        )
    assert exc.value.status_code == 422


def test_contextual_dictionary_has_explicit_unavailable_fallback(monkeypatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "zh")
    monkeypatch.setattr(media_interaction, "_run_structured", lambda *args, **kwargs: (_ for _ in ()).throw(HTTPException(503, "unavailable")))
    payload = media_interaction.contextual_dictionary(
        media_interaction.ContextualDictionaryIn(
            text="学习", context="我喜欢学习。", source_language="zh", target_language="vi"
        )
    )
    assert payload == {
        "available": False,
        "source_language": "zh",
        "target_language": "vi",
        "selected_text": "学习",
        "claim": "contextual_dictionary_unavailable",
    }
