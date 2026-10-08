# Agent contract v2 — proposal (awaiting human approval)

**Status:** APPROVED by the human unchanged and applied, 2026-09-27: `AGENT_CONTRACT.md`
is `contract_version: 2` (D-092). This file stays as the record of the reasoning;
the contract is the authority.

**Why.** Two reasons. (a) The new learner design (D-088) makes Orena a place of
its own - Orena Home, the phone bar's centre action, the rail's "Ask Orena" card
- and opens a thread with Orena speaking first; v1 cannot address either. (b)
Five v1 actions and three surface ids name identifiers the product does not
have (`word_id`, a fetchable `attempt_id`, a server-held take); as written they
cannot be executed by any client. Neither lane has implemented v1's actions
yet, so v2 replaces those shapes instead of carrying both.

Compatibility: §1-§3 are additive. §4-§5 change the payloads of `save_word`,
`unsave_word`, `play_user`, `say_again`, `compare_with_model`, `start_review`,
`add_word_to_collection` and the parameters of three surface ids. A server never
emits a v2-only field, action shape or id to a client that declared
`contract_version: 1`; to a v1 client it emits none of the changed actions.

---

## 1. A surface id for the Orena destination

Add to §6.1: `orena.home`.

- **As `context.surface`:** the learner is in Orena Home (the phone bar's centre
  action, the rail's "Ask Orena" card, a link). v1 made the client omit
  `surface` there, so a question asked in Orena Home looked like one asked with
  no context.
- **As a `navigate` intent:** `{ intent: "orena.home" }` moves a contextual
  conversation to the full destination (the design's contextual panel offers
  that step).
- Voice is a way of talking, not a surface: a voice conversation carries the
  surface it was started from.

## 2. An opening turn with no learner message

Add to §3: `"trigger": "message" | "open"` (default `message`; `message` is
required only for `message`). The client sends `trigger: "open"` when a thread
starts empty: Orena Home with no thread on this device, or the contextual panel
opened on a selection (`context.selected_item`).

```text
session → segment_delta… → segment_end{0, <support>, …, neutral_explain}
→ suggestion{label, intent} ×(1-5) → [action{…} ×(0-2)] → done
```

- Read-only: no `memory_update`; only `LOW`-risk actions; no error claim
  without `evidence` (§5.3 unchanged).
- One segment, ≤ 240 characters, in the `support` language; Design Contract
  rule 50 governs it like any learner copy.
- Not a learner turn: it does not advance `turn_ordinal`; a `soft_limited`
  learner gets the suggestions without the greeting, never an error.
- At most one per thread; the client may reuse it for the same `surface` +
  `selected_item` within a session.
- New canonical stream **S13 opening** (surface `orena.home`, `trigger: open`):
  `session → segment_end{0, vi, "…", neutral_explain} → suggestion{"Ôn từ đến hạn", vocabulary.review_due} → … → done`.

## 3. Display fields on handoff and source cards

The design's Orena Home draws an action as a card (kind and duration, title,
one line on why, the button) and a source as a card (title, kind). Add one
optional object to `action` and `evidence`:

```json
"display": { "title": "…", "kind": "reading | listening | speaking | writing | vocabulary | grammar | review", "duration_s": 480, "reason": "…" }
```

`title`, `kind`, `duration_s` are copied from the domain record the server read
- never generated or estimated, absent when there is none. `reason` is the only
generated field: ≤ 90 characters, `support` language, checkable, never praise.
The button's text stays `action.label`.

## 4. Action payloads the new UI can execute (replaces §7's shapes)

| type | v1 payload | v2 payload | How the client executes it (existing APIs) |
| --- | --- | --- | --- |
| `save_word` | `{ word_id \| { text, lang } }` | `{ text, lang }` | `POST /api/library/vocabulary` `{ word: text, … }`. The library keys a word on its text and the **session's active learning language**; if `lang` is not the active learning language the client does not save and logs it. |
| `unsave_word` (CONFIRM) | `{ word_id }` | `{ text, lang }` | The UI's own confirm, then `DELETE /api/library/vocabulary/{text}` (same language rule). |
| `play_user` | `{ attempt_id, item_id? }` | `{ take_ref, item_id? }` | Client-only. The server stores no take audio (D-076): the new UI holds the learner's takes for the session (and, only if the learner opted in, on the device). `take_ref` is minted by the client, sent in `context.take_ref`, and may only be echoed back - the agent never invents one. Unknown or expired `take_ref`: ignored and logged. |
| `say_again` | `{ attempt_id \| content_id, item_id? }` | `{ content_id, item_id? }` | Open the speaking workspace on that line for a new take (the line is what matters; no attempt lookup). |
| `compare_with_model` | `{ attempt_id, item_id }` | `{ take_ref, item_id }` | Open Compare With Model on the client-held take (same rule as `play_user`). |
| `start_review` | `{ scope: "due" \| "word", word_id? }` | `{ scope: "due" }` or `{ scope: "word", text, lang }` | Client-composed: `due` reads `GET /api/library/review-queue` and opens the Review workspace on it; `word` opens Review on that one saved word (the design's single-word review from Word Detail). Nothing due / word not saved: the UI says so, no review opens. |
| `add_word_to_collection` | `{ word_id, collection_id? }` | `{ text, lang, target?: { system: "deck" \| "library", id } }` | Two systems exist and the payload names which. `deck`: `POST /api/vocabulary/decks/{id}/words` `{ word }` (the word must be saved first). `library`: keep the word as an item (`POST /api/library/items` `{ kind: "word", word }`), then `POST /api/library/collections/{id}/items` `{ item_id }`. The client saves the word first when needed. `target` absent: the UI opens its own add-to sheet and the learner chooses. `id` must come from a tool read, never be generated. |

`navigate`, `play_model` and `risk` rules are unchanged. `label` stays ≤ 24
characters in the `support` language.

## 5. Context identifiers that exist

- **Words** are named by text and language, not by id. `context.selected_item`
  for a word is `{ type: "word", text, lang }` (v1's `id` is dropped for words;
  it stays for sentences, feedback items and grammar points, which have ids).
- **Speaking takes** are client-held: `context.take_ref` (client-minted, §4).
- **Speaking attempts.** The server keeps an audio-free record of each assessed
  take (`POST /api/speech/attempts` returns its id) but has no read by id: the
  list endpoint filters only by `asset_id` / `segment_id`. `context.attempt_id`
  therefore stays in the contract as **that record's id**, and the proposal
  records a **backend gap**: an owner-scoped read by id (a repository method the
  tool gateway calls, optionally `GET /api/speech/attempts/{id}`), no schema
  change. Until it exists the client sends `attempt_id` only together with
  `context.content_id` and `context.selected_item.id` (the line), so the tool
  can find the record through the existing filtered list; evidence always comes
  from the server's record, never from client-supplied scores. When no record
  was stored (history not configured, 503), the client omits `attempt_id` and
  the agent makes no pronunciation error claim (§5.3).
- **Surface ids with parameters** (§6.1) follow the same identifiers:
  `vocabulary.word{text, lang}`, `speaking.word_detail{take_ref, item_id}`,
  `speaking.compare{take_ref, item_id}`. The others are unchanged.

## 6. Locale codes

The contract keeps `zh-CN` in `context.locale`, segments and payloads. Internally
the product uses `zh` (the learning language, `/api/session/bootstrap`) and
`zh`/`vi`/`en` for packs. Each side maps at its own boundary: the client sends
`zh-CN` for the product's `zh` and maps `lang: "zh-CN"` back to `zh` before any
API call; the agent maps the same way at its tool gateway. `en` is `en` on both
sides.

## 7. Considered and not proposed

- **A text-mode "thinking" event.** The client shows Orena thinking from send to
  the first event, and `tool_call.label` while a tool runs.
- **Evidence, action, error, metered and memory states in the contextual panel
  and voice mode.** The design has not drawn them; v1 events already describe
  them. Client work, not contract work.
- **Voice transport.** §9 stays provisional.
- **Client-supplied pronunciation evidence** in place of the attempt read (§5):
  rejected; an error claim must rest on the server's own record.

## 8. What changes where, on approval

| Where | Change |
| --- | --- |
| `AGENT_CONTRACT.md` | §3 `trigger`, `take_ref`, word `selected_item`; §4/§5 `display`; §6.1 `orena.home` and the three re-parameterised ids; §7 the seven payloads; §3 locale note; §12 S13 and S5 (`{ text: "我", lang: "zh-CN" }`); `contract_version: 2` |
| `DECISION_LOG.md` | an entry recording the change and the approval |
| UI lane (`codex/work`) | supported intents/actions per v2; `trigger: open`; the mock replays S13 and the revised S5; cards render `display`; the take store mints `take_ref`; the dispatcher executes §4 through the listed APIs |
| Intelligence lane | merges `codex/work` forward; implements `trigger: open`, `orena.home`, `display`, the v2 payloads and S13 in its contract tests; closes the attempt read-by-id gap or uses the filtered list |
| Backend gap | owner-scoped speaking-attempt read by id (no schema change), tracked in `UI_BACKEND_GAPS.md` |
