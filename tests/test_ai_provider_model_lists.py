"""What a provider offers in the Admin model picker: a stored list is a cache, a code-owned allowlist is read-time.

The Admin credential save stores the whole live list it saw (`models: live`), so a stored list is a snapshot, not an
operator restriction. For OpenRouter the allowlist is code-owned (`check_model_allowed`: a pinned, zero-rate ':free'
id), so a model added to the price catalogue after the credential was saved must appear without a re-save. An explicit
operator allowlist (the `OPENROUTER_MODELS` environment variable; any other provider's stored or environment list)
keeps its meaning, and a code-owned rule still applies on top of it.
"""

from __future__ import annotations

import pytest

from writing_coach.ai import providers as providers_module
from writing_coach.ai.providers import build_providers

GEMMA = "google/gemma-4-31b-it:free"
GEMMA_SMALL = "google/gemma-4-26b-a4b-it:free"
NEMOTRON = "nvidia/nemotron-3-super-120b-a12b:free"
LIVE = [GEMMA, GEMMA_SMALL, NEMOTRON, "cohere/north-mini-code:free", "openrouter/free", "vendor/paid-model"]
PRICED = sorted([GEMMA, GEMMA_SMALL, NEMOTRON])


class _Catalogue:
    status_code = 200

    def __init__(self, ids):
        self._ids = ids

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return {"data": [{"id": model} for model in self._ids]}


@pytest.fixture
def live(monkeypatch):
    calls: list[str] = []
    state = {"ids": LIVE, "down": False}

    def fake_get(url, **_kwargs):
        calls.append(url)
        if state["down"]:
            raise providers_module.requests.ConnectionError("down")
        return _Catalogue(state["ids"])

    monkeypatch.setattr(providers_module.requests, "get", fake_get)
    monkeypatch.delenv("OPENROUTER_MODELS", raising=False)
    monkeypatch.delenv("OPENAI_MODELS", raising=False)
    providers_module.reset_catalogue_cache()
    yield type("Live", (), {"calls": calls, "state": state})
    providers_module.reset_catalogue_cache()


def _openrouter(models=None):
    credential = {"api_key": "test-key-not-real"}
    if models is not None:
        credential["models"] = models
    return build_providers({"openrouter": credential})["openrouter"]


def test_a_credential_saved_before_a_model_was_priced_still_offers_it(live) -> None:
    """The :8021 case: the saved list had only gemma-31b; pricing later added gemma-26b and nemotron."""

    provider = _openrouter(models=[GEMMA])
    assert provider.list_models() == PRICED
    assert provider.discover_models_live() == PRICED


def test_the_stored_list_is_the_fallback_when_the_catalogue_cannot_be_read_and_is_re_filtered(live) -> None:
    provider = _openrouter(models=[GEMMA, "vendor/unlisted:free", "openrouter/free"])
    live.state["down"] = True
    assert provider.list_models() == [GEMMA]  # offline: the cache, minus anything no longer allowed
    with pytest.raises(providers_module.AIProviderUnavailable):
        provider.discover_models_live()  # discovery itself never answers from the cache


def test_with_no_stored_list_the_live_catalogue_filtered_by_the_allowlist_is_offered(live) -> None:
    assert _openrouter().list_models() == PRICED


def test_an_explicit_environment_allowlist_still_restricts_and_is_still_filtered(live, monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_MODELS", f"{GEMMA_SMALL}, vendor/unlisted:free, openrouter/auto")
    provider = _openrouter()
    assert provider.list_models() == [GEMMA_SMALL]  # not the whole catalogue, and nothing that is not allowed
    assert provider.discover_models_live() == [GEMMA_SMALL]
    assert live.calls == []  # an explicit allowlist never asks the catalogue


@pytest.mark.parametrize("provider_id", ["openai", "groq", "gemini", "deepseek"])
def test_other_providers_keep_their_stored_list_exactly(live, provider_id) -> None:
    built = build_providers({provider_id: {"api_key": "test-key-not-real", "models": ["my-model", "another"]}})[provider_id]
    assert built.list_models() == ["another", "my-model"]
    assert built.discover_models_live() == ["another", "my-model"]
    assert live.calls == []


def test_another_providers_environment_allowlist_is_unchanged(live, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("OPENAI_MODELS", "gpt-4o-mini,gpt-4o")
    assert build_providers()["openai"].list_models() == ["gpt-4o", "gpt-4o-mini"]
    assert live.calls == []


# --- review of #179: the catalogue is cached per process, and health never touches the network ----------------------


@pytest.fixture
def clock(monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(providers_module, "_catalogue_clock", lambda: now["t"])
    providers_module.reset_catalogue_cache()
    yield now
    providers_module.reset_catalogue_cache()


def test_repeated_listings_and_rebuilt_providers_make_one_catalogue_call(live, clock) -> None:
    for _ in range(5):
        assert _openrouter(models=[GEMMA]).list_models() == PRICED  # providers() rebuilds the object every call
    shared = _openrouter()
    assert shared.list_models() == PRICED and shared.default_model in PRICED  # default_model lists again
    assert len(live.calls) == 1


def test_the_cache_expires_after_ten_minutes(live, clock) -> None:
    provider = _openrouter()
    provider.list_models()
    clock["t"] += 599
    provider.list_models()
    assert len(live.calls) == 1
    clock["t"] += 2
    live.state["ids"] = [GEMMA]
    assert provider.list_models() == [GEMMA]
    assert len(live.calls) == 2


def test_the_cache_is_per_credential_and_endpoint(live, clock) -> None:
    _openrouter().list_models()
    other = build_providers({"openrouter": {"api_key": "another-test-key", "models": [GEMMA]}})["openrouter"]
    other.list_models()
    assert len(live.calls) == 2


def test_a_failed_catalogue_is_remembered_briefly_not_retried_on_every_request(live, clock) -> None:
    live.state["down"] = True
    provider = _openrouter(models=[GEMMA, "vendor/unlisted:free"])
    for _ in range(4):
        assert provider.list_models() == [GEMMA]  # the stored list, re-filtered
    assert len(live.calls) == 1
    clock["t"] += 31
    live.state["down"] = False
    assert provider.list_models() == PRICED  # asked again after the short failure window
    assert len(live.calls) == 2


def test_explicit_discovery_is_always_live_and_refreshes_the_cache(live, clock) -> None:
    provider = _openrouter()
    provider.list_models()
    live.state["ids"] = [GEMMA, GEMMA_SMALL]
    assert provider.discover_models_live() == sorted([GEMMA, GEMMA_SMALL])  # the credential test sees the truth
    assert len(live.calls) == 2
    assert provider.list_models() == sorted([GEMMA, GEMMA_SMALL])  # and the picker follows
    assert len(live.calls) == 2


def test_offline_listing_never_calls_the_network(live, clock) -> None:
    assert _openrouter().list_models(offline=True) == []  # nothing cached or stored yet: empty, not a request
    assert _openrouter(models=[GEMMA, "vendor/unlisted:free"]).list_models(offline=True) == [GEMMA]
    _openrouter().list_models()
    assert _openrouter().list_models(offline=True) == PRICED  # once cached it is shared
    other = build_providers({"openai": {"api_key": "test-key-not-real"}})["openai"]
    assert other.list_models(offline=True) == []
    assert len(live.calls) == 1  # only the one explicit listing


def test_health_reads_no_catalogue_and_reports_no_models(live, clock, monkeypatch) -> None:
    import writing_coach.ai.platform as platform

    provider = _openrouter()
    monkeypatch.setattr(platform, "active_selection", lambda: (provider, GEMMA))
    status = platform.active_ai_status()
    assert status["ready"] is True and status["provider"] == "openrouter"
    assert live.calls == []
    openai = build_providers({"openai": {"api_key": "test-key-not-real"}})["openai"]
    monkeypatch.setattr(platform, "active_selection", lambda: (openai, "gpt-4o-mini"))
    assert platform.active_ai_status()["ready"] is True
    assert live.calls == []
