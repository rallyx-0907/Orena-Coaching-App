"""Orena Memory M2 (ORENA_MEMORY.md rev 4.1 §4.1, §4.4, §6; D-222): the store contract for explicit memory, the switch,
the version and suppression, run against BOTH `InMemoryMemoryStore` and `PostgresMemoryRepository`.

The PostgreSQL half skips unless `ORENA_TEST_POSTGRES_URL` names a throwaway database (it upgrades it to head). The
summary and continuity contract (checkpoint, finalise, tombstones) is M3's table and stays in
`tests/test_agent_memory_store.py`, against the fake, until M3 (decision 2 of the M2 plan).

    ORENA_TEST_POSTGRES_URL=postgresql+psycopg://user:pw@host/orena_memory_rehearsal \\
        python -m pytest tests/test_agent_memory_contract.py
"""

from __future__ import annotations

import os
import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from writing_coach.agent.memory_keys import MemoryKeys
from writing_coach.agent.memory_store import (
    ANY_LANGUAGE,
    CONTINUITY,
    EXPLICIT,
    EXPLICIT_TTL,
    LIMITS,
    InMemoryMemoryStore,
    MemoryLimit,
    MemoryOff,
    MemoryScope,
    memory_section,
)

T0 = datetime(2026, 10, 18, 9, 0, tzinfo=UTC)
KEYS = "v1:" + "k" * 40
URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")


@pytest.fixture(scope="module")
def engine():
    if not URL:
        pytest.skip("ORENA_TEST_POSTGRES_URL is not set; PostgreSQL contract not run")
    sqlalchemy = pytest.importorskip("sqlalchemy")
    from alembic import command

    from writing_coach.persistence.runtime import _runtime_alembic_config

    cfg = _runtime_alembic_config()
    cfg.set_main_option("sqlalchemy.url", URL.replace("%", "%%"))
    command.upgrade(cfg, "head")
    engine = sqlalchemy.create_engine(URL, future=True, pool_size=12, max_overflow=4)
    yield engine
    engine.dispose()


def _incarnation(engine, user_id: uuid.UUID | None = None) -> MemoryScope:
    from sqlalchemy import text

    user_id = user_id or uuid.uuid4()
    incarnation_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id, user_key, email, name, picture, role, created_at) "
                          "VALUES (:id, :key, '', '', '', 'user', now()) ON CONFLICT (id) DO NOTHING"),
                     {"id": user_id, "key": f"memory-{user_id}"})  # fmt: skip
        conn.execute(text("UPDATE account_incarnations SET status = 'deleted', deleted_at = now() WHERE user_id = :u AND status = 'active'"),
                     {"u": user_id})  # fmt: skip
        epoch = conn.execute(text("SELECT coalesce(max(epoch), 0) + 1 FROM account_incarnations WHERE user_id = :u"),
                             {"u": user_id}).scalar()  # fmt: skip
        conn.execute(text("INSERT INTO account_incarnations (id, user_id, epoch, status, created_at) "
                          "VALUES (:id, :u, :e, 'active', now())"), {"id": incarnation_id, "u": user_id, "e": epoch})
    return MemoryScope(str(user_id), str(incarnation_id))


class Fixture:
    """A store and two learners' scopes, plus how to recreate learner A as a new incarnation."""

    def __init__(self, kind: str, engine=None, keys: str = KEYS):
        self.kind, self.engine, self.keys = kind, engine, MemoryKeys.parse(keys)
        if kind == "fake":
            self.store = InMemoryMemoryStore(self.keys)
            self.a, self.b = MemoryScope("user-a", "inc-a1"), MemoryScope("user-b", "inc-b1")
        else:
            from writing_coach.persistence.memory_repository import PostgresMemoryRepository

            self.store = PostgresMemoryRepository(engine, self.keys)
            self.a, self.b = _incarnation(engine), _incarnation(engine)

    def recreated(self) -> MemoryScope:
        if self.kind == "fake":
            return MemoryScope(self.a.user_id, "inc-a2")
        return _incarnation(self.engine, uuid.UUID(self.a.user_id))

    def rekeyed(self, keys: str):
        """The same rows under another key configuration (an operator adds or drops a version)."""
        if self.kind == "fake":
            self.store._keys = MemoryKeys.parse(keys)
            return self.store
        from writing_coach.persistence.memory_repository import PostgresMemoryRepository

        return PostgresMemoryRepository(self.engine, MemoryKeys.parse(keys))

    def continuity(self, scope: MemoryScope, slot: str, code: str, now: datetime = T0):
        """A continuity item as M3's checkpoint writes it (fake: through checkpoint; PostgreSQL: the row itself)."""
        if self.kind == "fake":
            self.store.checkpoint(scope, agent_session_id=f"s-{uuid.uuid4()}", language="zh", turns_covered=4,
                                  summary={"practised": [], "focus": None, "open_task": None},
                                  context=[(slot, code)], now=now)  # fmt: skip
            return
        from sqlalchemy import text

        version, value_key = self.keys.stamp(slot, code)
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO learner_memories (id, incarnation_id, user_id, language_code, class, kind, slot, text, code,"
                " value_key, key_version, source, expires_at, created_at, updated_at)"
                " VALUES (:id, :i, :u, 'zh', 'continuity', 'context', :slot, :code, :code, :vk, :kv, 'summary',"
                " :exp, :now, :now)"),
                {"id": uuid.uuid4(), "i": scope.incarnation_id, "u": scope.user_id, "slot": slot, "code": code,
                 "vk": value_key, "kv": version, "exp": now + timedelta(days=14), "now": now})  # fmt: skip


@pytest.fixture(params=["fake", "postgres"])
def mem(request):
    if request.param == "fake":
        return Fixture("fake")
    return Fixture("postgres", request.getfixturevalue("engine"))


def add(store, scope, text, *, language="zh", kind="goal", slot=None, now=T0):
    return store.add_explicit(scope, language=language, kind=kind, text=text, slot=slot, source="learner_asked",
                              now=now)  # fmt: skip


# --- scope ----------------------------------------------------------------------------------------------------------


def test_learners_and_incarnations_never_see_each_other(mem):
    add(mem.store, mem.a, "Tôi học để phỏng vấn")
    assert mem.store.items(mem.b, "zh", T0) == []
    assert mem.store.items(mem.recreated(), "zh", T0) == []  # a deleted and recreated account: a new incarnation


def test_language_scope_and_the_any_language_items(mem):
    add(mem.store, mem.a, "ví dụ ngắn", kind="preference")
    add(mem.store, mem.a, "giải thích bằng tiếng Việt", kind="preference", language=ANY_LANGUAGE)
    assert {i.text for i in mem.store.items(mem.a, "zh", T0)} == {"ví dụ ngắn", "giải thích bằng tiếng Việt"}
    assert {i.text for i in mem.store.items(mem.a, "en", T0)} == {"giải thích bằng tiếng Việt"}


# --- version and switch ---------------------------------------------------------------------------------------------


def test_every_explicit_change_bumps_the_version(mem):
    s, a = mem.store, mem.a
    seen = [s.state(a).version]

    def changed():
        seen.append(s.state(a).version)
        assert seen[-1] > seen[-2]

    item = add(s, a, "đi làm")
    changed()
    s.delete_item(a, item.id, T0)
    changed()
    s.set_enabled(a, False)
    changed()
    s.set_enabled(a, True)
    changed()
    add(s, a, "thi HSK")
    s.delete_all(a, "items", T0)
    assert s.state(a).version > seen[-1] + 1


def test_a_missing_state_reads_as_enabled_version_zero(mem):
    state = mem.store.state(mem.a)
    assert state.enabled and state.version == 0 and mem.store.probe(mem.a, T0) == state


def test_off_writes_nothing_and_sends_nothing_but_delete_and_switch_still_work(mem):
    s, a = mem.store, mem.a
    item = add(s, a, "đi làm")
    s.set_enabled(a, False)
    with pytest.raises(MemoryOff):
        add(s, a, "thi HSK")
    assert memory_section(s, a, "zh", T0) is None
    assert [i.id for i in s.items(a, "zh", T0)] == [item.id]  # stored items stay
    assert s.delete_item(a, item.id, T0) and s.items(a, "zh", T0) == []  # deleting works while OFF
    assert s.set_enabled(a, True).enabled and s.items(a, "zh", T0) == []  # nothing back-filled


def test_a_pack_built_at_an_older_version_is_detectable_and_a_delete_never_reaches_the_next_section(mem):
    s, a = mem.store, mem.a
    item = add(s, a, "Mình học để phỏng vấn")
    built = memory_section(s, a, "zh", T0)
    assert built.explicit == ({"kind": "goal", "text": "Mình học để phỏng vấn"},)
    assert any(e["id"] == item.id for e in built.provenance) and built.version == s.state(a).version
    s.delete_item(a, item.id, T0)  # another worker
    assert s.probe(a, T0).version != built.version
    after = memory_section(s, a, "zh", T0)
    assert after.explicit == () and after.version == s.state(a).version


# --- explicit -------------------------------------------------------------------------------------------------------


def test_a_retried_note_does_not_duplicate_and_a_single_valued_slot_keeps_the_latest(mem):
    s, a = mem.store, mem.a
    first = add(s, a, "Đi làm")
    again = add(s, a, " đi  làm ")
    assert again.id == first.id and len(s.items(a, "zh", T0)) == 1
    add(s, a, "concise", kind="preference", slot="explanation_length")
    add(s, a, "detailed", kind="preference", slot="explanation_length")
    assert [i.text for i in s.items(a, "zh", T0) if i.slot == "explanation_length"] == ["detailed"]


def test_a_kept_note_is_kept_for_the_pilot_retention_and_then_gone(mem):
    """Pilot data is kept up to 6 months (owner, PRE-005, 2026-10-18): a kept note expires EXPLICIT_TTL after it was
    last asked for, and is then invisible to every read, as any expired item is, until the sweep deletes it."""
    s, a = mem.store, mem.a
    item = add(s, a, "Phỏng vấn xin việc")
    assert item.expires_at == T0 + EXPLICIT_TTL and EXPLICIT_TTL <= timedelta(days=181)
    assert [i.id for i in s.items(a, "zh", T0 + EXPLICIT_TTL - timedelta(minutes=1))] == [item.id]
    assert s.items(a, "zh", T0 + EXPLICIT_TTL) == []
    section = memory_section(s, a, "zh", T0 + EXPLICIT_TTL)
    assert section is None or section.explicit == ()


def test_asking_to_keep_the_same_words_again_renews_the_retention(mem):
    s, a = mem.store, mem.a
    first = add(s, a, "Phỏng vấn xin việc")
    later = T0 + timedelta(days=100)
    again = add(s, a, "phỏng vấn xin việc", now=later)
    assert again.id == first.id and again.expires_at == later + EXPLICIT_TTL
    assert [i.id for i in s.items(a, "zh", T0 + EXPLICIT_TTL + timedelta(days=1))] == [first.id]


def test_a_note_used_in_a_turn_is_kept_six_months_from_that_use(mem):
    """Owner (Privacy Policy, via Hermes 2026-10-19): a note expires 6 months after it was last used - kept again by
    the learner, or read into the model's context in a real turn, whichever is later. `renew` moves only live explicit
    notes of this scope, while memory is ON, and says how many."""
    s, a = mem.store, mem.a
    item = add(s, a, "Phỏng vấn xin việc")
    used = T0 + timedelta(days=170)
    assert s.renew(a, [item.id], used) == 1
    assert [i.expires_at for i in s.items(a, "zh", used)] == [used + EXPLICIT_TTL]
    assert [i.id for i in s.items(a, "zh", T0 + EXPLICIT_TTL + timedelta(days=30))] == [item.id]
    assert s.renew(a, [str(uuid.uuid4()), "not-an-id"], used) == 0
    lapsed = add(s, a, "Luyện HSK4", kind="plan")
    late = T0 + EXPLICIT_TTL + timedelta(days=1)
    assert s.renew(a, [lapsed.id], late) == 0 and [i.id for i in s.items(a, "zh", late)] == [item.id]  # gone stays gone


def test_renewing_moves_nothing_while_memory_is_off_or_in_another_scope(mem):
    s, a = mem.store, mem.a
    item = add(s, a, "Phỏng vấn xin việc")
    assert s.renew(mem.b, [item.id], T0 + timedelta(days=10)) == 0
    s.set_enabled(a, False)
    assert s.renew(a, [item.id], T0 + timedelta(days=10)) == 0
    s.set_enabled(a, True)
    assert [i.expires_at for i in s.items(a, "zh", T0)] == [T0 + EXPLICIT_TTL]


def test_after_expiry_the_same_words_and_a_new_slot_value_can_be_kept(mem):
    """Review of #292 P1-1: an expired row still holds the unique (value_key) and single-slot indexes until it is
    deleted, so keeping again after expiry clears the learner's own expired notes first."""
    s, a = mem.store, mem.a
    old = add(s, a, "Phỏng vấn xin việc")
    add(s, a, "concise", kind="preference", slot="explanation_length")
    later = T0 + EXPLICIT_TTL + timedelta(days=1)
    again = add(s, a, "Phỏng vấn xin việc", now=later)
    slot = add(s, a, "concise", kind="preference", slot="explanation_length", now=later)
    assert again.id != old.id and again.expires_at == later + EXPLICIT_TTL
    assert sorted(i.id for i in s.items(a, "zh", later)) == sorted([again.id, slot.id])


def test_expired_notes_do_not_count_against_the_limit(mem):
    s, a = mem.store, mem.a
    for n in range(LIMITS[EXPLICIT]):
        add(s, a, f"ghi chú số {n}")
    later = T0 + EXPLICIT_TTL
    assert add(s, a, "ghi chú mới", now=later).text == "ghi chú mới"


def test_explicit_past_the_limit_is_refused(mem):
    s, a = mem.store, mem.a
    for n in range(LIMITS[EXPLICIT]):
        add(s, a, f"mục tiêu {n}")
    version = s.state(a).version
    with pytest.raises(MemoryLimit):
        add(s, a, "một nữa")
    assert s.state(a).version == version and len(s.items(a, "zh", T0)) == LIMITS[EXPLICIT]
    assert add(s, a, "mục tiêu 3").text == "mục tiêu 3"  # the same words again is a retry, not a new item


def test_deleting_an_unknown_or_foreign_item_is_false(mem):
    s = mem.store
    item = add(s, mem.a, "đi làm")
    assert not s.delete_item(mem.b, item.id, T0)
    assert not s.delete_item(mem.a, str(uuid.uuid4()), T0) and not s.delete_item(mem.a, "not-an-id", T0)
    assert [i.id for i in s.items(mem.a, "zh", T0)] == [item.id]


def test_bulk_delete_removes_items_in_every_language_and_counts_them(mem):
    s, a = mem.store, mem.a
    add(s, a, "đi làm")
    add(s, a, "explain in Vietnamese", language=ANY_LANGUAGE)
    add(s, a, "job interview", language="en")
    assert s.delete_all(a, "items", T0) == 3
    assert s.items(a, "zh", T0) == [] and s.items(a, "en", T0) == []
    with pytest.raises(ValueError):
        s.delete_all(a, "everything", T0)


# --- suppression and keys -------------------------------------------------------------------------------------------


def test_deleting_a_continuity_item_leaves_a_suppression_key_that_bulk_delete_keeps(mem):
    s, a = mem.store, mem.a
    mem.continuity(a, "interest", "sport")
    item = next(i for i in s.items(a, "zh", T0) if i.cls == CONTINUITY)
    assert item.code == "sport" and item.slot == "interest"
    s.delete_item(a, item.id, T0)
    s.delete_all(a, "all", T0)
    assert s.suppressed(a, "zh", CONTINUITY, "interest", "sport", T0)
    assert not s.suppressed(a, "zh", CONTINUITY, "interest", "travel", T0)  # by slot and value, not slot alone
    assert not s.suppressed(a, "zh", CONTINUITY, "interest", "sport", T0 + timedelta(days=15))  # its former TTL


def test_rows_written_before_a_rotation_still_dedupe_and_suppress_and_a_dropped_version_refuses(mem):
    s, a = mem.store, mem.a
    mem.continuity(a, "interest", "sport")
    s.delete_item(a, next(i for i in s.items(a, "zh", T0) if i.cls == CONTINUITY).id, T0)
    first = add(s, a, "đi làm")
    rotated = mem.rekeyed(KEYS + ",v2:" + "n" * 40)  # the operator adds v2; v1 stays configured
    again = add(rotated, a, "đi làm")
    assert again.id == first.id and again.key_version == 1
    assert rotated.suppressed(a, "zh", CONTINUITY, "interest", "sport", T0)
    assert add(rotated, a, "thi HSK").key_version == 2  # new rows use the current version
    with pytest.raises(ValueError):
        MemoryKeys.parse("v2:" + "n" * 40).check_in_use(rotated.versions_in_use())


# --- concurrency ----------------------------------------------------------------------------------------------------


def test_concurrent_identical_adds_keep_one_row(mem):
    s, a = mem.store, mem.a
    results, errors = [], []

    def one():
        try:
            results.append(add(s, a, "Tôi muốn ví dụ về bóng đá", kind="interest").id)
        except Exception as exc:  # noqa: BLE001 - the assertion below names it
            errors.append(exc)

    threads = [threading.Thread(target=one) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == [] and len(set(results)) == 1 and len(s.items(a, "zh", T0)) == 1


# --- PostgreSQL only ------------------------------------------------------------------------------------------------


@pytest.fixture
def pg(engine):
    return Fixture("postgres", engine)


def test_a_write_on_an_incarnation_deleted_in_flight_writes_nothing(pg):
    from sqlalchemy import text

    from writing_coach.agent.memory_store import MemoryUnavailable

    item = add(pg.store, pg.a, "đi làm")
    with pg.engine.begin() as conn:
        conn.execute(text("UPDATE account_incarnations SET status = 'deleted', deleted_at = now() WHERE id = :i"),
                     {"i": pg.a.incarnation_id})  # fmt: skip
    version = pg.store.state(pg.a).version
    with pytest.raises(MemoryUnavailable):
        add(pg.store, pg.a, "thi HSK")
    with pytest.raises(MemoryUnavailable):
        pg.store.delete_item(pg.a, item.id, T0)
    assert pg.store.state(pg.a).version == version


def test_reads_fail_closed_once_the_incarnation_is_deleted(pg):
    """Review of M2.1 P2-2: a scope resolved before account deletion reads nothing after it."""
    from sqlalchemy import text

    add(pg.store, pg.a, "đi làm")
    pg.continuity(pg.a, "interest", "sport")
    pg.store.delete_item(pg.a, next(i for i in pg.store.items(pg.a, "zh", T0) if i.code == "sport").id, T0)
    with pg.engine.begin() as conn:
        conn.execute(text("UPDATE account_incarnations SET status = 'deleted', deleted_at = now() WHERE id = :i"),
                     {"i": pg.a.incarnation_id})  # fmt: skip
    assert pg.store.items(pg.a, "zh", T0) == []
    snap = pg.store.snapshot(pg.a, "zh", T0, 2)
    assert snap.items == () and not snap.state.enabled
    assert memory_section(pg.store, pg.a, "zh", T0) is None
    assert not pg.store.suppressed(pg.a, "zh", CONTINUITY, "interest", "sport", T0)


def test_the_sweep_deletes_only_expired_rows_in_bounded_batches(pg):
    s, a = pg.store, pg.a
    keep = add(s, a, "đi làm")  # explicit: no expiry
    for code in ("sport", "travel", "food"):
        pg.continuity(a, "interest", code)
    s.delete_item(a, next(i for i in s.items(a, "zh", T0) if i.code == "food").id, T0)  # leaves a key to T0+14d
    later = T0 + timedelta(days=15)
    assert s.sweep_expired(later, batch=1) == 2  # one item and one key at most per table
    s.sweep_expired(later, batch=500)
    assert [i.id for i in s.items(a, "zh", later)] == [keep.id]
    from sqlalchemy import text

    with pg.engine.connect() as conn:
        left = conn.execute(text("SELECT count(*) FROM learner_memories WHERE incarnation_id = :i"),
                            {"i": a.incarnation_id}).scalar()  # fmt: skip
    assert left == 1


def test_session_summaries_are_m3(pg):
    assert pg.store.summaries(pg.a, "zh", T0, 5) == [] and pg.store.delete_all(pg.a, "sessions", T0) == 0
    for call in (lambda: pg.store.finalise(pg.a, "s1", T0), lambda: pg.store.delete_summary(pg.a, "s1", T0),
                 lambda: pg.store.checkpoint(pg.a, agent_session_id="s1", language="zh", turns_covered=4,
                                             summary={}, context=[], now=T0)):  # fmt: skip
        with pytest.raises(NotImplementedError):
            call()
