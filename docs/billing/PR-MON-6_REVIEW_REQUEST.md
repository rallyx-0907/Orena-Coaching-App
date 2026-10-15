# PR-MON-6 implementation: review request

| | |
| --- | --- |
| **Design** | `PR-MON-6_DESIGN.md` revision 2. APPROVED FOR IMPLEMENTATION / MIGRATION GATE (`418e937e`). Migration gate APPROVED (`94529920`). |
| **Schema** | `migrations/proposed/20261015_0034_funding_admissions.py`. **Still proposed**: not promoted, not applied anywhere. |
| **Code commits** | `995036e1` (slice A), `8f13b921` (slice B), then the review fixes. |
| **Everything off by default** | `ORENA_FUNDING_ADMISSIONS` (admissions), `FUNDING_ENFORCEMENT` (the backstop: off, log or enforce), `CREDITS_ENABLED`, quota enforcement per meter. No meter price (H-1), no cost-gate inputs (H-7), no promotional grant (H-8), no credit pack. |

## What is built, by design section

| § | Built | Where |
| --- | --- | --- |
| 5.6 | Admission transaction. The row is inserted ON CONFLICT DO NOTHING, then taken FOR UPDATE, then the digest is compared. The source is chosen once, and its backing reservation is written in the same transaction through savepoints. Then the snapshot. Retries replay; 409 for conflict, completed and closed. | `persistence/funding_repository.py` `admit` |
| 4 | Order: promotional (earliest expiry) → plan → credits → refuse. One source per operation. | `billing/funding.py` `FundingService.admit` |
| 4 step 1 | Feature access is checked before the stored-review bypass. A plan-disabled meter is refused with 403 even when the review is cached. Credits never unlock it. | `product/quota.py` `require_feature`; `app.py` `/api/evaluate` |
| 3, 5.3 | Settle charges `snapshot.price × units`, whatever rung served (H-3). A result of 0 units is a release. A hold that has expired is released and never collected. The allowance reservation, once dispatched, is settled at 0. All of it idempotent. | `funding_repository.py` `settle`, `release` |
| 2.1 | Live check (one read). Its first paid request moves the row to `dispatched`. | `funding_repository.py` `live`, `dispatch` |
| 2 | The backstop runs at these points: each paid rung of `generate_structured` (skipped as `unfunded`), the legacy selection, each agent round, ASR, pronunciation, live-voice mint, word TTS, Supadata. `SystemFunding` covers operator tests and media batches. The modes are off, log and enforce. In enforce, `FundingRequired` answers 503 `funding_required`. | `billing/funding_context.py`, `ai/platform.py`, the clients |
| 2.1 | Propagation. The context is a ContextVar reset in `finally`. `run_funded` carries it to threads; asyncio tasks get a copy. Agent rounds enter it only around the request, with no `yield` inside the scope. Voice mints enter it around the mint. | `agent/turn.py` `_round`, `agent/voice_session.py` |
| 5.6 crash table | Reconciler. A funded or dispatched row whose backing has closed is completed from it. An old `admitting` row with an exact backing is kept for adoption; otherwise it is refused. A non-exact `fund:<op>` reservation opens a `funding_admission_conflict`, which is resolved once nothing keyed `fund:<op>` is still open. It runs on the quota reconciler's tick, after that tick has closed abandoned reservations through the admission. | `funding.py` `reconcile`, `quota.py` `reconcile_once` / `QuotaReconcileSchedule.tick` |
| 8 | `ai_cost_records.operation_id` and `meter` are written when the columns exist. Cost is aggregated per operation, then per unit; incomplete operations are never counted as USD 0; the zero-cost share is reported apart; the per-pack gate uses `effective_vnd_per_credit`; a pack that fails is not offered and not sold. | `ai/account_costs.py`, `persistence/platform_repository.py`, `billing/cost_model.py`, `billing/service.py` |
| 9, 10 | 429 `quota_exhausted` with `reason`, `allowance`, `promotional`, `credits` and `options`. `GET /api/billing/funding`, `GET /api/billing/estimate`, `GET /api/admin/billing/cost-model`. | `quota.py` `_fund`, `funding_api.py` |
| 11 | Promotional grants: claimed once per `users.id`, with 0007 buckets as their usage. Plan windows ignore `promo:` buckets. | `billing/promotional.py`, `quota_repository.py` |
| 5.5 | `media.import` is allowance-only. Its by-operation dispatch, settle and release go through the admission. | `funding.py`, `quota.py` |

## Choices made in implementation, for the reviewer

1. **A 403 or 429 writes nothing.** The whole admission transaction is rolled back, as 0007's rejected reserve is,
   so the same operation id may be admitted later. `refused` is the reconciler's state for a crashed `admitting`
   row. The design's diagram puts 403/429 on `admitting → refused`; persisting those would turn a learner's later
   retry, after a top-up, into 409 `operation_closed`.
2. **Refusal reasons.**
   - `credits_unavailable` when credits are not ready;
   - `not_credit_eligible` when they are ready but the meter has no approved price, or fails the gate;
   - `insufficient_credits`;
   - `allowance_exhausted` for allowance-only meters.
3. **The admission's `operation_ref` is the gate's operation id.** Routes do not yet pass their own reference, such
   as a review id.
4. **409 categories.** Design §5.4's `operation_completed` and `operation_closed` are answered as the gate's
   existing `operation_finished`, with `context.state` set to `completed` or `closed`. The agent contract's §2.1 lists
   every category the gate can answer, and it belongs to another lane, so no new category is added.
5. **Backstop timeout.** The live check's minimum hold time is the rung's HTTP timeout. Clients without a known
   timeout pass 0, which still requires an unexpired, open hold.

## Before `FUNDING_ENFORCEMENT=enforce` can be switched (design §2, §14)

- **Run log-only first.** Every `unfunded_paid_would_skip` must be either metered or declared `SystemFunding`. The
  paths known still to declare are: prefetch, the catalogue and admin content generators, reading on demand, and
  dictionary AI. Each is learner-facing or system work that §6's new meters (H-2, not enforced) will cover.
- **0034** must be promoted and applied (human gates), and `ORENA_FUNDING_ADMISSIONS` switched on.

## Evidence (local execution, not CI)

- **Hermetic tests:**
  - `tests/test_funding_gate.py`: access before cache, ticket, refusals, 409s;
  - `tests/test_funding_context.py`: modes, live check, stale context, threads, asyncio, platform gate;
  - `tests/test_cost_model.py`: aggregation, incomplete evidence, zero-cost share, per-pack gate, input validation.
- **PostgreSQL tests:**
  - `tests/test_funding_postgres.py`: precedence, promotional order, refusals that write nothing, retry and conflict,
    concurrency, snapshot after a price change, H-3 loop, idempotency, dispatched release, live check, reconciler
    adoption, refusal and conflict, deleted account;
  - `tests/test_funding_gate_postgres.py`: precedence through the gate, credits unavailable, backstop with live
    admission, stale context, expiring or closed hold, attribution and aggregation.
- **Full-suite results** are recorded in `BILLING_STATUS.md` with this commit.

## Independent pre-review (fresh-context agent, read-only, on `26ee7142`): REQUEST CHANGES, no P0

This is a pre-check by a separate agent, not the formal architecture/code review (an implementer never
self-approves).

| Finding | Disposition |
| --- | --- |
| **P1-1:** the agent round's FundingContext. The reviewer said the provider stream is created outside the scope. | **Partly wrong; the real part is fixed.** `stream_agent_turn` is a generator function, so its backstop runs at the first `next()`, which was already inside the scope. What was true: the round's cost record at the stream's end ran outside the scope, so agent costs were unattributed. `_Turn._round` now runs every `next()` inside the scope, with no `yield` inside it. Test: `test_an_agent_round_runs_every_step_in_its_funding_context_and_none_leaks_between_yields`. |
| **P1-2:** a same-operation twin got a second live ticket over one admission. | **Fixed.** A replayed open admission answers 409 `operation_in_progress` at the gate (`AdmissionOutcome.replayed`). There is one live ticket per admission; a crashed holder's admission is closed by the reconciler. Test: `test_a_replayed_open_admission_is_in_progress_never_a_second_ticket`. |
| **P2-1:** the cost gate was read inside the admission transaction (a second connection). | **Fixed.** The credit terms are read before the transaction. |
| **P2-2:** the reconciler paged every open row. | **Fixed.** `closed_backing_rows` reads only rows whose backing has closed. |
| **P2-3:** one failing funded row aborted the quota tick. | **Fixed.** Each row is isolated with a warning and `continue`. |
| **P2-4:** a credits settle that fails transiently is lost when the hold expires. | **Accepted (C7):** an expired hold is released, never collected. Recorded as a known cost. A retry belongs with the PR-MON-8 runtime work. |
| **P2-5:** `require_feature` changes `/api/evaluate` behaviour whenever the meter is enforced. | **Intended (P1-1 of the design review).** A plan-disabled learner with a cached review now gets 403. It changes nothing while quota enforcement is off, which is the default. |
| **P2-6:** `exact_backing` ignored the reserve digest. | **Fixed.** It mirrors the 0034 guard: the canonical digest of the hold's own amount and TTL. |
| **P2-7:** learner media imports run under `SystemFunding`. | **As designed** (§2: media batches, bounded by the media spend caps). The admission's own context for personal imports is a later refinement. |
| **P2-8:** prefetch, reading workers and media fallbacks carry no context. | Already a precondition of enforce mode above (log-only first). |
| **P2-9:** a skipped unfunded rung is labelled `skipped_budget` with reason `unfunded`. | Known and fails closed. The telemetry label stays, to keep the routing contract unchanged. |

Re-run after the fixes (local): funding, gate, quota and contract suites 174 passed + 1 INHERITED #160; agent and
voice suites 1254 passed.
