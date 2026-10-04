# S6 Admin media review and publication checkpoint

Date: 2026-10-02. Lane: `codex/work`. Reviewed base: `479b680` plus this bounded delta.

MILESTONE=Admin shared-media rights review and publication
STATUS=REVIEWABLE (not human product approval)
COMMIT=the code commit containing this checkpoint
WEB_URL=http://127.0.0.1:8021/next
WEB_ROUTE=#/admin/content/media/<media-id>
HOW_TO_REACH_IT=Admin -> Imports -> Media -> upload -> Open -> Rights & origin -> Save rights review -> Publish -> Open as learner -> Listen
EN_PARITY=English fixture imported, prepared, reviewed, published and opened in Listening with Vietnamese meanings through the same UI
ZH_PARITY=Chinese fixture reviewed, published and opened in Listening with pinyin and Vietnamese support meanings
CROSS_CAPABILITY_STATUS=Admin publication opens the existing Content and Listening routes; prior Dictation/Shadowing evidence remains S2

## What changed

Admin can record unknown, cleared or denied rights on shared imported media. Clearance requires confirmation and a permission/license note. It does not publish by itself. Publish/Republish require a usable transcript, completed processing and cleared rights; backend checks and writes against the latest record atomically. Withdrawing clearance unpublishes a live item, and remains possible during reprocessing. The pipeline checks latest rights again at its final publication write. Restore returns archived media to unpublished, with a separate publication decision. Review/processing badges and filters now reflect real states.

Browser testing found that a manually published transcript held for rights review still opened an empty Listening room. The existing learner resolver now accepts completed held transcripts while preserving publication, owner and language admission checks.

The rights form extends pinned Admin A12 using its existing form primitives and the A14 rights-review pattern, under the explicit current human Admin lifecycle instruction. No competing design/product authority or new persistence schema was introduced.

## Browser evidence

Only internally authored synthetic-speech QA fixtures were used. Both are archived after verification; no uncertain-rights public content was cleared.

- Chinese `market-zh-admin-review`: two real ASR segments, 11.6 seconds. Saved clearance survived page reload and sandbox web restart. Publish yielded Published and Open as learner. Content -> Listen showed the Chinese transcript, pinyin, Vietnamese meanings and existing player controls. Before the resolver correction this same journey showed an unavailable transcript; that observation is superseded by the verified correction.
- Changing saved rights to Unknown yielded Unpublished and removed Publish/Republish and Open as learner. Archive preserved transcript and permission note. Restore yielded Unpublished without automatic publication.
- At 390x844 the rights form remained operable; page and both main elements had scrollWidth/clientWidth 390, with no horizontal overflow. Viewport override was reset.
- English `morning-en-admin-review`: Admin Upload file -> English -> Import -> Open showed three real transcript segments, 9.8 seconds, Needs review. Saving attested clearance enabled Publish. Published -> Open as learner -> Listen showed all three English segments and Vietnamese meanings. It was archived afterwards.

Evidence images: `evidence/s6-admin-media/zh-listening.png`, `evidence/s6-admin-media/rights-mobile.png`. Additional EN evidence is saved alongside them.

## Validation and independent review

Local application-image execution: 260 passed, four existing deprecation warnings, across Admin console routes/content/security/authorization, media pipeline integration, personal-media isolation and Listening MVP integration. Ruff passed for touched Python files. Node Admin media lifecycle, Admin screens/areas, three-language copy and browser ESM graph gates passed (331 modules). This is local evidence, not CI PASS or a full-suite claim.

Independent reviewer `/root/review_media_basic` reviewed the bounded working diff against `479b680`: initially REQUEST CHANGES for stale publish and processing-time rights revocation; after corrections APPROVE with no actionable P0/P1/P2. A separate focused review approved the held-transcript learner resolver. Reviewer did not run Docker/tests. Human approval remains separate.

## Remaining basic coverage

This completes the bounded rights-review/publication path, not all Admin. Import queue still retains its immediate No transcript result after asynchronous preparation; processing stages/progress and automatic refresh in Admin need the next normal-operations slice. Admin Overview, Users and Operations entry points remain basic product gaps, followed by canonical Grammar and integrated Intelligence/Agent. Level/topic editing and substantial real EN/ZH supply remain required. Existing Books/Progress and S2 Listening checkpoints are preserved.

Human review: inspect the rights form, attestation, Publish confirmation, learner link, withdrawal and Restore behavior; use rights-cleared media with a usable transcript. Archived QA entries remain accessible to Admin for inspection, not learners.
