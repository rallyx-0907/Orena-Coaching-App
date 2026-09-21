# Canonical UI ↔ backend tracker

## Governance

Purpose: the single tracker of what the Canonical UI Baseline needs from the
backend, API, data and business logic, and where each need stands. Authority:
D-066. The baseline (`docs/design/canonical-ui/`) decides the interface and the
data it shows; the backend adapts. A gap is worked, never a reason to remove,
move or redesign a component. Change when a requirement, a contract or a status
changes. Do not store secrets, screenshots or unverified claims. This file
replaces the D-060 backlog (GAP-001..052) and absorbs the 2026-09-21 audit; it
is the only tracker, so no audit file may run beside it.

Rules:

- **Metric rule (D-066 rule 4).** A metric the baseline draws that has no
  measured value renders `0` in its canonical component. The `0` is a UI
  fallback and is never stored, sent or counted as a measurement; the read model
  carries `measured: false`. Demo figures never ship.
- **Status.** `READY` = the slice meets every point of D-066 rule 13 (canonical
  visual on desktop and phone, real data, no production mock, state kept over a
  reload, auth, loading/empty/error/retry, fallback correct, tests pass, no
  duplicate implementation). `IN_PROGRESS` = in scope now and unfinished.
  `BLOCKED` = waits on a gate named in the row. Nothing is `READY` until it has
  been run in a browser against the real backend.
- **Gates.** `[REVIEW]` a schema or migration for learner-owned data needs a
  recorded independent architecture review before it is applied to a shared or
  sandbox runtime. `[PROVIDER]` credentials are a human gate. `[CONTENT]` the
  work is supplying content or metadata, not code. `[DEF]` a measurement or rule
  needs an official definition before it is built.
- **Slice.** S1 Word and Sentence Sheet, S2 Writing review and revision, S3
  Listening and Dictation, S4 Reading comprehension per question, S5 catalogue
  Search, L later (learner persistence, progress measurement, pronunciation).
- Every schema field must trace to a row here or to a real business need.

Baseline pin: 2026-09-21, design project
`7a5604ca-1e11-4d8e-8305-7d0cb32d552d`; files and SHA-256 in
`docs/design/canonical-ui/PINS.tsv`. Audit facts below were read from code and
schema on that date at `76e69b9`; none has been run against the baseline UI.

## Summary by canonical screen

| Canonical UI | Required contract | Backend implementation | Data source / DB | Tests | Status |
| --- | --- | --- | --- | --- | --- |
| Quick Sheet, word | `WordDetail` | `/api/dictionary/word-detail` (projection in `word_detail.py`) over `reading_lookup` and the contextual explanation; `ui/quick-sheet.js` | vocabulary catalog, tagger, AI capability | `tests/test_word_detail.py` (held to the pinned contract), `test_orena_reading_room.mjs`, `test_media_interaction` | IN_PROGRESS (S1 built; see log) |
| Sentence sheet | `SentenceSheet` | `/api/dictionary/sentence-sheet`; parts and vocabulary in `ui/quick-sheet.js` | as above | as above | IN_PROGRESS (S1 built; see log) |
| Writing review | `WritingReview` | `/api/evaluate` through a serializer; `issue.examples` and `issue.kind` in the evaluator contract | `essays` | `test_writing_evaluation`, `test_writing_review_completeness`, `test_writing_review_reuse`, `test_orena_writing_review.mjs` | IN_PROGRESS (S2) |
| Writing revision | `RevisionCompare` | `revision_delta` through a serializer | `essays` chain | `test_writing_revision_contract` | IN_PROGRESS (S2) |
| Writing entry, workspace | `ContentCard`, draft | `/api/drafts`, `/api/tasks/generate`; prompt library | account backbone, catalogue | `test_work_api`, `test_orena_writing_workspace.mjs` | BLOCKED (`[CONTENT]` prompts; drafts past sandbox) |
| Listening library, workspace | `ContentCard`, `AudioPlayer`, `Transcript` | `listening_api`, `media_*`; add `content_type`, duration and remaining labels | catalogue JSON, `listening_progress` | `test_listening_*`, `test_orena_pure_listening.mjs` | IN_PROGRESS (S3) |
| Dictation | `DictationResult` | client evaluator, `practiceOutcome`; assisted flag | outcomes | `test_dictation_evaluator.mjs`, `test_orena_dictation_*.mjs` | IN_PROGRESS (S3) |
| Reading library, book detail | `ContentCard`, `Chapter` | `reading_library_api`; add kind, level, duration | `reading_books`, `reading_book_chapters` | `test_reading_library_api`, `test_orena_reading_library.mjs` | BLOCKED (`[REVIEW]` catalogue schema) |
| Reading workspace | `ReadingChapter` | `libraryBookChapter`, `readingTranslate`; whole-chapter translation | book assets, translation cache | `test_reading_translation`, `test_orena_reading_room.mjs` | IN_PROGRESS (S4) |
| Reading comprehension | comprehension | per-question check endpoint; per-chapter generation | `reading_sessions`, `reading_attempts` | none for the routes yet: add before changing | IN_PROGRESS (S4) |
| Search (all libraries) | `ContentCard[]` | catalogue search API, read-only | books, listening, vocabulary, collections | add | IN_PROGRESS (S5) |
| Speaking library | `ContentCard` | Speaking catalogue | catalogue | add | BLOCKED (`[CONTENT]`) |
| Speaking workspace | `PronunciationResult` | provider abstraction, normalized contract, Azure and SpeechSuper adapters, tone contour | `speaking_attempts` (no raw audio) | `test_speech_pronunciation`, `test_speaking_evaluator`, `test_m3_pronunciation_contract.mjs` | IN_PROGRESS (L); E2E `[PROVIDER]` |
| Vocabulary library, card, strokes | `VocabularyCollection`, `WordDetail` | `vocabulary_library`, stroke order | `vocabulary_*` | `test_vocabulary_library*`, `test_chinese_stroke_order`, `test_orena_vocabulary_library.mjs` | IN_PROGRESS (L) |
| Vocabulary context clips | `ContextClip` | word to clip index over listening transcripts | new index | add | BLOCKED (`[REVIEW]`/index design) |
| Vocabulary review | `VocabularyCard` | three-grade scheduler and interval preview | `saved_words` | `test_vocabulary_cards`, `test_orena_vocabulary_card.mjs`; add SRS tests | BLOCKED (`[REVIEW]` rule change) |
| Progress overview, trends | `ProgressOverview`, `ProgressTrends` | read model over the domain owners; every metric carries `measured` | LearnerSummary, events (new) | `test_learner_summary`, `test_orena_growth_summary.mjs` | BLOCKED (`[DEF]`, `[REVIEW]`) |
| Home / Discover | `AppShell`, `ContentCard` | shared card serializer; Continue read model | catalogues, device continuation | `test_orena_discover_layout.mjs` | IN_PROGRESS (L) |
| App shell | `AppShell` | profile fields; metric fallback | profile, LearnerSummary | `test_orena_foundation.mjs` | IN_PROGRESS (foundation with S1) |

## Requirements

Legend for each table: **Have** is what the backend does today; **Need** is the
change. Group headers name the contract, data source and tests once.

### Shell — `AppShell` · profile, LearnerSummary · `test_orena_foundation.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| SH-1 | Display name and avatar | `/api/me` gives email and mode → profile fields | L | BLOCKED `[REVIEW]` |
| SH-2 | Level next to the language ("B1", "HSK 2") | CEFR `declared_level`, not stored, no HSK → stored level per language framework | L | BLOCKED `[REVIEW]` |
| SH-3 | Language ("NORSK" in the mock) | `/api/platform/languages` is en and zh → none; Norwegian is demo data | - | IN_PROGRESS |
| SH-4 | Rank label ("Virtuoso · bậc 4") | none → rank definition and ladder; shows `0` until measured | L | BLOCKED `[DEF]` |
| SH-5 | Streak in the top bar and headers | none → streak definition and measurement; shows `0` | L | BLOCKED `[DEF]` |
| SH-6 | Level per skill in the rail | none → stored level per skill | L | BLOCKED `[REVIEW]` |
| SH-7 | Search field, desktop and phone | none server-side → S5 | S5 | IN_PROGRESS |
| SH-8 | Active nav and skill, five-item phone bar | client routing → none | - | IN_PROGRESS |
| SH-9 | Loading, empty, error | baseline draws none → keep the existing skeleton and degraded panel | - | IN_PROGRESS |
| SH-10 | Auth | Google OAuth, session guard, admin guard → none | - | IN_PROGRESS |

### Home — `AppShell`, `ContentCard` · catalogues, device continuation · `test_orena_discover_layout.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| HM-1 | Continue strip: kind, title, 68%, "còn 4 phút", resume | device `continuation`; progress only where a place is recorded → a `ContinueLearning` read model; cross-device is gated | L | BLOCKED `[REVIEW]` |
| HM-2 | "Mới cho bạn · phù hợp trình độ" | nothing ranks content → level-based ordering (needs SH-2) | L | BLOCKED `[REVIEW]` |
| HM-3 | Reading, Listening, Vocabulary rails | separate shapes per domain → the shared `ContentCard` serializer | L | IN_PROGRESS |
| HM-4 | Speaking rail | no Speaking library → SP-1 | L | BLOCKED `[CONTENT]` |
| HM-5 | Writing rail "Gợi ý viết mỗi ngày" | only AI task generation → WR-2 | L | BLOCKED `[CONTENT]` |
| HM-6 | Card: 17 types, skill, hue, badge (ĐANG LUYỆN, ĐÃ LƯU, TẠO RIÊNG, ĐÃ NHẬP) | per-domain fields; hue is artwork → one serializer | L | IN_PROGRESS |
| HM-7 | Populated rails | 7 listening lessons, books only after admin import → supply content | L | BLOCKED `[CONTENT]` |

### Reading — `ReadingChapter`, `Chapter`, `ContentCard` · `reading_books`, `reading_book_chapters`, assets · `test_reading_library_api`, `test_reading_translation`, `test_orena_reading_library.mjs`, `test_orena_reading_room.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| RD-1 | 11 type chips (books, excerpts, articles, news, essays, stories, dialogues, quotes, own, imported) | books carry no kind, level or topic → catalogue metadata | L | BLOCKED `[REVIEW]` |
| RD-2 | Card: author, level, kind, minutes | author and word count only → level, kind, and an owned reading-speed rule for minutes | L | BLOCKED `[REVIEW]` |
| RD-3 | Search inside the library | none → S5 | S5 | IN_PROGRESS |
| RD-4 | "Nhập văn bản", TẠO RIÊNG / ĐÃ NHẬP | import exists, device memory → wire the badge | L | IN_PROGRESS |
| RD-5 | Paged cover grid | cursor and `/cover` exist → none (real art is supply) | - | IN_PROGRESS |
| RD-6 | Book hero: continue chapter, 34%, time left | `libraryBook`; percent from continuation → `Chapter.progress` | L | IN_PROGRESS |
| RD-7 | Chapter state read / reading / unread | only the current chapter (device) → durable chapter state | L | BLOCKED `[REVIEW]` |
| RD-8 | "Bạn đã lưu từ đây … + 83 từ" | saved words carry no book link → word-to-book link | L | BLOCKED `[REVIEW]` |
| RD-9 | Book bookmark, menu, listen | none; device speech for words → saved items, audio | L | BLOCKED `[REVIEW]` `[PROVIDER]` |
| RD-10 | Position inside a chapter | chapter only → exact position | L | BLOCKED `[REVIEW]` |
| RD-11 | Bilingual layer | `readingTranslate`, first 12 paragraphs → whole chapter, batched and cached | S4 | IN_PROGRESS |
| RD-12 | Panel tabs Word, Grammar, Notes | Word only → grammar notes and notes | L | BLOCKED `[REVIEW]` |
| RD-13 | Action bar: save, listen, check, discuss, write a response, read later | check, discuss (`conversation-turn`) and response (`practice_context`) partly exist; save and read-later do not → wire and add saved items | L | IN_PROGRESS |
| RD-14 | Comprehension: one question, verdict and "đoạn giúp bạn trả lời", skippable | generated sessions hold answer, explanation and evidence, but `/answer` grades the whole set → per-question check; sessions for library chapters | S4 | IN_PROGRESS |
| RD-15 | "Bỏ qua vẫn tính đã đọc" | no completion record → part of RD-7 | L | BLOCKED `[REVIEW]` |

### Quick Sheet — `WordDetail`, `SentenceSheet` · vocabulary catalog, tagger, AI capability · `test_media_interaction`, `test_reading_lookup`, `test_orena_understanding.mjs`, `test_r16_contextual_dictionary.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| QS-1 | Layer 1: headword, IPA or pinyin, part of speech, speaker, save | lookup returns all of it → serializer | S1 | IN_PROGRESS |
| QS-2 | "Nghĩa ở câu này" in layer 1 | dictionary meaning only; contextual meaning is an AI explain → a contextual-meaning request through the provider abstraction, distinct from lookup | S1 | IN_PROGRESS |
| QS-3 | Seven usage levels | `USAGE_JUDGEMENTS` are the same seven → rename to the contract values | S1 | IN_PROGRESS |
| QS-4 | "Vì sao ở đây?": verdict, reason, examples, common mistake, grammar note, related | `judgement`, `judgement_reason`, `examples`, `counter_examples`, `grammar_notes`, `vocabulary` → map | S1 | IN_PROGRESS |
| QS-5 | Core idea, mental model, contrast | not in the schema → extend the explanation schema | S1 | IN_PROGRESS |
| QS-6 | "Hỏi tiếp" chips and free question | `follow_ups`, `question` → none | S1 | IN_PROGRESS |
| QS-7 | Where you met it; your own sentences | provenance is device memory; essays not indexed by word → `learnerSentences` read model; sources gated | S1 / L | IN_PROGRESS / BLOCKED `[REVIEW]` |
| QS-8 | "Lưu giải thích" | no saved explanation → saved explanations | L | BLOCKED `[REVIEW]` |
| QS-9 | Chinese variant with pinyin | annotate and explain cover it → none | S1 | IN_PROGRESS |
| QS-10 | Writing-feedback variant | same contract plus `errors[].suggestion` → S2 | S2 | IN_PROGRESS |
| QS-11 | Sentence sheet: translation, short explanation, structure, vocabulary with saved state | all but structure → `structure[{chunk, role}]`, language-neutral roles | S1 | IN_PROGRESS |
| QS-12 | Audio pauses and resumes | client → none | - | IN_PROGRESS |

### Listening, Dictation — `ContentCard`, `AudioPlayer`, `Transcript`, `DictationResult` · catalogue JSON, `listening_progress`, `shadowing_progress`, outcomes · `test_listening_*`, `test_orena_pure_listening.mjs`, `test_dictation_evaluator.mjs`, `test_orena_dictation_*.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| LS-1 | Nine type chips | lessons have topic and tags, no `content_type` → add it to the catalogue content | S3 | IN_PROGRESS |
| LS-2 | Card: duration, level, time left, video badge | all exist → `durationLabel`, remaining | S3 | IN_PROGRESS |
| LS-3 | Library search | none → S5 | S5 | IN_PROGRESS |
| LS-4 | Player: scrubber, transport, speed, loop | lesson and progress read/write → none | S3 | IN_PROGRESS |
| LS-5 | Transcript with pinyin, translation, active word, autoscroll | timeline, annotate, translate → none | S3 | IN_PROGRESS |
| LS-6 | Listening comprehension | none → items and scoring | L | BLOCKED `[CONTENT]` |
| LS-7 | Bookmark | none → saved items | L | BLOCKED `[REVIEW]` |
| LS-8 | Deep actions: dictation, shadow, read line, keep phrase, inspect | all exist → none | S3 | IN_PROGRESS |
| DC-1 | Line 2 of 5, clip range, replay | progress and excerpt → none | S3 | IN_PROGRESS |
| DC-2 | Hint level 1-3, "5 / 11 ký tự" | positional reveal → none | S3 | IN_PROGRESS |
| DC-3 | Pinyin per revealed character | reveal is characters only → per-character reading | L | IN_PROGRESS |
| DC-4 | Result: score, count, wrong / missing / extra | evaluator has all → map `status` to `kind` | S3 | IN_PROGRESS |
| DC-5 | "Đã dùng gợi ý — không tính vào chuỗi" | LearnerSummary knows assisted for dictation → durable assisted flag | L | BLOCKED `[REVIEW]` |
| DC-6 | Keep a word from the result | `saveLibraryVocabulary` → none | S3 | IN_PROGRESS |

### Speaking — `PronunciationResult` · `speaking_attempts` (no raw audio, D-066 rule 7) · `test_speech_pronunciation`, `test_speaking_evaluator`, `test_m3_pronunciation_contract.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| SP-1 | Six practice types, "2/5 câu" | no Speaking library → catalogue of clip, sentences, type, level | L | BLOCKED `[CONTENT]` |
| SP-2 | "Ghi âm của tôi" library | no durable audio by policy → show `0` saved; durable audio needs its own review | L | BLOCKED `[REVIEW]` |
| SP-3 | Clip, sentence, waveform, mic controls | clip, transcript, recorder, mic readiness → none | L | IN_PROGRESS |
| SP-4 | Transcribe | `/api/speech/transcribe`, unconfigured → credentials | L | BLOCKED `[PROVIDER]` |
| SP-5 | Score panel: overall, accuracy, fluency, passed | Azure adapter, unconfigured → normalized contract, provider abstraction, SpeechSuper adapter; metrics `0` with no attempt; canonical unavailable state without a provider | L | IN_PROGRESS (E2E `[PROVIDER]`) |
| SP-6 | Timing note | offsets available → compare with the model clip | L | IN_PROGRESS |
| SP-7 | Per-word note in words | phoneme accuracy only → tone and phoneme rules, or coaching | L | IN_PROGRESS |
| SP-8 | Tone curve, target and actual | none → pitch contour service | L | IN_PROGRESS |
| SP-9 | Compare, hear your take | client blob → none | L | IN_PROGRESS |
| SP-10 | Free talk: topic, phrases, what you said, comment | `evaluateSpeaking` needs ASR → topic and phrase content | L | BLOCKED `[CONTENT]` `[PROVIDER]` |
| SP-11 | Recording state | client → none | L | IN_PROGRESS |

### Writing — `WritingReview`, `RevisionCompare`, draft · `essays`, `essay_revisions`, account drafts · `test_writing_evaluation`, `test_writing_review_completeness`, `test_writing_review_reuse`, `test_writing_revision_contract`, `test_writing_evaluator_contract`, `test_work_api`, `test_orena_writing_review.mjs`, `test_orena_writing_workspace.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| WR-1 | Entry: continue draft, "lưu 6 phút trước" | account drafts (sandbox) and device → `updated_at` | L | BLOCKED `[REVIEW]` |
| WR-2 | "Theo gợi ý": prompt list by kind, level, target words | AI task generation only → curated prompt library | L | BLOCKED `[CONTENT]` |
| WR-3 | Four modes | free, own prompt, `practice_context` exist → wire | L | IN_PROGRESS |
| WR-4 | Workspace: autosave, word count, target | limits, count, `saveDraft` → none | S2 | IN_PROGRESS |
| WR-5 | Review: summary, strengths, three issues, rule, related grammar, ask more | `summary_vi`, `strengths_vi`, `errors[]`, `grammar_links` → serializer | S2 | IN_PROGRESS |
| WR-6 | Example sentence per issue | no such field → add to the evaluator contract, versioned | S2 | IN_PROGRESS |
| WR-7 | Issue kind: register, grammar, punctuation, vocabulary, naturalness | categories are rubric keys → extend the taxonomy, EN and ZH together | S2 | IN_PROGRESS |
| WR-8 | Four dimensions, 0-100 | five rubric keys → serialize the four drawn; keep `task_achievement` | S2 | IN_PROGRESS |
| WR-9 | "Lưu nhận xét" | every review is stored as an essay → none | S2 | IN_PROGRESS |
| WR-10 | "Lưu khái niệm" | no saved concept from a review → saved concept | L | BLOCKED `[REVIEW]` |
| WR-11 | Apply a fix | client, uses `anchored` → none | S2 | IN_PROGRESS |
| WR-12 | Revision: v1 and v2, fixed / remaining / new, headline | `revision_delta` → titles, details and headline from the data | S2 | IN_PROGRESS |
| WR-13 | Dimension change "72 → 88" | delta is a difference → return `from` and `to` | S2 | IN_PROGRESS |
| WR-14 | Done, edit again | client → none | S2 | IN_PROGRESS |

### Vocabulary — `VocabularyCollection`, `VocabularyCard`, `WordDetail`, `ContextClip` · `vocabulary_collections`, `vocabulary_entries`, memberships, `saved_words` · `test_vocabulary_library*`, `test_vocabulary_cards`, `test_chinese_stroke_order`, `test_orena_vocabulary_*.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| VC-1 | Collections with language, size, percent | `vocabularyLibraryCollections` → shared card | L | IN_PROGRESS |
| VC-2 | Real packs | catalog gated until a pack is published → supply | L | BLOCKED `[CONTENT]` |
| VC-3 | Search words or collections | inside one collection only → S5 | S5 | IN_PROGRESS |
| VC-4 | Card front and back, mastery 0-3 | entries, `review_stage` → define mastery mapping once | L | IN_PROGRESS |
| VC-5 | Deep card: senses, collocations, contrast, mistake, mental model, related | free-text fields → structured entry or on-demand explain | L | IN_PROGRESS |
| VC-6 | "Lấy từ đâu" | device provenance → durable source link | L | BLOCKED `[REVIEW]` |
| VC-7 | "Câu của bạn" | essays not indexed by word → read model (as QS-7) | L | IN_PROGRESS |
| VC-8 | Han strokes: radical, components, order, animation | offline stroke pack → check the pack for decomposition | L | IN_PROGRESS |
| VC-9 | Trace along, free write | no canvas → client capability | L | IN_PROGRESS |
| VC-10 | Context clips for a word | no word-to-clip index → inverted index over listening transcripts | L | BLOCKED `[REVIEW]` |
| VC-11 | Review: three grades with intervals, 3 / 24 | `again` / `got_it` → three-grade scheduler, interval preview, server-chosen queue; map old states, add tests, keep history | L | BLOCKED `[REVIEW]` |
| VC-12 | Tier, 87/150, "chưa thuộc", show all | progress and filters exist; tier does not → tier definition | L | BLOCKED `[DEF]` |
| VC-13 | Han or Latin script | `orthography` → none | L | IN_PROGRESS |

### Progress — `ProgressOverview`, `ProgressTrends` · LearnerSummary, `saved_words`, `reading_attempts`, `essays` · `test_learner_summary`, `test_orena_growth_summary.mjs`, `test_writing_analytics`

Every value below renders `0` (a chart, its zero state) until measured.

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| PG-1 | Streak | none → definition and measurement | L | BLOCKED `[DEF]` |
| PG-2 | Study time and per-skill time | no duration is recorded → official rule (time of completed work, never app-open time) and telemetry | L | BLOCKED `[DEF]` `[REVIEW]` |
| PG-3 | Words mastered | `review_stage` → one threshold | L | IN_PROGRESS |
| PG-4 | Just learned, with samples | `saved_words.added_at` → none | L | IN_PROGRESS |
| PG-5 | Reviewing, due, done today | due from `next_review_at`; no event → review events | L | BLOCKED `[REVIEW]` |
| PG-6 | Comprehension 9/11 and sequence | `reading_attempts` for generated passages → chapter quizzes (S4) | L | IN_PROGRESS |
| PG-7 | Recall accuracy, cards, got / unsure / forgot | cumulative counters only → review event table; needs VC-11 | L | BLOCKED `[REVIEW]` |
| PG-8 | Recent evidence per skill | LearnerSummary latest observations → `EvidenceItem` projection | L | IN_PROGRESS |
| PG-9 | Rank panel | none → SH-4 | L | BLOCKED `[DEF]` |
| PG-10 | 18-week heatmap | none → per-day activity | L | BLOCKED `[DEF]` `[REVIEW]` |
| PG-11 | Next action | `practiceRecommendation`, `crossSkillCue`, `reviewCue` → one contract | L | IN_PROGRESS |
| PG-12 | Improving over four weeks | only comparable measures may show a trend → series where comparable, `0` otherwise | L | BLOCKED `[DEF]` |
| PG-13 | Recurring errors | `error-memory` covers Writing → cross-domain read model | L | IN_PROGRESS |
| PG-14 | "Dựa trên gì" counts | derivable → after PG-7 | L | IN_PROGRESS |

## Progress log

**S1 Quick Sheet** (2026-09-21, `codex/work`). Built: `word_detail.py` and two endpoints
(QS-1..6, 11); `context_meaning`, `core_idea`, `mental_model`, `contrast`,
`common_mistake`, `structure` in the explanation schema; `ui/quick-sheet.js` and
`quick-sheet.css` (layer one, ask, deeper, sentence and its parts) called from
Reading and the Listening transcript through `ui/lexical.js`; the old lookup panel,
selection toolbar and reader panel styles removed. Checked in a browser on the
sandbox (:8011), vi interface, English text: docked in the reader, popover in
Listening, phone sheet with scrim. Local: pytest 1148 passed / 118 skipped, all CI
`.mjs` gates pass except `test_m3_pronunciation_contract.mjs`, which has failed
since D-065 removed the score from the report (it is a Speaking-slice item).

Not READY yet - what is left before S1 can be called READY:

- Chinese in a browser (hanzi, pinyin, the grammar-word label) and the zh interface.
- Phone: the ask, deeper and sentence views, not only layer one.
- Save from the sheet end to end with a reload, and the provider-down and retry states.
- Speaking still mounts the layer (`ui/speaking.js`): check it.
- The explanation and summary come back in English when the support language is
  Vietnamese on the sandbox's provider; the request names Vietnamese, so this is the
  provider's output (handoff: local model quality), to be checked with the live one.
- `QS-7` `sources` / `learnerSentences` are empty until their read models exist;
  `QS-8` "Lưu giải thích" keeps its place, disabled and saying so.
- Writing feedback, Vocabulary and Practice still open the older Understanding
  surface (`ui/understanding.js`); it is retired when S2 and the Vocabulary work
  move onto the sheet.
- Found on the way, fixed: the Listening transcript's words could not be tapped
  (a stale `.media-encounter` root); `.media-encounter` selectors remain as dead
  CSS to remove in S3.

## Old tracker (GAP-001..052) mapped

Carried into a row above: GAP-001 SH-5 PG-1 · 002/003/008 PG-2 · 004 SH-2 SH-6 ·
006 HM-1 · 011/026 SH-7 · 012 HM-6 RD-5 · 013 SH-1 · 014 PG-5 · 019 superseded
by VC-11 (three grades) · 020 VC-12 · 021 SP-5..8 · 022/027/029 RD-1 RD-2 LS-1 ·
025 LS-6 · 028 (per-word only) DC-3 · 032/034 RD-9 RD-13 · 035 RD-7 RD-15 · 036/039
RD-12 · 040 RD-10 · 043 VC-11 · 044 RD-1 · 045 RD-11 · 047 VC-12 · 048 SH-4 PG-9 ·
049 PG-10 · 051 DC-3 · 052 HM-2.

Not drawn by the baseline, so no longer tracked (git history keeps them): GAP-005,
007, 009, 010, 015, 016, 017, 018, 023, 024, 028 (whole-text pinyin), 030, 031,
033, 037, 038, 041, 042, 046, 050. Profile, My Content, Admin, Onboarding, states,
Modal/Drawer and tablet have no canonical design; their current implementation
stays until the human supplies one (D-066).
