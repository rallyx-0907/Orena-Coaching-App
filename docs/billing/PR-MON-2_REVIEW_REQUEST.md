# PR-MON-2 Price Integrity + Runtime Readiness — independent architecture review request

The change is payment/entitlement, so `AGENTS.md` §1 requires an independent architecture review; the implementer
may not approve it. Record the reviewer, the reviewed commit and the verdict in Git, in
`docs/reviews/architecture/PR_MON_2_PRICE_READINESS_REVIEW_<date>.md`.

| | |
| --- | --- |
| Branch | `feature/monetization-billing-v1` |
| Base | `main` `aa016dc1` (PR-MON-1 merged as #153) |
| Decisions under review | D-MON-015 (price integrity, how; implements D-MON-005), D-MON-016 (fail-safe commerce discovery; closes the PR-MON-1 review P2 / R-MON-010) |
| Schema | none (0027 `billing_orders` stays proposed) |
| Runtime effect today | none for learners. Every runtime reports `orders_schema_absent`, so `billing_ready` stays false everywhere. `GET /api/admin/billing/readiness` is new and admin-only. |

## Problems

1. **Two independent price sources** (R-MON-004).
   - The catalogue (`product/catalog.py`, Admin-editable, D-153) is what the learner is shown.
   - `BILLING_PRICES_FILE` is what is charged.
   - Nothing compared them, so an Admin price edit, or a typo in the file, could charge a learner an amount they
     were never shown.
2. **`billing_ready` was a constant `False`** in five places. It said nothing true about the runtime.
3. **Startup discovery (review P2, R-MON-010).** An unreadable table listing installed no billing source. That was
   indistinguishable from a deployment without commerce, so a paid account read the legacy row for the life of the
   process. The source also required the backbone to be `active`, and the same failed listing leaves the backbone
   `unavailable`.

## Change

1. **`writing_coach/billing/price_integrity.py`** (new).
   - Converts a catalogue amount to integer minor units (USD has 2 decimals, VND has 0), by `Decimal` with no
     rounding.
   - `check_prices` compares each price with the catalogue entry for its plan, period and currency:
     `match` / `mismatch` / `unknown`.
   - `blocked_gateways` lists every gateway with any non-matching price.
2. **`BillingService`** (`billing/service.py`).
   - It takes `catalog`, which defaults to the strict catalogue read.
   - `offered()`: only prices of configured, unblocked gateways. An unreadable catalogue offers nothing.
   - `start_checkout()` checks before anything is written or sent:
     - `catalog_unavailable` (503);
     - `price_mismatch` (409, the gateway is blocked);
     - `price_unconfirmed` (422, the learner's confirmed amount or currency is missing);
     - `price_changed` (409, the confirmed price is not the server's).

     Only after these checks does it look for a second live subscription and create the order.
   - `gateway_report()`: configured, webhook verification, price checks and ready, per gateway. No key material.
   - `load_prices()` now refuses:
     - a plan that is not a paid catalogue plan by its own id (`premium`, `free` and unknown ids are refused);
     - a currency the catalogue does not price in;
     - an unknown gateway;
     - a key that appears twice.
3. **`writing_coach/billing/readiness.py`** (new).
   - `report(RuntimeFacts)` names every blocker:
     - switch, PostgreSQL, backbone;
     - 0006 tables, `billing_orders`;
     - entitlement source;
     - public URL (https in production);
     - catalogue, and whether any gateway is ready.
   - `billing_ready()` is cached for 5 s and never raises. With billing off it touches no database.
4. **`writing_coach/product/entitlement.py`**: `table_state()` returns present/absent/unreadable, and
   `DiscoveringCommerceSource` uses it:
   - **installed**: the commerce tables are listed, so the record is read;
   - **absent**: the listing answered without them, so there is no billing row;
   - **unverified**: the listing failed, so every read raises `CommerceUnreadable`, with a retry at most every 5 s.
     Once the listing answers, its result is kept.
5. **`app.py`**.
   - The source is installed wherever commerce is expected: PostgreSQL with `ORENA_ACCOUNT_BACKBONE` asked for. It
     no longer depends on the backbone being `active`.
   - Readiness is configured, and `configure_product_billing_ready` installs it.
6. **Surfaces.**
   - Real readiness: `ProductService.account_state`, `/api/product/plans`, `/api/product/admin/plans`, and the
     admin console's `billing` field.
   - `mobile_account_state` pins `billing_ready: false`, because the frozen native contract is
     `z.literal(false)`.
   - The checkout body gains optional `amount_minor` and `currency`. They are optional so that the route's
     body-validation order still answers 503 when billing is off.
   - `GET /api/admin/billing/readiness` returns the report.

## Semantics to review

| Case | Result |
| --- | --- |
| Every price of a gateway equals the catalogue | offered; checkout proceeds |
| One price of a gateway differs, by any amount | **nothing on that gateway** is offered; every checkout on it is `price_mismatch` |
| Admin edits a catalogue price | the next read (catalogue cache ≤ 5 s) blocks that gateway until the file is updated and the process restarted |
| Catalogue unreadable | nothing offered; checkout `catalog_unavailable` 503; readiness `catalog_unavailable` |
| Learner confirmed amount ≠ server amount, or a different currency | `price_changed`; no order, no gateway call |
| Commerce listing fails at startup (PostgreSQL, backbone asked) | plan reads raise → quota 503, Plan `available: false`; retry every 5 s; readiness `entitlement_source_unverified` |
| Commerce listed absent | no billing row (unchanged behaviour) |
| SQLite, no engine, backbone not asked | no source (unchanged behaviour) |
| `/api/product/me` (mobile) | `billing_ready: false` always |

## Questions for the reviewer

1. **Gateway-wide block.** Is blocking the whole gateway on one mismatch right? The alternative is blocking only the
   mismatched key. Either satisfies "a mismatch blocks checkout". The gateway-wide block forces an operator to fix
   the configuration rather than sell a partial catalogue.
2. **Confirmed price.** It is optional in the schema, but `start_checkout` requires it. Is that acceptable, given
   that no learner client calls checkout yet (the wiring comes in PR-MON-9)?
3. **Fail closed on unreadable discovery.** A transient startup failure makes plan reads fail for up to 5 s per
   retry, until the listing answers. Is this the intended safe side?
4. **Dropping the `backbone.is_active` requirement** for the entitlement source (D-MON-016). The membership guard's
   transactional check (`product_repository._billing_owns`) is unchanged.
5. **Polar's own price** (R-MON-011). Orena cannot read what Polar will charge without calling the API. Is deferring
   the sandbox verification to PR-MON-8 and the webhook amount anomaly to PR-MON-3 acceptable?

## Evidence

See the commit and the test results recorded in `BILLING_STATUS.md` ("Test status").

- New: `tests/test_billing_price_integrity.py`.
- Moved to canonical plan ids and catalogue prices: `tests/test_billing.py`.
