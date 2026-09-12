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
  ORENA_CONTENT_ARCHITECTURE.md` §5-§10); Discover/Home distribute from them
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
  pipeline yet (§18). What must not happen is treating further one-at-a-time
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

## `writing_coach/becoming_*`

- **Status:** LEGACY TECHNICAL NAMESPACE
- **Current replacement:** current Orena domain contracts; broad renaming is not
  required by this tombstone.
- **Why retired:** the module prefix is historical implementation vocabulary.
- **What may remain:** stable modules, imports, API route names, tests, and
  persistence compatibility identifiers.
- **What must not happen:** these symbols must not define current product
  identity, routing, architecture, or a separate learning system.
