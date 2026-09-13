# Architecture Invariants

These rules must not drift through incidental implementation work. Changing an
invariant requires an explicit accepted decision, an appended Decision Log
entry, and corresponding current-state and handoff updates.

## Persistence

- PostgreSQL is authoritative.
- SQLite is frozen rollback/archive only.
- No dual-write.
- No reverse sync from PostgreSQL to SQLite.
- No silent SQLite fallback.
- No startup import.
- No automatic startup Alembic.
- No destructive persistent-volume cleanup.
- Production data mutation is always a human gate.
- Schema ownership remains Alembic-based for PostgreSQL.

## Frontend

- Orena is the active product identity and `/` is the canonical learner route.
  `/becoming` is compatibility-only; legacy BECOMING-named filesystem
  namespaces do not define current product direction.
  These invariants protect technical consistency, accessibility, responsive
  behavior, shared contracts, and regression safety.

Learner-facing product hierarchy, visual composition, and experience direction
are governed by `docs/product/ORENA_PRODUCT_CONSTITUTION.md`.

Shared primitives should be preserved and reused where useful, but existing
screen composition is not permanently frozen when a deliberate product task
requires it to evolve.

- `BECOMING_FRONTEND_VERSION` remains exactly `2.17.5` until an explicitly
  scoped, reviewed change updates it.
- Backend and architecture tasks do not casually touch frontend code or assets.
- Preserve shared responsive behavior, accessibility, EN/ZH parity,
  light/dark parity, and reusable design-system primitives.
- Journey, Review, Library / Active Recall UI, shared layout primitives,
  gutters, spacing, overflow, and container-width primitives are protected.
- `static/becoming/orena/**` is the bounded frontend `2.17.5` presentation layer
  for the shared Orena shell and learner screens. Its `--o-*` tokens and `.o-*`
  primitives remain shared; dedicated screen styles may compose them but must
  not copy shared tokens, layout primitives, or responsive contracts into new
  page-local systems. D-024 completes the approved screen migration without
  relaxing protected domain, persistence, EN/ZH, accessibility, or learner-flow
  contracts.
- `docs/visual-references/**` remains untouched unless explicitly scoped.

## Content and learning domains

- Reading, Writing, Listening, Speaking, and Vocabulary are Orena's five
  separate canonical content domains (D-049, corrected by D-050). Do not
  force them into one universal content schema; they share infrastructure
  (ingestion, rights, search, feed) through
  `docs/product/ORENA_CONTENT_ARCHITECTURE.md` §4, not a merged object model.
- The Understanding Engine is a horizontal capability shared across all five
  domains (`docs/product/ORENA_UNDERSTANDING_ENGINE.md` §1) — it is not a
  sixth domain, and it must not be built on a required precomputed knowledge
  store; it generates from the learner's exact context (D-050,
  `docs/project/LEGACY_TOMBSTONES.md`, "Language Knowledge modeled as a sixth
  content domain / mandatory precomputed graph").
- Discover/Home distribute content from domain libraries; they must not own
  hard-coded canonical content
  (`docs/project/LEGACY_TOMBSTONES.md`, "Discover/Home owning hard-coded
  canonical content").
- The Understanding Engine (`docs/product/ORENA_UNDERSTANDING_ENGINE.md`) must
  always distinguish four things — mental model, mnemonic, linguistic
  explanation, and verified etymology/history — and never present an invented
  mental model or mnemonic as verified linguistic fact.
- Orthography (stroke order and equivalents) is implemented as a general
  `orthography` capability, never hard-coded to one script
  (`docs/product/ORENA_VOCABULARY_ARCHITECTURE.md` §4).

## Multilingual product

- Shared product behavior applies to EN and ZH.
- A shared feature is implemented once through a language-neutral contract.
- Language adapters are used only for genuine linguistic differences.
- Future languages plug into shared contracts rather than receiving copied
  product flows.
- Conceptually language-scoped learner data is isolated by user and learning
  language.

## Closed-stage protection

- A reviewed CLOSED subsystem is a protected baseline. Later work consumes its
  contracts instead of casually replacing or refactoring it.
- R5 Grammar Knowledge System is closed at the PR #44 baseline: preserve stable
  Grammar Concept IDs, Static Grammar KB authority, schema-v2 models, the shared
  renderer, multilingual language-context separation, and Grammar runtime AI
  `0`.
- Do not re-run or recreate superseded broad structural Grammar migration write
  paths over concept-specific authoring.
- M1 Shared Media Learning contracts are likewise protected: one canonical
  media asset/transcript/segment model is reused by Listening and Speaking
  Shadowing.
- Reopening a closed subsystem requires a concrete regression, explicit product
  extension, or accepted architecture decision.

## Release operations

Release order is an operational rollout decision.

It does not define Orena's conceptual product hierarchy.

A capability may reach public readiness earlier than another capability without
becoming the identity or organizing principle of Orena.

Current release state and operational gates are recorded in
`PROJECT_STATE.md`, `CURRENT_HANDOFF.md`, and relevant accepted decisions.

No learner-facing capability may be promoted to public without the required
review and explicit human authorization.

## AI Platform

- The AI Control Plane owns AI infrastructure and AI workload configuration;
  it is not a general product-domain registry.
- `reading_evaluator` and `writing_linguistic` are deterministic and not
  provider-configurable. Word segmentation and part-of-speech tagging are a
  solved local problem; a provider must never be routed either workload.
- Speech capabilities are reserved and unimplemented until Speaking work
  explicitly implements them.
- Capability configuration and diagnostics never persist or expose credentials.
- No provider-to-provider fallback or silent paid-provider failover.
- Shared-media translation may select Groq or local Marian once from explicit
  configuration; a provider failure must stop rather than silently fail over.
- Static configuration validation remains separate from live provider/model
  testing.
- Learner `generate_structured()` remains on legacy `active_selection()` until
  one reviewed atomic activation switches the whole runtime contract.
- Persisted fallback policy is metadata until runtime activation explicitly
  implements its behavior.

## Mobile

- docs/project/MOBILE_IMPLEMENTATION_SPEC.md is the canonical implementation
  contract for R19-R21. Mobile implementation and review must not contradict it
  without an explicit accepted architecture decision.
- The native mobile client uses **React Native + Expo + TypeScript** in a
  dedicated `mobile/` workspace.
- Mobile consumes the same authoritative backend/domain contracts as web; there
  is no mobile-only learning architecture, scoring model, Grammar curriculum,
  Media Learning model, or learner-progress authority.
- Web DOM/CSS is not copied into mobile as a second presentation implementation,
  and a WebView is not the primary mobile product shell.
- Provider/API secrets remain server-side. Mobile configuration may contain only
  non-secret public endpoints/identifiers intended for client distribution.
- Sensitive authentication/session material is stored only through OS-backed
  secure storage; ordinary app cache/storage must not hold reusable secrets.
- EN/ZH parity, accessibility, light/dark behavior, language-scoped learner data,
  and truthful degraded/unavailable states apply equally to mobile.
- Immutable/versioned reference data may use bounded client caching; mutable
  learner/server state remains server-authoritative. Large server datasets are
  not bundled into the app by default.
- Microphone/audio capture remains transient by default and must not introduce
  raw-audio persistence without an explicit accepted decision.
- Android and iOS share one product contract. Platform-specific adapters are
  allowed only for genuine native differences such as permissions, audio,
  secure storage, deep links, and system integration.

## Operations

- Never use `docker compose down -v`.
- Never print or commit secrets, credential-bearing URLs, authorization
  headers, or raw sensitive provider responses.
- No automatic production migration or production capability-row mutation.
- Cloudflare, DNS, OAuth, secret, and production staging infrastructure changes
  require explicit scope and human authorization.
- Do not casually re-enable the disabled Windows Cloudflared service; the
  Docker connector is canonical.
- Preserve rollback evidence and persistent PostgreSQL data.

## Git

- `main` is stable and verified; development occurs on `codex/*` or an
  explicitly approved development branch.
- Never force-push `main`, merge automatically to `main`, or rewrite verified
  history.
- Never use `git clean -fd`, arbitrary `git add -A`, or destructive
  `git reset --hard` without explicit authorization.
- Do not delete unrelated untracked files or `docs/visual-references/**`.
- Stage only files belonging to the coherent reviewed change.
- Leave every checkpoint reviewable with exact validation and status evidence.

## Human gates

Stop before production data mutation, runtime activation, unapproved schema or
Alembic work, Cloudflare/DNS/OAuth/secret changes, paid-provider or billing
decisions, destructive Git, volume deletion, public release, rollback-path
removal, ambiguous architecture decisions, unresolved P0 findings, or repeated
P1 findings that require broader redesign.

Delegated by D-054, inside the assigned lane and the **sandbox only**:
applying an independently approved additive migration and switching
`ORENA_ACCOUNT_BACKBONE` on, under the runbook's safety gates. Production
(8000) and preview (8010) keep every gate above.
