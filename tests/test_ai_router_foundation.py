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
STANDBY = "google/gemma-4-26b-a4b-it:free"


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


@pytest.mark.parametrize("model", ["openrouter/auto", "openrouter/free", "OpenRouter/Auto:free", "gemma-4:free", "google/gemma-4-31b-it", "", "vendor/unlisted:free"])
def test_openrouter_refuses_router_ids_unprefixed_ids_and_paid_ids(monkeypatch, post, model) -> None:
    provider = _openrouter(monkeypatch)
    with pytest.raises((AICapabilityConfigInvalid, AIProviderUnavailable)):
        _ask(provider, model=model)
    assert post.sent == []  # refused before any request


@pytest.mark.parametrize("model", ["openrouter/auto", "openrouter/free", "gemma-4:free", "google/gemma-4-31b-it", "vendor/unlisted:free"])
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
        enabled=False, provider="openrouter", model=GEMMA, backup_provider="openrouter", backup_model=STANDBY,
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
    for model in (GEMMA, STANDBY):
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


# --- review 43ce4621 (P1-1, P1-2, P2-1) ---------------------------------------------------------------------------


def test_an_unlisted_free_model_is_refused_because_the_ledger_would_charge_it_as_unpriced() -> None:
    """P1-1: a ':free' id with no zero-rate catalogue entry is 'unpriced' (0.01 USD a call on the shared guard)."""

    assert estimate_token_cost("openrouter", "vendor/unlisted:free", None)["state"] == "unpriced"
    with pytest.raises(AICapabilityConfigInvalid, match="catalogue"):
        providers_module.check_model_allowed("openrouter", "vendor/unlisted:free")
    providers_module.check_model_allowed("openrouter", GEMMA)  # the pinned ones pass
    providers_module.check_model_allowed("openai", "anything-goes")  # no rule for other providers


def test_the_model_picker_lists_only_catalogued_free_models(monkeypatch) -> None:
    provider = _openrouter(monkeypatch)
    assert provider._accept_model(GEMMA) and provider._accept_model(STANDBY)
    assert not provider._accept_model("vendor/unlisted:free") and not provider._accept_model("openrouter/free")


@pytest.mark.parametrize(
    ("provider", "model"), [("openai", "gpt-4o-mini"), ("gemini", "gemini-3.5-flash-lite"), ("deepseek", "deepseek-chat")]
)
def test_word_translation_refuses_a_paid_model_until_a_spend_cap_exists(provider, model) -> None:
    """P1-2: free or local only, primary and standby (the per-capability cap is a later slice)."""

    with pytest.raises(AICapabilityConfigInvalid, match="free or local"):
        validate_capability_config("word_translation", CapabilityConfig(enabled=False, provider=provider, model=model))
    with pytest.raises(AICapabilityConfigInvalid, match="free or local"):
        validate_capability_config(
            "word_translation",
            CapabilityConfig(enabled=False, provider="openrouter", model=GEMMA, backup_provider=provider, backup_model=model),
        )


def test_word_translation_accepts_a_local_model() -> None:
    validate_capability_config("word_translation", CapabilityConfig(enabled=False, provider="ollama", model="qwen3:8b"))


def test_other_capabilities_are_not_limited_to_free_models() -> None:
    validate_capability_config("writing_evaluator", CapabilityConfig(enabled=False, provider="openai", model="gpt-4o-mini"))
    assert require_capability("word_translation").free_only is True
    assert require_capability("writing_evaluator").free_only is False


def test_the_wire_check_is_in_the_single_choke_point_every_request_passes(monkeypatch, post) -> None:
    """P2-1: _post_chat and the stream both refuse a router id, whatever method reached them."""

    provider = _openrouter(monkeypatch)
    with pytest.raises(AICapabilityConfigInvalid):
        provider._post_chat({"model": "openrouter/auto", "messages": []})
    with pytest.raises(AICapabilityConfigInvalid):
        provider.stream_chat(messages=[], tools=[], model="openrouter/free", max_output_tokens=5)
    with pytest.raises(AICapabilityConfigInvalid):
        provider.generate_json(messages=[], schema={}, model="vendor/unlisted:free", max_output_tokens=5, temperature=0)
    assert post.sent == []


# --- verified catalogue (2026-10-14), endpoint normalisation, the Admin picker ------------------------------------

NEMOTRON = "nvidia/nemotron-3-super-120b-a12b:free"
CATALOGUE_IDS = [
    "cohere/north-mini-code:free", "google/gemma-4-26b-a4b-it:free", "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free", "nvidia/nemotron-3-ultra-550b-a55b:free",
    "openrouter/free", "vendor/paid-model", "anthropic/claude-paid",
]


def test_the_pinned_free_models_are_the_verified_ones_and_the_nonexistent_qwen_is_gone() -> None:
    assert PRICING_CATALOG_VERSION != "2026-10-14.v3"
    for model in (GEMMA, STANDBY, NEMOTRON):
        rate = resolve_token_pricing("openrouter", model)
        assert rate is not None and (rate.input_per_million, rate.output_per_million) == (0, 0)
        providers_module.check_model_allowed("openrouter", model)
    assert resolve_token_pricing("openrouter", "qwen/qwen3-next-80b-a3b-instruct:free") is None
    with pytest.raises(AICapabilityConfigInvalid):
        providers_module.check_model_allowed("openrouter", "qwen/qwen3-next-80b-a3b-instruct:free")


def test_the_admin_model_picker_offers_only_the_priced_free_ids_of_the_live_catalogue(monkeypatch) -> None:
    """Admin > AI & Models > Capability routing > Word translation: the Model control is `provider.models`, which is the
    provider's live catalogue filtered by the allowlist - so exactly the pinned free ids the catalogue still lists."""

    class _Catalogue:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self):
            return {"data": [{"id": model} for model in CATALOGUE_IDS]}

    requested: list[str] = []

    def fake_get(url, **_kwargs):
        requested.append(url)
        return _Catalogue()

    monkeypatch.setattr(providers_module.requests, "get", fake_get)
    provider = _openrouter(monkeypatch)
    assert provider.list_models() == sorted([GEMMA, STANDBY, NEMOTRON])
    assert provider.discover_models_live() == sorted([GEMMA, STANDBY, NEMOTRON])
    assert requested[0] == "https://openrouter.ai/api/v1/models"


@pytest.mark.parametrize(
    "entered",
    [
        "https://openrouter.ai/api/v1/chat/completions",
        "https://openrouter.ai/api/v1/chat/completions/",
        "https://openrouter.ai/api/v1/",
        "  https://openrouter.ai/api/v1/Chat/Completions  ",
        "https://openrouter.ai/api/v1",
    ],
)
def test_an_endpoint_entered_as_the_chat_completions_url_is_normalised_to_the_base(monkeypatch, post, entered) -> None:
    assert providers_module.normalize_openai_base_url(entered) == "https://openrouter.ai/api/v1"
    for provider_id in ("openrouter", "openai", "groq"):
        built = build_providers({provider_id: {"api_key": "test-key-not-real", "base_url": entered}})[provider_id]
        assert built.base_url == "https://openrouter.ai/api/v1"
    monkeypatch.setenv("OPENROUTER_BASE_URL", entered)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    env_built = build_providers()["openrouter"]
    assert env_built.base_url == "https://openrouter.ai/api/v1"
    _ask(env_built)
    assert post.sent[0]["url"] == "https://openrouter.ai/api/v1/chat/completions"  # never .../chat/completions/chat/...


def test_model_discovery_uses_the_normalised_base_not_chat_completions_models(monkeypatch) -> None:
    seen: list[str] = []

    class _Empty:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self):
            return {"data": [{"id": GEMMA}]}

    monkeypatch.setattr(providers_module.requests, "get", lambda url, **_k: seen.append(url) or _Empty())
    built = build_providers({"openrouter": {"api_key": "test-key-not-real",
                                            "base_url": "https://openrouter.ai/api/v1/chat/completions"}})["openrouter"]
    assert built.discover_models_live() == [GEMMA]
    assert seen == ["https://openrouter.ai/api/v1/models"]


def test_saving_an_endpoint_stores_the_normalised_base(monkeypatch) -> None:
    import writing_coach.ai.platform as platform

    monkeypatch.setattr(platform, "_platform_repository", None)
    values = platform._provider_credential_values(
        "openrouter",
        platform.ProviderCredentialIn(api_key="test-key-not-real", base_url="https://openrouter.ai/api/v1/chat/completions",
                                      models=[GEMMA], default_model=GEMMA),
    )
    assert values["base_url"] == "https://openrouter.ai/api/v1"
