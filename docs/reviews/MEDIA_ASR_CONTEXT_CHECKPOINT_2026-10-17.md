# Media ASR context and transcript review — 2026-10-17

MILESTONE=Video Sources Phase 2 / ASR A+B and EN caption cleanup
STATUS=IMPLEMENTING
BRANCH=claude/media-asr-context-corrections
BASE=2cb555ddcd5cc36b14c4fc731f74c341d32a1633
REVIEWED_APPLICATION_COMMIT=e814a4ec636ae8a104005f6afa6b55fa5997923c
WEB_URL=http://127.0.0.1:8021/
WEB_ROUTE=/#/admin/content/media/:id
HOW_TO_REACH_IT=Admin > Content > Media > item > Transcript

The owner approved A+B, English caption cleanup and continuation of import sitting6 on 2026-10-17.
This checkpoint verifies code locally; the running sandbox has not been restarted/deployed with it.
Live model quality, matched-audio comparison and the A12 visual fidelity gate remain open. No human
product approval or public readiness is claimed.

## Change and scope

- A: optional source title and any already available description guide Whisper. The prompt is bounded to
  224 UTF-8 bytes at codepoint boundaries, conservatively within the provider's token limit
  ([Groq speech documentation](https://console.groq.com/docs/speech-to-text)). Current YouTube oEmbed metadata
  supplies no description; this path uses title only, with no extra metadata request or invented description.
- B: only a genuinely new shared Admin admission may receive automatic text repair. Chinese correction
  requires ASR provenance; existing Chinese captions stay unchanged. English removes speaker/music noise
  and can restore punctuation/case/spacing, with Unicode word/number preservation. Personal, legacy and
  pre-existing records are excluded; retries consume eligibility, unfinished recovery preserves it.
- Bounded batches, existing configured media Groq provider/model and output allowance, per-call spend check
  and actual-usage accounting. No fallback provider. As first built, any failure held the item before
  translation; the live trial showed that was wrong and "Live trial fixes" below supersedes it: acceptance is
  per cue, a rate limit is paced, and a correction failure never blocks the item.
- Each actual edited cue retains before/after, unchanged timing, index, validated per-cue reason and
  provider/model. A12 uses its existing compact rows with escaped text and EN/VI/ZH labels. No CSS changes.
- Existing D-111 publication policy remains intact. Phase2 operationally keeps every item held with rights
  unconfirmed; this task neither publishes items nor adds a new publication/approval flow.

Protected area: shared Media Learning plumbing is deliberately extended for the approved task; canonical
asset/transcript/segment shapes and learner ownership are preserved. Persistence: existing shared Admin
`processing` JSON only, no DB/schema/migration. Runtime/env/provider/credentials: unchanged. Application
version `1.4.0` and frontend version `2.17.5` unchanged. `/api/agent/*`, mobile, brand and owner edits untouched.

## Independent review

Implementer: `/root/asr_implementation`. Independent reviewer: `/root/restore_review` (separate subagent).
Final verdict: **APPROVE — spec compliance and quality**, after correcting the two initial P1 findings
(ZH caption scope, prior-publication eligibility), Unicode/empty-cue/rationale P2 findings and the subsequent
helper-placement P1 caught by application import during regression testing. No scoped P0/P1/P2 remains.

Frozen source review patch SHA256: `dfcdf6aa5570d6dd02e0cc4a8177eb60411a35c3813e1854911d239ba780605b`.
This is code review, not human product approval or CI evidence.

## Local validation

- Broad media/caption/ASR/translation/quota/ownership pytest: **842 passed, 0 failed, 21 skipped**,
  5 existing deprecation warnings, 61.72s. Disposable container, repository read-only, isolated SQLite
  databases in tmpfs, provider keys empty, 1GB/1CPU limit. Host free RAM checked >2GB before each Docker run.
- Ruff on changed Python files: PASS. `test_groq_speech_asr.py` and `test_media_transcript_quality.py`: PASS.
- Node Admin media review and Admin areas: PASS (43 Admin routes, 112-route matrix, three UI languages).
  Browser ESM graph: PASS, 300 modules linked.
- Full local Node run: 141/142; Writing workspace gate depends on the owner's uncommitted Design Contract
  edits. That exact gate passes on a clean HEAD archive. The owner's file was not edited or staged.
  The final committed application snapshot `e814a4ec` was then archived and tested independently:
  **142/142 Node gates PASS; browser ESM graph PASS (300 modules)**, without the owner's unstaged edits.
- Two earlier media regressions were reproduced as passing on clean base HEAD, then fixed in this slice;
  both are included in the final 842-pass run. Project-memory and architecture validators: PASS.
  The referenced prior verified commit was independently resolved with host Git (the application image has
  no Git executable). No full pytest, Docker build or CI PASS is claimed by these local runs.

Exact pytest target set:
`tests/test_media*.py tests/test_d4_personal_media_isolation.py tests/test_quota_media_import*.py tests/test_speech_asr_url.py tests/test_supadata_async_jobs.py tests/test_youtube_audio_resolver.py`.

## Import sitting6 and remaining evidence

Sitting6 **STOPPED** at 2026-10-17 14:34Z. The container HTTPS request to `api.ipify.org` failed with
SSL EOF before `yt_dlp` was imported or YouTube was probed. Zero YouTube/Supadata/ASR/translation/import
requests occurred. The owned live-provider lock was released. No retry, VPN change or runtime restart.

Latest preflight ledger: Supadata13/20 requests on 2026-10-17; media list value today USD0.088405,
all-time USD0.982455; explicit paid spend today USD0. This task added zero provider spend. Refresh the
ledger on resume; the snapshot is not a current quota guarantee. Trial/reviewer artifacts report
37 usable items (EN19/ZH18), with EN11/ZH12 remaining; this session did not re-audit catalog contents.

Five benchmark cases were prepared from actual prior reviews: three known ZH idiom spellings and two EN
caption-noise cases. They are not full sentence/audio ground truth. No live before/after accuracy gain,
latency or token-cost improvement is claimed. Next: restore/verify egress, then live text-quality and
matched-audio benchmark, real A12 before/after review, and continued paced held imports under the lock.
Phase3 scoring and Phase4 family selection remain after Phase2.

EN_PARITY=shared pipeline/guard tests pass; live quality pending.
ZH_PARITY=ASR-specific correction and caption exclusion tested; live quality pending.
CROSS_CAPABILITY_STATUS=canonical shared Media Learning shape preserved; no fresh learner journey claim.
WHAT_THE_HUMAN_SHOULD_REVIEW=actual corrected text against audio, every flagged edit/reason, A12 rows in
desktop/phone and both themes, then paced trial outcomes. The milestone is not yet REVIEWABLE.

## Live trial fixes (2026-10-17, after the sitting 6A trial and ASR benchmark)

Owner-approved scope A+B unchanged; no new provider, env flag, schema or migration; no live provider call was made
for these fixes (tests use fakes, the live-provider lock was not touched). Evidence that drove them: the ASR
benchmark (4 ZH, 2 EN real cases) and sitting 6A (2 imports held untranslated). Local execution only.

- **Per-cue acceptance (P1-1).** `reject_cue_edit` in `media_transcript_pipeline.py` decides each proposed cue on its
  own: non-empty and within twice its length, English lexemes (words and numbers, NFC, any script) unchanged,
  Chinese changed Han characters within an allowance. A refused cue keeps its raw text and is recorded in
  `processing.transcript_correction_rejected` (index, start_ms, code, before, proposed); every valid repair is kept.
  Chinese allowance (replaces the global "20 % of all cues" ratio): Levenshtein distance over Han characters only
  (punctuation edits are free) of at most a quarter of the cue's Han characters, at least 2, at most 4, and always
  leaving one original character of a cue longer than one. It admits the homophone fixes the trial needed
  (渡舰->渡江, 床弦->船舷, 舰->剑, 船一正->船身) and refuses the rewrite of a cue; it is a general length-relative rule, not
  tuned to a video. Homophone plausibility (pypinyin) was considered and left out: the distance bound alone is
  enough and needs no dictionary.
- **Never blocks the item (P1-2).** The `transcript_correction_failed/unavailable` hold before translation is gone.
  The pipeline always continues on the best available text (raw for rejected cues, the accepted repairs and the
  deterministic noise strip otherwise) to translation and then the normal review/rights rules. Outcome recorded in
  processing: `transcript_correction_state` = `applied | partial | failed | unavailable` and
  `transcript_correction_detail` = stable code (`lexemes_changed`, `edit_ratio_exceeded`, `empty_cue`,
  `rate_limited`, `spend_cap`, `provider_*`, `malformed_result`, ...). Stale values are reset when a run starts.
- **Pacing (P1-3).** Each batch runs inside the existing `translation_pacing` allowance (D-218 output-token
  pacing, 150 s shared by all batches, the translation run's own total). A `rate_limited` answer naming a wait of at
  most 90 s that fits the remaining allowance is slept once (`self._sleep`) and that batch asked once more; any
  other failure, a longer wait or a second refusal stops the step. Batches already accepted are kept (`partial`);
  later batches keep raw text. No unbounded retry, spend is checked before every attempt, usage is booked per call.
- **Title prompt (P1/P2-4).** Cheapest correct design: the prompt is sent only when the audio is at most
  `ASR_PROMPT_MAX_SECONDS` = 120 s (it helped the 47-78 s clips and hurt the 282 s story), and a prompted chunk whose
  text carries the full-width digit/symbol/letter junk signature (`asr_text_has_junk`) is transcribed once more
  without the prompt (extra call checked against the cap and booked). A no-prompt reference pass for every item was
  rejected as doubling ASR cost. Honest limit: silent content loss on a short clip (no junk) is not detectable
  without a reference pass; it is not claimed fixed.
- **Noise (P2-5).** English only: `>>`/`>>>`; any square-bracket group of 1-4 plain words (`[crying]`, `[gasps]`,
  `[door creaks]`; not `[1]`); a parenthesised group only when it is the whole cue or names a sound from a closed
  vocabulary (`(music)` yes, `(Paris)`/`(yes)` no). A cue that becomes empty is dropped (as the canonical caption
  cleaning drops it) and recorded as a row with reason code `noise_removed`; it no longer aborts the repair. Chinese
  text is never stripped. The deterministic strip also applies when the model is unavailable.
- **A12 (P2-6).** Rows now carry `reason_code` (`noise_removed` | `model_edit`); a deterministic edit shows a
  translated reason, not "No change."; the state hint (`failed`, `unavailable`, `partial`) shows the translated
  detail code; rejected cues appear in the same compact rows ("Not applied: ..."). Copy in EN/VI/ZH in
  `copy-content.js`; the old "held for review" wording is removed. Existing `rowList`/`a-hint` only, no CSS change.

Local execution (not CI): media pytest target set **879 passed, 0 failed, 21 skipped** (was 842 passed; 37 new
tests in `tests/test_media_correction_per_cue.py` and the updated integration tests), disposable container,
repository read-only, tmpfs databases, provider keys empty, 1 GB / 1 CPU, host free RAM above 2 GB checked before
each run. Ruff on touched Python: PASS. Node admin media review, admin areas, admin control: PASS; browser ESM graph:
PASS (300 modules). Not done: live re-run of the failing cases, A12 visual check with real applied/partial rows,
sandbox restart (not allowed). The owner-dirty Design Contract and untracked UX files are not staged.

## Review of `7a0957fe`: CHANGES REQUIRED, P1 fixed (2026-10-17)

The independent review of `7a0957fe` returned **CHANGES REQUIRED: one P1 and five P2**. The earlier APPROVE above covers
`e814a4ec` only and does not cover this code. The reviewer's full text was reported in the owner's CLI session and is not
in the repository; only the P1 was relayed, so **the five P2 findings are open and unaddressed**.

- **P1 (fixed in this working tree, not yet re-reviewed).** A shared item with `rights=cleared` whose correction did not
  finish was published automatically with uncorrected text. Rights are cleared for the corrected transcript, and D-111
  allows automatic publication only when every check passed. Now, when `transcript_correction_state` is `partial` or
  `failed`, `_run` still translates, then holds the item (`state=held`, `status=review`, `auto_published=False`) with the
  reason `transcript_correction_incomplete` and `detail` set to the correction state; model clips are not cut for it.
  `applied` publishes as before. `unavailable` (unsupported language, no corrector configured) is not an attempt that
  failed, so it does not hold. Learner-owned imports are never held by it. A person publishes or reprocesses the held item.
  Decision for the owner: any single refused cue (`partial`) holds the item; this is the strictest reading and can be
  relaxed by editing `CORRECTION_HOLD_STATES`.
- Admin A12: the stored reason has copy in EN/VI/ZH (`impErr_transcript_correction_incomplete`), the held banner is titled
  "Needs review" rather than "Failed", and a rights hold keeps its existing presentation.
- Tests: the old integration test that asserted a failed correction still publishes a cleared item now asserts the hold;
  added cleared-item publishes only on `applied`, no learner-import hold, reason message and 3-language copy.

Local execution (not CI), same target set, same disposable container recipe, host RAM checked above 2 GB first:
media pytest **883 passed, 0 failed, 21 skipped** (879 before; 4 new). Ruff on the three touched Python files, Node admin
media review, Node admin areas, browser ESM graph (300 modules) and `validate_project_memory.py`: PASS. Not done: live
provider re-run (the earlier agent died on a provider rate limit, and a paid run needs the owner's go-ahead), A12 visual
check, review of the five P2 findings, independent re-review of this P1 fix (the implementer may not approve it).

## Exact changed files and memory transaction

Code/tests: `app.py`; `writing_coach/speech_asr.py`; `writing_coach/media_transcript_pipeline.py`;
`writing_coach/media_transcript_quality.py`; `writing_coach/media_translation.py`;
`writing_coach/media_source_import.py`; `static/orena/screens/admin/content-pages.js`;
`static/orena/screens/admin/copy-content.js`; `scripts/test_groq_speech_asr.py`;
`scripts/test_media_transcript_quality.py`; `scripts/test_orena_admin_media_review.mjs`;
`tests/test_speech_asr_url.py`; `tests/test_media_pipeline_integration.py`; `tests/test_media_correction_per_cue.py`;
`tests/test_media_translation_groq.py`; `tests/test_quota_media_import.py`;
`tests/test_speech_transcribe_guard.py`.

Memory/evidence: this checkpoint; `docs/project/CURRENT_HANDOFF.md`;
`docs/project/CURRENT_PRODUCT_STATE.yaml`; `docs/product/ORENA_STATUS.md`.
`PROJECT_STATE.md` unchanged. No Decision Log entry: bounded implementation of the explicit owner approval,
with existing architecture/provider/publication contracts retained. No production/deployment operation.
The owner-dirty Design Contract and untracked `.agents/`, UX review docs/evidence are excluded from staging.

User changes left at the application checkpoint (`git status --short`):

```text
 M docs/project/DESIGN_CONTRACT.md
?? .agents/
?? docs/UX_REVIEW_AGENT.md
?? docs/UX_REVIEW_LOG.md
?? docs/UX_REVIEW_RULES.md
?? docs/reviews/evidence/cross-skill-audit/
?? docs/reviews/evidence/onboarding-audit/
?? docs/reviews/evidence/places-audit/
?? docs/reviews/evidence/speaking-audit/
?? docs/reviews/evidence/vocabulary-audit/
?? docs/reviews/evidence/writing-audit/
?? docs/ux-review-evidence/
```
