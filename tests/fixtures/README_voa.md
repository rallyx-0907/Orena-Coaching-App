# VOA fixtures (trimmed real pages)

Each file keeps the page title, canonical link, Open Graph and JSON-LD metadata and the `#article-content`
block of the original page, and nothing else. Used by `tests/test_reading_rights_refinement.py`.
Licence: VOA staff-produced content is a work of the US government (public domain); the wire-derived pages
are VOA rewrites that name an agency, which is exactly what the test shows is not asserted as public domain.
Fetched 2026-10-14. Purpose of each is the rights refinement of D-193; they are not learner content.

| File | Source URL | Publisher | Purpose |
| --- | --- | --- | --- |
| `voa_zh/staff_article.html` | https://www.voachinese.com/a/house-china-select-committee-calls-for-tighter-security-on-federally-funded-research-20261013/8210904.html | VOA 中文 | staff byline (李逸华), no credit line: rights kept |
| `voa_zh/wire_derived_article.html` | https://www.voachinese.com/a/8007815.html | VOA 中文 | ends "(此文依据了法新社的报道。)": withheld |
| `voa_zh/wire_derived_article_ap.html` | https://www.voachinese.com/a/7993803.html | VOA 中文 | ends "(本文依据了美联社的报道。)": withheld |
| `voa_en/wire_adapted_article.html` | https://learningenglish.voanews.com/a/france-sets-new-plasma-record-in-hunt-for-nuclear-fusion/7983265.html | VOA Learning English | "adapted this story ... based on reporting from Agence France-Presse": withheld |
