/* The screens of the new learner UI that are built, by the folder name a route names in
   shell/routes.js (`screen`). A route whose screen is not listed here renders the design's Coming
   soon screen. Each loader is a dynamic import so a learner downloads a room only when they enter
   it; scripts/validate_browser_esm_graph.mjs walks every screen listed here. */
export const SCREENS = Object.freeze({
  coming: () => import('../screens/coming/screen.js'),
  today: () => import('../screens/today/screen.js'),
  word: () => import('../screens/word/screen.js'),
  library: () => import('../screens/library/screen.js'),
  profile: () => import('../screens/profile/screen.js'),
  content: () => import('../screens/content/screen.js'),
  check: () => import('../screens/check/screen.js'),
  discussion: () => import('../screens/discussion/screen.js'),
  'reading-transfer': () => import('../screens/reading-transfer/screen.js'),
  discover: () => import('../screens/discover/screen.js'),
  progress: () => import('../screens/progress/screen.js'),
  collection: () => import('../screens/collection/screen.js'),
  grammar: () => import('../screens/grammar/screen.js'),
  'grammar-concept': () => import('../screens/grammar-concept/screen.js'),
  search: () => import('../screens/search/screen.js'),
  practice: () => import('../screens/practice/screen.js'),
  settings: () => import('../screens/settings/screen.js'),
});
