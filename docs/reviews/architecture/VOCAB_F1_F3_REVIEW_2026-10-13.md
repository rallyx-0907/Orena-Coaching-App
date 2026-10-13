# Architecture review - Vocabulary F1 (status admission) and F3 (seed visibility)

- Reviewer: Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer.
- Date: 2026-10-13. Base: origin/main `172ae216`.
- Commits reviewed:
  - F1: branch `claude/vocab-status-admission`, head `44b6109b`.
  - F3: branch `claude/vocab-seed-visibility`, head `aca8dd6f`.
- Basis: reading of both diffs and of the surrounding code at those commits (`vocabulary_repository.py`, `admin_console_api.py`, `app.py`, `vocabulary_library.py`, `vocabulary_feed.py`, `becoming_library.py`, `admin_content.py`, `static/orena/capabilities/admin-content.js`, `screens/feed`, the D-187 token guard and tests, the static seed JSON). No code was run and no Docker was used. This is a code and design review, not a test result and not product approval.

## Verdicts

| Branch | Verdict |
| --- | --- |
| F1 `claude/vocab-status-admission` @ 44b6109b | **APPROVED WITH CONDITIONS** (C1 below, an operational data check; no code change required) |
| F3 `claude/vocab-seed-visibility` @ aca8dd6f | **APPROVED WITH CONDITIONS** (C2, C3, C4 below; C2 is a human acknowledgement) |

There is no P0 on either branch.

---

## F1: status route cannot publish around admission

### What the fix does
`set_collection_status` (`writing_coach/persistence/vocabulary_repository.py:1096-1099`) now calls `_publication_admission(provenance)` when the target is `published` and the state really changes. It runs inside the same transaction, after the transition table check, before any write. The Admin route (`admin_console_api.py:1085-1111`) maps `ValueError` to 422 `vocabulary_status_refused`. The check is the same function the `/publish` route reaches through `finalize_collection_publication` (line 1123), so there is one admission definition.

### Every path that can set a collection to `published` (checked at 44b6109b)
| Path | Gate | Result |
| --- | --- | --- |
| `POST /api/admin/console/content/vocabulary/{id}/publish` (`admin_console_api.py:1034-1069`) | `attested` required, then `finalize_collection_publication` -> `_publication_admission` | gated, unchanged |
| `POST .../{id}/status` -> `set_collection_status` | now `_publication_admission` | **fixed by F1** |
| `import_source` with `catalog_status=published` (repository line 661) | `_publication_admission(collection_provenance)` on the incoming provenance | gated. Every caller in `app.py` passes `pending_review` (lines 3879, 3992, 3998); none passes `published` |
| Admin import route D-111 auto-publish (`app.py` `_vocabulary_admission`, ~3648-3662 and ~4153) | builds an approved admission, then `finalize_collection_publication` | gated; the admission is explicit and marked `auto_published` |
| Content-pack importer (`app.py:3865-3902`) | `finalize_collection_publication(..., admission=...)` | gated |
| Admin bulk action | none found for vocabulary collections; the lifecycle footer calls `setCollectionStatus` one id at a time | n/a |
| Scripts | none set a vocabulary collection to published outside the repository API | n/a |
| Static seed JSON | `catalog_status` is data in the file, not a lifecycle path (see F3) | n/a |

Result: after F1, `finalize_collection_publication` and `set_collection_status` are the only two functions that write `catalog_status = published` on an existing row, and both call `_publication_admission`. `import_source` can create a row as published only with a valid admission in the same call.

### D-187 service token
The token is scoped by `service_auth.VOCABULARY_INGEST_PATHS` to `POST /api/admin/vocabulary/preview` and `.../import`, and anything else is treated as anonymous (401). F1's own test `test_the_ingest_service_token_cannot_reach_the_status_route` confirms 401 and no state change. The token import also forces `pending_review` and refuses an existing collection that is not `pending_review`. The token cannot reach `/publish` or `/status`. No change needed.

### Over-blocking check
- **Admin UI.** `lifecycleIntents` hides `publish` for vocabulary ("publishes through its own attested form", `admin-content.js`), and `COLLECTION_STATES` only reaches `published` through intent `publish`, which the footer never offers. So the Admin UI never calls `/status` with `published`. F1 cannot break it. Re-publishing from the UI goes through `/publish` with a fresh attestation, which overwrites the admission.
- **Reversible lifecycle.** `published <-> unpublished` keeps `provenance.admission` (unpublish does not remove it), so re-publish by `/status` succeeds when the earlier admission is still valid. `pending_review -> archived -> unpublished` and `unpublished -> archived` need no admission and still work (test `test_other_transitions_need_no_admission`).
- **A re-import into an unpublished set** replaces `provenance` (repository line 722-723), which drops the admission. Re-publish by `/status` is then refused, and `/publish` (fresh attestation) is the way. That is the correct direction.
- **D-111.** Untouched (it uses `finalize_collection_publication`).
- **Existing tests.** `tests/test_content_lifecycle_reversible.py` changes `repository.set_collection_status(.., "published")` to a helper `_admit` that calls `finalize_collection_publication` with a full admission. This is a real publication, not a loosened check: the transition-table assertions (`archived -> published` raises) still run, because the transition check precedes the admission check. `test_vocabulary_ingest_token.py` and `test_admin_authorization_matrix.py` use `set_collection_status` only for `unpublished`, `archived` or a path that 422s/503s; they are unaffected.

### Findings

**P0**: none.

**P1**: none.

**P2-1. `finalize_collection_publication` ignores the transition table** (`vocabulary_repository.py:1129`). It publishes from any state except published, including `archived`, and from `unpublished`. `_VOCABULARY_TRANSITIONS` forbids `archived -> published` for the status route and the lifecycle test pins it ("restore returns it to the shelf, not to the learner"), but `POST .../publish` on an archived id would publish it directly, with a fresh attestation. The attestation is a deliberate human act, so this is not a bypass of admission, but it is an inconsistency with the stated lifecycle and the UI never offers it. Required (follow-up, not a condition): either apply `_VOCABULARY_TRANSITIONS` in `finalize_collection_publication` (allow `pending_review` and `unpublished` only), or record in D-178/the lifecycle decision that an attested publish may come from archived. Add a test either way.

**P2-2. Re-publish by `/status` reuses an old admission.** `unpublished -> published` through `/status` passes when `provenance.admission` from the first publication is still valid, so a set taken down (for example for a rights concern) can be put back by one API call with no new attestation. `status_history` records the actor, and the UI does not offer this path, so the exposure is API-only. Required (follow-up): when a set is unpublished for withdrawal, mark the admission as superseded or require a fresh `/publish` for `unpublished -> published`, or document in D-178 that `/status` re-publish intentionally restores the previous attestation. Pick one; the General catalogue review (P1-5) makes this more important, because the admission is the General gate.

**P2-3. Refused status moves are not audited.** `admin_console_api.py` writes `_audit(... "outcome": "ok")` only on success. A refused publish attempt through `/status` leaves no audit row. Add an audit with `outcome: refused` and the reason.

**P2-4. Missing negative tests** in `tests/test_vocabulary_status_admission.py`: (a) `unpublished -> published` after a re-import dropped the admission (must 422); (b) `archived -> unpublished -> published` with no admission (422 at the last step); (c) a pending set whose provenance carries a valid admission, moved by `/status` to published, then asserting `provenance.admission` is unchanged and `status_history` has the entry; (d) the refusal leaves `status_history` and `updated_at` unchanged; (e) a missing same-origin header on `/status` is refused (the route calls `_same_origin`, nothing tests it for this route).

**P2-5. `import_source` can move an `archived` or `unpublished` row to `pending_review`** through the field loop (repository ~line 715) because only the "published must not be demoted" case is skipped. D-187 already documents and guards this for the token. For a session administrator it bypasses the transition table (`archived -> pending_review` is not an allowed move). Pre-existing, outside F1. Report only.

### Condition for F1

**C1 (operational, before this reaches staging 8000 or any long-lived database).** F1 blocks new unadmitted publications; it does not repair rows that were already published through the old route. Before merge, the human or operator should run a read-only check on each deployment database for `vocabulary_collections` with `catalog_status = 'published'` whose `provenance->'admission'` fails `_publication_admission` (missing, not approved, not attested, rights not publishable, completeness not complete, empty `attested_by`). Such sets stay learner-visible after F1 and, once the General catalogue ships, will be visible as their own collection but absent from General (that is the safe direction, see the General review P2-6). Decide per set: re-publish through `/publish` with a real attestation, or unpublish. This is a human data decision, not an agent task, and is not a code change in F1.

---

## F3: unpublished static seeds no longer reach learners

### What the fix does
- New `published_vocabulary_entries(language)` and `_LEARNER_ENTRY_INDEX`, built from `_LEARNER_CATALOG_BY_ID` (top-level collections whose `catalog_status` is `published`, plus `internal` extensions folded into a published parent).
- Feed: `_vocabulary_feed_pool` (`app.py:4443`) and the default pool of `daily_feed_candidates` (`vocabulary_feed.py:127`) use the published pool.
- Word page, saved words, neighbours: `vocabulary_entry_for` (`vocabulary_library.py:428-441`) reads `_LEARNER_ENTRY_INDEX`, so `becoming_library._catalog_entry_for` (line 145) no longer returns a seed word.
- The raw `all_vocabulary_entries`, `list_vocabulary_source_collections`, `get_vocabulary_source_collection` remain for authoring and tests. Production code outside `vocabulary_library.py` no longer calls them (grep at aca8dd6f: only tests and `scripts/build_vietnamese_wiktionary_pack.py` read the raw JSON file, which is authoring tooling).

### Data fact that decides the learner effect
All twelve static collections are `catalog_status: seed` today (English: `toeic-600-essential`, `common-3000`, and `cefr-b2/c1/c2` as extensions of `common-3000`, also `seed`; Chinese: `hsk-1` to `hsk-7-9`). The extensions are `seed`, not `internal`, so even a published parent would not pick them up until they are marked `internal`. So after F3 the static learner pool is empty for both languages. Nothing static is published and nothing is folded.

### Surfaces checked
| Surface | Source after F3 | Reads raw seed? |
| --- | --- | --- |
| Feed (`/api/vocabulary/feed`) | published static (empty) + persisted `list_entries_for_language` (published memberships only) | no |
| Library / Discover collection lists and detail | `_LEARNER_CATALOG_BY_ID` + persisted (already gated before F3) | no |
| Word page, saved words, neighbours (`becoming_library`) | persisted `find_entry` first, then `vocabulary_entry_for` (learner index) | no |
| Catalogue search | persisted repository only | no |
| Practice, Review, recall, quiz, Reading lookup, `word_deep`, agent read tools, `deck_repository` | import only `normalize_vocabulary_word`; entries come from saved words or persisted entries | no |
| `collection_ids_for_word` (`vocabulary_library.py:444-454`) | **raw** `_WORD_INDEX` built from `_CATALOG_BY_ID` | **yes, see P2-1** |

JS clients: `screens/feed/screen.js` shows `emptyMarkup` when `cards.length` is zero and guards `payload?.items || []`; `feed/model.js` maps over items. An empty feed does not break the screen. The Feed route builds `items` from candidates and returns `[]` plus the date for an empty pool. I did not execute the browser; the empty branch is in the code and the existing empty-state visual is the screen's own (no new UI is added by F3).

### Findings

**P0**: none.

**P1**: none.

**P2-1. `collection_ids_for_word` still reads the raw seed** (`vocabulary_library.py:444`, index at line 316). It has no production caller at aca8dd6f (only `tests/test_vocabulary_library.py`), so there is no leak today, but it is a learner-shaped accessor ("curated collection ids containing the word") that would report seed collection ids for a word the learner cannot otherwise see. Required: make it use the learner catalog (a `_LEARNER_WORD_INDEX`), or rename and document it as authoring-only, and update its test. It is the only remaining raw accessor with a learner-shaped name.

**P2-2. The positive path for the production defaults is untested.** The new test `test_a_published_static_collection_would_still_reach_learners` monkeypatches `_LEARNER_CATALOG_BY_ID` and `_LEARNER_ENTRY_INDEX` and checks `vocabulary_entry_for` and `published_vocabulary_entries`, but never calls `daily_feed_candidates` or the Feed route with a published static collection. The rewritten `tests/test_vocabulary_feed.py` passes `candidate_pool=all_vocabulary_entries(...)` explicitly, so the selector's default argument is exercised only for the empty case. Required: add (a) a Feed default-pool test with a published static collection (monkeypatched as above) asserting its words are selectable, (b) a test that an `internal` extension of a published parent is folded and reaches `vocabulary_entry_for`, (c) a negative test that an `internal` extension whose parent is not published stays hidden, (d) a test that a `seed`-status extension of a published parent stays hidden (the current data shape).

**P2-3. The saved-word test is a deliberate behaviour reversal and loses positive coverage.** `test_saved_catalog_word_reuses_static_card_content_without_new_persistence` (asserted level, framework, phonetic, examples from the seed) became `test_saved_word_is_not_enriched_from_an_unpublished_static_seed`. The reversal is correct under F3 and the new assertions (`not framework`, `not phonetic`, `examples in (None, [])`) are not weaker than needed to state the new rule. But nothing now proves that a saved word that exists in a **published persisted** collection still gets level, phonetic and examples on `/api/library/vocabulary`; `test_the_word_page_fallback...` only checks the term. Required: add the positive companion (saved word present in a published persisted set keeps its enrichment).

**P2-4. Rewritten Feed route tests: acceptable, with a note.** The new autouse fixture in `tests/test_vocabulary_feed_route.py` imports one published English and one published Chinese collection and finalizes them with a full admission. That is the real publication path, not a mock of the gate, and the assertions were not loosened. The one comment edit ("No published entry carries level C2") matches the fixture. Nothing was weakened to pass. The fixture imports words that look like the old seed ("client", "你好"), so a reader could think they are still the seed; consider distinct names to avoid confusion with `SEED_EN`/`SEED_ZH` in `test_vocabulary_seed_visibility.py`.

**P2-5. Test doubles in `test_vocabulary_seed_visibility.py` swap module globals** (`_LEARNER_CATALOG_BY_ID`, `_LEARNER_ENTRY_INDEX`) through `monkeypatch`. That is fine (restored per test) but the test depends on the private name `_build_entry_index` and `_build_learner_catalog`. Prefer a small public builder or a fixture in `vocabulary_library` so a rename does not silently disable the test. Low priority.

**P2-6. The persisted Feed pool is still capped at 5,000 entries** (`app.py` `list_entries_for_language(..., limit=5000)`), now the only source of Feed content. Pre-existing, but it was previously masked by the 70-word seed. Note for the General catalogue and any large import.

### Learner and product effect (for the human)

1. **With no published collection the Feed is empty, in English and in Chinese.** Today that is every deployment whose only content is the seed JSON. The learner sees the Feed screen's existing empty state, not an error. Before F3 the Feed showed up to ~70 seed words (35 TOEIC/common words, 33 HSK1 words and so on), most of which were not in any published collection.
2. **A learner who saved a word that exists only in the seed loses its enrichment** (level, framework, phonetics, examples) on the saved list and the word page. The word itself, the learner's own state, review scheduling and the audio endpoint are untouched. A word that is also in a published persisted collection keeps everything, because `_catalog_entry_for` asks the persisted repository first.
3. **Consistency with the decisions.** D-178 item 3 ("moderation stays per set: pending_review -> approved -> published on the collection") and the collection lifecycle say a learner reaches content through a published collection. The Library list and detail routes already enforced that for the seed; the Feed and word-page fallback were the two paths that did not. F3 removes the inconsistency. It also matches the module's own docstring ("a 35-word seed must not be presented as a finished `3000 Common Words` pack"). I found no decision that promises the seed as a learner fallback. D-111 (auto-publish when rights are cleared and the set is complete) is the route by which real content becomes visible, and is unchanged.
4. **Product impact in one sentence.** F3 is correct, but its visible effect is that a fresh or sandbox deployment shows an empty Feed until at least one vocabulary collection is published; if the human wants the Feed to show something on day one, the answer is to publish a reviewed collection (or the planned General catalogue), not to restore the raw seed.

### Conditions for F3

- **C2 (human acknowledgement, required before merge).** The human confirms that an empty Feed on deployments with no published vocabulary collection, and the loss of seed enrichment on saved seed-only words, is accepted. It is the intended consequence of the lifecycle decisions, but it is a visible learner-facing change and the agents must not decide it alone.
- **C3 (code).** Resolve P2-1 (`collection_ids_for_word`) in this branch, since it is the same defect class and a two-line change. If the human prefers to defer, record it in `docs/project/CURRENT_HANDOFF.md` P1/P2 list.
- **C4 (tests).** Add the positive-path tests in P2-2 and P2-3. They are small and they protect the "no over-hiding" requirement, which is currently proven only through monkeypatched module state.

---

## Overlap with the General catalogue (D-188 proposed, review on `claude/vocab-general-catalogue`)

- **Scope fit.** The General design derives from persisted, admission-valid published collections only (its P1-4). F3 does not change that: it removes the raw static path and leaves the persisted path alone. The General review states F3 is unaffected and need not wait for it; I confirm that. After F3 there is also no case where the Feed, the word page and General disagree because of the seed, which was the third inconsistency named in that review (P1-4, third bullet).
- **F1 is the dependency that matters.** General's gate is "published AND `_publication_admission` passes". F1 makes the second half true for every set that becomes published after it. Without F1, a set published through `/status` is visible as a collection but absent from General. With F1, new sets are consistent; only legacy rows (C1) can still diverge. That makes C1 more valuable once General ships.
- **Merge conflicts.** Both F1 and the General branch edit `writing_coach/persistence/vocabulary_repository.py` (F1 changes four lines at ~1096 in `set_collection_status`; General adds ~200 lines elsewhere). I expect a trivial or no textual conflict. The General branch's tests call `set_collection_status(..., "unpublished", ...)` only, so F1 does not break them. F1's and F3's tests are independent of General's.
- **P2-2 (F1 re-publish reusing an old admission) interacts with General P1-5**: withdrawal is by set. If the human wants withdrawal to be a strong lever, the superseded-admission option in F1 P2-2 should be decided together with General's H3 kill switch.
- **Static published collections later.** If a static collection is ever marked `published`, F3 lets it reach learners (Feed, word page) but General, being persisted-only, will not list it. That is consistent with General P1-4, but should be stated in D-188 (the General review already requires it).

---

## Summary of required actions

| Id | Branch | Kind | Action |
| --- | --- | --- | --- |
| C1 | F1 | Operational condition | Read-only check of already-published sets lacking a valid admission, per deployment, before merge to a long-lived database; human decides per set |
| C2 | F3 | Human acknowledgement | Accept the empty Feed and lost seed enrichment |
| C3 | F3 | Code | `collection_ids_for_word` must not read the raw seed (P2-1) |
| C4 | F3 | Tests | Positive-path tests for the published default pool, internal-extension folding, and enrichment of a persisted saved word (P2-2, P2-3) |
| P2 | F1 | Follow-ups | Transition table in `finalize_collection_publication`, superseded admission on withdrawal, audit of refusals, extra negative tests (P2-1 to P2-5) |

Reviewer: Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer. Commits reviewed: F1 `44b6109b`, F3 `aca8dd6f`, both on origin/main `172ae216`. Not product approval and not activation authorization.
