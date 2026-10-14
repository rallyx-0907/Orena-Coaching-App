# PR-MON-3 Billing Orders + Reconciliation Safety — design and migration plan

State: **DESIGN, stopped at the review checkpoint.** The plan changes the financial schema: it revises the proposed
0027. Nothing is implemented, and nothing is promoted or applied anywhere. The independent architecture review
(payment/entitlement and schema, `AGENTS.md` §1) and the human decisions in §9 come before code.

Inspected on `main` `d55526a2` (2026-10-14).

## 1. Migration topology, verified from the repository

The Alembic chain (`migrations/versions/`, read by `alembic.ini`) is linear:

```text
0001 → … → 0023 → 0025 → 0029 → 0030 → 0026      (single head: 20261005_0026_ai_cost_records)
```

- The numbering is not the order. 0026 was re-parented onto 0030 when 0030 was promoted (README, D-177).
- `migrations/proposed/` is not read by Alembic. It holds:

| Proposal | `down_revision` | Owner | Status against today's head |
| --- | --- | --- | --- |
| `20261001_0024_media_entries` | `20260930_0023` | media | **Stale parent.** Promoted as is, it would fork the chain. It must be re-parented when promoted. Not Billing's. |
| `20261005_0027_billing_orders` | `20261005_0026` | Billing | Correct parent today. |
| `20261005_0028_reading_derived_texts` | `20261005_0027` | Reading | The parent is **linearity only**. The Reading table has no foreign key to and no logical dependency on billing. `tests/test_reading_on_demand.py:388` pins `down_revision == "20261005_0027"`. |

`0026 → 0027 → 0028` is therefore a proposed linear tail. The only relation between 0027 and 0028 is that
0028 was written after 0027.

**Runtime state is not verified here.** D-177 records that 0026 was promoted in source control only and that "no
runtime has ever applied it". Whether any runtime has applied it since is the operator's record. The Billing lane
does not query :8000, :8010 or :8021. No document records 0027 or 0028 applied to a shared runtime. Tests apply them
only to throwaway schemas: `tests/test_billing.py`, `tests/test_effective_entitlement_postgres.py`, and
`tests/test_reading_on_demand.py`, which applies 0028 and rolls it back.

**Proposed topology rule (decision H1).** Whichever of 0027 and 0028 is promoted first takes the head of the day,
and the other is re-parented onto it at its own promotion.

- If Billing goes first, nothing changes: 0028 already sits on 0027.
- If Reading goes first, 0028 is re-parented onto 0026, the Reading lane updates its test pin, and 0027 is
  re-parented onto 0028.

The Billing lane does not edit 0028 or its test.

## 2. What exists today

- **Proposed 0027.**
  - The sequence `billing_order_code_seq` starts at 100001.
  - The table `billing_orders` holds:
    - `id`, a unique `operation_id`, a unique `order_code`;
    - `incarnation_id`, a foreign key to `account_incarnations` (RESTRICT);
    - `gateway`, `plan_id`, `period` (month/year), `currency`, `amount_minor` (> 0), `external_reference`;
    - `state`, one of created / pending / paid / expired / cancelled / refunded / failed;
    - `paid_event_id`, `paid_at`, `paid_sequence` (unique per incarnation), `period_end`, `refunded_at`,
      `refund_note`, `created_at`, `updated_at`.
  - CHECK constraints: the state list, the period, the amount, and `paid_at` present if and only if the order is
    paid or refunded.
  - Indexes: a partial unique index on `(gateway, external_reference)` and an index on `(incarnation, created_at)`.
  - `downgrade()` drops everything.
- **`PostgresBillingRepository`** (`persistence/billing_repository.py`):
  - `create_order` is idempotent per operation.
  - `mark_paid` locks the incarnation (`FOR NO KEY UPDATE`), then the order. It checks the amount, currency and
    payment link, assigns `paid_sequence`, and also accepts a late payment for an `expired` or `cancelled` order.
  - `mark_refunded` handles operator refunds.
  - `prepaid_state` replays the account's orders into its prepaid access.
- **`PostgresCommerceRepository.record_event`** (0006):
  - an exactly-once receipt per `(provider, external_event_id)`;
  - a version per provider subscription;
  - terminal receipts that a trigger keeps immutable.
- **Webhooks** (`billing/service.py`, `billing_api.py`):
  - payOS payments run `mark_paid`, then `sync_prepaid`.
  - Polar subscription events run `record_event`.
  - Polar refund events, and every other verified event, return `ignored`.
  - Every verified outcome answers **200**. A business anomaly leaves only a log line.

## 3. Money failure modes today

| # | Case | Today | Severity |
| --- | --- | --- | --- |
| F1 | A verified payOS payment for an unknown order code | 200, a log line, nothing durable | P1 (R-MON-002) |
| F2 | A verified payment whose amount, currency or payment link differs from the order | 200, a log line | P1 |
| F3 | A payment for an order that is already refunded, or paid by another event | 200, a log line | P1 |
| F4 | A payment for a deleted account | The order is recorded `paid` (good). The refund obligation exists only in a log line | P1 |
| F5 | **Crash between `mark_paid` and `sync_prepaid`** (two transactions) | Repaired only if the provider redelivers: `duplicate` re-syncs. payOS's retry policy is **not documented** (its webhook page only says to answer 2xx), so a lost redelivery leaves money taken and no access. D-MON-014 already blocks a manual grant in this window | P1 (R-MON-002) |
| F6 | `sync_prepaid` or `record_event` returns `unknown`, `foreign_incarnation` or `payload_conflict` | 200, a log line. A `received` receipt exists only for `unknown` | P1 |
| F7 | The payOS webhook never arrives (lost, endpoint down, payOS does not retry) | The order stays `pending` forever, and money is taken with no access | P1 |
| F8 | A Polar subscription event that names no Orena checkout | 200 `unknown`, a log line | P2 |
| F9 | A Polar refund | `ignored`, a log line. Access follows Polar's subscription events, but the refund itself is not recorded | P2 |
| F10 | An abandoned checkout | The order stays `created` or `pending` forever. Polar checkouts also create an order row that is never paid | P3 (noise, no money) |
| F11 | A database error during webhook processing | An exception, so 500. Polar retries; payOS behaviour is unknown | P2 |
| F12 | The webhook endpoint keeps failing | Polar disables the endpoint after 10 consecutive non-2xx deliveries, so a non-2xx for business anomalies would turn into lost events | design constraint |

Provider facts used:
- Polar retries a failed delivery up to 10 times with exponential backoff. It disables the endpoint after 10
  consecutive failures, counts a timeout over 10 s and any 3xx/4xx/5xx as a failure, and recommends answering
  within 2 s ([Polar delivery docs](https://polar.sh/docs/integrate/webhooks/delivery)).
- payOS documents only that the merchant answers 2XX ([payOS webhook](https://payos.vn/docs/du-lieu-tra-ve/webhook/)).
- payOS's SDKs expose a payment-link lookup by `orderCode` that returns `status`, `amountPaid` and `transactions`
  ([payos on PyPI](https://pypi.org/project/payos)). The exact REST path and status values must be confirmed in the
  sandbox (PR-MON-8).

## 4. Design

### 4.1 Principle

A verified money event is acknowledged with 2xx **only after** a durable record exists: the order, a receipt, or a
reconciliation item. If that record cannot be written, the answer is 5xx so the provider retries. Nothing that
moved money is ever only a log line. Business anomalies are never 4xx/5xx, because a retry cannot fix them and
Polar would disable the endpoint (F12).

### 4.2 Reconciliation items, new table `billing_reconciliation_items`

One durable row per money anomaly, which an operator or the reconciler can resolve. Replaying the same anomaly is
idempotent through the unique key `(kind, gateway, dedupe_key)`, and `occurrences` and `last_seen_at` count the
repeats.

| `kind` | Opened by | `dedupe_key` |
| --- | --- | --- |
| `payment_unknown_order` | F1 | the event id |
| `payment_mismatch` | F2 | the event id |
| `payment_not_payable` | F3 | the event id |
| `paid_deleted_account` | F4 (refund owed) | the order code |
| `entitlement_unsynced` | F5 or F6: a payment recorded without access granted | `<incarnation>:<orders version>` |
| `event_undecided` | F6, F8: `unknown`, `foreign_incarnation`, `payload_conflict`, or no checkout | the event id |
| `provider_refund` | F9: a Polar refund, matched to an account where it can be (§4.6) | the refund id |
| `provider_paid_unrecorded` | F7: the provider says paid but Orena holds no payment | the order code |

- The state is `open`, `resolved` or `dismissed`. A resolution records the note, the actor and the time.
- A trigger refuses a DELETE and any change to identity or money columns. A resolved item is terminal: a later
  replay only increments `occurrences`.
- Columns hold sanitized facts only: gateway, event id, order code, incarnation, amount, currency, the provider
  state name and the payload digest. There is no raw payload, no email and no card data.

### 4.3 Webhook outcome mapping (both providers)

| Outcome | Durable effect | HTTP |
| --- | --- | --- |
| Signature, malformed or oversize failure | none (D-MON-004) | 401 / 400 / 413 (unchanged) |
| Gateway not configured | none | 404 (unchanged) |
| `applied` / `duplicate` / `stale` | the order and the receipt | 200 |
| Ignored by design (a non-payment payOS code, an unhandled Polar type) | none (no money moved) | 200 |
| F1–F4, F6, F8, F9 | a reconciliation item, written before the answer | 200 |
| Writing the item fails, or any database or infrastructure error | none committed | **503**, so the provider retries |

payOS receives the same mapping. Its redelivery is not relied on: §4.5 covers it.

### 4.4 The crash between `mark_paid` and `sync_prepaid` (R-MON-002, F5)

- **Detection** is derived, not stored, so it cannot go stale. For each incarnation with paid orders, compare the
  orders' prepaid version with `commerce_provider_subscriptions.object_version` for `prepaid:<incarnation>`. That
  is the same arithmetic as D-MON-014's guard.
- **Repair.** The reconciler calls `sync_prepaid` with the event id `<gateway>:reconcile:<incarnation>:<version>`.
  This is idempotent: a repeated version is a duplicate, an older one is `stale`.
- **Escalation.** If the gap is still there after a repair attempt, or the verdict is not `apply`, the reconciler
  opens `entitlement_unsynced`.
- `mark_paid` and `sync_prepaid` are not merged into one transaction. The two-write design was approved in
  PR-MON-1 (D-MON-014), and replay repair keeps it correct.

### 4.5 Reconciler

The reconciler follows the existing `QuotaReconcileSchedule` pattern: a daemon thread with one tick every
`BILLING_RECONCILE_INTERVAL_SECONDS` (default 60). It starts only where the billing service exists. With several
processes, `pg_try_advisory_xact_lock` makes one tick run at a time, and order rows are locked
`FOR UPDATE SKIP LOCKED`. Each tick runs these steps, and each step catches its own errors:

1. **Entitlement gaps** (§4.4).
2. **payOS pull (F7).** For `pending` payOS orders older than `BILLING_PULL_AFTER_SECONDS` (default 120) and not yet
   expired, read the payment link by `orderCode`. If it is PAID with the order's amount, run the **same**
   `mark_paid` and `sync_prepaid` path. The event id is built exactly like the webhook's
   (`<paymentLinkId>:<reference>:<orderCode>`), so a later webhook is a `duplicate`. If it is PAID with a different
   amount, open `payment_mismatch`. If it is CANCELLED or EXPIRED, record the order as `cancelled` or `expired`.
   - This is an outbound call to payOS, and it runs only when billing is enabled with keys (a human gate).
   - Tests use a fake gateway. The live response shape is verified in the PR-MON-8 sandbox (R-MON-013).
3. **Abandoned-order expiry (F10).** A `created` or `pending` order past `expires_at` becomes `expired`. A payOS
   order is pulled once first, so a payment never expires unseen.
   - `mark_paid` still accepts an expired order, because the money wins and access is granted.
   - A Polar order expiring changes nothing: the account binding in `_known_checkout` reads the order whatever its
     state.

### 4.6 Polar refunds (F9): match only where safe

- A refund carries `subscription_id` or `order_id`. When `subscription_id` maps to an incarnation through
  `commerce_provider_subscriptions` (a committed mapping, permanent), the reconciler records `provider_refund` for
  that account, resolved automatically with "access follows subscription events".
- When nothing maps, it records an open `provider_refund` for an operator.
- **Access is not changed by the refund itself.** Polar sends the subscription's own revoke or cancel events, and
  those already decide access (D-MON-011). Whether a refund should revoke access immediately is decision H4.

### 4.7 Operator surface (API only; the Admin Orders UI stays deferred)

All admin-guarded:
- `GET /api/admin/billing/reconciliation?state=open`: the items, with counts per kind.
- `POST /api/admin/billing/reconciliation/{id}/resolve` with `{resolution: resolved|dismissed, note}`: audited, and
  no money moves.
- `POST /api/admin/billing/reconcile`: runs one tick now and returns its counts.

The readiness report gains `reconciliation_open: <count>`. It is information only and never a blocker, so a
backlog cannot stop new payments from being recorded.

## 5. Exact schema change: proposed 0027 revision 2

0027 is still a proposal and has never been applied to any runtime the lane knows of (§1), so it is **revised in
place** rather than given a follow-up revision. `revision` and `down_revision` stay the same. The changes are listed
below.

`billing_orders`:
- `+ expires_at TIMESTAMPTZ NOT NULL`. It is set at creation (`created_at + BILLING_ORDER_TTL`, default 30 min). The payOS
  payment request is sent with the same expiry (`expiredAt`; today's request sets none, and the field is verified
  in the PR-MON-8 sandbox), so the link and the order expire together.
- `+ refunded_by VARCHAR(20) NULL`, with `CHECK (refunded_by IN ('operator','provider'))` and
  `CHECK ((state = 'refunded') = (refunded_by IS NOT NULL))`.
- `+ refund_reference VARCHAR(200) NULL`, with a partial unique index on `(gateway, refund_reference)` where it is
  not null.
- `+ index ix_billing_orders_open_expiry` on `(state, expires_at)` where `state IN ('created','pending')`, for the
  sweeper.
- `+ index ix_billing_orders_paid` on `(incarnation_id, paid_sequence)` where `paid_sequence IS NOT NULL`, for the
  replay and the gap scan.

Unchanged: every existing column and constraint, the state vocabulary, and the sequence.

New `billing_reconciliation_items`:

```text
id UUID PK
kind VARCHAR(40) NOT NULL         CHECK in the §4.2 list
gateway VARCHAR(40) NOT NULL
dedupe_key VARCHAR(200) NOT NULL  UNIQUE (kind, gateway, dedupe_key)
external_event_id VARCHAR(200) NULL
order_code BIGINT NULL            FK billing_orders(order_code) RESTRICT
incarnation_id UUID NULL          FK account_incarnations(id) RESTRICT
amount_minor BIGINT NULL, currency VARCHAR(3) NULL   (as reported by the provider)
provider_state VARCHAR(60) NULL, payload_digest VARCHAR(128) NULL, reason VARCHAR(400) NULL
state VARCHAR(12) NOT NULL DEFAULT 'open'  CHECK IN ('open','resolved','dismissed')
resolution_note VARCHAR(400) NULL, resolved_by VARCHAR(200) NULL, resolved_at TIMESTAMPTZ NULL
                                  CHECK ((state = 'open') = (resolved_at IS NULL))
occurrences INTEGER NOT NULL DEFAULT 1 CHECK (> 0)
first_seen_at, last_seen_at TIMESTAMPTZ NOT NULL
INDEX (state, kind, first_seen_at); INDEX (incarnation_id)
TRIGGER: no DELETE; no UPDATE of kind/gateway/dedupe_key/event/order/incarnation/amount/currency;
         no change once state <> 'open' except occurrences/last_seen_at
```

No change to 0006 or 0007, to any learner table, or to 0028.

## 6. Rollback implications

- **Before any real payment** (sandbox only): `downgrade()` drops both tables and the sequence. In revision 2 it
  first **refuses** if either table holds a row, so a rehearsal can go down and up, but a runtime that took money
  cannot lose its financial records through Alembic.
- **After real payments:** the schema is never downgraded. Rollback means rolling back the code: the tables are
  additive, and the earlier code ignores them while `BILLING_ENABLED` is off. Retention follows D-MON / item 5, a
  human decision.
- **Code rollback with billing on** is not supported. Billing must be switched off first (`BILLING_ENABLED=0`).
  Webhooks then answer 503 `billing_off`, Polar retries for a while, and the reconciler catches up when billing is
  back on.
- **Promotion order** with 0028 follows §1 (H1). Promoting 0027 never forces 0028.

## 7. Implementation slices (after review APPROVE and H-decisions)

1. 0027 revision 2, plus a repository for the reconciliation items (idempotent upsert, resolve), plus a trigger
   test.
2. Webhook outcome mapping (§4.3): write the item before acknowledging, and answer 503 when that write fails.
3. The gap detector and repair (§4.4).
4. The reconciler: tick, advisory lock, expiry, payOS pull behind a gateway interface with a fake in tests.
5. Polar refund matching (§4.6).
6. The admin API (§4.7) and the readiness count.

Everything stays in Billing files: `billing/`, `persistence/billing_repository.py`, `billing_api.py`, the
proposed 0027, tests, and the start-up wiring in `app.py`. Credits (PR-MON-4) and UI are out of scope, and #160 is
not touched.

## 8. Test and rehearsal plan (throwaway PostgreSQL 16 only)

- **Migration:**
  - head 0026 + 0027 revision 2: upgrade, downgrade (empty), upgrade;
  - downgrade refused with a row present;
  - the trigger refuses a DELETE or an identity change;
  - every CHECK and unique constraint is probed;
  - 0028 on top of 0027 still applies (topology).
- **Webhook mapping:** each of F1–F4, F6, F8, F9 gives 200 and one item; a replay gives the same item with
  `occurrences + 1`; a failure to write the item gives 503 and nothing committed.
- **Crash injection:**
  - `mark_paid` commits, then `sync_prepaid` raises. The webhook answers 503, the reconciler repairs the gap, and
    access equals a clean run.
  - With no redelivery, the gap is repaired by the tick alone.
- **The payOS pull** with a fake: PAID gives one payment, and a later webhook is a `duplicate`; PAID with a wrong
  amount gives `payment_mismatch`; CANCELLED or EXPIRED gives the state; and the pull runs before expiry.
- **Concurrency:** two reconcilers at once give one tick (advisory lock); a webhook racing the pull for the same
  order gives exactly one payment.
- **Expiry:** an expired order paid late is accepted, access is granted, and no duplicate occurs.
- **Regression:** every PR-MON-1 and PR-MON-2 Billing and entitlement test, plus every `tests/*_postgres.py`. The
  one failure in #160 is inherited.
- **Mutations:** remove the write-before-ack, the gap repair, the pull-before-expiry, the downgrade guard and the
  trigger. Each must fail tests.
- **No shared runtime:** nothing runs on :8000, :8010 or :8021, and nothing applies 0027 anywhere outside a
  throwaway database.

## 9. Decisions for the human owner

| # | Decision | Lane recommendation |
| --- | --- | --- |
| H1 | Promotion order and parent rule for 0027 and 0028 (§1) | Whichever is promoted first takes the head, and the other re-parents. Billing does not edit 0028. |
| H2 | Revise the never-applied 0027 in place (revision 2) instead of adding a new revision | Revise in place. It is not in the chain and has no runtime history. Needs confirmation that no runtime ever applied 0027 by hand. |
| H3 | Allow the payOS **pull** (outbound status read) as the safety net for lost webhooks (§4.5 step 2) | Yes. payOS documents no retry policy, so without the pull, F7 can take money silently. It runs only with billing enabled and keys set. |
| H4 | Does a Polar refund revoke access at once, or does access follow Polar's subscription events? | Follow the subscription events (current behaviour). Record every refund durably. |
| H5 | Order expiry window (`BILLING_ORDER_TTL`) | 30 min, sent to payOS as the link's own expiry. Operational, not commercial. |
| H6 | Who resolves reconciliation items, and does resolving ever move money? | Admin only, with an audit note. Resolving never moves money; a refund is a separate, recorded act. |
| H7 | Retention of `billing_orders` and reconciliation items | Keep indefinitely until the legal/refund/terms decision (item 5). No sweep in PR-MON-3. |

Not decided by the lane: any price, credit or trial number, production keys, activation, or applying any migration
to a shared runtime.

## 10. Risks

- **R-MON-002** is addressed by §4.2–4.5 once implemented.
- **New R-MON-013:** the shape of the payOS lookup response and the PAID/CANCELLED/EXPIRED vocabulary are assumed
  from the SDK documentation and must be verified in the sandbox (PR-MON-8) before the pull is trusted in
  production.
