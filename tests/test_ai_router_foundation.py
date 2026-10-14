"""AI Cost Router slice 1 foundations (D-195): the OpenRouter provider, free-model pricing, the
`word_translation` catalogue entry, the input-class rule and the telemetry fields.

Nothing here touches the network: `requests.post` is replaced by a fake.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from writing_coach.agent.budget import DailySpendGuard
from writing_coach.ai import providers as providers_module
from writing_coach.ai.base import (
    AICapabilityConfigInvalid,
    AIProviderError,
    AIProviderUnavailable,
    sanitize_telemetry,
)
from writing_coach.ai.capabilities import AIFallbackPolicy, AIOperation, require_capability
from writing_coach.ai.config import CapabilityConfig, validate_capability_config
from writing_coach.ai.pricing import (
    PRICING_CATALOG_VERSION,
    estimate_token_cost,
    is_free_model,
    resolve_token_pricing,
)
from writing_coach.ai.providers import (
    OpenAICompatibleProvider,
    build_providers,
    get_provider_definition,
)

GEMMA = "google/gemma-4-31b-it:free"
QWEN = "qwen/qwen3-next-80b-a3b-instruct:free"


class _Response:
    def __init__(self, status: int = 200, body: Any = None) -> None:
        self.status_code = status
        self._body = body if body is not None else {
            "choices": [{"message": {"content": '{"meaning": "xin chào"}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
        }
        self.headers: dict[str, str] = {}

    def json(self) -> Any:
        return self._body


@pytest.fixture
def post(monkeypatch):
    sent: list[dict[str, Any]] = []
    queue: list[Any] = []

    def fake_post(url, **kwargs):
        sent.append({"url": url, **kwargs})
        item = queue.pop(0) if queue else _Response()
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr(providers_module.requests, "post", fake_post)
    sent_queue = type("Q", (), {"sent": sent, "queue": queue})
    return sent_queue


def _openrouter(monkeypatch) -> OpenAICompatibleProvider:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    return build_providers()["openrouter"]


def _ask(provider, model=GEMMA, **kwargs):
    return provider.generate_json_once(
        messages=[{"role": "user", "content": "{}"}],
        schema={"type": "object"},
        model=model,
        max_output_tokens=50,
        temperature=0.0,
        **kwargs,
    )


# --- OpenRouter provider ----------------------------------------------------------------------------------------


def test_openrouter_is_a_structured_text_provider_that_may_log_prompts() -> None:
    definition = get_provider_definition("openrouter")
    assert definition is not None
    assert definition.supports(AIOperation.STRUCTURED_TEXT_GENERATION)
    assert {"temperature", "timeout_seconds"} <= definition.supported_option_keys
    assert definition.may_log_prompts is True
    assert get_provider_definition("openai").may_log_prompts is False


def test_openrouter_uses_its_base_url_and_the_named_environment_key(monkeypatch, post) -> None:
    provider = _openrouter(monkeypatch)
    assert provider.configured and provider.base_url == "https://openrouter.ai/api/v1"
    _ask(provider)
    assert post.sent[0]["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert post.sent[0]["headers"]["Authorization"].startswith("Bearer ")


def test_openrouter_is_not_configured_without_a_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert build_providers()["openrouter"].configured is False


def test_openrouter_never_lets_openrouter_fail_over_on_its_own(monkeypatch, post) -> None:
    _ask(_openrouter(monkeypatch))
    assert post.sent[0]["json"]["provider"] == {"allow_fallbacks": False}


def test_other_providers_do_not_send_a_provider_block(monkeypatch, post) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    _ask(build_providers()["openai"], model="gpt-4o-mini")
    assert "provider" not in post.sent[0]["json"]


@pytest.mark.parametrize("model", ["openrouter/auto", "openrouter/free", "OpenRouter/Auto:free", "gemma-4:free", "google/gemma-4-31b-it", ""])
def test_openrouter_refuses_router_ids_unprefixed_ids_and_paid_ids(monkeypatch, post, model) -> None:
    provider = _openrouter(monkeypatch)
    with pytest.raises((AICapabilityConfigInvalid, AIProviderUnavailable)):
        _ask(provider, model=model)
    assert post.sent == []  # refused before any request


@pytest.mark.parametrize("model", ["openrouter/auto", "openrouter/free", "gemma-4:free", "google/gemma-4-31b-it"])
def test_static_validation_refuses_the_same_ids(model) -> None:
    config = CapabilityConfig(enabled=False, provider="openrouter", model=model, fallback_policy=AIFallbackPolicy.NONE)
    with pytest.raises(AICapabilityConfigInvalid):
        validate_capability_config("word_translation", config)
    standby = CapabilityConfig(
        enabled=False, provider="openrouter", model=GEMMA, backup_provider="openrouter", backup_model=model
    )
    with pytest.raises(AICapabilityConfigInvalid):
        validate_capability_config("word_translation", standby)


def test_errors_carry_the_http_status(monkeypatch, post) -> None:
    provider = _openrouter(monkeypatch)
    post.queue.extend([_Response(429, {"error": {"message": "rate limit"}}), _Response(503, {})])
    with pytest.raises(AIProviderError) as first:
        _ask(provider)
    with pytest.raises(AIProviderError) as second:
        _ask(provider)
    assert (first.value.status_code, second.value.status_code) == (429, 503)
    assert AIProviderError().status_code is None


def test_a_timeout_is_passed_to_the_request_and_raises_a_timeout_error(monkeypatch, post) -> None:
    provider = _openrouter(monkeypatch)
    _ask(provider, timeout=1.25)
    assert post.sent[0]["timeout"] == 1.25
    _ask(provider)
    assert post.sent[1]["timeout"] == provider.timeout  # no timeout asked: the provider's own
    post.queue.append(providers_module.requests.Timeout())
    with pytest.raises(providers_module.AIProviderTimeout) as caught:
        _ask(provider, timeout=0.5)
    assert isinstance(caught.value, AIProviderUnavailable)


# --- Capability + input-class rule ------------------------------------------------------------------------------


def test_word_translation_is_a_configurable_opt_in_public_reference_capability() -> None:
    definition = require_capability("word_translation")
    assert definition.operation is AIOperation.STRUCTURED_TEXT_GENERATION
    assert definition.provider_backed and definition.configurable and definition.implemented
    assert definition.allowed_fallback_policies == {AIFallbackPolicy.NONE, AIFallbackPolicy.DETERMINISTIC_FALLBACK}
    assert definition.input_class == "public_reference" and definition.opt_in is True


def test_every_other_provider_capability_carries_learner_text() -> None:
    from writing_coach.ai.capabilities import all_capabilities

    for definition in all_capabilities():
        if definition.key != "word_translation":
            assert definition.input_class == "learner_text", definition.key
            assert definition.opt_in is False


def test_word_translation_accepts_a_free_openrouter_pool() -> None:
    config = CapabilityConfig(
        enabled=False, provider="openrouter", model=GEMMA, backup_provider="openrouter", backup_model=QWEN,
        timeout_seconds=3, temperature=0.0,
    )
    validate_capability_config("word_translation", config)


@pytest.mark.parametrize("capability", ["writing_evaluator", "learner_dictionary", "text_discussion"])
def test_learner_text_capabilities_refuse_prompt_logging_and_free_endpoints(capability) -> None:
    config = CapabilityConfig(enabled=False, provider="openrouter", model=GEMMA)
    with pytest.raises(AICapabilityConfigInvalid, match="learner"):
        validate_capability_config(capability, config)
    standby = CapabilityConfig(
        enabled=False, provider="openai", model="gpt-4o-mini", backup_provider="openrouter", backup_model=GEMMA
    )
    with pytest.raises(AICapabilityConfigInvalid, match="learner"):
        validate_capability_config(capability, standby)


def test_free_is_decided_by_the_price_table_or_the_free_suffix_never_by_guesswork() -> None:
    assert is_free_model("openrouter", GEMMA) and is_free_model("openrouter", "vendor/unlisted:free")
    assert not is_free_model("openai", "gpt-4o-mini") and not is_free_model("openrouter", "vendor/paid")
    # A paid model on a provider that does not log prompts stays valid for learner text.
    validate_capability_config("writing_evaluator", CapabilityConfig(enabled=False, provider="openai", model="gpt-4o-mini"))


def test_a_per_capability_timeout_now_saves() -> None:
    validate_capability_config(
        "writing_evaluator", CapabilityConfig(enabled=False, provider="openai", model="m", timeout_seconds=30)
    )
    with pytest.raises(AICapabilityConfigInvalid):
        CapabilityConfig(enabled=False, provider="openai", model="m", timeout_seconds=0)


# --- Pricing ---------------------------------------------------------------------------------------------------


def test_the_catalog_version_moved_and_free_models_have_explicit_zero_rates() -> None:
    assert PRICING_CATALOG_VERSION != "2026-10-04.v2"
    for model in (GEMMA, QWEN):
        rate = resolve_token_pricing("openrouter", model)
        assert rate is not None and rate.input_per_million == 0 and rate.output_per_million == 0


@pytest.mark.parametrize("usage", [None, {}, {"prompt_tokens": 5}, {"prompt_tokens": 5, "completion_tokens": 2}])
def test_a_free_model_is_estimated_at_zero_whatever_usage_was_reported(usage) -> None:
    cost = estimate_token_cost("openrouter", GEMMA, usage)
    assert cost["state"] == "estimated" and cost["amount"] == 0 and cost["currency"] == "USD"


def test_free_calls_do_not_trip_the_daily_spend_guard() -> None:
    """The ledger counts a success whose cost state is not "estimated" as an unpriced call (0.01 USD each)."""

    events = [{"outcome": "success", "provider": "openrouter", "cost": estimate_token_cost("openrouter", GEMMA, None)}
              for _ in range(500)]

    def read(_since: datetime) -> tuple[float, int]:
        usd = sum(e["cost"]["amount"] or 0 for e in events)
        unpriced = sum(1 for e in events if e["cost"]["state"] != "estimated")
        return usd, unpriced

    guard = DailySpendGuard(cap_usd=1.0, read=read, now=lambda: datetime(2026, 10, 14, 12, tzinfo=UTC))
    assert guard() is None  # 500 calls * 0.01 would have been 5 USD if they were "unpriced"


def test_an_unknown_model_is_still_unpriced() -> None:
    assert estimate_token_cost("openrouter", "vendor/unlisted:free", None)["state"] == "unpriced"


# --- Telemetry -------------------------------------------------------------------------------------------------


def _event(**extra: Any) -> dict[str, Any]:
    return {"capability": "word_translation", "origin": "learner", "provider": "openrouter", "model": GEMMA,
            "outcome": "failure", "error_class": "provider_error", **extra}


def test_router_fields_pass_the_allowlist_and_junk_does_not() -> None:
    safe = sanitize_telemetry(_event(tier="free", phase="pool", attempt=2, fallback_reason="rate_limited",
                                     http_status_class="429", router_version="1"))
    assert (safe["tier"], safe["phase"], safe["attempt"]) == ("free", "pool", 2)
    assert (safe["fallback_reason"], safe["http_status_class"], safe["router_version"]) == ("rate_limited", "429", "1")
    junk = sanitize_telemetry(_event(tier="https://x", phase="Bad Phase", attempt=-3, fallback_reason="a b",
                                     http_status_class="teapot", router_version="x y", word="lamp", prompt="lamp"))
    for key in ("tier", "phase", "attempt", "fallback_reason", "http_status_class", "router_version"):
        assert junk.get(key) is None, key
    assert "word" not in junk and "prompt" not in junk


def test_events_without_router_fields_keep_their_old_shape() -> None:
    safe = sanitize_telemetry(_event())
    assert not ({"tier", "phase", "attempt", "fallback_reason", "http_status_class", "router_version"} & set(safe))
