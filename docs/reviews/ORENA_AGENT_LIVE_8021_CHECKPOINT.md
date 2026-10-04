# Orena agent live on the lane runtime :8021 — checkpoint (2026-10-04)

Human instruction 2026-10-04: turn Orena on at :8021 (not :8011, deferred by D-102), checked in full
against AGENT_CONTRACT v5. Recorded as D-125.

## What changed

- The client no longer carries a switch. `static/orena/agent/transport.js` asks
  `GET /api/agent/capabilities` once per visit; 404 hides every Orena entry point, anything else is
  live, and a turn waits for that answer, so the mock never answers in place of a server. The
  contract mock (§11) serves only when the address forces it (`?agent=…`). `AGENT_ENABLED` on the
  server is therefore the one per-environment switch (production never serves the agent).
- :8021 web recreated with `AGENT_ENABLED=true`, everything else copied (values never printed);
  previous container kept stopped as `orena-next-verify-web-before-agent-enabled`. Schema head
  `20261004_0025` (applied earlier after pg_dump + restore check).
- Admin › AI legacy selection set to Gemini `gemini-3.5-flash-lite` on :8021 (the agent routes on the
  legacy selection until R2 activation; it never runs on a local model).

## Contract v5 evidence (live :8021)

| Check | Result |
| --- | --- |
| Agent off (before recreation): capabilities | 404 → rail "Ask Orena", field and mic absent |
| capabilities | 200, contract 5, 14 capabilities |
| Turn SSE | `session → tool_call → tool_result → segment_delta → segment_end → done` |
| 409 | target `zh-CN` against an English learner: `{"detail":"target_language_mismatch"}` |
| 429 | after 59 capability reads: `rate_limited`, `Retry-After: 28`; the client keeps Orena present |
| `context.address` | `{self: chị, user: em}` → "Chào em! Hôm nay em có 2 từ đến hạn ôn." |
| Opening turn | real data ("You have 2 words due for review today"), suggestions, no `memory_update`, no action |
| `tool_call.label` | "Đang xem từ đến hạn" (`get_due_vocabulary`); rendered while a tool runs (gate) |
| Action is an invitation | "Take me to my due review" → card "Review due words"; the route stayed `#/orena` until tapped |

Cost: 9 agent rounds, 24,487 prompt / 259 completion tokens, USD 0.008 (application telemetry), under
the shared live-provider lock. Gates: agent contract gate updated (no client switch; 200 live, 404
absent, no mock reply), all 132 CI Node gates locally 131 + the known local-only Design Contract
failure.

Limits: the `tool_call` label flashes for about a second in the browser and was not captured on
screen; voice (§9) not exercised; :8011 and :8000 unchanged.
