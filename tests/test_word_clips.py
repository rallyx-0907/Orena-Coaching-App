"""Where a word is actually said.

The one thing worth holding hardest: a clip is a real moment in real media.
A lesson that merely *lists* a word in its vocabulary is not evidence that the
word is spoken in any particular segment of it, so only the segment's own
transcript decides.
"""

from types import SimpleNamespace

from writing_coach import word_clips


def lesson(lesson_id, title, segments, *, topic="talk"):
    return SimpleNamespace(
        lesson_id=lesson_id,
        topic=topic,
        artwork="listen",
        vocabulary=("想",),
        media_object=SimpleNamespace(asset=SimpleNamespace(title=title)),
        playback=SimpleNamespace(url=f"https://example.test/{lesson_id}.mp3", kind="audio"),
        source=SimpleNamespace(segments=segments),
    )


def segment(start, end, text, *, pinyin="", vi=""):
    return {
        "start_ms": start,
        "end_ms": end,
        "original_text": text,
        "pinyin": pinyin,
        "translations": {"vi": vi} if vi else {},
    }


def test_only_segments_that_really_say_the_word_come_back():
    lessons = [
        lesson(
            "order",
            "在餐厅点菜",
            [
                segment(0, 3000, "你好，请问几位？"),
                segment(72000, 78000, "我们想要一张靠窗的桌子。", pinyin="Wǒmen xiǎng yào…", vi="Chúng tôi muốn một bàn cạnh cửa sổ."),
            ],
        )
    ]
    found = word_clips.clips_for("想", lessons, support="vi")
    assert [clip["text"] for clip in found] == ["我们想要一张靠窗的桌子。"]
    assert found[0]["at"] == "01:12"
    assert found[0]["title"] == "在餐厅点菜"
    assert found[0]["translation"] == "Chúng tôi muốn một bàn cạnh cửa sổ."
    assert found[0]["seconds"] == 6


def test_a_lesson_that_lists_the_word_but_never_says_it_gives_no_clip():
    lessons = [lesson("quiet", "Nothing said", [segment(0, 2000, "你好。")])]
    assert word_clips.clips_for("想", lessons, support="vi") == []


def test_the_list_is_bounded_and_stops_where_it_is_told():
    lessons = [
        lesson("many", "Many", [segment(i * 1000, i * 1000 + 900, "我想。") for i in range(20)])
    ]
    assert len(word_clips.clips_for("想", lessons, support="vi", limit=3)) == 3


def test_the_same_word_twice_is_the_same_answer_twice():
    lessons = [
        lesson("a", "A", [segment(0, 1000, "我想去。")]),
        lesson("b", "B", [segment(0, 1000, "我想看。")]),
    ]
    once = word_clips.clips_for("想", lessons, support="vi")
    again = word_clips.clips_for("想", lessons, support="vi")
    assert once == again
    assert [clip["lessonId"] for clip in once] == ["a", "b"]


def test_the_timestamp_is_written_the_way_the_frame_writes_it():
    assert word_clips.at_label(0) == "00:00"
    assert word_clips.at_label(72000) == "01:12"
    assert word_clips.at_label(108000) == "01:48"


def test_a_translation_the_learner_cannot_read_is_left_out_rather_than_guessed():
    lessons = [lesson("x", "X", [segment(0, 1000, "我想。", vi="Tôi muốn.")])]
    found = word_clips.clips_for("想", lessons, support="fr")
    assert found[0]["translation"] == ""


def test_how_to_play_it_travels_with_the_clip():
    lessons = [lesson("x", "X", [segment(0, 1000, "我想。")])]
    clip = word_clips.clips_for("想", lessons, support="vi")[0]
    assert clip["url"].endswith("x.mp3")
    assert clip["kind"] == "audio"
    assert clip["startMs"] == 0 and clip["endMs"] == 1000


def test_a_lesson_with_no_title_is_still_recognisable_by_its_topic():
    bare = lesson("x", "", [segment(0, 1000, "我想。")], topic="ordering")
    assert word_clips.clips_for("想", [bare], support="vi")[0]["title"] == "ordering"
