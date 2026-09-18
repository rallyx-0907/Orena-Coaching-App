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

/* --- The line being spoken is the protagonist --------------------------- */
assert.match(encounter, /<section class="learning-stage"/, 'the current line has its own stage');
assert.ok(
  encounter.indexOf('class="learning-stage"') < encounter.indexOf('class="transcript-panel"'),
  'the stage comes before the transcript, not after it',
);
/* It must not be put back inside the list: that is the defect - a learner
   scanning a long transcript to find where the voice is. */
const placeMoment = encounter.slice(
  encounter.indexOf('function placeMoment('),
  encounter.indexOf('function paintFollow('),
);
assert.doesNotMatch(placeMoment, /item\.append\(moment\)/, 'the stage is not moved into the transcript list');
assert.match(placeMoment, /toggleAttribute\('data-current'/, 'the transcript marks the current row instead');
assert.match(rooms, /\.transcript-panel li\[data-current\] > \[data-segment\]/, 'and that row is visibly current');
assert.match(encounter, /data-back-to-current/, 'a learner who reads ahead is offered one way back');

/* --- Playback and word class are different signals ---------------------- */
const speakingWordStart = experiences.indexOf('.spoken .word[data-speaking]');
const speakingWord = experiences.slice(
  speakingWordStart,
  experiences.indexOf('@media (prefers-reduced-motion: reduce)', speakingWordStart),
);
assert.doesNotMatch(speakingWord, /^\s*color:/m, 'where the voice is does not speak in colour');
assert.match(speakingWord, /background:/, 'it reads as a ground');
assert.match(rooms, /\.token\[data-pos='verb'\]\s*\{[^}]*color:/s, 'what a word is stays the colour signal');

/* --- One legend, on request, never under the sentence ------------------- */
assert.equal((encounter.match(/data-word-legend/g) || []).length, 2, 'one legend node, and one reference to it');
assert.match(encounter, /data-legend-toggle/, 'the legend is opened from its own control');
assert.ok(
  encounter.indexOf('data-word-legend') > encounter.indexOf('class="stage-toggles"'),
  'the legend belongs to the controls, not to the line',
);
assert.doesNotMatch(encounter, /close-look-guide/, 'the per-line colour explainer is retired');

/* --- Three small controls, and a compact action row --------------------- */
for (const toggle of ['meaning', 'pinyin', 'colors'])
  assert.match(encounter, new RegExp(`data-stage-toggle="${toggle}"`), `${toggle} is a learner control`);
assert.match(encounter, /localStorage\.setItem\(STAGE_KEY/, 'the three preferences are kept as the reader keeps its own');
const stageActions = encounter.slice(
  encounter.indexOf('class="stage-actions"'),
  encounter.indexOf('class="stage-toggles"'),
);
assert.match(stageActions, /data-replay-line/, 'Replay is the one control in the open');
assert.match(stageActions, /data-menu-toggle="practice"/);
assert.match(stageActions, /data-menu-toggle="more"/);
for (const intent of ['shadowing', 'speaking', 'dictation'])
  assert.match(stageActions, new RegExp(`data-intent="${intent}"`), `${intent} lives inside a menu`);
assert.doesNotMatch(encounter, /class="moment-actions"/, 'the row of equal buttons is gone');

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
assert.match(speaking, /items\.length$/m, 'a way in with nothing behind it is absent rather than empty');
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
assert.match(rooms, /@media \(max-width: 800px\)[\s\S]*?\.learning-stage/, 'the stage has its own phone layout');
assert.match(rooms, /@media \(max-width: 600px\)[\s\S]*?\.speak-grid/, 'so does the Speaking landing');

console.log('Learning stage: current line first, one legend, compact actions, Dictation apart, Speaking standalone, EN/ZH: PASS');
