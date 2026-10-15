# PR-MON-7: cost-tiered AI routing (design)

**Status: DESIGNING, revision 1.** For independent architecture review. No product code. Migration 0034 is untouched
(proposed, not promoted, not applied). Credits, quota enforcement and funding enforcement stay off, and no meter price,
credit pack or promotional grant is configured.

- **Base:** `main` at `8abab02f43f15c286654ffc43511396cef356ea7` (PR-MON-6 merged as #223).
- **Goal (Billing roadmap):** for learner-facing AI, `deterministic/cache → local → free → cheap paid → premium`,
  keeping I-1: **no funded entitlement, no paid-provider request.**
- **Constraint:** one AI routing system. This design extends the D-195 router and the capability chain that already
  exist (`writing_coach/ai/router/`, `ai/platform.py`, `ai/routing.py`, `ai/config.py`, `ai/capabilities.py`) and
  PR-MON-6's backstop. It builds no new router layer.

## 1. What exists today (code map)

| Piece | Where | Facts that shape this design |
| --- | --- | --- |
| **Tiers** | `ai/routing.py:141` `provider_tier`; `ai/pricing.py:154` `is_free_model`; price catalogue `pricing.py:30-80` (`2026-10-14.v7`) | Only `local` (Ollama), `free` (zero-rate catalogue entry or a pinned `:free` OpenRouter id) and `paid` exist. There is **no `cheap` or `premium`** in code. |
| **Capability chain** | `platform.generate_structured` capability mode, `:700-824`; `routing.build_chain` `:222` / `run_chain` `:241` | `[primary, backup?]` in operator order. Per-rung timeout and deadline. The validator runs inside the chain, with re-asks for invalid output, and each paid re-ask is admitted again. `_budget_gate`, then PR-MON-6's `_funded_gate`, per paid rung; all-unfunded raises `FundingRequired`. Rung telemetry carries `billable_attempt`. |
| **Router (D-195)** | `ai/router/router.py:132-279`, `contract.py`, `cache.py`, `policy.py`, `tap.py` | Contract (input model, normalize, prompt, validator, TTL) → deterministic tier → **L1 cache, shared across accounts, in-process LRU 4096** → negative cache → single flight → the chain above. The cache key has no account or model in it. Only `word_translation` is routed. |
| **Capabilities** | `ai/capabilities.py:110-262` | `input_class` defaults to `learner_text`; only `word_translation` is `public_reference`. Nothing uses `published_content`. Tier rules are expressed only through `free_primary_only`, `paid_standby_cap_policy` and `paid_standby_models`. `agent_turn_fast` / `agent_turn_deep` are `configurable=False, implemented=False` (human ruling 2026-09-27). |
| **Config** | `ai/config.py:48-259` | `CapabilityConfig` v1 is primary + backup, timeout, temperature, fallback_policy. **The privacy rule** (`:244-254`): a `learner_text` capability may not use a free tier or a provider that may log prompts. It is checked when a config is saved or loaded and on every capability-mode call. |
| **Runtime mode** | `platform.py:79-91, 679-697` | `AI_RUNTIME_MODE` defaults to `legacy`: **every caller except the router uses the single Admin `active_selection()`**, with no chain, no backup and no `input_class` check. Only the router passes `capability_mode=True`. |
| **Providers** | `ai/providers.py` | `may_log_prompts` is set for OpenRouter only. Ollama is `kind="local"`, structured text only. Agent-turn streaming is cloud providers only (spec D2). |
| **Funding (PR-MON-6)** | `billing/funding_context.py`, `product/quota.py` | A FundingContext exists only inside a funded quota admission (`writing.review`, `orena.message`, `pronunciation.audio`, `media.import`). The backstop modes are off, log and enforce. With enforce, every paid call outside an admission or `SystemFunding` is refused. |

## 2. Capability matrix: current learner AI paths

**Legend.**
- **Mode:** L = legacy single selection; C = capability mode.
- **Input class** is what the prompt really carries, not the catalogue's label.
- **Cache scope:** S = shared across learners; P = per learner; none = no cache.

| # | Path (entry) | Key used | Mode | Input really sent | Bypass / cache in front | Local could serve the contract? | Free/OpenRouter privacy-allowed? | Quota meter / PR-MON-6 admission | Fallback today | Proposed slice |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `POST /api/evaluate` (app.py:3319 → `evaluate_with_ai` :1708) | `writing_evaluator` | L | learner essay + task (learner_text) | per-learner stored review + `_review_gate` single flight; feature access first (PR-MON-6) | uncertain: 2200-token rubric JSON; needs the benchmark (§6) | **no** | `writing.review` admitted (funded when on) | heuristic only if `ALLOW_FALLBACK`, else 502/503 | **7A** |
| 1b | `POST /api/essays/{id}/review/refresh` (:3535) | `writing_evaluator` | L | same | none | same | no | **none** (deliberately unmetered, D-161) | none | 7A (needs a funding answer, H7-3) |
| 2 | `POST /api/improve` (:2903 → `improve_with_ai` :2505) | `writing_improver` | L | learner text ≤ 20,000 | none | likely (bounded schema); benchmark | **no** | `writing.review` admitted | none (502/503) | **7A** |
| 3 | `POST /api/texts/discussion/turns` (text_discussion.py:174) | `text_discussion` | L | learner question + passage + history | stored repeat by request id | possible; benchmark | **no** | `orena.message` admitted | none (503) | **7A** |
| 4 | Reading translate (reading_translation.py:87) | `learner_translation` | L (or a direct Groq/local engine by env) | sentences of a published article, a book, **or the learner's own import** | DerivedCache S (memory), persistent only for `article:` ids **asserted by the client** | yes: local Marian already exists as an engine | only for a **server-verified** published source | **none** | none (503) | **7B** (published) / **7A** (learner import) |
| 5 | Reading summary (reading_summary.py:47) | `text_discussion` (reused) | L | published article, book chapter, **or raw learner text** | DerivedCache S; persistent for article ids | possible | only for a verified published source | **none** | none (503) | **7B** / **7A** |
| 6 | Dictionary `GET /api/dictionary` (app.py:2802) | `learner_dictionary` | L | **one word or short phrase** (public reference) | shared learning-cache SQLite (S, 30 days); dictionaryapi.dev first for English | yes | **yes** (public_reference), but needs its own capability key | **none** | 503 | **7B** |
| 7 | Word detail / sentence sheet / contextual / registers / spoken-response / media explain / conversation turn (media_interaction.py, word_detail.py, conversation.py) | `learner_dictionary` (`contextual_dictionary` for conversation, **not in the catalogue**) | L | selection + sentence context (published or learner import), **learner questions, learner speech transcripts** | DerivedCache S on the gloss/explanation variants (persistent for client-asserted `article:` ids); none on the others | possible for short gloss; doubtful for tutoring | no (learner_text), except a gloss of a verified published sentence | **none** | sheet answers from the dictionary; others 502/503 | **7A**; gloss of verified published text **7B** |
| 8 | Word deep `GET …/vocabulary/{w}/deep` (word_deep.py) | `learner_dictionary` | L | catalogue example, else **the learner's saved fragment** | shared asset store keyed **without the context** | possible | only with the catalogue example | **none** | `{}` | **7B** (catalogue example only); learner-fragment variant 7A |
| 9 | Word translation tap / prefetch (ai/router/tap.py) | `word_translation` | **C (router)** | word only (public_reference) | deterministic sheet first, router L1 S, single flight | — | **yes** (free primary, capped Groq standby) | **none**; the paid standby is skipped under enforce | sheet stands (miss) | **unchanged** (already the target shape) |
| 10 | Task generation `/api/tasks/generate`, `/api/practice/next` (app.py:2392) | `writing_task_generator` | L | task type, level, word target, **free-text topic ≤ 120** | none | yes | only if the topic is an enumerated value (a free-text topic is learner-typed) | **none** | always the built-in task (it also hides `FundingRequired`) | **7B** if topics are enumerated, else **7A** |
| 11 | Orena Intelligence `POST /api/agent/turn` (agent/turn.py → `stream_agent_turn`) | telemetry `agent_turn_fast` | L, cloud only | learner message + personal context + tool results | none (stored repeat by turn) | **no** (spec D2: never local) | **no** | `orena.message` admitted, funded per round (PR-MON-6) | error event, no failover | **7C** |
| 11b | Agent opening greeting, rolling-summary compaction (turn.py:457, :1092) | — | L | snapshot / conversation | opening limiter, snapshot greeting | no | no | **none** | snapshot greeting; compaction failure swallowed | 7C |
| 12 | Live voice mint, ASR, pronunciation, media pipeline, word TTS | (non-text) | — | audio / transcript | — | — | — | `orena.message` (voice), `pronunciation.audio`, `media.import`; system funding for media | — | **out of scope** (not structured text) |
| 13 | Reading comprehension generation (admin) | `reading_generator` | L | published article | — | possible | published_content | admin, no learner meter | one retry | **7B**, later (admin) |

## 3. Findings that bear on the design (reported, not resolved here)

| # | Finding | Why it matters |
| --- | --- | --- |
| F-1 | **Legacy mode bypasses the privacy rule.** Every path except the router uses the single Admin selection, and `input_class` is never checked in legacy mode. If the operator selected an OpenRouter free model as the active selection, learner text would reach it. | The D-195/D-104 privacy rule holds today only by operator discipline. PR-MON-7A moves learner capabilities into capability mode, where the rule is checked on every call. A guard in legacy mode belongs in 7A too (§5.1). |
| F-2 | **Shared caches hold learner-derived content.** The DerivedCache's memory layer is shared, and its persistent layer trusts a client-supplied `content_id` starting with `article:`. The word-deep cache key ignores its context, but that context can be the learner's saved fragment. | Learner-derived explanations can be served to other learners. PR-MON-7 must not widen this, and needs a cache-scope rule (§5.3). Fixing the existing leak belongs to the Reading/Dictionary owners; flagged as H7-5. |
| F-3 | **`contextual_dictionary` is not a catalogued capability.** In capability mode `require_capability` raises, so that path would fail with 503. | 7A must give it a catalogued key (or `learner_dictionary`) before moving it. |
| F-4 | **One key per meaning is missing.** `learner_dictionary` covers both a public word lookup (#6) and learner tutoring (#7). `text_discussion` is reused for summaries (#5). | A privacy class is per capability. Public and learner uses need separate keys, decided by the server, before either can be routed differently (7B). |
| F-5 | **Many paid learner paths have no meter.** Dictionary, word detail and the sheets, contextual, registers, spoken response, media explain, reading translate and summary, task generation, word deep and review refresh are all unmetered. | Under `FUNDING_ENFORCEMENT=enforce` their paid rungs are refused, and task generation silently falls back. PR-MON-7 cannot fund them; this is PR-MON-6's own precondition (§6 meters, H-2). Until then a paid rung on those paths stays legacy-ungated (enforcement off) or skipped (enforce). See H7-3. |
| F-6 | **Agent turns ignore capability configs.** `stream_agent_turn` uses the legacy selection, cloud only, with no chain, and `agent_turn_*` are not configurable by human ruling. | 7C needs that ruling revisited; it is not something a design can assume. |

## 4. Tiers: definitions from existing sources only

| Tier | Definition (no new pricing source) |
| --- | --- |
| `deterministic` | A contract's `deterministic(inp)`, or a stored or derived result produced without a model call (stored review, CC-CEDICT, catalogue, dictionaryapi.dev, local Marian MT). |
| `cache` | The router's L1 (shared, only for public/published capabilities), or a per-learner stored result. |
| `local` | `provider_tier == "local"`: Ollama on Orena's own machine. A **trusted local** provider is one whose `ProviderDefinition` is `kind="local"` and `may_log_prompts=False`. Local is privacy-allowed for `learner_text`. |
| `free` | `provider_tier == "free"`: a zero-rate catalogue entry or a pinned `:free` OpenRouter id (`check_model_allowed`). **Never for `learner_text`** (`config.py:244-254`). |
| `cheap paid` | `provider_tier == "paid"`, **and** the model is in that capability's reviewed `paid_standby_models`, with a priced catalogue entry and a `paid_standby_cap_policy` cap. That is the existing D-195 mechanism; no price threshold is invented. |
| `premium` | Any other `paid` model. **Not used by 7A or 7B.** The D-195 amendment keeps escalation and premium tiers refused in v1. 7C proposes it for agent turns only, behind a human decision (H7-4). |

## 5. Design

### 5.1 One routing system: capability mode per capability

- **One routing system.** Routing is the existing capability chain (`generate_structured` capability mode). The D-195
  router sits in front of that chain where a contract and a shared cache are wanted (7B).
- **No global flip.** A capability moves out of the legacy single selection only when its key is listed in a new
  switch, `ORENA_CAPABILITY_ROUTING` (empty by default), **and** it has a saved, valid capability config. The call
  sites keep their capability keys and pass `capability_mode=routed(key)`; no feature names a model.
- **Legacy guard (F-1).** In legacy mode, a `learner_text` capability whose active selection is a free tier or a
  prompt-logging provider is refused (503 `capability_unavailable`), instead of sending the text. This is the same
  rule as `config.py:244-254`, applied at call time. It changes nothing for a correctly configured deployment.

### 5.2 Order of work for a routed call

The order is deterministic/stored, then cache, then the chain:

```
feature access (PR-MON-6 require_feature, unchanged, before any bypass)
 -> deterministic / stored result (per capability, unchanged)
 -> cache (7B: router L1 shared - public/published only; 7A: per-learner stored results only)
 -> chain rung 1 (primary: local, or free when the input class allows)
 -> chain rung 2 (backup: cheap paid under the capability's reviewed models + cap + I-1 backstop)
```

- **v1 config already expresses this.** The primary is local or free, and the backup is cheap paid. **No config v2
  and no N-model pool.** A third rung (local, then free, then paid) is possible only for public/published capabilities,
  and it is not needed for 7A or 7B. If a capability ever needs one, `build_chain` is documented to take one config
  field and no code; that would be its own reviewed change.
- **Validation before falling through.** Each rung's answer goes through the capability's validator (the router
  contract's `validate`, or the existing schema validators `validate_result` and the improver's schema checks). An
  invalid answer is retried `retry_invalid` times, then the next rung is tried. The local rung counts as answered only
  when its output passes the same validator a paid answer must pass. Quality for the learner is protected by the
  validator plus the benchmark acceptance of §6. A paid retry is admitted again by both gates.

### 5.3 Cache scope by input class

The router contract gains one field, `cache_scope`:
- `shared` is allowed only for `public_reference` and `published_content`;
- `none` is the only value for `learner_text`. The router's L1 is never used for it.

This enforces in code proposal §2.4 ("shared cache only for public/published"), which today is documentation.

Per-learner results stay where they already are, in the feature's own store (the stored review, the discussion
repeat). No new cache table is added (non-goal). A capability is `published_content` only when the server has
verified the source: an article id that the server resolves to a published article, never a client-asserted
`content_id` (F-2).

### 5.4 Funding and attribution

The routed call runs inside the operation's existing context, so every rung inherits the same `FundingContext` and
operation id. In order:

1. **Local and free rungs** need no prepaid funding (§7 of PR-MON-6: free rungs are not gated).
2. **The paid rung** is admitted by `_budget_gate` (a daily cap, if the capability has one), then by `_funded_gate`.
   That gate makes the live database check of PR-MON-6 §2.1: the admission is funded or dispatched, the backing is
   open, and a credit hold outlives the rung's real timeout.
3. **Funding runs out between rungs or retries.** The re-ask is refused (`unfunded`) and no request is sent.
4. **Settlement happens once per operation, never per rung.** The quota or credits ticket is settled by the feature
   after the chain returns:
   - `writing.review` settles 1 per review, whatever rung served it (H-3: credits pay for metered work);
   - the heuristic fallback settles 0, as today.

   A rung failure or an invalid retry never settles, so the chain cannot charge twice.
5. **Attribution.** Every billable attempt (`billable_attempt`, PR-MON-6 formal review) is written with the
   operation's `operation_id` and meter, so local, free and paid tries all aggregate into one operation's cost
   evidence.
6. **Quota units do not change.** A routed operation consumes exactly what it consumes today.

### 5.5 Slice boundaries

**PR-MON-7A: structured learner workloads.** The route is deterministic/stored → trusted local → funded cheap paid.
- **Capabilities:**
  - `writing_evaluator` (#1);
  - `writing_improver` (#2);
  - `text_discussion` (#3);
  - `learner_dictionary` for its learner uses (#7);
  - the learner-import variants of #4, #5 and #8.
- **Changes:**
  - the `ORENA_CAPABILITY_ROUTING` switch;
  - the legacy guard (F-1);
  - `cache_scope` on contracts;
  - a catalogued key for the conversation turn (F-3);
  - configs that put a trusted local primary in front of a reviewed cheap paid backup;
  - benchmark acceptance per capability before it is listed.
- **Funding:**
  - Metered paths (#1, #2, #3) get the paid rung inside their existing admission.
  - Unmetered paths (#7, the learner variants of #4, #5 and #8, and the review refresh) stay local-first. Their paid
    rung follows H7-3.
- **Never:** OpenRouter or any free tier for these inputs.

**PR-MON-7B: public and published workloads.** The route is deterministic/cache → reviewed free pool → cheap funded
paid standby.
- **New public keys, decided by the server:**
  - a dictionary entry capability (#6, `public_reference`);
  - published reading translation and summary (#4, #5, `published_content`, only for server-verified published
    sources);
  - a catalogue-example word deep (#8);
  - task generation when its topic is an enumerated value (#10).
- **Each gets a router contract** (validator, normalize, shared L1, TTL), reusing the D-195 free catalogue as it
  stands. No new free model id.
- **Unchanged:** `word_translation` is already this shape.

**PR-MON-7C: Orena Intelligence.** It is not routed through the structured router: it streams, uses native tool calls
and has its own Agent Contract.

The proposal is a reviewed agent routing adapter in `stream_agent_turn`:
- configs for `agent_turn_fast` / `agent_turn_deep` (this needs H7-4: the 2026-09-27 ruling made them
  non-configurable);
- a two-rung chain of cloud agent-capable providers (cheap paid, then premium paid);
- failover only **before the first streamed token** of a round, never mid-stream;
- tool-call semantics and memory/context unchanged;
- the per-round FundingContext and the live check as today;
- per-round attribution.

Not proposed: a local or free tier (spec D2, and agent input is `learner_text`).

The adapter would also give the opening greeting and the rolling-summary compaction (#11b) an explicit funding
answer: `SystemFunding` with a USD cap, or the turn's admission. That is H7-3.

### 5.6 Failure behaviour

| Situation | Result |
| --- | --- |
| The local rung is down or slow | It is skipped, or times out within its own deadline; the next rung follows the existing health cooldown. |
| The local answer is invalid | It is retried, then the paid rung is tried if funded; otherwise the existing error (502/503) or the existing fallback (heuristic review, built-in task). |
| The paid rung is unfunded under enforce | It is skipped (`unfunded`). If no unpaid rung answered: `FundingRequired`, answered 503 `funding_required`. Task generation keeps its built-in fallback, so its unfunded case is logged. |
| The paid rung is over budget | It is skipped (`budget`), as today. |
| The capability is listed but its config is missing or invalid | 503 `capability_not_configured`. It never silently falls back to legacy. |
| Legacy mode with a `learner_text` capability on a free or prompt-logging selection | 503, nothing sent (F-1). |

## 6. Test plan

- **Routing switch:**
  - unlisted capabilities behave exactly as today (legacy);
  - a listed capability without a config answers 503;
  - a listed capability with a config uses its chain.
- **Privacy:**
  - a `learner_text` capability never reaches a free or prompt-logging rung, in capability mode or legacy mode;
  - `cache_scope=shared` is refused for `learner_text`;
  - a client-asserted `article:` id is never treated as published.
- **Order:**
  - feature access first (403 before any bypass);
  - a stored or deterministic hit sends nothing;
  - local before paid;
  - an invalid local answer falls through only after retries;
  - a valid local answer never reaches paid.
- **Funding:**
  - a paid rung inside an admission passes the live check;
  - an expired hold between rungs gives no paid request;
  - an unfunded paid rung on an unmetered path is skipped (enforce) or logged (log);
  - one settlement per operation across rungs and retries;
  - every billable attempt is attributed to the same operation id.
- **Units:** `writing.review` and `orena.message` consumption is unchanged per operation, for every rung that serves
  it.
- **Telemetry:** rung, tier, fallback reason and `billable_attempt` per attempt; the router rollup counts unchanged
  for `word_translation`.
- **Benchmark acceptance (offline, before listing a capability):** `writing_evaluation_benchmark_runner.py` and
  equivalent golden sets for the improver and discussion. They compare the local model's validated-output rate and
  quality against the paid baseline. The threshold is human decision H7-2.
- **7C (when approved):**
  - streaming unchanged;
  - failover only before the first token;
  - tool calls intact;
  - per-round funding;
  - no local or free rung for agent turns.

## 7. Rollout (everything off by default)

1. **7A code** behind `ORENA_CAPABILITY_ROUTING` (empty), with the legacy guard. Configs saved only by the operator.
2. **List one capability at a time** after its benchmark acceptance. Watch the cost-model report (PR-MON-6 §8)
   per operation.
3. **7B contracts.** Each is off until its capability config is saved and listed.
4. **7C** only after H7-4.

Nothing here enables credits, quota enforcement or funding enforcement. It adds no price, pack or grant, and does
not touch 0034.

## 8. Non-goals

- Config v2 and N-model pools.
- An Admin pool editor redesign.
- A persistent AI cache, a migration, or a new AI result table.
- A new provider marketplace.
- Production activation.
- New free model ids.
- Any change to quota units.
- Routing agent turns through the structured router.
- Non-text paid paths (ASR, pronunciation, TTS, live voice, media pipeline).
- Fixing the existing shared-cache leaks of F-2, which belong to their owners (flagged, H7-5).

## 9. Open human decisions

| Id | Decision |
| --- | --- |
| H7-1 | **What "cheap paid" means.** This design uses the existing per-capability reviewed `paid_standby_models` allowlist, with a cap. The alternative would be a price threshold, which would be a new number. |
| H7-2 | **Benchmark acceptance for a local primary,** per capability: the validated-output rate and quality versus the paid baseline. |
| H7-3 | **Unmetered paid learner paths** (dictionary, the sheets, reading translate and summary, review refresh, agent greeting and compaction). Options: give them meters (PR-MON-6 H-2 limits), run them as `SystemFunding` under a USD cap, or keep them local- and free-only once funding is enforced. |
| H7-4 | **Lift the 2026-09-27 ruling for agent turns,** making `agent_turn_fast` / `agent_turn_deep` configurable, for 7C. |
| H7-5 | **The shared-cache leaks of F-2:** which lane owns the fix, and whether it blocks 7B. |

## 10. Contradictions found

- **D-195:** none with the decision itself. The proposal's §2.4 cache-scope rule is not enforced in code; 7A makes
  it code (§5.3). The legacy runtime mode bypasses the D-195/D-104 privacy rule (F-1); 7A closes that.
- **PR-MON-6:** none. F-5 (unmetered paid paths are refused under enforce) is PR-MON-6's own documented
  precondition. PR-MON-7 does not change it and raises the choice as H7-3.
- **Agent Contract and spec D2:** "local first" for Intelligence contradicts spec D2 (never a local model for agent
  turns), and agent input is `learner_text`. So 7C tiers agent turns only within paid cloud providers (H7-4).
- **Capability configuration:** `contextual_dictionary` is used but not catalogued (F-3). `learner_dictionary` and
  `text_discussion` each carry two input classes (F-4).
