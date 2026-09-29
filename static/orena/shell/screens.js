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
  orena: () => import('../screens/orena/screen.js'),
  progress: () => import('../screens/progress/screen.js'),
  collection: () => import('../screens/collection/screen.js'),
  grammar: () => import('../screens/grammar/screen.js'),
  'grammar-concept': () => import('../screens/grammar-concept/screen.js'),
  search: () => import('../screens/search/screen.js'),
  practice: () => import('../screens/practice/screen.js'),
  settings: () => import('../screens/settings/screen.js'),
  review: () => import('../screens/review/screen.js'),
  feed: () => import('../screens/feed/screen.js'),
  errors: () => import('../screens/errors/screen.js'),
  listening: () => import('../screens/listening/screen.js'),
  dictation: () => import('../screens/dictation/screen.js'),
  shadowing: () => import('../screens/shadowing/screen.js'),
  onboarding: () => import('../screens/onboarding/screen.js'),
  writing: () => import('../screens/writing/screen.js'),
  'writing-compare': () => import('../screens/writing-compare/screen.js'),
  // rewrite ('rewrite', #/rewrite) and timed-writing ('timed-writing', #/timed-writing) are
  // deliberately NOT registered: no real backend exists for either (no content endpoint for a
  // fixed core-message + register-context rewrite drill, no timed-prompt bank, no AI grading of
  // "communication worked"/"register fit" - the old UI's versions used only client-side regex
  // heuristics, never a server contract; checked `infrastructure/api.js` and `app.py` in full).
  // Per the Wave B brief ("Context Rewrite / Timed Writing: real backends only, else Coming
  // soon"), their routes fall through to this file's own documented fallback above and render
  // the design's Coming soon screen, titled from their own `crumb` (shell/routes.js:
  // 'contextRewrite' / 'timedWriting', both already real shellCopy keys). See
  // SCRATCH/reports/write.md.
  speak: () => import('../screens/speak/screen.js'),
  compare: () => import('../screens/compare/screen.js'),
  attempts: () => import('../screens/attempts/screen.js'),
  'speak-summary': () => import('../screens/speak-summary/screen.js'),
  reader: () => import('../screens/reader/screen.js'),
  'reader-complete': () => import('../screens/reader-complete/screen.js'),
  react: () => import('../screens/react/screen.js'),
  respond: () => import('../screens/respond/screen.js'),
  'free-talk': () => import('../screens/free-talk/screen.js'),
  conversation: () => import('../screens/conversation/screen.js'),
  situation: () => import('../screens/situation/screen.js'),
  // retell ('retell/:id'), timed-reaction ('timedreact'), interview ('mock') and sounds ('sound')
  // are deliberately NOT registered here, the same documented-omission pattern as rewrite/
  // timed-writing above: no real backend exists for any of the four. The Speaking catalogue
  // (`writing_coach/speaking_library.py`, PRACTICE_TYPES "retell"/"sounds"/"interview") ships
  // empty by product decision (UI_BACKEND_GAPS SP-1) and, even authored, its schema carries only
  // {line_id, text, reading, translations} - no key-point checkpoints for Retell's real coverage
  // scoring, no interview-question bank, no minimal-/tone-pair dataset, no timed-prompt bank; the
  // frames' own RETELL_POINTS/MOCK_Q/TRE/PAIRS are prototype-only fixtures, not content this build
  // can read for real (see SCRATCH/reports/speak-more.md). Their routes fall through to this
  // file's own documented fallback above and render the design's Coming soon screen, titled from
  // their own `crumb` (shell/routes.js: 'retell' / 'timedReaction' / 'mockInterview' / 'soundTone',
  // already real shellCopy keys).
});
