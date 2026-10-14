# Architecture review: Reading quality admission gate (P0-E, D-191 PROPOSED)

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
- Articles that predate `page_facts` have no facts: no `media_page`, `bot_challenge`, `special_page` or title index flags are ever raised for them, so already-stored candidates sit at the previous behaviour and can be published. Required (P1-4 / condition): a read-only audit script like the provenance checker that recomputes `quality_flags` over unpublished and published articles (it cannot get raw-page facts, but it can compute body-only codes) and lists them; do not backfill silently. State this limitation in the D-191 entry.
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
- P1-4 Articles stored before `page_facts` bypass the fact-based codes: add a read-only audit/recompute script and state the limitation in D-191 before the real corpus is published.

### P2
- P2-1 Override is only in the audit log; add it to the article's own status event.
- P2-2 Store `QUALITY_VERSION` with the stored issues; recompute body-derived codes on body change.
- P2-3 `index_page` listing heuristic is hard; consider soft or stricter (timelines, poems).
- P2-4 Vacuous conditional in the medium-confidence engine test.
- P2-5 Override has no separate permission or second reviewer; consider a role if the corpus becomes public.
- P2-6 Document that pasted/uploaded text never gets fact-based codes.
- P2-7 D-191 stays PROPOSED until reviewer line and commit are recorded in the entry.

Reviewer: Delegated Architecture Reviewer, Claude Opus 5.5, independent of the implementer. Commit reviewed: ae8b96db.

# Review addendum: PR #159 reading quality gate, post-merge with D-190

Reviewer: Claude Opus 5.5, Delegated Architecture Reviewer (independent; did not write this code)
Date: 2026-10-14
Commits reviewed: 30ab15ff (merge of origin/main 9c947602 + D-191 renumber + composed UI), 3d5a948f (integration tests)
Prior review: READING_QUALITY_GATE_REVIEW_2026-10-13.md (6a8d0a74). Main's D-190 reviewed in READING_PROVENANCE_REVIEW_2026-10-13.md.
Method: read-only git diff/show. No tests were re-run by me. CI: `gh pr checks 159` at review time: changes pass, node-gates pass, python-gates / pytest / docker-build pending.

## Verdict: APPROVED WITH CONDITIONS (no P0, no P1; two P2s and one process condition)

## Findings by check

1. Conflict resolution. Diff 9c947602..30ab15ff for reading_admin_api.py and reading_content_repository.py is additive only. Nothing of main's is removed or altered:
   provenance_blockers, build_provenance, _provenance_map, published_missing_provenance, overlay/revision bump, `acknowledge_warnings`, `reading_rights_not_cleared`, the "published_over_warnings" event key, the `acknowledged_warnings` audit field and the D-189 docstring are all intact. The merge dropped the earlier pre-merge quality-in-publication_blockers design (`quality_override` mixed into blockers, "D-18X" tag) in favour of a separate quality_blockers(); the pre-merge gate behaviour is preserved (hard codes, reasoned override, repository QualityRefused, audit action name admin.reading_article_quality_override). Rights warning text and the 409 message are main's.
2. Route semantics (reading_admin_api.py set_article_status, ~L797-865). Correct:
   - Precedence: quality 409 when quality_open, else rights 409; both carry all blockers plus `override_fields`; `override_field` retained only when rights_open (main's contract).
   - Each flag only clears its own kind (`rights_open`/`quality_open` computed independently). `quality_override` does not clear rights; `acknowledge_warnings` does not clear quality.
   - One reason, 422 reading_reason_required when either kind exists and the reason is blank.
   - Audit: publish_refused records the full blocker list; quality_override audit is written only after all gates pass (no audit of an override that then fails on rights); the published audit carries warnings + acknowledged_warnings.
   - Repository never refuses for rights. QualityRefused is raised only from hard_issues(). The review event writes `warnings`/`published_over_warnings` and `quality_override`/`quality_codes`/`quality_version` in one dict inside one transaction: atomic.
   - A quality-only override leaves no `published_over_warnings`, so published_missing_provenance / the provenance checker report such an article as "NO RECORDED OVERRIDE". The property the human required holds.
3. Other paths. set_status("published") has exactly one production caller (the route); automatic admission (reading_admission.py L67) refuses any flagged item (D-111). scripts/agent_e2e/harness.py L206 calls the repository directly and would now raise QualityRefused on a hard-flagged article (fail closed; not a bypass). No other publish path found. Known and recorded limitations, not new: legacy articles without page_facts are not blocked (listed by check_reading_quality_backlog.py); a body edit does not recompute body-derived codes (recorded follow-up). A script that calls the repository with quality_override=True and a reason publishes an incomplete credit with no rights override: this is intended by the policy (repository never refuses rights) and is now pinned by a test and the checker.
4. Tests. 3d5a948f adds seven tests through the real route (call(setup.app, ...)) and the real repository/sqlite engine: quality-only does not pass rights (409, no quality audit), ack-only does not pass quality, neither flag lists both fields quality-first, both-no-reason 422, both-with-reason records both key sets and audits, repository-level quality override leaves no rights override and the real checker module flags it (exit 1, "NO RECORDED OVERRIDE"), auto-admission still refuses. These prove the required property. The diff vs main of existing tests shows no removed or loosened assertion; changes to existing rights tests in 30ab15ff are main's D-190 semantics (rights are warnings needing acknowledge_warnings), applied consistently.
5. UI and copy. reading.js builds one dialog from qualityBlockers + publicationBlockers + publicationAdvice, one reason, and sends the two flags separately via confirmationsFor (quality items by `gate:'quality'`). The 409 retry only re-asks for a confirmation not yet given; otherwise rethrows (no loop). EN/VI/ZH have rdIssue_* labels for all hard/soft codes and err_reading_quality_not_cleared; the quality copy says "does not look like an article ... confirm and give a reason to publish anyway". No copy says rights block publishing; rdPublishRisk/rdWarn_*/err_reading_rights_not_cleared are main's warning wording. UI_BACKEND_GAPS entry correctly records that the design draws no distinct quality control.
6. Decision log. D-189 and D-190 are byte-intact vs main (the DECISION_LOG diff is a pure append of D-191, no removed lines). D-191 is accurate on the independence, precedence, repository-as-last-gate and checker points. It is stale in one sentence (P2-1).
7. CI and the media failure. The PR diff touches no media-fallback code (no media path in the 9c947602..30ab15ff file list). tests/test_media_fallback_poll_claim.py::test_completed_transition_is_atomic_under_concurrency is a concurrency test that passed alone and failed only under xdist: plausibly a pre-existing flake/timing sensitivity, unrelated to this PR. Condition: confirm on the CI pytest job (pending now) and, if it fails there, reproduce on origin/main before attributing.

## Findings

P0: none.
P1: none.

P2-1 (docs): DECISION_LOG.md D-191 point 2 says "`reading_admin_api.publication_blockers` returns them as `{code, gate: "quality"}`". After the merge it is `quality_blockers()` (publication_blockers is rights-only). Fix the sentence. Also the stated status "PROPOSED" must be updated to record this addendum's reviewer, commits and outcome in Git when accepted (point 9 currently cites only the pre-merge review).
P2-2 (UI robustness): static/orena/screens/admin/reading.js, 409 retry branch: on the second dialog the flags sent come from `needed` computed on the full blocker list, so a quality-only retry after the first pass re-sends only the fields still missing instead of the union with `confirmed`. Today this is safe because the server lists all blockers in every 409, but `confirmed = needed` should be `{...confirmed OR needed}` to survive a future server that lists only the open kind.
P2-3 (carried from prior review, still open): a separate permission for quality_override and recomputing body-derived codes on body edit remain follow-ups.

## Conditions for acceptance
1. CI aggregate `test` job green on 3d5a948f (python-gates, pytest, docker-build pending at review time). Do not claim CI PASS before that.
2. If the media poll-claim test fails in CI, show it also fails on main before treating it as unrelated.
3. Apply P2-1 and record this review in D-191 (can be in the merge commit or a follow-up docs commit).

## Addendum 2026-10-14: tightened rules, re-review required

`claude/reading-quality-voa` (`QUALITY_VERSION` reading-quality/3) adds two hard rules to `reading_page_quality`:
`index_page` for a structureless page whose body is under 400 Hanzi / 150 words, and `media_page` for a player page with
no article or main element and a body under 600 Hanzi / 200 words (new extractor fact `no_semantic_container`). This
changes the publish lifecycle (more items refused without an override), so a fresh independent architecture review of
the PR is required before D-191 returns to ACCEPTED. Review points: false-positive risk of the size limits on short
genuine pages that lack an article element, and that stored items are not re-evaluated.

# Architecture review: PR #163, reading-quality/3

Reviewer: Claude Opus 5.5, Delegated Architecture Reviewer (independent of the implementer)
Commit reviewed: 8055ddbc (base main d55526a2)   Date: 2026-10-14
Method: read-only (git diff/show, file reads). Tests were not run by the reviewer.

## Verdict: APPROVED WITH CONDITIONS

Conditions
1. CI aggregate `test` green on 8055ddbc before merge. At review time `gh pr checks 163`: changes pass, node-gates pass,
   python-gates / pytest / docker-build pending. No CI PASS claim is made here.
2. Add an attribution README to `tests/fixtures/reading_quality/` (P1-1 below).
3. Record this review in D-191 (as done for the earlier review).

## Findings

P0: none.

P1-1 Fixture licensing/attribution. 7 files, 660 KB, third-party HTML.
- VOA (4 articles/pages) and NASA: US-government works, public domain. OK. VOA articles quote wire reports in
  passing (e.g. voa_zh_article_8210116.html:629 cites 路透社 reporting); those are attributed paraphrase in a VOA
  staff article, not wire text copied wholesale. Low risk.
- global_voices_article.html is CC BY 3.0 (the page itself carries the licence badge, line 172-173, and the footer
  licence text). CC BY requires attribution; the saved page keeps the byline and licence link inside the HTML, which
  arguably satisfies it, but there is no README and the directory does not state source URL, author, licence or
  retrieval date. Add `tests/fixtures/reading_quality/README.md` listing each file: source URL, publisher,
  licence (public domain US-gov / CC BY 3.0 with author + link), retrieval date, and why it is kept. Keep the
  files; shrinking is optional.
- Size: 660 KB of text in a repo with 2481 files in the base-to-HEAD stat (lane drift), so negligible. A shrink
  to the semantic skeleton would make tests less faithful to the real extractor input; not recommended.

P2-1 False-positive surface of `teasers_only` (reading_page_quality.py:~202). `no_article_structure` is true only
when `few_prose_paragraphs` (<2 prose paragraphs) AND (`no_article_or_main_element` OR `fallback_to_whole_page`)
(reading_article_extraction.py:698-700). So a genuine short single-paragraph item (a 300-Hanzi brief or a short
notice) on a div-only site now becomes a hard `index_page` where before it was clean. Mitigations exist: it needs
BOTH signals, any article/main/role=main wrapper exempts it, and hard codes are overridable with an audited reason.
Acceptable, but D-191 should say so explicitly ("short single-paragraph pages without an article element need an
override"). Consider a negative test for exactly that shape (one 300-Hanzi paragraph in a plain div) documenting the
accepted behaviour; the current negative tests only cover long bodies and real multi-paragraph articles.

P2-2 `no_semantic_container` is derived as `"no_article_or_main_element" in reasons`, which is appended only when
`method == "dominant_container" and not semantic` (extraction ~line 666). On `page_fallback` or other methods the fact
is False, so a player page that fell back to whole-page extraction is NOT caught by the new media rule (it may still be
caught by the index rule if few prose paragraphs). Name and docstring ("body came from a plain container") are slightly
broader than behaviour. Not a regression; note it in the comment, or derive from `not semantic` directly if the
intent is "no semantic ancestor" regardless of method.

P2-3 The 600/200 media limit versus the older 260/60: a short genuine article that embeds a video and sits in a
plain div (no article/main) with 260-600 Hanzi is now hard-blocked. Same override path; same note as P2-1.

## Answers to the review questions

1. Correctness. Logic is additive and monotone: new flags only add hard codes under conjunctions of structure facts
   and size; thresholds sit below the shortest genuine evidence (VOA 785 / 1390 Hanzi, NASA 589 / GV 1686 words).
   The fact is computed inside `extract_article`, the single extraction function; the only production caller found is
   `reading_source_import.py:335`, which serves URL, poller and job intake, and `ExtractedArticle.metadata()` stores
   `page_facts` for all of them (lines 308-309). Admission reads facts with `(extraction or {}).get("page_facts")` and
   `quality_flags` uses `facts.get(...)`, so a missing key (older rows, pasted text) is falsy and safe: no new flag,
   no exception. Pasted/legacy items without facts are simply unaffected.
2. EXTRACTOR_VERSION. Strictly the extraction output changed (a new key in page_facts), so a bump to article-extract/5
   would be the pure-provenance answer, and stored rows would then be distinguishable as having/lacking the fact.
   Not bumping is defensible: nothing in the repo compares `extractor_version` for caching or invalidation (only
   written at line 291 and asserted equal to "article-extract/4" in tests/test_reading_article_extraction.py:381 and
   tests/test_reading_source_cleanup.py:254), and `QUALITY_VERSION` records the rule change. Consequence if bumped:
   those two assertions must change (an edit, not a weakening). Recommendation: acceptable as is; prefer a bump only
   if the team wants to tell rows with the fact from rows without. The backlog checker
   (`scripts/check_reading_quality_backlog.py`) recomputes from stored facts, so rows stored with page_facts but
   without `no_semantic_container` will not be re-judged by the new media rule, and `teasers_only` WILL apply to
   stored rows that have `no_article_structure`. That asymmetry is consistent with "stored items are not
   re-evaluated" only partly: the checker can surface index-type rows newly. Worth one sentence in D-191.
3. Tests. Diff of tests/test_reading_page_quality.py is purely additive (+48, 0 deletions); no assertion weakened.
   Positives: /p/6197 -> index_page, /p/9647 -> media_page, /z/1741 still index_page. Negatives: two VOA 中文
   articles, NASA, Global Voices all `== []` (strictest form). Unit test covers both sides of the
   `no_semantic_container` switch and the size cutoff. Gap: no short-genuine-single-paragraph case (P2-1).
4. See P1-1.
5. D-191 amendment: accurate against the code (400/150, 600/200, no source name, stored items not re-evaluated,
   re-review required). Slight overstatement: "stored items are not re-evaluated" is true for admission but the
   backlog checker can re-judge them (see 2). Addendum in READING_QUALITY_GATE_REVIEW_2026-10-13.md is accurate.
6. `gh pr checks 163` (single call): changes pass 9s; node-gates pass 13s; docker-build, pytest, python-gates pending.
