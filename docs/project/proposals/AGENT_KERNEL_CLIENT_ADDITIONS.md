# Conversation kernel: additive client contract items (proposal for the UI lane)

Status: PROPOSED, 2026-10-07. Author: Intelligence lane (`feature/orena-intelligence`). The contract
(`AGENT_CONTRACT.md`) is edited only on `codex/work` (D-086); this file lists what the server already tolerates and
what the client may adopt. Nothing here is required: a client that sends none of it keeps working, and a server
ignores unknown fields.

## What the server now does without any client change

- Keeps the recent turns of a session (in this process, 30 minutes of idle time, 20 turns / 36k characters) and shows
  them to the model, so follow-ups and references work in text. The client already sends `session_id` on each turn.
- Keeps one open offer per session (any action) and lets the model accept or decline it from the learner's words.
- Keeps a factual focus (active topic, current word/sentence, a long pasted text).
- A language change does not start a new conversation.

These are server limits, not a contract: the transcript is still device memory (§10), and the server's copy is lost
after the idle time, on a restart or on another worker. Durable conversations and memory wait for the human and an
architecture review (`AGENTS.md` §7).

## Additive items for text + voice as one conversation (all optional)

1. **`POST /api/agent/voice/session` response gains `session_id`** (string): the conversation the voice session is part
   of. The client already may send `session_id` in the request body; when it does, the voice session opens inside that
   typed conversation. When it does not, the response says which session was created, and the client sends it on its
   next typed turn.
2. **An utterance identity** (`live-voice.js` implements it, `utteranceTracker`): the client numbers what the learner
   says per voice session (`u1`, `u2`, ...; an opaque token of at most 64 characters, never the words). It opens with the
   first thing that belongs to the utterance (its transcript or a tool call) and closes at the vendor's `turnComplete`.
   - `POST /api/agent/voice/tool` gains `utterance`.
   - **New** `POST /api/agent/voice/turn { voice_session_id, utterance, heard? }`, sent at `turnComplete` whenever the
     learner spoke, with or without a tool call. The server counts the utterance as one turn of the conversation, once
     (a repeat of the same `utterance` is a no-op), and puts its words in once.
   Identical words said twice are two utterances. A client that sends no identity is still served, but its spoken turns
   are not counted as turns.
3. **`POST /api/agent/voice/end` request gains `transcript`** (optional array, at most 40 items):
   `[{ "role": "user" | "assistant", "text": string, "utterance": string }]` (a reply carries the utterance it answers),
   from `inputTranscription` / `outputTranscription`. The server merges it by `utterance` - never by the words - so each
   reply sits behind the words it answers, and a typed turn or an earlier spoken one with the same words is never taken
   for it. Items that are not a turn are ignored; each text is cut to 4000 characters. Send it on the end paths the
   client can (button, socket close; the `pagehide` beacon carries none).
4. **`do_action` gains `requested`** (boolean, model-facing, not a client field): the model sets it when the learner's
   own words asked for the action or accepted Orena's offer. The client sees no change: an action that runs at once
   still arrives with `open: true` (§7), now also for words no phrase list knows.

## Behaviour a client may see

- An action accepted from an open offer arrives with `open: true` and an `id` that is the offer's own (`p<n>-<hash>`),
  stable for that offer; the offer's button (`a1` ...) keeps its stream-local id.
- The same words said twice ("ok lưu", "ok lưu") run the action once; the second time no `open` action is sent.
- The server says an action was *sent*, never that it worked: the app shows the result.

## Not proposed

No change to the event stream, the action allowlist or the request schema of a text turn.
