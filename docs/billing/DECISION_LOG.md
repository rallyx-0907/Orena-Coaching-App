# Billing / Monetization lane — decision log (append-only)

Format: `D-MON-XXX | date | decision | reason | consequences`. Never edit a recorded decision; a change is a new
entry that names what it supersedes. Project-wide `D-` numbers are assigned at merge (do not claim D-188).
"Human" means the human owner's instruction; "lane" means proposed by the lane leader, pending review where noted.

D-MON-001 | 2026-10-13 | Free vs paid cost policy (human). Generous Free core: Reading, dictionary, saved vocabulary,
review/flashcards, collections, progress, cached content, deterministic/local lookup. Limited, quota-controlled Free
AI: Writing feedback, contextual Reading AI, simple word/context questions, Orena Intelligence, on free/local/cheap
models. Paid-first with only a small new-user allowance: realtime voice, pronunciation/cloud STT, long audio/video,
media import/transcription/analysis, heavy Agent runs, large-context reasoning. | Engagement must not scale
uncontrolled cost; a provider's free model may not stay free. | Never unlimited Free; even zero-price AI is metered;
expensive paths need subscription allowance or credits after the trial.

D-MON-002 | 2026-10-13 | Prepaid credits (human). Top up, consume, stop at zero. No auto-recharge, no negative
balance, no surprise or recurring charge. Retries never double-debit, webhook replays never double-credit, and
refunds/reversals stay auditable. payOS/VND first; Polar credits deferred unless trivial and safe. | Pay-as-you-go
without a subscription. | An append-only ledger (PR-MON-4) and a reserve-before-dispatch admission (PR-MON-6); needs
a migration through review and the human gate.

D-MON-003 | 2026-10-13 | Gateway direction (human). payOS: Vietnam prepaid plan access and credits. Polar:
international subscriptions as merchant of record; Orena consumes its lifecycle and rebuilds no tax, VAT, invoice
or renewal. | Both accept an individual seller; Polar carries tax. | An architecture direction only; no production
activation without the human gate.

D-MON-004 | 2026-10-13 | Webhook failure classes (human). Transport/security failures (signature, malformed,
oversize) are rejected normally. A verified money event with a business mismatch (deleted account, amount mismatch,
unknown mapping, entitlement failure) goes: durable record → durable reconciliation/incident state → operator
visibility. | Provider retries cannot fix a business mismatch and create noise; a payment must never be silently
lost. | Exact HTTP/retry semantics are set per provider in PR-MON-3; today's "200 + log line" is an open gap.

D-MON-005 | 2026-10-13 | Price integrity (human). Checkout only at a server-offered price that exactly matches the
effective catalogue entry (plan, period, currency, amount); a mismatch blocks checkout. Browser amounts and plans are
never trusted. `billing_ready` reflects runtime capability (switch, schema, backbone, credentials, prices, webhook
configuration) and never exposes secrets. | The learner is never charged an amount other than the one shown. | PR-MON-2
removes the independence of `BILLING_PRICES_FILE` and the catalogue and the hardcoded `billing_ready=False`.

D-MON-006 | 2026-10-13 | Effective entitlement precedence (lane; pending independent architecture review). One
resolver: valid billing (`commerce_subscriptions`, state active/trialing, `paid_through` absent or in the future) →
valid manual/legacy row → Free. Billing outranks manual, following D-154's own "billing is never overwritten by hand";
no Admin override of a paid entitlement exists, and none is added. `past_due`/`paused`/`pending`/`unknown` grant
nothing until a grace policy exists (commerce architecture §3: missing policy blocks paid admissions). The billing
source is installed by store presence (PostgreSQL + backbone + 0006 tables), not by `BILLING_ENABLED`. | A recorded
payment must change the effective plan, in one place; a recorded paid entitlement must not vanish when checkout is
switched off. | Plan UI, quota and the language limit agree by construction; an Admin plan change on a billing-owned
account is 409; grace is a human policy input.

D-MON-007 | 2026-10-13 | Cost telemetry (human). Reuse `ai_cost_records`; keep it possible to compute Free/Plus/Pro
cost per user, cost by feature and by provider/model, revenue against cost and heavy users. No finance dashboard. |
Margin protection needs data, not BI. | No new telemetry store; later PRs keep the account and feature attribution on
cost rows.

D-MON-008 | 2026-10-13 | Sequence (human). The PR-MON-1..10 order in `BILLING_STATUS.md` governs. The brief's
"PR 1 — Billing Activation Foundation" (§18) is split across PR-MON-1 (entitlement), PR-MON-2 (price/readiness),
PR-MON-3 (orders/migration), PR-MON-8 (runtime) and PR-MON-9 (checkout UI). | Checkout before a payment can change
the plan would take money for nothing. | One PR at a time; PR-MON-1 first.

D-MON-009 | 2026-10-13 | One documentation tree (human). The brief's `docs/monetization/{MASTER_PLAN,STATUS,
DECISION_LOG,RISK_REGISTER}.md` map onto `docs/billing/{BILLING_LANE,BILLING_STATUS,DECISION_LOG,RISK_REGISTER}.md`;
`BILLING_STATUS.md` is the only resume point. | No parallel documentation. | `docs/monetization/` is not created.

D-MON-010 | 2026-10-13 | Billing outranks manual, confirmed (human). D-MON-006's precedence stands: a paid billing
entitlement outranks a manual/legacy row and cannot be overridden from Admin in PR-MON-1. A future support override
is a separate break-glass mechanism with authorization, a reason, an audit trail and an expiry. | D-154 intent; a
paid entitlement must not be silently replaced by hand. | No override path is built now; break-glass is out of
PR-MON-1's scope.

D-MON-011 | 2026-10-13 | Polar past_due grace, 2 days (human). Supersedes the part of D-MON-006 that made `past_due`
grant nothing. A Polar subscription in `past_due` (Polar `past_due`/`unpaid`) keeps its paid entitlement for 48 hours
from the end of its paid period; after that it reads as Free while it stays past due; a recovered payment restores
the plan from Polar's own state. The number is policy, not resolver code (`writing_coach/product/billing_grace.py`,
`BILLING_PAST_DUE_GRACE_HOURS`, 0..336, default 48). The anchor is `paid_through`, which the Polar adapter records
for a past-due event as `past_due_at`, else `current_period_start`, else the stored end of the last paid period:
Polar advances the cycle before charging, so a past-due `current_period_end` is the unpaid cycle's end. | Recoverable
failed renewals should not cut a paying learner off at once; arrival time cannot anchor the window (commerce §3). |
`paused`/`pending`/`unknown` and payOS still have no grace. The policy is environment-configured until the Admin
policies page gains its EN/VI/ZH copy (UI lane); `subscription.past_due` is now a handled Polar event.

D-MON-012 | 2026-10-13 | A still-owned billing relationship suppresses manual/legacy (independent review of PR-MON-1,
P1-1). Supersedes D-MON-006's "falls through to manual/legacy" for non-granting billing states. Billing releases the
account only when its effective state is `ended` (including a granting state past `paid_through`) or the row is
absent; every other state (`past_due` outside grace, `paused`, `pending`, `unknown`, anything unrecognised) reads
Free, stays billing-owned, and no manual or legacy plan applies. | A manual Pro must never surface because a paid
subscription is temporarily failing. | One predicate (`entitlement.billing_owns`) serves the resolver, the Admin
pre-check and the transactional re-check.

D-MON-013 | 2026-10-13 | Manual plan writes re-check billing ownership inside their transaction (review P1-2).
`apply_membership` locks the account's active incarnation `FOR NO KEY UPDATE` and refuses any plan change while
billing owns the account; nothing is written. | The pre-check alone left a window in which a payment could land and
the manual row would later resurface. | A manual grant exists only if it committed before billing took ownership;
then the existing policy applies when billing ends.

D-MON-014 | 2026-10-13 | A committed prepaid payment or refund that is not yet synced to access counts as billing
ownership (re-verification of PR-MON-1 P1-2). Extends D-MON-013. Inside the membership transaction, under the
incarnation lock, the orders' prepaid version (`billing_orders` paid + refunded, the arithmetic `sync_prepaid`
records) ahead of the version `commerce_provider_subscriptions` applied for `prepaid:<incarnation>` refuses a plan
change. | payOS writes the payment (`mark_paid`) and the access (`sync_prepaid`) in two transactions; the window
between them must not admit a latent manual grant. | The smallest change: no billing redesign; it also holds an
account whose sync crashed until it is repaired (R-MON-002, PR-MON-3), which is the safe side.

D-MON-015 | 2026-10-14 | Price integrity, how (PR-MON-2; implements D-MON-005; pending independent review). The
catalogue stays the shown price and the prices file stays the gateway binding (a merchant of record charges its own
configured price, so neither can be derived from the other); they are compared on every offer, checkout and readiness
read, in exact integer minor units (USD 2 decimals, VND 0), against the catalogue read strictly. A price with no
catalogue entry or a different amount is a mismatch, and **one mismatch blocks every offer and checkout on its
gateway** until an operator fixes it; an unreadable catalogue sells nothing. A prices file names only a paid
catalogue plan by its own id (no `premium` alias, no `free`), a catalogue currency and a known gateway, and no price
twice. A checkout starts only at the amount and currency the learner confirmed (`price_changed`, never charged from
the browser). `billing_ready` is the runtime's readiness (switch, PostgreSQL, backbone, 0006 tables, `billing_orders`,
entitlement source, public URL, a ready gateway), named per blocker, never a secret; the frozen mobile contract keeps
`billing_ready: false`. | The learner is charged exactly what was shown, and an Admin price change can never silently
make the two diverge. | `GET /api/admin/billing/readiness` reports it. With 0027 still proposed, every runtime reports
`orders_schema_absent`, so `billing_ready` stays false everywhere until PR-MON-3.

D-MON-016 | 2026-10-14 | Commerce discovery fails safe (closes review P2 / R-MON-010; pending independent review).
"Not deployed" is no PostgreSQL, the account backbone not asked for, or a listing that answered without the 0006
tables: no billing row, as before. "Expected but unreadable" is PostgreSQL with the backbone asked for and a listing
that failed: the billing source is still installed and every plan read through it raises, so quota answers 503 and
the Plan screen reports unavailable, never a silent legacy plan. It asks again at most every 5 s and keeps the first
answer. The source no longer also requires the backbone to be `active`, so a backbone left `unavailable` by the same
failed listing cannot hide a paid account. | A paid account must never read a legacy plan because one startup query
failed. | Readiness names `entitlement_source_unverified` / `commerce_schema_unreadable`.

D-MON-017 | 2026-10-14 | The learner payment entrypoints require a billing-ready runtime (PR-MON-2 review P1). Extends
D-MON-015. `GET /api/billing/offers` lists nothing and `POST /api/billing/checkout` answers 503 `billing_not_ready`
(retryable) unless `billing.readiness.billing_ready()` is true - the same decision every surface reports - checked
before any order is written or any gateway is called. A verified webhook, the administrator's refund and the readiness
report are never gated: money already taken is received and reconciled. `billing_ready` does not mean the Polar-side
price was verified (R-MON-011). | Readiness that only informs a screen would let a runtime without `billing_orders`
or with a wrong public URL start a payment. | Reviewer: ChatGPT, verdict recorded in
`docs/reviews/architecture/PR_MON_2_PRICE_READINESS_REVIEW_2026-10-14.md`.

D-MON-018 | 2026-10-14 | Billing Orders + Reconciliation Safety, how (PR-MON-3; design APPROVED by the independent
reviewer on `5b445175`, implementation pending its review). Implements D-MON-004. A verified money event is
acknowledged only once durable (the order, a receipt, or a `billing_reconciliation_items` row); when nothing could be
recorded the webhook answers 503 so the provider retries; a business anomaly is recorded, then answered 200. Provider
facts are stored without foreign keys; Orena's links only when matched. Resolution is per kind and enforced by CHECKs
and a trigger: paid-without-access (`entitlement_unsynced`) is closed only by the reconciler once access is granted;
money kinds need an outcome with a reference or an audited reason and are never dismissed; a critical item reopens
when seen again, and an open critical item closes new checkouts on its gateway. A reconciler (session advisory lock on
a dedicated connection, short transactions, no transaction across the provider call) repairs prepaid access gaps
(R-MON-002), asks payOS about every unsettled order - a locally expired one too - until a successful lookup gives a
documented terminal answer, and expires abandoned orders locally only. A payOS order is the unit of payment: one
payment per order, whichever source saw it first; a webhook-paid order gets one confirming lookup (overpayment).
Polar refunds are recorded and matched only through a committed subscription mapping; they never change access (H4).
H1-H7 as decided by the review; H2 taken as a follow-up revision 0031 (no operator confirmation). | Money must never be
acknowledged and then lost, and paid-without-access must never be silenced. | Proposed 0031; no migration promoted or
applied; billing stays off. Record: `docs/reviews/architecture/PR_MON_3_RECONCILIATION_REVIEW_2026-10-14.md`.

D-MON-019 | 2026-10-14 | Prepaid credit ledger policy, C1-C7 (human, on the PR-MON-4 design `43a3dedf`). C1: credit
left on a deleted account is a financial liability - kept, never forfeited, never auto-refunded, history never
cascaded or rewritten; no new topup/reserve/settle/spend; release, reserve_expire, refund, reversal and controlled
adjustment still allowed; tracked by `credit_balance_on_deletion` until resolved. C2: no automatic transfer to a new
incarnation (no inheritance, identity lookup, reuse or resurrection). C3: the reserve is a hard upper bound -
charged = min(actual, hold), the rest `uncharged`, DB-enforced, never collected later; a late settle is not charged
and is recorded. C4: adjustments only as audited ledger deltas (reason, actor, idempotency key, digest), never below
zero, no "set balance". C5: a reversal reverses only what is available (never reserved credits, never negative) and
records the shortfall with its top-up/reversal context. C6: purchased credit does not expire in v1; reservation
expiry (`reserve_expire`) is a different concept. C7: reserve TTL default 30 minutes, `expires_at` stored on the
reserve from its own transaction and authoritative. | Credits are customer money: nothing may vanish, go negative or
be charged twice or later. | Frozen in `PR-MON-4_DESIGN.md` revision 2; not decided: credit-VND rate, meter prices,
Free allowance, auto top-up, activation, promotions, incarnation transfer.

D-MON-020 | 2026-10-14 | Credit ledger architecture after the review of `e5ccc114` (lane, pending the focused
re-review). (1) 0032 depends on 0031's schema (it replaces the reconciliation kind CHECK): order 0027 -> 0031 -> 0032,
never promoted or re-parented ahead of 0031. (2) The snapshot write boundary is database privilege: tables and the
ledger function owned by a NOLOGIN `orena_credit_owner`; the runtime (member of `orena_credit_runtime`) has no UPDATE
on the snapshot columns and no UPDATE/DELETE/TRUNCATE on the ledger; the only writer is a SECURITY DEFINER trigger
function with a fixed search_path; the guard trigger is defense in depth; readiness refuses credits while the
runtime connects as a superuser or table owner. (3) A reversal applies min(requested, available, remaining
reversible), every request has an immutable `credit_reversal_requests` receipt keyed by its money-side event, a
replay returns the stored outcome and is never re-evaluated, and digests cover request intent, never derived
results. | A financial snapshot needs an authorization boundary, and a reversal must be decided exactly once. |
Deployment prerequisite (operator gate): the runtime must connect as a non-superuser member of `orena_credit_runtime`
before credits are enabled.

D-MON-021 | 2026-10-14 | Credit ledger design revision 4 after the review of `2b6da4a7` (lane, pending the focused
re-review). Reversal requests carry no back-reference: `credit_ledger.reversal_request_id` (exactly for `reversal`,
partial UNIQUE) is the only link, inserted after its request, so the request stays immutable with immediate
constraints. A money-side refund/chargeback event is globally unique on reversal requests (`source_type`,
`source_ref`). 0032 extends `billing_reconciliation_items` with nullable structured `credit_*` references, per-kind
CHECKs, extended class lists and a replaced guard trigger that also freezes the new facts. The definer function's
schema is not writable by untrusted roles (else a dedicated `orena_credit` schema); 0032 needs a superuser or
CREATEROLE executor, or roles provisioned out of band and asserted; `credit_runtime_privileges` checks every
boundary-defeating privilege. | Constraints must be satisfiable as written, one money event must move credit once,
and reconciliation facts must be as immutable as PR-MON-3's. | No code; 0032 not yet created; rebase and topology
check before creating it.

D-MON-022 | 2026-10-14 | payOS credit top-up policy, K1/K2/K5/K6 (human, on the PR-MON-5 design `5a5c4053`). K1: PR-MON-5
implements the credit-pack configuration contract only; production has no packs; sizes and prices are decided with
the PR-MON-6 meter/cost model; no packs file means no credit products. K2: a credit-pack order is refunded in full or
not at all (no partial monetary refund in v1, the operator decides); a recorded full refund attempts the reversal of
the full `credit_units`, C5 reverses what it can, the rest is `credit_reversal_shortfall`, never negative. K5: the
pack-checkout API ships in PR-MON-5 behind `CREDITS_ENABLED`, credit runtime readiness and a configured pack, with no
UI. K6: no purchase-count limits in v1 beyond idempotency, server-side pack validation and confirmed amount, currency
and units. | Credits sold for money need an exact, auditable path, and the commercial numbers belong to the cost
model. | Recorded in `PR-MON-5_DESIGN.md` revision 2 with the review's lifecycle fixes (exact-match fulfillment,
`credit_reversal_unapplied`, terminal outcomes of `credit_topup_unapplied`, exclusive order payloads).


D-MON-023 | 2026-10-14 | PR-MON-6 funding decisions (human, on the PR-MON-6 design `cd9f6ae3`). H-1: no production
credit prices; the configuration/evidence contract only, a meter's credits step unavailable until its price is
approved. H-2: internal units frozen - `speech.transcribe` second, `reading.assist` request, `word.assist` request,
`writing.task` request, `speech.evaluate` second, `audio.tts` character; granularity and Free/Plus/Pro limits stay
human gates, no new meter enforced before them. H-3: credits pay for metered work, not provider cost - credits-funded
work settles its meter charge whichever rung (local, free, paid) served it; only deterministic/stored/cache work
completed before funding admission is free; no per-model learner price. H-4: credits do not unlock a meter the
effective plan disables (v1); feature access precedes any cache/deterministic bypass. H-5: `media.import` is
allowance-only; no settle-at-acceptance + refund. H-6: `quota.abandoned_settles = admitted`, for the allowance only;
credit abandonment releases/expires (C7). H-7: VND per credit, FX, margin floor and minimum evidence are not chosen;
the cost-model report and the per-pack consistency gate come first, no pack sellable until approved, FX a configured
auditable reference, never live. H-8: no production promotional grants; the configuration/storage/claim and
anti-reclaim contract only, default none. | Stable learner prices, no reusable-credit loop through zero-cost rungs,
and no commercial number invented ahead of evidence. | Recorded in `PR-MON-6_DESIGN.md` revision 2 with the review's
P1 fixes (access before bypass, the admission state machine with live funding at dispatch, operation-level cost and
per-pack margin gate).


D-MON-024 | 2026-10-15 | Domestic gateway direction (owner decision, corrected the same day). The owner has no bank
account payOS supports. payOS is therefore no longer the preferred production domestic gateway. Its adapter
(`writing_coach/billing/payos.py`) stays in the repository unchanged, as the existing alternative, used only if the
owner later has a supported bank path. payOS belongs to the Casso ecosystem: there is no separate "Casso + VietinBank"
fallback and no `CassoGateway`. A genuinely separate Casso product would be research evidence first, then review.
The primary candidate is SePay + VietinBank (personal account). SePay observes the owner's own account; it moves no
money and cannot refund a personal account. It is built and validated in PR-MON-8 behind the normalized `PaymentFact`,
with every money-side invariant unchanged (provider evidence only, exact amount and currency, idempotent redelivery,
one credit per payment, reconciliation items for unmatched payments, durable deleted-account obligations, the
approved refund and reversal semantics). International stays Polar. SePay is not approved for production: provider
activation, credentials and the live test are human gates. PR-MON-6 is unchanged. | The available bank path decides
the domestic provider; the core must not depend on any one of them. | Assessment and PR-MON-8 scope in
`DOMESTIC_GATEWAY_SEPAY_ASSESSMENT.md`.


D-MON-025 | 2026-10-15 | PR-MON-7 owner decisions closing H7-6, H7-3, H7-5 and H7-4 (after PR-MON-7A-first was
approved at `94f96a8f`). H7-6: Ollama Cloud is approved at the provider/privacy-policy level for `learner_text` under
its documented privacy and retention terms; a model is allowlisted only with an acceptable commercial licence, an H7-2
benchmark pass for the capability, known (reference) pricing and its exact id entered explicitly; nothing is
populated automatically. H7-3: `word.assist`, `reading.assist`, `writing.task` count requests per day with bootstrap
limits Free/Plus/Pro 30/300/1500, 10/100/500 and 5/30/100, in the Admin-editable plan catalogue, never hardcoded at a
route; `speech.transcribe`, `speech.evaluate` (seconds) and `audio.tts` (characters) are wired with enforcement off
until their limits are approved. H7-5: learner text uses an account/incarnation-scoped cache or none; a shared cache
only for content the server verifies as public/published from authoritative stored data, never from a client id,
prefix, flag, type or source id; a dedicated cache-isolation slice follows 7A-first. H7-4: 7C may configure a reviewed
cloud model for `agent_turn_fast` and a reviewed stronger one for `agent_turn_deep`, through a separate Agent adapter
(native streaming and tool calling, Agent Contract and memory semantics, per-round funding and attribution), failover
only before the first streamed token, one `orena.message` per learner turn; Ollama Cloud evaluated, not assumed. H7-2,
H7-7 and H7-8 stay open; no routing, credit, quota or funding enforcement is enabled. | Provider privacy no longer
blocks, while each learner model still earns its place; limits stay data, not code; no learner result crosses an
account. | `PR-MON-7_DESIGN.md` §12 and §14.


D-MON-026 | 2026-10-15 | PR-MON-7 owner decisions closing H7-7 and H7-8, completing H7-4 and fixing the H7-2 process
(same owner message as D-MON-025). H7-7: provider credits are never zero model cost; `economic_cost_usd` stays the
catalogue/reference estimate; an owner-configured Ollama Cloud covered-credit allowance in USD of estimated economic
cost, monthly, explicit configuration (amount, window anchor), default 0/disabled, shared-ledger accounting with used
and remaining estimates; `provider_credit_estimated` while available, `unknown` otherwise; exhausted or unknown skips
the Ollama Cloud primary (reviewed paid backup within its own cap, else graceful failure), never pay as you go; the
80%-of-visible-credit rule is operator guidance, with no balance API, assumed credit amount or scrape. H7-8: the
existing paid quality baseline of each 7A-first capability is its candidate reviewed backup, no new model searched;
daily caps $0.50 (`writing_evaluator`), $0.50 (`writing_improver`), $1.00 (`text_discussion`), Admin-editable
infrastructure caps; closed once the baseline ids are verified, unresolved ones reported. H7-4: Ollama Cloud must
separately prove tool calling, streaming, multi-round state, Agent Contract compatibility, privacy, latency and quality
for 7C. H7-2 stays open: benchmark live-catalogue candidates against the paid baseline (guideline: schema-valid >= 99%,
critical <= 1%, quality >= 95% of baseline with no bucket < 90%, p95 <= min(1.25x, 6 s), cost <= 50%); the owner
approves any winner explicitly. Delivery order and PR split: 7D1 decisions + cache isolation, 7D2 speech/TTS meters,
7B1 plan meters, 7B2 follow-up routing, 7C adapter; each a draft PR synced to main. Everything stays off. | A covered
subsidy must never turn into silent cash spend, and a backup must be a model already trusted. | `PR-MON-7_DESIGN.md`
§12 and §14.


D-MON-027 | 2026-10-15 | Owner clarifications for PR-MON-7D1. H7-8 is DECIDED: the exact existing Gemini baseline
(`gemini` / `gemini-3.5-flash-lite` by repository evidence) is the backup strategy, pending one operator verification of
the live `ai.active_selection` / `ai.capability.*` rows before it enters a production reviewed backup allowlist;
repository documentation is never treated as proof of the runtime row, and 7D1 is not blocked. Learner cache scope is
the account incarnation wherever the backbone exposes it: server-verified public/published content may use the shared
in-process cache and the shared persistent DerivedStore; learner/private content uses an incarnation-scoped in-process
cache and is never persisted to the shared store; where no incarnation can be obtained safely the seam bypasses
learner caching rather than falling back to a global cache; raw client account/content identifiers are never scope
authority; no new table for learner-derived cache in 7D1. The tests that locked the old client-asserted `article:`
persistence are replaced by authority-boundary tests. | Learner-derived answers stay with the account incarnation
that produced them. | `PR-MON-7_DESIGN.md` §14.7, §14.8; `PR-MON-7D1_REVIEW_REQUEST.md`.


D-MON-028 | 2026-10-15 | H7-8 runtime verification (operator, read-only). On the :8000 runtime database a read-only
transaction read `platform_settings`: `ai.active_selection`, `ai.capability.writing_evaluator`,
`ai.capability.writing_improver` and `ai.capability.text_discussion` are all `gemini` / `gemini-3.5-flash-lite`, with
no backup provider or model. No row was modified. H7-8 is therefore closed on runtime evidence: that exact pair is the
reviewed paid backup of the three 7A-first capabilities, to be entered into their allowlists only by the activation
change (with the D-MON-026 caps), never automatically. | D-MON-027 required the live row, not documentation. |
`PR-MON-7_DESIGN.md` §12, §14.7.


D-MON-029 | 2026-10-15 | Domain boundary (owner). Three domains with one contract between them: Billing / Commerce
(checkout, subscription and payment, SePay / payOS / Polar, credit top-up when Credits are used, transactions,
webhook/IPN, refund and reversal, reconciliation, payment status, pricing and packs, production payment rollout)
records and settles the payment and grants the purchased commercial product or credits; Plan & Entitlements (feature
access, plan entitlements, quota, semantic meters, usage, Free/Plus/Pro limits, the Plan & Usage UI) resolves the
effective plan, feature access and quota; AI Economics / Routing Optimization
(Admin > AI & Models: provider/model registry, capability routing, model qualification and benchmark, quality, latency,
provider cost and credits, per-tier routing policy, spend caps, fallback, margin, profit optimization under a quality
floor) chooses the provider and model; a provider call returns usage, cost and latency evidence. Billing and cost
accounting receive only `operation_id, capability, provider, model, usage, estimated/actual cost`, never why a model
was chosen. No provider or model is globally fixed for Orena: Ollama Cloud is one provider in the pool beside Gemini,
OpenRouter, Azure, Groq and later ones; selection is per capability by quality, privacy class, plan tier, cost and
budget, latency, availability, covered capacity, spend cap and fallback policy; Free may prefer deterministic/cache,
then free, covered or cheap qualified models, Plus/Pro a better pool or a higher budget. A benchmark qualifies a
model per capability (eligible for one, not for another) and never picks a single winner; nothing is auto-promoted.
H7-2 is stopped in the Billing lane (no benchmark run, no Ollama Cloud credits spent, no corpus/golden/grader built
for it): the working key and the 18-model live catalogue confirm the integration only, and H7-2 moves to the AI
Economics backlog. It is not a Billing completion gate. PR-MON-7B2 is split: 7B2a (wiring `word.assist`,
`reading.assist`, `writing.task` with deterministic/stored/safe-cache first) belongs to Plan & Entitlements; 7B2b
(provider/model pool, free/covered/cheap routing, fallback, quality/cost optimization) and 7C (Intelligence routing)
belong to AI Economics. Billing is complete when a user pays, the payment is confirmed, the right plan or credits are
granted, and the transaction can be reconciled and refunded safely. Nothing is activated by this decision. | The
lanes stop treating model quality as a payment blocker, and a payment never depends on which model answered. |
`BILLING_STATUS.md` (boundary, sequence, payment-ready list), `BILLING_LANE.md`, `PR-MON-7_DESIGN.md` header.


D-MON-030 | 2026-10-17 | Domestic bank and QR account (owner, after SePay Test Mode and one Live transfer on the
`:8031` sandbox; revised after the delta review of `5b396941`). Production uses **VPBank** through SePay, the only bank
the owner can currently link (supersedes the VietinBank assumption of D-MON-024; the adapter is bank-agnostic by
configuration; NAPAS BIN `970432`). The memo keeps `SEVQR <PREFIX><code>` (harmless with VPBank; SePay parsed the code
through it). The learner must not see the owner's main account number in production. Orena can put a configured
virtual account (`SEPAY_VA_NUMBER`, `[0-9A-Z]{1,19}`) in the VietQR while still receiving and matching only on the
main account and the exact payment code. In production, SePay checkout without a valid VA fails closed
(`sepay_va_unset`); development and test keep the main-account QR. That production *uses a VPBank VA* is not decided:
SePay documents VPBank official VA as Test-Mode-only today, so the VA must be proven on the real Live account
(activation gate 8). If Live cannot provide one, production SePay checkout stays closed until the owner decides
otherwise explicitly. A VA hides the account number, not the owner's name (RR-8.2). Gates 1-6 passed (Test Mode
webhook, cursor, bank reference, `webhook_success`, QR scan; one Live main-account transfer, paid once and refunded).
| No production checkout that exposes the main account, and no production claim proven only in Test Mode. |
`PR-MON-8_DESIGN.md` §13.


D-MON-031 | 2026-10-17 | Gate 7 preparation (owner). Launch prices for the SePay domestic gateway are the plan
catalogue's current values (Plus 199,000 VND a month and 1,590,000 a year; Pro 399,000 and 3,190,000), sold through
`sepay` as one-time prepaid periods. The production host is chosen after the app is deployed to the VPS. The owner runs
gate 7 personally (migration 0027 -> 0033, environment, SePay Live webhook, restart, grace 1 h, readiness) from
`RUNBOOK_SEPAY_ACTIVATION.md`; no agent runs it. The `:8031` sandbox and its quick tunnel were removed. Credits, quota
and funding enforcement, migration 0034 and the SePay feed stay off. | A price the owner chose explicitly, and a
launch operated by the owner on a host chosen deliberately. | `RUNBOOK_SEPAY_ACTIVATION.md`.


D-MON-032 | 2026-10-17 | Payment model (owner). **Plans are card subscriptions; only Credits use a bank-transfer
QR.** Plus/Pro are sold as auto-renewing subscriptions on a card the learner registers in billing, charged every month or
year like other market apps. The subscription gateway is **Polar** (merchant of record, international cards, USD; the
adapter exists since PR-MON-1..3). SePay's VietQR bank transfer is used **only to top up Credits**. A domestic
recurring-card gateway is not chosen now; it may be researched later if many learners lack an international card.
Consequences:
- SePay never sells a plan. The code refuses a `sepay` plan price (a small change for review, `PR-MON-8_DESIGN.md`
  §14).
- D-MON-031's SePay plan prices are withdrawn. The catalogue's USD prices (Plus 9.99/79.99, Pro 19.99/159.99) are the
  candidates for Polar, to be confirmed as Polar products.
- Gate 7 splits:
  - **7a**, Credits by SePay: needs Credits enabled, R-MON-014, approved credit packs and prices;
  - **7b**, subscriptions by Polar: needs PR-MON-10 (Polar configuration, sandbox E2E, manage/cancel) and PR-MON-9
    (the Billing Sheet's card checkout).
- `RUNBOOK_SEPAY_ACTIVATION.md` is rewritten for 7a. Nothing is enabled. | Recurring revenue without monthly manual
  transfers, and one clear place for QR payments. | `PR-MON-8_DESIGN.md` §14, `BILLING_STATUS.md`,
  `RUNBOOK_SEPAY_ACTIVATION.md`.

