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
