/* Addresses of the UI that `/` served before the cutover (D-091 item 5, D-143). A bookmark, a link in a
   note or an old tab still arrives somewhere real: the place of the learner UI that does the same job.
   Pure, so scripts/test_orena_former_addresses.mjs pins every mapping.

   formerAddress('#/encounter?id=media:abc') -> '#/content/media%3Aabc'; null for an address that is
   already the learner UI's own (including the ones whose path did not change: discover, practice,
   conversation, progress, profile, search, admin). */

// The old Platform Admin console's sections (`#/admin?id=<section>`), and where each now lives.
const ADMIN_SECTIONS = Object.freeze({
  overview: 'admin/overview',
  ai: 'admin/ai',
  users: 'admin/users',
  content: 'admin/content',
  imports: 'admin/imports',
  operations: 'admin/operations',
  reading: 'admin/reading',
});

// Old practice intentions with no lesson: the place that offers that practice now.
const PRACTICE_INTENTS = Object.freeze({
  follow: 'discover',
  reading: 'discover',
  dictation: 'discover',
  shadowing: 'practice',
  speaking: 'practice',
  writing: 'write',
  grammar: 'grammar',
  recall: 'review',
});

// Old places whose path the learner UI does not have; the value is where the job is done now.
const PLACES = Object.freeze({
  language: 'library',
  expression: 'library',
  writing: 'write',
  preferences: 'settings',
  continue: 'today',
  history: 'progress',
});

function content(id, kind = '') {
  if (!id) return '';
  const value = id.includes(':') || !kind ? id : `${kind}:${id}`;
  return value.includes(':') ? `content/${encodeURIComponent(value)}` : '';
}

export function formerAddress(hash = '') {
  const [rawPath, rawQuery = ''] = String(hash).replace(/^#\/?/, '').split('?');
  const path = rawPath.replace(/\/+$/, '');
  const query = new URLSearchParams(rawQuery);
  const id = query.get('id') || '';
  let target = '';
  if (path === 'encounter') target = content(id) || 'discover';
  else if (path === 'book') target = content(id, 'book') || 'discover';
  else if (path === 'content' && id) target = content(id) || 'discover';
  else if (path === 'collection' && id) target = `collection/${encodeURIComponent(id)}`;
  else if (path === 'collection') target = 'library';
  else if (path === 'admin' && id) target = ADMIN_SECTIONS[id] || 'admin';
  else if (path === 'practice' && query.get('intent')) {
    const intent = query.get('intent');
    const lesson = ['dictation', 'shadowing', 'speaking'].includes(intent) ? content(id) : '';
    target = lesson || PRACTICE_INTENTS[intent] || 'practice';
  } else if (Object.hasOwn(PLACES, path)) target = PLACES[path];
  return target ? `#/${target}` : null;
}
