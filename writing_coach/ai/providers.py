from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import requests
from urllib.parse import urlsplit, urlunsplit

from writing_coach.ai.base import (
    AIProviderError,
    AIProviderNotConfigured,
    AIProviderResponseInvalid,
    AIProviderUnavailable,
    AIResult,
    ChatFinished,
    ChatStreamEvent,
    ChatTextDelta,
    ChatToolCall,
    extract_json_object,
)
from writing_coach.ai.capabilities import AIOperation


@dataclass(frozen=True)
class ProviderDefinition:
    """Static provider metadata, independent of credentials or live status."""

    id: str
    name: str
    kind: str
    secret_mode: str
    supported_operations: frozenset[AIOperation]
    supported_option_keys: frozenset[str]

    def supports(self, operation: AIOperation) -> bool:
        return operation in self.supported_operations


_STRUCTURED_TEXT_OPERATIONS = frozenset({AIOperation.STRUCTURED_TEXT_GENERATION})
# The managed chat providers also stream agent turns with native tool calls
# (Orena Intelligence, D-085). A local model never does (spec D2).
_CLOUD_CHAT_OPERATIONS = _STRUCTURED_TEXT_OPERATIONS | {AIOperation.AGENT_TURN}

_RATE_LIMIT_HEADER_KEYS = {
    "x-ratelimit-limit-requests": "requests_limit",
    "x-ratelimit-remaining-requests": "requests_remaining",
    "x-ratelimit-limit-tokens": "tokens_limit",
    "x-ratelimit-remaining-tokens": "tokens_remaining",
}


def _normalized_rate_limit_headers(headers: object) -> dict[str, int | None]:
    """Extract only safe integer values from allowlisted response headers."""

    result = {key: None for key in ("requests_limit", "requests_remaining", "tokens_limit", "tokens_remaining")}
    if not hasattr(headers, "items"):
        return result
    for name, key in _RATE_LIMIT_HEADER_KEYS.items():
        raw = next((value for header, value in headers.items() if str(header).casefold() == name), None)
        if type(raw) is int and raw >= 0:
            result[key] = raw
            continue
        if not isinstance(raw, str):
            continue
        value = raw.strip()
        if len(value) > 15 or not re.fullmatch(r"\d+", value):
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if parsed <= 10**15:
            result[key] = parsed
    return result
# generate_json() consumes temperature per request. Timeout is currently bound
# to each runtime instance from environment configuration, so capability config
# must not claim it is independently supported yet.
_TEXT_OPTION_KEYS = frozenset({"temperature"})
_PROVIDER_DEFINITIONS = (
    ProviderDefinition(
        id="ollama",
        name="Ollama",
        kind="local",
        secret_mode="none",
        supported_operations=_STRUCTURED_TEXT_OPERATIONS,
        supported_option_keys=_TEXT_OPTION_KEYS,
    ),
    ProviderDefinition(
        id="openai",
        name="OpenAI API",
        kind="cloud",
        secret_mode="server-managed",
        supported_operations=_CLOUD_CHAT_OPERATIONS,
        supported_option_keys=_TEXT_OPTION_KEYS,
    ),
    ProviderDefinition(
        id="deepseek",
        name="DeepSeek API",
        kind="cloud",
        secret_mode="server-managed",
        supported_operations=_CLOUD_CHAT_OPERATIONS,
        supported_option_keys=_TEXT_OPTION_KEYS,
    ),
    ProviderDefinition(
        id="groq",
        name="Groq API",
        kind="cloud",
        secret_mode="server-managed",
        supported_operations=_CLOUD_CHAT_OPERATIONS,
        supported_option_keys=_TEXT_OPTION_KEYS,
    ),
    ProviderDefinition(
        id="gemini",
        name="Gemini API",
        kind="cloud",
        secret_mode="server-managed",
        supported_operations=_CLOUD_CHAT_OPERATIONS,
        supported_option_keys=_TEXT_OPTION_KEYS,
    ),
)
_PROVIDER_CATALOG = MappingProxyType(
    {definition.id: definition for definition in _PROVIDER_DEFINITIONS}
)


def provider_definitions() -> tuple[ProviderDefinition, ...]:
    """Return static descriptors without instantiating or probing providers."""

    return _PROVIDER_DEFINITIONS


def get_provider_definition(provider_id: str) -> ProviderDefinition | None:
    """Look up a known provider descriptor without inspecting its environment."""

    return _PROVIDER_CATALOG.get(str(provider_id or "").strip().casefold())


def _schema_instruction(schema: dict[str, Any]) -> str:
    return (
        "\nReturn exactly one valid JSON object. It must follow this JSON Schema:\n"
        + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    )


def _invalid_model_catalog() -> AIProviderResponseInvalid:
    return AIProviderResponseInvalid("AI provider returned an invalid model catalog.")


def _model_catalog(envelope: object, *, container_key: str, model_key: str) -> list[str]:
    if not isinstance(envelope, dict):
        raise _invalid_model_catalog()
    entries = envelope.get(container_key)
    if not isinstance(entries, list):
        raise _invalid_model_catalog()
    models: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise _invalid_model_catalog()
        model = entry.get(model_key)
        if not isinstance(model, str) or not model.strip():
            raise _invalid_model_catalog()
        models.append(model.strip())
    return models


def _safe_provider_http_hint(response: requests.Response | None) -> str:
    """Return a coarse provider error hint without forwarding response data."""

    if response is None:
        return ""
    try:
        envelope = response.json()
        message = envelope.get("error", {}).get("message", "") if isinstance(envelope, dict) else ""
    except (ValueError, AttributeError):
        return ""
    if not isinstance(message, str):
        return ""
    lowered = message.casefold()
    if "api key" in lowered or "authentication" in lowered or "unauthenticated" in lowered:
        return "Google rejected the API credential."
    if "permission" in lowered or "forbidden" in lowered:
        return "The provider denied permission for this credential."
    if "quota" in lowered or "rate limit" in lowered:
        return "The provider quota or rate limit was reached."
    return ""


def _openai_message_content(envelope: object) -> tuple[dict[str, Any], str]:
    if not isinstance(envelope, dict):
        raise AIProviderResponseInvalid("AI provider returned an invalid response.")
    choices = envelope.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise AIProviderResponseInvalid("AI provider returned an invalid response.")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise AIProviderResponseInvalid("AI provider returned an invalid response.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise AIProviderResponseInvalid("AI provider returned an invalid response.")
    return choices[0], content


def _ollama_message_content(envelope: object) -> tuple[dict[str, Any], str]:
    if not isinstance(envelope, dict):
        raise AIProviderResponseInvalid("AI provider returned an invalid response.")
    message = envelope.get("message")
    if not isinstance(message, dict):
        raise AIProviderResponseInvalid("AI provider returned an invalid response.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise AIProviderResponseInvalid("AI provider returned an invalid response.")
    return envelope, content


class OllamaProvider:
    id = "ollama"
    name = "Ollama"
    kind = "local"
    secret_mode = "none"

    def __init__(self, credential_override: dict[str, Any] | None = None) -> None:
        credential_override = credential_override or {}
        override_url = credential_override.get("base_url")
        # The application runs in Docker, where 127.0.0.1 is the container
        # itself and can never be the host's Ollama. Compose and .env.example
        # both default the endpoint to the Docker host alias, so the code
        # default matches the documented deployment instead of pointing at
        # nothing and degrading every evaluation to 503.
        self.base_url = str(
            override_url if isinstance(override_url, str) and override_url.strip() else os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
        ).strip().rstrip("/")
        self.default_model = str(
            credential_override.get("default_model") or os.getenv("OLLAMA_MODEL", "qwen3:8b")
        ).strip()
        override_models = credential_override.get("models")
        self.allowed_models = [str(value).strip() for value in override_models if str(value).strip()] if isinstance(override_models, list) else []
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT", "180"))

    @property
    def configured(self) -> bool:
        return True

    def list_models(self) -> list[str]:
        if self.allowed_models:
            return sorted(dict.fromkeys(self.allowed_models))
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            response.raise_for_status()
            return sorted(
                {
                    str(item.get("name") or "").strip()
                    for item in response.json().get("models", [])
                    if str(item.get("name") or "").strip()
                }
            )
        except Exception:
            return []

    def discover_models_live(self) -> list[str]:
        """Discover models without collapsing transport failures into an empty list."""

        if self.allowed_models:
            return sorted(dict.fromkeys(self.allowed_models))

        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            response.raise_for_status()
            envelope = response.json()
        except requests.ConnectionError as exc:
            raise AIProviderUnavailable("Ollama is not reachable.") from exc
        except requests.Timeout as exc:
            raise AIProviderUnavailable("Ollama timed out.") from exc
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            raise AIProviderError(f"Ollama returned HTTP {status} during model discovery.") from exc
        except ValueError as exc:
            raise _invalid_model_catalog() from exc
        return sorted(set(_model_catalog(envelope, container_key="models", model_key="name")))

    def generate_json_once(self, **kwargs: Any) -> AIResult:
        """Execute one live-test request; Ollama has no compatibility retry."""

        return self.generate_json(**kwargs)

    def generate_json(
        self,
        *,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        model: str,
        max_output_tokens: int,
        temperature: float,
        seed: int | None = None,
    ) -> AIResult:
        if not model:
            raise AIProviderUnavailable("No Ollama model is selected.")

        options: dict[str, Any] = {
            "temperature": temperature,
            "num_ctx": 4096,
            "num_predict": max_output_tokens,
        }
        if seed is not None:
            options["seed"] = seed

        body = {
            "model": model,
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "format": schema,
            "options": options,
            "messages": messages,
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=body,
                timeout=self.timeout,
            )
            response.raise_for_status()
            envelope = response.json()
        except requests.ConnectionError as exc:
            raise AIProviderUnavailable("Ollama is not reachable.") from exc
        except requests.Timeout as exc:
            raise AIProviderUnavailable("Ollama timed out.") from exc
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            raise AIProviderError(f"Ollama returned HTTP {status}.") from exc
        except ValueError as exc:
            raise AIProviderError("Ollama returned a non-JSON HTTP response.") from exc

        envelope, content = _ollama_message_content(envelope)

        return AIResult(
            data=extract_json_object(content),
            provider=self.id,
            model=model,
            runtime={
                "done_reason": envelope.get("done_reason"),
                "total_duration_ns": envelope.get("total_duration"),
                "load_duration_ns": envelope.get("load_duration"),
                "prompt_eval_count": envelope.get("prompt_eval_count"),
                "eval_count": envelope.get("eval_count"),
                "eval_duration_ns": envelope.get("eval_duration"),
            },
        )


class OpenAICompatibleProvider:
    kind = "cloud"
    secret_mode = "server-managed"

    def __init__(
        self,
        *,
        provider_id: str,
        name: str,
        api_key_env: str,
        base_url_env: str,
        default_base_url: str,
        models_env: str,
        default_models: tuple[str, ...] = (),
        model_filter: str = "",
        credential_override: dict[str, Any] | None = None,
    ) -> None:
        credential_override = credential_override or {}
        self.id = provider_id
        self.name = name
        override_key = credential_override.get("api_key")
        self.api_key = str(
            override_key if isinstance(override_key, str) else os.getenv(api_key_env, "")
        ).strip()
        override_url = credential_override.get("base_url")
        self.base_url = str(
            override_url if isinstance(override_url, str) and override_url.strip() else os.getenv(base_url_env, default_base_url)
        ).strip().rstrip("/")
        override_models = credential_override.get("models")
        raw_models = override_models if isinstance(override_models, list) else os.getenv(models_env, "").split(",")
        self.allowed_models = [str(value).strip() for value in raw_models if str(value).strip()]
        self.default_models = list(default_models)
        self.default_model_override = str(credential_override.get("default_model") or "").strip()
        self.model_filter = model_filter
        self.timeout = int(os.getenv("CLOUD_AI_TIMEOUT", "180"))
        self._last_rate_limit = _normalized_rate_limit_headers(None)

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url)

    @property
    def default_model(self) -> str:
        models = self.list_models()
        if self.default_model_override and (not models or self.default_model_override in models):
            return self.default_model_override
        return models[0] if models else ""

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _model_catalog_request(self) -> tuple[requests.Response, bool]:
        """Request the catalog from the configured provider endpoint.

        Gemini's OpenAI-compatible endpoint exposes ``/models`` and expects
        the same Bearer authentication as ``/chat/completions``. Keeping
        discovery on that compatibility contract is important because it is
        also the contract used by the configured endpoint. If that catalog
        rejects a Gemini credential, retry discovery through Gemini's native
        catalog as a compatibility fallback; chat requests still use the
        configured endpoint.
        """

        response = requests.get(
            f"{self.base_url}/models",
            headers=self._headers(),
            timeout=10,
        )
        if getattr(response, "status_code", 200) < 400:
            return response, False

        parsed = urlsplit(self.base_url)
        is_gemini_compatibility = (
            self.model_filter == "gemini-text"
            and parsed.hostname == "generativelanguage.googleapis.com"
            and parsed.path.rstrip("/").endswith("/v1beta/openai")
        )
        if not is_gemini_compatibility:
            return response, False

        native_path = parsed.path.rstrip("/")[: -len("/openai")] + "/models"
        native_url = urlunsplit((parsed.scheme, parsed.netloc, native_path, "", ""))
        native_response = requests.get(
            native_url,
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        return native_response, True

    def _catalog_models(self, envelope: object, *, native_gemini: bool) -> list[str]:
        if native_gemini:
            return [
                model.rsplit("/", 1)[-1]
                for model in _model_catalog(envelope, container_key="models", model_key="name")
            ]
        models = _model_catalog(envelope, container_key="data", model_key="id")
        if self.model_filter == "gemini-text":
            # Gemini's OpenAI-compatible catalogue answers with resource names
            # ("models/gemini-2.5-flash"); the chat endpoint and the filter take
            # the bare model id, the same one the native catalogue yields.
            return [model.rsplit("/", 1)[-1] for model in models]
        return models

    def _accept_model(self, model: str) -> bool:
        if not model:
            return False
        if self.model_filter == "openai-text":
            lowered = model.casefold()
            blocked = (
                "audio", "realtime", "transcribe", "tts", "image",
                "embedding", "moderation", "dall-e", "search-preview",
                "computer-use", "sora", "whisper", "codex",
            )
            if any(word in lowered for word in blocked):
                return False
            return bool(lowered.startswith("gpt-") or re.match(r"^o\d", lowered))
        if self.model_filter == "groq-text":
            # Groq serves speech, text-to-speech and prompt-classification models
            # from the same catalog endpoint. Only chat models belong in a
            # structured-text picker; whisper is reached through the speech
            # adapter, not through here.
            lowered = model.casefold()
            blocked = ("whisper", "orpheus", "prompt-guard", "safeguard", "tts")
            return not any(word in lowered for word in blocked)
        if self.model_filter == "gemini-text":
            lowered = model.casefold()
            blocked = ("embedding", "imagen", "veo", "live", "audio", "tts")
            return lowered.startswith("gemini-") and not any(word in lowered for word in blocked)
        return True

    def list_models(self) -> list[str]:
        if not self.configured:
            return []
        if self.allowed_models:
            return sorted(dict.fromkeys(self.allowed_models))
        if self.default_models:
            return list(self.default_models)

        try:
            response, native_gemini = self._model_catalog_request()
            response.raise_for_status()
            return sorted({
                model
                for model in self._catalog_models(response.json(), native_gemini=native_gemini)
                if self._accept_model(model)
            })
        except Exception:
            return []

    def discover_models_live(self) -> list[str]:
        """Return an authoritative catalog or a typed live-discovery failure."""

        if not self.configured:
            raise AIProviderNotConfigured(f"{self.name} is not configured on the server.")
        if self.allowed_models:
            return sorted(dict.fromkeys(self.allowed_models))

        try:
            response, native_gemini = self._model_catalog_request()
            response.raise_for_status()
            envelope = response.json()
        except requests.ConnectionError as exc:
            raise AIProviderUnavailable(f"{self.name} is not reachable.") from exc
        except requests.Timeout as exc:
            raise AIProviderUnavailable(f"{self.name} timed out.") from exc
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            hint = _safe_provider_http_hint(exc.response)
            raise AIProviderError(
                f"{self.name} returned HTTP {status} during model discovery. {hint}".strip()
            ) from exc
        except ValueError as exc:
            raise _invalid_model_catalog() from exc
        return sorted(
            model
            for model in set(self._catalog_models(envelope, native_gemini=native_gemini))
            if self._accept_model(model)
        )

    def _post_chat(self, body: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=body,
            timeout=self.timeout,
        )
        self._last_rate_limit = _normalized_rate_limit_headers(getattr(response, "headers", None))
        if response.status_code >= 400:
            detail = _error_detail(response)
            error = AIProviderError(
                f"{self.name} returned HTTP {response.status_code}. {detail[:300]}".strip()
            )
            error.rate_limit = dict(self._last_rate_limit)
            raise error
        try:
            return response.json()
        except ValueError as exc:
            raise AIProviderError(f"{self.name} returned a non-JSON HTTP response.") from exc

    def generate_json(
        self,
        *,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        model: str,
        max_output_tokens: int,
        temperature: float,
        seed: int | None = None,
    ) -> AIResult:
        if not self.configured:
            raise AIProviderUnavailable(f"{self.name} is not configured on the server.")
        if not model:
            raise AIProviderUnavailable(f"No model is selected for {self.name}.")

        enriched = [dict(message) for message in messages]
        if enriched and enriched[0].get("role") == "system":
            enriched[0]["content"] = str(enriched[0].get("content") or "") + _schema_instruction(schema)
        else:
            enriched.insert(0, {"role": "system", "content": _schema_instruction(schema).strip()})

        body: dict[str, Any] = {
            "model": model,
            "messages": enriched,
            "stream": False,
            "max_tokens": max_output_tokens,
            "response_format": {"type": "json_object"},
            "temperature": temperature,
        }
        if seed is not None:
            body["seed"] = seed

        try:
            envelope = self._post_chat(body)
        except AIProviderError as first_error:
            retry = dict(body)
            retry.pop("temperature", None)
            retry.pop("seed", None)
            try:
                envelope = self._post_chat(retry)
            except AIProviderError:
                raise first_error

        first_choice, content = _openai_message_content(envelope)

        usage = envelope.get("usage") if isinstance(envelope.get("usage"), dict) else {}
        return AIResult(
            data=extract_json_object(content),
            provider=self.id,
            model=model,
            runtime={
                "finish_reason": first_choice.get("finish_reason"),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "rate_limit": dict(self._last_rate_limit),
            },
        )

    def generate_json_once(
        self,
        *,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        model: str,
        max_output_tokens: int,
        temperature: float,
        seed: int | None = None,
    ) -> AIResult:
        """Execute one structured request without the legacy compatibility retry."""

        if not self.configured:
            raise AIProviderNotConfigured(f"{self.name} is not configured on the server.")
        if not model:
            raise AIProviderUnavailable(f"No model is selected for {self.name}.")

        enriched = [dict(message) for message in messages]
        if enriched and enriched[0].get("role") == "system":
            enriched[0]["content"] = str(enriched[0].get("content") or "") + _schema_instruction(schema)
        else:
            enriched.insert(0, {"role": "system", "content": _schema_instruction(schema).strip()})

        body: dict[str, Any] = {
            "model": model,
            "messages": enriched,
            "stream": False,
            "max_tokens": max_output_tokens,
            "response_format": {"type": "json_object"},
            "temperature": temperature,
        }
        if seed is not None:
            body["seed"] = seed
        try:
            envelope = self._post_chat(body)
        except requests.ConnectionError as exc:
            raise AIProviderUnavailable(f"{self.name} is not reachable.") from exc
        except requests.Timeout as exc:
            raise AIProviderUnavailable(f"{self.name} timed out.") from exc

        first_choice, content = _openai_message_content(envelope)
        usage = envelope.get("usage") if isinstance(envelope.get("usage"), dict) else {}
        return AIResult(
            data=extract_json_object(content),
            provider=self.id,
            model=model,
            runtime={
                "finish_reason": first_choice.get("finish_reason"),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "rate_limit": dict(self._last_rate_limit),
            },
        )


    def stream_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
        max_output_tokens: int,
        temperature: float | None = None,
        should_stop: Callable[[], bool] = lambda: False,
        read_timeout: float | None = None,
    ) -> Iterator[ChatStreamEvent]:
        """One streamed chat round with native tool calls (Orena Intelligence, D-085).

        The same chat/completions endpoint as `generate_json_once`, with
        `stream: true` and the OpenAI `tools` array. Transport and HTTP
        failures raise here, before anything streams; the returned iterator
        yields text deltas, then each complete tool call, then one
        `ChatFinished`, and stops early when `should_stop()` turns true.
        `read_timeout` bounds each wait for the response and for every next
        piece of it, so a silent provider cannot hold a worker thread for the
        whole server timeout after the learner has gone.
        """

        if not self.configured:
            raise AIProviderNotConfigured(f"{self.name} is not configured on the server.")
        if not model:
            raise AIProviderUnavailable(f"No model is selected for {self.name}.")
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "max_tokens": max_output_tokens,
        }
        if tools:
            body["tools"] = tools
        if temperature is not None:
            body["temperature"] = temperature
        if self.id in _STREAM_USAGE_PROVIDERS:
            # These report usage on a stream only when asked; an endpoint whose
            # support is unverified is not sent a field it may reject, and its
            # usage stays unknown rather than being guessed.
            body["stream_options"] = {"include_usage": True}
        wait = min(float(self.timeout), read_timeout) if read_timeout and read_timeout > 0 else float(self.timeout)
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=body,
                timeout=(min(10.0, wait), wait),
                stream=True,
            )
        except requests.ConnectionError as exc:
            raise AIProviderUnavailable(f"{self.name} is not reachable.") from exc
        except requests.Timeout as exc:
            raise AIProviderUnavailable(f"{self.name} timed out.") from exc
        self._last_rate_limit = _normalized_rate_limit_headers(getattr(response, "headers", None))
        if response.status_code >= 400:
            try:
                detail = _error_detail(response)
            finally:
                response.close()
            error = AIProviderError(f"{self.name} returned HTTP {response.status_code}. {detail[:300]}".strip())
            error.rate_limit = dict(self._last_rate_limit)
            raise error
        return self._read_chat_stream(response, should_stop)

    def _read_chat_stream(
        self, response: requests.Response, should_stop: Callable[[], bool]
    ) -> Iterator[ChatStreamEvent]:
        calls: dict[object, dict[str, Any]] = {}
        order: list[object] = []
        finish_reason = ""
        usage: dict[str, Any] = {}
        try:
            for raw in response.iter_lines():
                if should_stop():
                    return
                line = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw or "")
                if not line.startswith("data:"):
                    continue  # blank keep-alives, comments, event names
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except ValueError as exc:
                    raise AIProviderResponseInvalid(f"{self.name} sent a malformed stream chunk.") from exc
                if not isinstance(chunk, dict):
                    raise AIProviderResponseInvalid(f"{self.name} sent a malformed stream chunk.")
                if chunk.get("error"):
                    raise AIProviderError(f"{self.name} reported an error while streaming.")
                for container in (chunk, chunk.get("x_groq")):
                    if isinstance(container, dict) and isinstance(container.get("usage"), dict):
                        usage = container["usage"]
                for choice in chunk.get("choices") or ():
                    if not isinstance(choice, dict) or choice.get("index", 0) != 0:
                        continue
                    delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        yield ChatTextDelta(content)
                    for position, part in enumerate(delta.get("tool_calls") or ()):
                        if not isinstance(part, dict):
                            continue
                        key = _tool_call_key(part, position, order)
                        slot = calls.get(key)
                        if slot is None:
                            slot = calls[key] = {"id": "", "name": "", "arguments": [], "extra": None}
                            order.append(key)
                        if isinstance(part.get("id"), str) and part["id"]:
                            slot["id"] = part["id"]
                        if isinstance(part.get("extra_content"), dict):
                            slot["extra"] = part["extra_content"]
                        function = part.get("function") if isinstance(part.get("function"), dict) else {}
                        if isinstance(function.get("name"), str) and function["name"]:
                            slot["name"] = function["name"]
                        if isinstance(function.get("arguments"), str):
                            slot["arguments"].append(function["arguments"])
                    if isinstance(choice.get("finish_reason"), str) and choice["finish_reason"]:
                        finish_reason = choice["finish_reason"]
        except requests.RequestException as exc:
            raise AIProviderUnavailable(f"{self.name} stopped streaming.") from exc
        finally:
            response.close()
        for number, key in enumerate(order):
            slot = calls[key]
            if not slot["name"]:
                raise AIProviderResponseInvalid(f"{self.name} sent a tool call without a name.")
            yield ChatToolCall(
                id=slot["id"] or f"call_{number}",
                name=slot["name"],
                arguments="".join(slot["arguments"]),
                extra=slot["extra"],
            )
        # The provider's own reason, never normalised to a normal stop (independent review 2026-10-04): tool calls with
        # "stop" (Gemini's way) are a tool round; anything else - "length", a safety or content filter, or no reason
        # at all (a stream cut short) - is passed on as it is, and the caller fails closed on it.
        if order and finish_reason in ("tool_calls", "stop"):
            reason = "tool_calls"
        else:
            reason = finish_reason or "missing"
        details = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), dict) else {}
        yield ChatFinished(
            finish_reason=reason,
            prompt_tokens=_count(usage.get("prompt_tokens")),
            completion_tokens=_count(usage.get("completion_tokens")),
            cached_tokens=_count(details.get("cached_tokens")),
            rate_limit=dict(self._last_rate_limit),
        )


def _error_detail(response: Any) -> str:
    """The provider's own error message, or "". Gemini's OpenAI-compatible endpoint wraps it in a list."""

    try:
        payload = response.json()
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            payload = payload[0]
        return str(payload.get("error", {}).get("message") or "")
    except Exception:
        return ""


# Endpoints that send a usage chunk on a stream when asked
# (`stream_options.include_usage`). Groq reports it unasked (`x_groq.usage`).
# Gemini's OpenAI-compatible endpoint: verified by the agent's live run, 2026-09-28.
_STREAM_USAGE_PROVIDERS = frozenset({"openai", "deepseek", "gemini"})


def _tool_call_key(part: dict[str, Any], position: int, order: list[object]) -> object:
    """Which call a streamed fragment belongs to.

    OpenAI numbers fragments with `index`; an endpoint that sends each call
    whole may leave it out, so a fragment with a new id starts a new call and
    one with neither continues the last.
    """

    if isinstance(part.get("index"), int):
        return ("index", part["index"])
    if isinstance(part.get("id"), str) and part["id"]:
        return ("id", part["id"])
    return order[-1] if order else ("position", position)


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def build_providers(provider_credentials: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    provider_credentials = provider_credentials or {}
    return {
        "ollama": OllamaProvider(provider_credentials.get("ollama")),
        "openai": OpenAICompatibleProvider(
            provider_id="openai",
            name="OpenAI API",
            api_key_env="OPENAI_API_KEY",
            base_url_env="OPENAI_BASE_URL",
            default_base_url="https://api.openai.com/v1",
            models_env="OPENAI_MODELS",
            default_models=(),
            model_filter="openai-text",
            credential_override=provider_credentials.get("openai"),
        ),
        "deepseek": OpenAICompatibleProvider(
            provider_id="deepseek",
            name="DeepSeek API",
            api_key_env="DEEPSEEK_API_KEY",
            base_url_env="DEEPSEEK_BASE_URL",
            default_base_url="https://api.deepseek.com",
            models_env="DEEPSEEK_MODELS",
            default_models=("deepseek-v4-flash", "deepseek-v4-pro"),
            credential_override=provider_credentials.get("deepseek"),
        ),
        # Groq speaks the OpenAI chat API, so it needs no adapter of its own.
        # Measured against this account: a structured translation answers in
        # about a second, where the local model needed thirty-seven.
        "groq": OpenAICompatibleProvider(
            provider_id="groq",
            name="Groq API",
            api_key_env="GROQ_API_KEY",
            base_url_env="GROQ_BASE_URL",
            default_base_url="https://api.groq.com/openai/v1",
            models_env="GROQ_MODELS",
            default_models=(),
            model_filter="groq-text",
            credential_override=provider_credentials.get("groq"),
        ),
        "gemini": OpenAICompatibleProvider(
            provider_id="gemini",
            name="Gemini API",
            api_key_env="GEMINI_API_KEY",
            base_url_env="GEMINI_BASE_URL",
            default_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            models_env="GEMINI_MODELS",
            default_models=(),
            model_filter="gemini-text",
            credential_override=provider_credentials.get("gemini"),
        ),
    }
