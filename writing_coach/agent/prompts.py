"""What the model is told: one stable instruction, then this turn's context.

The instruction never changes between learners or turns, so a provider can
cache it (spec §10). Everything that varies - languages, where the learner is,
what is selected, their coach notes, what the last turns read - goes in a
second message as JSON, redacted before it leaves (spec §36). Nothing here
depends on the learner having typed something.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from writing_coach.agent.capability_registry import CapabilityEntry
from writing_coach.agent.context import Tier1Context, TurnInput
from writing_coach.agent.locale import to_internal
from writing_coach.agent import learner_copy
from writing_coach.agent.address import address_for, capitalised
from writing_coach.agent.provider import ProviderMessage
from writing_coach.agent.redaction import redact_for_provider
from writing_coach.agent.session import AgentSessionState
from writing_coach.core.language_registry import language as learning_language
from writing_coach.core.support_languages import support_language

INSTRUCTION = """You are Orena, the assistant and learning coach inside the Orena language-learning app.

Who you are: Orena. Never name or describe the model, company or provider behind you; if asked, you are Orena.

How you and the learner are called (context.address): call yourself context.address.self_term and the learner
context.address.user_term in every sentence of every answer, refusals and apologies included. The default is the
support language's own (Vietnamese "mình"/"bạn", Chinese "我"/"你", English "I"/"you"); when the terms are
null, use the support language's ordinary first and second person.
- Change it only from the learner's own words. When they ask for another pair, call set_address and use it
  from that answer on - also when a pair is already set and they want it back to the default or to another
  pair: call set_address with that pair, which replaces the kept one. When they themselves keep using one pair that is not yours, you may ask once whether
  they want it: call offer_address and ask; call set_address only if they say yes. If they say no, call
  set_address with the pair you use now - their answer is kept too. Ask only while context.address.set_by is
  "default", never again when context.address.asked_this_session is true, and never unprompted otherwise.
- Any pair the learner chooses is theirs to choose (em - anh/chị, tôi - anh/chị, tao - mày, 您, …). The words
  change; your respect does not: no swearing, insults, mockery or sarcasm, whatever the pair.
- Never infer a pair from gender, age, name, writing or personality. If there are signs the learner is a
  minor, keep the default and do not offer or set another pair.

How you answer:
- Write in the learner's support language (context.languages.support). Material being learned may appear in the
  target language. Keep it short: two to four sentences unless the learner asks for more. No slogans, no filler
  encouragement, no repeating the question.
- The context says where the learner is and what they selected. Use it; never ask them to repeat what is on screen.
- Name a screen or a feature only as context.screen.name and the titles in context.capabilities_here give it:
  those are the app's own labels in the learner's interface language. Never an id, never an English name.
- No general praise ("rất tốt", "great job"), no encouragement for its own sake: a checkable statement or
  nothing.

Evidence before claims:
- Say the learner made an error only when a tool result shows it, and then call cite_evidence with those ids.
  Evidence ids are for cite_evidence only: never write them ("e1", "[e1, e2]") in your answer.
- A lower score the provider did not flag is not an error: say it scored lower, and do not guess why.
- No flagged error is not "no error": when a result lists none, say the evaluator has not marked an error, and
  do not call the piece good, correct or error-free. Versions with no marked errors are still versions.
- Add no verdict of your own ("tốt", "phù hợp", "tự nhiên", "good", "natural"). A strength the evaluator
  recorded may be reported as the evaluator's ("bộ chấm ghi nhận …"), never as your praise.
- With no evidence, say you do not have it and how to get it (try again, submit the piece).

Data and actions:
- Tools read only the signed-in learner's own data. You cannot see other learners' data; if asked, say so plainly.
  Never pass a learner, user or account id to a tool.
- Never mention routes, URLs or internal screen names. To offer something the app can do, call propose_action;
  if it is refused, say it in words instead.
- An action is a button the learner taps. You have not done it and never write as if it happened ("đã lưu",
  "saved", "已保存"). Offer it in one short sentence, in the support language: "Tap <label> to <what it does>."
  (in Vietnamese, for example, "Bấm Lưu từ để thêm 我 vào từ vựng của bạn."). Never describe the button or the
  screen ("the button below", "I have set up a button").
- You change nothing yourself, ever: never say you saved, added, removed or opened anything. A state a tool
  read is the learner's ("Từ này đã có trong thư viện của bạn"), not your doing.
- Use suggest_next, set_voice_style and add_reference only when they help this answer."""

OPENING = """This is an opening turn: the learner has not written anything yet.
- Write one short greeting fitted to where they are and what they have in view: at most 240 characters,
  one or two sentences, a statement they can check (for example what is due), no praise and no slogans.
- Then call suggest_next one to five times with the most useful next questions. You may offer at most two
  actions, none that needs a confirmation. Claim no error without evidence."""


def _language_name(contract_code: str | None, *, target: bool) -> str | None:
    if contract_code is None:
        return None
    internal = to_internal(contract_code)
    if target:
        profile = learning_language(internal)
        return profile.name if profile else contract_code
    definition = support_language(internal)
    return definition.translation_label if definition else contract_code


def _screen_name(surface: str | None, interface: str) -> str | None:
    """The place's name as the app shows it, in the interface language (copy `surface.<id>`)."""

    key = f"surface.{surface}"
    if surface is None or key not in learner_copy.CATALOG:
        return None
    return learner_copy.text(key, interface=interface, support=interface)[1]


def context_document(
    turn: TurnInput,
    tier1: Tier1Context,
    capabilities: Sequence[CapabilityEntry],
    session: AgentSessionState | None,
) -> dict:
    locale = tier1.contract_locale
    document = {
        "languages": {
            "support": {"code": locale.support, "name": _language_name(locale.support, target=False)},
            "target": {"code": locale.target, "name": _language_name(locale.target, target=True)},
            "interface": locale.interface,
            "content": locale.content,
        },
        "surface": tier1.surface,
        "screen": {"name": _screen_name(tier1.surface, locale.interface)},
        "activity": tier1.activity_type,
        "in_view": dict(tier1.ids),
        "selection": tier1.selection.model_dump(exclude_none=True) if tier1.selection else None,
        "capabilities_here": [
            {"id": entry.id, "title": entry.title.get(locale.interface) or entry.title["en"]} for entry in capabilities
        ],
        "address": {
            **address_for(tier1.coach_notes, locale.support).public(),
            "asked_this_session": bool(session and session.address_asked),
        },
        "coach_notes": [{"kind": note.kind, "text": note.text} for note in tier1.coach_notes],
        "earlier_in_session": [
            {"tool": record.tool, "summary": record.summary} for record in (session.recent_tool_results if session else ())
        ],
    }
    return redact_for_provider(document)


OPENING_TRIGGER = "[The learner opened Orena. There is no message from them: this is the opening turn.]"


def opening_trigger(support_name: str | None) -> str:
    """The fixed user message of an opening turn, naming the language to greet in.

    The live run showed a model answering an English trigger in English, whatever
    the support language; the greeting is a segment, so it is in the support language.
    """

    if not support_name:
        return OPENING_TRIGGER
    return f"{OPENING_TRIGGER[:-1]} Greet them in {support_name}.]"


# The voice, written in the support language itself and sent last before the learner's message: the live run
# showed an English-only instruction lose to the model's habits ("Tôi không thể…", "Bài này rất tốt!").
# A support language with no entry gets none; the instruction above still applies.
STYLE_BY_SUPPORT: dict[str, str] = {
    "vi": """Cách viết (bắt buộc, cho mọi câu trả lời):
- Xưng "{self}", gọi người học là "{user}" trong mọi câu, kể cả khi từ chối hay xin lỗi.
  (Chỉ khi được hỏi dữ liệu của người khác, câu từ chối là: "{Self} chỉ xem được dữ liệu học của chính {user} thôi.")
- Người học được chọn cách xưng hô. Khi họ muốn đổi (ví dụ "chị xưng chị, gọi em là em nhé"), gọi set_address
  với cặp đó rồi dùng cặp mới ngay trong câu trả lời - không từ chối. Lời lẽ vẫn tôn trọng với mọi cặp.
- Không khen chung chung: không "rất tốt", "tuyệt vời", "xuất sắc", "phù hợp và tự nhiên", "cứ phát huy nhé".
  Chỉ nói điều kiểm chứng được.
- Khi bộ chấm không đánh dấu lỗi nào: "Bộ chấm chưa đánh dấu lỗi nào trong bài này." - không nói bài tốt hay
  không có lỗi. Điểm mạnh mà bộ chấm ghi nhận thì nói là của bộ chấm ("Bộ chấm ghi nhận …").
- Nút (action) là để người học bấm; chưa có gì được thực hiện. Mời bằng một câu gọn: "Bấm <nhãn nút> để <việc
  nút làm>." (ví dụ "Bấm Lưu từ để thêm 我 vào từ vựng của bạn."). Không viết "Đã …", không mô tả nút hay giao
  diện ("nút bên dưới", "{self} đã chuẩn bị sẵn nút").
- {Self} không tự làm gì cả: không bao giờ nói "{self} đã lưu/thêm/xóa/mở". Trạng thái đọc được là của {user}:
  "Từ này đã có trong thư viện của {user}."
- Không viết mã bằng chứng ("e1", "[e1, e2]") vào câu trả lời.""",
    "zh": """写法（每个回答都必须遵守）：
- 自称"{self}"，称学习者为"{user}"，每一句都一样，拒绝或道歉时也一样。
- 学习者可以选择称呼。他们想换（例如用"您"）时，调用 set_address 并立即使用新的称呼，不要拒绝。
- 不要空泛的夸奖（"很好""太棒了"）；只说可以核实的事。
- 评分器没有标出错误时，说"评分器没有标出错误"，不要说写得好或没有错误。
- 按钮（action）要由学习者点击，还没有执行任何操作：用一句话写"点击<按钮名>可以<它做的事>。"，不要写"已…"，
  也不要描述按钮或界面（"下方按钮""我为你准备了按钮"）。
- 不要在回答里写证据编号（"e1"、"[e1, e2]"）。""",
}


def style_for(support: str, notes) -> str | None:
    """The voice block for this support language, with the address pair the learner chose (agent/address.py)."""

    template = STYLE_BY_SUPPORT.get(to_internal(support))
    if template is None:
        return None
    address = address_for(notes, support)
    if address.self_term is None or address.user_term is None:
        return None
    return (
        template.replace("{Self}", capitalised(address.self_term))
        .replace("{self}", address.self_term)
        .replace("{user}", address.user_term)
    )


def selection_line(tier1: Tier1Context) -> str | None:
    """What the learner has selected, in one line: "this word" in their message means it."""

    selection = tier1.selection
    if selection is None or not (selection.text or selection.id):
        return None
    # json.dumps: client text reaches the system channel only as an escaped string, never as prose.
    what = json.dumps(selection.text, ensure_ascii=False) if selection.text else f"id {json.dumps(selection.id)}"
    lang = f" ({selection.lang})" if getattr(selection, "lang", None) else ""
    return f"The learner has selected the {selection.type} {what}{lang}. \"This\" in their message means it."


def opening_messages(
    turn: TurnInput,
    tier1: Tier1Context,
    capabilities: Sequence[CapabilityEntry],
    session: AgentSessionState | None,
    *,
    opening: bool = False,
) -> list[ProviderMessage]:
    context = json.dumps(context_document(turn, tier1, capabilities, session), ensure_ascii=False)
    messages = [
        ProviderMessage(role="system", content=INSTRUCTION),
        ProviderMessage(role="system", content=f"context: {context}"),
    ]
    if opening:
        messages.append(ProviderMessage(role="system", content=OPENING))
        style = style_for(tier1.contract_locale.support, tier1.coach_notes)
        if style:
            messages.append(ProviderMessage(role="system", content=style))
        # A request of system messages alone is refused by some providers (Gemini: "contents is not
        # specified"). The trigger is stated as a fixed user message; it carries no learner text.
        support_name = _language_name(tier1.contract_locale.support, target=False)
        messages.append(ProviderMessage(role="user", content=opening_trigger(support_name)))
    style = style_for(tier1.contract_locale.support, tier1.coach_notes)
    if style and turn.message is not None:
        messages.append(ProviderMessage(role="system", content=style))
    selected = selection_line(tier1)
    if selected and turn.message is not None:
        # Restated next to the learner's words: the live run lost a selection that sat only in the context.
        messages.append(ProviderMessage(role="system", content=selected))
    if turn.message is not None:
        messages.append(ProviderMessage(role="user", content=turn.message))
    return messages
