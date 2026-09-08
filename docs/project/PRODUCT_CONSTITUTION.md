# Orena Product Constitution

## Governance

**Purpose:** define durable, high-authority Orena product intent.

**Authority:** human-governed. Agents must treat this file as read-only unless
the human explicitly changes product direction. A change requires an appended
Decision Log entry, explicit supersession of any prior accepted decision, and
matching state/validator updates.

**Change when:** an explicit human decision changes a durable product
principle. **Do not store:** implementation status, temporary workarounds,
backlog, historical narrative, or claims made only to match current code.

## Product identity and routing

- The active product name and learner-facing identity is **Orena**.
- The canonical Orena web route is `/`.
- `/becoming` is deprecated and compatibility-only. No new learner feature may
  target it.
- Historical paths such as `static/becoming/**`, `templates/becoming/**`, and
  `writing_coach/becoming_*` may remain while technically required. Their names
  are implementation history, not current product direction.
- A legacy namespace, filename, symbol, branch, screenshot, comment, or archived
  document never authorizes revival of the BECOMING product identity or route.

## Learner-facing experience model

- Orena's discovery surface is world-first rather than skill-menu-first.
- The canonical content relationship is:

```text
Language → World → Zone → Journey → Lesson → Activity
```

- Listening, Speaking, Reading, Writing, Grammar, Vocabulary/Dictionary, and
  Review remain connected learning mechanisms. They do not have to dominate
  Home or Explore as a flat feature taxonomy.
- **Home** exists for motivation, discovery, and real continuation.
- **Progress** is a separate destination for reflection and learning analytics.
  Home may show progress attached to a specific journey or lightweight global
  cues, but it must not become a KPI/analytics dashboard.
- Discovery surfaces should make the learner want to start something; focused
  learning surfaces should reduce competing visual noise; completion/reward
  moments may become more expressive again.

## Design and native parity

- Orena launches Web first. The approved **responsive Orena web product** is the
  visual, functional, interaction, and product-meaning source of truth.
- Responsive approval is not a single desktop screenshot. Golden learner
  surfaces are deliberately composed and reviewed at desktop, tablet, and
  mobile-web reference widths.
- Native mobile is a **full native port** of the same Orena product. It is not a
  redesign, simplified edition, WebView shell, generic Expo interpretation,
  generic Material interpretation, or generic iOS interpretation.
- The cross-platform rule is **shared meaning, adaptive composition**.
  Native preserves feature access, learner outcomes, content/state identity,
  navigation meaning, interaction intent, progress semantics, EN/ZH behavior,
  design tokens, visual DNA, and state behavior.
- Native and narrow Web do **not** have to preserve desktop simultaneous
  visibility, column count, exact card dimensions, chrome placement, or
  pixel-for-pixel composition. Smaller surfaces may progressively reveal the
  same information through scroll, rails, sheets, tabs, or other appropriate
  native composition.
- Desktop must not simply be shrunk into mobile, and mobile must not rediscover
  or simplify the product.

## Connected learning system

Orena is not four isolated skill applications. Its core learning system is:

```text
Listening ↔ Speaking ↔ Reading ↔ Writing
```

Library / Active Recall, Grammar, Dictionary, Progress, and Media Learning are
shared infrastructure. Evidence and content should move meaningfully between
skills rather than being trapped inside a module.

Canonical continuity includes:

```text
Listen → Dictation → Read transcript → Dictionary / Vocabulary
→ Shadow → Speaking feedback → Writing response → Active Recall
```

Do not create parallel media, progress, dictionary, vocabulary, scoring, or
learning-evidence systems per skill or per client.

## Languages

- English and Chinese are equally first-class.
- Shared features support EN and ZH in the same implementation and batch.
- Do not implement English now with Chinese promised later.
- Language adapters exist only for genuine linguistic differences.

## Listening and Media Learning

- Listening is content-library-first. Curated, interesting learning content is
  the primary experience; learner media import is secondary.
- Curated and learner-imported media use the same Listening Engine.
- Normal Listening, Active Listening, Dictation, Shadowing, transcript,
  dictionary, translation, Pinyin, progress, and resume share canonical media
  contracts.
- One canonical Media Learning Object powers relevant downstream learning
  experiences. Do not build skill-specific media pipelines.
- Rights and provenance belong to the canonical source/media object and follow
  downstream Listening, Speaking, Reading, and Writing use.

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
