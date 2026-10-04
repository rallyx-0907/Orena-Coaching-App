# Reading registered-source admission checkpoint

Date: 2026-10-04. Lane: codex/work. Bounded S1 under accepted D-111;
Grammar remains deferred. Implementation status: IMPLEMENTING (full fidelity
and release gate open). This is functional evidence, not human approval.

## Checkpoint and independent review

COMMIT=e74735b615bf37c3f44c75e86e6466bc14b38dd3
BASE=4df9d7ab4c277528d354bc920b6bf465417c7dac
Initial implementation=b1ae47d1d08166068eb48c80d9dd1ee3f84dd67b.
Reviewer=/root/collection_review, independent Codex review role.
Final exact-commit verdict: no unresolved P0/P1/P2 code findings.
Reviewer read code/contracts; root performed all runtime/test verification.
Initial review findings (attribution, untranslated reasons, duplicate conflict,
race reporting, URL origin borrowing and provenance labels) were corrected.
b1ae47d exact review requested changes; e74735b closes those findings.

## What changed and why

Registered source identity was not carried by Admin imports, source automation
was never consumed and candidates always waited for review. Chinese learning
targets came from character windows, including “在松树林” and “松树林里”.

Imports now bind to the existing registry. Source policy is inherited only from
an active source; fetched URLs must match its explicit HTTP(S) origin. Explicit
per-text rights override defaults on new snapshots. The registered name owns
provenance. Shared deterministic Chinese annotation supplies whole-token words
(e.g. 松树) and bounded adjacent repeated phrases rather than arbitrary n-grams.

The existing article transaction checks current source/snapshot, rights, visible
attribution, language, quality and grounded targets. It records rule version and
reasons in existing analysis/review events, then publishes with target visibility
atomically only on success. Historical admin_approved target fields represent
visibility approval; the event actor remains orena:reading-engine, never a human.
Unknown/denied/invalid evidence stays in review. Conflicting rights on duplicate
bytes are refused with localized guidance to the existing article rights review;
the immutable snapshot and existing article are not silently changed.

Sequential duplicate imports reuse the same article before analysis. The
repository lock/recheck prevents duplicate publication in a lost-precheck race
and the job correctly reports duplicate. Racing deterministic analysis may still
run twice; there is no paid analysis in this engine. No schema/new content model.

## Real sandbox evidence

WEB_URL=http://127.0.0.1:8021/next
WEB_ROUTE=#/admin/reading/add?mode=text
HOW_TO_REACH_IT=Profile -> Platform admin -> Content -> Reading -> Add content.
MILESTONE=S1 registered-source admission
STATUS=IMPLEMENTING (functional checkpoint; full fidelity open)
EN_PARITY=verified import/publication/read/reopen and phone viewport
ZH_PARITY=verified same flow, Hanzi/Pinyin and whole-token targets
CROSS_CAPABILITY_STATUS=existing shared Reading/Library owner reused; Free Reading
offered without falsely advertising an absent comprehension set. Media D-121
and S3 vocabulary/SRS remain unchanged.
WHAT_THE_HUMAN_SHOULD_REVIEW=registered-source selection, inherited versus explicit
rights, held reasons and source provenance; remaining level/enrichment/question
gaps are not presented as complete.
Review uses existing registered-source select and article evidence rows.

Admin browser form selected QA authored Reading EN/ZH and submitted two original
texts authored for this QA. Exactly one owned queued job was claimed/processed
per bounded run; no worker loop, source polling or question generator was started.

| Evidence | EN | ZH |
| --- | --- | --- |
| Initial job | f413e2a8-703f-4b93-8da4-3d5876d38665 | 755b34f8-0081-4a1a-9da7-f3273bc24438 |
| Article | 22fc134d-f3eb-4c7f-b723-d0701bbc05b2 | f1efe7a5-04d8-4689-b46a-cf16c0c367dc |
| Source snapshot | e4535b0a-ea31-4837-ad84-6570ba804cbb | f3441a3c-75b6-4bdb-8066-0a3c0f8e098e |
| Admission | published, no reasons, revision 1 | published, no reasons, revision 1 |
| Reader | original text, desktop and 360x740 | original Hanzi/Pinyin, desktop and 360x740 |

Registered source=f084a94c-1912-4417-bc62-14cf4eb87834. Chinese targets:
森林, 大家, 学生, 松树, 植物, 竹林, 老师, 观察. These are token-based
suggestions, not proof that a pedagogical level/translation has been validated.

Walked import -> publication -> Open as learner -> Content -> Start reading;
reopened Reader and restarted only orena-next-verify-web. Published articles and
revision 1 persisted. Read-only navigation uses existing APIs; it starts no source
job. The existing generic route-fetch loader can still show “Preparing your
lesson”; it is not a source-processing job and is not claimed fixed by this slice.

Real repeated EN import job 86b2f082-7d22-4280-a0fe-7d1d678692f0 returned duplicate,
same article/snapshot. In that bounded process _build_candidate was instrumented
to raise if called; no analysis/materialization occurred. Queue ended empty.

Unknown-rights fixture 0574a6e4-693b-4895-ad46-bf4855fb1e2a stayed needs_review:
automation_not_allowed, rights_not_cleared, attribution_unknown, too_short.
Browser showed Publish disabled and localized reasons in Processing evidence.
Final form reload confirmed registered Source is readOnly with canonical name.

Provider instrumentation: /api/admin/ai/operations?limit=200 before/after retained
10 events, sample_truncated=false, latest 2026-10-03T12:15:14.879733+00:00;
zero events on 2026-10-04. Initial deterministic preparation and navigation both
made zero paid provider calls in this slice. Future source enrichment/question
derivatives must be prepared/persisted once; new learner answers/recordings may
legitimately request assessment. No provider credentials/config changed.

D-111 QA hygiene: both published QA articles archived after verification through
the existing Admin status API; records/evidence retained. The one held fixture
remains Admin-only. These fixtures do not count toward production content breadth.

## Validation actually run

- Final changed-flow Python batch: 159 passed, 0 failed (147.51s): admission,
  engine, processing, route and repository tests. Includes URL isolation,
  attribution, explicit rights conflict, grounded targets and race reuse.
- Earlier focused final-rights batch plus D4: 168 passed, 22 skipped; clean HEAD
  D4-only comparison: 18 passed, 22 skipped. Not a full-suite baseline comparison.
- Broad local Python before the last origin correction: 2838 passed, 4 failed,
  370 skipped, 19 warnings (334.32s). Three known inherited failures:
  test_ai_capabilities static provider set, test_ai_capability_config provider parity,
  test_media_lifecycle republish expectation. Additional D4 review-refresh failure
  occurs in full suite, not focused current/clean HEAD; cause unresolved. Do not
  call that fourth failure an inherited defect or a proven regression.
- All 130 CI-listed Node commands locally: 128 passed, 2 failed, unchanged known
  failure identities: test_orena_screen_word dated due fixture;
  test_orena_writing_workspace exact contract-rule assertion affected by the
  human-owned Design Contract edit. Validators were not weakened.
- After final correction: Admin areas PASS (34 guarded routes, three languages),
  copy PASS (46 tables, 2666 keys EN/VI/ZH), ESM PASS (340 modules linked).
- Ruff touched Python files: PASS, --no-cache because repository mount is readonly.
- Architecture validation, project-memory validation and git diff --check: PASS.
- Local execution only; no CI PASS, full-gate PASS or production approval claim.

## Fidelity, risks and remaining work

Provenance: pinned Orena-Admin.dc.html A21 existing select/field grid, A22 registered
sources, A23 article evidence rows, adapted to source identity and admission state.
No CSS, token, artwork, mascot, layout infrastructure or native code changed.
Function/responsiveness checked EN/ZH at 360x740; full measured source/skin fidelity,
light-theme comparison, touch-device QA and exported screenshots remain OPEN.
Screenshots were inspected in browser tool output, not saved as report artifacts.

Free Reading alone is admitted here; no comprehension set was generated. Only
capabilities with ready prerequisites are exposed. Source volume/licensed supply,
level calibration (Chinese count/level remains a coarse heuristic), vocabulary
meaning/context enrichment, question materialization/auto-approval, whole-product
QA and release/operations gates remain open. This is not full S1 or production.
Accepted next order: vocabulary enrichment -> practice on publish -> Agent;
Grammar later. Preserve prior S3/media/Books/Progress checkpoints.

## Files and operational record

Implementation files (exact base-to-final diff):

- docs/product/ORENA_CONTENT_ARCHITECTURE.md
- docs/reviews/READING_SOURCE_ADMISSION_PLAN.md
- scripts/test_orena_screen_admin_areas.mjs
- static/orena/capabilities/admin-reading.js
- static/orena/screens/admin/copy-imports.js
- static/orena/screens/admin/copy-reading.js
- static/orena/screens/admin/reading-pages.js
- static/orena/screens/admin/reading.js
- tests/test_reading_admission.py
- tests/test_reading_content_engine.py
- tests/test_reading_processing.py
- writing_coach/persistence/reading_content_repository.py
- writing_coach/reading_admin_api.py
- writing_coach/reading_admission.py
- writing_coach/reading_content_engine.py
- writing_coach/reading_processing.py
- writing_coach/reading_source_import.py

Documentation transaction updates CURRENT_HANDOFF.md, CURRENT_PRODUCT_STATE.yaml,
ROADMAP.md, ORENA_STATUS.md and this checkpoint. PROJECT_STATE.md unchanged.
Decision Log entry not required: implements accepted D-111 and clarifies D-121,
without another content model or new durable product direction.

Protected changes: canonical Reading content lifecycle and its Admin consumer,
deliberate scope with independent review. Persistence: existing PostgreSQL owners,
no migration/schema/sync changes. Runtime: only :8021 restart and bounded owned
QA jobs/fixture archival; worker remains stopped, volumes preserved. Application
and frontend version unchanged (1.4.0). Production/preview/deployment unchanged.
At code checkpoint, Git status was only M docs/project/DESIGN_CONTRACT.md;
that human-owned edit is preserved and excluded from every commit.
