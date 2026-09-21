# Orena Legacy Tombstones

## Governance

**Purpose:** prevent retired product directions from being revived by fresh
agents. **Authority:** human-governed. Agents may add or alter a tombstone only
after explicit human instruction and an accepted Decision Log entry.

**Change when:** a direction is explicitly retired or superseded.
**Do not store:** ordinary defects, temporary blockers, backlog, or
implementation history that has no revival risk. Tombstones must never be
removed merely because current code conflicts with them.

## `/becoming`

- **Status:** DEPRECATED / COMPATIBILITY ONLY
- **Current replacement:** `/`
- **Why retired:** Orena is the canonical product and root route.
- **What may remain:** a bounded redirect/alias and tests proving it resolves to
  `/`; historical references in archived evidence.
- **What must not happen:** new learner navigation, links, screens, feature
  ownership, or product development targeting `/becoming`.

## Historical BECOMING user-facing product identity

- **Status:** RETIRED
- **Current replacement:** Orena
- **Why retired:** the active product identity has transitioned to Orena.
- **What may remain:** historical Decision Log wording, release evidence,
  technical constants, database names, and compatibility artifacts.
- **What must not happen:** learner-facing branding or current product docs may
  not present BECOMING as the active app.

## `static/becoming/**`

- **Status:** RETIRED AND PHYSICALLY REMOVED (D-046).
- **Replacement:** new Orena product in `static/orena/`.
- **Must not happen:** restoring skill dashboards, old Listening/Shadowing shells,
  mode routers or screen/session handoffs, even under new names. Extract independent
  capabilities; Git preserves the obsolete implementation.

## `templates/becoming/**`

- **Status:** RETIRED AND PHYSICALLY REMOVED (D-046).
- **Replacement:** `templates/orena/index.html` at `/`.
- **Must not happen:** restoring the old learner shell or competing root template.

## Discover/Home owning hard-coded canonical content

- **Status:** RETIRED (D-049).
- **Current replacement:** Domain libraries (`docs/product/
  ORENA_CONTENT_ARCHITECTURE.md` §5-§9); Discover/Home distribute from them
  (§3).
- **Why retired:** Growing the entry surface by hand-editing a small array
  directly in `static/orena/content/texts.js` (or an equivalent per-domain
  array) reads as fast content growth but is the exact pattern D-049 exists to
  stop: it never scales past a hand-curated handful and keeps the strategic
  content problem looking solved when it is not.
- **What may remain:** The existing hand-authored `origin: generated` items
  already in such arrays are valid content under
  `ORENA_CONTENT_ARCHITECTURE.md` §2 and are not deleted; a hand-authored
  array remains an acceptable **starting seam** for a domain that has no
  pipeline yet (§17). What must not happen is treating further one-at-a-time
  edits to that array as the ongoing content-growth strategy.
- **What must not happen:** New agents must not "grow Discover" by adding more
  literal entries to a hard-coded array and calling it library growth. New
  content growth targets the owning domain's library and its shared
  ingestion/admission/moderation pipeline
  (`ORENA_CONTENT_EXECUTION_ARCHITECTURE.md` §1, §3), with Discover/Home
  reading from it, not authoring it.

## Vocabulary as a flat saved-word list

- **Status:** RETIRED as the target model (D-049).
- **Current replacement:** Orena Vocabulary Cards
  (`docs/product/ORENA_VOCABULARY_ARCHITECTURE.md`).
- **Why retired:** `word -> translation` plus a recall-review schedule is the
  correct baseline (`ORENA_COLLECTION_ARCHITECTURE.md`'s existing saved-word/
  `LanguageItemRef` seam) but is not a complete Vocabulary product.
- **What may remain:** The existing saved-word identity, occurrence
  provenance, and Active Recall scheduling are the foundation a Vocabulary
  Card is built on, unchanged (`ORENA_VOCABULARY_ARCHITECTURE.md` §3).
- **What must not happen:** Treating the current flat list as Vocabulary's
  finished end-state, or building a second, disconnected "card" system instead
  of enriching the existing saved-word object.

## Language Knowledge modeled as a sixth content domain / mandatory precomputed graph

- **Status:** RETIRED (D-050, correcting an over-modeling introduced by D-049's
  first integration).
- **Current replacement:** The Understanding Engine is a horizontal capability
  shared across Orena's five content domains — Reading, Writing, Listening,
  Speaking, Vocabulary — not a sixth learner-facing library
  (`docs/product/ORENA_UNDERSTANDING_ENGINE.md` §1). It is AI-first and
  context-grounded: explanations generate from the learner's exact context
  through the Orena Explanation Contract, not from a required precomputed
  knowledge store (`ORENA_UNDERSTANDING_ENGINE.md` §2-3). An optional
  explanation support layer (caching, retrieval, trusted references) may be
  added later only once real usage justifies it (`ORENA_UNDERSTANDING_ENGINE.md`
  §5); a structured knowledge graph is a possible optimization inside that
  layer, never a prerequisite.
- **Why retired:** The first pass integrating
  `docs/product/ORENA_PHILOSOPHY_AMENDMENT_CONTENT_UNDERSTANDING.md` (whose own
  §2.6/§7/§16 still carry this framing as a historical artifact) modeled
  "Language Knowledge" as a peer of Reading/Writing/Listening/Speaking/
  Vocabulary and treated a Language Knowledge Graph as something the
  Understanding Engine needed before it could work. Neither claim was the
  intended product model.
- **What may remain:** Everything else D-049 established — five domains as
  domains, the Orena Vocabulary Card spec and orthography, the Discover/Home
  distribution correction, and the content scale philosophy — is unaffected
  and stays in force.
- **What must not happen:** New agents reading the amendment document directly
  must not reintroduce a sixth "Language Knowledge" domain, a learner-browsable
  Understanding/Language-Knowledge screen, or a database that must be
  pre-populated before an explanation can be generated. Treat the amendment
  document as historical context for *why* the Understanding Engine and
  Vocabulary Card work exist, not as the current section-numbering or
  domain-count authority — `ORENA_CONTENT_ARCHITECTURE.md` and
  `ORENA_UNDERSTANDING_ENGINE.md` are.

## The Ink / Paper design system (D-059) and the D-065 update

- **Status:** RETIRED (D-066, explicit human instruction 2026-09-21). Removal
  from the code is part of the migration and finishes when nothing depends on it.
- **Current replacement:** the Canonical UI Baseline, one Dark Glass system
  (`docs/design/canonical-ui/`).
- **Why retired:** the human approved a frozen baseline as the single visual and
  data authority; it lists the D-059/D-065 source documents as legacy.
- **What may remain until migrated:** the Ink/Paper tokens, the theme registry,
  the borderless-card block and the surfaces built on them, only as code that
  has not yet been replaced. A surface is migrated to the baseline, then the old
  pieces are deleted.
- **What must not happen:** building anything new on Ink, Paper, the reader's
  sepia block, borderless cards or the learning-surface opening sentence; a
  hybrid of the two systems; a Paper or light theme returning as a setting;
  reading D-059 or D-065 as design authority.

## The UI rules before the baseline (D-046, D-051, D-057, D-060 measurements)

- **Status:** RETIRED where they conflict with the design (D-067, explicit human
  instruction 2026-09-21).
- **Current replacement:** the Claude Design project read at its source, and
  `DESIGN_CONTRACT.md` as rewritten by D-067.
- **Why retired:** they described an older design language ("one design language,
  distinct compositions", a shared icon toolbar, "the card wall is not a layout",
  Discover not organised by skills, a compacting phone header, the core learning
  viewport, a Practice group in the rail, dense phone scale) and were being used
  to overrule the design.
- **What may remain until migrated:** code built to them, only as code that has
  not yet been replaced; the surface is migrated to the design and the old
  implementation is deleted.
- **What must not happen:** citing one of these rules against the design;
  restyling an old interaction instead of removing it; adding UI the design does
  not draw because an old rule asked for it.

## `writing_coach/becoming_*`

- **Status:** LEGACY TECHNICAL NAMESPACE
- **Current replacement:** current Orena domain contracts; broad renaming is not
  required by this tombstone.
- **Why retired:** the module prefix is historical implementation vocabulary.
- **What may remain:** stable modules, imports, API route names, tests, and
  persistence compatibility identifiers.
- **What must not happen:** these symbols must not define current product
  identity, routing, architecture, or a separate learning system.
