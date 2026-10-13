# Orena Vocabulary Generator (n8n)

An n8n workflow that turns a word list into Orena vocabulary cards, checks every card against the repository
schema, and either hands you an import-ready file (**file mode**, the default) or also sends it to a running Orena
(**api mode**). It follows `main`, not the older local workflow: the schema, the admin preview/import contract and the
moderation lifecycle are the repository's (`docs/vocab/`, `writing_coach/vocabulary_entry_format.py`,
`POST /api/admin/vocabulary/preview` and `/import`, D-178).

```
word list -> enrich (Free Dictionary, Tatoeba, CC-CEDICT, CVDICT, Unihan, Make Me a Hanzi)
          -> card -> AI fills only the gaps (optional) -> STRICT validation
          -> local files (ready / rejected / report)   <- always, first
          -> api mode only: preview -> (every row ready?) -> import -> report
```

## Import the workflow

In n8n: **Workflows -> Import from URL** (or *Import from File* with `orena_vocab_generator.json`):

```
https://raw.githubusercontent.com/rallyx-0907/Orena-Coaching-App/<branch>/integrations/n8n/orena_vocab_generator.json
```

The file carries no credentials, no secrets and no instance ids; after importing you attach credentials yourself
(below). It imports inactive. `build_workflow.py` rebuilds it from `src/*.js`; edit the sources, never the JSON.

## File mode (default): needs nothing from Orena

1. **A persistent folder.** The generator writes to `/files/orena` inside the n8n container (change it in the *Config*
   node, `output.dir`, or with `ORENA_VOCAB_OUT_DIR`). The old `/home/node/.n8n-files` is not persistent in a default
   Docker setup. Mount a volume there and let n8n read and write it:

   ```yaml
   services:
     n8n:
       image: docker.n8n.io/n8nio/n8n
       environment:
         - N8N_RESTRICT_FILE_ACCESS_TO=/files        # n8n 2.x only touches files under this path
       volumes:
         - n8n_data:/home/node/.n8n
         - ./orena-files:/files                      # a bind mount of the PARENT; the generator writes to /files/orena
   volumes:
     n8n_data:
   ```

   **Create the output folder yourself, before the first run** - n8n's Read/Write Files node does not create folders
   (a fresh install otherwise fails with `ENOENT realpath '/files/orena'`), and it must be writable by the n8n user (uid 1000):

   ```
   mkdir -p ./orena-files/orena
   ```

   The workflow checks this first: it writes a small `.orena-write-check` marker and, if that fails, stops at once with
   a message naming the folder, before anything is downloaded.

   `docker run`: add `-e N8N_RESTRICT_FILE_ACCESS_TO=/files -v "$PWD/orena-files:/files"` (after the `mkdir`).
2. **Run it.** Open the workflow and press **Execute workflow** (the *Run test* path: two sample words), or edit
   *Test input*. **The word list, batch title and delivery mode (`file` / `api`) are chosen on the *Test input* node (or
   the Form), not in *Config*.** *Config* has only a default `mode`, used when the input item does not set one; the
   input wins, and the run summary and report say where the mode came from (`mode_source`). To use the form, see "The
   form is protected" below.
3. **Import the result.** In Orena Admin, import `/files/orena/<collection>.<hash>.ready.jsonl` (one file per
   language: Orena keeps one language per set). It lands in a set that is **pending review**; you publish it there.

No Orena URL, no Orena credential and no AI key are needed. Without AI, a word is `ready` only if the dictionaries
and the line give it everything (see "Known limitations": English needs the Vietnamese meaning on the line).

### Input format

One word per line: `word - level [- Vietnamese meaning]` (separators: an em or en dash, ` - `, comma, semicolon, tab).
`resilient — C1 — kiên cường`, `森林 — HSK4`. EN levels A1-C2; ZH levels 1-6 or 7-9. The language comes from the
characters.

### What is written (and what is critical)

| File | When | If the write fails |
| --- | --- | --- |
| `<collection>.<hash>.ready.jsonl` (named by its content: same input -> same name and bytes) | before anything is sent | **Critical.** The run stops with an error, and nothing is sent to Orena. |
| `<run>_rejected.json` (each rejected record, its reasons) | before anything is sent | Non-critical: listed in the run summary and the report; the batch is not affected. |
| `<run>_report.json`, `<run>_report.csv` | before the sync, then rewritten with its outcome | Non-critical, same. |
| `zh_lookup.json` (the Chinese dictionary cache, first Chinese run only) | on that run | Required on that path (the run needs the dictionary it just built). |

The run summary (the last node's output) lists the files written, any non-critical write that failed, and the sync
status.

## API mode: sync to Orena after the files are written

Choose **Delivery mode: api** (form) or set it in *Test input*. It still writes the files first, then, per language:

1. **Preview** (`POST /api/admin/vocabulary/preview`, the ready file as `files`).
2. **Strict check of the answer.** The import happens only if every file's preview is a 2xx, `application/json`,
   has exactly the expected structure (`items[0].authored.{language_code, format, rows, counts, warnings}`), and **every
   row is `ready`** with a known `existing` (`new` or `duplicate`), the expected ids in order, and counts that match
   the rows. HTML, an unknown shape, a missing status code, a request error, any `refused`, `conflict` or unknown row
   blocks the **whole batch**: nothing is imported, the local files are untouched, the report says why.
3. **Import** (`POST /api/admin/vocabulary/import`, `metadata` + `duplicates`). Its answer is read the same way: the
   set must be `pending_review` and no source may have failed or conflicted.

`duplicates` defaults to `skip`. Rerunning the same input is safe: the ids are deterministic, the preview reports the
rows as `duplicate`, and the import reports `skipped`. `overwrite` replaces entries only while they belong to no
published set; an entry in a published set is refused by Orena in both modes.

### Settings and credentials

| What | Where |
| --- | --- |
| Orena base URL (origin, e.g. `https://orena.example`) | *Config* node `orena.baseUrl`, or env `ORENA_BASE_URL` |
| Orena credential | n8n credential **Header Auth**, selected on *Orena · Preview* and *Orena · Import* |
| AI endpoint / model (optional) | *Config* `ai.endpoint` / `ai.model`, or env `AI_ENDPOINT` / `AI_MODEL` |
| AI key | n8n credential **Header Auth**, selected on *AI · Fill gaps* |
| Output folder | *Config* `output.dir`, or env `ORENA_VOCAB_OUT_DIR` |

AI is on only when the endpoint is a valid http(s) URL **and** a model is set; a credential alone never turns it on
(the report says `ai.configured: false` and why). AI only fills gaps and every field it writes is tagged `ai-filled:*`.

#### Example: OpenRouter (free tier)

- Endpoint `https://openrouter.ai/api/v1/chat/completions` (*Config* `ai.endpoint`), and a model id in `ai.model`.
- Credential: **Header Auth**, Name exactly `Authorization`, Value `Bearer sk-or-...`. The Name must be only
  `Authorization` - no colon, no spaces; otherwise Node fails with `ERR_INVALID_HTTP_TOKEN`.
- Pick a **non-reasoning** `:free` model that supports `response_format` (JSON mode). A reasoning model can return an
  empty `content` with its answer in `reasoning`; the workflow then accepts only a complete JSON object found there and
  otherwise reports "AI returned no content (reasoning-only model? ...)". An upstream `error.message`/`code` in a 200
  answer is shown in the row warning.
- Free models are rate limited (per minute and per day) and may be busy; the AI node calls two at a time, one second
  apart. A 429 shows as `AI request failed: HTTP 429` or `Provider returned error (code 429)`: wait, or retry the run
  (the files are rewritten identically).

n8n 2.x blocks `$env` inside Code nodes by default (`N8N_BLOCK_ENV_ACCESS_IN_NODE`). Either set it to `false` or put the
values straight into the *Config* node; nothing else in the workflow reads the environment. Secrets are never
environment variables here: they are n8n credentials.

### How the workflow authenticates to Orena

Orena's admin guard is **session based** (`require_admin`, a Google sign-in cookie). Merged on `main`, an unattended
client cannot call the two vocabulary routes except from the machine's own address with sign-in off (D-185), which a
deployed Orena never allows. So today:

- **Local Orena with sign-in off:** the signed-out local admin answers only requests Orena sees as coming from the
  machine itself (D-185, `docs/SECURITY_BOUNDARY.md`). From an n8n container that depends on those Docker rules, so
  try a preview first; if it answers 401/403 the workflow blocks the import and your files are intact.
- **Deployed Orena:** use **file mode** and import in Admin. Pasting a session cookie into a Header Auth credential
  would work briefly and is not a design; do not use it for production.

**Proposed, needs architecture review (D-18X, not approved):** a scoped machine credential for exactly these two
routes (`writing_coach/service_auth.py`). If it is merged and enabled:

```
# 1. generate a token: 32 random bytes (never a typed passphrase)
python -c "import secrets; print(secrets.token_urlsafe(32))"
# 2. hash it; only the digest goes on the server
python -c "import getpass,hashlib;print(hashlib.sha256(getpass.getpass('token: ').encode()).hexdigest())"
# set on the Orena server:  VOCAB_INGEST_TOKEN_SHA256=<that hex digest>
# in n8n: Header Auth credential, Name "Authorization", Value "Bearer <the token>"
```

The server stores only the digest, compares in constant time, logs nothing, and the token works on
`POST /api/admin/vocabulary/preview` and `/import` only (every other route, method and path answers it as anonymous).
For this caller Orena **always** imports into a `pending_review` set, whatever the file format or metadata: `publish`,
`publication_attested` and the cleared-rights auto-publish rule are ignored, and `duplicates=overwrite` is refused
with a 422 (the workflow therefore always uses `skip` in api mode).

Rotation: put both digests in the variable, comma-separated (`old,new`), deploy, move n8n to the new token, then remove
the old digest and deploy again. Revocation is the same removal. Residuals (D-18X): every service import appears under
one fixed actor (`service:vocabulary-ingest`); wrong tokens (401) are not throttled, so the token must be high-entropy;
a session administrator whose browser sends a stray `Authorization: Bearer` header to these two routes gets a 401; the
service request skips the per-user database initialiser, which these routes do not use (the vocabulary catalogue is
global on PostgreSQL and in the SQLite dev adapter, and the tests run them on SQLite).

## Validation: what makes a record `ready`

Only a record that passes **all** of this goes to a ready file. Anything else goes to `rejected` with the reasons; it is
never downgraded to a draft and carried on.

- the repo schema (`docs/vocab/vocab_entry.schema.json`, embedded verbatim and interpreted by the workflow's validator):
  required fields, enums, CEFR/HSK scale and value, non-empty `pos`, 1-4 examples, no unknown or extra field;
- every meaning has a Vietnamese text; every example has `translation_vi`;
- highlight integrity: `highlight.match` is in the sentence (at least `occurrence` times); `reading_highlight.match`
  is in the `reading`;
- English: `en.ipa` has `uk` and/or `us`, each slash-delimited (`/rɪˈzɪliənt/`);
- Chinese: `zh.pinyin` is tone-marked pinyin; `zh.chars` spell the headword exactly, one pinyin per character, and the
  characters' pinyin joined equals `zh.pinyin`;
- the id is the deterministic id of the headword (`en:<slug>`, `zh-Hans:<hex code points>`);
- `status` is `draft` (the generator never publishes; Orena ignores a file's status anyway).

There is deliberately no `en.etymology_en` any more: the schema on `main` has no such field, and Orena refuses a row
that has one. The test `tests/test_n8n_vocab_workflow.py` and `scripts/test_n8n_vocab_workflow.mjs` fail if the
embedded schema stops equalling the repo's, if the workflow's validator disagrees with `jsonschema` on the shared
cases, or if the committed JSON is not what `build_workflow.py` builds.

### What the files claim

- **Level source:** `operator-supplied CEFR/HSK level (not checked against a word list)`. Nothing in the pipeline
  verifies a level; the README of `docs/vocab/` already notes that HSK 2.0 and 3.0 differ.
- **`rights_status: unknown`, `completeness: partial`** (editable in *Config*). The sources carry attribution /
  share-alike terms (Wiktionary via Free Dictionary, Tatoeba, CC-CEDICT, CVDICT) and no human has cleared the batch.
- **`tags`** record provenance: `gen:n8n-vocab-generator`, `src:<source>` for each dictionary used, and
  `ai-filled:<field>` for anything the AI wrote, so a reviewer can find it. The audio URL of the dictionary is not
  copied (the card uses text-to-speech); no etymology is invented.

## Sources (reviewed against the current card)

| Source | Gives | Notes |
| --- | --- | --- |
| Free Dictionary API (`dictionaryapi.dev`) | EN IPA (uk/us by audio file name), part of speech, English definition, synonyms/antonyms, example sentences | Untagged IPA is not used unless `untaggedIpaAs` is set. No Vietnamese. |
| Tatoeba (`api_v0/search`) | example sentences with a Vietnamese translation (EN and ZH) | CC BY 2.0 FR; sentences without a Vietnamese translation are dropped unless AI fills the translation. |
| CC-CEDICT (MDBG export) | ZH pinyin, English glosses, classifiers, sentence pinyin | No part of speech: inferred only from "to ..." / classifier / `CL:` and flagged as a warning. |
| CVDICT | ZH Vietnamese glosses | |
| Unihan | stroke count, Kangxi radical, Hán-Việt (`kVietnamese`), radical names | First reading only. |
| Make Me a Hanzi | character decomposition for `components` | |

All six URLs were checked reachable when this was written; they are `Config` settings, not code.

## The form is protected

The **Form** trigger is a webhook. It is set to **Basic Auth**: attach an *HTTP Basic Auth* credential before activating
the workflow, and check that the form URL asks for a password before you share it. Whatever the form sends:

- `overwrite` from the form is **ignored** (forced to `skip`) unless you set `allowFormOverwrite` in *Config* or
  `ORENA_VOCAB_ALLOW_FORM_OVERWRITE=true`. Only the *Run test* path (an operator in the editor) can choose it, and only in file mode: api mode always skips.
- `api` mode from the form still needs the Orena URL and credential, and still only creates `pending_review` sets.
- The output folder and Orena URL cannot be set from the form.

## Known limitations

- **Not run end to end in n8n here.** What is verified: the workflow's Code nodes run in a Node vm with a mocked n8n
  runtime and recorded HTTP fixtures (`scripts/test_n8n_vocab_workflow.mjs`), and the files they generate are accepted
  by the real preview/import routes in a Python test. The HTTP/file nodes themselves were not executed. The strict
  readers assume the HTTP Request node's full-response output (`statusCode`, `headers`, `body`) and the Code node's
  `this.helpers.prepareBinaryData`; if your n8n version differs the failure is closed (the import is blocked), and the
  fix is in `src/lib_sync.js` / `src/build_files.js`.
- **English needs the Vietnamese meaning.** No deterministic source gives an English word's Vietnamese meaning. Put it
  on the line (`resilient — C1 — kiên cường`) or configure the AI fill; otherwise the word is `rejected`.
- **The id is an editorial handle.** Orena identifies an entry by (language, term, **first** part of speech). If a later
  run picks a different first part of speech (the dictionary changed, or the AI filled it), Orena sees a second entry
  for the word, not a duplicate (the preview warns "another entry for this word is stored").
- The Chinese dictionary build is slow the first time (it downloads four sources) and needs the `zh_lookup.json`
  cache to be writable.
- HSK level 7-9 is one band in the schema; a word's level is never verified against HSK 3.0.
- Tatoeba and the dictionaries are rate-limited; large batches are fetched 3 at a time, one second apart.
