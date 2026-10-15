# PR-MON-6 Cost-aware entitlement / Free trial / Credits fallback — design

**State: DESIGN revision 2, for a focused re-review.** There is no code and no migration file. Nothing is promoted
or applied. The schema this design needs is described in §11 as a future proposed revision. It is written only after
this design is APPROVED, and it goes through its own migration gate.

Revision 1 (`cd9f6ae3`) got REQUEST CHANGES (record:
`docs/reviews/architecture/PR_MON_6_COST_AWARE_ENTITLEMENT_REVIEW_2026-10-14.md`). Its architecture was accepted.
Revision 2 changes only:

- **P1-1:** feature access is checked before any cache or deterministic bypass (§4).
- **P1-2 / H-3:** credits-funded work settles its meter charge whichever rung served it. The zero-cost release is
  gone (§5.3, §7).
- **P1-3:** the funding-admission state machine, its serialization, crash recovery, decision snapshot and live
  funding at dispatch (§5.6, §2.1, §11).
- **P1-4:** the cost model aggregates per operation, and the margin gate runs per actual pack (§8).
- **Human decisions:** H-2 to H-6 closed; H-1, H-7 and H-8 stay off and get no values here (D-MON-023, §13).

Inspected on the lane branch after PR-MON-5 merged as #207 (`2aa3bd04`), 2026-10-14.

**Out of scope, and decided by no one here.** Every number:
- credit prices per meter (H-1);
- VND per credit, FX, margin floor and minimum evidence (H-7);
- promotional quantities, eligibility and validity (H-8);
- granularity and the Free/Plus/Pro limits of the new meters (H-2).

PR-MON-4/5 invariants stand: C1–C7, D-MON-020/021/022, and K1/K2/K5/K6. §12 lists where this design touches them.
No contradiction was found that reopens any of them.

## 1. What exists today (the facts the design builds on)

- **One quota gate:** `writing_coach/product/quota.py`.
  - Per-meter buckets (`commerce_quota_buckets`), plus reservations (`commerce_quota_reservations`, migration 0007).
  - A ticket lifecycle that is already reserve → dispatch → settle/release:
    - `Ticket.dispatch/settle/release`;
    - `settle` clamps actual to `[0, units]`;
    - an exception before dispatch releases; an exception after dispatch settles 0.
  - A reconciler for stale tickets, and fail-closed 503 behaviour.
  - Off by default (`ORENA_QUOTA_ENFORCEMENT` / `product.quota_enforcement`).
- **Wired meters** (catalogue `product/catalog.py`):
  - `writing.review`: per review, monthly;
  - `orena.message`: per message, daily; live voice charges 60 s chunks as messages;
  - `pronunciation.audio`: seconds, monthly, measured locally before dispatch;
  - `media.import`: source seconds, monthly, asynchronous, settled by operation id;
  - `languages.target`: a count cap.
  - Plans are `free` / `plus` / `pro`, with the limits in the catalogue.
- **Effective entitlement (PR-MON-1):** `product/entitlement.resolve()` gives the plan. Allowances come only from
  the catalogue `Plan.entitlements`.
- **Provider cost:**
  - `ai_cost_records` (migration 0026, per user account) holds estimated USD per successful **call**, by feature,
    provider and model, plus token and audio counts, and a `cost_state` (estimated / unpriced / partial / unknown).
  - `ai/pricing.py` is an exact-match USD price table.
  - `routing.provider_tier()` says local, free or paid.
- **Paid dispatch chokepoints:**
  - text goes through `platform.generate_structured()` (the chain, with `_budget_gate` skipping paid rungs);
  - the agent goes through `platform.stream_agent_turn()`;
  - non-text calls are ASR, pronunciation, the voice token mint, word TTS and media providers.
- **Unmetered today (R-MON-005):** ASR transcribe, translate, dictionary/word-detail AI, word-tap AI, Reading
  translate and summary, task generation, word TTS, Listening and speech evaluation. These have only rate limits and
  USD spend caps.
- **Credit ledger (PR-MON-4):**
  - `reserve(amount, operation_id, meter, operation_ref, ttl ≤ 30 min)`;
  - `settle(actual > 0)`, clamped to the hold. The excess is `uncharged` and never collected (C3);
  - `release` and `expire_reserve`;
  - `insufficient_credits` with the amount available;
  - `account_under_review` and `account_deleted`;
  - idempotency by operation id plus digest (meter, amount and ref differences are a `conflict`).
  - Off unless `CREDITS_ENABLED` is set and R-MON-014 holds.
  - Canonical lock order: incarnation `FOR SHARE` → credit account `FOR UPDATE`.
- **Nothing links quota and credits today.** Credits are never consumed.

## 2. The primary invariant, and where it is enforced

**I-1. No funded admission, no paid-provider call.** A paid-provider outbound request happens only for an operation
whose **durable** admission is `funded` (or `dispatched`) for that meter, and whose backing reservation is still
open at the moment of the request (§2.1). The backing reservation is either:
- a quota reservation (plan or promotional allowance), or
- a credit hold.

A paid-provider request is a `provider_tier = paid` rung, or any non-text provider with a price.

Enforcement is two layers. The first is the product layer; the second is the backstop.

1. **Admission at the feature** (§4, §5.6), before any provider work. This is where the learner is answered (403,
   429 and the options).
2. **The backstop at every paid chokepoint** (§2.1): `generate_structured` (per rung), `stream_agent_turn` (per
   model round), and each non-text paid client (per request).
   - A paid rung that fails the check is skipped, the same way `_budget_gate` skips a paid rung over budget, and the
     skip is logged as `unfunded_paid_skipped`.
   - When no unpaid rung remains, the call fails as `funding_required`.
   - A paid non-text request that fails the check is refused before it is sent.

**System-funded work** is never learner-funded and never silently free. This covers operator tests, configuration
checks, catalogue and prefetch generation, and media pipeline batches.
- It runs under an explicit `SystemFunding(reason)` context, distinct from any learner context.
- It is bounded by the existing USD caps (`AGENT_DAILY_SPEND_CAP_USD`, `WORD_TTS_SPEND_CAP_USD`, `media_spend`),
  which the backstop checks for it.
- A code path with neither learner funding nor system funding cannot reach a paid provider.

The backstop is switched by `FUNDING_ENFORCEMENT`, off by default.
- It is first log-only (`unfunded_paid_would_skip`).
- It is enforced only after every paid path has a meter (§6) or a system-funding declaration.
- Until then the existing spend caps remain the only brake on the unmetered paths, and R-MON-005 stays open.

### 2.1 `FundingContext` is a pointer, not funding

- **Created only after the commit.** A learner `FundingContext` is created only after the admission's durable state
  is `funded` (§5.6), and it carries only `(operation_id, meter, admission_digest)`.
  - It authorizes nothing by itself.
- **Live check before every paid outbound request.** The backstop does one indexed read that proves, at that moment:
  - the admission row exists, its digest matches the context, its meter matches the call's meter, and its state is
    `funded` or `dispatched`;
  - **its backing reservation is open:**
    - for a quota reservation: its state is reserved/dispatched (not settled, released or swept);
    - for a credit hold: it is not settled, released or expired, and `expires_at − now ≥ the call's provider timeout`.
      A hold that could expire mid-call does not authorize the call (the paid rung is skipped).
  - A context whose operation was settled, released, expired or reconciled therefore fails closed, even if it is
    still alive in memory.
- **The first paid request** moves the admission `funded → dispatched` (and the quota ticket's `dispatch`), in its
  own short transaction, before the request is sent.
- **Propagation and cleanup:**
  - The context lives in a `contextvars.ContextVar`, set by a context manager around the admitted operation. It is
    reset in `finally`, so it never outlives the operation, including on exceptions.
  - **Threads.** `contextvars` does not cross into a thread pool or a new thread by itself. Work handed to a worker
    goes through one helper, `run_funded(fn)`, which copies the *current* context explicitly. A thread started any
    other way sees no context and therefore cannot reach a paid provider (fail closed, logged).
  - **Async and streaming.** asyncio tasks inherit a copy at creation, and the generator that streams an agent turn
    runs inside the operation's context manager. The live check runs before each model round, so a stream that
    outlives its hold (TTL, settlement) stops at the next round.
  - **No reuse.** A context names one operation id. A second operation needs its own admission. Reuse after
    settlement fails the live check, because the state is terminal.
- `SystemFunding` is a separate context type. It never satisfies a learner check, and a learner context never
  satisfies a system check.

## 3. What a credit is

**A credit is a unit of metered work, not of money and not of provider cost.**
- Each credit-eligible meter has a configured **credit price per meter unit** (H-1, no values yet).
- A learner's credits buy that meter's units at that price. The charge is decided at admission from the meter and
  the units, snapshotted (§5.6), and **does not depend on which rung — local, free or paid — served the work**
  (H-3, closed).

Why this unit:
- **Stable to the learner.** An action costs the same credits whichever rung served it, so the UI can state the
  cost before the action (§10).
- **No reusable-credit loop.** A credits-funded operation always consumes its charge when it produces a result, so
  "reserve, get served for free, release, repeat" cannot happen (P1-2).
- **Separate from provider cost.** This is required by `ORENA_COMMERCE_ARCHITECTURE.md` ("commercial quota and
  provider token usage are separate ledgers with explicit unit mapping"). Provider cost is recorded and aggregated
  per operation (§8), which keeps the meter prices honest.
- **Integer only,** as in PR-MON-4. The seconds meters are priced per whole started unit of their configured
  granularity (H-2).

## 4. Feature access, then bypass, then funding (admission order)

For an operation with meter `m` and requested units `n` (the reservation upper bound, §5.2):

```
1. FEATURE ACCESS   meter m disabled by the effective plan        -> 403 feature_not_in_plan
                    (regardless of cache, deterministic result, allowance or credit balance)
2. BYPASS           deterministic / stored / cached result ready  -> served; no admission; 0 allowance, 0 credits
3. ALLOWANCE        included allowance covers n                   -> quota reservation (source = allowance)
                    included = promotional grants (earliest expiry first), then the plan window bucket
4. CREDITS          m credit-eligible (H-1 price approved and the cost gate passes, §8),
                    credits ready (CREDITS_ENABLED + R-MON-014),
                    account active and not under review,
                    available >= price(m) * n                     -> credit hold (source = credits)
5. REFUSE           otherwise                                     -> 429 quota_exhausted, reason + options (§9)
```

Feature access is separate from the funding requirement (P1-1). Step 1 runs first and reads only the effective
entitlement. A plan-disabled meter is refused before any cached or deterministic answer is returned.

Rules:
- **Credits never unlock a feature (H-4, closed).** They extend usage only of meters the effective plan enables. There
  is no `credit_unlocks_feature` setting in v1.
- **One source per operation.** An operation is funded wholly by the allowance or wholly by credits, never split.
  - For continuous work (voice), each chunk is its own operation, so a session moves from allowance to credits at a
    chunk boundary, without a split.
- **Allowance always comes first.** Credits are never consumed while included allowance covers the operation. A
  setting to prefer credits is not offered in v1.
- **Promotional before plan, earliest expiry first** (when grants exist; none in PR-MON-6, H-8).
- **A Free account** may hold and use credits on Free's enabled meters.
- **Failure modes:**
  - quota unavailable → 503 `quota_unavailable` (as today);
  - credits not ready → step 4 is skipped, never an error. The answer is then step 5 with reason
    `credits_unavailable`.

## 5. Lifecycle of paid AI work

```
admit (lock admission, choose source, reserve upper bound, snapshot) -> commit
  -> [dispatch: live check (§2.1), provider call, no transaction]
  -> settle from the snapshot | release
```

No transaction spans a provider call (PR-MON-4 §5). Every step is its own short transaction.

### 5.1 Reserve

- **Quota:** the existing `Ticket` reservation.
- **Credits:** `reserve(amount = snapshot.price_per_unit * n, operation_id = "fund:" + operation_id, meter = m,
  operation_ref, ttl)`.
  - `operation_ref` is the feature's own reference: review id, agent turn id, voice chunk id, pronunciation attempt
    id.
  - `ttl` is the meter's configured hold TTL, at most `HOLD_TTL` (30 min).
- Both backing reservations carry a key derived only from the operation id, so the admission can always find its
  exact backing reservation (§5.6).

### 5.2 Upper bound per meter (no overrun by construction)

| Meter | Units known before dispatch? | Hold |
| --- | --- | --- |
| `writing.review` | yes, 1 | `price × 1` |
| `orena.message` (text turn) | yes, 1 | `price × 1` |
| `orena.message` (voice chunk) | yes, one chunk of `voice_seconds_per_message` | `price × 1` per chunk |
| `pronunciation.audio` | yes, measured locally before dispatch | `price × ceil(seconds / granularity)` |
| new metered paths (§6) | yes, by their frozen unit | `price × units` |
| `media.import` (async, up to 6 h) | yes, source seconds | **allowance only (H-5, closed)** |

- Because the charge is in meter units, the actual can never exceed the hold. Settle is `price × actual_units`,
  with `actual_units ≤ units` and the price from the snapshot.
- C3's clamp stays as a backstop; it never fires by design.
- Provider-cost variance (tokens, extra rounds, fallbacks) is Orena's margin risk, not the learner's. It is measured
  per operation (§8).

### 5.3 Settle / release

Before admission, a deterministic, stored or cached result costs nothing (step 2). **After admission**, every outcome
that gives the learner a result settles, whichever rung or source produced it (H-3).

| Outcome after admission | Allowance (quota) | Credits |
| --- | --- | --- |
| a result was produced (paid, free or local provider, or a cache entry that appeared after admission, e.g. single-flight) | settle actual units | settle `snapshot.price × actual_units` |
| provider failed / error before any result | settle 0 (as today) | release |
| timeout with unknown provider outcome | settle 0 | release |
| client cancelled **after** a result was produced (agent: a model round ran) | settle actual units (as today) | settle |
| client cancelled before dispatch | release | release |
| crash: the reservation was never settled | quota reconciler, `quota.abandoned_settles = admitted` (H-6, closed) | `expire_reserve` at TTL = release, never a charge (C7) |
| settle arrives after the hold expired | — | `reservation_closed` + `credit_late_settle` item (PR-MON-4), not collected |

- **Credits are never charged for work the learner did not receive.** Abandonment releases or expires them.
- **The allowance settles abandonment as admitted** (H-6). The asymmetry is deliberate: a credit is money the
  learner paid.

### 5.4 Retry and idempotency

- **One operation id per admitted operation.** It is client-supplied where the API already takes one (an
  idempotency header on write routes); otherwise it is server-generated and returned.
- **The admission digest (P1-3.1).** It is sha256 over the canonical JSON, built like PR-MON-4's `digest()`, of:
  - `incarnation`, `operation_id`, `meter`, `units`, `operation_ref`;
  - `feature` (the route or capability that admitted it);
  - `unit_granularity`.
  - It holds the request's intent, not the decision: price and source are snapshot fields (§5.6), never inputs.
  - Same operation id with the same digest → the same admission. Same operation id with a different digest → **409
    `operation_conflict`**, with nothing reserved.
- **A retry never chooses again.** It reuses the snapshot's source and amount, never a second reservation and never
  a switch from allowance to credits.
- **On a terminal admission:**
  - `settled`: the route's stored result where the feature stores one; otherwise 409 `operation_completed`;
  - `released` or `refused`: 409 `operation_closed`. The client starts a new operation id, which is a new admission
    under the current policy.
- **Settle and release are idempotent** per operation id (PR-MON-4, and quota tickets).

### 5.5 Asynchronous meters

`media.import` runs up to 6 h, longer than any credit hold (30 min). It is **allowance-only** (H-5, closed). There is
no settle-at-acceptance-and-refund credit model.

### 5.6 The funding-admission state machine (P1-3)

**States:**

```
admitting --(source chosen, backing reservation written)--> funded --(first paid request)--> dispatched
admitting --(no source: 403/429, or proven unbacked, see recovery)--> refused
funded | dispatched --(result)--> settled
funded | dispatched --(failure, cancel, timeout, hold expiry, quota sweep)--> released
```

`settled`, `released` and `refused` are terminal. A terminal row is never reopened, and its operation id never funds
again.

**Snapshot.** Everything settlement and retry need is written in the admission row in the transaction that makes it
`funded`, and is immutable after that (P1-3.4):
- `source` (`allowance` / `promotional:<grant>` / `credits`);
- `units`;
- `price_per_unit` (credits) and `amount_reserved`;
- `unit_granularity`;
- `policy_version`: the catalogue revision, the meter-price configuration revision, and the cost-gate result id;
- the backing reservation id: `quota_reservation_id` or `credit_reserve_entry_id`.

Settlement computes the charge only from these fields. A later H-1 price, catalogue or policy change never touches an
admitted operation.

**Serialization (P1-3.2).**
- `funding_admissions.operation_id` is unique.
- The admission transaction:
  1. inserts the row `ON CONFLICT (operation_id) DO NOTHING`;
  2. takes it `FOR UPDATE`;
  3. compares the digest (409 on a mismatch);
  4. if the row is not `admitting`, returns its snapshot. Otherwise it chooses the source and writes the backing
     reservation **in the same transaction**, and sets `funded` with the snapshot.
- A concurrent request with the same operation id waits on that row lock, then sees `funded` and its snapshot. Two
  sources can never be reserved.
- **Canonical lock order:** `funding_admissions → account_incarnations (FOR SHARE) → quota bucket | credit account
  (FOR UPDATE)`.
  - This extends PR-MON-4's order (incarnation → credit account) at the front.
  - Paths that do not touch admissions (top-up, refund, deletion) keep their order and never wait on an admission
    while holding an incarnation lock, so no cycle exists.
  - The admission reconciler takes the admission row first, as well.
- **One-transaction precondition.** The quota and credit tables live in the same PostgreSQL database as
  `funding_admissions`. The migration gate verifies this on the deployed topology. If a deployment ever separated
  them, the two-phase path below is the contract, not a fallback chosen at runtime.

**Crash and race recovery (P1-3.3).** Each case says how a retry (same operation id) and the reconciler converge. No
case can create a second source.

| Crash point | What is durable | Retry / reconciler |
| --- | --- | --- |
| admission row committed, no reservation | one transaction makes this impossible. Two-phase topology only: `admitting`, nothing else | under the row lock, look up the exact backing reservation by its operation-id key in **both** stores. Found and exact → adopt (below). Proven absent → the retry continues admission; the reconciler moves it to `refused` only after the hold TTL **and** only with that proof made under the row lock |
| reservation committed, crash before the row is linked or `funded` | one transaction makes this impossible. Two-phase only: an open reservation keyed `fund:<op>` | **adopt:** verify the reservation exactly (meter, amount, ref and digest of the credit reserve; meter, units and key of the quota reservation), write the snapshot from it, set `funded`. A non-exact reservation is never adopted: the row goes to `refused`, the stray reservation is released by its own owner path, and a `funding_admission_conflict` reconciliation item is opened |
| `funded`, crash before dispatch | `funded` + open reservation | retry: the live check passes while the hold is open, so dispatch proceeds. Hold expired or quota swept: the reconciler moves the row to `released`, and the retry gets 409 `operation_closed` |
| settle or release committed, crash before the admission state update | the credit `settle`/`release` or quota settle is in the same transaction as the admission state change, so this cannot happen. Two-phase only: the ledger or quota reservation is closed while the row is `funded` or `dispatched` | the reconciler reads the backing reservation's terminal state and completes the row (`settled` or `released`), copying its amounts. It never re-settles |
| hold expired by PR-MON-4's `expire_reserve` while the row is `funded` or `dispatched` | expiry entry | the reconciler moves the row to `released`. A late settle gets `reservation_closed` (not collected) |

## 6. Meter model

- **Reuse the five meters.** For each, add configuration (not code):
  - `credit_price` (H-1, no values);
  - `credit_eligible`: v1 allows `writing.review`, `orena.message` and `pronunciation.audio`; never `media.import`
    (H-5) or `languages.target`;
  - `hold_ttl`;
  - `granularity` for the seconds meters (H-2).
- **Close R-MON-005.** Each paid path that is unmetered today gets a meter, with its unit **frozen** (H-2, closed):

| Meter | Unit | Paths |
| --- | --- | --- |
| `speech.transcribe` | second | `/api/speech/transcribe` (cloud ASR) |
| `reading.assist` | request | Reading translate/summary, contextual explain (`media_interaction`), `/api/translate` |
| `word.assist` | request | dictionary / word-detail AI and word-tap AI |
| `writing.task` | request | `/api/tasks/generate` |
| `speech.evaluate` | second | `/api/speech/evaluation` |
| `audio.tts` | character | word TTS on a learner request; pre-generated catalogue audio is system-funded |

- A new meter is **not enforced** until its granularity and its Free/Plus/Pro limits are approved (H-2). Until then
  its path keeps today's brakes, and is skipped as unfunded once `FUNDING_ENFORCEMENT` is on.
- Feature access (step 1) applies to every meter, old and new.

## 7. Deterministic / cache / local / free-provider paths (H-3, closed)

The chain order is `deterministic → cache → local → free → paid` (BILLING_LANE). PR-MON-7 owns the routing; this PR
owns the funding.

| What serves | When it is decided | Allowance | Credits |
| --- | --- | --- | --- |
| deterministic, stored result, result cache | **before** admission (step 2), after feature access (step 1) | 0 | 0 |
| local (Ollama, local ASR) | after admission | settle actual | settle `snapshot.price × units` |
| free provider model | after admission | settle actual | settle `snapshot.price × units` |
| paid provider | after admission, live check passed | settle actual | settle `snapshot.price × units` |

- Every operation that needs a provider of **any** tier is admitted.
- The credit charge never depends on the rung (H-3). Only work completed before admission is free.
- **D-MON-001 holds.** Zero-price AI is metered; with the allowance exhausted it needs credits, or it is refused.
- The paid rung additionally needs the live check (§2.1). A free or local rung does not call a paid provider, so it
  needs only the admission.

## 8. From provider cost to meter price (the cost model, P1-4)

No VND, FX, margin or credit value is invented. The system supplies operation-level evidence and a consistency gate;
the human supplies the numbers (H-1, H-7).

**Attribution.** Each `ai_cost_records` row written inside a `FundingContext` or a `SystemFunding` carries
`operation_id` and `meter` (nullable columns, §11). A call without them is **unattributed**: it is counted and
reported, never folded into a meter.

**Aggregate first by operation, then per unit.**

```
op_cost(operation_id, meter) = SUM(cost_usd of all attributed calls of that operation)
                                -- every model round, fallback and paid call of one learner operation
op_units = the admission's settled units
cost_per_unit(op)  = op_cost / op_units        (only for settled operations with op_units > 0)
```

**Evidence quality.**
- An operation is **complete** only if every attributed call has `cost_state = estimated` with a price, or a
  zero-price local/free call.
- An operation with any `unpriced`, `unknown` or `partial` billable call is **incomplete**. It is never counted as
  USD 0, and it is excluded from the percentiles but counted in the quality ratio.
- `quality(m) = complete operations / settled operations`.

**Statistics per meter** (`GET /api/admin/billing/cost-model`, a read; no new storage beyond §11's two columns):
- p50 / p95 / max of `cost_per_unit` over **paid-reaching** complete operations (those with at least one paid call).
  This is the gate's input.
- The same over all complete operations, for information.
- The zero-cost share: the operations served wholly by local or free rungs, reported separately and never blended
  into the paid p95.
- Counts: settled, complete, incomplete and unattributed calls.

**The gate, per actual pack.** For every configured pack `p` and every credit-eligible meter `m` that the pack's
credits may fund:

```
effective_vnd_per_credit(p) = p.amount_minor / p.credit_units
credit_price[m] * effective_vnd_per_credit(p)
      >=  p95_paid_usd_per_unit[m] * fx_usd_vnd * (1 + margin_floor)
and   complete_paid_ops(m) >= N   and   quality(m) >= Q
```

- A pack is offered only if it passes for **every** credit-eligible meter. Rounding and discounts are judged on the
  pack's real economics, never on an abstract global rate.
- A meter is credit-eligible only with an approved price (H-1) **and** at least one sellable pack under which it
  passes. With no approved inputs, nothing is credit-eligible and no pack is offered.
- `fx_usd_vnd` is a configured, auditable value with its source and date (H-7). It is never fetched live during
  admission or offering.
- The gate can only remove a pack from sale or a meter from credits (K1, K5); it never adds one.
- The gate's result is versioned (`cost_gate_id`) and snapshotted into each credits admission (§5.6), so an
  admitted operation is never re-judged.

## 9. Insufficient funding: the answer

There is still one status for "cannot fund this", **429 `quota_exhausted`**, so existing clients keep working. The
body is extended:

```json
{"error": "quota_exhausted", "meter": "writing.review",
 "reason": "allowance_exhausted | insufficient_credits | credits_unavailable | not_credit_eligible",
 "allowance": {"remaining": 0, "limit": 10, "window_resets_at": "..."},
 "promotional": [{"grant": "...", "remaining": 0, "expires_at": "..."}],
 "credits": {"available": 40, "needed": 60, "price_per_unit": 60},
 "options": ["upgrade", "buy_credits"]}
```

- `buy_credits` is listed only while `credit_offers()` is non-empty **and** the meter is credit-eligible.
  `upgrade` is listed only while a higher plan includes more of the meter.
- `feature_not_in_plan` stays a 403 (step 1).
- Nothing is charged, and no provider is called.

## 10. What PR-MON-9 (UI) needs

All of it is read-only and server-computed, so the UI never does arithmetic on prices:

- **`GET /api/billing/funding`:** per meter:
  - enabled by the plan;
  - allowance remaining, limit and window reset;
  - promotional grants remaining and their expiry;
  - credit-eligible, and the price per unit;
  - credits available and held.
- **`GET /api/billing/estimate?meter=&units=`** (pre-flight, no reservation):
  - which source would fund the operation;
  - credits needed;
  - whether it would be refused, and why (403 or the §9 reasons).
  - This is what "this will use 2 credits" is drawn from.
- **Recent consumption:** ledger entries carry `meter` and `operation_ref`, which become a feature label and a time.
  Settled, released and uncharged amounts are shown truthfully.
- **Refusal body** as in §9.
- No redesign: the Billing Sheet is wired in PR-MON-9.

## 11. Schema needed (described here; written only after approval, under its own migration gate)

- **`funding_admissions`:**
  - Identity and intent: `operation_id` (unique), `incarnation_id`, `meter`, `units`, `operation_ref`, `feature`,
    `unit_granularity`, `request_digest` (immutable; §5.4).
  - Snapshot, immutable once `funded`: `source`, `price_per_unit`, `amount_reserved`, `policy_version`,
    `cost_gate_id`, `quota_reservation_id`, `credit_reserve_entry_id`.
  - Lifecycle: `state` (`admitting` / `funded` / `dispatched` / `settled` / `released` / `refused`),
    `settled_units`, `settled_amount`, and timestamps.
  - Database guards, the same style as PR-MON-3/4:
    - `CHECK`s on the state × snapshot shape (`funded` and after require a source and exactly one backing id that
      matches the source; credits require a price and an amount);
    - a trigger that keeps the identity, intent and snapshot immutable, and allows only the forward transitions of
      §5.6;
    - a terminal state is final.
- **`promotional_grants`** and **`promotional_grant_usage`** (contract only; no grants configured, H-8):
  - A grant definition is configuration (id, meters and units, eligibility, `valid_days`). The default is none.
  - A grant **instance** belongs to an identity that survives delete-and-re-register (R-MON-003): the `users` row's
    sign-in subject, not the incarnation.
    - Unique `(grant_id, identity)`, so a grant is claimed once per identity, ever.
    - Its usage is reserved and settled like a quota bucket.
  - Hashing the identity, and what deletion keeps, are part of that migration's review (they touch account deletion,
    a human gate).
- **`ai_cost_records`:** add nullable `operation_id` and `meter` (§8).
- Whether these extend 0007's quota tables or stand alone is decided in the migration gate. The rule is that the
  existing quota system is extended, not replaced.

## 12. Interaction with PR-MON-4/5 contracts

- **Credit operations** are exactly PR-MON-4's `reserve` / `settle` / `release` / `expire_reserve`. There is no new
  kind and no new ledger path.
  - Integer amounts, the C3 clamp, `HOLD_TTL ≤ 30 min`, C7 expiry, the `account_under_review` / `account_deleted`
    refusals and the R-MON-014 readiness all apply unchanged.
  - The lock order is extended only at its front (§5.6).
- **The credits step is absent** unless `CREDITS_ENABLED` is set, the privilege check is clean, H-1 has a price for
  the meter, and the cost gate passes. The allowance path never depends on it.
- **K1/K2/K5/K6 unchanged.** The cost gate (§8) can only remove a pack from sale.
- **C1** (no credit on a deleted account) is mirrored: a deleted account is never admitted.

## 13. Human gates and decisions (D-MON-023)

| Id | Decision | State |
| --- | --- | --- |
| H-1 | `credit_price` per meter | **OFF.** No production prices; contract only. A meter's credits step stays unavailable until its price is approved |
| H-2 | units of the new meters | **CLOSED:** `speech.transcribe` second, `reading.assist` request, `word.assist` request, `writing.task` request, `speech.evaluate` second, `audio.tts` character. Granularity and Free/Plus/Pro limits stay human gates; no new meter is enforced before them |
| H-3 | do zero-cost rungs charge credits | **CLOSED:** credits pay for metered work, not provider cost. Credits-funded work settles its meter charge whatever served it; only deterministic/stored/cache work completed before admission is free |
| H-4 | do credits unlock plan-disabled features | **CLOSED: no** (v1) |
| H-5 | `media.import` on credits | **CLOSED: allowance only;** no settle-at-acceptance + refund |
| H-6 | `quota.abandoned_settles` | **CLOSED: `admitted`,** for the allowance only. Credit abandonment releases or expires (C7) |
| H-7 | VND per credit, FX, margin floor, minimum evidence N and Q | **OFF, not invented.** The report and gate are built first; no pack is sellable until approved. FX is a configured, auditable reference, never live |
| H-8 | promotional / new-user grants | **OFF.** Configuration, storage, claim and anti-reclaim contract only; default no grants |

## 14. Rollout (each step behind a switch, off by default)

1. The migration gate for §11. Proposed revision 0034 or later, tested on throwaway PostgreSQL. Promotion and
   application are human gates.
2. The admission state machine, the funding context and the allowance path. No behaviour change while quota
   enforcement is off. `quota.abandoned_settles = admitted` (H-6).
3. Attribution columns and the cost-model report (§8). Read-only.
4. The new meters (§6), not enforced before H-2's limits. The chokepoint backstop with `FUNDING_ENFORCEMENT`,
   log-only first (`unfunded_paid_would_skip`).
5. The credits step: inert until `CREDITS_ENABLED`, R-MON-014, an H-1 price and the H-7 inputs for the gate.
6. Promotional grants: the contract only, inert until H-8.

## 15. Tests the implementation must carry

- **Feature access first (P1-1):**
  - a disabled meter with a cache hit → 403;
  - a disabled meter with a deterministic result → 403;
  - an enabled meter with a cache hit → the result, with no admission and no allowance or credits consumed;
  - a disabled meter with credits available → 403.
- **H-3 (P1-2):**
  - a credits-funded operation served by a local rung settles `price × units`;
  - the same served by a free rung settles it;
  - the same served by a paid rung settles the same amount;
  - a cache entry appearing after admission settles;
  - a repeated "exhausted allowance → credits → zero-cost rung" loop consumes credits each time, until
    `insufficient_credits`.
- **The admission state machine (P1-3), PostgreSQL:**
  - same operation id: N concurrent requests produce exactly one reservation and one source;
  - same operation id with a different digest → 409, nothing reserved;
  - a retry after `funded` reuses the snapshot, even after an H-1 price change in between;
  - a terminal admission → 409 `operation_closed` / `operation_completed`;
  - injected crashes at each §5.6 crash point (two-phase harness): convergence with one source;
  - a non-exact stray reservation is not adopted; the conflict item opens;
  - an `admitting` row is refused only with proof of no backing reservation.
- **The live check (P1-3.5):**
  - a paid rung with a context whose hold expired → skipped, with zero outbound requests (fake transport);
  - the same after settlement or release;
  - the same with a remaining TTL shorter than the provider timeout;
  - a thread started without `run_funded` → no paid call;
  - the context does not leak to the next operation on the same thread or task;
  - a streaming turn stops paid rounds once its hold closes;
  - `SystemFunding` is allowed and capped, and never satisfies a learner check.
- **The cost model (P1-4):**
  - an operation with three paid calls is one operation-level cost;
  - an unpriced billable call makes its operation incomplete (never USD 0);
  - p95 over paid-reaching operations is not lowered by zero-cost operations;
  - a pack whose rounding lowers `effective_vnd_per_credit` below the floor for one meter is not offered, while
    another pack is;
  - thin evidence or low quality → not credit-eligible;
  - no H-1/H-7 inputs → no meter credit-eligible, no pack offered.
- **The funding order:**
  - allowance before credits;
  - promotional before plan, by expiry (with test grants only);
  - one source per operation.
- **Credits:**
  - reserve upper bound; settle actual ≤ hold, priced from the snapshot;
  - release on failure, timeout, or cancel before dispatch;
  - TTL expiry releases;
  - a late settle is not collected.
- **Concurrency (PostgreSQL):** N parallel admissions on the last allowance unit and on the last credits never
  exceed either.
- **Refusal body (§9):** `options` lists only what can actually be done.
- **Promotional grants:** one claim per identity across delete-and-re-register (R-MON-003); expiry; none by default.
- **Mutation tests** on the access order, the funding order, the live check, the digest, the snapshot and the
  per-pack gate.
