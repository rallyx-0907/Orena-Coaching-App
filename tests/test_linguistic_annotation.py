"""The shared tagger that replaced a 2 800-token-per-essay model call.

What is worth pinning here is not tagging accuracy — there is no gold standard
in this repository to measure that against, and the model it replaced was never
measured either. What is worth pinning is the contract the Review lens and the
Listening transcript both depend on: literal fragments, ordered, offsets that
index back into the source, labels from a fixed set, and the same answer every
time.
"""

from __future__ import annotations

import pytest

from writing_coach import linguistic_annotation as la
from writing_coach.ai.capabilities import AIOperation, require_capability


EN = "The students are studying Chinese in Beijing. They have written many essays."
ZH = "我每天学习中文。这个房间很舒服，早上的阳光很好。"


@pytest.mark.parametrize(("language", "text"), [("en", EN), ("zh", ZH)])
def test_offsets_index_back_into_the_source(language: str, text: str) -> None:
    annotations = la.annotate(language, text)

    assert annotations
    for item in annotations:
        assert text[item["start"] : item["end"]] == item["fragment"]


@pytest.mark.parametrize(("language", "text"), [("en", EN), ("zh", ZH)])
def test_annotations_are_ordered_and_do_not_overlap(language: str, text: str) -> None:
    annotations = la.annotate(language, text)

    cursor = 0
    for item in annotations:
        assert item["start"] >= cursor
        assert item["end"] > item["start"]
        cursor = item["end"]


@pytest.mark.parametrize(("language", "text"), [("en", EN), ("zh", ZH)])
def test_every_label_is_in_the_allowed_set(language: str, text: str) -> None:
    assert {item["pos"] for item in la.annotate(language, text)} <= la.ALLOWED_POS


@pytest.mark.parametrize(("language", "text"), [("en", EN), ("zh", ZH)])
def test_the_same_text_always_tags_the_same_way(language: str, text: str) -> None:
    # A deterministic tagger is what makes the cache and these tests meaningful.
    assert la.annotate(language, text) == la.annotate(language, text)


def test_punctuation_is_not_annotated() -> None:
    for item in la.annotate("zh", ZH):
        assert item["fragment"] not in {"。", "，"}
    for item in la.annotate("en", EN):
        assert item["fragment"] != "."


def test_chinese_annotations_carry_contextual_pinyin() -> None:
    annotations = la.annotate("zh", ZH)

    assert all(item["pronunciation"] for item in annotations)
    learn = next(item for item in annotations if item["fragment"] == "学习")
    assert learn["pronunciation"] == "xué xí"
    assert learn["pos"] == "verb"


def test_chinese_segments_into_words_not_characters() -> None:
    fragments = {item["fragment"] for item in la.annotate("zh", ZH)}

    assert "学习" in fragments and "房间" in fragments and "舒服" in fragments


def test_english_separates_proper_nouns_from_common_ones() -> None:
    # proper_noun is one of the four labels the model prompt collapsed into
    # "other". Separating them is the precision this change gains.
    by_fragment = {item["fragment"]: item["pos"] for item in la.annotate("en", EN)}

    assert by_fragment["Chinese"] == "proper_noun"
    assert by_fragment["students"] == "noun"
    assert by_fragment["The"] == "determiner"
    assert by_fragment["many"] == "adjective"


def test_english_modals_are_auxiliaries() -> None:
    # Only Penn's MD maps to auxiliary. "have" in "have written" is tagged VBP
    # and stays a verb, which is the tagger's judgement, not a bug here.
    by_fragment = {
        item["fragment"]: item["pos"]
        for item in la.annotate("en", "She can write and she has written.")
    }

    assert by_fragment["can"] == "auxiliary"


def test_a_sentence_final_word_keeps_its_period() -> None:
    """Known wart, pinned so it is not mistaken for a regression.

    TreebankWordTokenizer only splits a final period when the text has been
    sentence-tokenized first, so the last word of a sentence arrives with the
    period attached. This is the behaviour the Listening transcript has always
    had; it is recorded here rather than changed, because changing it would move
    every token boundary on a CLOSED M1 surface and belongs in its own change.
    """
    fragments = [item["fragment"] for item in la.annotate("en", EN)]

    assert "Beijing." in fragments
    assert "Beijing" not in fragments


def test_the_limit_is_respected() -> None:
    assert len(la.annotate("en", EN, max_annotations=3)) <= 3


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_empty_text_yields_nothing(text: str) -> None:
    assert la.annotate("en", text) == []
    assert la.annotate("zh", text) == []


def test_language_tags_are_normalised() -> None:
    assert la.annotate("ZH-Hans", ZH) == la.annotate("zh", ZH)


def test_writing_linguistic_is_deterministic_in_the_catalog() -> None:
    # The capability survives as a named workload, but nothing routes it to a
    # provider — the same shape reading_evaluator has always had.
    definition = require_capability("writing_linguistic")

    assert definition.operation is AIOperation.DETERMINISTIC
    assert definition.provider_backed is False
    assert definition.configurable is False
    assert definition.implemented is True


def test_the_tagger_reaches_no_provider() -> None:
    source = la.__dict__
    assert "generate_structured" not in source
    text = (
        __import__("pathlib").Path(la.__file__).read_text(encoding="utf-8")
    )
    for forbidden in ("generate_structured", "ai_json", "capability_key", "requests."):
        assert forbidden not in text


def test_curly_quotes_are_not_glued_to_the_word_and_offsets_index_the_source() -> None:
    from writing_coach.linguistic_annotation import annotate

    source = "\u201cI'm lonely,\u201d she said."
    tokens = annotate("en", source)
    fragments = [token["fragment"] for token in tokens]
    assert "I" in fragments and "\u201cI" not in fragments
    for token in tokens:
        assert source[token["start"]:token["end"]] == token["fragment"]


# PRE-105 / D23: the contexts of 落花生 (Xu Dishan, 1922) where 底 is written for the particle 的.
LUOHUASHENG_DI = [
    "我们底主人",
    "花生底好处很多",
    "父亲底话",
    "他底朋友来了",
    "这是我们底",
    "它底样子不好看",
    "你底书",
    "我们底后面有半亩隙地",
    "母亲说，今晚可以做一个收获节，也请你们爹爹来尝尝我们底新花生，如何？",
    "花生底用处很多",
    "你们爱吃花生么？",
    "妹妹底话",
    "姊姊底意思",
]


def _di_readings(text: str) -> list[str]:
    la._annotate_cached.cache_clear()
    return [item["pronunciation"] for item in la.annotate("zh", text) if item["fragment"] == "底"]


@pytest.mark.parametrize("text", [t for t in LUOHUASHENG_DI if "底" in t])
def test_di_written_for_the_particle_de_is_read_de(text: str) -> None:
    assert _di_readings(text) == ["de"]
    tokens = la.annotate("zh", text)
    for token in tokens:
        assert text[token["start"] : token["end"]] == token["fragment"]
    assert [t["pos"] for t in tokens if t["fragment"] == "底"] == ["particle"]


@pytest.mark.parametrize(
    "text",
    ["到底怎么回事", "桌子底下很暗", "海底世界", "彻底改变", "年底到了", "池底有水", "心底的话", "这座山的底部", "他探底成功", "锅底"],
)
def test_di_in_a_lexical_word_keeps_its_dictionary_reading(text: str) -> None:
    assert all(reading == "dǐ" for reading in _di_readings(text))


def test_di_particle_survives_a_noisy_tagger(monkeypatch) -> None:
    class Pair:
        def __init__(self, word: str, flag: str) -> None:
            self.word, self.flag = word, flag

    # The tagger mislabels the pronoun and the particle and glues 底 to the next word: the characters decide.
    def noisy(text: str):
        if text == "我们":
            return [Pair("我们", "v")]
        if text.endswith("我们"):
            return [Pair("我们", "x")]
        return [Pair("我们", "x"), Pair("底话", "n")]

    monkeypatch.setattr(la.pseg, "cut", noisy)
    la._annotate_cached.cache_clear()
    result = {item["fragment"]: item["pronunciation"] for item in la.annotate("zh", "我们底话")}
    assert result["底"] == "de" and result["话"] == "huà"
    # a verb before 底 is not a possessor, however the tagger labelled the rest
    monkeypatch.setattr(la.pseg, "cut", lambda text: [Pair("探", "v"), Pair("底话", "n")])
    la._annotate_cached.cache_clear()
    assert {item["fragment"]: item["pronunciation"] for item in la.annotate("zh", "探底话")}["底话"] == "dǐ huà"
    la._annotate_cached.cache_clear()
