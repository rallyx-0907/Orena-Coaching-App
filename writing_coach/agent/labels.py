"""The learner-facing names of the app's internal labels, for what a tool hands the model.

A tool result is read by the model and retold to the learner, so an internal
English label ("New", "tense", "Mispronunciation") reaching it reaches the
learner (human review of the live run, 2026-09-28). Each tool therefore gives
the model the label translated into the interface language - with, for the
review status, what it means - and never the internal key.

Interface layer (D-080): these are the names the app uses for states and
categories. One table per kind; every key has en, vi and zh-CN
(`tests/test_agent_labels.py` checks the vocabularies of both languages).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from writing_coach.agent.locale import to_contract

Table = Mapping[str, Mapping[str, str]]


def _table(rows: dict[str, tuple[str, str, str]]) -> Table:
    return MappingProxyType({key: MappingProxyType({"en": en, "vi": vi, "zh-CN": zh}) for key, (en, vi, zh) in rows.items()})


# Review status of a saved word, from its review stage (0 new, 1-2 learning, 3-4 known) and whether it is due.
REVIEW_STATUS = _table(
    {
        "not_learned": ("Not learned yet", "Chưa học", "未学习"),
        "learning": ("Learning", "Đang học", "学习中"),
        "known": ("Known", "Đã thuộc", "已掌握"),
        "due": ("Due for review", "Đến hạn ôn", "该复习了"),
    }
)
REVIEW_MEANING = _table(
    {
        "not_learned": ("saved, not reviewed yet", "đã lưu, chưa ôn lần nào", "已保存，还没复习过"),
        "learning": ("reviewed a few times, not yet secure", "đã ôn vài lần, chưa nhớ chắc", "复习过几次，还不牢固"),
        "known": ("remembered well, reviewed rarely", "nhớ ổn định, ôn thưa", "记得牢，偶尔复习"),
        "due": ("its review is due now", "đến lúc ôn lại", "现在该复习了"),
    }
)

# Writing error categories, English and Chinese evaluators together (languages/*/profile.py).
ERROR_CATEGORY = _table(
    {
        "article": ("Articles", "Mạo từ", "冠词"),
        "tense": ("Tense", "Thì", "时态"),
        "agreement": ("Subject-verb agreement", "Hòa hợp chủ ngữ - động từ", "主谓一致"),
        "word_choice": ("Word choice", "Chọn từ", "用词"),
        "word_form": ("Word form", "Dạng từ", "词形"),
        "preposition": ("Prepositions", "Giới từ", "介词"),
        "sentence_structure": ("Sentence structure", "Cấu trúc câu", "句子结构"),
        "punctuation": ("Punctuation", "Dấu câu", "标点"),
        "coherence": ("Coherence", "Mạch lạc", "连贯"),
        "task": ("Meeting the task", "Đáp ứng đề bài", "切题"),
        "naturalness": ("Naturalness", "Độ tự nhiên", "自然度"),
        "register": ("Register", "Văn phong", "语体"),
        "spelling": ("Spelling", "Chính tả", "拼写"),
        "other": ("Other", "Khác", "其他"),
        "word_order": ("Word order", "Trật tự từ", "语序"),
        "particle": ("Particles", "Trợ từ", "助词"),
        "aspect": ("Aspect", "Thể (了/过/着)", "体标记"),
        "complement": ("Complements", "Bổ ngữ", "补语"),
        "measure_word": ("Measure words", "Lượng từ", "量词"),
        "ba_sentence": ("把 sentences", "Câu chữ 把", "把字句"),
        "bei_sentence": ("被 sentences", "Câu chữ 被", "被字句"),
        "conjunction": ("Conjunctions", "Liên từ", "连词"),
        "character_choice": ("Character choice", "Chọn chữ Hán", "选字"),
        "collocation": ("Collocation", "Kết hợp từ", "搭配"),
        "redundancy": ("Redundancy", "Thừa từ", "冗余"),
    }
)

# The kind a writing review gives each issue.
ISSUE_KIND = _table(
    {
        "grammar": ("Grammar", "Ngữ pháp", "语法"),
        "naturalness": ("Naturalness", "Độ tự nhiên", "自然度"),
        "punctuation": ("Punctuation", "Dấu câu", "标点"),
        "register": ("Register", "Văn phong", "语体"),
        "vocabulary": ("Vocabulary", "Từ vựng", "词汇"),
    }
)

# The pronunciation provider's error types (its own marks, D-084).
PRONUNCIATION_ERROR = _table(
    {
        "mispronunciation": ("Mispronounced", "Phát âm sai", "发音错误"),
        "omission": ("Left out", "Bị bỏ sót", "漏读"),
        "insertion": ("Added", "Đọc thừa", "多读"),
        "unexpectedbreak": ("Unexpected pause", "Ngắt không đúng chỗ", "不当停顿"),
        "missingbreak": ("Missing pause", "Thiếu chỗ ngắt", "缺少停顿"),
        "monotone": ("Flat intonation", "Giọng đều đều", "语调平淡"),
    }
)


def label(table: Table, key: object, interface: str) -> str | None:
    """The key's name in the interface language (contract or internal code); None for an unknown key."""

    entry = table.get(str(key or "").strip().casefold())
    if entry is None:
        return None
    return entry.get(to_contract(interface), entry["en"])


def review_status(stage: object) -> str:
    """not_learned / learning / known from the review stage (becoming_library's 0-4)."""

    try:
        value = int(stage or 0)
    except (TypeError, ValueError):
        value = 0
    return "not_learned" if value <= 0 else ("learning" if value <= 2 else "known")


def review_state(stage: object, due: bool, interface: str) -> dict:
    """What the model is given about a saved word's review: names and meanings, never the internal stage label."""

    status = review_status(stage)
    state = {
        "status": label(REVIEW_STATUS, status, interface),
        "status_meaning": label(REVIEW_MEANING, status, interface),
        "due": bool(due),
    }
    if due:
        state["due_label"] = label(REVIEW_STATUS, "due", interface)
    return state


def category_label(key: object, interface: str) -> str:
    return label(ERROR_CATEGORY, key, interface) or label(ERROR_CATEGORY, "other", interface)


def issue_label(key: object, interface: str) -> str | None:
    return label(ISSUE_KIND, key, interface)


def pronunciation_label(key: object, interface: str) -> str | None:
    return label(PRONUNCIATION_ERROR, key, interface)
