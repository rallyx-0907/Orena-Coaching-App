# Proposal: Admin Grammar (import, review, publish) in the existing Admin

Status: **PROPOSED, for the human's layout approval. No Admin UI code is written until it is approved.**
2026-10-08, `codex/work` 125fd013. Backend: Grammar Store (`writing_coach/grammar_admin_api.py`, 17 routes under
`/api/admin/grammar/*`; PR #106 is the canonical backend/contract). Learner flow done first (Library, Concept, quiz
completion on `/api/grammar/v1/*`).

## Why a proposal

`Orena-Admin.dc.html` draws no Grammar screen. Its frames are A1 Overview, the generic `Admin list`, A8 Content,
A15-A17 Reading (overview, queue, review detail), A21 Add reading content, Comprehension set review and No access. The
Grammar workflow must therefore be composed from those patterns, as built and accepted (REVIEWABLE 2026-10-03) in
`screens/admin/`: the Imports hub and Content packs page (`imports-pages.js` `hubPage`, `packPage`), the Reading
queue and Reading review detail (`reading-pages.js` `queuePage`, `articlePage`), with the shared Admin blocks
(`blocks.js`: `pageHead`, `tabs`, `rowList`, `formBlock`, `banner`, `kv`, `metrics`, `pill`, `stateBlock`). No new
visual system, no dashboard, no new component unless listed below.

## Places (4) and where each pattern comes from

| # | Place | Route | Composed from | Content |
| --- | --- | --- | --- | --- |
| G1 | Imports hub row "Grammar packages" | `#/admin/imports` | `hubPage` rows (same row as Books / Media / Vocabulary / Content packs) | title, meta "Grammar Lab export packages", recent count pill, failed pill |
| G2 | Import a grammar package | `#/admin/imports/grammar` | Content packs `packPage` (file field, Check, Import, "What the import would do" plan list, result list) + A21's Rights block | file (.zip); **Check** = `POST imports/validate` -> summary `kv`: language, set version, point count, package hash (short, copyable), validator verdict, problems; plan `rowList`: new / changed / unchanged / refused per point (collapsed after 20, "Show all"); **Rights** `formBlock`: basis (Orena original / Licensed / Other, segmented) + attestation (textarea, required); **Import** -> receipt `metrics`: imported, unchanged, rejected, refused; "Review N imported" link to G3 |
| G3 | Grammar review queue | `#/admin/grammar` (tabs) | Reading queue `queuePage`: `tabs` with counts, search field, level filter, `rowList` | tabs: To review (imported) · Accepted · Published · Unpublished/Archived; language segmented EN / ZH; row: native title (+ pinyin for zh), level, function, version, rights pill (`rightsPill` tones), batch date; batch bar on To review / Accepted: **Accept all shown** (reason required) and **Publish accepted** (attestation checkbox, all-or-nothing, `POST /publish`) |
| G4 | Grammar point review detail | `#/admin/grammar/point/:id` | Reading review detail `articlePage`: head with status pills, `banner` for blockers, `kv`, rights editor, action bar | learner preview: the Concept view rendered read-only from the version (`GET versions/:id/preview`, same `conceptView` renderer the learner sees, so review = what learners get); versions list (vN, review status, rights status, batch, superseded); R5 aliases from the point; actions: Accept / Reject (reason), Rights (cleared / blocked, reason), Publish (attestation, the hard rights gate as A17's Publish), Unpublish, Archive, Restore |

Entry: Content home (A8) gains a "Grammar" tile beside Reading / Books / Media / Vocabulary that opens G3; the Imports
hub row opens G2. Both are existing tile/row components.

Phone (Admin's own phone pattern, as the accepted Admin areas): single column; tabs become the phone chips; the plan
and queue rows stack; the action bar is sticky at the bottom; the Concept preview keeps the learner phone layout.

States, all from existing blocks: loading skeleton, load error (`loadFailedBlock`), empty tab (`stateBlock`), refused
package (banner listing problem codes, nothing written), already-imported package (banner, link to the batch),
progress while importing (the global progress tray, as Reading imports), 409 rights/acceptance refusals as banners.

## Decisions for the human

| Id | Question | Options | Recommendation |
| --- | --- | --- | --- |
| HG-1 | Where Grammar lives | (a) Imports row + Content tile (above); (b) Imports only; (c) Content only | (a): import is an Imports act, review/publish is Content, as Reading |
| HG-2 | Review granularity for 595 points | (a) per point only; (b) "Accept all shown" with one reason + per-point override in G4 (above); (c) accept at import | (b): the packages are approved upstream; per-point review stays available |
| HG-3 | Rights | (a) one attestation per package at import, per-version override in G4 (as the API); (b) per point | (a) |
| HG-4 | Preview | (a) learner Concept renderer, read-only (above); (b) raw JSON / field table | (a): reviewers see exactly what learners see |
| HG-5 | Coverage and R5 map views (`/coverage`, `/r5-map`) | (a) not in the first slice; (b) a third tab in G3 | (a) |
| HG-6 | Publish scope | (a) bulk per language, all-or-nothing (API); (b) per point only | (a) plus per point in G4 |

Copy in EN / VI / ZH through `screens/admin/copy*.js`; codes and hashes stay as data. Verification when built:
1920x1080 and 390x844, light/dark, EN/VI/ZH, refused / already-imported / partial states, and the learner Library
showing a point published from G4.
