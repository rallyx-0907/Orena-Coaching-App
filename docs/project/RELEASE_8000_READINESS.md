# Release readiness: merging `codex/work` into `main` and running it on :8000

Date: 2026-10-07. Author: Claude lane. Read-only analysis of the repository at `8875df48` (`codex/work`, 875 commits
ahead of `origin/main` `7ff6985e`, 2026-09-14). No runtime, container, database or `.env` was read or changed; :8000 and
:8010 were not touched. Local runs are labelled local; CI has not been run on this branch.

The question: the :8000 container has run fine with its configuration; what is still unfinished before this branch goes
to `main` and runs there? This document decides nothing. It lists what is true, what blocks, who owns each step and
which human gate each step needs.

## Decided 2026-10-08 (D-146) - :8000 is staging, not production

:8000 and the public domain are **public, product-like staging** (`APP_ENV=staging`), for real-user testing; there is no
final production runtime yet. Where this file says "production" about :8000 below, read "public staging": the public
security requirements still apply, but no approved learner capability is held back because :8000 is public. Each
capability follows its own flag; `AGENT_ENABLED` is the Orena Intelligence switch (the old "never in production" rule
is retired). Proposed :8000 env: `APP_ENV=staging`, `AGENT_ENABLED=true`, `AGENT_VOICE_ENABLED=false`.

**Staging deployed 2026-10-08 (human decision after #101/#102):** `main` 5045fe74, image `orena:main-5045fe74`, schema
0029 (no migration). Deploy path: `scripts/staging_8000_deploy.ps1 -Image orena:main-<sha>` (web + `reading-worker`, same
image, same env). Runtime env: `%LOCALAPPDATA%\orena-product\staging-8000
untime.env`, operator-owned, outside Git,
ACL to the operator. Flags: `APP_ENV=staging`, `ORENA_ACCOUNT_BACKBONE=on`, `ORENA_PRACTICE_SESSION=on`,
`AGENT_ENABLED=true`, `AGENT_VOICE_ENABLED=false`, `AGENT_DAILY_SPEND_CAP_USD=1`, `AI_RUNTIME_MODE=capability`,
`PRONUNCIATION_PROVIDER` empty (Azure when configured). Provider credentials: Gemini and Azure Speech in the env file; a
:8000-own `AI_PROVIDER_SECRETS_KEY`. AI routing rows (`ai.active_selection`, eight `ai.capability.*`) mirror :8021
(gemini-3.5-flash-lite). Content: the S1 reading pack (4 sources, 30 EN + 22 ZH texts) promoted by content pack, sources
approved in Admin, 52 jobs consumed by the worker, all published. Media has no content-pack path yet.

## Decided 2026-10-08 (D-143) - read this first

The human decided B1-B5; sections below are the analysis they were decided on and are kept as written.

- **Shape:** one UI. The cutover is finished before the :8000 release: `/` runs the new UI; old paths still needed are
  ported or redirected, the rest deleted and tombstoned. Shapes A and C of section 4 are superseded.
- **0016:** :8000 takes it; legacy Reading rows stay in the read-only archive, nothing is converted.
- **Chain:** one production migration pack, rehearsed on a restored copy of :8000, reviewed by the human before any
  apply. Built: `docs/project/proposals/PRODUCTION_MIGRATION_PACK.md` (`scripts/product_migration_pack.py`), local
  synthetic evidence only; waiting for a :8000 backup taken by the human, its rehearsal, and the human's review.
- **First release:** `ORENA_ACCOUNT_BACKBONE=off`, :8000 invitation-only. B3/B4 do not block the controlled trial;
  they block a public release.
- **Release path (D-144):** candidate on `codex/work` -> restored-copy rehearsal -> human review -> PR, CI green ->
  `main` -> image from the exact `main` SHA -> final backup, rehearsal of it, authorized apply on :8000 -> smoke.
- **Rehearsal of :8000 done 2026-10-08 (PASS, evidence in `PRODUCTION_MIGRATION_PACK.md` 4b):** :8000 is at
  `20260828_0004` (not 0005 as section 1 assumed), so the chain is 21 revisions.
- **Observed on :8000 (read only):** its web container runs code bind-mounted from the `...-claudecode` worktree
  (`app.py`, `static/`, `templates/`, `writing_coach/` ...) on image `ai-writing-coach:local`. D-144 replaces this
  with an image built from the exact `main` SHA, with no source mounts.
- **Released 2026-10-08 (human authorization; historical, superseded by the staging deployment above):** final v3 backup `20261008T042406Z` rehearsed with `main` 6d7ebff0
  (PASS), then in a maintenance window (web stopped 04:36Z, no other session) the pack's preflight passed and the
  chain 0004 -> 0029 was applied: `verify_after` ready, rows kept, legacy Reading 14/1 frozen by 4 triggers, chain
  `65044f6e...` and execution `d418c352...` digests. The smoke of image `orena:main-6d7ebff0` found
  `/orena-brand/logo/*` 404 (the Dockerfile copied no `assets/`); fixed by PR #98, released as **`main` a2342e62,
  image `orena:main-a2342e62`**, no source mounts, only the `ai-writing-coach-data` volume; backbone and practice
  session `off`, billing/agent unset. Access restored 05:20Z. The old container is kept stopped as
  `ai-writing-coach-writing-coach-1-before-6d7ebff0` (restart `no`; it cannot run on the new schema). At that
  release, still open for the operator: `PRONUNCIATION_PROVIDER` was `demo`, no `reading-worker` ran, the agent was
  off. All three were resolved by the staging deployment of `main` 5045fe74 (above: Azure pronunciation, the worker,
  the agent on). Invitation-only is not in the application (any verified Google account signs in); it rests on the
  OAuth/Cloudflare configuration. Migration record: `proposals/PRODUCTION_MIGRATION_PACK.md` section 4c.
- **Runtime policy:** no new persistent runtime; :8021 dev/QA, :8000 product-like acceptance, rehearsal disposable.
- **Correction (2026-10-08 inventory):** the Admin console already exists in the new UI (`#/admin/*`, `screens/admin/*`,
  on `Orena Admin.dc.html`); sections 4 and 7 saying it is old-UI only are stale. Old `#/admin?id=<section>` links need a
  redirect at the cutover.

## 0. Verdict in five lines

1. **Hard blocker, no tool exists.** Migration `20260924_0016` (Reading canonical cutover) is non-additive and gated.
   `scripts/bootstrap_runtime_schema.py` refuses to cross it, and its only apply tool,
   `scripts/reading_canonical_cutover.py`, refuses port 8000 and 8010 by design (`REFUSED_PORTS`, line 67). :8000 cannot
   be brought to head with any shipped procedure until a human-authorized, independently reviewed production variant
   exists (B1).
2. **Authorization gaps.** Of the 20 revisions :8000 must apply, only 0017-0023 and 0025 name :8000 as a later gate; 0006-0016
   were authorized for dev and sandbox only ("explicitly not production"), and 0029 (D-142) is approved for :8021 only and has no recorded :8000 apply
   authorization at all (B2).
3. **Not blockers, proven.** The four unpromoted tables (0024, 0026, 0027, 0028) cannot break startup or a learner
   request on :8000: every code path is flag-guarded, wrapped, or not wired to the runtime (section 2).
4. **Product shape.** `/` is still the OLD UI and `/next` the NEW UI (D-091; the cutover is not done). A merge puts both
   on :8000. The new UI's sign-in flow is in progress in another lane (section 5).
5. **Server-side learner records (D4) stay dark** on :8000 unless `ORENA_ACCOUNT_BACKBONE=on`, and turning it on needs
   `ACCOUNT_RECORD_LIMITS` (approved, not built) and an account-deletion answer (D-055(b), not built). Recommended first
   release: backbone off (section 3).

## 1. Schema

> Historical analysis, written before the release. The whole chain 0004 -> 0029, including 0029, was applied to :8000
> on 2026-10-08 under the human's authorization: `proposals/PRODUCTION_MIGRATION_PACK.md` section 4c. Statements below that a
> revision "waits for authorization" describe the state before that apply.

### 1.1 The facts

- `origin/main` has revisions 0001-0005 in `migrations/versions/` (checked with `git ls-tree origin/main`).
- `codex/work` has 0001-0023, 0025 and 0029 in `migrations/versions/` (head `20261007_0029`), so :8000, if it is at 0005,
  must apply **20 revisions**: 0006-0023 (18), 0025, 0029.
- `migrations/proposed/` holds 0024, 0026, 0027, 0028. Alembic does not read it (`migrations/proposed/README.md`), so
  they are not part of the head and not required by startup. Chain note: 0026 revises `20261007_0029`, 0027 revises 0026,
  0028 revises 0027; **0024 still revises `20260930_0023`**, so it must be re-parented before it is ever promoted or the
  chain gets two heads (README: "re-parent it on 0025", now on 0029).
- Startup verifies, never migrates: `writing_coach/runtime_schema.py:29` (`readiness`) and `:73` (`SchemaNotReady`); wired
  in `writing_coach/persistence/runtime.py:103-111`. Anything other than "actual == head" refuses to serve. So code and
  schema are **one deployment unit**: new code on an old schema, or old code on a new schema, does not start.
- :8021's schema is `20261007_0029` (verified 2026-10-07 with `select version_num from alembic_version`): the human
  approved 0029 for :8021 only (review of fbf11df1); it was applied after a pg_dump. :8021 is at head; nothing to do there.

### 1.2 Each revision

| Rev | Adds | Review / authorization | Status for :8000 |
| --- | --- | --- | --- |
| 0006 commerce subscription inbox | 3 tables (`commerce_*`), additive | Delegated review round 3 `7020925` APPROVED WITH REQUIRED CHANGES, changes made; D-054 sandbox only | Sandbox-only authorization. Needs a :8000 authorization. Nothing wires a caller (billing off). |
| 0007 commerce quota buckets | 2 tables, additive | Round 3 APPROVED; sandbox only | Same as 0006. |
| 0008 vocabulary content catalog | collections, entries, memberships, import receipts | Review APPROVED `a1a90b7`; human authorization 2026-09-16, sandbox | Sandbox-only. Additive. |
| 0009 reading library | `reading_books`, `reading_book_chapters` | 3 rounds, round 3 APPROVED; authorization 2026-09-16, sandbox | Sandbox-only. Additive. |
| 0010 listening hint state | 2 columns + CHECK on listening progress | D-068/D-069 | Additive; defaults, no backfill. |
| 0011 essay review kept | 1 nullable column on `essays` | D-072.1 | Additive, metadata-only. |
| 0012 text discussions | 2 tables | 4 review rounds; "Sandbox only" | Sandbox-only. |
| 0013 my library + entry identity | 3 tables + 3 columns on `saved_words` | Round 1 APPROVED WITH REQUIRED CHANGES `dc8b340`, re-rehearsed; **dev and sandbox only, not production** (D-074) | Needs a :8000 authorization. |
| 0014 vocabulary decks | decks tables | APPROVED (`9f94ad5`, delegated reviewer); **dev and sandbox only, explicitly not production** | Needs a :8000 authorization. |
| 0015 reading content engine | 6 tables (Admin Content -> Reading) | Predecessor authorized for the 8012 sandbox; "integration revision ... requires independent delta review before shared-runtime apply" | **Delta review not recorded.** Needs review + authorization. |
| **0016 adaptive reading** | **Non-additive**: renames `reading_sessions`/`reading_attempts` to frozen `reading_legacy_*`, creates canonical `reading_attempts` and 3 more tables, `reading_articles.content_kind` | Architecture review APPROVED (no P0/P1) for the predecessor; D-083 sandbox authorization; "integration revision ... needs independent delta review and explicit runtime authorization"; "Production and preview keep every gate. The predecessor's authorization does not transfer." | **BLOCKER B1.** |
| 0017 declared level | `user_language_profiles.declared_level` | DECLARED_LEVEL_STORAGE.REVIEW; merged into D4 (D-104/D-105) | D4: authorized for :8021 only; ":8000 is not touched until the merge and its own gates" (D-105.1). |
| 0018 account settings | 4 columns on `users` (hot table: own step after backup) | D4 (APPROVE, `LEARNER_RECORDS_D4.REVIEW.md`; REHEARSAL 53 PASS at 100k rows) | Same. |
| 0019 review settings | 3 columns on `user_language_profiles` | D4 | Same. |
| 0020 listening score source | `listening_progress.score_source` default `client` | D4 | Same. |
| 0021 essay review history | table + PostgreSQL BEFORE UPDATE trigger | D4 | Same. |
| 0022 library items place | `place`, `place_at` + partial index | D4 | Same. |
| 0023 grammar quiz result | 3 columns + CHECK on `grammar_progress` | D4 | Same. |
| 0025 vocabulary sense localizations | localizations table (CC-CEDICT + Unihan data) | D-124; review APPROVE WITH CONDITIONS, closed; rehearsal at 100k entries; applied to :8021 only | Same ("any other runtime ... must apply it after a backup", README). |
| **0029 practice session id** | `speaking_attempts.practice_session_id` nullable + index | D-141/D-142; rehearsal 2 x 16 PASS (`PRACTICE_SESSION_IDENTITY.REHEARSAL.md`); doc status "IMPLEMENTED ON BRANCH, AWAITING HUMAN REVIEW"; "Any migration still waits for the human's authorization" | **No recorded human authorization even for :8021.** Needed before it is applied anywhere. |

Proposals not in the chain:

| Rev | Adds | Status | Needed for :8000 head? |
| --- | --- | --- | --- |
| 0024 `media_entries`, `media_entry_payloads` | PostgreSQL media metadata | APPROVE WITH CONDITIONS 2026-10-01; rehearsal PARKED (D-109); human authorization pending | No (section 2). |
| 0026 `ai_cost_records` | AI cost per account | PROPOSED; review APPROVE WITH CONDITIONS on the isolated slice; no authorization | No. |
| 0027 `billing_orders` | checkout orders | PROPOSED, billing OFF; payment/entitlement needs independent review | No. |
| 0028 `reading_derived_texts` | on-demand Reading cache | PROPOSED; human authorization pending | No. |

Rev 0016 is also not additive in effect: :8000's existing generated-reading sessions and attempts become a read-only
archive (rows kept, frozen by trigger). Meaningful history stays; D-083 says never to `reset-legacy` it without evidence.
Old code writing those tables fails loudly, which is why the cutover and the code are one unit.

### 1.3 The "before :8000" conditions (CURRENT_HANDOFF line 78-79)

| Condition | Met? | Evidence / note |
| --- | --- | --- |
| `ACCOUNT_RECORD_LIMITS` rev 3 built | **No** | `proposals/ACCOUNT_RECORD_LIMITS.md` is now rev 5, "APPROVED WITH CONDITIONS ... implementation not started". Matters only if the backbone is on (records API is served only while the backbone is `active`, `account_records_api.py:4`). With the flag off there is no server-side growth to bound. |
| Upload media deletion, D-055(b) | **No** | `UI_BACKEND_GAPS.md:4650,4693`: `delete_all_owned_media` exists, no workflow calls it. D-055: no runtime path may delete or re-register an account until the journal and owner-table workflow exist. Today no deletion path exists, so nothing is wrongly deleted, but personal uploads are retained with no byte or count rails. See B4. |
| Code and schema as one deployment unit | Mechanically enforced | Startup refuses a mismatch (above). The operator must migrate, then start the new image, in one window. Not "met", but cannot be violated silently. |
| Delete for an imported text, media-import bound (open for the human) | Open | CURRENT_HANDOFF line 77-78. |

### 1.4 Operator sequence (the human runs it; none of it is run here)

Preconditions: items B1 and B2 resolved; maintenance window set; no other lane operating Docker.

1. Report only, no change: `python scripts/bootstrap_runtime_schema.py --plan` against :8000's database. Record `current:`
   and the `pending:` list (a `gated` marker on 0016 is expected). If `current` is not 0005, stop and re-plan.
2. Backup: `python scripts/runtime_backup.py capture --out backups/pre-8000-merge.dump`, then `rehearse` (restore to a
   scratch database) and `verify` (script header lines 6-9). Take a **fresh** capture again immediately before 0018.
   Also snapshot the media volume and the SQLite archives (never delete them as cleanup, AGENTS section 10).
3. Rehearse on the restored copy, not on :8000: apply the full chain to the copy one revision per invocation, then
   `python scripts/rehearse_learner_records_schema.py --volume N` with N from the real row counts to measure lock holds
   (README: maintenance window is set from these measurements).
4. Apply on :8000, one revision per invocation, never `--upgrade` straight to head:
   `python scripts/bootstrap_runtime_schema.py --upgrade --from <rev> --to <rev> --confirm`.
   Order: 0006 .. 0015; then **0016 by the production-authorized cutover procedure only (B1)**; then 0017; **0018 alone
   straight after a fresh backup**; 0019 .. 0023; 0025; 0029 (only if authorized, B2).
5. Verify: `bootstrap_runtime_schema.py` report-only shows `ready` at `20261007_0029`; `GET /api/readiness` after start;
   row counts of the pre-existing tables unchanged against the step-1 record.
6. Start the new image (it requires a rebuild: `requirements.txt` and `Dockerfile` changed, section 3.3).
7. Rollback: inside the window (before writes resume) redeploy the old image on the restored archive. After writes resume,
   forward-fix only; a restore loses everything since the backup and is an authorized incident operation (MEDIA_METADATA
   and D4 rollback wording). 0016 is not reversible by an additive downgrade.

## 2. Code that touches tables from non-promoted proposals

All four proofs are by reading code; the related pytest modules are in the full run in section 8.

| Table | Code | Reachable without the table? | Verdict |
| --- | --- | --- | --- |
| `ai_cost_records` (0026) | `platform_repository.record_ai_cost` (`:631`), `delete_ai_costs_before` (`:657`), `ai_costs_by_account` (`:671`); caller `ai/account_costs.py` | Writes run on every priced call by a signed-in account. `record()` wraps the writer in `except Exception` and pauses 5 minutes (`account_costs.py:64`); the sweep is also wrapped (`:80-95`) and runs off the request thread. `ai_costs_by_account` catches `ProgrammingError` and returns `None`; the Admin route reports `available:false` (`ai/platform.py:983-1000`). The insert is bounded by `statement_timeout 500` / `lock_timeout 200`. | **Not a blocker.** Cost: one failed INSERT and one warning log line per 5 minutes while an account uses AI. The Admin per-account cost page shows "not available". |
| `billing_orders` (0027) | `persistence/billing_repository.py`; routes `billing_api.py` | `app.py:1029-1045`: the service exists only if `BILLING_ENABLED` is on **and** an engine **and** the backbone is active; otherwise `None`, and every route answers 503 `billing_off` via `_require_service` (`billing_api.py:41`). The repository is never constructed otherwise. Webhook path is public by design (`auth_support` public list) but returns 503 with no service. | **Not a blocker while `BILLING_ENABLED` is unset.** If an operator sets it on :8000 without 0027, checkout and webhooks would 500. Keep it unset. |
| `reading_derived_texts` (0028) | `persistence/reading_derived_repository.py`; `reading_derived.py` `DerivedCache` | `app.py:592` builds the repository (constructor only stores the engine; no DB I/O at import). `get_many`/`put_many` are wrapped (`reading_derived.py:98,127`), pause 5 minutes, and the in-process LRU still serves. Only published text persists. | **Not a blocker.** On-demand translations/summaries are regenerated per process restart instead of shared; the provider is called more often (cost, not failure). |
| `media_entries`, `media_entry_payloads` (0024) | `persistence/media_library_repository.py`, `media_models.py` | Not wired into the runtime: `grep` finds no import outside `scripts/import_media_index.py` and the rehearsal script. The media library stays on the file store (`media_library_store`, `MEDIA_LIBRARY_ROOT`). The ORM mirror is on its own inert `MediaBase`. | **Not a blocker.** Unreachable. |

ORM caveat: `AICostRecord` and `ReadingDerivedText` are declared on the main `Base` (`persistence/models.py:632,659`) but nothing
creates or verifies them at startup (verification is the Alembic revision only). Account deletion is reserved, so no
enumeration touches them yet; when it is built, the new tables must be in its enumeration (`deletion_enumeration.py`).

## 3. Environment and feature flags

Names only. No value was read; `.env` was not opened. "First :8000 run" is a recommendation, not a decision.

### 3.1 Flags introduced or changed by this branch

| Name | Read at | Default | Recommended first :8000 run |
| --- | --- | --- | --- |
| `ORENA_ACCOUNT_BACKBONE` | `account_backbone.py:30,53`; `compose.yaml` | off | **off.** On requires D4 limits (B3) and the deletion position (B4). Off: drafts, notes, conversations and private imports stay on-device; settings columns still exist. |
| `ORENA_PRACTICE_SESSION` | `speech_api.py:45-51`; compose | off | **off** (also an unauthorized revision, B2). Off: take writes NULL, `session=current` answers 404, Summary uses the 7-day fallback. |
| `BILLING_ENABLED`, `BILLING_PRICES_FILE`, `POLAR_*`, `PAYOS_*` | `billing/service.py:43`, `app.py:1033` | off / unset | **unset.** 0027 does not exist; no learner screen draws plans (BL-1). |
| `AGENT_ENABLED`, `AGENT_VOICE_ENABLED`, `AGENT_TURN_RETENTION_SWEEP` | `agent/api.py` | off | Superseded by D-146: `AGENT_ENABLED` alone decides, in every environment. :8000 staging: `AGENT_ENABLED=true`, `AGENT_VOICE_ENABLED=false`; the agent needs a provider credential and `AGENT_DAILY_SPEND_CAP_USD` set by the human. |
| `AI_RUNTIME_MODE` | `ai/platform.py:74` | `legacy` | Keep what :8000 uses today. |
| `MEDIA_MODEL_CLIPS` | `media_transcript_pipeline.py:443` | on (`"1"`) | on; model clips are cut at content readiness. Needs `ffmpeg` in the image (already). |
| `MEDIA_PIPELINE_INLINE`, `MEDIA_TRANSCRIPT_FALLBACK` (`none`/`supadata`), `SUPADATA_*`, `MEDIA_TRANSLATION_PROVIDER`, `MEDIA_PRETRANSLATE_LANGUAGES`, `MEDIA_DAILY_CAP_USD`, `MEDIA_ASR_BATCH_CAP_USD`, `MEDIA_AI_BATCH_CAP_USD` | `app.py:517-551`, pipeline | `none` / unset | Keep paid fallbacks off until the human sets caps (paid providers are a human gate). |
| `READING_TRANSLATION_PROVIDER`, `READING_COMPREHENSION_CAPABILITY`, `READING_LIBRARY_ASSET_ROOT`, `READING_WORKER_CONCURRENCY` | `app.py:572`, compose | provider unset | A `reading-worker` service is new in compose; without it, Admin Reading jobs stay queued. Reading comprehension generator is unconfigured until the human approves (CURRENT_HANDOFF line 118). |
| `MEDIA_LIBRARY_ROOT`, `MEDIA_LIBRARY_ASSET_ROOT`, `WORD_AUDIO_ASSET_ROOT`, `WORD_DEEP_ASSET_ROOT`, `USER_DATA_ROOT` | compose, app | repo-relative in code; `/data/...` in compose | **Verify before start:** compose now pins these under `/data` (volume `writing_data`). If :8000's existing media/assets live elsewhere, the new compose would silently point at empty directories. Operator check, not code. |
| `AI_PROVIDER_SECRETS_KEY` | compose | empty | Needed to save provider keys in Admin; otherwise the console refuses (closed state). |
| `PRONUNCIATION_PROVIDER` | `speech_pronunciation.py:619-654` | compose default changed from `demo` to empty | Unset now means "do not guess"; set `azure` (with `AZURE_SPEECH_KEY`/`AZURE_SPEECH_REGION`) if :8000 should score pronunciation. Do not leave `demo` on :8000. |
| `ORENA_LIMIT_IMPORT_TOMBSTONES` and the other `ORENA_LIMIT_*` | `account_records_api.py:54-62` | floor-validated; unset = default | Only the tombstone limit exists in code; the rest of the table is unbuilt (B3). |
| `WORD_TTS_SPEND_CAP_USD`, `AGENT_DAILY_SPEND_CAP_USD` | app | caps | Set deliberately before any provider voice is enabled. |
| `ORENA_ENVIRONMENT_LABEL` | `app.py:998` | `local` | Set to the :8000 label so Admin shows the right environment. |

### 3.2 Unchanged and already required in production

`APP_ENV`, `PUBLIC_BASE_URL`, `GOOGLE_CLIENT_ID`/`SECRET`/`REDIRECT_URI`, `SESSION_SECRET` (>= 32 characters),
`BOOTSTRAP_OWNER_EMAIL`, `PLATFORM_ADMIN_EMAILS`, `POSTGRES_RUNTIME_URL`, `PERSISTENCE_BACKEND`, `ALLOW_FALLBACK`
(recommended `false`), `OLLAMA_*`, `GROQ_*`, `GEMINI_*`/`OPENAI_*`/`DEEPSEEK_*`, `CLOUD_AI_TIMEOUT`, `KOKORO_*`,
`LOCAL_TRANSLATION_URL`. `core/deployment.py:80-121` refuses to start in production with a missing or short secret, a
non-HTTPS origin, or a redirect URI whose origin differs from `PUBLIC_BASE_URL`: :8000's existing values already
satisfy this, because it has run.

### 3.3 Image

`requirements.txt` raises fastapi, nltk, requests, python-multipart, cryptography, and moves yt-dlp to
`2026.08.19[default]`; the `Dockerfile` adds a Node 24 runtime for yt-dlp's YouTube challenge solver. :8000 therefore
needs a **rebuild**, not just a code mount; ffmpeg/ffprobe and the NLTK tagger are already in the image/CI path.

## 4. UI cutover (D-091)

- Today: `app.py:1690` serves the old UI (`templates/orena/index.html`) at `/`; `app.py:1703` serves the new UI
  (`templates/orena/next.html`) at `/next`. D-091 item 5: the cutover is its own slice, makes `/` serve the new UI,
  sends old addresses into the new flow (`product/legacy-routes.js`), deletes the old template, `ui/*.js`, stylesheets
  and `theme.js`, writes `LEGACY_TOMBSTONES.md` entries and replaces each retired gate with a gate on its successor.
  `IMPLEMENTATION_MAP.md:149` ("Retired by the cutover") is still empty.
- Must be true first: new-UI sign-in (section 5), Admin moved to the new UI (D-101 E; today the console is `/#/admin` in
  the old UI), Grammar decision (section 7), the human's approval of the remaining lane defaults, and the old-UI-only
  features either retired by tombstone or ported.
- Options:

| Shape | What it means | Risk | Verdict |
| --- | --- | --- | --- |
| A. Merge, keep `/` old, ship `/next` beside it | :8000's current learners see no change at `/`; `/next` is opt-in by URL | Two UIs on one backend; old UI at `/` is the retired Dark Glass baseline; schema change still applies to both (0016 breaks the old Reading flow: the old UI's generated Reading is retired by that revision, so `/` Reading degrades). | Lowest learner risk, but the old UI's Reading must be checked after 0016. |
| B. Cutover first, then merge | `/` is the new UI at release | Cutover slice not built; the sign-in and Admin pieces are missing; the biggest change ships with the biggest unknowns. | Not ready. |
| C. Merge, then cut over in a later release | Release 1 = A; release 2 = cutover | Two releases; needs a second gate and a second schema-free deploy. | Recommended as the lower-risk path, if the human accepts that `/` Reading is not the old generated flow any more. |

The human decides. Evidence that the old UI's Reading cannot survive 0016 unchanged: migration 0016 docstring ("Not
compatible with the code that runs today - by design"; retires the generated flow in the same deploy).

## 5. Authentication

- The new UI sign-in flow (next-target allowlist `auth_support.safe_next_target`, `NEXT_UI_PREFIX = "/next"`, working-tree
  diff of `auth_support.py`/`app.py`/onboarding/shell by another agent) is **in progress and uncommitted**. This document
  does not review it. Release is blocked on it only for the cutover shape (section 4), not for shape A.
- What :8000's OAuth means for the new UI: the redirect URI is fixed at `PUBLIC_BASE_URL + /auth/google/callback`
  (`core/deployment.py:98-106`); `/next` is not an OAuth path, so no Google console change is needed. The session cookie is
  `same_site="lax"`, `https_only` per `COOKIE_SECURE`, signed by `SESSION_SECRET` (`auth_support.py:539-540` at HEAD), and
  is shared by `/` and `/next` (same origin). With auth enabled, an unauthenticated `/next` redirects to `/login`
  (middleware at `auth_support.py:470-520` at HEAD: `/next` is not in the public list).
- Legacy-data claim: `maybe_claim_legacy_data(email, google_sub)` (`auth_support.py:178`, called at `:339` after Google
  callback) copies the legacy SQLite database into the first sign-in of `BOOTSTRAP_OWNER_EMAIL` only, and only when the
  per-user file does not exist. It touches SQLite archives, not PostgreSQL; it is unchanged by this branch, and it
  must not be broadened. Note the owner's PostgreSQL account row is created by `upsert_user`, independent of this.
- User accounts: `users` gains four columns (0018). Existing accounts read as "follow device / never chosen", so there is
  no data migration for learners.

## 6. Content and data :8000's learners will see

- Catalogue (listening/vocabulary/reading): content is data, not code. :8000's own data stays; shipped lists are
  `writing_coach/content/*`, `data/` (not read here). A fresh vocabulary catalogue (0008/0025) is empty until imported:
  `GET` collections is empty on :8000 until an operator imports (CC-CEDICT/Unihan vendored in the repo for ZH pinyin/`en`
  meanings).
- Reading: `reading_articles` start empty on :8000 after 0015/0016; Admin must import, review and publish (S1 admission
  loaded 30 EN + 22 ZH on :8021 only; per-text credits on the Licences page). Comprehension sets need the human's OK for
  the generator provider.
- Listening/Speaking model clips: new items cut model clips at content readiness. **Existing admitted media have none**;
  run `python scripts/backfill_model_clips.py --dry-run`, then `--max-lines 200` (bounded, idempotent, no provider call)
  against :8000's media root. **S-27 / D-140:** YouTube imports have no source audio at rest; the backfill cannot cut them
  until the shared fetch gets a ranged download (`media_safe_fetch.download_bounded`; HTTP 403 on an un-ranged GET). Owner:
  shared Media Learning / Codex lane (human decision 2026-10-07). Until then Compare shows "model plot unavailable" for
  those lessons (honest, not an error).
- Reading derived texts: first use per text costs a provider call (cache is per process without 0028). Provider caps
  apply; leave paid providers unset until the human sets them.
- Grammar: the canonical Grammar Store/API is deferred (D-111.4). New-UI Grammar shows its honest empty state;
  `grammar_progress` gains quiz-result columns (0023) but nothing serves Grammar content. R5 Grammar is retired; there
  is no fallback (CURRENT_HANDOFF line 33-34, 145-150).
- Vietnamese localization (D-124): vi policy built but NOT enabled until the human grades `docs/reviews/evidence/d124-vi`.
  A Vietnamese learner sees English-labelled meanings where the policy says so.
- Bounded backfills after migration (all idempotent, operator-run): `backfill_model_clips.py`; none for 0029 (no backfill,
  D-142.4); none for 0017-0023 (defaults, no backfill); `import_media_index.py` is **not** needed (0024 unpromoted).

## 7. Product completeness

Strict rule used here: a blocker is data loss, security, startup failure, or a broken core flow. Everything else is a
known limit.

**Blockers (not product polish): see section 9, B1-B5.**

**Not blockers, but unfinished** (evidence: `docs/UX_REVIEW_LOG.md` latest Batch status lines, `docs/reviews/*_DESIGN_AUDIT.md`
"Lane defaults pending human confirmation", `UI_BACKEND_GAPS.md`):

- Reading: APPROVED (D-136). Listening: VERIFIED at 461d471 (not "full Experience ACCEPTED").
- Speaking, Writing, Vocabulary, Places, Cross-skill: audited, fixed, Reviewer-verified; the human's real recording / AI /
  device check on 2026-10-07 accepted the recording and AI-scoring items ("khá là ok rồi"). The last sweeps are `PARTIAL`
  with LEX-092/LEX-086 `READY_FOR_VERIFY` (log line ~2779); these are visual/interaction fixes, not defects of data or
  security.
- **Onboarding: next in line** (CURRENT_HANDOFF, D-129 2). `ONBOARDING_DESIGN_AUDIT.md` has human-decision items and
  "Lane defaults pending human confirmation". Since a new learner's first run is the new UI's onboarding and the sign-in
  flow is in progress, this matters for the cutover (section 4) and not for shape A.
- Lane defaults awaiting confirmation: Places, Cross-skill, Vocabulary, Onboarding audits each carry a section; none is a
  correctness issue.
- Design gaps that stay "Coming soon" by design: Speaking modes Sound/Tone, Timed Reaction, Retell, Mock Interview
  (D-101 H9); Import "File: PDF, EPUB" variants; Progress PG-1 streak, PG-9 rank (BLOCKED `[DEF]`: need definition).
- Parked or deferred: **Orena Intelligence** (parked by the human; mock only; agent routes off in production);
  **Grammar** (deferred D-111.4); **Admin new UI** (admin lane; today `/#/admin` in the old UI, preserved by D-101 E);
  **native mobile** frozen (AGENTS section 5); billing UI (BL-1, no design).
- Speaking S-15a "this session only" depends on 0029 + flag; otherwise the 7-day fallback and documented gap apply.
- ZH writing evaluator recall: fix (1) landed (v2.7); the live benchmark run waits for the human's go (provider cost).

## 8. CI and local test state

CI (`.github/workflows/ci.yml`): `validate_project_memory.py`, `validate_architecture.py`, seven Python contract scripts
(`test_orena_backbone`, `account_profile`, `runtime_schema`, `work_contract`, `job_contract`, `account_backbone`,
`test_runtime_backup`), `build_listening_dev_catalog.py --check`, the browser ESM graph (needs
`node --experimental-vm-modules`), ~140 `.mjs` gates, `pytest -q test_app.py tests` with `PERSISTENCE_BACKEND=sqlite`, and
`docker build`. A PR `codex/work -> main` needs all of it green (pull_request trigger; `fetch-depth: 0`). CI has not been
run for this branch tip; any claim below is **local execution**.

Local results at `8875df48` plus the human's uncommitted `DESIGN_CONTRACT.md` edit:

- `validate_project_memory.py`: passes. `validate_architecture.py`: passes. `build_listening_dev_catalog.py --check`: SKIP
  (no committed catalog; `SNAPSHOT_REQUIRED` is False).
- Node gates (every `node scripts/*.mjs` in the CI list, run directly): 132 pass, 1 fail (`test_orena_writing_workspace.mjs`, the DESIGN_CONTRACT.md case below); the ESM-graph gate was not run locally.
- `test_orena_vocabulary_theme_tokens.mjs`: fails on HEAD; **not in CI** (reproduced locally).
- `test_orena_writing_workspace.mjs`: fails locally; per the lane it passes with a clean tree and fails only with the human's
  uncommitted `docs/project/DESIGN_CONTRACT.md` edit; **it is in CI**, so the edit must be committed in a consistent way
  or reverted before the PR (owner: human, who owns that file).
- Windows note: `test_orena_grammar.mjs` fails on a CRLF checkout and passes with LF (environment, memory note).
- Python suite in the application image (AGENTS section 9 recipe, SQLite, local, not CI): 4398 passed, 380 skipped, 1 failed in 9m46s. That failure was in the then-uncommitted sign-in work; after it landed (277c1ceb) the full suite is 4399 passed, 380 skipped, 0 failed.

CI remains the gate; a local pass is not CI evidence.

## 9. BLOCKERS table

| # | Item | Why | Owner | Smallest next step |
| --- | --- | --- | --- | --- |
| B1 | 0016 on :8000 | Decided (D-143 2): take it, no conversion. Tool built: the pack applies 0016 through the reviewed `reading_canonical_cutover.apply` behind production gates (`PRODUCTION_MIGRATION_PACK.md`). | Human (backup, review, authorization) | Human runs `product_backup.ps1` on :8000 and `product_migration_rehearsal.ps1` on it; reviews `rehearsal.json`. |
| B2 | Authorization of the chain | Decided (D-143 3): one pack, reviewed on a restored copy; 0015/0016/0029 get their own attention (pack section 5). | Human | Review the pack (code, this branch) and the rehearsal evidence; record the authorization the `apply` names. |
| B3 | `ACCOUNT_RECORD_LIMITS` not built | Not a blocker for the first release (D-143 4: backbone off). Blocks a public release. | Lane, then review | Build before public release. |
| B4 | Deletion and upload limits | Not a blocker for the invitation-only first release (D-143 4). Blocks a public release. | Lane + human | Build before public release; :8000 stays invitation-only until then. |
| B5 | UI cutover | Decided (D-143 1): `/` runs the new UI before the :8000 release; old paths ported/redirected or deleted and tombstoned. | Lane | The cutover slice (D-091 item 5). |
| B6 | (resolved - not a blocker) | `test_orena_writing_workspace.mjs` fails only with the human's uncommitted `DESIGN_CONTRACT.md` edit; on the committed tree (what CI checks out) it passes (verified 2026-10-07 with `git archive HEAD`). It becomes a blocker only if that edit is committed without updating the gate. | Human | Keep the edit uncommitted or update the gate with it. |
| B7 | (resolved - landed) | New-UI sign-in landed in 9be69a82 / 277c1ceb behind the existing auth switch (strict /next return target, signed-out Welcome, Google only; email form is gap SIGN-1). Full pytest on that tree: 4399 passed, 380 skipped, 0 failed (local, not CI). Runtime steps: `NEXT_SIGN_IN_RUNTIME.md`. | Lane | None; :8000 already has the OAuth env. |

Not blockers (resolved by analysis): unpromoted tables 0024/0026/0027/0028; agent routes in production; Grammar empty state;
YouTube model clips (S-27); Onboarding polish.

## 10. Human gates on release day, in order

1. Decide shape A or C (section 4) and whether :8000 gets the Reading cutover at all (B1, B5).
2. Authorize the schema for :8000, naming the revisions (B2). Independent delta review of 0015/0016 recorded in Git.
3. Decide backbone off for release 1 (B3) and whether :8000 is invitation-only (B4).
4. CI green on the PR; merge `codex/work` -> `main` (human merges; no auto-merge).
5. Maintenance window and "no other lane on Docker".
6. Backup captured, restore-rehearsed and verified (section 1.4 step 2).
7. Rehearsal of the 20-revision chain on the restored copy; lock times recorded (step 3).
8. Authorized apply on :8000, one revision per invocation, 0018 alone after a fresh backup (step 4).
9. Rebuild the image (`docker build`), start, verify `/api/readiness` and report-only schema check (steps 5-6).
10. Set flags per section 3.1 (backbone off, practice session off, billing/agent unset, pronunciation provider chosen).
11. Smoke: sign in via `/`, sign in via `/next`, one Reading read, one Dictation, one Speaking take, one Writing review, Admin
    opens.
12. Run `backfill_model_clips.py --dry-run` then bounded (section 6). Decide when to announce.
13. Cost caps and paid providers: human sets them before enabling any (provider credentials are a human gate).

## 11. What the lane can do next without a gate

- Draft the production-variant design for B1 (a document, not a change to the sandbox script) and a delta-review request
  for 0015/0016; prepare the restored-copy rehearsal script.
- Commit `RELEASE_8000_READINESS.md` (this file) and update it as gates are decided.
- Implement `ACCOUNT_RECORD_LIMITS` rev 5 against the existing proposal (code + tests, no schema), if the human wants
  the backbone on at release.
- Build the owner-media deletion step and upload limits (B4) as code and tests with no runtime touched.
- Re-parent proposal 0024 on the real head and update `migrations/proposed/README.md` (document and proposal file only).
- Continue the UX queue (Onboarding, LEX-092/086 verification), on :8021 only, one unit at a time.
- Run the CI-equivalent local sequence again after the `DESIGN_CONTRACT.md` decision.
