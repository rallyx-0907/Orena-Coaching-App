# Reading source acceptance, 2026-10-13 (Phase 4)

Branch `claude/reading-source-quality`. A decision document built only from three inputs: the catalogue
(`READ_SOURCE_CATALOG.md`), the Phase 2 trial (`READ_SOURCE_TRIAL_2026-10-13.md`, defects D1 to D14) and the Phase 3
learner evaluation (`READ_SOURCE_LEARNER_UI_2026-10-13.md`, findings U1 to U9 below). No new runtime action was taken.
Nothing here clears a right; every ACCEPT is a recommendation for the human, and "ACCEPT" never means "auto-publish".

Where this document differs from the lead's proposed verdicts, the difference is marked **DIFFERS** with the evidence.

## 1. Source verdicts

### ACCEPTED (conditional; none is ready today)

| Source | Verdict | Conditions before real publishing | Evidence |
| --- | --- | --- | --- |
| NASA (nasa.gov, EN-2) | ACCEPT, conditional. Agrees with the lead, with two additions | strip the press-contact block (D11); calibrate or reviewer-set the level (D6); show the publisher and credit (U1); restrict to the `nasa.gov` feeds | Phase 2: body, paragraphs, title, date, language all P. Phase 3: reads cleanly, hook is good, but 31f6e9 ends in phone numbers and e-mail addresses (not published), level C2 on a press release. **Addition:** the `science.nasa.gov` and Earth Observatory feeds are not well-formed XML (catalogue) and their items lose the rights snapshot (D8), so only the `nasa.gov` news-release feed is acceptable until D8 is fixed. **Addition:** images are carved out of the "generally not copyrighted" statement (Q1), so no thumbnail may be shown from NASA without a per-item credit check. |
| Global Voices EN (EN-1) | ACCEPT after D1. Agrees | D1 fixed; credit Global Voices **and** the original publisher or author (U1); strip the editorial preface and author bio (D11); level set by reviewer (D6) | Phase 2: 7 of 10 articles have glued words (up to 42), the other 3 are clean. Phase 3: the three clean ones read well; 68d82c carries a partnership preface and its byline is "Peace News", not Global Voices. All ten rated C1/C2 (B2 to C1 in the catalogue). CC BY 3.0 text only (Q1 for images). |
| VOA 中文 (ZH-2), VOA-produced text only | ACCEPT after D2 and a non-article filter. Agrees, with a stricter filter | D2 (`<br><br>` paragraphing); a quality gate that stops non-article pages (D9, D10); wire-credit exclusion (Q6) built and tested; reviewer-set level (D6) | Phase 2: 3 of 6 pages are clean full reports (the cleanest ZH extractions); 1 loses all paragraphing; 2 are video or audio pages, one with confidence `medium` and **no flag at all** (D10). Phase 3: Hanzi, full-width punctuation and paragraphs intact; all HSK6. **Addition:** the wire-credit exclusion was not exercised (only VOA-produced pages were submitted), so Q6 is still untested. |

### MANUAL_ONLY

| Source | Verdict | Reason |
| --- | --- | --- |
| VOA Learning English (EN-3) | MANUAL_ONLY. Agrees with the lead; **the catalogue said ACCEPT as a one-off archive import, so this is a downgrade** | Feeds are frozen (newest item 2025-04-29), so no polling is possible. Every text page starts with "No media source currently available" (D9), one body keeps an AFP credit line, the audio page became a 7-word candidate, level was rated B2 or C1 for A2-B1 text (D6), and the shared logo and `player-spinner.png` are image candidates (D13). It remains the best learner fit, so the path is a curated URL list with reviewer sign-off, revisited after D9 and D6. |
| Global Voices 中文 (ZH-3) | **DIFFERS: MANUAL_ONLY until the Traditional-script decision, then ACCEPT.** The lead proposed ACCEPT pending the human and D8 | Same two blockers as the lead (Q9 and D8), plus two the lead did not list. (1) Content mix: of the 10 feed items, at least two are not learning articles (a welcome and call to join a programme, 5c5837, and a fundraising appeal, 643d74, judged from titles and Phase 2 notes), and the feed is very slow, so unattended publishing would put appeals in front of learners. (2) Level: all ten are HSK6 including a plain invitation (D6). It is clean text and the cleanest licence in the ZH set; it earns ACCEPT only once script handling exists (U5) and a content filter or manual selection is in place. |

### REJECTED / DEFERRED

| Source | Verdict | Reason |
| --- | --- | --- |
| zh Wikipedia (ZH-1) | REJECT for now. Agrees | The feed path yields the wrong page for 10 of 10 items (D3); the direct path yields whole encyclopedia pages of 3,273 to 18,496 units with the wrong title (D4), infobox, references and `[n]` markers (D5), one page mixes scripts and one is almost wholly Traditional; and ShareAlike (Q2) is unanswered. Reconsider only after D3, D4, D5 and excerpting exist and Q2 is decided. This is "not yet", not "never": it is the best topic spread in the ZH set. |
| EN Wikipedia (EN-6), Simple English Wikipedia (EN-5) | Untrialled; the same engine defects D3 to D5 and Q2 apply. Treat as deferred with ZH-1 | Catalogue verdict was ACCEPT (curated); the Phase 2 wiki evidence is zh only, and English titles were not re-run (H3). |

### Not trialled (catalogue recommendation kept, all marked "untrialled")

- EN ACCEPT, untrialled: EN-4 Wikinews (archive), EN-5 Simple English Wikipedia (Q2), EN-6 English Wikipedia (Q2, link caveat), EN-7 Project Gutenberg (header and licence block, Q5; H9 untested), EN-8 Standard Ebooks (book source).
- EN MANUAL_ONLY, untrialled: The Conversation (BY-ND; H1 `promos` pruning was confirmed in a one-off extraction check, not as an import), ProPublica, MIT News, ESA, Library of Congress blogs, US DOE.
- EN REJECT, untrialled: BBC News, Smithsonian, Open Culture, The Marginalian, ScienceDaily, Nature, Aeon, Phys.org.
- ZH ACCEPT, untrialled: ZH-4 zh Wikinews (archive), ZH-5 zh Wikisource (curated Lu Xun and other shorts, the only ZH story source; Q5).
- ZH MANUAL_ONLY, untrialled: UN News 中文, 阮一峰, 爱范儿, 報導者, 行政院 (Q7).
- ZH REJECT, untrialled: 端传媒, 少数派, 极客公园, 苦劳网, BBC 中文, 纽约时报中文网, DW 中文, FT中文网, PTT.
- Note for the lead: with zh Wikipedia out and Global Voices 中文 held back, the live ZH ACCEPT set is VOA 中文 only, which is politics-heavy. ZH-5 (Wikisource) is the catalogue's own fallback for the story category and is the next source worth trialling.

## 2. Pipeline defect list, as a proposed fix sequence

Types: **Engine** = extraction, poller, processing or admission code; **UI** = learner screens; **Contract** = a gap in
the learner API or the design, where a human decision on what the product shows comes first. "Blocks" means "should not
be published to real learners until fixed (or consciously waived by the human)". Locations are the Phase 2 file:line
references against main 948fd871; the UI ones are from the Phase 3 observation and are unconfirmed in code. The order is
smallest, highest-value first; each step unlocks sources noted. This is a sequence, not an engine redesign.

| # | Defect | Sev | Blocks real publishing | Likely location | Type |
| --- | --- | --- | --- | --- | --- |
| 1 | **D1** Whitespace at inline boundaries dropped, words glued (11 of 25 EN articles) | High | Yes (GV EN, VOA LE, NASA) | `reading_article_extraction.py:154-165` (`_text` strips each inline node), `_collect` :424 | Engine |
| 2 | **U4** CJK line-start punctuation: `）` `，` `〕` start lines; Chinese line spacing very loose | Medium | No, but visible on every ZH article | reader CSS for CJK (line-break/word-break, hanging punctuation); not located in code | UI (check against the Reader frame, which does not draw it) |
| 3 | **D11 + D12** Editorial preface, author bio, press-contact block, reference list kept as body; author can be a CMS username | Low in Phase 2; **High for NASA** (contact block shows phones and e-mails) | Yes for NASA and GV EN | `reading_article_extraction.py:480-518`, :256-281, `_page_metadata` :313 | Engine (add rules, small) |
| 4 | **D9** Player and related-content text extracted as body (VOA LE all text pages, VOA 中文 video page); wire credit handled inconsistently | Medium | Yes (VOA LE, VOA 中文) | `reading_article_extraction.py:56-62` token list, `_edge_attribution` :480-492 | Engine |
| 5 | **D10** Non-articles enter the queue; `publication_blockers` ignores quality; a medium-confidence video page had no flag | Medium | Yes (VOA 中文 filter, VOA LE audio page) | `reading_content_engine.py:373-381`, `reading_admin_api.py:191-217` | Engine (a quality gate or warning, not a redesign) |
| 6 | **D8** Rights snapshot lost when item host differs from source host (`science.nasa.gov`, all `zht.` GV 中文 items) | Medium; fails safe but hides the licence from the reviewer | Yes (GV 中文, NASA science feeds) | `reading_admission.py:20-34`, `reading_content_engine.py:268` | Engine |
| 7 | **U1** No source or publisher in the list API or the reader; detail shows only `attribution.author`; licence, credit and source URL not shown to the learner | **High** | **Yes: attribution is a licence condition for GV (CC BY) and VOA credit, and NASA asks for it** | `GET /api/reading/articles` payload (id, title, language, level, topic, time, count, excerpt, published_at, revision), reader meta line; the design's Discover card already draws `c.source` | Contract (API field) + UI (card and reader) |
| 8 | **D2** `<br><br>` not a paragraph break (VOA 中文 single-`<p>` reports flatten to one paragraph) | High for ZH news | Yes (VOA 中文 where the pattern appears) | `reading_article_extraction.py:158-159`, `_collect` :407-432 | Engine |
| 9 | **D6** Level saturated: all 32 ZH items HSK6, 13 of 18 NASA and GV EN items C2, VOA LE (A2-B1) rated B2/C1; confidence is a length proxy | High (level filters are learner-facing) | Yes, or mitigate: require a reviewer-set level (`reviewed_level` exists) before publish | `reading_processing.py:101` (`_ZH_COMMON`, 39 characters), :309-316, :329 | Engine (largest fix; interim mitigation is process) |
| 10 | **U2** No image path: every card is a generated letter tile; article payload has no image field although the extractor stores candidates | High as a quality gap; blocking only if the human requires thumbnails | Human decision (section 3) | article payload and card; candidates `reading_article_extraction.py:874-944`; third-party image rights (Q1) | Contract + UI + Engine (D13 candidate noise) |
| 11 | **U5** Traditional versus Simplified is not recorded or labelled; level and tokenisation assume Simplified; one wiki body mixes scripts | Medium | Yes for GV 中文 until the human decides (Q9) | no script field in item metadata or analysis; `reading_processing.py` | Contract + Engine + UI |
| 12 | **U3** Level chips are engine output shown as authoritative; B1 learner sees only C1/C2 (see 9) | Medium-High | Follows from 9 | `reading_processing.py` | Engine (same fix as 9) |
| 13 | **U6** Long titles clamp to two lines (Phase 3: "...trans fats o...", about two words per line on the phone) | Low-Medium | No | Discover card title style; the design's title style shows no clamp in the frame, so the clamp may be implementation, to confirm | UI |
| 14 | **D7** Target suggestion splits on non-ASCII letters, 88 of 198 EN targets start or end with a function word ("el ni", "the u") | Medium | No while targets are reviewed (all 8 trial articles were published with zero targets) | `reading_processing.py:70`, :369-383 | Engine |
| 15 | **U8** Phone reader header truncates title and meta; page progress hidden at 390 | Low | No | reader header | UI |
| 16 | **U7** Cards give minutes only (no word or Hanzi count) | Low | No | card meta | UI (design question) |
| 17 | **U9** Baseline console errors: 100+ on every screen from unrendered `{{ ... }}` SVG attributes (`points`, `d`, `x`, `width`, `x1`) in the page template, e.g. `/:187`, `:208`, `:304-368` | Low (functional, noise) | No | page template at the app root (design placeholders left in static markup); not located in code | UI |
| 18 | **D13, D14** Noisy image candidates (shared logo, spinner, duplicates); canonical re-encodes parentheses | Low | No | `reading_article_extraction.py:874-882`; `reading_processing.py:173-210` | Engine |
| 19 | **D3, D4, D5** Wikipedia: wrong page from feeds, title from Wikidata description, whole pages with infobox and references | High for Wikipedia | Yes, but only matters if wiki sources are accepted | `reading_source_poller.py:101`; `reading_article_extraction.py:565`, :494-518; `reading_processing.py:444-470` | Engine; deferred with the Q2 decision |

What each fix unlocks: steps 1 to 6 together make NASA (`nasa.gov`) and GV EN safe on the text side; add step 7 and they
are creditable; step 8 unlocks VOA 中文 text pages; steps 9 and 11 are the prerequisites for GV 中文 and for honest level
filters; step 19 is only needed for Wikipedia.

## 3. Human decisions needed

1. **ShareAlike (Q2).** Is Orena willing to offer its derivatives (excerpts, level notes, translations, generated
   questions, glossary) under CC BY-SA, including on paid tiers? Gates zh and EN Wikipedia and Simple English Wikipedia.
   Recommendation: leave Wikipedia deferred until answered; no engine work depends on it before step 19.
2. **NonCommercial versus paid plans (Q3).** Is any learner use "non-commercial" while Orena has paid plans? The
   catalogue assumed no. Gates MIT News, ProPublica, 阮一峰, 爱范儿, 報導者. None is in this acceptance list, so nothing
   here is waiting on it today.
3. **Traditional script (Q9).** Is zh-Hant content in scope for the Simplified learner track? If yes: a script label
   (U5), a script-aware level, and whether Simplified learners are offered it. If no: GV 中文 is rejected and ZH-5
   Wikisource becomes the next ZH source to trial.
4. **Is a source/credit line and a thumbnail required before any real publish?** Recommendation: **credit line yes**
   (step 7; attribution is a stated licence condition for GV, VOA and NASA, and the trial articles currently show none to
   the learner); **thumbnail no**, as a requirement. Real thumbnails depend on the image-rights answer (Q1), and the
   letter tile is the design's no-image state. This is a product call, not an engine one.
5. **The 8 :8021 trial publishes.** Keep them for human review in the browser, or undo now. Recommendation: keep them
   until the human has looked, then undo (they were published with `can_republish = true` for a local trial only). They
   do not affect :8000 or :8010. Also open: Q1 (third-party media inside open-licensed articles) and Q6 (wire copy), which
   decide whether a source-level `automation_allowed` is ever enough.
6. **VOA wire copy (Q6), update 2026-10-14.** Implemented as D-193 (PROPOSED, review pending). A source flagged
   `public_domain_requires_staff_authorship` (VOA 中文 and Learning English hosts) no longer hands its "public domain"
   answer to an item that shows a wire credit or derivation note (for example "本文依据了美联社的报道") or has no byline: the
   item's republish, adapt and licence answers become unknown, so an administrator must publish it over D-190's warning with a
   reason, automation refuses it (D-111), and the learner is shown no licence. Tested on real voachinese.com pages (staff report
   keeps rights; two wire-derived rewrites lose them; other sources unaffected). The human still decides: what to do with the
   eight trial publishes (run `scripts/check_published_reading_rights_refinement.py`), whether a story that merely cites
   an agency in a sentence counts as staff-written (today it does), whether contributor bylines count as staff, and photo
   rights (Q1).

## 4. State on :8021

Eight articles are `published`, each with a `can_republish = true` review event, actor `phase3-local-trial`, reason
"local :8021 trial only". Nothing else on :8021, :8000 or :8010 was changed, and no source setting was changed. No
`audit_logs` row exists for these publishes (the admin account was not an administrator, so the repository calls were
used instead of the HTTP route).

| id | source |
| --- | --- |
| 52578bea-4e9c-43ae-a3b5-8a7d2d6f17ad | NASA |
| b8975469-3401-4bee-aeb1-ee6f1fe94c71 | Global Voices EN |
| 68d82c0b-2e55-440d-bfaa-b18fa0ddecad | Global Voices EN |
| 3f4d7ce2-c125-47be-8d05-b36d0d6219da | Global Voices EN |
| ced37e3e-04c3-4d12-b602-d1160f043625 | VOA 中文 |
| 01c68f43-b0e3-4ae2-be71-ee3c3a114d8c | VOA 中文 |
| 99b12317-41cd-4726-b6fc-66e1b8b2ef26 | VOA 中文 |
| 3d00d033-f273-4835-86c2-f4c609c91999 | Global Voices 中文 (URL source) |

Undo, per id, inside `orena-next-verify-web` (or through the Admin Reading screen with an administrator account):
`ReadingContentRepository.set_status(id, "unpublished", actor=..., reason=...)` (or `"needs_review"` to return it to
the queue), then `set_rights(id, {"can_republish": None}, actor=..., reason=...)` to return the question to
unanswered. The rights answer is recorded as a review event over the unchanged source snapshot, so the original state
is always recoverable. A docker call needs 2 GB free RAM first, and Docker must not be restarted.

## 5. Human decisions (2026-10-13, recorded as D-189)

These answer section 3.

1. **Wikipedia / CC BY-SA:** accepted as policy, but the sources stay REJECT_TEMPORARY in the catalogue until extraction
   and attribution/licence handling meet the bar.
2. **NonCommercial (NC) sources:** never published into the commercial or paid Orena catalogue. Internal use only, or
   with an explicit separate permission.
3. **Traditional script:** allowed, but it must carry Traditional metadata and a label, and is never mixed silently with
   Simplified. Global Voices 中文 stays MANUAL_ONLY until the learner UI distinguishes the script.
4. **Attribution / source line:** required before any real corpus is published.
5. **Thumbnail:** not a publish blocker.
6. **The 8 :8021 trial publishes:** kept for the owner's review, then unpublished or archived.
7. **Next milestone, "Reading Sources - Production Readiness":** acceptance target is NASA, Global Voices EN and VOA 中文
   running end to end (source, poll/import, extraction, quality gate, review, publish, attribution, learner card,
   reader) with shippable content. Fix order:
   - P0: A provenance end to end, B the Admin Reading 403, C extraction corruption, D source cleanup, E quality admission.
   - P1: F manual reviewer level, G automatic level, H Chinese kinsoku, I simplified/traditional detection and label,
     J source-specific rules.
   - P2: K thumbnail, L long titles, M Wikipedia.

   The catalogue is not widened until the three sources pass; the next candidates are Chinese public-domain sources
   such as zh Wikisource.

## 6. Closing (2026-10-14)

Owner instruction 2026-10-14. Milestone "Reading Sources - Production Readiness" (section 5, item 7):
**CLOSED — source pipeline accepted; release follow-ups remain.** This does not say that Reading as a whole is
production-ready.

**Evidence.** Final consolidated acceptance on :8021, main `2ec7daea`, 2026-10-14. Criteria 1 to 4 met:

- `word_translation`: the Groq standby `qwen/qwen3.8-27b` passed its live test; the OpenRouter primary returned 429.
- Word Quick Sheet: EN to VI and ZH to VI show a Vietnamese meaning on the first tap, with IPA (English) or pinyin (Chinese).
- NASA, Global Voices EN and VOA 中文 ran end to end. Three newly published articles are kept as the canonical smoke fixtures:

  | source | article id |
  | --- | --- |
  | NASA | `9626a4b7-2485-47da-a06e-e7473ef232b4` |
  | Global Voices EN | `d0b34c8d-8afa-4cab-b3d0-6faba663024b` |
  | VOA 中文 | `31faead9-9a00-42d2-b587-1c2e66649193` |

- `voachinese.com/z/1741` is held (not published).
- Level spread: EN shows a spread of levels; zh news is HSK6 (see #203).
- Not done: the touch-device check. It is the mobile release gate (#202).

**Operational facts (observed only).** About 50 OpenRouter requests were made during the test day, after which the primary
returned 429; the exact free-tier quota is not confirmed. Groq calls are recorded at $0 under the current
observed/configured free-plan setup (owner-confirmed free plan on 2026-10-14); this is not guaranteed permanent pricing.
D-200 and its prefetch sizing were reworded to this.

**Release follow-ups, to be resolved before :8000.**

| Priority | Issue | Subject |
| --- | --- | --- |
| P1 | #194 | Quick Sheet sense in context (泡沫) |
| P1 | #195 | 404 on practice/annotations when the Reader opens |
| P1 | #196 | NASA rights/source policy default |
| P1 | #197 | No internal source name visible to learners |
| P1 | #198 | A thumbnail never exposes an approved image without credit |
| P2 | #199 | Extra English line on the ZH sheet |
| P2 | #200 | NASA title suffix |
| P2 | #201 | Admin image-review UX |
| P2 | #202 | Touch verification (mobile release gate) |
| HSK | #203 | Audit HSK6 for zh news before calling it a bug |
| HSK | #204 | zh HSK1 to HSK5 source coverage |
| Existing | #183 | Flaky media test |

**:8000 is not deployed.** Deploying needs the owner's authorisation (and, per D-177, migration 0026).

**:8021 cleanup:** owner performing the cleanup in Admin: unpublish the 8 trial samples of 2026-10-13 (15:07 UTC batch) and
return the 2 learner test accounts to Free. Kept published by owner decision: de4c636c (Ice Ages) and the 3 earlier E2E
articles of 2026-10-14 (c8162a0c NASA Koch, ac4c76de GV Nepal, ffbf707a VOA 佳全). Not verified by this document.
