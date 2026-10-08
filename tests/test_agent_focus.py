"""The conversation kernel, slice 3: what "that", "it" and "the paragraph" refer to (architecture target §6).

The runtime keeps a small, factual focus - the active topic and its referents - taken from what was selected, looked
up, offered or pasted; it never parses the learner's words for it. The model reads it with the conversation, so
"từ đó", "ý trên" or "đoạn thứ 3" resolve without asking the learner to repeat. A long paste stays reachable after
the recent-turn window has moved past it.
"""

from __future__ import annotations

from writing_coach.agent.fake_provider import call_tools, reply
from writing_coach.agent.focus import Focus, focus_after
from writing_coach.agent.limits import AgentLimits
from tests.test_agent_pending import SAVE_MITIGATE, context_of, offer, request, session_of, talk
from tests.test_agent_turn import hermetic, runtime  # noqa: F401 - fixture


def test_a_word_the_learner_asked_about_and_was_offered_becomes_the_topic():
    rt, provider = runtime([*offer(SAVE_MITIGATE), reply("An example.")])
    first, _ = talk(rt, None, "mitigate nghĩa là gì?")
    talk(rt, session_of(first), "cho ví dụ nữa")
    focus = context_of(provider.requests[-1])["conversation_focus"]
    assert focus["active_topic"] == {"type": "word", "value": "mitigate", "lang": "en"}
    assert focus["referents"]["current_word"] == "mitigate"


def test_a_selection_gives_the_word_and_its_sentence_as_referents():
    selected = {"type": "word", "text": "abate", "lang": "en", "sentence": "The storm will abate by noon."}
    rt, provider = runtime([reply("Giảm bớt."), reply("Ok.")])
    body = request("từ này là gì?").model_dump(mode="json")
    body["context"]["selected_item"] = selected
    from writing_coach.agent.schemas import TurnRequest
    from tests.test_agent_turn import run

    first = run(rt, TurnRequest.model_validate(body))
    talk(rt, session_of(first), "nó thuộc loại từ gì")
    focus = context_of(provider.requests[-1])["conversation_focus"]
    assert focus["referents"]["current_word"] == "abate"
    assert focus["referents"]["current_sentence"] == "The storm will abate by noon."


def test_a_newer_topic_replaces_the_older_one_and_a_quiet_turn_keeps_it():
    first = focus_after(Focus(), word=("mitigate", "en"))
    kept = focus_after(first)
    assert kept.topic == {"type": "word", "value": "mitigate", "lang": "en"}
    newer = focus_after(kept, word=("abate", "en"))
    assert newer.topic["value"] == "abate" and newer.referents["current_word"] == "abate"


def test_the_focus_survives_a_change_of_learning_language():
    rt, provider = runtime([*offer(SAVE_MITIGATE), reply("你好。")])
    first, _ = talk(rt, None, "mitigate nghĩa là gì?")
    talk(rt, session_of(first), "nói bằng tiếng Trung", target="zh-CN")
    assert context_of(provider.requests[-1])["conversation_focus"]["active_topic"]["value"] == "mitigate"


ARTICLE = "Artificial intelligence has fundamentally changed work. " * 60  # ~3,300 characters, a pasted text


def test_a_pasted_text_stays_reachable_after_the_recent_turns_moved_on():
    rt, provider = runtime([reply(f"a{i}") for i in range(1, 6)], limits=AgentLimits(max_recent_turns=2))
    first, _ = talk(rt, None, ARTICLE + "\nTác giả phản đối điều gì?")
    sid = session_of(first)
    for message in ("câu 2", "câu 3", "câu 4"):
        talk(rt, sid, message)
    talk(rt, sid, "đoạn thứ 3 lập luận có yếu không?")
    last = provider.requests[-1]
    shown = [m for m in last.messages if ARTICLE[:100] in m.content]
    assert len(shown) == 1 and shown[0].role == "user"  # reachable once, not twice, as part of the conversation
    assert context_of(last)["conversation_focus"]["referents"]["pasted_text"]["chars"] >= len(ARTICLE)


def test_a_pasted_text_in_the_recent_turns_is_not_sent_twice():
    rt, provider = runtime([reply("a1"), reply("a2")])
    first, _ = talk(rt, None, ARTICLE + "\nTóm tắt giúp mình.")
    talk(rt, session_of(first), "đoạn 2 nói gì?")
    last = provider.requests[-1]
    assert len([m for m in last.messages if ARTICLE[:100] in m.content]) == 1


def test_a_word_a_tool_was_asked_about_is_the_topic():
    from pydantic import BaseModel, ConfigDict

    from writing_coach.agent.tools import AgentTool, ToolPermission, ToolRegistry, ToolResult

    class WordArgs(BaseModel):
        model_config = ConfigDict(extra="forbid")
        text: str

    tools = ToolRegistry()
    tools.register(AgentTool(
        name="get_word_detail", description="A word.", input_model=WordArgs, permission=ToolPermission.READ_ONLY,
        backed_by="writing_coach.becoming_library:library_summary", languages=("en", "zh-CN"),
        label_key="tool.get_word_detail",
        handler=lambda learner, args: ToolResult(summary="a word", data={}, evidence=(), count=1),
    ))
    rt, provider = runtime([call_tools(("c1", "get_word_detail", {"text": "scarcity"})), reply("Sự khan hiếm."),
                            reply("Ví dụ.")], tools=tools)
    first, _ = talk(rt, None, "scarcity nghĩa là gì?")
    talk(rt, session_of(first), "cho ví dụ với điện")
    focus = context_of(provider.requests[-1])["conversation_focus"]
    assert focus["active_topic"] == {"type": "word", "value": "scarcity", "lang": "en"}


def test_the_instruction_tells_the_model_to_resolve_references_from_the_conversation_and_focus():
    from writing_coach.agent.prompts import INSTRUCTION

    assert "context.conversation_focus" in INSTRUCTION and "ask what they mean only when" in " ".join(INSTRUCTION.split())
