/* The Listening workspace's baseline details (D-066, Orena Listening frames 02-03):
   the "Luyện sâu" sheet, and the promises the workspace makes about a tapped line and about
   auto-scroll. The sheet's markup is pure; the encounter's wiring is held by reading its source,
   as the workspace gates do. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { lineSheetHtml } from '../static/orena/ui/line-sheet.js';
import { copy } from '../static/orena/ui/copy.js';
import { referenceCopy } from '../static/orena/ui/reference.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

/* Five ways to work on the line, named and explained in every interface language. */
const WAYS = ['dictation', 'shadowing', 'speaking', 'keep', 'inspect'];
for (const locale of ['en', 'zh', 'vi']) {
  const r = referenceCopy[locale];
  const html = lineSheetHtml({ r, c: copy[locale], when: '01:12', text: '我们想要一张靠窗的桌子。', language: 'zh' });
  for (const way of WAYS) assert.match(html, new RegExp(`data-way="${way}"`), `${locale}: ${way} is a way`);
  assert.match(html, /data-way="close"/, `${locale}: the sheet can be closed`);
  assert.match(html, /01:12/, `${locale}: it says which line`);
  assert.match(html, /lang="zh"/, `${locale}: the line keeps its own language`);
  for (const key of ['listenDeepTitle', 'listenDeepDictation', 'listenDeepShadow', 'listenDeepRead', 'listenDeepKeep', 'listenDeepInspect', 'listenAutoScroll', 'listenSeekHere', 'listenLoopLine', 'listenMore'])
    assert.ok(r[key], `${locale} has ${key}`);
}
const hostile = lineSheetHtml({ r: referenceCopy.en, c: copy.en, when: '0:01', text: '<img src=x onerror=alert(1)>', language: 'en' });
assert.doesNotMatch(hostile, /<img/, 'the line is escaped');

const encounter = read('static/orena/ui/encounter.js');
const listening = read('static/orena/listening.css');

/* A tapped line goes to that line and plays it; a tapped word asks about the word (bugs 7 and 12). */
const goTo = encounter.slice(encounter.indexOf('const goToLine = ('), encounter.indexOf("root.querySelectorAll('[data-loop-line]')"));
assert.ok(goTo.length > 200, 'the line handler was found');
assert.match(goTo, /model\.select\(s\.segment_id\)/, 'the tapped line becomes the current one');
assert.match(goTo, /replaySegment\(playerRoot, payload\.playback, s\.start_ms, null, rate\)/, 'and the voice plays on from it');
assert.match(goTo, /event\.target\.closest\('\.line-original'\)\) return;/, 'a tap on a word is left to the lexical layer');
assert.match(encounter, /goToLine\(segmentIdOf\(line\), \{ play: false \}\)/, 'a word in another visible line moves the current line there, paused, before it is asked about');
assert.doesNotMatch(encounter, /data-seek-here|data-picked/, 'there is no second, half-way "picked" state');
const loop = encounter.slice(encounter.indexOf("root.querySelectorAll('[data-loop-line]')"), encounter.indexOf("const seekInput"));
assert.match(loop, /s\.start_ms, s\.end_ms/, '"replay line" plays that line only');
assert.match(listening, /li\[data-current\] > \.line-pick \{\s*display: flex/, "the current line's own round action is shown by the attribute alone");
/* The overflow is a menu icon, not a bare "..." (bug 13). */
assert.match(encounter, /data-deep-open[^>]*>\$\{icon\('list'/, 'the top bar\'s overflow is the menu icon');

/* Auto-scroll is a kept preference that really stops the list following the voice. */
assert.match(encounter, /autoscroll: savedStage\.autoscroll !== false/, 'on by default, and kept');
assert.match(encounter, /if \(stage\.autoscroll && !readingAhead\(\)\) keepCurrentInView\(\);/, 'off means the voice no longer moves the list');

/* Word-class colours have no switch, so a stored "on" must not survive. */
assert.match(encounter, /colors: false,/, 'a stored colour preference cannot leave the transcript in a state nobody can undo');

/* The played part of the scrubber follows its position. */
assert.match(encounter, /seekInput\.style\.setProperty\('--fill'/);
assert.match(listening, /::-webkit-slider-thumb \{[^}]*background: #fff/, 'a white knob');

/* The frame's numbers (D-067, Design Contract rule 42): "Listening workspace" at 1920x1080. */
for (const [what, pattern] of [
  ['a 76px top bar over a stage and a 700px transcript', /grid-template-columns: minmax\(0, 1fr\) 700px;\s*grid-template-rows: 76px/],
  ['the stage padded 10/36/36 with 24 between its parts', /\.listen-stage \{[^}]*gap: 24px;[^}]*padding: 10px 36px 36px;/s],
  ['a 32px display title', /\.listen-identity h1 \{[^}]*font-size: 32px;[^}]*font-weight: 800;/s],
  ['a 6px track and a 15px knob', /::-webkit-slider-thumb \{[^}]*inline-size: 15px;/s],
  ['54px controls and a 64px play', /\.listen-controls \.icon-button \{[^}]*inline-size: 54px;/s],
  ['a 58px comprehension action', /\.listen-quiz \{[^}]*block-size: 58px;/s],
  ['the transcript padded 26/24/30', /padding: 26px 24px 30px;/],
  ['rows of 56px time and the line, 18 apart', /grid-template-columns: 56px minmax\(0, 1fr\);\s*column-gap: 18px;/],
]) assert.match(listening, pattern, what);
/* The room draws nothing the frame does not: no writing response, no end-of-recording panel. */
const room = encounter.slice(encounter.indexOf('<div class="listen-workspace"'), encounter.indexOf('</details>`;'));
assert.doesNotMatch(room, /data-response-host|reached-the-end|data-back-to-current/, 'nothing the frame does not draw');
assert.match(room, /data-deep-open/, "the frame's top-right button opens the deeper actions");
for (const locale of ['en', 'zh', 'vi']) assert.ok(referenceCopy[locale].listenHint, `${locale} has the transcript hint`);

console.log('Listening workspace: deep sheet, picked line, auto-scroll, scrubber, EN/ZH/VI: PASS');
