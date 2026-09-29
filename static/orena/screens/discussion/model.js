/* Discussion (design route `discussion`, frame 46): pure data mapping, DOM-free so
   scripts/test_orena_screen_discussion.mjs can test it without a browser.

   The backend's source kinds (writing_coach/persistence/discussion_repository.py SOURCE_KINDS)
   are `story | media | reading_session | book_chapter` - a vocabulary written for the OLD content
   model (`static/orena/ui/discussion.js#discussionSource`), not the new "<kind>:<id>" content-id
   scheme every screen shares today. `discussionSourceFor` is this screen's own mapping from the
   new scheme onto that same real backend vocabulary, kept as close to the old mapping's own logic
   as the new id shape allows: a book chapter is `book_chapter` (source id "<bookId>:<chapterId>",
   the same shape the backend's own book-chapter routing already expects elsewhere), a media item
   is `media`, and everything else this screen ever reaches from Reader (an article, a learner's
   own imported text) is the generic `story` kind - there is no `article` source kind in the
   backend's vocabulary, so an article's discussion is a story about it, the same fallback the old
   mapping used for anything it didn't special-case. Recorded as a mapping decision, not a backend
   gap: docs/project/UI_BACKEND_GAPS.md. */

export function parseContentId(raw) {
  const value = String(raw || '');
  const first = value.indexOf(':');
  if (first === -1) return { kind: '', id: '' };
  const kind = value.slice(0, first);
  const rest = value.slice(first + 1);
  if (kind === 'book') {
    const second = rest.indexOf(':');
    if (second === -1) return { kind, id: rest, chapterId: '' };
    return { kind, id: rest.slice(0, second), chapterId: rest.slice(second + 1) };
  }
  return { kind, id: rest };
}

export function discussionSourceFor({ kind, id, chapterId }) {
  if (kind === 'book') return { source_kind: 'book_chapter', source_id: chapterId ? `${id}:${chapterId}` : id };
  if (kind === 'media' || kind === 'upload') return { source_kind: 'media', source_id: id };
  return { source_kind: 'story', source_id: id };
}

/* One request id per submission, so a retry after a lost response returns the exchange already
   produced instead of asking the provider twice - the endpoint's own dedup key. */
export function newRequestId() {
  if (crypto?.randomUUID) return crypto.randomUUID();
  return `r${Date.now()}${Math.random().toString(16).slice(2)}`.slice(0, 64);
}

/* The thread as the backend actually returns it -> what the screen paints: turns already in
   ordinal order (list_turns/find_discussion already sort them; this only guards against a caller
   passing an unsorted array, e.g. an optimistic local one), each carrying the one flag the
   markup needs to tell a bubble side. A row with no recognised role is dropped rather than shown
   as either speaker - never a guess. */
export function mapTurns(turns) {
  return (Array.isArray(turns) ? turns : [])
    .filter((turn) => turn && (turn.role === 'learner' || turn.role === 'assistant'))
    .slice()
    .sort((a, b) => (a.ordinal ?? 0) - (b.ordinal ?? 0))
    .map((turn) => ({ role: turn.role, isAssistant: turn.role === 'assistant', body: String(turn.body || '') }));
}

/* The backend's own cap on one turn's body (writing_coach/persistence/discussion_repository.py
   MAX_BODY_CHARACTERS), named once so the input stops at it instead of refusing a longer send. */
export const MAX_BODY_CHARACTERS = 4000;

export function canSend(text, maxLength = MAX_BODY_CHARACTERS) {
  const trimmed = String(text || '').trim();
  return trimmed.length > 0 && trimmed.length <= maxLength;
}

/* Enter sends - except the Enter that confirms a candidate while a Chinese (or Japanese, Korean)
   input method is composing, which is not a send: `isComposing`, or the legacy keyCode 229 some
   engines report instead. */
export function isSendKey({ key, isComposing = false, keyCode = 0 } = {}) {
  return key === 'Enter' && !isComposing && keyCode !== 229;
}

/* The learner's own question, as the thread shows it the moment it is sent (the source appends it
   before the reply arrives, `dsSend`); replaced by the server's own turns once they are read back. */
export function optimisticTurn(text) {
  return { role: 'learner', isAssistant: false, body: String(text || '').trim() };
}
