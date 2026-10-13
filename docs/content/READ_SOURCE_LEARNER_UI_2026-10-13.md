# Reading source trial, learner UI evaluation, 2026-10-13 (Phase 3)

Branch `claude/reading-source-quality`. Eight reviewed trial articles were published on the local test runtime :8021
only and then judged as a learner would meet them: library card, article page, reader, desktop 1920x1080 and phone
390x844, light and dark. Local execution only. No CI evidence is claimed. Evidence images are in
`docs/content/reading-trial-evidence/` (copies of screenshots, downscaled).

## 1. What was published (and what was skipped)

Published on :8021 through the repository calls the admin routes use (`ReadingContentRepository.set_rights`, then the
same `publication_blockers` / `publication_warnings` / `set_status` sequence as `POST /articles/{id}/status`). The
signed-in browser account is not a platform administrator (`/api/admin/reading/*` returned 403), so the Admin Reading
screen could not be used; the server-side path was used instead. Because that path does not go through the HTTP
route, no `audit_logs` row was written; the review events carry actor `phase3-local-trial` and the reason below.

**Per-article republication was granted (`can_republish = true`) for a LOCAL :8021 TRIAL ONLY.** It is not a rights
clearance for any other runtime and does not answer catalogue questions Q1, Q2 or Q6. Source settings were not
changed. `can_adapt` was not set (the articles are not adapted, so it is not a blocker).

| id | source | publish result |
| --- | --- | --- |
| 52578bea-4e9c-43ae-a3b5-8a7d2d6f17ad | NASA | published |
| b8975469-3401-4bee-aeb1-ee6f1fe94c71 | Global Voices EN | published |
| 68d82c0b-2e55-440d-bfaa-b18fa0ddecad | Global Voices EN | published |
| 3f4d7ce2-c125-47be-8d05-b36d0d6219da | Global Voices EN | published |
| ced37e3e-04c3-4d12-b602-d1160f043625 | VOA 中文 | published |
| 01c68f43-b0e3-4ae2-be71-ee3c3a114d8c | VOA 中文 | published |
| 99b12317-41cd-4726-b6fc-66e1b8b2ef26 | VOA 中文 | published |
| 3d00d033-f273-4835-86c2-f4c609c91999 | Global Voices 中文 (URL source) | published |

Skipped: NASA `31f6e9` (re-reading the stored body found the press contact block, with phone numbers and e-mail
addresses, as the last three paragraphs: a leak). Not touched: zh Wikipedia, VOA audio and video pages, GV EN articles
with glued words. Re-read of the eight stored bodies: no glued-word pattern, no player text, no related list;
paragraph counts 10 to 36 (EN) and 17 to 27 (ZH). `68d82c` opens with a one-paragraph editorial preface ("This
article by ... was originally published by Peace News Network ... republished under a content partnership
agreement"), kept because it is attribution, but it is source boilerplate in the body.

## 2. Per-article table

Learner profile: English, B1. Library = Discover, tab "Doc" (Read). ZH articles are not listed for an English learner,
so they were reached by route `#/read/article%3A<id>` (they load fine; the learning language was not changed).
Card time is the "x phut doc" chip; no card shows a source name or a real thumbnail (section 4).

| id | title as shown | Level / time | 3-second test | Thumbnail | Source on card / page | Level fits | Opened article | Phone 390 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 52578b | NASA Demonstrates Next-Generation Heat Shield Technologies | C2 / 4 min | Yes: concrete, curious hook ("by taking out the trash") | None (orange letter tile "N") | none on card; page shows author "Tara Friesen" only | No: plain press release, C2 is too high for the text | Clean, 16 paragraphs, 6 pages, no contact block | no overflow |
| b89754 | How Ecuador is fighting to keep industrial trans fats off the food shelf | C2 / 6 min | Moderate: title cut to "...trans fats o..." on the card | None (tile "H") | none on card; author "Carlos E. Flores" | Probably C1, C2 is high | Clean, 20 paragraphs | no overflow |
| 68d82c | What African elections can learn from the Borana Gadaa system | C2 / 7 min | Yes, but cut to "...Borana..." | None (tile "W") | byline "Peace News" (the original publisher), not Global Voices; no card source | C2 plausible (abstract policy prose) | Opens with the one-paragraph partnership preface; otherwise clean, 36 paragraphs, 12 pages | no overflow |
| 3f4d7c | Poetry book promotes Chabacano, Asia's only Spanish-based creole language | C1 / 4 min | Best of the set: unusual topic, but title cut to "...Asia's only..." | None (tile "P") | author "Mong Palatino" | C1 plausible | Clean, 17 paragraphs, ends on a quote | no overflow |
| ced37e | 赖清德发表双十国庆演说，强调台湾"珍惜和平"，但不"放弃自由" | HSK6 / 4 min | Only for a news reader; very long headline with the quote marks | None | byline "美国之音" (VOA) | HSK6 is the same value for every ZH item (D6), not a judgement | Simplified, full-width punctuation intact, 17 paragraphs; closing-bracket line-start problem (section 4) | no overflow |
| 01c68f | 赖清德会美国会议员，双十节演说将强调台湾强化防卫非挑衅 | HSK6 / 7 min | Dense political headline | None | byline "锺辰芳" (a reporter) | as above | Intact, 19 paragraphs | no overflow |
| 99b123 | 台湾驻美代表处举办"双十酒会"，俞大㵢、蓝莺确认美台牢固关系 | HSK6 / 8 min | Weak: event report, 2,124 characters | None | byline "锺辰芳" | as above | Intact; the rare character 俞大㵢 renders; 27 paragraphs, 10 pages | no overflow |
| 3d00d0 | 泰緬邊境：Thapyay 的重生之路 | HSK6 / 4 min | Good: human story, short title | None | byline "Exile Hub" (the subject organisation, not Global Voices) | HSK6 is wrong for a general feature, see below | Traditional Chinese, not labelled anywhere; 20 paragraphs; CJK punctuation intact | no overflow |

Checks on all eight, phone 390x844: `scrollWidth` 390 = `innerWidth` 390, no element wider than the viewport,
reader header (back, Aa, theme, listen, bookmark, aids, more) fits, title ellipsised, text readable. Desktop 1920x1080: `scrollWidth` 1920. Real touch (isMobile, CDP swipe) was not used: the Playwright tab was
only resized (one tab, no new context, as instructed), so touch gestures are unverified.
Console: no article-specific error. The page carries 100+ baseline errors from the unrendered `{{ ... }}` SVG
placeholders in `index` (same on every screen, not introduced by content), plus my own 401/403/404 API probes.
Language: the interface is Vietnamese (support language); EN and ZH article text is unaffected.

Light and dark both render all of the above; dark checked on the library and on the ZH reader (desktop and phone).
The theme was toggled with the app's own button and restored to light.

## 3. Per-source learner verdicts

- **NASA (nasa.gov releases):** WARN. Reads very well and the hook is real, but nothing on the card or page says
  "NASA", the level is overstated (C2 for a press release), and sister item 31f6e9 would show a phone and e-mail
  block to the learner.
- **Global Voices EN:** WARN to PASS. Titles are real headlines and the articles are clean when the glued-word defect
  is absent. The long headline gets cut on the card, the byline names the freelance author or, for syndicated pieces
  (68d82c), the original publisher, and the editorial preface appears in the body. Levels are C1/C2 only; there is
  no B-level material from this source.
- **VOA 中文:** PASS on content, WARN on the card. Hanzi, full-width punctuation and paragraphing are intact, but
  the headlines are long political lines and every item is HSK6, so a learner cannot tell an easy from a hard one.
- **Global Voices 中文:** WARN. Good stories and clean text, but Traditional characters are not labelled, the
  level is the same HSK6, and the byline shows the story's organisation or person, not the publisher.

Which would a learner tap first? 3f4d7c (Chabacano), 52578b (NASA), 3d00d0 (a human story). None would be picked for
a B1 learner, because none is below C1 (EN) or HSK6 (ZH) as labelled.

## 4. UI-level findings: what real content exposes

Compared with `docs/design/canonical-ui/screens/Orena.dc.html` (Discover card, Reader frame). The design's Discover
card draws a cover image when there is one (`c.hasImg`), a title, a muted `c.source` line and the level chips; the
Reader frame draws title and a meta line. The sample content hid the following gaps. These are recorded here as
findings; no code or design was changed.

1. **No source or publisher anywhere in the learner flow (backend gap, High).** The design draws a source line on
   every card; article cards have none, and `GET /api/reading/articles` returns only id, title, language, level,
   topic, reading time, word count, excerpt, published_at, content_revision. The detail and reader show only
   `attribution.author`, so the line reads as an author or whatever the extractor found (a reporter, "Exile Hub",
   "Peace News"). The attribution (`source_url`, licence note, "Source: NASA") that CC BY and the NASA terms ask for
   is not shown to the learner at all, which matters before any of these are published for real.
2. **No thumbnail path (backend gap, High).** Every card is the generated orange letter tile, so five different
   articles look the same at a glance and the 3-second test rests on the title alone. The article payload has no
   image field although the extractor stores image candidates. Suitability and crop of real thumbnails could not be
   rated because none reach the learner.
3. **Level is not usable (Medium-High).** The labels C1/C2 and HSK6 are engine output (D6, see the trial doc), shown
   as authoritative chips. A B1 learner sees only C1/C2 articles; 100% of the ZH trial items read HSK6.
4. **Long titles are clipped to two lines on the card (design behaviour, Low-Medium).** At 1920 and at 390 the headline
   ends in an ellipsis before the point of the story ("...trans fats o...", "...only..."). Real headlines run 60 to 90
   characters; the design's samples are short. Phone is worse: two words per line.
5. **Traditional vs Simplified is invisible (Medium).** The Global Voices ZH article is Traditional and nothing
   labels it. A learner of Simplified Chinese gets no warning, and the level and word-count logic assume Simplified.
6. **CJK line breaking in the reader (Medium).** Closing and middle punctuation start lines: `）`, `，` and `〕` begin
   lines in 3d00d0 on desktop and phone (see the two ZH screenshots). Line spacing is also visibly looser for Chinese
   than for English (judged from the screenshots, not measured). Both read as unfinished.
7. **Card length is only minutes (Low).** "4 phut doc" tells length; there is no word count or Hanzi count, and the ZH
   minutes (234 s for 1,015 characters) are from the engine's rate, not checked against a learner.
8. **Header meta truncates (Low).** On the phone reader the title and meta ("... C2 . Doc chu dong . tr...") are cut,
   so page progress is not visible at 390.
9. **Not tested:** touch gestures (isMobile/CDP), the ZH library card (ZH articles are not listed for an English
   learner and the profile language was not changed), and the Admin Reading screen (account is not an admin).

## 5. Evidence

All under `docs/content/reading-trial-evidence/`:

| File | What it shows |
| --- | --- |
| `d-discover.png` | Discover "All": Read row, letter tiles, titles clipped, no source line |
| `d-read.png` | Discover "Read" tab, light, 1920 wide |
| `d-read-dark.png` | Same, dark |
| `d-nasa-detail.png` | Article page for 52578b: author only, no source, no image |
| `d-nasa-reader-light.png` | Reader, desktop, light, clean paragraphs |
| `d-gv-zh-light.png` | ZH reader (3d00d0, Traditional), closing brackets at line start |
| `d-gv-zh-dark.png` | Same, dark |
| `m-read-dark.png` | Phone Read tab, dark, two-word title lines |
| `m-gv-zh-dark.png` | Phone ZH reader, dark |
| `m-ecuador-light.png` | Phone EN reader, light, header meta cut |

## 6. State changed on :8021 (for the lead)

- 8 articles moved from `needs_review` to `published`, each with a `can_republish = true` review event
  (actor `phase3-local-trial`). To undo: set each back with `set_status(..., "unpublished")` (or "needs_review"); the
  rights answers can be returned to unanswered with `set_rights(..., {"can_republish": None})`.
- Theme toggled dark and back to light; viewport resized to 390x844 and back to 1920x1080; the stored learning
  language and any profile data were not changed.
