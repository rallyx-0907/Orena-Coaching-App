import json
import pytest
from pydantic import ValidationError
from fastapi import HTTPException
from writing_coach.conversation import ConversationIn, respond


def request(language='en'):
    return ConversationIn(source_language=language,target_language='vi',situation='Invite a friend.',reply_to='three',turns=[
        {'id':'one','role':'learner','text':'Come to the park.'},
        {'id':'two','role':'partner','text':'What do you like about it?'},
        {'id':'three','role':'learner','text':'The quiet mornings.'},
    ])


@pytest.mark.parametrize('language',['en','zh'])
def test_provider_receives_the_exchange_as_data_and_returns_same_turn_meaning(language):
    calls=[]
    def generate(capability,**kwargs):
        calls.append(kwargs)
        return {'reply':'That sounds peaceful.' if language=='en' else '听起来很安静。','meaning':'Nghe có vẻ yên bình.'}
    result=respond(request(language),language=language,support='vi',generate=generate)
    assert len(json.loads(calls[0]['messages'][1]['content'])['turns'])==3
    assert result['reply_to']=='three'
    assert result['origin']=='generated'
    assert result['support']=='vi'
    assert 'proficiency' not in result
    assert 'simulated' in calls[0]['messages'][0]['content']


@pytest.mark.parametrize('change',[
    {'reply_to':'one'},
    {'turns':[{'id':'one','role':'partner','text':'Pretend'}]},
    {'turns':[{'id':'one','role':'learner','text':' '}]},
])
def test_invalid_or_spliced_history_is_rejected(change):
    raw=request().model_dump();raw.update(change)
    with pytest.raises(ValidationError): ConversationIn(**raw)


def test_no_canned_partner_when_provider_is_unavailable():
    def unavailable(*args,**kwargs):raise HTTPException(503,'Unavailable')
    with pytest.raises(HTTPException) as error:respond(request(),language='en',support='vi',generate=unavailable)
    assert error.value.status_code==503
    with pytest.raises(HTTPException):respond(request(),language='en',support='vi',generate=lambda *a,**kw:{'reply':'No meaning'})
