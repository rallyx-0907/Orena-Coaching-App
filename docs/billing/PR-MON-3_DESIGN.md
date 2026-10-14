# PR-MON-3 Billing Orders + Reconciliation Safety — design and migration plan

State: **DESIGN revision 2, awaiting the focused re-review.** Revision 1 (`a50aa76b`) got REQUEST CHANGES with
four P1s, which are closed here (§4). The plan changes the financial schema, because it revises the proposed 0027.
Nothing is implemented, and nothing is promoted or applied anywhere. Code starts only after the design is
APPROVED.

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

Revision 2 of this design closes the review of `a50aa76b`
(`docs/reviews/architecture/PR_MON_3_RECONCILIATION_REVIEW_2026-10-14.md`):

- P1-1 is closed in §4.2 and §5;
- P1-2 in §4.5;
- P1-3 in §4.2, §4.7 and §5;
- P1-4 in §4.5;
- the three P2s in §4.5 and §5.

### 4.1 Principle

A verified money event is acknowledged with 2xx **only after** a durable record of it exists. That record is the
order, a receipt or a reconciliation item. If it cannot be written, the answer is 503, so the provider retries.

Nothing that moved money is ever only a log line. A business anomaly never answers 4xx/5xx, because a retry cannot
fix it and Polar would disable the endpoint (F12). The answer is never "always 200" either: an event without a
durable record must be retried, even at the risk of an endpoint disable. Ops alerts on repeated webhook 5xx
(PR-MON-8 runbook).

### 4.2 Reconciliation items, new table `billing_reconciliation_items`

There is one durable row per money anomaly. Replaying the same anomaly is idempotent on `(kind, gateway,
dedupe_key)`; a repeat only raises `occurrences` and updates `last_seen_at`.

**Provider facts and Orena links are separate columns** (P1-1):
- `reported_order_code`, `reported_amount_minor`, `reported_currency`, `external_event_id`, `provider_state` and
  `payload_digest` are what the provider said. They have **no foreign key**, so an order code Orena never issued is
  still stored.
- `billing_order_id` (foreign key to `billing_orders.id`) and `incarnation_id` (foreign key to
  `account_incarnations.id`) are Orena's own links. Both are set only when the reconciler matched the fact to
  Orena's records, and both are RESTRICT.

Each kind has its own resolution rule (P1-3, H6):

| `kind` | Opened by | `dedupe_key` | Class | How it leaves `open` |
| --- | --- | --- | --- | --- |
| `entitlement_unsynced` | F5/F6: a payment is recorded, access is not granted, and a repair already failed | `<incarnation>:<orders version>` | **critical** | **Only automatically**, by the reconciler. It resolves with outcome `entitlement_synced` once the orders' prepaid version equals the applied commerce version and the sync was `apply`/`duplicate`. No administrator can resolve or dismiss it. |
| `provider_paid_unrecorded` | F7: the provider says paid and Orena holds no payment | the order code | **critical** | Resolved only with an outcome: `payment_recorded` (automatic, once the order is paid), `refund_confirmed` or `reversal_confirmed`, each with a reference. Never dismissed. |
| `paid_deleted_account` | F4: money arrived for a deleted account, so a refund is owed | the order code | money | Resolved only with `refund_confirmed` plus a reference, or `obligation_waived` plus an audited financial reason. Never dismissed. |
| `payment_unknown_order` | F1 | the event id | money | Resolved with `payment_matched` (an order named), `refund_confirmed` or `obligation_waived`, each with a reference or reason. Never dismissed. |
| `payment_mismatch` | F2, or an overpayment the pull sees (§4.5) | the event id or `pull:<order>` | money | The same outcomes as `payment_unknown_order`. Never dismissed. |
| `payment_not_payable` | F3 | the event id | money | The same outcomes as `payment_unknown_order`. Never dismissed. |
| `event_undecided` | F6/F8: `unknown`, `foreign_incarnation`, `payload_conflict`, or no checkout | the event id | review | Resolved, or dismissed with a note confirming no money obligation. |
| `provider_refund` | F9: a Polar refund | the refund id | record | Matched to an account: resolved automatically as `recorded` (access follows subscription events, H4). Unmatched: open, then resolved with a note. Dismissal is allowed only with a note. |
| `provider_state_unresolved` | The pull horizon passed without a terminal provider answer, or the provider sent a state Orena does not recognise (§4.5) | the order code | review | Resolved with an outcome, or reopened if a later lookup changes it. |

- **Reopen.** A critical item whose condition is detected again goes back to `open`. `reopened` counts the
  times. A critical item can therefore never be left terminal while its condition holds.
- **Database enforcement.** The rules above are CHECK constraints and a trigger (§5), not only application code.
- **What a column may hold.** Only sanitized facts. There is no raw payload, no email and no card data (H7).

**Readiness (P1-3).** Each gateway's readiness gains a check: an **open critical item on that gateway**
(`entitlement_unsynced` or `provider_paid_unrecorded`) makes that gateway not ready, under the blocker
`reconciliation_critical`.
- If every gateway is blocked, `billing_ready` is false, and the D-MON-017 route gate closes new checkouts.
- Webhooks, the reconciler and the admin routes keep running, so the item can actually be repaired.
- Other open items are shown as counts and do not block.

### 4.3 Webhook outcome mapping (both providers)

| Outcome | Durable effect | HTTP |
| --- | --- | --- |
| Signature, malformed or oversize failure | none (D-MON-004) | 401 / 400 / 413 (unchanged) |
| Gateway not configured | none | 404 (unchanged) |
| `applied` / `duplicate` / `stale` | the order and the receipt | 200 |
| Ignored by design (a non-payment payOS code, an unhandled Polar type) | none (no money moved) | 200 |
| F1–F4, F6, F8, F9 | a reconciliation item, committed before the answer | 200 |
| The item cannot be written, or any database or infrastructure error | none committed | **503**, so the provider retries |

payOS gets the same mapping. Orena does not rely on payOS redelivering a webhook; §4.5 covers that case.

### 4.4 The crash between `mark_paid` and `sync_prepaid` (R-MON-002, F5)

- **Detection** is derived, not stored, so it cannot go stale. For each incarnation with paid orders, compare the
  orders' prepaid version with `commerce_provider_subscriptions.object_version` for `prepaid:<incarnation>`. This
  is the D-MON-014 arithmetic.
- **Repair.** Call `sync_prepaid` with the event id `<gateway>:reconcile:<incarnation>:<version>`. A repeated
  version is a duplicate; an older one is `stale`.
- **Escalation.** If the gap is still there after one repair attempt, or the verdict is not
  `apply`/`duplicate`, open (or reopen) `entitlement_unsynced`. It blocks its gateway's readiness (§4.2) until a
  later tick closes the gap and auto-resolves it.
- `mark_paid` and `sync_prepaid` stay two transactions (D-MON-014). Repair by replay keeps them correct.

### 4.5 Reconciler

**Lock scope (P1-4).**
- A tick first takes a **session-level** advisory lock, `pg_try_advisory_lock(<billing reconciler key>)`, on a
  **dedicated connection** that holds no transaction. A process that does not get the lock skips the tick.
- The lock is released with `pg_advisory_unlock` in `finally`. If the process dies, the connection closes and
  PostgreSQL releases the lock.
- Each mutation is its own **short transaction**. Examples: claim one order, record one lookup result, run one
  `mark_paid`, one `sync_prepaid`, one item upsert. That transaction takes its row locks
  (`FOR UPDATE SKIP LOCKED` on the order) and commits.
- **No transaction and no row lock is open while payOS is called.**
- The lock connection is checked before each step. If it was lost, the tick stops at once and the next tick starts
  over.
- Idempotency is the last line of defence when a webhook and a pull race each other (below).

**Schedule.** The reconciler follows the existing `QuotaReconcileSchedule` pattern: a daemon thread with one tick
every `BILLING_RECONCILE_INTERVAL_SECONDS` (default 60). It starts only where the billing service exists. Each step
catches its own errors.

1. **Entitlement gaps** (§4.4), and auto-resolution of the critical items whose condition has gone.
2. **payOS pull (F7, P1-2).**
   - **Which orders it reads.** The pull reads every payOS order whose provider outcome is not settled:
     `provider_settled_at IS NULL`, state `created`, `pending` **or `expired`**, and `next_lookup_at <= now`.
   - **Local expiry does not stop the pull.** An order leaves the pull set only when a **successful** lookup has
     returned a documented terminal answer:
     - `PAID` with `amountPaid` equal to the order amount: the payment is recorded through the same `mark_paid`
       and `sync_prepaid` path, and the order is settled.
     - `CANCELLED` with `amountPaid = 0`: the order is recorded `cancelled` and settled.
   - **Non-terminal answers keep the order in the pull set.** These are `PENDING`, `PROCESSING`, any other or
     unrecognised status (`EXPIRED` included until the sandbox shows it, R-MON-013), a timeout, a network error and
     a 429. Each one schedules the next lookup with backoff: `next_lookup_at = now + min(60 s × 2^attempts, 6 h)`,
     or the provider's `Retry-After` on a 429.
   - **Horizon.** After `BILLING_PULL_HORIZON` (default 14 days, an operational setting, not a commercial
     retention period) without a terminal answer, the order opens `provider_state_unresolved` and keeps a daily
     lookup. The search never simply stops.
   - **Rate limit (P2).** At most `BILLING_PULL_PER_TICK` lookups per tick (default 20), each with a 5 s timeout.
     A 429 ends the pull step for this tick. Rate-limiting and transport errors never open a money item.
   - **Idempotency without guessing (P2).** A pulled payment's event id is `payos:order:<orderCode>`, never a
     reconstruction of the webhook's id. The payOS order is the unit of payment: `mark_paid` records one payment
     per order and keeps `paid_reference`, the provider's transaction reference when it is known.
     - A later verified fact for an already-paid order with the same amount and link is a `duplicate`. This
       covers a webhook after a pull, and a pull after a webhook.
     - If both references are known and they differ, the fact is a second real payment, so `payment_not_payable`
       is opened.
     - Every webhook-paid payOS order gets **one confirming lookup**. `amountPaid` greater than the order amount
       is an overpayment and opens `payment_mismatch`, so a second transfer with an unreadable reference is still
       found.
   - **PAID with a different amount** opens `payment_mismatch`, and the order is not paid.
   - **When it runs.** Only with billing enabled and keys set (H3), through the gateway interface. Tests use a
     fake.
3. **Abandoned-order expiry (F10, H5).** A `created` or `pending` order past `expires_at` becomes `expired`, and
   that is all.
   - It is not settled, so the pull above keeps reading it.
   - `mark_paid` still accepts it: a verified late payment always wins over the local expiry.
   - A Polar order expiring changes nothing. `_known_checkout` reads the order whatever its state, and Polar
     orders are never pulled.

### 4.6 Polar refunds (F9, H4)

- A refund carries `subscription_id` or `order_id`.
- If `subscription_id` maps to an incarnation through a committed `commerce_provider_subscriptions` row, a
  `provider_refund` item is recorded for that account and resolved automatically (`recorded`).
- Otherwise the item stays open for an operator.
- The refund itself never changes access. Access follows Polar's subscription lifecycle events (H4).

### 4.7 Operator surface (API only; the Admin Orders UI stays deferred)

All admin-guarded and audited:

- `GET /api/admin/billing/reconciliation?state=open&kind=`: the items, the counts per kind, and the critical count.
- `POST /api/admin/billing/reconciliation/{id}/resolve` with `{resolution, outcome, reference, note}`:
  - the note is required;
  - the outcome must be one the kind allows (§4.2), otherwise the answer is 409;
  - the endpoint can never resolve `entitlement_unsynced`;
  - it **moves no money and changes no access**, because a refund, grant or revoke is its own separate, recorded
    operation (H6).
- `POST /api/admin/billing/reconcile`: runs one tick now (the same lock) and returns its counts.

The readiness report gains `reconciliation: {open, critical_by_gateway}`. Critical items block their gateway
(§4.2); the others are counts only.

## 5. Exact schema change: proposed 0027 revision 2

**Pre-condition (H2).** The revision is changed in place only after an operator confirms three things:
- no shared or runtime database has `alembic_version = 20261005_0027`;
- no `billing_orders` table exists that was created by hand from it;
- no long-lived sandbox needs the old history kept.

The Billing lane does not query :8000, :8010 or :8021 to establish this. If it cannot be confirmed, 0027 stays as
it is, and the change below becomes a new revision on top of it. The ids, the head rule and `down_revision` follow
H1 at promotion time.

`billing_orders`:
- `+ expires_at TIMESTAMPTZ NOT NULL`, set as `created_at + BILLING_ORDER_TTL` (default 30 min, H5).
  - The payOS payment request carries the same expiry as `expiredAt`. Today's request sets none, and the field is
    taken from payOS's documentation (R-MON-013).
- `+ paid_reference VARCHAR(200) NULL`: the provider's transaction reference, when known.
- `+ provider_status VARCHAR(30) NULL`, `+ provider_checked_at TIMESTAMPTZ NULL`, `+ next_lookup_at TIMESTAMPTZ NULL`,
  `+ lookup_attempts INTEGER NOT NULL DEFAULT 0 CHECK (>= 0)`, `+ provider_settled_at TIMESTAMPTZ NULL`.
- `+ refunded_by VARCHAR(20) NULL` with two CHECKs: `refunded_by IN ('operator','provider')`, and
  `(state = 'refunded') = (refunded_by IS NOT NULL)`.
- `+ refund_reference VARCHAR(200) NULL`, with a partial unique index on `(gateway, refund_reference)` where it is
  not null.
- `+ index ix_billing_orders_pull` on `(gateway, next_lookup_at)` where
  `provider_settled_at IS NULL AND state IN ('created','pending','expired')`.
- `+ index ix_billing_orders_open_expiry` on `(state, expires_at)` where `state IN ('created','pending')`.
- `+ index ix_billing_orders_paid` on `(incarnation_id, paid_sequence)` where `paid_sequence IS NOT NULL`.
- `+ trigger billing_orders_no_delete`: refuses every DELETE (P2). Orders are financial records, and no repository
  path deletes one.

Unchanged: every existing column and constraint, the state vocabulary, and the sequence.

New `billing_reconciliation_items`:

```text
id UUID PK
kind VARCHAR(40) NOT NULL              CHECK in the §4.2 list
gateway VARCHAR(40) NOT NULL
dedupe_key VARCHAR(200) NOT NULL       UNIQUE (kind, gateway, dedupe_key)
-- provider facts: no foreign keys (P1-1)
external_event_id VARCHAR(200) NULL
reported_order_code BIGINT NULL
reported_amount_minor BIGINT NULL, reported_currency VARCHAR(3) NULL
provider_state VARCHAR(60) NULL, payload_digest VARCHAR(128) NULL, reason VARCHAR(400) NULL
-- Orena's links, set only when matched
billing_order_id UUID NULL             FK billing_orders(id) RESTRICT
incarnation_id UUID NULL               FK account_incarnations(id) RESTRICT
-- resolution (P1-3)
state VARCHAR(12) NOT NULL DEFAULT 'open'   CHECK IN ('open','resolved','dismissed')
resolution_outcome VARCHAR(30) NULL, resolution_reference VARCHAR(200) NULL
resolution_note VARCHAR(400) NULL, resolved_by VARCHAR(200) NULL, resolved_at TIMESTAMPTZ NULL
reopened INTEGER NOT NULL DEFAULT 0, occurrences INTEGER NOT NULL DEFAULT 1 CHECK (> 0)
first_seen_at, last_seen_at TIMESTAMPTZ NOT NULL
CHECK ((state = 'open') = (resolved_at IS NULL))
CHECK (state <> 'dismissed' OR kind IN ('event_undecided','provider_refund','provider_state_unresolved'))
CHECK (state <> 'resolved' OR kind NOT IN (<critical and money kinds>) OR resolution_outcome IS NOT NULL)
CHECK (kind <> 'entitlement_unsynced' OR state = 'open'
       OR (resolution_outcome = 'entitlement_synced' AND resolved_by = 'reconciler'))
CHECK (state = 'open' OR kind NOT IN (<money kinds>) OR resolution_outcome <> 'obligation_waived'
       OR resolution_note IS NOT NULL)
CHECK (resolution_outcome IS NULL OR resolution_outcome IN
       ('entitlement_synced','payment_recorded','payment_matched','refund_confirmed','reversal_confirmed',
        'obligation_waived','recorded'))
INDEX (state, kind, first_seen_at); INDEX (gateway) WHERE state = 'open'; INDEX (incarnation_id)
TRIGGER: no DELETE; no UPDATE of kind/gateway/dedupe_key or of any provider-fact column; a terminal row changes only
         occurrences/last_seen_at, or reopens (critical kinds only: state -> 'open', reopened + 1, resolution
         columns cleared)
```

The exact allowed outcome for each kind (the table in §4.2) is checked by the repository and by the resolve route.
The CHECKs above are the database's backstop for the safety-critical rules.

No change to 0006 or 0007, to any learner table, or to 0028.

## 6. Rollback implications

- **Before any real payment** (sandbox only): `downgrade()` drops both tables, the triggers and the sequence. It
  first **refuses** if either table holds a row, so a rehearsal can go down and up, but Alembic can never drop a
  runtime's financial records.
- **After real payments:** the schema is never downgraded. Rollback means rolling back the code: the tables are
  additive, and the earlier code ignores them while `BILLING_ENABLED` is off. No automated deletion until a
  retention/legal policy exists (H7).
- **Code rollback with billing on** is not supported. Billing must be switched off first (`BILLING_ENABLED=0`).
  Webhooks then answer 503 `billing_off`, Polar retries for a while, and the pull catches up on payOS when billing
  is back on.
- **Promotion** follows H1. Promoting 0027 never forces 0028.

## 7. Implementation slices (only after the design is APPROVED)

1. 0027 revision 2 (or the follow-up revision, H2), plus the item repository (idempotent upsert, per-kind
   resolve, reopen), plus trigger and CHECK tests.
2. The webhook outcome mapping (§4.3): the item is written before the answer, and a failed write answers 503.
3. The gap detector, repair and auto-resolution (§4.4), and the readiness `reconciliation_critical` blocker.
4. The reconciler: the session lock, short transactions, expiry, and the payOS pull behind a gateway interface
   (fake in tests), with backoff, horizon, rate limit and the confirming lookup.
5. Polar refund matching (§4.6).
6. The admin API (§4.7).

Everything stays in Billing files: `billing/`, `persistence/billing_repository.py`, `billing_api.py`, the
proposed 0027, tests, and the start-up wiring in `app.py`. Credits (PR-MON-4) and UI are out of scope, and #160 is
not touched.

## 8. Test and rehearsal plan (throwaway PostgreSQL 16 only)

- **Migration:**
  - head 0026 + 0027 revision 2: upgrade, downgrade (empty), upgrade;
  - downgrade refused with a row in either table;
  - the order trigger refuses a DELETE;
  - the item trigger refuses a DELETE and changes to identity or fact columns;
  - every CHECK is probed, including: `entitlement_unsynced` cannot be resolved by an administrator or dismissed;
    a money kind cannot be dismissed or resolved without an outcome; `obligation_waived` without a note is
    refused;
  - 0028 on top of 0027 still applies.
- **P1-1:**
  - a verified payOS payment for an order code absent from the database gives one `payment_unknown_order` with
    `reported_order_code` kept and no foreign key involved;
  - the webhook answers 200 only after the commit;
  - a replay gives the same row with `occurrences = 2`.
- **P1-2:**
  - the last lookup before `expires_at` fails (timeout or 429), the order expires locally, a later tick reads PAID,
    and the payment is recorded and access granted, with no webhook at all;
  - an `EXPIRED` or unknown status keeps the order in the pull set;
  - the horizon opens `provider_state_unresolved`, and the daily lookups continue.
- **P1-3:**
  - an administrator's resolve or dismiss of `entitlement_unsynced` gives 409 at the route and is refused by the
    database;
  - an open critical item makes its gateway not ready, so checkout answers 503 `billing_not_ready`, while webhooks
    and the reconciler still run;
  - repair auto-resolves the item and readiness returns;
  - a re-detection reopens it.
- **P1-4:**
  - two reconcilers at once give one tick;
  - no transaction is open during the fake payOS call (asserted from `pg_stat_activity` / `pg_locks` inside the
    fake);
  - the lock is released after an exception and after the connection is killed.
- **Idempotency:**
  - webhook then pull, and pull then webhook, give one payment;
  - two different known references give `payment_not_payable`;
  - an overpayment seen by the confirming lookup gives `payment_mismatch`.
- **Crash injection:** `mark_paid` commits, then `sync_prepaid` raises. The webhook answers 503, and the tick
  repairs the gap with no redelivery.
- **Rate limit:** a 429 stops the step with no item opened, and the backoff is respected.
- **Regression:** every PR-MON-1 and PR-MON-2 Billing and entitlement test, plus every `tests/*_postgres.py` (the
  one failure, #160, is inherited).
- **Mutations:** remove each of the following, and each removal must fail tests:
  - the write-before-ack;
  - the gap repair;
  - expired orders in the pull set;
  - the critical readiness blocker;
  - the per-kind resolve rule;
  - the session lock;
  - the downgrade guard;
  - each trigger.
- **No shared runtime:** nothing runs on :8000, :8010 or :8021, and 0027 is applied nowhere outside a throwaway
  database.

## 9. Human decisions (as decided by the review, 2026-10-14)

| # | Decision | Status |
| --- | --- | --- |
| H1 | Promotion order of 0027/0028 | **Decided.** Revision numbers are not the order. At promotion: read the real Alembic head; parent the revision on the current head; one financial or content migration enters the chain at a time; the lane that promotes later re-parents its own revision. Billing never edits Reading's files. |
| H2 | Revise the never-applied 0027 in place | **Conditional approve.** Only after the operator's confirmation in §5. Otherwise a new revision. The lane does not query shared runtimes. |
| H3 | payOS pull | **Decided, yes.** Billing on, valid keys, through the gateway interface, timeout, rate limit and backoff, sandbox verification before production. |
| H4 | Polar refund revokes access at once? | **Decided, no.** Access follows Polar's subscription lifecycle. Every refund is recorded durably. |
| H5 | Order TTL of 30 min, sent to payOS as `expiredAt` | **Decided.** The TTL is never the point at which Orena stops looking for a payment (§4.5). A verified late payment wins. |
| H6 | Admin resolve with audit; resolving moves no money | **Decided, with the per-kind rules of §4.2.** Admin only, note required, and no implicit charge, refund, grant or revoke. |
| H7 | Retention | **Decided.** No automated deletion in PR-MON-3 until a retention/legal policy exists. Minimal data: no raw payload, no email, no card data. |

Still the human's alone: the operator confirmation for H2; any price, credit or trial number; production keys;
activation; applying any migration to a shared runtime.

## 10. Risks

- **R-MON-002** is addressed by §4.2–4.5 once implemented.
- **R-MON-013** (narrowed by the review):
  - The reviewer reports that payOS's official documentation covers the payment-request lookup by
    `orderCode`/`paymentLinkId`, `expiredAt`, `amountPaid` and the statuses PAID, PENDING, PROCESSING and
    CANCELLED. The lane re-reads those pages at implementation.
  - The exact shape of the transaction reference, and any status outside that set (`EXPIRED` included), must be
    verified in the sandbox before production activation.
  - The idempotency model does not depend on them (§4.5).
- **Ops:** repeated webhook 5xx can make Polar disable the endpoint. The PR-MON-8 runbook adds an alert.
