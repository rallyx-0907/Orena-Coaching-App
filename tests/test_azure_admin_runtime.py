from types import SimpleNamespace

import pytest

from writing_coach.ai.providers import build_providers, get_provider_definition
from writing_coach.ai.capabilities import AIOperation


def test_azure_providers_are_separate_operations():
    assert get_provider_definition('azure-openai').supports(AIOperation.STRUCTURED_TEXT_GENERATION)
    assert get_provider_definition('azure-speech').supports(AIOperation.PRONUNCIATION_EVALUATION)
    assert not get_provider_definition('azure-speech').supports(AIOperation.STRUCTURED_TEXT_GENERATION)


def test_current_environment_key_can_be_tested_but_not_sent_to_new_endpoint(monkeypatch):
    from fastapi import HTTPException
    from writing_coach.ai import platform
    provider = SimpleNamespace(secret_mode='server-managed', api_key='synthetic-key',
        base_url='https://eastus.stt.speech.microsoft.com', default_model='pronunciation-assessment')
    monkeypatch.setattr(platform, 'providers', lambda: {'azure-speech': provider})
    monkeypatch.setattr(platform, '_stored_provider_credentials', lambda name: {})
    values = platform._provider_credential_values('azure-speech', platform.ProviderCredentialIn(), require_models=False, test_current=True)
    assert values['api_key'] == 'synthetic-key'
    with pytest.raises(HTTPException):
        platform._provider_credential_values('azure-speech', platform.ProviderCredentialIn(base_url='https://westus.stt.speech.microsoft.com'), require_models=False, test_current=True)
    with pytest.raises(HTTPException):
        platform._provider_credential_values('azure-speech', platform.ProviderCredentialIn(), require_models=False)


def test_azure_openai_uses_deployment_and_api_key(monkeypatch):
    provider = build_providers({'azure-openai': {
        'api_key': 'test-secret', 'base_url': 'https://test.openai.azure.com/openai/v1',
        'models': ['my-deployment'], 'default_model': 'my-deployment',
    }})['azure-openai']
    sent = []
    def post(url, **kwargs):
        sent.append((url, kwargs))
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, headers={}, json=lambda: {
            'choices': [{'message': {'content': '{"ok": true}'}}],
        })
    monkeypatch.setattr('writing_coach.ai.providers.requests.post', post)
    result = provider.generate_json_once(messages=[], schema={}, model='my-deployment',
                                        max_output_tokens=32, temperature=0, seed=None)
    assert result.data['ok'] is True
    assert sent[0][0].endswith('/openai/v1/chat/completions')
    assert sent[0][1]['headers']['api-key'] == 'test-secret'
    assert sent[0][1]['json']['model'] == 'my-deployment'
    assert sent[0][1]['allow_redirects'] is False


def test_unreadable_speech_credential_disables_assessment_not_startup(monkeypatch):
    from fastapi import HTTPException
    from writing_coach.ai import platform
    from writing_coach.speech_pronunciation import build_speech_pronunciation_provider
    def unreadable(name):
        raise HTTPException(503, 'Stored provider credential is unavailable.')
    monkeypatch.setattr(platform, '_stored_provider_credentials', unreadable)
    monkeypatch.delenv('PRONUNCIATION_PROVIDER', raising=False)
    monkeypatch.delenv('AZURE_SPEECH_KEY', raising=False)
    monkeypatch.delenv('AZURE_SPEECH_REGION', raising=False)
    assert build_speech_pronunciation_provider() is None


@pytest.mark.parametrize('endpoint', ['http://eastus.stt.speech.microsoft.com',
                                     'https://attacker.invalid', 'https://eastus.stt.speech.microsoft.com/path'])
def test_azure_speech_refuses_nonregional_endpoint(endpoint):
    from writing_coach.ai.azure import speech_region
    with pytest.raises(ValueError):
        speech_region(endpoint)


def test_azure_speech_auth_test_does_not_return_token(monkeypatch):
    from writing_coach.ai.azure import AzureSpeechControlProvider
    sent = []
    def post(url, **kwargs):
        sent.append((url, kwargs))
        return SimpleNamespace(status_code=200)
    monkeypatch.setattr('writing_coach.ai.azure.requests.post', post)
    provider = AzureSpeechControlProvider({'api_key': 'test-secret', 'base_url': 'https://eastus.stt.speech.microsoft.com'})
    assert provider.discover_models_live() == ['pronunciation-assessment']
    assert sent[0][0] == 'https://eastus.api.cognitive.microsoft.com/sts/v1.0/issueToken'
    assert sent[0][1]['allow_redirects'] is False


def test_saved_speech_credentials_feed_existing_adapter(monkeypatch):
    import writing_coach.ai.platform as platform
    from writing_coach.speech_pronunciation import build_speech_pronunciation_provider
    monkeypatch.setattr(platform, '_stored_provider_credentials', lambda name: {
        'api_key': 'test-secret', 'base_url': 'https://eastus.stt.speech.microsoft.com',
    } if name == 'azure-speech' else {})
    monkeypatch.delenv('PRONUNCIATION_PROVIDER', raising=False)
    monkeypatch.delenv('AZURE_SPEECH_KEY', raising=False)
    monkeypatch.delenv('AZURE_SPEECH_REGION', raising=False)
    provider = build_speech_pronunciation_provider()
    assert provider._region == 'eastus'
    assert provider._locale('en') == 'en-US'
    assert provider._locale('zh') == 'zh-CN'


def test_dynamic_speech_resolver_does_not_keep_revoked_key(monkeypatch):
    import writing_coach.speech_api as speech
    from fastapi import HTTPException
    current = [object()]
    monkeypatch.setattr(speech, '_speech_pronunciation_provider', current[0])
    monkeypatch.setattr(speech, '_speech_pronunciation_resolver', lambda: current[0])
    assert speech._pronunciation_provider() is current[0]
    current[0] = None
    with pytest.raises(HTTPException) as failure:
        speech._pronunciation_provider()
    assert failure.value.status_code == 503
