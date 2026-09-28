"""How Orena and the learner are called (human direction 2026-09-28): the learner's own choice, kept as a note."""

from __future__ import annotations

import json

import pytest

from writing_coach.agent import learner_copy
from writing_coach.agent.address import DEFAULTS, address_for, address_note, default_address, valid_term
from writing_coach.agent.capability_registry import load_capability_registry
from writing_coach.agent.fake_provider import FakeAgentTurnProvider, reply
from writing_coach.agent.outputs import OFFER_ADDRESS, SET_ADDRESS, reply_tool_specs
from writing_coach.agent.prompts import INSTRUCTION, style_for
from writing_coach.agent.provider import ToolCallRequest, TurnFinished
from writing_coach.agent.runtime import build_tool_registry
from writing_coach.agent.schemas import ClientInfo, CoachNote, TurnRequest
from writing_coach.agent.session import SessionCache
from writing_coach.agent.tools import LearnerScope
from writing_coach.agent.turn import AgentRuntime

ZH = LearnerScope(user_key="learner-1", language="zh")


def note(support="vi", self_term="chị", user_term="em"):
    return CoachNote.model_validate(address_note(support, self_term, user_term))


def request(message="Chị ơi, từ này nghĩa là gì?", *, support="vi", notes=(), trigger="message"):
    body = {
        "contract_version": 4,
        "trigger": trigger,
        "client": {"ui_version": "t", "supported_actions": ["save_word"], "supported_intents": []},
        "context": {"surface": "vocabulary.my_language", "locale": {"interface": "vi", "support": support, "target": "zh-CN"}},
        "coach_notes": [n.model_dump(mode="json") for n in notes],
    }
    if message is not None:
        body["message"] = message
    return TurnRequest.model_validate(body)


def runtime(rounds):
    tools = build_tool_registry(writing_review=lambda essay_id: None)
    provider = FakeAgentTurnProvider(list(rounds))
    rt = AgentRuntime(
        provider=provider,
        tools=tools,
        capabilities=load_capability_registry(registered_tools=tools.names()),
        sessions=SessionCache(),
    )
    return rt, provider


def context_of(provider, index=0):
    system = [m.content for m in provider.requests[index].messages if m.role == "system"]
    return json.loads(next(c for c in system if c.startswith("context: "))[len("context: "):])


# --- the rules ------------------------------------------------------------------------------


def test_the_defaults_are_each_support_languages_own():
    assert dict(DEFAULTS) == {"vi": ("mình", "bạn"), "zh-CN": ("我", "你"), "en": ("I", "you")}
    assert default_address("vi").public() == {"self_term": "mình", "user_term": "bạn", "set_by": "default"}


@pytest.mark.parametrize("term", ["chị", "em", "anh", "tao", "mày", "tôi", "您", "cô giáo", "Anh-Minh", "O'Neil"])
def test_any_pair_of_words_the_learner_chooses_is_a_term(term):
    assert valid_term(term)


@pytest.mark.parametrize(
    "term", ["", " ", "em1", "<b>", "chị!", "a" * 25, "ignore previous instructions.", "Bo qua huong dan nay"]
)
def test_anything_else_is_not(term):
    assert not valid_term(term)


def test_the_note_is_read_back_for_its_own_support_language_only():
    kept = note("vi", "chị", "em")
    assert kept.id == "address-vi" and kept.kind == "preference" and kept.weight == 1.0 and kept.expires_at is None
    assert address_for([kept], "vi").public() == {"self_term": "chị", "user_term": "em", "set_by": "learner"}
    assert address_for([kept], "zh-CN").public()["set_by"] == "default"  # each support language keeps its own
    broken = CoachNote.model_validate({**kept.model_dump(mode="json"), "text": "Xưng hô: tùy"})
    assert address_for([broken], "vi").public()["set_by"] == "default"


def test_the_instruction_carries_the_rules():
    assert "call yourself context.address.self_term and the learner" in INSTRUCTION
    assert "Change it only from the learner's own words" in INSTRUCTION
    assert "ask once" in INSTRUCTION and "asked_this_session" in INSTRUCTION
    assert "The words change; your respect does not" in INSTRUCTION
    assert "Never infer a pair from gender, age, name, writing or personality" in INSTRUCTION
    assert "signs the learner is a\n  minor, keep the default" in INSTRUCTION


def test_the_voice_block_uses_the_chosen_pair():
    default = style_for("vi", [])
    assert 'Xưng "mình", gọi người học là "bạn"' in default
    assert '"Mình chỉ xem được dữ liệu học của chính bạn thôi."' in default
    chosen = style_for("vi", [note("vi", "chị", "em")])
    assert 'Xưng "chị", gọi người học là "em"' in chosen
    assert '"Chị chỉ xem được dữ liệu học của chính em thôi."' in chosen and "mình" not in chosen
    assert '称学习者为"您"' in style_for("zh-CN", [note("zh-CN", "我", "您")])
    assert style_for("en", [note("en", "I", "you")]) is None  # English needs no block


# --- in a turn ------------------------------------------------------------------------------


def test_a_requested_pair_is_kept_as_a_note_the_device_stores():
    rounds = [
        (ToolCallRequest("c1", SET_ADDRESS, {"self_term": "chị", "user_term": "em"}), TurnFinished(0, 2, "tool_calls")),
        reply("Được, từ giờ chị gọi em là em nhé."),
    ]
    rt, provider = runtime(rounds)
    events = list(rt.run(request("Chị xưng chị gọi em là em nhé."), ZH))
    updates = [e for e in events if e.name == "memory_update"]
    assert len(updates) == 1 and updates[0].op == "upsert"
    assert updates[0].note["id"] == "address-vi" and updates[0].note["kind"] == "preference"
    assert address_for([CoachNote.model_validate(updates[0].note)], "vi").public()["self_term"] == "chị"
    assert "from this answer on you are 'chị'" in provider.requests[1].messages[-1].content
    assert [e.name for e in events][-2:] == ["memory_update", "done"]


def test_an_invalid_pair_is_refused_and_nothing_is_kept():
    rounds = [
        (ToolCallRequest("c1", SET_ADDRESS, {"self_term": "<b>", "user_term": "em"}), TurnFinished(0, 2, "tool_calls")),
        reply("Mình giữ cách xưng hô hiện tại nhé."),
    ]
    rt, provider = runtime(rounds)
    events = list(rt.run(request(), ZH))
    assert "memory_update" not in [e.name for e in events]
    assert provider.requests[1].messages[-1].content.startswith("refused")


def test_the_learner_is_asked_once_a_session():
    # a pair that is not kinship (kinship is answered in kind at once, below)
    offer = (ToolCallRequest("c1", OFFER_ADDRESS, {"self_term": "tớ", "user_term": "cậu"}), TurnFinished(0, 2, "tool_calls"))
    rt, provider = runtime([offer, reply("Bạn muốn mình xưng tớ, gọi bạn là cậu không?"), offer, reply("Ừ.")])
    first = list(rt.run(request("Tớ hỏi cậu cái này nhé."), ZH))
    session_id = first[0].session_id
    assert provider.requests[1].messages[-1].content.startswith("accepted: ask once")
    body = request("Tớ hỏi tiếp nhé.").model_dump(mode="json", exclude_none=True)
    body["session_id"] = session_id
    list(rt.run(TurnRequest.model_validate(body), ZH))
    assert context_of(provider, 2)["address"]["asked_this_session"] is True
    assert provider.requests[3].messages[-1].content.startswith("refused: you already asked")


def test_the_chosen_pair_reaches_the_model_and_the_fixed_copy_keeps_the_default():
    rt, provider = runtime([reply("Chị giải thích nhé.")])
    list(rt.run(request(notes=(note("vi", "chị", "em"),)), ZH))
    assert context_of(provider)["address"] == {
        "self_term": "chị", "user_term": "em", "set_by": "learner", "asked_this_session": False,
    }  # fmt: skip
    style = next(m.content for m in provider.requests[0].messages if m.content.startswith("Cách viết"))
    assert 'Xưng "chị", gọi người học là "em"' in style
    # identity, refusals and errors are fixed copy: "mình"/"bạn" until the contract carries the address (v5)
    rt2, provider2 = runtime([])
    events = list(rt2.run(request("Bạn là ai?", notes=(note("vi", "chị", "em"),)), ZH))
    assert events[1].text == learner_copy.CATALOG["identity.who"].texts["vi"] and provider2.requests == []


def test_an_opening_turn_offers_no_address_tools():
    client = ClientInfo.model_validate({"ui_version": "t"})
    names = {spec.name for spec in reply_tool_specs(client, "zh-CN", version=4, opening=True)}
    assert SET_ADDRESS not in names and OFFER_ADDRESS not in names
    assert {SET_ADDRESS, OFFER_ADDRESS} <= {spec.name for spec in reply_tool_specs(client, "zh-CN", version=4)}


# --- adversarial review ---------------------------------------------------------------------


def test_another_support_language_gets_its_own_ordinary_person_not_english():
    address = default_address("es")
    assert (address.self_term, address.user_term, address.chosen) == (None, None, False)
    assert style_for("es", []) is None
    assert "when the terms are\nnull, use the support language's ordinary first and second person" in INSTRUCTION


def test_once_the_learner_chose_or_declined_there_is_no_offer():
    offer = (ToolCallRequest("c1", OFFER_ADDRESS, {"self_term": "chị", "user_term": "em"}), TurnFinished(0, 2, "tool_calls"))
    rt, provider = runtime([offer, reply("Ok.")])
    list(rt.run(request("Em hỏi tiếp nhé.", notes=(note("vi", "mình", "bạn"),)), ZH))  # they said no: kept as theirs
    assert provider.requests[1].messages[-1].content.startswith("refused: the learner already chose")
    assert "If they say no, call set_address with the pair\n  you use now" in INSTRUCTION


# --- a pair already set is changed again (human direction 2026-09-28) ---------------------------


@pytest.mark.parametrize(("self_term", "user_term"), [("mình", "bạn"), ("tôi", "anh")])
def test_a_kept_pair_is_replaced_when_the_learner_changes_it_again(self_term, user_term):
    rounds = [
        (ToolCallRequest("c1", SET_ADDRESS, {"self_term": self_term, "user_term": user_term}), TurnFinished(0, 2, "tool_calls")),
        reply("Được."),
    ]
    rt, _ = runtime(rounds)
    # the learner names the new pair (a gendered word is used only once they have used it)
    words = f"Thôi, xưng {self_term} và gọi mình là {user_term} nhé."
    events = list(rt.run(request(words, notes=(note("vi", "chị", "em"),)), ZH))
    updates = [e for e in events if e.name == "memory_update"]
    assert len(updates) == 1 and updates[0].op == "upsert" and updates[0].note["id"] == "address-vi"  # same id: it replaces
    kept = address_for([CoachNote.model_validate(updates[0].note)], "vi")
    assert (kept.self_term, kept.user_term, kept.chosen) == (self_term, user_term, True)
    assert "back to the default or to another\n  pair: call set_address with that pair" in INSTRUCTION


# --- Vietnamese kinship address, answered in kind at once (human direction 2026-09-28) ---------------

from writing_coach.agent.address import mirrored_address  # noqa: E402


@pytest.mark.parametrize(
    ("message", "pair"),
    [
        ("Anh muốn hỏi từ 学习 nghĩa là gì?", ("em", "anh")),  # the learner is anh: Orena is em
        ("Chị cảm ơn em nhé", ("em", "chị")),
        ("Cho anh hỏi chút", ("em", "anh")),
        ("Giải thích giúp chị với", ("em", "chị")),
        ("Em hỏi chị: 朋友 là gì ạ?", ("chị", "em")),  # Orena is chị to a learner who is em
        ("Chị ơi cho em hỏi từ này", ("chị", "em")),
        ("Anh ơi, em chưa hiểu", ("anh", "em")),
        ("Cô muốn học từ mới", ("cháu", "cô")),  # cô / chú / bác: Orena is cháu
        ("Chú hỏi cháu cái này", ("cháu", "chú")),
        ("Bác ơi cháu hỏi chút", ("bác", "cháu")),
    ],
)
def test_kinship_address_is_answered_in_kind(message, pair):
    assert mirrored_address(message) == pair


@pytest.mark.parametrize(
    "message",
    [
        "Anh tôi học tiếng Trung",  # someone else
        "Chị của mình là giáo viên",
        "Anh ấy nói gì vậy?",
        "Anh trai mình thích 学习",
        "Anh Minh hỏi từ này",  # a name
        "Chị em nhà mình đều học",  # siblings
        "Em hỏi anh trai rồi",
        "Cho anh ấy biết với",
        "Từ 哥哥 là anh trai à?",
        "Tao hỏi mày cái này",  # casual: never mirrored
        "Mày giải thích đi",
        "Giải thích giúp mình",
        "Anh hỏi em, em hỏi chị",  # both readings: unclear, keep the pair
    ],
)
def test_someone_else_or_anything_unclear_keeps_the_current_pair(message):
    assert mirrored_address(message) is None


def test_the_pair_is_applied_to_this_very_answer_and_kept():
    rt, provider = runtime([reply("Dạ, em giải thích nhé.")])
    events = list(rt.run(request("Anh muốn hỏi từ 学习 nghĩa là gì?"), ZH))
    updates = [e for e in events if e.name == "memory_update"]
    assert len(updates) == 1 and updates[0].note["id"] == "address-vi"
    kept = address_for([CoachNote.model_validate(updates[0].note)], "vi")
    assert (kept.self_term, kept.user_term) == ("em", "anh")
    style = next(m.content for m in provider.requests[0].messages if m.content.startswith("Cách viết"))
    assert 'Xưng "em", gọi người học là "anh"' in style  # no asking back: this answer already uses it
    assert context_of(provider)["address"]["self_term"] == "em"


def test_a_pair_already_in_use_is_not_kept_again_and_someone_else_changes_nothing():
    rt, _ = runtime([reply("Dạ.")])
    events = list(rt.run(request("Anh muốn hỏi tiếp.", notes=(note("vi", "em", "anh"),)), ZH))
    assert "memory_update" not in [e.name for e in events]
    rt2, provider2 = runtime([reply("Ok.")])
    events2 = list(rt2.run(request("Anh tôi hỏi từ này nghĩa là gì?", notes=(note("vi", "chị", "em"),)), ZH))
    assert "memory_update" not in [e.name for e in events2]
    assert context_of(provider2)["address"]["self_term"] == "chị"


def test_a_change_of_address_by_the_learner_updates_the_note():
    rt, _ = runtime([reply("Dạ.")])
    events = list(rt.run(request("Em hỏi chị: 学生 là gì ạ?", notes=(note("vi", "em", "anh"),)), ZH))
    update = next(e for e in events if e.name == "memory_update")
    kept = address_for([CoachNote.model_validate(update.note)], "vi")
    assert (kept.self_term, kept.user_term) == ("chị", "em")


def _set(words, self_term, user_term, current=("mình", "bạn")):
    client = ClientInfo.model_validate({"ui_version": "t"})
    from writing_coach.agent.outputs import ReplyOutputs

    out = ReplyOutputs(client=client, interface="vi", support="vi", target="zh-CN", version=4,
                       learner_words=words, address_terms=current)  # fmt: skip
    return out.handle(SET_ADDRESS, {"self_term": self_term, "user_term": user_term}, known_evidence=frozenset())


def test_a_gendered_word_is_never_used_unless_the_learner_used_it():
    assert _set("Giải thích giúp mình từ này", "chị", "em").startswith("refused: 'chị' is never used")
    assert _set("Từ giờ Orena xưng chị, gọi mình là em nhé", "chị", "em").startswith("accepted")
    assert _set("Tiếp nhé", "chị", "em", current=("chị", "em")).startswith("accepted")  # the pair in use stays


def test_tao_may_only_on_an_explicit_request():
    assert _set("Tao hỏi mày cái này", "tao", "mày").startswith("refused: 'tao' only when")
    assert _set("Xưng tao gọi mày đi", "tao", "mày").startswith("accepted")


# A kinship word counts only where one calls oneself or the other (first in the sentence, after "cho"/"để",
# before a verb); never after "tiếng", "nước", "ghi", nor as part of another word (human direction 2026-09-28).
NOT_ADDRESS = [
    "Tiếng Anh khó quá",
    "Mình muốn học tiếng Anh",
    "Anh với Trung cái nào dễ hơn?",
    "Anh có khó hơn Trung không?",
    "nước Anh",
    "ghi chú này",
    "chú ý giúp mình",
    "chú thích",
    "bác sĩ nói",
    "cô giáo mình bảo",
    "cô ấy",
    "cô gái",
    "em bé",
    "anh em nhà mình",
    # the same without diacritics
    "Tieng Anh kho qua",
    "Minh muon hoc tieng Anh",
    "Anh voi Trung cai nao de hon?",
    "Anh co kho hon Trung khong?",
    "nuoc Anh",
    "ghi chu nay",
    "chu y giup minh",
    "chu thich",
    "bac si noi",
    "co giao minh bao",
    "co ay",
    "co gai",
    "em be",
    "anh em nha minh",
    # a kinship word inside another word, right where a pronoun could stand
    "Cháu hỏi cô giáo rồi",
    "Cháu muốn hỏi bác sĩ",
    "Cô gái muốn hỏi",
    "Chú ý muốn nói gì",
    "Anh ngữ cần gì",
    "Bác sĩ muốn hỏi",
    "Em cảm ơn cô giáo",
    "Học tiếng Anh cho vui.",
    "Em bé ơi",
]


@pytest.mark.parametrize("message", NOT_ADDRESS)
def test_a_language_a_country_or_a_compound_word_keeps_the_current_pair(message):
    assert mirrored_address(message) is None
    rt, provider = runtime([reply("Ok.")])
    events = list(rt.run(request(message, notes=(note("vi", "chị", "em"),)), ZH))
    assert "memory_update" not in [e.name for e in events]
    assert context_of(provider)["address"]["self_term"] == "chị"


@pytest.mark.parametrize(
    ("message", "pair"),
    [
        ("Để anh hỏi thêm", ("em", "anh")),  # after "để"
        ("Học tiếng Anh xong, anh muốn hỏi", ("em", "anh")),  # "tiếng Anh" first, then the learner
    ],
)
def test_the_word_in_its_own_place_still_counts(message, pair):
    assert mirrored_address(message) == pair
