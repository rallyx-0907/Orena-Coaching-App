# Orena settings reference

Every operator setting: where it is set, what it does, the pilot and production values, and whether a change needs a
restart. Owner's goal (2026-10-20): operators tune settings in Admin, so moving from test to production is easy, and the
pilot runs like production.

- **Pilot** is the invitation-only :8000 runtime (`APP_ENV=staging`).
- **Production** is the future public product (`APP_ENV=production`).
- A value marked *owner* is the owner's decision. Any other value in the Pilot or Production column is a recommendation.
- No value in this document is a secret. Secrets are named here and never written down.

This file describes settings. `docs/project/RELEASE_8000_READINESS.md` holds the :8000 release record and
`docs/project/CURRENT_HANDOFF.md` the live state. When this file and the code disagree, the code is right and this file
is the defect: `writing_coach/policies.py` is the registry of Admin policies.

Classes used below:

- **(a) Secret.** A credential. It stays in the environment and is never shown in Admin.
- **(b) Infrastructure, boot or activation gate.** It stays in the environment. This covers URLs, paths, databases,
  `APP_ENV`, ports, provider wiring, pool sizes, and the human's activation gates (migrations, payments, paid voice).
- **(c) Safety fuse.** A hard limit set in the environment. Admin may **tighten** it and never loosen it.
- **(d) Operational tunable.** It is set in Admin. An environment variable, where one exists, can pin it.

"Applies" says when a change takes effect:

- **live**: an Admin change applies within 5 seconds in every worker and at once in the worker that saved it.
- **restart**: an environment change applies only once the container is recreated from the env file
  (`scripts/staging_8000_deploy.ps1` on :8000).

---

## 1. How settings resolve

Admin writes each editable record as one row in `platform_settings`. Every write is a compare-and-set with an audit row.

| Record (`platform_settings` key) | Admin page | Code |
| --- | --- | --- |
| `platform.policies` | Admin › Operations › Policies & limits | `writing_coach/policies.py` |
| `product.quota_enforcement` (the switch and its meters) | The same page, first block | `writing_coach/product/quota.py` |
| `product.plan_catalog` (Free, Plus and Pro prices and limits) | Admin › Plans | `writing_coach/product/catalog.py` |
| `ai.active_selection`, `ai.capability.<key>`, encrypted provider credentials | Admin › AI | `writing_coach/ai/platform.py`, `writing_coach/ai/config.py` |
| `agent.provider_data_classes` | Admin › AI › Data classes | `writing_coach/agent/data_class.py` |
| `content.visibility` | Admin › Content | `writing_coach/content_visibility.py` |

### A policy (`writing_coach/policies.py`)

A policy resolves in this order, highest first:

1. **The environment pin.** When the policy's variable is set and not empty, it wins. Admin shows the field as "Locked
   by environment" and refuses to save it. A set value that cannot be read falls back to the default, not to the Admin
   value.
2. **The Admin value**, stored in `platform.policies` and validated against its type and range on every read. A stored
   value that no longer validates is ignored, and the default applies.
3. **The default**, the constant the code carried before D-172.

**Safety fuses** work differently (BQ, owner 2026-10-20: Admin may tighten, never loosen):

- **`ai.daily_spend_ceiling_usd`.** Since D-250 this is the system spend **monitor's alert threshold**, never a block.
  `AI_DAILY_SPEND_CEILING_USD` is its hard maximum, not a lock. The threshold in force is the lower of the two. Admin
  refuses a value above the environment. With no Admin value, the environment's threshold applies. Every public runtime
  (staging and production) refuses to start without the environment value, and an Admin value alone never counts.
- **The five retention sweeps** (`feedback.`, `agent.turn_`, `agent.memory_`, `usage.` and `admin_audit.retention_sweep`)
  keep a published promise of the Privacy Policy. On staging and production a sweep is **on by default**, so removing
  its pin keeps it on, and saving it off is refused. Only an explicit `off` pin in the environment leaves one off, and
  startup logs that as an ERROR. In development the default is off and Admin may switch them either way.
- **The quota switch.** On staging and production, Admin may switch enforcement on and add meters. Switching it off, or
  removing a meter it enforces, is refused.
- "Staging and production" means every `APP_ENV` name the deployment guard treats as public, including its aliases
  (`stage`, `prod`, `public`, any letter case). `ORENA_QUOTA_METERS` is a floor: the meters enforced are the variable's,
  plus any the Admin setting adds while it is switched on.

If the settings store cannot be read, a worker keeps the last values it read. A worker that never read the store uses
the defaults, but a fuse's environment maximum still holds. `agent.daily_spend_cap_usd` fails closed (`value_strict`)
when the store was never read.

### The quota switch (`product/quota.py`)

- `ORENA_QUOTA_ENFORCEMENT=off` means off and `=on` means on, whatever Admin holds.
- When the variable is unset, the Admin setting decides. A store that was never read fails closed with 503.
- The code comment requires :8000 to pin both variables, so the Admin setting is never the only authority there. Admin
  can still add meters on top of the pinned ones.

### Other records

- **The plan catalogue** has no environment layer. It is the Admin document, else the built-in Free, Plus and Pro.
  Enforcement reads it strictly and fails closed (`CatalogUnavailable`, 503).
- **The AI capability rows** have no environment layer. Provider credentials resolve from the Admin encrypted store
  first, then the environment. Model allowlists (`*_MODELS`) and base URLs come from the environment.
- **The data classes** are the Admin record once it is saved. Before that, `AGENT_PROVIDER_DATA_CLASSES` is the record.

### Everything else

Everything else is read from `os.environ`, and a change needs a restart. `compose.yaml` passes each variable through,
and most default to empty.

### Boot guards (`core/deployment.py`, `core/published_promises.py`)

These refuse to start:

- **In staging and production:** `PUBLIC_BASE_URL` must be HTTPS and not local, Google OAuth must be complete,
  `SESSION_SECRET` must be at least 32 characters, and `GOOGLE_REDIRECT_URI` must share the origin.
- **In staging and production:** every plan's per-learner daily AI cost cap must resolve to more than 0
  (`ai.learner_cost.daily_usd_free`, `_plus`, `_pro`, and `ai.learner_cost.hard_ratio` at least 1), and
  `AI_DAILY_SPEND_CEILING_USD` (the monitor's alert threshold) must be set (D-250, PRE-502 R2).
- **In production only:** `LEGAL_EFFECTIVE_DATE` must be set.
- **Everywhere:** an unclear value is refused rather than guessed for the retention sweep variables,
  `AI_DAILY_SPEND_CEILING_USD`, `AI_DAILY_SPEND_WARN_RATIO`, `AGENT_LEARNER_PACK`, `AGENT_PROMPT_LAYOUT`,
  `AGENT_STABLE_TOOLS`, `MEDIA_TRANSCRIPT_FALLBACK` and `ORENA_LIMIT_IMPORT_TOMBSTONES`.

On a public runtime, an unmet published promise (a promised sweep pinned off) is logged as an ERROR at start and listed
in Admin's readiness summary (`unmet_promises`); a missing per-learner cap or monitor threshold refuses to start. Both read the **effective** value: a variable when it is set,
else the Admin policy.

### Rule of thumb

- **Keep in the environment** what differs by *where* the runtime runs: secrets, URLs, paths, `APP_ENV`, activation
  gates and hard ceilings.
- **Keep in Admin** what differs by *how much* the runtime may do: limits, caps, rates and retention.
- **Never leave a tunable pinned in `runtime.env`** unless the pin is a deliberate fuse, because a pin silently locks the
  Admin field.

---

## 2. Spend caps and AI budget

**D-250 (owner, 2026-10-21): no app-wide cap, only a cap per learner by plan.** Nothing below pauses AI for every
learner because of the whole system's spend. Each learner has a daily AI cost cap by plan, counted from the per-account
ledger (`ai_cost_records`): at the cap their paid calls go to the economy model, at the cap x the hard ratio only free
and local models answer them, and a request with nothing else is 429 `quota_exhausted` (feature `ai.daily_cost`, no
figure shown). The per-capability caps measure the request's own learner. The system total is a monitor: it warns,
then raises a high-severity alert (log, provider health signal / health.log, Admin overview) and refuses nothing.

Every USD amount is measured at list price. A free-plan call counts at list price and an unpriced call at 0.01 USD,
except in the per-learner cost cap, where a provider whose `cost.free_tier.*` flag is on costs nothing. The media caps
are counted separately.

| Name | Set in | Type / range | Default | Meaning | Raise / lower | Pilot | Production | Risk if wrong | Related | Applies |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `AI_DAILY_SPEND_CEILING_USD` | env, **(c)** | USD ≥ 0; unset = no monitor (development only) | unset | The system spend **monitor's alert threshold** on the whole AI ledger per UTC day (D-250). At it: a high-severity alert in the log, the provider health signal and Admin. It never refuses or pauses AI. | Raise: a later alert. Lower: an earlier one. | **2** (owner, 2026-10-20); required at start | Required at start. Size it from the cost model. | Unset: no alert. Too low: alerts every day. | `ai.daily_spend_ceiling_usd`, `ai.learner_cost.*` | restart |
| `ai.daily_spend_ceiling_usd` | Admin › Policies › Spend caps, **(c)** lower-only | USD 0–10 000, or empty; never above the env value; confirm above 50 or empty | empty (the env threshold) | Lowers the monitor's alert threshold without a restart. The threshold in force is the lower of this and the env value. | Lower: an earlier alert. Raising past the env value is refused. | empty | empty | 0 alerts from the first paid call. | env threshold | live |
| `ai.daily_spend_warn_ratio` | Admin › Spend caps; pin `AI_DAILY_SPEND_WARN_RATIO` | 0.05–1 | 0.8 | The share of the threshold at which a warning is logged and shown in Admin. | Raise: a later warning. Lower: an earlier one. | 0.8, in Admin (unpinned) | 0.7–0.8 | Too high leaves no time to react. | threshold | live (Admin); restart (pin) |
| `ai.learner_cost.daily_usd_free` | Admin › Spend caps | USD 0.001–10; confirm above 1 | 0.02 | One Free learner's AI cost per UTC day (D-250, D-248 §2). At it their paid calls go to the economy model. Hidden from learners. | Raise: more paid AI per Free learner. | 0.02 | 0.02 | Too high: Free costs more than planned. | `hard_ratio`, `economy_model` | live |
| `ai.learner_cost.daily_usd_plus`, `_pro` | Admin › Spend caps | USD 0.001–10; confirm above 1 | Plus ≈0.0608, Pro ≈0.1223: 60% of 79.000 / 159.000 VND over 30 days at `vnd_per_usd` | One Plus / Pro learner's AI cost per UTC day. Until Admin stores a value it follows the formula at the current rate and share. | Raise: more AI per paying learner. | the formula | the formula, revisited with real costs | Too high: a plan costs more than it earns. | `vnd_per_usd`, `revenue_share` | live |
| `ai.learner_cost.vnd_per_usd` | Admin › Spend caps | 10 000–50 000 | 26 000 | The VND→USD rate the Plus and Pro defaults are derived with (an assumption, D-250). | Raise: lower USD caps. | 26 000 | the current rate | Wrong: caps drift from 60% of revenue. | plan caps | live |
| `ai.learner_cost.revenue_share` | Admin › Spend caps | 0.05–1; confirm above 0.8 | 0.6 | The share of a plan's monthly price its learner's AI may cost (D-248: 60% of net revenue; gross list price used until net is known). | Raise: more AI per learner. | 0.6 | owner | Above 1 is a loss per learner. | plan caps | live |
| `ai.learner_cost.hard_ratio` | Admin › Spend caps | 1–5; confirm above 3 | 1.5 | The hard ceiling as a multiple of the learner's cap: at it only free and local models answer that learner until UTC midnight. | Raise: the economy model answers longer. | 1.5 | 1.5 | Below 1 is refused at start. | plan caps | live |
| `ai.learner_cost.economy_model` | Admin › Spend caps | `gemini/gemini-3.1-flash-lite`, `gemini/gemini-3.5-flash-lite`, `none` | `gemini/gemini-3.1-flash-lite` | The paid model a learner's calls use between the cap and the hard ceiling. `none`: only free and local models. | — | default | default | A model the provider does not offer leaves only free rungs. | plan caps | live |
| `agent.daily_spend_cap_usd` | Admin › Spend caps; pin `AGENT_DAILY_SPEND_CAP_USD` | USD 0.01–10 000, or "no cap"; confirm above 50 | no cap | Daily cap on Orena chat and voice. It fails closed when the store was never read. | Raise: more Orena use. Lower: Orena pauses sooner. | **Remove `AGENT_DAILY_SPEND_CAP_USD` from `runtime.env`** so Admin governs it; set it at or below the 2 USD ceiling | At or below the ceiling. Never "no cap". | "No cap" leaves only the system ceiling. | ceiling, `agent.*` limits | live (Admin); restart (pin) |
| `media.daily_cap_usd` | Admin; pin `MEDIA_DAILY_CAP_USD` | USD 0–10 000; confirm above 250 | 25 | Daily cap on media import AI and speech recognition (admin imports). | Raise: more imports per day. | under the ceiling | 10–25, under the ceiling | Above the ceiling it has no effect; 0 blocks every import. | batch caps, price estimates | live |
| `media.batch_cap_asr_usd` | Admin; pin `MEDIA_ASR_BATCH_CAP_USD` | USD 0–1 000; confirm above 50 | 5 | Speech-recognition cost allowed for one import batch. | Raise: longer items. Lower: a batch stops early. | 2 | 5 | Too low: long videos fail. | `media.asr_max_seconds` | live |
| `media.batch_cap_ai_usd` | Admin; pin `MEDIA_AI_BATCH_CAP_USD` | USD 0–1 000; confirm above 100 | 10 | AI (translation, correction) cost allowed for one batch. | As above. | 3 | 10 | As above. | `media_translation` | live |
| `media.asr_usd_per_hour` | Admin; pin `MEDIA_ASR_USD_PER_HOUR` | 0.001–100 | 0.04 | Price estimate the media caps use for speech recognition. | Raise: caps bind sooner. | 0.04 | the provider's list price | Below the real price, the caps under-count. | media caps | live |
| `media.ai_usd_per_million_tokens` | Admin; pin `MEDIA_AI_USD_PER_MILLION_TOKENS` | 0.001–1 000 | 1.0 | Price estimate for media AI tokens of an unpriced model. | As above. | 1.0 | the real blended price | As above. | media caps | live |
| `media.supadata_daily_requests` | Admin; pin `MEDIA_SUPADATA_DAILY_REQUESTS` | 0–1 000 (0 = off) | 20 | Most Supadata caption requests per UTC day (credits). | Raise: more fallback captions. | 20 | per plan credits | Too high: credits run out. | `media.caption_source` | live |
| `word_tts.spend_cap_usd` | Admin; pin `WORD_TTS_SPEND_CAP_USD` | USD 0–1 000; confirm above 50 | 5 | Lifetime cap on Azure word-audio synthesis. | Lower: the local or device voice answers sooner. | 1 | 5 | Low; a fallback voice is used. | `KOKORO_TTS_URL` | live |
| `word_translation.daily_spend_cap_usd` | Admin; pin `WORD_TRANSLATION_DAILY_SPEND_CAP_USD` | 0–100; confirm above 5 | 0.5 | Daily cap on the paid standby of word translation, **per learner** (D-250; background work with no account: the capability's total). At the cap only the free pool answers. | Raise: more paid fallback. | **0.25**, capability on (owner) | 0.25–2 | 0: a tap can fail while the free pool is busy. | `word_translation` capability | live |
| `word_sense_choice.daily_spend_cap_usd` | Admin; pin `WORD_SENSE_CHOICE_DAILY_SPEND_CAP_USD` | 0–100; confirm above 5 | 0.25 | Daily cap on the paid rungs of choosing a word's sense in context, per learner (D-250). | As above. | **0.25**, capability on (owner) | 0.25–1 | 0: the neutral sense is shown. | `word_sense_choice` capability | live |
| `writing_evaluator.`, `writing_improver.`, `text_discussion.daily_spend_cap_usd` | Admin; pins `WRITING_EVALUATOR_…`, `WRITING_IMPROVER_…`, `TEXT_DISCUSSION_DAILY_SPEND_CAP_USD` | 0–100; confirm above 5 | 0 (no paid backup) | Daily cap of a routed capability's reviewed paid backup, per learner (D-250). Applies only while the capability is in `ORENA_CAPABILITY_ROUTING`. | Raise: a paid backup may answer. | 0 (owner, H7-8) | owner | Above 0 with an unreviewed backup costs money. | `ORENA_CAPABILITY_ROUTING` | live |
| `cost.free_tier.groq`, `.supadata`, `.gemini` | Admin › Spend caps | bool | on / on / off | Marks a provider account as on a free plan. Cost events are stamped and reported apart from real spend. It never zeroes a cap. | Switch when the account plan changes. | match the real accounts | off for every paid account | Wrong: the cost report mislabels spend. | Admin › AI › Costs | live |
| `FUNDING_ENFORCEMENT` | env, **(c)** | off / log / enforce | off | Paid-provider backstop: no funded admission means no paid call (PR-MON-6). | Stricter: log, then enforce. | off | enforce once billing is live | Enforce before admissions exist refuses paid AI. | `ORENA_FUNDING_ADMISSIONS` | restart |

## 3. Orena (agent) and live voice

| Name | Set in | Type / range | Default | Meaning | Raise / lower | Pilot | Production | Risk if wrong | Related | Applies |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `AGENT_ENABLED` | env, (b) gate | bool | off | Builds the Orena runtime and its routes (D-146). | — | true | true after review | — | provider credential, agent cap | restart |
| `AGENT_VOICE_ENABLED` | env, (b) gate | bool | off | Paid live voice; the human's activation (D-169). | — | false | owner gate | cost | `voice.*`, `orena.voice` plan limit | restart |
| `agent.turns_per_window` | Admin › Orena | 1–600 | 12 | Learner turns per rate window. | Raise: chattier. Lower: throttles. | 12 | 12–20 | Too high: abuse cost. | `agent.rate_window_seconds` | live |
| `agent.capability_reads_per_window` | Admin | 1–6 000 | 60 | Tool reads per window. | — | 60 | 60 | — | — | live |
| `agent.rate_window_seconds` | Admin | 10–3 600 s | 60 | The window of the two limits above. | — | 60 | 60 | — | — | live |
| `agent.max_input_tokens_per_turn` | Admin | 4 000–200 000 | 48 000 | Input token budget per turn. | Raise: more context and more cost per turn. | 48 000 | 32 000–48 000 | Too high: cost per message. | memory pack | live |
| `agent.model_openings_per_window`, `agent.opening_window_seconds`, `agent.opening_max_output_tokens` | Admin | 1–20; 60–86 400 s; 50–1 024 | 1; 1 800; 200 | Model-written greetings. | — | defaults | defaults | — | — | live |
| `voice.resumption` | Admin; pin `AGENT_VOICE_RESUMPTION` | bool | on | Resume a dropped voice session. | — | on | on | — | — | live |
| `voice.session_cap_seconds` | Admin | 60–3 600 s | 900 | Longest voice session. | — | 900 | 900 | — | `orena.voice` | live |
| `voice.chunk_units` | Admin (confirmed, charging) | 1–10 | 2 | Messages charged per voice chunk. | Raise: charges more. | 2 | owner | charges learners | `voice_seconds_per_message` | live |
| `AGENT_LEARNER_PACK` | env, (b) | on / off (strict) | off | Sends the learner profile pack to the model. | — | per review | per review | privacy | data classes | restart |
| `AGENT_PROMPT_LAYOUT`, `AGENT_STABLE_TOOLS` | env, (b) | legacy / stable; on / off (strict) | legacy / off | Prompt-cache layout (benchmark-gated). | — | legacy / off | after the benchmark | quality regressions | — | restart |
| `AGENT_PROVIDER_DATA_CLASSES` | env seed; Admin › AI › Data classes wins once saved | `provider[:model]=none\|learning_profile\|full_memory` | none for all | Which learner data each provider may receive. | — | in Admin | in Admin | privacy leak if too broad | `AGENT_MEMORY_HMAC_KEYS` | live (Admin) |
| `AGENT_MEMORY_HMAC_KEYS` | env, **(a)** | `v<n>:<32+ chars>`, comma list | unset (no Orena Memory) | Signing keys of Orena Memory. | — | set | set and rotated | a leak allows memory forgery | backbone | restart |
| `agent.memory_retention_sweep` | Admin › Feedback & retention (confirmed, delete); pin `AGENT_MEMORY_RETENTION_SWEEP` (strict on/off) | bool; on public runtimes on-only | off | Deletes Orena Memory notes unused for 180 days (a published promise). | — | on (the :8000 deploy script requires the variable to be present as exactly `on` or `off`; it does not check which, so set `on`) | on | Off breaks the Privacy Policy. | published promises | live (Admin); restart (pin) |

## 4. Speech, rates, feedback and retention

| Name | Set in | Type / range | Default | Meaning | Raise / lower | Pilot | Production | Risk if wrong | Related | Applies |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `speech.take_max_seconds` | Admin › Speech | 10–900 s | 300 | Longest recorded take. | — | 300 | 300 | — | `pronunciation.audio` meter | live |
| `speech.asr_daily_seconds` | Admin; pin `SPEECH_ASR_DAILY_SECONDS` | 60–86 400 s | 3 600 | Daily speech-recognition brake per account. | Raise: more Speaking. | 3 600 | per cost model | cost | ceiling | live |
| `speech.pronunciation_max_concurrent` | Admin; pin `PRONUNCIATION_MAX_CONCURRENT` | 1–32 | 8 | Parallel Azure assessments. | Raise: throughput and 429s. | 4–8 | per Azure tier | Azure 429s | — | live |
| `speech.no_speech_charged` | Admin (confirmed, charging) | bool | on | Charges a take with no speech. | — | owner | owner | charges learners | — | live |
| `rate.speech_ai_per_10min`, `rate.writing_ai_per_10min`, `rate.essay_ai_per_10min`, `rate.dictionary_ai_per_10min`, `rate.reading_ai_per_10min` | Admin › Rates | 1–5 000 (speech 5–5 000) | 60 / 30 / 30 / 120 / 300 | Per-account request rate on paid routes. | Lower: an abuse brake. | defaults | defaults | Too low: real learners get 429. | quota | live |
| `rate.media_learning_per_hour` | Admin › Media | 1–1 000 | 30 | Per-account media learning requests per hour. | — | 30 | 30 | — | — | live |
| `rate.signin_start_per_10min`, `rate.signin_callback_per_10min`, `rate.signin_exchange_per_10min` | Admin › Rates | 1–5 000 | 120 / 200 / 200 | Per client address; a shared NAT shares the limit. | — | defaults | defaults | Too low locks out a school NAT. | — | live |
| `feedback.daily_limit` | Admin › Feedback | 1–100 | 10 | Feedback items per learner per day. | — | 10 | 10 | — | — | live |
| `feedback.retention_sweep` | Admin (confirmed, delete); pin `FEEDBACK_RETENTION_SWEEP` | bool; on public runtimes on-only | off | Deletes feedback past `feedback.retention_days` (published: 24 months). | — | on | on | Off breaks the promise. | `feedback.retention_days` | live |
| `feedback.retention_days` | Admin (delete) | 30–730 | 730 | Feedback retention; can only be shortened. | — | 730 | 730 | — | Privacy Policy | live |
| `agent.turn_retention_sweep` / `agent.turn_retention_days` | Admin; pin `AGENT_TURN_RETENTION_SWEEP` (delete) | bool, on public runtimes on-only / 7–90 | off / 90 | Agent activity rows. | — | on / 90 | on / 90 | Off breaks the promise. | — | live |
| `ai_costs.retention_days` | Admin (delete) | 90–396 | 396 | AI cost rows (13 months); no switch. | — | 396 | 396 | — | — | live |
| `usage.retention_sweep` | Admin (confirmed, delete); pin `USAGE_RETENTION_SWEEP` (strict on/off) | bool; on public runtimes on-only | off | Deletes usage counts past 12 months (PRE-502 R8). | — | on, in Admin | on | Off breaks the promise. | published promises | live (Admin); restart (pin) |
| `admin_audit.retention_sweep` | Admin (confirmed, delete); pin `ADMIN_AUDIT_RETENTION_SWEEP` (strict on/off) | bool; on public runtimes on-only | off | Deletes admin audit rows past 24 months. | — | on, in Admin | on | Off breaks the promise. | published promises | live (Admin); restart (pin) |
| `AZURE_PRONUNCIATION_EN_LOCALE`, `AZURE_PRONUNCIATION_ZH_LOCALE`, `AZURE_PRONUNCIATION_ENABLE_PROSODY` | env, (b) | locale; bool | en-US, zh-CN, false | Azure assessment locale and prosody. | — | defaults | defaults | A wrong locale gives wrong scores. | — | restart |
| `AZURE_PRONUNCIATION_TIMEOUT_SECONDS`, `AZURE_PRONUNCIATION_MAX_BYTES`, `AZURE_PRONUNCIATION_MAX_REFERENCE_CHARS`, `DEMO_PRONUNCIATION_MAX_*` | env, (b) provider limits | s; bytes; chars | 30; 8 MiB; 1 200 | Provider hard limits. | — | defaults | defaults | Above the provider's limit: errors. | — | restart |
| `PRONUNCIATION_PROVIDER` | env, (b) | azure / none / demo (demo refused on public runtimes) | Azure when a key exists, else none | Which scorer is used. | — | empty (Azure) | azure | demo gives fake scores | Azure keys | restart |
| `GROQ_ASR_MODEL`, `GROQ_ASR_TIMEOUT_SECONDS`, `GROQ_ASR_MAX_BYTES` | env, (b) | model; s; bytes | whisper-large-v3-turbo; 120; 24 MiB | Speech recognition. | — | defaults | defaults | — | — | restart |

## 5. Media import, Listening, Reading and Vocabulary

| Name | Set in | Type / range | Default | Meaning | Raise / lower | Pilot | Production | Risk if wrong | Related | Applies |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `media.asr_max_seconds` | Admin › Media; pin `MEDIA_ASR_MAX_SECONDS` | 60–43 200 s | 5 400 | Longest audio recognised per item. | Raise: longer videos, more cost. | 5 400 | 5 400 | — | batch caps | live |
| `media.model_clips_enabled`, `media.model_clip_max_lines` | Admin; pins `MEDIA_MODEL_CLIPS`, `MEDIA_MODEL_CLIP_MAX_LINES` | bool; 10–5 000 | on; 500 | Cut model-line clips. | — | on; 500 | on; 500 | disk use | — | live |
| `media.caption_source` | Admin; pin `MEDIA_CAPTION_SOURCE` | youtube / supadata_native / youtube_then_supadata_native | youtube | Where YouTube captions come from (D-215). | — | youtube | owner | Supadata credits | `MEDIA_TRANSCRIPT_FALLBACK` | live |
| `media.zh_scripts_accepted` | Admin | simplified / any | simplified | Refuse Traditional-script caption tracks (D-218). | — | simplified | simplified | — | — | live |
| `reading.source_poll_interval_seconds` | Admin › Media; pin `READING_SOURCE_POLL_INTERVAL_SECONDS` | 0–86 400 s (0 = off) | 900 | How often the Reading worker checks approved RSS/Atom sources. The worker re-reads it every tick. | Lower: fresher articles, more fetches. | 900 | 900–3 600 | 0: no new articles. | Admin › Reading per-source `auto_publish`, `image_policy` | live |
| `vocabulary.general_catalogue_enabled` | Admin › Vocabulary | bool | on | The derived General word catalogue (D-188). | — | on | on | — | — | live |
| `MEDIA_TRANSCRIPT_FALLBACK` | env, (b) | none / supadata (strict; supadata needs a key) | none | Builds the Supadata fallback client at start. | — | none | owner | Overlaps `media.caption_source` (see §9). | `SUPADATA_*` | restart |
| `MEDIA_TRANSLATION_PROVIDER`, `READING_TRANSLATION_PROVIDER` | env, (b) | groq / ai / local | groq with a Groq key / local | Translation engine wiring. | — | owner | owner | — | `media_translation` | restart |
| `MEDIA_PRETRANSLATE_LANGUAGES` | env | comma list | vi | Support languages pre-translated at import. | Add: more cost per import. | vi | vi, plus zh or en when used | Missing: learners wait for on-demand translation. | — | restart |
| `MEDIA_PIPELINE_WORKERS`, `MEDIA_FALLBACK_START_WORKERS`, `READING_WORKER_CONCURRENCY` | env, (b) pool sizes | int; 1–32; 1–8 | 2; 4; 1 | Worker pool sizes. | Raise: throughput and RAM. | 2; 4; 1 | per host | RAM, provider 429s | — | restart |
| `MEDIA_PIPELINE_INLINE` | env, (b) dev and tests | bool | off | Runs the pipeline inside the request. | — | off | off | — | — | restart |
| `GROQ_TRANSLATION_MODEL`, `GROQ_TRANSLATION_MAX_COMPLETION_TOKENS`, `GROQ_TRANSLATION_OUTPUT_TOKENS_PER_MINUTE` | env | model; 256–8 192; ≤ 10 M or unset | openai/gpt-oss-120b; 2 048; learnt | Groq translation model, output reservation and rate. | — | defaults | the account's limits | Too high: 413 or 429 storms. | — | restart |
| `MEDIA_RIGHTS_CLEARED_PROVIDERS`, `MEDIA_RIGHTS_CLEARED_HOSTS` | env, (b) human rights gate | comma lists | empty | Sources whose rights are cleared. | — | owner per source | owner | rights breach | Admin › Content rights | restart |
| `SUPADATA_REQUEST_TIMEOUT_SECONDS`, `SUPADATA_MAX_WAIT_SECONDS`, `SUPADATA_POLL_INTERVAL_SECONDS` | env, (b) | s | 20; 150; 1 | Supadata client timing. | — | defaults | defaults | — | — | restart |
| `ENABLE_DEV_LISTENING_CATALOG` | env, (b) dev only (refused on public runtimes) | bool | off | The generated dev overlay. | — | off | off | — | — | restart |
| `DEFAULT_SUPPORT_LANGUAGE` | env, (b) | a supported BCP-47 tag | en | The deployment's neutral support language. | — | en | en | — | — | restart |
| `VOCABULARY_PIVOT_PAIRS`, `LOCAL_TRANSLATION_URL`, `MAX_LOADED_TRANSLATION_MODELS`, `KOKORO_TTS_URL`, `KOKORO_READING_AWARE` | env, (b) | pairs; URL; int; URL; "1" | empty; http://local-translator:8090; 2; empty; off | Local translation and word voice services. | — | defaults | defaults | RAM; wrong polyphone readings | `word_tts.spend_cap_usd` | restart |

## 6. Plans, quota and billing

**Admin › Plans** (`product.plan_catalog`, no environment layer) holds the meter limits and prices. The code owns each
meter's window and unit; an administrator edits only the numbers (≤ 10 000 000) and the prices (≤ 10⁹). Changes apply
live.

| Meter | Window | Free | Plus | Pro | Enforced (wired) |
| --- | --- | --- | --- | --- | --- |
| `orena.message` (`voice_seconds_per_message` 1–3 600, default 60) | day | 20 | 200 | 1 000 | yes |
| `writing.review` | month | 2 | 10 | 50 | yes |
| `pronunciation.audio` (minutes) | month | 5 | 30 | 120 | yes |
| `media.import` (minutes) | month | 15 | 120 | 600 | yes |
| `languages.target` | count | 1 | 2 | 2 | yes (count cap) |
| `word.assist` / `reading.assist` / `writing.task` | day | 30 / 10 / 5 | 300 / 100 / 30 | 1 500 / 500 / 100 | no: catalogue only |
| `orena.voice` (on/off and minutes, D-248) | month | off | 100 min (6 000 s) | 300 min (18 000 s) | a plan feature, enforced whatever the quota switch says |
| `progress.weekly_report` (on/off, D-248) | — | off | on | on | a plan feature (the server check on the weekly report route is the Intelligence lane's) |
| `media.tools_weekly` (videos with Orena's look-up, D-248) | week (ISO, Monday) | 3 | 10 000 | 10 000 | yes, when the quota switch lists it and `access.enforced` is on; Plus and Pro are never metered (full tools) |
| Prices (USD / VND, monthly and yearly) | — | 0 | 9.99 / 199 000; 79.99 / 1 590 000 | 19.99 / 399 000; 159.99 / 3 190 000 | display only while billing is off |

| Name | Set in | Type / range | Default | Meaning | Raise / lower | Pilot | Production | Risk if wrong | Related | Applies |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Quota switch `product.quota_enforcement` | Admin › Policies (first block), **(c)** on public runtimes on-only; pin `ORENA_QUOTA_ENFORCEMENT` | on / off | off | Whether plan limits are enforced. | Admin may switch it on; off is refused on staging and production. | **on, pinned** (the code requires :8000 to pin it) | on, pinned | Off: unlimited use on Free. | `ORENA_QUOTA_METERS` | live (Admin); restart (pin) |
| Enforced meters | Admin; `ORENA_QUOTA_METERS` is a floor | a subset of the wired meters | none | Which limits are enforced: the variable's meters plus any Admin adds while its switch is on. | Admin may add; removing one is refused on staging and production. | **pinned to all 5 wired meters** | all wired meters | A missing meter is not counted. | catalogue | live (Admin); restart (pin) |
| `quota.abandoned_settles` | Admin (confirmed, charging) | admitted / zero | admitted | What a reservation whose worker died costs. | — | admitted | owner | — | — | live |
| `billing.domestic_late_payment_grace_hours` | Admin › Billing (charging) | 0–168; 0 = unconfigured | 0 | SePay late-payment grace. 0 makes every SePay payment fail closed. | — | 0 (no SePay) | 1 (owner, PR-MON-8) | 0 in production with SePay: no payment is granted. | `BILLING_DOMESTIC_GATEWAY` | live |
| `billing.past_due_grace_hours` | Admin › Billing (confirmed, charging); pin `BILLING_PAST_DUE_GRACE_HOURS` | 0–336 h | 48 (owner, 2026-10-13) | How long a Polar `past_due` subscription keeps its paid plan. | Raise: longer free use after a failed payment. | 48 | 48 | Long: free use after a failed payment. 0: the plan drops at once. | Polar | live (Admin); restart (pin) |
| `billing.new_sales` | Admin › Billing (confirmed, charging); pin `BILLING_NEW_SALES` | bool | on | Off pauses new checkouts only. Webhooks, the portal and the reconciler keep running (PR-MON-10). | — | n/a while billing is off | on; off during an incident | A pause left on loses sales. | billing readiness | live (Admin); restart (pin) |
| `BILLING_ENABLED`, `BILLING_PRICES_FILE`, `CREDITS_ENABLED`, `ORENA_FUNDING_ADMISSIONS`, `BILLING_DOMESTIC_GATEWAY`, `BILLING_CREDIT_PACKS_FILE`, `BILLING_METER_PRICES_FILE`, `BILLING_PROMOTIONAL_GRANTS_FILE`, `BILLING_COST_GATE_FILE`, `SEPAY_FEED_ENABLED`, `POLAR_ENVIRONMENT` | env, (b) payment gates | flags; JSON paths on `/data`; sandbox / production | off / unset; Polar `sandbox` | Commerce activation and the approved price files. | — | off | owner gates 7a / 7b | selling without approval | `docs/billing/` runbooks | restart |
| `BILLING_RECONCILE_INTERVAL_SECONDS`, `BILLING_PULL_AFTER_SECONDS`, `BILLING_PULL_PER_TICK`, `BILLING_PULL_HORIZON_DAYS` | env, (b) internal | ≥ 5 s; ≥ 0 s; ≥ 1; ≥ 1 day | 60; 120; 20; 14 | Payment reconciler cadence. | — | defaults | defaults | Too fast: provider rate limits. | — | restart |
| Account plan grant | Admin › Accounts (D-154) | plan and an optional end date | Free | Give a learner Plus or Pro by hand. | — | pilot testers | support cases | — | catalogue | live |
| `access.enforced` | Admin › Policies › Content access (confirmed) | bool | off | D-248 content gating: on, a Free learner is refused a Plus Reading body or a Plus video tool (403 `plan_required`). Off, the tiers and the private cache of a paid body still apply. Videos always play. | Turn on with the learner locked state (MV2-3). | off until MV2-3 | on | On before the locked state ships: Free learners see an error. | `product/content_access.py` | live |
| `access.reading_free_percent` | Admin › Policies › Content access | 0–100 | 30 | About this share of each (language, level) of Reading is Free, by a stable per-article bucket with a floor. | — | 30 | 30 | — | rotation | live |
| `access.reading_rotation_per_week` | Admin › Policies › Content access | 0–50 | 2 | More Reading articles of each (language, level) Free each ISO week, on a deterministic rotation. | — | 2 | 2 | — | — | live |
| `access.set_free_items` | Admin › Policies › Content access | 0–50 | 1 | The first items of each set (vocabulary collection, grammar function, mock test) that are Free. | — | 1 | 1 | — | — | live |
| Content access overrides `product.content_access` | `PUT /api/product/admin/content-access` (audited; Admin page later) | ≤ 2 000 `<kind>:<id>` → free / plus / pro | none | Force one item Free or paid. A video can only be made Free (watching is never sold). | — | — | editorial | — | — | live |

## 7. AI providers, routing and models

| Name | Set in | Type / range | Default | Meaning | Pilot | Production | Risk if wrong | Related | Applies |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Capability rows: `writing_evaluator`, `writing_linguistic`, `reading_generator`, `writing_task_generator`, `writing_improver`, `learner_dictionary`, `learner_translation`, `word_translation`, `word_sense_choice`, `media_translation`, `media_transcript_correction`, `grammar_lesson_generator`, `text_discussion`, `reading_evaluator` | Admin › AI (`ai.capability.<key>`) | enabled, provider, model, backup, `timeout_seconds`, temperature, fallback policy | the legacy selection | Which model answers each job. Privacy rules refuse a free or logging provider for learner text. | `word_translation` and `word_sense_choice` **on** (owner); the rest as reviewed | the reviewed chain per capability | Learner text reaching a provider that may log it (the guard refuses this). | data classes, caps | live |
| `ai.active_selection` | Admin › AI (deprecated `PUT /api/admin/ai/config`) | provider and model | Ollama `OLLAMA_MODEL` | The legacy single selection. | set | replace with capability rows | — | `AI_RUNTIME_MODE` | live |
| `AI_RUNTIME_MODE` | env, (b) | legacy / capability | legacy | Learner routing mode. | capability | capability | the legacy path is used | — | restart |
| `ORENA_CAPABILITY_ROUTING` | env | a comma subset of `writing_evaluator`, `writing_improver`, `text_discussion` | empty | Moves a capability onto its reviewed chain with a paid backup (PR-MON-7A). | empty | owner per capability | — | `*_daily_spend_cap_usd` | restart |
| `ALLOW_FALLBACK` | env, (b) | bool | false | Legacy local fallback. | false | false | — | — | restart |
| `CLOUD_AI_TIMEOUT`, `OLLAMA_TIMEOUT`, `OLLAMA_CLOUD_TIMEOUT` | env, (b) | s | 180; 180; 120 | Provider default timeouts; a capability's `timeout_seconds` overrides them. | defaults | defaults | — | — | restart |
| `OLLAMA_URL`, `OLLAMA_MODEL`, `*_BASE_URL`, `AZURE_SPEECH_REGION` | env, (b) | URL or id | provider defaults | Endpoints. | — | — | — | — | restart |
| `OPENAI_MODELS`, `DEEPSEEK_MODELS`, `GEMINI_MODELS`, `GROQ_MODELS`, `OPENROUTER_MODELS`, `OLLAMA_CLOUD_MODELS`, `AZURE_OPENAI_DEPLOYMENTS` | env, (b) | comma lists | per compose | Model allowlists Admin may choose from. | — | reviewed models only | An unreviewed model becomes selectable. | capability rows | restart |
| `ORENA_ENVIRONMENT_LABEL` / `ORENA_ENV_LABEL` | env, (b) | text | local | Labels cost events and the Admin header. | staging-8000 | production | mixed cost reports | — | restart |
| `ai.health_window_minutes` | Admin › Policies › Provider health | 1–120 min | 10 | How far back recorded AI calls count for provider health (docs/operations/PROVIDER_HEALTH.md). | 10 | 10 | Too long: an old outage keeps alerting. | health check | live |
| `ai.health_consecutive_failures` | Admin › Policies › Provider health | 1–50 | 3 | Failures in a row that alert (a spending cap or a rejected key alerts at the first). | 3 | 3 | Too high: learners notice first. | health check | live |
| `ai.health_window_failures` | Admin › Policies › Provider health | 1–1000 | 3 | Failures inside the window that alert. | 3 | 3 | Too low: noise. | health check | live |
| `ai.breaker_hard_cooldown_minutes` | Admin › Policies › Provider health | 1–1440 min | 30 | How long the router skips a provider after a spending cap (that model) or a rejected key (the provider); then one request probes. | 30 | 30 | Too short: every request pays a failed call first. | capability backups | live |
| `ai.breaker_rate_limit_failures` | Admin › Policies › Provider health | 1–20 | 3 | Rate limits in a row that stand a provider down for the shorter pause. | 3 | 3 | — | — | live |
| `ai.breaker_rate_limit_cooldown_seconds` | Admin › Policies › Provider health | 10–3600 s | 120 | How long a rate-limited provider is skipped. | 120 | 120 | Too long: a free tier that recovered is left idle. | — | live |

## 8. Infrastructure, identity, secrets and activation gates (environment only, restart)

| Name(s) | Class | Default | Meaning |
| --- | --- | --- | --- |
| `APP_ENV` | (b) | development | development / staging / production. Staging and production apply every public guard, and the fuses above become tighten-only. |
| `PUBLIC_BASE_URL`, `GOOGLE_REDIRECT_URI` | (b) | loopback | The HTTPS origin; the callback must share it. |
| `GOOGLE_CLIENT_ID` | (b) | empty | Sign-in is on when it is set with the secret. |
| `GOOGLE_CLIENT_SECRET`, `SESSION_SECRET` (32+ characters) | (a) | empty | Refused at start on public runtimes when missing. |
| `BOOTSTRAP_OWNER_EMAIL`, `PLATFORM_ADMIN_EMAILS`, `ALLOW_LOCAL_ADMIN` | (b) | empty | Admin identity; local admin is never available on public runtimes. |
| `NATIVE_AUTH_ENABLED` | (b) | off | Native app sign-in (mobile is frozen). |
| `LEGAL_EFFECTIVE_DATE` | (b) | empty | Required in production (D-233). |
| `PERSISTENCE_BACKEND`, `POSTGRES_RUNTIME_URL`, `POSTGRES_SHADOW_URL` | (b); the URLs carry a password, so treat them as (a) | postgresql | PostgreSQL is authoritative. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | (b) / (a) | compose dev values | The database container. |
| `WRITING_DB`, `AUTH_DB`, `PLATFORM_DB`, `PRODUCT_DB`, `VOCABULARY_DB`, `LEARNING_CACHE_DB` | (b) | `data/*.db` | SQLite archive and cache paths. |
| `USER_DATA_ROOT`, `MEDIA_LIBRARY_ROOT`, `MEDIA_LIBRARY_ASSET_ROOT`, `READING_LIBRARY_ASSET_ROOT`, `WORD_AUDIO_ASSET_ROOT`, `WORD_DEEP_ASSET_ROOT`, `ORENA_DELETION_LOG` | (b) | repo-relative; `/data/...` in compose | Must be on the volume. |
| `ORENA_PUBLISHED_BIND_HOST`, `ORENA_INSECURE_DEV_LAN_BIND_HOST`, `ORENA_TRUST_DOCKER_PUBLISHED_PORT`, `APP_BIND_HOST` | (b) | 127.0.0.1; 1 | The loopback boundary (issue #137). |
| `CLOUDFLARE_TUNNEL_TOKEN` | (a) | empty | The public tunnel. |
| `AI_PROVIDER_SECRETS_KEY` | (a) | empty | Encrypts the provider keys saved in Admin; without it Admin refuses to save a key. |
| `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_CLOUD_API_KEY`, `AZURE_OPENAI_API_KEY`, `AZURE_SPEECH_KEY`, `SUPADATA_API_KEY` | (a) | empty | The environment fallback; a key saved in Admin wins. |
| `POLAR_ACCESS_TOKEN`, `POLAR_WEBHOOK_SECRET`, `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY`, `SEPAY_WEBHOOK_SECRET`, `SEPAY_API_TOKEN` | (a) | empty | Payment credentials. |
| `SEPAY_ACCOUNT_NUMBER`, `SEPAY_ACCOUNT_NAME`, `SEPAY_BANK_BIN`, `SEPAY_VA_NUMBER`, `SEPAY_PAYMENT_PREFIX`, `SEPAY_API_BASE` | (b), sensitive | empty | Bank receiving details. |
| `VOCAB_INGEST_TOKEN_SHA256` | (a) | empty | The service ingest token hash. |
| `ORENA_ACCOUNT_BACKBONE`, `ORENA_PRACTICE_SESSION`, `ORENA_READING_PRACTICE_SUBMIT` | (b) gates tied to migrations | off | On for :8000 (backbone and practice session). |
| `ORENA_LIMIT_IMPORT_TOMBSTONES` | (b) | 360 (floor 52) | A learner-record bound. |
| `HF_HOME`, `TRANSFORMERS_OFFLINE`, `BASE_IMAGE`, `APP_VERSION`, `ORENA_BACKUP_DIR`, `CONTENT_PACK_LOG` | (b) container, build and scripts | — | Not read by the application. |
| `daily_backup_8000.ps1` parameters (not environment): `-MinFreeRamGBDump`, `-MinFreeRamGB`, `-MinFreeDiskGB`, `-RetryUntil`, `-RetryEveryMinutes`, `-OffsiteDir`, `-OffsiteKeyFile`, `-OffsiteKeepCount`, `-VerifyOffsite`, `-NoOffsite`, `-DryRun` | (b) the :8000 backup task, set at registration | 0.8 GB; 2 GB; 5 GB; 06:00; 30 min; `%USERPROFILE%\OneDrive\Orena-Backups`; `%LOCALAPPDATA%\orena-product\offsite-backup.key` (path only, its content is (a)); 14 sets; off; off; off | Not read by the application. Meaning, exit codes and the re-registration command: `docs/project/RELEASE_8000_READINESS.md` section 12. |

## 9. Open decisions

1. **`MEDIA_TRANSCRIPT_FALLBACK` (env) and `media.caption_source` (Admin) overlap.** A Supadata mode in Admin while the
   variable is `none` may leave no client to call. They should become one setting.
2. **Plan prices.** The prices in Admin › Plans are display only; the sold prices come from `BILLING_PRICES_FILE` and
   the credit and meter files. The two could disagree once billing is live.
3. **Provider keys.** They are secrets, but Admin stores them encrypted and that store wins over the environment.
   Whether production should drop the environment fallback is a decision.
4. **Still environment-only tunables**: `ORENA_CAPABILITY_ROUTING`, `MEDIA_PRETRANSLATE_LANGUAGES`, the Groq
   translation limits and an optional stricter-only `FUNDING_ENFORCEMENT`. Each needs its own small change.

---

## 10. Test → production checklist

Do these in order on the runtime being promoted. Each step names where the value is set.

**Environment (the env file; a restart applies it)**

1. `APP_ENV=production`, with an HTTPS `PUBLIC_BASE_URL`, complete Google OAuth, a 32+ character `SESSION_SECRET` and
   `LEGAL_EFFECTIVE_DATE`. The app refuses to start without them.
2. `AI_DAILY_SPEND_CEILING_USD` (the spend monitor's alert threshold, D-250) set from the cost model. Staging and
   production refuse to start without it and without the per-learner caps. (Pilot: 2; it now alerts, never pauses AI.)
3. `ORENA_QUOTA_ENFORCEMENT=on` and `ORENA_QUOTA_METERS` listing every wired meter.
4. Secrets present for the providers in use, `AI_PROVIDER_SECRETS_KEY` and `AGENT_MEMORY_HMAC_KEYS`.
5. **Remove every tunable pin you did not mean as a fuse**: `AGENT_DAILY_SPEND_CAP_USD`, `AI_DAILY_SPEND_WARN_RATIO`,
   `BILLING_PAST_DUE_GRACE_HOURS`, `BILLING_NEW_SALES`, `READING_SOURCE_POLL_INTERVAL_SECONDS`, `MEDIA_*_CAP_USD`,
   `WORD_*`, `SPEECH_ASR_DAILY_SECONDS`, and the sweep variables you want Admin to hold. A pin locks the Admin field.
6. Payment and activation gates stay off until the owner's gate for each (`BILLING_ENABLED`, `CREDITS_ENABLED`,
   `ORENA_FUNDING_ADMISSIONS`, `AGENT_VOICE_ENABLED`, `FUNDING_ENFORCEMENT`).
7. `ORENA_ENVIRONMENT_LABEL=production`.

**Admin (applies live)**

8. Policies › Spend caps: the per-learner caps (`ai.learner_cost.*`: Free 0.02, Plus and Pro by the formula, hard
   ratio 1.5, the economy model offered by the provider); the agent cap (never "no cap", until the Intelligence lane
   makes it per learner); `word_translation` and `word_sense_choice` caps 0.25 (per learner); the warn ratio 0.7–0.8.
9. Policies › Feedback & retention: all five sweeps show **on** (the public-runtime default) and none is pinned `off`.
   They cannot be switched off on this runtime.
10. Policies › Billing: `billing.past_due_grace_hours` 48; `billing.new_sales` on once billing is approved;
    `billing.domestic_late_payment_grace_hours` 1 if SePay is used.
11. Admin › AI: each capability on its reviewed chain; `word_translation` and `word_sense_choice` on; the `cost.free_tier.*`
    flags matching the real accounts; the data classes set.
12. Admin › Plans: the approved limits and prices.

**Verify**

13. Admin's readiness summary lists no `unmet_promises`.
14. Policies & limits shows "Locked by environment" only on the settings you pinned on purpose.
15. `GET /api/admin/ai-spend` shows the monitor's threshold (`monitor_only: true`) and the agent cap you expect.
