# Orena Product Constitution

## Governance

**Purpose:** preserve durable compatibility, technical-product, routing,
multilingual, media-learning, persistence, and native-parity invariants inherited
by the current Orena implementation.

This file is NOT the canonical learner-facing Product North Star.

Current learner-facing product direction is defined by:

`docs/product/ORENA_PRODUCT_CONSTITUTION.md`

Current content-world direction is defined by:

`docs/product/ORENA_CONTENT_ARCHITECTURE.md`

Approved Orena visual identity is defined by:

`assets/brand/orena/`

**Authority:** subordinate to explicit current human instruction,
`docs/product/ORENA_PRODUCT_CONSTITUTION.md`, and
`docs/product/ORENA_CONTENT_ARCHITECTURE.md` for learner-facing product intent.

This file remains authoritative only for compatible technical/product invariants
that have not been superseded by those higher-authority sources or an accepted
Decision Log entry.

**Change when:** an explicit accepted decision changes one of these durable
compatibility or technical-product invariants.

**Do not store:** current visual direction, temporary implementation status,
backlog, historical narrative, or product philosophy that belongs in the
canonical Orena Product Constitution.

## Product identity and routing

- The active product name and learner-facing identity is **Orena**.
- The canonical Orena web route is `/`.
- `/becoming` is deprecated and compatibility-only. No new learner feature may
  target it.
- D-046 retires the historical learner-product implementation. Git is the archive.
  Stable `writing_coach/becoming_*` capability and persistence contracts may remain.
- A legacy namespace, filename, symbol, branch, screenshot, comment, or archived
  document never authorizes revival of the BECOMING product identity or route.

## Design and native parity

- The approved responsive Orena web product is the visual, functional, and
  interaction source of truth.
- Native mobile is a **full native port** of the same Orena product. It is not a
  redesign, simplified edition, generic Expo interpretation, generic Material
  interpretation, or generic iOS interpretation.
- Native preserves the approved UI, UX, functionality, navigation,
  interaction/animation intent, state behavior, EN/ZH behavior, light/dark
  behavior, and learner flows. Only necessary platform mechanics may differ.

## Connected learning system

Orena is experience-centered, not discovery-only (D-046). Discovery, intentional
Practice, continuation, learner-owned content and learner memory are valid entry
intentions. They converge on shared capabilities and learner evidence.

Do not restore historical skill dashboards, Listening shells, Shadowing Studio,
mode hierarchies, or screen-oriented handoffs. Extract useful primitives before
deleting mixed modules. Do not create separate learning engines per entry intent.

## Languages

- English and Chinese are equally first-class.
- Shared features support EN and ZH in the same implementation and batch.
- Do not implement English now with Chinese promised later.
- Language adapters exist only for genuine linguistic differences.

## Listening and Media Learning

- Follow is first-class: synchronized playback, active original subtitle and
  same-segment support-language meaning. Seek, selection, replay and speed changes
  preserve that relationship. Chinese is primary; Pinyin is contextual.
- Learners can stay in Follow without doing Dictation or Shadowing.
- Curated and learner-imported media use the same capability primitives and
  canonical Media Learning Object. Rights and provenance travel with the content.
- Practice can begin directly or emerge from an encounter; evidence stays shared.

## Persistence

- PostgreSQL is authoritative.
- SQLite is test, archive, and rollback only.
- No dual-write, reverse synchronization, silent fallback, automatic startup
  import, or automatic startup Alembic.
- Production data mutation requires explicit human authorization.

## Commercial production and human gates

Orena is a commercial production product. Tests passing is not equivalent to
production readiness. Public release, production authentication, billing,
subscription enforcement, production AI/provider activation, live credentials,
production migration, Cloudflare/DNS, signing/store publication, destructive
operations, and rollback-path removal remain explicit human gates.
