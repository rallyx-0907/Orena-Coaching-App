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

## `writing_coach/becoming_*`

- **Status:** LEGACY TECHNICAL NAMESPACE
- **Current replacement:** current Orena domain contracts; broad renaming is not
  required by this tombstone.
- **Why retired:** the module prefix is historical implementation vocabulary.
- **What may remain:** stable modules, imports, API route names, tests, and
  persistence compatibility identifiers.
- **What must not happen:** these symbols must not define current product
  identity, routing, architecture, or a separate learning system.
