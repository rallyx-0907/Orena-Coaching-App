# Orena Intelligence — Agent Contract

Governance

Purpose: the single interface between the Orena Intelligence backend (lane `feature/orena-intelligence`, D-085) and the new learner UI that replaces the old one on `codex/work` (D-086). Both sides implement this file; neither reads the other's implementation.
Authority: D-085, D-086, D-092, D-094, D-095, D-096. Below AGENTS.md, ARCHITECTURE_INVARIANTS.md and the human gates; above either lane's own notes.
Change when: a field, event, action, intent or rule below changes. Edit **only on `codex/work`** through a reviewed commit that bumps `contract_version` and records the change in DECISION_LOG.md; the intelligence lane receives it by merging `codex/work` forward. Never edit this file on the intelligence lane.

`contract_version: 8`

v8 (D-16T, 2026-10-10): live voice is charged by duration against the same plan limit of Orena messages (`orena.message`): one message per `voice_seconds_per_message` seconds (the server's catalogue; 60 to begin with), reserved when the session opens and settled by the seconds it really lasted. `POST /api/agent/voice/session` (§9) can now answer `429 quota_exhausted` (not even one message left today: no token is minted, the voice conversation does not start, and the client does not fall back to its cascade, whose turns would be refused too) and `503 quota_unavailable`; the 503 `quota_voice_not_metered` of v7 is gone. `max_seconds` is now the session's own cap - 900 or fewer, as many seconds as the learner's remaining messages buy - and the vendor token lives exactly that long; the client ends the session at `max_seconds`. `Idempotency-Key` and `X-Orena-Timezone` (§3) also apply to the voice session request. No event, action, intent or other field changed; a client that declares `contract_version` ≤ 7 reads `max_seconds` as it always did and meets the two statuses as any failed session, falling back to its device cascade (its turns are then ordinary message turns, §3.3).

v7 (D-164, 2026-10-09): the plan's limit of Orena messages (`orena.message`, D-163) reaches this interface. §2.1 names the new HTTP statuses of `/api/agent/*` - `429 quota_exhausted` (an object body, told apart from the string `rate_limited`; never waited out or resent), `409 operation_in_progress | operation_finished | operation_conflict` (never a language change), `403 account_deleted | feature_not_in_plan`, `503 quota_unavailable` - and what the UI does with each; §3 names the optional request headers `Idempotency-Key` and `X-Orena-Timezone` and §3.3 what counts as a message (a turn that asks a model for the learner's message is one; the opening greeting and every answer made without a model are free and never refused, and the model writes at most one greeting per account per 30 minutes - past that the greeting is built from the learner's snapshot, still a full §3.2 stream); §9 names `503 quota_voice_not_metered` for `POST /api/agent/voice/session`. No event, field, action or intent changed. The statuses occur only where the server enforces the plan quota; a client that declares `contract_version` ≤ 6 sends neither header and, if it meets one of them, reads `429` as `rate_limited` and `409` as a language change - the shipped UI is v7.

v6 (D-145, 2026-10-08): voice and text are one conversation, and every spoken utterance is one turn of it. The client numbers what the learner says per voice session (`utterance`, an opaque token such as `u1`, never the words); `POST /api/agent/voice/tool` carries it, the new `POST /api/agent/voice/turn` closes it at the vendor's turn end, and `POST /api/agent/voice/end` may carry a transcript whose items are tagged with it (§9). All additions are optional: a client that declares `contract_version` ≤ 5 sends none of them and is served as before, except that its spoken turns are not counted as turns of the conversation. No event, action or text-turn request changes.

v5 (D-096, 2026-09-28): the learner's address - how Orena says "I" and "you" - travels as `context.address` and is kept as a coach note of kind `address` (§5.6), and the server's fixed copy follows it; a reply that comes with an action offers it and never reports it done, and no reply names a provider (§7, §10; S2 and S5 reworded); the UI publishes each surface's name and purpose for the server (§6.2); new canonical streams S14 and S15. A client that declares `contract_version` ≤ 4 sends no `address` and gets the language defaults; a server never sends an `address` note to it.

v4 (D-095, 2026-09-27): §2.1 names the HTTP statuses of `/api/agent/*` and what the UI does with each - `404` while the agent is off (Orena is absent, not an error), `409 target_language_mismatch`, `429 rate_limited` with `Retry-After` (wait, then send again) - and §4.1 names the stream's error classes and what each `fallback` asks of the UI. No event, field, action or intent changed; a server answers a v3 client exactly as before.

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
POST /api/agent/voice/session  → §9 (with /voice/tool and /voice/end)
```

Auth: the app's existing session. The server never trusts an identifier the model produces; the learner is always the authenticated caller.

SSE framing: `event: <name>\ndata: <json>\n\n`. The stream always ends with `done` or `error`. The client may abort (fetch AbortController); the server stops generating.

### 2.1 HTTP status

The client reads the status before it reads a stream. Every `/api/agent/*` route answers one of these:

| Status | Body | When | The UI |
| --- | --- | --- | --- |
| `200` | the stream (§4), or the registry (§8) | the request was admitted | reads it |
| `401` | the app's | no authenticated session; the app's auth answers before the agent runs | the app's own sign-in handling, as for any API; not an agent state |
| `404` | `{"detail": "Not Found"}` | the agent is off on this server: `AGENT_ENABLED` is not on, and always in production. While it is off every `/api/agent/*` request answers 404, a malformed one too (never 422) | Orena is absent for the rest of the visit: the UI hides every Orena entry point (the rail's Ask Orena field and mic, the phone bar's centre action, every Ask Orena control, the Orena destination). Not an error: no message, no retry. The UI learns it from `GET /api/agent/capabilities` when it starts, or from any 404 on these routes |
| `409` | `{"detail": "target_language_mismatch"}` | turn only: `context.locale.target`, mapped at the server's boundary (`zh-CN` → `zh`), is not the learner's learning language on the server - it changed in another tab or on another device after the UI built its context. Nothing ran and nothing was metered | the UI re-reads the learner's learning language and applies it as any change of learning language; the learner's message stays unsent in the composer; nothing is resent automatically |
| `422` | a validation detail | a request that does not match §3, or an `interface` on §8 that is not an interface language | a client defect: the client logs it and ends the turn with its own `transport` error, `fallback: none` (§4.1) |
| `429` | `{"detail": "rate_limited"}`, header `Retry-After: <seconds>` (whole seconds, at least 1) | the learner's sliding window is full; turns and capability reads are counted apart. Checked after the 404 and before the body is read: nothing ran, nothing was metered, and the refused request is not counted | a brief wait state, not an error: Orena stays thinking, then the client sends the same request again after `Retry-After` seconds; refused again, it waits again. The learner may cancel the wait (abort) |
| `429` | `{"detail": {"category": "quota_exhausted", "message", "retryable": false, "context": {"feature": "orena.message", "used", "limit", "unit", "window": "day", "resets_at", "plan", "upgrade"}}}`, header `Retry-After: <seconds until resets_at>` | turn, and the voice session (v8, §9): the learner's plan limit of Orena messages for this day (the learner's timezone, §3 `X-Orena-Timezone`) is used up. Refused before the stream (or before the voice token); nothing ran and nothing was charged. `detail` is an **object with a `category`**; `rate_limited`'s is a string | told, never waited out or resent: the reply's error line reads the server's own figures (`used` of `limit`) in the interface language, with the way to the plans (`context.upgrade`); the learner's message stays. `Retry-After` is when the limit resets, not a wait to resend |
| `409` | `{"detail": {"category": "operation_in_progress" \| "operation_finished" \| "operation_conflict" \| "account_not_ready", "message", "retryable"}}` | turn and voice session (v7, v8): the request's `Idempotency-Key` (§3) names a message already being processed (`in_progress`, retryable), already processed (`finished`) or sent with another body (`conflict`); or the learner's account is not set up yet (`account_not_ready`, retryable). `detail` is an object; `target_language_mismatch`'s is a string | the client's own `transport` error with `fallback: retry`; the retry is a new send with a new key. Never a change of learning language |
| `403` | `{"detail": {"category": "account_deleted" \| "feature_not_in_plan", "message", "retryable": false, "context": {"feature", "plan", "upgrade"}}}` (context on `feature_not_in_plan`) | turn and voice session (v7, v8): the account was deleted, or the learner's plan has no Orena messages. Nothing ran | the client's own `transport` error, `fallback: none` |
| `503` | `{"detail": {"category": "quota_unavailable", "message", "retryable": true, "context": {"reason"}}}` | turn and voice session (v7, v8): while the plan quota is enforced, the limit cannot be checked (the store or the catalogue is unavailable). Fail closed: nothing ran and no voice token was minted | the client's own `transport` error, `fallback: retry` |

A `409` or `422` counts toward the learner's limit; only a refused `rate_limited` `429` does not. The v7 statuses come after the learner's window, so they count.

---

## 3. Request — `POST /api/agent/turn`

```json
{
  "contract_version": 7,
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
    "address": { "self": "chị", "user": "em", "lang": "vi" },
    "client_evidence": { "pitch_contour_ref": "optional; measured client-side, never invented" }
  },
  "coach_notes": [
    { "id": "n1", "kind": "preference | goal | plan", "text": "…", "weight": 0.7, "last_reinforced": "ISO-8601", "expires_at": "ISO-8601 | null" }
  ]
}
```

Request headers (v7, both optional):

- `Idempotency-Key: <string, ≤ 200 printable characters>` - one per learner message, reused only when that same message is sent again (a resend after a `rate_limited` wait keeps it; a retry the learner taps mints a new one). The server counts a message against the plan once per key; a key already finished answers `409 operation_finished` (§2.1). Without it the server mints one: nothing is deduplicated, nothing is counted twice.
  It applies to `POST /api/agent/turn` (a `message` turn), to `POST /api/agent/voice/session` (v8: one per session the learner opens; it makes a repeated open request the same operation, never a second reservation) and to the text discussion route only. `POST /api/agent/voice/turn` and `POST /api/agent/voice/tool` neither require nor read it: a spoken utterance's own `utterance` token (§9) stays its identity, and the plan quota never touches those routes.
- `X-Orena-Timezone: <IANA zone, e.g. Asia/Ho_Chi_Minh>` - the device's timezone. The plan's limit of Orena messages is per day and the day ends at the learner's local midnight (`resets_at` in a `429 quota_exhausted`). Absent or invalid: the zone of the learner's last window, else UTC.

Rules:

- Omit any field that does not apply. Never send page state, DOM, or the whole profile.
- `trigger` ∈ `message` (default; `message` required) | `open` (no `message`; §3.2).
- `surface` is a **surface id** from §6.1, not a route.
- `locale` follows D-079: `interface`, `support`, `target`; `content` is the language of the content in view. Chinese is `zh-CN` in this contract; the product's internal code is `zh`, and each side maps at its own boundary (the client sends `zh-CN` for `zh` and maps `lang: "zh-CN"` back to `zh` before any API call; the agent does the same at its tool gateway). `en` is `en` on both sides.
- `activity_type` ∈ `app_help | coaching | review | reading | listening | pronunciation_practice | free_talk | conversation_practice | writing | grammar | vocabulary`.
- `selected_item`: `type` ∈ `word | sentence | feedback_item | grammar_point`. A word is named by `{ text, lang }` - the product has no word ids. A sentence, feedback item or grammar point carries its `id` and `text`.
  A word selected in a text may also carry `sentence`: the sentence it was selected in, as the learner sees it (≤ 500 characters, optional). "What does this word mean here?" is answered from that sentence; without it the agent knows only the word and the content (LEX-006).
- `attempt_id` is the id of the audio-free record the server stored for an assessed speaking take (`POST /api/speech/attempts` returns it). While no read-by-id exists (backend gap N-9), the client sends it only together with `content_id` and `selected_item.id` (the line), so the tool gateway can find the record through the existing filtered list. Evidence always comes from the server's record, never from client-supplied scores. When no record was stored, `attempt_id` is omitted.
- `take_ref` names a speaking take the new UI holds for the session (the server stores no take audio, D-076). It is minted by the client; the agent may only echo back a `take_ref` it received.
- `coach_notes` live in device memory (D-085 lane spec D7/D18); send at most 20, most weighted first, total ≤ 2 KB. They are of kind `preference`, `goal` or `plan`; the `address` note is never among them (§5.6).
- `address` is the learner's chosen way for Orena to say "I" and "you" in the support language (§5.6); omitted means that language's default.

### 3.1 Client capabilities are binding

The agent emits an `action` only if its `type` is in `client.supported_actions`, and a `navigate` only if its `intent` is in `client.supported_intents`. When the learner asks for something the client cannot do, the agent says so in plain words and emits no action. This is how a flow dropped from the new UI disappears from the agent without a backend change.

### 3.2 The opening turn

A client sends `trigger: "open"` when a thread starts empty: Orena Home with no thread on this device, or the contextual panel opened on a selection. The server answers with one greeting fitted to the context and learner, then the ways forward:

```text
session → segment_delta… → segment_end{0, <support>, …, neutral_explain}
→ suggestion{label, intent} ×(1-5) → [action{…} ×(0-2)] → done
```

- Read-only: no `memory_update`; only `LOW`-risk actions; no error claim without `evidence` (§5.3). It applies an existing `context.address` and never sets or offers one.
- One segment, ≤ 240 characters, in the `support` language; Design Contract rule 50 (learning-first copy) governs it.
- Not a learner turn: it does not advance `turn_ordinal`. A `soft_limited` learner gets the suggestions without the greeting, never an error.
- At most one per thread; the client may reuse it for the same `surface` + `selected_item` within a session.
- Free and never refused (§3.3). The model writes at most one greeting per account per 30 minutes; a greeting asked for sooner is built by the server from the learner's snapshot (a fact it holds, the default suggestions for the surface) with no model, and is the same stream, with the same events, to the client. A refresh or a reconnect therefore never costs a model call each time.

### 3.3 What counts as an Orena message (v7)

The plan limits Orena messages per day (Free / Plus / Pro: 20 / 200 / 1000; the catalogue is the server's). Where the server enforces it:

- A `trigger: "message"` turn that asks a model is **one** message, however many model rounds, tools or retries inside the turn it takes. Admission is decided once, before the stream starts: a refusal is a plain JSON status (§2.1) and nothing streams. A turn that ends in an `error` event, or that asked a model for nothing usable, is not counted; a turn the learner abandons after the model has started is counted.
- Free, and never refused even when the day is used up: the opening greeting (§3.2), an identity answer (§7 copy), "open it" on an offered place, and the opening on a selection - answers the server makes without a model.
- The text discussion over a reading (`POST /api/texts/discussion/turns`, not this contract) is also an Orena message; its `request_id` is its idempotency key.
- A live voice session (§9, v8) is charged by its duration: one message per `voice_seconds_per_message` seconds (the server's catalogue), a started unit counting as whole, so a session that lasted 61 seconds is two messages when the unit is 60. The server reserves the messages the session may use when it opens, mints the token for the seconds they buy, and settles the seconds it really lasted when it ends. A voice session that was never ended is charged what was reserved.
- The browser's push-to-talk cascade (§9 fallback) is not a voice session: its transcribed words are an ordinary message turn, one message each, with nothing added for the transcription.

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

`error.message` is learner-safe, already in the `support` language and addressed as §5.6 says. It never contains a provider name, key, region or raw provider output.

### 4.1 Error classes

An `error` event ends the turn. The UI acts on its `fallback`, never on its `class`: an unknown class is handled by its `fallback`, and an unknown `fallback` reads as `none`.

| `fallback` | The UI |
| --- | --- |
| `retry` | shows `message` with a retry control; retrying sends the same turn again as a new request. A retry is the learner's, never automatic: there is no switch to another provider |
| `text_only` | the voice session ended (§9): voice mode closes, the conversation continues in text, and `message` says so |
| `none` | shows `message`; there is nothing to retry |

The classes a server sends:

| `class` | `fallback` | When |
| --- | --- | --- |
| `provider_unavailable` | `retry` | the model provider did not answer usably: down, timed out, empty or malformed |
| `internal_error` | `retry` | any other failure inside the turn |
| `voice_unavailable` | `text_only` | a voice session failed (§9) |

The client adds one class of its own, which a server never sends: `transport`, with `fallback: retry` when the network fails, a status outside §2.1 arrives, or the stream ends without `done` or `error`, and with `fallback: none` for a `422`. Its message is the client's own copy in the `support` language.

A suggestion's `intent` is a prompt intent: it names the question the suggestion asks, in the `prompt.` namespace (`prompt.review_due`, `prompt.next_step`, `prompt.explain_word`, …). It is never a §6.1 surface or navigation id - going somewhere is an `action` (`navigate`). Tapping a suggestion sends its `label` as the learner's next message.

The client shows Orena as thinking from the moment it sends a turn until the first event other than `session` and `metered` (which are bookkeeping and arrive first), and shows `tool_call.label` while a tool runs; there is no separate text-mode thinking event. A turn never leaves the learner with an idle panel (LEX-028): when nothing arrives from the server for 90 seconds - before the response starts or between two events - the client stops the request and shows its own `transport` error with `fallback: retry`; a turn that ends with `done` but no text, action or suggestion is shown the same way.

---

## 5. Payload types

### 5.1 Segment

A reply is a list of segments, not one string, so mixed-language speech and reference audio can be routed.

```json
{ "index": 0, "lang": "vi",    "text": "Âm 是 bị đánh dấu là phát âm sai, điểm 6/100. Nghe mẫu rồi thử lại nhé:", "voice_style": "gentle_correction" }
{ "index": 1, "lang": "zh-CN", "text": "是", "voice_style": "reference" }
```

A segment's `text` may use a Markdown subset, which the client renders as its meaning, never as syntax (LEX-006):
headings, **bold**, *italic*, bulleted and numbered lists, `> ` quotes, inline `code`, and `http(s)` links. A
`reference` segment is plain text. Going somewhere in the app is always an `action` event (`navigate`, §7), never
a link written into the text: the client drops a non-web link, label and all, rather than show a command payload.
A simple question gets a short answer: the meaning first, then grouped readings and examples, one per line.

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

The agent proposes; the device stores. `upsert` carries a full note (§3 shape, with a new or existing `id`); `remove` carries `{ id }`. The client applies it, keeps weights and expiry, and drops notes whose weight decays below its threshold. The agent only proposes notes the learner stated directly; never emotions, circumstances or health. Kinds are `preference | goal | plan`, plus `address` (§5.6), which follows its own rules.

### 5.5 Display (actions and evidence, optional)

The new UI draws an action as a card (kind and duration, a title, one line on why, the button) and a source as a card (title, kind).

```json
"display": { "title": "A Morning in the City", "kind": "reading | listening | speaking | writing | vocabulary | grammar | review", "duration_s": 480, "reason": "Có 3 cụm bạn đã lưu hôm qua." }
```

`title`, `kind` and `duration_s` are copied from the domain record the server read for this action or evidence - never generated or estimated, absent when there is none. `reason` is the only generated field: ≤ 90 characters, in the `support` language, a statement the learner can check, never praise. The button's text is still `action.label`. A client that draws no cards ignores `display`.

### 5.6 Address (how Orena says "I" and "you")

`context.address` carries the learner's own choice, for their support language; omitted means that language's default. The object has `lang` and at least one of `self`, `user`, `register`:

```json
"address": { "self": "chị", "user": "em", "lang": "vi" }
"address": { "user": "小明", "register": "polite", "lang": "zh-CN" }
"address": { "user": "Minh", "lang": "en" }
```

| `lang` | default | `self` (how Orena refers to itself) | `user` (how Orena addresses the learner) | `register` |
| --- | --- | --- | --- | --- |
| `vi` | `mình` / `bạn` | e.g. `chị`, `em`, `tớ` | e.g. `em`, `anh`, `Minh`, `anh Minh` | ignored |
| `zh-CN` | `我` / `你`, `plain` | optional, default `我` | a form of address or name, e.g. `小明`, `王老师` | `plain` (你, the default) or `polite` (您, only when the learner asks) |
| `en` | `I` / `you` | ignored | a form of address or name used when calling the learner; it never replaces "you" | ignored |

A support language without a row uses its own ordinary first and second person, never the English pair.

- **Applied** only when `address.lang` equals `context.locale.support`; otherwise that language's default. It applies to every support-layer text addressed to the learner: segments in the support language, the opening turn (§3.2), `error.message` (§4), and the server's fixed support copy - identity answers, refusals, errors - through `{self}` / `{user}` slots whose defaults reproduce the unaddressed text. Not to interface-layer labels, which never address the learner in the first or second person, and not to target-language material (a Chinese example keeps its own `你` / `我`).
- **Terms.** `self` and `user` are 1-24 characters and at most 3 words, made only of Unicode letters - any script, with their combining marks: Vietnamese with its diacritics, Han characters - and single spaces between words. No digits, punctuation, symbols, line breaks or markup. `Nguyễn`, `anh Hương`, `小明` are valid. The client validates before storing and before sending; the server validates again and, if anything is invalid, uses the default for the whole object.
- **Data, never instruction.** The server always escapes the terms before they reach the model and never inserts them raw into its instructions.
- **This turn only.** The terms may carry the learner's name. The server uses them for the turn and never writes them to logs, telemetry, traces or any server store.
- **Casing.** Stored as the learner gave them; the server capitalises a sentence-initial use (`Chị là Orena…`).

How it changes - both lanes read these the same way:

1. Orena never asks about address on its own when the learner has given no sign of one.
2. The learner asks for a pair or a register ("Gọi mình là em nhé", "请用您称呼我", "Call me Minh"): applied at once.
3. Vietnamese kinship terms the learner uses of themselves or of Orena are answered in kind at once and saved: the learner calls themselves `anh` / `chị` → Orena says `em`; `cô` / `chú` / `bác` → `cháu`; the learner says `em` and calls Orena `anh` / `chị` → Orena uses that word. Self-reference is told apart from talk about others ("anh tôi"); when unsure, the current pair stays. Orena never uses a kinship term the learner has not used, and `tao` / `mày` only when explicitly asked.
4. A pair the learner keeps using that the server does not map by itself (e.g. `tớ` - `cậu`): Orena confirms once whether to use it. A yes sets it; a no is saved as the current pair, so Orena does not ask again.
5. Signs that the learner is a minor keep the default.
6. Nothing is inferred from gender, age, personality, a name or the learner's writing. The UI never derives it from the profile or anything else.

The note that keeps it:

```json
{ "id": "address-vi", "kind": "address",
  "address": { "self": "chị", "user": "em", "lang": "vi" },
  "text": "Xưng hô: Orena xưng \"chị\", gọi người học là \"em\".",
  "weight": 1, "last_reinforced": "ISO-8601", "expires_at": null }
```

- Set by `memory_update { op: "upsert" }` under the rules above; the reply that sets it already uses it. A change - to another pair, or back to the default - is an upsert that replaces the note (back to the default carries the default pair).
- One per support language: `id` is `address-<lang>`.
- `text` is the line the learner reads in `preferences.agent_memory`, in the support language; the server reads `address`, never parses `text`.
- It does not decay and has no expiry. The learner can delete it there (the privacy exit, §10); without it the default applies.
- The client sends it as `context.address` for the current support language on every request and never puts it in `coach_notes`.

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

- `content_id` is `<kind>:<id>`, one namespace for the UI and the agent (decision F-9, 2026-10-04): `article:<id>` (a Reading article), `book:<book_id>:<chapter_id>` (a book chapter), `media:<id>` (a Listening lesson or media item, curated or imported). The same string is the `context.content_id` the UI sends and the `payload.content_id` the agent returns; the UI maps it to its own route id. A tool may accept a bare id for an older client, never emit one.
- `grammar_id` is a Grammar Lab point id (D-100; decision F-3, 2026-10-04). An R5 Concept ID is never sent or emitted. Until the canonical Grammar Store/API serves points, the UI leaves `grammar.point` out of `client.supported_intents`, so by §3.1 no grammar point is navigated to.

Adding an id: contract change (bump version). Renaming a screen in the UI: no contract change.

### 6.2 Surface names and purposes (published by the UI)

The UI owns its places and says what they are, once. For every §6.1 id it publishes the place's `name` - the title of the route the id opens, from the shell's own copy, as the learner reads it - and a one-line `purpose`: what the learner does there, at most 90 characters, learning-first (Design Contract rule 50). Both are interface layer, in `en`, `vi` and `zh-CN`.

- Written in the new UI's copy layer (`static/orena/copy/surfaces.js`) and published as generated data, `static/orena/copy/surfaces.json`:

  ```json
  { "contract_version": 6,
    "surfaces": {
      "vocabulary.my_language": {
        "name":    { "en": "…", "vi": "…", "zh-CN": "…" },
        "purpose": { "en": "…", "vi": "…", "zh-CN": "…" } } } }
  ```

- A gate regenerates the file from the copy and fails on any difference, a §6.1 id without a `name`, or a `purpose` over the limit.
- The server reads names and purposes from this file (it arrives with `codex/work` merged forward) for "what is this screen for?" answers and for naming a place, and keeps no copies of its own. A surface without a `purpose` gets its name only; the server never writes a purpose of its own.
- Purposes are written once `docs/design/canonical-ui/IMPLEMENTATION_MAP.md` is stable - every screen a §6.1 id opens is built - so each describes a place that exists as drawn. Until then the file carries names only.

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
  - The server marks such an action with `"open": true` in its own data, in text turns and in voice (§9). The
    client runs exactly the actions so marked, at once, and keeps their buttons in the thread.
  - In text turns only `navigate` is ever marked. In voice, any low-risk action the learner asked for may be (R30).
  - A CONFIRM-risk action marked `open` still goes through the UI's own confirmation.
  - A short "open it" right after an offer ("mở giúp tôi", "open it", "打开它") is answered by the server with the
    offered `navigate`, marked `open`, and a one-line "opening it now" reply in the support language.
- A segment that comes with an action **offers** it: it never says or implies the action was done ("Mình lưu …", "Saved it for you", "我帮你保存了"). The learner does it by tapping or confirming. A `memory_update` is different: the device applies it without a tap, so a reply may say it is applied (S14).
- A reply that names the button uses its `label` as the learner sees it (interface language), and does not describe the button or the interface: "Bấm Lưu từ để thêm 我 vào từ vựng của bạn." The sentence around the label - an offer, including the server's own offer copy - is in the `support` language like the rest of the reply; only the quoted label stays as the button reads (D-135).
- A `navigate` to the learner's My Library about a word is offered only when that word is actually in their library (a tool read says so); a word not saved gets no My Library button and no offer to open it (D-135).
- Words: the vocabulary library keys a word on its text and the **session's active learning language**. A word action whose `lang` is not the active learning language is not executed; the client logs it.
- Ids in payloads (`content_id`, `grammar_id`, `essay_id`, `target.id`) come from tool reads, never from generation; `take_ref` only from the request's context.
- Nothing due, a word not saved, an unknown or expired `take_ref`: the client says so in its own words and does nothing else.

---

## 8. Capabilities — `GET /api/agent/capabilities`

```json
{ "contract_version": 6,
  "capabilities": [
    { "id": "speaking.pronunciation.line", "title": "…", "surfaces": ["speaking.workspace"],
      "actions": ["play_model", "play_user", "say_again", "compare_with_model"],
      "languages": ["en", "zh-CN"], "evidence_source": "speech.pronunciation", "status": "active | pending" } ] }
```

The UI may use it for suggestions and "Ask Orena" entry points. The UI's drift test: every `surfaces[]` and `actions[]` entry of an `active` capability is either handled by the new UI or knowingly absent from `supported_*`.

---

## 9. Voice session (mode A, R28)

Live voice is speech-to-speech through the vendor the server chooses (R28; the vendor is server configuration, never named to the client). It is off unless the
server runs with `AGENT_VOICE_ENABLED` beside `AGENT_ENABLED`. While off, the routes answer 404.

1. **Open a session.**
   - Request: `POST /api/agent/voice/session` with a turn body without `message`:
     `{ contract_version, session_id?, client, context, coach_notes }`.
   - 200 response:
     `{ voice_session_id, mode: "s2s", transport: "websocket", connect: { url, ephemeral_token, expires_at, setup }, max_seconds }`.
   - `max_seconds` (v8) is this session's cap in whole seconds: 900, or fewer when the learner's remaining Orena messages today buy fewer (`messages × voice_seconds_per_message`). The vendor token lives exactly that long (`connect.expires_at`). The client ends the session at `max_seconds` (it closes the socket and posts `/voice/end`, §9.6) and never opens another socket on the same token. It does not show a countdown or a notice of its own unless the design draws one.
   - Errors:
     - 429 `rate_limited` with Retry-After (the daily cap and turn window apply first);
     - 429 `quota_exhausted` (v8): `{"detail": {"category": "quota_exhausted", …, "context": {"feature": "orena.message", …}}}` (§2.1) - not even one message is left in the learner's day, so no session can start. No token is minted and nothing was charged. The client shows the server's figures where it shows a failed request, with the way to the plans, and does **not** fall back to its device cascade (its turns would be refused as well);
     - 409 `target_language_mismatch`, or `operation_in_progress | operation_finished | operation_conflict | account_not_ready` (v8, §2.1: the request's `Idempotency-Key` repeats a session already open or finished); 403 `account_deleted | feature_not_in_plan`;
     - 503 `voice_unavailable`;
     - 503 `quota_unavailable` (v8): while the plan quota is enforced, the limit cannot be checked (fail closed). No token is minted; the client carries the conversation on its device cascade exactly as for `voice_unavailable`. (v7's interim `quota_voice_not_metered` no longer exists.) `/voice/tool`, `/voice/turn`, `/voice/context` and `/voice/end` are unchanged by the quota: they act on a session `voice/session` created and read no `Idempotency-Key`; the `utterance` token is their identity;
     - 404 while voice is off.
2. **Connect.**
   - Open a WebSocket to `connect.url + "?access_token=" + encodeURIComponent(ephemeral_token)`.
   - Send `JSON.stringify(connect.setup)` as the first message. It only names the model; the server locks
     everything else.
   - Wait for a message that has the key `setupComplete`. Its value is `{}`, so the key is the signal.
3. **The conversation.** All audio is PCM16 mono.

   | | Message shape |
   | --- | --- |
   | Microphone, 16 kHz | `{ realtimeInput: { audio: { data: <base64>, mimeType: "audio/pcm;rate=16000" } } }` |
   | Orena's audio, 24 kHz | `serverContent.modelTurn.parts[].inlineData.data` |
   | Learner's words, shown in the thread | `serverContent.inputTranscription.text` |
   | Orena's words, shown in the thread | `serverContent.outputTranscription.text` |
   | Barge-in | `serverContent.interrupted`: the client stops playback at once and drops what is queued |
   | End of Orena's turn | `serverContent.turnComplete` |

   The provider's voice activity detection ends each utterance.
4. **Tools.**
   - On `{ toolCall: { functionCalls: [{ id, name, args }] } }`, the client posts `POST /api/agent/voice/tool` with
     `{ voice_session_id, utterance, calls, heard }`, where `heard` is the latest input transcription of the
     utterance in progress (absent while it has not arrived) and `utterance` is its identity (see Utterances below).
   - The answer is `{ responses, events }`. The client sends `{ toolResponse: { functionResponses: responses } }` on
     the socket and renders `events` as ordinary §4 events: `tool_call`, `tool_result`, `evidence`, `action`,
     `memory_update`.
   - An action is a button the learner taps. Buttons come only through the server.
   - 404 `voice_session_not_found` means the session is over.
   - R29, opening on request: when the learner's own words asked to open, play, listen to, watch or read a
     place, the answer carries a top-level `open: "<action id>"`. The client runs that action at once, without a
     tap (the §7 navigate-on-request precedent); the action event still arrives and its button stays in the
     thread. With no `open`, only the button is drawn.
   - The read tool `find_content` finds content in the learning language: the listening library and published
     reading. `offer_button` can offer `open_content`, which navigates to `listening.workspace` for `media:`
     content and to `reading.workspace` for `article:` or `book:` content. The content id always comes from a
     tool read. The session body lists both intents in `client.supported_intents`.
   - R30, one generic tool: `do_action` replaces `offer_button`.
     - Arguments: `type` from `client.supported_actions`, `intent` from `client.supported_intents`, and the optional
       ids and fields of §7.
     - The server fills in what is in view, builds the §7 payload and judges it like `propose_action`.
     - A low-risk action the learner's own words asked for comes with `open` and runs at once. A CONFIRM action
       (for example `unsave_word`) runs through the app's own confirm dialog, never silently. An action nobody
       asked for is a button only.
   - R30, context during a session.
     - The client posts `POST /api/agent/voice/context { voice_session_id, context }` on every route change and
       every line or word selection while the session runs, settled about 350 ms. `context` is the §3 context
       without `locale`.
     - The answer is `{ voice_session_id, note }`; 404 `voice_session_not_found`, 422 for a context that is not a
       valid object.
     - The client sends `note` on the socket as
       `{ clientContent: { turns: [{ role: "user", parts: [{ text: note }] }], turnComplete: false } }`, so Orena
       takes it in without answering it.
     - Ids in view become ids actions may name.
   - Utterances (v6).
     - The client numbers what the learner says within the session (`u1`, `u2`, ...: an opaque token of at most 64
       characters from `A-Za-z0-9._:-`; never the words, so the same words said twice are two utterances). An
       utterance opens with the first thing that belongs to it (its input transcription or a tool call) and closes
       at `serverContent.turnComplete`. A closed utterance is never reopened: a tool call that comes before the next
       transcript belongs to the next utterance. A turn with no learner words, such as Orena's own greeting, has none.
     - When the learner spoke, the client posts `POST /api/agent/voice/turn { voice_session_id, utterance, heard? }`
       at `turnComplete`, whether or not a tool was called. The answer is `{ voice_session_id, counted }`; `counted`
       is false when the utterance was already counted (by a tool call or an earlier post) or has no identity.
     - The server counts each utterance once as one turn of the conversation (an open offer ages and expires, a sent
       action leaves the duplicate window) and puts its words in once. 404 `voice_session_not_found` as above.
     - A client that sends no `utterance` is served, but its spoken turns are not counted.
   - R30, recognition: the locked setup carries the session's support and target languages for input
     transcription. Unclear or wrong-language input is answered "say it again", never acted on.
5. **Voices (R29).**
   - `GET /api/agent/voice/voices?interface=<en|vi|zh-CN>` answers
     `{ default, voices: [{ id, gender: "female"|"male", label }] }`.
   - There are ten voices: `f-clear`, `f-bright`, `f-warm`, `f-soft`, `f-young`, `f-gentle`, `m-calm`, `m-lively`,
     `m-friendly`, `m-steady`. Labels are in the interface language, and no vendor name appears.
   - The route has the same gates as `/voice/tool`.
   - The client keeps the learner's choice on the device and sends it as an optional `"voice": "<id>"` in the
     session body. The server locks it into the token; an unknown or missing id uses the default.
6. **End.**
   - `POST /api/agent/voice/end { voice_session_id, transcript? }` answers `{ voice_session_id, seconds }`. The client sends it
     when the learner stops, leaves (sendBeacon on pagehide), the socket closes, or `max_seconds` pass.
   - `transcript` (v6, optional, at most 40 items) is `[{ role: "user" | "assistant", text, utterance }]` from the two
     transcriptions, in order; a reply carries the `utterance` it answers. The server merges it into the
     conversation by `utterance`, never by the words, so each reply sits behind the words it answers and a typed turn
     or an earlier spoken one with the same words is never taken for it. An item that is not a turn is ignored; each
     text is cut to 4,000 characters. The `pagehide` beacon carries none.
   - The server bills the session time into the shared ledger. A session never ended is billed at its cap.
   - Plan (v8): the server settles the messages the session really used - `ceil(seconds / voice_seconds_per_message)`, never more than it reserved - and releases the rest. A session never ended is charged what it reserved (its cap). The answer's `seconds` is the wall-clock time from the token to the end, at most `max_seconds`. The learner is charged for time, whatever was said: a session that ended at once is still one started unit.

Rules:
- A provider key never reaches the client.
- Raw audio is not stored.
- Failure is never a switch to another vendor. The client falls back to its own cascade (D-138: record,
  `POST /api/speech/transcribe`, a §3 turn, device speech) for 404, 503 or a failed session.
- Mobile Safari starts audio only from a gesture, so the client creates its audio contexts inside the learner's
  tap.

---

## 10. Identity and privacy

- Learner-facing name is **Orena**. No segment, `error.message` or fixed copy names a provider or model - evidence is described by what was measured ("Âm 是 bị đánh dấu …") - and the UI never displays a provider or model name taken from a reply. Provider metadata, if ever shown, comes from runtime metadata outside this contract.
- The address terms (§5.6) are used for the turn only and never logged or stored by the server.
- The client sends the minimum context in §3; the server applies its own redaction.
- Conversation history and coach notes are device memory; the account store is out of scope until an architecture review under ORENA_ACCOUNT_DATA_ARCHITECTURE.md.
- `preferences.agent_memory` lists coach notes and lets the learner delete them. It is not a feature; it is the privacy exit.

---

## 11. Mock agent (UI lane)

The UI builds and tests against a frontend mock that replays §12 streams, selected by a flag, with no backend. The same streams are the backend's contract tests: the real server must produce the same event sequence and payload shapes (text may differ).

The mock also answers the §2.1 statuses a live server can give (`?agent=H404`, `H409`, `H429` in the address), so every state the UI owes them can be built and reviewed without a backend.

---

## 12. Canonical streams (fixtures)

`S1 app_help` — surface `vocabulary.my_language`, "Màn này dùng để làm gì?"

```text
session → segment_delta… → segment_end{0, vi, …, neutral_explain} → suggestion{"Ôn từ đến hạn", prompt.review_due} → done
```

`S5 save_word` — selected word 我 (`{ type: word, text: "我", lang: "zh-CN" }`), "Lưu từ này."

```text
session → segment_end{0, vi, "Bấm Lưu từ để thêm 我 vào từ vựng của bạn.", brief_ack}
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
→ segment_end{0, vi, "Âm 是 bị đánh dấu là phát âm sai …", gentle_correction} → segment_end{1, zh-CN, "是", reference}
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

`S14 address` — surface `orena.home`, "Gọi mình là em, còn Orena xưng chị nhé."

```text
session → memory_update{upsert, {id: "address-vi", kind: address, address: {self: "chị", user: "em", lang: "vi"}, weight: 1, expires_at: null}}
→ segment_end{0, vi, "Được rồi, từ giờ chị gọi em là em nhé.", brief_ack} → done
```

`S15 identity with address` — surface `home`, `context.address {self: "chị", user: "em", lang: "vi"}`, "Bạn là ai?"

```text
session → segment_end{0, vi, "Chị là Orena, trợ lý học tập AI … của em …", neutral_explain} → done   # fixed copy, by rule, no model
```
