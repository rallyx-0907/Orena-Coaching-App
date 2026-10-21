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

What the learner's text-AI total counts (review of #487):
- **a paid call without a catalogue price** (`unpriced`: Ollama Cloud, which publishes no per-token price - a recorded
  gap - or any operator-added model) counts a conservative per-call estimate, `ai.learner_cost.unpriced_call_usd`
  (default USD 0.0008: above the list price of a typical 2,000-in / 500-out call on the gpt-oss-120b class, about USD
  0.0006), so its paid spend stays capped. Each UTC day with such calls raises one monitor alert ("unpriced provider in
  use"). At the default a Free learner (USD 0.02) makes 25 of them before the economy model and 37 before the hard
  ceiling; 20 never throttle (the fixture in tests/test_learner_cost_cap.py).
- **no local model** (`ollama`, our own machine: cost 0) and no free-tier provider (`cost.free_tier.*`): these count 0.
- **no feature with its own plan meter**: `agent_voice` (voice minutes, D-249), `pronunciation_evaluator`
  (pronunciation minutes), `speech_asr` (the daily recognition brake), `word_tts` (the `audio.tts` meter and its own
  cap). Those are limited per learner by their meters; this cap is for text AI. (They stay in the system monitor.)
- **calls in flight**: before each paid call `admit_paid` reads the state and reserves the call's estimate under that
  learner's lock, atomically, so concurrent calls of one learner cannot all pass. A released estimate keeps counting
  until a ledger read newer than its release (settle, then drop). Reservations are per process: across workers the
  overshoot is bounded by workers x one learner's concurrent calls x one call's estimate. Cost rows the per-account
  recorder could not write yet (ai/account_costs.py keeps and retries them) are added from its pending queue.

System costs: work with no signed-in account (background jobs, the media pipeline) and an administrator's own runs
(origin `operator_test`, `configuration`, never recorded per account) are system costs. They reach the monitor only,
never a learner cap.

Faults never block everyone either: a ledger that cannot be read degrades the learner to the economy model (bounded
cost, still answered) instead of refusing; a plan that cannot be read uses the Free cap. A store with no per-account
ledger at all (the SQLite archive) has no learner cap, and a public runtime refuses to start without one
(`ledger_wired`, core/published_promises.py). The Intelligence lane calls `learner_cost_state` from the agent turn (and
picks `economy`), as the router does here.
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
CACHE_SECONDS = 5.0             # the ledger read is cached; calls in flight are counted apart (`reserve`)
# Never counted in a learner's text-AI total (see the module docstring).
LOCAL_PROVIDERS: tuple[str, ...] = ("ollama",)
METERED_FEATURES: tuple[str, ...] = ("agent_voice", "pronunciation_evaluator", "speech_asr", "word_tts")
ESTIMATE_INPUT_TOKENS = 2_000   # a reservation's input when the caller gives none
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
        _inflight.clear()
        _settling.clear()
        _unpriced_alerted.clear()


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


def uncounted_providers() -> tuple[str, ...]:
    """Providers that cost Orena nothing: local models and free-tier accounts."""
    return (*LOCAL_PROVIDERS, *_free_tier_providers())


_unpriced_alerted: set[str] = set()
UNPRICED_POLICY = "ai.learner_cost.unpriced_call_usd"


def unpriced_call_usd() -> float:
    """What one PAID call without a catalogue price counts in a learner's cap (re-review of #487): a conservative
    per-call estimate, never 0, so an unpriced paid provider (Ollama Cloud's credits, an operator-added model) cannot leave a
    learner's paid spend uncapped. Local and free-tier calls are excluded before this, so they stay at 0."""
    return float(policies.value(UNPRICED_POLICY))


def note_unpriced(count: int, moment: datetime | None = None) -> None:
    """A learner total held paid calls without a price: counted at `unpriced_call_usd` each, one monitor alert a UTC day."""
    if not count:
        return
    day = (moment or _now()).date().isoformat()
    with _lock:
        if day in _unpriced_alerted:
            return
        _unpriced_alerted.clear()
        _unpriced_alerted.add(day)
    _log.error("ALERT unpriced provider in use: %d paid AI call(s) in a learner's cost today have no catalogue price; "
               "each counts the estimate %s USD in the learner's cap. Add the model's price to ai/pricing.py.",
               int(count), unpriced_call_usd())


# Reservations are held in this process. With several workers a learner's calls in flight on other workers are not seen
# until their rows reach the ledger: the overshoot is bounded by (workers x one learner's concurrent calls x one call's
# estimate) - a few cents at most - and the ledger, read fresh every CACHE_SECONDS, catches up (re-review of #487: the
# simple, documented option, chosen over a shared reservation store, which would be a new persistence decision).
_inflight: dict[str, float] = {}
# Released reservations whose ledger row may not be visible yet: (released at, usd). Each counts until a ledger read that
# started after it was released; then the row itself is counted (settle first, then the estimate is dropped).
_settling: dict[str, list[tuple[float, float]]] = {}
_STRIPES = 64
_account_locks = [threading.Lock() for _ in range(_STRIPES)]


def account_lock(account: str) -> threading.Lock:
    """One learner's lock (striped): the state check and the reservation of a paid call happen under it together."""
    return _account_locks[hash(account) % _STRIPES]


class _Reservation:
    def __init__(self, account: str | None, usd: float) -> None:
        self.account, self.usd, self._open = account, usd, account is not None and usd > 0

    def release(self) -> None:
        if not self._open:
            return
        self._open = False
        with _lock:
            left = _inflight.get(self.account, 0.0) - self.usd
            if left > 1e-12:
                _inflight[self.account] = left
            else:
                _inflight.pop(self.account, None)
            # Settle, then invalidate: the estimate keeps counting until a ledger read newer than this moment.
            _settling.setdefault(self.account, []).append((_monotonic(), self.usd))

    def __enter__(self) -> _Reservation:
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


def estimate_call_usd(provider: str, model: str, *, input_tokens: int | None = None,
                      output_tokens: int | None = None) -> float:
    """A paid call's cost before it is sent: list price, or `unpriced_call_usd` for a paid model with no catalogue price;
    0 for a local or free-tier one."""
    if provider_tier(provider, model) != "paid" or provider in uncounted_providers():
        return 0.0
    from writing_coach.ai.pricing import list_rate

    rates = list_rate(provider, model)
    if rates is None:
        return unpriced_call_usd()
    tokens_in = ESTIMATE_INPUT_TOKENS if input_tokens is None else max(0, int(input_tokens))
    tokens_out = 500 if output_tokens is None else max(0, int(output_tokens))
    return (tokens_in * rates[0] + tokens_out * rates[1]) / 1_000_000


def reserve(account: str | None, usd: float) -> _Reservation:
    """Hold `usd` against `account` while a paid call is in flight; release it when the call returns."""
    held = _Reservation(account if account not in (None, *_NOT_AN_ACCOUNT) else None, float(usd or 0.0))
    if held._open:
        with _lock:
            _inflight[held.account] = _inflight.get(held.account, 0.0) + held.usd
    return held


def admit_paid(account: str | None, target: ProviderTarget, usd: float, *, single_model: bool = False) -> _Reservation:
    """The atomic step before one paid call: under the learner's lock, read the state (ledger + calls in flight) and, unless
    the hard ceiling is reached, reserve the call's estimate. At the hard ceiling: `LearnerCostCapReached`. A degraded
    learner may still use the economy model; `single_model` (one selected model with no economy rung to give way to) is
    refused only at the hard ceiling. A local or free rung, or no account, needs no admission."""
    if account in (None, *_NOT_AN_ACCOUNT) or provider_tier(target.provider, target.model) != "paid" or usd <= 0:
        return _Reservation(None, 0.0)
    with account_lock(account):
        state = learner_cost_state(account)
        economy = state.economy
        is_economy = economy is not None and (target.provider, target.model) == (economy.provider, economy.model)
        degraded_off = state.state == DEGRADE and not is_economy and not state.fault and not single_model
        if state.state == REFUSE or degraded_off:
            raise LearnerCostCapReached(state)
        return reserve(account, usd)


def in_flight_usd(account: str) -> float:
    with _lock:
        return _inflight.get(account, 0.0)


def _pending_usd(account: str, since: datetime) -> float:
    from writing_coach.ai import account_costs

    try:
        return float(account_costs.pending_usd(account, since))
    except Exception:  # noqa: BLE001 - the queue is a best effort on top of the ledger
        return 0.0


def _settling_usd(account: str, read_at: float) -> float:
    """Released estimates the ledger read taken at `read_at` cannot include yet; older ones are dropped (settled)."""
    with _lock:
        held = [item for item in _settling.get(account, []) if item[0] >= read_at]
        if held:
            _settling[account] = held
        else:
            _settling.pop(account, None)
        return sum(usd for _at, usd in held)


def _spent(account: str, since: datetime) -> float:
    now = _monotonic()
    with _lock:
        held = _cache.get(account)
        fresh = held is not None and now - held[0] < CACHE_SECONDS
    if fresh:
        read_at, ledger = held
    else:
        reader = _read
        if reader is None:
            raise RuntimeError("no per-account AI ledger")
        read_at = now
        usd, unpriced = reader(account, since, exclude_providers=uncounted_providers(),
                               exclude_features=METERED_FEATURES)
        note_unpriced(int(unpriced))
        ledger = float(usd) + int(unpriced) * unpriced_call_usd()
        with _lock:
            _cache[account] = (read_at, ledger)
            _cache.move_to_end(account)
            while len(_cache) > MAX_CACHED:
                _cache.popitem(last=False)
    return ledger + in_flight_usd(account) + _settling_usd(account, read_at) + _pending_usd(account, since)


def ledger_wired() -> bool:
    """Whether the per-account ledger is installed and readable (a public runtime refuses to start otherwise)."""
    reader = _read
    if reader is None:
        return False
    try:
        reader("__startup_probe__", _midnight(_now()), exclude_providers=(), exclude_features=())
    except Exception:  # noqa: BLE001 - not wired: no table, no PostgreSQL, the archive store
        _log.error("per-learner AI cost ledger is not readable", exc_info=True)
        return False
    return True


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
