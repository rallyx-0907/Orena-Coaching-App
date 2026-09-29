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
| `reading_practice_article_set.json` | `GET /api/reading/practice/articles/{id}` (404 `reading_set_not_available` - the real shape while no article has an approved set; see `reading_practice_next.json`) | 2026-09-28 |
| `practice_recommendation.json` | `GET /api/practice-recommendation` | 2026-09-28 |
| `essays.json` | `GET /api/essays` (empty - see "Content/data gaps this sandbox cannot fill") | 2026-09-28 |
| `practice_outcomes.json` | `GET /api/practice-outcomes?limit=5` (empty, same reason: needs an essay) | 2026-09-28 |
| `reading_practice_evidence.json` | `GET /api/reading/practice/evidence?limit=5` (empty - submission is off, `ORENA_READING_PRACTICE_SUBMIT` is unset) | 2026-09-28 |
| `speech_attempts.json` | `GET /api/speech/attempts?limit=5` (empty - no speech provider in this sandbox) | 2026-09-28 |
| `product_commerce.json` | `GET /api/product/commerce` | 2026-09-28 |
| `platform_languages.json` | `GET /api/platform/languages` | 2026-09-28 |
| `library_grammar.json` | `GET /api/library/grammar` | 2026-09-28 |
| `library_grammar_lesson.json` | `GET /api/library/grammar/{id}` | 2026-09-28 |
| `library_review_queue_pinned_listening.json` | `GET /api/library/review-queue` after pinning a listening item (`POST /api/library/items {kind: "listening"}`) | 2026-09-28 |
| `grammar_concept_library_grammar_lesson_timeline.json` | `GET /api/library/grammar/a2-present-perfect-vs-past-simple` (a pattern-stage block of type `timeline`) | 2026-09-28 |
| `progress_essays_list.json` | **built, not captured** - see "Built from the serializer" below | 2026-09-28 |

## Data created for this capture

A few routes only answer with real content once the account has some, and the
running app's own write endpoints were used to create it - never a direct
database write:

- **A book**, to capture `GET /api/reading/library/books` and its detail
  route: a minimal, real EPUB (one short chapter of original placeholder
  prose, no copyrighted text) was built and imported through the real admin
  flow, `POST /api/reading/library/import`.
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

## Bugs found outside the field-shape class (reported, not fixed here)

- `GET /api/library/vocabulary/{word}/audio` answers `500 Internal Server
  Error` for a word that *is* in the catalogue (reproduced with `health` and
  `vacancy`, both real saved/feed words) - `pen`/`extinct`/etc. (not in the
  catalogue) correctly answer `200 {"available": false, "reason": "no_entry"}`
  instead. Both `screens/word/screen.js` and `screens/library/screen.js`
  already wrap this call in `try/catch` and fall back to "no audio", so
  nothing crashes - but the 500 itself is a real backend defect, not a UI
  field-shape bug, and is out of this task's scope to fix.
