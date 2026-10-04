# Intelligence lane: reconciliation on the D4 baseline

**Lane:** `feature/orena-intelligence` at `9012af7` (merge of `codex/work` `8640338`). **Date:** 2026-10-01.
**Method:** read-only audit plus host-side gates. No Docker, no PostgreSQL, no pytest were run here (the lead's SQLite
pytest, 3504 passed / 348 skipped, is the only suite evidence). Nothing in the contract or learner UI was edited.
**Status:** audit record, not a verdict. It is not CI evidence and not an independent review (D-107 point 6).

`codex/work` has moved since `8640338` by four documentation-only commits (D-107, ACCOUNT_RECORD_LIMITS rev 4/5 and its
review). Nothing in them changes code this lane reads; the lane has not yet merged them (D-107 itself is absent from
this worktree's DECISION_LOG).

## 1. Host-side checks (local execution)

| Check | Result |
| --- | --- |
| `python scripts/validate_project_memory.py` | exit 0 |
| `python scripts/validate_architecture.py` | exit 0 |
| `node --experimental-vm-modules scripts/validate_browser_esm_graph.mjs` | exit 0 |
| every `node scripts/*.mjs` named in `.github/workflows/ci.yml` (122 gates, including `test_orena_agent.mjs`) | 122 of 122 exit 0 |
| working tree afterwards | clean (the gates wrote nothing) |

Not run on the host (need dependencies the host lacks): the `python scripts/test_orena_*.py` gates in `ci.yml` and all pytest.

## 2. Per-gap state (UI_BACKEND_GAPS.md section I, written 2026-09-27/28)

"Resolved by D4" below means a D4 store now exists that could back the tool; no gap is closed by the merge alone, because
no Intelligence code reads any D4 store yet. Every I-row is therefore still open as a *tool*; the table says what changed
underneath it.

| Gap | Pre-merge claim | State on this baseline | Evidence |
| --- | --- | --- | --- |
| I-1 `get_learning_weaknesses` | built (Slice 3), counts only | **changed**: still built and correct in shape, but its listening count now rests on rows whose score may be client-sourced (finding F-2); grammar still null | `agent/coaching.py:222`; `listening_progress_policy.py:24`; migration `20260930_0020` |
| I-2 `get_tone_analysis` | no measured tone | **open, unchanged**. D-103 point 5 approves Azure/ASR for lane E2E only; it adds no tone measurement | `agent/tool_plan.py` (gap); `DECISION_LOG.md` D-103 |
| I-3 `get_stress_analysis` | no per-word stress | **open, unchanged** | same |
| I-4 `get_grammar_mistakes_summary` | completion only | **changed, still open**: grammar progress now stores `last_quiz_correct/total/at` (migration 0023, `learning_repository.py:39,416`), but D-104 H-4 / `clean_quiz_result` call the number client-reported and "never read as evidence". Try-it-yourself belongs to the Writing record. Not a usable mistake store | `learning_repository.py:44-58` |
| I-5 `get_reading_mistakes` | no public per-question read | **open, unchanged**: `ReadingEvidenceRepository` is untouched by the merge; `list_evidence` still returns scores only | `reading_evidence_repository.py:1053` |
| I-6 `get_word_context_in_reading` | no sentence-from-content service | **open**. Partially addressable only for *kept* words: `GET /api/library/vocabulary/{word}/provenance` returns source and sentence (D-104 provenance), but it sits behind `ORENA_ACCOUNT_BACKBONE` (default off) and is learner-owned data needing its own review before an agent reads it | `account_records_api.py:395`; `provenance_repository.py:236` |
| I-7 `get_listening_mistakes` | dictation comparison runs in the client | **changed, still open**: the server now scores dictation (`dictation_evaluator.py`, `listening_api.py:655-670`) and stores `last_answer` and `score_source`, but it stores a percentage and `exact`, no mismatch list. `resolve_progress_line` (`listening_api.py:603`) plus `last_answer` would let a deterministic diff be built; that is a Listening-owner decision | `listening_progress_policy.py`; `specialized_repository.py:1537` |
| I-8 `ability()` writes | read via `list_evidence` | **unchanged** (file untouched) | `skill_tools.py:` reading progress |
| I-9 listening lesson route translates and writes | catalogue only | **changed**: `stored_media_entry` is now owner and language gated through `media_library_store.visible_to` (`listening_api.py:115-132`, `media_library_store.py:100`), so a pure, safe read of an owner's imported media exists. The agent still reads the curated catalogue only (`app.py:733`), so imported and `url:`/`upload:` items answer "no such lesson" (finding F-5) | |
| I-10 `word_detail.py` provider call | catalogue and card builders | **unchanged** | |
| I-11 to I-15 contract payloads | resolved by contract v2 (D-092) | **resolved, unchanged**. Word keys are still text under the session language; the merge adds nothing to saved-word ids | |
| I-16 read-by-id of an attempt | missing (N-9) | **open, unchanged**: `list_speaking_attempt_records` only gained a `since` filter | `specialized_repository.py` diff |
| I-17 capability keys reserved | legacy active selection | **unchanged**: `agent_turn_fast` still `configurable=False` (`ai/capabilities.py:192`). Admin's AD-6 status ("learner evaluator still uses legacy routing") is true of the agent too; the Admin UI must not imply otherwise | `ai/platform.py:333` |
| I-18 streaming shape not verified live | provider | **open [PROVIDER]**, needs the live run | `scripts/agent_live/` |
| I-19 voice / TTS | not approved | **open, unchanged** | |
| I-20 metering | `agent.turn`, `agent.tokens` | **unchanged in code**; new note F-7 on deletion enumeration | `product_repository.py:61` |
| I-21 fallback | none | **unchanged** | |
| I-22 route health, Gemini 429 | quota | **open [PROVIDER]**, activation decision | |
| I-23 identity answers | resolved | **resolved, unchanged** | |
| I-24 rate limit | in process | **open for deployment** (per worker); note ACCOUNT_RECORD_LIMITS proposes account-level rails, which are separate from the agent limiter | `agent/ratelimit.py` |
| I-25 capability status | active list | **unchanged**; `home.overview`, `progress.overview`, `library.find`, `preferences.agent_memory` still `pending`. D4 now offers inputs for some (finding F-8) | `agent/capabilities/*.json` |

The rest of section I (Admin rights, D4 slice notes, QA rounds) is codex/work's record carried by the merge. It is not an
Intelligence gap list and is not re-audited here.

## 3. Integration breakages and risks

Severity follows REVIEW_POLICY: P0 data loss or cross-learner leak, P1 wrong learner-facing answer or security, P2 wrong
under a stated condition or test that cannot pass, P3 polish or watch item.

No P0 and no P1 was found. No cross-account or cross-language read path was found: every agent read goes through the
request context the turn sets (`agent/turn.py:119-127`), the turn is refused with 409 when the target language differs from
the session's (`agent/api.py`), and the stores the agent reads are all scoped by `(user, language)`.

| # | Sev | Finding | Where | Reasoning / repro |
| --- | --- | --- | --- | --- |
| F-1 | P2 | A PostgreSQL agent test cannot pass on the D4 schema | `tests/test_agent_tools_postgres.py:210-231` | The test saves progress with `best_accuracy_percent=100, best_exact=True, last_answer=""` and no `score`, then asserts `exact_count == 1`. Since D-103.2, `merge_progress(stored, values, None)` (`listening_progress_policy.py:24-37`) ignores client `best_*` and returns `best_exact=False`. The assertion fails when the test runs. SQLite pytest skips the file, which is why the merge looked green. Fix is in the test: pass a server `score` (`{"accuracy_percent":100,"exact":True}`) through the repository |
| F-2 | P2 | The agent states client-sourced dictation scores as facts | `agent/skill_tools.py:318-319,342`; `agent/coaching.py:222` | `_listening_progress_payload` now carries `score_source` (`specialized_repository.py:1547`), `"client"` for every row written before D4 (H-14: not verified, superseded by the next server result). `get_listening_attempt` and the weaknesses count report `best_accuracy` and `exact` without it, so "you got this line exactly" may rest on a number nobody verified. Fix: return `verified` from `score_source == "server"` and leave unverified numbers out of counts and evidence |
| F-3 | P2 | Navigating to a grammar point opens a screen that cannot resolve the id | `agent/grammar_tools.py` (R5 ids); `app.py:2179,2241`; `static/orena/agent/intents.js:30`; `screens/grammar-concept/model.js:4` | The agent returns R5 Concept IDs. D-100 retired R5 as the source, and the Grammar Concept screen reads a test-only fixture. D-101 F says old R5 ids redirect through Grammar Lab provenance once the content store exists; until then `navigate grammar.point{R5 id}` lands on not-found. Recorded dependency (contract bump per D-100 point 5), not a regression. Needs the contract bump and the grammar store |
| F-4 | P3 | "N words due" can exceed what the review screen shows | `agent/read_tools.py` `_due_review_summary`, `agent/coaching.py:134` | D4 stores `review_limit_per_day` and `review_new_per_day` (`account_profile.py`, `becoming_memory.py:121`); the cap is applied client-side (`static/orena/product/recall-modes.js`). The agent reads the raw server due count. Honest wording ("due now") is correct; a reply that promises "N cards today" would not be |
| F-5 | P3 | Imported or personal media is invisible to the agent | `app.py:733-737`, `agent/skill_tools.py:266` | `listening.workspace` is also opened on `url:`/`upload:`/personal ids (media-source.js, D4 acceptance 1). The agent resolves curated catalogue ids only. Safe (no leak), but "no such lesson" is wrong for an item the learner is looking at. `stored_media_entry` is now an owner-gated pure read that could serve it |
| F-6 | P3 | An agent session survives a language switch | `agent/context.py:76`, `agent/session.py:93` | The session is keyed by `user_key` only. After D4's `adoptLearningLanguage` the same `session_id` can resolve "this word" from `last_selected_entity` of the other language. Each request is still language-checked (409), so tools read the right language; only the carried selection is stale |
| F-7 | P3 | `usage_events` rows written by the agent are not in the D-055(b) deletion enumeration | `agent/runtime.py` meter; `models.py:474`; `persistence/deletion_enumeration.py` | The `users` row survives deletion, so the `ON DELETE CASCADE` never fires; `deletion_enumeration.py` lists D4 tables only. Rows hold counts and a request id, no content. The deletion workflow author must decide; this lane adds a table-less writer, so it needs no migration |
| F-8 | P3 | Stored reviews may be pre-v2.7 | `app.py:_agent_writing_review`, `essay_review` | `get_current_writing_evaluation` quotes the stored review. D-103.7/H-15 refresh stale Chinese reviews in the UI path, and an essay whose identity cannot be proved is served as stored. The tool does not tell the model the review may predate the current evaluator |
| F-9 | P3 | Content-id namespaces are unreconciled | `agent/skill_tools.py:_content_parts`; `static/orena/screens/listening/model.js:28-31` | The UI uses `media:<id>` for continuation and discovery but the raw lesson id as the listening route id; the agent accepts raw lesson ids only. The UI bridge does not yet publish `content_id` per screen (`agent-bridge.js`), and `AGENT_LIVE` is `false` (`transport.js:14`), so this has not been exercised. Must be fixed in one place, with the contract's §6.1 as the owner |
| F-10 | P3 | Watch: Speaking persistence is about to change | D-104 required follow-up, `UI_BACKEND_GAPS.md` | Spoken Free Talk, Situation and React takes will become audio-free speaking attempts with null pronunciation. `_attempt_summary` tolerates missing dimensions, but `speaking_progress` averages and `get_pronunciation_history` need re-checking when it lands |
| F-11 | Info | Shared-file footprint for reverse integration | `git diff --stat 8640338 HEAD` | Beyond `writing_coach/agent/`, the lane edits `app.py` (agent wiring), `ai/providers.py` (+204, streaming), `ai/platform.py`, `ai/capabilities.py`, `ai/base.py`, `ai/pricing.py`, `persistence/product_repository.py`, `product/repository.py` (`daily_usage`), `.env.example`, `scripts/voice_spike/*`, `docs/project/{AGENT_SPEC,CURRENT_HANDOFF,UI_BACKEND_GAPS}.md`. The three docs will conflict on any merge back. `ai/providers.py` changes the path every learner AI call takes |
| F-12 | Info | `codex/work` working tree is mid-change in code the agent calls | `becoming_library.py` (`source_kind` pattern widened), `media_library_api.py`, `work_repository.py` | Uncommitted on codex/work; the next merge-forward must re-run the agent's vocabulary tests against it |

What the agent writes: nothing learner-owned. It keeps a per-process session cache (`agent/session.py`) and, per completed
turn, two usage rows (`agent.turn`, `agent.tokens`). It never touches `works`, `work_turns`, annotations, imports,
responses, provenance, continuation places or account settings. Orena conversation history and agent memory stay
device-side, which matches D-104 ("Orena conversation/history persistence" remains deferred).

Reads confirmed unaffected by D4, by inspection: `library_summary`, `list_library_vocabulary`, `saved_vocabulary_state`,
`catalog_entry_for` (`becoming_library` untouched by the merge; D4 place rows are excluded from saved listings by
`_place_only`, `library_repository.py:62`); `essay_review` and `api_error_memory` (scope-checked `get_essay`);
`list_speaking_attempt_records`, `speaking_progress`; reading evidence and article reads; learner summary composition.

### Opportunities (not breakages; each is a product or contract decision)

- F-O1 `declared_level` is now stored per learning language. The snapshot omits `current_level` by ruling (2026-09-27, R4);
  exposing a *declared* level labelled as such is a product decision.
- F-O2 `/api/learner-activity` (`learner_activity.py:compute_activity`) gives a real streak and the ISO week from server
  records, with the learner's timezone. It could back `progress.overview`; the agent has no timezone input today.
- F-O3 `GET /api/essays/{id}/review/history` and `list_essay_review_history` give an earlier review, which could back a
  "what changed since the last review" answer.
- F-O4 `surfaces.json` carries names only (24 entries, no purposes); purposes wait on the UI lane (§6.2).

## 4. PostgreSQL and live-runtime dependence of the Intelligence tests

| Needs | Tests | Notes |
| --- | --- | --- |
| PostgreSQL (`ORENA_TEST_POSTGRES_URL`, throwaway DB, runs Alembic head) | `tests/test_agent_tools_postgres.py` (6 tests: writing history scoping, grammar completion scoping, speaking attempts, listening progress, reading context and progress, snapshot and weaknesses) | Skipped in the lead's run, so the agent has had **no PostgreSQL proof on migrations 0017-0023**. F-1 means one of the six is expected to fail |
| PostgreSQL, D4 reads the agent shares | `tests/test_d4_listening_authority.py`, `test_d4_grammar_quiz.py`, `test_d4_review_refresh.py`, `test_d4_profile_account.py`, `test_d4_continue.py`, `test_reading_evidence_postgres.py` | codex/work's tests; run them on the merged tree because the agent reads the same repositories |
| Live provider ([PROVIDER] gate, `--approved --cap-usd`) | `scripts/agent_live/run.py` (not a pytest) | Needs the human's approved cost cap and the `gemini-text` lock; `test_agent_live_runner.py` and `test_agent_live_lock.py` are hermetic fakes |
| Neither (hermetic) | all other `tests/test_agent_*.py`, `test_ai_agent_stream.py`, `scripts/test_orena_agent.mjs` | Included in the lead's SQLite run and the 122 Node gates |

## 5. Proposed E2E plan (not executed)

**Runtime.** The lane's own throwaway stack, `scripts/agent_live/compose.yaml` (project `orena-agent-live`, :8013 or :8015,
PostgreSQL 17 on tmpfs, `alembic upgrade head` once, no volumes). Never :8000, :8010, :8011 or :8021. One lane operates
Docker at a time (AGENTS section 10), so the lead must schedule it. The image `ai-writing-coach:local` must be built from
this worktree first.

**Environment.** `APP_ENV=development`, `AGENT_ENABLED=true`, `PERSISTENCE_BACKEND=postgresql`, sign-in off (the one
development learner), `OLLAMA_URL` unreachable, Gemini selected through `PUT /api/admin/ai/config`
(`gemini-3.5-flash-lite`), key only as a boolean check. Two variants of the same pass: `ORENA_ACCOUNT_BACKBONE` off (the
compose default) and on, to prove the agent's reads are invariant to the backbone. Add `ORENA_TEST_POSTGRES_URL` pointing at
the same throwaway server for the pytest pass.

**Order.**
1. Fix nothing yet. Run `tests/test_agent_tools_postgres.py` and the D4 PostgreSQL files above against the throwaway DB.
   Expect F-1 to fail; record the actual set.
2. Seed per language through the real routes, as one learner, EN then ZH (switch with `POST /api/platform/language` and keep
   the cookie): save 3 words (one due), submit one essay with errors and one refresh (`/api/essays/{id}/review/refresh`),
   write dictation progress through `POST /api/listening/progress` (server-scored) *and* one legacy row with
   `score_source='client'` inserted by SQL to exercise F-2, one speaking attempt with a flagged word, one reading attempt,
   one grammar completion with a quiz result, one imported media item.
3. Drive `/api/agent/*` with the Node live transport (`static/orena/agent/transport.js` `liveTurn`, fetch injected to the
   sandbox) so the UI's real client code, not a Python stand-in, reads the stream. `AGENT_LIVE` stays `false` in the
   source; the harness calls `liveTurn` directly, which needs no UI edit.
4. Flows, each in EN and ZH (target `en` / `zh-CN`, interface `en` / `vi` / `zh-CN`):
   - D-101 G list: capabilities 404 with the agent off; SSE turn; `409 target_language_mismatch`; `429` with `Retry-After`;
     `context.address`; actions offered, never claimed; the opening turn from real data.
   - Tool reads: due words, saved state, word detail, writing evaluation and feedback and history, grammar point and search,
     pronunciation history/attempt/word, listening context/attempt, reading context/progress, snapshot, weaknesses, next
     activities.
   - Isolation: a second account is not available without sign-in, so isolation stays on the PostgreSQL pytest
     (`learner_context` with two learners and two languages, already written) rather than E2E.
   - Language switch mid-session (F-6), review-limit wording (F-4), `media:`/`url:` ids (F-5, F-9), grammar navigate (F-3).
5. Check metering rows (`agent.turn`, `agent.tokens`) and that no D4 table gained a row from an agent turn (works, library_items,
   language_provenance counts before and after).
6. Live provider pass last, under the human's cap and the lock (`run.py --approved --cap-usd ... --flows coaching,notes`),
   to close I-18/I-22 for the provider actually selected.

**Evidence to keep:** commands and exit codes, the per-flow result JSON outside the repository (`--out`), the row counts of
step 5, and which flows used EN vs ZH. Label all of it local execution.

## 6. What must be true before reverse integration (Intelligence to codex/work) can be reviewed

D-107 point 6: not before Intelligence tests and E2E, and an independent review, pass on this D4 baseline.

1. This lane merges `codex/work` forward again (D-107 and the limits proposals; plus any commit made by then) with no
   conflict left in `app.py`, the three docs, or `ai/*`, and `AGENT_CONTRACT.md` unchanged by this lane.
2. The PostgreSQL agent tests pass on Alembic head including 0017-0023, after F-1 is fixed in the test (a lane test edit,
   not a contract or UI edit). Local PostgreSQL results are labelled local execution; CI has no PostgreSQL service.
3. F-2 is fixed (a score that is not server-verified is not stated as fact), or recorded as a human-accepted limit.
4. F-3 and F-9 have an owner: the contract bump for Grammar Lab ids and the content-id grammar are codex/work decisions
   (D-100 point 5). The lane must not choose them.
5. The E2E of section 5 has run on the throwaway stack, EN and ZH, with the backbone off and on, and the live provider pass
   has the human's approved cap (I-18, I-22).
6. The static gates stay green after the merge-forward: `validate_project_memory`, `validate_architecture`, the ESM graph,
   all `ci.yml` Node gates, and the full pytest in the image.
7. An independent architecture review of the shared-file footprint (F-11), above all `ai/providers.py`, `ai/platform.py`,
   `product_repository.daily_usage` and the `app.py` wiring, by someone who did not write them (AGENTS section 1).
8. `UI_BACKEND_GAPS.md` section I is rewritten against this document by the owner of that file (codex/work for the shared
   copy). This file does not edit it.
9. Activation stays a separate human gate: production never serves the agent (`agent/api.py:agent_enabled`), and
   `AGENT_LIVE` is flipped only on :8011 after the merge (D-101 G).

## 7. E2E run on the throwaway stack (2026-10-04, local execution)

`python scripts/agent_e2e/run.py` on `812c557` + the E2E scripts (merge of `codex/work` `88b1c81`): project
`orena-agent-e2e` on :8016, PostgreSQL 17 on tmpfs at Alembic head, sign-in off, **no provider reached** (no key set,
nothing billed). Each stack was taken down after its pass.

| Pass | In-container harness (real app, real routes, scripted provider) | UI client (`transport.js` `liveTurn`, real HTTP) |
| --- | --- | --- |
| agent on, `ORENA_ACCOUNT_BACKBONE` off | 69 / 69 | 5 / 5 |
| agent on, `ORENA_ACCOUNT_BACKBONE` on | 69 / 69 | 5 / 5 |
| agent off | - | 2 / 2 (capabilities 404, a turn is `absent`) |

What the harness covers, in EN and ZH: seeding through the routes (words, a server-scored dictation line, grammar
completion) or, where the route needs a provider, through the same repository under the same request context (an
essay review, a scored speaking take, a legacy client-scored dictation row, a reading set and attempt); every read
tool through `POST /api/agent/turn` (19 tools; a refused or failed read is a failure); the data each tool read is the
learner's own in the turn's language (writing history, speaking attempt, saved words, reading) and the other language
sees nothing; F-2 holds (a client-scored line reads `verified: false`, `exact: null`); 409 on a target mismatch; S15
identity in the learner's address; a language switch on the same session (F-6) answers; 429 with the turn budget
spent; no row added to `works`, `work_turns`, `library_items`, `language_provenance` by agent turns, and metering rows
written (`usage_events` +78). The UI client checks the same S15/409/429 statuses through its own live path.

Not covered here: the live provider pass (I-18, I-22), which needs the human's approved cap; isolation between two
accounts (sign-in is off; it stays on the PostgreSQL pytest); F-3, F-4, F-5, F-9 (recorded decisions or dependencies).
Results JSON outside the repository.
