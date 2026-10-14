# Reading quality fixtures

Trimmed copies (scripts, styles, svg and inline attributes removed; text intact) of real pages, kept so the
quality-gate tests in `tests/test_reading_page_quality.py` run offline. Retrieved 2026-10-14.

| File | Source URL | Publisher | Licence | Purpose |
| --- | --- | --- | --- | --- |
| `voa_zh_topic_page_p6197.html` | https://www.voachinese.com/p/6197.html | Voice of America 中文 | US-government work, public domain | positive: topic page, hard `index_page` |
| `voa_zh_player_page_p9647.html` | https://www.voachinese.com/p/9647.html | Voice of America 中文 | US-government work, public domain | positive: player page, hard `media_page` |
| `voa_zh_section_z1741.html` | https://www.voachinese.com/z/1741 | Voice of America 中文 | US-government work, public domain | positive: section page, hard `index_page` |
| `voa_zh_article_8210116.html` | https://www.voachinese.com/a/airport-in-saudi-capital-of-riyadh-is-struck-again-a-day-after-deadly-attack-20261011/8210116.html | Voice of America 中文 | US-government work, public domain | negative: must stay clean. It paraphrases Reuters reporting with attribution; no wire text is copied wholesale. |
| `voa_zh_article_8208799.html` | https://www.voachinese.com/a/un-at-least-200-000-displaced-in-yemen-conflict-as-houthi-rebels-attack-main-airport-20261007/8208799.html | Voice of America 中文 | US-government work, public domain | negative: must stay clean |
| `nasa_news_release.html` | https://www.nasa.gov/news-release/nasa-energy-department-advance-new-era-of-nuclear-powered-exploration/ | NASA | US-government work, public domain | negative: must stay clean |
| `global_voices_article.html` | https://globalvoices.org/2026/09/28/bye-bye-birdie-the-calypso-king-of-the-world-dies-at-91/ | Global Voices | CC BY 3.0, https://creativecommons.org/licenses/by/3.0/ ; author: the byline kept inside the saved page | negative: must stay clean |

The Global Voices file keeps its byline and licence badge in the HTML. Not for use outside these tests.
