# Billing / Monetization lane — canonical context (master plan)

Lane-local context for `feature/monetization-billing-v1`. It routes to the owning documents and records what is
specific to this lane. It is not a second governance system: authority stays with `AGENTS.md`,
`docs/project/PROJECT_MEMORY.md` and the documents they name.

This file holds only **stable** product and architecture direction; the Master Execution Brief (human, 2026-10-13)
is its source. The lane's documents are one tree, mapped onto the brief's four files (§21):

| Brief | This lane |
| --- | --- |
| `MASTER_PLAN.md` | this file |
| `STATUS.md` (resume point) | `BILLING_STATUS.md` |
| `DECISION_LOG.md` (append-only, `D-MON-XXX`) | `DECISION_LOG.md` |
| `RISK_REGISTER.md` | `RISK_REGISTER.md` |

## Session protocol (brief §22, §23)

- **Start:** read this file, then `BILLING_STATUS.md` and the recent `DECISION_LOG.md` entries. Check actual `main`
  and the open lane PR, then continue from "Exact next action".
- **End:** update `BILLING_STATUS.md`, append any new decision, touch the risk register only when a real residual risk
  changed, record the commit SHA, and state the next atomic action.
- **One leader.** Subagents research, review and test. They own no decisions and keep no architecture truth of their
  own. Findings return to the leader, who updates these files.
- **Process size** (§24):
  - UI-only: browser check, max two repair cycles.
  - Feature: targeted tests plus API smoke.
  - Financial/security/release: full gate, migration review, webhook verification, E2E and the human gate.
  - No full CI after every small change.

## Goal

Free users genuinely experience Orena at very low marginal cost, and heavy compute is paid. Two exactly-once
guarantees: a payment is recorded once, and entitlement or credits change once. Orena never creates an
unlimited-cost Free user, and never dispatches expensive compute without entitlement, quota or reserved credits. No
enterprise billing rewrite.

## Domain boundary (D-MON-029, owner 2026-10-15)

**Billing handles money. Plan & Entitlements handle access and usage limits. AI Economics handles provider/model
selection and profit-quality optimization. No provider or model is globally fixed for Orena. Benchmark qualifies
models per capability and is not a Billing completion gate.** (D-MON-029)

```text
Billing                -> records/settles payment, grants the purchased commercial product or credits
Plan & Entitlements    -> resolves the effective plan, feature access and quota
AI Economics           -> chooses provider and model per capability
Provider call          -> returns usage / cost / latency evidence
```

This lane is **Billing / Commerce**. It is complete when a user pays, the payment is confirmed, the right plan or
credits are granted, and the transaction can be reconciled and refunded safely. Plan & Entitlements work (meters,
quota, Plan & Usage) and AI Economics work (routing, model qualification, H7-2) may still be delivered from this
worktree when the owner asks, but they are labelled by their own domain and never gate Billing.

## Product model (stable)

**Four economic modes**
1. **Free**: useful, not a demo, at near-zero marginal cost.
2. **Plus/Pro subscriptions**: payOS prepaid month or year in Vietnam; Polar subscription as merchant of record
   internationally.
3. **Prepaid credits / pay-as-you-go**: top up, use until zero.
4. **New-user trial**: a small promotional allowance on expensive features.

**Cost classes** (D-MON-001)

| Class | Features | Rule |
| --- | --- | --- |
| HIGH | voice, cloud STT and pronunciation, long media, Agent workflows, large context, multi-call generation | trial only, then subscription allowance or credits |
| MEDIUM | Writing correction, Intelligence Q&A, Reading context, grammar explanation, summaries, contextual translation | `cache → deterministic/local → free/cheap → stop at Free quota` |
| LOW | Reading, dictionary, saved vocabulary, review, collections, progress, cached and already-generated content | generous Free |

**Cost rules**
- The model chain is `deterministic → cache → local/free → cheap → expensive`, going deeper only when necessary.
- A provider's free model is not assumed to stay free, so free-model AI stays quota-controlled.
- **AI is invoked intentionally.** Never on screen open, word tap, card appearance or article load (§4).
- The acquisition loop is: read anything → tap a word → understand at once → save → review → ask AI only when needed.
  Orena Intelligence is the paid layer above it.

**Credits** (D-MON-002)
- An append-only ledger (`credit_accounts`, `credit_ledger`), never a bare `users.balance`. The ledger types are
  topup, consume, refund, reversal and admin_adjustment.
- Every mutation is idempotent per operation id. The balance is derived from the ledger, or cached in the same
  transaction as the ledger write.
- Credits are reserved before dispatch. The balance never goes negative, and there is no auto-recharge and no
  "charge later".
- `meter → credit price` is configuration that changes without a migration or code rewrite. Meters are reused
  (`orena.message`, `writing.review`, `pronunciation.audio`, `media.import`, `languages.target`).

**Quota + credits** (§11): plan allowance → credits, if the feature allows them → reserve → dispatch → settle →
release. With neither, the request is refused before any paid provider call. The existing quota system is extended,
not replaced.

**Trial** (§14)
- Allowances are configuration, reusable across features, never a UI hack.
- Exhaustion shows Upgrade and/or Use Credits, never a silent failure.
- **No trial reset by logout or account tricks.** The trial is bound to an identity that survives
  delete-and-re-register: an incarnation alone is not enough (risk R-MON-003).

**Gateways** (D-MON-003)
- payOS: plan access (payment → verified webhook → paid order → prepaid subscription → `paid_through`) and credit
  top-up (verified webhook → ledger credit, exactly once). An existing adapter that stays in the repository.
- **Domestic direction (D-MON-024, 2026-10-15):** payOS (a Casso-ecosystem product) is no longer the preferred
  production domestic gateway, because the owner's banks are not supported. The primary candidate is SePay +
  VietinBank, built and validated in PR-MON-8 behind the same `PaymentFact` (`DOMESTIC_GATEWAY_SEPAY_ASSESSMENT.md`).
  payOS remains the alternative only if a supported bank path appears later. Activation is a human gate.
- Polar: Orena consumes its lifecycle (active, trialing, past_due, canceled, `current_period_end`,
  `cancel_at_period_end`) and rebuilds none of its tax, VAT, invoice or renewal. No invented local cancellation state.

**Checkout** (§7): plan → period → price → confirm → operation UUID → checkout → gateway. A return URL never grants
anything; only verified gateway state does. Checkout runs only at a server-offered price matching the catalogue, in
plan, period, currency and amount (D-MON-005).

**Readiness** (§6): a gateway is ready only when the billing switch, the DB/schema, the account backbone, the
credentials, the price configuration and the webhook configuration are all valid. Readiness never exposes secrets.

**Margin** (D-MON-007): keep the data needed for cost per Free, Plus and Pro user; cost by feature and by
provider/model; revenue against cost; and heavy users. One power user must not be able to silently create large
losses.

**Admin minimum** (§16, no redesign)
- Billing runtime status and gateway readiness.
- Orders, subscription state, credit balance and ledger.
- Cost records and quota usage.
- A blocking price mismatch.
- Manual adjustment and refund, with authorization and audit.

**Learner copy direction** (§17; the design still owns the visuals)
- Free: learn normally with limited AI. Plus: AI as a regular assistant. Pro: higher AI, voice and Agent limits.
- Pay as you go: "Không muốn đăng ký? Nạp tiền và dùng bao nhiêu trả bấy nhiêu."
- Wallet: balance, top up, approved packages, recent transactions, "No automatic recharge".

**Out of scope** (§20) unless payment safety needs it: Stripe, accounting platform, affiliates, family plans,
gifting, coupons, referral credits, enterprise billing, invoicing UI, revenue analytics, wallet gamification, crypto,
arbitrary currencies, finance reporting, any billing rewrite.

**Required test classes** (§19)
- Payment: checkout, duplicate operation, duplicate webhook, invalid signature, wrong price, wrong currency, refund,
  deleted account.
- Credits: top-up once, webhook replay, consume once, retried consume, insufficient balance, provider failure,
  reservation release, refund/reversal.
- Entitlement: Free allowance, Free exhausted, paid quota, paid quota exhausted with and without credits, no dispatch
  when funding is unavailable.
- Cost protection: expensive paths cannot bypass admission.

**Human gates** (§25): stop and report rather than decide on final prices, credit conversion, meter credit prices,
trial quantities, production credentials, migration promotion, legal/refund/terms, production activation.

## Lane

| | |
| --- | --- |
| Worktree | `C:\Users\calis\Downloads\Orena-Billing` |
| Branch | `feature/monetization-billing-v1` |
| Base | `main` `172ae216397e6dfaa1f74aa32417f48b7c2365fd` (2026-10-13) |
| Owns | billing / monetization implementation: gateways, orders, webhooks, entitlement grant from payment, price alignment, refunds, reconciliation, billing activation plumbing |
| Does not own | learner or admin UI design (UI lane, `codex/work`), the Agent Contract (D-086), quota metering already reviewed (D-161..D-172), project-wide decision numbers |
| Runs in parallel with | the UI lane; never depends on its uncommitted work |

Not named in `AGENTS.md` §3 yet. Report that at merge; do not edit `AGENTS.md` from this lane.

## Isolation rules (human instruction, 2026-10-13)

- Do not use `:8000` (public staging, D-146), `:8010` (preview) or `:8021` (UI-lane QA) unless the human authorizes it.
- Runtime tests use a **separate Billing sandbox**, allocated when needed (proposed `:8031`, own compose project and
  own volumes, never `ai-writing-coach-data` / `ai-writing-coach-postgres-data`). Only one lane runs conflicting
  Docker test containers at a time; check `docker ps` and free RAM (> 2 GB) first.
- Shared files (`app.py`, auth/entitlement, quota/meter code, `CURRENT_HANDOFF.md`, `AGENTS.md`, Product Catalog and
  pricing UI contracts): inspect latest `main` first, keep the change minimal, note the overlap in `BILLING_STATUS.md`
  ("Cross-lane conflicts"), redesign no unrelated UI.

## Decision IDs

Do not claim `D-188` or any project-wide number. Use `D-MON-001`, `D-MON-002`, ... recorded in `BILLING_STATUS.md`
("Lane decisions"); the project number is assigned at merge.

## Migration rule

- The actual Alembic head is `20261005_0026` (`ai_cost_records`). It is re-parented on `20261008_0030`, so the
  filename order is not the chain order (0025 → 0029 → 0030 → 0026).
- `migrations/proposed/20261005_0027_billing_orders.py` is parented on 0026. `0028_reading_derived_texts` (proposed)
  is parented on 0027, so promoting 0027 forces a decision on 0028's parent too.
- No billing migration is applied to a shared environment by this lane. Each one goes through independent
  architecture review (AGENTS.md §1: payment/entitlement), a rehearsal on a copy, and human authorization.
- 0026 is promoted in source only (D-177); `:8000` deployment sequencing around it is still open on `main`.

## Sources of truth

| Topic | Authority |
| --- | --- |
| Billing design, gateways, review history | `docs/project/proposals/BILLING_GATEWAYS.md` |
| Commerce lifecycle, ordering, event receipts | `docs/product/ORENA_COMMERCE_ARCHITECTURE.md` (stale on plan names: Free/Premium) |
| Plans, prices shown, limits | `writing_coach/product/catalog.py` + Admin `product.plan_catalog` (D-153) |
| Plan quota enforcement | `writing_coach/product/quota.py` (D-161, reviews in `docs/reviews/architecture/*QUOTA*`) |
| Manual plan grant | `writing_coach/product/membership.py` (D-154) |
| Learner plan / pricing / billing sheet visuals | Claude Design frames "Plan & usage", "Pricing", "Billing Sheet" in `Orena.dc.html` (D-067, D-088) |
| Legal commitments (refund, terms) | `docs/legal/public/*.json` (served); `DRAFT_*.md` are superseded |
| Human gates | `docs/project/ARCHITECTURE_INVARIANTS.md` "Human gates" (billing, paid providers, schema, production) |
| Monetization brief | the human's Monetization/Billing Master Brief (pending; record its location here once received) |

## Code map

| Area | Files |
| --- | --- |
| Gateway layer | `writing_coach/billing/{gateway,payos,polar,prepaid,service}.py` |
| HTTP | `writing_coach/billing_api.py` (offers, checkout, webhooks, admin refund); wired at `app.py:1215-1235` |
| Persistence | `writing_coach/persistence/billing_repository.py` (`billing_orders`), `commerce_repository.py` (0006 tables) |
| Effective plan | `writing_coach/product/service.py:70` → `persistence/product_repository.py:45` (legacy `subscriptions`) |
| Tests | `tests/test_billing.py`, `tests/test_product_commerce.py`, `tests/test_product_membership.py` |
| Env names | `BILLING_ENABLED`, `BILLING_PRICES_FILE`, `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY`, `POLAR_ACCESS_TOKEN`, `POLAR_WEBHOOK_SECRET`, `POLAR_ENVIRONMENT` (not yet in `.env.example` / `compose.yaml`) |
