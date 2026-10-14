# AI Cost Router — design proposal

Status: PROPOSED. The owner answered decisions 1, 3, 4 (lane) and 6 below on 2026-10-14. Independent architecture
review is required before slice 1 merges. Date: 2026-10-14. Base: main d55526a2.

## 0. Owner instruction (2026-10-14)

There is one AI Cost Router, shared by all of Orena. It is built on the existing capability routing in Admin → AI & Models.
There is no second AI subsystem for translation, and feature code never names a model.
- **Cost tiers.** The order is deterministic/local → free model pool → cheap paid → premium. A more expensive tier is used
  only when the capability needs it, or when a cheaper tier fails on quality or availability.
- **Admin settings per capability.** An ordered pool of providers and models. Each model can be enabled or disabled and has its
  own timeout. Fallback conditions, an optional escalation tier, a maximum total latency, a token/output budget and
  "Test capability".
- **Routing.**
  - Deterministic and local layers come first.
  - A 429, a timeout or an unavailable provider moves to the next model.
  - Invalid output gets a bounded retry or fallback.
  - The model is never picked at random.
  - A premium tier is used only where the capability allows it.
- **Cache and telemetry.**
  - The cache holds the capability's result, not one model's, so changing the model does not pay again for the same
    request.
  - Telemetry per capability, provider and model records: requests, cache hits, tokens, estimated cost, latency, error and
    fallback rate, and the model actually used.

## 1. What exists today

The capability runtime already does most of this, so the router extends `writing_coach/ai/`. It does not replace it.

| Piece | Where | State |
|---|---|---|
| Capability catalogue (code-owned) | `writing_coach/ai/capabilities.py:84-219` `_DEFINITIONS`; `AIOperation` :19; `AIFallbackPolicy` :33 | writing_evaluator, writing_linguistic, reading_generator, writing_task_generator, writing_improver, learner_dictionary, learner_translation, grammar_lesson_generator, text_discussion, reading_evaluator, plus speech and agent keys (reserved). There is no `word_translation`. |
| Capability config | `writing_coach/ai/config.py:46-136` `CapabilityConfig` v1 | Fields: `enabled, provider, model, backup_provider, backup_model, timeout_seconds, temperature, fallback_policy`. Unknown fields are refused (:120-125). |
| Config storage | `platform_settings` row `ai.capability.<key>` (`config.py:24`, `persistence/platform_repository.py:499-553`); generic `get_setting/set_setting` with compare-and-set and audit (:470-497) | Config needs no DDL. |
| Failover chain | `writing_coach/ai/routing.py`: `classify` :86, `ProviderHealth` cooldown :103-163, `build_chain` :176 (2 rungs), `run_chain` :195 | Each rung is tried once and every attempt is logged. |
| Runtime entry | `writing_coach/ai/platform.py:452-573` `generate_structured()` | Capability mode (`AI_RUNTIME_MODE` :71) builds the chain at :527 and runs it at :553. |
| Providers | `writing_coach/ai/providers.py`: catalogue :84-127; `OpenAICompatibleProvider` :358; `generate_json_once` :634 (no hidden retry) | No OpenRouter provider. |
| Credentials | D-037 encrypted store (`platform.py:669-907`, `ai/credentials.py`) | Reusable. |
| Price table | `writing_coach/ai/pricing.py:28-39`, versioned (D-034) | An unknown model counts as "unpriced". |
| Telemetry | `ai.operation` rows in `audit_logs` (`platform_repository.py:597-615`), allowlist `sanitize_telemetry` (`ai/base.py:233-274`), aggregates (`control_plane.py:310-420`) | |
| Cost ledger | `ai_cost_records` (migration 0026, on main, D-177); `/api/admin/ai/costs` (`platform.py:969-998`) | |
| Spend caps | `agent/budget.py` (`UNPRICED_ALLOWANCE_USD = 0.01` :31); `policies.py:138-152`; `ai_spend_since` :670, `ai_spend_for_capability` :685 | |
| Admin AI API | `platform.py`: GET `/config` :632, `/catalog` :642, `/operations` :910; PUT `/config/{key}` :1117; POST `/test/{key}` :1206 (health JSON only) | `require_admin`, audited. |
| Admin design | `Orena-Admin.dc.html`: A2 "AI & Models" (tabs Providers, Capability routing, Token usage); A5 "Capability routing" (Primary and Standby, Test primary/standby, Availability, a same-provider warning; Standby is "used automatically when the primary fails") | |
| Reading cache | `writing_coach/reading_derived.py:69` `DerivedCache` (in-process LRU; the PostgreSQL store's table 0028 is only a proposal) | |
| Word tap | `writing_coach/reading_lookup.py`: the docstring :1-10 says "Never AI"; `TAP_BUDGET_SECONDS = 2.0` :40; layers catalogue :334, CC-CEDICT :357, dictionaryapi :373, MT :396; `_safe_machine_translation` :272-275 | Tests `tests/test_lookup_deterministic.py:1-46` and `tests/test_reading_lookup.py:276-287` pin "never AI". |
| Second translation path (to remove later) | `media_translation.py:239-280` `GroqTranslationProvider` (hardcodes its model); `reading_translation.py:42-63` (engine chosen from an environment variable); `reading_summary.py:47` borrows `text_discussion` | |

### Gaps

- **G1. Per-model timeout cannot be saved or applied.**
  - `supported_option_keys = {"temperature"}`, so `validate_capability_config` refuses `timeout_seconds` (`config.py:177-189`).
  - `ProviderTarget.timeout_seconds` is never used (`platform.py:535-551`).
  - The HTTP timeout comes from `CLOUD_AI_TIMEOUT`, which defaults to 180 s.
  - There is no total deadline.
- **G2.** Semantic validation runs after `generate_structured` returns, so a bad meaning does not move on to the next model.
- **G3.** A pool has at most two rungs, and has no enable, tier, escalation or token budget settings.
- **G4.** `AIProviderError` carries no HTTP status (`providers.py:563-569`), so telemetry cannot tell a 429 from a 402, a 401 or a 5xx.
- **G5.** Free models are "unpriced", so `DailySpendGuard` charges each call $0.01.
- **G6.** There is no result cache at the capability level.
- **G7.** Telemetry has no fields for cache hits, tier or fallback reason, and the allowlist would drop them.
- **G8.** "Test capability" does not run the real contract on a sample input.
- **G9.** There is no OpenRouter provider and no guard against random-router ids (`openrouter/auto`, `openrouter/free`).
- **G10.** Memory contradiction (section 7).
- **G11.** The "word tap never AI" rule. The owner superseded it on 2026-10-14 (decision 1).

## 2. Target architecture

### 2.1 Contracts

`ai/capabilities.py` stays the only catalogue (D-006). The router adds a contract per routed key in `writing_coach/ai/router/`:
`contract.py`, `policy.py`, `router.py`, `cache.py`, `stats.py` and `contracts/<key>.py`.

A `CapabilityContract` has:
- `key`, `contract_version`, `prompt_version`;
- `input_model`, a pydantic model with `extra=forbid` and hard length limits;
- `normalize()`, which builds the cache key;
- `build_messages()`, which passes the input as JSON data in the user role and never splices it into instructions;
- `output_schema` (checked with jsonschema), `validate()` (semantic checks) and an optional `deterministic()` tier 0;
- `accepted_operations`;
- `input_class`: `public_reference`, `published_content` or `learner_text`;
- a `cache` policy, a `default_policy` and a `sample_input`.

Mapping the owner's capability names to keys:

| Owner's name | Key |
|---|---|
| word_translation | new key, slice 1 |
| short_translation | `learner_translation` |
| short_summary | new key, for `reading_summary` |
| simple_explanation, contextual_tutoring | `learner_dictionary`, `text_discussion` |
| writing_feedback | `writing_evaluator`, `writing_improver` |
| classification, level_estimation, metadata_extraction | new keys, each added when it has a consumer |
| agent_reasoning | stays `agent_turn_*`, owned by the Intelligence lane and not routed in v1 |

### 2.2 Pool configuration: same document, version 2, no migration

```json
{ "config_version": 2, "enabled": true, "fallback_policy": "deterministic_fallback",
  "pool": [ {"provider":"openrouter","model":"google/gemma-4-31b-it:free","enabled":true,"timeout_ms":2500,"tier":"free"},
            {"provider":"openrouter","model":"qwen/<pinned>:free","enabled":true,"timeout_ms":2500,"tier":"free"} ],
  "escalation": [],
  "escalate_on": ["invalid_output", "exhausted"],
  "max_total_latency_ms": 4000, "max_output_tokens": 120, "retry_invalid": 1, "temperature": 0.0,
  "daily_spend_cap_usd": 0 }
```

- **Reading.** The reader accepts v1 and v2. A v1 document becomes the pool `[primary, backup?]`.
- **Writing.** The existing PUT maps primary and standby onto `pool[0..1]`. Writes go through `set_setting` with compare-and-set
  and audit.
- **Validation, static only (D-011):**
  - The provider must support one of the contract's operations.
  - The tier must agree with `pricing.py`.
  - An escalation entry must sit above the pool's tier, and only where the contract allows escalation.
  - `openrouter/*` router ids are refused.
  - The free tier, and any provider that may log prompts, are refused for `learner_text` contracts.

### 2.3 Router algorithm

```text
route(cap, raw_input, deadline=None):
  inp = contract.input_model(**raw_input)            # 422 before any call
  key = sha256(cap, contract_version, prompt_version, canonical(normalize(inp)))   # model NOT in key
  deterministic hit -> return; cache hit -> return; negative cache -> unavailable; single-flight join
  policy = load (v1|v2); disabled -> AICapabilityDisabled
  T = min(deadline, now + max_total_latency)
  for phase in (pool, escalation if contract allows and last_reason in escalate_on):
    for entry in enabled entries:
      skip if provider cooling; skip if tier >= cheap and capability daily cap exceeded
      for retry in 0..retry_invalid:
        stop if T - now < MIN_ATTEMPT
        try: out = validate(schema(provider.generate_json_once(..., model, timeout=min(entry, remaining),
                                                                temperature, max_output_tokens)))
             cache.put(key, out, provenance); return out
        except InvalidOutput: retry same model once, then next model
        except availability (429/402/5xx/timeout/unavailable): cool provider, next model
        except AICapabilityError: raise (terminal)
  negative-cache; deterministic_fallback -> contract fallback; else AllProvidersUnavailable
```

- **Ordering.** The order is fixed and never random. The router owns failover; OpenRouter's own `models` fallback is not used,
  and requests send `provider.allow_fallbacks=false`.
- **Reuse the existing runtime.** `generate_structured` gains `validate=` and `deadline=`, and `generate_json_once` gains
  `timeout=`. No second runtime is written.

### 2.4 Cache

- **Key.** Capability, contract version, prompt version, normalized input and parameters. It never includes the model.
- **Value.** The output plus its provenance: provider, model, tier, prompt version and time. Provenance is visible to Admin only.
- **L1, in-process.** A bounded LRU per worker, with single-flight and a negative cache of about 60 s.
- **L2, persistent.** One generic table `ai_capability_results` in a later slice. This is gated: a proposal, independent review,
  a rehearsal and human authorization. Recommendation: re-cut the 0028 proposal onto it.
- **TTL and purge.** TTL is set per contract (`word_translation`: 180 days). The cache is invalidated by bumping
  `prompt_version`, or by an audited admin purge.
- **Shared scope.** A shared cache is allowed only for `public_reference` and `published_content` input. Learner text is
  never cached across learners (D-104).

### 2.5 Telemetry: no new table

- **Fields added to `ai.operation`.** `tier`, `phase`, `attempt`, `fallback_reason`, `http_status_class` and `router_version`.
  `AIProviderError` gains a `status_code`.
- **Counts per request and cache hit.** Kept as in-process counters and flushed as one `ai.router.rollup` audit row per worker
  every 60 s. There is no audit row per tap.
- **Cost per account.** Recorded in `ai_cost_records` (0026).
- **Admin views.** Aggregates by capability, provider, model and tier.

### 2.6 Cost model

- **Price table.** `pricing.py` stays the only source.
  - The version is bumped.
  - Every pinned `:free` model gets an explicit zero-rate entry, with its source and date. This closes G5.
  - A paid tier on an unpriced model is refused.
- **Optional later.** OpenRouter's `usage.include` can be recorded as a cross-check only.

### 2.7 Admin UI

**Slice 1 has no UI change.** The A5 Primary and Standby settings map onto `pool[0..1]`, and OpenRouter appears in the provider
list.

**A design addendum is needed** before the UI slice:
1. An ordered pool editor. Each row has provider, model, a tier pill, an enable toggle, a timeout and a Test button.
2. An escalation section.
3. Budget settings: maximum latency, maximum output tokens, retries and the daily spend cap.
4. A "Test capability" panel with a sample input, a run, the result, a trace for each attempt and the validator's verdict.
5. Statistics: cache-hit rate, fallback rate, model used, cost per 1,000 requests, and a cache purge.
6. A tier column on the Token usage tab.

### 2.8 Test capability endpoint

`POST /api/admin/ai/router/{capability}/test` takes `{input?, entry?, write_cache:false}`.
- **Guards.** It requires `require_admin` and same-origin, uses `origin=operator_test`, writes an audit row, and takes
  `confirm_paid` for any paid tier. It is rate-limited.
- **Response.** The output, the validation result, and one entry per attempt with provider, model, tier, outcome, error
  class, latency, usage and cost. It carries no prompt text and no secrets.

Companion endpoints:
- `GET /api/admin/ai/router`
- `PUT /api/admin/ai/router/{cap}`, a v2 document with `expected_updated_at`
- `POST .../{cap}/cache/purge`

### 2.9 First consumer: `word_translation`

- **Input** (owner decision 1: the word only, never the sentence):
  - `text`: 1-3 words, at most 40 characters
  - `source_language`: `en` or `zh`
  - `target_language`: a support language
  - `part_of_speech?`: optional

  Meaning in context stays with `/word-detail` and "Why here?" (D-130.3, D-133).
- **Output:** `{meaning: 1..80 chars, alternatives?: ≤2}`. The validator refuses newlines, URLs, markup and text in the wrong
  script. An echo of the input is accepted only for a proper noun.
- **Lookup order.** Catalogue → CC-CEDICT and dictionaryapi → `route("word_translation", deadline = what remains of the tap
  budget)`.
  - If the deadline passes, the call still finishes and fills the cache.
  - `meaningSource` stays `machine_translation`, so the response contract and the UI do not change.
- **Brake.** Cache-miss calls are limited per account. Over the limit, the learner gets the deterministic answer, never a 429.
- **Pool.** Set through the existing A5 or the API, never in code:
  - primary: `openrouter / google/gemma-4-31b-it:free`
  - standby: a pinned free Qwen

  Both ids are checked against the live OpenRouter catalogue when slice 1 is implemented.

## 3. Lanes

**Owner decision (2026-10-14).** The UI/Reading lane builds the router core in small PRs, each reviewed by an independent
architecture reviewer.
- **The Intelligence lane** calls the router only through `route()` and keeps the `agent_turn_*` keys. Nobody edits
  `/api/agent/*` semantics or `AGENT_CONTRACT.md`.
- **The interface** is `route(capability_key, input, deadline=None) -> RouteResult`, plus the contract's input and output models.

## 4. Gates and review

1. **The basic tap may call AI through `word_translation`, sending the word only.** Owner: yes. A Decision Log entry supersedes
   "lookup never AI" before the tests change.
2. **Failover and escalation policy.** Operator-configured ordered pools with tier labels, per-capability spend caps and full
   telemetry count as explicit failover, not silent failover (D-010 clarified). The entry supersedes D-035's primary-only
   wording (section 7). Escalation to a paid tier happens only where the contract allows it and the operator has enabled it.
   This follows from the owner's router instruction; the slice 1 Decision Log entry records it.
3. **New provider OpenRouter, free models only.** Owner: yes.
   - Only pinned `:free` models; no credit is bought.
   - The router ids `openrouter/free` and `openrouter/auto` are refused.
   - Free endpoints may log prompts, so they receive only `public_reference` input, never learner text.
   - The key is entered by the owner, either in the D-037 encrypted store or as `OPENROUTER_API_KEY`. Agents never handle it.
4. **Runtime activation.** `word_translation` ships disabled. The owner switches it on, :8021 first and then :8000. QA calls go
   through the live-provider lock (D-130.7), and tests use fake providers.
5. **Cost.** The daily cap is 0 USD for free-only pools. A paid escalation needs a cap set by the owner.
6. **Order.** Owner: slice 1 first, before the Admin design addendum.
7. **Schema.** The persistent cache (a later slice) needs independent review and human authorization.
8. **Admin auth.** No new auth model. Mutating endpoints require same-origin and audit, and the test endpoint requires
   `confirm_paid` for paid tiers.
9. **Architecture review.** Slices 1 and 2 change cost and failover semantics, so each needs an independent reviewer recorded
   in Git.

## 5. PR plan

- **PR 0 (this document).** Docs only.
- **PR 1: `word_translation` end to end.** No schema and no UI change; the capability ships disabled.
  - **Providers.** OpenRouter provider (OpenAI-compatible, base `https://openrouter.ai/api/v1`, allowlisted model ids,
    `openrouter/*` refused); a `timeout=` on `generate_json_once`; `status_code` on errors.
  - **Pricing.** Zero-rate entries for the pinned free models.
  - **Capability.** `word_translation` added to the catalogue.
  - **Router.** `ai/router/` with `route()` over v1 config: deadline, per-attempt timeout, validator inside the chain,
    `retry_invalid = 1`, L1 cache with single-flight and a negative cache, plus the new telemetry fields.
  - **Lookup.** `reading_lookup` calls the router as its last layer. The "never AI" tests change only together with the
    decision entry.
  - **Tests** (fake providers only): failover on 429, timeout and 5xx; invalid output → retry → next model; terminal errors not
    failed over; deadline; a cache key without the model; single-flight; negative cache; router ids refused; free models do not
    trip `DailySpendGuard`; a disabled capability leaves the answer unchanged; EN and ZH parity; telemetry carries no prompt or
    word text.
- **PR 2.** Config v2 (pool) and the router admin API, backend only.
- **PR 3.** Admin UI, after the design addendum.
- **PR 4.** Local and MT tiers: Marian (`LocalHttpTranslationProvider`) and Hy-MT2 as pool entries.
- **PR 5.** Persistent cache. Gated: needs a migration.
- **PR 6 onward.** One consumer per PR: `learner_translation`, `short_summary`, and moving media translation's Groq engine into
  a capability, which removes the second translation subsystem.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Free quota exhaustion | Shared cache with single-flight and a negative cache; word-only input; cooldown on 429/402; a second free model; a local tier later; a per-account brake |
| Nondeterminism | Temperature 0 and a seed where supported; pinned ids; the first valid answer is cached; `prompt_version` in the cache key; a validator with a bounded retry |
| Prompt injection | Slice 1 sends no article text, only a selection of at most 40 characters, as JSON data; a strict output schema and validator |
| Latency on a tap | Deterministic layers answer first; the router gets only what remains of the tap budget, then completes in the background; per-entry timeouts and a total deadline |
| Cost runaway | Paid tiers only under a per-capability cap that fails closed; escalation off by default; free models priced at 0; a cap on attempts; operator tests marked as such |
| Privacy on free endpoints | The `input_class` gate; learner text is never sent to a free tier and never shared-cached |
| Governance conflicts | Settled in Decision Log entries before code; tests change only with a recorded decision (AGENTS §8) |

## 7. Memory contradiction

```
MEMORY CONTRADICTION
Conflicting implementation: writing_coach/ai/routing.py (commit a50f96a7, 2026-09-22) and
  writing_coach/ai/platform.py:527-553 automatically fail over to the configured backup
  provider/model on an availability failure; the pinned Orena-Admin.dc.html A5 says the
  standby is "Used automatically when the primary fails".
Governing product rule: DECISION_LOG D-035 ("Learner runtime routing remains primary-only;
  no automatic retry, cross-provider failover, or activation is implied"); D-010 ("No
  provider-to-provider silent paid failover"); docs/ORENA_AI_COST_REDUCTION_PLAN.md §6-7
  ("backup" means an operator selection, never a silent failover).
Likely stale side: D-035 and the cost plan wording (the code and the pinned design agree
  with each other and with the owner's 2026-10-14 router instruction).
Human decision required: settled by the owner's 2026-10-14 router instruction (section 0);
  record it as a Decision Log entry in slice 1 that supersedes D-035 and clarifies D-010.
```
