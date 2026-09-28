# Agent contract v5 — proposal (awaiting human approval)

**Status:** PROPOSED, 2026-09-28. Nothing in `AGENT_CONTRACT.md` changes until the
human approves; on approval it becomes `contract_version: 5` with a DECISION_LOG
entry, edited on `codex/work` only.

**Why.** Orena speaks to the learner in the support language, and Vietnamese
(and, less often, Chinese) has no neutral way to say "I" and "you": today the
server's fixed copy and the model both use the default `mình` / `bạn`. A learner
who wants to be called `em` by an Orena that says `chị`, or wants `您` in
Chinese, has no way to say so that sticks. v5 carries that preference as data:
the learner states it, the device keeps it, every request sends it, and the
server applies it to the model's reply and to its own fixed copy (identity,
refusals, errors).

**The rule the whole change rests on:** how Orena says "I" and "you" comes only
from the learner's own words. Neither side derives it from the profile, a name,
gender, age, the learner's writing or anything else; neither side asks for it
unprompted.

Compatibility: additive. A client that declares `contract_version` ≤ 4 sends no
`address` and gets the language defaults, exactly as today; a server never sends
an `address` note to such a client.

---

## 1. `context.address` (§3)

```json
"context": {
  "locale": { "interface": "vi", "support": "vi", "target": "zh-CN", "content": "zh-CN" },
  "address": { "self": "chị", "user": "em", "lang": "vi" }
}
```

- `self` - how Orena refers to itself; `user` - how Orena addresses the
  learner; `lang` - the support language they belong to, in contract codes
  (`vi`, `en`, `zh-CN`).
- Omitted means the language default:

  | `lang` | `self` | `user` |
  | --- | --- | --- |
  | `vi` | `mình` | `bạn` |
  | `zh-CN` | `我` | `你` |
  | `en` | `I` | `you` |

- The server applies it only when `address.lang` equals `context.locale.support`;
  otherwise it uses that support language's default. (A learner who switches
  support language keeps each language's own preference on the device.)
- It is **data, never instruction.** `self` and `user` are 1-24 characters of
  letters (any script, with their marks), spaces, hyphens or apostrophes; no
  digits, other punctuation, line breaks or markup. The client validates before
  storing and before sending; the server validates again and, on anything else,
  ignores the object and uses the default. The server passes the values to the
  model as quoted data, never as part of its instructions.
- Casing: the device stores the words as the learner gave them; the server
  capitalises a sentence-initial use (`Chị là Orena…`) and otherwise uses them
  as stored.

## 2. What the server applies it to

- Every **support-layer** text addressed to the learner: model segments in the
  support language, the opening turn (§3.2), `error.message` (§4), and the
  server's fixed support copy - identity answers, refusals such as S8, error
  messages. Fixed copy gains `{self}` / `{user}` slots in the `vi` and `zh-CN`
  packs whose defaults reproduce today's text exactly.
- Not to **interface-layer** labels (action and suggestion labels,
  `tool_call.label`, capability titles, D-080/D-094): those never address the
  learner in the first or second person, so they need no slot.
- Not to target-language material: a Chinese example sentence keeps its own
  `你`/`我`.

## 3. Coach note kind `address` (§5.4)

The preference is kept in device memory as a coach note:

```json
{ "id": "address:vi", "kind": "address",
  "address": { "self": "chị", "user": "em", "lang": "vi" },
  "text": "Xưng chị, gọi em", "weight": 1, "last_reinforced": "ISO-8601", "expires_at": null }
```

- Set only through `memory_update { op: "upsert" }` when the learner states a
  preference in a turn ("Gọi mình là em nhé", "请用您称呼我"). The same reply
  already uses it. `remove` with `{ id: "address:<lang>" }` when the learner asks
  to go back to the default.
- One per support language: `id` is `address:<lang>`, so an upsert replaces the
  previous one.
- `text` is the learner-readable summary shown in `preferences.agent_memory`
  (support language); it is not sent back to the model.
- It **does not decay** and has no expiry: it stays until the learner changes or
  deletes it. The learner sees it, and can delete it, in
  `preferences.agent_memory` - the privacy exit (§10).
- The client sends it as `context.address` for the matching support language on
  every request, and **does not** include it in `coach_notes` (so it never
  competes with the 20-note / 2 KB budget and never reads as a mere preference).
- The opening turn stays read-only (§3.2): it applies an existing address, never
  sets one.

## 4. Privacy (§10)

- The preference is device memory like every coach note; the server applies it
  to the turn and stores nothing.
- `user` may be a name the learner asked to be called by. It leaves the device
  with each request, as the learner's own words, and is redacted like any
  learner text in traces.

## 5. Canonical streams (§12, the mock and the backend's contract tests)

`S14 address` - surface `orena.home`, "Gọi mình là em, còn Orena xưng chị nhé."

```text
session → memory_update{upsert, {id: "address:vi", kind: address, address: {self: "chị", user: "em", lang: "vi"}, text: "Xưng chị, gọi em", weight: 1, expires_at: null}}
→ segment_end{0, vi, "Được rồi, từ giờ chị gọi em là em nhé.", brief_ack} → done
```

`S15 identity with address` - surface `home`, `context.address {self: "chị", user: "em", lang: "vi"}`, "Bạn là ai?"

```text
session → segment_end{0, vi, "Chị là Orena, trợ lý học tập AI … của em …", neutral_explain} → done   # fixed copy, answered by rule, no model
```

## 6. What each side builds (after approval)

- **UI (`codex/work`):** `agent/contract.js` (the kind, the validation, the
  defaults), `agent/memory.js` (the address note: one per language, no decay,
  kept out of `coach_notes`), `agent/session.js` (`context.address` from memory
  for the current support language), the memory sheet lists and deletes it, the
  mock plays S14/S15, `scripts/test_orena_agent.mjs` checks all of it. No
  Settings control: the design draws none (Design Contract rule 43), so the
  preference is set only in conversation.
- **Intelligence lane:** accept and validate `context.address`, apply it to the
  prompt as data and to the `vi` / `zh-CN` fixed copy through the slots, emit the
  `address` note only on an explicit statement, and pass S14/S15.

## 7. Questions for the human

1. **Names.** May `user` be a name ("gọi mình là Minh"), or only a form of
   address? *Recommendation: allow a name - it is the learner's own words, kept
   on the device, turn-scoped on the server.*
2. **English.** English has no choice of pronoun. Should `address` apply to `en`
   at all? *Recommendation: `en` accepts only `user` (a name used when greeting
   or calling the learner), never replaces "I"/"you"; `self` is ignored.*
3. **Asking.** Should Orena ever offer the choice ("Bạn muốn mình xưng hô thế
   nào?")? *Recommendation: not in v5 - only on the learner's own statement, as
   you specified; revisit with onboarding if the design adds it.*
