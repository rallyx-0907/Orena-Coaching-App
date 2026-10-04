"""Azure Speech control-plane adapter; assessment remains in speech_pronunciation."""
import os
import re
from urllib.parse import urlsplit

import requests

from writing_coach.ai.base import AIProviderError, AIProviderUnavailable


def speech_region(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    match = re.fullmatch(r'([a-z0-9]+)\.stt\.speech\.microsoft\.com', parsed.hostname or '')
    if not match or parsed.scheme != 'https' or parsed.path not in {'', '/'} or parsed.port or parsed.query or parsed.fragment or parsed.username:
        raise ValueError('Use the HTTPS regional Azure Speech endpoint.')
    return match[1]


class AzureSpeechControlProvider:
    id = 'azure-speech'
    name = 'Azure Speech'
    kind = 'cloud'
    secret_mode = 'server-managed'
    default_model = 'pronunciation-assessment'

    def __init__(self, credentials=None):
        credentials = credentials or {}
        self.api_key = credentials.get('api_key', os.getenv('AZURE_SPEECH_KEY', '')).strip()
        region = os.getenv('AZURE_SPEECH_REGION', '').strip()
        self.base_url = credentials.get('base_url') or (f'https://{region}.stt.speech.microsoft.com' if region else '')

    @property
    def configured(self):
        try:
            speech_region(self.base_url)
            return bool(self.api_key)
        except ValueError:
            return False

    def list_models(self):
        return [self.default_model] if self.configured else []

    def discover_models_live(self):
        if not self.configured:
            raise AIProviderUnavailable('Azure Speech key and regional endpoint are required.')
        region = speech_region(self.base_url)
        try:
            response = requests.post(f'https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken',
                headers={'Ocp-Apim-Subscription-Key': self.api_key}, timeout=10, allow_redirects=False)
        except requests.RequestException as exc:
            raise AIProviderUnavailable('Azure Speech connection failed.') from exc
        if response.status_code != 200:
            raise AIProviderError(f'Azure Speech returned HTTP {response.status_code}.')
        return [self.default_model]
