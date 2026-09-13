# Orena Commerce Read-Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver I3's first implementation phase — "read adapters preserving
current truthful states" — under `docs/product/ORENA_COMMERCE_ARCHITECTURE.md`
§5, without touching schema, enforcement or the I2 activation gate.

**Architecture:** Wrap the existing, already-tested `ProductService`/
`ProductRepository` read path in the canonical `accountCommerce`/
`resolveEntitlement` contract shape from §2, additively. Do not replace
`account_state`/`feature_access` — `tests/test_product_account_state.py`
already locks their shape, including mobile-contract parity (R15 closeout).

**Tech stack:** Existing FastAPI route, `writing_coach/product/*`,
`writing_coach/persistence/product_repository.py` (PostgreSQL), pytest.

**Spec:** `docs/product/ORENA_COMMERCE_ARCHITECTURE.md`,
`docs/project/ORENA_BACKBONE_INTEGRATION_GATES.md` (I3 row).

## Why this scope, and not more

`ORENA_BACKBONE_INTEGRATION_GATES.md` gates I3 on "I1-I2 transaction
foundation; read UI first; enforcement/provider activation separately gated."
Two things bound this plan to the read phase only:

- **I2 is schema-deployed but flag-off** (`I2_ACTIVATION_RUNBOOK.md` §6, §9).
  The runbook is explicit that wiring any write path happens *after*
  `ORENA_ACCOUNT_BACKBONE=on`, which is a HUMAN GATE, not done and not asked
  for. §4's `reserve`/`settle` admission needs a durable reservation, which is
  I2 write-path territory — out of scope here.
- **Discovered gap:** `writing_coach.reference_backbone.Scope` and
  `account_profile.scope_of()` (I1) have no live caller anywhere in `app.py` —
  only their own test exercises them (`scripts/test_orena_account_profile.py`).
  I1's incarnation-scoped identity is a pure, tested decision layer, not yet
  wired to a real request. Canonical incarnation-scoped commerce therefore
  cannot be built honestly yet either. This plan keys off the existing,
  live `user_key` identity (`current_user_key()` in `writing_coach/product/api.py`)
  the same way the current `/api/product/me` route already does, and does not
  invent incarnation wiring as a side effect.

**Global constraints:**
- No schema, migration, or `ORENA_ACCOUNT_BACKBONE` change.
- No enforcement: `billing_ready` stays `False`; no route may deny a request
  based on `resolveEntitlement` yet — display only.
- Preserve `ProductService.account_state`/`feature_access` and every existing
  `/api/product/*` response shape byte-for-byte; add, do not rename or replace.
- EN/ZH parity for any new learner-facing copy.

---

### Task 1: Canonical read-adapter module

**Files:**
- Create: `writing_coach/product/commerce.py`
- Test: `tests/test_product_commerce.py`

**Interfaces:**
- Produces: `SubscriptionState` enum-like literal set
  (`none|pending|trialing|active|past_due|paused|ended|unknown`);
  `accountCommerce(user_key: str) -> dict` (plan, subscription with the
  canonical state vocabulary, features, `billing_ready: False`,
  `readiness: "known"|"unavailable"`); `resolveEntitlement(user_key: str,
  feature: str) -> EntitlementDecision` (`feature, allowed: bool | None,
  reason, entitlement_state, quota: {limit, used, remaining} | None`).
  `allowed=None` means unknown, never treated as denied or granted.

- [ ] **Step 1: Write failing contract tests**

  Assert: an unrecognized provider status (e.g. `"paused"`, `"unknown-status"`)
  maps to its own canonical state instead of collapsing into `inactive`;
  `resolveEntitlement` returns `allowed=None` (not `False`) when usage lookup
  raises, mirroring today's `usage_state="unavailable"`; `accountCommerce`
  never includes a provider/customer identifier; existing
  `ProductService.account_state`/`feature_access` outputs are unchanged by
  this module's existence (import both, assert no monkeypatching occurred).

- [ ] **Step 2: Run and confirm failure**

  `python -m pytest -q tests/test_product_commerce.py` inside the hermetic
  Docker recipe (`AGENTS.md` §9). Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement the adapter**

  Build `commerce.py` on top of `product_service` only — no new repository,
  no new table. Map `SubscriptionService`'s current two-state
  (`active|trialing` vs. everything else) into the fuller canonical
  vocabulary only where the underlying status string already distinguishes
  it (e.g. `past_due`, `paused`, `ended` if the repository ever returns
  them); anything not recognized is `unknown`, never guessed into `active`
  or `none`.

- [ ] **Step 4: Pass the contract tests, then the existing product suite**

  Run `tests/test_product_commerce.py`, `tests/test_product_account_state.py`,
  `tests/test_product_foundation.py`, `tests/test_persistence_runtime.py`.
  All must pass; the existing three must be byte-for-byte unaffected.

- [ ] **Step 5: Commit**

  Stage only the two files above and commit
  `feat(commerce): add the canonical read-adapter contract`.

---

### Task 2: Surface it as a real learner-facing read (investigate destination first)

**Files:** TBD after inspection — likely one of the eleven destinations' Profile
surface plus `static/orena/infrastructure/api.js` (the `productMe()` client
call already exists and is currently unused by any UI module — confirm with
`grep -rn "productMe" static/`).

- [ ] **Step 1: Locate the correct destination**

  Read `ORENA_REFERENCE_ARCHITECTURE.md`'s eleven-destination map and the
  current Profile/Growth room module. Confirm whether a plan/usage read
  belongs there or is a new sub-view; do not invent a twelfth destination.

- [ ] **Step 2: Write failing UI contract assertions**

  In the relevant `scripts/test_orena_*.mjs` gate (existing or new): assert
  the surface renders known plan/feature-usage facts, renders an explicit
  "not yet available" state when `readiness: "unavailable"`, and never
  renders a provider/customer identifier or an enforcement action (no
  "upgrade" call-to-action wired to a real checkout — `billing_ready` is
  `False`).

- [ ] **Step 3: Implement the read-only view**

  Call `api.productMe()`, render via `accountCommerce`'s shape. No theme,
  layout-primitive, or protected-area change beyond what the destination's
  existing module already owns.

- [ ] **Step 4: Pass Foundation and the ESM graph gate.**

- [ ] **Step 5: Commit**

  `feat(commerce): show plan and usage in <destination>`.

---

### Task 3: Record truth and hand off

- [ ] Update `docs/project/CURRENT_HANDOFF.md`: I3 read phase status, the
  Scope/incarnation gap finding, and the exact next task (subscription
  inbox/reconciliation repository, per §5's second implementation phase —
  still gated from real provider credentials).
- [ ] Update `docs/project/CURRENT_PRODUCT_STATE.yaml` only if verified truth
  changed (a new passing test count, a new reviewable route).
- [ ] `python scripts/validate_project_memory.py`, then commit
  `docs(commerce): record the I3 read-adapter slice`.
