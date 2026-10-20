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

/* --- The phone: the keyboard never hides the Transcript, the hint is an eye (2026-10-11, D-175) --------------
   A learner typing on a phone could not see or scroll the Transcript under the answer (the typing state hid
   it), the Transcript had one row left after Check, and the hint row was mostly words. Structure, read from
   source: the browser check in docs/project/UI_BACKEND_GAPS.md measures the result. */
const practiceSrc = read('static/orena/screens/dictation/line-practice.js');
const dictCss = read('static/orena/screens/dictation/dictation.css');
const listenCss = read('static/orena/screens/listening/listening.css');
const listenSrc = read('static/orena/screens/listening/screen.js');
globalThis.document = globalThis.document || { documentElement: { lang: 'en', dataset: {} } };
const { ICONS } = await import('../static/orena/kit/icons.js');
const { setLanguages } = await import('../static/orena/copy/index.js');
const { t: dictT } = await import('../static/orena/screens/dictation/copy.js');

const rulesFor = (css, selectorPart) => [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
  .filter(([, selector]) => selector.includes(selectorPart))
  .map(([, selector, body]) => ({ selector: selector.trim(), body }));

// The hint is the package's eye glyph with its words kept as its accessible name and tooltip, and the ladder
// note as its description; the put-away toggle is a chevron with its words likewise.
for (const name of ['eye', 'chevron-up', 'chevron-down']) assert.ok(ICONS[name], `Lucide "${name}" is in the pinned set`);
const hintButtonMarkup = practiceSrc.match(/<button[^>]*data-hint\b[^>]*>.*?<\/button>/s)?.[0] || '';
assert.match(hintButtonMarkup, /icon\('eye'/, 'the hint button draws the eye glyph');
assert.match(hintButtonMarkup, /aria-describedby="\$\{noteId\}"/, 'the ladder note describes the hint button');
assert.match(hintButtonMarkup, /class="s-dict__actlabel" data-label/, 'the hint keeps its words as a label span');
assert.match(practiceSrc, /data-hint-note id="\$\{noteId\}"/, 'the note carries the id the hint points at');
assert.match(practiceSrc, /setAttribute\('aria-label', label\)/, 'a glyph control is named by its words');
assert.match(practiceSrc, /labelControl\(button, t\(view\.key, view\.values\)\)/, 'the hint is named by its ladder label');
assert.match(practiceSrc, /labelControl\(toggle, t\(hintHidden \? 'hintShow' : 'hintHide'\)\)/, 'the toggle is named by its action');
assert.match(practiceSrc, /icon\(hintHidden \? 'chevron-down' : 'chevron-up'/, 'the toggle draws a chevron, not a second eye');
// Every one of those names exists, and differs, in the three interface languages.
const names = ['hintGive', 'hintMore', 'hintMaxed', 'hintHide', 'hintShow', 'hintNoteStart', 'hintNoteStartHan', 'showAnswer', 'answerShownBadge'];
const byLang = {};
for (const ui of ['en', 'vi', 'zh']) {
  setLanguages({ ui });
  byLang[ui] = names.map((key) => dictT(key, { n: 2, total: 3 }));
  byLang[ui].forEach((value, i) => assert.ok(value && !value.includes(names[i]), `${ui}: ${names[i]} is translated`));
}
assert.notDeepEqual(byLang.vi, byLang.en, 'Vietnamese has its own hint words');
assert.notDeepEqual(byLang.zh, byLang.en, 'Chinese has its own hint words');
setLanguages({ ui: 'en' });

// The desk keeps the frame's words (glyphs hidden there); the phone shows the glyphs and hides the words and note.
assert.ok(rulesFor(dictCss, '.s-dict__hint > .ic').some((r) => /display:\s*none/.test(r.body)), 'the desk hides the eye');
const phone = (part) => rulesFor(listenCss, part).filter((r) => r.selector.includes(':root[data-device="mobile"]'));
assert.ok(phone('.s-dict__hint > .ic').some((r) => /display:\s*flex/.test(r.body)), 'the phone shows the eye');
assert.ok(phone('.s-dict__hintnote').some((r) => /clip:\s*rect\(0 0 0 0\)/.test(r.body)), 'the phone does not print the ladder note');
assert.ok(phone('.s-dict__actlabel').some((r) => /clip:\s*rect\(0 0 0 0\)/.test(r.body)), 'the phone does not print the hint words');
assert.ok(phone('.s-dict__check').some((r) => /flex:\s*1 1 auto/.test(r.body)), 'Check is the one wide action on the phone');

// Typing keeps the Transcript: no typing rule hides it, one keeps a floor for it, and the room follows the
// visible viewport (the keyboard) with the pane observer reframing the current line as it shrinks.
for (const rule of rulesFor(listenCss, '.is-typing')) {
  if (/display:\s*none/.test(rule.body)) {
    assert.doesNotMatch(rule.selector, /\.s-listening__transcript(?![-_])/, `typing never hides the Transcript (${rule.selector})`);
  }
}
// Only the task stays above the keyboard: the header and the Transcript's own title give their height to its rows.
for (const part of ['.s-listening__head', '.s-listening__transcript-head', '.s-listening__seek']) {
  assert.ok(phone(`.is-typing ${part}`).some((r) => /display:\s*none/.test(r.body)), `typing gives ${part}'s height to the Transcript`);
}
// It takes what the task leaves (no floor that would push the answer box under the keyboard on a short screen).
assert.ok(phone('.is-typing .s-listening__transcript').some((r) => /min-height:\s*0;/.test(r.body)), 'typing gives the Transcript what the task leaves');
assert.ok(rulesFor(listenCss, '.s-listening.is-typing').some((r) => /var\(--ls-visible-h/.test(r.body)), 'typing fits the visible viewport');
assert.match(listenSrc, /viewport\?\.addEventListener\('resize'/, 'the visible height follows visualViewport');
assert.match(listenSrc, /new ResizeObserver\(/, 'a resized Transcript frames the current line again');
// Not typing, Dictation on the phone draws its picture as the compact strip, and after a check keeps a real share
// for the Transcript - after the media blocks, so a short phone's 72px floor does not win.
assert.ok(phone('.is-dictation:not(.is-typing) .s-listening__player').some((r) => /height:\s*96px/.test(r.body)), 'the picture is the compact strip in Dictation');
const share = listenCss.lastIndexOf('.is-dictation:not(.is-typing):has(.s-dict__result) .s-listening__transcript');
assert.ok(share > listenCss.lastIndexOf('@media (max-height: 700px)'), 'the Dictation share comes after the short-phone floors');
assert.match(listenCss.slice(share), /^[^}]*min-height:\s*30%/, 'after a check the Transcript keeps at least 30% of the body');

/* --- #445: after Check the result is in view on the phone, never under the keyboard --------------------------
   WebKit sends no focusout when the focused answer box is replaced by the result, so the room stayed in its
   keyboard layout. Check lets go of the field first, the room ends typing at once and brings the result's stage to
   its score, settling again while the visible viewport grows back; the page itself is never what scrolls. */
const checkFn = practiceSrc.slice(practiceSrc.indexOf('async function check()'));
assert.ok(checkFn.indexOf('.blur()') > -1 && checkFn.indexOf('.blur()') < checkFn.indexOf('paint()'),
  'Check lets go of the answer box before the result replaces it');
assert.match(practiceSrc, /event\.keyCode !== 229/, "an input method's Enter commits its word, never the answer");
assert.match(practiceSrc, /!event\.isComposing/, 'and so does a composing Enter');
const onCheck = listenSrc.slice(listenSrc.indexOf('onCheck:'), listenSrc.indexOf('onRetry:'));
assert.match(onCheck, /revealResult\(\)/, 'the room settles the result after every check');
const reveal = listenSrc.slice(listenSrc.indexOf('function revealResult()'));
assert.match(reveal, /classList\.remove\('is-typing'\)/, 'typing ends at once, not after the focusout delay');
assert.match(reveal, /removeProperty\('--ls-visible-h'\)/, 'the room is the full visible area again');
assert.match(reveal, /viewport\.addEventListener\('resize'/, 'and settles again while the keyboard closes');
assert.match(reveal, /stage\.scrollTop = 0/, "the stage, the result's own region, starts at the score");
assert.doesNotMatch(reveal.slice(0, reveal.indexOf('setTimeout(')), /scrollIntoView/, 'nothing scrolls the page itself');

/* --- #445, owner decision 2026-10-20: matched words are green, and the answer can be shown -------------------
   Green is the semantic success pair the Live check strip already uses, with no edge (D-147). "Show answer" is a
   control of the hint row's own style (a glyph on the phone, its words on the desk), reveals the line as a check does,
   and records it through the attempt model's `revealed` - never a score. */
for (const side of ['.s-dict__chip--mine-correct', '.s-dict__chip--src-correct']) {
  const rule = rulesFor(dictCss, side);
  assert.ok(rule.some((r) => /background:\s*var\(--green-soft\)/.test(r.body) && /color:\s*var\(--green\)/.test(r.body)), `${side} is the success pair`);
  assert.ok(rule.every((r) => !/border|outline|box-shadow/.test(r.body)), `${side} draws no edge`);
}
const revealButton = practiceSrc.match(/<button[^>]*data-reveal[^>]*>.*?<\/button>/s)?.[0] || '';
assert.match(revealButton, /class="s-dict__hint s-dict__reveal"/, "Show answer takes the hint row's button style");
assert.match(revealButton, /aria-label="\$\{t\('showAnswer'\)\}"/, 'and is named by its words');
assert.match(revealButton, /icon\('book-open'/, 'a Lucide glyph on the phone');
assert.ok(practiceSrc.indexOf('data-reveal') < practiceSrc.indexOf('data-check'), 'it sits before Check, not after it');
const revealFn = practiceSrc.slice(practiceSrc.indexOf('async function reveal()'), practiceSrc.indexOf('async function check()'));
assert.match(revealFn, /evidence\.reveal\(\)/, "the reveal is the attempt model's own record");
assert.doesNotMatch(revealFn, /evidence\.compare|checkAnswer/, 'showing the answer scores nothing');
assert.match(revealFn, /revealedIds\.add\(line\.id\)/, 'the line is revealed as a check reveals it');
assert.match(revealFn, /onCheck\(line\)/, 'and the room settles it in view as after a check');
assert.match(revealFn, /if \(readOnly\) return;/, "an administrator's preview stores nothing");
assert.match(practiceSrc, /answerChips\(seg\.text, lesson\.language\)/, 'the shown line is drawn in its own spelling');

console.log('Dictation workspace: a held line is the whole of what may be played; the phone keeps the Transcript while typing and draws the hint as an eye: PASS');
