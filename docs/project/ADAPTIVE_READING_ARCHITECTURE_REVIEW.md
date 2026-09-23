# Adaptive Reading schema — architecture review, round 1

    VERDICT:         REQUEST CHANGES
    REVIEWER:        Delegated Architecture Reviewer (Claude Opus 5)
    REVIEWED COMMIT: 00dcf183960e6969816e9f17d62b288f6a25c501
    PROPOSAL:        docs/project/ADAPTIVE_READING_SCHEMA_PROPOSAL.md
    DATE:            2026-09-24
    APPLIED:         no — the migration may not be written or applied until a
                     later round passes

Recorded under `AGENTS.md`, "Architecture review authority": the reviewer's
identity, the reviewed commit and the outcome live in Git, and the implementer
did not approve its own work.

**Scope note the reviewer put first, and it changes what this verdict means:**
`git show --stat 00dcf18` is one file, the document. No migration, no model, no
DDL exists yet. Much of this is a review of prose describing constraints, and
**it must be repeated against the DDL** when that is written.

---

## Blockers

1. **The set table's partial unique index forbids the workflow the table exists
   for.** The proposal justifies a separate table with "an article can have a
   set that was rejected and a new one being prepared", then constrains it
   `UNIQUE (article_id) WHERE status <> 'archived'`. `rejected` is not
   `archived`, so a rejected set and a new draft collide. Preparing a
   replacement would force archiving the rejection — destroying the history the
   table exists to keep. Same defect class as round-1 P1-1/P1-3 of the Reading
   Content Engine review. The predicate matching the real rule is
   `WHERE status = 'approved'`.

2. **A path exists from an admin article purge to destroyed learner evidence.**
   `reading_comprehension_sets.article_id` is `ON DELETE CASCADE`;
   `reading_practice_attempts` names no `ON DELETE` at all. Deleting an article
   cascades the sets away and then either takes the attempts with them or
   silently breaks the documented purge path. The engine's rule is the
   opposite and written down: `RESTRICT` upward for anything that is evidence
   behind something a learner read.

3. **This is learner-owned schema authored without the specification it is
   required to be authored against.** `CURRENT_HANDOFF.md` (BLOCKED) requires a
   learner-owned schema to be authored against
   `ORENA_ACCOUNT_DATA_ARCHITECTURE.md`. The proposal never names it, and four
   of its requirements are missing: an evaluator/rule version on the attempt; a
   projection policy version, checkpoint and "discardable" declaration on
   `reading_ability`; an idempotency key so a retried submit does not apply the
   ability step twice; and enumeration of the two new account-keyed owner
   tables in the deletion workflow (D-054). Not "these tables may not exist" —
   the design has not been done against the contract that governs it.

4. **`evidence_start`/`evidence_end` point into a column an Admin edits**, with
   nothing recording which revision they were computed against. `update_article`
   accepts a new `body`, bumps `content_revision`, and nothing invalidates the
   offsets. The failure is silent and lands on published learner content.

5. **Partial indexes are declared for one dialect**, against a rule this
   repository already wrote down: `postgresql_where` alone becomes a full index
   on SQLite, so the hermetic suite would enforce a constraint the runtime does
   not have — and here it would make the "rejected set plus replacement"
   scenario untestable.

## Required changes (21)

Uniqueness and keys: the approved-only predicate (1); explicit `ON DELETE` on
every FK, `RESTRICT` upward (2); `user_id` as a real FK (3); uuid surrogate plus
`UniqueConstraint(user_id, language_code)` on `reading_ability`, matching every
other learner table (4).

Versions and idempotency: rule/evaluator version on the attempt and projection
policy version on ability, declared rebuildable (5); an idempotency key in the
shape `TextDiscussionTurn.request_id` already uses (6).

Minimality: drop `recent_json` — the index already answers it (7); partial
progression index on `completed_at IS NOT NULL` (8).

Constraints: `NOT (admin_approved AND admin_rejected)` plus `machine_suggested`
(9); `rank >= 0`, and reconsider unique rank (10); bound `correct_index` above
(11); an approved set must have at least one question (12); bound `score`, or
say what else goes into it (13).

Types: `Float`, not `Numeric` — `Numeric` appears nowhere in this repository and
round-trips differently on SQLite (14); widen `ability` — `numeric(5,3)`
silently excludes an Elo-style model (15); state the `completed_at` rule (16).

Integration: add `content_kind` to `LEARNER_VISIBLE_FIELDS` and the learner list
projection (17); decide the explanation's language — the existing surface reads
`explanation_vi` only (18); commit to the PostgreSQL constraint proof (19); name
the three other readers of `reading_sessions` (20); correct the six factual
errors (21).

## Six factual errors in the proposal

1. The engine's partial unique on `request_hash` is an **inclusion** predicate,
   not the exclusion shape the proposal claims to copy.
2. **`CHECK (evidence_text <> '')` does not enforce grounding.** A CHECK cannot
   reach `reading_articles.body`; it forbids the empty string and nothing else.
   The proposal's headline claim, and the commit message that carried it, are
   false. The only real grounding check is in application code.
3. The targets' `(article_id, rank)` index is **not** unique and does carry
   `rank >= 0`; the proposal is stricter one way and weaker the other.
4. Targets also carry `machine_suggested` and the mutual-exclusion CHECK; the
   proposal copies neither.
5. "The generation logic is reused" is not true as written: the generator is
   hard-wired to four questions and four options, produces no `question_type`,
   no offsets, and a Vietnamese-only explanation. The eight-type enum and the
   3-6 rule require rewriting it.
6. `migrations/proposed/` is no longer where the engine's migration sits.

## Answers to the six questions the human asked

- **Minimal / ownership:** the four-way split is right and should not be merged.
  `recent_json`, `question_count` and `score` are the non-minimal parts.
- **Duplication:** none with `reading_articles`, `reading_article_targets` or
  `reading_source_items`, checked field by field. `analysis_json` is a name
  collision, not a duplication. Missing for review: the mutual-exclusion CHECK,
  `machine_suggested`, and the `content_revision` the set was built against.
- **Ability without hard-coding an algorithm:** the shape is model-agnostic; the
  precision, the missing rule version and storing only `passage_level` rather
  than the difficulty actually consumed are what hard-code it.
- **Evidence invariant:** reasonable for every type because it does not do what
  was claimed. Grounding belongs in the repository and at review; `main_idea`
  and `authors_purpose` need either a paragraph span or a nullable evidence with
  a rule saying which types may omit it.
- **Deprecation:** sound, but `reading_sessions` has four readers, not one —
  the cross-skill cue and the learner summary would quietly regress. Also
  `text_discussions.source_kind` has no value for a corpus article, so Text
  Discussion could not attach to one; and `reading_practice_attempts` sits one
  word from the existing `reading_attempts`, which is the parallel-evidence
  pattern `ORENA_ACCOUNT_DATA_ARCHITECTURE.md` forbids.
- **`content_kind` / source category:** correctly scoped, and **defer source
  category entirely** — the reviewer's judgement is that deferring is better
  than acceptable: it has zero occurrences anywhere, and the work it would do is
  already done by the source's rights columns. Two enum collisions to resolve
  (`book_excerpt` vs the book catalog, `story` vs `text_discussions.source_kind`)
  and a fourth vocabulary for the same axis in `ReadingGenerateIn.material`.

## What the reviewer said not to change

The four-table split; `options_json` as JSON; `content_kind` on the article
rather than the immutable snapshot; the three axes kept separate;
`passage_level` as a point-in-time snapshot; both `ability_before` and
`ability_after` on the attempt; the three-step deprecation with step 3 gated
separately; and no ML, no second vocabulary store, no change to Free Reading.

## Next round must include

The DDL itself, the four `ORENA_ACCOUNT_DATA_ARCHITECTURE.md` requirements, a
downgrade story (learner evidence must not be down-migrated away), and the
PostgreSQL constraint proof. Then this review is repeated against the migration
rather than against prose.
