"""One question of the reading check, answered as the learner answers it.

The canonical check (D-067, "Reading · comprehension result") gives the verdict
and the lines that settle it straight after the answer, so a question has to be
scorable on its own. What must not change with it is what a learner's record
means: the attempt is still the whole set, written once, and scoring a single
question records nothing.
"""
import json
import sqlite3

import pytest

from writing_coach.becoming_reading import (
    ReadingAnswerIn,
    ReadingChoiceIn,
    configure_becoming_reading,
    grade_reading_answer,
    submit_reading_answers,
)
from writing_coach.becoming_reading_selftest import fake_generate
from writing_coach.persistence.specialized_repository import (
    SQLiteSpecializedLearningRepository,
)

QUESTIONS = [
    {
        "id": 1,
        "question": "Why did the team change its meeting?",
        "options": ["Most updates could be read first.", "The office closed.", "c", "d"],
        "correct_index": 0,
        "explanation_vi": "Phần lớn cập nhật có thể đọc trước.",
        "evidence_fragment": "most updates could be read before the call",
    },
    {
        "id": 2,
        "question": "What does the manager send in advance?",
        "options": ["A video", "A short written summary", "c", "d"],
        "correct_index": 1,
        "explanation_vi": "Người quản lý gửi bản tóm tắt ngắn.",
        "evidence_fragment": "a short written summary",
    },
]


@pytest.fixture()
def session(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # Specialized initialization upgrades the core learning tables, so they
    # exist first here exactly as they do in the runtime.
    conn.execute(
        """
        CREATE TABLE saved_words(
            word TEXT PRIMARY KEY COLLATE NOCASE,
            phonetic TEXT NOT NULL DEFAULT '',
            part_of_speech TEXT NOT NULL DEFAULT '',
            definition TEXT NOT NULL DEFAULT '',
            added_at TEXT NOT NULL,
            translation_vi TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE vocabulary_learning(
            word TEXT PRIMARY KEY COLLATE NOCASE,
            source_essay_id INTEGER,
            source_fragment TEXT NOT NULL DEFAULT '',
            source_kind TEXT NOT NULL DEFAULT 'manual',
            focus_note TEXT NOT NULL DEFAULT '',
            review_stage INTEGER NOT NULL DEFAULT 0,
            successful_recalls INTEGER NOT NULL DEFAULT 0,
            lapse_count INTEGER NOT NULL DEFAULT 0,
            last_reviewed_at TEXT NOT NULL DEFAULT '',
            next_review_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    repository = SQLiteSpecializedLearningRepository(lambda: conn)
    configure_becoming_reading(repository, fake_generate)
    repository.initialize()
    created = repository.create_reading_session_record(
        {
            "created_at": "2026-09-23T07:00:00+07:00",
            "language_code": "en",
            "target_level": "B2",
            "topic": "work",
            "learner_goal": "work",
            "title": "A Shorter Weekly Meeting",
            "passage": "Most updates could be read before the call.",
            "questions": QUESTIONS,
            "recycled_words": [],
            "generation_mode": "generated",
        }
    )
    return conn, int(created["id"])


def test_one_question_is_scored_on_its_own(session):
    _, session_id = session
    answered = grade_reading_answer(session_id, 0, ReadingChoiceIn(choice=0))
    assert answered["valid"] is True
    assert answered["index"] == 0
    assert answered["result"]["correct"] is True
    assert answered["result"]["correct_index"] == 0
    assert answered["result"]["evidence_fragment"] == QUESTIONS[0]["evidence_fragment"]
    assert answered["claim"] == "comprehension_check_only"

    wrong = grade_reading_answer(session_id, 1, ReadingChoiceIn(choice=0))
    assert wrong["result"]["correct"] is False
    assert wrong["result"]["selected_index"] == 0


def test_scoring_one_question_records_no_attempt(session):
    conn, session_id = session
    grade_reading_answer(session_id, 0, ReadingChoiceIn(choice=0))
    grade_reading_answer(session_id, 1, ReadingChoiceIn(choice=1))
    attempts = conn.execute("SELECT COUNT(*) FROM reading_attempts").fetchone()[0]
    assert attempts == 0

    # The set, once, is still what an attempt is.
    scored = submit_reading_answers(session_id, ReadingAnswerIn(answers=[0, 1]))
    assert scored["correct_count"] == 2
    assert conn.execute("SELECT COUNT(*) FROM reading_attempts").fetchone()[0] == 1


def test_a_question_nobody_asked_is_refused(session):
    _, session_id = session
    for index in (-1, 2, 99):
        refused = grade_reading_answer(session_id, index, ReadingChoiceIn(choice=0))
        assert refused["found"] is True
        assert refused["valid"] is False
    assert grade_reading_answer(9999, 0, ReadingChoiceIn(choice=0)) == {"found": False}


def test_an_option_the_question_does_not_offer_is_refused(session):
    _, session_id = session
    conn, _ = session
    short = dict(QUESTIONS[0], options=["only", "two"])
    conn.execute(
        "UPDATE reading_sessions SET questions_json=? WHERE id=?",
        (json.dumps([short]), session_id),
    )
    conn.commit()
    refused = grade_reading_answer(session_id, 0, ReadingChoiceIn(choice=3))
    assert refused["valid"] is False
