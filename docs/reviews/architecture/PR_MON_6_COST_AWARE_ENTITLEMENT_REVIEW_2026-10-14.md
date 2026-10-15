# PR-MON-6 Architecture Review (design)

Recorded from the reviewer's verdict (relayed by the human, 2026-10-14). The design is
`docs/billing/PR-MON-6_DESIGN.md`.

---

# Review of design revision 1 (`cd9f6ae3433a009456e58b8efb29deb6c2de3c69`)

## VERDICT

**REQUEST CHANGES — focused revision**

The overall architecture is accepted. Do not redesign:

- a credit is metered work, not provider USD;
- allowance → credits → refuse;
- one funding source per operation;
- reserve → dispatch → settle/release;
- no database transaction across a provider call;
- I-1: no funded admission, no paid-provider call;
- PR-MON-4/5 C1–C7 and K1/K2/K5/K6 remain frozen.

## P1-1: feature access must precede the cache/deterministic funding bypass

Feature access is separate from the funding requirement. The required order is:

`feature access → deterministic/cache → funding admission → provider`

H-4 is closed: credits do not unlock a meter the effective plan disables. A disabled meter therefore returns 403
`feature_not_in_plan` regardless of a cache hit, a deterministic result, allowance or credit balance.

Required tests:
- disabled meter + cache hit → 403;
- disabled meter + deterministic result → 403;
- enabled meter + cache hit → the result, with no funding consumed.

## P1-2: close the zero-cost rung / reusable-credit loophole

Revision 1 released a credit hold when a credits-funded operation was served by a local or free rung. That allows:
allowance exhausted → reserve credits → served free → release → repeat, without consuming allowance or credits.

H-3 is closed: credits pay for metered work, not provider cost.
- A deterministic, stored or cached result available before admission costs no allowance and no credits.
- An allowance-funded operation consumes allowance as today.
- A credits-funded operation settles the configured meter charge, even when a local or free provider served it.
- A paid provider settles the same charge.
- The learner's credit price does not vary by model or provider.

Remove "release credits on a zero-cost rung" from the test plan.

## P1-3: make funding admission crash- and race-safe, and prove live funding at dispatch

Define the exact state machine and serialization contract for `funding_admissions`.

1. **One immutable operation identity.** An immutable request digest covers at least the incarnation, operation id,
   meter, requested/reserved units, operation reference, and any other field that changes the funding request. The
   same operation id with a different intent → 409 `operation_conflict`.
2. **Serialize by operation id.** Concurrent requests for one operation never reserve two sources. A source is
   chosen once and never changes on retry.
3. **Crash recovery.** Handle these cases explicitly:
   - the admission row is committed, no reservation;
   - the reservation is committed, crash before the row is linked or funded;
   - the admission is funded, crash before dispatch;
   - settlement or release is committed, crash before the admission state update.

   An exact backing reservation is adopted and verified, never duplicated. An old `admitting` row is refused only
   after proving that no exact backing reservation exists.
4. **Snapshot the funding decision.** Settlement and retry never recompute an admitted operation under a new H-1
   price or policy.
5. **`FundingContext` is not funding by itself.**
   - It is created only after the durable state is `funded`.
   - Immediately before any paid-provider outbound request, the backstop proves that the backing funding is still
     valid and open for that operation and meter. A credit hold whose TTL has expired cannot authorize a call.
   - Define propagation and cleanup across threads, streaming and async, so a context cannot leak into another
     operation.
   - `SystemFunding` stays separate and obeys its USD caps.

   Add concurrency and crash tests.

## P1-4: the cost model must price the economic operation and the actual packs

- **Aggregate per operation first.** Aggregate `(operation_id, meter) → SUM(priced paid-provider cost)`, then compute
  the cost per settled meter unit. p50/p95/max come from operation totals, not individual calls.
- **Zero-cost share is separate.** It must not hide the p95 of operations that reach a paid provider.
- **Unpriced calls lower evidence quality.** An unknown or unpriced billable call never silently counts as USD 0.
- **Judge each pack on its own economics.** For each pack, `effective_vnd_per_credit = pack.amount_minor /
  pack.credit_units`. Every offered pack must pass the margin/cost gate for every meter it may fund.

## Human decisions

| Id | Decision |
| --- | --- |
| H-1 | No production credit prices. Configuration and evidence contract only. |
| H-2 | Units frozen: `speech.transcribe` second, `reading.assist` request, `word.assist` request, `writing.task` request, `speech.evaluate` second, `audio.tts` character. Granularity and plan limits stay human gates. |
| H-3 | CLOSED: credits-funded work charges credits whichever rung served it. |
| H-4 | CLOSED: credits do not unlock plan-disabled features (v1). |
| H-5 | CLOSED: `media.import` is allowance-only. |
| H-6 | CLOSED: `quota.abandoned_settles = admitted`, for the allowance only. |
| H-7 | OFF: no VND/credit, FX, margin floor or evidence N chosen. Report and contract first. FX is a configured auditable reference, never live. |
| H-8 | OFF: no production grants. Contract and anti-reclaim only. Default none. |

## Still accepted

- One source per operation.
- Promotional before plan, earliest expiry first.
- No transaction around a provider call.
- `HOLD_TTL` ≤ 30 min.
- C3 never charges the excess later.
- The 429 body and the funding/estimate contracts for the UI.
- `media.import` allowance-only.
- Rollout switches off by default, and a log-only backstop stage first.
- No implementation or migration before approval.

## Deliverable

Update only the PR-MON-6 design, status and review documents. No code, no migration 0034, no promotion or
application, nothing enabled. Return the revision-2 commit for a focused review of the four P1s. If they close
cleanly, the next verdict should be APPROVE FOR IMPLEMENTATION / MIGRATION GATE.

**Answered by design revision 2** (this lane's next commit): §4 (P1-1), §3, §5.3 and §7 (P1-2), §2.1, §5.4, §5.6 and
§11 (P1-3), §8 (P1-4), §13 (decisions, D-MON-023).

---

# Focused re-review of design revision 2 (`418e937eb3bf62fefcc3e8a66941f567b1ad169f`), 2026-10-15

## VERDICT

**APPROVE FOR IMPLEMENTATION / MIGRATION GATE.** All four P1s are closed; no architecture blocker remains.

- **P1-1 CLOSED:** feature entitlement precedes deterministic/cache. A plan-disabled meter is always 403; the cache
  bypasses funding, never feature access.
- **P1-2 CLOSED:** H-3 is consistent with "a credit is metered work". After a credits admission, local, free and paid
  all settle the same snapshot price; only deterministic/stored/cache work completed before admission costs 0. The
  reserve → free → release → repeat loophole is gone.
- **P1-3 CLOSED:** an immutable digest, row serialization by `operation_id`, the source chosen exactly once, an
  immutable snapshot, explicit crash adoption/recovery, a canonical lock order, and live database validation
  immediately before each paid outbound request. A stale context, or a hold near or past expiry, cannot authorize a
  provider call.
- **P1-4 CLOSED:** cost is summed per `(operation_id, meter)` before cost per unit; unpriced/partial never becomes
  USD 0; the paid-reaching p95 is separate from zero-cost operations; the margin gate runs on each real pack's
  effective VND per credit, so discounts and rounding cannot slip under the floor.

H-1…H-8 are recorded as decided: H-2…H-6 closed; H-1, H-7 and H-8 OFF, with no commercial number invented.

## Allowed next step

The PR-MON-6 migration gate for §11: a proposed revision 0034 (or the one the real topology needs) with at least
`funding_admissions`, the promotional grant contract and storage, and the attribution fields
`ai_cost_records.operation_id` / `meter`. The gate is reviewed separately on: topology and the current Alembic head;
foreign keys, ownership and privileges; database guards for the immutable identity/snapshot and forward-only
transitions; operation-id uniqueness and concurrency; the delete/re-register identity rule of promotional grants;
upgrade/downgrade/rehearsal; PostgreSQL concurrency and mutation tests.

No feature implementation until the migration gate closes. No promotion or application of 0034, no quota, funding or
credits enabled, and no R-MON-014, without separate human authorization.

**Answered by** `docs/billing/PR-MON-6_MIGRATION_GATE_REVIEW_REQUEST.md` and the proposed
`migrations/proposed/20261015_0034_funding_admissions.py` (this lane's next commit).

---

# Migration-gate review of `5a2f5fd5d81ff62961072e5700b16d1476fe620c` (proposed 0034), 2026-10-15

## VERDICT

**REQUEST CHANGES — two focused P1s.** The migration architecture is otherwise accepted.

Accepted, not to be redesigned:
1. promotional usage reuses 0007's quota bucket and reservations (no `promotional_grant_usage` table);
2. the admission source may be `promotional`, the exact grant derived through the backing bucket;
3. `users.id` is the v1 anti-reclaim identity while the deletion model preserves that row. Purging `users` would
   require a separate human-approved migration to a durable keyed identity.

- **P1-1:** the exact credit backing must include the reserve request digest, using PR-MON-4's exact reserve digest
  contract (no second format). Tests: a canonical reserve funds; a reserve correct in account/key/meter/ref/amount but
  with a wrong digest can neither fund nor be adopted; retry/adoption never treats it as exact. A mutation removing
  the digest predicate must be killed.
- **P1-2:** `stray_released` must prove no open `fund:<op>` credit reserve in **any** account, not only the
  admission's incarnation. Regression: A admitted; B holds `fund:<op>`; A refused; conflict opened; resolution fails
  while B's hold is open, succeeds after it is released or expired. A mutation restoring the same-incarnation
  restriction must be killed.

Promotion prerequisite: the lane on current `main` (#212 at `d0261230`); one Alembic head; 0034 still the next free
revision; rerun the 0034 suite, the billing PostgreSQL batch, all 0034 mutations and the up/down-to-0033/up
rehearsal. No promotion or application of 0034, no feature code, no quota/funding/credits enabled, no R-MON-014.

**Answered by** revision 2 of the proposal (this lane's next commit); `PR-MON-6_MIGRATION_GATE_REVIEW_REQUEST.md` §10.

---

# Re-review of `945299206d80259532ce14d521a91bc1dd0700f7` (0034 revision 2), 2026-10-15

## VERDICT

**APPROVED: PR-MON-6 design revision 2 and the migration gate.** 0034 stays proposed: not promoted, not applied.
Before implementation the lane syncs to the latest `main` and re-proves the topology (one live head
`20261015_0033`, 0034 unclaimed, no conflict from #214) and the evidence (0034 suite, billing PostgreSQL batch, 0034
mutations, Alembic rehearsal). Then PR-MON-6 feature implementation per design revision 2, everything off by default;
no promotion or application, no R-MON-014, no credits or enforcement enabled, no merge without independent review and
CI.
