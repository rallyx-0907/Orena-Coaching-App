/* Every route of the new learner UI, one per frame of the pinned design (D-088, D-091;
   docs/design/canonical-ui/IMPLEMENTATION_MAP.md).

   - `path`     hash path pattern; `:name` segments become params.
   - `design`   the design script's own route key (state.route), so scripts/test_orena_shell.mjs
                can prove `focus` equals the design's focus list and `primary` its six places.
   - `screen`   folder under static/orena/screens/ holding screen.js; a route whose screen is not
                built yet renders the design's Coming soon screen with the route's title.
   - `focus`    a learning workspace (Design Contract rules 47, 49): no top bar, no phone header,
                no phone bar.
   - `crumb`    the key of its title in copy/shell.js (the top bar's breadcrumb screen label).
   - `lesson`   a content route that shows the design's loading skeleton while it loads.
   - `intent`   the AGENT_CONTRACT §6.1 id that opens it, when there is one. */

export const PRIMARY = Object.freeze(['today', 'discover', 'orena', 'practice', 'library', 'progress']);

export const ROUTES = Object.freeze([
  // Browsing places: the shell is drawn.
  { id: 'today', path: 'today', design: 'today', screen: 'today', focus: false, crumb: 'today', intent: 'home' },
  { id: 'discover', path: 'discover', design: 'discover', screen: 'discover', focus: false, crumb: 'discover', intent: 'library' },
  { id: 'content', path: 'content/:id', design: 'detail', screen: 'content', focus: false, crumb: 'content' },
  { id: 'orena', path: 'orena', design: 'orena', screen: 'orena', focus: false, crumb: 'orena', intent: 'orena.home' },
  { id: 'practice', path: 'practice', design: 'practice', screen: 'practice', focus: false, crumb: 'practiceHub' },
  { id: 'skillhub', path: 'practice/:skill', design: 'skillhub', screen: 'practice', focus: false, crumb: 'practiceHub' },
  { id: 'library', path: 'library', design: 'library', screen: 'library', focus: false, crumb: 'myLibrary', intent: 'vocabulary.my_language' },
  { id: 'collection', path: 'collection/:id', design: 'collection', screen: 'collection', focus: false, crumb: 'collection' },
  { id: 'word', path: 'word/:id', design: 'word', screen: 'word', focus: false, crumb: 'word', intent: 'vocabulary.word' },
  { id: 'grammarlib', path: 'grammar', design: 'grammarlib', screen: 'grammar', focus: false, crumb: 'grammar', intent: 'grammar.catalog' },
  { id: 'progress', path: 'progress', design: 'progress', screen: 'progress', focus: false, crumb: 'progress', intent: 'progress' },
  { id: 'profile', path: 'profile', design: 'profile', screen: 'profile', focus: false, crumb: 'profile' },
  { id: 'coming', path: 'coming/:key', design: 'coming', screen: 'coming', focus: false, crumb: 'comingSoon' },

  // Learning workspaces: focus.
  { id: 'settings', path: 'settings', design: 'settings', screen: 'settings', focus: true, crumb: 'settings', intent: 'preferences' },
  { id: 'search', path: 'search', design: 'search', screen: 'search', focus: true, crumb: 'search' },
  { id: 'reader', path: 'read/:id', design: 'reader', screen: 'reader', focus: true, crumb: 'reader', lesson: true, intent: 'reading.workspace' },
  { id: 'checku', path: 'read/:id/check', design: 'checku', screen: 'check', focus: true, crumb: 'checkUnderstanding', lesson: true },
  { id: 'rcomplete', path: 'read/:id/done', design: 'rcomplete', screen: 'reader-complete', focus: true, crumb: 'readingComplete', lesson: true },
  { id: 'rtransfer', path: 'read/:id/transfer', design: 'rtransfer', screen: 'reading-transfer', focus: true, crumb: 'readingTransfer', lesson: true },
  { id: 'discussion', path: 'read/:id/discuss', design: 'discussion', screen: 'discussion', focus: true, crumb: 'discussion' },
  { id: 'listening', path: 'listen/:id', design: 'listening', screen: 'listening', focus: true, crumb: 'listening', lesson: true, intent: 'listening.workspace' },
  { id: 'dictation', path: 'listen/:id/dictation', design: 'dictation', screen: 'dictation', focus: true, crumb: 'dictation', lesson: true, intent: 'listening.dictation' },
  { id: 'shadow', path: 'listen/:id/shadow', design: 'shadow', screen: 'shadowing', focus: true, crumb: 'shadowing', lesson: true },
  { id: 'react', path: 'listen/:id/react', design: 'react', screen: 'react', focus: true, crumb: 'reactReuse', lesson: true },
  { id: 'respond', path: 'respond/:id', design: 'respond', screen: 'respond', focus: true, crumb: 'respondToContent', lesson: true },
  { id: 'speak', path: 'speak/:id', design: 'speak', screen: 'speak', focus: true, crumb: 'pronunciation', lesson: true, intent: 'speaking.workspace' },
  { id: 'compare', path: 'speak/:id/compare', design: 'compare', screen: 'compare', focus: true, crumb: 'compareWithModel', intent: 'speaking.compare' },
  { id: 'attempts', path: 'speak/:id/attempts', design: 'attempts', screen: 'attempts', focus: true, crumb: 'attemptHistory' },
  { id: 'spsummary', path: 'speak-summary', design: 'spsummary', screen: 'speak-summary', focus: true, crumb: 'speakingSummary' },
  { id: 'freetalk', path: 'free-talk', design: 'freetalk', screen: 'free-talk', focus: true, crumb: 'freeTalk', lesson: true, intent: 'speaking.free_talk' },
  { id: 'conv', path: 'conversation', design: 'conv', screen: 'conversation', focus: true, crumb: 'conversation', lesson: true },
  { id: 'situation', path: 'situation', design: 'situation', screen: 'situation', focus: true, crumb: 'situationReaction', lesson: true },
  { id: 'retell', path: 'retell/:id', design: 'retell', screen: 'retell', focus: true, crumb: 'retell', lesson: true },
  { id: 'timedreact', path: 'timed-reaction', design: 'timedreact', screen: 'timed-reaction', focus: true, crumb: 'timedReaction', lesson: true },
  { id: 'mock', path: 'interview', design: 'mock', screen: 'interview', focus: true, crumb: 'mockInterview', lesson: true },
  { id: 'sound', path: 'sounds', design: 'sound', screen: 'sounds', focus: true, crumb: 'soundTone', lesson: true },
  { id: 'writing', path: 'write', design: 'writing', screen: 'writing', focus: true, crumb: 'writing', lesson: true, intent: 'writing.workspace' },
  { id: 'writingDraft', path: 'write/:id', design: 'writing', screen: 'writing', focus: true, crumb: 'writing', lesson: true, intent: 'writing.review' },
  { id: 'wrcompare', path: 'write/:id/compare', design: 'wrcompare', screen: 'writing-compare', focus: true, crumb: 'compareVersions', intent: 'writing.revision' },
  { id: 'rewrite', path: 'rewrite', design: 'rewrite', screen: 'rewrite', focus: true, crumb: 'contextRewrite', lesson: true },
  { id: 'timedwr', path: 'timed-writing', design: 'timedwr', screen: 'timed-writing', focus: true, crumb: 'timedWriting', lesson: true },
  { id: 'review', path: 'review', design: 'review', screen: 'review', focus: true, crumb: 'review', lesson: true, intent: 'vocabulary.review_due' },
  { id: 'timed', path: 'timed-recall', design: 'timed', screen: 'timed-recall', focus: true, crumb: 'timedRecall', lesson: true },
  { id: 'transfer', path: 'transfer', design: 'transfer', screen: 'transfer', focus: true, crumb: 'contextTransfer', lesson: true },
  { id: 'feed', path: 'feed', design: 'feed', screen: 'feed', focus: true, crumb: 'dailyFeed', lesson: true },
  { id: 'errfix', path: 'from-your-errors', design: 'errfix', screen: 'errors', focus: true, crumb: 'fromYourErrors', lesson: true },
  { id: 'gconcept', path: 'grammar/:id', design: 'gconcept', screen: 'grammar-concept', focus: true, crumb: 'grammar', lesson: true, intent: 'grammar.point' },
]);

export const DEFAULT_ROUTE = 'today';

const compiled = ROUTES.map((route) => {
  const names = [];
  const pattern = route.path
    .split('/')
    .map((segment) => {
      if (segment.startsWith(':')) {
        names.push(segment.slice(1));
        return '([^/]+)';
      }
      return segment.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    })
    .join('/');
  return { route, names, regex: new RegExp(`^${pattern}$`) };
});

/* "#/read/abc?tab=x" → { route, params: { id: 'abc' }, query: URLSearchParams }. An unknown address
   is null; the router sends it to the default place. */
export function match(hash = '') {
  const [pathPart, queryPart = ''] = String(hash).replace(/^#\/?/, '').split('?');
  const path = pathPart.replace(/\/+$/, '');
  const query = new URLSearchParams(queryPart);
  if (!path) return { route: byId(DEFAULT_ROUTE), params: {}, query };
  for (const { route, names, regex } of compiled) {
    const found = regex.exec(path);
    if (!found) continue;
    const params = {};
    names.forEach((name, index) => {
      params[name] = decodeURIComponent(found[index + 1]);
    });
    return { route, params, query };
  }
  return null;
}

export function byId(id) {
  return ROUTES.find((route) => route.id === id) || null;
}

/* The address of a route: href('reader', { id: 'x' }, { tab: 'notes' }) → "#/read/x?tab=notes". */
export function href(id, params = {}, query = {}) {
  const route = byId(id);
  if (!route) throw new Error(`Unknown route: ${id}`);
  const path = route.path.replace(/:(\w+)/g, (match, name) => {
    if (params[name] == null || params[name] === '') throw new Error(`Route ${id} needs ${name}`);
    return encodeURIComponent(params[name]);
  });
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) if (value != null && value !== '') search.set(key, value);
  const qs = search.toString();
  return `#/${path}${qs ? `?${qs}` : ''}`;
}
