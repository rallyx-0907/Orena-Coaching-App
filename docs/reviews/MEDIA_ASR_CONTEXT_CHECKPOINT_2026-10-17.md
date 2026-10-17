# Media ASR context and transcript review — 2026-10-17

MILESTONE=Video Sources Phase 2 / ASR A+B and EN caption cleanup
STATUS=IMPLEMENTING
BRANCH=claude/media-asr-context-corrections
BASE=2cb555ddcd5cc36b14c4fc731f74c341d32a1633
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
- One attempt per bounded batch, existing configured media Groq provider/model and output allowance,
  per-call spend check and actual-usage accounting. No fallback or automatic retry. Failure or absent
  configuration preserves raw text held for review, before translation/publication.
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

## Exact changed files and memory transaction

Code/tests: `app.py`; `writing_coach/speech_asr.py`; `writing_coach/media_transcript_pipeline.py`;
`writing_coach/media_transcript_quality.py`; `writing_coach/media_translation.py`;
`writing_coach/media_source_import.py`; `static/orena/screens/admin/content-pages.js`;
`static/orena/screens/admin/copy-content.js`; `scripts/test_groq_speech_asr.py`;
`scripts/test_media_transcript_quality.py`; `scripts/test_orena_admin_media_review.mjs`;
`tests/test_speech_asr_url.py`; `tests/test_media_pipeline_integration.py`;
`tests/test_media_translation_groq.py`; `tests/test_quota_media_import.py`;
`tests/test_speech_transcribe_guard.py`.

Memory/evidence: this checkpoint; `docs/project/CURRENT_HANDOFF.md`;
`docs/project/CURRENT_PRODUCT_STATE.yaml`; `docs/product/ORENA_STATUS.md`.
`PROJECT_STATE.md` unchanged. No Decision Log entry: bounded implementation of the explicit owner approval,
with existing architecture/provider/publication contracts retained. No production/deployment operation.
The owner-dirty Design Contract and untracked `.agents/`, UX review docs/evidence are excluded from staging.
