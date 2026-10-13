# Billing / Monetization lane — canonical context

Lane-local context for `feature/monetization-billing-v1`. It routes to the owning documents and records what is
specific to this lane. It is not a second governance system: authority stays with `AGENTS.md`,
`docs/project/PROJECT_MEMORY.md` and the documents they name. Live state is in `BILLING_STATUS.md` next to this file.

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
