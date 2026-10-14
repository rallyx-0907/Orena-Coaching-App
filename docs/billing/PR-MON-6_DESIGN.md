# PR-MON-6 Cost-aware entitlement / Free trial / Credits fallback — design

**State: DESIGN revision 1, for architecture review.** There is no code and no migration file. Nothing is promoted or
applied. The schema this design needs is described in §11 as a future proposed revision. It is written only after
this design is APPROVED, and it goes through its own migration gate.

Inspected on the lane branch after PR-MON-5 merged as #207 (`2aa3bd04`), 2026-10-14.

**Out of scope, and decided by no one here.** Each item is a named human gate in §13, and none gets a default value:
- the price of a meter unit in credits;
- the VND value of a credit and the packs on sale (K1);
- Free, trial and promotional quantities;
- margin floors;
- `quota.abandoned_settles`.

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
  - `ai_cost_records` (migration 0026, per user account) holds estimated USD per successful call, by feature,
    provider and model, plus token and audio counts.
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
- **Nothing links quota and credits today.** Credits are never consumed.

## 2. The primary invariant, and where it is enforced

**I-1. No funded admission, no paid-provider call.** A call to a paid rung (`provider_tier = paid`, or any non-text
provider with a price) happens only inside an operation that holds a funded admission:
- a quota reservation (plan or promotional allowance), or
- a credit hold;

and only when that funding covers the operation's meter.

Enforcement is two layers. The first is the product layer; the second is the backstop.

1. **Admission at the feature** (§4), before any provider work. This is where the learner is answered (429 and the
   options).
2. **A funding check at every paid chokepoint.**
   - `generate_structured`, `stream_agent_turn` and each non-text paid client read the current operation's funding
     from a context variable set by the admission (`FundingContext`: operation id, meter and source).
   - A paid rung **without** funding is skipped, the same way `_budget_gate` skips a paid rung over budget, and the
     skip is logged as `unfunded_paid_skipped`.
   - When no unpaid rung remains, the call fails as `funding_required`.
   - A paid non-text call without funding is refused before the request is sent.

**System-funded work** is never learner-funded and never silently free. This covers operator tests, configuration
checks, catalogue and prefetch generation, and media pipeline batches.
- It runs under an explicit `SystemFunding(reason)` context.
- It is bounded by the existing USD caps: `AGENT_DAILY_SPEND_CAP_USD`, `WORD_TTS_SPEND_CAP_USD` and `media_spend`.
- A code path with neither learner funding nor system funding cannot reach a paid provider.

The backstop is switched by `FUNDING_ENFORCEMENT`, which is off by default, like quota.
- It is turned on only after every paid path has a meter (§6) or a system-funding declaration.
- Until then, the existing spend caps remain the only brake on the unmetered paths, and R-MON-005 stays open.

## 3. What a credit is

**A credit is a unit of metered work, not of money and not of provider cost.**
- Each credit-eligible meter has a configured **credit price per meter unit**, for example *k* credits per review,
  per message or per audio minute. The values are human gates (H-1).
- A learner's credits buy that meter's units at that price. The charge is decided at admission from the meter and the
  units, and it does not depend on which model or provider ran.

Why this unit:
- **Stable to the learner.** An action costs the same credits whichever rung served it, so the UI can state the cost
  before the action (§10). Charging live provider USD would make the price move with routing, retries and model
  drift.
- **Separate from provider cost.** This is required by `ORENA_COMMERCE_ARCHITECTURE.md` ("commercial quota and
  provider token usage are separate ledgers with explicit unit mapping"). Provider cost is still recorded per call
  (`ai_cost_records`) and drives the cost model in §8, which keeps the meter prices honest.
- **Integer only,** as in PR-MON-4. A meter unit's price is an integer number of credits, and the seconds meters are
  priced per whole started unit of their configured granularity (§5.2).

## 4. The funding order (admission)

For an operation with meter `m` and requested units `n` (the reservation upper bound, §5):

```
0. deterministic / cache path available          -> served, no admission, no charge (§7)
1. meter m not in the account's plan (enabled = false)
       and m not marked credit_unlocks_feature   -> 403 feature_not_in_plan
2. included allowance covers n                   -> quota reservation (source = allowance)
       included = promotional grants (earliest expiry first), then the plan window bucket
3. m is credit-eligible, credits ready (CREDITS_ENABLED + R-MON-014),
       account active and not under review,
       available credits >= price(m) * ceil(n)  -> credit hold (source = credits)
4. otherwise                                     -> 429 quota_exhausted, with the reason and the options (§9)
```

Rules:
- **One source per operation.** An operation is funded wholly by the allowance or wholly by credits, never split.
  Remaining allowance smaller than `n` stays for a smaller operation. A split would need two settlements and two
  refusal paths for one result, and it buys nothing a learner can see.
  - For continuous work (voice), each chunk is its own operation, so a session moves from allowance to credits at a
    chunk boundary, without a split.
- **Allowance always comes first.** Credits are never consumed while included allowance covers the operation.
  - A setting to prefer credits (a learner who wants to save the daily allowance) is not offered in v1.
- **Promotional before plan, earliest expiry first.** Grants expire; plan windows renew. Spending the expiring units
  first never costs the learner anything.
- **Plan × credits.**
  - Credits extend a meter the plan includes. They do not unlock a meter the plan disables, unless that meter is
    configured `credit_unlocks_feature` (H-4; default unset means no).
  - A Free account may hold and use credits on Free's enabled meters.
- **Failure modes:**
  - quota unavailable → 503 `quota_unavailable` (as today);
  - credits not ready → the credits step is skipped, never an error. The answer is then step 4 with reason
    `credits_unavailable`, or the allowance as usual.

## 5. Lifecycle of paid AI work

```
admit (reserve upper bound) -> commit -> [dispatch: provider call, no transaction] -> settle actual | release
```

No transaction spans a provider call (PR-MON-4 §5). Every step is its own short transaction.

### 5.1 Reserve

- **Quota:** the existing `Ticket` (`begin` / `admit`).
- **Credits:** `reserve(amount = price(m) * n_units, operation_id, meter = m, operation_ref, ttl)`.
  - `operation_ref` is the feature's own reference: review id, agent turn id, voice chunk id, pronunciation attempt
    id.
  - `ttl` is the meter's configured hold TTL, at most `HOLD_TTL` (30 min).
- **Funding record:** the admission is written in a `funding_admissions` row (§11) *before* the reservation, in the
  state `admitting`. It then moves to `funded(source, reservation id)` in the reservation's own transaction where the
  repository allows it, or in the next one.
  - This record makes a retry find its funding (§5.4), and lets settlement and the reconciler pair the two sides.

### 5.2 Upper bound per meter (no overrun by construction)

| Meter | Units known before dispatch? | Hold |
| --- | --- | --- |
| `writing.review` | yes, 1 | `price × 1` |
| `orena.message` (text turn) | yes, 1 | `price × 1` |
| `orena.message` (voice chunk) | yes, one chunk of `voice_seconds_per_message` | `price × 1` per chunk |
| `pronunciation.audio` | yes, measured locally before dispatch | `price × ceil(seconds / granularity)` |
| new metered paths (§6) | yes, by their defined unit | `price × units` |
| `media.import` (async, up to 6 h) | yes, source seconds | **allowance only in v1** (§5.5) |

- Because the charge is in meter units (§3), the actual can never exceed the hold. Settle is `price × actual_units`,
  with `actual_units ≤ units`.
- C3's clamp stays as a backstop; it never fires by design.
- Provider-cost variance (tokens) is Orena's margin risk, not the learner's. The cost model (§8) controls it with
  per-meter p95 and `max_tokens` caps.

### 5.3 Settle / release

| Outcome | Allowance (quota) | Credits |
| --- | --- | --- |
| served by deterministic/cache after admission | settle 0 (release) | release |
| provider returned a result | settle actual units | settle `price × actual_units` |
| provider failed / error before any result | settle 0 (as today) | release |
| timeout with unknown provider outcome | settle 0 | release |
| client cancelled **after** a result was produced (agent: a model round ran) | settle actual units (as today) | settle |
| client cancelled before dispatch | release | release |
| crash: hold never settled | quota reconciler, `quota.abandoned_settles` (unchanged, H-6) | `expire_reserve` at TTL = release, never a charge |
| settle arrives after the hold expired | — | `reservation_closed` + `credit_late_settle` item (PR-MON-4), not collected |

**Credits never charge for work the learner did not receive.** Abandonment releases credits; it never charges them.
The quota side keeps its pending human decision (H-6). The asymmetry is deliberate: a credit is money the learner
paid.

### 5.4 Retry and idempotency

- **One operation id per admitted operation.**
  - It is client-supplied where the API already takes one (an idempotency header on write routes), otherwise
    server-generated and returned.
  - A retry with the same id:
    - re-reads `funding_admissions` and reuses the same funding (never a second hold, never a switch from allowance to
      credits);
    - the credit reserve returns `duplicate` (same digest) or `conflict` (different meter, amount or ref: refused 409
      `operation_conflict`).
- **Settle and release are idempotent** per operation id (PR-MON-4).
  - A settle after a release returns `reservation_closed`. A second settle is a `duplicate`.
- **A result served from the result cache on a retry** releases the retry's own admission, if it made one.

### 5.5 Asynchronous meters

`media.import` runs up to 6 h (`ASYNC_RECONCILE_AFTER`), longer than any credit hold (30 min). In v1 it is
**allowance-only**: not credit-eligible.

The alternative is to settle at acceptance and refund on failure (PR-MON-4 `refund`, capped). It is specified here but
not chosen (H-5), because it charges before the work is done.

## 6. Meter model

- **Reuse the five meters.** For each, add (configuration, not code) four settings:
  - `credit_price` (H-1);
  - `credit_eligible`: v1 is true for `writing.review`, `orena.message` and `pronunciation.audio`, false for
    `media.import` and `languages.target`;
  - `hold_ttl`;
  - `granularity` for the seconds meters.
- **Close R-MON-005.** Each paid path that is unmetered today gets a meter. This is a prerequisite for I-1's
  enforcement, not an option. Proposal, with the units fixed and the limits per plan as human gates:

| Proposed meter | Unit | Paths |
| --- | --- | --- |
| `speech.transcribe` | second of audio | `/api/speech/transcribe` (cloud ASR rung only; local ASR is free, §7) |
| `reading.assist` | call | Reading translate/summary, contextual explain (`media_interaction`), `/api/translate` paid rung |
| `word.assist` | call | dictionary / word-detail AI and word-tap AI paid rungs |
| `writing.task` | call | `/api/tasks/generate` |
| `speech.evaluate` | second | `/api/speech/evaluation` paid rung, if any |
| `audio.tts` | character or call (H-2) | word TTS on a learner request; pre-generated catalogue audio is system-funded |

- Every meter is admitted only **when its paid rung is the one that will run** (§7). A deterministic, cache or local
  answer never reaches admission.
- A path that is not yet migrated keeps its current brakes, and stays unfunded and therefore skipped once
  `FUNDING_ENFORCEMENT` is on.

## 7. Deterministic / cache / local / free-provider paths

The chain order is `deterministic → cache → local → free → paid` (BILLING_LANE). PR-MON-7 owns the routing; this PR
owns the funding.

| Rung that serves | Admission | Allowance | Credits |
| --- | --- | --- | --- |
| deterministic, stored result, result cache | none (checked before admission, as `writing.evaluate` already does) | 0 | 0 |
| local (Ollama, local ASR) | admitted against the allowance (D-MON-001: zero-price AI is still metered) | settle actual | **0 in v1 (H-3)** |
| free provider model | as local | settle actual | **0 in v1 (H-3)** |
| paid | admitted | settle actual | settle `price × units` |

- **When the chain is decided.** The admission sees the *maximum* rung the chain may reach for that operation.
  - If that maximum is local or free, the operation is admitted against the allowance only. With the allowance
    exhausted, it is refused (step 4); credits never fund a zero-price rung in v1 (H-3).
  - If the maximum is paid, the operation is funded as in §4.
  - After the call, settlement reads the rung that actually served:
    - a funded paid admission served by a free or local rung settles the allowance as admitted;
    - a credit hold served by a free or local rung is **released**, charged 0 credits (H-3 may set a near-zero price
      instead).
- So a credits-only learner never pays credits for zero-cost work. Zero-cost work stays bounded by the allowance and
  the existing rate limits. That keeps D-MON-001 ("Free is never unlimited") true: with the allowance exhausted and
  credits that never fund zero-price rungs, a free/local-only operation is refused.

## 8. From provider cost to meter price (the cost model)

No VND or credit value is invented. The system supplies evidence and a consistency gate; the human supplies the
numbers.

- **Cost sheet** (an admin read, no new storage). It is computed from `ai_cost_records` joined with each
  operation's meter. Per meter and per rung it gives:
  - calls;
  - p50 / p95 / max provider USD per meter unit;
  - the share of unpriced or estimated records;
  - the share served by zero-cost rungs.
  - It needs a meter tag on the cost record. Proposal: add `meter` and `operation_id` to the cost record (§11) when
    the call ran inside a `FundingContext`.
- **Inputs the human sets (H-1, H-7):**
  - `credit_price[m]` (credits per meter unit);
  - `vnd_per_credit`: the value of a credit in a pack, which determines pack prices;
  - `fx_usd_vnd` reference;
  - `margin_floor`.
- **Consistency gate,** the same style as PR-MON-2's price integrity. For every credit-eligible meter `m`:
  ```
  credit_price[m] * vnd_per_credit  >=  p95_usd_per_unit[m] * fx_usd_vnd * (1 + margin_floor)
  ```
  - A meter that fails is **not credit-eligible** (admission skips step 3 for it).
  - A configured credit pack whose `vnd_per_credit` would put any credit-eligible meter under the floor is **not
    sold** (`credit_offers` excludes it).
  - The gate also refuses when the evidence is too thin: fewer than N priced records, N being configuration (H-7).
  - It is reported, not silent: `GET /api/admin/billing/cost-model`.
- **How packs are derived later (K1 stays):** a pack is `credit_units × vnd_per_credit`, rounded as the human
  chooses. Its legitimacy is the gate above, not a number in code.

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

- `buy_credits` is listed only while `credit_offers()` is non-empty. `upgrade` is listed only while a higher plan
  includes more of the meter.
- `feature_not_in_plan` stays a 403.
- Nothing is charged, and no provider is called.

## 10. What PR-MON-9 (UI) needs

All of it is read-only and server-computed, so the UI never does arithmetic on prices:

- **`GET /api/billing/funding`:** per meter:
  - allowance remaining, limit and window reset;
  - promotional grants remaining and their expiry;
  - credit-eligible, and the price per unit;
  - credits available and held.
- **`GET /api/billing/estimate?meter=&units=`** (pre-flight, no reservation):
  - which source would fund the operation;
  - credits needed;
  - whether it would be refused, and why (§9 reasons).
  - This is what "this will use 2 credits" is drawn from.
- **Recent consumption:** ledger entries carry `meter` and `operation_ref`, which become a feature label and a time.
  Settled, released and uncharged amounts are shown truthfully.
- **Refusal body** as in §9.
- No redesign: the Billing Sheet is wired in PR-MON-9.

## 11. Schema needed (described here; written only after approval, under its own migration gate)

- **`funding_admissions`:**
  - columns: `operation_id` (unique), `incarnation_id`, `meter`, `units`, `source` (`allowance` / `promotional:<grant>`
    / `credits`), `quota_reservation_id`, `credit_reserve_entry_id`, `state` (`admitting` / `funded` / `settled` /
    `released` / `refused`), and timestamps.
  - One row per admitted operation.
  - It makes retries reuse their funding, pairs settlement with the right side, and gives the reconciler a join:
    - an `admitting` row older than the hold TTL with no reservation is closed as `refused`;
    - a `funded` row with a closed reservation is closed accordingly.
- **`promotional_grants`** and **`promotional_grant_usage`:**
  - A grant definition is configuration: id, meters and units, eligibility, `valid_days`, all quantities H-8.
  - A grant **instance** belongs to an identity that survives delete-and-re-register (R-MON-003): the `users` row's
    sign-in subject, not the incarnation.
    - Unique `(grant_id, identity)`, so a grant is claimed once per identity, ever.
    - Its usage is reserved and settled like a quota bucket.
  - Hashing the identity, and what deletion keeps, are part of that migration's review (they touch account deletion,
    a human gate).
- **`ai_cost_records`:** add nullable `meter` and `operation_id` (§8).
- Whether these extend 0007's quota tables or stand alone is decided in the migration gate. The rule is that the
  existing quota system is extended, not replaced.

## 12. Interaction with PR-MON-4/5 contracts

- **Credit operations** are exactly PR-MON-4's `reserve` / `settle` / `release` / `expire_reserve`. No new kind and no
  new ledger path.
  - Integer amounts, the C3 clamp, `HOLD_TTL ≤ 30 min`, `account_under_review` / `account_deleted` refusals and the
    R-MON-014 readiness all apply unchanged.
- **The credits step is absent** unless `CREDITS_ENABLED` is set and the privilege check is clean. The allowance path
  never depends on it.
- **K1/K2/K5/K6 unchanged.** The cost-model gate (§8) can only remove a pack from sale, never add one.
- **C1** (no credit on a deleted account) is mirrored: a deleted account is never admitted.

## 13. Human gates (each one blocks only what it names)

| Id | Decision | Blocks |
| --- | --- | --- |
| H-1 | `credit_price` per credit-eligible meter | the credits step for that meter |
| H-2 | units for the new meters (e.g. TTS per character or per call) and their plan limits | enforcing that meter |
| H-3 | whether zero-cost rungs ever charge credits (v1: never) | — (v1 default is "never", the learner-favourable side) |
| H-4 | `credit_unlocks_feature` per meter | credits on a meter the plan disables |
| H-5 | async meters credit-eligible (settle at acceptance + refund) | credits on `media.import` |
| H-6 | `quota.abandoned_settles` (existing, pending) | unchanged |
| H-7 | `vnd_per_credit`, `fx_usd_vnd`, `margin_floor`, minimum evidence N | any credit pack on sale; credit-eligibility under the gate |
| H-8 | promotional / new-user grants: meters, quantities, eligibility, validity | grants |

## 14. Rollout (each step behind a switch, off by default)

1. Migration gate for §11. Proposed revision 0034 or more, tested on throwaway PostgreSQL. Promotion and application
   are human gates.
2. Funding context, admission ledger and the allowance path. No behaviour change while quota enforcement is off.
3. New meters (§6) and the chokepoint backstop with `FUNDING_ENFORCEMENT` (log-only first: `unfunded_paid_would_skip`).
4. The credits step: inert until `CREDITS_ENABLED`, R-MON-014 and H-1 for a meter.
5. The cost sheet and gate (§8). Promotional grants (§11), inert until H-8.

## 15. Tests the implementation must carry

- I-1 on every chokepoint: a paid rung without funding is skipped or refused, with no outbound request (a fake
  transport asserts zero calls). The same with system funding is allowed and capped.
- The funding order:
  - allowance before credits;
  - promotional before plan, by expiry;
  - one source per operation;
  - a plan-disabled meter refused even with credits.
- Credits:
  - reserve upper bound;
  - settle actual ≤ hold;
  - release on failure, timeout, cancel before dispatch and a zero-cost rung;
  - TTL expiry releases;
  - a late settle is not collected.
- Retries:
  - same operation id → same funding, never a second hold, never a source switch;
  - a different payload → 409.
- Concurrency (PostgreSQL): N parallel admissions on the last allowance unit and the last credits never exceed
  either.
- Refusal body (§9). `options` only lists what can actually be done.
- The cost-model gate: a meter under the floor is not credit-eligible; a pack under the floor is not offered; thin
  evidence refuses.
- Promotional grants: one claim per identity across delete-and-re-register (R-MON-003); expiry.
- Mutation tests on the funding-order and backstop guards.
