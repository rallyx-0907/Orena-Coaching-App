"""Does the proposed schema actually refuse what its docstring says it refuses?

The rehearsal for `migrations/proposed/20260923_0013_my_library_and_entry_
identity.py`, kept in the repository so a reviewer can re-run it rather than
take the record on trust. It is not part of CI and touches no runtime: it talks
only to a throwaway PostgreSQL that the rehearsal starts and removes.

    docker run -d --name orena-schema-rehearsal-0013 -e POSTGRES_PASSWORD=rehearsal       -e POSTGRES_DB=rehearsal -p 55433:5432 postgres:16-alpine
    # in the app image, with migrations/proposed added to version_locations:
    alembic -c <ini> upgrade 20260923_0013
    python scripts/rehearse_my_library_schema.py
    docker rm -f orena-schema-rehearsal-0013

Each probe writes a row that must fail, and one that must succeed. A probe that
passed silently would be worthless, so every one of them asserts the error it
expects by name.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

URL = "postgresql+psycopg://postgres:rehearsal@host.docker.internal:55433/rehearsal"
engine = create_engine(URL)
now = datetime.now(UTC)
results: list[str] = []


def refuses(label: str, statements: list[tuple[str, dict]], expect: str) -> None:
    try:
        with engine.begin() as connection:
            for sql, params in statements:
                connection.execute(text(sql), params)
    except (IntegrityError, DBAPIError) as error:
        message = str(error.orig if hasattr(error, "orig") else error)
        assert expect in message, f"{label}: expected {expect!r} in {message!r}"
        results.append(f"REFUSED {label} ({expect})")
        return
    raise AssertionError(f"{label}: the database accepted what it must refuse")


def accepts(label: str, statements: list[tuple[str, dict]]) -> None:
    with engine.begin() as connection:
        for sql, params in statements:
            connection.execute(text(sql), params)
    results.append(f"ACCEPTED {label}")


USER = uuid.uuid4()
with engine.begin() as conn:
    conn.execute(
        text(
            "INSERT INTO users (id, user_key, email, name, picture, role, created_at)"
            " VALUES (:id, :key, :email, '', '', 'user', :now)"
        ),
        {"id": USER, "key": f"rehearsal-{USER}", "email": f"rehearsal-{USER}@example.test", "now": now},
    )

SAVED = uuid.uuid4()
with engine.begin() as conn:
    conn.execute(
        text(
            "INSERT INTO saved_words (id, user_id, language_code, word, normalized_word,"
            " phonetic, part_of_speech, definition, translation_vi, source_fragment, source_kind,"
            " focus_note, review_stage, successful_recalls, lapse_count, added_at, updated_at)"
            " VALUES (:id, :user, 'zh', :w, :w, '', '', '', '', '', 'manual', '', 0, 0, 0,"
            " :now, :now)"
        ),
        {"id": SAVED, "user": USER, "w": "行", "now": now},
    )

ITEM = (
    "INSERT INTO library_items (id, user_id, language_code, kind, saved_word_id, source_id,"
    " relationship, created_at, updated_at) VALUES (:id, :user, :lang, :kind, :saved, :source,"
    " :rel, :now, :now)"
)
base = {"user": USER, "lang": "zh", "now": now}

# A. entry identity ---------------------------------------------------------
refuses(
    "a linked saved word without its durable identity",
    [(
        "UPDATE saved_words SET entry_id = :entry WHERE id = :id",
        {"entry": uuid.uuid4(), "id": SAVED},
    )],
    # The FK fires first for a non-existent entry, which is also a refusal we
    # want; the check is probed separately below with a real entry.
    "saved_words",
)

ENTRY = uuid.uuid4()
with engine.begin() as conn:
    conn.execute(
        text(
            "INSERT INTO vocabulary_entries (id, language_code, term, normalized_term,"
            " identity_key, sense_key, pronunciations, readings, short_meanings,"
            " detailed_definitions, part_of_speech, examples, usage_notes, orthography, level,"
            " framework, topic, content_origins, provenance, created_at, updated_at)"
            " VALUES (:id, 'zh', :t, :t, :k, '', '[]', :readings, '[]', '[]', '', '[]', '[]',"
            " '{}', '', '', '', '{}', '{}', :now, :now)"
        ),
        {
            "id": ENTRY,
            "t": "行",
            "k": f"zh:行:xing2:{ENTRY}",
            # Two readings, so the ambiguity the probes below are about is real.
            "readings": '[{"text": "xíng"}, {"text": "háng"}]',
            "now": now,
        },
    )
refuses(
    "an entry link with an empty identity key",
    [("UPDATE saved_words SET entry_id = :entry WHERE id = :id", {"entry": ENTRY, "id": SAVED})],
    "ck_saved_words_entry_identity",
)
accepts(
    "an entry link that carries its identity and its reading",
    [(
        "UPDATE saved_words SET entry_id = :entry, entry_identity_key = :k, reading_key = 'xíng'"
        " WHERE id = :id",
        {"entry": ENTRY, "k": f"zh:行:xing2:{ENTRY}", "id": SAVED},
    )],
)
accepts(
    # Round 1, P2-2: the database accepts a link to a two-reading entry with no
    # reading. That is why the invariant is enforced at the write path and has
    # a regression test of its own - this probe records the gap, it does not
    # pretend the schema closes it.
    "a link to an ambiguous entry with no reading (the write path must refuse this)",
    [(
        "UPDATE saved_words SET entry_id = :entry, entry_identity_key = :k, reading_key = ''"
        " WHERE id = :id",
        {"entry": ENTRY, "k": f"zh:行:xing2:{ENTRY}", "id": SAVED},
    )],
)
accepts(
    "a hand-saved word with neither",
    [(
        "INSERT INTO saved_words (id, user_id, language_code, word, normalized_word, phonetic,"
        " part_of_speech, definition, translation_vi, source_fragment, source_kind, focus_note,"
        " review_stage, successful_recalls, lapse_count, added_at, updated_at)"
        " VALUES (:id, :user, 'zh', :w, :w, '', '', '', '', '', 'manual', '', 0, 0, 0, :now, :now)",
        {"id": uuid.uuid4(), "user": USER, "w": "重", "now": now},
    )],
)

# B. the kept-item relation -------------------------------------------------
refuses(
    "a word row with no saved word behind it",
    [(ITEM, {**base, "id": uuid.uuid4(), "kind": "word", "saved": None, "source": "", "rel": "kept"})],
    "ck_library_items_word_link",
)
refuses(
    "a reading row that points at a saved word",
    [(ITEM, {**base, "id": uuid.uuid4(), "kind": "reading", "saved": SAVED, "source": "r1", "rel": "kept"})],
    "ck_library_items_word_link",
)
refuses(
    "a non-word row with no source",
    [(ITEM, {**base, "id": uuid.uuid4(), "kind": "reading", "saved": None, "source": "", "rel": "kept"})],
    "ck_library_items_source",
)
refuses(
    # Round 1, P3-3: a word is named by its row, so it must not also carry a
    # routing string that means nothing.
    "a word row that also carries a source string",
    [(ITEM, {**base, "id": uuid.uuid4(), "kind": "word", "saved": SAVED, "source": "reading:9", "rel": "kept"})],
    "ck_library_items_source",
)
refuses(
    "a kind nobody draws",
    [(ITEM, {**base, "id": uuid.uuid4(), "kind": "podcast", "saved": None, "source": "p1", "rel": "kept"})],
    "ck_library_items_kind",
)

WORD_ITEM = uuid.uuid4()
accepts(
    "the word the learner kept",
    [(ITEM, {**base, "id": WORD_ITEM, "kind": "word", "saved": SAVED, "source": "", "rel": "kept"})],
)
refuses(
    "keeping the same word twice",
    [(ITEM, {**base, "id": uuid.uuid4(), "kind": "word", "saved": SAVED, "source": "", "rel": "kept"})],
    "ux_library_items_word",
)
READING_ITEM = uuid.uuid4()
accepts(
    "a passage the learner started",
    [(ITEM, {**base, "id": READING_ITEM, "kind": "reading", "saved": None, "source": "reading:1", "rel": "started"})],
)
refuses(
    "starting the same passage twice",
    [(ITEM, {**base, "id": uuid.uuid4(), "kind": "reading", "saved": None, "source": "reading:1", "rel": "started"})],
    "ux_library_items_source",
)
accepts(
    "keeping the passage as well as starting it",
    [(ITEM, {**base, "id": uuid.uuid4(), "kind": "reading", "saved": None, "source": "reading:1", "rel": "kept"})],
)

# C. one collection, one kind ----------------------------------------------
COLLECTION = uuid.uuid4()
accepts(
    "a collection of words",
    [(
        "INSERT INTO library_collections (id, user_id, language_code, kind, title, created_at,"
        " updated_at) VALUES (:id, :user, :lang, 'word', 'Cảm xúc', :now, :now)",
        {**base, "id": COLLECTION},
    )],
)
refuses(
    "a collection with no name",
    [(
        "INSERT INTO library_collections (id, user_id, language_code, kind, title, created_at,"
        " updated_at) VALUES (:id, :user, :lang, 'word', '', :now, :now)",
        {**base, "id": uuid.uuid4()},
    )],
    "ck_library_collections_title",
)
MEMBER = (
    "INSERT INTO library_collection_members (collection_id, item_id, kind, position, created_at)"
    " VALUES (:collection, :item, :kind, 0, :now)"
)
accepts("a word in a collection of words", [(MEMBER, {**base, "collection": COLLECTION, "item": WORD_ITEM, "kind": "word"})])
refuses(
    "a passage in a collection of words",
    [(MEMBER, {**base, "collection": COLLECTION, "item": READING_ITEM, "kind": "reading"})],
    "fk_library_member_collection",
)
refuses(
    "a passage smuggled in under the collection's kind",
    [(MEMBER, {**base, "collection": COLLECTION, "item": READING_ITEM, "kind": "word"})],
    "fk_library_member_item",
)

# D. what deleting does -----------------------------------------------------
with engine.begin() as conn:
    conn.execute(text("DELETE FROM saved_words WHERE id = :id"), {"id": SAVED})
with engine.connect() as conn:
    left = conn.execute(
        text("SELECT COUNT(*) FROM library_items WHERE id = :id"), {"id": WORD_ITEM}
    ).scalar()
    members = conn.execute(text("SELECT COUNT(*) FROM library_collection_members")).scalar()
assert left == 0, "deleting a saved word must remove the relationship to it"
assert members == 0, "and the membership with it"
results.append("CASCADED deleting a saved word removes its relationship and its membership")

with engine.begin() as conn:
    conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": USER})
with engine.connect() as conn:
    rest = conn.execute(text("SELECT COUNT(*) FROM library_items")).scalar()
    entry = conn.execute(
        text("SELECT COUNT(*) FROM vocabulary_entries WHERE id = :id"), {"id": ENTRY}
    ).scalar()
assert rest == 0, "deleting the account removes everything it kept"
assert entry == 1, "and leaves the shared catalogue alone"
results.append("CASCADED deleting the account removes what it kept and leaves the catalogue")

# E. what two writers do at once -------------------------------------------
# Round 1 ran these ad hoc and asked for them to be kept. Both are races the
# application relies on: the partial unique index decides an insert race, and
# the version counter decides an update race.
import threading  # noqa: E402 - the races are the last thing the rehearsal does

RACE_USER = uuid.uuid4()
RACE_WORD = uuid.uuid4()
with engine.begin() as conn:
    conn.execute(
        text(
            "INSERT INTO users (id, user_key, email, name, picture, role, created_at)"
            " VALUES (:id, :key, :email, '', '', 'user', :now)"
        ),
        {"id": RACE_USER, "key": f"race-{RACE_USER}", "email": f"race-{RACE_USER}@example.test", "now": now},
    )
    conn.execute(
        text(
            "INSERT INTO saved_words (id, user_id, language_code, word, normalized_word, phonetic,"
            " part_of_speech, definition, translation_vi, source_fragment, source_kind, focus_note,"
            " review_stage, successful_recalls, lapse_count, added_at, updated_at)"
            " VALUES (:id, :user, 'zh', :w, :w, '', '', '', '', '', 'manual', '', 0, 0, 0, :now, :now)"
        ),
        {"id": RACE_WORD, "user": RACE_USER, "w": "海", "now": now},
    )

start = threading.Barrier(2)
outcomes: list[str] = []
lock = threading.Lock()


def keep_it() -> None:
    start.wait()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(ITEM),
                {
                    "id": uuid.uuid4(), "user": RACE_USER, "lang": "zh", "kind": "word",
                    "saved": RACE_WORD, "source": "", "rel": "kept", "now": now,
                },
            )
        result = "kept"
    except (IntegrityError, DBAPIError) as error:
        result = "refused" if "ux_library_items_word" in str(error.orig) else f"other: {error}"
    with lock:
        outcomes.append(result)


threads = [threading.Thread(target=keep_it) for _ in range(2)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
assert sorted(outcomes) == ["kept", "refused"], outcomes
with engine.connect() as conn:
    kept = conn.execute(
        text("SELECT COUNT(*) FROM library_items WHERE saved_word_id = :id"), {"id": RACE_WORD}
    ).scalar()
assert kept == 1, kept
results.append("RACED two writers keeping the same word: one row, the other refused")

# The version counter: both readers see version 1, only one write lands.
pinned: list[int] = []
start = threading.Barrier(2)


def pin_it() -> None:
    start.wait()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "UPDATE library_items SET pinned_at = :now, version = version + 1"
                " WHERE saved_word_id = :id AND version = 1"
            ),
            {"now": now, "id": RACE_WORD},
        ).rowcount
    with lock:
        pinned.append(rows)


threads = [threading.Thread(target=pin_it) for _ in range(2)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
assert sorted(pinned) == [0, 1], pinned
with engine.connect() as conn:
    version = conn.execute(
        text("SELECT version FROM library_items WHERE saved_word_id = :id"), {"id": RACE_WORD}
    ).scalar()
assert version == 2, version
results.append("RACED two writers pinning it: one update, one no-op, version 2 - no lost write")

with engine.begin() as conn:
    conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": RACE_USER})

for line in results:
    print(" ", line)
print(f"{len(results)} probes")
