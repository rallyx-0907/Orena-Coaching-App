# Third-party notices

Orena includes, or is built on, the third-party data and software below. Learners see the data
credits in the app under Settings → Plan & privacy → Licences and data sources (`GET /api/licences`,
which reads the same registry as this file: `writing_coach/licences.py`). Per-item credits that live
with content - each stored word recording (Wikimedia Commons file, author, licence), each
listening source, each registered reading source and each book - are listed there from the data
itself, not here.

## Data and bundled assets

| Id | What | Licence | Where in the repository | Attribution |
| --- | --- | --- | --- | --- |
| `cc-cedict` | CC-CEDICT Chinese-English dictionary (2026-10-03 export) | CC BY-SA 4.0 | `writing_coach/languages/chinese/lexicon_data/` (repacked; licence text and modification notice there); also `writing_coach/languages/chinese/script_chars.json`, a list of Simplified-only and Traditional-only characters derived from its headwords by `scripts/build_chinese_script_table.py` (CC BY-SA 4.0, release 2026-10-03) | MDBG and CC-CEDICT contributors; CEDICT © 1997, 1998 Paul Andrew Denisowski |
| `unihan` | Unicode Unihan database 18.0.0 (`kMandarin`, `kVietnamese`, `kDefinition`) | Unicode License v3 | same folder | © Unicode, Inc. |
| `make-me-a-hanzi` | Hanzi stroke data (hanzi-writer-data 2.0.1) | Arphic Public License | `writing_coach/languages/chinese/stroke_data/` | Shaunak Kishore (Make Me a Hanzi); Arphic Technology Co., Ltd. |
| `open-dsl-dict` | open-dsl-dict `en-vi-enwiktionary` (from English Wiktionary translation tables, 2015) | CC BY-SA 3.0 / GFDL | `writing_coach/localization_data/vi_glosses.json.gz` (subset) | Wiktionary contributors; Open DSL Dictionary Project |
| `wiktionary-vi` | Vietnamese Wiktionary via kaikki.org (Wiktextract extraction of 2026-09-28) | CC BY-SA 4.0 (also GFDL) | same file (subset) | Wiktionary contributors; Tatu Ylonen's Wiktextract (kaikki.org) |
| `lucide` | Lucide icons, lucide-static 0.525.0 | ISC | `static/orena/kit/icons.js` | Lucide contributors |
| `google-fonts` | Fredoka, Outfit, Plus Jakarta Sans, Literata, JetBrains Mono, Noto Sans SC, Noto Serif SC | SIL Open Font License 1.1 | `static/orena/fonts/` (self-hosted `woff2` files, fetched once by `scripts/fetch_self_hosted_fonts.py`; each family's licence text in `static/orena/fonts/licences/`) | The fonts' authors |
| `nltk-tagger` | NLTK averaged perceptron tagger (English part-of-speech data) | Apache 2.0 | installed at build time | NLTK Project |
| `cefrj-vocabulary` | CEFR-J Vocabulary Profile 1.5, English word levels A1-B2 (single words, lowest level kept) | Free for research and commercial use with citation (TUFS terms of use) | `writing_coach/languages/english/level_words_cefrj.json`, built by `scripts/build_reading_level_tables.py`; read by `writing_coach/reading_level.py` | Tono Laboratory, Tokyo University of Foreign Studies (TUFS); The CEFR-J Wordlist Version 1.5, compiled by Yukio Tono (http://www.cefr-j.org/download.html) |
| `octanove-vocabulary` | Octanove Vocabulary Profile C1/C2 1.0, English word levels C1-C2 | CC BY-SA 4.0 - **ShareAlike**: this file, and any adaptation of it, stays under CC BY-SA 4.0. It is a separate data file so the licence does not extend to the CEFR-J table or to Orena's code | `writing_coach/languages/english/level_words_octanove_c1c2.json` (single words only, derived by the same script; licence text: `writing_coach/languages/english/CC-BY-SA-4.0.txt`) | Octanove Labs, distributed with the CEFR-J datasets by Open Language Profiles |
| `hsk30-vocabulary` | HSK 3.0 word and character levels (10,959 pure-Hanzi words and 3,000 characters of the 11,092-entry source list; only each entry's level is kept) | MIT (ivankra/hsk30). Its README notes that the original standard is a PRC Ministry of Education publication and that the copyright claim on the data is questionable | `writing_coach/languages/chinese/level_words_hsk30.json`, built by `scripts/build_reading_level_tables.py`; read by `writing_coach/reading_level.py` | Ivan Krasilnikov and Shawky, https://github.com/ivankra/hsk30 (commit 4ff9e391); derived from the PRC Ministry of Education HSK 3.0 standard |
| `cmudict` | CMUdict English pronunciations (125,923 headwords, first pronunciation, converted from ARPAbet to General American IPA) | BSD-style: redistribution and use, with or without modification, are permitted provided the copyright notice, the conditions and the disclaimer are retained (source) or reproduced (binary); commercial use is allowed. The licence text is bundled | `writing_coach/languages/english/cmudict_ipa.json.gz`, built by `scripts/build_english_ipa_table.py`; read by `writing_coach/languages/english/ipa.py`; licence text in `writing_coach/languages/english/CMUDICT-LICENSE.txt` | Copyright (C) 1993-2015 Carnegie Mellon University. All rights reserved. https://github.com/cmusphinx/cmudict (commit 74790861) |

Data under CC BY-SA remains under CC BY-SA after Orena's repackaging (share-alike); the repackaged
files are published with their licence texts and modification notices.

## Software

Runtime Python dependencies (`requirements.txt`), each under its own licence: FastAPI (MIT),
Starlette (BSD-3-Clause), Uvicorn (BSD-3-Clause), Pydantic (MIT), jieba (MIT), NLTK (Apache 2.0),
pypinyin (MIT), requests (Apache 2.0), yt-dlp (Unlicense), youtube-transcript-api (MIT),
google-auth and google-auth-oauthlib (Apache 2.0), itsdangerous (BSD-3-Clause), SQLAlchemy (MIT),
Alembic (MIT), psycopg (LGPL-3.0, used as an unmodified library), python-multipart (Apache 2.0),
httpx (BSD-3-Clause), cryptography (Apache 2.0 or BSD-3-Clause).

Browser software served with the public pages (Landing, Terms, Privacy): React 18.3.1 and ReactDOM 18.3.1 (MIT,
copyright Meta Platforms, Inc. and affiliates), the unmodified npm production builds, vendored in
`static/orena/public/vendor/` with their licence texts (`LICENSE.react.txt`, `LICENSE.react-dom.txt`) and verified
against the npm registry's integrity hashes. The design's page runtime (`static/orena/public/support.js`) is the
design project's own file.

Browser software served inside the learner app: qrcode-generator 1.4.4 (MIT, copyright (c) 2009 Kazuhiko Arase), vendored in `static/orena/vendor/qrcode-generator/qrcode.js` with its licence text (`LICENSE.qrcode-generator`). It is the upstream file with only an ES-module export added, and draws the payment QR of Credits locally (no network image, no third-party request). New dependency recorded in `UI_BACKEND_GAPS.md` CT-8.

The application image installs FFmpeg (`ffmpeg`, `ffprobe`) from Debian packages (LGPL-2.1+ /
GPL-2+ depending on build); Orena invokes it as a separate program and does not link it.

Test fixtures only (not shipped in the image, not served): `tests/fixtures/level_gold/zh/` holds Tatoeba sentences (CC BY 2.0 FR, sentence ids recorded per item) and Chinese Wikipedia lead paragraphs (CC BY-SA 4.0, page revision ids recorded per item; ShareAlike applies to those files only). See the fixture README for sources.
