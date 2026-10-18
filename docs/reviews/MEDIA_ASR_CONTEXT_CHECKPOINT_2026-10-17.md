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

**Superseded for the current head.** This section records the first review, of application commit `e814a4ec` only. Later
reviews of `7a0957fe`, `d7aed04f`, `54c8f608` and the final APPROVE of `317ffe9e` are recorded in the sections below;
read those for the current state.

Implementer: `/root/asr_implementation`. Independent reviewer: `/root/restore_review` (separate subagent).
Final verdict (for `e814a4ec`): **APPROVE — spec compliance and quality**, after correcting the two initial P1 findings
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

## Review of `d7aed04f`: REQUEST CHANGES, P1 and P2 fixed (2026-10-17)

A second independent review (Delegated Architecture Reviewer, read-only, no code run) of `d7aed04f` returned
**REQUEST CHANGES: one P1 and one P2**. It could not certify the five P2 findings of the earlier review one by one, because
their text is not in the repository. **Those five remain unaddressed.** The reviewer used `2cb555ddc` as the base; in that
checkout `origin/main` pointed at a different commit.

- **P1 - retry/reprocess bypassed the hold (fixed, not yet re-reviewed).** `retry()` cleared the eligibility marker and
  `_run` reset the correction state, so a `cleared` item held for a `failed` correction met no correction state on the
  retry and auto-published the raw text. Now a shared item that finishes with its correction incomplete carries the durable
  marker `transcript_correction_unresolved`. While it is set, `_run` holds the item unless that very run ends `applied`
  (a retry whose corrector fails again, or is not configured, stays held). `retry()` grants the correction admission again
  to such an item so it can finish `applied`. A person publishing by hand through the Admin status route clears the marker
  (their decision, after checking the transcript). Learner-owned imports never carry it.
- **P2 - A12 showed model-written reasons verbatim (fixed).** The reason is now a code from the closed list
  `CORRECTION_REASON_CODES` (`punctuation`, `capitalization`, `spacing`, `homophone`, `idiom`, `proper_noun`, `no_change`,
  `other`): the prompt asks for exactly one code, any other answer is stored as `other`, and A12 words the code from
  `copy-content.js` in EN, VI and ZH. A row stored before this change, holding a sentence, reads as "Other correction"
  instead of foreign text. No CSS change.
- Tests: retry of a held cleared item with a corrector that fails again, is unconfigured, or succeeds (only the last
  publishes, and clears the marker); the Admin status route clears the marker; the Node gate checks the reason in EN/VI/ZH, that a
  model sentence is never shown, and that an unknown reason reads as the generic one.

Local execution (not CI), disposable container (repository read-only, tmpfs databases, provider keys empty, 1 GB / 1 CPU,
host RAM 3.76 GB checked first): media pytest set plus `tests/test_admin_console_routes.py` and
`tests/test_admin_authorization_matrix.py` **1240 passed, 0 failed, 21 skipped**. Ruff on touched Python, Node admin media
review, Node admin areas, browser ESM graph (300 modules): PASS. Not done: independent re-review of this fix (the implementer
may not approve it), the five earlier P2 findings, the live provider re-run (a paid run needs the owner's go-ahead), A12 visual check.

## Review of `54c8f608`: REQUEST CHANGES, two P1 and one P2 fixed (2026-10-17)

A third independent review (Delegated Architecture Reviewer, read-only, no code run) of `54c8f608` returned **REQUEST
CHANGES: two P1 and one P2**. It confirmed the earlier hold-bypass P1 as closed (retry, recover, restore, translation-only
retry, caption-only paths, learner imports, `unavailable`). It again could not audit the five P2 findings of the first review
because their text is not in the repository: **they remain unaddressed**; their verbatim text should be recorded in the PR
or an issue before this stage closes.

- **P1 - the ZH guard only protected Han characters (fixed, not yet re-reviewed).** `reject_cue_edit("zh", ...)` measured the
  edit over Han characters only, so the model could change an entity or a figure inside a Chinese cue (VOA -> BOA, 2025 ->
  2026, GPT-5 -> GPT-6) with a Han distance of 0 - the trial had a real VOA -> BOA. Now every non-Han word or number of a
  Chinese cue must be unchanged (`_non_han_lexemes`, a Han character acting as a separator, NFC, case-folded); punctuation
  and spacing stay free, and a Han repair (渡舰 -> 渡江) is still accepted. A refused cue keeps its raw text with the code
  `lexemes_changed`, which A12 already words in EN/VI/ZH.
- **P1 - a single provider wait could exceed 90 s (fixed).** The per-wait cap was enforced only on the outer retry; the
  provider's own pacing (`_reserve_output`) was handed the whole 150 s allowance, so a window blocked for 120 s could be
  slept in one call. Each call now receives its own budget `min(90 s, what is left of 150 s)`, and what the provider actually
  waited is deducted from the shared total, which the outer retry also draws on. A wait longer than the cap is refused unsent.
- **P2 - stale A12 comment (fixed).** It said a model edit keeps the model's own reason; it now describes the reason codes.
- Tests: 9 Chinese cases with Latin words and numbers (the four the reviewer named, plus dropped/invented words, case,
  punctuation/spacing, a Han repair beside an untouched entity); a test through the real `_reserve_output` with a virtual
  clock and a window blocked 120 s, asserting no sleep and no request; a test that the budget handed to successive calls is
  `[90, 70]` after the provider spends 80 s.

Local execution (not CI), disposable container (repository read-only, tmpfs databases, provider keys empty, 1 GB / 1 CPU;
host RAM 2.49 GB, above the owner's 1 GB floor): media pytest set plus `tests/test_admin_console_routes.py` and
`tests/test_admin_authorization_matrix.py` **1251 passed, 0 failed, 21 skipped**. Ruff on touched Python, Node admin media
review, Node admin areas, browser ESM graph (300 modules): PASS. Not done: independent re-review of this fix (the implementer
may not approve it), the five first-review P2 findings, the live provider re-run (a paid run needs the owner's go-ahead), A12 visual check.

## Review of `317ffe9e`: APPROVE (2026-10-17)

Delegated Architecture Reviewer (independent of the implementer, per AGENTS.md "Architecture review authority"), reviewed
commit `317ffe9ebc5b1b658f57364693cbaab4bb391372` against `54c8f608`. Verdict **APPROVE**: no P0 and no P1 remain.

- ZH Latin/number guard, the 90 s per-wait cap with its shared 150 s total, and the stale A12 comment are **closed**. The
  reviewer confirmed the tests reach the real `_reserve_output` (window blocked 120 s: no sleep, no request) and the `[90, 70]`
  budget split, not only an outer mocked exception.
- CI on this exact SHA, checked by the implementer with `gh` (not taken from a report): workflow run #818, `CI`, conclusion
  `success`, head `317ffe9e`; jobs `python-gates`, `node-gates`, `pytest`, `docker-build` and the aggregate `test` all
  `success`. Earlier heads `54c8f608` (#815) and `7a0957fe` (#800) are also `success`.
- **P2, still open:** the verbatim text of the five findings from the first review of `7a0957fe` is in no repository file, PR
  comment or review thread, so it cannot be audited and is **not** claimed closed. It must be recorded in Git (or an issue)
  before this stage closes.
- **P2, bookkeeping:** the PR #261 description still carried the validation and "independent reviewer APPROVE" of
  `e814a4ec` while the head is `317ffe9e`. The PR is still a draft.
- **Not evidence of anything else.** This is architecture review: not product approval, not `:8000` deployment approval and
  not live-provider approval. **Still not done:** the A12 visual check with real applied/partial rows, and the live provider
  benchmark (cost ceiling $0.10, no new item created), which needs the owner's go-ahead. `:8021` still runs `7a0957fe`; it
  needs a restart to exercise the later fixes.

## Live provider benchmark on :8021 (owner-approved 2026-10-17): partial, one P1 found and fixed

Scope the owner approved: restart :8021 on the head (done, `5ca4ac43`, after CI #820 `success`), no `:8000`, no env or
credential change, no new item, no publication, rights unchanged, total provider spend cap USD 0.10, stop at the first
anomaly. Method (owner's option B): the pipeline's own `_correct_transcript` was run on the **transcript already stored** for
existing trial items, with a temporary eligibility marker that was removed afterwards; no Supadata, Whisper or translation call.
Provider: the one already configured on :8021 (Groq, `qwen/qwen3.8-27b`, OTPM limit 1000). Backup of the index before the run:
`/lanedata/backups/index.json.pre-asr-benchmark-20261017` (sandbox volume). Stored lesson text, status and rights are unchanged
(checked after the run); only the correction fields of `processing` were written, which is what A12 reads. Spend booked on
the benchmark batch: **USD 0.0169** of the 0.10 cap.

| Case | Item | Result | Reader's judgement |
| --- | --- | --- | --- |
| 1 ZH ASR idiom | `youtube-2HRoo7akLsU` 守株待兔, 14 cues | `applied`, 3.97 s, USD 0.0028; 12 cues accepted, 0 rejected | **better**: 守株带兔 -> 守株待兔 (the idiom), plus punctuation |
| 2 ZH ASR, previously failed | `youtube-cZbVZFJ7UrI` 灰姑娘, 26 cues | `partial` (`edit_ratio_exceeded`), 66.7 s, USD 0.0057; 14 accepted, 6 rejected | **better, not complete**: 回姑娘 -> 灰姑娘, 神仙焦木 -> 神仙教母 style fixes accepted; 6 cues with several recognition errors at once exceeded the quarter-of-Han allowance and stayed raw, as designed |
| 3 ZH with Latin/numbers | `youtube-rbLlUXT72C4` HSK1, 51 cues | **failed twice, then `partial`** (`malformed_result`), see below | **no change** for the failed cues; the entity guard was **not exercised** by a completed batch |
| 4, 5 EN caption | `youtube-4HGNqFdaD34`, `youtube-n6wpNhyreDE` | **not run** (stopped at case 3) | not judged |

What was **not** done: case 4 and 5; a case that observes the new hold and retry behaviour on a real `partial` item (the run
called the correction directly, so the item carries no `transcript_correction_unresolved` marker); the A12 check, because this
machine has no browser (Chrome, Edge or Playwright is not installed).

**P1 found by case 3 (fixed in the working tree, not yet reviewed).** The captured raw answers show the cause. Batch 1 (24
cues) came back valid (`finish_reason: stop`, 869 completion tokens, every number kept as written). The next batch was refused with
HTTP 429 (OTPM: limit 1000, used 829, requested 2048); the provider learned its limit from that refusal, so its reservation
cap fell to 500, and the retry after the 16 s wait asked for `max_completion_tokens: 500` for the **same 24-cue batch**. The
answer was cut off (`finish_reason: length`, 13 of 24 rows, the last rows merged and wrong) and was correctly refused as
`malformed_result`. The correction batches were a fixed 24 cues, not sized to the output-token allowance that translation
already respects, so on a model with a low output allowance most long items would end `partial` or `failed`. No unsafe text was
accepted: the refusal worked as designed.

Fix: `estimate_correction_output_tokens` (28 tokens per cue plus 0.6 per UTF-8 byte, rounded up from the measured 869 tokens
for 630 bytes) and `fit_correction_batch` cut each batch to the provider's `batch_output_ceiling()`, read again at every
attempt including the retry after a rate limit; cues that do not fit return to the front of the queue, none is dropped, and an
unknown allowance leaves the batch as it was. Tests: 51 short ZH cues under a 500-token allowance all return in order and end
`applied`; the allowance learned after the first refusal narrows the retry; an unknown allowance keeps `[24, 6]`; a batch always
keeps at least one cue; the estimate is not below the measured 869.

Local execution (not CI), disposable container (read-only repository, tmpfs databases, provider keys empty, 1 GB / 1 CPU, host
RAM 1.72 GB, above the owner's 1 GB floor): media set plus `tests/test_admin_console_routes.py` and
`tests/test_admin_authorization_matrix.py` **1260 passed, 0 failed, 21 skipped**. Ruff on touched Python, Node admin media
review, Node admin areas, browser ESM graph (300 modules): PASS.

**Gates still open.** Live benchmark: cases 3, 4 and 5 must be re-run on code that carries this fix (`:8021` needs another
restart; it mounts the repository, so a restart is enough), and the new hold/retry behaviour needs one real observation. This fix
changes behaviour, so it needs an independent re-review; the implementer cannot approve it. A12 visual check is open. PR #261
stays Draft.

## Review of `4a957730` (batch sizing): REQUEST CHANGES, P1 and P2 fixed

Independent review (read-only, no code run) of `4a957730`: **REQUEST CHANGES, one P1 and one P2**. CI #826 on that SHA was
`success` (reported by the reviewer); CI does not make the P1 go away. The first batch-sizing fix is otherwise confirmed:
the queue/remainder logic loses no cue, the estimator is above the measured 869 tokens and has a regression test, and nothing
adds a schema, env flag, provider, hardcoded id or language hack.

- **P1 - the ceiling ignored the per-request completion cap (fixed, not yet re-reviewed).** The pipeline asked only
  `batch_output_ceiling()`, which is `None` until the provider has learned an output allowance from a refusal. The real
  provider always has `max_completion_tokens` (default 2048) per request, so while the allowance was unknown a long batch
  (up to 6000 source characters, estimated near 4270 tokens) was still sent whole and cut off (`finish_reason: length`) on the very
  first request. The old test "an unknown allowance leaves the batch as it was" encoded that gap, because its fake had no request cap.
  Fix: `GroqTranslationProvider.correction_output_ceiling()` returns exactly what `correct` reserves (`_reservation_cap`, the smaller
  of the configured request cap and, once known, the per-request share of the allowance), without changing the translation
  contract; the pipeline reads it through `correction_ceiling()` (it falls back to `batch_output_ceiling`, ignores anything that is
  not a positive integer, and treats a broken provider as "no ceiling") at every attempt.
- **P2 - a single cue larger than the ceiling was still sent (fixed).** `correction_cue_fits()` finds it; the cue is not sent, keeps
  its raw text and is recorded as rejected with the new code `cue_too_large` (the state is `partial`). The code has words in EN, VI
  and ZH in A12, and the Node gate checks them.
- Tests (12 new, one replaced): the effective ceiling is the smaller of the request cap and the allowance share (500 cap, default
  2048, learned 1000 -> 500, 100000 -> 2048, 300 vs 1000 -> 300); with the allowance unknown a 500 cap splits before the first request;
  with the allowance unknown and the default cap a batch estimated above 2048 splits; learned 1000 gives the live case ceiling 500 and 51 cues all
  return `applied`; one oversized cue is never sent and the other three are corrected; a cue that fits is never skipped; the ceiling
  reads only a positive integer and survives a broken provider. The replaced test now says only a fake can be silent about its limits.
  The fake used by the new tests wraps the **real** provider's sizing and asserts every request's estimate stays under its ceiling.

Local execution (not CI), disposable container (read-only repository, tmpfs databases, provider keys empty, 1 GB / 1 CPU, host RAM
1.35 GB, above the owner's 1 GB floor): media set plus admin route tests and `tests/test_groq_translation_bounds.py`
**1284 passed, 0 failed, 21 skipped**. Ruff on touched Python, Node admin media review, Node admin areas and browser ESM graph (300 modules): PASS.

Still open: independent re-review of this fix; the live benchmark on `:8021` (cases 3, 4, 5, one real hold/retry observation; `:8021`
still runs `5ca4ac43` and needs a restart) and the A12 visual check. PR #261 stays Draft.

## Review of `fc728b6f`: APPROVE; the live re-run then found a second refusal form (fixed, not yet reviewed)

Independent review of `fc728b6f`: **APPROVE, no P0, no P1**, one bookkeeping/docs P2 (its text was not given to the implementer; not
claimed closed). CI #829 on that SHA was `success`, checked with `gh` by the implementer. `:8021` was restarted on it (it loads
`correction_ceiling` and `correction_output_ceiling`) and cases 3-5 were started within the owner's approval (USD 0.10 cap, no new
item, no publication, rights unchanged). **Case 3 stopped the run at the first anomaly; cases 4 and 5 were not run.**

Case 3 (HSK1, 51 cues) on the new code: `partial` (`rate_limited`), 90.6 s, USD 0.0038; 5 edits accepted (punctuation, 他 -> 她 three times),
0 rejected, the three cues with numbers (18, 38, 35) unchanged. The earlier cut-off answers (`finish_reason: length`) did **not** recur.
Total spend on the benchmark batch: **USD 0.0207** of 0.10. Stored text, status and rights are unchanged; the temporary marker was removed.

Cause of the stop, from the recorded raw answers replayed offline through the provider's own parsing (no provider call): Groq refuses an
output allowance in **two forms**. The form seen before, `Rate limit reached ... (OTPM): Limit 1000, Used 829, Requested 444`, carries a
`Used` count and the provider learned its limit from it. The form seen now, `Request too large ... (OTPM): Limit 1000, Requested 1816.
The request's expected output tokens exceed the enforced limit; reduce max_tokens`, has **no `Used`**: `_OTPM_REFUSAL` did not match it, the
limit was never learned, the ceiling stayed at the request cap of 2048, and every attempt sent the same 24 cues and was refused again
(calls 1, 3 and 4 of 4). The estimate for a request is the cap Groq prices (1816 expected for the 24 short cues, 869 written), so only learning the limit
shrinks the request. This is not specific to correction: translation shares `_learn_from_refusal` and had the same gap since D-218.
My earlier test only knew the first form, so it could not catch this; that was the test's gap, not the data's.

Fix (not yet reviewed): `_otpm_request_too_large()` reads `Limit N, Requested M`; `_learn_from_refusal()` learns the limit from it and
nothing else (no `used` to sync and no window to block: a request that was not admitted spent nothing of the minute), and returns the asked wait
unchanged, so translation is unaffected; the correction path reports this refusal as `request_too_large` with no wait instead of
`rate_limited`, and the pipeline retries it **once, at once** (no sleep, no draw on the 150 s allowance) only when the re-read ceiling
really narrows the batch, so it never repeats a request that would be refused the same way. The window-full form keeps its wait,
its sync and its single bounded retry. Tests (`tests/test_media_groq_refusal_forms.py`, 7): the two recorded sentences verbatim (organisation id as
recorded) are each read and not confused; the too-large form learns the limit (ceiling 500) with no wait and nothing blocked or used; the window-full form still
waits and syncs; translation's shared path learns it and returns the asked wait; through the real provider HTTP path a too-large refusal is retried at once with
a smaller batch (no sleep, cap at most 500, every cue asked once more, each provider wait within 90 s and 150 s in total); a single cue refused as too large is not
retried; the window-full refusal keeps its named wait and one retry. The HTTP-path tests run on a virtual clock after the first draft of one waited a real minute inside
the provider's own pacing and was killed by a test timeout - a test defect, now fixed.

Local execution (not CI), disposable container (read-only repository, tmpfs databases, provider keys empty, 1 GB / 1 CPU, host RAM 1.23 GB,
above the owner's 1 GB floor, `--timeout=60`): media set plus admin route tests and `tests/test_groq_translation_bounds.py`
**1291 passed, 0 failed, 21 skipped**. Ruff on touched Python, Node admin media review, Node admin areas and browser ESM graph (300 modules): PASS.

**Still open:** independent review of this fix; re-run of cases 3, 4 and 5 on `:8021` (needs a restart after the review), one real hold/retry observation; the A12 visual check
(this machine has no browser); the bookkeeping P2 of the `fc728b6f` review; the five first-review P2 findings (no recorded text). PR #261 stays Draft; neither gate has passed.

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
