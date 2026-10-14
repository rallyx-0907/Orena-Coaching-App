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
