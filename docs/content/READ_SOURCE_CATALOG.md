# Reading source catalogue (Phase 1)

Status: research only, surveyed 2026-10-13. Nothing here was imported into any Orena runtime, no paid API was called,
and no engine code was changed. Branch `claude/reading-source-quality`.

## 1. Method

- **Feeds.** Every feed URL below was fetched live (stdlib client, `User-Agent: OrenaMediaImport/1.0`, the poller's own
  agent string). Item counts, dates, full text versus summary and image enclosures were read from the XML. "Item span"
  is the newest-to-oldest date range in the feed as served; update frequency is derived from it.
- **Sample article.** For each source one or more real article pages were fetched with the same client and run through
  the repository's own `extract_article` (`article-extract/2`, stdlib only) without importing anything. Reported:
  extractor confidence (high/medium/low), prose "units" (words for EN, characters/words as `units()` counts them for ZH;
  the engine's floor is `MIN_PROSE_UNITS = 120`), whether the body was in the server HTML (all were; none needed
  JavaScript to show the article), `og:image` presence, and paywall wording.
- **Rights.** The licence text or terms page was fetched and quoted where it could be retrieved. Where a terms page
  returned 403/404/timeout it says so, and the source is treated as all rights reserved. A publisher's fame is never a
  reason. `automation_allowed` is "possible" only where an explicit licence or permission covers reuse of the text.
- **Levels.** CEFR / HSK values are my estimates from the samples and the register of the publication, not measured with
  a model. Treat them as +/- one level.
- **"Extraction compatibility"** means: does the existing generic extractor yield a clean, high-confidence body from the
  article URL a feed or an admin would supply.
- Licences below apply to text. Photographs, embedded media and third-party quotations frequently carry other terms
  (see section 5).
- Network limits: BBC pages refused connections, and sspai, 36kr, Huxiu and a few others timed out or returned 403 from
  this network; those are recorded as unverified rather than guessed.

## 2. English candidates

Legend: FT = full text in feed, SUM = summary only, IMG = image/enclosure in feed.

### EN-1 Global Voices (English)
- Homepage: https://globalvoices.org/ . Language: EN. Type: citizen-media news and essays, world society, culture, human rights, technology, life stories.
- Entry: RSS https://globalvoices.org/feed/ , HTTP 200, 15 items, FT, IMG on all 15. Item span 2026-10-03 to 2026-10-13 (about 1.5 per day).
- Sample: https://globalvoices.org/2026/10/12/what-african-elections-can-learn-from-the-borana-gadaa-system/ : server HTML, no paywall, `og:image` yes, extractor high, about 1,230 units, 28 paragraphs.
- Typical length 600 to 1,500 words. Level B2 to C1. Thumbnails: yes (`og:image` plus a feed image).
- Extraction: clean article markup.
- Rights: site footer "This site is licensed as Creative Commons Attribution 3.0 Some Rights Reserved" (https://globalvoices.org/about/lingua/ ; article pages carry `creativecommons.org/licenses/by/3.0`). Attribution to Global Voices and the author is required. Images and embedded tweets can carry other terms.
- `automation_allowed`: possible (explicit CC BY 3.0), text only; images need their own check.
- Recommendation: **ACCEPT**. Explicit open licence, daily, full-text feed, broad human topics.

### EN-2 NASA (nasa.gov news and features)
- Homepage: https://www.nasa.gov/ . Language: EN. Type: science and space news, features, Earth Observatory stories.
- Entry: RSS https://www.nasa.gov/feed/ , HTTP 200, 10 items, FT, no enclosures. Item span 2026-10-10 to 2026-10-13. (`https://www.nasa.gov/news-release/feed/` returns the identical 10.) `https://science.nasa.gov/feed/` and the Earth Observatory feed are served but fail strict XML parsing (not well-formed at line 8, column 45) and so are not poller-safe as is.
- Samples: `.../nasa-science-cargo-launch-on-35th-spacex-resupply-mission-to-station/` high, 420 units; https://science.nasa.gov/earth/earth-observatory/an-impact-structure-with-legs/ high, 411 units, 9 media; antarctic sea ice story high, 604 units. Server HTML, no paywall, `og:image` yes.
- Typical 400 to 900 words. Level B2 (press-release register), features B2 to C1. Thumbnails: yes.
- Extraction: clean.
- Rights: https://www.nasa.gov/nasa-brand-center/images-and-media/ : NASA content "generally are not subject to copyright in the United States. You may use this material for educational or informational purposes ...". "Generally" is the operative word: third-party and partner imagery, logos and the NASA insignia are carved out; no endorsement may be implied.
- `automation_allowed`: possible for text, with a per-item credit/third-party check for images.
- Recommendation: **ACCEPT**. US government work, clean pages, steady cadence.

### EN-3 VOA Learning English (archive)
- Homepage: https://learningenglish.voanews.com/ . Language: EN, written for learners. Type: news, science and technology, health and lifestyle, arts and culture, history, grammar.
- Entry: per-programme RSS under https://learningenglish.voanews.com/rssfeeds (for example `/api/zmg_pl-vomx-tpeymtm` Science and Technology, `/api/zmmpql-vomx-tpey-_q` Health and Lifestyle, `/api/zpyp_l-vomx-tpe_rym` Arts and Culture): HTTP 200, 20 items each, SUM (no body in feed), images present. **Every feed is frozen:** the newest item across all 40 programme feeds is 2025-04-29; most stop in March 2025. This is an archive, not a live source. (I could not find a live replacement.)
- Samples: `/a/how-physical-therapists-can-prevent-future-health-problems/7921334.html` high, 789 units; `/a/study-shows-how-earth-s-orbit-affects-ice-ages/7997495.html` high, 474 units. Some `/a/80xxxxx.html` pages are audio/video pages with no text body and extract low (7 units) correctly. Server HTML, no paywall, `og:image` yes.
- Typical 400 to 800 words. Level A2 to B1 (controlled vocabulary), the best learner-fit of any EN source. Thumbnails: yes.
- Extraction: clean on text stories, expected rejects on audio pages.
- Rights: https://www.voanews.com/p/5338.html "All text, audio and video material produced exclusively by the Voice of America is in the public domain. Credit for any use of VOA material should be given to voanews.com, Voice of America, or VOA. However, voanews.com content may also contain ... copyrighted material that is licensed for use in VOA programming only ... may not be copied, redistributed ... without the express permission of the copyright owner." Third-party (AP, AFP, Reuters) text and photos are excluded.
- `automation_allowed`: possible for VOA-produced text; third-party images and any wire-credited item must be excluded.
- Recommendation: **ACCEPT** (as a one-off archive import by URL list, not by polling). Public domain, leveled, interesting, but frozen.

### EN-4 Wikinews (English) (archive)
- Homepage: https://en.wikinews.org/ . Language: EN. Type: original news reports, world, society, culture, sport.
- Entry: no usable feed. `Special:NewsFeed` returns 404; the `feedrecentchanges` Atom feed (https://en.wikinews.org/w/api.php?action=feedrecentchanges&feedformat=atom , 200, 42 items, summaries) lists wiki edits, not published articles. The MediaWiki API (`list=categorymembers&cmtitle=Category:Published`) works and returns title and timestamp. **The project closed:** the newest Published article is "Wikimedia Foundation closes Wikinews after 21 years" dated 2026-05-03; before that about 3 to 10 per month.
- Sample: https://en.wikinews.org/wiki/Pope_Leo_XIV_visits_four_nations_in_Africa : high, 549 units, 3 media, `og:image` yes, no paywall. The extracted title was the literal "Wikinews article" (see section 6).
- Typical 300 to 700 words. Level B2. Thumbnails: yes.
- Extraction: clean body, bad title.
- Rights: https://en.wikinews.org/wiki/Wikinews:Copyright "All material published on Wikinews after December 16, 2024 is licensed under ... Creative Commons Attribution 4.0 ... prior [to that] but after September 25, 2005 ... Attribution 2.5 ... prior to September 25, 2005, is in the public domain." Attribute to "Wikinews".
- `automation_allowed`: possible, by article; images on Commons may differ.
- Recommendation: **ACCEPT** (archive, by API-listed URL). Open licence, but dated news and no live feed.

### EN-5 Simple English Wikipedia
- Homepage: https://simple.wikipedia.org/ . Language: EN. Type: encyclopedia articles written in basic English: science, animals, history, culture, everyday topics.
- Entry: direct URL only. The `featuredfeed` endpoint on simple.wikipedia.org returned an HTML page, not a feed (no Atom).
- Sample: https://simple.wikipedia.org/wiki/Octopus : high, 1,642 units, 41 paragraphs, `og:image` yes, no paywall. Extracted title was the Wikidata description "largest genus of octopuses" (see section 6).
- Typical 300 to 2,500 words. Level A2 to B1. Thumbnails: yes.
- Extraction: clean body, wrong title.
- Rights: Wikipedia text is CC BY-SA 4.0 and GFDL; the quoted wording is from the Chinese copyright policy page (see ZH-1), and I did not fetch the English or Simple English policy page separately. ShareAlike applies to adaptations (see open question Q2).
- `automation_allowed`: possible with explicit CC BY-SA 4.0, conditional on the Q2 decision.
- Recommendation: **ACCEPT** (curated URL list). Best level fit and clean, but the share-alike consequence needs a human call.

### EN-6 English Wikipedia (featured article and On this day)
- Homepage: https://en.wikipedia.org/ . Language: EN. Type: featured articles (culture, science, history, biography).
- Entry: Atom https://en.wikipedia.org/w/api.php?action=featuredfeed&feed=featured&feedformat=atom , HTTP 200, 10 items, summary about 6,700 chars of HTML, no enclosure. Item span 2026-10-04 to 2026-10-13, one per day. Item links point at `Special:FeedItem/featured/...` pages, not the article. Sample FeedItem page extracts low (157 units).
- Sample article: https://en.wikipedia.org/wiki/Octopus : high, 10,033 units, 162 paragraphs, `og:image` yes.
- Typical 3,000 to 15,000 words, far past a comfortable reading session. Level B2 to C1 and above. Thumbnails: yes.
- Extraction: clean on the real article; the feed link is the wrong page.
- Rights: CC BY-SA 4.0 and GFDL (same page as EN-5).
- `automation_allowed`: possible (explicit licence), conditional on Q2.
- Recommendation: **ACCEPT** (curated, using the article URL from the feed summary, and lead or section excerpting). Interesting and daily, but long.

### EN-7 Project Gutenberg (short stories)
- Homepage: https://www.gutenberg.org/ . Language: EN. Type: public-domain fiction, essays, short stories.
- Entry: RSS https://www.gutenberg.org/cache/epub/feeds/today.rss , HTTP 200, 11 items, SUM (titles only, no dates), no images. It lists new e-books, not stories chosen for readers. Practical entry is a curated list of direct URLs, for example https://www.gutenberg.org/cache/epub/1952/pg1952-images.html .
- Sample: "The Yellow Wallpaper": medium, 6,144 units, 258 paragraphs, `og:image` yes (the generic cover), no paywall. The Project Gutenberg header/licence block must be trimmed.
- Typical short stories 2,000 to 8,000 words. Level B2 to C2 (19th and early 20th century prose). Thumbnails: generic cover only.
- Extraction: workable; confidence medium (no `<article>`).
- Rights: https://www.gutenberg.org/policy/permission.html "Most permission requests we receive do not require a customised response" and the page's own sections "US only" and "Trademark". Public-domain status is US-based; the "Project Gutenberg" trademark carries its own terms.
- `automation_allowed`: possible per work for pre-1929 texts; a per-work check, not a source-wide flag.
- Recommendation: **ACCEPT** (curated shorts, story coverage).

### EN-8 Standard Ebooks (new releases)
- Homepage: https://standardebooks.org/ . Language: EN. Type: carefully edited public-domain books.
- Entry: Atom https://standardebooks.org/feeds/rss/new-releases , HTTP 200, 15 items, FT-ish (about 1,200 chars of description), image on all 15. Item span 2026-09-08 to 2026-10-12.
- Sample: book landing page extracts high at 572 units (a description, not the book). The text is under `/text/chapter-N` pages and whole books exceed `MAX_TEXT_CHARS`.
- Level C1 to C2. Thumbnails: yes (cover).
- Extraction: landing pages fine; reading needs chapter-level URLs.
- Rights: page carries https://creativecommons.org/publicdomain/zero/1.0 ("CC0"): the edition's new work is dedicated to the public domain, the underlying books are US public domain.
- `automation_allowed`: possible per book, with the same per-work check as Gutenberg.
- Recommendation: **ACCEPT** (as a book/chapter source, not for articles).

### EN-9 The Conversation
- Homepage: https://theconversation.com/ . Language: EN. Type: academic-authored explainers, society, science, culture.
- Entry: Atom https://theconversation.com/global/articles.atom , HTTP 200, 50 items, FT (average about 10,300 chars of HTML), no enclosures. Item span 2026-09-01 to 2026-10-12 (about 1.2 per day).
- Samples: https://theconversation.com/hooked-on-tuna-people-have-been-harvesting-these-ocean-predators-for-44-000-years-292428 . Server HTML, no paywall, `og:image` yes, author yes. **Extracted low (7 units) in 3 of 3 samples** even though the HTML has 31 paragraphs in `itemprop="articleBody"`. Cause confirmed locally: the container's class contains `inline-promos`; `_BOILERPLATE_TOKENS` includes `promos`, so the whole body is pruned. Removing that class makes the extractor return 1,141 units, high.
- Typical 700 to 1,500 words. Level B2 to C1.
- Rights: https://theconversation.com/republishing-guidelines "we ... publish under a Creative Commons - Attribution/No derivatives license. This means you can republish our articles online or in print for free, provided you follow these guidelines ... You can't edit our material, except to reflect relative changes in time, location and editorial style." Republication also requires keeping the byline, a link back, and the tracking pixel in the supplied embed.
- ND implication: reproduce the whole article unchanged, with their HTML. Orena's engine normalises, segments, sentence-splits and builds level or translated derivatives, and the learner UI re-flows text; most of that is a "derivative" under ND. Only an unaltered display plus link-out is clearly inside the licence.
- `automation_allowed`: not without a legal read of ND against the engine's transforms.
- Recommendation: **MANUAL_ONLY**. Excellent content, but ND is incompatible with automated adaptation.

### EN-10 ProPublica
- Homepage: https://www.propublica.org/ . Language: EN. Type: investigative long form, society.
- Entry: RSS https://www.propublica.org/feeds/propublica/main , HTTP 200, 20 items, FT (about 26,000 chars HTML), no enclosures. Item span 2026-10-02 to 2026-10-13.
- Sample: https://www.propublica.org/article/post-conviction-legal-delays-pennsylvania : high, 3,027 units, `og:image` yes, no paywall.
- Typical 2,000 to 5,000 words. Level C1.
- Rights: https://www.propublica.org/steal-our-stories/ "Unless otherwise noted, you can republish our articles for free under a Creative Commons license"; the article page links `creativecommons.org/licenses/by-nc-nd/3.0` (BY-NC-ND 3.0). NonCommercial and NoDerivatives both apply, plus "This story was originally published by ProPublica" credit and link rules.
- `automation_allowed`: no (NC and ND).
- Recommendation: **MANUAL_ONLY**. Heavy, grim, and NC-ND.

### EN-11 MIT News
- Homepage: https://news.mit.edu/ . Language: EN. Type: university research news, interviews.
- Entry: RSS https://news.mit.edu/rss/feed , HTTP 200, 50 items, FT (about 7,900 chars), image on all 50. Item span 2026-09-01 to 2026-10-13.
- Sample: https://news.mit.edu/2026/qa-building-accountability-behind-our-words-and-ai-civic-conversations-1013 : high, 2,492 units, `og:image` yes, no paywall.
- Typical 600 to 1,500 words. Level C1 (academic). Thumbnails: yes.
- Rights: article page links `creativecommons.org/licenses/by-nc-nd/3.0` (BY-NC-ND 3.0). (The site's /terms and /about-mit-news pages returned 404, so the page-level licence link is the evidence.)
- `automation_allowed`: no (NC and ND).
- Recommendation: **MANUAL_ONLY**. Educational and academic, so it must not dominate anyway.

### EN-12 ESA (European Space Agency) science news
- Homepage: https://www.esa.int/ . Language: EN. Type: space science.
- Entry: RSS https://www.esa.int/rssfeed/Our_Activities/Space_Science , HTTP 200, 15 items, SUM (about 2,200 chars), no images. Item span 2026-08-12 to 2026-10-13 (about 1 per 4 days).
- Sample: https://www.esa.int/Science_Exploration/Space_Science/Solar_Orbiter/Solar_Orbiter_tracks_origin_of_mysterious_magnetic_switchbacks : high, 902 units, `og:image` yes, no paywall.
- Typical 500 to 900 words. Level B2 to C1.
- Rights: https://www.esa.int/Services/Terms_and_conditions "The contents of the ESA website are intended for the personal and non-commercial use of its users ... ESA does not grant ..." (the sentence continues beyond what I read; some ESA multimedia carries separate CC licences, not verified here).
- `automation_allowed`: no.
- Recommendation: **MANUAL_ONLY**.

### EN-13 Library of Congress blogs
- Homepage: https://blogs.loc.gov/loc/ . Language: EN. Type: history, literature, culture, collections.
- Entry: RSS https://blogs.loc.gov/loc/feed/ , HTTP 200, 10 items, FT (about 6,200 chars), no enclosures. Item span 2026-09-08 to 2026-10-07 (about 1 per 3 days).
- Sample: https://blogs.loc.gov/loc/2026/10/saved-by-the-beauty-of-the-world-mary-oliver/ : high, 874 units, `og:image` yes, no paywall.
- Typical 500 to 1,000 words. Level B2.
- Rights: https://www.loc.gov/legal/ says the Library "generally do[es] not own the rights to materials in our collections", tells users to check copyright status themselves, and says nothing specific about blog posts. A posting by a federal employee is a US government work, but guests and quoted material are not covered.
- `automation_allowed`: not established.
- Recommendation: **MANUAL_ONLY** until a blog-specific statement is found.

### EN-14 US Department of Energy news (representative US government agency)
- Homepage: https://www.energy.gov/ . Language: EN. Type: government announcements.
- Entry: RSS https://www.energy.gov/rss/articles.xml , HTTP 200, 10 items, SUM (about 170 chars), no images. Item span 2026-09-29 to 2026-10-12.
- Sample: `energy.gov/articles/energy-department-authorizes-strategic-petroleum-reserve-exchange-address-supply` : low, 229 units, 1 paragraph (a short notice).
- Level C1, dry. Not interesting for learners.
- Rights: US federal government work (17 U.S.C. 105): public domain in the US. I did not fetch an agency-specific terms page.
- `automation_allowed`: rights would allow it; quality does not.
- Recommendation: **MANUAL_ONLY** (rights-clear but low value; NOAA, USGS, NPS and USDA pages returned 403 or empty feeds to this client).

### EN-15 BBC News
- Homepage: https://www.bbc.com/news . Feed https://feeds.bbci.co.uk/news/rss.xml , 200, 32 items, SUM, image on all 32, item span 2026-10-13 only.
- Sample: `bbc.co.uk/news/articles/c3ewegny45jvo` : high, 633 units, no paywall, `og:image` yes. Level B2.
- Rights: BBC Terms (https://www.bbc.co.uk/usingthebbc/terms/ ; I could not retrieve the clause wording, the page text did not match my probes) restrict reuse to personal, non-commercial use; no open licence.
- Recommendation: **REJECT**. All rights reserved.

### EN-16 Smithsonian Magazine
- Homepage: https://www.smithsonianmag.com/ . Feed https://www.smithsonianmag.com/rss/latest_articles/ , 200, 10 items, SUM, images, span 2026-10-09 to 2026-10-13.
- Sample: `smart-news/did-industrialization-gut-our-microbiomes-...-180989658/` : high, 859 units, `og:image` yes; the page contains the string "metered" but the article rendered in full.
- Rights: terms page returned HTTP 403 to this client; no open licence found. Treated as all rights reserved.
- Recommendation: **REJECT**.

### EN-17 Open Culture
- https://www.openculture.com/ . Feed https://www.openculture.com/feed , 200, 15 items, FT, no images, span 2026-10-01 to 2026-10-13. Sample medium, 652 units. Culture and life topics, B2.
- Rights: page footer "(c)2006-2026 Open Culture, LLC." and a "Copyright Policy" link; no open licence.
- Recommendation: **REJECT**.

### EN-18 The Marginalian
- https://www.themarginalian.org/ . Feed https://www.themarginalian.org/feed/ , 200, 20 items, FT, span 2026-09-30 to 2026-10-13. Sample medium, 599 units. Essays, culture, C1.
- Rights: no licence statement found on the article or about page; all rights reserved by default.
- Recommendation: **REJECT**.

### EN-19 ScienceDaily
- https://www.sciencedaily.com/ . Feed https://www.sciencedaily.com/rss/all.xml , 200, 60 items, SUM, no images, span 2026-10-08 to 2026-10-13. Sample high, 1,548 units (includes related-story boilerplate).
- Rights: footer "Copyright 1995-2026 ScienceDaily"; content is institutional press releases republished with ScienceDaily's own editing; no open licence.
- Recommendation: **REJECT**.

### EN-20 Nature (news)
- https://www.nature.com/ . Feed https://www.nature.com/nature.rss , 200, 75 items, FT-flagged (about 300 chars), span 2026-10-07 to 2026-10-13.
- Sample page returned a bot-challenge page ("Client Challenge", 3 KB): low, 35 units.
- Rights: news and commentary are all rights reserved; only specific research articles are CC BY.
- Recommendation: **REJECT**.

### EN-21 Aeon
- https://aeon.co/ . Feed https://aeon.co/feed.rss , 200, 20 items, SUM, span 2026-09-24 to 2026-10-13. Sample was a video page (high, 147 units, wording "paywall" in the page script).
- Rights: https://aeon.co/republish (per search summary; the site's own pages 404 to this client): republishing an essay needs a paid agreement and an unaltered copy; excerpts up to 250 words for critique. Page footer "(c) Aeon Media Group Ltd."
- Recommendation: **REJECT**.

### EN-22 Phys.org
- https://phys.org/ . Feed https://phys.org/rss-feed/ , 200, 30 items, SUM, images, span 2026-10-12 to 2026-10-13. The article page returned HTTP 403 to the Orena user agent.
- Rights: no open licence found (aggregates press releases); not retrievable by the engine.
- Recommendation: **REJECT**.

## 3. Chinese candidates

### ZH-1 Wikipedia 中文 (典范条目 / 今日 / 历史上的今天)
- Homepage: https://zh.wikipedia.org/ . Language: ZH (variant-converted on request: the sample served Simplified). Type: featured articles, culture, science, history, society, life.
- Entry: Atom https://zh.wikipedia.org/w/api.php?action=featuredfeed&feed=featured&feedformat=atom , HTTP 200, 10 items, summary about 2,000 chars, no enclosure, span 2026-10-04 to 2026-10-13, one a day. Also `feed=onthisday` (10 items, about 3,800 chars) and `feed=potd`. Item links are `Special:FeedItem/featured/...` pages (low when extracted, 153 units).
- Sample article: https://zh.wikipedia.org/wiki/%E7%AB%A0%E9%B1%BC : high, 14,553 units, 151 paragraphs, `og:image` yes, no paywall.
- Typical 1,500 to 15,000 characters. Level HSK 5 to 6+. Thumbnails: yes.
- Extraction: clean on the article; the feed link is the wrong page.
- Rights: https://zh.wikipedia.org/wiki/Wikipedia:%E7%89%88%E6%9D%83%E4%BF%A1%E6%81%AF "大部分文字及许多图片同时依 创用CC 姓名标示-相同方式分享 4.0 国际版授权条款 (CC BY-SA) 与 GNU 自由文件授权条款 (GFDL) 授权" (quoted from the Traditional-script copy of the page). Share-alike: see Q2.
- `automation_allowed`: possible (explicit licence), conditional on Q2.
- Recommendation: **ACCEPT** (curated, article URL taken from the feed summary, lead or section excerpting).

### ZH-2 VOA 中文 (美国之音)
- Homepage: https://www.voachinese.com/ . Language: ZH Simplified. Type: international and China news, US society, Taiwan, analysis.
- Entry: RSS https://www.voachinese.com/api/ , HTTP 200, 20 items, SUM (about 170 chars), image on all 20, span 2026-10-08 to 2026-10-13 (about 4 per day).
- Samples: `/a/taiwan-us-officials-celebrate-strong-democratic-partnership-at-double-ten-event-in-washington-20261008/8209315.html` high, 2,176 units, 27 paragraphs; `/a/analysts-say-details-are-key-to-any-russia-ukraine-energy-ceasefires-20261012/8210454.html` low (1,003 units but one long paragraph); the "VOA今日焦点" daily digest pages low or medium. Server HTML, no paywall, `og:image` yes.
- Typical 600 to 1,500 characters. Level HSK 5 to 6. Thumbnails: yes.
- Extraction: good on reports; digest and long single-paragraph pages are borderline.
- Rights: same VOA statement as EN-3 (https://www.voanews.com/p/5338.html): VOA-produced text is public domain; AFP, AP and Reuters text and photos are licensed to VOA only and are not.
- `automation_allowed`: possible only if wire-credited items are excluded per item.
- Recommendation: **ACCEPT** (conditional). Public domain, active, Simplified, but politics-heavy and mixed with licensed wire copy.

### ZH-3 Global Voices 中文
- Homepage: https://zh.globalvoices.org/ . Language: ZH **Traditional** (the feed's items resolve to `zht.globalvoices.org`). A Simplified edition was not found (`cn.globalvoices.org` 404; `/lingua/zh/feed/` 410 Gone). Type: citizen media translations, society, culture, human rights.
- Entry: RSS https://zh.globalvoices.org/feed/ , HTTP 200, 10 items, FT (about 6,200 chars), image on all 10. **Item span 2025-05-13 to 2026-05-15: about one a month and the newest is five months old.**
- Sample: https://zht.globalvoices.org/2026/04/14/37270/ : high, 997 units, 18 paragraphs, `og:image` yes, no paywall.
- Typical 800 to 1,500 characters. Level HSK 5 to 6. Thumbnails: yes.
- Extraction: clean.
- Rights: `creativecommons.org/licenses/by/3.0` on both `zh.globalvoices.org` and `zht` pages; "This site is licensed as Creative Commons Attribution 3.0" (https://globalvoices.org/about/lingua/).
- `automation_allowed`: possible (explicit CC BY 3.0), text only.
- Recommendation: **ACCEPT**. The cleanest licence in the ZH set, but Traditional-only and slow.

### ZH-4 中文维基新闻 (zh Wikinews) (archive)
- Homepage: https://zh.wikinews.org/ . Language: ZH (variants). Type: news reports.
- Entry: no usable feed. `feedrecentchanges` returned 4 items, all MediaWiki gadget edits. The API category listing works. **The project closed:** the newest Published article is dated 2026-05-06 and one of the last is "中文维基新闻此次关站纪实".
- Sample: https://zh.wikinews.org/wiki/%E4%B8%AD%E6%96%87%E7%BB%B4%E5%9F%BA%E6%96%B0%E9%97%BB%E6%AD%A4%E6%AC%A1%E5%85%B3%E7%AB%99%E7%BA%AA%E5%AE%9E : high, 949 units, `og:image` yes.
- Level HSK 5. Thumbnails: sometimes.
- Rights: https://zh.wikinews.org/wiki/Wikinews:%E7%89%88%E6%9D%83 links `creativecommons.org/licenses/by/2.5` and `by/4.0` (older articles 2.5, newer 4.0; same scheme as EN).
- `automation_allowed`: possible by article.
- Recommendation: **ACCEPT** (archive only, by API-listed URL). Open licence, volume is a few hundred articles, no live updates.

### ZH-5 中文维基文库 (zh Wikisource): Lu Xun and other public-domain literature
- Homepage: https://zh.wikisource.org/ . Language: ZH (mostly Simplified-served from Traditional source, variant conversion). Type: stories, essays, classical and early-modern literature.
- Entry: direct URL only. The `featuredfeed` endpoint returned an HTML page, not a feed.
- Sample: https://zh.wikisource.org/wiki/%E5%91%90%E5%96%8A (Lu Xun, 呐喊) : high, 2,560 units, 24 paragraphs, no `og:image`, no paywall.
- Typical 1,000 to 10,000 characters. Level HSK 6+ for modern vernacular, higher for classical. Thumbnails: none.
- Rights: Wikisource hosts only public-domain or freely licensed works; the status is per work (author death date), and the page template states it. I did not verify each individual text.
- `automation_allowed`: possible per work after the per-work PD check.
- Recommendation: **ACCEPT** (curated shorts; the only ZH story source here).

### ZH-6 联合国新闻 (UN News 中文)
- Homepage: https://news.un.org/zh/ . Language: ZH Simplified. Type: global affairs, health, climate, development.
- Entry: RSS https://news.un.org/feed/subscribe/zh/news/all/rss.xml , HTTP 200, 30 items, SUM (about 90 chars), image on all 30, span 2026-10-07 to 2026-10-12.
- Sample: https://news.un.org/feed/view/zh/story/2026/10/1142986 : high, 472 units, `og:image` yes, no paywall.
- Typical 400 to 900 characters. Level HSK 5.
- Rights: https://www.un.org/zh/about-us/copyright "版权所有 联合国 ... 除使用联合国网址的条款和条件所规定者外，非经发行人书面许可，本网址所提供材料无论全部或部分均不得以任何电子或机械形式或手段 ... " reproduced. The terms allow some non-commercial use; I did not read the permitted-use clause in full.
- `automation_allowed`: not established.
- Recommendation: **MANUAL_ONLY**.

### ZH-7 阮一峰的网络日志 (科技爱好者周刊)
- Homepage: https://www.ruanyifeng.com/blog/ . Language: ZH Simplified. Type: weekly technology and culture digest, essays.
- Entry: Atom https://www.ruanyifeng.com/blog/atom.xml , HTTP 200, 3 items, FT (about 14,000 chars), no images, span 2026-09-11 to 2026-10-08 (about weekly).
- Sample: `/blog/2026/09/weekly-issue-413.html` : high, 3,233 units, 86 paragraphs, no `og:image`, no paywall.
- Level HSK 5 to 6. Thumbnails: none.
- Rights: pages link `creativecommons.org/licenses/by-nc-nd/3.0` (BY-NC-ND 3.0).
- `automation_allowed`: no (NC and ND).
- Recommendation: **MANUAL_ONLY**.

### ZH-8 爱范儿 ifanr
- Homepage: https://www.ifanr.com/ . Language: ZH Simplified. Type: technology, gadgets, life, culture.
- Entry: RSS https://www.ifanr.com/feed , HTTP 200, 20 items, FT (about 16,500 chars), image on all 20, span 2026-10-09 to 2026-10-13 (about 5 per day).
- Sample: https://www.ifanr.com/1684008 : high, 5,011 units, 87 paragraphs, `og:image` yes, no paywall.
- Level HSK 5 to 6. Thumbnails: yes.
- Rights: site footer links `creativecommons.org/licenses/by-nc/4.0` (BY-NC 4.0), alongside "版权所有". Non-commercial only.
- `automation_allowed`: no, unless the human decides Orena's use is non-commercial (Q3).
- Recommendation: **MANUAL_ONLY**.

### ZH-9 報導者 The Reporter
- Homepage: https://www.twreporter.org/ . Language: ZH **Traditional only**. Type: long-form investigative and society reporting (Taiwan).
- Entry: RSS https://www.twreporter.org/a/rss2.xml , HTTP 200, 10 items, SUM (about 100 chars), image on all 10, span 2026-10-07 to 2026-10-12.
- Sample: https://www.twreporter.org/a/2026-local-elections-dpp-the-movement : medium (no `<article>`), 8,643 units, `og:image` yes, no paywall.
- Level HSK 6. Thumbnails: yes.
- Rights: on the article page "本文僅文字內容依 CC 創用姓名標示-非商業性-禁止改作 3.0 台灣授權條款釋出，文中照片不在此授權範圍內。" (BY-NC-ND 3.0 Taiwan, text only, photographs excluded).
- `automation_allowed`: no (NC and ND).
- Recommendation: **MANUAL_ONLY**.

### ZH-10 行政院 (Taiwan Executive Yuan) news and consumer notices
- Homepage: https://www.ey.gov.tw/ . Language: ZH Traditional. Type: government announcements and consumer information.
- Entry: RSS https://www.ey.gov.tw/RSS_Content.aspx?ModuleType=1 , served valid RSS 2.0 (verified with certificate checking off); my default Python client failed certificate verification on this host in the first attempt, so a TLS-chain issue is possible in the container too.
- Rights: the page says "以下內容之著作權均屬行政院或原著作權人所有，除有合理使用情形 ..." (copyright belongs to the Executive Yuan or the original author, apart from fair use). The separate Government Open Data License v1 (https://data.gov.tw/license : "使用者得再轉授權他人 ... 重製、散布、公開傳輸 ... 編輯、改作") covers published open datasets; it is not shown to cover site text.
- `automation_allowed`: no, until the agency states its licence for web text (Q4).
- Recommendation: **MANUAL_ONLY**.

### ZH-11 端传媒 The Initium
- Homepage: https://theinitium.com/ . Language: ZH Traditional and Simplified toggle. Feed https://theinitium.com/rss , 200, 15 items, FT (about 9,000 chars), image on all 15, span 2026-10-07 to 2026-10-12.
- Sample: `theinitium.com/20261013-wsj-why-china-doesnt-want-to-join-the-ranks-of-the-worlds-developed-countries/` : high, 342 units (truncated member preview), `og:image` yes, page contains "paywall".
- Rights: https://theinitium.com/copyright "本網站所有內容均受新加坡版權法保護，未經 Initium Media Group Inc. 事先書面同意，任何人不得複製、發行 ..." and "所有轉載都須獲得端傳媒許可".
- Recommendation: **REJECT**. The feed carries full text, but that is not a licence.

### ZH-12 少数派 sspai
- https://sspai.com/ . Feed https://sspai.com/feed timed out from this network. Rights terms not retrieved. Treated as all rights reserved.
- Recommendation: **REJECT** (unverified; reopen if the human supplies a licence).

### ZH-13 极客公园 GeekPark
- https://www.geekpark.net/ . Feed https://www.geekpark.net/rss , 200, 30 items, SUM (about 7,700 chars), no images, span 2026-10-01 to 2026-10-13. Sample high, 2,163 units; the homepage returned 403 to a browser-like client.
- Rights: no licence found.
- Recommendation: **REJECT**.

### ZH-14 苦劳网 Coolloud
- https://www.coolloud.org.tw/ . Traditional. Feed https://www.coolloud.org.tw/rss.xml , 200, 20 items, SUM (about 6,000 chars), no images, span 2026-08-29 to 2026-10-10. Sample high, 4,348 units.
- Rights: a "版權宣告" page is linked but its URL guesses 404'd and its text was not retrieved.
- Recommendation: **REJECT** (licence not verified).

### ZH-15 BBC 中文
- https://www.bbc.com/zhongwen/ . Feeds https://feeds.bbci.co.uk/zhongwen/simp/rss.xml and `.../trad/rss.xml` , 200, 38 items each, SUM, images, span 2026-10-03 to 2026-10-13. The article host refused connections from this network. Both feeds list the same `/trad` URLs in this sample.
- Rights: BBC terms, all rights reserved.
- Recommendation: **REJECT**.

### ZH-16 纽约时报中文网
- https://cn.nytimes.com/ . Feed https://cn.nytimes.com/rss/ , 200, 20 items, SUM, no images. Sample high, 1,681 units.
- Rights: all rights reserved, subscription model.
- Recommendation: **REJECT**.

### ZH-17 德国之声中文 (DW)
- https://www.dw.com/zh/ . Feed https://rss.dw.com/xml/rss-chi-all , 200, 60 items, SUM, no images; the item dates run back to 2019, so the feed is not a clean recent list. Terms not retrieved; all rights reserved by default.
- Recommendation: **REJECT**.

### ZH-18 FT中文网
- https://www.ftchinese.com/ . Feed https://www.ftchinese.com/rss/feed , 200, 20 items, SUM. Article fetch returned HTTP 429. Paywalled subscription publisher.
- Recommendation: **REJECT**.

### ZH-19 PTT
- https://www.ptt.cc/atom/Gossiping.xml , 200, 20 items, FT. User-generated forum posts with no licence and unsuitable content.
- Recommendation: **REJECT**.

## 4. Summary counts

| Language | ACCEPT | MANUAL_ONLY | REJECT | Total |
| --- | --- | --- | --- | --- |
| EN | 8 (EN-1 to EN-8) | 6 (EN-9 to EN-14) | 8 (EN-15 to EN-22) | 22 |
| ZH | 5 (ZH-1 to ZH-5) | 5 (ZH-6 to ZH-10) | 9 (ZH-11 to ZH-19) | 19 |

Six ACCEPT sources are archives or curated-URL sources with no live feed (EN-3, EN-4, EN-5, EN-7, ZH-4, ZH-5), so only these ACCEPT sources can be polled today: EN-1, EN-2, EN-6 (with the link caveat), EN-8, ZH-1 (with the link caveat), ZH-2, ZH-3 (very slow).

## 5. Ranked shortlist for the real-content trial

Chosen for: clean extraction, rights that a source-level `automation_allowed` can honestly rest on, and learner interest.

### English
1. **NASA** (EN-2). Feed https://www.nasa.gov/feed/ . US government work, all samples extract high with images, three to four items a day, B2.
2. **Global Voices (English)** (EN-1). Feed https://globalvoices.org/feed/ . Explicit CC BY 3.0, full text, widest topic spread (society, culture, life), high confidence, B2 to C1.
3. **VOA Learning English** (EN-3). Archive by URL list (feeds https://learningenglish.voanews.com/api/zmg_pl-vomx-tpeymtm and `/api/zmmpql-vomx-tpey-_q` list the stories; they stop in March 2025). Public domain, leveled A2 to B1, the best fit for learners; the trial should include the audio-only pages to confirm they are rejected cleanly.

Runner-up: Simple English Wikipedia (EN-5), pending Q2.

### Chinese
1. **中文维基百科 featured / on this day** (ZH-1). Feed https://zh.wikipedia.org/w/api.php?action=featuredfeed&feed=featured&feedformat=atom . Daily, explicit CC BY-SA, clean article pages, wide topics; needs the article URL taken from the summary (Q2 for share-alike).
2. **VOA 中文** (ZH-2). Feed https://www.voachinese.com/api/ . Public domain for VOA-produced text, four items a day, Simplified; trial must test the wire-credit exclusion.
3. **Global Voices 中文** (ZH-3). Feed https://zh.globalvoices.org/feed/ . Explicit CC BY 3.0 and full text; included to prove Traditional-script handling and a slow-cadence source. (If Traditional is out of scope, substitute 中文维基文库 ZH-5, curated Lu Xun and other public-domain shorts, for the story category.)

## 6. Rejected and restricted sources (reasons in one place)

- REJECT, all rights reserved or no licence found: BBC News, Smithsonian Magazine, Open Culture, The Marginalian, ScienceDaily, Nature, Aeon (paid republication), Phys.org, 端传媒, 少数派 (unverified), 极客公园, 苦劳网 (unverified), BBC 中文, 纽约时报中文网, DW 中文, FT中文网, PTT.
- MANUAL_ONLY, a licence exists but it excludes automated adaptation or commercial use: The Conversation (BY-ND), ProPublica (BY-NC-ND), MIT News (BY-NC-ND), ESA (personal non-commercial), Library of Congress blogs (no blog statement), US DOE (rights clear, content too thin), 联合国新闻, 阮一峰 (BY-NC-ND), 爱范儿 (BY-NC), 報導者 (BY-NC-ND), 行政院.

## 7. Open rights questions for the human

- **Q1. Third-party material inside an open-licensed article.** Global Voices, NASA and VOA all say the text licence does not cover embedded photographs, tweets and licensed wire copy. Does a source-level `automation_allowed` suffice if the engine strips or never stores images from these sources, or must each item pass a credit-line check?
- **Q2. ShareAlike.** Wikipedia (EN, Simple, ZH) is CC BY-SA 4.0. Orena's derivatives (excerpts, level notes, translations, generated questions, glossary) may be adaptations; ShareAlike would then require Orena to offer them under CC BY-SA. Is that acceptable for the catalogue and for paid tiers?
- **Q3. NonCommercial.** MIT News, ProPublica, 阮一峰, 爱范儿 and 報導者 are NC. Orena has paid plans; is any learner use "non-commercial"? I assumed no, so these are MANUAL_ONLY. A written permission from a publisher would change that.
- **Q4. NoDerivatives.** The Conversation, ProPublica, MIT News, 阮一峰 and 報導者 are ND. The engine normalises and re-flows text; is an unaltered, attributed, link-back display a legitimate Orena mode, or should these be link-out only?
- **Q5. Public domain scope.** Gutenberg and Wikisource status is US-law based and varies by author death date; Orena users are global. Do we accept US status, or restrict to authors who died before a cut-off year?
- **Q6. VOA wire copy.** Is excluding items that carry an AFP, AP or Reuters credit enough for ZH-2 and EN-3, and who maintains that rule? *Partly answered 2026-10-14 by D-192 (PROPOSED): items with a wire credit or no byline lose the source-level public-domain answer; the host table in `reading_rights_refinement.py` is the rule's owner.*
- **Q7. Taiwan government text.** Does the Government Open Data License v1 apply to agency web news, or only to datasets? Without written confirmation 行政院 stays MANUAL_ONLY.
- **Q8. Frozen archives.** VOA Learning English, Wikinews (EN and ZH) are closed or frozen. Is a one-off archive import a "source" under D-111, and does a closed project change the attribution wording?
- **Q9. Script variant.** Is Traditional Chinese content (Global Voices 中文, 報導者, 苦劳网, 行政院) in scope for the Simplified learner track?

## 8. Engine observations to prove in the trial (hypotheses)

1. `_BOILERPLATE_TOKENS` in `writing_coach/reading_article_extraction.py` contains `promos`; The Conversation wraps its article body in a container with class `inline-promos`, so all three sampled Conversation pages extract as 7 units (low). Removing the class made the same page extract high at 1,141 units. Likely over-matching of a class token on the body container.
2. Wikipedia featured feeds link to `Special:FeedItem/...` pages, which extract low (about 150 units). The real article URL is only inside the summary HTML. The poller would queue the wrong page.
3. Title extraction on wiki pages: Simple English Wikipedia "Octopus" returned the Wikidata description "largest genus of octopuses"; English Wikinews returned the literal "Wikinews article"; English Wikipedia returned "order of molluscs". The title picker prefers a metadata field over the page heading on these pages.
4. Whole-encyclopedia pages are 10,000 to 14,500 units, much longer than a reading session, and need lead or section excerpting rather than a single article.
5. Frozen or closed sources (VOA Learning English, both Wikinews) have no live feed, so there is no poll path; a URL-list or API-listing adapter would be needed for archive imports.
6. Bot-challenge and 403 pages (Nature "Client Challenge", Phys.org, NOAA, 极客公园 homepage) answer the Orena agent string with a challenge instead of an article; the extractor reports low confidence, but the failure is indistinguishable from a short article.
7. One feed (zh.globalvoices.org) serves Traditional script; I do not know whether the language/level stages classify zh-Hant correctly.
8. Source-level rights cannot express per-item third-party carve-outs (VOA wire copy, Wikisource per-work status, Gutenberg per-work status).
9. Gutenberg pages extract at medium confidence and will include the Project Gutenberg header/licence block unless trimmed.
10. A Taiwan government host failed certificate verification with one client; the container's CA bundle may reject it too.
