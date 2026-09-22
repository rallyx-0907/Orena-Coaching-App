import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { route, link, continuationLink, practiceIntentions } from '../static/orena/product/intent.js';
import { copy } from '../static/orena/ui/copy.js';

assert.equal(route(link('continue')).page, 'continue', 'Continue must have its own reachable experience');
const { experienceFor, entryPoints, referenceCopy, renderContinue } = await import('../static/orena/ui/reference.js');
for (const ui of ['en', 'zh']) {
  const entries = entryPoints(ui);
  assert.equal(new Set(entries.map(x => x.id)).size, entries.length);
  for (const entry of entries) {
    assert.ok(entry.label && entry.href);
    assert.equal(experienceFor(route(entry.href)), entry.id, `entry ${entry.id} must orient the learner correctly`);
  }
  assert.ok(referenceCopy[ui].continueEmpty);
}
assert.equal(experienceFor(route('#/encounter?id=story:test')), 'reading');
assert.equal(experienceFor(route('#/encounter?id=media:test')), 'listening');
assert.equal(experienceFor(route('#/encounter?id=media:test&intent=dictation')), 'practice');
assert.equal(route(continuationLink({id:'conversation:test',intent:'speaking'})).page, 'conversation');
assert.equal(experienceFor(route('#/conversation?id=conversation:test')), 'speaking');
/* --- A row does not reserve space for content it does not have ---

   The pattern list lays each row out on a fixed four-track grid: level, name,
   example, arrow. Only a minority of patterns carry a separate example - the
   rest are named by the sentence itself - so the example track sat empty
   across most of the list while the names wrapped in half the width beside it.
   The rule below gives that space back to the name when there is no example,
   and this holds it. */
const worldCss = readFileSync(new URL('../static/orena/world.css', import.meta.url), 'utf8');
assert.match(
  worldCss,
  /\.pattern-list > a:not\(:has\(> p\)\) > h2 \{\s*grid-column: 2 \/ span 2;/,
  'a pattern with no example must give the reserved track back to its name',
);
// The shared four-track row itself stays: a pattern that does have an example
// still aligns with every other row that does.
assert.match(worldCss, /\.pattern-list > a \{\s*grid-template-columns: 65px/);
/* Narrow, the row already stacks and keeps no reserved track, so the span must
   be given back - otherwise the name spreads under the arrow. The reset has to
   live inside the narrow block, after the rule it undoes. */
const narrow = worldCss.slice(worldCss.indexOf('@media (max-width: 800px)'));
assert.match(
  narrow,
  /\.pattern-list > a:not\(:has\(> p\)\) > h2 \{\s*grid-column: 2;/,
  'the stacked row must not let a name without an example reach the arrow',
);

/* --- The shell's default measure does not silently swallow a room's own ---

   The reference shell centres every direct child of #main inside 1480px. It is
   an ID-specificity rule, so a room asking for a narrower measure at plain
   class specificity loses without any warning: one recalled sentence and the
   rights line under a passage were both being set across 1080px. A room that
   is narrower than the shell default has to say so at the shell's specificity,
   and these hold the two that do. */
const referenceCss = readFileSync(new URL('../static/orena/reference.css', import.meta.url), 'utf8');
const roomsCss = readFileSync(new URL('../static/orena/rooms.css', import.meta.url), 'utf8');
assert.match(
  referenceCss,
  /#main > \* \{[^}]*max-width: 1480px/,
  'the shell default this correction exists for is still here',
);
const flat = roomsCss.replace(/\s+/g, ' ');
for (const [selector, measure] of [['.review-session', '730px'], ['.provenance', '800px']])
  assert.ok(
    flat.includes(`#main > ${selector} { max-width: ${measure}; }`),
    `${selector} must restate its measure above the shell default`,
  );

/* --- The practice map lives in Practice, and nowhere else ---

   The defect was repetition, not richness: every individual room re-rendered
   the whole eight-mode map at its top, so a learner already inside Speaking was
   told again that Orena is eight skills to choose between. The map belongs to
   Practice, which the learner chose to enter. Inside a room, navigation is
   local - where you are, and the way back.

   The learner-facing destinations themselves are unchanged, and this gate
   holds them so a navigation fix cannot quietly become an IA change again. */
for (const ui of ['en', 'zh']) {
  const ids = entryPoints(ui).map((x) => x.id);
  assert.deepEqual(
    ids,
    ['discover', 'continue', 'reading', 'listening', 'practice', 'writing',
      'speaking', 'understanding', 'content', 'language', 'recall'],
    `${ui}: the approved learner-facing destinations must stand`,
  );
}

/* The engine contract is untouched. Every intent still routes, because saved
   continuations and kept-language provenance hold these hrefs. */
assert.deepEqual(
  practiceIntentions,
  ['follow', 'reading', 'dictation', 'shadowing', 'speaking', 'writing', 'grammar', 'recall'],
  'the practice-intent contract must survive any navigation change',
);
for (const intent of practiceIntentions)
  assert.equal(route(link('practice', { intent })).intent, intent, `${intent} must still resolve`);
for (const page of ['content', 'language', 'continue', 'expression', 'encounter', 'conversation', 'collection'])
  assert.equal(route(`#/${page}`).page, page, `${page} must still resolve`);

const continueRoot = { innerHTML: '' };
renderContinue(continueRoot, {
  ui: 'en',
  c: copy.en,
  language: 'en',
  memory: {
    available: true,
    value: {
      continuation: [
        { id: 'book:alice/ch-4', title: 'Chapter IV', intent: 'reading', context: "Alice's Adventures in Wonderland", place: { index: 4, total: 14 } },
        { id: 'media:two', title: 'A second thread', intent: 'follow' },
      ],
      conversations: {},
      expressions: {},
    },
  },
});
/* Continuity, not a list of unfinished rows: the most recent thread leads with
   its own artwork, what it belongs to, how far through it is, and one way back
   in. The rest stay compact beneath it. */
assert.match(continueRoot.innerHTML, /class="continue-lead"/,
  'the thread the learner was last in leads the room');
assert.equal((continueRoot.innerHTML.match(/<a class="primary"/g) || []).length, 1,
  'exactly one primary way back in');
assert.match(continueRoot.innerHTML, /Alice&#039;s Adventures in Wonderland/,
  'a chapter is shown as a chapter of its book');
assert.match(continueRoot.innerHTML, /4\/14/, 'the place inside the whole is printed');
assert.match(continueRoot.innerHTML, /class="continue-progress"/, 'progress reads at a glance');
assert.match(continueRoot.innerHTML, /width:29%/, 'progress is computed from the real place');
assert.match(continueRoot.innerHTML, /class="content-cover"/,
  'a resumed item is recognisable by its own artwork');
assert.equal((continueRoot.innerHTML.match(/class="continue-card"/g) || []).length, 1,
  'the remaining threads stay compact');
assert.doesNotMatch(continueRoot.innerHTML, /thread-action/,
  'resume cards do not repeat permanent arrows when the whole card is clickable');

/* A thread with no known place never prints an invented one. */
assert.equal((continueRoot.innerHTML.match(/class="continue-progress"/g) || []).length, 1,
  'progress appears only where the entry actually carries a place');

const emptyContinue = { innerHTML: '' };
renderContinue(emptyContinue, {
  ui: 'en',
  c: copy.en,
  language: 'en',
  memory: { available: true, value: { continuation: [], conversations: {}, expressions: {} } },
});
assert.match(emptyContinue.innerHTML, /class="continue-empty"/, 'an empty room says so');
assert.match(emptyContinue.innerHTML, /<a class="primary" href="#\/"/,
  'with nothing to resume, the way out is the way in');

const forgetful = { innerHTML: '' };
renderContinue(forgetful, {
  ui: 'en',
  c: copy.en,
  language: 'en',
  memory: { available: false, value: { continuation: [], conversations: {}, expressions: {} } },
});
assert.match(forgetful.innerHTML, /notice/, 'a device that cannot remember says so');

/* --- A room that fails stays in its own room ------------------------------
   The regression: a media route the product could not classify fell back to
   Reading, so a learner who asked to listen got the Reading rail highlight and
   a Reading error. The learner's intention decides when the id cannot. */
assert.equal(experienceFor({ page: 'encounter', id: '', intent: 'follow' }), 'listening');
assert.equal(experienceFor({ page: 'encounter', id: '', intent: 'reading' }), 'reading');
assert.equal(experienceFor({ page: 'encounter', id: '', intent: null }), 'reading');
assert.equal(experienceFor({ page: 'encounter', id: 'media:x', intent: null }), 'listening');
assert.equal(experienceFor({ page: 'encounter', id: 'story:x', intent: 'follow' }), 'reading',
  'content that is a text is Reading whatever the intent says');

/* The failure state itself: short, domain-aware, and never printing a
   developer's English sentence under a learner's heading. */
const appSource = readFileSync(new URL('../static/orena/app.js', import.meta.url), 'utf8');
const failure = appSource.slice(appSource.indexOf('const room = experienceFor(ctx.location)'), appSource.indexOf("root.querySelector('#retry').onclick"));
assert.match(failure, /class="room-failed"/, 'the failure state has its own compact composition');
assert.match(failure, /ctx\.c\.cantOpen/, 'it says what happened in one localized line');
assert.match(failure, /ctx\.c\.backTo/, 'and offers the way back to the room the learner was in');
assert.match(failure, /room === 'listening'[\s\S]{0,160}intent: 'follow'/, 'Listening goes back to Listening');
assert.match(failure, /room === 'reading'[\s\S]{0,160}intent: 'reading'/, 'Reading goes back to Reading');
assert.doesNotMatch(failure, /esc\(error\.message\)/,
  'a thrown message is a diagnostic, not learner-facing copy');
assert.doesNotMatch(failure, /ctx\.c\.unavailable/,
  'the old "part of your world" sentence is not the heading any more');
for (const ui of ['en', 'zh']) {
  for (const key of ['cantOpen', 'backTo']) {
    assert.equal(typeof copy[ui][key], 'string', `${ui}.${key} is localized`);
    assert.ok(copy[ui][key].trim(), `${ui}.${key} is not empty`);
  }
  assert.match(copy[ui].backTo, /\{room\}/, `${ui}.backTo names the room it returns to`);
}
assert.notEqual(copy.en.cantOpen, copy.zh.cantOpen);

/* Removing the repeated bar has to be a composition change. Hiding it in CSS
   would leave every room still rendering the whole map to assistive
   technology, which is the same defect wearing a different coat. */
for (const path of ['static/orena/ui/expression.js', 'static/orena/ui/speaking.js', 'static/orena/ui/world.js']) {
  const src = readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
  assert.ok(!/intentNavigation\(/.test(src), `${path} must not repeat the whole practice map`);
  assert.ok(/practiceReturn\(/.test(src), `${path} must offer the way back to Practice`);
}
// The primitive itself stays available for a surface that genuinely needs the
// whole map - Practice is one - so this is removal from rooms, not deletion.
assert.ok(
  /export function intentNavigation/.test(
    readFileSync(new URL('../static/orena/ui/patterns.js', import.meta.url), 'utf8'),
  ),
  'the full map primitive remains for surfaces that want it',
);

/* --- The shell's destinations: the baseline's (D-066, D-067; Design Contract rules 38, 45, 47) ---

   Five destinations (Home, Library, Vocabulary, Progress, Profile) and four skills under KỸ NĂNG
   (Reading, Listening, Speaking, Writing) on a desk; the same five as an 88px tab bar on a phone.
   Nothing else is in the chrome: no Practice group, no Dictation entry, no account card, no
   destination sheet. The rooms where the learner works have neither. */
const {
  navigationTabs,
  referenceNavigation,
  navigationCurrent,
  topBar,
} = await import('../static/orena/ui/reference.js');
const { practiceOverview } = await import('../static/orena/ui/discovery.js');
const { homeHtml } = await import('../static/orena/ui/home.js');
const shellCtx = (ui, location, extra = {}) => ({
  ui,
  location,
  memory: { value: { continuation: [] } },
  ...extra,
});

for (const ui of ['en', 'zh', 'vi']) {
  const c = referenceCopy[ui];
  for (const key of ['home', 'library', 'vocabulary', 'progress', 'profile', 'reading', 'listening', 'speaking', 'writing', 'navSkills', 'tabVocabulary'])
    assert.ok(c[key], `${ui}: the shell needs "${key}"`);
  const nav = referenceNavigation(shellCtx(ui, route('#/')));
  assert.match(nav, /id="shellNav"/, 'the nav has an id to point at');
  const railHrefs = [...nav.matchAll(/<a class="nav-link[^"]*" href="([^"]+)"/g)].map((m) => m[1]);
  assert.deepEqual(railHrefs, [
    link(), link('content'), link('language'), link('progress'),
    link('practice', { intent: 'reading' }), link('practice', { intent: 'follow' }),
    link('practice', { intent: 'speaking' }), link('writing'),
  ], `${ui}: the baseline's rail`);
  assert.match(nav, /<button type="button" class="nav-link" data-preference data-nav="profile">/, `${ui}: Profile opens the profile sheet`);
  assert.equal((nav.match(/nav-link--skill/g) || []).length, 4, `${ui}: four skills`);
  assert.equal((nav.match(/aria-current="page"/g) || []).length, 1, 'exactly one is current on Home');
  assert.doesNotMatch(nav, /navPractice|nav-link--practice|data-nav="dictation"|nav-toggle/, `${ui}: nothing the design does not draw`);
  /* The learner's card at the foot of the rail is what every desktop frame draws (AppShell), asked for by
     the human on 2026-09-22; it opens the profile sheet rather than being a sixth destination. */
  assert.match(nav, /<button type="button" class="account-card" data-preference>/, `${ui}: the rail ends in the learner's card`);
  assert.doesNotMatch(nav, /class="nav-level"/, `${ui}: a skill prints a level only when the profile carries one`);
  /* Nothing is lost: the rooms that left the chrome are reached from where the design puts them
     (Home, Library, a skill's library, the Listening deep sheet). Continue and Recall are Home's and
     Vocabulary's; the Practice map still exists for the surfaces that ask for it. */
  const threeThreads = { value: { continuation: ['a', 'b', 'c'].map((x) => ({ id: `story:${x}`, title: x, intent: 'reading' })), expressions: {}, conversations: {} } };
  const reachable = [
    nav,
    topBar({ ui, language: 'en', support: 'vi', location: route('#/') }),
    practiceOverview({ c: copy[ui === 'vi' ? 'vi' : ui] || copy.en, ui }),
    homeHtml({ c: copy[ui] || copy.en, ui, language: 'en', support: 'vi', memory: threeThreads }, {}),
  ].join('');
  // The Practice map (#/practice) is the one entry the design does not draw: it left the chrome with the
  // Practice group and is a legacy page awaiting deletion (UI_BACKEND_GAPS.md), so it is not required here.
  for (const entry of entryPoints(ui).filter((x) => x.id !== 'practice'))
    assert.ok(reachable.includes(`href="${entry.href}"`), `${ui}: ${entry.id} is no longer reachable`);

  // The tab bar: five tabs, the last the learner's own, the way back lit.
  const tabs = navigationTabs(shellCtx(ui, route('#/')));
  assert.equal((tabs.match(/class="shell-tab"/g) || []).length, 5, `${ui}: five tabs`);
  assert.match(tabs, /<a class="shell-tab" href="#\/profile"/, 'Profile is a destination, as the source draws it');
  for (const [hash, tab] of [
    ['#/', '#/'],
    ['#/practice?intent=reading', '#/content'],
    ['#/encounter?id=media:test', '#/content'],
    ['#/practice?intent=recall', '#/language'],
    ['#/progress', '#/progress'],
    ['#/expression', '#/content'],
  ]) {
    const lit = navigationTabs(shellCtx(ui, route(hash)));
    assert.ok(lit.includes(`href="${tab}" aria-current="page"`), `${ui} ${hash}: the ${tab} tab leads back`);
    assert.equal((lit.match(/aria-current="page"/g) || []).length, 1, `${ui} ${hash}: one tab is current`);
  }
}
// Rail, tab bar and room agree about where the learner is; Dictation is Listening.
assert.equal(navigationCurrent(route('#/encounter?id=media:x&intent=dictation')), 'listening');
assert.equal(navigationCurrent(route('#/encounter?id=media:x&intent=shadowing')), 'listening');
assert.equal(navigationCurrent(route('#/practice')), 'practice');
assert.equal(experienceFor(route('#/progress')), 'progress');
{
  // A skill's library lights both the Library destination and the skill, as the baseline's frames do.
  const listening = referenceNavigation(shellCtx('en', route('#/practice?intent=follow')));
  assert.match(listening, /href="#\/content" aria-current="page"/);
  assert.match(listening, /nav-link--skill" href="#\/practice\?intent=follow" aria-current="page"/);
}

const shellCss = readFileSync(new URL('../static/orena/shell.css', import.meta.url), 'utf8');
// The baseline's geometry: a 280px rail, an 88px phone bar, five tabs, no destination sheet.
assert.match(shellCss, /--rail-width: 280px;/);
assert.match(shellCss, /--tabbar-height: 88px;/);
assert.match(shellCss, /#shell \{[^}]*padding: 26px 18px;/, 'the rail is padded 26/18');
assert.match(shellCss, /\.nav-link \{[^}]*padding: 13px 16px;[^}]*border-radius: 14px;/s, 'rows of 13/16 at radius 14');
assert.match(shellCss, /\.nav-link--skill \{[^}]*padding: 11px 16px;[^}]*border-radius: 12px;/s, 'skills of 11/16 at radius 12');
assert.doesNotMatch(shellCss, /nav-backdrop|data-menu|shell-foot|nav-toggle/, 'no destination sheet');
assert.match(shellCss, /\.account-card \{[^}]*margin-block-start: auto;/s, "the learner's card sits at the foot of the rail, as the frames draw it");
assert.match(shellCss, /@media \(max-width: 900px\)[\s\S]*\.account-card \{\s*display: none;/s, 'and a phone keeps it in the Profile tab instead');
// The rooms where the learner works have neither the rail nor the tab bar.
assert.match(shellCss, /html\[data-shell='off'\] #shell \{\s*display: none;/);
assert.match(shellCss, /html\[data-shell='off'\] \.shell-tabs \{\s*display: none;/);
const appJs = readFileSync(new URL('../static/orena/app.js', import.meta.url), 'utf8');
assert.match(appJs, /document\.documentElement\.dataset\.shell = shellBelongsTo\(ctx\.location\)/);
assert.match(appJs, /WORKING_PAGES = new Set\(\['encounter', 'book', 'expression', 'conversation'\]\)/);
// A filter on the phone's shell would trap the fixed tab bar inside it.
const phoneNav = shellCss.slice(shellCss.indexOf('@media (max-width: 900px)'));
assert.match(phoneNav, /#shell \{[^}]*backdrop-filter: none;/, 'the phone shell carries no filter');
assert.match(phoneNav, /\.shell-tabs \{[^}]*position: fixed/);

console.log('Golden Star: approved destinations, intact intent contract, local in-room navigation, row composition, phone-reachable destinations and room measures: PASS');
