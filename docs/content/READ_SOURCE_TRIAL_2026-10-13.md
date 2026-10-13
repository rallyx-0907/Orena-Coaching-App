# Reading source trial, 2026-10-13 (Phase 2)

Branch `claude/reading-source-quality`. Real articles from the Phase 1 shortlist were put through the existing
pipeline on the local test runtime :8021 (engine at main 948fd871, not modified; no engine code changed in this
branch). Every field below was judged from the stored `reading_articles` / `reading_source_items` rows, not from job
status. Local execution only; no CI evidence is claimed.

## 1. What was run

- Sources were created and activated through `ReadingContentRepository` inside `orena-next-verify-web` (the same
  repository calls `POST /api/admin/reading/sources` makes), URLs were submitted with `ReadingContentEngine.submit`
  (the `POST /jobs` path) and feeds were polled with `ReadingSourcePoller.poll_source` (the one-shot
  `python -m writing_coach.reading_source_poller` code path, constructed with `max_entries=10` so no feed queued more
  than 10 items). The :8021 worker then fetched, extracted and analysed every job.
- **How auto-publish was blocked.** `reading_admission.automatic_admission` publishes only if every reason list is
  empty; one of its reasons is `rights_not_cleared` (`policy.can_republish is not True`). Every trial source is
  `active` but has `can_republish = false` and `can_adapt = false`. Feed sources keep `automation_allowed = true`
  (the poller's eligibility rule needs it); URL-list sources have `automation_allowed = false`, which adds
  `automation_not_allowed`. Reason for `can_republish = false`: the catalogue's open questions Q1 (third-party
  media inside an open-licensed article), Q2 (ShareAlike) and Q6 (VOA wire copy) are unanswered, so a human has not
  cleared republication. The licence text, attribution and URL are stored truthfully in each source's `license_note`.
  `attribution_required = true` everywhere. The NASA QA source already used the same setting.
- **Verified result: 0 trial articles are published.** `select count(*) ... where status='published' or
  published_at is not null` over the trial and NASA sources returned 0; all 57 trial and NASA articles are
  `needs_review`, and every one carries `analysis.admission.decision = "review"`. (The 53 published articles in the
  runtime belong to earlier sample sources and were not touched.)

### Counts

| Source | Submitted | Extracted (job completed) | needs_review | Failed |
| --- | --- | --- | --- | --- |
| NASA (existing QA source, RSS) | 23 jobs over its life (feed items, retries) | 8 articles | 8 | 14 failed jobs in history, none open (see 3.1) |
| Global Voices EN (RSS) | 10 (first 10 of 15 feed items) | 10 | 10 | 0 |
| VOA Learning English (URL list) | 8 submissions, 7 unique | 7 (6 text + 1 audio page) | 7 | 0 |
| zh Wikipedia featured, feed path | 10 | 10 | 10 | 0 |
| zh Wikipedia featured, direct article URLs | 5 | 5 | 5 | 0 |
| VOA 中文 (URL list, VOA-produced only) | 6 | 6 | 6 | 0 |
| Global Voices 中文 (RSS) | 10 (the whole feed) | 10 | 10 | 0 |
| Global Voices 中文 (URL list, overlap probe) | 1 | 1 | 1 | 0 |

No job failed, which is itself a finding: 4 pages that are not readable articles were accepted as candidates
(section 3, D10).

### Column key for the tables

`T` title, `A` author, `D` published date, `B` body completeness against the live page, `P` paragraph boundaries,
`L` leakage (navigation, ads, captions, related, boilerplate), `G` language detection (all PASS: `en`/`zh` correct,
confidence 0.78 to 1.0, no `language_mismatch`), `V` level plausibility, `X` targets, `C` canonical URL, `I`
image candidate, `R` rights and attribution snapshot on the item, `E` extraction confidence calibrated, then the
confidence value, the engine's word or Hanzi count, the estimated level. Cells run in the order
`T A D B P L G V X C I R E`; each is P (pass), W (warn) or F (fail). Completeness was measured by fetching each live
page and checking every live paragraph of at least 60 characters (25 for ZH) against the stored body: no article lost
a main-text paragraph; the misses were donation banners, photo captions and bylines, which is correct removal.
Glued-word counts compare every stored word with the live page's word list.

## 2. Per-source results

### 2.1 NASA (EN, RSS `https://www.nasa.gov/news-release/feed/`, existing source `qa-nasa-news-rss`)

Verdict: **WARN, usable.** Body, paragraphs, title, date, image and language are good. Three `science.nasa.gov`
items lost their rights snapshot; every item is rated C1/C2; press releases keep their contact block.

| id | title | T A D B P L G V X C I R E | conf | units | level | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 52578b | NASA Demonstrates Next-Generation Heat S | P P P P P P P W F P P P P | high | 745 | C2 | C2 conf 1.0 for news register; 3 fragment targets: at nasa, developed at, generation of |
| a74d9d | NASA’s SpaceX CRS-35 Mission to Launch H | P P P P P P P W F P P F P | high | 500 | C2 | C2 conf 1.0 for news register; 3 fragment targets: the human brain, the space station, on earth; rights not inherited (source_origin_mismatch), snapshot empty, attribution_unknown |
| 405ff2 | NASA to Conduct Flyover, Engage NFL Fans | P W P P P W P P W P P P P | high | 248 | C1 | no author; leakage: press contact block; fragment targets: the agency’s, the game |
| 3e9dc4 | NASA Seeks US Industry Plans for Commerc | P W P P P W P W F P P P P | high | 420 | C2 | no author; leakage: press contact block; C2 conf 1.0 for news register; 3 fragment targets: in low earth, the agency’s, on the agency’s |
| e0df89 | Antarctic Sea Ice Grows to Its 2026 Maxi | P P P P P W P P F P P F P | high | 553 | C1 | leakage: reference list; editorial preface; 3 fragment targets: accessed october, and ice data, national snow and; rights not inherited (source_origin_mismatch), snapshot empty, attribution_unknown |
| f0e395 | An Impact Structure With Legs | P P P P W W P P F P P F P | high | 382 | C1 | 2 glued word(s): theOctober, theU; leakage: reference list; editorial preface; 5 fragment targets: image of the, of the crater, accessed october; rights not inherited (source_origin_mismatch), snapshot empty, attribution_unknown |
| 31f6e9 | NASA Science, Cargo Launch on 35th Space | P W P P P W P W F P P P P | high | 407 | C2 | no author; leakage: press contact block; C2 conf 1.0 for news register; 5 fragment targets: the space, earth and, research and |
| a1eaeb | NASA JPL Testing Readies Voyager Technol | P W P P P W P W F P P P P | high | 671 | C2 | author is CMS username albarne1; leakage: press contact block; C2 conf 1.0 for news register; 4 fragment targets: the moon, the lunar, the moon base |

Existing items reported as found: 8 articles, all `needs_review`. Extra evidence: four APOD "image of the day" pages
were refused with `There is no readable article in this page` (correct); ten earlier jobs failed with `This text is
longer than the engine accepts` for ordinary 400 to 750 word releases (the same URLs now exist as articles; cause not
reproduced, history only). Rights: `nasa.gov` items inherit the source's licence note; `science.nasa.gov` items do
not (D8).

### 2.2 Global Voices EN (RSS `https://globalvoices.org/feed/`)

Verdict: **WARN, not ready for learners until D1 is fixed.** Title, byline, date, thumbnail, rights (CC BY 3.0 text
inherited and stored) and paragraphing are right and the full body is present in every article, but 7 of 10 articles
contain words glued together by the extractor (7 of 10 have at least one, 5 have five or more, up to 42 in one article).

| id | title | T A D B P L G V X C I R E | conf | units | level | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| b89754 | How Ecuador is fighting to keep industri | P P P P P P P W W P P P P | high | 1097 | C2 | C2 conf 1.0 for news register; fragment targets: fats and, on september |
| 6b06ec | Subsea cables and oil pipelines: The inf | P P P P F W P W F P P P P | high | 991 | C2 | 28 glued words from lost inline whitespace (e.g. Abbasspoketo); leakage: editorial preface; author bio; C2 conf 1.0 for news register; 3 fragment targets: in the gulf, and microsoft, and oil |
| 67dec6 | Trump’s ‘Agreements on Reciprocal Trade’ | P P P P W W P W W P P P P | high | 1268 | C2 | 4 glued word(s): Reports, alsopart; leakage: editorial preface; C2 conf 1.0 for news register; fragment targets: the u, access to |
| ad3bae | Bangladesh-Malaysia recruitment reforms  | P P P P F P P W W P P P P | high | 1644 | C2 | 5 glued words from lost inline whitespace (e.g. agreementin); C2 conf 1.0 for news register; fragment targets: approximately usd, costs and |
| 676965 | El Niño speeds climate crisis and tests  | P P P P W W P W F P P P P | high | 1215 | C2 | 1 glued word(s): neveranything; leakage: editorial preface; C2 conf 1.0 for news register; 5 fragment targets: el ni, the world, of food |
| a4dd5a | Africa’s governments already treat the i | P P P P F W P P F P P P P | high | 1609 | C1 | 42 glued words from lost inline whitespace (e.g. Africasince); leakage: editorial preface; author bio; 6 fragment targets: right to, the right, the right to |
| 68d82c | What African elections can learn from th | P P P P P W P W W P P P P | high | 1199 | C2 | leakage: editorial preface; C2 conf 1.0 for news register; fragment targets: the borana, the borana gadaa |
| 9e51fb | When free speech has a price: Youth voic | P P P P F P P W F P P P P | high | 828 | C2 | 13 glued words from lost inline whitespace (e.g. Azagaiaobserved); C2 conf 1.0 for news register; 5 fragment targets: in public, the right, in mozambique |
| b6ff73 | Alibaba sues Pentagon to denounce being  | P P P P F W P W F P P P P | high | 1362 | C2 | 12 glued words from lost inline whitespace (e.g. Councilof); leakage: editorial preface; C2 conf 1.0 for news register; 3 fragment targets: the chinese, the dod, the u |
| 3f4d7c | Poetry book promotes Chabacano, Asia’s o | P P P P P P P P F P P P P | high | 678 | C1 | 3 fragment targets: city of, in zamboanga, the book |

### 2.3 VOA Learning English (URL list, 7 pages)

Verdict: **WARN on text pages, FAIL on the audio page.** Text is complete, but every text page begins with the
player placeholder "No media source currently available", the "Words in This Story" glossary stays in the body of one page and is gone from three others, one body keeps an AFP
"reported this story for Agence France-Presse" credit line (four others had theirs stripped, so the handling is
inconsistent), and the level is wrong for a learner-English source.

| id | title | T A D B P L G V X C I R E | conf | units | level | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 946e67 | Wilbur and Orville Wright: The First Air | P P P P W F P F F P W P P | high | 474 | B2 | 1 glued word(s): glidersat; leakage: player placeholder text; glossary block; level B2 but source is A2-B1 controlled English; 4 fragment targets: the wright brothers, and orville wright, in the air; candidates include a shared logo and player-spinner.png |
| ed4203 | Methods for Protecting Earth against an  | P P P P W F P F F P W P P | high | 649 | C1 | 1 glued word(s): slowlychange; leakage: player placeholder text; wire credit line in body; level C1 but source is A2-B1 controlled English; 6 fragment targets: the asteroid, a spacecraft, an asteroid; candidates include a shared logo and player-spinner.png |
| 912e8a | Total Lunar Eclipse to Turn Moon Red | P P P P P F P F F P W P P | high | 441 | B2 | leakage: player placeholder text; level B2 but source is A2-B1 controlled English; 6 fragment targets: the moon, the sun, a total lunar; candidates include a shared logo and player-spinner.png |
| f0378d | Study Shows How Earth’s Orbit Affects Ic | P P P P P F P F F P W P P | high | 460 | C1 | leakage: player placeholder text; level C1 but source is A2-B1 controlled English; 3 fragment targets: changes in, in earth’s orbit, the earth’s; candidates include a shared logo and player-spinner.png |
| 167399 | How Physical Therapists Can Prevent Futu | P P P P W F P F W P W P P | high | 785 | C1 | 2 glued word(s): confidenceand, moreinclined; leakage: player placeholder text; level C1 but source is A2-B1 controlled English; fragment targets: of falling; candidates include a shared logo and player-spinner.png |
| 6cf7ab | A Short History of Spacecraft Landings o | P P P P P F P F F P W P P | high | 540 | B2 | leakage: player placeholder text; level B2 but source is A2-B1 controlled English; 7 fragment targets: the moon, on the moon, the lunar; candidates include a shared logo and player-spinner.png |
| c8ab6d | Barbara McClintock, Geneticist and Nobel | W W P F P F P F P P W P P | low | 7 | C1 | audio/video page, title only; no author; 7 words: Accessibility links / No media source currently available; leakage: player placeholder text; level C1 but source is A2-B1 controlled English; candidates include a shared logo and player-spinner.png |

Dedupe: the ice-age URL `study-shows-how-earth-s-orbit-affects-ice-ages/7997495.html` was submitted twice;
the second submission returned the same job id with `duplicate = true`, so 8 submissions produced 7 jobs. The
audio-only page `/a/8010810.html` was not rejected: it became an article of 7 words ("Accessibility links / No media
source currently available") flagged `too_short` and `extraction_low_confidence`, waiting in the queue.

### 2.4 zh Wikipedia featured: feed path

Verdict: **FAIL.** 10 of 10 feed items resolve to `Special:FeedItem` pages, not articles. The poller stored a 120 to
190 character lead with a generic title.

| id | title | T A D B P L G V X C I R E | conf | units | level | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 8d1d07 | 维基百科2026年10月5日典范条目 | F W P F P P P W P F F P P | low | 149 | HSK6 | title is a generic feed label, not the article; no author; wrong page, only the ~150-char feed lead stored; HSK6 conf 1.0 (same for all ZH items); canonical is Special:FeedItem, not the article; no image candidate |
| ad2109 | 维基百科2026年10月9日典范条目 | F W P F P P P W P F W P P | low | 165 | HSK6 | title is a generic feed label, not the article; no author; wrong page, only the ~150-char feed lead stored; HSK6 conf 1.0 (same for all ZH items); canonical is Special:FeedItem, not the article; only a feed thumbnail |
| b4c57e | 维基百科2026年10月8日典范条目 | F W P F P P P W P F W P P | low | 149 | HSK6 | title is a generic feed label, not the article; no author; wrong page, only the ~150-char feed lead stored; HSK6 conf 1.0 (same for all ZH items); canonical is Special:FeedItem, not the article; only a feed thumbnail |
| be7f2e | 维基百科2026年10月13日典范条目 | F W P F P P P W P F W P P | low | 119 | HSK6 | title is a generic feed label, not the article; no author; wrong page, only the ~150-char feed lead stored; HSK6 conf 1.0 (same for all ZH items); canonical is Special:FeedItem, not the article; only a feed thumbnail |
| 2513f7 | 维基百科2026年10月12日典范条目 | F W P F P P P W P F W P P | low | 179 | HSK6 | title is a generic feed label, not the article; no author; wrong page, only the ~150-char feed lead stored; HSK6 conf 1.0 (same for all ZH items); canonical is Special:FeedItem, not the article; only a feed thumbnail |
| 0fc093 | 维基百科2026年10月7日典范条目 | F W P F P P P W P F W P P | low | 149 | HSK6 | title is a generic feed label, not the article; no author; wrong page, only the ~150-char feed lead stored; HSK6 conf 1.0 (same for all ZH items); canonical is Special:FeedItem, not the article; only a feed thumbnail |
| b8c45c | 维基百科2026年10月4日典范条目 | F W P F P P P W P F W P P | low | 175 | HSK6 | title is a generic feed label, not the article; no author; wrong page, only the ~150-char feed lead stored; HSK6 conf 1.0 (same for all ZH items); canonical is Special:FeedItem, not the article; only a feed thumbnail |
| 9b1557 | 维基百科2026年10月6日典范条目 | F W P F P P P W P F W P P | low | 174 | HSK6 | title is a generic feed label, not the article; no author; wrong page, only the ~150-char feed lead stored; HSK6 conf 1.0 (same for all ZH items); canonical is Special:FeedItem, not the article; only a feed thumbnail |
| 141aed | 维基百科2026年10月11日典范条目 | F W P F P P P W P F W P P | low | 186 | HSK6 | title is a generic feed label, not the article; no author; wrong page, only the ~150-char feed lead stored; HSK6 conf 1.0 (same for all ZH items); canonical is Special:FeedItem, not the article; only a feed thumbnail |
| e0739a | 维基百科2026年10月10日典范条目 | F W P F P P P W P F W P P | low | 149 | HSK6 | title is a generic feed label, not the article; no author; wrong page, only the ~150-char feed lead stored; HSK6 conf 1.0 (same for all ZH items); canonical is Special:FeedItem, not the article; only a feed thumbnail |

### 2.5 zh Wikipedia featured: direct article URLs (5)

Verdict: **FAIL as a learner article, WARN as a source.** Extraction is accurate, but a whole encyclopedia page
(3,273 to 18,496 units, four of five flagged `too_long`) with the wrong title, the infobox flattened into the first lines
and the reference list kept.

| id | title | T A D B P L G V X C I R E | conf | units | level | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| d6fb68 | 生物体从环境中摄取营养物转变为自身物质，同时将自身原有组成部分转变为废物（而后排 | F P W W P W P W F P P P P | high | 10926 | HSK6 | title is the Wikidata description (JSON-LD headline); date = page creation datePublished; whole encyclopedia page incl. infobox, [n] markers, references; leakage: infobox, [n] markers, references, external links; HSK6 conf 1.0 (same for all ZH items); targets include citation boilerplate 原始内容/内容存档; too_long flag (10926 units) |
| 3bc7cd | 2020年發生於墨西哥的一場強烈地震 | F P W W P W P W F P P P P | high | 3273 | HSK6 | title is the Wikidata description (JSON-LD headline); date = page creation datePublished; whole encyclopedia page incl. infobox, [n] markers, references; leakage: infobox, [n] markers, references, external links; HSK6 conf 1.0 (same for all ZH items); targets include citation boilerplate 原始内容/内容存档 |
| e07340 | 由任天堂於2008年推出的掌上遊戲機 | F P W W P W P W F P P P P | high | 9141 | HSK6 | title is the Wikidata description (JSON-LD headline); date = page creation datePublished; whole encyclopedia page incl. infobox, [n] markers, references; leakage: infobox, [n] markers, references, external links; HSK6 conf 1.0 (same for all ZH items); targets include citation boilerplate 原始内容/内容存档; too_long flag (9141 units) |
| ae38fd | 肯塔基州第9任州长 | F P W W P W P W F P P P P | high | 9374 | HSK6 | title is the Wikidata description (JSON-LD headline); date = page creation datePublished; whole encyclopedia page incl. infobox, [n] markers, references; leakage: infobox, [n] markers, references, external links; HSK6 conf 1.0 (same for all ZH items); targets include citation boilerplate 原始内容/内容存档; too_long flag (9374 units) |
| fff911 | 野蛮人柯南 (1982年电影) - 维基百科，自由的百科全书 | W P W W P W P W F W P P P | high | 18496 | HSK6 | title carries the site suffix; date = page creation datePublished; whole encyclopedia page incl. infobox, [n] markers, references; leakage: infobox, [n] markers, references, external links; HSK6 conf 1.0 (same for all ZH items); targets include citation boilerplate 原始内容/内容存档; canonical re-encodes parentheses as %28; too_long flag (18496 units) |

The page for 代谢 mixes scripts inside one body ("代謝（英語：metabolism）又稱新陳代謝、代谢反应"), and 任天堂DSi is served
almost entirely in Traditional characters (475 Traditional-only against 21 Simplified-only markers), while the other
four are Simplified. All five are labelled plain `zh`.

### 2.6 VOA 中文 (URL list, 6 VOA-produced pages; wire-credited items were deliberately not submitted)

Verdict: **PASS on 3 of 6, WARN or FAIL on the others.** The three full reports are the cleanest ZH extractions in
the trial. The single-`<p>` report loses all paragraphing; the two video or audio pages are not articles.

| id | title | T A D B P L G V X C I R E | conf | units | level | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 86b5c0 | 分析人士：细节是俄乌能源停火协议的关键 | P P P P F P P W P P P P P | low | 983 | HSK6 | double <br> breaks flattened to one paragraph; HSK6 conf 1.0 (same for all ZH items) |
| ced37e | 赖清德发表双十国庆演说，强调台湾“珍惜和平”，但不“放弃自由” | P P P P P P P W P P P P P | high | 1015 | HSK6 | HSK6 conf 1.0 (same for all ZH items) |
| 01c68f | 赖清德会美国会议员，双十节演说将强调台湾强化防卫非挑衅 | P P P P P P P W P P P P P | high | 1831 | HSK6 | HSK6 conf 1.0 (same for all ZH items) |
| 99b123 | 台湾驻美代表处举办“双十酒会”，俞大㵢、蓝莺确认美台牢固关系 | P P P P P P P W P P P P P | high | 2124 | HSK6 | HSK6 conf 1.0 (same for all ZH items) |
| d829dd | 历史学者潘东凯：卢比奥雅典演说“项庄舞剑、意在沛公” 以西方文明抗衡共产主义 | P P P F P F P W P P P P W | medium | 240 | HSK6 | video page: 245 units, lead sentence duplicated, then related-link list; leakage: player placeholder text; related-content list; HSK6 conf 1.0 (same for all ZH items); confidence medium on a page with no article |
| a646fe | 原声带：慕容雪村｜铁幕徐徐落下 中国人还能怎么办？ | P P P W F P P W P P P P P | low | 216 | HSK6 | audio/video blurb only, 264 chars; double <br> breaks flattened to one paragraph; HSK6 conf 1.0 (same for all ZH items) |

Chinese checks on this source: Hanzi and full-width punctuation intact, no U+FFFD, no stray space between Hanzi (0
occurrences); names such as 俞大㵢 survive. The only spaces in the bodies are the sentence separators produced by the
flattened `<br><br>` paragraphs (20 in the first report).

### 2.7 Global Voices 中文 (RSS `https://zh.globalvoices.org/feed/`, Traditional script)

Verdict: **PASS on content, FAIL on rights inheritance, WARN on level and script labelling.** All ten bodies are
complete, correctly paragraphed Traditional text with no mojibake and no stray Hanzi-Hanzi spaces. The feed's items
live on `zht.globalvoices.org` while the source's origin is `zh.globalvoices.org`, so no item inherited the source's
licence or attribution; the same article through a source whose origin is `zht.` did (compare the last row of 2.8).

| id | title | T A D B P L G V X C I R E | conf | units | level | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 5c5837 | 歡迎參加「臺灣原住民語言的數位推動」 | P P P P P P P W P P P F P | high | 956 | HSK6 | HSK6 conf 1.0 (same for all ZH items); rights not inherited (source_origin_mismatch), snapshot empty, attribution_unknown |
| 643d74 | 請多多支持全球之聲的募款活動！ | P P P P P P P W P P P F P | high | 1044 | HSK6 | HSK6 conf 1.0 (same for all ZH items); rights not inherited (source_origin_mismatch), snapshot empty, attribution_unknown |
| 204d65 | 前進倫敦書展：讓世界看見南亞 | P P P P P P P W P P P F P | high | 2190 | HSK6 | HSK6 conf 1.0 (same for all ZH items); rights not inherited (source_origin_mismatch), snapshot empty, attribution_unknown |
| c45e25 | 泰緬邊境：Thapyay 的重生之路 | P P P P P P P W P P P F P | high | 972 | HSK6 | HSK6 conf 1.0 (same for all ZH items); rights not inherited (source_origin_mismatch), snapshot empty, attribution_unknown |
| e8d67f | 別再誤會太極拳了：孫佩強大師揭祕「以柔克剛」的真正意涵 | P P P P P P P W P P P F P | high | 3314 | HSK6 | HSK6 conf 1.0 (same for all ZH items); rights not inherited (source_origin_mismatch), snapshot empty, attribution_unknown |
| d9663f | 阿美族語數位工作者 Omah Canglah──族語也可以很現代！ | P P P P P P P W P P P F P | high | 1586 | HSK6 | HSK6 conf 1.0 (same for all ZH items); rights not inherited (source_origin_mismatch), snapshot empty, attribution_unknown |
| 62a5f2 | 委內瑞拉：陌生而令人恐懼的聲響 | P P P P P P P W P P P F P | high | 1693 | HSK6 | HSK6 conf 1.0 (same for all ZH items); rights not inherited (source_origin_mismatch), snapshot empty, attribution_unknown |
| 88a3c5 | 泰雅族語數位工作者呂仲安／Pasang Teru──小而持續的努力才會累積成改變 | P P P P P P P W P P P F P | high | 1297 | HSK6 | HSK6 conf 1.0 (same for all ZH items); rights not inherited (source_origin_mismatch), snapshot empty, attribution_unknown |
| 3220fc | 泰雅族語數位工作者楊宬律／Tapas Katu──使用族語是很正常的事 | P P P P P P P W P P P F P | high | 1893 | HSK6 | HSK6 conf 1.0 (same for all ZH items); rights not inherited (source_origin_mismatch), snapshot empty, attribution_unknown |
| e9b4a5 | 賽德克族語數位工作者藍若水／Sayun Pihaw──要探討如何打開視角、擴大理 | P P P P P P P W P P P F P | high | 1193 | HSK6 | HSK6 conf 1.0 (same for all ZH items); rights not inherited (source_origin_mismatch), snapshot empty, attribution_unknown |

Script handling: `language = zh` for every item with `detected_language_confidence` 0.86 to 1.0; nothing records
that the text is Traditional (no script or variant field in the item metadata or analysis), and the level is HSK6
with confidence 1.0 for all ten, including a plain event invitation. Publisher typography is preserved as is, e.g.
"2026 年一月三日", "370 萬人" (spaces between Hanzi and digits or Latin); that is the source's text, not damage.

### 2.8 Global Voices 中文, URL list (overlap probe)

| id | title | T A D B P L G V X C I R E | conf | units | level | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 3d00d0 | 泰緬邊境：Thapyay 的重生之路 | P P P P P P P W P P P P P | high | 972 | HSK6 | HSK6 conf 1.0 (same for all ZH items) |

Overlap: `zht.globalvoices.org/2026/04/14/37270` arrived through both the feed source and this URL source. Dedupe is per
source, so there are two articles (`c45e25` and `3d00d0`) with identical bodies; this is the designed behaviour (the
preview lists the same bytes under another source via `find_duplicate_content`), not a defect, but the two rows
differ in rights state: the URL-source copy has the licence and attribution, the feed copy has none.

### Dedupe summary

| Check | Result |
| --- | --- |
| Same URL submitted twice | PASS: second call returned the first job (`duplicate = true`) |
| Re-polling each feed after ingestion | PASS: queued 0, skipped 10 for all three feeds, no second article |
| Same article via feed and via URL source | PASS by design: separate source, separate article, same content hash |
| Feed canonical vs real article (Wikipedia) | not deduped: feed points at `Special:FeedItem`, a different page (D3) |

## 3. Pipeline defects found with real sources

Severity: High (corrupts learner text or blocks a shortlisted source), Medium (wrong or missing metadata a reviewer
must fix), Low (cosmetic or noisy). File:line refer to main 948fd871.

| # | Defect | Source and URL | Observed | Likely location | Sev |
| --- | --- | --- | --- | --- | --- |
| D1 | Whitespace at an inline element boundary is dropped, gluing words | Global Voices EN `globalvoices.org/2026/10/09/trumps-agreements-on-reciprocal-trade-arts-threaten-equitable-access-to-the-internet-in-global-south/`; also `.../2026/10/09/subsea-cables-and-oil-pipelines-...` (28 words), `.../2026/10/07/africas-governments-...` (42), VOA LE `.../asteroid-strike/7989189.html` | Live HTML `first </em><a><em>published</em></a><em> by`; stored "was firstpublishedby EngageMedia", "agreement.It is alsopart"; 11 of 25 EN articles affected (7 of 10 GV EN, 3 of 6 VOA LE text pages, 1 of 8 NASA) | `reading_article_extraction.py:154-165` (`_text` strips every inline node's text at line 163, so the space inside `<em>first </em>` is lost before the parent joins children); same stripped value feeds `_collect` at :424 | High |
| D2 | Consecutive `<br><br>` is not a paragraph break | VOA 中文 `voachinese.com/a/analysts-say-details-are-key-to-any-russia-ukraine-energy-ceasefires-20261012/8210454.html`; also `.../roll-on-the-tape-murongxuecun-20261010/8210016.html` | Live source is one `<p>` with `<br /><br />` between paragraphs; stored as one 1,233 character paragraph with sentences separated by single spaces (20 of them), confidence `low` | `reading_article_extraction.py:158-159` (`br` becomes `" "`), `_collect` :407-432 | High for ZH news (VOA 中文 uses this pattern) |
| D3 | Wikipedia featured feeds queue the wrong page | `zh.wikipedia.org/w/api.php?action=featuredfeed&feed=featured&feedformat=atom`, e.g. `https://zh.wikipedia.org/wiki/Special:FeedItem/featured/20261005000000/zh` | 10 of 10 items stored as 120-190 character leads titled "维基百科2026年10月5日典范条目", canonical is the FeedItem URL, confidence `low` | `reading_source_poller.py:101` (`parse_feed`: `link = alternate or _text(children.get("link"))`) takes the entry link only; the real article URL is inside the summary HTML | High (blocks the shortlisted ZH-1 and EN-6 as polled sources) |
| D4 | Title taken from JSON-LD `headline`, which Wikipedia fills with the Wikidata description | `https://zh.wikipedia.org/wiki/代谢` ("生物体从环境中摄取营养物转变为自身物质，…") and 3 more; `.../野蛮人柯南_(1982年电影)` kept the `<title>` suffix " - 维基百科，自由的百科全书" | 4 of 5 wiki articles have a sentence-long description as title; live `<title>` is "代谢 - 维基百科，自由的百科全书" | `reading_article_extraction.py:565` (`ld["headline"] or og_title or h1 or title`), JSON-LD read at :283 | High for Wikipedia |
| D5 | Encyclopedia pages keep infobox, `[n]` markers, reference list and external links; those leak into targets | the five `zh.wikipedia.org` articles | Body starts with infobox key/value lines; ends with "^ 28.0 28.1 ... （原始内容存档于…）"; targets include 原始内容 and 内容存档 in 4 of 5 | `reading_article_extraction.py` `_clean_blocks` :494-518 (no section or reference awareness); `reading_processing.py:444-470` | Medium |
| D6 | Level is saturated and its confidence is a length proxy | all 32 ZH items HSK6 (VOA 中文, GV 中文, Wikipedia); EN: 13 of 18 NASA and GV EN items C2; VOA LE (A2-B1 by design) rated B2 x3 and C1 x4 | no ZH item below HSK6; confidence 1.0 for any text over 400 units | `reading_processing.py:101` (`_ZH_COMMON` is 39 Simplified characters, so almost every character of a natural text counts as uncommon), :309-316 (score saturates), :329 (confidence = f(word_count) only) | High (level filters are learner-facing) |
| D7 | Target suggestion splits on non-ASCII letters and accepts stopword fragments | GV EN `.../el-nino-speeds-climate-crisis-...` ("el ni"), `.../alibaba-sues-pentagon-...` ("the u"), `.../how-ecuador-...` ("fats and", "on september") | 88 of 198 EN targets begin or end with a function word, e.g. "approximately usd", "costs and", "accessed october" | `reading_processing.py:70` (`_EN_WORD` is ASCII-only, splits "Niño" and "U.S."), :369-383 (a phrase passes if any one word is uncommon) | Medium |
| D8 | Rights snapshot is lost when the item host differs from the source's `base_url` host | NASA `science.nasa.gov/missions/station/nasas-spacex-crs-35-mission-to-launch-health-research/` and 2 Earth Observatory pages; all 10 GV 中文 feed items (`zht.` vs `zh.`) | `rights_known = false`, snapshot `{}`, reasons `attribution_unknown`, `source_origin_mismatch`; the preview then shows no licence or credit | `reading_admission.py:20-34` (`source_origin_matches`), applied at `reading_content_engine.py:268` where rights are inherited | Medium (fails safe, but hides the licence the reviewer needs) |
| D9 | Media-player and related-content text is extracted as article text | VOA LE (all 6 text pages start "No media source currently available"); VOA 中文 `.../london-historian-gordon-poon-rubio-s-greece-speech-was-using-western-civilization-to-counter-cult-of-death-and-communism-20261007/8208887.html` ("美国之音 / 没有媒体可用资源 ... 相关内容 ... list") | placeholder as first body line in 6 of 6 text pages; related headlines as body; AFP credit line kept in 1 body and stripped from 4 others | `reading_article_extraction.py:56-62` token list has `player` but the placeholder sits in an unclassed element; `_edge_attribution` :480-492 handles only some credit shapes | Medium |
| D10 | Non-articles enter the review queue; only some are flagged | VOA LE audio page `learningenglish.voanews.com/a/8010810.html` (7 words, flagged); VOA 中文 `.../8208887.html` (245 units, confidence `medium`, `quality_issues = []`, no flag at all) | job completes `article_created`; publication gate checks rights only | `reading_content_engine.py:373-381` (issues attached, never refuse), `reading_admin_api.py:191-217` (`publication_blockers` ignores quality) | Medium |
| D11 | Editorial prefaces, author bios and reference lists kept as body | GV EN (6 of 10 start with a preface such as "This post is part of Global Voices' ... Spotlight series", 2 end with an author bio); NASA releases (contact block with phones and emails, 4 of 8); Earth Observatory ("Accessed October 8, 2026" list) | present in stored body | `reading_article_extraction.py:480-518` | Low |
| D12 | Author field can be a CMS username | NASA `.../nasa-jpl-testing-readies-voyager-technologies-lander-for-moon-mission/` | author "albarne1" | `reading_article_extraction.py:256-281`, `_page_metadata` :313 | Low |
| D13 | Noisy image candidates | VOA LE (site logo `6dad2-...` and `player-spinner.png` on every page), NASA (same file as `og` and `hero`) | candidate lists contain decorative and duplicate entries | `reading_article_extraction.py:874-882` (`_decorative_url`), :882-944 | Low |
| D14 | Canonical re-encodes parentheses | `zh.wikipedia.org/wiki/野蛮人柯南_(1982年电影)` stored as `...%281982%E5%B9%B4...%29` | differs from the page's own canonical link | `reading_processing.py:173-210` (`normalize_url`) | Low |

### Confirmation of the catalogue's 9 engine-gap hypotheses (section 8, items 1 to 9)

Item 10 (TLS chain on a Taiwan government host) was out of scope for the shortlist and was not tested.

| H | Hypothesis | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | `promos` token prunes The Conversation body | **Confirmed** | Not in the trial set; checked by running `extract_article` on the live article in the :8021 container: as served confidence `low`, with the class `inline-promos` removed `high`. Location `reading_article_extraction.py:56-62`. |
| 2 | Wikipedia feeds link to FeedItem pages | **Confirmed** | 10 of 10 items, D3. |
| 3 | Wrong title on wiki pages | **Confirmed (zh Wikipedia)** | D4: JSON-LD `headline` is the Wikidata description (live `"headline":"生物体从环境中摄取营养物…"` against `<title>代谢 - 维基百科…`). English pages were not re-run. |
| 4 | Whole-encyclopedia pages exceed a session | **Confirmed** | 5 articles of 3,273 to 18,496 units; 4 carry `too_long` (limit `MAX_ARTICLE_WORDS = 4000`, `reading_processing.py:82`), the 3,273-unit one does not. No excerpting exists. |
| 5 | Frozen or closed sources have no poll path | **Confirmed by construction** | VOA Learning English could only be imported by `ReadingContentEngine.submit` per URL; no adapter lists an archive. Not separately probed. |
| 6 | Bot-challenge and 403 pages look like short articles | **Partly refuted, partly new** | The audio page and the VOA 中文 audio/video pages that returned no article were flagged (`too_short`, `extraction_low_confidence`) and are visible in the queue, so low confidence is distinguishable. But a medium-confidence page without an article (8208887) has no flag (D10). No actual 403 or challenge page was fetched in this trial. |
| 7 | zh-Hant handling unknown | **Confirmed gap** | Language detection is right (`zh`, 0.86 to 1.0) and no mojibake, but no script label exists anywhere, level is HSK6 for all ten (D6, `_ZH_COMMON` is Simplified-only), and one Wikipedia body mixes scripts. |
| 8 | Source-level rights cannot express per-item carve-outs | **Confirmed, with a second form** | VOA LE bodies carry AP/AFP credit lines yet pass the same `rights` as VOA-produced ones (no per-item flag exists); and the origin rule drops rights entirely for items on a sibling host (D8). |
| 9 | Gutenberg header/licence block | **Not tested** | Gutenberg was not in the trial. |

## 4. Implications for Phase 3

- Safest Phase 3 publish sample (clean text, rights inherited): NASA `nasa.gov` releases (`52578b`, `31f6e9`), GV EN
  articles with no glued words (`b89754`, `68d82c`, `3f4d7c`), VOA 中文 full reports (`ced37e`, `01c68f`, `99b123`) and
  the URL-source GV 中文 article (`3d00d0`). Each still needs the reviewer to answer `can_republish`, which is the
  gate that was kept closed here.
- Do not publish from: zh Wikipedia (feed or direct), the two VOA 中文 non-text pages, the VOA LE audio page, or the
  GV EN articles with D1 (`6b06ec`, `a4dd5a`, `9e51fb`, `b6ff73`, `ad3bae`, `67dec6`).
- Fix order that would unlock most of the shortlist: D1, D2, D3 and D4 (extraction and poller), then D6 (level), D8.

All trial articles remain in `needs_review` on :8021 for Phase 3.
