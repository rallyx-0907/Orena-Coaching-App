# Orena Memory M0: before/after benchmark

Status: offline part run 2026-10-17 (local execution); **live part not run** - no provider key in this environment.
Proposal: `ORENA_MEMORY.md` §5.4, §7.2, §9 (M0). Script: `scripts/agent_prompt_cache_benchmark.py`.

## What M0 changed

1. **Prompt layout** (`AGENT_PROMPT_LAYOUT`, default `stable`): the per-turn context is split by how often it changes.
   The conversation's setting (languages, screen, what it offers, address, coach notes) is `context:` right after the
   instruction; this turn's part (in view, selection, earlier reads, open offer, focus, what was sent) is
   `context (this turn; ...):` after the conversation. `legacy` restores the single context message second.
2. **Stable tool list** (`AGENT_STABLE_TOOLS`, default `off`): every round and turn lists the same tools in one order;
   the turn's rules are enforced on the calls (a call the round does not allow is answered "unavailable: not offered
   in this turn" and never runs) and the last round sends `tool_choice: none`.
3. **Model pinned per conversation**: the active selection when the conversation's first model turn runs, kept in the
   session for every round and its rolling summary; an Admin change applies to new conversations. A pinned provider
   that can no longer stream here (removed or unconfigured) is pinned again to the current selection on the next turn
   (`pinned: repinned` in the turn record). A failed round still fails the turn: nothing switches provider on error.
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
| chat, 6 turns | legacy | en | 8 | 60,434 | 82.9% | 10,346 |
| chat, 6 turns | legacy | zh | 8 | 61,072 | 82.6% | 10,648 |
| chat, 6 turns | stable | en | 8 | 60,601 | 83.1% | 10,219 |
| chat, 6 turns | stable | zh | 8 | 61,240 | 83.0% | 10,410 |
| chat, 6 turns | stable+tools | en | 8 | 61,849 | 83.2% | 10,373 |
| chat, 6 turns | stable+tools | zh | 8 | 62,491 | 83.1% | 10,569 |
| chat, 20 turns | legacy | en | 25 | 173,403 | 88.8% | 19,494 |
| chat, 20 turns | legacy | zh | 25 | 176,655 | 88.2% | 20,913 |
| chat, 20 turns | stable | en | 25 | 173,861 | 88.2% | 20,602 |
| chat, 20 turns | stable | zh | 25 | 177,115 | 87.6% | 21,907 |
| chat, 20 turns | stable+tools | en | 25 | 177,297 | 88.3% | 20,756 |
| chat, 20 turns | stable+tools | zh | 25 | 180,551 | 87.8% | 22,063 |
| coaching, 6 turns | legacy | en | 12 | 91,607 | 87.4% | 11,567 |
| coaching, 6 turns | legacy | zh | 12 | 92,683 | 86.9% | 12,131 |
| coaching, 6 turns | stable | en | 12 | 91,855 | 88.1% | 10,889 |
| coaching, 6 turns | stable | zh | 12 | 92,932 | 88.0% | 11,160 |
| coaching, 6 turns | stable+tools | en | 12 | 93,732 | 88.2% | 11,046 |
| coaching, 6 turns | stable+tools | zh | 12 | 94,809 | 88.1% | 11,320 |
| coaching, 20 turns | legacy | en | 43 | 320,422 | 92.6% | 23,641 |
| coaching, 20 turns | legacy | zh | 43 | 326,475 | 92.1% | 25,835 |
| coaching, 20 turns | stable | en | 43 | 321,250 | 92.3% | 24,698 |
| coaching, 20 turns | stable | zh | 43 | 327,302 | 92.0% | 26,269 |
| coaching, 20 turns | stable+tools | en | 43 | 327,500 | 92.4% | 24,855 |
| coaching, 20 turns | stable+tools | zh | 43 | 333,552 | 92.1% | 26,425 |

Composition of one request (est. tokens, chat, turn 6): tools 4,050 (4,212 with the stable list), instruction 2,766,
context 156, conversation 479, other system messages (style, selection) 395.

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

## Live run (not done here)

Needs the owner's approval, a cost cap and a key for one provider (no key is present in this environment). The same
conversations, one model for every layout, measured per round: cached and uncached input, output, rounds, tool calls
(tool-selection parity between layouts), first-event and full-response latency, cost at the prices given:

    python scripts/agent_prompt_cache_benchmark.py --live --provider gemini --model gemini-3.5-flash-lite \
        --approved --cap-usd 0.30 --price-in 0.30 --price-cached 0.03 --price-out 2.50 --repeat 2 --turns 6 \
        --out <a path outside the repository>

Worst case at those prices: 3 layouts x 2 languages x 2 repeats x ~8 rounds x (~5k input + 1k output tokens) is about
$0.19 before any caching; the cap stops it earlier if the estimate is exceeded.

## Gate state

| M0 requirement (§9) | State |
| --- | --- |
| Cache-stable layout, fixed tool order, model pin, telemetry | built, tested (hermetic) |
| Before/after benchmark on the same EN/ZH conversations | offline done (above); live not run |
| Tool-selection parity | not measurable offline (rounds are scripted); live run needed |
| No cost claim beyond what was measured | none made |
