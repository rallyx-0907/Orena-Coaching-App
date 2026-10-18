"""The model step of a word tap's sense choice (D-228, PROPOSED), asked only when the zero-cost rules tie.

    choose_sense(word, sentence, senses, source, target, shared=...) -> int | None

The answer is the index of one of the stored `senses`, or ``None`` (the tap then keeps its neutral sense). It is
``None`` for every refusal and failure: the capability is not enabled, the account is over its brake, no model is
configured for this content, the daily cap of the paid models is reached, every model fails or answers badly. Nothing
here raises to the caller and nothing here can block a sheet.

Which models, in which order (owner decision 2026-10-18):

1. Configured models on a free tier, in the operator's order (provider order, then each provider's model list): a
   provider whose `cost.free_tier.<provider>` flag is on (D-219), or a zero-rate catalogue model (`is_free_model`).
   Only for the sentence of SHARED published content. A free tier may log prompts, so the sentence of a learner's own
   content (a personal import, their own writing) is learner text (D-104, D-195, D-224) and never goes there.
2. Then the cheapest priced paid models among the configured ones, cheapest first by the catalogue's list price. For a
   learner's own content only models whose provider does not log prompts and, where a provider needs a per-model privacy
   review, that have it.

The router walks that list in order: a rung that errors, is unavailable, is rate limited or answers badly hands over to
the next. Every paid rung is admitted by the capability's daily spend cap (`word_sense_choice.daily_spend_cap_usd`,
`ai/spend_gate`, counted in the shared AI ledger like every other call) and the funding gate; the free rungs are not
capped. The answer is cached in the router by (word, sentence hash, support language, content scope, senses).
"""

from __future__ import annotations

import hashlib
import logging

from writing_coach import cost_tier
from writing_coach.ai import platform
from writing_coach.ai.base import AICapabilityConfigInvalid, AICapabilityError, AIProviderError
from writing_coach.ai.capabilities import AIOperation
from writing_coach.ai.pricing import is_free_model, list_rate, resolve_token_pricing
from writing_coach.ai.providers import check_model_allowed, get_provider_definition
from writing_coach.ai.router import router as router_module
from writing_coach.ai.router import tap as tap_router
from writing_coach.ai.router.contract import RouterInputInvalid
from writing_coach.ai.routing import ProviderTarget
from writing_coach.core.request_context import current_user_key
from writing_coach.reading_cache_scope import learner_scope

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


def _may_receive_private_sentence(provider: str, model: str) -> bool:
    """The learner-text rule (D-104, D-195): no free tier, no provider that may log prompts, a reviewed model where a
    provider requires a per-model review. Unpriced models are refused too: their cost cannot be capped."""

    definition = get_provider_definition(provider)
    if definition is None or definition.may_log_prompts or is_free_tier_model(provider, model):
        return False
    if definition.learner_text_models is not None and model not in definition.learner_text_models:
        return False
    return resolve_token_pricing(provider, model) is not None


def build_pool(*, shared: bool) -> list[ProviderTarget]:
    """The ordered rungs for one request: free-tier models first (shared content only), then the cheapest paid ones."""

    free: list[ProviderTarget] = []
    paid: list[tuple[float, int, ProviderTarget]] = []
    for index, (provider, model) in enumerate(_configured_models()):
        if is_free_tier_model(provider, model):
            if shared and len(free) < MAX_FREE_RUNGS:
                free.append(ProviderTarget(provider, model))
            continue
        cost = estimated_call_usd(provider, model)
        if cost is None:
            continue  # no real price in the catalogue: a cap cannot count it
        if not shared and not _may_receive_private_sentence(provider, model):
            continue
        paid.append((cost, index, ProviderTarget(provider, model)))
    paid.sort(key=lambda row: (row[0], row[1]))
    return free + [target for _cost, _index, target in paid[:MAX_PAID_RUNGS]]


def _scope(shared: bool) -> str:
    if shared:
        return "shared"
    namespace = learner_scope().namespace
    if namespace:
        return f"private:{namespace}"
    # No account incarnation can be read: the router's cache is in-process only, so a per-account key is still private.
    return "private:" + hashlib.sha256(str(current_user_key()).encode("utf-8")).hexdigest()[:16]


def choose_sense(word: str, sentence: str, senses: list[str], source: str, target: str, *, shared: bool) -> int | None:
    raw = {
        "word": word, "sentence": sentence, "source_language": source, "target_language": target,
        "senses": list(senses), "cache_scope": _scope(shared),
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
    except (RouterInputInvalid, AICapabilityError, AIProviderError):
        return None
    except Exception as exc:  # noqa: BLE001 - a failing model step never blocks the sheet; the type only, never the text
        _log.warning("sense choice failed (%s)", type(exc).__name__)
        return None


def sense_choice_seam(word: str, sentence: str, senses: list[str], source: str, target: str, shared: bool) -> int | None:
    """`SenseChoiceSeam` for `ReadingLookupService` (D-228)."""

    return choose_sense(word, sentence, senses, source, target, shared=shared)
