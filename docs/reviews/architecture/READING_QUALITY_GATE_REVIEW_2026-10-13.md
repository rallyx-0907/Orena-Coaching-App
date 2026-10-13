# Architecture review: Reading quality admission gate (P0-E, D-18X PROPOSED)

Reviewer: Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer
Commit reviewed: ae8b96db (claude/reading-quality-gate) against origin/claude/reading-source-cleanup (PR #157)
Method: static read via `git show` / `git diff` only. No checkout, no tests run, no Docker.

## Verdict: APPROVED WITH CONDITIONS
The two-layer split (facts at extraction, verdict from stable codes in one file) is a good design and the soft/hard distinction is right. Conditions: close P1-1 (enforce the hard gate where the provenance gate lives) and P1-2 (the media and bot-challenge heuristics produce hard false positives on legitimate articles).

## 1. Every path to published
- Only two writers set status to published: `create_article` with automatic admission and `ReadingContentRepository.set_status`.
- Automatic admission (D-111): the engine adds the quality codes to `analysis.quality_issues` (`reading_content_engine.py:~382`), and `automatic_admission` does `reasons.extend(issues)`, so any code, hard or soft, holds the item. Content packs go through engine submit and admission, so they are covered, but a pack item has no `page_facts`, so only body-derived codes (`empty_body`, listing heuristic, `body_below_minimum`, `generic_title`) can fire for them.
- Admin route: `publication_blockers` -> 409 `reading_quality_not_cleared` (or `reading_rights_not_cleared` when mixed). Covered.
- P1-1 (bypass): the hard gate is in the route only. `ReadingContentRepository.set_status` (repository, line ~1066) does not check `hard_issues`, unlike the P0-A provenance gate, which was deliberately placed there so "a path that skips the route is still stopped". Scripts that call the repository directly (`scripts/agent_e2e/harness.py:206`) and any future caller publish a media page unchecked. Required: enforce `hard_issues` in `set_status` too (raise a typed refusal like `ProvenanceRefused`, with an explicit `quality_override` parameter carrying the reason and actor), and have the route only translate it.
- Merge with P0-A: both add to `publication_blockers`. P0-A's `provenance_blockers` have no `gate` key; this branch's have `gate: "quality"`. The collision is textual, not logical. After merging: (a) quality override filters only `gate == "quality"`, so provenance blockers survive an override (correct); (b) the 409 choice `all(gate == "quality")` sends mixed cases to `reading_rights_not_cleared` (correct); (c) the second message text in the route (P0-A adds `provenance_missing` text to the same `raise`) will conflict at merge: resolve by hand and add a test that an override with an incomplete credit still returns 409. P0-A's repository gate also runs after the route's, so provenance cannot be overridden. Add this combined test (P1-3).
- Republish after unpublish: goes through the same route and checks the stored `quality_issues`, so a republish needs the override again. Good.

## 2. Override safety
- Who: any admin who can call the status route (`_admin(request)`, same-origin). No separate permission, no second person. For the first real corpus this is acceptable (same as every other admin act), but it makes the override as easy as a publish.
- Audit: `admin.reading_article_quality_override` records the codes and the reason, written before the publish. Reason is required (422). Gap (P2): the audit is written even if the subsequent publish then fails on rights, and the article's own event history (`_record_event` in `set_status`) does not carry the override, so a reader of the article's history cannot see that it was published over a hard failure. Add `quality_override` and codes to the status event's changes, as `published_over_warnings` does for warnings.
- Never clears rights: correct, and tested (`test_a_quality_override_never_clears_the_rights_gate`), because only blockers with `gate == "quality"` are removed. Same for provenance after the P0-A merge (see above), but needs the explicit test.
- The flag is ignored for statuses other than published and when no quality blocker exists; fine.

## 3. Thresholds and false positives
- P1-2a `media_page`: `og:video`/player markup plus fewer than 400 Hanzi is hard. A legitimate Chinese news item with an embedded video and a 300-Hanzi body is blocked, and many short brief-style ZH articles are around that length. The trial's non-articles were 216-245 Hanzi, the shortest genuine one 983, so 400 leaves a large margin that the data does not need; consider 300, or make `media_page` soft above the lower bound. English 60 words is tight and fine.
- P1-2b `bot_challenge`: a title/h1 of 8 or fewer units matching a challenge phrase is hard. A real headline such as "Just a moment of silence for ..." (5 units), "Access denied to ..." or "Attention required" is hard-blocked, and `just a moment` and `access denied` are common phrases. Require the page to also be short (`page_units` small) for the title branch, as the visible-text branch already does.
- `index_page`: `_looks_like_listing` needs 8 or more lines, 70% short unpunctuated lines and 3 dated lines, or 70% lines opening with a date. Timelines, chronologies, obituaries with dated entries, and poems/lyrics with years can match; hard, so it needs an override. Medium risk; EN/ZH both. Prefer soft unless the body is also short in units per line on average, or add a prose-sentence exemption.
- `index_title` splits on `:`, `-`, `|`, `/`, so "Archive" or "All stories" as any one segment of a title triggers hard (for example "Latest news | BBC" is correct, "Opinion: all stories ..." is not matched, since a segment must match entirely). Acceptable.
- `special_page`: `/special:` path only; narrow and safe.
- Bot-challenge phrases in the first 600 characters of visible text for pages under 300 units: sensible; Chinese phrases are specific. Slightly too narrow for a Cloudflare page in another language, but the language set is EN/ZH.
- Soft: `body_below_minimum` 80 EN words / 120 Hanzi only holds review. Fine. `generic_title`: "news"/"latest" as full titles only. Fine.
- Counting: `units` counts each CJK char once and words otherwise, deterministic.

## 4. Determinism and storage
- Codes are computed once at ingest and stored in `analysis.quality_issues`; the route reads the stored list. Facts are stored in `analysis.extraction.page_facts`, so a reviewer can see why. Version constant `QUALITY_VERSION` exists but is not stored with the result (P2): store it next to the issues so a threshold change can be told from a stale verdict.
- Consequences: changing a threshold does not change existing articles; and because the gate trusts stored codes, an article whose body is edited or re-adapted later keeps the old verdict (P2: recompute `empty_body`/listing/size codes on body change, or at least at publish for the codes that need only the body).
- Articles that predate `page_facts` have no facts: no `media_page`, `bot_challenge`, `special_page` or title index flags are ever raised for them, so already-stored candidates sit at the previous behaviour and can be published. Required (P1-4 / condition): a read-only audit script like the provenance checker that recomputes `quality_flags` over unpublished and published articles (it cannot get raw-page facts, but it can compute body-only codes) and lists them; do not backfill silently. State this limitation in the D-18X entry.
- `item.metadata["extraction"]["page_facts"]` is only produced for URL extraction. Uploaded or pasted text never gets the hard fact codes, only body-derived ones; document this.

## 5. Tests
- Single commit, so the order of tests against code cannot be established; the tests are in the same commit as the implementation. I could not verify test-first. No existing test was weakened: the diff to existing tests only adds an `analysis` parameter to the `_article` helper (default unchanged) and new tests.
- Present: each hard code blocked (parametrised), soft publishable, clean publishable, override needs reason and is audited, override never clears rights, engine-level media page held, medium confidence flagged.
- `test_a_medium_confidence_page_is_flagged_and_held` is conditional (`if confidence == "medium"`): it can pass vacuously; make the fixture deterministic (P2).
- The route tests inject `quality_issues` directly, which tests the gate but not the production of the codes; the unit tests in `test_reading_page_quality.py` cover production with fixtures (VOA ZH video, etc.).
- Missing negatives (P2 unless noted):
  1. Short legitimate EN article (about 100 words) and short ZH article (about 150 Hanzi) are not hard-flagged.
  2. ZH article of 300 Hanzi with an embedded video is not `media_page` (this would currently FAIL: P1-2a).
  3. Headline "Just a moment of silence ..." is not `bot_challenge` (would currently fail: P1-2b).
  4. Dated timeline article and poem are not `index_page`.
  5. Repository-level `set_status` refusal of a hard code (P1-1) and the script path.
  6. Override plus incomplete credit still 409 (after the P0-A merge).
  7. Override with `status != published` is ignored; override when no hard code is present does not write an audit row.
  8. Legacy article without `page_facts` publishes (documents the known limitation).
  9. Content-pack imported item with a hard body code is held.
- UI/copy: EN/VI/ZH copy and the gaps entry are present in `copy-reading.js` and `UI_BACKEND_GAPS.md`; not reviewed for design fidelity (out of scope).

## Findings
### P0
None.

### P1
- P1-1 `reading_content_repository.py:~1066` (`set_status`) and `reading_admin_api.py:~776`: the hard gate lives only in the route; move the check into the repository transition with an explicit override parameter, consistent with P0-A.
- P1-2 `reading_page_quality.py` `MEDIA_PAGE_MAX_UNITS` (zh 400) and the title branch of `bot_challenge` in `page_facts`: hard false positives on legitimate short articles. Tighten (see section 3), and add the negatives.
- P1-3 Merge with P0-A: resolve the `raise orena_http_error(... reading_rights_not_cleared ...)` conflict by hand; add a combined override + provenance test.
- P1-4 Articles stored before `page_facts` bypass the fact-based codes: add a read-only audit/recompute script and state the limitation in D-18X before the real corpus is published.

### P2
- P2-1 Override is only in the audit log; add it to the article's own status event.
- P2-2 Store `QUALITY_VERSION` with the stored issues; recompute body-derived codes on body change.
- P2-3 `index_page` listing heuristic is hard; consider soft or stricter (timelines, poems).
- P2-4 Vacuous conditional in the medium-confidence engine test.
- P2-5 Override has no separate permission or second reviewer; consider a role if the corpus becomes public.
- P2-6 Document that pasted/uploaded text never gets fact-based codes.
- P2-7 D-18X stays PROPOSED until reviewer line and commit are recorded in the entry.

Reviewer: Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer. Commit reviewed: ae8b96db.
