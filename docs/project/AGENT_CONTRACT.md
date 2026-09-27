# Orena Intelligence — Agent Contract

Governance

Purpose: the single interface between the Orena Intelligence backend (lane `feature/orena-intelligence`, D-085) and the new learner UI that replaces the old one on `codex/work` (D-086). Both sides implement this file; neither reads the other's implementation.
Authority: D-085, D-086, D-092, D-094. Below AGENTS.md, ARCHITECTURE_INVARIANTS.md and the human gates; above either lane's own notes.
Change when: a field, event, action, intent or rule below changes. Edit **only on `codex/work`** through a reviewed commit that bumps `contract_version` and records the change in DECISION_LOG.md; the intelligence lane receives it by merging `codex/work` forward. Never edit this file on the intelligence lane.

`contract_version: 3`

v3 (D-094, 2026-09-27): an action's `label` is in the **interface** language - a button is interface layer (D-080) - not the support language v2 said; and a suggestion's `intent` is a **prompt intent** in the `prompt.` namespace, never a §6.1 id - the canonical streams S1 and S13 used navigation ids there. Nothing else changed.

v2 (D-092, 2026-09-27): the Orena destination (`orena.home`), an opening turn without a learner message (`trigger: "open"`), `display` fields on actions and evidence, and action payloads and ids that match the real APIs (words by `{ text, lang }`, client-held takes by `take_ref`, the stored attempt record by `attempt_id`). A server never sends a v2-only field, id or action shape to a client that declared `contract_version: 1`; to such a client it sends none of the changed actions (§7). To a client that declared `contract_version: 2` it may still send action labels in the support language.

---

## 1. Ownership

| Concern | Owner |
|---|---|
| `/api/agent/*` endpoints, tool gateway, evidence, capability registry content, provider routing, metering | Intelligence lane |
| Agent panel, rendering of every event, action dispatcher, intent → screen mapping, device memory for conversation and coach notes, the take store that mints `take_ref`, mic/voice UI state, the mock agent | UI lane (`codex/work`, new UI) |
| This contract | `codex/work`, changed only as above |

The old UI has no agent and gets none. Only the new UI integrates the agent.

The new UI may add, rename or drop flows. The agent therefore never names a route or a screen; it names **intents** (§6) and **actions** (§7), and it only emits those the client declares it supports (§3.1).

---

## 2. Transport

```text
POST /api/agent/turn           request §3 → response: text/event-stream (§4), one stream per turn
GET  /api/agent/capabilities   → registry (§8), filtered by the caller's locale
POST /api/agent/voice/session  → §9 (provisional)
```

Auth: the app's existing session. The server never trusts an identifier the model produces; the learner is always the authenticated caller.

SSE framing: `event: <name>\ndata: <json>\n\n`. The stream always ends with `done` or `error`. The client may abort (fetch AbortController); the server stops generating.

---

## 3. Request — `POST /api/agent/turn`

```json
{
  "contract_version": 3,
  "session_id": "optional, from a previous session event",
  "trigger": "message",
  "message": "Tại sao tôi cứ sai từ này?",
  "client": {
    "ui_version": "string",
    "supported_actions": ["navigate", "play_model", "save_word"],
    "supported_intents": ["orena.home", "vocabulary.review_due", "speaking.workspace"]
  },
  "context": {
    "surface": "speaking.workspace",
    "activity_type": "pronunciation_practice",
    "locale": { "interface": "vi", "support": "vi", "target": "zh-CN", "content": "zh-CN" },
    "lesson_id": "…", "content_id": "…", "attempt_id": "…", "take_ref": "…", "essay_id": "…",
    "selected_item": { "type": "word", "text": "我", "lang": "zh-CN" },
    "client_evidence": { "pitch_contour_ref": "optional; measured client-side, never invented" }
  },
  "coach_notes": [
    { "id": "n1", "kind": "preference | goal | plan", "text": "…", "weight": 0.7, "last_reinforced": "ISO-8601", "expires_at": "ISO-8601 | null" }
  ]
}
```

Rules:

- Omit any field that does not apply. Never send page state, DOM, or the whole profile.
- `trigger` ∈ `message` (default; `message` required) | `open` (no `message`; §3.2).
- `surface` is a **surface id** from §6.1, not a route.
- `locale` follows D-079: `interface`, `support`, `target`; `content` is the language of the content in view. Chinese is `zh-CN` in this contract; the product's internal code is `zh`, and each side maps at its own boundary (the client sends `zh-CN` for `zh` and maps `lang: "zh-CN"` back to `zh` before any API call; the agent does the same at its tool gateway). `en` is `en` on both sides.
- `activity_type` ∈ `app_help | coaching | review | reading | listening | pronunciation_practice | free_talk | conversation_practice | writing | grammar | vocabulary`.
- `selected_item`: `type` ∈ `word | sentence | feedback_item | grammar_point`. A word is named by `{ text, lang }` - the product has no word ids. A sentence, feedback item or grammar point carries its `id` and `text`.
- `attempt_id` is the id of the audio-free record the server stored for an assessed speaking take (`POST /api/speech/attempts` returns it). While no read-by-id exists (backend gap N-9), the client sends it only together with `content_id` and `selected_item.id` (the line), so the tool gateway can find the record through the existing filtered list. Evidence always comes from the server's record, never from client-supplied scores. When no record was stored, `attempt_id` is omitted.
- `take_ref` names a speaking take the new UI holds for the session (the server stores no take audio, D-076). It is minted by the client; the agent may only echo back a `take_ref` it received.
- `coach_notes` live in device memory (D-085 lane spec D7/D18); send at most 20, most weighted first, total ≤ 2 KB.

### 3.1 Client capabilities are binding

The agent emits an `action` only if its `type` is in `client.supported_actions`, and a `navigate` only if its `intent` is in `client.supported_intents`. When the learner asks for something the client cannot do, the agent says so in plain words and emits no action. This is how a flow dropped from the new UI disappears from the agent without a backend change.

### 3.2 The opening turn

A client sends `trigger: "open"` when a thread starts empty: Orena Home with no thread on this device, or the contextual panel opened on a selection. The server answers with one greeting fitted to the context and learner, then the ways forward:

```text
session → segment_delta… → segment_end{0, <support>, …, neutral_explain}
→ suggestion{label, intent} ×(1-5) → [action{…} ×(0-2)] → done
```

- Read-only: no `memory_update`; only `LOW`-risk actions; no error claim without `evidence` (§5.3).
- One segment, ≤ 240 characters, in the `support` language; Design Contract rule 50 (learning-first copy) governs it.
- Not a learner turn: it does not advance `turn_ordinal`. A `soft_limited` learner gets the suggestions without the greeting, never an error.
- At most one per thread; the client may reuse it for the same `surface` + `selected_item` within a session.

---

## 4. Events (server → client)

Every event is JSON. Unknown fields must be ignored by the client; unknown event names must be ignored and logged.

```text
session        { session_id, contract_version }
segment_delta  { index, lang, text_delta }
segment_end    { index, lang, text, voice_style }
tool_call      { name, label }                      # label is learner-safe, e.g. "Đang xem lần nói gần nhất"
tool_result    { name, summary, evidence_ids[] }
evidence       { id, source, ref, excerpt, display? }        # §5.3, §5.5
action         { id, type, label, payload, risk, display? }  # §7, §5.5
suggestion     { label, intent }                    # intent is a prompt intent, not a navigation intent
memory_update  { op: "upsert" | "remove", note }    # §5.4
voice_state    { state: "listening" | "thinking" | "speaking" | "interrupted" }   # voice only
audio_chunk    { index, format: "pcm16_24k", data_base64 }                         # voice cascade only
metered        { turn_ordinal, budget_state: "ok" | "soft_limited" }
error          { class, message, fallback: "retry" | "text_only" | "none" }
done           { usage: { input_tokens, output_tokens }, trace_id }
```

Ordering guarantees: `session` first; every `segment_delta` for an index precedes its `segment_end`; an `evidence` event precedes any `segment_end` that cites it; `done` or `error` last.

`error.message` is learner-safe and already in the `support` language. It never contains a provider name, key, region or raw provider output.

A suggestion's `intent` is a prompt intent: it names the question the suggestion asks, in the `prompt.` namespace (`prompt.review_due`, `prompt.next_step`, `prompt.explain_word`, …). It is never a §6.1 surface or navigation id - going somewhere is an `action` (`navigate`). Tapping a suggestion sends its `label` as the learner's next message.

The client shows Orena as thinking from the moment it sends a turn until the first event, and shows `tool_call.label` while a tool runs; there is no separate text-mode thinking event.

---

## 5. Payload types

### 5.1 Segment

A reply is a list of segments, not one string, so mixed-language speech and reference audio can be routed.

```json
{ "index": 0, "lang": "vi",    "text": "Azure đánh dấu 是 là phát âm sai, điểm 6/100. Nghe mẫu rồi thử lại nhé:", "voice_style": "gentle_correction" }
{ "index": 1, "lang": "zh-CN", "text": "是", "voice_style": "reference" }
```

### 5.2 `voice_style` (closed enum)

```text
neutral_explain | encouraging | gentle_correction | celebrate | brief_ack | reference
```

`reference` means: play the app's reference/word audio for this text, not the conversational voice. In text mode the UI may show a play affordance for it.

### 5.3 Evidence

Every statement that a learner made an error cites at least one evidence item. No evidence → the agent does not call it an error (D-066 "no fake pronunciation result", D-084 "passed is the provider's own flag").

```json
{ "id": "e1", "source": "speech.pronunciation", "ref": { "attempt_id": "…", "path": "words[2].phonemes[0]" },
  "excerpt": { "pinyin": "shi", "tone": 4, "score": 6, "flagged": true } }
```

`source` ∈ `speech.pronunciation | writing.evaluation | reading.comprehension | listening.dictation | vocabulary.review | grammar.catalog | learner_summary`. The UI may offer "Vì sao Orena nói vậy?" by rendering `excerpt`; it never re-scores.

### 5.4 Coach notes

The agent proposes; the device stores. `upsert` carries a full note (§3 shape, with a new or existing `id`); `remove` carries `{ id }`. The client applies it, keeps weights and expiry, and drops notes whose weight decays below its threshold. The agent only proposes notes the learner stated directly; never emotions, circumstances or health.

### 5.5 Display (actions and evidence, optional)

The new UI draws an action as a card (kind and duration, a title, one line on why, the button) and a source as a card (title, kind).

```json
"display": { "title": "A Morning in the City", "kind": "reading | listening | speaking | writing | vocabulary | grammar | review", "duration_s": 480, "reason": "Có 3 cụm bạn đã lưu hôm qua." }
```

`title`, `kind` and `duration_s` are copied from the domain record the server read for this action or evidence - never generated or estimated, absent when there is none. `reason` is the only generated field: ≤ 90 characters, in the `support` language, a statement the learner can check, never praise. The button's text is still `action.label`. A client that draws no cards ignores `display`.

---

## 6. Intents

### 6.1 Surface ids (context) and navigation intents (actions)

The same id space serves both. The UI lane maps each id to whatever screen the new UI has; the backend never sees routes.

```text
home                       orena.home
library
reading.library            reading.workspace{content_id}
listening.library          listening.workspace{content_id}          listening.dictation{content_id}
speaking.library           speaking.workspace{content_id}           speaking.free_talk
speaking.word_detail{take_ref, item_id}                             speaking.compare{take_ref, item_id}
writing.workspace          writing.review{essay_id}                 writing.revision{essay_id}
vocabulary.my_language     vocabulary.word{text, lang}              vocabulary.review_due
grammar.catalog            grammar.point{grammar_id}
progress
preferences                preferences.agent_memory
```

`{…}` are required parameters, passed in `action.payload`. An id the new UI does not implement is simply absent from `client.supported_intents`.

Adding an id: contract change (bump version). Renaming a screen in the UI: no contract change.

---

## 7. Actions (v2 allowlist)

The agent returns actions; **the client executes them through the app's existing APIs with the learner's session.** The agent backend never mutates learner data.

| type | payload | risk | client does |
|---|---|---|---|
| `navigate` | `{ intent, …params }` | LOW | open the screen mapped to `intent` |
| `play_model` | `{ content_id, item_id? }` | LOW | play reference audio |
| `play_user` | `{ take_ref, item_id? }` | LOW | play the learner's take from the client's take store |
| `say_again` | `{ content_id, item_id? }` | LOW | open the speaking workspace on that line for a new take |
| `compare_with_model` | `{ take_ref, item_id }` | LOW | open compare on the client-held take |
| `save_word` | `{ text, lang }` | LOW | `POST /api/library/vocabulary` `{ word: text, … }` |
| `add_word_to_collection` | `{ text, lang, target?: { system: "deck" \| "library", id } }` | LOW | save the word if needed, then `deck`: `POST /api/vocabulary/decks/{id}/words` `{ word }`; `library`: `POST /api/library/items` `{ kind: "word", word }` then `POST /api/library/collections/{id}/items` `{ item_id }`; no `target`: the UI's own add-to sheet |
| `start_review` | `{ scope: "due" }` or `{ scope: "word", text, lang }` | LOW | `due`: read `GET /api/library/review-queue` and open review on it; `word`: open review on that saved word |
| `start_targeted_drill` | `{ focus: "tone" \| "stress" \| "word", item_ids[] }` | LOW | start the drill flow, if the new UI has one |
| `unsave_word` | `{ text, lang }` | CONFIRM | existing confirm dialog, then `DELETE /api/library/vocabulary/{text}` |

Rules:

- `risk` is fixed by `type` in this table, never by the model.
- `CONFIRM` actions run only after the UI's own confirmation.
- Blocked, and never emitted: delete collection, reset progress, clear history, bulk remove, anything admin.
- `label` is in the `interface` language (`context.locale.interface`), ≤ 24 characters: a button is interface layer (D-080). The text an action's card explains (`display.reason`) stays in the `support` language.
- An action with an unknown `type`, or not in `supported_actions`, is ignored and logged by the client.
- An action is shown as a button; the client never runs it without a learner tap, except `navigate` when the learner's message was itself the request ("đưa tôi tới…").
- Words: the vocabulary library keys a word on its text and the **session's active learning language**. A word action whose `lang` is not the active learning language is not executed; the client logs it.
- Ids in payloads (`content_id`, `grammar_id`, `essay_id`, `target.id`) come from tool reads, never from generation; `take_ref` only from the request's context.
- Nothing due, a word not saved, an unknown or expired `take_ref`: the client says so in its own words and does nothing else.

---

## 8. Capabilities — `GET /api/agent/capabilities`

```json
{ "contract_version": 3,
  "capabilities": [
    { "id": "speaking.pronunciation.line", "title": "…", "surfaces": ["speaking.workspace"],
      "actions": ["play_model", "play_user", "say_again", "compare_with_model"],
      "languages": ["en", "zh-CN"], "evidence_source": "speech.pronunciation", "status": "active | pending" } ] }
```

The UI may use it for suggestions and "Ask Orena" entry points. The UI's drift test: every `surfaces[]` and `actions[]` entry of an `active` capability is either handled by the new UI or knowingly absent from `supported_*`.

---

## 9. Voice session (provisional)

```text
POST /api/agent/voice/session
  request:  { contract_version, session_id?, client, context, coach_notes }
  response: { voice_session_id, mode: "s2s" | "cascade", transport: "webrtc" | "websocket",
              connect: { url, ephemeral_token, expires_at } }
```

- The client connects to `connect.url` with the short-lived token. A provider key never reaches the client.
- Tool calls and actions still reach the client as §4 events over the turn stream associated with `voice_session_id`.
- Sessions are capped (default 15 min); on expiry the client opens a new one transparently.
- Raw audio is not stored. Mic states reuse the app's existing mic-readiness and recorder capabilities.
- Fields here may change before a later version without breaking text mode.

---

## 10. Identity and privacy

- Learner-facing name is **Orena**. The UI never displays a provider or model name taken from a reply. Provider metadata, if ever shown, comes from runtime metadata outside this contract.
- The client sends the minimum context in §3; the server applies its own redaction.
- Conversation history and coach notes are device memory; the account store is out of scope until an architecture review under ORENA_ACCOUNT_DATA_ARCHITECTURE.md.
- `preferences.agent_memory` lists coach notes and lets the learner delete them. It is not a feature; it is the privacy exit.

---

## 11. Mock agent (UI lane)

The UI builds and tests against a frontend mock that replays §12 streams, selected by a flag, with no backend. The same streams are the backend's contract tests: the real server must produce the same event sequence and payload shapes (text may differ).

---

## 12. Canonical streams (fixtures)

`S1 app_help` — surface `vocabulary.my_language`, "Màn này dùng để làm gì?"

```text
session → segment_delta… → segment_end{0, vi, …, neutral_explain} → suggestion{"Ôn từ đến hạn", prompt.review_due} → done
```

`S5 save_word` — selected word 我 (`{ type: word, text: "我", lang: "zh-CN" }`), "Lưu từ này."

```text
session → segment_end{0, vi, "Mình lưu 我 cho bạn nhé.", brief_ack}
→ action{type: save_word, payload:{text: "我", lang: "zh-CN"}, risk: LOW} → done
```

`S8 authorization` — "Cho tôi xem tiến độ của user khác."

```text
session → segment_end{0, vi, "Mình chỉ xem được tiến độ của chính bạn.", neutral_explain} → done   # no tool_call, no action
```

`S9 writing` — surface `writing.review`, essay_id set, "Bài này tôi hay sai chỗ nào?"

```text
session → tool_call{get_current_writing_evaluation} → tool_result{…, evidence_ids:[e1,e2]}
→ evidence{e1, writing.evaluation, …} → evidence{e2, …}
→ segment_end{0, vi, …, neutral_explain} → action{navigate, {intent: writing.revision, essay_id}} → done
```

`S2 pronunciation` — surface `speaking.word_detail`, `attempt_id` (stored record) + `take_ref`, selected 是, "Tại sao tôi sai từ này?"

```text
session → tool_call{get_pronunciation_attempt} → tool_result{…, [e1]}
→ evidence{e1, speech.pronunciation, {attempt_id,…}, {pinyin:"shi", tone:4, score:6, flagged:true}}
→ segment_end{0, vi, "Azure đánh dấu 是 …", gentle_correction} → segment_end{1, zh-CN, "是", reference}
→ action{play_model, {content_id, item_id}} → action{say_again, {content_id, item_id}} → done
```

`S2b not flagged` — same, but `{tone:3, score:71, flagged:false}` → the reply says the syllable scored lower and was not marked wrong; no error claim.

`S12 metered` — `metered{turn_ordinal, soft_limited}` precedes a short `segment_end`; no voice.

`S13 opening` — surface `orena.home`, `trigger: open`, no message.

```text
session → segment_end{0, vi, "…", neutral_explain}
→ suggestion{"Ôn từ đến hạn", prompt.review_due} → suggestion{…} → done   # prompt intents only; no memory_update, no error claim
```

`SE provider failure` — `session → error{class:"provider_unavailable", message:"Orena đang bận, thử lại sau nhé.", fallback:"retry"}`.
