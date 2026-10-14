# PR-MON-3 Billing Orders + Reconciliation Safety — implementation review request

The change is payment code with a financial schema, so `AGENTS.md` §1 requires an independent architecture review,
and the implementer may not approve it. The approved design is `docs/billing/PR-MON-3_DESIGN.md`, revision 2,
APPROVED on `5b445175`. The review trail is in `docs/reviews/architecture/PR_MON_3_RECONCILIATION_REVIEW_2026-10-14.md`.
Record this verdict in the same file.

| | |
| --- | --- |
| Branch | `feature/monetization-billing-v1` |
| Base | `main` `d55526a2` |
| Decision | D-MON-018 (implements D-MON-004, design §4) |
| Schema | the new **proposed** `migrations/proposed/20261014_0031_billing_reconciliation.py` on the proposed 0027. Not promoted and not applied anywhere. |
| Runtime effect today | None. Billing is off, and 0027/0031 are proposed, so readiness stays `orders_schema_absent` everywhere and the reconciler does not start. |

## What changed, by design slice

1. **Schema and items.**
   - `0031` adds the following to `billing_orders`:
     - `expires_at`, `paid_reference`;
     - the lookup state: `provider_status`, `provider_checked_at`, `next_lookup_at`, `lookup_attempts`,
       `provider_settled_at`;
     - `refunded_by` and `refund_reference`;
     - three partial indexes;
     - a no-delete trigger.
   - `0031` adds the table `billing_reconciliation_items`:
     - provider facts with no foreign key, and Orena's links set only when matched;
     - the per-kind resolution CHECKs;
     - a guard trigger that forbids delete, keeps facts and links immutable, lets a terminal row change only its
       counters, and lets only a critical item reopen.
   - `downgrade()` refuses while either table holds a row.
   - `persistence/billing_reconciliation_repository.py`:
     - `record`: an idempotent upsert, which reopens a critical item;
     - `resolve`, which applies `RESOLUTION_RULES` and moves no money;
     - `auto_resolve` (the reconciler only), `items`, `summary`, `critical_by_gateway`.
2. **Write before acknowledging.**
   - `BillingService.record_payment` and `_item` record each money anomaly before the outcome returns:
     - `payment_unknown_order`, `payment_mismatch` and `payment_not_payable`;
     - `paid_deleted_account`;
     - `event_undecided`;
     - `provider_refund`.
   - `billing_api.billing_webhook` answers **503** when anything raises, so nothing durable means a retry.
   - A service without items cannot acknowledge an anomaly: it raises.
3. **Gaps.**
   - `PostgresBillingRepository.prepaid_gaps` compares, for active accounts, the orders' prepaid version with the
     applied version of `prepaid:<incarnation>`.
   - The reconciler repairs each gap with `sync_prepaid`, using the event id
     `<gw>:reconcile:<inc>:<version>`.
   - A gap that **survived its own repair** opens or reopens `entitlement_unsynced`, and the reconciler
     auto-resolves it once the gap is closed.
   - `gateway_report`, `offered` and `start_checkout` close a gateway that has an open critical item
     (`reconciliation_critical`, 503 retryable). Readiness names `reconciliation_critical` or
     `reconciliation_unavailable`.
4. **Reconciler** (`billing/reconciler.py`).
   - `PostgresTickLock` takes a session-level `pg_try_advisory_lock` on a dedicated connection. The implicit
     transaction is committed at once, as the review asked.
   - The lock is released in `finally`. If the release fails, the connection is invalidated, never returned to the
     pool.
   - The lock connection's liveness is checked before every step and before every lookup.
   - payOS lookups:
     - The pull set is every unsettled payOS order: created, pending, **expired**, and a webhook-paid one awaiting
       its confirming lookup.
     - Each order is claimed with a lease in its own short transaction, then the provider is called with no
       transaction open.
     - Only PAID with the order's amount, or CANCELLED with nothing paid, settles an order.
     - Anything else is asked again later. The backoff is `60 s × 2^n`, capped at 6 h, or a daily lookup past the
       14-day horizon, which also opens `provider_state_unresolved`.
     - A 429 ends the step and honours `Retry-After`, with no item opened.
     - At most `BILLING_PULL_PER_TICK` lookups per tick, each with a 5 s timeout.
   - A pulled payment uses `payos:order:<code>` and the same `record_payment` path. `mark_paid` now treats a payOS
     order as the unit of payment: a second fact with the same money and link is a duplicate, unless both
     references are known and differ (`not_payable`).
   - The confirming lookup finds an overpayment (`payment_mismatch`).
   - PAID that Orena cannot record opens the critical `provider_paid_unrecorded`.
   - Expiry is local only.
   - The reconciler starts with the app only where the billing service exists. payOS lookups run only with payOS
     keys.
5. **Polar refunds** (`_refund`). A refund is recorded as `provider_refund`. It is matched, and auto-resolved as
   `recorded`, only through a committed `commerce_provider_subscriptions` mapping. Otherwise it stays open. Access
   is never changed by it (H4).
6. **Admin API**, admin-guarded:
   - `GET /api/admin/billing/reconciliation`;
   - `POST /api/admin/billing/reconciliation/{id}/resolve`: a note is required, the outcome must be one the kind
     allows (otherwise 409), and the actor is the administrator's `google_sub`;
   - `POST /api/admin/billing/reconcile`.

   The readiness report gains `reconciliation`.

## Where the implementation goes beyond the approved text (please confirm)

1. **H2 branch:** a follow-up revision `0031`, not an edit of 0027 (no operator confirmation). The review said this
   choice needs no new architecture review.
2. `ix_billing_orders_pull` also covers `state = 'paid'`, because the confirming lookup of a webhook-paid order
   (§4.5) needs it. The design's index text listed only created, pending and expired.
3. As a follow-up on a table that might already hold rows, 0031 **backfills**: `expires_at = created_at + 30 min`,
   and `refunded_by = 'operator'` for refunded orders.
4. A verified payOS payment whose order code cannot be read is now `payment_unknown_order`. It was `ignored`.
5. payOS saying CANCELLED for an order Orena recorded paid opens `provider_state_unresolved` and keeps asking.
6. A partial `amountPaid` on a request still PENDING is non-terminal and asked again. Only a terminal status with an
   amount other than the order's opens `payment_mismatch`.
7. The resolution audit is the item itself (`resolved_by`, `resolution_note`, `resolved_at`, under the trigger). It
   is not also written to the admin console's audit log, which belongs to another module.
8. A service built without items reports `reconciliation: "not_configured"` and is not blocked. The running app
   always builds it with items. Tests that predate PR-MON-3 build it without them.

## Questions for the reviewer

1. Gap escalation only when the **same version** survives its repair in the same tick. A payment that lands
   mid-tick is repaired on the next tick and is not flagged. Is that the right threshold against false critical
   blocks?
2. Critical blocks are **per gateway**, not global. Is that acceptable?
3. One payment per payOS order, plus the confirming lookup, as the idempotency model (§4.5). Any case it misses?

## Evidence

See `BILLING_STATUS.md` ("Test status") for the commit and the results:
- `tests/test_billing_reconciliation.py`: no database;
- `tests/test_billing_reconciliation_postgres.py`: throwaway PostgreSQL 16 only;
- the updated `tests/test_billing.py`, `tests/test_effective_entitlement_postgres.py`,
  `tests/test_billing_price_integrity.py` and `tests/test_admin_authorization_matrix.py`;
- the mutation results.
