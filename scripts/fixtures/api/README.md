# Captured API payloads

Responses captured from the running application, so the new UI's screen gates
read the shape the backend really returns instead of a shape a test assumed.
A screen model that reads a field these payloads do not carry fails its gate.

Rules:

- Captured, not written: each file is a real response from the isolated
  verification stack (throwaway PostgreSQL, the seeded catalogue, the test
  learner), saved as returned. Trim long arrays only, never rename or add keys.
- No secrets and no real learner data: catalogue metadata and the seeded test
  learner only.
- Re-capture when the backend serializer changes; the file name says the route
  and its query.

| File | Route | Captured |
| --- | --- | --- |
| `me.json` | `GET /api/me` | 2026-09-28 |
| `session_bootstrap.json` | `GET /api/session/bootstrap` | 2026-09-28 |
| `learner_profile.json` | `GET /api/learner-profile` | 2026-09-28 |
| `library_vocabulary_summary.json` | `GET /api/library/vocabulary/summary` | 2026-09-28 |
| `reading_practice_next.json` | `GET /api/reading/practice/next` (no article has an approved comprehension set in this build - `available: false`, a real, common shape) | 2026-09-28 |
| `listening_library.en.json` | `GET /api/listening/library?language=en` | 2026-09-28 |
| `listening_library.zh.json` | `GET /api/listening/library?language=zh` | 2026-09-28 |
| `speaking_library.en.json` | `GET /api/speaking/library?language=en` | 2026-09-28 |
| `speaking_library.zh.json` | `GET /api/speaking/library?language=zh` | 2026-09-28 |
| `vocabulary_feed.en.json` | `GET /api/vocabulary/feed?language_code=en` | 2026-09-28 |
| `vocabulary_feed.zh.json` | `GET /api/vocabulary/feed?language_code=zh` | 2026-09-28 |
| `learner_summary.json` | `GET /api/learner-summary?window=7d` | 2026-09-28 |
| `library_review_queue.json` | `GET /api/library/review-queue` | 2026-09-28 |
| `vocabulary_catalogue_search.en.json` | `GET /api/vocabulary/catalogue/search?q=health&language_code=en` (empty - see "Content-state gaps" below) | 2026-09-28 |
| `vocabulary_catalogue_search.zh.json` | `GET /api/vocabulary/catalogue/search?q=你&language_code=zh` (empty, same reason) | 2026-09-28 |
| `collection_search.json` | `GET /api/collection?query=health&limit=20` (search/screen.js's own call shape) | 2026-09-28 |
| `collection_library.json` | `GET /api/collection?domains=reading,media&limit=24` (library/screen.js's own call shape) | 2026-09-28 |
| `reading_articles.en.json` | `GET /api/reading/articles?language=en` | 2026-09-28 |
| `reading_articles.zh.json` | `GET /api/reading/articles?language=zh` | 2026-09-28 |
| `reading_article_detail.json` | `GET /api/reading/articles/{id}` (English article) | 2026-09-28 |
| `reading_article_detail.zh.json` | `GET /api/reading/articles/{id}` (Chinese article) | 2026-09-28 |
| `reading_library_books.en.json` | `GET /api/reading/library/books?learning_language=en` (captured after importing one EPUB through the real admin `POST /api/reading/library/import` flow - see "Data created for this capture" below) | 2026-09-28 |
| `reading_library_books.zh.json` | `GET /api/reading/library/books?learning_language=zh` (no Chinese book imported - real empty shape) | 2026-09-28 |
| `reading_library_book_detail.json` | `GET /api/reading/library/books/{id}` | 2026-09-28 |
| `reading_library_book_chapter.json` | `GET /api/reading/library/books/{id}/chapters/{chapterId}` (Reader's own chapter-content contract; `blocks`/`paragraphs` trimmed to the first heading + 5 paragraphs of a real chapter, see "Data created for this capture") | 2026-09-28 |
| `media_annotate.en.json` | `POST /api/media-learning/annotate` (the local, non-AI tagger the Reader's word-role lens, pinyin and tap-to-word read; English - `annotations[].{fragment,start,end,pos,pronunciation,lemma}`) | 2026-09-29 |
| `media_annotate.zh.json` | `POST /api/media-learning/annotate` (Chinese, session switched to zh first; `pronunciation` is one pinyin syllable per character, space separated) | 2026-09-29 |
| `reading_translate.json` | `POST /api/reading/translate` (`status: "unavailable"` - no AI provider key in this sandbox; the ready shape, `translations[].{segment_id,translated_meaning}`, is `writing_coach/reading_translation_api.py`'s own serializer) | 2026-09-29 |
| `reading_practice_evidence_attempt.json` | `GET /api/reading/practice/evidence` with one attempt - **built, not captured** (submission is off in this sandbox, see "Built from the serializer" below) | 2026-09-29 |
| `vocabulary_library_collections.en.json` | `GET /api/vocabulary/library/collections?language_code=en` (empty - see "Content-state gaps") | 2026-09-28 |
| `vocabulary_library_collections.zh.json` | `GET /api/vocabulary/library/collections?language_code=zh` (empty, same reason) | 2026-09-28 |
| `library_vocabulary.json` | `GET /api/library/vocabulary?limit=5` (English, the seeded 3012-word learner) | 2026-09-28 |
| `library_vocabulary.zh.json` | `GET /api/library/vocabulary?limit=5` (Chinese - the learner's session switched to zh first, `POST /api/platform/language`) | 2026-09-28 |
| `library_collections.json` | `GET /api/library/collections` (captured after creating one via `POST /api/library/collections` and filing a kept word into it - see below) | 2026-09-28 |
| `vocabulary_decks.json` | `GET /api/vocabulary/decks` (captured after creating one via `POST /api/vocabulary/decks`) | 2026-09-28 |
| `library_items.json` | `GET /api/library/items?kind=word` (captured after `POST /api/library/items` kept one word) | 2026-09-28 |
| `library_items_reading.json` | `GET /api/library/items?kind=reading&sources={id}` (captured after `POST /api/library/items` kept one article) | 2026-09-28 |
| `word_audio.json` | `GET /api/library/vocabulary/pen/audio` (`available: false, reason: "no_entry"` - the common shape for a word with no catalogue identity; see "Bugs found outside the field-shape class" below for a 500 this same route returns for a *catalogued* word) | 2026-09-28 |
| `word_clips.json` | `GET /api/library/vocabulary/pen/clips?limit=5` | 2026-09-28 |
| `chinese_stroke_order.json` | `GET /api/chinese/stroke-order?word=你好` | 2026-09-28 |
| `word_detail.json` | `POST /api/dictionary/word-detail` (English word; `available: false` - no AI provider key in this sandbox, the documented fallback shape) | 2026-09-28 |
| `word_detail.zh.json` | `POST /api/dictionary/word-detail` (Chinese word, session switched to zh first; shows `script: "hanzi"` and a real `pinyin` value) | 2026-09-28 |
| `word_detail_sheet.json` | `POST /api/dictionary/word-detail` with `depth: "sheet"` (Word Quick Sheet's own contract, English; `available: false` - no AI provider key) | 2026-09-28 |
| `word_detail_sheet.zh.json` | `POST /api/dictionary/word-detail` with `depth: "sheet"` (Chinese; `script: "hanzi"`, real `pinyin`) | 2026-09-28 |
| `sentence_sheet.json` | `POST /api/dictionary/sentence-sheet` (Sentence Quick Sheet, English; `available: false` - no AI provider key, the documented `sentence_sheet_unavailable` fallback) | 2026-09-28 |
| `sentence_sheet.zh.json` | `POST /api/dictionary/sentence-sheet` (Chinese, session switched to zh first) | 2026-09-28 |
| `listening_library_lesson.en.json` | `GET /api/listening/library/{lessonId}?target_language=en` | 2026-09-28 |
| `listening_library_lesson.zh.json` | `GET /api/listening/library/{lessonId}?target_language=zh` | 2026-09-28 |
| `listening_progress.json` | `GET /api/listening/progress?asset_id=...` (captured after Dictation's own real `POST` from a live Check - `checked_attempt_count:1`, `best_accuracy_percent:44`, `last_answer` is the exact partial answer typed) | 2026-09-28 |
| `listening_shadowing_progress.json` | `GET /api/listening/shadowing-progress?asset_id=...` (one row per shadowed segment: `segment_id`, `completed_rounds`, `updated_at`; captured after real rounds of Shadowing completed on the isolated app) | 2026-09-29 |
| `reading_practice_article_set.json` | `GET /api/reading/practice/articles/{id}` (404 `reading_set_not_available` - the real shape while no article has an approved set; see `reading_practice_next.json`) | 2026-09-28 |
| `practice_recommendation.json` | `GET /api/practice-recommendation` | 2026-09-28 |
| `essays.json` | `GET /api/essays` (empty - see "Content/data gaps this sandbox cannot fill") | 2026-09-28 |
| `practice_outcomes.json` | `GET /api/practice-outcomes?limit=5` (empty, same reason: needs an essay) | 2026-09-28 |
| `reading_practice_evidence.json` | `GET /api/reading/practice/evidence?limit=5` (empty - submission is off, `ORENA_READING_PRACTICE_SUBMIT` is unset) | 2026-09-28 |
| `speech_attempts.json` | `GET /api/speech/attempts?limit=5` (empty - no speech provider in this sandbox) | 2026-09-28 |
| `product_commerce.json` | `GET /api/product/commerce` | 2026-10-09 (catalogue v2, D-161) |
| `platform_languages.json` | `GET /api/platform/languages` | 2026-09-28 |
| `library_grammar.json` | `GET /api/library/grammar` | 2026-09-28 |
| `library_grammar_lesson.json` | `GET /api/library/grammar/{id}` | 2026-09-28 |
| `library_review_queue_pinned_listening.json` | `GET /api/library/review-queue` after pinning a listening item (`POST /api/library/items {kind: "listening"}`) | 2026-09-28 |
| `grammar_concept_library_grammar_lesson_timeline.json` | `GET /api/library/grammar/a2-present-perfect-vs-past-simple` (a pattern-stage block of type `timeline`) | 2026-09-28 |
| `progress_essays_list.json` | **built, not captured** - see "Built from the serializer" below | 2026-09-28 |
| `speaking_item.json` | `GET /api/speaking/items/{id}` - **built, not captured** (the Speaking catalogue ships empty, `writing_coach/content/speaking_catalog.v1.json` is `{"items":[]}` in this sandbox, so no `speak:` id exists to ask for - `speech_api`/`speaking_library.py#_catalog_card`+`read_speaking_item` own field shapes, see "Built from the serializer" below) | 2026-09-28 |
| `text_discussion_empty.json` | `GET /api/texts/discussion?source_kind=story&source_id={articleId}` (a source with no thread yet - real, common shape) | 2026-09-28 |
| `reading_practice_article_set_approved.json` | `GET /api/reading/practice/articles/{id}` - **built, not captured** (no article in this sandbox has an approved comprehension set - see "Built from the serializer" below) | 2026-09-28 |
| `reading_practice_grade_result.json` | `POST /api/reading/practice/sets/{id}/questions/{id}/grade` - **built, not captured** (same reason: no approved set to grade a question from, and `ORENA_READING_PRACTICE_SUBMIT` is unset besides) | 2026-09-28 |
| `text_discussion_thread.json` | `GET /api/texts/discussion?source_kind=story&source_id={articleId}` after one real question (`POST .../turns`) - a populated thread; the assistant turn is the isolated stack's local model (`ollama` / `qwen3:8b`) | 2026-09-29 |
| `text_discussion_turn_response.json` | `POST /api/texts/discussion/turns` (the exchange's own response: the thread plus `reused`) | 2026-09-29 |
| `spoken_response.json` | `POST /api/dictionary/spoken-response` with a Paraphrase-mode `situation` and a typed answer (`target_language: vi`; the model answered its `why` lines in English - a real model quirk, not a shape difference). `landed_differently` is empty here: a real, common shape | 2026-09-29 |
| `spoken_response_landed.json` | `POST /api/dictionary/spoken-response` with a spoken-style answer that has errors (`target_language: vi`): `carried` and `landed_differently` both populated, each fix with `quote`/`instead`/`why`/`judgement` - the shape Free Talk's Fixes rows, Conversation's per-turn coaching and Situation Reaction's rows read | 2026-09-29 |
| `spoken_response.en.json` | `POST /api/dictionary/spoken-response` for a Listening segment's New-Context answer (React/Reuse's own call shape, `target_language: vi`): `carried`/`landed_differently` both populated with a real past-tense correction, `another_way`/`next_attempt`/`say_again` all real model text - `scripts/test_orena_screen_react.mjs`'s own capture | 2026-09-29 |
| `conversation_turn.json` | `POST /api/dictionary/conversation-turn` (one learner turn `l1`; the partner's `reply_to`/`text`/`meaning`/`support`, the local model's own words) | 2026-09-29 |
| `speech_transcribe_unavailable.json` | `POST /api/speech/transcribe` on the isolated stack: HTTP 503, `detail.category: speech_asr_unconfigured` (no speech provider is configured here, so the success body `{provider, model, language, text, segments, words}` cannot be captured - it is read from `writing_coach/speech_api.py`, see "Not captured (speak-more pass)") | 2026-09-29 |
| `writing_essay_detail_live.json` | `GET /api/essays/{id}` on the isolated stack after two real reviews of one piece through the Writing room (`POST /api/evaluate`, the local model `ollama` / `qwen3:8b`; English, level B1): the second version, with its `revisions[]` series and `delta`. The model named no demonstrated band (`cefr_estimate: ""`) and its findings overlap - real, common shapes | 2026-09-29 |
| `writing_essay_review_live.json` | `GET /api/essays/{id}/review` for the same essay (WritingReview: per-issue `kind`, `grammarRef`, `span`, `anchored`) | 2026-09-29 |
| `writing_essay_revision_live.json` | `GET /api/essays/{id}/revision` for the same essay (RevisionCompare: `fixed` / `remaining` / `added`, `dimensionDeltas`) | 2026-09-29 |
| `writing_essay_detail_v1_live.json` | `GET /api/essays/{id}` for the first version of that series | 2026-09-29 |
| `writing_evaluate.json` | `POST /api/evaluate` (a revision of a stored essay: `id`, `series_id`, `revision_no`, `delta`, `errors[]`, ...) - see "Built with a fixed evaluator answer" below | 2026-09-29 |
| `writing_essay_detail_v1.json`, `writing_essay_detail.json` | `GET /api/essays/{id}` for the two versions of an English piece (`revisions[]`, `issues[]` with the real `priority` flag, `strengths[]`, `dimensions`, `summary.interpretation`) - see "Built with a fixed evaluator answer" below | 2026-09-29 |
| `writing_essay_review_v1.json`, `writing_essay_review.json` | `GET /api/essays/{id}/review` for the same two versions | 2026-09-29 |
| `writing_essay_revision.json` | `GET /api/essays/{id}/revision` for the second version (four fixed, one remaining, one added; four dimension deltas) | 2026-09-29 |
| `writing_essay_revision_first.json` | `GET /api/essays/{id}/revision` for a first version: HTTP 404 (`{status, body}`) - nothing to compare with | 2026-09-29 |
| `writing_essay_keep.json` | `POST /api/essays/{id}/keep` (`{id, kept, kept_at}`) | 2026-09-29 |
| `writing_essay_detail.zh.json`, `writing_essay_review.zh.json` | the same two routes for a Chinese piece (an HSK-shaped `cefr_estimate` and a `conjunction` finding, a Chinese-only category) - see "Built with a fixed evaluator answer" below | 2026-09-29 |
| `essay_evaluate.json` | `POST /api/evaluate` on the isolated stack for a real Respond-to-Content Opinion answer about a Listening lesson (the local model, `ollama`/`qwen3:8b`; English, `band_status: insufficient_evidence`) - `id`/`overall`/`issues[].{quote,suggestion,why}`/`next_actions[]`, the fields Respond's `mapFeedback` reads (`scripts/test_orena_screen_respond.mjs`'s own capture, distinct from the Writing-room `writing_evaluate.json` series above) | 2026-09-29 |

## Built with a fixed evaluator answer (Writing, 2026-09-29)

The `writing_*.json` files above that are not `_live` came from `scripts/capture_writing_fixtures.py`,
which runs the real application in-process (FastAPI `TestClient`, a throwaway SQLite database, the
way `tests/test_saved_reviews.py` does) and replaces only the model call (`app.generate_structured`)
with one fixed structured evaluator answer per call. `validate_result`, the weighted overall, the
review bounds, persistence, `row_to_dict`, `revision_delta`, `project_writing_review` and
`project_revision_compare` are the product's own code, so each payload is what the routes really
return for those answers - nothing is written into a response by hand. They exist because they are
predictable (the same words, findings and scores on every re-capture, English with Vietnamese support
text, and a Chinese piece) where a local model's answer is not; the `_live` files are the same routes
answered by the isolated stack's own local model. The Writing gates read both.

## Data created for this capture

A few routes only answer with real content once the account has some, and the
running app's own write endpoints were used to create it - never a direct
database write:

- **A book**, to capture `GET /api/reading/library/books` and its detail
  route: a minimal, real EPUB (one short chapter of original placeholder
  prose, no copyrighted text) was built and imported through the real admin
  flow, `POST /api/reading/library/import`.
- **A second book** (Reader pass, 2026-09-28): the sandbox's PostgreSQL runs on
  tmpfs, so the book above no longer exists by the time this pass ran (`GET
  /api/reading/library/books/{id}` now 404s for its id; the listing route
  answers empty). A public-domain EPUB already on disk in this worktree
  (`data/reading_library_assets/books/12c0b5f7.../original.epub`) was
  imported the same way to capture `reading_library_book_chapter.json` - the
  one route (`GET .../books/{id}/chapters/{chapterId}`) that had no fixture
  yet. The resulting book (*Alice's Adventures in Wonderland*, 12 real
  chapters) was left in the sandbox, not cleaned up - the same "harmless seed
  row" reasoning as below, and useful real multi-chapter content for the
  Reader's own chapter-navigation journey.
- **A deck**, via `POST /api/vocabulary/decks`.
- **A filing collection**, via `POST /api/library/collections`, with one kept
  word filed into it via `POST /api/library/collections/{id}/items`.
- **Two kept items** (one `word`, one `reading`), via `POST /api/library/items`,
  to capture `GET /api/library/items` non-empty.

These are harmless seed rows on the throwaway sandbox stack (PostgreSQL on
tmpfs) and were left in place; nothing outside this capture depended on them
being absent.

## Content-state gaps (not a sandbox data problem - fix nothing here)

`GET /api/vocabulary/library/collections` and `GET /api/vocabulary/catalogue/search`
answer empty for every language and every query in this build, not because the
sandbox lacks data but because **no curated vocabulary collection is
published**: `writing_coach/vocabulary_library.py` has real curated content (5
English packs, 7 Chinese packs, confirmed by reading
`list_vocabulary_source_collections()`), but `list_vocabulary_collections()` -
the one `GET /api/vocabulary/library/collections` reads - filters to
"published" packs only, and none are. `GET /api/vocabulary/library/collections/{id}`
404s even for an unpublished pack's own id (`becoming_vocabulary_library_collection_detail`
falls back to the same published-only `get_vocabulary_collection()`), so no
capture of a real, non-empty collection item is possible through this build's
own endpoints. The audit for `screens/discover/model.js#entryFromCollection`
and `screens/collection/model.js` was done by reading the serializer's own
dict shape instead: `_summary()` and `vocabulary_card_from_catalog_entry()`
in `writing_coach/vocabulary_library.py` / `writing_coach/vocabulary_cards.py`.
Both screens' field reads (`id`, `language_code`, `level_range`, `item_count`,
`progress.learned_count`, `headword`, `identity.language`, `review_stage`,
`saved`) match those serializers exactly.

## Not captured (speak-more pass, 2026-09-29)

- **A successful `POST /api/speech/transcribe`**: this sandbox has no speech provider
  (`GET /api/speech/status` answers `configured: false`), so the route answers the 503 captured in
  `speech_transcribe_unavailable.json`. Free Talk, Conversation and Situation Reaction read only its
  `text`; `scripts/test_orena_screen_free-talk.mjs` checks that `writing_coach/speech_api.py` returns
  `"text": result.text`, and the screens' success paths are verified through a verification-only
  route intercept, never a shipped fixture. The text-generation routes (`spoken-response`,
  `conversation-turn`) DO answer on this stack - the isolated app carries a local model - so those
  are real captures.

## Not captured (Dictation/Shadowing pass, 2026-09-28)

- **A real measured `POST /api/speech/pronunciation` response**: this sandbox has no speech provider
  key, so a completed Shadowing round's result panel is verified with the provider-neutral envelope
  built field-for-field from `writing_coach/speech_pronunciation.py#SpeechPronunciationResult`
  (`words[].offset_ms`/`duration_ms`, `error_type`, the score fields) and served to the real screen
  through a verification-only route intercept - never shipped, never a fixture here; the model
  functions are exercised against the same shape in `scripts/test_orena_screen_shadowing.mjs`.

## Not captured - genuinely not producible in this sandbox

- **`POST /api/media-learning/import` / `POST /api/media-learning/import/status`**
  and **`GET /api/media/my/{id}`**: importing a learner's own media needs
  either a reachable, *supported-provider* media URL (a plain Wikimedia
  Commons file page answers `422 unsupported_provider`; no supported-provider
  URL was available to try) or an uploaded audio/video file the importer
  accepts (a minimal synthetic silent WAV, built for this capture, was
  rejected: `"This file could not be imported."`). The response shape was
  instead confirmed by reading `writing_coach/media_api.py`'s
  `serialize_media_acquisition()`/`_serialize_asset()`/`_serialize_transcript()`
  and cross-checked against `static/orena/capabilities/media-acquisition.js`'s
  own field whitelist (`pick(...)`) - every field that module reads is one
  these serializers actually return.
- **`POST /api/dictionary/word-detail` with a real AI-resolved answer, and any
  populated `GET /api/library/vocabulary/{word}/audio`**: this sandbox has no
  AI or speech provider key, so every AI-backed route answers its documented
  fallback (`available: false`) - which is itself the fixture captured (see
  `word_detail.json`, `word_audio.json`, `word_detail_sheet.json`,
  `sentence_sheet.json`). This is the environment, not a UI defect, per the
  task brief. The `available: true` shape for both routes (a populated
  `contextMeaning`/`structure`/`vocabulary`) was instead checked against
  `writing_coach/word_detail.py`'s `project_word_detail()` /
  `project_sentence_sheet()` projection functions directly - every field the
  Quick Sheet screens read is one of these two functions' own output keys.
- **A non-empty `GET /api/essays`, `/api/practice-outcomes`,
  `/api/speech/attempts`**: an essay requires `POST /api/evaluate` to
  succeed, which is AI-backed and fails closed in this sandbox
  (`502 evaluation_provider_failure`, confirmed by trying it) - and
  practice-outcomes/speech-attempts both derive from essays/speech providers
  this sandbox does not have either. `progress/model.js`'s field reads
  (`e.id/created_at/prompt/overall`, `o.essay_id/created_at/grammar_title/
  focus_label/overall`, `a.id/take_id/created_at/asset_id/transcript_text/
  dimensions`) were instead checked against the serializers directly:
  `writing_coach/persistence/learning_repository.py`'s `_essay_payload()`,
  `writing_coach/becoming_outcomes.py`, and
  `writing_coach/persistence/specialized_repository.py`'s `_speaking_payload()`.
  All match.
- **`GET /api/reading/practice/evidence` non-empty**: submission is gated by
  `ORENA_READING_PRACTICE_SUBMIT=on`, an environment variable this sandbox
  does not set (and this audit does not restart the container to change).
  `progress/model.js#buildReadingEvidence`'s field reads were checked against
  `writing_coach/persistence/reading_evidence_repository.py#list_evidence()`
  instead; they match (`id/article_id/title/created_at/correct_count/total`).

## Built from the serializer, not captured

- `progress_essays_list.json`: `GET /api/essays` cannot be made non-empty in this
  sandbox (an essay needs `POST /api/evaluate`, which is AI-backed and fails
  closed). The file is one list item written field for field from
  `writing_coach/persistence/learning_repository.py` `_essay_payload()` as
  `app.py` `row_to_dict()` serialises it for the list route: no `text`, and the
  bounded `excerpt` the list route derives from it (only `GET /api/essays/{id}`
  carries the full text). Re-capture it from a runtime that can evaluate an
  essay.
- `speaking_item.json`: the Speaking catalogue (`writing_coach/content/speaking_catalog.v1.json`)
  is `{"schema_version": 1, "items": []}` in this sandbox (confirmed by reading the file directly)
  - real, not a bug: `writing_coach/speaking_library.py`'s own module docstring says it "ships
    empty. Adding an item is a content decision, not code (UI_BACKEND_GAPS SP-1)." There is no
    `speak:` id `GET /api/speaking/items/{id}` can answer for in this environment, so this fixture
    is one item written field for field from `speaking_library.py#_catalog_card()` and
    `read_speaking_item()`'s own dict literals - `id`, `source`, `practice_type`, `title`,
    `language`, `level`, `line_count`, `duration_ms`, `artwork`, `thumbnail_url`, `lines[].
    {line_id, text, reading, translations}`. `screens/speak`, `screens/compare`,
    `screens/attempts` and `screens/speak-summary` all verified end to end against a real
    `media:<lessonId>` source instead (a Listening lesson eligible for shadowing - real content in
    this sandbox), the wave's own report says how.
- `pronunciation_measured` (used inline in `scripts/test_orena_screen_speak.mjs` and
  `scripts/test_orena_screen_compare.mjs`, not a shipped file): this sandbox has no speech
  provider (`docs/design/canonical-ui` verification notes), so `POST /api/speech/pronunciation`
  cannot answer its `score_kind:"measured"` shape here. Built field for field from
  `writing_coach/speech_api.py`'s own response dict (`sed -n '558..591p' speech_api.py`) and
  `writing_coach/speech_pronunciation.py`'s `PronunciationWord`/`SpeechPronunciationResult`
  dataclasses: `score_kind`, `mode`, `reference_text`, `recognized_text`, `pron_score`,
  `accuracy_score`, `fluency_score`, `completeness_score`, `prosody_score`, `words[].{word,
  accuracy_score, error_type, offset_ms, duration_ms, syllables[], phonemes[]}`. The real,
  documented `score_kind:"synthetic_demo"`/error paths were exercised live instead (no provider
  configured - `speak`'s own real error state, verified against `writing_coach/speech_api.py`'s
  503 `pronunciation_unconfigured` path).
- `reading_practice_article_set_approved.json` / `reading_practice_grade_result.json`: no article
  in this sandbox has an approved comprehension set (`reading_practice_article_set.json` above is
  the real 404 every article answers instead), so Check Understanding's interactive quiz could not
  be exercised against real content here. Built field for field from
  `writing_coach/persistence/reading_evidence_repository.py`'s own `_set_payload()`/
  `_question_payload(with_answer=False)`/`served_set()` (the approved-set shape) and
  `grade_question()` (the graded-answer shape) - `id/rank/question_type/prompt/options` for a
  question, `question_id/selected_index/correct/correct_index/explanation/evidence_fragment` for a
  grade result. `question_type` uses only the backend's real closed set (`main_idea`, `detail`,
  `inference`, `vocabulary_in_context`, `cause_effect`, `sequence`, `authors_purpose`,
  `reference`), never the design frame's own sample "factual/inference/meaning/intent" wording.
  `evidence_fragment` is the question's stored `evidence_text`: words copied exactly from the article
  body (`reading_evidence_repository.py` verifies `body[evidence_start:evidence_end] == evidence_text`),
  so it carries no quotation marks of its own, and it is `""` for a `main_idea` / `authors_purpose`
  question that has none.

- `reading_practice_evidence_attempt.json`: `GET /api/reading/practice/evidence` is empty here (`ORENA_READING_PRACTICE_SUBMIT` is unset, so no attempt can be written).
  One item, field for field from `writing_coach/persistence/reading_evidence_repository.py#list_evidence()`
  (`id/kind/article_id/set_id/language/title/topic/content_kind/created_at/passage_level/correct_count/total`,
  `content_kind` one of the model's `article`/`news`). Reading Complete's "understood" stat reads
  `article_id`, `correct_count` and `total` from it.

## Bugs found outside the field-shape class (reported, not fixed here)

- `GET /api/library/vocabulary/{word}/audio` answers `500 Internal Server
  Error` for a word that *is* in the catalogue (reproduced with `health` and
  `vacancy`, both real saved/feed words) - `pen`/`extinct`/etc. (not in the
  catalogue) correctly answer `200 {"available": false, "reason": "no_entry"}`
  instead. Both `screens/word/screen.js` and `screens/library/screen.js`
  already wrap this call in `try/catch` and fall back to "no audio", so
  nothing crashes - but the 500 itself is a real backend defect, not a UI
  field-shape bug, and is out of this task's scope to fix.
