# Vocabulary "General catalogue" per language - design (Option A)

Status: PROPOSED. Design APPROVED WITH CONDITIONS (`VOCAB_GENERAL_CATALOGUE_REVIEW_2026-10-13.md`, reviewed at 1c30c70d); implemented on the branch, awaiting code review. Section 10 records how each condition was met and supersedes anything above it. Branch `claude/vocab-general-catalogue`, from `origin/main` 172ae216.
Decision record: D-188, ACCEPTED, in `docs/project/DECISION_LOG.md`.
Author: implementer lane. Not self-approved: this changes what reaches learners (a content-visibility rule), so it
needs the independent review the lead has asked for, and the human decisions in section 9.

## 0. Summary of the finding the human must see first

The membership rule the lead set (rights cleared, complete, human-attested, not withdrawn) is the rule a
**published collection** already enforces. Every one of those facts lives on the **collection** (`provenance.admission`);
a vocabulary entry has no rights, review or attestation field of its own (`vocabulary_entries` columns, and the authored
schema `writing_coach/vocabulary_entry.schema.json`, which never reads `status`). So an entry can pass the gates only
through a set that passes them, and a set that passes them and is not withdrawn **is a published collection**.

Consequence: under those gates, **no word that is free today becomes reachable**. A "General catalogue" built to that
rule is the per-language, **persisted and admission-valid** subset of the words learners can already reach (section 10, P1-4: static seeds and sets published without a valid admission are excluded), as one browsable collection. It adds a place
to browse and page them; it does not release a single draft, unpublished or archived word. If the human wants free
(draft) words to reach learners, that needs a new human act (section 9, H1), not a different automatic rule. Anything
automatic that released them would bypass attestation, which D-111, D-178 point 3 and D-187 say it must not.

## 1. Free words as they exist today

A word is "free" when it has no membership in a published set. The sources (read from
`writing_coach/persistence/vocabulary_repository.py`, `app.py` import routes, `admin_console_api.py`):

| Class | How it arises | Reaches learners today |
| --- | --- | --- |
| In pending_review sets only | Admin import that is not auto-published: rights not cleared or not `complete` (D-111), any authored entry file (always pending, D-178 point 3), any D-187 service-token import (forced pending, never attested), any batch with a failed row (`batch_failed`), an import whose finalize failed (`publication_failure`) | No |
| In unpublished sets only | A moderator unpublished a published set (`set_collection_status`) | No |
| In archived sets only | A moderator archived a set | No |
| In no set | `memberships.collection_id` is `ON DELETE CASCADE` and no route deletes a collection, so this class should be empty; it can only come from out-of-band SQL | No |
| Static seed / reference entries | `vocabulary_library.py` JSON seeds. Not rows of `vocabulary_entries` | Published seeds: yes (static catalog). **Unpublished seeds: yes, today, through two raw paths** (`_ENTRY_INDEX` via `vocabulary_entry_for` used by the word page fallback, and `all_vocabulary_entries` used by the Feed pool). Recorded as finding F3, not changed here |
| Learner-saved words with no catalogue entry | `saved_words` rows | Not catalogue content; out of scope |

Count: **not measured.** No vocabulary database exists in this worktree and :8000/:8010 are off limits. The classes
above are structural. For a count on any sandbox the implementer will run, per language:

```sql
-- free entries: no membership in a published collection
SELECT e.language_code, COUNT(*) FROM vocabulary_entries e
WHERE NOT EXISTS (SELECT 1 FROM vocabulary_collection_memberships m
                  JOIN vocabulary_collections c ON c.id = m.collection_id
                  WHERE m.entry_id = e.id AND c.catalog_status = 'published')
GROUP BY e.language_code;
-- split by the status of the sets they are in
SELECT c.catalog_status, COUNT(DISTINCT m.entry_id) FROM vocabulary_collection_memberships m
JOIN vocabulary_collections c ON c.id = m.collection_id GROUP BY c.catalog_status;
```

Learner read paths all gate on `VocabularyCollection.catalog_status == 'published'` through a join on memberships:
`list_collections`, `get_collection`, `find_entry` (word page `#/word/<w>`), `search_entries`, `find_neighbours`,
`list_entries_for_language` (Feed pool). `set_collection_status` docstring: a new state is invisible to learners "by
construction".

## 2. The membership rule

**General is derived, not stored.** An entry is in the General catalogue of language L at the moment of each read iff:

1. `entry.language_code == L`, and
2. the entry has a membership in at least one collection S such that
   - `S.catalog_status == 'published'`, **and**
   - `_publication_admission(S.provenance)` accepts S. That is the repository's own publish gate, reused verbatim, not
     re-implemented: `review_status == approved`, `publication_attested is True`, `rights_status` in
     {public_domain, licensed, creator_authorized, internal_curated}, `completeness == complete`, non-empty
     `attested_by`.

"When do entries join": at the instant condition 2 becomes true for any of their sets, because there is no stored row
to write. There is no join job, no import hook, no publish hook, no recompute and no lazy backfill, so none of them can
fail, lag or be skipped. "How does removal work": at the instant condition 2 stops being true for the entry's last
qualifying set (set unpublished or archived, admission changed or lost, the entry's memberships removed), the next
read no longer returns it. Nothing needs cleaning up.

How each requirement holds:

- **Rights cleared / complete / attested:** by condition 2, using the one function the publish path already uses.
- **A token or service import is never attested (D-187):** the service path forces `publication_attested = False` and
  `review_status = pending_review`, so a token-imported set cannot satisfy condition 2. It joins only after a human
  publishes the set (Admin publish route attests with the admin's identity), the same event that makes it reachable
  today.
- **Withdrawn:** an entry whose only sets are unpublished or archived has no qualifying set. It is absent. It "cannot
  come back through General" because General never remembers anything. An entry in a published set A **and** an
  unpublished set B stays through A; that is correct, A is the gate.
- **Stricter than today in one respect:** the existing learner gate is `catalog_status == 'published'` alone. General
  also re-validates the admission, so a set that reached `published` without a valid admission (finding F1) is
  reachable as its own collection today but contributes nothing to General.
- **Entry content shown:** the entry row, exactly what the word page shows (`find_entry`), with no per-membership
  `content_snapshot` and no per-membership level/framework/topic override (those belong to one set). So General shows
  the same card as the word page.

D-111 auto-published sets (`attested_by = "orena:auto-publish (D-111)"`, `auto_published: true`) pass condition 2,
as they pass the publish gate today. Whether "attested by a human" excludes them is decision H2.

## 3. The General collection's own lifecycle

It has **no lifecycle state**, because it stores nothing. No row in `vocabulary_collections`, no membership rows, no
receipts, no admission of its own (an admission invented for it would be a rule attesting rights nobody checked).

- **"Imports never change published content" (D-178 point 4):** holds trivially. Nothing can import into General and
  General holds no content. `entry_has_published_membership` and `_authored_match.published_conflict` read real
  memberships only, so General causes no new conflicts and removes none.
- **Reserved identity:** the id `orena-general-<language_code>` (lower-case, as the repository stores codes). The
  collection id spaces must not collide: the import route and the content-pack importer (which both accept a
  caller-supplied `collection_id`) and `import_source` itself must refuse any id starting `orena-general-` (422).
  Generated ids (`stable_collection_id`) end in a 12-hex digest and cannot match by accident.
- **Who can edit it:** nobody; there is nothing to edit. **Who can unpublish it:** nobody directly. `publish`,
  `status` and `finalize_collection_publication` already answer "not imported" (422) for an unknown id, which is
  correct; the implementer adds an explicit message for the reserved prefix. A word leaves General by withdrawing its
  set, the control moderators already have. An operator kill switch for the whole feature is decision H3.
- **Content packs:** General must not be exportable. The `vocabulary_ids` lambda (`app.py`, `configure_content_packs`)
  and `_vocabulary_pack_export` call `list_collections` / `get_collection`; both must skip the General id.

## 4. Persistence

**No migration, no schema change, no new table, no new column, no stored row.** Reads add one query shape on existing
tables and existing indexes (`ix_vocabulary_collections_language_status`, `ix_vocabulary_memberships_entry`,
`ix_vocabulary_memberships_collection_position`).

Shape, one implementation for PostgreSQL and the SQLite dev adapter (both are `SQLAlchemyVocabularyRepository`):

1. Load `id, provenance` of `VocabularyCollection` where `language_code == L` and `catalog_status == 'published'`
   (hundreds of rows, not entries). Keep ids for which `_publication_admission` accepts. Guard: if the list exceeds a
   fixed bound (5,000) chunk the `IN` list rather than exceed driver parameter limits.
2. Entries: `WHERE language_code = L AND EXISTS (SELECT 1 FROM memberships m WHERE m.entry_id = e.id AND
   m.collection_id IN :ids)`, `ORDER BY normalized_term, identity_key`, `LIMIT/OFFSET`. EXISTS, not DISTINCT:
   PostgreSQL has no equality for `json`, which already broke `find_entry` once (comment in the repository).
3. Count and levels: `COUNT(*)` with the same predicate; levels as `SELECT DISTINCT level`, not by loading rows. The
   existing `_collection_stats` loads every member row and is wrong for a large set; General must not use it.

If measurement on a realistic catalogue shows step 2/3 too slow, add a short in-process cache keyed by (language, a
version of the published-id list). That is still no schema change. A stored/maintained membership table (a materialized
General) or an index migration is the point at which the implementer **stops and asks the human** (section 9, H4).
If H1 is answered "yes", the base design still needs no migration (section 9).

## 5. Id, title, ordering, paging, Admin

- **Id per language:** `orena-general-<language_code>`, listed only when that language has at least one qualifying
  entry (no empty collection). Languages are not enumerated: it is built for the language the request asks for, which
  `_require_vocabulary_language_code` already validates with `is_enabled`. Any catalogue language works with no code
  change.
- **Title per UI language:** collection titles are stored strings the clients show verbatim (Discover
  `entryFromCollection`, Library `curatedRows`, Collection `model.js`). The API returns a neutral English fallback
  `title` plus `system_kind: "general_catalogue"`. The clients map `system_kind` to a copy key in
  `static/orena/copy` (EN, VI, ZH, all three, no hardcoded string) and use that for the title. The mapping sits in the
  three existing model functions; no new component. The server never needs the UI language.
- **Sorting in Discover:** curated packs first, General last. Today the list sorts `(framework, title)`; General has
  an empty framework and would sort first, so the sort key gains `system_kind` last. The Discover screen must be
  checked not to re-sort.
- **Paging when large:** the existing collection endpoint already pages (`limit` 1-5000, `offset`, `has_more`,
  `total`). General uses it unchanged with the stable order in section 4. The list endpoint
  (`becoming_vocabulary_library_collections`) currently loads up to 5,000 entries of every collection to compute
  progress; for General that would be slow and silently capped. General is excluded from that loop and its progress
  is computed from the learner's saved words: a repository method `general_contains(language, normalized_terms)` (one
  chunked `IN` query over the learner's words) intersects them with the eligible set. Learner-bounded, not
  catalogue-bounded.
- **Admin:** a read-only row per language in the Content list: kind vocabulary, status `published`, subtitle derived
  from facts, `actions: ["preview"]` only (no publish, unpublish, archive, restore). Preview reads through the same
  `get_collection`. It is excluded from the overview "published/draft" counts (derived, not reviewable content).
  The implementer must confirm against the Admin design frames that a vocabulary row with a single `preview` action
  is drawn; if not, record it in `docs/project/UI_BACKEND_GAPS.md` rather than invent it.

## 6. Learner surfaces

Reuse only. Discover shelf uses the existing collection card; the card opens the existing Collection screen
(`#/collection/curated:orena-general-en`), which pages through the existing API; each word opens the existing word
page; search (`/api/vocabulary/catalogue/search`) and `find_entry` are untouched, because every General word already
satisfies their gate. No new card, badge, chip, hint, empty state or copy except the one translated title. The design
(`docs/design/canonical-ui/screens/`) draws no special card for it, and none is added.
Run the usual verification (EN, VI, ZH, light/dark, desktop and phone) before calling it REVIEWABLE; this document does
not.

## 7. Tests to write

Repository (PostgreSQL-compatible SQLAlchemy on the hermetic SQLite engine, one test each):
1. Published + valid admission -> entry listed, counted, findable by page; unpublished, archived, pending_review,
   never-published sets -> nothing.
2. Entry in published A and unpublished B stays; unpublish A -> gone; republish A -> back.
3. Admission invalid on a `published` set (missing attestation, rights `unknown`, completeness `partial`, empty
   `attested_by`) -> contributes nothing, though `list_collections` still lists the set.
4. D-187 service-token import of a set, then a human publish -> joins only after the publish; before it, absent.
5. Entry in a pending set that shares identity with a published entry -> shown from the entry row, no snapshot.
6. Language isolation (en vs zh vs a third catalogue language); empty language -> General not listed.
7. Paging stability: 3 pages over > page size entries, no duplicates, no gaps, `total`/`has_more` correct; search
   and level filters.
8. Entry in two published sets appears once.
9. No migration: `VOCABULARY_REQUIRED_COLUMNS` unchanged and the Alembic head unchanged.
10. PostgreSQL parity: the query has no `DISTINCT` over a `json` column (compiled-statement check).

Routes / app:
11. Reserved id refused on `/api/admin/vocabulary/import` and in the content-pack importer; publish/status on the
    General id -> 422.
12. Content-pack export excludes General.
13. `/api/vocabulary/library/collections` lists General last, with `system_kind`, and does not load 5,000 entries for
    it; progress counts only the learner's saved words that are eligible.
14. Collection detail for the General id pages; unknown language -> 404.
15. Word page / search / `find_entry` behaviour unchanged for the existing cases (regression).
16. Imports: authored import into a set still refuses `published_conflict`; General membership does not create a
    conflict for an entry only reachable through it.
17. Admin: listing has the read-only row, no actions, excluded from counts.

Front end (`scripts/*.mjs` gates): `system_kind` maps to the translated title in EN, VI and ZH in the three models;
a missing key fails the copy-parity gate; Discover order puts General last.

## 8. Findings outside this change (reported, not fixed)

- **F1.** `set_collection_status` (`POST /api/admin/content/vocabulary/{id}/status`) allows `pending_review ->
  published` with no admission check, bypassing `_publication_admission`. The Admin "publish" action for a draft uses
  the `/publish` route, so the UI path is safe, but the route is a gap. Recommend requiring a valid admission for any
  transition into `published`.
- **F2.** `becoming_vocabulary_library_collections` loads up to 5,000 entries per collection to compute progress.
  That is already slow for large sets and is the reason General cannot ride it.
- **F3.** Unpublished static seed entries reach learners through the Feed pool (`all_vocabulary_entries`) and the word
  page fallback (`vocabulary_entry_for`), against the "published only" docstring of `vocabulary_library.py`.
- **F4.** `list_entries_for_language(limit=5000)` orders by `identity_key`; in a catalogue above 5,000 entries per
  language the Feed pool and the saved-word resolver never see the rest. General does not change this.

## 9. Decisions the human must make (not settled from the code)

- **H1. Does Option A mean "draft words become reachable"?** As specified it does not (section 0): it cannot, under
  the gates. If yes, the missing piece is a human act, not a rule: an Admin action to publish a draft set **into
  General without its own card** (the admin attests rights and completeness exactly as for publish; recorded in the
  set's `provenance`, e.g. `listing: "general_only"`, with `status` published and the card hidden from Discover). That
  also needs no migration. It is an extension; it is not designed here beyond this sentence.
- **H2. Does a D-111 rule-attested set count as "attested by a human"?** Recommended yes: it is a published set today
  and the policy is the human's own (D-111 point 1). If no, General excludes every auto-published set, which would be
  most of it.
- **H3. Operator kill switch.** Do you want a per-deployment switch (an operational policy, D-172) that hides General
  entirely? Without it nobody can unpublish General; it can only shrink by withdrawing sets. Recommended: yes, default
  on.
- **H4. Performance escape hatch.** If the derived query is too slow at the real catalogue size, the next step is a
  cache (no schema change) and only then an index migration. Confirm that crossing into a migration stops for approval.
- **H5. F1 and F3** are separate fixes; say whether to open them.

## 10. After the independent review (APPROVED WITH CONDITIONS) - what was decided and built

Human decisions: derived General, no migration; H1 rejected (no "publish into General only"); H2 yes (D-111 rule-attested
sets count). Lead decisions: H3 kill switch yes, default on; H4 no cache in this slice; F1 and F3 are fixed on other
branches and are not touched here.

- **P1-1 reserved id.** `is_reserved_collection_id` matches `NFKC + strip + casefold` with prefix `orena-general-`.
  Enforced inside `import_source` (every caller), `finalize_collection_publication` and `set_collection_status` (own
  message), and earlier with a clean 422 in `_admin_vocabulary_metadata` (Admin import, preview and the service-token
  import all pass through it before the token guard's `get_collection`) and in `_vocabulary_pack_import`. The resolver
  `general_collection_language` accepts only the exact lower-case id; the language must pass `is_enabled`, else 404. A
  stored row under the reserved id is **fail-closed**: the synthetic id wins, the row is never listed to learners and
  never contributes.
- **P1-2 separate methods.** `general_summary`, `general_page`, `general_contains` on the repository; composed only in
  the two learner routes in `app.py`. `list_collections`, `get_collection`, `_collection_stats`, the pack code and the
  Admin repository are unchanged. **No Admin row** (revised from section 5).
- **P1-3 defensive admission.** `_admission_qualifies` coerces provenance with `_copy_json`, requires a mapping and
  catches `ValueError`, `TypeError` and `AttributeError` per collection; the gate itself is `_publication_admission`.
- **P1-4 scope.** General(L) is the **persisted, admission-valid subset**. It excludes static seed collections
  (`vocabulary_library.py`, not rows of `vocabulary_entries`, no admission record), words of a set that reached
  `published` without a valid admission (F1), and the raw Feed and word-page seed paths (F3). It is not "the union of
  reachable words". After F3 is fixed, nothing in that fix changes this scope, because General reads persisted rows only.
- **P1-5 withdrawal is by set.** Pinned by `test_withdrawal_is_by_set_not_by_content_and_this_is_pinned`; recorded in D-188.
- **P2-1 query.** One combined predicate: an OR of `EXISTS ... IN (chunk)` (chunk size `_GENERAL_ID_CHUNK = 500`, lowered
  in a test), so COUNT, OFFSET and LIMIT see one set. More than `_GENERAL_ID_LIMIT = 20000` qualifying collections is a
  logged error and General is withheld (`VocabularyContentUnavailable`), never truncated. Order `(normalized_term,
  identity_key)`; level filter on the entry's own level only. Measurement trigger for keyset paging: about 100k entries
  per language.
- **P2-2 progress.** The list and the detail route both compute General's progress from the requesting learner's own saved
  words (`saved_vocabulary_words()` then `general_contains`, chunked) and `saved_vocabulary_state` for those words only.
- **P2-3** the General summary carries no `provenance` or `attested_by` (tested).
- **P2-4 clients.** `static/orena/copy/general-catalogue.js` holds the one key in EN, VI and ZH, and
  `collectionTitle(item)` (English `title` is the fallback) is used by the Discover, Library and Collection models.
  General sorts last on the server (appended after the sort), and no client re-sorts.
- **P2-5 kill switch (H3).** The D-172 operational policy `vocabulary.general_catalogue_enabled` (bool, default true,
  group `vocabulary`), read per request through `policies.value`. Off: General is absent from the list and its detail
  answers 404; search, the word page, the Feed and every real collection are unchanged. No cache (H4).
- **P2-6** the "published with an invalid admission" case is a live test; the gate is not weakened to the status flag.
- **Fix after browser verification.** Items are drawn from a qualifying membership (snapshot, level, framework, topic),
  chosen snapshot-first then lowest collection id; levels and the level filter use the effective level of qualifying
  memberships. See D-188 "Content shown". Section 2's "Entry content shown: the entry row" is superseded.
