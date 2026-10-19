"""Issue #346: which messages change or forget a coach note. On a match the server holds the answer and, if the model
changed nothing, tells it to "call forget_note now" - so a false match can delete a note nobody asked to delete. A match
needs a change word AND either an explicit note noun or an overlap with something the note is about; a shared function
phrase ("giúp mình", "帮我", "这个") is not "about" anything."""

from __future__ import annotations

import pytest

from writing_coach.agent.notes import FORGET, note_intent, notes_the_message_changes
from writing_coach.agent.schemas import CoachNote


def note(text, id_="n-1"):
    return CoachNote(id=id_, kind="preference", text=text, weight=0.5, last_reinforced="2026-10-19T00:00:00+00:00")


@pytest.mark.parametrize(("message", "kept"), [
    ("Mình hay quên từ này, ôn lại giúp mình?", "Giải thích thật ngắn gọn giúp mình"),
    ("Sửa câu này giúp mình", "Cho mình ví dụ ngắn giúp mình"),
    ("我的学习记录不是很好，我该学什么？", "帮我用中文解释"),
    ("帮我改一下这句话", "帮我多举例子"),
    ("Actually, what does this word mean?", "Explain in English please"),
    ("Thôi, lưu ý giúp mình cách dùng 了", "Mình thích ví dụ ngắn"),  # "lưu ý" in the message is no note noun
    # "quên"/"忘"/"forget" as "I forget", with a real topical overlap (#346, review of #347)
    ("Mình hay quên ngữ pháp này quá", "Giải thích ngữ pháp thật kỹ"),
    ("我总是忘记这个语法", "多讲语法"),
    ("I always forget the grammar rules", "Explain grammar simply"),
    # an "I forget" sentence whose words look imperative, with real content overlap (re-review of #347)
    ("Mình hay quên từ vựng, ôn lại giúp mình", "Ôn lại từ vựng mỗi ngày"),
    ("Mình hay quên ngữ pháp khi đi thi", "Giải thích ngữ pháp thật kỹ"),
    ("I always forget this grammar rule", "Explain grammar simply"),
    ("我总是忘掉这个语法", "多讲语法"),
])
def test_an_ordinary_learning_message_changes_no_note(message, kept):
    assert notes_the_message_changes(message, [note(kept)]) == ()


@pytest.mark.parametrize(("message", "kept", "intent"), [
    ("Quên ghi chú về ví dụ đó đi.", "Mình thích ví dụ thật ngắn", FORGET),
    ("À không, ví dụ dài hơn một chút thì em dễ hiểu hơn.", "Mình thích ví dụ thật ngắn", "correct"),
    ("Forget that note please", "Explain in English please", FORGET),
    ("忘掉那条笔记吧", "帮我用中文解释", FORGET),
    ("Đừng giải thích bằng tiếng Anh nữa, dùng tiếng Việt", "Giải thích bằng tiếng Anh", "correct"),
    # a stopped phrase plus real content still matches
    ("Thôi, đừng cho mình ví dụ ngắn nữa", "Cho mình ví dụ ngắn", "correct"),
    ("别再帮我举例子了", "帮我多举例子", "correct"),
    ("Quên cái ví dụ ngắn đó đi", "Cho mình ví dụ ngắn", FORGET),
    ("quên giùm mình cái ví dụ ngắn", "Cho mình ví dụ ngắn", FORGET),
    ("Quên chuyện ví dụ ngắn", "Cho mình ví dụ ngắn", FORGET),
    ("Forget the short examples", "Give me short examples", FORGET),
    ("忘记那个例子吧", "多举例子", FORGET),
    ("把那个例子忘了", "多举例子", FORGET),
])
def test_a_real_note_request_still_matches(message, kept, intent):
    assert notes_the_message_changes(message, [note(kept)])
    assert note_intent(message) == intent


def test_content_overlap_picks_only_the_note_it_is_about():
    short, chinese = note("Cho mình ví dụ ngắn", "n-1"), note("Giải thích bằng tiếng Trung", "n-2")
    assert notes_the_message_changes("Thôi, đừng cho mình ví dụ ngắn nữa", [short, chinese]) == (short,)


def test_a_decomposed_note_noun_still_counts():
    import unicodedata

    decomposed = unicodedata.normalize("NFD", "Quên ghi chú đó đi")
    assert notes_the_message_changes(decomposed, [note("Mình thích ví dụ ngắn")])
