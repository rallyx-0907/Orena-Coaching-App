# PR-MON-7: cost-tiered AI routing (design)

**Status: DESIGNING, revision 2 (docs only).** It revises revision 1 (`2bdfdbb1`) after the independent review (3 P1)
and the owner's decisions of 2026-10-15. There is no product code. Migration 0034 is untouched: proposed, not
promoted, not applied. Credits, quota enforcement and funding enforcement stay off. No meter price, credit pack or
promotional grant is configured.

- **Base:** `main` at `8abab02f43f15c286654ffc43511396cef356ea7` (PR-MON-6 merged as #223).
- **Goal:** cheaper learner-facing AI with I-1 intact: **no funded entitlement, no paid-provider request**.
- **One AI routing system.** This design extends the existing D-195 router and capability chain
  (`writing_coach/ai/router/`, `ai/platform.py`, `ai/routing.py`, `ai/config.py`, `ai/capabilities.py`) and PR-MON-6's
  backstop. It does not add config v2, N-model pools, a persistent AI cache, a new result table or a marketplace.

## 0. How revision 2 closes the review's P1s

| Review finding | Closed by |
| --- | --- |
| **P1-1:** free provider calls on paths with no quota or brake | Every learner-triggered remote AI operation is admitted under a real semantic meter (`word.assist`, `reading.assist`, `writing.task`, `writing.review`, `orena.message`; §3). A cache miss cannot create unlimited OpenRouter or Ollama Cloud requests. Order: access → deterministic/stored → safe cache → **admission** → chain → settle once (§5). |
| **P1-2:** "local primary" could not be enforced, and production depended on a local GPU | **Local models are removed as a production tier** (owner decision). The covered-credit primary is a **cloud** provider (Ollama Cloud), and static validation proves it is in the capability's **reviewed primary allowlist** (§4.2). A random primary entered by an operator is refused. Until a primary is approved, the capability stays unlisted and off. |
| **P1-3:** learner shared-cache paths were silently included in 7A | Paths whose cache crosses learner boundaries are **blocked** from routing until they are isolated (§6, H7-5 decision). 7A-first contains only capabilities whose stored results are account-scoped. |

## 1. Code map (what exists at `8abab02f`)

| Piece | Where | Facts |
| --- | --- | --- |
| **Tiers** | `ai/routing.py:141` `provider_tier`; `ai/pricing.py:154` `is_free_model`; price catalogue `pricing.py:30-80` | `local` = the `ollama` provider id, `free` = a zero-rate catalogue entry or a pinned `:free` OpenRouter id, `paid` = everything else. |
| **Capability chain** | `platform.generate_structured`, capability mode `:700-824`; `routing.build_chain` / `run_chain` | `[primary, backup?]`; the validator runs inside the chain, with re-asks for invalid output (a paid re-ask is admitted again); `_budget_gate`, then PR-MON-6's `_funded_gate` per paid rung; rung telemetry with `billable_attempt`. |
| **D-195 router** | `ai/router/` | A contract → deterministic tier → L1 cache (in-process, **shared**, the key has no account) → negative cache → single flight → the chain. Only `word_translation` is routed. |
| **Capabilities** | `ai/capabilities.py:110-262` | `input_class` defaults to `learner_text`; tier rules exist only as `free_primary_only`, `paid_standby_cap_policy`, `paid_standby_models`. Nothing says which primary is reviewed. |
| **Config** | `ai/config.py:48-259` | v1 is primary + backup. The privacy rule (`:244-254`): `learner_text` never goes to a free tier or a provider that may log prompts. It is checked when a config is saved or loaded and on every capability-mode call. |
| **Runtime mode** | `platform.py:79-91, 679-697` | `AI_RUNTIME_MODE=legacy` by default. **Every caller except the router uses the single Admin `active_selection()`**, and its save route (`PUT /api/admin/ai/config`, `platform.py:1254`) checks neither the free tier nor prompt logging (F-1). |
| **Providers** | `ai/providers.py` | `ollama` is `kind="local"`, the dev adapter. OpenRouter sets `may_log_prompts`. Agent-turn streaming is cloud only (spec D2). **There is no Ollama Cloud provider.** |
| **Meters** | `product/catalog.py:69` | Catalogued: `orena.message`, `writing.review`, `pronunciation.audio`, `media.import`, `languages.target`. `word.assist` (request), `reading.assist` (request) and `writing.task` (request) have their units frozen by PR-MON-6 H-2, but **no Free/Plus/Pro limits** yet (a human gate). |
| **Funding** | `billing/funding_context.py`, `product/quota.py` | A FundingContext exists inside a funded admission. The backstop modes are off, log and enforce; with enforce, every paid call outside an admission or `SystemFunding` is refused. |

## 2. Tiers (revision 2)

| Tier | Definition | Production use |
| --- | --- | --- |
| `deterministic` / `stored` | No model call: a stored review, a discussion repeat, CC-CEDICT, the catalogue, dictionaryapi.dev, local Marian MT, a contract's `deterministic()`. | Yes, always first. |
| `shared cache` | The router L1, **only** for server-verified `public_reference` / `published_content`. | Yes, for public or published input. |
| `free` | `provider_tier == "free"`: a reviewed OpenRouter `:free` id (the D-195 catalogue). | **Only for public or published input.** Never for `learner_text`. |
| `covered-credit cloud` | A **cloud** provider whose bill is currently covered by provider credits the owner holds: **Ollama Cloud** (a new provider id, e.g. `ollama_cloud`, `kind="cloud"`). It is **paid** in the pricing model, with its real estimated cost, never $0. | The primary, where reviewed (§4). |
| `cheap paid` | A paid `(provider, model)` in the capability's **reviewed paid-backup allowlist**, priced in the catalogue, under the capability's reviewed spend-cap policy, passing capability and privacy validation (**H7-1, approved**). No global price threshold. | The backup. |
| `premium` | Any other paid model. | **Not used in 7A or 7B.** 7C only, if ever approved. |
| `local` (`ollama`) | The local or dev adapter, unchanged in the repository. | **Not a PR-MON-7 production tier** (owner decision). It is never configured as a learner primary, and no production path depends on a local GPU. |

## 3. Semantic meters: no learner AI path stays unmetered (H7-3, approved)

Every learner-triggered remote AI operation is admitted under one of these meters. Deterministic, stored and cache
hits happen **before** admission and consume nothing.

| Meter | Unit | Operations |
| --- | --- | --- |
| `word.assist` | request | `word_translation` miss needing a model; dictionary AI; contextual word/sentence gloss; registers / usage explanation; word detail AI; word-deep AI; similar word/phrase explanation |
| `reading.assist` | request | reading translation; reading summary; passage, article and media-transcript explanation (content comprehension, not chat) |
| `writing.task` | request | AI task / exercise generation (the built-in task may answer before admission) |
| `writing.review` | request | writing evaluation; writing improvement; **review refresh** (no longer deliberately unmetered when it calls remote AI) |
| `orena.message` | request | `text_discussion`; conversational tutor turns; Orena Intelligence turns |

- **No second charge inside one operation.** Model rounds, retries, rungs and the rolling-summary compaction of an
  admitted Intelligence turn consume no extra unit. Compaction stays attributed to that turn's operation where
  technically possible.
- **Agent opening greeting.** The order is a stored greeting, then a deterministic/template greeting. AI generation
  before a learner message needs its own separately reviewed funding and meter policy; it never becomes an unmetered
  paid call.
- **`SystemFunding`** stays for genuine system, operator or background work under its USD caps. It is never used to
  avoid metering a learner-triggered feature.
- **The meters are the per-account brake.** No second quota system is introduced. The `word_translation`
  application brake (`tap.py`, 20 per 60 s) may stay as defence in depth while `word.assist` becomes the quota source.
- **Limits are a human gate.** `word.assist`, `reading.assist` and `writing.task` need their Free/Plus/Pro limits and
  granularity before they are enforced (PR-MON-6 H-2). Until enforced, their paths are not listed for routing in a
  way that could spend without a bound (§8, rollout).

## 4. Capability policy and validation

### 4.1 Routing shapes

**Learner-authored or private input:**

```
feature access -> deterministic / stored / safe (account-scoped) result
  -> meter admission
  -> primary: reviewed privacy-safe Ollama Cloud (covered credit)
  -> backup: reviewed cheap paid
  -> stop
```

**Server-verified public or published input:**

```
feature access -> deterministic / shared cache
  -> meter admission
  -> primary: reviewed OpenRouter free
  -> backup: reviewed Ollama Cloud (covered credit)  [or a reviewed cheap paid, per capability]
  -> stop
```

- **v1 config is not extended.** It gives two rungs. Where a capability would want three (free, then covered credit,
  then cheap paid), revision 2 picks the **two most useful** per capability (§6) and defers the third rung.
- **No premium tier** in 7A or 7B.

### 4.2 Static enforcement of the reviewed primary (closes P1-2)

The capability metadata in `ai/capabilities.py` is extended conceptually. These are new fields of the existing
definition, not config v2:

- **`reviewed_primary_models`:** the `(provider, model)` pairs accepted as that capability's primary. Empty means the
  capability cannot be routed (it stays legacy and unlisted).
- **`paid_standby_models`** and **`paid_standby_cap_policy`:** the existing reviewed paid-backup allowlist and spend
  cap.
- **`input_class`:** as today.

`validate_capability_config` refuses, when a config is saved or loaded and on every capability-mode call:
- a primary not in `reviewed_primary_models`;
- a backup not in `paid_standby_models`, unpriced, or without a readable cap above zero;
- any `local` provider as primary or backup of a learner production capability;
- for `learner_text`: a free tier, a provider that may log prompts, and an Ollama Cloud model **unless its
  privacy/retention classification is explicitly reviewed** (a per-model flag, H7-6).

No model ids and no cap numbers are chosen here. Until H7-2 names a primary, `reviewed_primary_models` is empty and
the capability cannot be listed.

### 4.3 Ollama Cloud as a cloud provider (covered credit)

- **A distinct provider id** (e.g. `ollama_cloud`), `kind="cloud"`, with its own credential (an environment variable
  name only, value a human gate), reviewed model ids, the normal timeout and failure semantics, structured-text
  support, and a `may_log_prompts` / retention classification set from the provider's documented terms.
- The local `ollama` adapter is **not** pointed at a cloud URL.
- **Pricing.** Each reviewed model has a catalogue entry with its real price. If Ollama Cloud publishes no per-token
  price, the owner supplies a reviewed reference price with its source and date (like PR-MON-6's FX: configured,
  auditable, never fetched live) (H7-7).
- **It is never priced at $0** because credits currently cover it, and `provider_tier` classifies it as `paid`.

### 4.4 Cost accounting for covered credits

Every billable attempt is recorded with:
- its estimated economic cost from the catalogue;
- provider and model;
- the operation id and meter (PR-MON-6 attribution);
- **`cost_coverage`**: `provider_credit` while an owner-configured covered-credit allowance for that provider is not
  exhausted according to Orena's own accounting, else `cash`.

No external "remaining credits" API is assumed. If one is ever officially documented, adopting it is a later reviewed
change. Admin can then show the estimated compute cost against the cash cost currently covered by provider credits.

When the configured allowance is exhausted:
- the covered-credit rung keeps its real cost and becomes `cash`;
- whether it may then still serve is an activation decision (H7-7). The safe default is to treat the provider like
  any other paid rung: admitted, capped, funded.

## 5. Order and settlement invariant (every PR-MON-7 learner capability)

```
feature access -> deterministic / stored result -> safe cache -> meter/funding admission -> provider chain
  -> settle once for the learner operation
```

- **Cache and deterministic hits** spend no provider money and settle no AI meter.
- **Every fresh model call is quota-controlled:** free-provider, Ollama Cloud covered-credit and paid calls alike.
- **The paid backup is already inside the same admission.** I-1's live check applies at the paid rung, including
  Ollama Cloud, which is priced as paid. No paid request is sent after the funding expires.
- **Retries and rungs** never add a learner charge. Every billable attempt keeps the operation id and the meter. The
  feature settles **once**.
- **PR-MON-6 H-3 is preserved.** Once credits fund an operation, the result settles from the immutable funding
  snapshot. Routing never re-selects a funding source because a cheaper provider answered.

## 6. Capability and meter matrix (revision 2)

Key. Input = what the prompt really carries. Cache = shared (S), per learner (P), or none.

| # | Path | Capability key | Input | Meter | Cache before admission | Rung 1 → Rung 2 | Slice |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `POST /api/evaluate` | `writing_evaluator` | learner essay | `writing.review` | P: stored review (account + language, last 60 essays) | Ollama Cloud (reviewed) → cheap paid | **7A-first** |
| 1b | review refresh | `writing_evaluator` | learner essay | `writing.review` (**now metered**) | P | same | **7A-first** |
| 2 | `POST /api/improve` | `writing_improver` | learner text | `writing.review` | none | Ollama Cloud (reviewed) → cheap paid | **7A-first** |
| 3 | `POST /api/texts/discussion/turns` | `text_discussion` | learner question + passage | `orena.message` | P: repeat by `request_id` inside the learner's own discussion (`discussion_repository._scope()` = user + language; **confirmed account-scoped**) | Ollama Cloud (reviewed) → cheap paid | **7A-first** |
| 4a | Reading translate, learner import | `learner_translation` | learner-imported text | `reading.assist` | **S, unsafe** (shared DerivedCache memory; client-asserted `article:`) | Ollama Cloud → cheap paid | **blocked** until isolated → 7A-follow-up |
| 4b | Reading translate, verified published | new public key (e.g. `published_translation`) | published content | `reading.assist` | S (server-verified source only) | OpenRouter free → Ollama Cloud | **7B** |
| 5a | Reading summary, learner import / raw text | new learner key (split from `text_discussion`, F-4) | learner text | `reading.assist` | **S, unsafe** | Ollama Cloud → cheap paid | **blocked** → 7A-follow-up |
| 5b | Reading summary, verified published | new public key | published content | `reading.assist` | S (verified) | OpenRouter free → Ollama Cloud | **7B** |
| 6 | `GET /api/dictionary` AI | new public key (split from `learner_dictionary`, F-4) | one word / short phrase | `word.assist` | S: learning-cache dictionary | OpenRouter free → Ollama Cloud | **7B** |
| 7 | Word detail / sentence sheet / contextual / registers / spoken response / media explain / conversation turn | `learner_dictionary`; `contextual_dictionary` must be catalogued (F-3) | learner selection or question or speech, or published sentence | `word.assist` (gloss, registers, word detail); `reading.assist` (passage or media explanation); `orena.message` (conversation turn, spoken-response tutor) | **S, unsafe** on the gloss and explanation variants | Ollama Cloud → cheap paid | **blocked** → 7A-follow-up. A gloss of a server-verified published sentence → **7B** |
| 8a | Word deep, catalogue example | new public key | catalogue example | `word.assist` | S | OpenRouter free → Ollama Cloud | **7B** |
| 8b | Word deep, learner fragment | `learner_dictionary` | learner's saved fragment | `word.assist` | **S, unsafe** (key ignores context) | Ollama Cloud → cheap paid | **blocked** → 7A-follow-up |
| 9 | `word_translation` tap / prefetch | `word_translation` | word only | `word.assist` on a model miss (prefetch is system work: `SystemFunding`, free pool only, no learner charge) | S: router L1, deterministic sheet first | free → capped paid standby (today) | **7B** (meter wiring; routing shape already in place) |
| 10 | Task generation | `writing_task_generator` | parameters + free-text topic | `writing.task` | none (built-in task before admission) | free → Ollama Cloud only if the topic becomes an enumerated value; otherwise learner_text: Ollama Cloud → cheap paid | **7B** |
| 11 | Orena Intelligence turn | (legacy, telemetry `agent_turn_fast`) | learner message + personal context | `orena.message` | none | unchanged | **7C** |
| 11b | Opening greeting / compaction | — | — | greeting: none (stored or template); compaction: the turn's own `orena.message` operation | — | — | **7C** |
| 12 | ASR, pronunciation, TTS, live voice, media pipeline | non-text | — | existing meters / `SystemFunding` | — | — | out of scope |

## 7. Slice boundaries (revision 2)

### PR-MON-7A-first (narrow, all off by default)

**Capabilities:** `writing_evaluator`, `writing_improver`, `text_discussion`. All three have account-scoped stored
results and existing meters (`writing.review`, `orena.message`).

**What it adds:**
- **Meter plumbing for these capabilities only.** It adds metering to the review refresh under `writing.review`.
- **`ORENA_CAPABILITY_ROUTING`,** empty by default. A capability is routed only when listed **and** its config is
  valid. A listed capability with a missing config answers 503 and never falls back to legacy silently.
- **The legacy privacy guard (F-1).** In legacy mode a `learner_text` capability is refused (503) when the active
  selection is a free tier or a prompt-logging provider.
- **Reviewed-primary validation (§4.2)** and the local-provider refusal for learner production capabilities.
- **The Ollama Cloud provider and covered-credit accounting (§4.3, §4.4)**, only as far as these capabilities need.
- **A benchmark harness** that compares a proposed Ollama Cloud model with the current paid baseline. It reports:
  - schema-valid rate;
  - semantic correctness and task quality;
  - critical failure rate;
  - latency;
  - estimated cost.

  It extends the existing `writing_evaluation_benchmark_runner.py` and adds golden sets for the improver and the
  discussion.

**Gates:**
- **The benchmark is an activation gate, not an implementation gate.** The code lands with routing off. A capability
  is listed for learners only after H7-2 accepts its primary.
- **No local model** and no OpenRouter free for these capabilities.

### PR-MON-7A-follow-up (after cache isolation)

**Paths:** learner dictionary and contextual paths (#7), learner-import reading translation and summary (#4a, #5a),
learner-fragment word deep (#8b), each under its semantic meter.

**Blocked until** their caches no longer cross learner boundaries: account-scoped keys, or bypassing the shared
cache. A client-provided `article:` prefix is never proof of publication.

### PR-MON-7B (public and published)

**Meters and paths:**
- `word.assist`: dictionary entry (#6), catalogue-example word deep (#8a), and `word_translation` meter wiring (#9);
- `reading.assist`: server-verified published translation and summary (#4b, #5b);
- `writing.task` (#10).

**Shape:**
- new public capability keys decided by the server (F-4);
- router contracts with `cache_scope=shared` (shared only for public or published classes);
- the reviewed OpenRouter free primary, with Ollama Cloud covered credit or a reviewed cheap paid backup as the second
  rung, chosen per capability;
- no new free model id.

### PR-MON-7C (Orena Intelligence only)

**Not routed through the structured router.** It is a separately reviewed agent adapter for `agent_turn_fast` /
`agent_turn_deep`, which needs H7-4 because the 2026-09-27 ruling made them non-configurable.

**Rules for the adapter:**
- failover only before the first streamed token of a round;
- tool calling, streaming, Agent Contract semantics and memory unchanged;
- per-round FundingContext and live check;
- per-round attribution;
- the greeting and compaction policy of §3.

**Ollama Cloud** *may* be evaluated as a cloud agent provider only if a specific model proves native tool calling,
streaming, Agent Contract semantics, privacy, latency and quality. That is not assumed.

**No change to Intelligence** in 7A or 7B.

## 8. Failure behaviour

| Situation | Result |
| --- | --- |
| Primary (Ollama Cloud) down, slow or invalid after retries | The reviewed backup, if funded and within its cap. Otherwise the existing error (502/503) or the existing fallback (heuristic review when `ALLOW_FALLBACK`, built-in task). |
| Paid rung unfunded under enforce | Skipped (`unfunded`). With no other rung: 503 `funding_required`. |
| Paid rung over its cap | Skipped (`budget`). |
| Meter exhausted | 429 `quota_exhausted` before any provider call. A cache or deterministic hit is still served. |
| Capability listed but config missing or invalid | 503 `capability_not_configured`, never a silent legacy fallback. |
| Primary not in the reviewed allowlist, or a local provider configured | Refused when the config is saved or loaded, and on the call. |
| Legacy mode, `learner_text` capability, free or prompt-logging selection | 503, nothing sent. |
| Covered-credit allowance exhausted | The rung's cost becomes `cash`; whether it still serves follows H7-7. |

## 9. Test plan

- **Routing switch:**
  - an unlisted capability behaves as today;
  - a listed capability without a config answers 503;
  - a listed capability with a config uses its chain.
- **Static policy:**
  - an unreviewed primary is refused, and so is a local provider for a learner production capability;
  - an unreviewed, unpriced or uncapped backup is refused;
  - a `learner_text` capability never reaches a free tier, a prompt-logging provider, or an Ollama Cloud model whose
    privacy is not reviewed;
  - the same refusals hold in legacy mode (F-1).
- **Meters and order:**
  - feature access comes first;
  - deterministic, stored and cache hits create no admission and no spend;
  - a free or covered-credit call consumes the meter;
  - one settlement per operation across rungs and retries;
  - the review refresh is now metered;
  - an exhausted meter is refused before any provider call.
- **Funding:**
  - the paid and covered-credit rungs pass the live check inside the admission;
  - an expired hold sends nothing;
  - credits-funded operations settle from the snapshot, whatever rung answered;
  - every billable attempt carries the same operation id and meter.
- **Cost accounting:**
  - an Ollama Cloud call is recorded at its catalogue price, never $0;
  - `cost_coverage` reads `provider_credit` until the configured allowance is used, then `cash`.
- **Cache isolation:**
  - blocked paths are not routable;
  - a client-asserted `article:` id is never treated as published;
  - `cache_scope=shared` is refused for `learner_text`.
- **Benchmark harness:** it produces the five measurements per proposed model. Acceptance is not a CI gate.
- **7C (when approved):** streaming and tools intact, failover only before the first token, per-round funding.

## 10. Rollout (everything off by default)

1. **7A-first code**, with `ORENA_CAPABILITY_ROUTING` empty, no reviewed primary configured and the Ollama Cloud
   credential absent. Nothing changes for learners.
2. **Activation, per capability,** after H7-2 (primary accepted), H7-6 (privacy classification) and H7-7 (reference
   price and covered allowance). The owner lists one capability at a time and watches the PR-MON-6 cost-model report
   per operation.
3. **7A-follow-up** only after cache isolation. **7B** only once `word.assist`, `reading.assist` and `writing.task`
   have their plan limits. **7C** only after H7-4.

This rollout does not enable credits, quota enforcement or funding enforcement, configures no price, pack or grant,
and does not touch 0034.

## 11. Non-goals

- Local models as a production tier.
- Config v2 and N-model pools.
- An Admin pool editor redesign.
- A persistent AI cache, a migration, or a new AI result table.
- A provider marketplace.
- Production activation.
- New free model ids.
- An assumed provider-credit API.
- Any change to quota units.
- Routing Intelligence through the structured router.
- Non-text paid paths.
- Fixing the shared-cache leaks themselves (owned by Reading and Dictionary; they block their paths, §7).

## 12. Decisions

| Id | State |
| --- | --- |
| H7-1 | **APPROVED:** cheap paid is a per-capability reviewed `(provider, model)` allowlist, priced in the catalogue, under a reviewed spend cap and normal validation. No global price threshold. |
| H7-2 | **OPEN (activation):** which Ollama Cloud model is accepted as the covered-credit primary for each capability, judged on the benchmark (schema-valid rate, quality, critical failures, latency, cost) against the paid baseline. |
| H7-3 | **APPROVED:** no learner AI path stays unmetered. The semantic meters are in §3. **OPEN:** the Free/Plus/Pro limits and granularity of `word.assist`, `reading.assist` and `writing.task` (PR-MON-6 H-2), needed before 7B and 7A-follow-up are enforced. |
| H7-4 | **OPEN:** making `agent_turn_fast` / `agent_turn_deep` configurable for 7C (revisits the 2026-09-27 ruling). |
| H7-5 | **DECIDED:** learner-boundary cache leaks block only their own paths (§7); public/published shared cache needs server-verified classification. **OPEN:** which lane fixes the isolation, and when. |
| H7-6 | **OPEN:** Ollama Cloud's privacy and retention classification per model, needed before it may receive `learner_text`. |
| H7-7 | **OPEN:** Ollama Cloud reference prices (if no per-token price is published) and the owner-configured covered-credit allowance, including whether a rung keeps serving as `cash` once the allowance is used. |
| H7-8 | **OPEN:** the reviewed paid-backup `(provider, model)` and spend cap for each 7A-first capability. |

## 13. Contradictions and findings

| Area | Finding |
| --- | --- |
| **D-195** | The decision itself is consistent. Its cache-scope rule (shared cache only for public or published input) is not in code; 7A-first adds it to contracts. The legacy runtime mode bypasses the D-195/D-104 privacy rule (F-1); 7A-first closes that. |
| **PR-MON-6** | Consistent. The unmetered paid paths (F-5) are resolved by H7-3's semantic meters, whose limits stay a human gate (H-2). |
| **Agent Contract / spec D2** | No local model for agent turns; revision 2 has no local production tier at all. 7C may evaluate Ollama Cloud as a cloud agent provider only under its own review. |
| **Capability configuration** | `contextual_dictionary` is used but not catalogued (F-3). `learner_dictionary` and `text_discussion` each carry two input classes, so the public uses get their own keys (F-4). Capabilities have no notion of a reviewed primary yet; 7A-first adds `reviewed_primary_models` (§4.2). |
| **Shared caches** | Shared caches serve learner-derived content across accounts (F-2): the DerivedCache trusts a client-asserted `article:` id, and the word-deep cache key ignores context. The affected paths are blocked (§7). |
