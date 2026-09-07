/* Following a piece of media to its end, understanding it, is a way of
   learning in its own right - not the corridor to an exercise. It leads the
   list because it is the first thing a learner does with a voice, and because
   without it Listening quietly collapses into Dictation. */
export const practiceIntentions = [
  'follow',
  'dictation',
  'shadowing',
  'speaking',
  'writing',
  'grammar',
  'recall',
];

// Intentions that open a practice panel over the moment. Follow is absent by
// design: it is the encounter itself.
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
    ].includes(path)
      ? path
      : 'discover',
    id: q.get('id') || '',
    intent: practiceIntentions.includes(q.get('intent'))
      ? q.get('intent')
      : null,
  };
}
export function link(page = 'discover', { id = '', intent = null } = {}) {
  const query = new URLSearchParams();
  if (id) query.set('id', id);
  if (practiceIntentions.includes(intent)) query.set('intent', intent);
  return `#/${page === 'discover' ? '' : page}${query.size ? '?' + query : ''}`;
}
export function supports(content, intent) {
  if (!intent) return true;
  if (['follow', 'dictation', 'shadowing'].includes(intent))
    return ['audio', 'video', 'embed'].includes(
      content.kind || content.playback_kind,
    );
  return true;
}

export function continuationLink(item) {
  if (item.intent === 'writing' || item.id.startsWith('expression:'))
    return link('expression', { id: item.id });
  if (item.id.startsWith('grammar:'))
    return link('practice', { id: item.id.slice(8), intent: 'grammar' });
  return link('encounter', { id: item.id, intent: item.intent });
}
export function sourceLink(id) {
  if (id.startsWith('expression:')) return link('practice');
  if (id.startsWith('grammar:'))
    return link('practice', { id: id.slice(8), intent: 'grammar' });
  return link('encounter', { id });
}
