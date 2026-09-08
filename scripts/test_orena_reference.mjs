import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { route, link, continuationLink, practiceIntentions } from '../static/orena/product/intent.js';

assert.equal(route(link('continue')).page, 'continue', 'Continue must have its own reachable experience');
const { experienceFor, entryPoints, referenceCopy } = await import('../static/orena/ui/reference.js');
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
/* Closed, the list is out of the page rather than merely invisible - hiding it
   with opacity or a clip would leave eleven links in the tab order and read
   out by a screen reader while the sheet is shut. */
assert.match(phoneNav, /#shell nav \{ display:none; \}/, 'the sheet is closed, not just hidden');
assert.match(
  phoneNav,
  /#shell\[data-menu='open'\] nav \{ display:flex;/,
  'and opens on the shell state the control sets',
);
// The group headings come back in the sheet; the flattened strip had dropped
// them, so eleven destinations arrived as one undifferentiated run.
assert.match(phoneNav, /\.nav-group > small \{ display:block; \}/);
assert.match(phoneNav, /\.nav-group \{ flex-direction:column;/);
// Touch targets are not the thing that gives when space is short.
assert.match(phoneNav, /\.nav-toggle \{[^}]*min-height:46px/);
assert.doesNotMatch(phoneNav, /#shell nav a \{[^}]*font-size:1[0-2]px/);

console.log('Golden Star: approved destinations, intact intent contract, local in-room navigation, row composition, phone-reachable destinations and room measures: PASS');
