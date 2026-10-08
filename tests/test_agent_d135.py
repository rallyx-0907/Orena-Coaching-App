"""D-135 (2026-10-06, human direction on LEX-006; AGENT_CONTRACT §7):

- the sentence that offers an action is in the support language - the server's offer copy included - while the
  button label it quotes stays interface layer (D-080);
- a navigate to My Library about a word is offered only when a tool read says the word is in the learner's
  library; a word not saved gets no My Library button.
"""

from __future__ import annotations

import pytest

from tests.test_agent_coaching import _runtime
from writing_coach.agent import learner_copy
from writing_coach.agent.outputs import PROPOSE_ACTION, ClientInfo, ReplyOutputs
from writing_coach.agent.provider import TextDelta, ToolCallRequest, TurnFinished
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.tools import LearnerScope


@pytest.mark.parametrize("key", [k for k in learner_copy.CATALOG if k.startswith("offer.")])
def test_every_offer_sentence_is_support_layer(key):
    assert learner_copy.CATALOG[key].layer is learner_copy.CopyLayer.SUPPORT
    assert learner_copy.language_of(key, interface="en", support="vi") == "vi"


def test_the_offer_is_in_the_support_language_and_quotes_the_interface_label():
    request = TurnRequest.model_validate({
        "contract_version": 5, "trigger": "message", "message": "Lưu 花生 giúp mình",
        "client": {"ui_version": "t", "supported_actions": ["save_word"], "supported_intents": []},
        "context": {"surface": "orena.home", "locale": {"interface": "en", "support": "vi", "target": "zh-CN"}},
    })  # fmt: skip
    rounds = [(TextDelta("花生 là hạt lạc."),
               ToolCallRequest("c1", PROPOSE_ACTION, {"type": "save_word", "payload": {"text": "花生", "lang": "zh-CN"}}),
               TurnFinished(0, 3, "tool_calls"))]  # fmt: skip
    rt, _ = _runtime(rounds)
    events = list(rt.run(request, LearnerScope(user_key="learner-1", language="zh", interface="en")))
    ends = [e for e in events if e.name == "segment_end"]
    assert len(ends) == 1 and ends[0].lang == "vi"  # one support-language segment, the offer inside it
    assert ends[0].text == "花生 là hạt lạc. Bấm Save word để thêm 花生 vào từ vựng của bạn."
    assert next(e for e in events if e.name == "action").label == "Save word"  # the label stays interface layer


def _outputs(message="Mở từ này trong My Library", *, word="花生"):
    client = ClientInfo.model_validate({"ui_version": "t", "supported_actions": ["navigate"],
                                        "supported_intents": ["vocabulary.word", "vocabulary.my_language"]})  # fmt: skip
    out = ReplyOutputs(client=client, interface="en", support="vi", target="zh-CN", learner_words=message,
                       focused=word is not None, text_in_view=word is not None, selected_word=word)  # fmt: skip
    out.learn_ids("text", ("花生",))
    return out


OPEN_WORD = {"type": "navigate", "payload": {"intent": "vocabulary.word", "text": "花生", "lang": "zh-CN"}}
MY_LIBRARY = {"type": "navigate", "payload": {"intent": "vocabulary.my_language"}}


@pytest.mark.parametrize("action", [OPEN_WORD, MY_LIBRARY])
def test_a_word_not_known_to_be_saved_gets_no_my_library_button(action):
    out = _outputs()
    answer = out.handle(PROPOSE_ACTION, action, known_evidence=frozenset())
    assert answer.startswith("refused: 花生 is not in the learner's library") and out.actions == []


@pytest.mark.parametrize("action", [OPEN_WORD, MY_LIBRARY])
def test_a_word_a_tool_read_found_saved_gets_its_my_library_button(action):
    out = _outputs()
    out.learn_from({"word": "花生", "saved": True, "status": "learning"})
    assert out.handle(PROPOSE_ACTION, action, known_evidence=frozenset()).startswith("accepted")


def test_a_read_that_found_the_word_not_saved_keeps_it_out():
    out = _outputs()
    out.learn_from({"word": "花生", "saved": False})
    assert out.handle(PROPOSE_ACTION, OPEN_WORD, known_evidence=frozenset()).startswith("refused: 花生 is not")


def test_my_library_with_no_word_concerned_is_unchanged():
    out = _outputs("Mở thư viện của mình", word=None)
    assert out.handle(PROPOSE_ACTION, MY_LIBRARY, known_evidence=frozenset()).startswith("accepted")
