# Product completion audit and slice plan (D-109)

**2026-10-01, `codex/work` at `4ccacda`, proved on the lane runtime :8021** (real backend on PostgreSQL, schema
`20260930_0023`, `ORENA_ACCOUNT_BACKBONE` active, auth `local`, one admin learner, lane AI = Gemini
`gemini-3.5-flash-lite`, Groq Whisper and Azure Speech configured). Method: the real UI driven with Playwright (1920x1080,
learning language `en` and `zh`, fake microphone fed with synthesised speech) plus the real APIs; every row below names
the route, request and what appeared. This is an audit record, not human approval and not CI evidence.

The existing per-flow matrix is `D3_PRODUCT_MATRIX.md`. This file does not compete with it: it re-proves the flows
against D-109's definition of done (content/admin side and learner side as one connected system, EN and ZH), and the
changed D3 cells are listed in the matrix under "Updates 2026-10-01".

D-109 definition of done, used as the yardstick: **Learner** - discover content, learn, practise, get useful feedback, save
state, return, continue, see progress. **Admin** - introduce or generate content, validate/review where needed, publish,
and see it usable by learners without editing code.

## 0. What the bench is, and what it is not

- The EN learner library on :8021 is mostly QA debris. Counted honestly (published, learner-visible):

| Content | EN | ZH |
| --- | --- | --- |
| Reading articles, real | 3 (Lion and the Mouse C1, Fox and the Grapes B2, Tortoise and the Hare B2) | 1 (故乡（节选） HSK6) |
| Reading articles, QA debris "Bridge ..." | 18 published, 14 "Auto/Bridge" waiting in review | 0 |
| Books (EPUB) | 1 (Alice, 12 chapters; chapters do not open, see G-11) | 0 |
| Listening / Speaking lessons (curated, Commons) | 2 (one audio A1, one video B2) | 4 (3 audio HSK1-2, 1 video HSK4) |
| Vocabulary: built-in catalogue (feeds the Daily feed) | 76 words | 80 words |
| Vocabulary: Admin-published collections | 0 | 0 |
| Grammar in the new UI | 0 points (empty state) | 0 points (empty state) |
| Grammar elsewhere (not wired to the new UI) | R5 `/api/library/grammar`: 269 lessons; Grammar Lab: 10 `draft_ai` points | R5: 239 lessons; Grammar Lab: 0 |
| Approved reading comprehension sets | 1 (mine) + earlier Gutenberg set | 1 (mine) |

  The learner library does not feel populated in either language; ZH is thinner than EN everywhere.
- Test content I created is listed in section 6. Nothing was deleted that I did not create.

## 1. Status per area x language

Legend: **WORKS** = works end to end in a browser/API as a real operator or learner; **PARTIAL** = runs but a step
breaks or is thin; **MISSING** = no path. "Evidence" is route -> request -> status -> what appeared.

### 1a. Content and Admin

| Area | EN | ZH | Evidence |
| --- | --- | --- | --- |
| Reading: enter (text/URL/file) -> process -> review -> publish -> learner | **PARTIAL** | **PARTIAL** | `POST /api/admin/reading/jobs` (kind=text) -> job `completed` in under 1 s -> article `needs_review` (EN B2, 8 targets; ZH word_count 102) -> `POST .../articles/{id}/status published` 200 -> `/api/reading/articles?language=` lists it -> `/next#/read/article:{id}` opens and renders. Every step ran in the Admin's own API. **Breaks:** (a) every article lands in `needs_review`; `automation_allowed` is false on all four sources and the code says "no auto-publish" (`reading_admin_api.py:743`), so D-109's "flows automatically where confidence is sufficient" does not exist; (b) ZH target extraction is character n-gram junk: targets "的西红柿", "子里" with empty meanings and a ZH level of HSK5 for a text a learner reads as HSK2-3 (`analysis.level_confidence` 0.40); EN gets whole words. The same ZH sentence segments correctly in the reader (`/api/media-learning/annotate` gave 篮子), so a segmenter exists and is not used by ingestion. |
| Reading comprehension sets: generate -> review -> approve -> learner Check | **PARTIAL** | **PARTIAL** | `POST .../comprehension-sets {support_language:vi}` -> Gemini draft in 2 s, 4 questions (ZH and EN). Approval needs each question `approve` then set `draft -> needs_review -> approved` (my first attempts with `approved` failed with `reading_set_transition_refused`). Then `/next#/read/article:{id}/check` runs, answers post, `POST /api/reading/practice/attempts` 200, evidence list shows 3/3 (ZH) and 1/4 (EN). **Breaks:** generation and approval are manual per article; nothing runs on publish; no auto-approve when evidence spans validate. |
| Books (EPUB import -> chapters -> publish -> learner reads) | **PARTIAL** | **MISSING (not proved)** | Admin: Imports/Books, Content/Books list Alice `published`. Learner: Discover lists the book, Content Detail renders, "Start reading" -> `GET /api/reading/library/books/{id}/chapters/{id}` **503 `reading_library_chapter_unavailable`** (asset store has no chapter payload) so the reader shows "Couldn't load this story". D3 proved this chapter at 200 on 2026-09-29, so either the lane stack's asset store lost its files after a restart or chapter payloads are not durable. No ZH EPUB was available to test. |
| Listening media from a **YouTube URL** | **PARTIAL (no transcript)** | **not tried** | `POST /api/media/admin/preview` reports `has_transcript: true`; `POST /api/admin/console/imports/media` -> `Imported`, **published at once**, `segment_count 0`, issue `transcript_missing`; Reprocess returns the same. The learner Listening workspace has nothing to follow or dictate. Cause in this runtime: `transcript_fallback` = none (`MEDIA_TRANSCRIPT_FALLBACK=none`), captions recovery is deferred ("a separate, later step") and `background_jobs: none` means nothing runs it. |
| Listening media from an **audio/video upload** | **PARTIAL (no transcript)** | **PARTIAL (no transcript)** | `POST /api/admin/console/imports/media-upload` with a 9.6 s EN and an 11.4 s ZH WAV -> `Imported`, `lesson_id ""`, `segment_count 0`, **published**, listed in `/api/listening/library`. Admin page says "No usable transcript - learners can't use this media ... until it has a transcript" and offers only Reprocess; there is no ASR step, no transcript editor and no hold-before-publish. Yet the same audio transcribes correctly through `POST /api/speech/transcribe` (Groq, ZH `每天早上我都去附近的市场买菜 ...` with 4 timed segments). The learner upload path (`/api/media-learning/upload`) behaves identically (`transcript_available false`). |
| Curated listening lessons (existing 6) | **WORKS** | **WORKS** | `/next#/listen/zh-culture-nationalities`: transcript with pinyin per character, vi line translation, Dictation, Shadowing, React, Respond all open. Thin: 2 EN, 4 ZH. |
| Vocabulary collection: import CSV -> map -> publish -> learner | **WORKS** | **WORKS** | `POST /api/admin/vocabulary/preview` detects columns (high confidence on term/POS/example/level; ZH `reading` mapped) -> `POST .../import` with `publish:true, publication_attested:true` -> `imported 5`, collection `published` -> `/api/vocabulary/library/collections?language_code=` lists it -> Discover "Collections" tab and `#/collection/{id}` show 5 words (ZH with pinyin and stroke data). Admin UI at `#/admin/imports/vocabulary` and `#/admin/content/vocabulary`. **Gaps:** no enrichment step (meanings are only what the CSV gave, here English; the vi support-language gloss appears only when the learner opens Word Detail and the AI call runs); no "generate a collection from published content". |
| Grammar: catalog -> generation -> validation -> review -> publish -> learner | **MISSING** | **MISSING** | `/next#/grammar` -> "No grammar points yet." (`GET /orena-assets/content/grammar/catalog.{en,zh}.json` 404). No `/api/grammar/v1/*`, no Admin Grammar page, no store. Upstream: Grammar Lab has 10 EN points all `draft_ai`, 0 ZH. PR #67 (contract v0.4 patch) and PR #68 (13 sample points) are both **OPEN, unmerged**; the store proposal (`GRAMMAR_CONTENT_STORE.md` rev 2) is PROPOSED. |
| Practice generated from published content | **PARTIAL** | **PARTIAL** | What exists is derived, not generated by an operator: Dictation/Shadowing/Speak from a lesson's transcript segments, Reading Check from an approved set, Daily feed from the built-in catalogue. The Admin "Practice generator" (A24-A27) is not built and has no backend. Nothing is produced automatically when content is published. |
| Failed jobs visible and recoverable | **WORKS** | **WORKS** | A URL job to a blocked address -> `failed`, `last_error_code unsafe_url`, attempt 1 of 3; `#/admin/imports/jobs` has Running/Failed/Completed filters and `POST /api/admin/reading/jobs/{id}/retry` exists. Media and vocabulary failures appear in Imports history (`failed_7d`). Not proved: a failed ASR/transcript job (none exists). |
| Admin overview of unpublished / invalid / in review / failed / live | **PARTIAL** | **PARTIAL** | The data exists: `GET /api/admin/console/overview` (content published/draft, transcript_missing, failed_7d, attention list) and Reading overview (Published 22, Needs review 14, Failed jobs, Active sources). The new Admin has **no Overview page** (A1 out of staging scope), so "what is live, waiting, broken" is spread over Reading overview, Content home and Imports with no single place and no cross-type "needs attention" list. Learner-facing debris (18 "Bridge" articles) cannot be told from real content without opening each. |
| Automatic flow vs review | **MISSING** | **MISSING** | Reading: article-level and source-level `automation_allowed` exist (D-106) but nothing consumes them to publish; sets always manual; media publishes automatically **without** a quality check (the opposite of D-109's intent); vocabulary requires an attested publish. No confidence score gates anything. |

### 1b. Learner loops

| Skill | EN | ZH | Evidence |
| --- | --- | --- | --- |
| Reading (discover -> read -> look up -> check -> done -> history -> return) | **WORKS** | **WORKS** | Reader renders (ZH with pinyin ruby and per-word Quick Sheet, EN plain); word tap -> Quick Sheet; `PUT /api/continue/article:{id}` 200 on open (server-side place); Check: `POST .../questions/{id}/grade` x3-4, `POST /api/reading/practice/attempts` 200, "You understood 3 / 3"; Progress -> History and Evidence list the attempt in a fresh browser context. Thin: 3 EN and 1 ZH real articles; books do not open (G-11). |
| Listening (Workspace, Dictation, Shadowing, React, Respond) | **WORKS** | **WORKS** | Dictation: typed answer, Check, `POST /api/listening/progress` 200, per-word (EN) / per-character (ZH) diff, "2 of 2 checked". Workspace transcript, vi translation, Follow/Shadowing modes render. Only for lessons that have a transcript; imported media is a dead end (section 1a). Shadowing/React feed the speech provider (below). |
| Speaking (Scripted, Compare, Attempts, Summary, Free Talk, Conversation, Situation) | **PARTIAL** | **PARTIAL** | Scripted ZH with a fake mic: Allow-microphone sheet, `POST /api/speech/pronunciation` (Azure, `measured`), `POST /api/speech/evaluation`, `POST /api/speech/attempts` all 200; result card shows Needs work, Accuracy, "recognised: 是。". EN pronunciation via API: 91 accuracy / 25 fluency (Azure). Situation ZH: Groq transcribe -> `POST /api/dictionary/spoken-response` -> `PUT /api/responses/situation:...` 200 (saved server-side; D3 said it saved nothing). **Breaks on return:** `#/speak/{id}/attempts` shows "Attempts 0" in a fresh context although `GET /api/speech/attempts` holds the attempt (the screen never reads the server list); Speaking Summary shows "0 tasks" (session-only). Coaching on a good sentence returned the learner's own sentence as the "natural alternative". Conversation and Free Talk need a real voice turn (not driven). |
| Writing (setup -> draft -> review -> revise -> compare -> history) | **WORKS** | **WORKS** | EN: 70-word draft, `PUT /api/drafts/expression:free` 200 (server draft; D3 had it device-only), Review -> `POST /api/evaluate` 200 in ~10 s, v1 with priority issue "many peoples", 69/100, Strengths, Next action. ZH: 94 Hanzi, 88/100, 1 grammar issue (known recall limit, `ZH_WRITING_EVALUATOR_RECALL.md`), feedback in the learner's support language. History/Evidence list both. The draft chip still says "Saved on this device". |
| Vocabulary / Recall (save -> due -> review -> schedule) | **WORKS** | **WORKS** | ZH: Collection -> word `市场` -> Word Detail (Gemini, vi gloss, stroke order) -> bookmark `POST /api/library/vocabulary` 200 -> `#/review` "1 of 1" -> Reveal -> Got it -> `POST .../review` 200 -> `review_stage 1`, `next_review_at` +1 day. **Breaks:** the collection's "Save" shows a toast "unavailable" (no way to add a whole collection) and "Start review - 5 items" opens "Nothing due" because the 5 words are not saved; each word must be saved one by one. |
| Grammar | **MISSING** | **MISSING** | Section 1a. Writing's feedback names grammar categories (EN "Grammar" fix, ZH `aspect`, `word_order` in `/api/error-memory`) and `/api/practice-recommendation` returns `focus_family: grammar`, but there is no Grammar destination to send the learner to. |
| Progress / Continue | **PARTIAL** | **PARTIAL** | Works: `#/progress?tab=history` and `?tab=evidence` list reading, speaking and writing events in a fresh context, Profile shows streak and due reviews from `/api/learner-activity`, Today's "Continue" rows come from `GET /api/continue` (server). **Breaks:** Progress Overview shows "-" for every skill and 0 for Knowing -> Using although `/api/learner-summary` holds 14 writing versions and the reading, review and speaking records; "Rank" says "no milestones"; From Your Errors says "No recent writing errors" right after a review with three fixes; Today and Continue are cluttered by QA entries (`tone`, `clip`, `bench`). |

### 1c. Connected system

| Connection | EN | ZH | Evidence |
| --- | --- | --- | --- |
| Word met in Reading -> Vocabulary -> review | **WORKS** | **WORKS** | Reader -> tap `basket` / `篮` (segmented to 篮子) -> Quick Sheet "Save word" -> `POST /api/library/vocabulary` and `POST .../{word}/provenance` 200 (source article and sentence stored) -> word is due in Review. Free Talk then offers "Useful phrases - from your library: 篮子, 市场". |
| Word met in Listening -> Vocabulary | **PARTIAL** | **PARTIAL** | Vocabulary Focus sheet and Word Detail exist; not driven end to end in this audit (curated lessons only). |
| Grammar weakness in Writing/Speaking -> Grammar | **MISSING** | **MISSING** | No Grammar content to link to. Agent `navigate grammar.point` would land on not-found (reconciliation F-3). |
| Imported content -> several activities | **PARTIAL** | **PARTIAL** | An imported text can be read, and a published article gets Check, Discuss, Transfer and word saving. Imported/uploaded audio and YouTube have no transcript, so Dictation, Shadowing, React and word saving are unavailable for them. |
| Progress across sessions | **PARTIAL** | **PARTIAL** | Continue place, history, evidence, drafts and Situation responses persist server-side; Attempt History, Speaking Summary and the Overview measures do not come back (above). |
| Orena Agent | **MISSING (by gate)** | **MISSING (by gate)** | `AGENT_LIVE = false` (`static/orena/agent/transport.js:14`); `/api/agent/*` is not served on :8021 (404); the Orena panel runs on the contract mock (`#/orena` shows scripted chips). Intelligence lane at `9012af7` (reconciliation D4): no P0/P1, six P2/P3 items that block an honest "understands current content": F-1 a failing PostgreSQL test, F-2 client-sourced dictation scores stated as fact, F-3 grammar ids, F-5/F-9 imported media and content-id namespaces unreconciled, F-4 due counts. Live proof needs the provider gate; I did not run it. |
| EN/ZH equivalence | **-** | **PARTIAL** | Same screens, same journeys, ZH adds pinyin ruby, per-character dictation, stroke order, HSK levels, Hanzi counts. Not equivalent: ZH content is 1 article / 0 books / 4 lessons / 0 grammar; ZH ingestion targets and level estimate are wrong (above); ZH writing recall is low; ZH pinyin is per character (`shì chǎng`), not per word. Classifier/particle mechanics exist only as writing-error categories (`aspect`, `word_order`); no learner content teaches them because Grammar is empty. |

## 2. Gaps that block D-109's definition of done

Classes: **C** content supply, **L** learner loop, **X** connection, **P** EN/ZH parity, **D** data loss / security.
No D item was found in this audit (nothing lost, no cross-learner read); G-11 below may be a durability problem and is the one
to confirm.

| # | Class | Gap | Blocks |
| --- | --- | --- | --- |
| G-1 | C | Library is thin and ZH thinner (table in section 0). Content breadth is a rights decision per text, so it is also a human gate. | "feels populated" |
| G-2 | C | No automatic flow anywhere; every article and set is manual; media is the opposite - auto-published with no quality check. | D-109.1 |
| G-3 | C | Audio, video and YouTube imports produce published, transcript-less lessons. No ASR step although Groq Whisper is configured and proved on the same audio; no transcript editor; YouTube captions need a fallback provider (paid) or the deferred recovery step. | Listening content path |
| G-4 | C/P | ZH ingestion: junk targets, wrong level estimate; EN is fine. | ZH reading content quality |
| G-5 | C | Grammar: no store, no API, no Admin import, no ZH points, PR #67/#68 unmerged. Whole skill absent for learners. | D-109.1, .2, .3 |
| G-6 | C | Vocabulary collections lack enrichment (support-language meaning, audio) and cannot be generated from published content. | Vocabulary supply |
| G-7 | C | Admin has no single overview of unpublished/invalid/in review/failed/live, and no way to see or hide QA debris. | D-109.1 |
| G-8 | C | "Practice generated from published content": no generator, no on-publish hook. | D-109.1 |
| G-9 | L | Whole-collection add to review is missing (Save toast; Start review shows nothing). | Vocabulary loop |
| G-10 | L | Attempt History, Speaking Summary, Progress Overview, Rank and From Your Errors do not read the server records that exist; they show 0 or empty after a real session. | "see progress", "return, continue" |
| G-11 | L/D | Book chapters do not open on :8021 (503); chapter payloads are in an asset store, not PostgreSQL. | Books |
| G-12 | X | Grammar weakness has nowhere to go; Agent not live; Agent cannot see imported media. | D-109.3, .4 |
| G-13 | P | ZH content, ZH ingestion, ZH grammar, ZH writing recall. | D-109.5 |

## 3. Ordered slices

Each slice is one complete journey a human can review in a browser, on :8021, EN and ZH. Order puts the slices that make the
library populated and the normal journeys complete first. "Reuse" names code that already exists.

**S1. Reading content flows in at volume, in both languages.**
Journey: operator adds a text/URL/file (EN and ZH) -> it is processed with correct targets and level -> a source or article
with `automation_allowed` and clean analysis is published without a human, anything else waits in the queue with the reason
-> the question set generates on publish and auto-approves when every question's evidence span validates, otherwise waits ->
the learner sees, reads, checks it. Includes fixing ZH segmentation and level (G-4) and a bulk import of rights-cleared EN/ZH
texts. Reuse: reading ingestion (`reading_processing.py`), `linguistic_annotation.py` / the `annotate` segmenter, D-106
`automation_allowed`, comprehension generation and Gemini, the queue/Review pages. Depends on: the auto-publish decision
(Q1) and per-source rights (Q2). Human gates: rights per text; whether sets may auto-approve.

**S2. Listening media becomes a lesson.**
Journey: operator or learner adds a URL or file -> the audio is transcribed with timing (existing `/api/speech/transcribe`
Groq Whisper), segmented, translated (existing Groq translation) -> it publishes only when it has a transcript, otherwise it
holds as Draft with the reason and a transcript editor/paste -> learner follows, dictates, shadows. YouTube: use public
captions where they exist; the paid fallback provider stays off until Q3. Reuse: `speech_transcribe`, `media_ingestion.py`,
`media_recovery_policy.py`, `media_translation.py`, Admin media detail (Reprocess already shown), `MediaImport*`. Fixes G-3.

**S3. Vocabulary collections that are usable.**
Journey: operator imports a list, or generates one from published articles' approved targets -> the support-language meaning
(and audio/pinyin for ZH) is filled by one batch AI pass shown in preview -> publish -> learner opens the collection, "Add
all to my words" (or per-word), and the words are due in Review the same day. Reuse: `vocabulary_source_import.py`,
`/api/dictionary/word-detail`, `vocabulary_library`, `library/vocabulary` save and `/review`, provenance, Daily feed.
Fixes G-6, G-9. Depends on: none. Human: AI enrichment cost cap.

**S4. Progress and return are true.**
Journey: after a normal session (read, listen, speak, write, review) the learner opens Progress, Attempt History, Speaking
Summary, From Your Errors and Rank in a new browser and sees what they did. Reuse: `GET /api/learner-summary`,
`/api/learner-activity`, `/api/speech/attempts`, `/api/error-memory`, `api.speakingAttempts` + `ui/voice-response.js`
(D3 already located them). Remove QA debris from the bench so counts mean something. Fixes G-10. No new persistence.

**S5. Grammar, first approved set, both languages.**
Journey: operator imports an approved Grammar Lab export -> dry run -> commit -> publish -> learner browses Grammar Library,
opens a Concept, tries it, and a Writing error category links to the matching point. Reuse: `GRAMMAR_CONTENT_STORE.md` rev
2, `GRAMMAR_CONTENT_CONTRACT.md`, built frames 44/47, `product/grammar-source.js`, Writing's error categories and
`/api/practice-recommendation`. Depends on: PR #67 and #68 merge, the store's independent review, ZH Grammar Lab content (none
exists). Human gates: merge of #67/#68; store schema approval; ZH point authoring. Fixes G-5, G-12 (grammar half), G-13.

**S6. Admin Overview: what is live, waiting, broken.**
Journey: operator opens one page that lists published/draft/in-review/invalid/failed per content type and language, each row
linking to its fix; QA debris can be archived in bulk. Reuse: `GET /api/admin/console/overview`, Reading operations/queue,
Imports history, the Admin shell. A1 is "out of staging scope" in the map; D-109 brings it in. Fixes G-7. Needs the human to
confirm the Overview frame (Q5).

**S7. Practice follows publishing.**
Journey: publishing an article or lesson makes its practice appear without a separate step (Check set, Dictation lines,
vocabulary candidates, a Writing prompt from the text) and the Admin shows what was produced. Reuse: S1-S3 hooks,
`/api/practice/next`, `/api/tasks/generate`. Fixes G-8. Depends on S1-S3.

**S8. Books open, ZH books work.**
Journey: operator imports an EPUB (EN and ZH) -> chapters store durably -> learner reads, saves words, returns to the
chapter. First confirm whether G-11 is the lane stack or a product defect. Reuse: `reading_library_api.py`, asset store
(consider keeping chapters where PostgreSQL has them). Fixes G-11.

**S9. Orena Agent live and aligned.**
Journey: with the human's gate, `AGENT_LIVE` on, the agent answers about the current article, lesson and saved words in the
learner's language and routes to Grammar and imported media. Reuse: reconciliation F-1..F-9, `AGENT_CONTRACT.md` v5. Depends
on S5 (grammar ids) and the provider gate. Fixes G-12.

**S10. ZH parity pass.** Fix what S1-S5 leave: ZH writing recall (fix (1) landed; live benchmark waits for the human's go),
word-level pinyin, coaching quality on correct sentences, classifier/particle practice from Grammar. Fixes G-13.

## 4. Deprioritised under D-109.7

- The `ACCOUNT_RECORD_LIMITS` rev 3/4 build, media-metadata PostgreSQL migration and its 2M-row rehearsal: infrastructure
  hardening with no effect on a normal journey.
- The Chinese evaluator live benchmark (USD 0.50 cap): cost-gated and secondary to content supply.
- The eight Coming-soon screens (Sound/Tone, Timed Recall/Reaction/Writing, Retell, Context Rewrite/Transfer, Mock Interview):
  deferred by D-101/H9; they are extra modes, not the six loops.
- Multi-device sync protocol, receipt compaction, account-deletion runtime, export format: architecture holds, not journeys.
- Agent `usage_events` deletion enumeration (F-7), per-worker rate limiter (I-24), streaming-shape live check (I-18) until S9.
- Phone-width and four-viewport rule-49 re-measurement of surfaces that are not changing.
- Cutover (`/` to `/next`) and :8000 deployment: human gate, after the product is complete.

## 5. Open questions for the human

1. **Auto-flow.** D-109.1 says AI content flows automatically where confidence is sufficient; the code states "no
   auto-publish" as a policy. May articles publish themselves when the source has `automation_allowed` and analysis is clean,
   and may question sets auto-approve when every evidence span validates? What confidence rule (S1)?
2. **Content supply and rights.** Which sources may populate the library, and how many items per language and level count as
   "populated" (suggested starting target: 30 reading texts, 20 listening lessons, 10 vocabulary collections per language)?
   Who decides rights per text?
3. **YouTube transcripts.** Turn on a paid caption fallback (`MEDIA_TRANSCRIPT_FALLBACK`), rely on public captions only, or
   transcribe provider audio with ASR? Media should no longer publish without a transcript - agreed?
4. **Grammar.** Merge PR #67/#68, approve the store proposal, and who authors Chinese points? In the meantime the old R5
   library holds 269 EN / 239 ZH lessons unreachable in `/next`; keep them retired (D-100) or bridge them read-only?
5. **Admin Overview.** The pinned Admin design has an Overview frame (A1) that the staging build left out; build it now to
   D-109's "see what is unpublished, invalid, waiting, failed or live"?
6. **Enrichment cost.** A batch AI pass for vocabulary meanings, and ASR for every upload, spend provider money. A cap?
7. **Book chapter 503 (G-11).** Is the lane stack's asset store meant to be durable? A restart seems to have lost chapter
   payloads; confirm before S8.
8. **QA debris.** May I (or the QA lane) archive the 18 "Bridge ..." articles, the 14 review items and the `tone`/`clip`
   imports so the EN library can be judged?
9. **Agent.** When is the provider gate for `AGENT_LIVE` opened, and should S5 precede it (the agent routes to Grammar)?

## 6. Test content created on :8021 (kept unless noted)

- Reading: article `9118e4e5-2ee4-467b-8401-14c06372a2ae` "PC-AUDIT The Morning Market" (EN, published) with approved set
  `a576d949-...`; article `da68bb88-ca88-4c3d-aad8-37d4176c6fca` "PC-AUDIT 早晨的市场" (ZH, published) with approved set
  `36372333-...`; article `e7892251-...` (ZH, my shell mangled the Chinese; **rejected**); failed job `2c135a9a-...`
  (blocked URL, left as the example of a visible failure).
- Media: `youtube-jNQXAC9IVRw`, `upload-0920f114...` (EN WAV), `upload-62e2915d...` (ZH WAV) - all three **archived**; a
  learner upload `upload-97e265ab...` was created and **deleted**. Source WAVs are in the session scratchpad.
- Vocabulary: collections `en-pc-audit-morning-market-words-1b67c62a0f47` and `zh-hsk-pc-audit-21ed9bcec348` (published).
- Learner records: saved words `市场` (reviewed once), `篮子`, `basket`; writing essays 27 (ZH) and 41 (EN); reading attempts
  on both PC-AUDIT articles; one Situation response; one speaking attempt; dictation progress on
  `zh-culture-nationalities` and `en-daily-pen-in-my-bag`.
- Learning language restored to `en`, interface `vi` (`GET /api/account-settings`).

## 7. Method notes

- Admin writes need an `Origin` header equal to the host (the console sends it); a bare `curl` gets `admin_origin_required`.
- Shell-passed Chinese text was mangled on this Windows host; Chinese form fields must be sent from UTF-8 files. Findings
  about ZH above come from correct UTF-8 submissions.
- Not driven: phone viewport, dark theme, Vietnamese interface checks (covered by earlier slices), Conversation and Free Talk
  voice turns, ZH EPUB import, live agent.
