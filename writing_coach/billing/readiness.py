"""Billing runtime readiness (PR-MON-2, D-MON-005, D-MON-015): `billing_ready` is true only when this runtime can
really take a payment and grant what it buys.

Revision 8.2 (PR-MON-8 §14.4, D-MON-032): plans and credits are separate capabilities. The top-level `blockers` are
the **runtime** blockers only:

* the switch (`BILLING_ENABLED`), PostgreSQL, and the account backbone `active`;
* the commerce schema (0006) and the orders table (`billing_orders`) present - `unreadable` is not `absent`;
* the billing entitlement source installed, so a payment changes the plan (`installed`, not `absent` or `unverified`,
  R-MON-010);
* a public base URL for the gateways' return pages (https in production);

plus `no_billing_capability_ready` when neither capability is ready. Each capability's own blockers stay in
`capabilities.<name>.blockers` and are never copied up, so `ready: true` always comes with `blockers: []`:

* `plans` - Polar configured with its keys (and so its webhook verification), priced, every price exactly the
  catalogue's, and no open critical reconciliation item on it (PR-MON-3 §4.2);
* `credits` - packs, credits ready, the domestic gateway chosen explicitly (`BILLING_DOMESTIC_GATEWAY`) and sellable
  (SePay's late-payment grace, its VA in production), no critical item on it and no open credit gap. The domestic
  gateway blocks nothing while Credits is not configured.

The report names states and booleans only; it never holds a key, a secret or a credential. `billing_ready()` is the
cheap read the product surfaces call: with billing off it decides without touching the database, it never raises,
and its answer is kept `CACHE_SECONDS`.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_log = logging.getLogger(__name__)
CACHE_SECONDS = 5.0


@dataclass(frozen=True)
class RuntimeFacts:
    switch: bool
    backend: str
    backbone: str  # active | disabled | unavailable
    commerce_schema: Callable[[], str]  # present | absent | unreadable
    orders_schema: Callable[[], str]  # present | absent | unreadable
    entitlement_source: Callable[[], str]  # installed | absent | unverified
    service: Any | None  # the BillingService, None where billing is not built
    public_base_url: str
    production: bool


def _url_state(url: str) -> str:
    url = url.strip().casefold()
    if not url:
        return "unset"
    return "https" if url.startswith("https://") else "http"


def report(facts: RuntimeFacts) -> dict[str, Any]:
    checks = {
        "switch": "on" if facts.switch else "off",
        "database": facts.backend or "none",
        "account_backbone": facts.backbone,
        "commerce_schema": facts.commerce_schema(),
        "orders_schema": facts.orders_schema(),
        "entitlement_source": facts.entitlement_source(),
        "public_base_url": _url_state(facts.public_base_url),
    }
    blockers: list[str] = []
    if not facts.switch:
        blockers.append("billing_off")
    if facts.backend != "postgresql":
        blockers.append("database_not_postgresql")
    if facts.backbone != "active":
        blockers.append(f"account_backbone_{facts.backbone}")
    for name, good in (("commerce_schema", "present"), ("orders_schema", "present"), ("entitlement_source", "installed")):
        if checks[name] != good:
            blockers.append(f"{name}_{checks[name]}")
    if checks["public_base_url"] == "unset":
        blockers.append("public_base_url_unset")
    elif facts.production and checks["public_base_url"] != "https":
        blockers.append("public_base_url_not_https")
    service = facts.service
    gateways = service.gateway_report() if service is not None else {}
    if service is None and not blockers:
        blockers.append("billing_service_absent")
    capabilities = ({"plans": service.plans_capability(gateways), "credits": service.credits_capability()}
                    if service is not None else {})  # fmt: skip
    if not any(capability["ready"] for capability in capabilities.values()):
        blockers.append("no_billing_capability_ready")
    result = {"ready": not blockers, "blockers": blockers, "checks": checks, "capabilities": capabilities,
              "gateways": gateways}  # fmt: skip
    if facts.service is not None and hasattr(facts.service, "reconciliation_summary"):
        result["reconciliation"] = facts.service.reconciliation_summary()
    return result


_facts: RuntimeFacts | None = None
# (expiry, {"ready": runtime ready, "plans": capability ready, "credits": capability ready})
_cache: tuple[float, dict[str, bool]] | None = None
_lock = threading.Lock()


def configure(facts: RuntimeFacts | None) -> None:
    global _facts, _cache
    with _lock:
        _facts, _cache = facts, None


def current_report() -> dict[str, Any]:
    """The full report, for an administrator. A runtime that never configured billing is reported as off."""

    facts = _facts
    if facts is None:
        return {"ready": False, "blockers": ["billing_off"], "checks": {"switch": "off"}, "capabilities": {},
                "gateways": {}}
    return report(facts)


def _decided() -> dict[str, bool]:
    """The runtime's answer and each capability's, kept `CACHE_SECONDS`; never raises."""

    global _cache
    facts = _facts
    closed = {"ready": False, "plans": False, "credits": False}
    if facts is None or not facts.switch or facts.service is None:
        return closed
    now = time.monotonic()
    cached = _cache
    if cached is not None and cached[0] > now:
        return cached[1]
    try:
        full = report(facts)
        ready = bool(full["ready"])
        decided = {"ready": ready,
                   **{name: ready and bool(capability.get("ready"))
                      for name, capability in full.get("capabilities", {}).items()}}  # fmt: skip
        decided = {**closed, **decided}
    except Exception:  # noqa: BLE001 - a probe that fails is "not ready", never a failed product read
        _log.warning("billing readiness could not be decided; reporting not ready", exc_info=True)
        decided = closed
    with _lock:
        if _facts is facts:
            _cache = (now + CACHE_SECONDS, decided)
    return decided


def billing_ready() -> bool:
    return _decided()["ready"]


def capability_ready(name: str) -> bool:
    """`plans` or `credits` (PR-MON-8 §14.4): the runtime is ready and so is that capability."""

    return bool(_decided().get(name, False))
