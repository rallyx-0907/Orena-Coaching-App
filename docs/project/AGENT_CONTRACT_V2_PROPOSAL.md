# Agent contract v2 — proposal (awaiting human approval)

**Status:** PROPOSED, 2026-09-27. Not in force. `AGENT_CONTRACT.md` stays at
`contract_version: 1` until the human approves; after approval the change is
made in `AGENT_CONTRACT.md` on `codex/work` only, `contract_version` becomes 2,
and a Decision Log entry records it (D-086; the human's migration brief, item 6).
Until then the new UI runs on the v1 mock and renders these surfaces from
client-side material only.

**Why now.** The new learner design (D-088) makes Orena a place of its own and
gives it three entry points the v1 contract cannot address: the Orena
destination (Orena Home, the phone bar's centre action), the rail's "Ask Orena"
card, and a thread that opens with Orena speaking first. It also draws handoff
and source cards that need a few display fields the v1 events do not carry.

All changes are additive and optional: a v1 server and a v2 client still work
together, and a v2 server never sends a v2 field to a client that declared
`contract_version: 1`.

---

## 1. A surface id for the Orena destination

Add to §6.1:

```text
orena.home
```

- **As `context.surface`:** the learner is in Orena Home (reached from the
  phone bar's centre action, the rail's "Ask Orena" card, or a link). Until
  now the client had to omit `surface` there, so the agent could not tell a
  question asked in Orena Home from one asked with no context at all.
- **As a `navigate` intent:** `{ intent: "orena.home" }` opens Orena Home, for a
  reply that moves a contextual conversation to the full destination (the
  design's Contextual Orena panel offers exactly that step).
- Voice mode is a way of talking, not a surface: a voice conversation started
  from Orena Home carries `orena.home`; one started from a workspace carries
  that workspace's surface.

## 2. An opening turn with no learner message

Add a request field to §3:

```json
{ "trigger": "open" }
```

`trigger` ∈ `message` (default; v1 behaviour, `message` required) | `open`
(`message` absent). An opening turn is what the client sends when a thread
starts empty: Orena Home with no thread on this device, or the Contextual Orena
panel opened on a selection (`context.selected_item` set).

The server answers an opening turn with a greeting fitted to the context and
learner - no learner claim is made in it - and then the ways forward:

```text
session → segment_delta… → segment_end{0, <support>, …, neutral_explain}
→ suggestion{label, intent} ×(1-5) → [action{…} ×(0-2)] → done
```

Rules:

- Read-only: no `memory_update`, and only actions whose `risk` is `LOW`.
- No error claim without `evidence` (§5.3 applies unchanged).
- Short: one segment, ≤ 240 characters, in the `support` language; the Design
  Contract's rule 50 (learning-first copy) governs it like any learner copy.
- Metering: an opening turn is not a learner turn; it does not advance
  `turn_ordinal`, and a `soft_limited` learner gets the suggestions without a
  greeting rather than an error.
- Cacheable: the client may reuse an opening turn for the same
  `surface` + `selected_item` within one session and never sends more than one
  per thread.

New canonical stream (§12):

```text
S13 opening — surface orena.home, trigger open, no message
session → segment_end{0, vi, "…", neutral_explain}
→ suggestion{"Ôn từ đến hạn", vocabulary.review_due} → suggestion{…} → done
```

## 3. Display fields on handoff and source cards

The design's Orena Home draws an action as a card - kind and duration, a title,
one line on why, and the button - and a source as a card with a title and kind.
v1 `action` and `evidence` carry only ids. Resolving every possible id through
separate content APIs on the client is slow and would duplicate the server's own
lookups, so add one optional object to both events:

```json
"display": {
  "title": "A Morning in the City",
  "kind": "reading | listening | speaking | writing | vocabulary | grammar | review",
  "duration_s": 480,
  "reason": "Có 3 cụm bạn đã lưu hôm qua."
}
```

- `title`, `kind` and `duration_s` are copied from the domain record the server
  read for this action or evidence; never generated, never estimated. Absent
  when the server has no such record.
- `reason` is the only generated field: ≤ 90 characters, in the `support`
  language, a statement the learner can check (rule 50), never praise.
- The button's own text is still `action.label` (§7, ≤ 24 characters).
- A client that does not render cards ignores `display`; the action still works.

## 4. Considered and not proposed

- **A text-mode "thinking" event.** The client shows Orena as thinking from the
  moment it sends a turn until the first event, and shows `tool_call.label`
  while a tool runs. v1 already carries everything needed.
- **Evidence and action cards, error, metered and memory states in the
  contextual panel and voice mode.** The design has not drawn them yet, but the
  v1 events already describe them; they are client work, not contract work.
- **Voice transport.** §9 stays provisional; the design's voice mode needs only
  `voice_state`, which v1 has.

## 5. What changes where, on approval

| Where | Change |
| --- | --- |
| `AGENT_CONTRACT.md` | §3 `trigger`; §6.1 `orena.home`; §4/§5 `display` on `action` and `evidence`; §12 S13; `contract_version: 2` |
| `DECISION_LOG.md` | an entry recording the change and the approval |
| UI lane (`codex/work`) | `client.supported_intents` gains `orena.home`; Orena Home and the contextual panel send `trigger: "open"` on an empty thread; the mock replays S13; cards render `display` |
| Intelligence lane | receives it by merging `codex/work` forward; implements `trigger: "open"`, `orena.home`, `display`, and S13 in its contract tests |
