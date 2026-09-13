> **Authority scope**
>
> This document records verified implementation, runtime, operational, release,
> and technical state.
>
> It does not define Orena's Product North Star or learner-facing information
> architecture.
>
> Current learner-facing product direction is defined by:
>
> `docs/product/ORENA_PRODUCT_CONSTITUTION.md`
>
> and:
>
> `docs/product/ORENA_CONTENT_ARCHITECTURE.md`
>
> Existing UI and historical release sequencing are implementation evidence,
> not permanent learner-facing product authority.

# Verified Project State

## Provider credential configuration

The Admin application has a server-managed provider credential flow for local
QA: same-origin authenticated test/save/remove actions, encryption before
platform-store persistence, and masked status responses. Provider/model
capability configuration remains secret-free. The separate
`AI_PROVIDER_SECRETS_KEY` bootstrap secret is required at runtime and must be
delivered through an approved secret store. Production credential bootstrap,
live validation, runtime activation, backup/restore, and public release remain
human-gated.

This document records verified current truth only. It is not a wish list or a
historical narrative.

## Identity and versions

- Product: Orena. BECOMING-named paths and symbols are legacy technical
  compatibility, not the active product identity.
- Repository: `CalisJI/ai-writing-coach`
- Last verified application/runtime baseline:
  `7b1740e66a3f8ef82b2fc728dedaf7dd2c1d1b6f`

This SHA identifies the verified application/runtime baseline inherited by this
governance checkpoint. Documentation-only or governance-only descendant commits
may advance `main` without changing that baseline. Update this field only after
a reviewed change materially changes verified application, runtime, product, or
operational state.

- Application version: `1.4.0`
- Legacy-named `BECOMING_FRONTEND_VERSION` compatibility pin: `2.17.5`
- Current Orena program: **R21 Mobile Release Readiness — HUMAN STORE-RELEASE
  GATE.** R0–R20 local foundations are preserved; R20 delivered the real native
  learner flows on top of those contracts and R21 prepares controlled release. R8/R11 promotion, R2 activation,
  production operations, store signing/credentials, billing, and public release
  remain deferred human gates and do not block non-production mobile development.

## Orena UI/UX integration

- Branch `codex/orena-ui-ux-integration` now includes every previously missing
  commit from local `claude/work`: the `606f24c` Claude tooling checkpoint,
  `0053152` validator-governance checkpoint, and the `43` application commits
  through `04bfb97`. Claude tooling/hooks are present and historical release
  gates are archived; no source commit remains intentionally excluded.
- Frontend `2.17.5` keeps one shared Orena shell, token, primitive, responsive,
  EN/ZH, accessibility, and light/dark contract. Dedicated Orena presentation
  layers now cover Home, Writing, Review, Reading, Listening, Speaking,
  Grammar, Library, Journey, Profile, onboarding, and sign-in; this completes
  the bounded screen migration accepted in D-024.
- Profile uses grouped learning, learning-experience, appearance, and account
  settings with accessible custom select fields, three-state Pinyin, palette
  cards, truthful rollback after failed saves, evidence-derived Growth Rank,
  bounded mobile listboxes, and centered mobile chrome. Theme changes made in
  shared chrome remain synchronized with the Profile control.
- Grammar uses a deterministic pedagogy composition layer over the existing
  schema-v2 source models. Every one of the `508 / 508` EN/ZH lessons retains
  its stable Grammar Concept ID and source blocks, exposes block-type
  traceability, and renders a real primary model, formula/word-order treatment,
  contextual use, examples, contrasts, mistakes, practice, recall, and transfer
  where present. Open lessons use a focused workspace with a bounded teaching
  column and `288px` rail; mobile uses one column, the active lesson title and a
  fixed Back action. Back restores focus to the exact control that opened the
  lesson.
- The Chinese learner dictionary now has deterministic stroke-order practice
  backed by a vendored `9,565`-character, `14.1 MB` data pack and lazy-loaded
  renderer. `GET /api/chinese/stroke-order` is read-only, uses no AI or runtime
  CDN, reports unavailable glyphs truthfully, and exposes a stable source
  version with immutable ETag validation. The mutable/provider-backed
  `GET /api/dictionary` path is explicitly `no-store`. D-023 records the
  durable data and licensing decision.
- Writing/Review POS annotation and Listening transcript annotation now share
  one deterministic local implementation (`NLTK`/`jieba`/`pypinyin`) through
  `writing_coach/linguistic_annotation.py`. `writing_linguistic` is no longer
  provider-backed; its cache and public payload shape are unchanged. D-025
  records this decision.
- Shared-media translation keeps the provider-neutral boundary but selects
  Groq when `GROQ_API_KEY` is configured, with local Marian retained when no
  external key is present or when explicitly selected. Selection occurs once
  from `MEDIA_TRANSLATION_PROVIDER`; malformed/failed responses stop without
  provider failover. Quota headers are captured for a future admin surface.
  D-026 supersedes D-021's local default. No production key, activation, or
  deployment was changed in this sync.
- Media and speech routes that already expose semantic error categories now
  build the canonical `{category, message, retryable, context}` error envelope;
  the frontend request wrapper exposes those fields without branching on prose.
  `docs/ORENA_AI_COST_REDUCTION_PLAN.md` now records implemented P0/P2 slices;
  Groq selection remains configuration-driven and does not activate billing,
  quota enforcement, subscription enforcement, deployment, or production
  capability-mode cutover.
- Local automated evidence at
  `6c93d05b3cb1c79c2986af0ab4a83cf664eae3a9`: release gate PASS at frontend
  `2.17.5`; architecture PASS; full regression `561 passed, 3 warnings` with no
  failures or skips; browser ESM graph PASS with `50` linked modules; all nine
  CI Node media contracts PASS; Profile and Grammar contracts PASS, including
  `508 / 508` EN/ZH lessons; canonical error-envelope, Hanzi route/renderer, and
  Hanzi-pack digest checks PASS; Grammar pedagogy audit PASS for EN `269` and ZH
  `239`; focused linguistic/translation/capability coverage PASS (`101 tests`).
- Interactive Brave QA against an isolated current-branch runtime verified the
  Home, Profile, and Grammar flows at desktop and mobile breakpoints. Profile
  retained its two-column desktop hierarchy and single-column mobile layout;
  its open listbox stayed inside the viewport. Grammar retained its teaching /
  `26px` gap / `288px` rail layout on desktop, recomposed to one column on
  mobile, exposed ten traced source blocks, produced no horizontal overflow,
  and restored focus after Back. No browser console error was observed.
  Screenshot capture timed out in the browser integration, so human visual
  acceptance remains pending. The QA container used temporary `/tmp` SQLite,
  was removed after testing, and did not touch PostgreSQL or port `8000`.
- This checkpoint is not deployed and does not promote any learner skill to
  PUBLIC. Application version `1.4.0` and frontend version `2.17.5` are
  unchanged.
- The former one-shot release gates now live under
  `scripts/archive/release-gates/` as historical evidence. The surviving
  validators assert current contracts; no validator was weakened to make this
  batch pass.

## Persistence

- PostgreSQL is the authoritative runtime.
- SQLite is a frozen rollback/archive source only.
- There is no dual-write.
- There is no reverse sync from PostgreSQL to SQLite.
- There is no silent SQLite fallback from PostgreSQL runtime failure.
- There is no startup auto-import.
- A genuinely empty PostgreSQL runtime may bootstrap automatically to the
  current Alembic head. Any non-empty database with a missing or mismatched
  revision fails closed; existing runtime databases are never auto-upgraded.
- Persistent volumes are never cleanup targets. Normal development and
  operations must never use `docker compose down -v`.
- Governance work must not mutate production runtime data.

The repository still contains SQLite implementations and historical migration
tooling because rollback, archive inspection, tests, and the completed cutover
history remain relevant. Their presence does not make SQLite the deployed
authority.

## Production staging

- Public endpoint: `https://orena.chillpickle.org`
- Request path: Internet → Cloudflare HTTPS → Docker Cloudflare Tunnel
  connector → `writing-coach:8000` → PostgreSQL.
- Google OAuth production staging passed.
- Public health and readiness passed.
- Authenticated `GET /api/product/me` passed against PostgreSQL.
- EN learner staging smoke passed.
- ZH learner staging smoke passed.
- Library, Journey, and Profile staging smoke passed.
- The Windows Cloudflared service was intentionally disabled after duplicate
  tunnel replicas caused 502 behavior.
- The Docker Cloudflared connector is canonical. Unrelated work must not
  reconfigure or duplicate it.

## Product release architecture

- R15 — SaaS Plans, Entitlements & Usage Policy: **COMPLETE / LOCAL
  ACCEPTANCE PASS**. Authenticated account-state API, learner Profile, and
  read-only Admin surfaces now expose the existing Free/Premium catalog and
  PostgreSQL-backed usage with localized unavailable/exhausted/unlimited
  states. Billing and feature enforcement remain disabled.

- R16 — Advanced Learning Intelligence: **COMPLETE / LOCAL ACCEPTANCE
  PASS** for contextual dictionary lookups in Writing, Review, Reading, and
  shared Listening/Speaking transcripts; adaptive Writing difficulty;
  error-memory review cues; cross-skill transfer; and the scheduled Library
  review handoff. These behaviors share authenticated, source-grounded,
  language-scoped contracts with explicit insufficient, unavailable, and
  no-actionable-evidence states. Provider activation and live credentialed
  validation remain deferred.
  - R17 — Product Analytics & Operational Observability: **COMPLETE / LOCAL
    ACCEPTANCE PASS**. Admin-only activity, return, source-specific funnel,
    cost, learner-impact failure/degraded aggregates, and operational readiness
    evidence use bounded PostgreSQL/configuration records, redact learner
    identifiers and raw content, and expose explicit ready, degraded,
    insufficient, unavailable, or deferred states without learner-event writes
    or entitlement enforcement. The authenticated route boundary and
    aggregate-only redaction are covered by the mounted ASGI regression;
    live/production release gates remain deferred.

- R18 — Mobile/API Readiness: **COMPLETE / LOCAL ACCEPTANCE PASS**. The
  deterministic Chinese stroke-order endpoint now returns source/version
  metadata with public immutable cache semantics and conditional ETag support;
  unavailable data is explicitly non-cacheable. The provider-backed or mutable
  dictionary endpoint is explicitly `no-store`, preserving conservative web
  and future mobile behavior without duplicating datasets client-side. The
  authenticated `/api/session/bootstrap` route adds a compact, versioned,
  read-only session/language contract for web and future mobile consumers;
  production release remains governed separately. The media import status
  route also offers an opt-in bounded response for opaque resume polling while
  preserving the full acquisition response by default.

- R0 — Product Release Architecture: **CLOSED**.
- R1 — Production Staging + Cloudflare + Google OAuth: **CLOSED / PASS**.
- R2 — AI Capability Control Plane: **HUMAN GATE / READY, NOT PRODUCT-BLOCKING**.
- M1 — Media Learning Foundation: **CLOSED / FOUNDATION COMPLETE**.
- R3 — Writing Evaluation Completion: **COMPLETE / LOCAL ACCEPTANCE PASS**.
- R5 — Grammar Knowledge System: **CLOSED / APPROVED / merged via PR #44**.
- R6 — Speaking Core: **COMPLETE / LOCAL ACCEPTANCE PASS**.

Current learner skill truth:

| Skill     | Release state | Source    | Internal  | Public |
| --------- | ------------- | --------- | --------- | ------ |
| Writing   | BETA          | available | available | no     |
| Speaking  | DEVELOPMENT   | available | available | no     |
| Reading   | DEVELOPMENT   | available | available | no     |
| Listening | DEVELOPMENT   | available | available | no     |

The first public product gate requires all four conditions:

- Writing COMPLETE;
- Speaking COMPLETE;
- English PASS;
- Chinese PASS.

Only after that reviewed gate may Writing and Speaking be promoted to PUBLIC
together. Reading and Listening are later, separate releases. No current
learner skill is PUBLIC.

## Multilingual product rule

Shared learner-facing behavior applies to every supported learning language.
The current mandatory languages are EN and ZH. Do not build a shared feature
for English and later copy it for Chinese.

Use one shared language-neutral contract plus a language adapter only where a
real linguistic difference requires it. Examples include English tokenization,
phonemes, stress, and grammar details, and Chinese Hanzi segmentation, Pinyin,
tones, measure words, particles, and grammar details.

Conceptually language-scoped learner data remains isolated by:

`user + learning_language`

## M1 Media Learning Foundation

M1 is **CLOSED / FOUNDATION COMPLETE** after the explicit post-R5
program review. M1.1 through M1.6 are closed and merged. The provider-neutral,
learner-neutral Media Learning Object remains the canonical shared content
contract: source-language transcript, stable timestamped segment identities,
support-language translations, internal Listening consumption, and
shared-media Shadowing reuse the same asset.

Learner progress remains separate and scoped by user and learning language.
Future durable Listening progress belongs to R11, advanced Shadowing belongs to
R9, and full Speaking evaluation/pronunciation belongs to R7. Those stages
consume M1; they do not reopen or duplicate its foundation.

Explicit M1 closeout evidence remains canonical:

- M1.1 is **CLOSED / APPROVED / merged** — media object and segment contracts.
- M1.2 is **CLOSED / APPROVED / merged** — media ingestion and transcript acquisition.
- M1.3 is **CLOSED / APPROVED / merged** — Shared Media Translation.
- M1.4 is **CLOSED / APPROVED / merged** — Listening MVP integration and acceptance.
- M1.5 is **CLOSED / APPROVED / merged** — Active Listening transcript reconstruction.
- M1.6 Shared-media Shadowing integration is **CLOSED / APPROVED / merged** via PR #33.

One imported media source is represented once as a reusable Media Learning
Object and is consumed by both Listening and Speaking Shadowing through the same
canonical asset and timestamped segments. Learner progress remains separate.

M1.2 is **CLOSED / APPROVED / merged**. It established the authenticated media
import API, isolated YouTube adapter, explicit learning-language caption
selection, canonical transcripts, stable content-derived segment identities,
and provider-hosted playback without durable media persistence, audio download,
or audio transcription.

M1.3 is **CLOSED / APPROVED / merged**. It established one backend
support-language contract for `vi`, `en`, and `zh` and atomic enrichment of the
same Media Learning Object through the existing `learner_translation`
capability, with explicit ready, not-required, transcript-unavailable,
too-large, and unavailable states.

PV-2 / OREN-10 merged the first authenticated internal Listening workspace.
PV-3 / OREN-11 merged selected-segment navigation, Previous / Next, canonical
timestamp replay, supported playback rates, and stronger selection visibility.

M1.4 is **CLOSED / APPROVED / merged**. It verified that the reviewed M1.1-M1.3
backend and PV-2/PV-3 workspace form one truthful, internally usable EN/ZH
follow-along flow over canonical Media Learning segments.

M1.5 is **CLOSED / APPROVED / merged**. It added bounded, deterministic
transcript-reconstruction practice over canonical Media Learning segments with
browser-session-only practice state referencing canonical `asset_id` and
`segment_id`. It did not add durable learner-progress persistence.

M1.6 Shared-media Shadowing integration is **CLOSED / APPROVED / merged** via
PR #33. It reuses the same canonical Media Learning `asset_id`, transcript
segments, translations, and provider-hosted playback inside the existing
Listening workspace, with browser-session-only Shadowing round state. It did
not add a Speaking route, microphone capture, ASR, pronunciation scoring,
durable learner-progress persistence, or public release. Listening and Speaking
remain non-public.

## R5 Grammar Knowledge System

R5 is **CLOSED / APPROVED / merged via PR #44** at baseline
`d88c8cb17b16412b8c8b0de6d5fe7ab8f4a69061`.

Verified closeout:

- English `269 / 269`;
- Chinese `239 / 239`;
- total `508 / 508`;
- schema-v2 source-backed concept-specific learning models `508 / 508`;
- Grammar runtime AI `0`;
- representative expert-reviewed lessons `3`;
- `505` lessons remain explicitly `human_expert_validation=pending` as a
  deferred content-quality track.

Static Grammar KB remains source of truth. Stable Grammar Concept IDs, the
shared schema-v2 renderer, multilingual language-context separation,
capability-driven Chinese reading aids/Pinyin, and activity-evidence completion
semantics are protected. Future skill integrations consume these contracts
rather than duplicating or mass-rewriting Grammar.

## R6 Speaking Core

R6 is **COMPLETE / LOCAL ACCEPTANCE PASS** at the prepared-media internal
checkpoint. Speaking Core reuses the current language-scoped shared Media
Learning session from Listening and adds local
microphone recording, RNNoise-based voice enhancement when available, and
immediate playback of the learner's take. When configured, the stopped take
is sent transiently through the authenticated speech API to Groq ASR. Orena
does not persist the audio take to the learner account.

The recognized transcript is compared deterministically with the selected
source segment to show content-match plus missing/extra token feedback. This
is not pronunciation, fluency, or proficiency scoring. Speaking remains
**DEVELOPMENT** and non-public. R2 `speech_asr` control-plane activation and
public `pronunciation_evaluator`/`speaking_evaluator` capability promotion
remain later gates.

## R2 AI Capability Control Plane

- Slice 1: **CLOSED / APPROVED / merged**.
- Slice 2: **CLOSED / APPROVED / merged**.
- Slice 3: **CLOSED / APPROVED / merged via PR #10**.
- Slice 4: **CLOSED / APPROVED / merged via PR #15**.

The capability-centric control plane exists. Canonical admin APIs are:

- `GET /api/admin/ai/config`
- `PUT /api/admin/ai/config/{capability_key}`
- `POST /api/admin/ai/test/{capability_key}`

Legacy global admin mutation and provider-test endpoints remain transitional
and deprecated.

Capability-aware learner runtime support is implemented behind one central
`LEGACY` / `CAPABILITY` mode. Seven provider-backed workloads pass explicit,
product-wide capability identities. `LEGACY` remains the default and current
production behavior; production has **not** been activated to `CAPABILITY`.
In `CAPABILITY` mode, routing resolves the exact persisted provider/model and
does not fall back to `active_selection()`.

### Current capability catalog

Configurable, implemented, provider-backed capabilities:

- `writing_evaluator`
- `reading_generator`
- `writing_task_generator`
- `writing_improver`
- `learner_dictionary`
- `learner_translation`
- `grammar_lesson_generator`

Deterministic capability:

- `reading_evaluator`
- `writing_linguistic`

The `learner_translation` provider catalog includes Groq and local Marian. The
runtime selects the configured engine once at startup; it never silently fails
over between providers.

Reserved in the R2 control plane and not activated:

- `speech_asr` — R6 currently uses a direct internal Groq ASR adapter outside
  control-plane activation.

Reserved for later public/capability activation:

- `pronunciation_evaluator` public activation
- `speaking_evaluator` public activation (the internal per-take contract is
  locally verified below)

Capability configuration is product-wide. Per-language capability IDs such as
`writing_evaluator_en` and `writing_evaluator_zh` do not exist and must not be
invented.

Persisted `fallback_policy` is configuration metadata for later activation.
It is not active learner fallback behavior. There is no provider-to-provider
fallback and no silent paid-provider failover.

## Current next development areas

The post-R5 roadmap uses one primary learner-visible lane.

- **R3 — Writing Evaluation Completion: COMPLETE / LOCAL ACCEPTANCE PASS.**
  The shared evaluator/request/schema/evidence architecture, deterministic EN/ZH
  benchmark, scoring safeguards, degraded-state truthfulness, and end-to-end
  Writing/Review evidence flow are verified. Writing remains BETA pending human
  public-gate review.
- **R4 — Writing Learning Loop + Grammar Transfer: COMPLETE / LOCAL ACCEPTANCE PASS.**
  Review, Home, and Journey Grammar practice actions preserve exact evidence,
  backend-valid context, fresh draft state, and source revision lineage into the
  real Write evaluation payload. Practice outcomes return through the existing
  Review/Journey contracts and consume stable R5 Grammar IDs.
- **R6 — Speaking Core: COMPLETE / LOCAL ACCEPTANCE PASS.**
  Prepared EN/ZH shared-media fixtures now verify mounted record → transient ASR
  → deterministic content-match feedback, together with truthful missing-session,
  unsupported-recorder, and transcription-failure states. Audio and attempts
  remain transient; no pronunciation, fluency, proficiency, or durable-progress
  claim is made. The verified R3/R4 Writing and Grammar-transfer contracts are
  unchanged.
- **R7 — Speaking Evaluation + Pronunciation: COMPLETE / LOCAL ACCEPTANCE PASS.**
  Mounted EN/ZH take flows carry reference text, transcript, optional ASR
  confidence, content-match evidence, and optional pronunciation evidence into
  the existing evaluator. Feedback keeps measured dimensions separate and
  marks proficiency unassessed; synthetic and failure provenance remain
  explicit. Completed evaluator envelopes now persist as audio-free,
  learner-scoped Speaking attempts with bounded history/progress retrieval;
  public activation and broader release remain deferred.
- **R8 — Public Product Gate: Writing + Speaking EN/ZH: PRE-PUBLIC MATRIX
  COMPLETE / HUMAN PROMOTION GATE.** The deterministic EN/ZH Writing and
  Speaking matrix, degraded-state checks, and browser module graph pass locally;
  persistence/runtime boundaries are recorded as static inspections alongside
  separately executed backend contracts in `docs/project/R8_PRE_PUBLIC_MATRIX.json`.
  Provider credentialed validation, production migration, capability activation,
  and public promotion remain explicitly deferred.
- **R9 — Speaking Advanced / Shadowing Studio: COMPLETE / LOCAL ACCEPTANCE PASS.**
  Selected EN/ZH canonical media segments now carry their asset, language, and
  segment identity into the existing Speaking recorder/evaluator and back into
  the same Shadowing Studio mode. Listening now retrieves only the latest
  authenticated, language/asset/segment-matching Speaking outcome and renders
  dimension-specific feedback with localized empty/error states. No raw audio
  persistence, new provider, or public capability activation was added.
- **R10 — Reading Completion: COMPLETE / LOCAL ACCEPTANCE PASS.** The mounted
  EN/ZH Reading contract verifies session creation, comprehension answers tied
  to exact passage evidence, learner-scoped history reopening, saved-word
  handoff to Library, and contextual dictionary lookup with explicit
  unavailable states. The deterministic pre-public matrix is recorded in
  `R10_PRE_PUBLIC_MATRIX.json`; provider credentials, production mutation, and
  public Reading promotion remain deferred.
- **R11 — Listening Completion: PRE-PUBLIC MATRIX COMPLETE / HUMAN PROMOTION
  GATE.** The deterministic EN/ZH matrix covers mounted Active reconstruction
  resume, Shadowing round resume, Shadowing-to-Speaking feedback continuity,
  localized unavailable/failure states, and the browser module graph. Its
  canonical report distinguishes behavioral passes from PostgreSQL-only,
  language/asset/segment scope, and audio-free static inspections. Production
  migration, capability activation, and public Listening promotion remain
  deferred.
- **R12 — Retention & Growth: COMPLETE / LOCAL ACCEPTANCE PASS.** Home now offers
  a localized return-to-Listening cue only for a recent language-scoped lesson;
  the handoff carries a source URL and bounded segment/mode context, and
  Listening restores valid state or falls back to the canonical first segment
  and Follow mode. Home also surfaces the existing device-local Listening time
  and daily goal, with a route back to Listening's established goal control;
  malformed or unavailable local records remain explicitly unclaimed. No
  transcript/audio payload is stored and public retention promotion remains
  deferred.
- R12 also composes one prioritized, localized Home next-practice plan from
  existing Writing, Reading, Listening, and Speaking evidence. It reuses the
  established flow for each available action and stays quiet when evidence is
  unavailable; it creates no new progress or completion claim.
- R12's onboarding activation slice now turns a baseline Writing
  recommendation into one localized first-practice action when no resumable
  cross-skill evidence exists. The action uses the saved goal/style and
  target level through the existing task-generation endpoint, clears stale
  draft state, and leaves the learner on Home with a localized error when
  generation is unavailable.
- **R13 — Platform Admin Completion: COMPLETE / LOCAL ACCEPTANCE PASS.** The
  existing Platform Admin includes a capability matrix sourced from
  the canonical admin control-plane response. Implemented provider-backed
  capabilities expose scoped provider/model/enabled controls through the
  canonical capability configuration route; deterministic and reserved
  capabilities remain read-only. The matrix shows audit-safe saved-state
  provenance and provides explicit click-only health checks for eligible
  configurations. Saved configuration and health checks remain distinct from
  learner runtime and do not activate it; failures clear stale matrix data
  without exposing provider credentials.
  The deterministic `scripts/r13_release_matrix.mjs` runner executes the
  mounted Admin contract and verifies the canonical API/backend contract
  boundaries; credentialed provider health and runtime activation remain
  explicit human-gated deferrals in `R13_LOCAL_ACCEPTANCE_MATRIX.json`.
- **R14 — AI Usage, Cost, Quota & Provider Operations: COMPLETE / LOCAL
  ACCEPTANCE PASS.** Existing provider-backed structured-generation and Platform
  Admin live-test boundaries now expose one sanitized capability/provider/model/
  latency/usage telemetry shape. Missing token or quota data remains unknown;
  durable events now use the existing PostgreSQL audit boundary and read-only
  Admin aggregation with bounded healthy/degraded/provider-failure evidence
  states. Admin token totals preserve provider-reported prompt/completion/total
  dimensions and distinguish complete, partial, and unavailable usage; billing,
  quota enforcement, and credentialed live validation remain deferred. The
  operations surface also carries allowlisted provider request/token limit and
  remaining headers, reporting exhaustion only when remaining capacity is zero.
  Bounded UTC day-bucket trends expose request, failure, latency, token, and
  rate-limit evidence while preserving explicit unknown timestamp/usage states.
- R14 cost evidence now snapshots exact-match provider/model pricing provenance
  at telemetry creation. Complete prompt/completion usage is estimated only
  for cataloged models; unknown models, partial usage, and absent usage remain
  separate unpriced/partial/unknown states. Admin aggregates by currency and
  catalog version for capability and seven-day trend buckets; this is
  observation only, with no billing, quota enforcement, live price fetching,
  or provider activation.
- R14 capability settings also support an optional validated standby
  provider/model pair. Admin can explicitly check standby readiness and shows
  sanitized provenance, while learner routing remains primary-only and never
  performs automatic retry or failover.
- The deterministic `scripts/r14_release_matrix.mjs` runner now verifies the
  mounted Admin operations behavior and records the telemetry, persistence,
  aggregation, pricing, and provider-control boundaries as local contract
  evidence in `R14_LOCAL_ACCEPTANCE_MATRIX.json`. Credentialed provider
  validation, production observation, billing/quota enforcement, and learner
  runtime activation remain explicit human-gated deferrals.
- **R16 — Advanced Learning Intelligence: COMPLETE / LOCAL ACCEPTANCE PASS.**
  Focused local contracts verify contextual dictionary grounding in Reading and
  shared Listening/Speaking transcript tokens, adaptive Writing difficulty,
  localized error-memory review cues, cross-skill transfer handoffs, and the
  scheduled Library review action. The evidence chain preserves EN/ZH parity,
  literal learner context, language-scoped provenance, and explicit unavailable
  or insufficient states without inventing proficiency. Credentialed provider
  checks, production activation, and public promotion remain deferred.
- **R2 — AI Capability Control Plane: HUMAN GATE / READY.**
  Static/runtime support exists. Production migration/config initialization,
  credentialed validation, activation, and rollback execution remain human
  gates and do not block R3/R4.
- **M1 — Media Learning Foundation: CLOSED / FOUNDATION COMPLETE.**
  Future Listening durability and advanced Shadowing belong to R11/R9.
- **R5 — Grammar Knowledge System: CLOSED.**
  Future skills consume its stable concept IDs and shared schema-v2 contracts.
  Expert validation of the remaining 505 lessons is a deferred content-quality
  track, not a reason to reopen the architecture.

The intended product sequence is:

`R3 → R4 → R6 → R7 → R8 → R9 → R10`

R2 production activation is completed when explicitly authorized and before a
public capability-dependent release requires it.

## R19–R21 mobile product direction

- **R18 is API/mobile readiness, not the mobile application.** It is locally
  complete and remains the server-contract foundation for native clients.
- **R19 — Native Mobile App Foundation: COMPLETE / LOCAL ACCEPTANCE PASS.** The
  dedicated React Native + Expo + TypeScript `mobile/` workspace has shared
  EN/ZH behavior, typed API/session contracts, secure native session storage,
  navigation/theme/accessibility foundations, bounded caching, native
  microphone/media boundaries, and portable Android/iOS build preparation.
  Host/device validation, signing, stores, and production actions remain human
  gates.
- **R20 — Mobile Learning Experience Parity: COMPLETE / LOCAL ACCEPTANCE PASS.**
  The existing Writing, Review, Grammar, Reading, Listening, Speaking/Shadowing,
  Library, Journey, Home, onboarding, and Profile flows are implemented as
  native mobile vertical slices consuming the same backend/domain contracts.
  `scripts/r20_release_matrix.mjs` executes the mounted native suites and pins
  the result in `docs/project/R20_LOCAL_ACCEPTANCE_MATRIX.json`: nine verified
  mounted checks, six static contract inspections, and five explicit human
  deferrals. Device QA, provider credentials, store release, billing
  activation, and public skill promotion remain gated.
- **R21 — Mobile Release Readiness: PLANNED / HUMAN STORE-RELEASE GATE.** Prepare
  Android/iOS release builds, OAuth/deep-link configuration, privacy/device QA,
  diagnostics, store metadata, and R15-compatible mobile entitlement/billing
  readiness. Signing keys, store credentials, production OAuth changes,
  production activation, billing activation, and public store submission remain
  explicit human gates.
