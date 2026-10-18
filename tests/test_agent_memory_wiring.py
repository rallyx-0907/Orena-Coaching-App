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


def test_a_full_memory_provider_gets_the_learners_memory_in_the_pack():
    rt, provider, store = wired([reply("a1")])
    keep(store, rt.memory)
    run(rt)
    assert seen(provider, "Mình học để phỏng vấn")


def test_below_full_memory_the_pack_carries_no_memory():
    rt, provider, store = wired([reply("a1")], classes=PROFILE)
    keep(store, rt.memory)
    run(rt)
    assert not seen(provider, "Mình học để phỏng vấn")
    assert any(m.content.startswith("<orena_learner_pack") for m in provider.requests[0].messages)  # M1 pack stays


def test_without_an_active_incarnation_nothing_is_read():
    mem, store = memory()
    keep(store, mem)
    mem.incarnations.active = None  # the account was deleted, or the backbone has no incarnation for it
    rt, provider, _ = wired([reply("a1")], mem=mem)
    run(rt)
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
    first = run(rt)
    assert seen(provider, "Mình học để phỏng vấn", 0)
    store.delete_item(scope(rt.memory), item.id, T0)  # another worker
    session_id = next(e.session_id for e in first if e.name == "session")
    run(rt, turn_request("hỏi tiếp", session_id=session_id))
    assert not seen(provider, "Mình học để phỏng vấn", 1)


def test_a_memory_bearing_pack_raises_the_conversation_to_full_memory():
    rt, provider, store = wired([reply("a1")])
    keep(store, rt.memory)
    first = run(rt)
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
    assert not sent_notes(provider.requests[0])  # the device's notes are not the source for a v9 client


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

    service, post, body, mem, store = voice()
    keep(store, mem)
    service.open(body, LEARNER)
    assert "Mình học để phỏng vấn" in setup_text(post)
    service, post, body, mem, store = voice()
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
