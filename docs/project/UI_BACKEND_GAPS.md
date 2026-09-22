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
| Writing review | `WritingReview` | `GET /api/essays/{id}/review` (`writing_contract.py`); `example` in the evaluator contract (v2.5), English `register` category; `ui/writing-feedback.js` | `essays` | `tests/test_writing_contract.py` (held to the pinned contract), `test_writing_evaluation`, `test_orena_writing_review.mjs` | IN_PROGRESS (S2 built; see log) |
| Writing revision | `RevisionCompare` | `GET /api/essays/{id}/revision`; `revision_delta` judged by the words | `essays` chain | `test_writing_revision_contract`, `test_writing_contract` | IN_PROGRESS (S2 built; see log) |
| Writing entry, workspace | `ContentCard`, draft | `/api/drafts`, `/api/tasks/generate`; prompt library | account backbone, catalogue | `test_work_api`, `test_orena_writing_workspace.mjs` | BLOCKED (`[CONTENT]` prompts; drafts past sandbox) |
| Listening library, workspace | `ContentCard`, `AudioPlayer`, `Transcript` | `listening_api`, `media_*`; `content_type` derived; library `ui/library-browse.js`; workspace details open (see log) | catalogue JSON, `listening_progress`, device memory | `test_listening_*`, `test_orena_library.mjs`, `test_orena_pure_listening.mjs` | IN_PROGRESS (S3a built, S3b open) |
| Dictation | `DictationResult` | `capabilities/dictation-result.js`, `ui/dictation-screen.js`; `pinyin_alignment.py`; the evaluator and evidence save unchanged | outcomes, catalogue JSON | `test_orena_dictation_screen.mjs`, `test_pinyin_alignment.py`, `test_dictation_evaluator.mjs` | IN_PROGRESS (S3b built; DC-5 needs a decision) |
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
| LS-1 | Nine type chips | `content_type` derived from playback, topic and tags (`listening_catalog.content_type`, served in `lesson_metadata`); chips only for types some item has; a lesson that says nothing gets none; imported = the learner's own media | S3a | IN_PROGRESS (built; see log) |
| LS-2 | Card: duration, level, time left, video badge | duration on the cover, level, "time left" and a progress bar from the place in device memory, video and provenance badges | S3a | IN_PROGRESS (built; see log) |
| LS-3 | Library search | the bar's search filters the room's own items (title, level, type); catalogue-wide search stays S5 | S5 | IN_PROGRESS |
| LS-4 | Player: scrubber, transport, speed, loop | scrubber violet with a white knob and a played part that follows the position; transport, speeds and "replay line" as before | S3b | IN_PROGRESS (built; see log) |
| LS-5 | Transcript with pinyin, translation, active word, autoscroll | header chips (auto-scroll, the reading, the support language); auto-scroll is a kept preference that really stops the list following; a tapped line is picked ("Tua tới đây", "Nghe lại dòng") and the voice does not move | S3b | IN_PROGRESS (built; see log) |
| LS-6 | Listening comprehension | none → items and scoring | L | BLOCKED `[CONTENT]` |
| LS-7 | Bookmark | none → saved items | L | BLOCKED `[REVIEW]` |
| LS-8 | Deep actions: dictation, shadow, read line, keep phrase, inspect | one "⋯" button and a sheet (`ui/line-sheet.js`); the five ways run the practices that already existed | S3b | IN_PROGRESS (built; see log) |
| DC-1 | Line 2 of 5, clip range, replay | its own screen: segmented progress, the clip with its range and a bar of where the voice is, replay | S3b | IN_PROGRESS (built; see log) |
| DC-2 | Hint level 1-3, "5 / 11 ký tự" | three levels, leading units, never the whole line (held by a gate); typed-earned units also shown | S3b | IN_PROGRESS (built; see log) |
| DC-3 | Pinyin per revealed character | `pinyin_alignment.py` cuts the reviewed reading into one syllable per character; served as `pinyin_chars_by_segment`; a line that does not agree draws none | S3b | IN_PROGRESS (built; see log) |
| DC-4 | Result: score, count, wrong / missing / extra | `capabilities/dictation-result.js` maps the evaluator to `DictationResult`; a substitution is one wrong place; the count under the ring is the count the score is made of | S3b | IN_PROGRESS (built; see log) |
| DC-5 | "Đã dùng gợi ý — không tính vào chuỗi" | `used_hint` + hint level stored with the attempt (D-068); no score effect | L | BLOCKED (migration chain awaiting authorization + architecture review) |
| DC-6 | Keep a word from the result | "Lưu <term>": the lesson's own vocabulary term found in the line, else the whole line, into device memory | S3b | IN_PROGRESS (built; see log) |

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
| WR-5 | Review: summary, strengths, three issues, rule, related grammar, ask more | `summary_vi`, `strengths_vi`, `errors[]`, `grammar_links` → serializer | S2 | IN_PROGRESS (built) |
| WR-6 | Example sentence per issue | no such field → add to the evaluator contract, versioned | S2 | IN_PROGRESS (built) |
| WR-7 | Issue kind: register, grammar, punctuation, vocabulary, naturalness | categories are rubric keys → extend the taxonomy, EN and ZH together | S2 | IN_PROGRESS (built) |
| WR-8 | Four dimensions, 0-100 | five rubric keys → serialize the four drawn; keep `task_achievement` | S2 | IN_PROGRESS (built) |
| WR-9 | "Lưu nhận xét" | every review is stored as an essay → none | S2 | IN_PROGRESS (built) |
| WR-10 | "Lưu khái niệm" | no saved concept from a review → saved concept | L | BLOCKED `[REVIEW]` |
| WR-11 | Apply a fix | client, uses `anchored` → none | S2 | IN_PROGRESS (built) |
| WR-12 | Revision: v1 and v2, fixed / remaining / new, headline | `revision_delta` → titles, details and headline from the data | S2 | IN_PROGRESS (built) |
| WR-13 | Dimension change "72 → 88" | delta is a difference → return `from` and `to` | S2 | IN_PROGRESS (built) |
| WR-14 | Done, edit again | client → none | S2 | IN_PROGRESS (built) |

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

**S3a Library** (2026-09-21, `f75991f`). Built: the baseline's library for Reading and
Listening as one surface (`ui/library-browse.js`): a bar with the room's name, a search and
the import action; one row of single-choice type chips offered only for types some item
really has; a grid of ContentCards with the length on the cover, a progress bar and "time
left" from the place the learner reached (device memory), a video badge and a provenance
badge (said once, not repeated in the line), and an authored "3 min" shown in the interface
language. Backend: `content_type` for listening lessons, derived and tested
(`test_every_lesson_carries_a_type_the_baseline_names_or_none`). The D-060 facet layout and its
CSS are deleted; a new gate `scripts/test_orena_library.mjs` (in CI) holds the contract and the
copy for every catalogue type in en, zh and vi. Checked in a browser on the sandbox (vi):
desktop Reading and Listening, phone Listening with touch (chip tap filters, no horizontal
overflow, chips scroll). Local: pytest 1160 passed / 118 skipped; every CI `.mjs` gate passes
except `test_m3_pronunciation_contract.mjs`.

Not READY yet - S3 as a whole:

- The Listening workspace has the baseline's structure (player, scrubber, transport, speeds,
  comprehension button, bookmark, transcript with VI) but not its details: the transcript
  header is the shared learning toolbar's row of icon buttons where the baseline draws
  "Tự cuộn", PINYIN and VI chips and puts the deep actions (dictation, shadow, read the
  line, keep, inspect) behind one "⋯"; the scrubber is amber where the baseline's is violet
  with a white knob. `learning-toolbar.js` is shared with Reading, so it changes in one pass.
- The catalogue's lesson `en-travel-rainy-day-taxi` is a single 71 s segment (one very long
  transcript line): a content-segmentation gap `[CONTENT]`, not code.
- Dictation is a panel beside the player; the baseline draws its own screen (segmented
  progress, the player inside a centred card with the hint-level pill, hint shape with pinyin,
  a result column with the score ring, marks and actions). The evaluator, hint levels, score,
  wrong/missing/extra and save already exist and are reused. DC-3 (pinyin per character) and
  DC-5 (assisted flag kept) are still open.
- Search (S5) and the catalogue-wide result page are untouched; the Library page
  (`#/content`, all kinds) uses the same component with type chips only.
- Browser checks of the zh interface and of imported items in the library.

**S3b Listening workspace and Dictation** (2026-09-21, `8bdb649`, `3c70516`, `3df3aee`). Built from
the pinned frames (Orena Listening 02, 03, 04), not from the previous implementation:

- Workspace: header chips (Tự cuộn, the reading, the support language) and one "⋯"; a tapped
  line is picked and offers "Tua tới đây" and "Nghe lại dòng", the voice stays where it is; the
  deep ways (dictation, shadow, read the line, keep, look closer) are a sheet over the workspace
  (popover on a desk, bottom sheet on a phone, closes on navigation); an audio lesson has a poster;
  the identity line is level · type · length; the scrubber is violet with a white knob. Word-class
  colours have no switch on the baseline, so they are off and their legend is gone.
- Dictation: its own screen - segmented progress, the clip, the pills (hear again, speed, hint
  level), the shape of the line with a reading under each character, the field, and a result
  column (ring, what was typed with each wrong, missing and extra place marked and tappable, the
  right line with the missed characters lit, the reading and the meaning, next line / try again /
  replay / keep). The comparison, score, hint module and evidence save are the ones that existed;
  `capabilities/dictation-result.js` only puts them in the baseline's shapes. The streak pill
  shows 0 (not measured). A used hint says "Đã dùng gợi ý." and nothing more.
- Backend/data: `pinyin_alignment.py` and `pinyin_chars_by_segment` in the lesson payloads;
  the aligner is verifiable (pypinyin only says where a syllable ends), left a line unaligned
  rather than wrong, and caught two real typos in the reviewed readings (`zhǎodào`, `Bǎikē`),
  corrected in the catalogue. Every Chinese line the catalogue ships aligns (a test holds it).
- Chinese and localization: keys are in parity across en, zh and vi in both copy packs; the
  library, the workspace, the deep sheet, Dictation, the Quick Sheet (word, deeper, typed
  question) and the Writing review with its finding sheet were run in a browser in a Chinese
  interface with Chinese text and real answers (Gemini): second person, Chinese throughout.
- Checked in a browser on the sandbox with real touch: Dictation and the workspace on a phone (no
  horizontal overflow, the deep sheet is a bottom sheet with a scrim, the result follows the task),
  the library on a phone (two columns, the item in progress leads). Local: pytest 1171 passed /
  118 skipped; every CI `.mjs` gate passes except `test_m3_pronunciation_contract.mjs`; new gates
  `test_orena_library.mjs`, `test_orena_dictation_screen.mjs`, `test_orena_listening_workspace.mjs`.
- Deleted: the old Dictation panel's CSS and code (`revealAnswer`, `.dictate-*`, `.hint-line`,
  `data-mode='dictation'`), the audio identity block, the D-060 library layout.

Decisions the human closed (D-068, 2026-09-21):

- **DC-5.** Approved: the used-hint state is stored with the attempt, and no scoring effect is
  inferred without a scoring rule. Storing it means two columns on `listening_progress` (the last
  attempt's `used_hint` and hint level), a schema change for learner-owned data: it is authored as a
  migration after the chain still awaiting human authorization (`20260916_0008` and
  `20260916_0009`, sandbox at `20260912_0007`) and needs a recorded independent architecture review
  before it is applied. Until then nothing about it is built and the screen says nothing about
  hints used.
- **The lesson `en-travel-rainy-day-taxi` is removed** from the catalogue (six lessons remain); its
  source `commons-taxi-dialogue-1` goes with it.
- **Reveal in Dictation.** The baseline draws no "show the answer", and a hint never shows the whole
  line, so the screen has none; the recorded `revealed` evidence path is now unreachable from the UI.

Not READY yet - what is left of S3:

- LS-6 (comprehension) and LS-7 (bookmark as a saved item) stay `BLOCKED` as before; the bookmark
  is device memory.
- The workspace on a phone stacks the poster, the transport and the transcript; the baseline's
  phone puts a top bar (back, the reading and support chips, bookmark) over a longer transcript with
  the transport at the bottom. Functional and touch-checked, not yet the same composition.
- Word-class colouring code (`closeLook`, annotation of the current line) has no UI; delete it.
- The two `verify_writing_*_browser.mjs` scripts still wait for the deleted `.review-headline`.
- The library's chips show only types that exist; the baseline draws the full fixed set.

**S2 Writing review and revision** (2026-09-21). Built: `writing_contract.py` and two
endpoints (WR-5..9, 11..14); `example` per finding and the English `register`
category (evaluator contract `writing-evaluation-v2.5`); one table maps every
category of both languages to the baseline's five kinds; `ui/writing-feedback.js` and
`writing-feedback.css` (overview, findings, dimensions, the finding sheet with apply,
the version comparison) replace the old report renderer, the revision workbench and
the locate helper. Checked in a browser on the sandbox with the real provider
(vi interface, English text, desktop): review, opening a finding, applying it (draft
changed, count fell), a second version and its comparison. Two root causes found and
fixed on the way: the comparison was handed an unparsed earlier review and saw none of
its findings; and it matched findings by identical wording, so it called a reworded
finding fixed and new at once - it now asks the words. Local: pytest and every CI
`.mjs` gate pass except `test_m3_pronunciation_contract.mjs`.

Not READY yet:

- Chinese (zh text, zh interface) and the phone in a browser; the provider-down state.
- WR-1..4 (entry with four modes, prompt library, workspace top bar) and WR-10 (save a
  concept) are untouched; the room's frame is still the earlier composition.
- Dead styles from the old review (`.review-*` overview/issue/dimension rules,
  `.correction*`) and now-unused copy keys (`reviewFocus`, `reviewDeeper`,
  `reviewLocate`, ...) remain to be removed; they share names with the Vocabulary review
  session's classes, so they need a careful pass.
- `ui/understanding.js` is still used by comprehension, conversation, the encounter,
  voice response and grammar; it goes when those move onto the Quick Sheet.
- The comparison shows the two drafts side by side only when the frame is 820px or
  wider; in the room's result column it shows the banner and the changes, as the
  baseline's phone does.

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

**Bug pass on S1/S2** (2026-09-21, commits `fb9a9ec`, `3651ed0`). Six reported defects,
each with its root cause:

- The ask-more input looked dead: a repaint on every state change rebuilt the sheet and
  erased the question being typed. The draft and its focus now survive a repaint, and the
  newest answer scrolls into view. Checked: a 52 s repaint kept text and focus.
- A sheet outlived the screen it was opened from. Every sheet (word, sentence, finding) now
  closes on a route change. Checked with `history.back()` and a hash change, for the word
  sheet and the Writing finding sheet.
- Feedback spoke about "the learner". `VOICE_POLICY` in the writing evaluator and the tutor
  prompts sets second person (bạn / you / 你); the evaluator contract is `writing-evaluation-v2.6`,
  so stored reviews in the old voice are retired. The answer language is now named in the last
  line of the tutor prompt, naming `judgement_reason` and `follow_ups`, which a model otherwise
  leaves in the text's language. Checked live in vi: gloss, verdict, follow-ups and a typed
  question all in Vietnamese; zh word (`终于`) gives pinyin, no IPA, Vietnamese explanations.
- Rails could not be swiped on a phone: `touch-action: pan-y` blocked horizontal panning.
  Checked with a real touch swipe (touch-enabled mobile context, CDP touch events): the
  For-you rail moved from 0 to 217 px. Not a resized mouse viewport.
- The reader's back link went to a route that answered `{"detail":"Not Found"}`; it now
  returns to the book, or to Practice when there is none.
- The For-you cards were unequal (a legacy `align-items:start` in `rooms.css`): now one height (183 px).

Also: the first-layer gloss is no longer replaced when the full explanation loads (for Chinese
the full answer can be a sentence translation). Deleted the old Writing review layout's CSS
(`.review-*`, `.correction*`, ~250 lines across four files), including a legacy
`.review-bar` box that also clipped the vocabulary session's header. Phone sheet checked with
touch (bottom sheet, scrim, no horizontal overflow, closes on navigation).

Still open from S1/S2: the zh *interface* on the sheets and the phone views of ask/deeper
for zh; provider-down states are covered by unit tests, not a browser pass; the two
`verify_*_browser.mjs` scripts (cited in docs) wait for the deleted `.review-headline` and
must be rewritten for the new markup; unused copy keys (`reviewFocus`, `reviewDeeper`,
`reviewLocate`, ...); WR-1..4, WR-10, QS-7, QS-8; `ui/understanding.js` stays for its other
callers. The provider's 15-50 s latency for the full explanation and about 40 s for a review
is provider speed, shown by the loading states, not fixed here.

## Writing workspace, measured against "Writing workspace" and "Writing review" (D-067)

Built to the frame: a 76px top bar (back, title, saved, word count, one "Nhận xét" pill), a 920px column
with the prompt card (the intention field lives in it) and the piece as a 24px serif document; a review
makes two panes (994 : 820, radius 20, padding 28/30). Removed because the frame draws nothing for
them - decisions for the human, not guesses:

- **The level control.** Decided (D-068 follow-up): no selector; the review aims at the level the learner
  declared in their profile (`declared_level`), else the level of the text answered, else nothing.
- **Register exploration and the revision history** are kept and now sit behind the top bar's menu (three
  lines), the design's pattern for "everything deeper behind one button".
- **The "Cần một điểm bắt đầu?" starters** are legacy of the old entry and stay below the room until the
  Writing entry frame (ContentCard / SectionRail of prompts) is built.
- The prompt card's second line ("B1 · ≈150 từ · giọng thân mật") and the "/ ≈150 từ" target in the count
  need a task with a level, a length and a tone; the free-writing room has none, so the card is one line
  and the count is the words written.
- Still not the frame: the review pane's own content (overview, "làm tốt", "ba chỗ cần sửa" cards with
  three chips each, "các mặt" bars), the top bar's "Lưu nhận xét" / "Sửa lại" pair, the revision
  compare frame, the error sheet, and the entry.

## Bugs 7-13 (2026-09-21) - what changed and where

| # | Result | Where |
| --- | --- | --- |
| 7 | PASS: a replaced or closed sheet is cancelled; only the latest tap is answered; the last tap's own selection no longer reads as a drag; words in any visible line are askable (the line becomes current, paused) | `ui/lexical.js`, `ui/quick-sheet.js`, `ui/encounter.js`, `scripts/test_orena_lookup_race.mjs` |
| 8 | PASS: follow-ups go to a contextual tutor (answer first, never restated, short by default, earlier turns carried) | `media_interaction.answer_learner_question`, `word_detail.py`, `tests/test_word_detail.py` |
| 9 | PASS: Previous / Next on the Dictation rail, in step with the progress | `ui/dictation-screen.js`, `dictation.css` |
| 10 | PASS: hear, line, field and check fit 390x844 (check at y 572-622); a long line scrolls in its own pane | `dictation.css` |
| 11 | PASS as built in S3b (ring, count, marks, right line; no invented number); no new deviation found | `ui/dictation-screen.js` |
| 12 | PASS: a tap on a line goes to it and plays it; the half-way picked state is deleted | `ui/encounter.js`, `listening.css` |
| 13 | PASS: the overflow is the menu icon (three lines) | `ui/encounter.js`, `ui/symbols.js`, `ui/expression.js` |

"Ink + Paper": the Paper theme was retired by D-066; there is one theme, so the check is desktop and phone
in one theme.

## Bugs 14-15 and the design sync (2026-09-22)

| # | Result | Where |
| --- | --- | --- |
| 14 | PASS: a word typed with an extra letter ("breack") is still wrong and the hint never shows it whole - the place where it parts from the target stays masked; the old test that expected the word revealed is re-expressed | `capabilities/dictation-hints.js`, `scripts/test_orena_dictation_hints.mjs` |
| 15 | PASS: on a desk the task is one screen (check button at 979/1080, 720/768, 686/720; with or without a result); the picture takes what the height allows, the line scrolls in its own pane | `dictation.css`, `scripts/test_orena_dictation_screen.mjs` |

Design sync: tokens and the contracts checked are unchanged; the rules documents were read for the first time and
are recorded in `docs/design/canonical-ui/SYNC_2026-09-22.md`. From them: the Writing review is a Draft / Review tab
pair on a phone and the revision is three columns with a banner - both built now. Still to build from the templates:
the Writing entry, Home (top bar with search, level and streak, the Continue strip, section rails at 300x170 / 232x132),
Reading (library, book detail, workspace) - each read from the source when it is worked on.

## Writing entry and the ground (2026-09-22)

Built to "Writing entry": `ui/writing-entry.js`, `writing-entry.css`, route `#/writing`. The draft card is drawn only when
the device holds a continuation for Writing; the prompt rail is the texts' own prompts (badge = the text's kind, meta =
its level and length); "search" filters the prompts; "See all" opens the rail into a grid. Not drawn because the
app holds no such data: "saved N minutes ago" on the draft card, a category badge for prompts that have no kind,
a target length. The error sheet is the finding sheet (`issueSheetHtml`), already the frame's: fragment struck,
correction, kind, why, rule well, example, ask / save concept / apply.

## Writing review and revision, second pass (2026-09-22)

Built to "Writing review" and "Writing revision" (desktop and phone): the findings are marked in the draft itself
(`ui/draft-marks.js`), the pane labels are drawn, the top bar's one primary action follows the room (Review / Revise /
Done), and a revision is the banner, the legend, the two versions marked and the changes with the dimension deltas at
their foot. The phone's revision bar is "Revise more" beside "Done".

- **A mark is earned.** The contracts carry the words of a finding (`fragment`; a change's `title`), not where they
  are. A mark is drawn only where the words occur exactly once in the text, the rule apply-fix uses; otherwise the
  finding stays guidance and marks nothing. The revision marks what was fixed and what is still there in the earlier
  version, what is still there and what is new in the later one; it cannot mark the words that replaced a fix
  (`detail` carries the evaluator's suggestion, not the learner's words). Positions in the contract would end both limits.
- **"Lưu nhận xét" (save the review) is not drawn.** A review is already kept with the piece; saving it as something
  else needs a place in learner data that is held for the account architecture (AGENTS.md, holds). Decision needed:
  what "saved" means here (a kept set of rules in My Language?), then it is one button.
- **Where the findings of a revision went.** The revision frame draws no findings, so a version with a version before
  it opens on the comparison and its findings are one menu item away ("Review of this version"), and back. The frame
  gives no button to revise again from the desktop comparison; it is behind the same menu (the phone has it in the bar).
- **The design's Vietnamese sentences are sample text.** The changes list shows the evaluator's own words (the
  fragment, its kind, the correction and reason), not the frame's "Giọng văn đã thân mật".

## Home, built to its frames (2026-09-22)

`ui/home.js` + `home.css` replace `discoverySpread`: the baseline's top bar (the one search, the level, the
streak), the Continue strip, then the rails the frames draw - what is new for you, Reading, Listening,
Speaking, Writing, Vocabulary - and what the learner kept. Every card is a real item; a rail with nothing
in it is not drawn. The old composition (greeting, hero pair, "for you"/"saved" only) and its stylesheet
are deleted (rule 44).

- **The frames' sidebar draws an account card and per-skill levels; the app's rail does not.** The shell is
  already built to `AppShell` (D-066) and the human kept the current logo; the account lives in the profile
  sheet. Per-skill levels have no source (`skillLevels` in `AppShell.json` is unserved). Decision needed
  before the rail grows a card.
- **The streak is still unmeasured (GAP-001).** The chip keeps its place and shows "—", as everywhere else.
- **"For you" is the catalogue's own order (GAP-052).** There is no recommender; the rail alternates
  listening and reading so the phone's first two cards show both, and says nothing about why.
- **The frame's phone tab bar holds Home / Library / Vocab / Progress / Profile**, which the shell already
  draws; Home draws no navigation of its own.
- **Not drawn because nothing supplies them:** a per-card "ĐANG LUYỆN / ĐÃ LƯU" badge (`badge` in
  `ContentCard.json` is unserved), the frame's "còn 4 phút" (a thread records a place, not a remaining time).

## Reading workspace, to its frame (2026-09-22)

"Reading · bilingual + panel" is one screen, and now so is the room: a 4px hairline of the learner's place
across the top, a 72px bar, the text at its 780px measure beside the 440px panel, each scrolling on its own,
and the frame's floating bar under the text. What used to sit under the text - the prepared notes, the
optional check, the response, the rights - is reached from that bar and opens as a sheet (D-068: a function
is not deleted because the mockup omits it; it goes where the design's patterns put it).

- **The frame's bar has six pills; the app draws what exists.** Lưu bài (keep), Nghe (unavailable, as
  before), Kiểm tra hiểu (disabled with no questions, D-068), Viết phản hồi (the response composer, primary),
  the prepared notes when the text has them, and the rights. **"Thảo luận" is not drawn**: there is no
  discussion over a whole text, only the per-selection understanding surface. Decision needed: either a
  thread against a text (learner data, so the account architecture holds it) or the pill leaves the design.
- **"Đọc tiếp sau" is not drawn either.** The frame draws both "Lưu bài" and a primary "Đọc tiếp sau"; the app
  has one bookmark and remembers the place by itself, so a second one would be the same action twice.
- **The sheet is the app's existing dialog, not the design's sheet pattern.** The Quick Sheet's glass is not
  yet a shared primitive; restyling every sheet is its own slice.

## The rail's learner card and per-skill levels (2026-09-22, human decision)

The human asked for both (answer (c) to the five points). Built: the card at the foot of the rail - who this
is, the level they declared and the language they are learning - opening the profile and settings sheet, as
the frames draw it; hidden on a phone, where the Profile tab is that door.

**Per-skill levels are drawn only when the profile carries one** (`profile.skill_levels[skill]`). Nothing
serves that field today (`skillLevels` in `AppShell.json` is unserved), so no level prints. Repeating the one
declared level on all four skills would be a figure nobody measured. **Backend needed:** a per-skill level on
the learner profile, derived from real evidence, before those slots can fill.

## Reviews read back (2026-09-22, D-072.1, no schema)

The Writing room lists the pieces that were reviewed (`GET /api/essays`, this learner and this language,
eight most recent) with the version, the level the evaluator estimated and the date the row states. A row
opens the review stored with that piece (`GET /api/essays/{id}/review`) in a sheet: nothing is copied and
nothing new is written. **The bookmark ("Lưu nhận xét", `essays.review_kept_at`) is approved but not built:**
it waits on the independent architecture review, so the list is every reviewed piece, not a curated set.

## Book detail, measured against the source (2026-09-22, D-067)

Measured `[data-screen-label="Book detail · chapters"]` in `Orena Reading.dc.html` against
`#/book?id=…` at 1920x1080. **Corrected to the frame** (each verified in the running app):
book title 40→38, the chapters heading from a mono `ds-label` to the frame's Nunito 24/800 section
heading, the cover 176→220 wide with radius 14→18, chapter rows padding 12/14→16/20 and radius
13→15, list gap 7→9, chapter title 14→18, chapter number →15, chapter meta →13.5.

Reading Library needed nothing: at 1920 it already measures the frame exactly (bar 84 / padding
0 40, title Nunito 26/800, cover 236x315 radius 16 with the glass ring, grid gap 28, cover-to-text
13, card title Nunito 18/700). The per-skill CSS (`.lib[data-skill='reading']`) is what carries it.

**Not resolved here, because the design and the implementation differ in composition and rules 43-44
make that a decision, not a fix:**

- **The frame draws neither the chip row nor the stat tiles.** The app's hero carries
  `Đọc · EN · 5 chương · 1,200 từ` as chips and four `book-stat` tiles (words saved, reading time,
  average score, audio) that mostly render an honest dash. The frame carries one DM Mono line -
  `B1 · tiểu thuyết · 12 chương · 22 phút còn lại` - and no tiles at all.
- **The frame draws one action.** The app draws a primary plus three disabled icon buttons
  (bookmark, download, more). The disabled-placeholder question is already open for
  "Kiểm tra hiểu"; this is the same question on this screen.
- **The frame puts the saved words in the hero**, under `BẠN ĐÃ LƯU TỪ ĐÂY`, as word pills with a
  `+ 83 từ` overflow. The app has the same data but in a right-hand aside, beside an "About" section
  and a "Similar" note the frame does not draw.
- **The frame has no "chỉ chương chưa đọc" filter.**
- **A chapter row is one line in the frame** (number · title · `18 phút`), 56px tall. The app stacks
  the meta under the title, so the row is ~90px, and the meta is a **word count**, not minutes -
  minutes would need a per-chapter reading-time estimate the catalogue does not carry.
- **Cover proportion.** The frame's cover is 220x300; the app's artwork keeps its own ratio and
  renders 220x322.
- **Colour.** The frame's chapter text is `rgba(255,255,255,0.72)` and its number/meta
  `rgba(255,255,255,0.55)`; the app reads `--text-secondary` / `--text-muted`. Components may only
  read semantic tokens (`AGENTS.md`, Theme), so if these must match exactly it is a token question
  for `theme.css`, not a component override.
