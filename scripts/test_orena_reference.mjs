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
for (const [selector, measure] of [['.recall-moment', '760px'], ['.provenance', '800px']])
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

/* --- Reaching the eleven destinations on a phone ---

   The rail becomes a header below 900px, and the whole list used to be laid
   out across it: three groups wrapping onto three lines, each line wider than
   the screen. That cost 228px of an 844px phone and left Listening, Patterns &
   meaning and Recall off the right edge, where nothing could reach them.

   The list now sits behind one control that names where the learner is. These
   hold the parts that would silently undo it. */
const { navigationToggle, referenceNavigation } = await import('../static/orena/ui/reference.js');
const shellCtx = (ui, location) => ({ ui, location, memory: { value: { continuation: [] } } });

for (const ui of ['en', 'zh']) {
  assert.ok(referenceCopy[ui].destinations, `${ui}: the control needs a name`);
  // Closed, it still answers "where am I" - that is why it is not a hamburger.
  for (const [hash, id] of [['#/', 'discover'], ['#/continue', 'continue'], ['#/language', 'language']]) {
    const toggle = navigationToggle(shellCtx(ui, route(hash)));
    const label = entryPoints(ui).find((x) => x.id === id).label;
    assert.ok(
      toggle.includes(`>${label}<`),
      `${ui} ${hash}: the control must name the destination the learner is in`,
    );
  }
  const toggle = navigationToggle(shellCtx(ui, route('#/')));
  assert.match(toggle, /aria-expanded="false"/, 'it reports its own state');
  assert.match(toggle, /aria-controls="shellNav"/, 'it names what it opens');
  assert.ok(
    toggle.includes(referenceCopy[ui].destinations),
    'the accessible name says it opens the destinations, not only where you are',
  );
  // Every approved destination is still in the list behind it.
  const nav = referenceNavigation(shellCtx(ui, route('#/')));
  assert.match(nav, /id="shellNav"/, 'the control has something to point at');
  for (const entry of entryPoints(ui))
    assert.ok(nav.includes(`href="${entry.href}"`), `${ui}: ${entry.id} left the list`);
  assert.equal((nav.match(/<a /g) || []).length, 11, `${ui}: all eleven destinations`);
  assert.equal((nav.match(/aria-current="page"/g) || []).length, 1, 'exactly one is current');
}

// Desktop is untouched: the control does not exist there, and the rail still
// shows every destination at once.
assert.match(
  referenceCss,
  /\.nav-toggle \{ display: none; \}/,
  'the rail must not render a menu control',
);
const phoneNav = referenceCss.slice(referenceCss.indexOf('@media(max-width:900px)'));
/* The sheet is a curtain over the room, not a wedge above it. Living in the
   header's grid meant opening it pushed everything below down and closing it
   pulled it back - the page reflowed twice for a menu. */
assert.match(phoneNav, /#shell nav \{[^}]*position:absolute/, 'the sheet must overlay, not displace');
assert.match(phoneNav, /#shell nav \{[^}]*top:100%/, 'it hangs off the header');
/* Closed it must be out of the tab order and the accessibility tree, or eleven
   links stay reachable behind a shut menu. `visibility:hidden` does that and
   still animates; `opacity:0` alone would not. */
assert.match(phoneNav, /#shell nav \{[^}]*visibility:hidden/, 'closed means unreachable, not just invisible');
assert.match(
  phoneNav,
  /#shell\[data-menu='open'\] nav \{[^}]*visibility:visible/,
  'and opens on the shell state the control sets',
);
// Tapping the room behind it closes it, which is the gesture people try first.
assert.match(phoneNav, /\.nav-backdrop \{/, 'there is something to tap outside');
assert.match(phoneNav, /#shell\[data-menu='open'\] ~ \.nav-backdrop \{ display:block; \}/);
assert.match(
  readFileSync(new URL('../static/orena/app.js', import.meta.url), 'utf8'),
  /backdrop\.onclick = \(\) => setMenu\(false\)/,
  'the backdrop must actually close it',
);
// Motion is a courtesy, not a requirement.
assert.match(phoneNav, /prefers-reduced-motion: reduce/, 'the animation can be turned off');
// The group headings come back in the sheet; the flattened strip had dropped
// them, so eleven destinations arrived as one undifferentiated run.
assert.match(phoneNav, /\.nav-group > small \{ display:block; \}/);
assert.match(phoneNav, /\.nav-group \{ flex-direction:column;/);
// Touch targets are not the thing that gives when space is short.
assert.match(phoneNav, /\.nav-toggle \{[^}]*min-height:46px/);
assert.doesNotMatch(phoneNav, /#shell nav a \{[^}]*font-size:1[0-2]px/);

console.log('Golden Star: approved destinations, intact intent contract, local in-room navigation, row composition, phone-reachable destinations and room measures: PASS');
