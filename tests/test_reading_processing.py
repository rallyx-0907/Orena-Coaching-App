"""The Reading engine's deterministic stage - no AI, no network, no database.

Everything here runs before any model is asked anything: cleaning, URL
canonicalization, the content fingerprint dedupe depends on, language
validation, the text measurements a level estimate is built from, and the
first pass of learning-target candidates. These are the facts the pipeline is
allowed to treat as certain, so each one is pinned by a test rather than by
"it looked right once".
"""
from __future__ import annotations

import pytest

from writing_coach.reading_processing import (
    analyze_article,
    clean_source_text,
    content_fingerprint,
    detect_language,
    normalize_url,
    quality_issues,
    suggest_targets,
)


# ---- cleaning ---------------------------------------------------------------

def test_clean_drops_script_and_style_bodies_entirely():
    raw = "<p>Real text.</p><script>alert('x')</script><style>p{color:red}</style>"
    cleaned = clean_source_text(raw)
    assert cleaned == "Real text."
    assert "alert" not in cleaned and "color" not in cleaned


def test_clean_never_returns_markup_even_for_hostile_input():
    raw = '<div onclick="steal()"><img src=x onerror=alert(1)>Hello <b>world</b></div>'
    cleaned = clean_source_text(raw)
    assert "<" not in cleaned and ">" not in cleaned
    assert "onerror" not in cleaned and "steal" not in cleaned
    assert cleaned == "Hello world"


def test_clean_keeps_paragraph_boundaries_and_collapses_the_rest():
    raw = "<h1>Title</h1>\n\n<p>First   line.</p><p>Second line.</p><br>Third."
    assert clean_source_text(raw) == "Title\n\nFirst line.\n\nSecond line.\n\nThird."


def test_clean_unescapes_entities_and_keeps_chinese_intact():
    assert clean_source_text("<p>caf&eacute; &amp; th&eacute;</p>") == "café & thé"
    assert clean_source_text("<p>今天天气很好。</p>") == "今天天气很好。"


def test_clean_drops_chrome_that_is_never_the_article():
    raw = "<nav>Home About</nav><article>The body.</article><footer>© 2026</footer>"
    assert clean_source_text(raw) == "The body."


def test_clean_accepts_plain_text_unchanged_apart_from_whitespace():
    assert clean_source_text("  Just a pasted sentence.  ") == "Just a pasted sentence."


# ---- URL canonicalization ---------------------------------------------------

def test_normalize_url_folds_scheme_host_and_default_port():
    assert normalize_url("HTTPS://Www.Example.COM:443/Path") == "https://example.com/Path"


def test_normalize_url_drops_tracking_parameters_and_fragment():
    url = "https://example.com/story?utm_source=x&id=7&fbclid=abc#section"
    assert normalize_url(url) == "https://example.com/story?id=7"


def test_normalize_url_orders_remaining_parameters_so_dedupe_sees_one_url():
    first = normalize_url("https://example.com/a?b=2&a=1")
    second = normalize_url("https://example.com/a?a=1&b=2")
    assert first == second == "https://example.com/a?a=1&b=2"


def test_normalize_url_keeps_a_bare_host_usable_and_rejects_nonsense():
    assert normalize_url("https://example.com/") == "https://example.com/"
    assert normalize_url("not a url") == ""
    assert normalize_url("javascript:alert(1)") == ""


# ---- fingerprint ------------------------------------------------------------

def test_fingerprint_is_stable_across_whitespace_but_not_across_content():
    assert content_fingerprint("A sentence.") == content_fingerprint("  A   sentence.\n")
    assert content_fingerprint("A sentence.") != content_fingerprint("A sentence!")
    assert len(content_fingerprint("A sentence.")) == 64


# ---- language ---------------------------------------------------------------

def test_detect_language_reads_english_and_chinese():
    english, en_confidence = detect_language(
        "The garden was quiet in the morning, and the old man watered every plant."
    )
    chinese, zh_confidence = detect_language("早上的花园很安静，老人给每一棵植物浇水。")
    assert english == "en" and en_confidence > 0.5
    assert chinese == "zh" and zh_confidence > 0.5


def test_detect_language_refuses_to_guess_when_there_is_nothing_to_read():
    assert detect_language("") == ("", 0.0)
    assert detect_language("1234 5678 :::")[0] == ""


def test_detect_language_does_not_call_a_mostly_chinese_text_english():
    language, _ = detect_language("这是一篇关于 Orena 的文章，主要内容是中文。")
    assert language == "zh"


# ---- measurements and level -------------------------------------------------

def test_analyze_counts_english_words_sentences_and_reading_time():
    body = "The cat sat on the mat. It was warm there. The cat slept."
    analysis = analyze_article(body, "en")
    assert analysis.word_count == 13
    assert analysis.sentence_count == 3
    assert analysis.reading_time_seconds > 0
    assert analysis.estimated_level in {"A1", "A2", "B1", "B2", "C1", "C2"}


def test_analyze_counts_chinese_by_character_not_by_space():
    analysis = analyze_article("今天天气很好。我们去公园散步。", "zh")
    assert analysis.word_count == 13
    assert analysis.sentence_count == 2
    assert analysis.estimated_level.startswith("HSK")


def test_a_simple_text_estimates_lower_than_a_dense_one():
    simple = analyze_article(
        "The dog runs. The cat sits. A bird sings. The sun is warm. We walk home.", "en"
    )
    dense = analyze_article(
        "Notwithstanding the committee's preliminary determination, the subsequent "
        "reassessment demonstrated that institutional accountability mechanisms had "
        "systematically underestimated the environmental consequences of the proposed "
        "infrastructural redevelopment programme.",
        "en",
    )
    levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    assert levels.index(dense.estimated_level) > levels.index(simple.estimated_level)


def test_estimate_confidence_is_lower_for_a_very_short_text():
    short = analyze_article("The cat sat.", "en")
    longer = analyze_article("The cat sat on the mat. " * 40, "en")
    assert short.confidence < longer.confidence
    assert 0.0 <= short.confidence <= 1.0 and 0.0 <= longer.confidence <= 1.0


def test_analysis_is_deterministic_for_the_same_input():
    body = "A quiet morning in the garden. The old man watered every plant carefully."
    assert analyze_article(body, "en") == analyze_article(body, "en")


# ---- quality ----------------------------------------------------------------

def test_quality_flags_a_text_too_short_to_be_an_article():
    assert "too_short" in quality_issues("Hello.", "en")


def test_quality_flags_a_language_mismatch_rather_than_silently_accepting_it():
    issues = quality_issues("今天天气很好，我们去公园散步，然后回家吃饭。" * 5, "en")
    assert "language_mismatch" in issues


def test_quality_flags_boilerplate_repetition():
    issues = quality_issues(("Subscribe to our newsletter. " * 60), "en")
    assert "repetitive" in issues


def test_quality_is_silent_on_an_ordinary_article():
    body = (
        "The market opened early on Saturday. Farmers arrived with boxes of fruit "
        "and vegetables, and the square filled with people before the sun was high. "
        "Children ran between the stalls while their parents argued about prices. "
        "By noon the best tomatoes were gone, and the bakery had sold every loaf. "
        "The oldest seller said the crowd was the largest she had seen this year. "
        "A young baker explained that he starts his ovens at three in the morning. "
        "Two musicians played near the fountain and collected coins in a hat. "
        "Rain arrived in the afternoon, and the stalls closed earlier than usual. "
        "Several sellers packed their vans while the square emptied around them. "
        "The council has promised a permanent roof before the winter markets begin. "
        "Nobody could remember a summer with so many visitors from other towns. "
        "The market will open again on Wednesday, weather permitting."
    )
    assert quality_issues(body, "en") == []


# ---- learning targets -------------------------------------------------------

def test_targets_are_bounded_ranked_and_carry_their_sentence():
    body = (
        "The committee decided to carry out a review. They had to carry out the work "
        "quickly because the deadline was approaching. The review showed that the "
        "infrastructure was deteriorating faster than anyone had predicted."
    )
    targets = suggest_targets(body, "en", limit=8)
    assert 1 <= len(targets) <= 8
    assert [target.rank for target in targets] == list(range(len(targets)))
    assert all(target.context for target in targets)
    assert all(target.text.lower() in body.lower() for target in targets)
    assert all(target.machine_suggested for target in targets)


def test_targets_skip_the_words_every_learner_already_has():
    body = "The cat and the dog were in the house with the man and the woman. " * 5
    texts = {target.canonical_form for target in suggest_targets(body, "en", limit=8)}
    assert not texts & {"the", "and", "was", "were", "with", "in"}


def test_targets_find_a_repeated_phrase_not_only_single_words():
    body = (
        "She had to look after her brother every afternoon. Looking after him was "
        "tiring, but she liked to look after someone who needed her. To look after "
        "a child is to plan every hour of the day."
    )
    targets = suggest_targets(body, "en", limit=8)
    assert any(" " in target.canonical_form for target in targets)


def test_targets_work_for_chinese_without_spaces():
    body = "环境保护是每个人的责任。环境保护需要长期努力。政府提出新的环境保护政策。"
    targets = suggest_targets(body, "zh", limit=8)
    assert targets
    assert any(target.canonical_form == "环境保护" for target in targets)


def test_targets_are_deterministic_and_never_duplicate_a_form():
    body = "The engineer will carry out the test. The engineer will carry out the repair. " * 4
    first = suggest_targets(body, "en", limit=8)
    second = suggest_targets(body, "en", limit=8)
    assert first == second
    assert len({target.canonical_form for target in first}) == len(first)


@pytest.mark.parametrize("language", ["en", "zh"])
def test_targets_on_an_empty_body_are_empty_not_invented(language):
    assert suggest_targets("", language, limit=8) == []
