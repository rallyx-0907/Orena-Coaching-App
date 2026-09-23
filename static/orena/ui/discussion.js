/* The learner's conversation about a whole text (D-072.2).

   The bar under the text draws "Thảo luận" - the source's fourth action - and
   it opens this thread. Everything here is the learner's own words and the
   tutor's answers, read back from the account (`/api/texts/discussion`), never
   from device memory: this is the first conversational content Orena keeps.

   What this file will not do: invent an answer. When no provider can answer,
   the question stays in the box, the room says the tutor is unavailable and
   offers a retry - the endpoint's own contract. */
import { esc } from './html.js';
import { icon } from './phosphor.js';

const MAX_BODY = 4000;

/* The identity the app already routes on, split into the two fields the
   endpoint scopes a thread by. `story:borrowed-table` is a kind and an id; a
   book chapter carries the book and the chapter, and the thread belongs to the
   chapter that is open. */
export function discussionSource(item, book = null) {
  const raw = String(item?.id || '');
  if (book?.id) return { source_kind: 'book_chapter', source_id: raw.replace(/^book:/, '') };
  const [kind, rest] = raw.includes(':') ? [raw.slice(0, raw.indexOf(':')), raw.slice(raw.indexOf(':') + 1)] : ['', raw];
  if (kind === 'media') return { source_kind: 'media', source_id: rest };
  if (kind === 'reading') return { source_kind: 'reading_session', source_id: rest };
  return { source_kind: 'story', source_id: rest || raw };
}

const turnHtml = (turn, language, support) => `<li class="discussion-turn" data-role="${esc(turn.role)}">
  <span class="ds-label discussion-turn__who">${turn.role === 'learner' ? '' : icon('sparkle', { size: 13 })}</span>
  <p lang="${esc(turn.role === 'learner' ? support : support)}">${esc(turn.body)}</p>
</li>`;

/* One request id per submission, so a retry after a timeout returns the answer
   that was already produced instead of spending a second provider call. */
const newRequestId = () =>
  (crypto?.randomUUID ? crypto.randomUUID() : `r${Date.now()}${Math.random().toString(16).slice(2)}`).slice(0, 64);

export function discussionSection(c, r) {
  return `<section class="discussion" data-discussion>
    <ol class="discussion-thread" data-discussion-thread></ol>
    <p class="discussion-note" data-discussion-note role="status" hidden></p>
    <form class="discussion-composer" data-discussion-form>
      <label class="sr-only" for="discussion-body">${esc(r.readerDiscuss)}</label>
      <textarea id="discussion-body" name="body" rows="2" maxlength="${MAX_BODY}" data-discussion-body
        placeholder="${esc(r.discussionPlaceholder)}"></textarea>
      <button type="submit" class="primary" data-discussion-send>${icon('paper-plane-tilt', { size: 17 })}<span>${esc(r.discussionSend)}</span></button>
    </form>
  </section>`;
}

export function mountDiscussion(root, { c, r, source, language, support, alive = () => true }) {
  const thread = root.querySelector('[data-discussion-thread]');
  const form = root.querySelector('[data-discussion-form]');
  const field = root.querySelector('[data-discussion-body]');
  const send = root.querySelector('[data-discussion-send]');
  const note = root.querySelector('[data-discussion-note]');
  if (!thread || !form) return;

  const say = (message, tone = '') => {
    note.hidden = !message;
    note.textContent = message || '';
    note.dataset.tone = tone;
  };
  const paint = (turns) => {
    thread.innerHTML = turns.map((turn) => turnHtml(turn, language, support)).join('');
    thread.scrollTop = thread.scrollHeight;
  };
  const query = new URLSearchParams(source).toString();

  /* The whole thread, read back. A POST answers with only the pair it wrote,
     so the thread is re-read rather than appended to - the account, not the
     page, is what holds the conversation. */
  const load = async () => {
    try {
      const response = await fetch(`/api/texts/discussion?${query}`);
      if (!response.ok) throw new Error(String(response.status));
      const payload = await response.json();
      if (!alive()) return true;
      paint(payload.turns || []);
      return true;
    } catch {
      if (alive()) say(c.unavailable, 'error');
      return false;
    }
  };
  load();

  let pending = false;
  form.onsubmit = async (event) => {
    event.preventDefault();
    const body = String(field.value || '').trim();
    if (!body || pending) return;
    pending = true;
    send.disabled = true;
    say(r.discussionThinking);
    const request_id = newRequestId();
    try {
      const response = await fetch('/api/texts/discussion/turns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...source, body, request_id }),
      });
      if (!alive()) return;
      if (!response.ok) {
        /* The endpoint answers 503 when no provider could answer and 409 at the
           cap. Neither is the learner's fault and neither invents an answer, so
           their question stays in the box for a retry. */
        say(response.status === 409 ? r.discussionFull : r.discussionUnavailable, 'error');
        return;
      }
      await response.json();
      field.value = '';
      say('');
      await load();
    } catch {
      if (alive()) say(r.discussionUnavailable, 'error');
    } finally {
      pending = false;
      send.disabled = false;
    }
  };
}
