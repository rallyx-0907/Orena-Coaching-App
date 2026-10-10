"""The plan catalogue: Free, Plus and Pro (D-153), version 2 - the design's meters (D-160).

The defaults below are the design's three tiers (Orena.dc.html `BILL_PLANS`: names, monthly and yearly
prices in USD and VND, and the limits `lim: {msg, wr, pron, imp, lang}`). The design's Pricing frame is the
source of truth for which meters exist and their numbers (human, 2026-10-09):

    orena.message        per day     20 / 200 / 1000 messages   (voice: N seconds of voice = 1 message)
    writing.review       per month    2 /  10 /   50 reviews
    pronunciation.audio  per month    5 /  30 /  120 minutes    (stored in seconds)
    media.import         per month   15 / 120 /  600 minutes    (stored in seconds)
    languages.target     a count cap  1 /   2 /    2 languages  (no window)

What each meter is - its window, its unit and how many stored units make one displayed unit - is the code's
(`METERS`); an administrator changes only the numbers (and a meter's own parameters, e.g. how many seconds
of voice count as one Orena message). Features the design does not promise (dictionary lookups, saved
words, the boolean flags of catalogue v1) are not plan entitlements any more: every plan has them, nothing
meters them, and their cost telemetry is unchanged.

An administrator's change is stored as one `platform_settings` document (`PLAN_SETTING_KEY`) and applies from
the moment it is saved, in every worker within `CACHE_SECONDS`. A stored version-1 document (the meters
before D-160) is read with its prices kept and its old limits ignored - the meters changed, so there is no
limit to carry - and the administrator's next save writes version 2.

Two reads, deliberately different: `current_plans()` is the display read and never fails (a store it cannot
read gives the built-in values, logged); `current_plans(strict=True)` is the enforcement read and raises
`CatalogUnavailable` when the store or the stored document cannot be read, so quota enforcement fails closed
(HTTP 503) rather than enforcing limits nobody set. Billing is not live (`billing_ready` is False
everywhere), so a price is what the product shows, never what anyone is charged.
"""

from __future__ import annotations

import hashlib
import logging
import math
import time
from dataclasses import dataclass, field, replace
from collections.abc import Mapping
from typing import Any, Protocol

PLAN_SETTING_KEY = "product.plan_catalog"
CATALOG_VERSION = 2
CURRENCIES: tuple[str, ...] = ("USD", "VND")
PERIODS: tuple[str, ...] = ("monthly", "yearly")
MAX_PRICE = 1_000_000_000
MAX_LIMIT = 10_000_000

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Meter:
    """What a metered feature is. Code-owned: an administrator never changes a window or a unit.

    `window` is `day`, `month` or None (a count cap, not a bucket). `unit` is one stored/bucket unit;
    `display_unit` is what a learner reads, and `scale` stored units make one displayed unit (60 seconds
    are one minute). `params` names the meter's own admin-editable whole numbers with their bounds.
    """

    key: str
    window: str | None
    unit: str
    display_unit: str
    scale: int = 1
    params: Mapping[str, tuple[int, int]] = field(default_factory=dict)


METERS: dict[str, Meter] = {
    meter.key: meter
    for meter in (
        # Human 2026-10-09: a voice conversation is charged by duration, 1 voice minute = 1 message by default.
        Meter("orena.message", "day", "message", "message", params={"voice_seconds_per_message": (1, 3600)}),
        Meter("writing.review", "month", "review", "review"),
        Meter("pronunciation.audio", "month", "second", "minute", scale=60),
        Meter("media.import", "month", "second", "minute", scale=60),
        # A count of target languages; only ADDING one beyond the cap is refused, on the server (language_limit.py, D-170).
        Meter("languages.target", None, "language", "language"),
    )
}


@dataclass(frozen=True)
class Entitlement:
    key: str
    enabled: bool = True
    # Per window, in the meter's stored unit (seconds for the minute meters). None = unlimited.
    limit: int | None = None
    params: Mapping[str, int] = field(default_factory=dict)

    @property
    def meter(self) -> Meter:
        return METERS[self.key]

    @property
    def window(self) -> str | None:
        return self.meter.window

    @property
    def monthly_limit(self) -> int | None:
        """The frozen native contract's field: the limit of a monthly meter, in its stored unit."""
        return self.limit if self.meter.window == "month" else None

    def as_dict(self) -> dict[str, Any]:
        meter = self.meter
        return {
            "key": self.key,
            "enabled": self.enabled,
            "limit": self.limit,
            "window": meter.window,
            "unit": meter.unit,
            "display_unit": meter.display_unit,
            "scale": meter.scale,
            "params": dict(self.params),
            "monthly_limit": self.monthly_limit,
        }


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    description: str
    price_label: str
    entitlements: tuple[Entitlement, ...]
    rank: int = 0
    # {"monthly": {"USD": 9.99, "VND": 199000}, "yearly": {...}}
    prices: Mapping[str, Mapping[str, float]] = field(default_factory=dict)

    def entitlement_map(self) -> dict[str, Entitlement]:
        return {item.key: item for item in self.entitlements}

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price_label": self.price_label,
            "rank": self.rank,
            "prices": {period: dict(self.prices.get(period, {})) for period in PERIODS},
            "entitlements": [item.as_dict() for item in self.entitlements],
        }


def _prices(monthly_usd: float, monthly_vnd: float, yearly_usd: float, yearly_vnd: float) -> dict[str, dict[str, float]]:
    return {
        "monthly": {"USD": monthly_usd, "VND": monthly_vnd},
        "yearly": {"USD": yearly_usd, "VND": yearly_vnd},
    }


VOICE_SECONDS_PER_MESSAGE = 60


def _entitlements(messages: int, reviews: int, pronunciation_minutes: int, import_minutes: int,
                  languages: int) -> tuple[Entitlement, ...]:
    return (
        Entitlement("orena.message", limit=messages, params={"voice_seconds_per_message": VOICE_SECONDS_PER_MESSAGE}),
        Entitlement("writing.review", limit=reviews),
        Entitlement("pronunciation.audio", limit=pronunciation_minutes * 60),
        Entitlement("media.import", limit=import_minutes * 60),
        Entitlement("languages.target", limit=languages),
    )


FREE = Plan(
    id="free",
    name="Free",
    description="Everything you need to start a daily habit.",
    price_label="Free",
    rank=0,
    prices=_prices(0, 0, 0, 0),
    entitlements=_entitlements(20, 2, 5, 15, 1),
)

PLUS = Plan(
    id="plus",
    name="Plus",
    description="For steady learners who use Orena every day.",
    price_label="Plus",
    rank=1,
    prices=_prices(9.99, 199000, 79.99, 1590000),
    entitlements=_entitlements(200, 10, 30, 120, 2),
)

PRO = Plan(
    id="pro",
    name="Pro",
    description="For heavy speaking and writing practice.",
    price_label="Pro",
    rank=2,
    prices=_prices(19.99, 399000, 159.99, 3190000),
    entitlements=_entitlements(1000, 50, 120, 600, 2),
)

# The default catalogue, in rank order. `PLANS` keeps its name: the persistence importer seeds the `plans`
# table from it.
PLANS: dict[str, Plan] = {plan.id: plan for plan in (FREE, PLUS, PRO)}

# A subscription stored before Plus and Pro existed names "premium": it is Pro, the plan with Premium's limits.
LEGACY_PLAN_ALIASES: dict[str, str] = {"premium": PRO.id}

# Kept for callers that name the old top plan.
PREMIUM = PRO

DEFAULT_PLAN_ID = FREE.id
FEATURE_KEYS: tuple[str, ...] = tuple(METERS)


class PlanCatalogInvalid(ValueError):
    """An administrator's catalogue document that cannot be applied."""


class CatalogUnavailable(RuntimeError):
    """The catalogue in force cannot be known: the store failed, or what it holds cannot be read."""


class PlanSettingStore(Protocol):
    def get_setting(self, key: str) -> dict | None: ...
    def set_setting(self, key: str, value: dict, *, updated_by: str = "", expected_updated_at: object = ...,
                    audit: dict | None = None) -> dict: ...


_store: PlanSettingStore | None = None
# The catalogue in force, kept a few seconds so a quota check on every request does not read the database each
# time; a save in this process clears it at once, and every other worker sees it within CACHE_SECONDS. Only a
# successful read is kept - a failed one is never cached, so an enforcement read right after it still fails
# closed instead of being answered with the built-in values.
CACHE_SECONDS = 5.0
_cache: tuple[float, dict[str, Plan], str] | None = None


def _clear_cache() -> None:
    global _cache
    _cache = None


def configure_plan_store(store: PlanSettingStore | None) -> None:
    global _store
    _store = store
    _clear_cache()


def _number(value: object, *, what: str, integer: bool = False, upper: int) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanCatalogInvalid(f"{what} must be a number.")
    if not math.isfinite(value) or value < 0 or value > upper:
        raise PlanCatalogInvalid(f"{what} must be between 0 and {upper}.")
    if integer:
        if int(value) != value:
            raise PlanCatalogInvalid(f"{what} must be a whole number.")
        return int(value)
    return round(float(value), 2)


def _validated_prices(plan_id: str, raw_prices: object) -> dict[str, dict[str, float]]:
    raw_prices = raw_prices or {}
    if not isinstance(raw_prices, Mapping):
        raise PlanCatalogInvalid(f"{plan_id}: prices must be an object.")
    prices: dict[str, dict[str, float]] = {}
    for period in PERIODS:
        by_currency = raw_prices.get(period) or {}
        if not isinstance(by_currency, Mapping):
            raise PlanCatalogInvalid(f"{plan_id}: {period} prices must be an object.")
        prices[period] = {}
        for currency in CURRENCIES:
            amount = by_currency.get(currency, PLANS[plan_id].prices[period][currency])
            prices[period][currency] = _number(
                amount, what=f"{plan_id} {period} {currency}", integer=currency == "VND", upper=MAX_PRICE
            )
    if plan_id == FREE.id and any(value for period in prices.values() for value in period.values()):
        raise PlanCatalogInvalid("Free has no price.")
    return prices


def _validated_entitlement(plan_id: str, item: object) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise PlanCatalogInvalid(f"{plan_id}: each entitlement must be an object.")
    key = str(item.get("key") or "")
    if key not in METERS:
        raise PlanCatalogInvalid(f"{plan_id}: unknown feature {key!r}.")
    meter = METERS[key]
    enabled = item.get("enabled", True)
    if type(enabled) is not bool:
        raise PlanCatalogInvalid(f"{plan_id} {key}: enabled must be true or false.")
    limit = item.get("limit")
    if limit is None:
        raise PlanCatalogInvalid(f"{plan_id} {key}: a limit is required.")
    limit = _number(limit, what=f"{plan_id} {key} limit", integer=True, upper=MAX_LIMIT)
    default = PLANS[plan_id].entitlement_map()[key].params
    raw_params = item.get("params") or {}
    if not isinstance(raw_params, Mapping):
        raise PlanCatalogInvalid(f"{plan_id} {key}: params must be an object.")
    unknown = set(raw_params) - set(meter.params)
    if unknown:
        raise PlanCatalogInvalid(f"{plan_id} {key}: unknown parameter {sorted(unknown)[0]!r}.")
    params: dict[str, int] = {}
    for name, (low, high) in meter.params.items():
        value = _number(raw_params.get(name, default.get(name)), what=f"{plan_id} {key} {name}", integer=True,
                        upper=high)
        if value < low:
            raise PlanCatalogInvalid(f"{plan_id} {key} {name} must be between {low} and {high}.")
        params[name] = value
    return {"key": key, "enabled": enabled, "limit": limit, "params": params}


def validate_catalog(document: object, *, accept_v1: bool = False) -> dict[str, Any]:
    """The administrator's document, normalized: prices and limits for exactly the three plans.

    Version 2: `{"version": 2, "plans": [{"id", "prices": {period: {currency: amount}}, "entitlements": [{key,
    enabled, limit, params?}]}]}`. A plan's entitlements may name some meters only; the rest keep the code's
    defaults. Names, descriptions, ranks, windows and units stay the code's; Free is free.

    `accept_v1` is for READING a stored document: a version-1 document (no `version`, or 1) keeps its prices and
    drops its limits, whose features no longer exist. A save is always version 2 - an editor still showing the
    old features is refused rather than silently losing what it sent.
    """
    if not isinstance(document, Mapping):
        raise PlanCatalogInvalid("The catalogue must be an object.")
    version = document.get("version", 1)
    legacy = version in (None, 1)
    if legacy and not accept_v1:
        raise PlanCatalogInvalid("This catalogue was written for the old plan features. Reload the page.")
    if not legacy and version != CATALOG_VERSION:
        raise PlanCatalogInvalid(f"Unknown catalogue version {version!r}.")
    rows = document.get("plans")
    if not isinstance(rows, list):
        raise PlanCatalogInvalid("The catalogue needs a list of plans.")
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise PlanCatalogInvalid("Each plan must be an object.")
        plan_id = str(row.get("id") or "").strip().casefold()
        if plan_id not in PLANS:
            raise PlanCatalogInvalid(f"Unknown plan {plan_id!r}.")
        if plan_id in seen:
            raise PlanCatalogInvalid(f"Plan {plan_id!r} appears twice.")
        prices = _validated_prices(plan_id, row.get("prices"))
        entitlements: dict[str, dict[str, Any]] = {}
        if not legacy:
            raw_entitlements = row.get("entitlements") or []
            if not isinstance(raw_entitlements, list):
                raise PlanCatalogInvalid(f"{plan_id}: entitlements must be a list.")
            for item in raw_entitlements:
                normalized = _validated_entitlement(plan_id, item)
                entitlements[normalized["key"]] = normalized
        seen[plan_id] = {"id": plan_id, "prices": prices, "entitlements": list(entitlements.values())}
    if set(seen) != set(PLANS):
        raise PlanCatalogInvalid("The catalogue must name Free, Plus and Pro.")
    return {"version": CATALOG_VERSION, "plans": [seen[plan_id] for plan_id in PLANS]}


def _overlay(plan: Plan, row: Mapping[str, Any]) -> Plan:
    stored = {item["key"]: item for item in row.get("entitlements", [])}
    entitlements = tuple(
        Entitlement(
            item.key,
            enabled=bool(stored[item.key]["enabled"]),
            limit=stored[item.key]["limit"],
            params=dict(stored[item.key].get("params") or item.params),
        ) if item.key in stored else item
        for item in plan.entitlements
    )
    return replace(plan, prices=row.get("prices") or plan.prices, entitlements=entitlements)


def stored_catalog() -> dict | None:
    """The administrator's saved document with its `updated_at`/`updated_by`, or None (defaults apply)."""
    if _store is None:
        return None
    try:
        return _store.get_setting(PLAN_SETTING_KEY)
    except Exception:
        return None


def catalog_revision(updated_at: object) -> str:
    """Ten hex characters naming one saved catalogue; `default` when nothing is stored."""
    if not updated_at:
        return "default"
    return hashlib.sha256(str(updated_at).encode("utf-8")).hexdigest()[:10]


def policy_version(plan_id: str, revision: str) -> str:
    """What a quota bucket records as the policy its limit came from (String(40))."""
    return f"c{revision}:{plan_id}"[:40]


def _fetch() -> tuple[dict[str, Plan], str]:
    if _store is None:
        return dict(PLANS), "default"
    try:
        record = _store.get_setting(PLAN_SETTING_KEY)
    except Exception as error:
        raise CatalogUnavailable("The plan catalogue store could not be read.") from error
    if not record:
        return dict(PLANS), "default"
    try:
        document = validate_catalog(record.get("value"), accept_v1=True)
    except PlanCatalogInvalid as error:
        raise CatalogUnavailable(f"The stored plan catalogue cannot be read: {error}") from error
    rows = {row["id"]: row for row in document["plans"]}
    plans = {plan_id: _overlay(plan, rows[plan_id]) for plan_id, plan in PLANS.items()}
    return plans, catalog_revision(record.get("updated_at"))


def current_catalog(*, strict: bool = False) -> tuple[dict[str, Plan], str]:
    """The catalogue in force now and its revision. `strict` raises `CatalogUnavailable` instead of falling back."""
    global _cache
    now = time.monotonic()
    if _cache is not None and _cache[0] > now:
        return dict(_cache[1]), _cache[2]
    try:
        plans, revision = _fetch()
    except CatalogUnavailable:
        if strict:
            raise
        # A stored document is never half-applied; the display read shows the built-in values and says why.
        _log.warning("plan catalogue unreadable; showing the built-in values", exc_info=True)
        return dict(PLANS), "default"
    _cache = (now + CACHE_SECONDS, plans, revision)
    return dict(plans), revision


def current_plans(*, strict: bool = False) -> dict[str, Plan]:
    """The catalogue in force now: the defaults with the administrator's saved prices and limits on top."""
    return current_catalog(strict=strict)[0]


def save_catalog(document: object, *, updated_by: str = "", expected_updated_at: object = ...,
                 audit: dict | None = None) -> dict:
    """Validate and store the administrator's catalogue; it applies from this moment. `expected_updated_at` (the
    version the editor loaded, None for "nothing stored yet") is checked inside the store's write transaction, and
    `audit` is written in that same transaction (review of #112)."""
    normalized = validate_catalog(document)
    if _store is None:
        raise RuntimeError("The plan catalogue store has not been installed by the persistence runtime.")
    saved = _store.set_setting(PLAN_SETTING_KEY, normalized, updated_by=updated_by,
                               expected_updated_at=expected_updated_at, audit=audit)
    _clear_cache()
    return saved


def resolve_plan_id(plan_id: str | None) -> str:
    key = (plan_id or "").strip().casefold()
    return LEGACY_PLAN_ALIASES.get(key, key)


def known_plan_id(plan_id: str | None) -> bool:
    return resolve_plan_id(plan_id) in PLANS


def plan_by_id(plan_id: str | None, *, strict: bool = False) -> Plan:
    plans = current_plans(strict=strict)
    return plans.get(resolve_plan_id(plan_id), plans[DEFAULT_PLAN_ID])
