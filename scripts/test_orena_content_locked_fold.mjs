/* Gate for #474: on Content Detail the locked preview's Unlock is reachable without scrolling (360x740, 390x844).

   Content Detail is a browsing place (shell/routes.js `focus:false`, `.o-main` scrolls as a page). For a Plus article
   it mounts the Reader's locked preview (screens/reader/locked.js), whose card is the bottom row next to the scroll
   region (#472). That only holds when the view has the column's height: the router's `.o-screen` has none, so without
   a rule `.s-reader { height: 100% }` resolves to auto and the card follows the preview in the page scroll. reader.css
   gives the screen the column when it holds the locked view (`.o-screen:has(> .s-reader-locked)`), as Orena home does.
   Without it (main after #473) the region collapsed to 32px and hid the preview. Measured on :8021 with this branch's
   files routed in (EN/VI/ZH): Unlock y 528-572 at 360x740 (phone bar at 650), 632-676 at 390x844 (bar at 754),
   958-1002 at 1920x1080; no page scroll, no horizontal overflow, the preview scrolls in its region. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const strip = (text) => text.replace(/\/\*[\s\S]*?\*\//g, '');

// Content Detail stays a browsing place: the fix must not turn it into a focus room.
const routes = readFileSync('static/orena/shell/routes.js', 'utf8');
const contentRoute = routes.split('\n').find((line) => /id:\s*'content'/.test(line)) || '';
assert.ok(/focus:\s*false/.test(contentRoute), 'Content Detail is a browsing place (focus:false)');

// Its refusal mounts the Reader's locked preview straight into its own screen element.
const screen = readFileSync('static/orena/screens/content/screen.js', 'utf8');
assert.ok(/import\s*\{\s*mountLockedPreview\s*\}\s*from\s*'\.\.\/reader\/locked\.js'/.test(screen), 'Content Detail uses the Reader locked preview');
assert.ok(/return mountLockedPreview\(element, ctx, refusal/.test(screen), 'the refusal draws the locked preview into the screen element');

// The locked view's root is `.s-reader.s-reader-locked`, the direct child the CSS rule matches.
const locked = readFileSync('static/orena/screens/reader/locked.js', 'utf8');
assert.ok(/return html`<div class="s-reader s-reader-locked">/.test(locked), 'the locked view root is .s-reader-locked');
assert.ok(/mount\(element, lockedPreviewMarkup\(/.test(locked), 'the view is mounted as the element\'s child');

// reader.css: the screen holding the locked view fills the column, so the view's 100% resolves and the foot stays put.
const css = strip(readFileSync('static/orena/screens/reader/reader.css', 'utf8'));
const block = css.match(/(^|\n)\.o-screen:has\(>\s*\.s-reader-locked\)\s*\{([^}]*)\}/);
assert.ok(block, '.o-screen:has(> .s-reader-locked) rule exists');
const body = block[2];
assert.ok(/(^|[;\s])height:\s*100%/.test(body), 'the screen takes the column height');
assert.ok(/display:\s*flex/.test(body) && /flex-direction:\s*column/.test(body), 'the screen is a column');
assert.ok(/min-height:\s*0/.test(body), 'the screen may shrink so the region scrolls, not the page');
const frame = css.match(/(^|\n)\.s-reader\s*\{([^}]*)\}/);
assert.ok(frame && /height:\s*100%/.test(frame[2]), 'the locked view fills its screen');

// Content Detail's own stylesheet does not size the screen another way (its unlocked page still scrolls as a page).
const contentCss = strip(readFileSync('static/orena/screens/content/content.css', 'utf8'));
assert.ok(!/\.o-screen/.test(contentCss), 'content.css leaves .o-screen alone; the unlocked page keeps its page scroll');

console.log('Content Detail locked fold gate (#474) OK');
