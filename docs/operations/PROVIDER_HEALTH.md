# Provider health and the router's circuit breaker (PR BZ)

From 2026-10-19 23:17Z every Gemini call on :8000 answered HTTP 429 "Your project has exceeded its monthly spending
cap". Nobody knew until the owner saw "Orena đang bận". Owner rule: Hermes is alerted before learners notice.

## What is measured

`writing_coach/ai/health_signal.py` reads the `ai.operation` rows the runtime already writes (`audit_logs`, the shared AI
ledger). There is no new table and no new schema. Each failed row now carries a closed `failure_class`, decided from
the provider's answer when it is recorded. The provider's message itself is never kept.

| Class | Meaning | Alerts |
| --- | --- | --- |
| `spend_cap` | spending cap or prepaid credit exhausted (429 with spending-cap text, `insufficient_quota`, 402) | at once, high |
| `auth` | key rejected (401 / 403) | at once, high |
| `rate_limit` | any other 429 (per-minute quota). Gemini's per-minute 429 also says "quota" and "billing" and stays here. | threshold |
| `unconfigured` | no key, no model, a retired model (404), a disabled capability | threshold |
| `server` | 5xx | threshold |
| `timeout` | no answer in time | threshold |
| `schema` | request refused as invalid (400 / 422), unparsable answer | threshold |
| `other` | anything else | threshold |

Threshold: `ai.health_consecutive_failures` failures in a row, or `ai.health_window_failures` inside
`ai.health_window_minutes` (defaults 3, 3, 10). All three are Admin policies (Policies & limits › Provider health).
Not counted: skipped rungs (breaker, budget, privacy), an answer the capability's validator refused, a learner who
left mid-stream, a chain's closing summary row, and operator tests.

## The circuit breaker

`writing_coach/ai/routing.py` `ProviderHealth`, in each app process:

- `spend_cap`: that **model** is skipped for `ai.breaker_hard_cooldown_minutes` (30). A project cap (Gemini) stands
  each model down at its own first failure. A credit balance (OpenRouter 402) leaves the provider's free models
  answering.
- `auth`: the whole **provider** is skipped for the same time.
- `ai.breaker_rate_limit_failures` (3) rate limits in a row: the provider is skipped for
  `ai.breaker_rate_limit_cooldown_seconds` (120).
- Anything else: the existing doubling cooldown (30 s to 300 s after 3 failures).
- When the cooldown ends, one request probes (half open). If it fails again, the breaker opens again.

While a rung is down the chain goes straight to the next configured rung. That rung still passes the spend and funding
gate, the per-learner quota (checked before the request reaches the router) and the D-104 guard: a capability whose
input is `learner_text` never asks a free-tier, prompt-logging or unreviewed model, even as a backup. When every rung is
refused, nothing is sent and the caller returns its gentle error or deterministic answer.

Each switch is recorded on the answering row (or on the chain's closing row when nobody answered) as
`provider_switch: {from, to, reason, trigger}`. It holds provider ids and closed words only.

The breaker covers capability-mode calls (`generate_structured` through `run_chain`). It does not cover the legacy single
selection (`AI_RUNTIME_MODE=legacy`, no backup) or Orena agent turns (`agent_turn_fast`, which by design never switches
provider and belongs to the Intelligence lane).

## Where it is read

- **Admin:** `GET /api/admin/ai/health` (admin guard). It returns the report, this process's breaker, recent switches
  and the providers that are down. Also `providers` in `GET /api/admin/readiness-summary`.
  - Overview and AI & Models show a banner while a provider is down.
  - The AI & Models provider and routing pills show the failure and last error.
  - Operations shows the switch history.
- **Health check:** `scripts/health_check_8000.ps1` runs
  `docker exec <app> python -m writing_coach.ai.health_signal`. This is one read-only SELECT and prints one JSON line.
  It writes to `%USERPROFILE%\.orena\health\`:

```text
health.log
  2026-10-19T23:40:01Z FAIL providers status=alert severity=high window_min=10 gemini:spend_cap(high) failed=6 consecutive=6 since=2026-10-19T23:17:04Z last=2026-10-19T23:39:40Z caps=agent_turn_fast,learner_dictionary on_backup=- [spending cap reached]
  2026-10-19T23:40:01Z JSON providers {"version":1,"status":"alert","severity":"high","alerts":[...],"down":[...],"switches":[...],...}
  2026-10-19T23:40:01Z ALERT providers gemini:spend_cap raised
health.state.json
  "providers": {"status": "alert", "severity": "high", "checked_at": "...", "line": "...", "alerts": [...], "down": [...]}
```

The healthy line is `PASS providers status=ok calls=<n> window_min=10`. When the telemetry cannot be read, the check logs
`WARN providers status=unknown ...`, which is not a failure.

A high alert (spending cap or rejected key) raises the notification at once, without waiting for `-AlertAfter`. It
raises again only when the set of high alerts changes, and the run exits with code 2.

**For Hermes:** alert when `providers.severity == "high"`. Also alert when `providers.status == "alert"` on two runs in a
row.

## Report shape (version 1)

`version`, `checked_at`, `window_minutes`, `thresholds`, `available`, `truncated` (more than 500 rows in the window),
`status` (`ok` / `alert` / `unknown`), `severity` (`high` / `medium` / null).

- `alerts[]`: `provider`, `severity`, `failure_class`, `failed`, `consecutive_failures`, `last_error_at`,
  `failing_since`, `capabilities`.
- `providers[]`: per provider, with `capabilities[]` under it.
- `down[]`: `provider`, `reason`, `since`, `severity`, `on_backup`, `without_backup`, `breaker_open`,
  `seconds_remaining`.
- `switches[]`: `at`, `capability`, `from`, `to`, `reason`, `trigger`, `answered`.
- `line`: the CLI only.

Everything in the report is a count, an id, a timestamp or a closed word. It never contains a prompt, a key, a
learner's words or a provider's message.
