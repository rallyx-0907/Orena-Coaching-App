/* Practice Hub / Skill Hub (routes 'practice', 'skillhub' - shell/routes.js) - pure, DOM-free data
   mapping, so scripts/test_orena_screen_practice.mjs can prove it without a browser.

   The pinned design (08-Practice-Hub.html, 09-Skill-Hub.html; S1 orena-script.js:599 `SK`) groups
   practice around six skills (Speak, Write, Listen, Vocabulary, Grammar, Reading), each with a
   short list of named modes. Design Contract rule 40: a mode this build cannot open for real - no
   route, or a route that needs a content id nothing here can supply - is left out, never invented
   with a placeholder id or a fabricated "coming soon" dimming.

   Corrected per the surface review (docs/project/UI_BACKEND_GAPS.md N-22): Listen and Reading DO
   each have one mode reachable without inventing a content id - `GET /api/listening/library`
   (`listenModes`) and `GET /api/reading/practice/next` (`readingModes`), the exact same real,
   already-consumed-elsewhere-in-this-tree endpoints `screens/today/screen.js` already calls. A
   skill's section renders only when its builder actually returns at least one mode (data-driven,
   `buildSkillSections`), never a hardcoded list of which skills "have" content - if the Listening
   library or the Reading queue is temporarily empty, that skill's section simply does not render
   that visit, the same way the design's own Continue section disappears when it is empty. */
import { isDeferred } from '../../shell/routes.js';
import { speakingResumeTarget } from '../../product/speaking-resume.js';

/* Every mode maps to a real shell/routes.js entry; its label is that route's own crumb, already
   translated in copy/shell.js (shellCopy) - this file only decides *which* routes belong to which
   skill and *whether* a content-needing mode has a real id to open. */

/* All six skills the design draws, in the human's order (2026-10-09, D-152: Listen, Speak, Read, Write,
   Vocabulary, Grammar on desktop and phone; the design's `SK` order was Speak, Write, Listen, Vocabulary,
   Grammar, Reading). Whether a given skill's *section* actually renders on Practice Hub is decided by
   `buildSkillSections` from real data, not by this list - this is the full vocabulary of known
   skills (used by Skill Hub to tell "a real skill with nothing to show right now" from "not a
   skill at all"), not a pre-filtered subset. */
export const SKILL_ORDER = ['listen', 'speak', 'reading', 'write', 'vocabulary', 'grammar'];

const SPEAK_ICONS = {
  freetalk: 'mic',
  conv: 'messages-square',
  situation: 'rotate-ccw',
  timedreact: 'timer',
  mock: 'square-check-big',
  sound: 'audio-lines',
  speak: 'audio-lines',
  shadow: 'repeat',
  retell: 'rotate-ccw',
};
/* The design's PH_MAP: "Continue draft" and "Prompt" are `pen` (Lucide pen-line), "Free Writing" and "Your
   Topic" are `note` (Lucide notebook-pen). */
const WRITE_ICONS = { continue: 'pen-line', prompt: 'pen-line', free: 'notebook-pen', topic: 'notebook-pen', earlier: 'history' };
/* 'keyboard' (design PH_MAP "Dictation":"kbd") and 'repeat' (design PH_MAP "Shadowing":"repeat",
   the same icon Speak's own Shadowing mode already uses) - both already present in kit/icons.js,
   no sync needed. */
const LISTEN_ICONS = { dictation: 'keyboard', listening: 'headphones', react: 'arrow-left-right' };
/* The design's PH_MAP: Due review is `cards` (Lucide panels-top-left), Collections `lib` (Lucide library-big), Timed
   Recall `zap`, Context Transfer `target`. The design gives Daily Feed `cards` and Saved language `lib` as well, so two
   tiles of one group read as the same place; Daily Feed (flame) and Saved language (bookmark) have their own Lucide
   icons here (LEX-071, a deviation recorded for the human). */
const VOCAB_ICONS = { review: 'panels-top-left', timed: 'zap', transfer: 'target', feed: 'flame', collections: 'library-big', language: 'bookmark' };
const GRAMMAR_ICONS = { grammarlib: 'book-open' };
/* 'book-open' (design PH_MAP "Start Reading Practice":"book" - the same path as Lucide's
   book-open, already reused by Grammar library above). */
const READING_ICONS = { reader: 'book-open' };

export const SKILL_ICONS = {
  speak: SPEAK_ICONS,
  write: WRITE_ICONS,
  listen: LISTEN_ICONS,
  vocabulary: VOCAB_ICONS,
  grammar: GRAMMAR_ICONS,
  reading: READING_ICONS,
};

/* The design tints every skill's icon swatches with that skill's own hue (08-Practice-Hub.html
   `ps.tint`/`pi.iconStyle`, 09-Skill-Hub.html's group modes render iconless so this only reaches
   Practice Hub's tiles and the Continue row) - never a single flat accent (Design Contract rule
   32, "skill hue belongs to artwork, icons and small markers"). The six hues already live in
   kit/tokens.css as theme-independent `--skill-*` tokens for exactly this job (today/model.js,
   grammar/grammar.css and progress/screen.js already read them the same way) - reused here, never
   redefined. Vocabulary's own token is `--skill-vocab`, matching the design's Vocabulary/#F2B705
   pairing. */
export const SKILL_TINT = {
  speak: 'var(--skill-speak)',
  write: 'var(--skill-write)',
  listen: 'var(--skill-listen)',
  vocabulary: 'var(--skill-vocab)',
  grammar: 'var(--skill-grammar)',
  reading: 'var(--skill-read)',
};

/* One Speaking library item (GET /api/speaking/library) of a given practice_type, or null. The
   first match is taken in whatever order the backend returned - no ranking is invented. `clip`
   items carry a `media:<lessonId>` id (speaking_library.py's own format, the same one
   ui/speaking.js already decodes) - the shadow route needs the bare lesson id. */
function firstOfType(items, type) {
  return items.find((item) => item && item.practice_type === type) || null;
}

/* Generic Pronunciation opens the shared content chooser, including personal imports;
   it never silently assigns the first catalogue item. Deferred modes remain excluded. */
/* The design's own order and groups for Speak (S1 `SK.Speak.groups`): Situation Reaction,
   Conversation, Free Talk under "Speak naturally"; Pronunciation, Shadowing, Sound / Tone under
   "Improve pronunciation"; Timed Reaction, Retell, Mock Interview under "Challenge yourself". Only
   the modes this build offers are drawn (D-101 H9); a group with none is simply absent. */
export const SPEAK_GROUPS = ['natural', 'pronounce', 'challenge'];

export function speakModes(items = []) {
  const list = Array.isArray(items) ? items : [];
  const modes = [
    { key: 'situation', group: 'natural', routeId: 'situation' },
    { key: 'conv', group: 'natural', routeId: 'conv' },
    { key: 'freetalk', group: 'natural', routeId: 'freetalk' },
    /* Pronunciation opens the source chooser first, always (human, 2026-10-08, D-149, superseding D-139 HD-3): the
       learner picks what to practise before any attempt. */
    { key: 'speak', group: 'pronounce', labelRouteId: 'speak', routeId: 'discover', query: { tab: 'listen', practice: 'pronunciation' } },
    /* Shadowing opens the shared room (D-119) through the media chooser: its route needs a media id, which only
       the learner's choice supplies (D-139 HD-2). */
    { key: 'shadow', group: 'pronounce', labelRouteId: 'shadow', routeId: 'discover', query: { tab: 'listen', practice: 'shadowing' } },
    { key: 'sound', group: 'pronounce', routeId: 'sound' },
    { key: 'timedreact', group: 'challenge', routeId: 'timedreact' },
  ];
  const retell = firstOfType(list, 'retell');
  if (retell) modes.push({ key: 'retell', group: 'challenge', routeId: 'retell', params: { id: retell.id }, level: retell.level || '' });
  modes.push({ key: 'mock', group: 'challenge', routeId: 'mock' });
  return shown(modes);
}

/* D-101 H9: a mode whose route is deferred is not offered. */
function shown(modes) {
  return modes.filter((mode) => !isDeferred(mode.routeId));
}

/* The design's own groups for Write (S1 `SK.Write.groups`): Continue draft, Prompt, Free Writing and Your
   Topic under "Write freely"; Respond to Content and Context Rewrite under "Respond"; Timed Writing under
   "Under pressure". Only what this build can open for real is drawn (D-101 H9, HW-1 B): Context Rewrite and
   Timed Writing are not built; Respond to Content needs a content id nothing here supplies (W-17,
   UI_BACKEND_GAPS). So only "Write freely" is present. Prompt and Your Topic open the room with Prompt
   Setup already open (HW-2 B); Free Writing opens the room named "Free writing". Continue draft is listed
   only while a draft is waiting. `draft` is { title, n } for it. */
export const WRITE_GROUPS = ['free', 'respond', 'pressure'];

export function writeModes(draft = null, earlier = 0) {
  const modes = [];
  if (draft && draft.n > 0) modes.push({ key: 'continue', group: 'free', routeId: 'writing', draft });
  modes.push(
    { key: 'prompt', group: 'free', routeId: 'writing', query: { setup: 'prompt' } },
    { key: 'free', group: 'free', routeId: 'writing', query: { entry: 'free' } },
    { key: 'topic', group: 'free', routeId: 'writing', query: { setup: 'topic' } },
  );
  // The drafts "Start new draft" set aside stay reachable (LEX-062): one row opens their list.
  if (earlier > 0) modes.push({ key: 'earlier', group: 'free', routeId: 'writing', action: 'earlier', count: earlier });
  return shown(modes);
}


/* Human correction: listening comprehension and dictation are separate choices,
   both choose content before practice. Speaking owns the single pronunciation /
   shadowing entry. Only lessons with materialized questions admit comprehension. */
export function listenModes(items = [], last = null) {
  const list = Array.isArray(items) ? items : [];
  const modes = [];
  if (list.some(item => item?.comprehension_count > 0)) modes.push({ key: 'listening', labelRouteId: 'listenQuestions', routeId: 'discover', query: { tab: 'listen', practice: 'listening' } });
  // Personal prepared imports also support dictation; the chooser owns admission.
  modes.push({ key: 'dictation', labelRouteId: 'dictation', routeId: 'discover', query: { tab: 'listen', practice: 'dictation' } });
  /* React / Reuse opens the learner's last listened line (X-01, HX-1 A; the Pronunciation pattern, D-139 HD-3). With
     no such line the tile is not drawn: its route needs a media id and a line only the learner's own history supplies. */
  if (last?.params?.id) modes.push({ key: 'react', routeId: 'react', params: last.params, query: last.query });
  return modes;
}

/* Reading's one mode reachable without an invented id: Start Reading Practice, gated on
   GET /api/reading/practice/next's own `available` flag (reading_practice_api.py) - literally
   "the next reading item for a learner, generically", already consumed the same way by
   screens/today/screen.js's buildRecommendationPool (`reading.next.set.article`,
   `reading.next.recommendation`). `available: false` (no article published in this environment
   right now) is a real, honest empty, not a missing endpoint - the mode list is simply empty, the
   same shape as Listen when the library has no matching item. The design's other Reading modes -
   Paraphrase/Inference/Context Shift (its own "Transfer" group) and "Continue reading" (its own
   "Continue" group, device-memory, already covered by continuationRows()) - have no comparable id
   source and stay out (rule 40). */
export function readingModes(reading) {
  const article = reading && reading.available ? reading.next?.set?.article : null;
  if (!article?.id) return [];
  const mode = { key: 'reader', routeId: 'reader', params: { id: article.id }, level: article.level || '' };
  if (reading.next?.recommendation) mode.query = { rec: reading.next.recommendation };
  return [mode];
}

/* The design's groups for Vocabulary (S1 `SK.Vocabulary.groups`): Due Review and Timed Recall under "Recall",
   Context Transfer under "Use", Daily Feed, Collections and Saved language under "Browse". Only what this build
   opens for real is drawn (D-101 H9, HV-1 B): Timed Recall and Context Transfer are deferred, so only Recall (Due
   Review) and Browse are present. Due Review carries the learner's real due count (context().due, rule 40: 0 is a
   real answer, not an absence). Collections and Saved language are My Library's own tabs (`?tab=`). */
export const VOCABULARY_GROUPS = ['recall', 'use', 'browse'];

export function vocabularyModes(due = 0) {
  const n = Number.isFinite(Number(due)) ? Math.max(0, Number(due)) : 0;
  return shown([
    { key: 'review', group: 'recall', routeId: 'review', due: n },
    { key: 'timed', group: 'recall', routeId: 'timed' },
    { key: 'transfer', group: 'use', routeId: 'transfer' },
    { key: 'feed', group: 'browse', routeId: 'feed' },
    { key: 'collections', group: 'browse', routeId: 'library', query: { tab: 'collections' } },
    { key: 'language', group: 'browse', routeId: 'library', query: { tab: 'language' } },
  ]);
}

/* Skill Hub Vocabulary's Recommended card, only from real data: the due count. Nothing is due, nothing is
   recommended (HV-1 B). */
export function vocabularyRecommendation(due = 0) {
  const n = Number.isFinite(Number(due)) ? Math.max(0, Math.trunc(Number(due))) : 0;
  return n > 0 ? { n } : null;
}

export const SKILL_GROUPS = { speak: SPEAK_GROUPS, write: WRITE_GROUPS, vocabulary: VOCABULARY_GROUPS };

/* Grammar library is the one entry point this round wires for real; a "next concept"/"quick quiz"
   tile would need a recommended-lesson id nothing here derives without inventing a selection. */
export function grammarModes() {
  return [{ key: 'grammarlib', routeId: 'grammarlib' }];
}

export const SKILL_BUILDERS = {
  speak: (data) => speakModes(data.speakingItems),
  write: (data) => writeModes(data.draft, data.earlier),
  listen: (data) => listenModes(data.listeningItems, data.lastListenedLine),
  vocabulary: (data) => vocabularyModes(data.due),
  grammar: () => grammarModes(),
  reading: (data) => readingModes(data.reading),
};

/* Practice Hub's sections, data-driven: a skill's section appears only when its builder actually
   returned at least one real, addressable mode this visit - never a hardcoded subset of
   SKILL_ORDER. Speak/Write/Vocabulary/Grammar always have at least one fixed, parameterless mode,
   so they always render; Listen/Reading render only when their real catalogue/queue actually has
   something to open right now. */
export function buildSkillSections(data = {}) {
  return SKILL_ORDER
    .map((skill) => ({ skill, modes: SKILL_BUILDERS[skill](data) }))
    .filter((section) => section.modes.length > 0);
}

/* Device memory's continuation entries (product/memory.js `continuation[]`) mapped to a route this
   build can actually resume, by the same id-prefix vocabulary product/intent.js already uses for
   the old UI's own routing (continuationExperience) - reused here only to classify, never to build
   an old-UI href. An entry whose prefix/intent has no confirmed id-contract with an unbuilt new-UI
   screen (a spoken conversation, an imported/url:/upload: media item, a plain reading id) is left
   out rather than guessed at (rule 40) - it is still there next time the learner opens the room
   that owns it, just not resumable from this hub. */
export function continuationTarget(item) {
  const speaking = speakingResumeTarget(item);
  if (speaking) return speaking;
  const id = String(item?.id || '');
  const intent = item?.intent || null;
  if (/^essay:\d+$/.test(id)) return { kind: 'write', routeId: 'writingDraft', params: { id } };
  if (/^(article|book|text):.+/.test(id)) return { kind: 'reading', routeId: 'reader', params: { id } };
  if (/^(expression|essay):/.test(id) || intent === 'writing') {
    return { kind: 'write', routeId: 'writing' };
  }
  if (id.startsWith('grammar:')) {
    const gid = id.slice('grammar:'.length);
    if (!gid) return null;
    return { kind: 'grammar', routeId: 'gconcept', params: { id: gid } };
  }
  // A conversation the learner left (kept with the account when the deployment keeps work there,
  // D4 I6): the Conversation room opens it by id and carries on where it stopped.
  if (/^conversation:[\w-]+$/.test(id)) {
    return { kind: 'speak', routeId: 'conv', query: { id } };
  }
  if (id.startsWith('media:')) {
    const mediaId = id.slice('media:'.length);
    if (!mediaId) return null;
    if (intent === 'dictation') return { kind: 'listen', routeId: 'dictation', params: { id: mediaId } };
    if (intent === 'shadowing') return { kind: 'listen', routeId: 'shadow', params: { id: mediaId } };
    return { kind: 'listen', routeId: 'listening', params: { id: mediaId } };
  }
  return null;
}

const KIND_ICON = { write: 'pen-line', listen: 'headphones', grammar: 'languages', speak: 'mic', reading: 'book-open' };
/* Reuses SKILL_TINT's own per-skill hues (now that SKILL_TINT carries a `listen` entry too) -
   never a second literal for the same token. */
const KIND_TINT = { write: SKILL_TINT.write, listen: SKILL_TINT.listen, grammar: SKILL_TINT.grammar, speak: SKILL_TINT.speak, reading: SKILL_TINT.reading };

/* Up to `limit` continuation rows (most-recent-first, memory.js's own order), each carrying enough
   to draw a row and to link to a real route. `place` (product/memory.js readPlace) is the only
   real progress figure a continuation entry can carry; a row with none shows no progress text
   rather than an invented "time left". */
export function continuationRows(continuation = [], { limit = 5 } = {}) {
  const list = Array.isArray(continuation) ? continuation : [];
  const rows = [];
  for (const item of list) {
    const target = continuationTarget(item);
    if (!target) continue;
    rows.push({
      id: String(item.id || ''),
      title: String(item.title || ''),
      kind: target.kind,
      icon: KIND_ICON[target.kind] || 'target',
      tint: KIND_TINT[target.kind] || 'var(--accent-fill)',
      routeId: target.routeId,
      params: target.params,
      query: target.query,
      place: item.place || null,
      context: String(item.context || ''),
    });
    if (rows.length >= limit) break;
  }
  return rows;
}

/* GET /api/practice-recommendation (becoming_practice.py build_practice_recommendation) - Writing's
   own recommender; the only skill with one. No duration is ever returned, so the eyebrow never
   grows a fabricated "~N min". */
export function writeRecommendation(rec) {
  if (!rec || typeof rec !== 'object') return null;
  const title = String(rec.focus_label || '').trim();
  if (!title) return null;
  return { title, reason: String(rec.reason || '').trim(), actionLabel: String(rec.action_label || '').trim() };
}

/* Skill Hub Speak's Recommended card (D-139 HD-1): the line the learner's real attempts say is weakest.
   `rows` are the account's speaking attempts (`product/speaking-history.js#attemptRow`); only a VERIFIED score counts
   (an unverified attempt has no score to be weak by). Each line is judged by its LATEST verified attempt, so a line
   the learner has since improved is not recommended again. Returns up to `limit` candidates, weakest first, each with
   the real evidence for its reason line: the line's score and its lowest-scoring word, when the account kept words.
   No attempts, no candidate (no card). */
export function weakestLines(rows = [], limit = 3) {
  const latest = new Map();
  for (const row of Array.isArray(rows) ? rows : []) {
    if (!row?.verified || row.overall == null || !row.assetId || !row.segmentId) continue;
    const key = `${row.assetId}\u0000${row.segmentId}`;
    if (!latest.has(key) || (row.at || 0) >= (latest.get(key).at || 0)) latest.set(key, row);
  }
  return [...latest.values()]
    .sort((a, b) => a.overall - b.overall || (b.at || 0) - (a.at || 0))
    .slice(0, limit)
    .map((row) => {
      const words = (row.evidence?.words || []).filter((word) => word.score != null && word.text);
      const weakest = words.reduce((low, word) => (low && low.score <= word.score ? low : word), null);
      return { assetId: row.assetId, segmentId: row.segmentId, overall: row.overall, word: weakest ? { text: weakest.text, score: weakest.score } : null };
    });
}
