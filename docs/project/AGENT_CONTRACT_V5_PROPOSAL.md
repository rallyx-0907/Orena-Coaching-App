# Agent contract v5 — proposal (awaiting human approval)

**Status:** PROPOSED, 2026-09-28. Nothing in `AGENT_CONTRACT.md` changes until the
human approves; on approval it becomes `contract_version: 5` with a DECISION_LOG
entry, edited on `codex/work` only.

Two changes, one version: **A.** the learner's address preference (how Orena
says "I" and "you"); **B.** replies offer actions and never report them done,
and no reply names a provider - with the fixtures that broke either rule.

Compatibility: additive. A client that declares `contract_version` ≤ 4 sends no
`address` and gets the language defaults, exactly as today; a server never sends
an `address` note to such a client. Part B changes wording, not shapes.

---

## A. The address preference

**Why.** Orena speaks in the support language, and Vietnamese (less often
Chinese) has no neutral "I" and "you": today the server's fixed copy and the
model use the default `mình` / `bạn`. A learner who wants to be `em` to an Orena
that is `chị`, or wants `您`, has no way to say so that sticks - and the server's
fixed copy (identity, refusals, errors) cannot follow a preference the contract
does not carry.

**The human ruling it follows (R19, 2026-09-28, recorded in the intelligence
lane's `AGENT_SPEC.md` §0):** the address changes only from the learner's own
words - they ask for a pair, or they keep using one themselves and say yes when
asked once. Any pair they choose (em - anh/chị, tôi - anh/chị, 您 …) is accepted
and the replies stay respectful. Nothing is inferred from gender, age,
personality, a name or the learner's writing; signs that the learner is a minor
keep the default. One design for every support language. The UI never derives
it from the profile or anything else.

The intelligence lane already applies it in model replies (`55eb880`,
`01e20f0`) with v4's shapes: a `preference` note with id `address-<lang>` whose
text encodes the pair. v5 gives it a structured shape and lets the server's
fixed copy follow it.

### A1. `context.address` (§3)

```json
"context": {
  "locale": { "interface": "vi", "support": "vi", "target": "zh-CN", "content": "zh-CN" },
  "address": { "self": "chị", "user": "em", "lang": "vi" }
}
```

- `self`: how Orena refers to itself; `user`: how Orena addresses the learner;
  `lang`: the support language they belong to, in contract codes.
- Omitted means the language default:

  | `lang` | `self` | `user` |
  | --- | --- | --- |
  | `vi` | `mình` | `bạn` |
  | `zh-CN` | `我` | `你` |
  | `en` | `I` | `you` |

  A support language without a row uses its own ordinary first and second
  person, never the English pair.
- Applied only when `address.lang` equals `context.locale.support`; otherwise
  that support language's default. Each language keeps its own preference on
  the device.
- **Data, never instruction.** Each term is 1-24 characters and at most 3 words
  ("chị", "cô giáo", "anh Minh"): letters of any script with their marks,
  spaces, hyphens or apostrophes; no digits, other punctuation, line breaks or
  markup. The client validates before storing and before sending; the server
  validates again and on anything else uses the default. The server hands the
  terms to the model as quoted data, never as part of its instructions.
- Casing: the device stores the terms as the learner gave them; the server
  capitalises a sentence-initial use (`Chị là Orena…`).

### A2. What the server applies it to

- Every **support-layer** text addressed to the learner: model segments, the
  opening turn (§3.2), `error.message` (§4), and the server's fixed support copy -
  identity answers, refusals such as S8, error messages - through `{self}` /
  `{user}` slots whose defaults reproduce today's text exactly.
- Not **interface-layer** labels (action and suggestion labels, `tool_call.label`,
  capability titles; D-080, D-094): they never address the learner in the first
  or second person.
- Not target-language material: a Chinese example keeps its own `你` / `我`.

### A3. Coach note kind `address` (§5.4)

```json
{ "id": "address-vi", "kind": "address",
  "address": { "self": "chị", "user": "em", "lang": "vi" },
  "text": "Xưng hô: Orena xưng \"chị\", gọi người học là \"em\".",
  "weight": 1, "last_reinforced": "ISO-8601", "expires_at": null }
```

- Set only through `memory_update { op: "upsert" }`, when the learner asks for a
  pair or says yes to the one offer R19 allows. The same reply already uses it.
  `remove` with `{ id: "address-<lang>" }` returns to the default.
- One per support language: `id` is `address-<lang>`, so a change of mind
  replaces it.
- `text` is the learner-readable line in `preferences.agent_memory`, in the
  support language; the server reads `address`, never parses `text`.
- It does not decay and has no expiry; it stays until the learner changes or
  deletes it (the privacy exit, §10).
- The client sends it as `context.address` for the current support language on
  every request and **does not** put it in `coach_notes`, so it never competes
  with the 20-note / 2 KB budget.
- The opening turn applies an existing address and never sets or offers one
  (§3.2: no `memory_update`).

### A4. Privacy (§10)

The preference is device memory like every coach note; the server applies it
to the turn and stores nothing. A term may contain a name the learner asked to
be called by ("anh Minh"); it leaves the device with each request as the
learner's own words and is redacted from traces like any learner text.

---

## B. Replies offer actions; no reply names a provider

**Why.** An action is a button the learner taps (`LOW`) or confirms (`CONFIRM`),
§7. The canonical stream S5 pairs the reply "Mình lưu 我 cho bạn nhé." with a
`save_word` action the learner has not tapped: it reads as if Orena saved the
word. And S2 (and the §5.1 example) has the reply name the pronunciation
provider ("Azure đánh dấu 是 …"), which §10 forbids.

### B1. Rules (§4 segments, §7 actions)

- A segment that comes with an action **offers** it: it never says or implies
  the action was done ("Mình lưu …", "Saved it for you", "我帮你保存了"). The
  learner does it by tapping or confirming. A `memory_update` is different: the
  device applies it without a tap, so a reply may say it is applied (S14).
- A reply that names the button quotes the action's `label` exactly as the
  learner sees it - interface language (§7, D-094) - even inside a
  support-language sentence.
- No segment, `error.message` or fixed copy names a provider or model (§10);
  evidence is described by what was measured ("Âm 是 bị đánh dấu …").

### B2. Fixtures reworded (§5.1, §12)

| Where | Now | v5 |
| --- | --- | --- |
| §12 S5 | "Mình lưu 我 cho bạn nhé." | "Bấm “Lưu từ” để thêm 我 vào từ vựng của bạn." |
| §12 S2 | "Azure đánh dấu 是 …" | "Âm 是 bị đánh dấu là phát âm sai …" |
| §5.1 example | "Azure đánh dấu 是 là phát âm sai, điểm 6/100. Nghe mẫu rồi thử lại nhé:" | "Âm 是 bị đánh dấu là phát âm sai, điểm 6/100. Nghe mẫu rồi thử lại nhé:" |

The same wording follows in the UI's mock (vi, en, zh) and in the intelligence
lane's tests that copy these fixtures (`tests/test_agent_contract_streams.py`,
`tests/test_agent_events.py`, `tests/test_agent_turn.py` on
`feature/orena-intelligence`). The lane's reply check (`agent/honesty.py`)
currently lets "Mình lưu 我 cho bạn nhé." through as an offer; under B1 it is a
claim.

---

## C. Canonical streams added (§12)

`S14 address` - surface `orena.home`, "Gọi mình là em, còn Orena xưng chị nhé."

```text
session → memory_update{upsert, {id: "address-vi", kind: address, address: {self: "chị", user: "em", lang: "vi"}, weight: 1, expires_at: null}}
→ segment_end{0, vi, "Được rồi, từ giờ chị gọi em là em nhé.", brief_ack} → done
```

`S15 identity with address` - surface `home`, `context.address {self: "chị", user: "em", lang: "vi"}`, "Bạn là ai?"

```text
session → segment_end{0, vi, "Chị là Orena, trợ lý học tập AI … của em …", neutral_explain} → done   # fixed copy, by rule, no model
```

## D. What each side builds (after approval)

- **UI (`codex/work`):** `agent/contract.js` (the kind, the term validation, the
  defaults), `agent/memory.js` (the address note: one per language, no decay,
  kept out of `coach_notes`), `agent/session.js` (`context.address` for the
  current support language), the memory sheet lists and deletes it, the mock
  plays S14 and S15 and the reworded S2 and S5 in vi, en and zh,
  `scripts/test_orena_agent.mjs` checks all of it. No Settings control: the
  design draws none (Design Contract rule 43).
- **Intelligence lane:** move its `preference` note to the `address` kind and
  object, read `context.address`, fill the fixed-copy slots, treat the S5
  wording as a claim, reword the copied fixtures, pass S14 and S15.

## E. Question for the human

1. **A name in a term.** R19 accepts "any pair they choose", and the lane accepts
   up to 3 words ("anh Minh"). Confirm that a name inside a term is fine, since
   it leaves the device with every request. *Recommendation: yes - the learner's
   own words, device memory, turn-scoped on the server.*
