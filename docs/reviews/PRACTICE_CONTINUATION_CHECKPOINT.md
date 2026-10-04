# Practice Hub continuation correction — 2026-10-04

MILESTONE=Practice continuation correction
STATUS=IMPLEMENTING (functional correction available for web review; full fidelity gate remains open)
COMMIT=88286930712eedf37c6571e62737bd780d676dbe (includes 5b1114e)
WEB_URL=http://127.0.0.1:8021/next#/practice
WEB_ROUTE=practice
HOW_TO_REACH_IT=Practice in the main navigation

## Root cause and resulting flow

The former Hub projected the five latest routable continuation entries directly
into Continue cards. Opening Compare alone records a navigation visit. The
server place adapter supplies Listening's navigation-only `1/1` fallback; the
Hub displayed that as if it were learning progress. Canonical and upload aliases
also produced duplicate cards for the same media.

Continue now admits up to three most-recent substantiated unfinished activities:
a nonempty unsubmitted free-writing draft; an existing conversation with learner
turns, not ended or capped; a reading position strictly between 0% and 100%, with
the source still readable in the active learning language. Each row states the
reason and resumes the owning workspace's actual saved state. Reviewed essays
link to their existing piece instead of opening a new empty writing workspace.

Ordinary visits live behind Recently opened in the existing shared sheet. Stored
media is resolved using read-only shared source APIs; stable asset/canonical
identity deduplicates aliases, keeping the most recent selected segment. Media
line counts are actual transcript positions, labelled as the last opened line,
never completion or mastery. Missing, unready, unavailable and wrong-language
reading/media sources are omitted. No learner records are deleted or migrated.

There is no inferred speaking completion goal, invented assessment threshold,
new schedule, or obligation to finish every line in a video. Dictation and other
visit-only entries remain recent history until their owning capability exposes
substantiated unfinished work. Existing vocabulary due review stays separate.

## Evidence

- Real :8021 Chinese profile originally showed duplicate imported-video Compare
  cards plus unrelated `1/1 Continue` entries. After the correction it honestly
  showed no pending work and one Recently opened action.
- Writing originally had an empty draft. Typed `今天我去市场买水果。` without
  requesting evaluation: Hub showed Draft not submitted; Continue reopened the
  exact nine-Hanzi text. Restored the original empty text through the editor:
  pending card disappeared. No evaluation/provider call was requested.
- Recent sheet showed the imported video once, with actual line 1/26; the
  existing Chinese Wikipedia media was labelled line 2/7. Selecting it opened
  Shadowing / Pronunciation with line 2 selected, original model control enabled,
  Pinyin and meaning already present, no source preparation UI.
- Wrong-language and no-longer-readable reading entries disappeared from Recent.
- Desktop and 390x844 phone Hub/sheet checked. Continue reasons and phone titles
  wrap rather than hiding the explanation; shared sheet owns scrolling and close
  / Escape / focus behaviour. Recent rows use Pronunciation, not an internal
  Compare label. No native mobile changes.
- Vietnamese phone Hub and Recent sheet checked: Học tiếp, Bài mở gần đây,
  actual selected-line labels and the reason for a recent visit render fully.
- EN/ZH instrumented fixture test: only ready-source GET methods are supplied;
  selected line survives, repeated reads reuse shared source cache, wrong language
  is rejected. No acquisition, ASR, translation, TTS or evaluation method is
  available to this path. This is instrumented local evidence, not a production
  provider billing audit.

EN_PARITY=shared eligibility/route/source logic and English fixture passed
ZH_PARITY=shared logic, Chinese fixture and real browser draft/media journey passed
CROSS_CAPABILITY_STATUS=existing draft/conversation/Reader state reused; media
original selected segment reused; existing due-review system unchanged

## Local validation and review

- New continuation gate PASS; Practice screen gate PASS; ESM graph PASS, 336 modules.
- CI-listed Node commands: 127 total, 125 PASS, 2 FAIL, 0 skipped. Failures match
  the already-reproduced baseline: Word `dueInDays` date-sensitive assertion and
  Writing's old rule-number assertion against human-owned Design Contract edits.
  Neither validator was weakened; Design Contract working-tree changes preserved.
- Project memory validator PASS; architecture validator PASS (1.4.0).
- No Python/backend change; the preceding full hermetic Python baseline remains
  2805 passed, 3 inherited failures, 370 skipped. It was not rerun for this UI slice.
- Independent reviewer: `/root/readiness_review`; APPROVE for exact commit
  `88286930712eedf37c6571e62737bd780d676dbe`, no P0/P1/P2. Initial P2 (distinct
  excerpts sharing an asset were collapsed) corrected: canonical lesson identity
  takes precedence and a regression test preserves both. Engineering review only.

Fidelity accounting: pinned Practice Hub and sheet patterns read; existing row,
heading, tint tokens and overlay reused. Human-requested pending/recent separation
is the deliberate interaction change. EN/ZH source logic and EN/VI interface
checked; title/reason wrapping and phone scroll checked at 390x844. Semantic
theme/contrast gates passed with unchanged tokens. Copy states only eligibility,
saved place and action. No new art. Full EN/ZH/VI visual comparison in both themes,
physical-phone touch and replacement cutover are not established by this batch;
the full fidelity gate remains open, hence IMPLEMENTING rather than APPROVED.

## Scope and review checkpoint

Changed files: `.github/workflows/ci.yml`; `scripts/test_orena_practice_continuation.mjs`;
`scripts/test_orena_screen_practice.mjs`; `static/orena/screens/practice/continuation.js`,
`model.js`, `screen.js`, `copy.js`, `practice.css`.

Protected-area change: deliberate minimal Practice/continuation projection and
resume routing; shared media, persistence, layout kit and accessibility unchanged.
No schema, migrations, new storage, runtime configuration, deployment, production
operation, application/frontend version change or paid-provider activation.
PROJECT_STATE.md unchanged. CURRENT_HANDOFF.md and ORENA_STATUS.md updated.
Decision Log entry not required: clarification of existing continuation/navigation
semantics, not a new content or learner persistence model.
Git after implementation: the only remaining application-external modification
is human-owned `docs/project/DESIGN_CONTRACT.md`; this checkpoint/status/handoff
are committed separately. No files from that human edit were staged.

WHAT_THE_HUMAN_SHOULD_REVIEW=truthful pending versus recent separation, whether
each reason and destination is clear, and the phone Hub/sheet density.
Remaining blockers: wider Product Completion/fidelity and existing gate failures
remain open; this does not establish human approval or release readiness.
