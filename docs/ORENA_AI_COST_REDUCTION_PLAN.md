# Orena — AI cost reduction plan

**Status:** APPROVED 2026-08-26. **P0 and P2 are implemented** (D-023, D-024);
P1, P2b, P3 and P4 remain to do.
**Written:** 2026-08-26, against `claude/work`.
**Goal:** stop paying a language model to do work that a dataset or a free API
already does exactly, so the AI budget is spent where a model is genuinely the
only thing that can do the job.

Every number below was measured in this repository or downloaded and counted
while writing this document. Nothing here is an estimate dressed as a fact.

## 0. Correction — what "AI cost" actually is here

This plan was first written in tokens. Measured afterwards, that framing was
wrong, and the truth is more urgent.

`platform_settings` holds **no persisted provider selection**, so
`active_selection()` falls through to `_default_selection()`, which returns
Ollama. `OPENAI_API_KEY` and `DEEPSEEK_API_KEY` are absent from the environment.
**The product runs entirely on a local `qwen3:8b` today, and the money cost is
zero.**

What it costs instead, measured against the running Ollama with the real
dictionary prompt:

```
one Chinese word lookup · qwen3:8b · 37.1 s · 808 tokens out · 21.8 tok/s
```

**Thirty-seven seconds to look up one word.** That is the "chậm chạp" this work
is really about. Two consequences:

- Replacing the dictionary with a dataset is not a saving of pennies. It takes a
  37-second wait to a sub-10 ms lookup. That is a different product, not a
  cheaper one.
- It does not survive the mobile app. One 8B model serialises requests, so two
  learners tapping words at the same time wait twice as long. The current
  architecture holds only because there is one user on one machine.

Every token figure in §1 still stands — they are what the prompts ask for. Read
them as *time* rather than as *money*, and as money only for the day a cloud
provider is configured or the load outgrows one GPU.

## 1. Where the tokens go today

Nine provider-backed capabilities exist. This is what each one actually costs
and what triggers it.

| Capability | Call site | Output budget | Fires when | Volume |
| --- | --- | --- | --- | --- |
| `learner_dictionary` (zh) | `app.py:1052` | **1 100** | every Chinese word looked up | **very high** |
| `learner_translation` | `app.py:1343` | **550** | every inline translation | **very high** |
| `writing_linguistic` | `becoming_linguistics.py:217` | **2 800** | Review parts-of-speech lens | per essay |
| `writing_evaluator` | `app.py:324` | 2 200 | essay submitted | per submission |
| `reading_generator` | `becoming_reading.py:530` | 2 200 | reading passage generated | per passage |
| `writing_improver` | `app.py:903` | 1 800 | Improve / polish pressed | on demand |
| media `/explain` | `media_interaction.py:349` | 1 500 | learner presses Explain | on demand |
| `learner_dictionary` (en) | `app.py:965` | 650 | only when dictionaryapi.dev misses | rare |
| `writing_task_generator` | `app.py:749` | 500 | task generated | per task |
| `grammar_lesson_generator` | — | — | never — R5 static KB, runtime AI `0` | none |
| `reading_evaluator` | — | — | deterministic by design | none |

Two things are already right and are the model to copy:

- **Grammar** carries 508 lessons with **zero** runtime AI. Static KB, shared
  renderer, stable concept IDs.
- **Transcript annotation** (`/api/media/annotate`) segments and tags every
  visible subtitle with jieba + pypinyin + NLTK. No provider call, no latency.

The waste is concentrated in the top three rows. A learner watching one video
and tapping thirty words spends **33 000 output tokens on dictionary lookups
alone** — for facts that have been written down in free dictionaries for years.

## 2. Two rules

1. **If a dataset or free API answers it exactly, the model never sees it.**
   Word senses, pinyin, stroke order, part of speech, segmentation, and
   dictionary-form translation are all lookup problems.
2. **AI is for judgement and for questions the learner asked.** Evaluating a
   learner's own sentences, rewriting their text, explaining why a phrase works
   in this context — a model is genuinely the only thing that can do these, and
   the learner pressed a button to get them.

## 3. The work, ordered by tokens removed per unit of effort

### P0 — `writing_linguistic` → the annotator this repo already has

**DONE.** Removed 2 800 output tokens per essay. Decision Log D-023.

The tagger now lives in `writing_coach/linguistic_annotation.py`, shared by the
Review lens and the Listening transcript, and `writing_linguistic` is
deterministic in the catalog. Measured against the AI annotations cached in
eleven real learner essays: **92% identical spans, 82% label agreement on those
spans**, and 67 of the 259 disagreements are the local tagger being more
specific. Neither tagger has a gold standard here, so this is a change of engine
rather than a measured loss — and Writing and Listening now agree with each
other, which they did not before.

One wart is recorded rather than fixed: a sentence-final word arrives with its
period attached, because `TreebankWordTokenizer` only splits it after sentence
tokenization. That is the behaviour the Listening transcript has always had, and
changing it would move every token boundary on a CLOSED M1 surface, so it needs
its own change.

`becoming_linguistics.py` asks a model to segment text and tag parts of speech.
`media_interaction.py:163-230` already does exactly that, deterministically:
NLTK `pos_tag` for English, `jieba.posseg` for Chinese, with contextual pinyin
from pypinyin. Both are already in `requirements.txt`.

The local tagger's label set is a **superset** of the eleven labels the prompt
asks for — it also distinguishes `proper_noun`, `classifier` and `interjection`,
which matter for Chinese and which the prompt collapses into `other`.

So this is not a new capability. It is deleting one of two implementations of
the same thing and keeping the one that is free, instant, and more precise.

- Extract the annotator out of `media_interaction.py` into a shared module both
  callers use, so Writing and Listening cannot drift apart.
- `writing_linguistic` becomes deterministic in the capability catalog, the way
  `reading_evaluator` already is.
- Keep the existing annotation cache and the literal-span validation.

**Risk:** the AI tagger may currently produce friendlier groupings on messy
learner text. Mitigation: build EN/ZH fixtures from real stored essays and
compare span-by-span before switching.

### P1 — Chinese dictionary → CC-CEDICT + Unihan

**Effort: medium. Removes 1 100 output tokens per lookup — the largest single
line in the budget.**

Downloaded and counted while writing this:

| Source | Size | Contents | Licence |
| --- | --- | --- | --- |
| CC-CEDICT | 3.97 MB gz / 9.7 MB raw | **124 934 entries**, 121 174 unique simplified headwords: traditional, simplified, pinyin, English senses | CC BY-SA 4.0 |
| Unihan | 8.5 MB zip → **3.07 MB** trimmed | per character: `kMandarin` 44 348, `kDefinition` 23 285, **`kVietnamese` 8 306**, plus radical/stroke counts and simplified↔traditional variants | Unicode licence |

Coverage check against the learner's own lookup history — every Chinese word
this account has ever looked up is present in CC-CEDICT:

```
舒服 → [shu1 fu5] /comfortable/feeling well/
学习 → [xue2 xi2] /to learn; to study/
清晨 → [qing1 chen2] /early morning/
怎么样 → [zen3 me5 yang4] /how?/how about?/how was it?/
叫醒 → [jiao4 xing3] /to awaken; to wake sb up; to rouse/
进度 → [jin4 du4] /rate of progress/
服   → [fu2] /clothes/dress/to serve/to obey/…
```

Where each field of the current Chinese entry would come from:

| Field | Today | Proposed |
| --- | --- | --- |
| `word`, `traditional` | AI | CC-CEDICT |
| `phonetic` (pinyin) | AI | CC-CEDICT numbered pinyin → tone marks, deterministic |
| `definitions` | AI | CC-CEDICT senses |
| `part_of_speech` | AI | jieba `posseg` + the existing `_chinese_pos` mapping |
| `characters[]` breakdown | AI | CC-CEDICT single-character entries + Unihan `kDefinition` |
| **Hán-Việt reading** | *not offered at all* | Unihan `kVietnamese` — a real gain for Vietnamese learners |
| `translation_vi` | AI | precomputed at build time — see below |

**Vietnamese glosses are precomputed, not translated at runtime.** The decision
taken is zero runtime cost and instant response, which rules out calling any
translator while the learner waits. So the Vietnamese column is built once, into
the vendored pack, and runtime becomes a pure lookup — the same shape as the
stroke pack.

Two tiers, because quality and cost pull in opposite directions across 121k
entries:

- **Tier 1 — the vocabulary learners actually meet** (HSK 1-9 plus common words,
  on the order of 20-30k entries). Translated once through Groq's free tier,
  batched, and reviewed by sampling. Measured recipe: `openai/gpt-oss-120b` with
  `reasoning_effort: "low"`, twenty entries a call, **each entry given its
  CC-CEDICT English senses as context**. That came back in 1.4 s at ~16 output
  tokens an entry, so 30 000 entries is roughly 1 500 requests and 500 k tokens —
  inside the free quota spread over a day or two of background running.
- **Tier 2 — the long tail.** Ships with the English sense and the Hán-Việt
  reading. If a learner opens one, the existing on-demand path fills it in and
  the 30-day cache keeps it.

**The risk is real and was measured.** Asked to translate the bare character
`服`, a small model returned *"điện, mặc"* — the first word is meaningless. Given
the CC-CEDICT senses `/clothes; to serve; to obey/` alongside, a larger model
returned *"quần áo; phục vụ; tuân theo"*, which is right. Context is the whole
game, and it is free. Tier 1 is small enough to sample before it ships; anything
that fails review ships as Tier 2 rather than shipping a wrong meaning.

Packaging follows the pattern the stroke-order pack already established:
vendored under `writing_coach/languages/chinese/`, a rebuild script, a digest
in the index, and the licence text carried unaltered. CC BY-SA 4.0 requires
attribution and share-alike on the data — the learner-facing note must credit
CC-CEDICT the way the stroke note credits Make Me a Hanzi.

**AI keeps exactly one job here:** a word CC-CEDICT does not carry (slang, names,
very new coinages). That call stays, behind the existing 30-day cache, and its
result is labelled as model-generated rather than dictionary-sourced.

### P2 — Groq becomes the translation default; local stays an explicit backup

**DONE.** Decision Log D-024.

Verified end to end against the real API: a three-segment Chinese batch came back
in **1.43 s** with natural Vietnamese, and the quota headers were captured. The
engine is chosen once at startup by `MEDIA_TRANSLATION_PROVIDER`, and Groq is
also registered in the AI provider catalog so capabilities can be routed to it.

**One correction to what this plan said.** It specified
`reasoning_effort: "low"`. Measurement afterwards showed that is wrong to encode:
under `response_format: json_object` it is unnecessary, and the other Groq models
reject it outright with HTTP 400 — `qwen/qwen3.6-27b` accepts only
`none`/`default`, and `groq/compound` refuses it entirely. So the request sets
the JSON response format, which is what actually prevents the empty-string
answer, and sends no reasoning parameter at all.

The direction taken is **no local model as the production default** — production
has no GPU — with **Groq for translation**, and the local translator **kept as an
explicit backup** for a future VPS.

- `learner_translation` and the media translation boundary both default to Groq.
- `services/local_translation` is **repaired and kept, not retired**. It is the
  fallback if Groq is unreachable, if the account is out of quota, or if a
  deployment must run without any external dependency. Both faults still need
  fixing: `protobuf` is missing from its requirements (already fixed on this
  branch), and three of its four models were never provisioned.

**This extends D-021 rather than superseding it.** D-021 established a
provider-neutral translation boundary whose default was the local service; what
changes is which provider is default, not the boundary. A new Decision Log entry
records the change of default and the backup role.

**One invariant applies here and must not be bent.** `ARCHITECTURE_INVARIANTS.md`
states there is no provider-to-provider fallback and no silent failover.
"Backup" therefore means **an explicit configured selection an operator makes**,
visible in the admin surface — not an automatic switch the runtime performs when
a request fails. A silent switch would change a learner's results without anyone
knowing which engine produced them.

#### What was measured on the account's own key

| Model | Time | Output tokens | Vietnamese |
| --- | --- | --- | --- |
| `openai/gpt-oss-120b` (`reasoning_effort: low`) | **1.00 s** | **138** | correct, including the hard case |
| `qwen/qwen3.6-27b` | 3.40 s | 1 471 | best wording, ten times the tokens |
| `groq/compound` | 2.92 s | 737 | correct |
| `openai/gpt-oss-20b` (`reasoning_effort: low`) | 0.73 s | 29 | **unreliable — do not use** |

Against 37 seconds locally, the working models answer in **one to three
seconds**. `openai/gpt-oss-120b` at `reasoning_effort: low` is the pick: fastest
of the reliable three and by far the cheapest in tokens.

#### Three findings that would otherwise be discovered in production

**A reasoning model returns an empty string, not an error, when the token budget
is too small.** `gpt-oss-20b` with `max_tokens=120` spent all 120 tokens
reasoning and returned `""`. The same call with `reasoning_effort: "low"`
answered in 29 tokens. Any Groq integration must set `reasoning_effort`
explicitly and treat empty content as a failure to retry, not as a valid answer.

**Quality collapses without context.** Asked to translate the bare character
`服`, `gpt-oss-20b` produced *"điện, mặc"* — the first word is meaningless.
Handed the CC-CEDICT senses `/clothes; to serve; to obey/`, `gpt-oss-120b`
returned *"quần áo; phục vụ; tuân theo"*, which is right. **Never send a bare
headword. Always send the dictionary senses as context.** This is the single
biggest quality lever and it costs nothing.

**Cloudflare, not Groq, rejects some clients.** A request with the default
`Python-urllib` User-Agent is refused with HTTP 403 and Cloudflare error 1010.
The `requests` default User-Agent passes (verified: HTTP 200), so the existing
ASR adapter in `speech_asr.py` is fine — but any new client must be checked
rather than assumed.

#### The rate limit is the real design constraint

Read from the live response headers on this key:

```
x-ratelimit-limit-requests   1000
x-ratelimit-limit-tokens     8000     (per minute)
```

**These are per API key, which means per product, not per learner.** Groq's free
tier is a **development and testing budget**, not the production plan. The
production answer is not to design around 1 000 requests a day — it is to make
the budget **visible before it bites**:

- the admin surface reports quota consumed and remaining, read from the
  `x-ratelimit-*` headers the API already returns on every call;
- it raises an alert as the ceiling approaches, rather than after learners start
  seeing failures;
- from there an operator either raises the credit or selects a different model,
  which the per-capability control plane already expresses.

That said, quota headroom does not change what belongs on which path. Even on a
paid tier, sending a request for every word a learner taps is the wrong shape —
it is slower than a lookup and it costs money to answer a question a dictionary
answered for free. So the routing below stands on its own merits:

- **Groq should not serve a per-tap action.** Dictionary lookups go to the
  dataset (P1) — faster than any API can be, and free at any tier.
- **Groq is right for the one-time precompute.** Batched 20 words to a call,
  measured at 330 output tokens and 1.42 s, 30 000 entries is ~1 500 requests —
  about two days of background running inside the free quota, or one day at 50
  per call. Total tokens are on the order of 840 k, well inside the per-minute
  ceiling spread over that window.
- **Groq is right for on-demand explanation**, where the learner presses a
  button and volume is naturally low.
- **Inline translate needs a cache and a ceiling.** Cache by source hash, and
  decide what the product does when the daily quota is gone — degrade to the
  dataset gloss, not to a spinner.

Limits are per model, so putting explanation and translation on different models
buys separate buckets. Useful during development; not a substitute for the
admin-side quota reporting above.

### P2b — the meaning *here*, resolved from the phrase around the word

**Effort: small on top of P1 and P2. This is the feature the earlier findings
were pointing at.**

Chinese meaning is contextual, and the measurement already showed what happens
without context: the bare character `服` came back as *"điện, mặc"*. The fix is
not a better model — it is to stop asking the question without context.

**Send the word together with the phrase it appeared in, and ask which of the
dictionary's own senses applies.**

The context is already available at every call site, for free:

| Surface | Where the containing phrase comes from |
| --- | --- |
| Listening | the transcript segment the token sits in — already carried as `data-segment-id` |
| Writing | the sentence around the learner's selection in the editor |
| Review | the sentence the evidence fragment was quoted from |

What the learner sees becomes two layers, and only the second one costs
anything:

1. **All the dictionary senses**, from CC-CEDICT — free, instant, always shown.
2. **"Nghĩa ở đây"** — one line naming which of those senses is in play in this
   sentence, and why.

This shape has three properties worth having:

- **The model's job becomes selection, not generation.** Handed four senses and
  one sentence, "which applies" is a few output tokens, fast and hard to get
  wrong — where "what does 服 mean" invited the wrong answer.
- **It cannot invent a meaning.** The answer is constrained to senses the
  dictionary carries, the same honesty rule the stroke data follows. If none fit,
  the honest answer is to say so, not to make one up.
- **It degrades cleanly.** With no quota, no network, or no context available,
  layer 1 still stands on its own and the entry is still useful. Layer 2 is
  additive, so it can be lazy, cached by (word + context hash), or turned off
  entirely without breaking the screen.

### P3 — English dictionary: close the AI fallback

**Effort: small. Removes 650 output tokens on the rare miss.**

English already does the right thing — free `dictionaryapi.dev` first, AI only
on a miss. Closing the gap entirely means adding an offline source (WordNet via
NLTK, already a dependency, or a Wiktionary extract) so a miss degrades to a
second dataset rather than to a model.

Lowest priority of the four: the fallback rarely fires.

### P4 — `writing_task_generator` → a curated bank

**Effort: small–medium. Removes 500 output tokens per task.**

The capability already permits `DETERMINISTIC_FALLBACK`. A writing prompt at a
given level, topic and length is a content problem, not a reasoning problem —
R5 solved the identical problem for Grammar with a static KB of 508 lessons.

A bank of prompts per level × task type × topic, with deterministic selection
and no repeats inside a session, removes the call entirely. Where genuine
novelty is wanted — a topic the bank does not cover — the **smallest available
model** is the right tool: writing a prompt is not the job that needs the good
model. Setting a small model on `writing_task_generator` while
`writing_evaluator` keeps the strong one is exactly what the capability control
plane exists to express, since provider and model are configured per capability.

Grading is where a strong model earns its cost. Setting a prompt is not.

### Deliberately keeping AI

| Capability | Why a model is the right tool |
| --- | --- |
| `writing_evaluator` | Judges the learner's own sentences against a rubric and must quote their exact words. No dataset can do this. |
| `writing_improver` | Rewrites the learner's text while preserving their voice. |
| `reading_generator` | Produces new level-appropriate passages. A corpus could supplement it, not replace it. |
| media `/explain` | Contextual explanation the learner explicitly asked for. Already opt-in — this is the shape every other AI feature should move toward. |

## 4. What this adds up to

At 21.8 tok/s on the local model, the token figures convert straight into
waiting: a 1 100-token dictionary entry is roughly **37 seconds**, and a
1 500-token explanation roughly **70**. Per learner session, on the two
highest-volume paths:

- **Watching a video and tapping 30 words:** 30 × 1 100 = 33 000 output tokens
  today → **0** after P1.
- **Translating 10 selections:** 10 × 550 = 5 500 tokens and ~6 minutes of
  waiting today → about **10 seconds** after P2, on someone else's hardware.
- **Reviewing one essay's POS lens:** 2 800 → **0** after P0.

What remains is submission-time evaluation, on-demand improvement and
on-demand explanation — all of them things the learner asked for and a model
must do.

Repository weight added: ~4 MB (CC-CEDICT) + ~3 MB (the Unihan subset),
alongside the 14 MB stroke pack already committed. One-time and offline.

Be clear about what changes and what does not: the dictionary and the stroke
data stop depending on anything outside the server, while translation and
explanation **become** a third-party runtime dependency on Groq, bounded by a
free-tier quota shared across the whole product. That is a deliberate trade — a
one-second answer that can run out, in place of a thirty-seven-second answer
that cannot.

## 5. Sequencing

```
P0   writing_linguistic → local tagger        small, no new data, no provider
P2   translation → Groq default               unblocks P1's precompute
P1   Chinese dictionary → CC-CEDICT + Unihan  the big one; precompute runs on P2
P2b  contextual "nghĩa ở đây"                 needs P1's senses and P2's provider
P4   writing_task_generator → bank
P3   English offline fallback
```

P0 first: it is the cheapest, adds no data and needs no provider at all. P2
before P1 because the Vietnamese precompute runs through it. P1 is the largest
saving and the largest piece of work. P2b comes last of the three because it
needs both — the dictionary's senses to choose between, and a provider to choose
with.

Repairing the local translator can happen any time after P2; it is the backup
path, so nothing is blocked on it.

## 6. Governance

- **Decision Log:** P1 and P2 each need an entry. P1 introduces a second
  vendored licensed dataset (share-alike, so the attribution requirement is
  stricter than the stroke pack's). **P2 extends D-021** rather than superseding
  it: the provider-neutral boundary stays, the default provider changes, and the
  local service becomes the explicit backup. The entry must also record that
  "backup" means an operator selection, never a silent failover.
- **`ARCHITECTURE_INVARIANTS.md`:** the AI Platform section says
  `reading_evaluator` is deterministic and not provider-configurable. P0 adds
  `writing_linguistic` to that sentence; the catalog change is a real invariant
  change and needs the accepted-decision path.
- **Protected areas:** P1 touches the shared dictionary contract that Writing,
  Review, Library and Listening all consume. The payload shape must not change
  — only where each field comes from.
- **R2 human gate:** none of this needs production capability activation. It
  reduces what the control plane has to route, it does not reactivate it.
- **Multilingual invariant:** P0 and P2 apply to EN and ZH together. P1 is
  Chinese-specific because Chinese has no free dictionary path today while
  English already has one — that is a genuine linguistic-resource difference,
  not an English-first implementation.

## 7. Decisions taken — 2026-08-26

**Vietnamese glosses: precomputed.** Zero runtime cost and instant response, so
nothing is translated while the learner waits. Two tiers as set out in P1.

**Unihan: take the fields that do a job, not the whole archive.** Measured:

| | Size | What it buys |
| --- | --- | --- |
| Full archive, unzipped | **42.5 MB** | mostly Japanese/Korean/Cantonese readings, IRG source references and printed-dictionary page indices — nothing this product reads |
| `Unihan_Readings.txt` alone | 8.8 MB | parses in 0.2 s |
| **Useful-field subset** | **3.07 MB JSON / 0.72 MB gzipped**, 50 423 characters | Mandarin + Hán-Việt readings, English definitions, radical/total strokes, simplified↔traditional variants |

So the answer to "does taking everything hurt?": on a server, 40 MB is survivable
but buys nothing — every extra field is for a language this product does not
teach. The subset above is deliberately *wider* than the three fields first
proposed, because radical/stroke counts and variant mappings are cheap and
genuinely useful in a learner dictionary. Take that; skip the rest.

**No local model in production.** Production has no GPU, and the 37-second
measurement shows what a local LLM costs without one. Ollama stays a development
convenience; it must never be the production selection, and the fact that
`_default_selection()` currently falls through to it is a deployment hazard to
close.

**Groq does the translating; its free tier is the dev budget.**
`openai/gpt-oss-120b` at `reasoning_effort: "low"`, always given dictionary
senses as context. In production, quota is reported and alerted in the admin
surface, and an operator raises credit or changes model from there.

**The local translator is repaired and kept as an explicit backup** for a future
VPS — an operator-selected provider, never a silent automatic failover.

**Contextual meaning is resolved from the phrase around the word** (P2b), against
the dictionary's own senses, so the model selects rather than invents.

**Writing tasks: bank first, smallest model second, strong model never.** Grading
is where a strong model earns its cost; setting a prompt is not. Per-capability
provider/model configuration already exists to express exactly this split.

## 8. The mobile app changes the sizing rules

A mobile client is coming, so resource discipline moves from "nice" to
"structural". Three rules follow.

**Datasets stay on the server. Nothing ships inside the app binary.** The three
packs together are ~21 MB — 14 MB stroke, ~4 MB CC-CEDICT, ~3 MB Unihan. Bundling
them would inflate the download, and every dictionary correction would then need
an app release. All of it stays behind the API, which is already how
`/api/chinese/stroke-order` is built. The device holds nothing but responses.

**Turn on response compression — this is the single cheapest win in this
document.** The app has no `GZipMiddleware`, so every API response goes out
uncompressed today. Measured on the heaviest payload there is:

```
好好学习 stroke data:  8 474 B raw  →  2 755 B gzipped   (67% smaller)
```

That is one middleware line and it applies to every endpoint, not just this one.

**Cache what cannot change.** Stroke data for a character is immutable — 学 will
not gain a ninth stroke. The same is true of a dictionary entry between data
rebuilds. Long-lived, versioned `Cache-Control` on those endpoints means a device
downloads a character once, ever. Today the API sends no cache headers at all.

Two smaller shaping notes, both measured:

- The stroke payload is **70% outline paths, 21% medians**. Both are needed —
  outlines to draw, medians to grade a traced stroke — so neither can be dropped,
  which makes compression and caching the levers rather than trimming fields.
- The dictionary shows one character at a time behind its tabs, so the client
  should fetch **per character rather than per word**: a four-character word goes
  from one 8.5 KB request to four 2.5 KB requests, of which the learner usually
  opens one.

## 9. Options considered and not taken

Recorded so the next agent does not re-derive them.

### 9.1 A CPU-only sense-ranking model

Choosing which CC-CEDICT sense fits a sentence is a ranking problem, and a
118 MB int8 embedding model (`multilingual-e5-small`, MIT, or
`paraphrase-multilingual-MiniLM-L12-v2`, Apache-2.0) answers it on CPU in
milliseconds, deterministically, and cannot invent a sense that is not in the
dictionary.

**Not taken.** The direction is no local model in production. Worth recording
that the reason given — no GPU — would not by itself have ruled these out, since
they are CPU models; but with contextual reading served by Groq's on-demand
explanation, nothing is left for them to do. Revisit only if the Groq quota
turns out to bind on the explain path.

### 9.2 Marian as the default translation provider

Kept, but demoted. Groq answers in about a second with better Vietnamese, so
Marian is no longer the default — it is the explicit backup for a VPS
deployment or an outage, and both of its faults still need fixing before it can
serve that role.

### 9.3 A local LLM for explanation

`qwen3:8b` is installed and free. At 21.8 tok/s it needs about seventy seconds
for a 1 500-token explanation, and production has no GPU to do better. Ruled out
with the rest of the local-model path.

## 10. What has not been decided

- **What the learner sees when quota is exhausted**, between the admin alert and
  the operator acting on it. Falling back to the dataset gloss is the honest
  answer; a spinner is not. The dataset layer exists precisely so there is
  something to fall back to.
- **Where the quota reporting lives in the admin surface**, and what threshold
  raises the alert.
- **How the backup provider is selected** — per capability, or one switch for
  the whole translation boundary.

## 11. Operator note: Groq free plan (2026-10-14)

`groq / llama-3.1-8b-instant` is recorded in `writing_coach/ai/pricing.py` at a zero rate because the owner confirmed the
Groq account is on the free plan (no billing). If billing is ever added to that Groq account, those calls become billable
while the ledger still shows 0: update the pricing entry first, and set `word_translation.daily_spend_cap_usd`
(Admin, Policies, Spend caps) to the amount you accept. The paid Groq entries used by media translation are separate and
unchanged. See D-195, amendment 2026-10-14.
