"""Each learner's own daily AI cost cap, by plan (D-251; D-248 point 2's hidden per-learner ceiling).

Owner, 2026-10-21: "không có trần chung cho app, chỉ có trần cho từng người dùng theo gói". There is no app-wide cap that
pauses AI for every learner; a limit applies to one learner, by the learner's plan. One heavy learner never slows or
blocks another.

    learner_cost_state(user_key=None) -> LearnerCostState   (.state: "ok" | "degrade" | "refuse"; .economy)

The day's (UTC) cost of one account is read from the per-account AI ledger that already exists (`ai_cost_records`,
AC-2: account, feature, provider, model, estimated USD), so this adds no table. A provider whose free-tier flag is on
(`cost.free_tier.<provider>`, D-219) costs Orena nothing and is not counted.

- below the plan's cap: `ok`;
- at the cap: `degrade` - a paid call goes to the economy model (`ai.learner_cost.economy_model`) instead of the
  capability's own paid rungs; free and local rungs run as before;
- at the hard ceiling (the cap x `ai.learner_cost.hard_ratio`): `refuse` - no paid call; a request with nothing but paid
  rungs is answered 429 `quota_exhausted` (feature `ai.daily_cost`, window `day`, `resets_at` the next UTC midnight; a
  Free learner also gets the way to the plans). The amounts stay hidden (D-248): the refusal names no figure.

The caps are policies (Admin > Policies & limits, group "spend"). Free is USD 0.02 a day. Plus and Pro are D-248's 60% of
the plan's monthly price spread over 30 days at `ai.learner_cost.vnd_per_usd` (default 26,000 VND a dollar): Plus
79.000 d -> about USD 0.061 a day, Pro 159.000 d -> about USD 0.122 a day, unless an administrator stores a USD figure.

Faults never block everyone either: a ledger that cannot be read degrades the learner to the economy model (bounded
cost, still answered) instead of refusing; a plan that cannot be read uses the Free cap. A request with no signed-in
account (a background job, a bare development server) has no learner cap. The Intelligence lane calls
`learner_cost_state` from the agent turn (and picks `economy`), as the router does here.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from writing_coach import policies
from writing_coach.ai.base import AIProviderUnavailable
from writing_coach.ai.routing import ProviderTarget, provider_tier

_log = logging.getLogger(__name__)

OK, DEGRADE, REFUSE = "ok", "degrade", "refuse"
FEATURE = "ai.daily_cost"
REASON = "learner_cost_cap"

PLANS: tuple[str, ...] = ("free", "plus", "pro")
CAP_POLICY = "ai.learner_cost.daily_usd_{plan}"
CAP_POLICIES: dict[str, str] = {"free": "ai.learner_cost.daily_usd_free", "plus": "ai.learner_cost.daily_usd_plus",
                                "pro": "ai.learner_cost.daily_usd_pro"}
RATE_POLICY = "ai.learner_cost.vnd_per_usd"
SHARE_POLICY = "ai.learner_cost.revenue_share"
HARD_POLICY = "ai.learner_cost.hard_ratio"
ECONOMY_POLICY = "ai.learner_cost.economy_model"
# D-248 point 1: the monthly price of each paid plan, in VND. The Free plan has no price; its cap is its own policy.
PLAN_MONTHLY_VND: dict[str, int] = {"plus": 79_000, "pro": 159_000}
DAYS_PER_MONTH = 30
DEFAULT_VND_PER_USD = 26_000
DEFAULT_REVENUE_SHARE = 0.6
DEFAULT_FREE_USD = 0.02
UNPRICED_ALLOWANCE_USD = 0.01   # a call recorded without a price counts this much, never zero (as the system monitor)
CACHE_SECONDS = 5.0             # a soft cap: calls in flight inside one window may overshoot it a little
MAX_CACHED = 4096
# Request contexts that are not a signed-in account (ai/account_costs.py): no learner cap.
_NOT_AN_ACCOUNT = frozenset({"", "legacy", "local-admin", "local"})


def derived_daily_usd(plan: str, *, vnd_per_usd: float = DEFAULT_VND_PER_USD,
                      share: float = DEFAULT_REVENUE_SHARE) -> float:
    """D-248's ceiling for a paid plan: `share` of its monthly price, in USD, spread over 30 days."""
    return round(PLAN_MONTHLY_VND[plan] * share / vnd_per_usd / DAYS_PER_MONTH, 4)


DEFAULT_DAILY_USD: dict[str, float] = {"free": DEFAULT_FREE_USD,
                                       **{plan: derived_daily_usd(plan) for plan in PLAN_MONTHLY_VND}}


class LearnerCostCapReached(AIProviderUnavailable):
    """No paid call for this learner today: the plan's hard ceiling is reached. Not a provider failure."""

    code = REASON
    failure_class = "not_counted"   # ai/health_signal.py: never counted as a provider outage

    def __init__(self, state: LearnerCostState) -> None:
        super().__init__("You have used today's AI allowance for your plan.")
        self.state = state

    def facts(self) -> dict[str, Any]:
        facts: dict[str, Any] = {"feature": FEATURE, "window": "day", "resets_at": self.state.resets_at,
                                 "plan": self.state.plan}
        if self.state.plan in (None, "free"):
            from writing_coach.product.quota import UPGRADE_HREF

            facts["upgrade"] = UPGRADE_HREF
        return facts


@dataclass(frozen=True)
class LearnerCostState:
    state: str                      # ok | degrade | refuse
    account: str | None = None
    plan: str | None = None
    spent_usd: float | None = None
    cap_usd: float | None = None
    hard_usd: float | None = None
    resets_at: str | None = None
    economy: ProviderTarget | None = None   # the model a degraded paid call uses; None: free and local rungs only
    fault: bool = False


_read: Callable[..., tuple[float, int]] | None = None
_lock = threading.Lock()
_cache: OrderedDict[str, tuple[float, float]] = OrderedDict()   # account -> (monotonic, spent)
_monotonic: Callable[[], float] = time.monotonic
_now: Callable[[], datetime] = lambda: datetime.now(UTC)


def configure(read: Callable[..., tuple[float, int]] | None, *, monotonic: Callable[[], float] | None = None,
              now: Callable[[], datetime] | None = None) -> None:
    """app.py: `read(user_key, since, exclude_providers=...)` -> (USD, calls without a price) from `ai_cost_records`.
    None (tests, a bare server): no learner cap is applied."""
    global _read, _monotonic, _now
    with _lock:
        _read = read
        _cache.clear()
    _monotonic = monotonic or time.monotonic
    _now = now or (lambda: datetime.now(UTC))


def reset() -> None:
    with _lock:
        _cache.clear()


def current_account() -> str | None:
    """The signed-in account of the request being served, or None (background work, a local development key)."""
    from writing_coach.core.request_context import current_user_key

    key = str(current_user_key() or "")
    return None if key in _NOT_AN_ACCOUNT else key


def daily_cap_usd(plan: str | None) -> float:
    """The plan's daily cap now. An unknown plan (a legacy id) has the Free cap. Plus and Pro follow D-248's formula at
    the policy rate and share until an administrator stores a USD figure (or the environment pins one)."""
    chosen = plan if plan in PLANS else "free"
    key = CAP_POLICIES[chosen]
    if chosen in PLAN_MONTHLY_VND and not policies.has_admin_value(key) and not policies.is_pinned(key):
        return derived_daily_usd(chosen, vnd_per_usd=float(policies.value(RATE_POLICY)),
                                 share=float(policies.value(SHARE_POLICY)))
    return float(policies.value(key))


def economy_target() -> ProviderTarget | None:
    choice = str(policies.value(ECONOMY_POLICY) or "none")
    if "/" not in choice:
        return None
    provider, model = choice.split("/", 1)
    return ProviderTarget(provider, model)


def _plan_of(account: str) -> tuple[str | None, bool]:
    """(plan id, fault). None with no plan system on this server (no cap applies)."""
    from writing_coach.product import quota

    plan_for = quota.runtime().plan_for
    if plan_for is None:
        return None, False
    try:
        return str(plan_for(account, strict=True).id), False
    except Exception:  # noqa: BLE001 - an unreadable plan is the lowest cap, never "no cap" and never everyone refused
        _log.warning("learner cost cap: plan unreadable; the Free cap applies", exc_info=True)
        return "free", True


def _midnight(moment: datetime) -> datetime:
    return datetime(moment.year, moment.month, moment.day, tzinfo=UTC)


def _free_tier_providers() -> tuple[str, ...]:
    from writing_coach import cost_tier

    return tuple(provider for provider in cost_tier.PROVIDERS if cost_tier.is_free_tier(provider))


def _spent(account: str, since: datetime) -> float:
    now = _monotonic()
    with _lock:
        held = _cache.get(account)
        if held is not None and now - held[0] < CACHE_SECONDS:
            return held[1]
    reader = _read
    if reader is None:
        raise RuntimeError("no per-account AI ledger")
    usd, unpriced = reader(account, since, exclude_providers=_free_tier_providers())
    spent = float(usd) + int(unpriced) * UNPRICED_ALLOWANCE_USD
    with _lock:
        _cache[account] = (now, spent)
        _cache.move_to_end(account)
        while len(_cache) > MAX_CACHED:
            _cache.popitem(last=False)
    return spent


def learner_cost_state(user_key: str | None = None) -> LearnerCostState:
    """Where this learner stands against the plan's daily cost cap now. `user_key` None: the request's own account."""
    account = user_key if user_key is not None else current_account()
    if account is None or account in _NOT_AN_ACCOUNT or _read is None:
        return LearnerCostState(OK)
    plan, plan_fault = _plan_of(account)
    if plan is None:
        return LearnerCostState(OK, account=account)
    moment = _now()
    midnight = _midnight(moment)
    resets_at = (midnight + timedelta(days=1)).isoformat().replace("+00:00", "Z")
    cap = daily_cap_usd(plan)
    hard = round(cap * float(policies.value(HARD_POLICY)), 6)
    economy = economy_target()
    try:
        spent = _spent(account, midnight)
    except NotImplementedError:   # a store with no per-account ledger at all (the SQLite archive, tests): no learner cap
        return LearnerCostState(OK, account=account, plan=plan)
    except Exception:  # noqa: BLE001 - one learner's unreadable ledger degrades that learner, it blocks nobody
        _log.warning("learner cost cap: per-account ledger unreadable; the economy model answers", exc_info=True)
        return LearnerCostState(DEGRADE, account, plan, None, cap, hard, resets_at, economy, fault=True)
    state = REFUSE if spent >= hard else DEGRADE if spent >= cap else OK
    return LearnerCostState(state, account, plan, round(spent, 6), cap, hard, resets_at, economy, fault=plan_fault)


def admitted_chain(chain: Iterable[ProviderTarget], state: LearnerCostState) -> list[ProviderTarget]:
    """The rungs a learner in `state` may use. `ok`: all. `degrade`: the free and local rungs, then the economy model in
    place of every other paid rung. `refuse`: the free and local rungs only (zero-cost paths stay uncapped)."""
    rungs = list(chain)
    if state.state == OK:
        return rungs
    kept = [rung for rung in rungs if provider_tier(rung.provider, rung.model) != "paid"]
    if state.state == DEGRADE and state.economy is not None:
        economy = state.economy
        paid = [rung for rung in rungs if provider_tier(rung.provider, rung.model) == "paid"]
        if paid:
            same = next((rung for rung in paid if (rung.provider, rung.model) == (economy.provider, economy.model)), None)
            kept.append(same or ProviderTarget(economy.provider, economy.model, paid[0].timeout_seconds))
    return kept


def refusal_body(error: LearnerCostCapReached, now: datetime | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    """The 429 `quota_exhausted` body and headers for a learner at the hard ceiling."""
    from writing_coach.core.errors import error_detail

    facts = error.facts()
    headers: dict[str, str] = {}
    if facts.get("resets_at"):
        moment = now or datetime.now(UTC)
        wait = (datetime.fromisoformat(str(facts["resets_at"]).replace("Z", "+00:00")) - moment).total_seconds()
        headers["Retry-After"] = str(max(1, int(wait)))
    return {"detail": error_detail("quota_exhausted", "You have used today's AI allowance for your plan.",
                                   retryable=False, context=facts)}, headers


def configured_problems(policy: Callable[[str], Any] | None = None) -> list[str]:
    """The plans without a usable per-learner cap (production refuses to start with any, core/published_promises.py).
    `policy(key)` is the reader the start check was given; a reader that cannot answer for a key (it knows only some
    policies, or raises) leaves that key to the registry (`policies.value`, which never raises)."""

    def read(key: str) -> Any:
        if policy is None:
            return policies.value(key)
        try:
            return policy(key)
        except Exception:  # noqa: BLE001 - the registry answers: an absent store is the defaults, never "no cap"
            return policies.value(key)

    problems = []
    for plan in PLANS:
        try:
            value = daily_cap_usd(plan) if policy is None else read(CAP_POLICIES[plan])
            ok = value is not None and float(value) > 0
        except Exception:  # noqa: BLE001 - unreadable is not configured
            ok = False
        if not ok:
            problems.append(plan)
    try:
        if not float(read(HARD_POLICY)) >= 1:
            problems.append("hard_ratio")
    except Exception:  # noqa: BLE001
        problems.append("hard_ratio")
    return problems
