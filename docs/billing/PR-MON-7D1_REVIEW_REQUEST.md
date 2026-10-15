# PR-MON-7D1: decisions + Reading cache isolation (review request)

**Status: IMPLEMENTING, draft PR for CI and independent review.** Stacked on PR-MON-7A-first (#231, approved at
`94f96a8f`, not merged), because the PR-MON-7 design and the Billing decision log live there. Nothing is activated:
`ORENA_CAPABILITY_ROUTING` stays empty, no Ollama Cloud learner model, no `learner_text_models` entry, Credits, quota
enforcement and funding enforcement off, 0034 proposed, 0027 -> 0033 not applied, R-MON-014 not run, no price, pack or
grant, no payment or runtime migration. No new table and no schema change.

## Decisions recorded

- **D-MON-025:** H7-6 (Ollama Cloud provider privacy, model-level allowlist mandatory), H7-3 (daily request-meter
  bootstrap limits in the plan catalogue), H7-5 (cache isolation architecture), H7-4 (Intelligence via a separate
  Agent adapter).
- **D-MON-026:** H7-7 (covered-credit allowance), H7-8 (existing paid baseline as backup, caps $0.50 / $0.50 / $1.00),
  the H7-4 proof list for Ollama Cloud, the H7-2 benchmark process and the delivery order.
- **D-MON-027:** H7-8 DECIDED, pending one operator verification of the live `ai.active_selection` /
  `ai.capability.*` rows; the incarnation cache-scope invariant; the replacement of the leak-locking tests.

Details: `PR-MON-7_DESIGN.md` §12 and §14 (§14.8 is the cache authority matrix).

## What changed

- **`writing_coach/reading_cache_scope.py` (new).** The server decides the scope:
  - `SHARED`: a server-verified published article (`get_published_article`) whose title and body contain every text
    the request derives from;
  - `inc:<incarnation>`: the learner's active account incarnation (resolved, never created);
  - `UNSCOPED`: no readable incarnation. No learner/private caching at all: nothing is written and no learner
    entry is read. Exact verified-public shared entries (keyed by the exact published text) may still be reused,
    because the shared namespace only ever holds server-verified published content.

  A client `content_id`, prefix or flag is only a claim. An unreadable published store means not published.
- **`DerivedCache`:** the in-process LRU is namespaced by scope. A learner scope reads its own entries, then the shared
  ones (which only ever hold verified published text). Writes go to the scope's own namespace. The persistent store is
  read and written in the shared scope only. `UNSCOPED` writes nothing and reads only the shared in-process entries.
- **Reading translation, summary, word-detail, sentence-sheet:** `persist=<client prefix>` replaced by the
  server-decided scope. A summary by verified `article_id` stays shared; a book chapter or raw text is learner-scoped.
- **Basic tap (`reading_lookup`):** the learner's scope, resolved on the request thread and passed to the
  local-engine worker.
- **Word deep:** a catalogue-example explanation (8a) stays in the shared file store. A learner-fragment explanation
  (8b) is in-process only, keyed by the incarnation and the fragment, and never reads or writes the shared file (so an
  existing poisoned file is never served for a fragment).
- **`app.py`:** wires the incarnation resolver (account backbone) and the published-article reader.

## Tests changed because they encoded the old unsafe behaviour

- `tests/test_reading_on_demand.py::test_translate_endpoint_persists_only_for_a_published_article` became
  `test_translate_endpoint_shares_only_a_server_verified_published_article`. A fake `article:` id, and a real
  published id with text the article does not contain, both stay out of the table; only a verified segment persists.
- `tests/test_reading_on_demand.py::test_published_content_is_kept_in_the_shared_table` became
  `test_only_server_verified_published_content_is_kept_in_the_shared_table`. A bare `article:abc` claim stays out; the
  verified article is kept.
- `tests/test_reading_on_demand.py::test_the_sentence_sheet_is_cached_but_the_learners_question_never_is` now names a
  published article the server knows.
- Six suites (`test_lookup_bounds`, `test_lookup_contract`, `test_lookup_deterministic`, `test_lookup_guards`,
  `test_reading_on_demand`, `test_reading_translation`) gain a one-learner incarnation fixture. Their reuse assertions
  are unchanged; reuse now needs an incarnation.
- Service-level `persist=True` / `persist=False` became `scope=SHARED` / the learner default.

## New contract tests (`tests/test_reading_cache_isolation.py`)

1. A fake `article:abc` with no published row gets no shared scope and never reaches the table.
2. Learner/private ids (`book:`, `import:`, `published:true`, a bare id, an unknown article, a published id with
   foreign text) never get the shared scope. An unreadable store is not published.
3. A server-verified published article is shared and persisted, and learner B reuses it.
4. Learner A's private result is never served to learner B.
5. The same incarnation reuses its own result.
6. A new incarnation of the same account inherits nothing.
7. Word deep: a learner fragment never reaches another learner or the store; different fragments do not collide; a
   poisoned shared file is never read for a fragment.
8. A catalogue-example word-deep explanation stays shareable.

Also covered: no incarnation means no learner caching, and never a global one. A learner scope still reads the
shared published answers (a tap). An unverified summary is the learner's own. Word-detail shares only verified
published text.

## Unblocked for PR-MON-7A-follow-up (not activated)

- the learner dictionary and contextual paths (#7: word-detail, sentence-sheet);
- learner-import Reading translation and summary (#4a, #5a);
- learner-fragment word deep (#8b).

The published counterparts (#4b, #5b, #8a) keep a server-verified shared scope for 7B.

## Out of scope

- the legacy dictionary cache's missing language in its key (a correctness issue, not a leak);
- the router L1 (`word_translation`, word-only public reference);
- rows an earlier build may have put in `reading_derived_texts` under an unverified `article:` claim. That table
  exists only through the unapplied proposed migration 0028. A learner scope never reads the store, and a shared read
  is keyed by verified published text.
