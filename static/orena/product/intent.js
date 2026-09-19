/* Following a piece of media to its end, understanding it, is a way of
   learning in its own right - not the corridor to an exercise. It leads the
   list because it is the first thing a learner does with a voice, and because
   without it Listening quietly collapses into Dictation. */
export const practiceIntentions = [
  'follow',
  'reading',
  'dictation',
  'shadowing',
  'speaking',
  'writing',
  'grammar',
  'recall',
];

/* Reading sits beside Follow for the same reason: a passage read to its end is
   the learning, and the questions after it are optional. */

// Intentions that open a practice panel over the moment. Follow and Reading are
// absent by design: they are the encounter itself.
export const deeperPractice = ['dictation', 'shadowing', 'speaking'];
export function route(hash = '') {
  const [path, query] = String(hash).replace(/^#\/?/, '').split('?');
  const q = new URLSearchParams(query || '');
  return {
    page: [
      'practice',
      'encounter',
      'content',
      'language',
      'expression',
      'preferences',
      'conversation',
      'continue',
      'collection',
      'admin',
      // D-059: Progress is a destination of its own, over the learner's
      // recorded evidence (LearnerSummary). Additive; no route changed.
      'progress',
      // D-059 Phase 4: a book has its own address, so Library cards are links.
      'book',
      // Global search, with its query in the address so it survives a reload.
      'search',
      // The learner's last thirty days of work, read from the owners that hold it.
      'history',
    ].includes(path)
      ? path
      : 'discover',
    id: q.get('id') || '',
    intent: practiceIntentions.includes(q.get('intent'))
      ? q.get('intent')
      : null,
    q: q.get('q') || '',
  };
}
export function link(page = 'discover', { id = '', intent = null, q = '' } = {}) {
  const query = new URLSearchParams();
  if (id) query.set('id', id);
  if (q) query.set('q', q);
  if (practiceIntentions.includes(intent)) query.set('intent', intent);
  return `#/${page === 'discover' ? '' : page}${query.size ? '?' + query : ''}`;
}
export function supports(content, intent) {
  if (!intent) return true;
  if (['follow', 'dictation', 'shadowing'].includes(intent))
    return ['audio', 'video', 'embed'].includes(
      content.kind || content.playback_kind,
    );
  // A voice is followed; a passage is read. Neither substitutes for the other,
  // so an intention to read must not offer an audio moment.
  if (intent === 'reading')
    return !['audio', 'video', 'embed'].includes(
      content.kind || content.playback_kind,
    );
  return true;
}

export function continuationLink(item) {
  if (item.id.startsWith('conversation:'))
    return link('conversation', { id: item.id });
  if (item.intent === 'speaking' && !/^(media:|url:)/.test(item.id))
    return link('practice', { id: item.id, intent: 'speaking' });
  if (item.id.startsWith('voice:'))
    return link('practice', { id: item.id, intent: 'speaking' });
  if (item.intent === 'writing' || /^(expression|essay):/.test(item.id))
    return link('expression', { id: item.id });
  if (item.id.startsWith('grammar:'))
    return link('practice', { id: item.id.slice(8), intent: 'grammar' });
  return link('encounter', { id: item.id, intent: item.intent });
}

/* A continuation belongs to the experience the learner was using, not to
   whichever page happens to render the shared device memory. Prefixes remain
   the routing truth; `intent` refines practice performed over source media. */
export function continuationExperience(item = {}) {
  const id = String(item.id || '');
  const intent = item.intent || '';
  if (id.startsWith('conversation:') || id.startsWith('voice:') || intent === 'speaking')
    return 'speaking';
  if (/^(expression|essay):/.test(id) || intent === 'writing') return 'writing';
  if (id.startsWith('grammar:') || intent === 'grammar') return 'understanding';
  if (intent === 'recall') return 'recall';
  if (/^(media:|url:|upload:)/.test(id)) {
    if (['dictation', 'shadowing'].includes(intent)) return 'practice';
    return 'listening';
  }
  if (intent === 'dictation' || intent === 'shadowing') return 'practice';
  return 'reading';
}
export function sourceLink(id) {
  if (id.startsWith('conversation:')) return link('conversation', { id });
  if (id.startsWith('voice:'))
    return link('practice', { id, intent: 'speaking' });
  /* A phrase kept from the learner's own writing leads back to that writing.
     This used to drop the work reference and land on the Practice room, so a
     card reading "From your own writing - Something you want to say" opened a
     room the learner had not been in. A way back that reopens unrelated content
     is worse than none: it looks like the thing it is not. */
  if (id.startsWith('expression:') || id.startsWith('essay:'))
    return link('expression', { id });
  if (id.startsWith('grammar:'))
    return link('practice', { id: id.slice(8), intent: 'grammar' });
  return link('encounter', { id });
}
