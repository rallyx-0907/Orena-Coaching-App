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

/* --- The shell's destinations (D-059, Design Contract rule 38) ---

   Five destinations and a Practice group replace the eleven-link rail, and a
   phone reaches them through a tab bar plus one control that opens the whole
   map as a sheet. The reshape must not cost a single way in: every earlier
   destination's href is still in the map, and these hold the parts that would
   silently undo that. */
const {
  navigationToggle,
  navigationTabs,
  referenceNavigation,
  navigationCurrent,
  topBar,
} = await import('../static/orena/ui/reference.js');
const { practiceOverview, discoverySpread } = await import('../static/orena/ui/discovery.js');
const shellCtx = (ui, location, extra = {}) => ({
  ui,
  location,
  memory: { value: { continuation: [] } },
  ...extra,
});

for (const ui of ['en', 'zh', 'vi']) {
  const c = referenceCopy[ui];
  for (const key of ['home', 'library', 'vocabulary', 'progress', 'you', 'dictation', 'allDestinations', 'practiceNavigation'])
    assert.ok(c[key], `${ui}: the shell needs "${key}"`);
  const nav = referenceNavigation(shellCtx(ui, route('#/')));
  assert.match(nav, /id="shellNav"/, 'the control has something to point at');
  /* D-060: the rail is exactly the approved one - four destinations, the
     Practice heading, five practice rooms. */
  const railHrefs = [...nav.matchAll(/<a class="nav-(?:link|heading)[^"]*" (?:id="navPractice" )?href="([^"]+)"/g)].map((m) => m[1]);
  assert.deepEqual(railHrefs, [
    link(), link('content'), link('language'), link('progress'),
    link('practice'),
    link('practice', { intent: 'reading' }), link('practice', { intent: 'follow' }),
    link('practice', { intent: 'speaking' }), link('practice', { intent: 'dictation' }), link('expression'),
  ], `${ui}: the approved rail`);
  assert.equal((nav.match(/aria-current="page"/g) || []).length, 1, 'exactly one is current');
  // A practice room's icon wears its domain hue; the row stays neutral.
  assert.match(nav, /class="nav-link nav-link--practice" href="[^"]+" data-nav="reading" data-domain="reading"/);
  /* Nothing that existed is lost: every earlier destination is still reached
     from its named home - the rail, the top bar, the practice map, or Home. */
  const threeThreads = { value: { continuation: ['a', 'b', 'c'].map((x) => ({ id: `story:${x}`, title: x, intent: 'reading' })), expressions: {}, conversations: {} } };
  const reachable = [
    nav,
    topBar({ ui, language: 'en', support: 'vi', location: route('#/') }),
    practiceOverview({ c: copy[ui === 'vi' ? 'vi' : ui] || copy.en, ui }),
    discoverySpread({ c: copy[ui] || copy.en, ui, language: 'en', support: 'vi', memory: threeThreads }, {}),
  ].join('');
  for (const entry of entryPoints(ui))
    assert.ok(reachable.includes(`href="${entry.href}"`), `${ui}: ${entry.id} is no longer reachable`);

  const toggle = navigationToggle(shellCtx(ui, route('#/')));
  assert.match(toggle, /aria-expanded="false"/, 'it reports its own state');
  assert.match(toggle, /aria-controls="shellNav"/, 'it names what it opens');
  assert.ok(toggle.includes(`aria-label="${c.allDestinations}"`), 'an icon-only control is named');

  // The tab bar: four places and the learner's own, the way back lit.
  const tabs = navigationTabs(shellCtx(ui, route('#/')));
  assert.equal((tabs.match(/class="shell-tab"/g) || []).length, 5, `${ui}: five tabs`);
  assert.match(tabs, /<button class="shell-tab" type="button" data-preference>/, 'You opens the profile sheet');
  for (const [hash, tab] of [
    ['#/', '#/'],
    ['#/practice?intent=reading', '#/content'],
    ['#/encounter?id=media:test', '#/content'],
    ['#/practice?intent=recall', '#/language'],
    ['#/progress', '#/progress'],
    ['#/expression', '#/'],
  ]) {
    const lit = navigationTabs(shellCtx(ui, route(hash)));
    assert.ok(lit.includes(`href="${tab}" aria-current="page"`), `${ui} ${hash}: the ${tab} tab leads back`);
    assert.equal((lit.match(/aria-current="page"/g) || []).length, 1, `${ui} ${hash}: one tab is current`);
  }
}
// Rail, tab bar and room agree about where the learner is.
assert.equal(navigationCurrent(route('#/encounter?id=media:x&intent=dictation')), 'dictation');
assert.equal(navigationCurrent(route('#/encounter?id=media:x&intent=shadowing')), 'listening');
assert.equal(navigationCurrent(route('#/practice')), 'practice');
assert.equal(experienceFor(route('#/progress')), 'progress');

const shellCss = readFileSync(new URL('../static/orena/shell.css', import.meta.url), 'utf8');
// The phone-only parts do not exist on a desk.
assert.match(shellCss, /\.shell-bar,\n\.shell-tabs,\n\.nav-backdrop \{\n  display: none;/);
const phoneNav = shellCss.slice(shellCss.indexOf('@media (max-width: 900px)'));
/* The map is a sheet over the room, not a wedge above it, and closed it is
   out of the tab order and the accessibility tree. */
assert.match(phoneNav, /#shellNav \{[^}]*position: fixed/, 'the sheet must overlay, not displace');
assert.match(phoneNav, /#shellNav \{[^}]*visibility: hidden/, 'closed means unreachable, not just invisible');
assert.match(phoneNav, /#shell\[data-menu='open'\] #shellNav \{[^}]*visibility: visible/, 'it opens on the shell state');
// Tapping the room behind it closes it; the curtain sits below the shell's
// own layer, or it would cover the sheet it opened.
assert.match(phoneNav, /\.nav-backdrop \{[^}]*z-index: var\(--z-sticky\)/);
assert.match(phoneNav, /#shell\[data-menu='open'\] ~ \.nav-backdrop \{\s*display: block;/);
assert.match(
  readFileSync(new URL('../static/orena/app.js', import.meta.url), 'utf8'),
  /backdrop\.onclick = \(\) => setMenu\(false\)/,
  'the backdrop must actually close it',
);
// A filter on the sticky bar would trap the fixed sheet and tab bar inside it.
assert.doesNotMatch(phoneNav.split('#shellNav {')[0], /^\s*(-webkit-)?backdrop-filter\s*:/m, 'the sticky bar carries no filter');
// Working, the tab bar steps aside so the learning has the height (rule 12).
assert.match(phoneNav, /#shell\[data-compact\] \.shell-tabs \{\s*transform: translateY\(100%\);/);
// Motion is a courtesy, not a requirement.
assert.match(phoneNav, /prefers-reduced-motion: reduce/, 'the animation can be turned off');
// Touch targets are not the thing that gives when space is short.
assert.match(phoneNav, /\.shell-tab \{[^}]*min-block-size: 48px/);

console.log('Golden Star: approved destinations, intact intent contract, local in-room navigation, row composition, phone-reachable destinations and room measures: PASS');
