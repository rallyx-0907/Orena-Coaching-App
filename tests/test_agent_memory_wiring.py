"""Orena Memory M2.2 (ORENA_MEMORY.md rev 4.1 §5.2, §6, §8; D-222; Agent Contract v9 §5.4, §10): the store wired into
a turn - the pack's memory section, the per-turn version probe, the switch, G8 for memory, and server-applied notes for
a v9 client. The store here is the in-memory fake; the PostgreSQL repository passes the same contract
(tests/test_agent_memory_contract.py)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from writing_coach.agent.data_class import ProviderDataClasses
from writing_coach.agent.fake_provider import call_tools, reply
from writing_coach.agent.memory_keys import MemoryKeys
from writing_coach.agent.memory_runtime import MemoryRuntime
from writing_coach.agent.memory_store import InMemoryMemoryStore
from writing_coach.agent.memory_pack import PackBuilder
from writing_coach.persistence.ids import stable_uuid
from tests.test_agent_data_class import GEMINI, NOTE, sent_notes
from tests.test_agent_learner_pack import NOW, sources
from tests.test_agent_prompt_cache import Router
from tests.test_agent_turn import VI, hermetic, run, runtime, turn_request  # noqa: F401 - fixture

T0 = datetime(2026, 10, 17, 8, 0, tzinfo=UTC)
ACCOUNT = str(stable_uuid("user", VI.user_key))
FULL = "gemini=full_memory"
PROFILE = "gemini=learning_profile"


class Incarnations:
    def __init__(self, active: str | None = "inc-1"):
        self.active = active

    def resolve(self, account):
        return self.active if account == ACCOUNT else None

    def ensure_active(self, account):
        if self.active is None:
            raise ValueError("no incarnation")
        return self.resolve(account)


def memory(store=None, active="inc-1"):
    store = store or InMemoryMemoryStore(MemoryKeys.parse("v1:" + "k" * 40))
    return MemoryRuntime(store=store, incarnations=Incarnations(active)), store


def wired(rounds, *, classes=FULL, mem=None, store=None, active="inc-1"):
    rt, provider = runtime(rounds)
    rt.pack = PackBuilder(sources=sources(), enabled=True, clock=lambda: NOW)
    rt.router = Router(GEMINI)
    rt.data_classes = ProviderDataClasses.parse(classes) if classes else None
    if mem is None:
        mem, store = memory(store, active)
    rt.memory = mem
    rt.pack.memory = mem.pack_reader()
    return rt, provider, store


def scope(mem):
    return mem.scope(VI.user_key)


def keep(store, mem, text="Mình học để phỏng vấn", language="zh"):
    return store.add_explicit(scope(mem), language=language, kind="goal", text=text, slot=None,
                              source="learner_asked", now=T0)  # fmt: skip


def seen(provider, text, index=0):
    return any(text in m.content for m in provider.requests[index].messages)


def v9_request(message="Tại sao tôi sai từ này?", **extra):
    from writing_coach.agent.schemas import TurnRequest

    body = turn_request(message, coach_notes=[NOTE], **extra).model_dump(mode="json", by_alias=True,
                                                                         exclude_none=True)  # fmt: skip
    body["contract_version"] = 9
    return TurnRequest.model_validate(body)


# --- the pack -------------------------------------------------------------------------------------------------------


def test_a_full_memory_provider_gets_the_learners_memory_for_a_v9_client_only():
    rt, provider, store = wired([reply("a1"), reply("a2")])
    keep(store, rt.memory)
    run(rt, v9_request())
    assert seen(provider, "Mình học để phỏng vấn", 0)
    run(rt)  # a v8-or-lower client: exactly as before, device notes only (review of #279: D-223 keeps v8 unchanged)
    assert not seen(provider, "Mình học để phỏng vấn", 1)


def test_below_full_memory_the_pack_carries_no_memory():
    rt, provider, store = wired([reply("a1")], classes=PROFILE)
    keep(store, rt.memory)
    run(rt, v9_request())
    assert not seen(provider, "Mình học để phỏng vấn")
    assert any(m.content.startswith("<orena_learner_pack") for m in provider.requests[0].messages)  # M1 pack stays


def test_without_an_active_incarnation_nothing_is_read():
    mem, store = memory()
    keep(store, mem)
    mem.incarnations.active = None  # the account was deleted, or the backbone has no incarnation for it
    rt, provider, _ = wired([reply("a1")], mem=mem)
    run(rt, v9_request())
    assert not seen(provider, "Mình học để phỏng vấn")


def test_memory_off_sends_neither_memory_nor_device_notes():
    rt, provider, store = wired([reply("a1")])
    keep(store, rt.memory)
    store.set_enabled(scope(rt.memory), False)
    run(rt, turn_request(coach_notes=[NOTE]))
    assert not seen(provider, "Mình học để phỏng vấn") and not sent_notes(provider.requests[0])


def test_a_delete_reaches_the_next_turn_of_an_open_conversation():
    """§5.2: the pack is frozen per conversation, and rebuilt when the memory version moved (another worker or
    device deleted something): the next model call carries no deleted item."""
    rt, provider, store = wired([reply("a1"), reply("a2")])
    item = keep(store, rt.memory)
    first = run(rt, v9_request())
    assert seen(provider, "Mình học để phỏng vấn", 0)
    store.delete_item(scope(rt.memory), item.id, T0)  # another worker
    session_id = next(e.session_id for e in first if e.name == "session")
    run(rt, v9_request("hỏi tiếp", session_id=session_id))
    assert not seen(provider, "Mình học để phỏng vấn", 1)


def test_a_memory_bearing_pack_raises_the_conversation_to_full_memory():
    rt, provider, store = wired([reply("a1")])
    keep(store, rt.memory)
    first = run(rt, v9_request())
    session_id = next(e.session_id for e in first if e.name == "session")
    state, _ = rt.sessions.open(session_id, VI.user_key)
    assert state.data_class_sent >= 2


# --- v9: notes the server applies -----------------------------------------------------------------------------------

KEEP = ("c1", "remember_note", {"kind": "preference", "text": "Giải thích bằng tiếng Việt"})


def updates(events):
    return [e for e in events if e.name == "memory_update"]


def test_v9_remember_is_stored_on_the_server_and_marked_stored_server():
    rt, provider, store = wired([call_tools(KEEP), reply("Mình đã ghi nhớ.")])
    events = run(rt, v9_request("Từ giờ ghi nhớ giúp mình là giải thích bằng tiếng Việt"))
    [update] = updates(events)
    assert update.stored == "server" and update.to_wire()["stored"] == "server"
    [item] = store.items(scope(rt.memory), "zh", NOW)
    assert item.text == "Giải thích bằng tiếng Việt" and update.note["id"] == item.id
    # It says when the note goes (the pilot retention, review of #292 P2-2), and the turn's clock, not the first keep.
    assert update.note["expires_at"] == item.expires_at.isoformat() is not None
    # The device's notes are not where it is kept; one the learner has not placed still reaches the model (ruling (b)).
    assert sent_notes(provider.requests[0])


def test_v9_server_notes_reach_the_model_with_their_ids_and_forget_deletes_them():
    mem, store = memory()
    item = keep(store, mem, text="Giải thích thật ngắn gọn")
    rt, provider, _ = wired([call_tools(("c1", "forget_note", {"id": item.id})), reply("Đã xoá.")], mem=mem)
    events = run(rt, v9_request("Quên ghi chú đó đi"))
    assert seen(provider, item.id) and seen(provider, "Giải thích thật ngắn gọn")
    [update] = updates(events)
    assert update.op == "remove" and update.stored == "server"
    assert update.note == {"id": item.id, "text": "Giải thích thật ngắn gọn"}  # the device clears a same-text copy
    assert store.items(scope(rt.memory), "zh", NOW) == []


def test_a_v8_client_keeps_device_only_behaviour_with_no_stored_field():
    rt, provider, store = wired([call_tools(KEEP), reply("Mình đã ghi nhớ.")])
    events = run(rt, turn_request("Từ giờ ghi nhớ giúp mình là giải thích bằng tiếng Việt", coach_notes=[NOTE]))
    [update] = updates(events)
    assert update.stored is None and "stored" not in update.to_wire()
    assert store.items(scope(rt.memory), "zh", NOW) == [] and sent_notes(provider.requests[0])


def test_v9_below_full_memory_falls_back_to_the_device():
    rt, _, store = wired([call_tools(KEEP), reply("Mình đã ghi nhớ.")], classes=PROFILE)
    events = run(rt, v9_request("Từ giờ ghi nhớ giúp mình là giải thích bằng tiếng Việt"))
    [update] = updates(events)
    assert update.stored == "device" and store.items(scope(rt.memory), "zh", NOW) == []


def test_v9_with_memory_off_keeps_nothing_on_the_server():
    rt, _, store = wired([call_tools(KEEP), reply("Được.")])
    store.set_enabled(scope(rt.memory), False)
    events = run(rt, v9_request("Từ giờ ghi nhớ giúp mình là giải thích bằng tiếng Việt"))
    assert all(u.stored != "server" for u in updates(events)) and store.items(scope(rt.memory), "zh", NOW) == []


def test_the_thirty_first_server_note_is_refused_and_nothing_is_kept():
    rt, provider, store = wired([call_tools(KEEP), reply("Chưa được.")])
    for n in range(30):
        keep(store, rt.memory, text=f"mục tiêu {n}")
    events = run(rt, v9_request("Từ giờ ghi nhớ giúp mình là giải thích bằng tiếng Việt"))
    assert updates(events) == [] and len(store.items(scope(rt.memory), "zh", NOW)) == 30
    refusal = next(m.content for m in provider.requests[1].messages if m.role == "tool")
    assert refusal.startswith("refused:") and "memory.limit" in refusal


@pytest.mark.parametrize("version", [8, 9])
def test_without_a_memory_runtime_nothing_changes(version):
    rt, provider = runtime([call_tools(KEEP), reply("Mình đã ghi nhớ.")])
    request = v9_request("Từ giờ ghi nhớ giúp mình là giải thích bằng tiếng Việt") if version == 9 else turn_request(
        "Từ giờ ghi nhớ giúp mình là giải thích bằng tiếng Việt", coach_notes=[NOTE])
    [update] = updates(run(rt, request))
    assert update.stored in (None, "device") and sent_notes(provider.requests[0])


# --- voice ----------------------------------------------------------------------------------------------------------


def voice(classes=FULL, version=5):
    from tests.test_agent_voice_session import Post, _body, _service

    post = Post()
    service = _service(post)
    service.runtime.pack = PackBuilder(sources=sources(), enabled=True, clock=lambda: NOW)
    service.runtime.data_classes = ProviderDataClasses.parse(classes)
    mem, store = memory()
    service.runtime.memory = mem
    service.runtime.pack.memory = mem.pack_reader()
    body = _body()
    body["contract_version"] = version
    body["coach_notes"] = [NOTE]
    return service, post, body, mem, store


def setup_text(post):
    return post.calls[0][2]["bidiGenerateContentSetup"]["systemInstruction"]["parts"][0]["text"]


def test_voice_gets_the_memory_when_cleared_and_none_with_memory_off():
    from tests.test_agent_voice_session import LEARNER

    service, post, body, mem, store = voice(version=9)
    keep(store, mem)
    service.open(body, LEARNER)
    assert "Mình học để phỏng vấn" in setup_text(post)
    service, post, body, mem, store = voice(version=5)  # v8 or lower: no account notes
    keep(store, mem)
    service.open(body, LEARNER)
    assert "Mình học để phỏng vấn" not in setup_text(post)
    service, post, body, mem, store = voice(version=9)
    keep(store, mem)
    store.set_enabled(scope(mem), False)
    service.open(body, LEARNER)
    assert "Mình học để phỏng vấn" not in setup_text(post) and NOTE["text"] not in setup_text(post)


def test_voice_v9_keeps_a_note_on_the_server():
    from tests.test_agent_voice_session import LEARNER

    service, _, body, mem, store = voice(version=9)
    sid = service.open(body, LEARNER)["voice_session_id"]
    call = {"id": "c1", "name": "remember_note", "args": {"kind": "preference", "text": "Giải thích bằng tiếng Việt"}}
    answer = service.relay(sid, [call], LEARNER, heard="Từ giờ ghi nhớ giúp mình là giải thích bằng tiếng Việt")
    assert answer["responses"][0]["response"]["result"].startswith("accepted")
    [event] = answer["events"]
    assert event["data"]["stored"] == "server"
    assert [i.text for i in store.items(scope(mem), "zh", NOW)] == ["Giải thích bằng tiếng Việt"]


# --- the server's memory ------------------------------------------------------------------------------------------


def test_memory_exists_only_with_keys_and_an_active_backbone_and_bad_keys_refuse_to_start():
    class Backbone:
        is_active, incarnations = True, Incarnations()

    made = []
    store = lambda keys: made.append(keys) or InMemoryMemoryStore(keys)  # noqa: E731
    keys = {"AGENT_MEMORY_HMAC_KEYS": "v1:" + "k" * 40}
    assert MemoryRuntime.from_env({}, Backbone(), store) is None and made == []
    inactive = type("Off", (), {"is_active": False, "incarnations": None})()
    assert MemoryRuntime.from_env(keys, inactive, store) is None and made == []
    assert MemoryRuntime.from_env(keys, Backbone(), store).store is not None and len(made) == 1
    with pytest.raises(ValueError):
        MemoryRuntime.from_env({"AGENT_MEMORY_HMAC_KEYS": "v1:short"}, Backbone(), store)


# --- review of M2.2 -------------------------------------------------------------------------------------------------

OLLAMA = __import__("writing_coach.agent.provider", fromlist=["ModelRoute"]).ModelRoute("ollama", "m")


def test_with_the_pack_off_server_notes_raise_the_conversation_and_a_lower_provider_is_refused():
    """P1-1: the gate follows Orena Memory, not only the pack."""
    rt, provider, store = wired([reply("a1"), reply("a2")], classes="gemini=full_memory,ollama=none")
    rt.pack.enabled = False
    keep(store, rt.memory, text="Giải thích thật ngắn gọn")
    first = run(rt, v9_request())
    assert seen(provider, "Giải thích thật ngắn gọn", 0)
    session_id = next(e.session_id for e in first if e.name == "session")
    rt.router.selection, rt.router.is_usable = OLLAMA, (lambda route: route != GEMINI)
    refused = run(rt, v9_request("hỏi tiếp", session_id=session_id))
    assert any(e.name == "error" for e in refused) and len(provider.requests) == 1


def test_a_failed_probe_fails_closed_for_device_notes():
    rt, provider, store = wired([reply("a1")])
    store.probe = lambda scope, now: (_ for _ in ()).throw(RuntimeError("db down"))
    run(rt, turn_request(coach_notes=[NOTE]))
    assert not sent_notes(provider.requests[0])


@pytest.mark.parametrize("version", [8, 9])
def test_with_memory_off_remember_writes_nothing_anywhere(version):
    """P1-2: OFF - nothing new is written, on the server or the device (§6)."""
    rt, provider, store = wired([call_tools(KEEP), reply("Được.")])
    store.set_enabled(scope(rt.memory), False)
    message = "Từ giờ ghi nhớ giúp mình là giải thích bằng tiếng Việt"
    events = run(rt, v9_request(message) if version == 9 else turn_request(message, coach_notes=[NOTE]))
    assert updates(events) == [] and store.items(scope(rt.memory), "zh", NOW) == []
    refusal = next(m.content for m in provider.requests[1].messages if m.role == "tool")
    assert refusal.startswith("refused: memory.off")


def test_a_store_error_never_breaks_the_turn():
    """P2-1: reading the notes and keeping one both fail; the learner still gets an answer."""
    rt, provider, store = wired([call_tools(KEEP), reply("Chưa được.")])
    store.items = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down"))
    store.add_explicit = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down"))
    events = run(rt, v9_request("Từ giờ ghi nhớ giúp mình là giải thích bằng tiếng Việt"))
    assert not any(e.name == "error" for e in events) and updates(events) == []
    refusal = next(m.content for m in provider.requests[1].messages if m.role == "tool")
    assert refusal.startswith("refused: memory.unavailable")


def test_a_correction_that_cannot_be_kept_still_reports_the_removed_note():
    """P2-2: the old note's delete is reported even when the new one fails."""
    from writing_coach.agent.memory_store import MemoryUnavailable

    mem, store = memory()
    old = keep(store, mem, text="Giải thích thật ngắn gọn")
    rt, _, _ = wired([call_tools(("c1", "remember_note", {"kind": "goal", "text": "Giải thích dài hơn",
                                                         "replaces": old.id})), reply("Được.")], mem=mem)  # fmt: skip
    store.add_explicit = lambda *a, **k: (_ for _ in ()).throw(MemoryUnavailable())
    events = run(rt, v9_request("Sửa ghi chú giải thích thật ngắn gọn thành giải thích dài hơn"))
    removes = [u for u in updates(events) if u.op == "remove"]
    assert store.items(scope(mem), "zh", NOW) == []  # the old note was deleted before the new one failed
    assert [r.note for r in removes] == [{"id": old.id, "text": "Giải thích thật ngắn gọn"}]


def test_server_notes_reaching_the_model_keep_the_request_caps():
    """P2-6: at most MAX_COACH_NOTES and MAX_COACH_NOTES_BYTES, newest first."""
    from writing_coach.agent.contract import MAX_COACH_NOTES, MAX_COACH_NOTES_BYTES
    from writing_coach.agent.schemas import coach_notes_bytes

    mem, store = memory()
    for n in range(30):
        store.add_explicit(scope(mem), language="zh", kind="goal", text=f"mục tiêu số {n:02d}", slot=None,
                           source="learner_asked", now=T0.replace(minute=n))  # fmt: skip
    notes = mem.notes(mem.turn(VI.user_key, version=9, cleared=True), "zh")
    assert 0 < len(notes) <= MAX_COACH_NOTES and coach_notes_bytes(list(notes)) <= MAX_COACH_NOTES_BYTES
    assert notes[0].text == "mục tiêu số 29" and [n.text for n in notes] == sorted((n.text for n in notes), reverse=True)


# --- M2.3: device notes the learner has not placed (contract v9 §3/§10, UI-lane ruling (b)) ----------------------


def test_v9_server_mode_still_sends_unplaced_device_notes_after_the_account_notes():
    rt, provider, store = wired([reply("a1")])
    keep(store, rt.memory, text="Mình học để phỏng vấn")
    run(rt, v9_request())
    text = "\n".join(m.content for m in provider.requests[0].messages)
    assert "Mình học để phỏng vấn" in text and NOTE["text"] in text
    assert text.index("Mình học để phỏng vấn") < text.index(NOTE["text"])  # the account's notes come first


def test_a_device_note_the_account_already_holds_is_sent_once():
    rt, provider, store = wired([reply("a1")])
    keep(store, rt.memory, text="giải thích thật ngắn gọn.")  # same_note: case and closing punctuation aside
    run(rt, v9_request())
    text = "\n".join(m.content for m in provider.requests[0].messages)
    assert text.casefold().count("giải thích thật ngắn gọn") == 1


def test_device_notes_only_fill_the_room_the_account_notes_leave():
    mem, store = memory()
    for n in range(30):
        store.add_explicit(scope(mem), language="zh", kind="goal", text=f"g{n:02d}", slot=None,
                           source="learner_asked", now=T0.replace(minute=n))  # fmt: skip  # 20 fill the count cap
    rt, provider, _ = wired([reply("a1")], mem=mem)
    run(rt, v9_request())
    assert not sent_notes(provider.requests[0])


def test_in_server_mode_forgetting_a_device_note_is_applied_by_the_device():
    rt, _, store = wired([call_tools(("c1", "forget_note", {"id": NOTE["id"]})), reply("Đã xoá.")])
    item = keep(store, rt.memory, text="Mình học để phỏng vấn")
    events = run(rt, v9_request("Quên ghi chú đó đi"))
    [update] = updates(events)
    assert update.op == "remove" and update.stored == "device" and update.note == {"id": NOTE["id"]}
    assert [i.id for i in store.items(scope(rt.memory), "zh", NOW)] == [item.id]  # the account is untouched


def test_in_server_mode_correcting_a_device_note_stays_on_the_device():
    call = ("c1", "remember_note", {"kind": "preference", "text": "Giải thích dài hơn", "replaces": NOTE["id"]})
    rt, _, store = wired([call_tools(call), reply("Được.")])
    events = run(rt, v9_request("Sửa ghi chú giải thích thật ngắn gọn thành giải thích dài hơn"))
    [update] = updates(events)
    assert update.op == "upsert" and update.stored == "device" and update.note["id"] == NOTE["id"]
    assert update.note["text"] == "Giải thích dài hơn" and store.items(scope(rt.memory), "zh", NOW) == []


def test_voice_server_mode_sends_the_account_notes_then_unplaced_device_notes():
    from tests.test_agent_voice_session import LEARNER

    service, post, body, mem, store = voice(version=9)
    keep(store, mem, text="Mình học để phỏng vấn")
    sid = service.open(body, LEARNER)["voice_session_id"]
    text = setup_text(post)
    assert text.index("Mình học để phỏng vấn") < text.index(NOTE["text"])
    # A voice forget is refused for every client today (voice reads no "asked" note); the account is never touched.
    forget = {"id": "c1", "name": "forget_note", "args": {"id": NOTE["id"]}}
    answer = service.relay(sid, [forget], LEARNER, heard="Quên ghi chú đó đi")
    assert answer["events"] == []
    assert [i.text for i in store.items(scope(mem), "zh", NOW)] == ["Mình học để phỏng vấn"]


def _note(id_, text, weight=0.5):
    from writing_coach.agent.schemas import CoachNote

    return CoachNote(id=id_, kind="preference", text=text, weight=weight, last_reinforced=T0)


def test_with_device_notes_orders_dedupes_and_fits_what_room_is_left():
    """Review of #281: account first; device by weight (client order on ties); a held, colliding or repeated
    device note is dropped; a large device note that does not fit does not block a smaller one that does."""
    from writing_coach.agent.contract import MAX_COACH_NOTES_BYTES
    from writing_coach.agent.memory_runtime import with_device_notes
    from writing_coach.agent.schemas import coach_notes_bytes

    account = (_note("a1", "Mình học để phỏng vấn", 1.0),)
    device = (_note("d1", "ví dụ ngắn", 0.4), _note("d2", "ví dụ về bóng đá", 0.4), _note("d3", "Ví dụ ngắn.", 0.9),
              _note("a1", "khác hẳn", 0.9), _note("d4", "mình học để phỏng vấn", 0.8))  # fmt: skip
    notes, ids = with_device_notes(account, device)
    assert [n.id for n in notes] == ["a1", "d3", "d2"]  # d1 repeats d3, d4 is held, "a1" collides; d2 after d3
    assert ids == {"d3", "d2"}
    big = _note("big", "x" * 400, 0.9)
    filler = tuple(_note(f"f{i}", "y" * 190, 1.0) for i in range(6))
    notes, ids = with_device_notes(filler, (big, _note("small", "z", 0.1)))
    assert "big" not in ids and "small" in ids and coach_notes_bytes(list(notes)) <= MAX_COACH_NOTES_BYTES


def test_keeping_the_words_of_an_unplaced_device_note_moves_it_to_the_account():
    """Review of #281 P2-5: a note is never both on the device and on the server (contract §5.4)."""
    call = ("c1", "remember_note", {"kind": "preference", "text": "Giải thích thật ngắn gọn"})
    rt, _, store = wired([call_tools(call), reply("Mình đã ghi nhớ.")])
    events = run(rt, v9_request("Từ giờ ghi nhớ giúp mình là giải thích thật ngắn gọn"))
    kept = [u for u in updates(events) if u.op == "upsert"]
    gone = [u for u in updates(events) if u.op == "remove"]
    assert kept and kept[0].stored == "server"
    assert [(g.note, g.stored) for g in gone] == [({"id": NOTE["id"]}, "device")]
    assert [i.text for i in store.items(scope(rt.memory), "zh", NOW)] == ["Giải thích thật ngắn gọn"]


@pytest.mark.parametrize("failure", ["unavailable", "limit", "store_error"])
def test_a_placement_that_is_not_kept_leaves_the_device_note_alone(failure):
    """Review of #279: the device copy is removed only after the account write committed."""
    from writing_coach.agent.memory_store import MemoryLimit, MemoryUnavailable

    error = {"unavailable": MemoryUnavailable(), "limit": MemoryLimit(), "store_error": RuntimeError("db down")}[failure]
    call = ("c1", "remember_note", {"kind": "preference", "text": "Giải thích thật ngắn gọn"})
    rt, _, store = wired([call_tools(call), reply("Chưa được.")])
    store.add_explicit = lambda *a, **k: (_ for _ in ()).throw(error)
    events = run(rt, v9_request("Từ giờ ghi nhớ giúp mình là giải thích thật ngắn gọn"))
    assert updates(events) == []  # no server upsert and no device remove: the device keeps its note


def test_a_question_about_a_kept_note_is_answered_from_it():
    """:8021 smoke step 5 (2026-10-18): the note reached the model (a forget by its id worked), yet "what am I learning
    English for?" was answered from the records ("no goal on record"). The model is told the notes are the learner's
    own words and answer a question about them, and no longer that the device keeps them (server mode keeps them)."""
    rt, provider, store = wired([reply("a1")])
    keep(store, rt.memory, text="Mình học để phỏng vấn")
    run(rt, v9_request("Mình học tiếng Trung để làm gì nhỉ?"))
    system = provider.requests[0].messages[0].content
    assert seen(provider, "Mình học để phỏng vấn")
    assert "the device keeps them" not in system
    assert "asks what they told you" in system and "answer from that note" in system
