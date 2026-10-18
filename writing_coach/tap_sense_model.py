"""The model step of a word tap's sense choice (D-228, PROPOSED), asked only when the zero-cost rules tie.

    choose_sense(word, sentence, senses, source, target, shared=...) -> int | None

The answer is the index of one of the stored `senses`, or ``None`` (the tap then keeps its neutral sense). It is
``None`` for every refusal and failure: the capability is not enabled, the account is over its brake, no model is
configured for this content, the daily cap of the paid models is reached, every model fails or answers badly. Nothing
here raises to the caller and nothing here can block a sheet.

Which content, which models (owner decision 2026-10-18, narrowed by the coordinator the same day, D-228):

* Only the sentence of SHARED published content (the server verified the article) is ever sent. A learner's own
  sentence (a personal import, their writing, anything unverified or without a `content_id`) is learner text and goes to
  no AI, free or paid, until the owner says otherwise: the neutral sense stays.
* Models, in order: configured models on a free tier, in the operator's order (provider order, then each provider's
  model list): a provider whose `cost.free_tier.<provider>` flag is on (D-219), or a zero-rate catalogue model. Then the
  2 cheapest priced paid models by the catalogue's list price. A rung that errors, is unavailable, is rate limited or
  answers badly hands over to the next.
* Every flagged or paid rung is admitted by the daily cap (`word_sense_choice.daily_spend_cap_usd`, `ai/spend_gate`,
  list price, shared AI ledger) and the funding gate (under FUNDING_ENFORCEMENT=enforce an unfunded learner skips them).
  Cached by (word, sentence hash, support language, scope, senses).
"""

from __future__ import annotations

import logging

from writing_coach import cost_tier
from writing_coach.ai import platform
from writing_coach.ai.base import AICapabilityConfigInvalid, AICapabilityError, AIProviderError
from writing_coach.ai.capabilities import AIOperation
from writing_coach.ai.pricing import is_free_model, list_rate
from writing_coach.ai.providers import check_model_allowed, get_provider_definition
from writing_coach.ai.router import router as router_module
from writing_coach.ai.router import tap as tap_router
from writing_coach.ai.router.contract import RouterInputInvalid
from writing_coach.ai.router.contracts.word_sense_choice import MAX_SENSE_CHARS
from writing_coach.ai.routing import ProviderTarget
from writing_coach.billing.funding_context import FundingRequired
from writing_coach.core.request_context import current_user_key

_log = logging.getLogger("orena.lookup")

CAPABILITY = "word_sense_choice"
MAX_FREE_RUNGS = 3
MAX_PAID_RUNGS = 2
# The shape of one call, for ordering paid models by price: a short sentence and a few senses in, one small object out.
TYPICAL_INPUT_TOKENS = 220
TYPICAL_OUTPUT_TOKENS = 8


def estimated_call_usd(provider: str, model: str) -> float | None:
    """The list-price cost of one typical call, or None when the model has no real price in the catalogue."""

    rates = list_rate(provider, model)
    if rates is None:
        return None
    return (TYPICAL_INPUT_TOKENS * rates[0] + TYPICAL_OUTPUT_TOKENS * rates[1]) / 1_000_000


def _configured_models() -> list[tuple[str, str]]:
    """(provider, model) of every cloud text model the operator has configured, in provider and list order."""

    found: list[tuple[str, str]] = []
    for provider_id, item in platform.providers().items():
        definition = get_provider_definition(provider_id)
        if definition is None or definition.kind == "local" or not getattr(item, "configured", False):
            continue
        if AIOperation.STRUCTURED_TEXT_GENERATION not in definition.supported_operations:
            continue
        try:
            try:
                models = item.list_models(offline=True)
            except TypeError:
                models = item.list_models()
        except Exception:  # noqa: BLE001 - one provider's model list failing leaves the others usable
            continue
        for model in models:
            name = str(model).strip()
            try:
                check_model_allowed(provider_id, name)  # e.g. OpenRouter: pinned ':free' ids only
            except AICapabilityConfigInvalid:
                continue
            if name:
                found.append((provider_id, name))
    return found


def is_free_tier_model(provider: str, model: str) -> bool:
    """A model the account gets free: a zero-rate catalogue model, or any model of a provider flagged as on a free plan."""

    return is_free_model(provider, model) or cost_tier.is_free_tier(provider)


def build_pool(*, shared: bool) -> list[ProviderTarget]:
    """The ordered rungs for one request: free-tier models first, then the 2 cheapest priced paid ones.

    Only shared (server-verified published) content has a pool. A learner's own sentence is learner text (D-104, D-195,
    D-224) and is sent to no AI at all until the owner decides otherwise (D-228): its pool is empty."""

    if not shared:
        return []
    free: list[ProviderTarget] = []
    paid: list[tuple[float, int, ProviderTarget]] = []
    for index, (provider, model) in enumerate(_configured_models()):
        if is_free_tier_model(provider, model):
            if len(free) < MAX_FREE_RUNGS:
                free.append(ProviderTarget(provider, model))
            continue
        cost = estimated_call_usd(provider, model)
        if cost is None:
            continue  # no real price in the catalogue: a cap cannot count it
        paid.append((cost, index, ProviderTarget(provider, model)))
    paid.sort(key=lambda row: (row[0], row[1]))
    return free + [target for _cost, _index, target in paid[:MAX_PAID_RUNGS]]


def enabled() -> bool:
    """Whether the capability is saved and enabled (the configuration the router reads, briefly held)."""

    try:
        router_module.load_config(CAPABILITY)
    except AICapabilityError:
        return False
    except Exception:  # noqa: BLE001 - an unreadable configuration is "off"
        return False
    return True


def _scope(shared: bool) -> str:
    return "shared" if shared else "private"


def choose_sense(word: str, sentence: str, senses: list[str], source: str, target: str, *, shared: bool) -> int | None:
    """The index of the sense the sentence means, or None (keep the neutral sense). Never raises."""

    if not shared:
        return None  # a learner's own sentence reaches no AI (D-228)
    # Each sense is sent as at most the contract's limit; the index still maps to the full stored sense.
    sent = [text[:MAX_SENSE_CHARS].strip() for text in senses]
    raw = {
        "word": word, "sentence": sentence, "source_language": source, "target_language": target,
        "senses": sent, "cache_scope": _scope(shared),
    }
    try:
        held = router_module.peek(CAPABILITY, raw)  # also the "enabled?" check: a disabled capability serves nothing
        if held is not None:
            return held.output["choice"]
        if tap_router._braked(current_user_key()):
            return None
        pool = build_pool(shared=shared)
        if not pool:
            return None
        return router_module.route(CAPABILITY, raw, pool=pool).output["choice"]
    except (RouterInputInvalid, AICapabilityError, AIProviderError, FundingRequired):
        return None  # a quiet miss: not enabled, over a cap, unfunded, or every model failed
    except Exception as exc:  # noqa: BLE001 - a failing model step never blocks the sheet; the type only, never the text
        _log.warning("sense choice failed (%s)", type(exc).__name__)
        return None


def sense_choice_seam(word: str, sentence: str, senses: list[str], source: str, target: str, shared: bool) -> int | None:
    """`SenseChoiceSeam` for `ReadingLookupService` (D-228)."""

    return choose_sense(word, sentence, senses, source, target, shared=shared)
