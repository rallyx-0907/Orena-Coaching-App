"""AI cost completeness (D-221, PROPOSED; owner report 2026-10-17: the Gemini console showed about USD 2.0 against
USD 0.92 on the :8021 cost page).

Fakes only: nothing reaches a network or a database. Covers the environment tag (the same provider key is spent from
many environments, each recording into its own database), the thinking tokens a provider reports only in its total,
the Gemini and Azure prices, and the admin connection test that spent tokens without a trace."""
from __future__ import annotations

import json
from typing import Any

import pytest

from tests.policy_support import installed
from writing_coach import cost_env
from writing_coach.ai import platform
from writing_coach.ai.base import AIResult, normalized_usage, reported_completion_tokens, sanitize_telemetry
from writing_coach.ai.pricing import (
    PRICING_CATALOG_VERSION,
    estimate_audio_cost,
    estimate_token_cost,
    resolve_token_pricing,
)
from writing_coach.ai.providers import build_providers
from writing_coach.media_spend import KIND_AI, KIND_ASR, SpendLedger

BASE = {"capability": "learner_dictionary", "outcome": "success", "provider": "gemini", "model": "gemini-3.5-flash-lite"}


# ---- 1. the environment label ------------------------------------------------------------------------------------

def test_an_explicit_label_wins_and_is_normalised():
    assert cost_env.label({"ORENA_ENV_LABEL": " Staging-8000 ", "PUBLIC_BASE_URL": "http://127.0.0.1:8021"}) == "staging-8000"


def test_the_label_is_the_host_and_port_of_the_public_address_when_none_is_set():
    assert cost_env.label({"PUBLIC_BASE_URL": "http://127.0.0.1:8021"}) == "127.0.0.1:8021"
    assert cost_env.label({"PUBLIC_BASE_URL": "https://App.Orena.Example/"}) == "app.orena.example"


def test_the_label_falls_back_to_the_app_environment_and_never_to_nothing():
    assert cost_env.label({"APP_ENV": "development"}) == "development"
    assert cost_env.label({}) == "unknown"


def test_an_unusable_label_is_never_stored_as_typed():
    assert cost_env.label({"ORENA_ENV_LABEL": "x y; drop table", "PUBLIC_BASE_URL": "http://127.0.0.1:8011"}) == "127.0.0.1:8011"
    assert cost_env.label({"ORENA_ENV_LABEL": "a" * 80}) == "unknown"


# ---- 2. the tag travels with every operation event ---------------------------------------------------------------

def test_telemetry_keeps_a_well_formed_environment_and_drops_anything_else():
    assert sanitize_telemetry({**BASE, "environment": "127.0.0.1:8021"})["environment"] == "127.0.0.1:8021"
    assert "environment" not in sanitize_telemetry({**BASE, "environment": "has spaces"})
    assert "environment" not in sanitize_telemetry({**BASE, "environment": ["x"]})
    assert "environment" not in sanitize_telemetry(BASE)


def test_every_persisted_operation_is_tagged_with_this_environment(monkeypatch):
    seen: list[dict] = []

    class Repository:
        def record_ai_operation(self, telemetry):
            seen.append(telemetry)

    monkeypatch.setattr(platform, "_platform_repository", Repository())
    monkeypatch.setenv("ORENA_ENV_LABEL", "sandbox-8011")
    with installed():
        platform._persist_operation_telemetry(dict(BASE))
    assert seen[0]["environment"] == "sandbox-8011"


def test_the_control_plane_probe_rows_are_tagged_too(monkeypatch):
    from writing_coach.ai.control_plane import AIControlPlane

    seen: list[dict] = []

    class Repository:
        def record_ai_operation(self, telemetry):
            seen.append(telemetry)

    monkeypatch.setenv("ORENA_ENV_LABEL", "probe-env")
    AIControlPlane(Repository())._record_operation(dict(BASE))
    assert seen[0]["environment"] == "probe-env"


def test_a_media_ledger_event_carries_the_environment(tmp_path):
    with installed():
        spend = SpendLedger(tmp_path / "spend.json", env={"ORENA_ENV_LABEL": "media-8021"})
        spend.record(KIND_ASR, 0.01, batch_id="b", provider="groq")
        spend.record(KIND_AI, 0.02, batch_id="b", provider="groq")
        spend.reserve_request(10, media_id="m", provider="supadata")
        events = json.loads((tmp_path / "spend.json").read_text(encoding="utf-8"))["events"]
        totals = spend.totals(30)
    assert [event["environment"] for event in events] == ["media-8021"] * 3
    assert totals["by_environment"] == [{"environment": "media-8021", "events": 3, "usd": 0.03}]


def test_a_report_names_this_environment_and_every_environment_that_wrote():
    rows = [{"environment": None, "calls": 5, "usd": 0.5}, {"environment": "a:1", "calls": 2, "usd": 0.25}]
    merged = platform.environment_report(rows, current="a:1")
    assert merged["current"] == "a:1"
    assert merged["by_environment"] == [
        {"environment": None, "calls": 5, "usd": 0.5, "current": False},
        {"environment": "a:1", "calls": 2, "usd": 0.25, "current": True}]


def test_the_archive_store_reports_no_environments():
    from writing_coach.persistence.platform_repository import SQLitePlatformRepository

    assert SQLitePlatformRepository.ai_cost_environments(object(), None) == []


# ---- 3. thinking tokens ------------------------------------------------------------------------------------------

def test_a_total_larger_than_prompt_plus_completion_is_thinking_billed_at_the_output_rate():
    usage = {"prompt_tokens": 1000, "completion_tokens": 40, "total_tokens": 1540}
    assert reported_completion_tokens(usage) == 540
    cost = estimate_token_cost("gemini", "gemini-3.5-flash-lite", {**usage, "completion_tokens": 540})
    assert cost["amount"] == round((1000 * 0.30 + 540 * 2.50) / 1_000_000, 8)


def test_a_completion_that_already_holds_the_thinking_is_not_counted_twice():
    assert reported_completion_tokens({"prompt_tokens": 1000, "completion_tokens": 540, "total_tokens": 1540}) == 540
    assert reported_completion_tokens({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": None}) == 5
    assert reported_completion_tokens({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 3}) == 5


def test_a_missing_completion_stays_unknown_never_zero():
    assert reported_completion_tokens({"prompt_tokens": 10, "completion_tokens": None, "total_tokens": 99}) is None
    assert reported_completion_tokens(None) is None


def _provider(monkeypatch, envelope: dict[str, Any]):
    provider = build_providers({"gemini": {"api_key": "synthetic-test-key"}})["gemini"]
    monkeypatch.setattr(provider, "_post_chat", lambda body, timeout=None: envelope)
    return provider


@pytest.mark.parametrize("method", ["generate_json", "generate_json_once"])
def test_the_adapter_hands_up_the_thinking_tokens_with_the_completion(monkeypatch, method):
    envelope = {"choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 420}}
    result = getattr(_provider(monkeypatch, envelope), method)(
        messages=[{"role": "user", "content": "x"}], schema={"type": "object"}, model="gemini-3.5-flash-lite",
        max_output_tokens=40, temperature=0.0)
    assert (result.runtime["prompt_tokens"], result.runtime["completion_tokens"]) == (100, 320)
    assert normalized_usage(result.runtime)["completion_tokens"] == 320


def test_a_stream_hands_up_the_thinking_tokens_with_the_completion(monkeypatch):
    chunks = [{"choices": [{"index": 0, "delta": {"content": "hi"}, "finish_reason": "stop"}]},
              {"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 420}}]

    class Response:
        status_code = 200

        def iter_lines(self):
            for chunk in chunks:
                yield ("data: " + json.dumps(chunk)).encode()
            yield b"data: [DONE]"

        def close(self):
            pass

    provider = build_providers({"gemini": {"api_key": "synthetic-test-key"}})["gemini"]
    events = list(provider._read_chat_stream(Response(), lambda: False))
    finished = events[-1]
    assert (finished.prompt_tokens, finished.completion_tokens) == (100, 320)


# ---- 4. prices -----------------------------------------------------------------------------------------------------

def test_gemini_3_1_flash_lite_is_priced_so_it_is_no_longer_an_unpriced_call():
    pricing = resolve_token_pricing("gemini", "gemini-3.1-flash-lite")
    assert pricing is not None and pricing.list_rates == (0.25, 1.50)
    cost = estimate_token_cost("gemini", "gemini-3.1-flash-lite", {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000})
    assert cost["state"] == "estimated" and cost["amount"] == 1.75


def test_the_catalogue_version_moved_with_the_prices():
    assert PRICING_CATALOG_VERSION >= "2026-10-17.v9"


def test_azure_neural_tts_is_the_published_fifteen_dollars_per_million_characters():
    from writing_coach.word_audio_azure import PER_MILLION_CHARACTERS

    assert PER_MILLION_CHARACTERS == 15.0


def test_the_gemini_live_rate_is_never_below_the_published_audio_floor():
    """Audio in USD 0.005 + audio out USD 0.018 a minute (3.8 Live, ai.google.dev pricing, read 2026-10-17) is
    USD 1.38 an hour with both sides streaming; the wall-clock rate is the ceiling that also covers the text and
    context tokens the server cannot see."""
    cost = estimate_audio_cost("gemini", "gemini-3.8-live", 3600.0)
    assert cost["state"] == "estimated" and cost["amount"] >= 1.38


# ---- 5. the admin connection test is a real, billed call ------------------------------------------------------------

def test_the_admin_selection_test_records_its_tokens_as_an_operator_test(monkeypatch):
    seen: list[dict] = []

    class Repository:
        def record_ai_operation(self, telemetry):
            seen.append(telemetry)

    class Item:
        id = "gemini"
        name = "Gemini"
        configured = True
        default_model = "gemini-3.5-flash-lite"

        def list_models(self):
            return ["gemini-3.5-flash-lite"]

        def generate_json(self, **kwargs):
            return AIResult(data={"ok": True}, provider="gemini", model=kwargs["model"],
                            runtime={"prompt_tokens": 60, "completion_tokens": 8, "total_tokens": 68})

    class Admin(dict):
        pass

    monkeypatch.setattr(platform, "_platform_repository", Repository())
    monkeypatch.setattr(platform, "providers", lambda: {"gemini": Item()})
    monkeypatch.setattr(platform, "_require_admin", lambda request: {"google_sub": "a"})
    monkeypatch.setattr(platform, "_record_admin_event", lambda *a, **k: None)
    with installed():
        out = platform.admin_ai_test(platform.AIConfigIn(provider="gemini", model="gemini-3.5-flash-lite"), object())
    assert out["ok"] is True
    row = seen[0]
    assert (row["capability"], row["origin"], row["provider"], row["outcome"]) == (
        "ai_connection_test", "operator_test", "gemini", "success")
    assert row["usage"]["prompt_tokens"] == 60 and row["cost"]["state"] == "estimated"
