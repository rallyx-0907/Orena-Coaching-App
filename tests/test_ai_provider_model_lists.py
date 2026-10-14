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
    return type("Live", (), {"calls": calls, "state": state})


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
