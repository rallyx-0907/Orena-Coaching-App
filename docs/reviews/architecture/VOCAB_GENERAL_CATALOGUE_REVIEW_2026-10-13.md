# Architecture review - Vocabulary "General catalogue" (D-188 proposed)

- Reviewer: Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer.
- Reviewed commit: `1c30c70d` (branch `claude/vocab-general-catalogue`), checked against the code at origin/main `172ae216`.
- Reviewed: `docs/reviews/architecture/VOCAB_GENERAL_CATALOGUE_DESIGN_2026-10-13.md` and the PROPOSED D-188 entry in `docs/project/DECISION_LOG.md`.
- Basis: reading of `writing_coach/persistence/vocabulary_repository.py`, `app.py` (import, learner and content-pack routes), `writing_coach/admin_console_api.py`, `writing_coach/persistence/admin_repository.py`, `writing_coach/content_pack_api.py`, `writing_coach/becoming_library.py`, `writing_coach/vocabulary_library.py`, `static/orena` collection consumers. No code was run and no Docker was used. This is a design review; no code exists yet.
- Human decisions taken as given: Option A; General derived at read time from published collections whose admission passes `_publication_admission`; draft words do not reach learners; H1 rejected; H2 = yes; F1 and F3 are separate PRs.

## Verdict: APPROVED WITH CONDITIONS

The core rule is sound. I found no way for a word to reach a learner through General that cannot already reach one. Every learner gate today is `catalog_status == 'published'` through a membership join, and General is strictly narrower (published AND a valid admission, with the same entry row). No migration is needed. Implementation may start once the P1 conditions below are accepted into the design and D-188. There is no P0.

## P0

None.

## P1 (conditions; each must be satisfied in the design or D-188 before code merges)

### P1-1. The reserved id must be enforced at the repository choke point, not only at two routes

Where: design section 3; `app.py` import route (`collection_metadata["collection_id"]`, line ~3951), `_vocabulary_pack_import` (`data.get("id")`), `import_source` (`collection.get("id")`).

What is wrong or underspecified:
- Two callers accept a caller-supplied id (the Admin import route and the content-pack importer). `import_source` accepts any id and creates a real row. Any other caller (scripts, a future route) can create a real row named `orena-general-en`.
- The service-token guard runs `repository.get_collection(collection_id, status=None)` first. For the reserved id that returns `None` (no row), which reads as "new set, allowed". The reserved check must run before that guard, otherwise the token path is the one place that depends on an incidental refusal.
- Matching by plain prefix is not enough. `_text` only collapses whitespace. `ORENA-General-en`, ` orena-general-en`, and a full-width or other NFKC-equivalent spelling pass a case-sensitive, non-normalised prefix test.
- A real row with the reserved id might already exist (out-of-band SQL, an earlier content pack). The design does not say which wins.

Required:
1. Put the refusal in `import_source` itself (so every caller is covered), plus an early 422 in the Admin import route and the content-pack importer for a clean message. Match on `unicodedata.normalize("NFKC", id).strip().casefold().startswith("orena-general-")`.
2. In the General resolver, match the exact lower-case id only, and parse the language by stripping the prefix. The remainder must pass `is_enabled`, otherwise 404 (never 500, never a general fallthrough).
3. The synthetic id wins over any stored row with that id. Decide fail-closed or fail-open in D-188 and test it.
4. `set_collection_status`, `finalize_collection_publication` and the Admin `/publish` and `/status` routes already answer "not imported" for an unknown id. Keep that, add a test that no row is created as a side effect, and give the reserved id its own message.

### P1-2. Keep General out of `list_collections` / `get_collection` / `_collection_stats` and out of Admin's `_content_records`

Where: design sections 3 and 5; `vocabulary_repository.list_collections` / `get_collection`; `app.py` `configure_content_packs` (`vocabulary_ids` lambda) and `_vocabulary_pack_export`; `admin_console_api._content_records`.

What is wrong:
- Design section 3 says the pack lambda and exporter "must skip" General. That is the wrong shape. `list_collections(status=None)` is the operator listing, `get_collection(status=None)` is the service-token guard, and `list_collections` is also the pack-export enumerator. If General is injected into those methods, every caller must remember to exclude it. This is exactly the "forgetting to filter" failure the `list_collections` docstring warns about.
- The Admin list is a separate query (`admin_repository.list_vocabulary_collections`). Adding a synthetic row to `_content_records` feeds `content_counts`, `status_counts`, the overview `published` total, `filter_records`, `paginate` and the "needs attention" counts. Excluding it from "overview counts" cannot be done without touching each of those consumers. The preview endpoint (line ~849) matches `content_id` against the same Admin list, so a synthetic row would also need a bespoke preview branch. Also, a vocabulary row with only a `preview` action may not be drawn by the Admin design; CLAUDE.md rule 4 says to invent nothing.

Required:
1. Implement General as separate repository methods (for example `general_summary(language)` and `general_page(language, search, level, limit, offset)`), composed at the app layer in the two learner routes only. `list_collections`, `get_collection`, `_collection_stats`, the pack code and the Admin repository stay unchanged. Then export exclusion is by construction, with a regression test, instead of by a skip list.
2. Do not add an Admin content row in this change. Admin shows real sets, which is where the moderator's controls are. If the human wants General visible to operators, expose one derived fact (for example eligible-word count per language) in an existing overview block, not a content record. If the row is kept anyway, it must be built outside `_content_records` or tagged and filtered in all four consumers, and the Admin design must be checked first (record the gap in `docs/project/UI_BACKEND_GAPS.md` if absent).

### P1-3. Evaluate admission per collection defensively

Where: design section 4 step 1; `_publication_admission` (line 248).

What is wrong: `_publication_admission` calls `provenance.get(...)` and raises `ValueError` on any failure. In step 1 General runs it over every published collection of the language. A published row whose `provenance` is not a mapping (null, string, legacy shape; `_copy_json` is used everywhere else precisely because of this) raises `AttributeError`, and a rejecting set raises `ValueError`. Either one that escapes turns the whole General read into a 500 or, in `_persisted_vocabulary_collection`, into a silent 404 through the broad `except`.

Required: coerce provenance with `_copy_json` plus an `isinstance(..., Mapping)` check, catch `ValueError` per collection, treat any failure as "does not qualify" and continue. Keep the exact gate (`publication_attested is True`, not truthiness). Tests: provenance null, a string, `{}`, `admission: "x"`, `publication_attested: "true"`, whitespace-only `attested_by`, rights `unknown`, completeness `partial`, and one valid set beside them, which must still be listed.

### P1-4. Scope statement: persisted collections only, and the design's "union of reachable words" claim is false

Where: design section 0 and D-188 "Rule".

What is wrong: section 0 says General is "the per-language union of the words learners can already reach". It is not.
- Static seed collections (`vocabulary_library.py`) are published and learner-visible, but they are not rows in `vocabulary_entries` and carry no admission record. Under the stated rule they are not in General. `becoming_vocabulary_library_collections` merges static and persisted summaries, so a language whose catalogue is mostly static would show a "General" that is a small fraction of Discover.
- Words in a set that reached `published` without a valid admission (F1) are reachable by search and the word page but are not in General.
- Static seed words reach the Feed and the word page by the raw paths of F3.

Required: state in the design and D-188 that General(L) is the persisted, admission-valid subset, and name what it excludes. The human should confirm that persisted-only is what Option A meant (static published seeds are repository-reviewed content and arguably qualify; including them means merging by `identity_key` as `_vocabulary_feed_pool` does, which is more work and is not recommended for this change). Do not describe it as the union. After F3 is fixed, re-check that nothing in the F3 fix changes this scope.

### P1-5. Withdrawal is by set, not by word or content; D-188 must say so

Where: design section 2 ("Withdrawn ... A is the gate") and D-188.

What is wrong: the claim that an entry in published A and withdrawn B "stays through A; that is correct" is true for membership but not for content. The entry row is shared and has no rights field. `import_source` merges a pending set's data into an existing entry row when that entry has no published membership (`_merge_existing_entry`: examples, meanings, definitions, usage notes, origins), and it never scrubs it. So if B (later withdrawn for a rights reason) created or enriched the entry first, and A (published) later shares the identity, the row learners see through General still carries B's text, and A's attestation never covered it. This is already true of the word page and of search. General does not create it, but General turns it into a bulk-browsable, pageable surface, which raises the stakes of a rights withdrawal. Likewise a rights change on A after publication has no effect on General (the admission is read at request time, but rights status changes go through status transitions, not through editing the admission). The admission record is immutable once published.

Required:
1. Record in D-188 that General inherits the by-set granularity of withdrawal, that shared entry rows can carry content from a withdrawn set, and that this is accepted (or give the human the choice). This is a rights-relevant behaviour and the design currently states the opposite.
2. Add a test that pins current behaviour (entry first imported via B, enriched, B unpublished, A published: the entry is in General with B-derived text), so a later fix is a deliberate change.
3. The practical emergency lever is H3 (see below). Treat H3 as required, not optional, for exactly this reason.

## P2 (should fix; may be done during implementation)

### P2-1. Query shape on PostgreSQL and SQLite

- EXISTS over `IN :ids` is correct and avoids the `json` DISTINCT trap. Keep `ORDER BY normalized_term, identity_key` (`identity_key` is unique, `uq_vocabulary_entry_identity`), so paging is total and stable. `ix_vocabulary_entries_language_term (language_code, normalized_term)` serves the filter and the first sort key.
- "Chunk the IN list" is ambiguous for a single paged query. Chunks must be combined in one predicate (`OR` of EXISTS per chunk, or `= ANY(:array)` on PostgreSQL), so `COUNT`, `OFFSET` and `LIMIT` see one set. Separate queries per chunk would break paging. SQLite's bound-variable limit is the practical ceiling there (999 on older builds). State the chunk size and test with the chunk size lowered, so the multi-chunk path runs in CI.
- The 5,000 "guard" must not be a silent truncation of eligible collections. Silently dropping sets shrinks General without anyone knowing. Fail closed with a logged error, or chunk without a cap. Separately, `limit` is bounded to 5,000 per page by the existing route; keep it.
- Deep `OFFSET` on a large language rescans and re-sorts. Acceptable at the stated sizes. If the catalogue approaches 100k per language, use keyset paging on `(normalized_term, identity_key)`. Note this as the measurement trigger, not now.
- Ordering depends on the database collation (PostgreSQL vs SQLite, and for Chinese). Tests must assert stability and no duplicates or gaps, never an exact cross-engine order of mixed-case or non-ASCII terms.
- `level` filtering: membership-level overrides belong to one set. General uses the entry's own level (design section 2). The filter must be `lower(entry.level) = :level` only, not the membership expression `_list_entries_in_session` uses. Also note the detail route re-filters search and level in Python after the database has paged, which is harmless for a database-side filter but must not be relied on.
- Levels: `SELECT DISTINCT level` is fine (a text column, not `json`).

### P2-2. Progress

- The design computes list-route progress from the learner's saved words via `general_contains`. `saved_vocabulary_state(candidates)` takes candidate words, so the route needs the learner's whole saved-word list first. Specify that source (and its bound for a learner with 1,600+ words, see `_catalog_resolver`).
- The detail route computes `progress` only over the page returned (default 100) for every collection today. For General, list progress (full) and detail progress (page) will disagree. Pre-existing for large sets, but General makes it visible. Either compute detail progress with the same bounded method or record the limitation.
- Progress must come only from the requesting learner's own state. Add a test that two learners see different progress on the same General page and that nothing about another learner is present.

### P2-3. Summary payload must not carry provenance

`_collection_summary` includes `provenance` (with `admission.attested_by`, which is the administrator's identity) in what `/api/vocabulary/library/collections` returns to learners today. That is pre-existing and should be reported, but the synthetic General summary must not copy it: no `provenance`, no `attested_by`, no per-set data. Also note the entry dicts carry `provenance.sources` (import filenames); check what `vocabulary_card_from_catalog_entry` strips and do not widen it.

### P2-4. Learner clients

- Title: `system_kind` -> copy key in all three models (Discover, Library, Collection). Fall back to the English `title` if a UI language has no key, and add the key in EN, VI and ZH (the copy-parity gate). Check the Library tab model, which also builds `collectionId: curated:${item.id}`.
- Sort: add `system_kind` as the last key. Confirm Discover and Library do not re-sort client-side. Test with a framework that sorts after `""`.
- Do not hardcode language pairs: the language comes from the request and `is_enabled`. Pre-existing hardcodes (`content_pack_api._items_for` accepts only `{"en","zh"}`, `configure_content_packs` defaults to `("en","zh")`) are unrelated to this change but mean pack export will never include a third language. Do not "fix" them here.

### P2-5. Cache and kill switch (H3, H4)

**H3 recommendation: yes, build it, default on.** Implement it at the app layer (the two learner routes), read per request from the existing operational-policy mechanism (D-172) if it fits, otherwise a single setting; not at repository level. Off means: General absent from the list, the General id answers 404 on the detail route, and nothing else changes (search, word page, Feed, real collections are untouched). Because withdrawal is by set (P1-5), this is the only quick lever for an operator who needs the aggregate surface gone. Log toggles. A restart-only env flag is acceptable only if the policy mechanism does not fit.

**H4 recommendation: no cache in the first slice; measure first, then cache only the summary.** If a cache is needed (the list route would run `COUNT` and level queries on every Discover load), cache only `{item_count, levels}` per language, keyed by a hash of the sorted eligible collection ids. That key is exact: published sets are immutable (`import_source` refuses new entries or memberships in a published set), so the same id set yields the same count. Never cache the eligible-id list or entry pages with a TTL: a stale cache would delay a withdrawal, which contradicts "leaves on the next read". Crossing into a new table or index migration stops for human approval, as the design says (agree).

### P2-6. Interaction with F1 and F3

- F1 (the `/status` route publishes with no admission check): until it is fixed, a set can be learner-visible as its own collection but contribute nothing to General. That is the safe direction, and it makes the General test for "published with invalid admission" a live case, not a hypothetical. Do not weaken the General gate to the status check on the grounds that F1 is "separate".
- F3 (unpublished static seeds reach learners): unaffected, because General reads persisted rows only. Say so, so the F3 fix is not blocked on this change, nor the reverse.
- When F1 is fixed, `set_collection_status` will refuse publish transitions without a valid admission, and General needs no change.

### P2-7. Persistence

Confirmed: no migration or schema change is needed. Existing indexes cover the shape (`ix_vocabulary_collections_language_status`, `ix_vocabulary_memberships_entry`). `VOCABULARY_REQUIRED_COLUMNS` exists at line 52, so test 9 is implementable. Orphan entries (no membership) are never listed; `memberships.collection_id` cascades, and no route deletes entries or collections. Test both anyway. Keep the repository read-only for General: no writes, no receipts, no `session.begin()`.

## Check results against the seven review questions

1. **Membership rule.** No new reachability. Token imports (D-187): forced `pending_review`, `publication_attested False`, so cannot qualify until a human publishes the set; verified in the import route. Unpublished and archived sets: excluded by `catalog_status`. Deleted entries: no delete route exists; cascade covers a deleted collection. Rights changes: admission is immutable after publish, so withdrawal is by set (P1-5). Entry in published plus withdrawn set: stays through the published set, with the content caveat of P1-5. Language mismatch: import validates the row language against the collection; General must still require both `entry.language_code == L` and a collection of language L, and test a hand-crafted cross-language membership. Spoofing the reserved id: see P1-1.
2. **Read paths.** Discover, Library and the Collection screen go through the two routes in `app.py`, which are the only learner entry points for collection ids. Paging, search and level are handled by the detail route. Word page (`find_entry`), catalogue search, Feed (`list_entries_for_language`), saved words and neighbours do not take a collection id and need no change. Fallback: for an unknown id `_persisted_vocabulary_collection` returns `None` and the route falls back to the static catalogue then 404, so there is no leak. Add a test that no static collection id begins `orena-general-`. The list route branches on `summary.get("origin") == "imported"`, so the General summary needs an explicit branch (P2-2).
3. **Admin.** Read-only enforcement is by absence of a row (publish, status, preview, import all see an unknown id). Overview counts and export exclusion are only achievable by construction, see P1-2.
4. **Derived query.** Sound with the changes in P1-3 and P2-1.
5. **Persistence.** Confirmed (P2-7).
6. **Multilingual parity.** The design is language-neutral and uses `is_enabled`. Keep the id parse general (P1-1) and the copy in EN, VI and ZH with an English fallback (P2-4). Nothing in the design is hardcoded to two languages.
7. **Tests.** Tests 1-17 are a good base. Missing negative tests, to be added:
   - reserved-id spoofing: `ORENA-GENERAL-EN`, leading and trailing space, full-width spelling, on the Admin import route, the service-token import route (must 422 before any write), the content-pack importer, and a direct `import_source` call. Assert `vocabulary_collections` is unchanged afterwards;
   - a pre-existing real row with the reserved id (precedence, fail-closed);
   - `orena-general-xx` for an unknown or disabled language, `orena-general-` empty, and a non-string id: 404, not 500;
   - Admin `/publish`, `/status`, preview and edit on the General id: 422 or 404, no side effect;
   - malformed provenance and admission variants (P1-3), with a valid sibling set still listed;
   - crafted cross-language membership (entry `en` in a `zh` set) not in either language's General;
   - orphan entry with no membership never listed;
   - entry first created by a set that is later unpublished, then included in a published set (the P1-5 pinning test);
   - D-111 auto-published set included (H2 positive), and one whose admission was altered excluded;
   - multi-chunk eligibility with the chunk size lowered, and a paging test that spans chunk boundaries;
   - an unpublish between page 1 and page 2: no error, `total` reflects the new state;
   - general summary has no `provenance` or `attested_by`;
   - kill switch off: absent from the list, detail 404, search and word page unchanged;
   - per-learner progress isolation;
   - content-pack export with General present in the database state (no General, nothing exported), and Admin overview and list counts unchanged by the feature.

## Sign-off

Approved with conditions P1-1 to P1-5. After they are written into the design and D-188, implementation may proceed without a second design review. Implementation itself needs the normal code review and the learner-surface verification (EN, VI, ZH, light and dark, desktop and phone) before `REVIEWABLE`. This review is not product approval.

Reviewer: Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer. Reviewed commit `1c30c70d`. Date 2026-10-13.

---

## Code review of a1f06e48

- Reviewer: Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer.
- Reviewed: `git diff 2fb25de8..a1f06e48` (15 files), read against the conditions above. Reading only: nothing was run, no Docker. The implementer's reported results (full suite 5672 passed, Node gates and ESM graph OK) were not re-verified by me and are local execution, not CI.

### Conditions, checked in code

- **P1-1 reserved id: met.** `is_reserved_collection_id` normalises with NFKC, trim and casefold. The refusal sits in `import_source`, `set_collection_status` and `finalize_collection_publication` (the repository choke point), and again early in `_admin_vocabulary_metadata` (this runs before the service-token `get_collection(status=None)` guard, so the token path is covered) and in `_vocabulary_pack_import`. The resolver `general_collection_language` accepts the exact lower-case id only and the detail route additionally requires `is_enabled`; every other spelling of the reserved space gets 404 from `_general_catalogue_page`, with no fall-through to the static catalogue or a stored row. Fail-closed for a pre-existing stored row: `_general_predicate` excludes reserved ids from the qualifying set, the list route skips such a row, and the detail route never reads it. Tests cover each of these.
- **P1-2 structure: met.** General has its own methods (`general_summary`, `general_page`, `general_contains`). `list_collections`, `get_collection`, `_collection_stats`, the Admin repository, `_content_records` and the pack code are untouched, so export and Admin counts exclude it by construction. No Admin content row was added. A regression test pins the Admin list and the pack enumeration.
- **P1-3 admission: met.** `_admission_qualifies` coerces with `_copy_json`, requires a Mapping, calls the unchanged `_publication_admission`, and treats `ValueError`, `TypeError` and `AttributeError` as "does not qualify". The strict gate (`is True`, rights set, `complete`, non-empty `attested_by`) is the existing function, not a copy. Parametrised tests cover malformed provenance with a valid sibling still listed.
- **P1-4 scope: met in text.** The design and D-188 now state persisted-only. The human should still confirm that reading (a decision, not a code matter).
- **P1-5 withdrawal: met.** D-188 records by-set withdrawal; `test_withdrawal_is_by_set_not_by_content_and_this_is_pinned` pins it. H3 is built.
- **Chunked predicate and the 20,000 cap: met.** One `and_(language, or_(*EXISTS(entry_id = entry.id AND collection_id IN chunk)))` is shared by count, levels, page and `general_contains`, so COUNT/OFFSET/LIMIT see one set. `_GENERAL_ID_CHUNK = 500` and 20,000 ids is at most 20,000 bound parameters, under the PostgreSQL (32,767 server-side) and modern SQLite (32,766) limits; older SQLite builds (999) are not supported by this value and the repository already assumes a modern one elsewhere. Above 20,000 it raises `VocabularyContentUnavailable` and logs, and the routes turn that into no General (list) or 404 (detail): fail closed, not truncation. The only DISTINCT is over the text column `level`, not `json`. Order is `(normalized_term, identity_key)` with unique `identity_key`, so paging is total. The chunk size and the cap are module values that tests lower, so the multi-chunk path and the cap run in CI.
- **Kill switch: met.** Policy `vocabulary.general_catalogue_enabled` (bool, default True, group `vocabulary`) is read per request by `_general_catalogue_enabled` (`value(...) is not False`); off removes General from the list and returns 404 on the detail, and nothing else changes. The new policies group is wired in `GROUPS`, `GROUP_ORDER` and the EN/VI/ZH admin copy with a fixture row in the Node gate.
- **Progress: met.** `_general_progress` takes the learner's own saved words, asks `general_contains` for those only (casefolded matching, chunked), and uses `saved_vocabulary_state` on the hits. The list and detail routes now use the same method, which also removes the page-only mismatch for General. A test checks two learners.
- **Client: met.** `collectionTitle(item)` maps `system_kind` to the EN/VI/ZH key with the server title as fallback and is used in Discover, Library and Collection models; a Node gate checks the three languages and that other collections keep their stored title. The server appends General last after the existing sort. The summary and page carry no `provenance`/`attested_by` (tested).
- **Tests: no weakened assertion.** The diff adds one Python test file and one Node gate and changes no existing assertion; the only edit to an existing test file is one added fixture row in `test_orena_admin_policies.mjs`. The negative tests I listed are present, including spoofed spellings on every import path, a stored reserved row, cross-language membership, orphan entries, the cap, per-learner progress, the kill switch and unchanged Admin/pack output.

### Findings

No P0 and no P1.

- **P2-A. PostgreSQL execution is not tested.** The chunked OR-of-EXISTS and the DISTINCT-on-level statement run only on the SQLite engine. They are standard SQL, and I found no PostgreSQL-specific risk by reading, but add a compiled-statement check on the PostgreSQL dialect (no DISTINCT over `json`), and exercise it once on the sandbox PostgreSQL when a lane may run Docker. Forty OR'd EXISTS at the cap is a heavier plan than one `IN`; measure on a realistic catalogue before relying on 20,000.
- **P2-B. Cost per request.** `general_page` re-computes count and distinct levels for every page, and the list route computes them per Discover load. Acceptable now; if measurement says otherwise, use the summary-only cache keyed by a hash of the eligible ids (my H4 recommendation), not a TTL on entries.
- **P2-C. Not verified here.** Discover's and Library's visual order with General last, and the card in EN/VI/ZH, light and dark, desktop and phone, need the usual browser verification before `REVIEWABLE`; the Node gate covers the title only. `include_review` on the General detail uses the page's saved words, as before.
- **P2-D. Notes for the human, unchanged from the design review.** Persisted-only scope (P1-4) and by-set withdrawal (P1-5) are accepted behaviours that the human has to confirm. The content-pack `{"en","zh"}` hardcode is pre-existing and was correctly left alone.

### Final verdict (code): APPROVED

Each condition is met in the code, not only in the text. Remaining items are P2 and do not block merge into the lane; browser verification and a PostgreSQL run are required before the surface is called `REVIEWABLE`. CI evidence is still needed for any claim beyond local execution. This is architecture approval only, not product approval.

Reviewer: Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer. Reviewed commit `a1f06e48`.
