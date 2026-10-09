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
| `cc-cedict` | CC-CEDICT Chinese-English dictionary (2026-10-03 export) | CC BY-SA 4.0 | `writing_coach/languages/chinese/lexicon_data/` (repacked; licence text and modification notice there) | MDBG and CC-CEDICT contributors; CEDICT © 1997, 1998 Paul Andrew Denisowski |
| `unihan` | Unicode Unihan database 18.0.0 (`kMandarin`, `kVietnamese`, `kDefinition`) | Unicode License v3 | same folder | © Unicode, Inc. |
| `make-me-a-hanzi` | Hanzi stroke data (hanzi-writer-data 2.0.1) | Arphic Public License | `writing_coach/languages/chinese/stroke_data/` | Shaunak Kishore (Make Me a Hanzi); Arphic Technology Co., Ltd. |
| `open-dsl-dict` | open-dsl-dict `en-vi-enwiktionary` (from English Wiktionary translation tables, 2015) | CC BY-SA 3.0 / GFDL | `writing_coach/localization_data/vi_glosses.json.gz` (subset) | Wiktionary contributors; Open DSL Dictionary Project |
| `wiktionary-vi` | Vietnamese Wiktionary via kaikki.org (Wiktextract extraction of 2026-09-28) | CC BY-SA 4.0 (also GFDL) | same file (subset) | Wiktionary contributors; Tatu Ylonen's Wiktextract (kaikki.org) |
| `lucide` | Lucide icons, lucide-static 0.525.0 | ISC | `static/orena/kit/icons.js` | Lucide contributors |
| `google-fonts` | Fredoka, Outfit, Plus Jakarta Sans, Literata, JetBrains Mono, Noto Sans SC, Noto Serif SC (and the old UI's Nunito, Nunito Sans, DM Mono, Roboto Mono, Noto Serif) | SIL Open Font License 1.1 | loaded from Google Fonts | The fonts' authors |
| `nltk-tagger` | NLTK averaged perceptron tagger (English part-of-speech data) | Apache 2.0 | installed at build time | NLTK Project |

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

The application image installs FFmpeg (`ffmpeg`, `ffprobe`) from Debian packages (LGPL-2.1+ /
GPL-2+ depending on build); Orena invokes it as a separate program and does not link it.
