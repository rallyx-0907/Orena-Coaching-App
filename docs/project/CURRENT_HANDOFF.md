# Current Handoff

## Governance

**Purpose:** current execution state only. **Authority:** active agent after
verified evidence. **Change when:** branch/lane, verified batch, status,
blocker, human gate, or exact next task changes. **Do not store:** durable
product philosophy, historical closeouts, implementation inventories, secrets.

## Current branch / lane

- Branch: `claude/integration-v2`; work sits on **draft PR #56** (`main` =
  `e8e2d70`). CI runs only on `push: [main]`/`pull_request` — no open PR means
  NO CI; check PR before claiming CI.
- Lane: Orena integration — Product UI Foundation + Golden Web Home;
  Listening catalog lane preserved, deferred.
- Read live HEAD via `git rev-parse HEAD`. Verified application baseline:
  `817429407f158c40d84d0555497802d325ea47a9`.
- Baseline ALREADY CONTAINS, do not re-implement: support-language
  separation, curated meaning+translation cache, background recovery
  orchestration, atomic provider-poll claim, L3 import pipeline,
  curated-transcript contract (D-046), offline transcript producer, preview
  tier (D-047/D-048), lesson-scoped progress + Continue Learning (D-049), and
  the Orena product layer + Home H1-H1.3 (D-051-D-054).
- Goes stale on EVERY commit — update it and the YAML together.

## Last verified batch

- **H1.3 lifecycle closeout**, local: no Python touched (866 backend
  unchanged), 31/31 CI-gated `.mjs` contracts, ESM graph (55 modules) and
  `validate_architecture` OK. Same 8 pre-H1 `.mjs` failures plus the isolated
  goal-editor gap; none in CI.
- Real EN/ZH playback verified by browser decode, not by a human.

## RUNTIME — ONE local Orena, read before touching Docker

- **D-048: ONE long-lived runtime.** `ai-writing-coach-writing-coach-1` on
  `127.0.0.1:8000`, `ai-writing-coach-postgres-1`, one cloudflared. Never a
  second container/DB/image/port/tunnel/Compose project or feature volume.
- Bind-mounted source: `docker compose restart writing-coach` suffices for
  Python/JS/CSS/catalog changes; rebuild ONLY for Dockerfile/requirements/
  system packages; env changes need `up -d`.
- Images: CURRENT `ai-writing-coach:local`, ROLLBACK
  `orena-rollback:pre-realmedia`. No QA/feature/milestone/test images.
- **D-047 tier**: `APP_ENV`=runtime/security, `ORENA_DEPLOYMENT_TIER`=content
  visibility (default production). Preview needs platform-admin, enforced
  server-side on listing AND lesson endpoints, per-USER. `compose.preview.yaml`
  is optional isolated staging only.
- 8 unused `orena-postgres-preview-data-*` volumes remain; deletion is a
  HUMAN GATE, reported not removed. `orena.chillpickle.org` runs `cbdedfd`,
  does NOT follow `main`, no CD.
- Three worktrees share one Docker runtime; check no other lane is mid-batch.

## IN PROGRESS

- H2 Golden Home: production artwork/visual fidelity. H1 shipped real
  artwork containers/ratios/crop rules with a textless development wash.
- Listening preserved: L1/L2 done, L2.5 one live check from done, L3 blocked
  on ingestion. Deferred, not invalidated.

## DONE

- R0-R20 preserved. Listening ENGINE locally accepted; Writing (`beta`),
  Speaking, Reading (`internal`) complete locally — do not rebuild them.
- REAL MEDIA CATALOG PARTIAL: 2 rights-cleared video lessons, 5 seed audio.
  L2/L3 importer reuses the YouTube adapter and canonical Media Learning
  Object; a failed caption request is never "no captions".
- L2.5 (D-042/D-044): support/learning language and UI locale distinct;
  meaning editorial → cached → live → truthful unavailable. Groq key VALID —
  that 403 was Cloudflare 1010.
- **D-049**: progress keyed by (user, language, LESSON, segment) for
  Dictation/Shadowing; Continue Learning built server-side from real
  PostgreSQL progress with discovery's visibility boundary.
- **D-051 (H1)**: `orena/product-components.{js,css}`, first reusable Orena
  layer (`data-orena-ui="v2"`). Home: Hero→Continue→Worlds→For You→
  Challenge→Continue Exploring; Writing dashboard/streak off Home. Worlds:
  versioned source (`orena_worlds.v1.json`+`world_catalog.py`+
  `GET /api/worlds`) MEASURED: EN 3/6, ZH 3/6.
- **D-052/D-053/D-054 (H1.1-H1.3)**: Home audit corrections — real
  practice-outcome statuses (not 4 invented); empty sections show real
  starters, no double-listing, independent repaint; components dropped
  `bodyHtml`/`secondaryActions`; `lang` split from content language.
  `renderHome` honors `root._cleanupScreen` + a bounded settle budget (no
  stale repaint, no permanent `aria-busy`, no waiting past cleanup) and now
  gates every shared-state write, not only `paint()`. Next Practice no
  longer duplicates a Listening continuation; a total personal outage reads
  unavailable not empty; a World's lead label splits UI from content
  language.

## CURATED TRANSCRIPT RUNTIME — done, proven in a browser

- **D-046**: transcript acquisition is INGESTION-time; a lesson never calls a
  provider on open. `tests/test_curated_transcript_contract.py` makes every
  provider raise and opens real EN/ZH lessons: **10ms**, 0 calls.
- Provenance travels with the text; older lessons default UNSPECIFIED: a
  PERSISTED CANONICAL TRANSCRIPT ARTIFACT, not "JSON forever".

## L3 SHORT-FORM PILOT — gated on ingestion

- 0 transcripts acquired; nothing invented. Three causes: transcript body →
  `IpBlocked`; Supadata → **429**; Groq ASR → yt-dlp resolves 1/11 EN sources
  and Groq 400s on googlevideo's 302.
- `scripts/acquire_listening_transcripts.py` produces the offline handoff;
  `SNAPSHOT_REQUIRED` stays False; pilot packs unchanged (D-045).

## PENDING

- H2 artwork, then the shell/navigation migration. No Explore/Progress route
  yet, so a World card opens its lead lesson via the autostart handoff.
- Listening human migration/dogfood, ingestion work, and human playback
  acceptance of the two real lessons all stay preserved.

## BLOCKED

- L3 content: YouTube IP ban (above). L2.5 cold acceptance: Supadata quota,
  paid-provider human gate. Home NOT rendered signed-in: dogfood requires
  Google sign-in, a human gate — verified instead against real
  components/CSS in sized frames.

## OPEN P0

- None known.

## OPEN P1

- **L2_5_REAL_COLD_ACCEPTANCE=PENDING_EXTERNAL_PROVIDER_QUOTA** on
  `iSTlFeW-Z9M` (Supadata 429, D-044, L2.5 NOT done). L3 content blocked (see
  L3 SHORT-FORM PILOT above).
- **Listening MODE not persisted**: Continue Learning resumes lesson/segment,
  not the prior mode. **Migration `20260903_0005` NOT applied** to dogfood DB
  (still `20260828_0004`); applying it is a human step.
- `test_r12_listening_goal_editor.mjs` and eight pre-H1 `.mjs` tests fail,
  none in CI (goal-editor: harness never resolves the library load before
  asserting).
- `orena/home.css` is largely dead, kept until the shell migration proves
  nothing depends on it. Registry is process-local: resume handles don't
  survive a restart. L1 is web only; native needs L6; iOS VP9/WebM unproven.

## HUMAN GATES

- Standing list: AGENTS.md §15 (production data/runtime, secrets, DNS, paid
  providers, deployment, mobile signing, publication, volume deletion).
  Signing in to dogfood; deleting 8 legacy volumes.

## NEXT EXACT TASK

**H2 Golden Home.** H1.1-H1.3 audit corrections are done — do not re-open
them. Replace the development artwork wash with approved production artwork
inside the containers H1 already built, render the signed-in Home at
1440/1024/390, compare against `ORENA_HOME_GOLDEN_SPEC.md`, fix the three
largest gaps at the highest shared level, and render again. Do not redesign
H1's composition.

Listening migration/dogfood and L3 ingestion stay preserved deferred work. Do
not run production/database mutation while executing UI work.
