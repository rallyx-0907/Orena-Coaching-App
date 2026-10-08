# D3 — skill × step matrix (D-101 D3, D-102)

**2026-09-29, `codex/work` at `93911f0`, proved on the lane runtime :8021 (real backend on
PostgreSQL, the working tree's static files).** Three read-only research passes, each cell with
file:line and endpoint evidence. The lead re-checked the heaviest findings on :8021:
- `PATCH /api/learner-profile {declared_level}` returns 501;
- `GET /api/account-backbone` reports `disabled`;
- a fresh session's learning language is `en`;
- the Attempt History screen never calls `api.speakingAttempts`.

Cell values: `RUNS_REAL` · `MISSING` · `N/A_BY_CONTRACT` · `PROPOSE_RETIRE`, where
`PROPOSE_RETIRE` waits for the human. `FUNCTIONAL_E2E_READY` and `CONTENT_SCALE_READY` are
recorded per row. Bench data the probes created is test data on :8021 only.

## Where the product stands

**No skill is complete.** Rows that are end-to-end ready today: Discussion (Reading), Profile
core, Progress overview/evidence/history, Respond to Content (Listening), and Writing in EN (with
one `MISSING`: the unsubmitted draft). Content scale is ready for nothing.

| Skill | RUNS_REAL | MISSING | N/A | RETIRE | Blocking themes |
| --- | --- | --- | --- | --- | --- |
| Reading | 18 (5 [I]) | 13 | 5 | 1 | position/completion device-only; no approved comprehension sets and no Admin path to make them; Reading Transfer stores nothing |
| Grammar | 3 (empty states) | 11 | 2 | 1 | no approved content, no Admin import, no grammar API, no progress store |
| Onboarding/Profile | 17 | 17 | 13 | 1 | `declared_level` not stored (501); **the learning language lives only in the session cookie**; Profile/Progress measures render 0 because nothing records them |
| Listening (Workspace, React, Respond) | 10 | 4 | 1 | 0 | place/continuation device-only; React stores nothing; no language check on listening progress (wrong-data risk) |
| Dictation | 4 | 1 | 0 | 0 | graded in the browser; the server stores the client's number (decision) |
| Shadowing | 2 | 3 (2 env) | 0 | 0 | stored but never read back; no speech provider on the bench |
| Speaking/Pronunciation (7 flows) | 17 | 15 (4 env) | 3 | 0 | Attempt History/Compare ignore the server's attempts; Free Talk, Situation and React save nothing; Conversation device-only; Summary sessionStorage-only |
| Writing | 9 | 1 | 0 | 0 | the unsubmitted draft is device-only (the server path exists behind the disabled backbone); ZH not proved on the bench |
| Vocabulary/Review | 23 | 11 | 6 | 0 | Collections empty (need Admin publish); From Your Errors can never fill (no client sends `practice_context`); Quick Sheet notes device-only |
| Orena | 0 | 6 | 9 | 0 | on the mock by design until G; history is device memory by AGENT_CONTRACT |
| Navigation/continuation | 9 | 6 | 5 | 0 | "continue where you left off" is device-only everywhere; Today's goal/streak have no backend |

"env" marks cells that fail only because the bench has no speech provider key (Azure Speech or
Groq). Adding one is a paid-provider human gate.

## What this means for the next milestones

- **D4 (one persistence proposal) must cover:**
  - `declared_level` (H2);
  - the learning language on the account;
  - reading/listening position and completion ("continue");
  - conversation records;
  - drafts (switch on or replace the disabled account-backbone path);
  - Reading Transfer and React/Free Talk/Situation results;
  - Sentence Quick Sheet notes and highlights;
  - grammar progress;
  - Speaking Summary.

  It is also the place to decide which recorded measures feed Profile/Progress (streak, minutes,
  goals).
- **E (Admin) is the content path for:** comprehension sets (the admin endpoints exist,
  `reading_admin_api.py:725-840`, with no UI), vocabulary collections, the Grammar Lab package, and
  the speaking/voice catalogue.
- **D7 reuse, already located:**
  - `api.speakingAttempts` plus `ui/voice-response.js` for Attempt History/Compare;
  - `capabilities/voice-feedback.js#evaluateVoice` for Free Talk/Situation/React;
  - `ui/speaking-workspace.js` for reading shadowing rounds back;
  - `capabilities/media-acquisition.js` / `api.mediaMy` for opening `url:` and `upload:` imports in
    the Listening workspace (today 404).
- **Wrong-data risks found:**
  - listening/shadowing progress accepts an asset of another language;
  - Progress shows an unmeasured pronunciation score as 0;
  - Chinese spoken-response coaching answers in Chinese instead of the support language;
  - a discussion thread is keyed by the session language, not the text's;
  - one ZH lesson is a single 12-second segment.

  Per D-101 these are fixed when they block an E2E or give wrong data.

## Updates since the matrix

- **2026-09-30. Reading, Check Understanding: `RUNS_REAL` in EN on the lane runtime.** Content
  arrived through the new Admin (`b4858d1`):
  - Project Gutenberg eBook #21, imported as job `889c0ac8`, reviewed and published as article
    `b483bd10`.
  - Comprehension set `996f0f65` (4 questions) generated on Gemini and approved.
  - With `ORENA_READING_PRACTICE_SUBMIT=on` on the bench, a learner answered it in `/next`.
    Lesson complete showed the server's `correct_count`/`total`.
  - The evidence record (`/api/reading/practice/evidence`) went from 0 to 1 for the article.
  - A fresh browser context (no device memory) shows the article in `#/progress?tab=history`.

  ZH still needs the same loop on a ZH article. Content scale is not ready (one article).

- **2026-10-01 (D-109 audit, `4ccacda`, :8021, `PRODUCT_COMPLETION_PLAN.md`). Cells whose evidence changed:**
  - Reading, Check Understanding: `RUNS_REAL` in **ZH** as well as EN (article `da68bb88`, 3/3, attempt 200, listed in
    Progress History in a fresh context). The Admin loop (ingest, publish, generate, approve) ran for both languages.
  - Reading position / "continue where you left off": `RUNS_REAL` (`PUT /api/continue/article:{id}`, Today reads
    `GET /api/continue`); was device-only.
  - Reading from a book: **`MISSING` on the lane stack** - chapter `GET` returns 503
    `reading_library_chapter_unavailable` (it returned 200 on 2026-09-29). Cause not yet isolated (G-11).
  - Writing, unsubmitted draft: `RUNS_REAL` (`PUT /api/drafts/expression:free` 200 with the backbone on); the chip still
    says "Saved on this device". Writing ZH: `RUNS_REAL` (94 Hanzi, 88/100, one issue).
  - Speaking, Situation: `RUNS_REAL` for the store (`PUT /api/responses/situation:...` 200); Scripted ZH with a microphone:
    `RUNS_REAL` (Azure `measured`, attempt stored). **Attempt History and Speaking Summary stay `MISSING`**: a fresh context
    shows 0 attempts / 0 tasks while `GET /api/speech/attempts` holds the record.
  - Vocabulary, Collections: `RUNS_REAL` once published through Admin (EN and ZH). The collection's whole-set "Save" is a
    toast and "Start review" is empty until words are saved one by one - `MISSING` (whole-collection add).
  - Word from Reading -> Vocabulary with provenance: `RUNS_REAL` EN and ZH (`POST /api/library/vocabulary` and
    `.../provenance` 200).
  - Listening, imported media (YouTube, upload): `MISSING` end to end - published with `segment_count 0`; no ASR or
    transcript editor in the content path although `POST /api/speech/transcribe` transcribes the same audio.
  - Progress Overview skills, Rank, From Your Errors: still `MISSING` - they show "-", "no milestones" and "no recent
    errors" after a session that wrote 14 reviewed essays and a graded reading set; Progress History and Evidence are
    `RUNS_REAL`.
  - Grammar: unchanged (`MISSING`, both languages); PR #67 and #68 still OPEN.
  - Speech providers (D-103): configured on the bench; Groq transcription and Azure pronunciation `RUNS_REAL` in EN and ZH.

## Decided (D-103, 2026-09-29)

- The retirements are approved: UI and routes only; domain logic and history are kept.
- Dictation stays `MISSING` until the server recomputes the deterministic score before storing it.
- Book chapters and pasted texts are `N/A_BY_CONTRACT` for comprehension, and get no dead Check
  Understanding entry.
- Metrics follow "a real metric or no metric".
- Speech providers are approved for lane E2E.
- Curated prompts go into Writing Setup, with the Prompt Bank as their destination.
- The Chinese evaluator gets a per-pair identity plus a refresh-if-stale on open that keeps
  history.

## Decisions the human is asked for (one batch) (asked; answered by D-103)

1. **Retirements (`PROPOSE_RETIRE`):**
   - the old `#/continue` room;
   - the old per-skill library rooms;
   - the old R5 grammar path and Writing's R5 `grammar_links` in the UI;
   - the old Growth summary room (covered by `#/progress`);
   - the recall task modes no frame draws.

   `#/language` is already covered.
2. **Dictation grading:** accept the client-side edit distance with the server storing the number
   (the cell becomes `N/A_BY_CONTRACT`), or move grading to the server.
3. **Book chapters and pasted texts have no comprehension assessment** (sets are keyed by
   article): confirm `N/A_BY_CONTRACT`.
4. **Profile/Progress measures** (streak, weekly minutes, goals, achievements, trends): build a
   recorded measure in D4, or keep the honest zero.
5. **A speech provider for the lane runtime** (paid, human gate), without which Shadowing,
   Pronunciation and Compare cannot be proved.
6. **The old Writing entry's curated prompt rail** (`content/texts.js`) has no home in `/next`:
   carry it into Writing's setup, or let it go.

The three research parts follow, unedited.


---

## D3 matrix, part 1: Reading, Grammar, Onboarding/Profile

Bench: `http://127.0.0.1:8021` (HEAD `ff68f45`, `codex/work`, PostgreSQL, auth `local`, one local admin
user, AI legacy runtime = Ollama `qwen3:8b`). Checked 2026-09-29. Nothing in the repository was
edited. Browser probes: `scratchpad/d3p1_browser.cjs` (EN, 1920x1080) and `scratchpad/d3p1_zh.cjs`
(ZH session + zh interface); API probes: curl and `scratchpad/d3p1_zh.py`.
Bench writes I made (test data): 2 EN + 2 ZH discussion turns (`request_id d3-probe-*`), one kept
library item (`reading`, Fox and the Grapes), one no-op profile PATCH (`goal=everyday`); the session
language was put back to `en`.

`[V]` = exercised on :8021 or in the browser. `[I]` = read from code or tests, not exercised.
Cell codes: RR = RUNS_REAL, MI = MISSING, NA = N/A_BY_CONTRACT, RET = PROPOSE_RETIRE.

Bench content counts (all [V]):

| Source | EN | ZH |
| --- | --- | --- |
| Published articles `GET /api/reading/articles?language=` | 2 (Fox and the Grapes B2, Tortoise and the Hare B2) | 1 (故乡（节选） HSK6) |
| Shared-library books `GET /api/reading/library/books?learning_language=` | 1 (Alice, 12 chapters) | 0 |
| Approved comprehension sets `GET /api/reading/practice/articles/{id}` | 0 (404 `reading_set_not_available` for both) | 0 (404) |
| Approved grammar points (`/orena-assets/content/grammar/catalog.<lang>.json`) | 0 (404) | 0 (404) |
| Grammar Lab drafts in `grammar_lab/content/en` (must NOT be read, D-101 F) | 10, all `status: draft_ai` | 0 |
| Learning languages `GET /api/platform/languages` | en | zh |

---

## 1. Reading

| flow | content | do | assess | store | return | reuse | E2E | scale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Reading (summary)** | RR (thin) | RR | MI (no sets) | MI | MI | see rows | no | no (EN 2 art + 1 book, ZH 1 art, 0 sets) |
| Reader `#/read/:id` (article) | RR [V] R1 | RR [V] R2 | NA [I] R3 | MI [V] R4 | MI [V] R5 | R6 | no | no: EN 2 / ZH 1 |
| Reader, book path `book:<id>:<ch>` | RR EN / MI ZH [V] R7 | RR [V] R7 | NA [I] R8 | MI [V] R4 | MI [V] R5 | R6 | no | no: EN 1 book (12 ch) / ZH 0 |
| Reader, own pasted text `text:` | MI [V] R9 (device only) | RR [I] | NA [I] R8 | MI [V] R9 | MI [V] R9 | R9 | no | n/a (learner's own) |
| Check Understanding `#/read/:id/check` | MI [V] C1 | RR [I] C2 (empty state [V]) | RR [I] C3 | RR [I] C4 | RR [I] C5 | C6 | no | no: EN 0 / ZH 0 sets |
| Reading Complete `#/read/:id/done` | RR [V] K1 | RR [V] K1 | NA [I] K2 | MI [V] K3 | MI [V] K3 | R6 | no | follows Reader |
| Reading Transfer `#/read/:id/transfer` | RR [V] T1 | RR [V] T1 | RR [V] T2 | MI [I] T3 | MI [I] T3 | T4 | no | follows Reader |
| Discussion `#/read/:id/discuss` | RR [V] D1 | RR [V] D1 | NA [I] D2 | RR [V] D3 | RR [V] D4 | none | **yes** | follows Reader |
| Old `#/continue` / old continuation shelf | – | – | – | – | – | RET [I] R10 | – | – |

## 2. Grammar

| flow | content | do | assess | store | return | reuse | E2E | scale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Grammar (summary)** | MI | RR (empty states only) | MI | MI | MI | see rows | no | no (0 / 0) |
| Grammar Library `#/grammar` | MI [V] G1 | RR [V] G2 (empty state) | NA [I] G3 | MI [I] G4 | MI [I] G4 | G5 | no | no: EN 0 / ZH 0 |
| Grammar Concept `#/grammar/:id` · explanation, quiz | MI [V] G1 | RR [V] G2 ("not available") | NA [I] G6 (quiz) | MI [I] G7 | MI [I] G7 | G5 | no | no: EN 0 / ZH 0 |
| Grammar Concept · Try it yourself | MI [V] G1 | RR [I] | MI [I] G8 | MI [I] G8 | MI [I] G8 | G9 | no | no |
| Grammar Lab package → Admin import/review/publish → learner source | MI [I] G10 | – | – | – | – | G10 | no | – |
| Old R5 grammar (old UI reference, `/api/library/grammar*`, `grammar_progress` by R5 id) | – | – | – | – | – | RET [I] G11 | – | – |

## 3. Onboarding / Profile

| flow | content | do | assess | store | return | reuse | E2E | scale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Onboarding/Profile (summary)** | RR | RR | NA | MI | MI | see rows | no | yes (en, zh) |
| Welcome `#/welcome` · languages step (learning + support) | RR [V] O1 | RR [V] O2 | NA [I] O3 | MI [V] O4 (learning lang) / RR [V] O5 (support) | MI [V] O4 | O6 | no | yes: en, zh |
| Welcome · level step (`declared_level`, H2) | RR [I] O7 | RR [V] O2 | NA [I] O3 | MI [V] O8 | MI [V] O8 | O9 | no | yes: en A1-C2 / zh HSK (see O7) |
| Profile `#/profile` · core (who, plan, due, saved, rank) | RR [V] P1 | RR [V] P1 | NA [I] P2 | NA [I] P2 | RR [V] P1 | none | **yes** | yes |
| Profile · streak, week minutes, daily goal, weekly goal, achievements | MI [V] P3 | – | NA | MI [I] P3 | MI [V] P3 | none | no | – |
| Settings `#/settings` · languages, plan & privacy | RR [V] S1 | RR [V] S1 | NA [I] P2 | MI [V] O4 (target lang) / RR [V] O5 (support) | MI [V] O4 | O6 | no | yes |
| Settings · Review tab (review modes/limits) | RR [I] | RR [I] | NA | MI [I] S2 | MI [I] S2 | S2 | no | – (Vocabulary/Review owner) |
| Settings · Learning tab, appearance, interface language | – | RR [I] | NA | NA/D4 [I] S3 | – | none | – | – |
| Settings · Notifications | MI [I] S4 | – (rows drawn disabled) | NA | MI | MI | none | no | – |
| Progress `#/progress` · Overview/Evidence/Rank/History | RR [V] Q1 | RR [V] Q1 | NA [I] P2 | NA [I] P2 | RR [V] Q1 | Q2 | **yes** (reading/grammar domains empty, see Q1) | yes |
| Progress · Trends, Knowing→Using, time/streak, skill % | MI [I] Q3 | – | NA | MI | MI | none | no | – |
| Old Growth summary (`ui/growth-summary.js`) | – | – | – | – | – | RET [I] Q2 | – | – |

---

## Evidence

**Reading**

- **R1** `GET /api/reading/articles?language=en` → 200, 2 items; `?language=zh` → 200, 1 item;
  `GET /api/reading/articles/c9011157-…` → 200 with `body`. Loader: `screens/reader/source.js:18-38`.
- **R2** Browser EN `/next#/read/article:c9011157-…` renders title + text; ZH session
  `/next#/read/article:c7d373fe-…` renders 故乡 with per-character pinyin; no page errors.
  Bookmark: `POST /api/library/items {kind:reading, source_id}` → 200 `relationship:kept, version:1`,
  read back with `GET /api/library/items?kind=reading&sources=…` [V] (`reader/source.js:108-114`,
  `reader/screen.js:781-784`). Aid "translation": `POST /api/reading/translate` → 200
  `{"status":"unavailable","translations":[]}` on the bench (no translation provider configured;
  aid, not a step). "Summary" has no backend (`reader/screen.js:19-21`).
- **R3** Evidence architecture §1 Reading: evidence = "submitted answers, question/source revision,
  evaluator result"; excluded claim: "reading time alone proves understanding"
  (`docs/product/ORENA_EVIDENCE_ARCHITECTURE.md:11`). Reading the text is not assessed; the assessment
  is Check Understanding.
- **R4** Position, furthest %, chapter index are written only to device memory: `memory.enter(...)`
  (`reader/screen.js:163-181`) → localStorage `orena.encounters.v1:<owner>:<lang>`
  `.continuation` (`product/memory.js:49-50`). Highlights: `orena.reader.highlights.v1:<owner>`
  (`reader/highlights.js:16-18`). Sentence notes: `orena.quicksheet.notes.v1:<owner>`
  (`screens/quick-sheet/model.js:223-224`). Browser proof: after a Reader visit the
  `continuation` list holds `article:c9011157-…` and `book:4dee…:5818…`; a fresh browser context
  (= new device) has `[]`. No server table holds reading position (tables in
  `persistence/models.py`; `reading_attempts` is check answers only). `library_items.relationship`
  allows `started` (`models.py:577`) but nothing in `/next` writes it.
- **R5** Return reads the same device list: Content Detail `placeFor` (`screens/content/model.js:85-90`),
  Discover progress (`screens/discover/model.js:31-86`), Reader reopen point
  (`reader/screen.js:163-166`). New device / new browser → progress gone [V].
- **R6** Reuse: the account work backbone `writing_coach/work_api.py` (`GET/PUT /api/works/{id}`,
  operation-id + version, `commit_mutation`) is built but `GET /api/account-backbone` →
  `{"state":"disabled"}` [V]; ACCOUNT_DATA_ARCHITECTURE §2 names "Continue", "Draft/reading
  response" and "Imported private text" as its target objects. `library_items` (`started`
  relationship, used by old `ui/collection.js:686`) can carry "started" but not a position. Old UI
  keeps continuation in the same device memory (`ui/encounter.js:94,472`), so nothing server-side to
  move. → D4.
- **R7** Book: `GET /api/reading/library/books/4dee…` → 12 chapters; chapter
  `GET …/chapters/5818…` → 200 blocks. Browser: `/next#/read/book:4dee…` shows "CHAPTER I … · 1/12".
  ZH: 0 books.
- **R8** Books and own texts have no comprehension contract: `reader/source.js:96-99` ("Books and
  imported texts have no comprehension-question contract today"); `reading_comprehension_sets` is
  keyed by article (`reading_admin_api.py:725-760`). Marked NA; **human to confirm** that book
  chapters need no assessment.
- **R9** Paste-text import writes device memory only: `memory.add({title,text})` → `imports[]`
  (`product/memory.js:346-365`; `screens/import/sheet.js:223`); Reader loads it from there and throws
  "This text is not on this device" elsewhere (`reader/source.js:68-69`). ACCOUNT_DATA_ARCHITECTURE §2:
  present authority "device work", target "account-owned content access record". Kept state of a
  `text:` item: `memory.value.kept` (`reader/source.js:110`). Reuse: work backbone (R6).
- **R10** D-101 D3 lists `#/continue` among open old flows. `/next` has no `continue` route
  (`shell/routes.js`); Today/Discover/Content draw continuation from device memory (R5). Propose
  retiring the old route once server continuation (D4) replaces it; needs approval.
- **C1** 0 approved sets on the bench for all 3 articles (`GET /api/reading/practice/articles/{id}`
  → 404 `reading_set_not_available`); `GET /api/admin/reading/articles/{id}/comprehension-sets` →
  `{"items":[]}` for all 3; `GET /api/reading/practice/next` → `{"available":false}`. Sets are
  generated by `POST /api/admin/reading/articles/{id}/comprehension-sets` (AI) and published via
  `…/comprehension-sets/{id}/status` (`reading_admin_api.py:732-826`), but **no admin UI calls these
  endpoints** (grep `comprehension-sets` over `static/` → no hits; `admin/api.js:87-125` covers
  sources, queue, articles, jobs only). Content cannot reach this flow through the product.
- **C2** Browser EN/ZH: `/check` shows "No comprehension check for this text yet" / "这篇文章暂时没有
  理解检查". Grading path: `check/screen.js:135` (set), `:203` grade, `:225` submit with operation id.
- **C3** `POST /api/reading/practice/sets/{set}/questions/{q}/grade` and `POST /attempts`
  (`reading_practice_api.py:126-183`); tests `tests/test_reading_practice_routes.py:415`.
- **C4** Table `reading_attempts` (`models.py:1276`) + `reading_ability_projections` (`:1337`);
  idempotent submit tested on PostgreSQL (`tests/test_reading_evidence_postgres.py:214,264`).
  `GET /api/reading/practice/ability` → 200 `attempts:0`.
- **C5** `GET /api/reading/practice/evidence` → 200 `{"items":[]}`; read by Reading Complete
  ("understood") and Progress Evidence (`progress/screen.js`, `api.readingEvidence`); learner-summary
  `reading` domain `checks_answered` = 0 (status `empty`) [V].
- **C6** Reuse for the missing Admin step: none in the old UI or current Admin (only
  `admin/copy.js:246,263` labels the AI capability). Backend endpoints exist; E must add the
  generate/review/publish screens.
- **K1** Browser: `/done` shows "0 saved from this text · 0 notes & highlights · — understood · Next:
  The Tortoise and the Hare". Saved words from `GET /api/library/vocabulary` (server) [V].
- **K2** A summary screen; evidence arch §1 (R3). Nothing to assess.
- **K3** "Finished" = device `continuation.within = 100` (`reader-complete/screen.js:80`,
  `content/model.js:85`); "notes & highlights" count is device (`reader-complete/screen.js:59-68`).
  No server completion record for a read.
- **T1** Browser EN and ZH render the source sentence and three modes.
- **T2** `POST /api/dictionary/spoken-response` EN → 200 in 14 s with `carried` +
  `landed_differently`; ZH (session zh) → 200 in 46 s, `available:false` (nothing named). Without the
  zh session it answers 409 "Transcript language must match the current learning language".
  Quality note: the EN answer listed the same quote as both carried and wrong (qwen3:8b).
- **T3** Nothing is written: `reading-transfer/screen.js:12-14` ("nothing is written to the learner's
  record - there is no Reading Transfer evidence contract - so "Finish" only leaves"). D-101
  Persistence requires attempt/result on the server → MISSING; D4 must also decide which evidence
  owner holds it (the evidence architecture has no producer row for it).
- **T4** Reuse: `writing_coach/work_api.py` (reading response is a target work object,
  ACCOUNT_DATA_ARCHITECTURE §2 "Draft/reading response"); the coaching call already lives in
  `infrastructure/api.js:130`.
- **D1** `GET /api/texts/discussion?source_kind=story&source_id=c9011157-…` → 200; browser `/discuss`
  shows the stored thread (EN) and the ZH thread (ZH session).
- **D2** Evidence arch §1 "Understanding": excluded claim "receiving AI text is evaluated learner
  performance" (`ORENA_EVIDENCE_ARCHITECTURE.md:17`). A Q&A thread is not assessed.
- **D3** `POST /api/texts/discussion/turns` EN → 200 in 10.5 s, turns 3-4 persisted (ollama qwen3:8b);
  ZH (session zh) → 200, `language_code: zh`. Tables `text_discussions` / `text_discussion_turns`
  (`models.py:845,1120`), idempotent by `request_id`.
- **D4** Re-GET after the posts: EN thread `turn_count 4`, ZH thread `turn_count 2`, and the browser
  reload shows them. The thread is keyed by the **session learning language**, not the text's: a ZH
  article asked about under an `en` session is stored as an `en` thread (observed; answer quality in
  ZH was also poor - it invented facts about 故乡). Not blocking, but ZH E2E requires the zh session.

**Grammar**

- **G1** `GET /orena-assets/content/grammar/catalog.en.json` and `catalog.zh.json` → 404; the seam
  reads only that static path (`product/grammar-source.js:4-24`); no `/api/grammar/v1` exists (D-100
  point 4). 10 EN drafts in `grammar_lab/content/en/` are `draft_ai` and must not be read (D-101 F).
- **G2** Browser EN: `/grammar` "No grammar points yet."; `/grammar/en.present_perfect` "This grammar
  point is not available."; ZH: "还没有语法点。". Both built on `GRAMMAR_CONTENT_CONTRACT.md` and
  verified only with the test fixture (`IMPLEMENTATION_MAP.md`, frames 44/47 "building").
- **G3** A browsing catalogue; nothing to assess.
- **G4** Library groups need learner state (recent errors, saved, suggested): contract §9 "Hợp đồng
  này không định nghĩa nơi lưu các trạng thái đó" (the contract does not define where that state is
  stored) (`GRAMMAR_CONTENT_CONTRACT.md:288-290`). Nothing is stored for Grammar Lab ids today.
- **G5** Reuse: `grammar_progress` table (`models.py:215`, unique `(user, language, lesson_id)`,
  `lesson_id String(255)`) and `/api/library/grammar/{id}/complete` (`app.py:2157-2177`) - but the
  route 404s any id that is not an R5 lesson (`active_grammar_by_id()`), so it cannot take Grammar
  Lab ids as is. `library_items.kind` already allows `grammar` (`models.py:575`) for "saved".
  learner-summary `grammar` domain reads `grammar_progress` (`patterns_marked_complete`, status
  `empty` on the bench [V]).
- **G6** Quiz: contract §7 "`answer` là chỉ số 0-based vào `options`" (the key ships in the content,
  `GRAMMAR_CONTENT_CONTRACT.md:204-219`); no server grading is defined. NA for the server grade,
  **but** the result is evidence per evidence arch §1 Grammar ("canonical Concept ID, actual response
  and existing domain judgment") → store is still required (G7).
- **G7** `grammar-concept/screen.js:9-13`: "The quiz writes nothing either (the R5 completion endpoint
  does not know Grammar Lab ids)". No read of per-point progress exists.
- **G8** Try it: contract §7 "câu học viên viết được chấm bởi engine viết hiện có (cùng đường
  Writing), và kết quả đi theo đường bằng chứng có sẵn của app" (graded by the existing writing
  engine, evidence through the app's existing path) (`GRAMMAR_CONTENT_CONTRACT.md:253-257`). The
  screen never concludes and records nothing until `pattern_rule` (PR #67) (`grammar-concept/
  screen.js:9-13`, D-101 F).
- **G9** Reuse: the writing evaluator path (`api.essays`, writing routes) and the old grammar
  transfer check `tests/test_writing_grammar_transfer.py` for how Writing records grammar use.
- **G10** D-101 E/F: approved Grammar Lab export → Admin import/review/publish → learner source.
  `static/orena/admin/*` has no grammar import (grep `grammar` in admin JS → only `copy.js`); no
  backend admin grammar route (`writing_coach/*admin*.py`). Everything in this chain is missing.
- **G11** D-101 F "No R5": the new screens read no R5; R5 ids resolve through `aliases`. The old R5
  library (`GET /api/library/grammar` → 269 lessons [V]), its completion endpoints and old UI
  (`ui/reference.js`, `ui/patterns.js`, `ui/expression.js` `completeGrammar`) are proposed for
  retirement at the cutover, with R5 completions carried over through `aliases` (contract §9 rule 2).
  Needs human approval (data carry-over is a D4 item).

**Onboarding / Profile**

- **O1** `GET /api/platform/languages` → 200, `en`, `zh`, support-language list. Level grids from the
  language registry (en A1-C2; zh HSK1-6, HSK7-9).
- **O2** Browser EN: `/next#/welcome` renders the 5 steps (Welcome, Account, Languages, Your level,
  Meet Orena). Support pick = `PATCH /api/learner-profile` (`onboarding/screen.js:303-319`).
- **O3** H2 (D-101): declared level is "the learner's self-declared current level … never measured or
  inferred". Onboarding assesses nothing.
- **O4** The learning language lives only in the **server session cookie**:
  `POST /api/platform/language` sets `request.session["language"]` (`core/platform_api.py:37-43`);
  the middleware defaults to `en` without it (`auth_support.py:409-411`). Proof: set `zh` in cookie
  jar 1 → bootstrap `active: zh`; a new cookie jar (new login/device) → `active: en` [V]. A ZH learner
  who signs in again lands in English. Not on the account → MISSING, and it also breaks H2's
  "`#/welcome` opens when there is no learning language" (there is always one, the default).
- **O5** `PATCH /api/learner-profile {expected_version, goal}` → 200, `updated_at` advanced; table
  `user_language_profiles` (account + language). `support_language` is an account setting
  (`account_profile.py:75-83`) read back by `GET /api/learner-profile` [V].
- **O6** Reuse: `user_language_profiles` / `account_profile.py` settings pattern (the H2 proposal
  already adds a column there); the old UI's language switch uses the same session endpoint, so
  nothing server-side to reuse for the learning language.
- **O7** Levels offered: en A1-C2, zh HSK1-6 (H2: HSK 7-9 is one band). `declaredLevelPatch` sends
  CEFR only; an HSK pick is never sent (`onboarding/model.js:188-199`).
- **O8** `PATCH /api/learner-profile {declared_level:"B1"}` → **501**
  `{"reason":"not_yet_stored","field":"declared_level"}` [V]; `account_profile.py:94-95`
  `stored=False`; `GET` shows `declared_level: ""` (en and zh). The pick survives only in
  sessionStorage `orena.onboarding.level` and the in-memory shell context. `entryRoute` ignores the
  level (`shell/routes.js:77-87`).
- **O9** Reuse: `docs/project/proposals/DECLARED_LEVEL_STORAGE.md` rev 2 (PROPOSED; review
  `…REVIEW.md` = REQUEST CHANGES) - a column on `user_language_profiles`, fold into D4.
- **P1** `GET /api/library/vocabulary/summary` → 200 (due 2, saved 3021, ladder); `GET
  /api/product/commerce` → 200 plan Free; `GET /api/me` → 200. Browser EN and ZH `/profile` render.
- **P2** Read model: evidence arch §5 "Profile composes it with declared goals/preferences and
  commerce facts through read APIs; none of those panels writes another domain's state"
  (`ORENA_EVIDENCE_ARCHITECTURE.md:92-97`).
- **P3** No backend measure for streak, week minutes, daily goal, weekly-goal count; achievements
  `{"status":"unavailable","reason":"no_approved_policy"}` in `GET /api/learner-summary` [V]
  (`profile/model.js:11-17`, UI_BACKEND_GAPS N-21/N-25). They render 0 / "Not tracked yet". Human
  decision: build a study-time/streak aggregate (D4) or accept the design element at its honest zero.
- **S1** Browser `/settings` renders Languages (English / Chinese · 中文, support language) and Plan.
  Target pick = session only (O4); support pick = profile PATCH (O5).
- **S2** Review modes/limits: `memory.value.reviewSettings` in `orena.encounters.v1:<owner>:<lang>`
  (`settings/screen.js:186-191,333`; `product/memory.js:62-68`). Learner preference with learning
  effect, device only. Owner is Vocabulary/Review (part 2/3); listed here because Settings draws it.
- **S3** Reader text size `orena.reader` (`product/reader-settings.js:68`), transcript prefs
  `orena.stage` (`product/transcript-stage.js:18`), `orena.appearance` (`kit/device.js:13`):
  presentation, device by design (D-101 Persistence). Interface language `orena.interface`
  (`kit/boot.js:19`): the account architecture names it an account-wide setting, but it is
  `stored=False` (`account_profile.py:80-83`) - D4 to decide.
- **S4** Notifications: "no real source anywhere … every row drawn disabled" (`settings/screen.js:13-14`,
  UI_BACKEND_GAPS N-28).
- **Q1** `GET /api/learner-summary?window=90d` → 200: writing current 13, listening 5, speaking 50,
  language 200, **reading empty 0** (no sets, C1), **grammar empty 0** (R5 table, G5). Browser
  `/progress?tab=history` lists today's listening/dictation entries (server records). Reads:
  `api.essays` (200), `api.readingEvidence` (200), `api.speakingAttempts` → `/api/speech/attempts`,
  `api.practiceOutcomes` (200 empty).
- **Q2** Old `ui/growth-summary.js` shows the same learner-summary domains; Progress Overview covers
  it. Propose retiring it at the cutover (D-101 lists "Growth summary" as an open old flow). Needs
  approval.
- **Q3** `progress/model.js:4-10`: no trend, daily time, streak or per-skill % measure exists
  (learner_summary `growth.status` is always "unavailable"). Trends and Knowing→Using render empty or
  zero.

---

## Device-only learner state (input to D4)

| Key / place | What | Skill | Why it matters |
| --- | --- | --- | --- |
| localStorage `orena.encounters.v1:<owner>:<lang>` → `continuation[]` | reading position, furthest %, chapter index, "finished" (within = 100) | Reading | progress; lost on a new device (R4, R5) |
| same → `imports[]` | learner's own pasted texts (`text:` ids, max 20, 12 000 chars) | Reading | learner content; unreadable elsewhere (R9) |
| same → `kept[]` | bookmark of a `text:` item | Reading | kept state for own texts |
| same → `reviewSettings` | review modes and limits | Settings (Vocabulary/Review owner) | learner preference that shapes review (S2) |
| localStorage `orena.reader.highlights.v1:<owner>` | sentence highlights per content id | Reading | learner-owned annotations |
| localStorage `orena.quicksheet.notes.v1:<owner>` | sentence notes (Reader, other rooms) | Reading (+ shared) | learner-owned notes |
| server **session cookie** `session["language"]` | active learning language | Onboarding/Settings | not on the account: a new login resets to `en` (O4) |
| sessionStorage `orena.onboarding.level` + shell context `level` | declared level pick | Onboarding | server answers 501 (O8); H2 |
| (nothing, not even device) | Reading Transfer answers + coaching | Reading | attempt/result required on server (T3) |
| (nothing, not even device) | Grammar quiz answers, Try-it sentences, per-point progress / saved | Grammar | G7, G8 |
| localStorage `orena.interface` | interface language | Settings | account-wide per architecture, `stored=False`; D4 to decide (S3) |
| `orena.reader`, `orena.stage`, `orena.appearance`, sessionStorage `orena.onboarding.step`, `orena.next.navOrigin/depth` | presentation / navigation | – | device by design, not D4 |


---

## D3 part 2: Listening, Dictation, Shadowing, Speaking/Pronunciation

HEAD `ff68f45` (codex/work), bench `http://127.0.0.1:8021` (auth local, PostgreSQL), 2026-09-29.
Read-only on the repo. Probes and raw output: `scratchpad/d3p2/` (`probe.py`, `probe_zh.py`,
`probe_eval.py`, `ui_probe.cjs`, `voice_probe.cjs`, `respond_probe.cjs`, `progress_probe.cjs`,
`ui_en.json`, `ui_zh.json`, `ai_probe.txt`, `eval_probe.txt`).

How ZH was exercised: `POST /api/platform/language {"language":"zh"}` sets only the requesting
client's session scope (`writing_coach/core/platform_api.py:37-43`, read by `auth_support.py:410`),
so no stored profile was changed. Each probe used its own cookie jar or browser context.

**Bench limit that blocks every recorded take:** `GET /api/speech/status` returns
`{"configured":false,...,"pronunciation":{"configured":false}}`. With a generated 1.5 s 16 kHz WAV,
`POST /api/speech/pronunciation` returns 503 `pronunciation_unconfigured` and
`POST /api/speech/transcribe` returns 503 `speech_asr_unconfigured`, in both EN and ZH. The lane
runtime has no Azure Speech or Groq ASR key (`.env.example:66-89`), and adding a paid provider is a
human gate. Those cells are marked `MISSING (env)`: the code path exists, but the runtime cannot
run it. The 100 EN/ZH `speaking_attempts` rows already on the bench came from a
`stub-for-verification` provider, so they are not real evidence.

Legend: RR = RUNS_REAL, MS = MISSING, NA = N/A_BY_CONTRACT, [V] = verified, [I] = inferred.
Evidence IDs are in brackets, e.g. (L1.c).

## Skill: Listening

| flow | content | do | assess | store | return | reuse | E2E | scale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Listening (summary)** | RR [V] | RR [V] | NA / RR | **MS** (workspace, React) / RR (Respond) | **MS** / RR | see rows | **no** | **no**: EN 2 / ZH 4 lessons |
| Listening Workspace `#/listen/:id` (L1) | RR [V] (L1.c) | RR [V] render, [I] playback (L1.d) | NA (L1.a) | **MS**: place and "listened" live only on the device (L1.s) | **MS**: place comes back from device memory (L1.r) | none on the server; D4 (L1.u) | no | no: EN 2 lessons / 8 segments, ZH 4 / 13 |
| React / Reuse `#/listen/:id/react` (L2) | RR [V] (L2.c) | RR [I] typed; spoken = MS (env) (L2.d) | RR [V] coaching API EN/ZH (L2.a) | **MS**: nothing persisted (L2.s) | **MS** (L2.r) | `capabilities/voice-feedback.js#evaluateVoice`, `ui/spoken-coaching.js` (L2.u) | no | no: same lessons |
| Respond to Content `#/respond/:id` (L3) | RR [V] (L3.c) | RR [V] (L3.d) | RR [V] `/api/evaluate` EN+ZH (L3.a) | RR [V] `essays` (L3.s) | RR [V] Progress History/Evidence (L3.r) | n/a | **yes** | no: EN 2 / ZH 4 listening sources, plus reading sources (not counted here) |

## Skill: Dictation

| flow | content | do | assess | store | return | reuse | E2E | scale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Dictation (summary)** | RR [V] | RR [V] | **MS** (server-side), needs a decision (D.a) | RR [V] | RR [V] | none | **no** (yes if the human accepts the client grader) | **no**: EN 2 / ZH 4 lessons |
| Dictation `#/listen/:id/dictation` (D) | RR [V] (D.c) | RR [V] EN+ZH in the browser (D.d) | **MS**: grading runs in the browser and the server stores the client's number (D.a) | RR [V] `listening_progress` (D.s) | RR [V] reload plus Progress (D.r) | none (D.u) | no | no: EN 8 segments / ZH 13 |

## Skill: Shadowing

| flow | content | do | assess | store | return | reuse | E2E | scale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Shadowing (summary)** | RR [V] | **MS (env)** | **MS (env)** | RR [V] API | **MS** | `ui/speaking-workspace.js` | **no** | **no**: EN 2 / ZH 4 |
| Shadowing `#/listen/:id/shadow` (S) | RR [V] (S.c) | **MS (env)**: a take cannot finish on the bench (S.d) | **MS (env)**: pronunciation returns 503 (S.a) | RR [V] `shadowing_progress` API; attempt record [I] (S.s) | **MS** [V]: rounds are never read back or shown (S.r) | `ui/speaking-workspace.js:622` (S.u) | no | no |

## Skill: Speaking / Pronunciation

| flow | content | do | assess | store | return | reuse | E2E | scale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Speaking (summary)** | RR [V] | RR typed / **MS (env)** recorded | RR coaching / **MS (env)** pronunciation | RR `speaking_attempts` for scripted takes / **MS** for free speech, conversation and summary | RR in Progress / **MS** in the rooms | `capabilities/voice-feedback.js`, `ui/voice-response.js`, `ui/speaking-free.js` | **no** | **no**: speaking EN 2 / ZH 4 items; voice invitations EN 3 / ZH 3 |
| Scripted Pronunciation `#/speak/:id` (P1) | RR [V] (P1.c) | **MS (env)** (P1.d) | **MS (env)** 503; `/api/speech/evaluation` RR [V] (P1.a) | RR [V] `speaking_attempts` (P1.s) | RR [V] Progress History/Evidence (P1.r) | n/a | no | no: EN 2 items / 8 lines, ZH 4 / 13 |
| Compare With Model `#/speak/:id/compare` (P2) | RR [V] (P2.c) | **MS (env)** (P2.d) | **MS (env)**; pitch contour is browser-only (P2.a) | RR [I] same recorder writes `speaking_attempts` (P2.s) | **MS** [V]: reads only this tab's takes (P2.r) | `ui/voice-response.js:130` (P2.u) | no | no |
| Attempt History `#/speak/:id/attempts` (P3) | RR [V] (P3.c) | RR [V] view opens (P3.d) | NA: a view of takes (P3.a) | **MS** [V]: lists the session/IndexedDB take store, not the server (P3.s) | **MS** [V]: the server holds the line's attempt, the room shows "Attempts 0" (P3.r) | `api.speakingAttempts(limit, assetId, segmentId)` + `ui/voice-response.js:130` (P3.u) | no | no |
| Speaking Summary `#/speak-summary` (P4) | NA: no content of its own (P4.c) | RR [V] renders (P4.d) | NA: summary only (P4.a) | **MS** [V]: `sessionStorage` (P4.s) | **MS** [V]: a new session shows nothing done (P4.r) | `api.speakingAttempts` / `api.learnerSummary` speaking domain (P4.u) | no | n/a |
| Free Talk `#/free-talk` (P5) | RR [V]: client-bundled invitations EN 3 / ZH 3 (P5.c) | RR [I] typed; recorded = MS (env) (P5.d) | RR [V] coaching API; unscripted pronunciation not called (P5.a) | **MS**: nothing reaches the server (P5.s) | **MS** (P5.r) | `capabilities/voice-feedback.js#evaluateVoice`, `ui/speaking-free.js:213` (P5.u) | no | no: 3 / 3 |
| Conversation `#/conversation` (P6) | RR [V]: invitations plus AI partner (P6.c) | RR [V] typed turn EN+ZH (P6.d) | RR [V] API / [I] UI "how did it land" coaching (P6.a) | **MS** [V]: device memory only (P6.s) | **MS** [V]: reload returns to the scenario picker (P6.r) | `product/conversation.js`, `ui/conversation.js` (device only); server work = D4 (P6.u) | no | no: 3 / 3 |
| Situation Reaction `#/situation` (P7) | RR [V]: invitations EN 3 / ZH 3 (P7.c) | RR [V] typed EN+ZH (P7.d) | RR [V] coaching in the UI, EN+ZH (P7.a) | **MS** [V]: `sessionStorage` ledger only (P7.s) | **MS** (P7.r) | `capabilities/voice-feedback.js#evaluateVoice` (P7.u) | no | no: 3 / 3 |

The four deferred Coming-soon screens that belong to these skills (Retell, Timed Reaction, Mock
Interview, Sound/Tone) are not rows here.

## Evidence

### Content counts on the bench

- `GET /api/listening/library?language=en` returns 2 published items: `en-science-cosmic-calendar`
  (6 lines) and `en-daily-pen-in-my-bag` (2 lines).
- `GET /api/listening/library?language=zh` returns 4: `zh-daily-what-is-this` (1),
  `zh-culture-nationalities` (2), `zh-culture-where-are-you-from` (3) and
  `zh-technology-search-wikipedia` (7).
- Every item has `available_modes` `[listen, active, dictation, shadowing]` and
  `is_development_candidate:false`.
- `GET /api/speaking/library` returns EN 2 and ZH 4 items. All are `media:` clips derived from
  listening; no scripted speaking items are published.
- Voice invitations are `static/orena/content/voice-invitations.js`: 3 EN and 3 ZH, bundled in the
  client, with no server catalog and no Admin path.

### Listening Workspace (L1)

- **L1.c** `ui_en.json`/`ui_zh.json`: the lesson GET returns 200 and the transcript renders in EN
  ("A pen in my bag") and ZH ("这是什么？"). There is no load error and no page error.
- **L1.d** Transcript, speed and line controls render. Audio is a Wikimedia Commons `.ogg`;
  playback was not exercised headless, so it is [I].
- **L1.a** Product Constitution §17, lines 579-580: "The learner may watch, listen, follow, and
  understand for the entire clip without entering Dictation or Shadowing." Follow defines no
  assessment; the assessed actions are the Dictation and Shadowing rows.
- **L1.s** The only server writes are vocabulary saves (`screens/listening/screen.js:84-88`,
  `/api/library/vocabulary`).
- **L1.s** The place and continuation are written only to device memory:
  `c.memory.enter({id, title, segment})` at `screens/listening/screen.js:117-121`, stored under
  `orena.encounters.v1:<owner>:<lang>`.
- **L1.s** No server record says the learner followed or finished a clip. Account Data
  Architecture §2 lists "Continue | device references | account work-derived index" as the target.
- **L1.r** `screens/listening/screen.js:60` restores the place with
  `placeFor(c.memory?.value?.continuation, contentId)`, which is the device. Only the dictation
  dots come from the server (`:76`, `GET /api/listening/progress`).
- **L1.u** The old `ui/encounter.js` also keeps continuation on the device, so there is nothing to
  reuse. This goes to D4.

### React / Reuse (L2)

- **L2.c** The lesson loads (200) in EN and ZH and the React screen renders.
- **L2.d** Typed answer: `screens/react/screen.js:186-191`, not driven in the browser, so [I].
  Spoken answer: `api.transcribeSpeech` at `:290` returns 503 on the bench.
- **L2.a** `POST /api/dictionary/spoken-response` returned 200 in 11.7 s (EN) and 12.9 s (ZH)
  (`ai_probe.txt`). The contract says "This is coaching, not measurement"
  (`writing_coach/media_interaction.py:716-724`).
- **L2.s** No `saveSpeakingAttempt` call and no other write exist in `screens/react/`; the
  coaching result lives only in the tab.
- **L2.u** `capabilities/voice-feedback.js` (already shared) transcribes, evaluates and saves an
  audio-free attempt through `POST /api/speech/attempts`. The old `ui/voice-response.js` and
  `ui/speaking-free.js` use it.

### Respond to Content (L3)

- **L3.c** Sources: listening lesson, reading article and book chapter
  (`screens/respond/screen.js:53-78`). It rendered in EN and ZH.
- **L3.d** `respond_probe.cjs`: typed about 50 words and pressed "Get feedback". The request
  returned 200 and the evaluation rendered (fixes, "Next step", Revise / Ask Orena why / Done).
- **L3.a** `POST /api/evaluate` returned 200: EN essay id 14 (32.6 s) and ZH essay id 2 (26.9 s),
  evaluator `ollama:qwen3:8b` (`eval_probe.txt`).
- **L3.s** Both rows are in `GET /api/essays` with `language_code` en and zh (writing repository).
- **L3.r** `/next#/progress?tab=history` and `?tab=evidence` list "Writing · What is your opinion
  of this clip? · 78" (EN) and "你对这段内容有什么看法？ · 75" (ZH) after reload
  (`progress_probe.cjs`).
- **L3.r gap:** the essay carries its source only as the free text
  `writing_context.journal_context`. The Respond room never reopens a previous response to the
  same source.

### Dictation (D)

- **D.c** Every listening item offers dictation. The EN lesson has 2 segments; the ZH
  `zh-daily-what-is-this` has 1 segment of 12 s holding the whole dialogue.
- **D.d** `ui_probe.cjs`, EN and ZH: fill `[data-input]` and click `[data-check]` gives
  `POST /api/listening/progress 200`.
- **D.a** `checkAnswer` runs the client evaluator `capabilities/dictation-evaluator.js`.
  `POST /api/listening/progress` (`writing_coach/listening_api.py:586-604`) stores the
  client-reported `best_accuracy_percent` and does not grade it again.
- **D.a** The grader is deterministic (edit distance) and has no server equivalent. The human
  decides whether server-side grading is required. If not, reclassify this cell as
  N/A_BY_CONTRACT.
- **D.s** Table `listening_progress` (`writing_coach/persistence/models.py:280`).
  `POST /api/listening/progress` returned 200 in EN scope (`1df7abc9…`) and ZH scope
  (`19d4ed2e…`, `language:"zh"`); `GET` returns the same rows.
- **D.r** After reload the room shows "2 of 2 checked" (EN) and "1 of 1 checked" (ZH), with dot
  states from `GET /api/listening/progress`.
- **D.r** Progress History shows "Listening · Dictation · 100 / 13", and learner-summary returns
  `dictation_best_match` observations.

### Shadowing (S)

- **S.c** The shadowing screen renders the EN and ZH lines after lesson GET 200.
- **S.d/S.a** The take goes through `createSpeakingTake`, then `api.assessPronunciation`
  (`capabilities/speaking-take.js:127`), which returns 503 `pronunciation_unconfigured` on the
  bench. `keepRound()` runs only after a real result (`screens/shadowing/screen.js:314-320`).
- **S.s** Table `shadowing_progress` (`models.py:317`). `POST /api/listening/shadowing-progress`
  returned 200 in EN and ZH scope, and `GET` returned the rows (EN `completed_rounds:14` was kept,
  because the server never lowers a count).
- **S.s** The attempt record, through `keep` in `speaking-take.js:141-160`, is [I].
- **S.r** `api.shadowingProgress` is called only inside `keepRound`
  (`screens/shadowing/screen.js:381`), so the room never shows past rounds.
- **S.r** `writing_coach/learner_summary.py` has no shadowing domain, and the Progress probe found
  no "shadow" text in History or Evidence (EN or ZH).
- **S.u** Old `ui/speaking-workspace.js:622` reads `api.shadowingProgress(source.assetId)` when the
  room opens.

### Scripted Pronunciation (P1)

- **P1.c** `#/speak/media:en-daily-pen-in-my-bag` shows "Target sentence Anna, do you have a pen?"
  and the ZH item shows its line. Both come from lesson GET 200 through
  `product/speaking-source.js`.
- **P1.d/P1.a** The take path is `product/speaking-recorder.js`, then `speaking-take.js:127`,
  which returns 503 on the bench.
- **P1.a** The deterministic normaliser `POST /api/speech/evaluation` returned 200 in ZH with a
  probe envelope (`speaking_evaluator.py`).
- **P1.s** Table `speaking_attempts` (`models.py:347`). `POST /api/speech/attempts` in ZH scope
  returned 200, item `daf15859…` (take `d3-probe:30d6a4b6`); `GET ?asset_id&segment_id` returns it.
- **P1.s** Scope is enforced: an EN-scope post of language `zh` returns 422 "language does not
  match the learner scope" (`speech_api.py:128-130`).
- **P1.r** `screens/progress/screen.js:84` calls `api.speakingAttempts(30)`. History and Evidence
  list the "Speaking" rows in EN and ZH after reload.

### Compare With Model (P2)

- **P2.c** Renders "Hear model" and the line in EN and ZH.
- **P2.a** Pronunciation uses the same recorder and returns 503. The contour comes from
  `capabilities/audio-analysis.js` and is measured in the browser only.
- **P2.s** `createSpeakingRecorder` should write through the same `speaking-take` path. Not
  exercised, so [I].
- **P2.r** `screens/compare/screen.js:28,71` reads `listTakes` from `product/take-store.js`
  (session Map plus opt-in IndexedDB). It makes no server read.

### Attempt History (P3)

- **P3.d** The screen opens with "Attempts 0 / Best 0".
- **P3.s/P3.r** `screens/attempts/screen.js:16,35` calls `listTakes` and `keepRecent`, the device
  only.
- **P3.r** Verified in ZH: the server has an attempt for
  `commons-zh-lesson-7-dialogue-1:000` (`GET /api/speech/attempts?...` returns 1 item), yet
  `/next#/speak/media:zh-daily-what-is-this/attempts` shows "Attempts 0". The screen's own copy
  says scores are kept without audio, but it does not show them.
- **P3.u** `api.speakingAttempts(limit, assetId, segmentId)` already exists at
  `infrastructure/api.js:441`. Old `ui/voice-response.js:130` reads it per segment.

### Speaking Summary (P4)

- **P4.s** `product/speaking-session.js:10` stores key `orena.speaking.session.v1` in
  `sessionStorage`, and its header calls this device memory by design.
- **P4.r** After a new context and a completed Situation, the room shows "Buổi này chưa ghi nhận
  gì" (nothing recorded), even though the server holds speaking attempts. D-101 says
  "completion/history" must be on the server.
- **P4.u** Derive the summary from `GET /api/speech/attempts` over the session window, or from the
  `learner-summary` speaking domain (`writing_coach/learner_summary.py:194`).

### Free Talk (P5)

- **P5.c** Rendered topics: EN "Make room for someone…" and ZH "带一个人认识你的城市…". The page
  also calls `GET /api/library/vocabulary?limit=4&order=recent` (200).
- **P5.d** The typed path (`screens/free-talk/screen.js:122,296`) was not driven. The spoken path
  (`:264` transcribe) returns 503.
- **P5.a** Coaching `:313` returned 200 through the API. New Free Talk never calls
  `assessPronunciation(..., 'unscripted')`; old `ui/speaking-free.js:213` did.
- **P5.s** Only `logSpeakingTask` (`:224`, `sessionStorage`) is written. There is no
  `saveSpeakingAttempt`.
- **P5.s** The server already accepts free expression: "Free expression has no reference line. It
  uses the same audio-free evidence record" (`speech_api.py:134-135`).
- **P5.u** `capabilities/voice-feedback.js#evaluateVoice`, as `ui/speaking-free.js:24,214` uses it.

### Conversation (P6)

- **P6.c/P6.d** `voice_probe.cjs`: Start, type a turn, submit. `POST /api/dictionary/conversation-turn`
  returned 200 in EN (8.6 s, reply plus VI meaning) and ZH (1.3 s).
- **P6.s** `memory.conversation(convo)` at `screens/conversation/screen.js:71-74` stores under
  `orena.encounters.v1:local:en` (1482 B) and `…:zh` (1194 B) in `localStorage`.
- **P6.s** The Account Data Architecture §2 row is "Conversation | device sequence | account work
  with ordered immutable turns" (target, not yet built).
- **P6.r** After reload the room shows the scenario picker, not the conversation, and nothing is
  on the server.

### Situation Reaction (P7)

- **P7.d/P7.a** `voice_probe.cjs`: typed an answer and pressed Submit.
  `POST /api/dictionary/spoken-response` returned 200 and the room rendered "One useful
  improvement · … / Natural alternative · …" in EN and ZH.
- **P7.s** Only `logSpeakingTask` (`screens/situation/screen.js:121`, `sessionStorage`) is
  written.

### Problems found along the way

These are not D3 cells, but each can give a learner wrong data or wrong grading (D-101 exceptions).

1. **Listening progress has no scope check (wrong data).** `POST /api/listening/progress` and
   `/shadowing-progress` accept an asset of any language in the current scope. A sessionless probe
   stored the ZH asset `commons-zh-lesson-7-dialogue-1` as `language:"en"`, and EN Progress now
   shows "Listening · Dictation · 12" for a Chinese line. `speech_api.py:128-130` rejects the same
   mismatch for speaking; `listening_api.py:586-625` does not. (Row `606aaa51…` is my probe data
   on the bench.)
2. **An unmeasured score is shown as 0 (wrong data).** A speaking attempt with
   `pronunciation:null` (fluency 65) appears in ZH Progress History and Evidence as
   "Speaking · 这是什么 · 0". This row is my probe, but a real free-expression or unmeasured take
   would show the same.
3. **Coaching answers in the wrong language (learner correctness).** ZH `spoken-response` with
   `target_language:"en"` came back with its `why` in Chinese (API probe). In the UI, the ZH
   Situation "useful improvement" was also in Chinese rather than the support language. Seen with
   `ollama:qwen3:8b`.
4. **One ZH lesson is a single long line (content quality).** `zh-daily-what-is-this` is one 12 s
   segment holding the whole six-sentence dialogue with speaker labels. It is too long for
   Dictation, Shadowing or Scripted Pronunciation as one line.

## Device-only learner state (feeds D4)

| key / store | writer | what it is | D4? |
| --- | --- | --- | --- |
| `localStorage orena.encounters.v1:<owner>:<lang>` → `.continuation` | `screens/listening/screen.js:117-121` (`product/memory.js#enter`) | listening place and continuation per clip | yes (Continue / work index) |
| same → `.answers[<asset>#<segment>]` | `screens/dictation/screen.js:158-167` | unsent dictation draft | yes (draft/work), low priority |
| same → `.conversations` | `screens/conversation/screen.js:71-74` (`product/memory.js#conversation`) | whole conversation: turns and coaching | **yes** (Conversation work, Account Data Architecture §2/§3) |
| same → `.imports` | `screens/respond/screen.js:88` | learner's own imported `text:` source for Respond | yes (imported private text; owned by Content/Library) |
| `sessionStorage orena.speaking.session.v1` | `product/speaking-session.js` (speak, free-talk, conversation, situation) | this session's speaking tasks, feeding Speaking Summary | yes: derive from server attempts rather than add a table |
| module memory `take-store.js` `rich`/`attemptIds` maps, plus IndexedDB `orena-speaking/attempts` (opt-in) | `product/take-store.js`, `capabilities/speaking-attempts.js` | per-line take list: audio blobs, overall score, flagged words | scores: **yes**, read `speaking_attempts` instead. Audio: no; transient by design (Account Data Architecture §2, "Microphone raw audio") |
| `localStorage orena.speaking.keepRecent` | `capabilities/speaking-attempts.js:13` | opt-in to keep recordings on the device | no (device preference) |
| `localStorage orena.stage` | `product/transcript-stage.js:18` | transcript presentation stage | no (presentation) |
| none (never stored) | React, Free Talk, Situation | coaching results and the free-speech attempt | **yes**: `speaking_attempts` already accepts free expression (`speech_api.py:134`); coaching text has no store |
| none (never read back) | Shadowing | rounds are stored on the server but never shown | read-side only; no schema needed |


---

## D3 matrix — part 3: Writing · Vocabulary/Review · Orena · Navigation/continuation · Open old flows

Bench: `http://127.0.0.1:8021` (PostgreSQL, auth local, `GET /api/health` → `schema_version 11`,
`ai_ready true`), HEAD `ff68f45` on `codex/work`, 2026-09-29. Read-only on the repo; learner test
records were created on the bench only (essays 12 and 13, saved word `bench`, one review grade).
Active learning language on the bench was **en** throughout (`GET /api/session/bootstrap`
`language.active: "en"`). I did not change the profile, because the other D3 agents share the
bench. Every ZH cell that needs an active-zh profile is therefore **[I]**, and the endpoints
refuse cross-language calls as designed (`POST /api/dictionary/word-detail` with
`source_language: zh` → `409 "Transcript language must match the current learning language."`).
The AI provider was left as it was: `writing_evaluator` has no saved config; evaluations ran on
`ollama:qwen3:8b` at about 48 s each.

Browser: headless Chrome on `/next` at 1920x1080, EN, light. Scripts: `scratchpad/d3p3*.cjs`,
output in `scratchpad/d3p3_out.txt`. No page errors on any route I opened.

Legend: RR = RUNS_REAL · M = MISSING · N/A = N/A_BY_CONTRACT · RET = PROPOSE_RETIRE · [V] verified
· [I] inferred. Deferred (not listed): Context Rewrite, Timed Writing, Timed Recall, Context
Transfer.

---

## 1. Writing

| flow | content | do | assess | store | return | reuse | E2E | scale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Writing (skill)** | RR EN [V] / ZH [I] | RR [V] | RR [V] | RR essays / **M draft** | RR [V] | draft-sync + work_api exist | **no** | n/a (learner-authored); curated prompts 0 in /next |
| W1 Writing compose + review (`#/write`, `#/write/:id`, Prompt Setup sheet, keep) | RR [V] W1c | RR [V] W1d | RR [V] W1a | RR essays [V] W1s1 · **M draft** [V] W1s2 | RR [V] W1r | `product/draft-sync.js` + `writing_coach/work_api.py` (flag); `ui/writing-entry.js` prompt rail | no | EN 14 essays on bench, ZH [I]; prompt catalogue: none in /next |
| W2 Compare Versions (`#/write/:id/compare`) | RR [V] W2c | RR [V] | RR [V] W2a | RR [V] W2s | RR [V] W2r | none needed | yes (EN) · ZH [I] | EN series 12 (2 versions) |

## 2. Vocabulary / Review

| flow | content | do | assess | store | return | reuse | E2E | scale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Vocabulary/Review (skill)** | RR (feed, lookup) / **M curated collections** | RR | RR (review scheduler) | RR saved_words / **M notes, errors drill** | RR | Admin vocab publish; `writing_errors` | **no** | feed 5/day EN · 5/day ZH; curated collections EN 0 / ZH 0; catalogue search 0/0 |
| V1 Word Quick Sheet (overlay) | RR [V] V1c | RR API [V] / UI tap [I] | N/A V-na | RR [V] V1s | RR [V] V1r | reimplemented, see V1x | yes (EN) · ZH [I] | AI lookup, open-ended |
| V2 Sentence Quick Sheet (overlay) | RR [V] V2c | RR API [V] / UI [I] | N/A V-na | **M** notes / "Save highlight" V2s | **M** V2r | none (no server shape) | no | AI lookup |
| V3 Word Detail (`#/word/:id`) | RR [V] V3c | RR [V] | N/A V-na | RR [V] | RR [V] V3r | — | yes (EN) · ZH [I] | clips 0 for `bench`; audio unavailable |
| V4 My Library (`#/library`) | RR [V] V4c | RR [V] | N/A V-na | RR [V] | RR [V] | — | yes (EN) · ZH [I] | EN 3021 saved (seeded), ZH [I] |
| V5 Collection Detail (`#/collection/:id`) | **M** [V] V5c | **M** (nothing to open) | N/A V-na | **M** V5s | **M** [I] | `static/orena/admin/imports.js`, `admin/content.js`, `admin_console_api.py:1023` | no | **EN 0 / ZH 0** published collections |
| V6 Review Session (`#/review`) | RR [V] V6c | RR [V] V6d | RR [V] V6a | RR [V] V6s | RR [V] V6r | — | yes (EN) · ZH [I] | EN 2 due at test time |
| V7 Vocabulary Daily Feed (`#/feed`) | RR [V] V7c | RR [V] | N/A V-na | RR [V] V7s | RR [V] V7r | — | yes (EN) · ZH content [V], UI [I] | 5 EN / 5 ZH per day |
| V8 From Your Errors (`#/from-your-errors`) | **M** [V] V8c | **M** (empty state only) [V] | **M** V8a | **M** V8s | **M** V8r | `writing_errors` table (models.py:130), `GET /api/essays/{id}` issues | no | **0 / 0**; the source can never fill (V8c) |

**Quick Sheet and `capabilities/lexical.js`.** The new Quick Sheet does **not** reuse
`capabilities/lexical.js`. It is its own implementation (`screens/quick-sheet/sheet.js`) over the
same server contracts: `POST /api/dictionary/word-detail` (`depth:'sheet'`),
`POST /api/dictionary/sentence-sheet` and `POST /api/library/vocabulary`. Nothing in `/next`
imports `capabilities/lexical.js`. The new Reader has its own tap layer,
`screens/reader/lexical.js`, which shares only `product/word-span.js`.
`capabilities/lexical.js` still imports `../ui/html.js` (line 24) and `../ui/quick-sheet.js` (line
25), so it and `ui/quick-sheet.js` belong to the old UI alone and can go at the cutover. What
survives is the server lookup contract, not the client module.

## 3. Orena (the panel runs on the contract mock by design until G)

| flow | content | do | assess | store | return | reuse | E2E | scale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Orena (skill)** | **M·G** (mock) | **M·G** (mock) | N/A O-na | N/A (device by contract) O-st | N/A (device) | intelligence lane `/api/agent/*` | **no (until G)** | n/a |
| O1 Orena Home (`#/orena`) | **M·G** [V] O1 | **M·G** [V] O1 | N/A | N/A O-st | N/A [I] | `agent/transport.js` live path already written | no | — |
| O2 Contextual panel (from any surface) | **M·G** [I] O2 | **M·G** [I] | N/A | N/A O-st | N/A | `screens/orena/dispatcher-setup.js` (actions call real APIs) | no | — |
| O3 Voice mode (inline + immersive) | **M·G** [I] O3 | STT RR-partial [I] / reply **M·G** | N/A | N/A | N/A | `capabilities/audio-recorder.js`, `POST /api/speech/transcribe` | no | — |

**What G must prove on the lane runtime** (D-101 G, contract v5), in EN and ZH, with
`AGENT_LIVE = true` (`static/orena/agent/transport.js:14`, `false` today):
1. A `GET /api/agent/capabilities` 404 hides Orena. It is 404 on :8021 today [V].
2. SSE turns stream: `session` first, `done`/`error` last.
3. A 409 `target_language_mismatch` keeps the message unsent and re-reads the learning language.
4. A 429 honours `Retry-After`.
5. `context.address` is applied.
6. Actions are only **offered**, never claimed as done (contract line 339).
7. The opening turn (`trigger:"open"`) comes from real learner data (due words, the last essay),
   not a canned greeting.
8. Every error claim cites `evidence` from a server record (contract §5.3, line 197).
9. Voice: transcribe → a live turn → spoken reply, with no fabricated transcript.
10. The panel's actions (save word, open review, and so on) land in the real stores.
11. Each surface has a one-line purpose in en/vi/zh.

## 4. Navigation / continuation surfaces (only their continuation and progress)

| flow | content | do | assess | store | return | reuse | E2E | scale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Continuation (cross-skill)** | RR | RR | N/A N-na | **M** (device-only) N-st | **M** N-rt | `/api/collection` (account durability), `api.listeningProgress`, reading attempts, `work_api` | **no** | — |
| T Today (`#/today`) | RR [V] T-c | RR [V] | N/A N-na | **M** continuation; **M** goal/streak/level T-s | **M** For-you "continue" device only T-r | see N-st | no | listening 2 EN/4 ZH, speaking 2/4, feed 5/5, reading next `available:false` |
| D Discover (`#/discover`) | RR [V] D-c | RR [V] | N/A | **M** card progress % + own imports device-only D-s | **M** D-r | see N-st | no | articles 2/1, books 1/0, listening 2/4, collections 0/0 |
| C Content Detail (`#/content/:id`) | RR [V] C-c | RR [V] (Keep: `POST /api/library/items`, UI click [I]) | N/A | Keep RR [I] · "Continue" place **M** C-s | **M** C-r | see N-st | no | as Discover |
| S Search (`#/search`) | RR [V] S-c | RR [V] | N/A | N/A (recents are presentation) S-s | RR (server results) [V] | — | yes (EN) | catalogue search 0 EN / 0 ZH (unpublished) |

**"Continue where you left off" is device-only.** Today (`screens/today/model.js:134-190`),
Discover (`screens/discover/model.js:31-112`), Content Detail (`screens/content/screen.js:150`),
the Practice Hub continue row (`screens/practice/model.js:207-233`) and My Library's content-tab
progress (`screens/library/model.js:31-36`, where `pct` is always 0) all read
`memory.value.continuation` from `product/memory.js`. That is localStorage key
`orena.encounters.v1:<owner>:<lang>`, written by `memory.enter()` (`product/memory.js:276`). No
server read feeds any of them. The account data architecture's own row, "Continue | device
references | account work-derived index plus device unsent work", names the target. It goes to D4.

---

## Evidence (keyed by cell)

**Writing**
- **W1a** `POST /api/evaluate` (app.py:2434) → `200` in 48 s: `id 12, series_id 12, revision_no 1,
  overall 67.2, evaluator "ollama:qwen3:8b", schema_version "writing-evaluation-v2"`, with
  `summary_vi`, per-dimension scores and `grammar_links`. [V]
- **W1c** The content of Writing is the learner's own task. Sources in /next:
  - the Prompt Setup sheet (`screens/writing/screen.js:626-644`);
  - Respond to Content (`#/respond/:id`, which sends `writing_context.journal_context`,
    `screens/respond/screen.js:241`).

  The old Writing entry's curated prompts rail (`ui/writing-entry.js:76`,
  `contentFor(language).filter(item => item.prompt)` from `static/orena/content/texts.js`) has no
  counterpart in /next. See the old-flows list, "per-skill libraries". [V]
- **W1d** `#/write/13` renders the stored piece with the controls "v2 / Setup / Compare versions /
  Review again" and the note "Saved on this device" (browser). The Review action posts the same
  payload shape as `reviewPayload()` (`screens/writing/model.js:168`), and that shape was exercised
  directly. [V]
- **W1s1** Stored in the `essays` table (`persistence/models.py:66`) through
  `_learning_repository`. `POST /api/essays/13/keep` → `200 {"kept":true,"kept_at":…}`. [V]
- **W1s2** The draft (unsubmitted text and task) is device memory:
  - keys: `memory.value.expressions['essay:<series>' | 'expression:free' | '…::task']`
    (`screens/writing/screen.js:103,169,589,643`);
  - the server path is `GET/PUT /api/drafts/{key}` (`work_api.py:222,234`), used by
    `product/draft-sync.js`, but only when `GET /api/account-backbone` is `active`. On the bench it
    answers `{"state":"disabled"}` [V]. The flag is `ORENA_ACCOUNT_BACKBONE=on`
    (`account_backbone.py:30`);
  - register and target length are neither stored nor sent: a per-visit `Map`
    (`screens/writing/screen.js:70`), and `EssayIn.writing_context` is ignored by
    `evaluate_with_ai` (`model.js:163-167`). **→ D4.**
- **W1r** A reload of `#/write/13` fetches `GET /api/essays/13` and `/review` (both 200).
  `#/progress?tab=history` lists the piece from `GET /api/essays`, and so does `GET /api/collection`
  (`durability:"account"`). [V]
- **W2c/W2a** The second `POST /api/evaluate` with `parent_essay_id:12` → `200 id 13, series_id 12,
  revision_no 2, overall 85.2, delta {grammar:+20, vocabulary:+20, coherence:+20,
  task_achievement:+10}`. [V]
- **W2s/W2r** `GET /api/essays/13/revision` → 200. Browser `#/write/13/compare` fetches
  `/api/essays/13`, `/revision` and `/api/essays/12` and draws "Version 1 · Today …" beside
  version 2. [V]
- **ZH** Not exercised: `/api/evaluate` returns 409 `language_scope_mismatch` unless the active
  language is zh (app.py:2437-2447). `GET /api/essays` lists only the active scope (13 en). [I]

**Vocabulary / Review**
- **V1c** `POST /api/dictionary/word-detail {depth:'sheet', text:'river', source_language:'en',
  target_language:'vi'}` → `200` in 14.9 s: `contextMeaning:"sông", saved:true`. For ZH the call
  gives `409` while en is active (the guard) [V]; ZH content itself is [I].
- **V1s/V1r** `POST /api/library/vocabulary {word:'bench',…}` → `200`: `review_stage 0, due true`.
  The row is in `saved_words` (models.py:148). It reads back through
  `GET /api/library/vocabulary?search=bench` and through Search (`#/search`, "bench" → "My Library
  · 1 Word bench"). [V]
- **V2c** `POST /api/dictionary/sentence-sheet` → `200` in 23 s: translation "Tôi thích ngồi trên
  cái ghế.", with structure and vocabulary. [V]
- **V2s/V2r** Sentence notes are stored in localStorage
  `orena.quicksheet.notes.v1:<owner>` (`screens/quick-sheet/model.js:224`,
  `sheet.js:317,373`). "Save highlight" is not built because no endpoint exists
  (`sheet.js:14-19`). Per-term saves in the vocabulary tab are real. [V code]
- **V3c/V3r** Browser `#/word/bench` shows "Tôi thích ngồi trên ghế … Learning · Review in 1 day".
  The data comes from:
  - `GET /api/library/vocabulary?query=bench`;
  - `POST /api/dictionary/word-detail {depth:'full'}` → `200` in 50 s, `available:true`;
  - `/clips` → `{"total":0}`;
  - `/audio` → a 53-byte JSON, i.e. no audio. [V]
- **V4c** Browser `#/library` draws its five tabs, "Due Review · 2", and media rows. Its data
  calls all return 200: `/api/collection?domains=reading,media`, `/api/library/vocabulary`,
  `/api/library/collections` (`{"collections":[]}`), `/api/vocabulary/decks` (`{"items":[]}`) and
  `/api/library/review-queue` (`due_count 2`). [V]
- **V5c** `GET /api/vocabulary/library/collections?language_code=en` → `{"items":[]}`, and the
  same for zh [V]. The learner catalog admits only published packs
  (`vocabulary_library.py:333-347`), and none are published on the bench.
  `GET /api/vocabulary/catalogue/search` returns 0 items for both en and zh [V]. Publishing is
  `POST /api/admin/.../content/vocabulary/{collection_id}/publish` (`admin_console_api.py:1023`),
  which is milestone E.
- **V5s** The frame's "save collection" has no backend (`screens/collection/screen.js:104-106`).
  Per-word saves are real.
- **V6c/V6d** Browser `#/review` shows "Review 1 of 2 · Source-aware cue …" from
  `GET /api/library/vocabulary?status=due&order=due&limit=50`. [V]
- **V6a/V6s** `POST /api/library/vocabulary/bench/review {"result":"got_it"}` → `200`, moving the
  word from `review_stage 0→1` with `successful_recalls 1`, `last_reviewed_at` set and
  `next_review_at` +1 day. The grades are self-grades (`again|unsure|got_it`) scheduled by the
  server (`becoming_library.review_schedule`, `screens/review/model.js:6-14`). An unknown grade →
  422. [V]
- **V6r** After the grade, `bench` is no longer due, and `#/word/bench` shows "Review in 1 day". [V]
- **V7c** `GET /api/vocabulary/feed?language_code=en` returns 5 items (opportunity, …) and
  `language_code=zh` returns 5 items (决定 HSK2, …). Browser `#/feed` shows "5 cards". [V]
- **V7s/V7r** A save uses `POST /api/library/vocabulary` with `source_kind 'feed'`. The saved
  list already holds a `source_kind:"feed"` row (`keynote`) [V]. That the feed drops
  already-saved words is from the `vocabulary_feed.py` header. [I]
- **V8c** `GET /api/practice-outcomes` → `{"items":[],"latest":null}` [V]. Outcomes exist only for
  essays with `module_data.practice` (`becoming_outcomes.py:80-91`,
  `specialized_repository.py:452-459`). That field is set only from `EssayIn.practice_context`
  (app.py:2519-2523), and **no client sends it**: a grep for `practice_context` in `static/` finds
  nothing in either UI. The flow cannot receive content. Browser: "No recent writing errors to
  review yet". [V]
- **V8a/V8s/V8r** The check is client-side string equality (`screens/errors/screen.js:188`,
  `isCorrect`). The screen makes no POST, so drill results are not stored and nothing comes back.
  [V code]
- **V-na** Look-up, browsing and exposure flows have no assessment. Product Constitution §7: "An
  experience should use only the capabilities that genuinely improve learning and meaning." The
  graded part of vocabulary is Active Recall (§21), which is V6. [I: the contract has no explicit
  "no assessment" line for these]

**Orena**
- **O1** Browser `#/orena` draws "Chào bạn. Hôm nay bạn muốn ôn từ, đọc hay luyện nói?" with
  suggestion chips and makes **no** `/api/agent/*` call (network log). `AGENT_LIVE = false`
  (`agent/transport.js:14`) routes every turn to `mockTurn` (`agent/mock.js:308`).
  `GET /api/agent/capabilities` and `/api/agent/session` → 404 on :8021. [V]
- **O2** The panel uses the same transport. The dispatcher (`screens/orena/dispatcher-setup.js`)
  maps actions to real APIs. [I: not driven]
- **O3** `POST /api/speech/transcribe` exists (an empty body → 422) [V]. Reply speech is the
  browser's speechSynthesis, and there is no server `audio_chunk` (`screens/orena/voice.js:4-16`).
  [I]
- **O-na** AGENT_CONTRACT line 100: "Evidence always comes from the server's record, never from
  client-supplied scores". §5.3 (line 197): no error claim without evidence. Orena assesses
  nothing itself.
- **O-st** AGENT_CONTRACT line 383: "Conversation history and coach notes are device memory; the
  account store is out of scope until an architecture review". Line 26 gives device memory for
  conversation to the UI lane. The key is `orena.agent.v1:<owner>` (`agent/memory.js:15`). This
  is N/A by the current contract, but listed for D4 because D-101 asks about learner state that
  must survive across devices.

**Navigation / continuation**
- **T-c** Browser `#/today`: `/api/listening/library`, `/api/speaking/library`,
  `/api/library/review-queue`, `/api/reading/practice/next` (`{"available":false}`),
  `/api/learner-summary?window=7d` and `/api/vocabulary/feed` all return 200. [V]
- **T-s/T-r** Continuation comes from `memory.value.continuation` (`screens/today/screen.js:55`,
  `model.js:134`). The goal ring, streak and level/XP have no cross-activity backend
  (`screens/today/screen.js:4-6`, UI_BACKEND_GAPS N-21), so they draw 0%, "0% of today's goal".
  [V]
- **D-c** Browser `#/discover` shows "5 results" from the articles, books, listening and
  collections endpoints, all 200. [V]
- **D-s/D-r** Card progress is `progressFromContinuation(continuation, id)`
  (`discover/model.js:34-112`). Text and media imports come from `memory.value.imports` and
  `mediaImports` (`discover/screen.js:208-209`). All of these are device-only. [V code]
- **C-c** Browser `#/content/article:c9011157…` ("The Fox and the Grapes") and
  `#/content/media:en-daily-pen-in-my-bag` render from the real endpoints.
  `GET /api/reading/practice/articles/{id}` → 404, which the screen handles. [V]
- **C-s/C-r** "Continue listening/reading" is
  `placeFor(ctx.context.memory.value.continuation, contentId)` (`content/screen.js:150-153`). A
  text import is read from device memory only (`content/screen.js:50-51`). [V code]
- **S-c/S-s** Typing "bench" into `#/search` calls `/api/vocabulary/catalogue/search` (0 items),
  `/api/collection?query=bench`, `/api/reading/articles` and `/api/listening/library`, and shows
  "1 result". Recent queries are kept in `orena.next.search.recent.v1`
  (`search/model.js:13`); that is a presentation convenience and needs no server storage (D-101
  "Persistence"). [V]
- **N-st** Server data that exists and could feed a server-side continuation index:
  - `GET /api/collection` (`collection_query.py`; entries carry `durability:"account"`, an
    `action.route` and `updatedAt`);
  - `listening_progress` and `shadowing_progress` (models.py:280,317, read by
    `api.listeningProgress`);
  - `reading_attempts` (models.py:1276);
  - `essays`;
  - the `works` store behind `work_api` (flag off).

  Two problems with `/api/collection` as it stands: its `action.route` values are **old-UI
  routes** (`#/expression?id=essay%3A12`), which the new Search translates by domain
  (`search/model.js:221-226`); and it carries no in-item position.

---

## Device-only learner state (for D4)

| key / place | holds | used by (/next) | verdict |
| --- | --- | --- | --- |
| `orena.encounters.v1:<owner>:<lang>` → `continuation[]` (`product/memory.js:52,276`) | "where you left off": id, intent, title, place `{index,total,within}` | Today, Discover, Content Detail, Practice Hub, (Library pct) | **learner record → D4** |
| same → `expressions{}` (`essay:<series>`, `expression:free`, `::task`, draft-sync digests) | Writing drafts and tasks | Writing | **D4** (server path exists: `works` via `ORENA_ACCOUNT_BACKBONE`; activation is a gate) |
| same → `imports[]`, `kept[]` | learner's pasted texts, and kept ones | Discover, Content Detail, Import | **D4** (account data arch: "Imported private text … account-owned content access record") |
| same → `mediaImports[]` (`url:`, `upload:` memberships) | own media links and uploads | Discover, Import, Search | **D4** (the upload itself is server `media_id`; the membership is device) |
| same → `keptLanguage{}` | kept-language provenance | Quick Sheet / saves | D4 (arch table: "account relation to saved object") |
| same → `reviewQueue[]` | offline review grades not yet sent | Review Session | device by design (unsent work; flushed to server) — keep |
| same → `reviewSettings` | review limits and modes | old UI only (not read by /next) | preference — not required |
| same → `answers{}`, `revisions{}`, `conversations{}` | old-room answers, revision history, spoken conversations | Conversation (part 2), Reader | D4 (conversations: arch "account work with ordered immutable turns") |
| `orena.quicksheet.notes.v1:<owner>` | sentence notes | Sentence Quick Sheet | **learner record → D4** |
| `orena.agent.v1:<owner>` | Orena thread and coach notes | Orena Home, panel | device **by AGENT_CONTRACT:383**; D4 should decide whether to open that review |
| Writing `intentions` Map (in-memory, `screens/writing/screen.js:70`) | register and target length per piece | Writing | lost on reload; the evaluator ignores it → D4 or retire the controls |
| `orena.next.search.recent.v1` | recent searches | Search | presentation — not required |

---

## OPEN OLD FLOWS

| old flow | recommendation | evidence |
| --- | --- | --- |
| **`url:` imported media** (old: pasted link → `url:<url>` membership, opened by `renderEncounter` via `capabilities/media-acquisition.js`) | **keep + port (finish)** | See the list after this table. |
| **`#/language` room** (old My Language: saved words, curated collections, study; `ui/expression.js:1404 renderLanguage`) | **already covered** by `#/library`, `#/collection/:id`, `#/word/:id` and `#/feed`; retire the old room at the cutover | The same endpoints (`api.libraryVocabulary`, `api.vocabularyLibraryCollections`) are read by `screens/library` and `screens/collection` [V]. The open gap is curated-collection content (V5), not the room. |
| **`recall` intent** (`#/practice?intent=recall` → `renderRecallLanguage`, `ui/expression.js:724`, four task modes typing / listen_choose / dictation / cloze via `product/recall-modes.js`, `ui/recall-tasks.js`) | **already covered** by `#/review` (same due query, same scheduler). **PROPOSE_RETIRE** the typing / listen-choose / dictation task modes | `/next` Review offers `target` and `cloze` only (`screens/review/model.js:152`). The design's frame 13 draws the reveal card, and Timed Recall and Context Transfer are deferred Coming-soon frames. The extra modes have no frame, so under rule 43 they are not carried over. Human decision. |
| **`#/continue`** (old room listing device continuation threads, `ui/reference.js:1381 renderContinue`) | **PROPOSE_RETIRE** the room; its function is **already covered** by Today "For you", the Practice Hub continue row and Content Detail "Continue". The data behind it is **MISSING** server-side (D4) | The design has no continue frame (IMPLEMENTATION_MAP lists none). The /next consumers are in N-st. |
| **Per-skill libraries** (old `#/writing` Writing entry `ui/writing-entry.js`; Speaking library `ui/speaking.js:95 speakingLibrary`; media library `ui/media-library.js`) | **PROPOSE_RETIRE** as rooms: **already covered** by Discover (Read / Listen·Watch / Collections / Imported filters), Skill Hub `#/practice/:skill` and Progress › History. **One piece to decide:** the Writing entry's curated prompt rail (`content/texts.js` prompts) has no /next home | Browser `#/practice/write` draws "Write · Recommended … Orena selected it from repeated writing evidence" (`/api/practice-recommendation` 200) [V]. The speaking and listening catalogues are in Skill Hub and Discover (`screens/practice/screen.js:170-173`). Writing pieces are listed in `#/progress?tab=history` [V]. The prompts are client-hardcoded content, which is why the human decides; Grammar/Content could later serve prompts. |
| **Growth summary** (old Preferences › "Your growth", `ui/growth-summary.js`, LearnerSummary `window=all`) | **already covered** by `#/progress` (Overview / Evidence / History); retire at the cutover | `#/progress` calls `GET /api/learner-summary?window=all` plus essays, reading evidence, practice outcomes and speech attempts (browser network log) [V]. Same data, same honesty rules. |
| **Old R5 grammar ids in links** | **already covered** by redirect, for Search, Today, Practice continuation and Grammar Concept. **PROPOSE_RETIRE** for Writing `grammar_links` and From Your Errors | See the list after this table. |

**`url:` imported media, evidence.**
- The /next Import sheet (frame 58) already creates `url:` and `upload:` entries:
  `screens/import/model.js:67-96` and `sheet.js:247-299`, which reuse
  `capabilities/media-acquisition.js`. It then navigates to `#/listen/url:<url>`.
- The Listening workspace resolves its id only through
  `GET /api/listening/library/{lessonId}` (`screens/listening/screen.js:49-51`). On the bench a
  `url:` id → **404** `{"detail":"Not Found"}`, and an `upload:` id → **404**
  `listening_lesson_not_found` [V].
- So an imported item cannot be opened in /next. The Listening workspace needs the
  `media-acquisition` / `api.mediaMy` path (`static/orena/capabilities/media-acquisition.js`, and
  `api.mediaMy` already used by `screens/content/screen.js:49`).
- The membership is also device-only (D4).
- Part 1 (Listening) should confirm this.

**Old R5 grammar ids, evidence.**
- Today (`today/model.js:168-172`), the Practice continuation (`practice/model.js:220-224`) and
  Search (`search/model.js:223`) pass the raw id to `#/grammar/:id`, which resolves R5 ids through
  the catalogue `aliases` (`product/grammar-source.js:69-81`, D-101 F). That needs Grammar Lab
  content, and on the bench nothing is served, so every point draws "not available".
- Writing: `/api/evaluate` still returns `grammar_links` with R5 / static-grammar-kb ids (for
  example `"grammar_id":"a1-basic-prepositions-of-time","source":"static-grammar-kb"`, observed
  [V]). The new screen deliberately does not read them (`writing/model.js:16-18`), and the frame
  draws no "Related grammar".
- From Your Errors reads no grammar route (`errors/model.js:1-3`).
- Recommendation: keep the alias redirect (F). For Writing, either retire `grammar_links` in the
  UI, or re-map them to Grammar Lab ids once F ships; that is the human's decision. Its backend
  source, targeted practice `GET /api/grammar/{id}/practice` (app.py:3232), is R5 and goes with
  it.

---

## Counts (sub-rows only; the summary rows aggregate them)

| skill | RUNS_REAL | MISSING | N/A | RETIRE |
| --- | --- | --- | --- | --- |
| Writing (2 rows, 10 cells) | 9 | 1 (draft store; ZH unproved on all cells) | 0 | 0 |
| Vocabulary/Review (8 rows, 40 cells) | 23 | 11 | 6 | 0 |
| Orena (3 rows, 15 cells) | 0 | 6 (all M·G: mock until G) | 9 | 0 |
| Navigation/continuation (4 rows, 20 cells) | 9 | 6 | 5 | 0 |
| Open old flows (7) | — | — | — | 4 proposals (`#/continue`, per-skill library rooms, extra recall modes, Writing `grammar_links`) + 1 keep+port (`url:` open path) |
