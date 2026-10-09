"""The plan catalogue: Free, Plus and Pro (human, 2026-10-09, D-153).

The defaults below are the design's three tiers (Orena.dc.html `BILL_PLANS`: names, monthly and yearly
prices in USD and VND). Their limits are the existing feature keys; the design's own meters (messages,
pronunciation minutes, imports, languages) have no backend and are not plan entitlements here.

An administrator can change every price and every limit from Platform Admin. The change is stored as one
`platform_settings` document (`PLAN_SETTING_KEY`) and applies from the moment it is saved: every read of
the catalogue (`current_plans()`) overlays the stored document on these defaults. Billing is not live
(`billing_ready` is False everywhere), so a price is what the product shows, never what anyone is charged.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Protocol

PLAN_SETTING_KEY = "product.plan_catalog"
CATALOG_VERSION = 1
CURRENCIES: tuple[str, ...] = ("USD", "VND")
PERIODS: tuple[str, ...] = ("monthly", "yearly")
MAX_PRICE = 1_000_000_000
MAX_LIMIT = 10_000_000


@dataclass(frozen=True)
class Entitlement:
    key: str
    enabled: bool = True
    monthly_limit: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "enabled": self.enabled,
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


FREE = Plan(
    id="free",
    name="Free",
    description="Everything you need to start a daily habit.",
    price_label="Free",
    rank=0,
    prices=_prices(0, 0, 0, 0),
    entitlements=(
        Entitlement("writing.evaluate", monthly_limit=30),
        Entitlement("writing.improve", monthly_limit=10),
        Entitlement("library.grammar"),
        Entitlement("dictionary.lookup", monthly_limit=120),
        Entitlement("vocabulary.save", monthly_limit=100),
        Entitlement("analytics.basic"),
        Entitlement("analytics.advanced", enabled=False),
        Entitlement("practice.personalized", enabled=False),
        Entitlement("export.report", enabled=False),
    ),
)

PLUS = Plan(
    id="plus",
    name="Plus",
    description="For steady learners who use Orena every day.",
    price_label="Plus",
    rank=1,
    prices=_prices(9.99, 199000, 79.99, 1590000),
    entitlements=(
        Entitlement("writing.evaluate", monthly_limit=150),
        Entitlement("writing.improve", monthly_limit=60),
        Entitlement("library.grammar"),
        Entitlement("dictionary.lookup", monthly_limit=800),
        Entitlement("vocabulary.save", monthly_limit=1000),
        Entitlement("analytics.basic"),
        Entitlement("analytics.advanced"),
        Entitlement("practice.personalized"),
        Entitlement("export.report", enabled=False),
    ),
)

PRO = Plan(
    id="pro",
    name="Pro",
    description="For heavy speaking and writing practice.",
    price_label="Pro",
    rank=2,
    prices=_prices(19.99, 399000, 159.99, 3190000),
    entitlements=(
        Entitlement("writing.evaluate", monthly_limit=500),
        Entitlement("writing.improve", monthly_limit=250),
        Entitlement("library.grammar"),
        Entitlement("dictionary.lookup", monthly_limit=2000),
        Entitlement("vocabulary.save", monthly_limit=3000),
        Entitlement("analytics.basic"),
        Entitlement("analytics.advanced"),
        Entitlement("practice.personalized"),
        Entitlement("export.report"),
    ),
)

# The default catalogue, in rank order. `PLANS` keeps its name: the persistence importer seeds the `plans`
# table from it.
PLANS: dict[str, Plan] = {plan.id: plan for plan in (FREE, PLUS, PRO)}

# A subscription stored before Plus and Pro existed names "premium": it is Pro, the plan with Premium's limits.
LEGACY_PLAN_ALIASES: dict[str, str] = {"premium": PRO.id}

# Kept for callers that name the old top plan.
PREMIUM = PRO

DEFAULT_PLAN_ID = FREE.id
FEATURE_KEYS: tuple[str, ...] = tuple(item.key for item in FREE.entitlements)


class PlanCatalogInvalid(ValueError):
    """An administrator's catalogue document that cannot be applied."""


class PlanSettingStore(Protocol):
    def get_setting(self, key: str) -> dict | None: ...
    def set_setting(self, key: str, value: dict, *, updated_by: str = "", expected_updated_at: object = ...,
                    audit: dict | None = None) -> dict: ...


_store: PlanSettingStore | None = None
# The catalogue in force, kept a few seconds so a quota check on every request does not read the database each time;
# a save in this process clears it at once (review 2026-10-09).
CACHE_SECONDS = 5.0
_cache: tuple[float, dict[str, Plan]] | None = None


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


def validate_catalog(document: object) -> dict[str, Any]:
    """The administrator's document, normalized: prices and limits for exactly the three plans.

    `{"version": 1, "plans": [{"id", "prices": {period: {currency: amount}}, "entitlements": [{key, enabled,
    monthly_limit}]}]}`. Names, descriptions, ranks and which features exist stay the code's; Free is free.
    """
    if not isinstance(document, Mapping):
        raise PlanCatalogInvalid("The catalogue must be an object.")
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
        raw_prices = row.get("prices") or {}
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
        raw_entitlements = row.get("entitlements") or []
        if not isinstance(raw_entitlements, list):
            raise PlanCatalogInvalid(f"{plan_id}: entitlements must be a list.")
        entitlements: dict[str, dict[str, Any]] = {}
        for item in raw_entitlements:
            if not isinstance(item, Mapping):
                raise PlanCatalogInvalid(f"{plan_id}: each entitlement must be an object.")
            key = str(item.get("key") or "")
            if key not in FEATURE_KEYS:
                raise PlanCatalogInvalid(f"{plan_id}: unknown feature {key!r}.")
            enabled = item.get("enabled", True)
            if type(enabled) is not bool:
                raise PlanCatalogInvalid(f"{plan_id} {key}: enabled must be true or false.")
            limit = item.get("monthly_limit")
            default_limit = PLANS[plan_id].entitlement_map()[key].monthly_limit
            if default_limit is None and limit is not None:
                raise PlanCatalogInvalid(f"{plan_id} {key}: this feature has no monthly limit.")
            if default_limit is not None:
                if limit is None:
                    raise PlanCatalogInvalid(f"{plan_id} {key}: a monthly limit is required.")
                limit = _number(limit, what=f"{plan_id} {key} limit", integer=True, upper=MAX_LIMIT)
            entitlements[key] = {"key": key, "enabled": enabled, "monthly_limit": limit}
        seen[plan_id] = {"id": plan_id, "prices": prices, "entitlements": list(entitlements.values())}
    if set(seen) != set(PLANS):
        raise PlanCatalogInvalid("The catalogue must name Free, Plus and Pro.")
    return {"version": CATALOG_VERSION, "plans": [seen[plan_id] for plan_id in PLANS]}


def _overlay(plan: Plan, row: Mapping[str, Any]) -> Plan:
    stored = {item["key"]: item for item in row.get("entitlements", [])}
    entitlements = tuple(
        Entitlement(
            item.key,
            enabled=bool(stored[item.key]["enabled"]) if item.key in stored else item.enabled,
            monthly_limit=stored[item.key]["monthly_limit"] if item.key in stored else item.monthly_limit,
        )
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


def current_plans() -> dict[str, Plan]:
    """The catalogue in force now: the defaults with the administrator's saved prices and limits on top."""
    global _cache
    now = time.monotonic()
    if _cache is not None and _cache[0] > now:
        return dict(_cache[1])
    plans = _read_plans()
    _cache = (now + CACHE_SECONDS, plans)
    return dict(plans)


def _read_plans() -> dict[str, Plan]:
    record = stored_catalog()
    if not record:
        return dict(PLANS)
    try:
        document = validate_catalog(record.get("value"))
    except PlanCatalogInvalid:
        # A stored document this code cannot read is ignored, never half-applied.
        return dict(PLANS)
    rows = {row["id"]: row for row in document["plans"]}
    return {plan_id: _overlay(plan, rows[plan_id]) for plan_id, plan in PLANS.items()}


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


def plan_by_id(plan_id: str | None) -> Plan:
    plans = current_plans()
    return plans.get(resolve_plan_id(plan_id), plans[DEFAULT_PLAN_ID])
