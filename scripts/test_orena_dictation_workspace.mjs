/* Dictation: one line at a time, and leaving is not going back.

   Two defects a learner met, and the contracts that keep them from returning.

   The first was functional. Writing down line 3 played line 3, then line 4,
   then the rest of the lesson: only Replay was bounded, so the transport's own
   play button and the media element's native controls ran straight through.
   The boundary now belongs to the player, not to the call that started it.

   The second was navigational. "Back to Follow" and "Next" sat side by side as
   two arrows, so a learner reaching for the line before left Dictation
   altogether. Leaving is chrome; moving through the lesson is task navigation,
   and Dictation - which hides the transcript - moves through it with two
   arrows and a position, and nothing else. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { segmentHoldAction } from '../static/orena/capabilities/media-player.js';
import { copy } from '../static/orena/ui/copy.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const encounter = read('static/orena/ui/encounter.js');
const player = read('static/orena/capabilities/media-player.js');
const rooms = read('static/orena/rooms.css');

/* --- A held line is the whole of what may be played --------------------- */
const line = { start_ms: 5000, end_ms: 8000 };
assert.equal(segmentHoldAction(line, 5000, true), null, 'the start of the line is inside it');
assert.equal(segmentHoldAction(line, 6400, true), null, 'and so is the middle');
assert.equal(segmentHoldAction(line, 7999, true), null, 'right up to its last millisecond');
assert.equal(segmentHoldAction(line, 8000, true), 'pause', 'the end of the line stops playback');
assert.equal(segmentHoldAction(line, 8050, true), 'pause', 'and so does one clock tick past it');
assert.equal(segmentHoldAction(line, 21000, true), 'pause',
  'a player that ran on is stopped rather than left running');
assert.equal(segmentHoldAction(line, 900, true), 'seek',
  'playback that landed before the line is brought back to it');
/* A learner who paused mid-line to write it down comes back to where they
   paused, so a stopped player is never moved. */
for (const at of [900, 6400, 21000])
  assert.equal(segmentHoldAction(line, at, false), null, `a stopped player is left alone at ${at}`);
/* Nothing is held until something asks for it, and nonsense is not a hold. */
for (const bad of [null, {}, { start_ms: 5000 }, { start_ms: 8000, end_ms: 5000 }])
  assert.equal(segmentHoldAction(bad, 6000, true), null, 'an unusable hold binds nothing');

/* The hold binds the player, so every way in respects it. */
assert.match(player, /export function holdSegment/, 'a task can bind the player to one line');
assert.match(player, /export function releaseSegment/, 'and give the source back');
assert.match(player, /segmentHoldAction\(/, 'the clock asks the same question this test asks');
const toggle = player.slice(player.indexOf('export function togglePlayback'));
assert.match(toggle, /holdEndMs/, "the transport's play button plays the held line, not the lesson");
const replay = player.slice(player.indexOf('export function replaySegment'));
assert.doesNotMatch(replay, /holdEndMs=null|releaseSegment/, 'replaying inside a held line does not release it');

/* --- Dictation holds the line being written ----------------------------- */
assert.match(encounter, /function holdPractisedLine\(/, 'Dictation binds the line it is on');
const hold = encounter.slice(
  encounter.indexOf('function holdPractisedLine('),
  encounter.indexOf('function setRecordingLock('),
);
assert.match(hold, /practice !== 'dictation'[\s\S]*?releaseSegment/, 'and only Dictation does');
assert.match(hold, /holdSegment\(playerRoot, practiceTarget\.start_ms, practiceTarget\.end_ms\)/,
  "from the transcript's own timing, never a second copy of it");
assert.match(encounter, /if \(practice === 'dictation'\) holdPractisedLine\(\);/,
  'a player that connected late is bound as soon as it reports a time');
const closing = encounter.slice(
  encounter.indexOf('function closePractice('),
  encounter.indexOf('function holdPractisedLine('),
);
assert.match(closing, /releaseSegment\(playerRoot\)/, 'leaving Dictation gives the whole lesson back');

/* --- Leaving is not the line before ------------------------------------- */
assert.doesNotMatch(encounter, /data-follow\b/, 'the arrow that meant "leave" is gone');
assert.match(encounter, /data-exit-practice/, 'leaving has a control of its own');
assert.match(encounter, /symbol\('close', 18\)\}<span>\$\{esc\(c\.exitPractice\)\}/,
  "drawn as a cross with its own word, in the panel's chrome");
assert.match(encounter, /practiceRoot\.querySelector\('\[data-exit-practice\]'\)\.onclick = closePractice/,
  'and it is the only thing that closes the task');
for (const control of ['data-prev-moment', 'data-next-moment'])
  assert.match(encounter, new RegExp(control), `${control} is task navigation`);
const moveTo = encounter.slice(
  encounter.indexOf('const moveTo = (index) => {'),
  encounter.indexOf('nextButton.onclick'),
);
assert.doesNotMatch(moveTo, /closePractice/, 'moving between lines never leaves the task');
assert.match(moveTo, /openPractice\(intent\)/, 'it re-opens the same intention on another line');
assert.match(encounter, /previousButton\.onclick = \(\) => moveTo\(at - 1\)/, 'Previous is the line before');
assert.match(encounter, /nextButton\.onclick = \(\) => moveTo\(nextIndex\)/, 'Next is the line after');
assert.match(encounter, /previousButton\.disabled = at <= 0/, 'the first line has no line before it');

/* --- Previous, where you are, Next - and nothing else ------------------- */
/* Two attempts at arbitrary segment selection have been removed. Numbered
   pills said nothing a learner could recognise; a popover of real sentences
   read better but overlapped its own text, overflowed its pane and covered the
   task. Both were a second way to do what the two arrows already do. */
assert.doesNotMatch(encounter, /segment-navigator|data-goto-segment|data-segment-list/,
  'no numbered pills');
assert.doesNotMatch(encounter, /data-lines-host|linesHost/, 'and no segment list behind a control');
assert.doesNotMatch(encounter, /c\.lineNumber|c\.lineList|c\.lineWritten/,
  'nothing names a line by number or lists them');
assert.doesNotMatch(rooms, /\.segment-navigator/, 'and no stylesheet for either');
const toolbar = read('static/orena/ui/learning-toolbar.js');
assert.doesNotMatch(toolbar, /learning-menu__label|menuItemHtml|entry\.done/,
  'the shared bar keeps plain menu items, with nothing left over from the picker');
const foundation = read('static/orena/foundation.css');
assert.doesNotMatch(foundation, /learning-menu--wide/, 'and no stylesheet for one either');
/* The practice panel's navigation is three things, and the third is a state. */
const steps = encounter.slice(
  encounter.indexOf('<nav class="practice-steps"'),
  encounter.indexOf('<div data-practice-body>'),
);
assert.match(steps, /data-prev-moment/, 'Previous');
assert.match(steps, /class="practice-place"/, 'where you are');
assert.match(steps, /data-next-moment/, 'Next');
assert.doesNotMatch(steps, /data-menu-toggle|learningToolbar/, 'and no fourth control');
assert.equal((steps.match(/<button/g) || []).length, 2, 'two controls in the row, both arrows');

/* --- EN, ZH and VI all say it ------------------------------------------- */
for (const ui of ['en', 'zh', 'vi'])
  for (const key of [
    'exitPractice', 'previousLine', 'nextLine', 'lineNow', 'lineActionsLabel',
  ]) {
    assert.equal(typeof copy[ui][key], 'string', `${ui}.${key} exists`);
    assert.ok(copy[ui][key].trim(), `${ui}.${key} is not empty`);
  }

console.log('Dictation workspace: one line at a time, leaving is not going back, EN/ZH/VI: PASS');
