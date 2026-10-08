/* Dictation holds one line: playback is bounded to the line being written.

   A functional defect a learner met: writing down line 3 played line 3, then line 4,
   then the rest of the lesson, because only Replay was bounded. The boundary belongs to
   the player, not to the call that started it. The learner UI's segment player
   (product/original-segment-player.js) binds the player through holdSegment. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { segmentHoldAction } from '../static/orena/capabilities/media-player.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const player = read('static/orena/capabilities/media-player.js');
const segmentPlayer = read('static/orena/product/original-segment-player.js');

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

/* --- The learner UI binds a line through it ---------------------------- */
assert.match(segmentPlayer, /holdSegment\(root,\s*from,\s*to\)|holdSegment\(root,from,to\)/,
  'the original-segment player holds the line through the shared player');

console.log('Dictation workspace: a held line is the whole of what may be played: PASS');
