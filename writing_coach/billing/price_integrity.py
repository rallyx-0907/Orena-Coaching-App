"""Price integrity (PR-MON-2, D-MON-005, D-MON-015): a price is sold only when it is exactly the catalogue's.

Two records name a price, on purpose:

* the **catalogue** (`writing_coach.product.catalog`, Admin-editable, D-153) is what a learner is shown, per plan,
  `monthly`/`yearly` and currency, as a decimal amount;
* the **approved prices file** (`BILLING_PRICES_FILE`, `service.load_prices`) binds a plan and period to a gateway: the
  integer amount in minor units Orena charges (payOS) or the merchant of record's own price id (Polar).

Neither is derived from the other - a merchant of record charges the price configured on its side, which Orena
cannot write - so they are compared, every time: a price whose plan, period and currency have no catalogue entry, or
whose amount differs from it by any amount, is a mismatch, and a mismatch blocks checkout on its whole gateway
(`BillingService`). The comparison is exact, in integer minor units; nothing rounds it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from writing_coach.billing.gateway import Price

# How many decimal places one major unit has, for every currency the catalogue prices in (catalog.CURRENCIES).
MINOR_EXPONENT: dict[str, int] = {"USD": 2, "VND": 0}
# A billing period and the catalogue's name for it.
CATALOG_PERIOD: dict[str, str] = {"month": "monthly", "year": "yearly"}


@dataclass(frozen=True)
class PriceCheck:
    """One approved price against the catalogue. `status`: `match`, `mismatch` (the amounts differ) or `unknown`
    (the catalogue has no entry for this plan, period and currency)."""

    key: str
    plan_id: str
    period: str
    currency: str
    gateway: str
    amount_minor: int
    catalog_amount_minor: int | None
    status: str

    @property
    def matches(self) -> bool:
        return self.status == "match"

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "plan_id": self.plan_id, "period": self.period, "currency": self.currency,
                "gateway": self.gateway, "amount_minor": self.amount_minor,
                "catalog_amount_minor": self.catalog_amount_minor, "status": self.status}  # fmt: skip


def catalog_amount_minor(plans: Mapping[str, Any], plan_id: str, period: str, currency: str) -> int | None:
    """The catalogue's amount for this plan, billing period and currency, in the currency's minor unit; None when the
    catalogue names none (or names one that is not a whole number of minor units)."""

    plan = plans.get(plan_id)
    exponent = MINOR_EXPONENT.get(currency)
    if plan is None or exponent is None:
        return None
    amount = (plan.prices.get(CATALOG_PERIOD.get(period, "")) or {}).get(currency)
    if amount is None or isinstance(amount, bool):
        return None
    try:
        minor = Decimal(str(amount)).scaleb(exponent)
    except InvalidOperation:
        return None
    if not minor.is_finite() or minor != minor.to_integral_value():
        return None
    return int(minor)


def check_price(key: str, price: Price, plans: Mapping[str, Any]) -> PriceCheck:
    expected = catalog_amount_minor(plans, price.plan_id, price.period, price.currency)
    status = "unknown" if expected is None else ("match" if expected == price.amount_minor else "mismatch")
    return PriceCheck(key=key, plan_id=price.plan_id, period=price.period, currency=price.currency,
                      gateway=price.gateway, amount_minor=price.amount_minor, catalog_amount_minor=expected,
                      status=status)  # fmt: skip


def check_prices(prices: Mapping[str, Price], plans: Mapping[str, Any]) -> dict[str, PriceCheck]:
    return {key: check_price(key, price, plans) for key, price in prices.items()}


def blocked_gateways(checks: Iterable[PriceCheck]) -> set[str]:
    """Gateways with at least one price that is not the catalogue's: nothing is sold on them."""

    return {check.gateway for check in checks if not check.matches}
