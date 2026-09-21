/* The listening learning stage, the action hierarchy, and Speaking as a module.

   Source-level contracts for the architecture this batch fixed. What can only
   be checked in a browser is checked there; what can be pinned without one is
   pinned here, because the defects these guard against are the kind that come
   back quietly: the current line sinking into the transcript, the legend
   sprouting under every sentence, six equal buttons growing back, Dictation
   turning into Writing again, and Speaking becoming a branch of Listening. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const encounter = read('static/orena/ui/encounter.js');
const speaking = read('static/orena/ui/speaking.js');
const rooms = read('static/orena/rooms.css');
const experiences = read('static/orena/experiences.css');
const foundation = read('static/orena/foundation.css');

/* --- The line being spoken IS the active transcript row, and stays its size -
   It briefly had a stage of its own above the list; that said the same
   sentence twice and ate the height the transcript needed. The fix after it -
   swapping the row's compact form for a taller opened one in place - moved the
   defect rather than removing it: playback rewrote the list's geometry every
   few seconds, and a phone jumped. A row now carries every slot it can show,
   the panel decides which of them count, and becoming current changes only
   what the row says and how it is drawn. */
assert.doesNotMatch(encounter, /class="learning-stage"/, 'no separate current-line stage');
assert.doesNotMatch(encounter, /class="follow-moment"/, 'and no opened block swapped in for the row');
assert.doesNotMatch(encounter, /placeMoment/, 'nothing is moved into the current row');
const markCurrent = encounter.slice(
  encounter.indexOf('function markCurrent('),
  encounter.indexOf('function plainRow('),
);
assert.match(markCurrent, /toggleAttribute\('data-current'/, 'the row is marked current');
assert.doesNotMatch(markCurrent, /\.append\(|\.hidden = /,
  'marking the current line neither moves a node nor hides one');
/* Every row is built from the one template, with all four slots, so no slot
   can be added or removed by a change of line. */
const row = encounter.slice(
  encounter.indexOf('const transcriptRow = (s) => {'),
  encounter.indexOf('const lineActions = ['),
);
assert.ok(row.length > 200, 'the row shape was actually found');
for (const slot of ['line-when', 'line-state', 'line-original', 'line-pinyin', 'line-meaning'])
  assert.ok(row.includes(slot), `every row carries ${slot}`);
assert.equal((encounter.match(/const transcriptRow = /g) || []).length, 1,
  'one row shape, current or not');
/* Which supporting slots are shown is the panel's, so it is true of all rows
   at once - and the stylesheet reserves their height, so a translation or a
   reading arriving late cannot move the list. */
assert.match(encounter, /transcript\.dataset\.showMeaning/, 'meanings are a panel-wide display preference');
assert.match(encounter, /transcript\.dataset\.showReading/, 'so are readings');
assert.match(rooms, /\.transcript-panel\[data-show-meaning='on'\] \.line-meaning \{[^}]*min-block-size/,
  'the meaning slot keeps its height on every row');
assert.match(rooms, /\.transcript-panel\[data-show-reading='on'\] \.line-pinyin \{[^}]*min-block-size/,
  'and so does the reading slot');
/* The current row is drawn, never re-laid-out: only properties that occupy no
   space may differ between a current row and any other. */
const currentRow = rooms.slice(
  rooms.indexOf(".transcript-panel li[data-current] > [data-segment] {"),
  rooms.indexOf('.transcript-note {'),
);
for (const property of [
  'padding', 'margin', 'border-width', 'display', 'min-height', 'min-block-size',
  // A bolder line is a wider line, and a wider line can take one more row.
  'font-weight', 'font-size', 'line-height', 'letter-spacing',
])
  assert.ok(!new RegExp(`^\s*${property}:`, 'm').test(currentRow),
    `the current row does not change ${property}`);
assert.match(currentRow, /box-shadow: inset/, 'its edge is drawn inside the row it already had');
assert.match(encounter, /data-back-to-current/, 'a learner who reads ahead is offered one way back');

/* --- The actions belong to a shared bar, not to a row ------------------- */
assert.doesNotMatch(encounter, /class="stage-actions"/, 'no action row inside the transcript');
assert.doesNotMatch(encounter, /data-replay-line/, 'Replay is not a control of a row');
assert.ok(
  encounter.indexOf('learningToolbar(lineActions') < encounter.indexOf('<ol>'),
  'the bar has a fixed place above the list',
);
assert.doesNotMatch(row, /button data-menu-toggle|data-action=|data-toggle=/,
  'and a row contains no action at all');
const toolbar = read('static/orena/ui/learning-toolbar.js');
assert.match(toolbar, /export function learningToolbar/, 'the bar is a shared primitive');
assert.match(toolbar, /export function bindLearningToolbar/);
assert.match(toolbar, /symbol\(icon, 18\)/, 'its controls are icons');
assert.match(toolbar, /aria-label="\$\{esc\(label\)\}"/, 'named in the support language');
assert.match(toolbar, /data-tip="\$\{esc\(label\)\}"/, 'with the same words on hover and focus');
/* A menu is placed by measurement, and on a phone it is a sheet that cannot
   leave the viewport in either direction. */
assert.match(toolbar, /function placeMenu\(/, 'menus are placed against the viewport');
assert.match(toolbar, /getBoundingClientRect\(\)/, 'by measuring, not by a written coordinate');
assert.doesNotMatch(toolbar, /(top|left|right|bottom):\s*-?\d+px/, 'no hard-coded coordinates');
assert.match(foundation, /\.learning-menu\[data-align='end'\]/, 'a bar near an edge opens inward');
assert.match(foundation, /\.learning-menu\[data-drop='up'\]/, 'and a short window opens upward');
assert.match(foundation, /@media \(max-width: 600px\)[\s\S]*?\.learning-menu \{[\s\S]*?position: fixed/,
  'a phone gets a sheet rather than a popover that can overflow');

/* Media and transcript share one viewport: the transcript scrolls inside its
   own pane rather than the page scrolling between them. */
assert.match(rooms, /@media \(min-width: 801px\)[\s\S]*?grid-template-columns: minmax\(0, 1\.3fr\) minmax\(320px, 1fr\)/,
  'desktop uses its width before stacking');
assert.match(rooms, /\.transcript-panel \{[\s\S]{0,200}?position: sticky/,
  'the transcript pane keeps its place while the media stays visible');

/* --- Playback and word class are different signals ---------------------- */
const speakingWordStart = experiences.indexOf('.line-original .word[data-speaking]');
const speakingWord = experiences.slice(
  speakingWordStart,
  experiences.indexOf('@media (prefers-reduced-motion: reduce)', speakingWordStart),
);
assert.doesNotMatch(speakingWord, /^\s*color:/m, 'where the voice is does not speak in colour');
assert.match(speakingWord, /background:/, 'it reads as a ground');
assert.match(rooms, /\.token\[data-pos='verb'\]\s*\{[^}]*color:/s, 'what a word is stays the colour signal');

/* --- The transcript header is the baseline's (D-066) -------------------- */
assert.doesNotMatch(encounter, /data-word-legend|name: 'legend'|name: 'colors'/,
  'the word-class legend and colour switch are not on the baseline transcript, so neither is drawn');
assert.ok(
  encounter.indexOf('learningToolbar(lineActions') < encounter.indexOf('<ol>'),
  'the display preferences sit with the transcript heading, not in the list',
);
assert.doesNotMatch(encounter, /close-look-guide/, 'the per-line colour explainer is retired');

/* --- Every reusable action of the current line, in the one bar ---------- */
const actions = encounter.slice(
  encounter.indexOf('const lineActions = ['),
  encounter.indexOf('/* The approved listening workspace'),
);
assert.ok(actions.length > 200, "the bar's actions were actually found");
for (const name of ['autoscroll', 'meaning', 'pinyin', 'deep'])
  assert.match(actions, new RegExp(`name: '${name}'`), `${name} is a control of the bar`);
for (const toggle of ['autoscroll', 'meaning', 'pinyin'])
  assert.match(actions, new RegExp(`name: '${toggle}',[^}]*kind: 'toggle'`),
    `${toggle} is a display preference, not an action`);
assert.doesNotMatch(actions, /name: '(replay|practice|colors|legend|more)'/,
  'everything deeper than hearing and asking is behind the one button');
const lineSheet = readFileSync(new URL('../static/orena/ui/line-sheet.js', import.meta.url), 'utf8');
for (const intent of ['dictation', 'shadowing', 'speaking', 'keep', 'inspect'])
  assert.match(lineSheet, new RegExp(`name: '${intent}'`), `${intent} is one of the ways to work on a line`);
assert.match(encounter, /localStorage\.setItem\(STAGE_KEY/, 'the three preferences are kept as the reader keeps its own');
assert.doesNotMatch(encounter, /class="moment-actions"/, 'the row of equal buttons is gone');
assert.doesNotMatch(encounter, /class="stage-toggles"/, 'and so is the row of text pills');
/* Nothing in the bar is a large text button: an icon carries it and the
   support language names it. */
assert.doesNotMatch(actions, /<button/, 'the bar is built from named actions, not from markup');

/* --- Dictation is not Writing ------------------------------------------- */
assert.match(encounter, /data-response-host/, 'the writing response is addressable');
const openPractice = encounter.slice(encounter.indexOf('async function openPractice('));
assert.match(openPractice, /responseHost\.hidden = true/, 'a practice mode hides the writing response');
const closePractice = encounter.slice(
  encounter.indexOf('function closePractice('),
  encounter.indexOf('function setRecordingLock('),
);
assert.match(closePractice, /responseHost\.hidden = false/, 'and leaving it brings the response back');

/* --- Speaking is a module, entered without Listening -------------------- */
assert.match(speaking, /function speakingLanding\(/, 'Speaking has a landing of its own');
assert.match(speaking, /if \(!location\.id\) return speakingLanding\(/, 'arriving with nothing chosen reaches it');
for (const key of ['speakContinue', 'speakRepeat', 'speakRespond', 'speakPrompt'])
  assert.match(speaking, new RegExp(`c\\.${key}`), `${key} is one of the ways in`);
assert.match(speaking, /continuationExperience\(x\) === 'speaking'/, 'unfinished speaking is real state');
assert.match(speaking, /continuationExperience\(x\) === 'listening'/, 'a line worth repeating comes from real listening');
assert.match(speaking, /body \? `<section class="speak-section"/,
  'a way in with nothing behind it is absent rather than empty');
/* Four ways in, each composed for what it is - not four of the same
   rectangle (DESIGN_CONTRACT: the card-wall anti-pattern). */
assert.match(speaking, /class="speak-resume"/, 'the one thing to carry on with leads with its artwork');
assert.match(speaking, /class="speak-rail"/, 'lines worth repeating sit on a rail');
assert.match(speaking, /class="speak-situations"/, 'situations are text and read as text');
assert.doesNotMatch(speaking, /class="speak-card"/, 'the wall of equal cards is gone');
assert.match(speaking, /entries\.find\(\(x\) => continuationExperience\(x\) === 'speaking'\)/,
  'Continue is one current thing, not a history dump');
assert.match(speaking, /mountLexicalLayer\(\{/, 'Speaking asks about language through the shared layer');

/* --- Microphone readiness, and what it may claim ------------------------ */
const mic = read('static/orena/capabilities/mic-readiness.js');
assert.match(mic, /track\.stop\(\)/, 'the readiness check releases the device it opened');
assert.match(mic, /NotFoundError/, 'no device and refused permission are different answers');
const voice = read('static/orena/ui/voice-response.js');
assert.match(voice, /mic\.stop\(\);/, 'leaving the room stops the readiness stream');
assert.match(voice, /micVeryQuiet/, 'a near-silent take says so');
assert.match(voice, /\[Orena Speaking\] capture/, 'the negotiated capture settings are inspectable');
assert.match(rooms, /\.mic-readiness\[data-state='ready'\] \.mic-readiness__state::before/, 'mic state is not colour alone');

/* --- EN and ZH ---------------------------------------------------------- */
for (const ui of ['en', 'zh'])
  for (const key of [
    'stageMeaning', 'stagePinyin', 'stageWordColors', 'stagePartsOfSpeech',
    'stagePractice', 'stageMore', 'stageShadowLine', 'stageSayYourself',
    'stageSaveSentence', 'stageBackToCurrent', 'wordConnectors',
    'speakRepeat', 'speakRespond', 'speakPrompt', 'speakContinue',
    'micReady', 'micNoDevice', 'micDenied', 'micVeryQuiet',
  ]) {
    assert.equal(typeof copy[ui][key], 'string', `${ui}.${key} is localized`);
    assert.ok(copy[ui][key].trim(), `${ui}.${key} is not empty`);
  }
assert.notEqual(copy.en.stagePractice, copy.zh.stagePractice);

/* --- The phone is designed, not squeezed -------------------------------- */
assert.match(rooms, /@media \(max-width: 600px\)[\s\S]*?\.speak-rail/, 'the Speaking rail has its own phone layout');
assert.match(rooms, /@media \(max-width: 600px\)[\s\S]*?\.speak-resume/, 'so does the Speaking landing');

console.log('Learning stage: current line first, one legend, compact actions, Dictation apart, Speaking standalone, EN/ZH: PASS');
