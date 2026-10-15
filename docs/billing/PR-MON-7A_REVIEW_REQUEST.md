# PR-MON-7A-first: review request

| | |
| --- | --- |
| **Design** | `docs/billing/PR-MON-7_DESIGN.md` revision 2.1, APPROVED FOR IMPLEMENTATION (`7e83c4b9`). |
| **Base** | `main` at `006ad0f7037f793657f0225cb6bac6101b8f8645`, merged into the lane. The only overlap was in two admin JS files, which this slice does not touch. |
| **Scope** | `writing_evaluator`, `writing_improver`, `text_discussion`, and the shared routing and policy infrastructure they need. Nothing else is routed. |
| **Off by default** | `ORENA_CAPABILITY_ROUTING` is empty. No reviewed primary or backup model, no Ollama Cloud credential, every new daily cap is 0. Credits, quota enforcement and funding enforcement stay off. 0034 untouched. |

## What it adds

| Design § | Change | Where |
| --- | --- | --- |
| 4.3 | **Ollama Cloud provider** (`ollama-cloud`):<br>- `kind="cloud"`, structured text only;<br>- its own credential (`OLLAMA_CLOUD_API_KEY` or the D-037 store) and base URL (`https://ollama.com`, `POST /api/chat` with a Bearer key, per docs.ollama.com/cloud);<br>- only operator-listed models;<br>- the tokens it reports are priced from the catalogue;<br>- `provider_tier` = `paid` (never $0);<br>- `learner_text_models=frozenset()`, so no model may receive learner text until reviewed (H7-6).<br>The local `ollama` adapter is unchanged; it gains no-op hooks only. | `ai/providers.py`, `ai/platform.py` (provider metadata) |
| 4.2 | **Reviewed-primary policy.** Capabilities gain `reviewed_primary_models` (empty: H7-2/H7-8). `validate_routed_policy` refuses:<br>- a capability that is not routable;<br>- a primary that has not been reviewed;<br>- a local provider anywhere in the chain;<br>- for learner text: a free tier, a prompt-logging provider, or a model whose privacy has not been reviewed;<br>- a backup that has not been reviewed;<br>- an unpriced paid model;<br>- (when saving) a backup without a readable daily cap above 0.<br>Daily cap policies: `writing_evaluator`, `writing_improver` and `text_discussion` `.daily_spend_cap_usd`, all 0 by default. They apply **only to a routed call** (`ROUTED_BACKUP_CAP_POLICY`, `routed_definition`), so existing capability-mode configs keep their behaviour. The provider id is `ollama-cloud` (hyphenated, like `azure-openai`, as the credential store requires). | `ai/capabilities.py`, `ai/config.py`, `policies.py` |
| 5.1 / 7 | **`ORENA_CAPABILITY_ROUTING`.** Only `ROUTABLE_CAPABILITIES` are honoured; other keys are ignored and logged. A listed capability runs `generate_structured` in capability mode on its saved config, after `validate_routed_policy`. A listed capability with no config raises `AICapabilityNotConfigured`, which surfaces as 503; it never falls back to the legacy selection. The reading summary shares the `text_discussion` key, so it passes `routable=False` and stays legacy until its own slice. | `ai/platform.py`, `reading_summary.py` |
| F-1 | **Legacy privacy guard.** In legacy mode, a learner-text capability (or an unknown or missing key) is refused before sending when the single selection is a free tier, a prompt-logging provider, or a model whose privacy has not been reviewed. | `ai/platform.py` `_legacy_privacy_guard` |
| 4.4 | **Covered-credit coverage.** Every Ollama Cloud event carries `cost_coverage="unknown"` (an estimate, never a cash fact) until H7-7. Its catalogue cost is unchanged. The telemetry allowlist keeps only `provider_credit_estimated`, `cash` and `unknown`. | `ai/platform.py`, `ai/base.py` |
| 3 (H7-3) | **The review refresh is metered.** A refresh that calls remote AI is one `writing.review`. It is admitted after the stored-review checks, dispatched before the call, and settled once: 1 on success, 0 when it cannot be earned. A current review is not admitted. | `app.py` `essay_review_refresh`, `_refresh_with` |
| 7 | **Error mapping.** A routed but unconfigured evaluator answers 503 `evaluation_unavailable`, even with `ALLOW_FALLBACK`: a configuration fault is not a reason for the heuristic. The improver answers 503 instead of 502, and `FundingRequired` keeps its own 503. | `app.py` |
| 7 (H7-2) | **Benchmark harness.** For each model it reports schema-valid rate, quality, critical-failure rate, latency (p50/p95/max) and estimated cost, counting unpriced cases apart. It works on live callables or captured replays, compares a candidate with a baseline, and **returns no verdict**: acceptance is the owner's activation decision. | `ai/model_benchmark.py` |

## Activation steps (not taken)

1. **H7-6:** review an Ollama Cloud model's privacy and retention, and add it to the provider's `learner_text_models`.
2. **H7-2 and H7-8:** run the benchmark of that model against the paid baseline. On acceptance, add it to the
   capability's `reviewed_primary_models` and the backup to `paid_standby_models`, and set the daily cap. All of
   this is a code review plus an owner setting.
3. **H7-7:** define the covered-credit allowance (budget, window, shared-ledger accounting, behaviour when exhausted).
   Until then coverage stays `unknown`.
4. **Configure and list:** set `OLLAMA_CLOUD_API_KEY` and `OLLAMA_CLOUD_MODELS`, save the capability config, and
   list one capability in `ORENA_CAPABILITY_ROUTING`.

## Invariants kept

- **Order:** feature access → stored or deterministic result → admission (`writing.review`, `orena.message`) → chain
  → settle once.
- Rungs and retries never add a learner charge.
- Every billable attempt keeps the operation id and meter (PR-MON-6).
- The paid rung, Ollama Cloud included, passes `_budget_gate`, then `_funded_gate` with its real timeout.
- **No local model tier and no OpenRouter free for learner text.** Nothing is routed unless it is listed.

## Evidence (local execution, not CI)

`tests/test_capability_routing.py` covers:
- **The provider:** distinct, paid, unconfigured without a key; the Bearer call carries no local options; usage is
  priced.
- **Policy:**
  - only the three keys are routable;
  - nothing is routable while the allowlists are empty;
  - a fully reviewed chain passes;
  - eight refusals: unreviewed primary, local primary, local backup, free provider for learner text, unreviewed
    privacy, unreviewed backup, unpriced paid model, cap 0;
  - a cap of 0 is valid at run time.
- **The switch:** empty by default, ignores keys it does not route; a listed but unconfigured key never uses
  legacy; an unreviewed config is refused before any call.
- **The legacy guard:** five keys, including a missing key and an uncatalogued one; public reference passes.
- **Coverage:** `unknown` for Ollama Cloud, cost kept.
- **The harness:** the five measurements, no verdict.
- **The metered refresh** (SQLite and PostgreSQL stacks):
  - one `writing.review` with settle 1;
  - settle 0 when it cannot be earned;
  - 429 before any provider call;
  - a current review is not admitted.
- **503 mapping**, and the reading summary staying legacy.

Full-suite results are recorded in `BILLING_STATUS.md` with this commit.
