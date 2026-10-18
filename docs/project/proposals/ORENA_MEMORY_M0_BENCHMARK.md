# Orena Memory M0: before/after benchmark

Status: offline part run 2026-10-17 (local execution); live part run 2026-10-17 by the UI-lane coordinator session at
the owner's request (local execution on :8021, issue #256), reviewed below. Decision: `legacy` stays the default.
Proposal: `ORENA_MEMORY.md` §5.4, §7.2, §9 (M0). Script: `scripts/agent_prompt_cache_benchmark.py`.

## What M0 changed

1. **Prompt layout** (`AGENT_PROMPT_LAYOUT`, default **`legacy`**; `stable` is opt-in): with `stable` the per-turn
   context is split by how often it changes.
   The conversation's setting (languages, screen, what it offers, address, coach notes) is `context:` right after the
   instruction; this turn's part (in view, selection, earlier reads, open offer, focus, what was sent) is
   `context (this turn; ...):` after the conversation. `legacy` keeps the single context message second, as before M0.
   Owner review of PR #259 (2026-10-17): `legacy` stays the default; `stable` is enabled explicitly for the capped
   live benchmark and becomes the default only once real-provider compatibility, tool-selection parity, quality and
   latency show no material regression.
2. **Stable tool list** (`AGENT_STABLE_TOOLS`, default `off`): every round and turn lists the same tools in one order;
   the turn's rules are enforced on the calls (a call the round does not allow is answered "unavailable: not offered
   in this turn" and never runs) and the last round sends `tool_choice: none` - to OpenAI, DeepSeek and Groq only;
   any other endpoint gets no tools on that round, as before. Opening and screen-help turns keep the per-round list
   (each refused call would be a further model round, and an opening is free to the learner).
3. **Model pinned per conversation**: the active selection when the conversation's first model turn runs, kept in the
   session for every round and its rolling summary; an Admin change applies to new conversations. A pinned provider
   that can no longer stream here (removed, unconfigured, or refused by the model allowlist) is pinned again to the
   current selection on the next turn (`pinned: repinned` in the turn record); so is one whose last turn failed at the
   provider once Admin has moved the selection (an outage or retired model is not waited out for the session's
   life). A failed round still fails its own turn: nothing switches provider mid-turn. A turn that asks no model pins
   nothing.
4. **Telemetry** in the `agent.turn` record: `prompt_layout`, `tools_digest`, `model_route`, `cached_input_tokens`,
   `uncached_input_tokens`, `tool_calls`, `cost_upper_bound` (the catalogue's uncached rate: cached input is not priced
   lower there yet), beside the existing per-round first-event and end times, rounds and tokens.

## Offline result: prefix reuse (upper bound, no provider)

The same scripted conversations through the real runtime under each layout. A scripted model answers with
answers of the length the study measured; `chat` reads twice in six turns, `coaching` reads on every turn (so this
turn's context changes every turn). For each request: the longest prefix of its wire body (tools, then messages) that
an earlier request of the same conversation already sent - what an implicit prefix cache could serve at best.
Token counts are estimates (a Han character about one token, other text about four characters a token) and run high
against the study's measured ~4.3k input tokens a round; compare the shares, not the absolute numbers.

| Scenario | Layout | Lang | Requests | Input (est. tokens) | Reusable prefix | Not reusable (est. tokens) |
| --- | --- | --- | --- | --- | --- | --- |
| chat, 6 turns | legacy | en | 8 | 60,787 | 82.9% | 10,389 |
| chat, 6 turns | legacy | zh | 8 | 61,428 | 82.6% | 10,696 |
| chat, 6 turns | stable | en | 8 | 60,953 | 83.2% | 10,261 |
| chat, 6 turns | stable | zh | 8 | 61,595 | 83.0% | 10,457 |
| chat, 6 turns | stable+tools | en | 8 | 62,203 | 83.3% | 10,417 |
| chat, 6 turns | stable+tools | zh | 8 | 62,846 | 83.1% | 10,612 |
| chat, 20 turns | legacy | en | 25 | 174,376 | 88.8% | 19,538 |
| chat, 20 turns | legacy | zh | 25 | 177,632 | 88.2% | 20,962 |
| chat, 20 turns | stable | en | 25 | 174,833 | 88.2% | 20,644 |
| chat, 20 turns | stable | zh | 25 | 178,087 | 87.7% | 21,951 |
| chat, 20 turns | stable+tools | en | 25 | 178,271 | 88.3% | 20,799 |
| chat, 20 turns | stable+tools | zh | 25 | 181,524 | 87.8% | 22,106 |
| coaching, 6 turns | legacy | en | 12 | 92,138 | 87.4% | 11,611 |
| coaching, 6 turns | legacy | zh | 12 | 93,217 | 86.9% | 12,179 |
| coaching, 6 turns | stable | en | 12 | 92,388 | 88.2% | 10,934 |
| coaching, 6 turns | stable | zh | 12 | 93,465 | 88.0% | 11,208 |
| coaching, 6 turns | stable+tools | en | 12 | 94,263 | 88.2% | 11,091 |
| coaching, 6 turns | stable+tools | zh | 12 | 95,339 | 88.1% | 11,362 |
| coaching, 20 turns | legacy | en | 43 | 322,191 | 92.6% | 23,686 |
| coaching, 20 turns | legacy | zh | 43 | 328,245 | 92.1% | 25,879 |
| coaching, 20 turns | stable | en | 43 | 323,020 | 92.3% | 24,743 |
| coaching, 20 turns | stable | zh | 43 | 329,072 | 92.0% | 26,313 |
| coaching, 20 turns | stable+tools | en | 43 | 329,271 | 92.4% | 24,899 |
| coaching, 20 turns | stable+tools | zh | 43 | 335,327 | 92.1% | 26,475 |

Composition of one request (est. tokens, chat, turn 6, stable layout): tools 4,050 (4,212 with the stable list),
instruction 2,809, context (both parts) 230, conversation 479, other system messages (style, selection) 321.

### Reading

- **The layouts are equivalent within about 1.5 points.** The prefix every layout already reuses is the tool list and
  the instruction: about 87% of a request. Before M0, the single context message was also identical from turn to turn
  whenever nothing in it changed, so the conversation behind it was reusable too.
- **Where the new layout wins**: turns whose own context changes (a read, a new selection, an offer): 70-270 estimated
  tokens a turn more reusable (coaching, 6 turns: 88.1% vs 87.4%).
- **Where it loses**: turns whose context does not change pay for this turn's part again after the conversation, about
  90 estimated tokens a turn (chat, 20 turns: 88.2% vs 88.8%).
- Each rolling-summary fold (from turn 14, about every 4 turns after) ends the reusable prefix at the conversation's
  start in both layouts.
- **Stable tools** add about 160 tokens a request (tools the round does not allow are listed) and change reuse by
  0.1 points in these scripts, where the allowed list rarely changes (no open offer, no last-round cut-off). They stay
  `off`.
- What the new layout is for is mostly ahead: the M1 learner pack (up to about 2k tokens) belongs in the stable setting,
  before the conversation, where it is reused on every turn.

**No cost or latency claim follows from this.** Whether and how much a provider caches - its minimum prefix, its
block size, its hit rate - is only measurable live.

## Live run (2026-10-17, Gemini 3.5 Flash-Lite, owner-approved)

Command as below, `--repeat 2 --turns 6`, spent $0.115 of the $0.30 cap. Full JSON and the review: issue #256.

| layout (EN+ZH, 2 repeats) | rounds | input | cached | hit | USD | USD / round |
|---|---|---|---|---|---|---|
| legacy | 39 | 177,178 | 69,049 | 0.390 | 0.0406 | 0.00104 |
| stable | 39 | 180,327 | 76,942 | 0.427 | 0.0382 | 0.00098 |
| stable+tools | 35 | 166,131 | 65,113 | 0.392 | 0.0368 | 0.00105 |

- **Gemini's implicit cache serves a fixed ~1,973 tokens a round**, in every run and every layout (on every round,
  or every round but a cold first one), about 42% of the ~4.7k input tokens a round - against an offline upper bound
  of 83-87%. Through the OpenAI-compatible endpoint the ordering after that block changes nothing that is cached.
- The hit-ratio difference is a cold-start artefact: `legacy` always ran first in each repeat. Cost per round is the
  same within noise (about $0.0010; about $0.0017 per learner turn at ~1.6 rounds).
- `stable+tools` had a lower first-event time but always ran last (order and load are confounded); for Gemini the
  last round sends no tools anyway (`tool_choice` goes to OpenAI, DeepSeek and Groq only).
- Tool selection: the same tool families in every layout; n=2 and seven `get_word_detail` environment errors make
  smaller differences inconclusive.
- Answer quality was not measured (the result held no answer text): fixed by A2 below.

**Decision:** keep `AGENT_PROMPT_LAYOUT=legacy` and `AGENT_STABLE_TOOLS=off`. Re-test `stable` on a chat model whose
cache follows the whole prefix (OpenAI, DeepSeek) in the M5 challenger benchmark. More savings on Gemini need explicit
context caching (native `cachedContent`, a new adapter: a provider gate) or a smaller fixed prefix (the tool schemas
are its largest part).

### How it is run

Needs the owner's approval, a cost cap and a key for one provider. The same conversations, one model for every
layout, measured per round: cached and uncached input, output, rounds, tool calls, first-event and full-response
latency, cost at the prices given:

    python scripts/agent_prompt_cache_benchmark.py --live --provider gemini --model gemini-3.5-flash-lite \
        --approved --cap-usd 0.30 --price-in 0.30 --price-cached 0.03 --price-out 2.50 --repeat 2 --turns 6 \
        --out <a path outside the repository>

### Answer quality with and without the learner pack (A2)

Every turn's learner message and Orena's answer are kept in the result; `--answers-md` writes them side by side for a
person to read. `--pack both` runs each conversation without and with the M1 learner pack, built from a fixed
fixture learner per language (`PACK_FIXTURES` in the script: a job-interview learner with recurring tense/aspect
errors, forgotten words and a flagged word; no database). `--exclude-tools` leaves out tools the environment cannot
serve. Suggested run (about $0.06 at those prices: 1 layout x 2 pack settings x 2 languages x 2 repeats):

    python scripts/agent_prompt_cache_benchmark.py --live --provider gemini --model gemini-3.5-flash-lite \
        --approved --cap-usd 0.15 --price-in 0.30 --price-cached 0.03 --price-out 2.50 --repeat 2 --turns 6 \
        --layouts legacy --pack both --exclude-tools get_word_detail \
        --out <outside the repository>/pack.json --answers-md <outside the repository>/pack_answers.md

What to read for: answers that use the pack where it helps (the goal, the recurring errors, the forgotten words),
nothing the pack does not say, no learner data repeated back unprompted, and no change in correctness. The provider
the run uses must be one the owner has cleared for `learning_profile` data (G8).

## Gate state

| M0 requirement (§9) | State |
| --- | --- |
| Cache-stable layout, fixed tool order, model pin, telemetry | built, tested (hermetic) |
| Before/after benchmark on the same EN/ZH conversations | offline and live done (above) |
| Tool-selection parity | live: same tool families; small differences inconclusive at n=2 |
| No cost claim beyond what was measured | none made |

## Review

Independent review of `85f5b89c` (a separate reviewer instance, read-only, 2026-10-17): no P0, no P1. Fixed in the
follow-up commit: a pinned route the allowlist refuses, or whose provider failed after Admin moved the selection, is
re-pinned (P2-1); openings and screen-help keep the per-round tool list (P2-2); `tool_choice` only to endpoints known
to take it (P2-3); tests for each, for the last-round call and for a pricer without `route` (P2-4); the benchmark's
composition counts both context parts (P3-5); the route's model label is the operator-safe one (P3-6); pinning only
on a turn that asks a model (P3-8); the instruction says once that `context.*` spans both messages (P3-10). Not
changed: P3-7 (the pricer's signature stays `Callable[..., dict]`, with the fallback tested), P3-9 (no contradiction:
§4.3 keeps the in-session rolling summary on the pinned model; `agent_session_summary` is M3's separate
capability). This is not the owner's independent review, which the PR still needs.
