# Architecture review: Reading provenance (P0-A, D-189 / D-190)

Reviewer: Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer
Commit reviewed: b94f4129 (branch claude/reading-provenance) against origin/main (948fd871)
Method: static read of the diff and the surrounding code at that commit. No tests run, no Docker.

## Verdict: APPROVED WITH CONDITIONS
The design is sound: one pure function, no schema change, one gate applied at three layers. Two P1 items must be closed (or consciously accepted by the human) before a real corpus is published. No P0.

## 1. Gate completeness
Every path that writes ReadingArticle.status = published goes through one of two places:
- `reading_content_repository.py:777` (create_candidate, automatic admission) is guarded by `automatic_admission` -> `provenance_blockers` (`reading_admission.py:57-61`).
- `reading_content_repository.py:1100-1105` (`set_status`) raises ProvenanceRefused. This covers the admin route (also pre-checked in `publication_blockers`, reading_admin_api.py:218), republish after unpublish (current status != published), content-pack import (it goes through engine submit -> admission; `exported_status` is advice only, content_packs.py:13), and scripts (`agent_e2e/harness.py:206` calls set_status, so it is gated too).
- No bulk route, no direct `update(ReadingArticle)` setting status, no raw-SQL publish found. No bypass.
- Residual (P2): `set_status` reads `get_article` outside the write transaction (check-then-write).
- Residual (P2): the gate runs only on the transition. A rights answer recorded later on a published article does not unpublish it. This matches the "no retroactive unpublishing" decision; the checker script covers it and should be run on a schedule.

## 2. Gate correctness
- "Required" is derived only from the effective rights (`attribution_state`), not hardcoded per source. Good.
- `unknown`: `missing_fields` returns [], so an unanswered question publishes via the admin route (advice `attribution_unknown`, reading_admin_api.py:231). Automatic admission still holds it (`attribution_unknown`, reading_admission.py:55). Pre-existing and intentionally kept, but it is the largest hole against D-189: a human can publish a real corpus with attribution unanswered and no credit. See P1-1.
- Stricter admission (author alone no longer suffices) is correct against D-189 and does not contradict D-111 (admission is deterministic and only escalates to review). Not a weakening; the old rule accepted an author with no publisher or licence.
- Who stops auto-publishing: any source whose snapshot has attribution_required true and (a) no item canonical_url (pasted or uploaded text), or (b) no license_note. `ReadingSource.attribution_required` defaults to True (models.py:1016), so an auto-admitting source created with an empty licence now goes to review. I could not enumerate live sources (no DB access); run the checker and count held `attribution_missing` items on staging before relying on throughput.
- Admission reads the snapshot rights while the admin route and set_status read the effective (overlaid) rights. Consistent enough since admission fires at ingest, but "the same gate" is slightly overstated.

## 3. Data and privacy
- Payload keys: publisher, url, author, license{name,url}, attribution_required, text. No `rights_effective`, no reviewer actor, no admin notes.
- Leak risk (P1-2): `license.name` and `text` come from `license_note`, admin free text up to 2000 chars (reading_admin_api.py:307/354). It was already shown in Settings > Licences, but is now on every list item and detail and in cached responses. Nothing stops an internal note being written there.
- content_revision: bumped on a rights answer for a published article (~line 977) and on publish. Not bumped when the source name changes (a rename changes the publisher of every cached article). P2.
- Query count: list = list query + one set-wise provenance join + one `_rights_decisions` query, constant per page, no N+1. The test's "3" counts only statements touching reading_articles; the decisions read is on another table, so the real figure is 4, still constant.
- Detail still emits both `attribution` and `provenance` with overlapping data; plan to deprecate `attribution`.

## 4. Tests
- Admission test: author-only expectation replaced by a stronger set (author alone held; full credit published; blank source name held). Not weakened.
- Payload-shape sets gained "provenance": correct.
- `test_an_adapted_article_also_needs_the_right_to_adapt` now uses `attribution_required: False`. Needed so the test isolates can_adapt; acceptable, but add a case where can_adapt and credit are both missing and both blockers are returned.
- test_content_packs.py now supplies a URL: legitimate.
- Query-count test loosened from == 2 to == 3 with a brittle string filter (`"original_author" not in s`): justified, but fragile.
- Missing negative tests (P2): unknown attribution stays publishable; explicit license_url vs note-embedded URL; licence note that is only a URL; republish after unpublish refused when credit was removed meanwhile; deny-list assertion that the learner payload has no rights_effective/actor/notes keys; a rights answer on an unpublished article does not bump the revision.

## 5. UI
- Changes are limited to existing source-line elements: Discover card `author`, Content Detail `source`, Reader toolbar `author`, plus a tiny helper `static/orena/product/provenance.js`. Nothing invented (CLAUDE.md rule 4).
- Fallback: publisher, else older `attribution.author`, else empty (the element is already optional). Sane.
- Side effect (P2): `relatednessScore` compares `current.source` (now a publisher) with `candidate.author || publisherOf(candidate)`; the author takes precedence on the candidate, so the match may no longer fire for same-publisher articles. Verify intent.
- Licence credit only in Settings > Licences: opinion for the human. Acceptable as an interim for staging or a closed corpus, since the publisher is visible where the learner reads and the licence plus link is reachable. NOT sufficient for CC BY / CC BY-SA content in a public launch: those licences expect the credit and licence reference reasonably attached to the work. Recommendation: accept as interim; take a human design decision (UI_BACKEND_GAPS entry exists) to add an original-link and licence line (Reader "..." menu or Content Detail sheet) before public corpus publication. The backend already supplies everything needed.

## 6. Global Voices
Putting "Peace News" in the author field is a workaround, not acceptable as the durable model. The text "Originally published by Global Voices (by Peace News)" asserts Peace News is the author when it is the original publisher of a republished text; it conflates a person with an organisation.

Recommended join with PR #157 (`original_publisher`, `original_url` in extraction metadata):
1. Extraction metadata is the source of truth. `build_provenance` takes optional `original_publisher` / `original_url` from the item metadata and renders "Originally published by Peace News via Global Voices, CC BY 3.0."; `publisher` stays the republisher, with `original_publisher` and `original_url` as additional fields.
2. `author` is for the human author only. Drop the "(by Peace News)" convention once #157 lands; fix existing items by reprocess, not by editing snapshots (immutable).
3. Gate: when metadata marks an item as a republication under a licence that requires crediting the original, `provenance_blockers` also requires `original_publisher`. Do this in one change after #157 merges so the gate has a single schema.
4. Order: merge #157 first (data), then rebase this branch onto it and add the fields; avoid two spellings of the same fact.

## Findings
### P0
None.

### P1
- P1-1 `reading_admin_api.py:231`, `reading_provenance.py` `missing_fields`: unknown attribution publishes by admin with no credit. Required: record an explicit decision (D-18X "Review needed" asks it). Recommend refusing `unknown` for a real corpus, and at minimum always requiring publisher and url, which are always known.
- P1-2 `reading_provenance.py` `split_license`; `reading_content_repository.py` ~1432: raw admin free-text `license_note` goes to every learner and into caches. Required: restrict the learner licence to a recognised name/URL or a dedicated field, cap its length, and add a leak test.

### P2
- P2-1 `reading_content_repository.py:1100`: check-then-write; do the check inside the write transaction.
- P2-2 `reading_content_repository.py` ~977: bump content_revision of a source's published articles when the source name changes.
- P2-3 `scripts/check_published_reading_provenance.py`: schedule it in ops; confirm exit code behaviour.
- P2-4 `tests/test_reading_content_repository.py` query-count filter is brittle; decisions query is uncounted.
- P2-5 `static/orena/screens/content/model.js` relatednessScore precedence.
- P2-6 Missing negative tests (section 4), including the combined can_adapt + credit blocker.
- P2-7 Global Voices author-field convention (section 6).
- P2-8 Licence line and original link absent from the reading surface; human design decision before public launch.
- P2-9 D-18X remains PROPOSED: record this reviewer line and commit in the decision entry, and flip to ACCEPTED once P1s close.

Reviewer: Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer. Commit reviewed: b94f4129.

## Change after review (2026-10-14)

The human replaced the publication policy this review approved. The hard gate in `ReadingContentRepository.set_status` and the
409-only admin route are gone: rights and attribution are now warnings that an administrator may publish over only with an
explicit `acknowledge_warnings` flag and a non-empty reason, recorded in the review event and audit record. The automatic
admission (D-111) still refuses unclear rights and attribution; the checker script now reports whether a flagged published row
carries a recorded override. P1-1 is closed by that human decision. **Re-review is required** of the amended behaviour before
D-190 (numbered D-18X at the time) is ACCEPTED; the verdict above applies to commit b94f4129 only.


## Re-review of the amended policy (2026-10-14)

Reviewer: Delegated Architecture Reviewer, model Claude Opus 5.5, independent of the implementer.
Commit reviewed: change 604cfbc7..b922f433, plus merge 94e7374f (HEAD of claude/reading-provenance). Date: 2026-10-14.
Method: read-only (git diff/show, source read); no Docker, no test execution. The implementer had no green full suite locally.

### Verdict: APPROVED WITH CONDITIONS

The change implements the human policy. The conditions are CI-only: the full suite must be green on PR #158 (at review time `gh pr checks 158` and `statusCheckRollup` report no checks at all for head 94e7374f, so there is no CI evidence yet), and the P2 items below are recorded as follow-ups. No P0 or P1.

### What was verified

1. Repository and paths. `ReadingContentRepository.set_status` (reading_content_repository.py ~1079-1140) has no rights or attribution refusal; `ProvenanceRefused` is deleted with no remaining reference in writing_coach, scripts or tests. The only code path that moves a Reading article to `published` outside creation is `POST /articles/{id}/status` (reading_admin_api.py ~751-820). The other POST routes (article edit, rights, targets, comprehension sets, jobs, sources) do not change article status; comprehension-set routes require an already published article. `unpublish -> republish` goes through the same route and re-computes the warnings from the current rights, so a credit removed in the meantime asks for the override again (tested). The server, not the client, enforces it: any warning without `acknowledge_warnings` gives 409 `reading_rights_not_cleared`, with the flag but a blank reason gives 422 `reading_reason_required`; the warnings list is computed server-side, so a client cannot suppress it. No bulk or set-level publish exists. The only non-route caller is scripts/agent_e2e/harness.py:206 (direct `set_status`, test harness) which publishes with no recorded override and is correctly reported by the checker as unrecorded. Nothing previously enforced was bypassed other than what the policy removed.
2. Audit. The review event (`published_over_warnings`, `warnings`, `reason`, `actor`) is written in the same transaction as the status update (`set_status`, `engine.begin()`), so the override and the state change are atomic. The admin audit record (`admin.reading_article_published`, with `warnings`, `acknowledged_warnings`, reason) follows in a separate write (existing pattern). The checker's "overridden" determination reads the latest `published` review event per article (ordered by created_at, id; last wins) and requires `published_over_warnings` and a non-blank reason; an older override cannot mask a later plain publish, and legacy rows with no event are "NO RECORDED OVERRIDE". Sound.
3. Automatic admission. reading_admission.py still refuses `rights_not_cleared`, `attribution_unknown` and `attribution_missing`; the only caller of the admission path is `create_article(automatic_admission=True)` in the engine, which is unchanged; a regression test covers all three reasons. The worker/poller cannot publish otherwise.
4. Tests. The `attribution_required: false` fixture changes are necessary and honest: those tests exercise other behaviour (automation, queue, E2E) and need a no-warning article now that an unanswered attribution question requires an override. The rewritten tests assert more, not less (409 body, `override_field`, 422 on blank reason, event contents, audit record, parametrised rights_not_cleared / rights_unknown / attribution_unknown, checker overridden vs legacy). The admin_areas node gate was changed only where the old assertion encoded the hard gate (disabled Publish); the replacement asserts the button is enabled and the warning text is shown. No validator was weakened beyond the policy.
5. UI. Publish opens the confirm dialog with `reason.required: true`; the confirm button is disabled until the reason is non-blank (host.js `ready`), and the server rechecks. If the client's list is incomplete (for example an incomplete credit) the 409 list is confirmed and the request is resent. EN, VI and ZH have the new keys (`rdWarn_provenance_missing`, `rdOverrideReasonHint`) and rewritten advice, banner, toast and error copy. No Reading copy still says publishing is refused for rights (the remaining "cannot be published" strings are the Grammar restriction feature, unrelated).
6. DECISION_LOG. The decision entry (D-18X at review time, D-190 at merge) states the policy accurately (manual publish always possible, warnings need `acknowledge_warnings` plus reason, 409/422 codes, repository never refuses, no automatic publication while unclear, hard gates reserved for integrity faults), says it amends D-105, and the checker semantics match the code. The merge 94e7374f brought in only main-side files (billing, source cleanup, extraction); it touched none of the files changed by this PR and shows no conflict-resolution damage.

### Findings

- P2-1 (reading_admin_api.py ~772-795): warnings are computed from `current` read before `set_status` writes; a rights change between the two would record the older warnings. Same check-then-write as the earlier P2-1; low impact since both steps are admin acts. Fold into the same follow-up.
- P2-2 (reading_content_repository.py `set_status`): the repository accepts `warnings` with a blank `reason` (route enforces the reason; direct callers do not). Consistent with "never a hard block in the repository", and the checker treats a blank reason as unrecorded; note it as a deliberate division of responsibility.
- P2-3 (static/orena/screens/admin/reading-pages.js:7): header comment still says copyright is a hard gate; update the comment.
- P2-4 (scripts/reading_canonical_e2e.py:219-221): label still says "refused (D-105)"; behaviour (409 then publish after answers) remains valid, but wording is stale.
- P2-5: the admin audit write is outside the review-event transaction, so a crash between them leaves the (authoritative) review event without the admin audit row. Pre-existing pattern; the checker uses the review event.
- P2-6: no CI evidence yet; the node gate `test_orena_screen_admin_areas.mjs` and the Python suite have not been run by anyone for this commit.

### Conditions for ACCEPTED

1. CI aggregate `test` green on PR #158 for head 94e7374f (not yet reported).
2. Record P2-1 to P2-5 as follow-ups; D-190 may flip from PROPOSED to ACCEPTED when 1 is met.

Reviewer: Delegated Architecture Reviewer, Claude Opus 5.5. Commit reviewed: 94e7374f (change b922f433).
