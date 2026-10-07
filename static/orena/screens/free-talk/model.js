/* Free Talk (frame 29-Free-Talk.html, route 'freetalk'; E2 §2). Pure, DOM-free data mapping so
   scripts/test_orena_screen_free-talk.mjs can prove it without a browser.

   The frame's own topic list, duration set and transcript/result numbers (`ftSuggest`, the
   hard-coded transcript stub, `analyze()`'s regex heuristic) are prototype content with no real
   backend behind them (E2 §2 "Bindings"/"Data the backend must provide") - never reproduced here
   (Design Contract rule 40). What is real: the topic bank (`content/voice-invitations.js`, the
   same Orena-authored situations the current Free Talk already opens from, C5 §4), a real ASR
   transcript (`POST /api/speech/transcribe`), and real coaching from that transcript
   (`POST /api/dictionary/spoken-response`, the exact "carried / landed_differently / another_way /
   next_attempt / say_again" shape `writing_coach/media_interaction.py#coach_spoken_response`
   returns - the same endpoint and shape the current Free Talk's own `coach()` already uses,
   `ui/speaking-free.js:251-267`). */
import { voiceInvitations } from '../../content/voice-invitations.js';
import { countLinkers } from './linking.js';

/* The frame draws three duration pills (E2: "1/2/3 min"); each is also the real cap the recorder
   auto-stops at, so choosing one has a real effect, not a cosmetic label. */
export const DURATIONS_MS = Object.freeze([60_000, 120_000, 180_000]);

/* Real, Orena-authored topics (not the frame's own fixed `ftSuggest` prompts) - the same bank the
   current Free Talk already opens from (C5 §4). `prompt` doubles as the coaching call's
   `situation` field once a topic is chosen. */
export function topics(language) {
  return voiceInvitations(language).map((item) => ({ key: item.key, title: item.title, prompt: item.prompt, cue: item.cue }));
}

/* `m:ss`, the frame's own clock (`clock()` in the source: minutes are not zero-padded). */
export function formatClock(ms) {
  const whole = Math.floor(Math.max(0, Number(ms) || 0) / 1000);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}

/* The frame's recording wave: 40 bars whose heights follow `25 + |sin(i * 1.3)| * 75` percent and
   whose pulse delay is `(i * 41) % 700` ms (`spWave` in the source, evaluated at second 0). Pure
   shape, no audio level - the source's own bars are not tied to the microphone either. */
export function waveBars(count = 40) {
  return Array.from({ length: count }, (_, i) => ({
    height: Math.round(25 + Math.abs(Math.sin(i * 1.3)) * 75),
    delay: (i * 41) % 700,
  }));
}

const HAN = /[㐀-鿿]/g;

/* Words for an English/Vietnamese transcript, Han characters for a Chinese one - the same
   language-aware unit the rest of Speaking already uses (speaking-workspace-line.js's
   one-unit-per-Han-character rule), not a whitespace split that would undercount Chinese to ~0. */
export function unitCount(text, language) {
  const trimmed = String(text || '').trim();
  if (!trimmed) return 0;
  if (language === 'zh') return (trimmed.match(HAN) || []).length;
  return trimmed.split(/\s+/).filter(Boolean).length;
}

/* The frame reads a recording shorter than this as "not enough to measure a pace" and draws a dash
   (`wpm: fb.wpm == null ? "—" : fb.wpm` in the source, fed by `analyze()` returning null under 5 s). */
export const MIN_PACE_MS = 5000;

/* Units per minute of the actual recording, from the real transcript and the real elapsed time -
   a derived real number, not the frame's own regex `analyze()` estimate. `null` when the take is
   too short to say (the frame's own "—", not a made-up 0 wpm): the screen draws the dash. */
export function pace(text, ms, language) {
  const elapsed = Number(ms) || 0;
  if (elapsed < MIN_PACE_MS) return null;
  return Math.round(unitCount(text, language) / (elapsed / 60_000));
}

/* The frame's three result tiles. Words and Pace are measured from the real transcript and the
   real elapsed time; Linking counts the linking words in the transcript through the language
   adapter in linking.js (D-139 HD-9) - a count, never a score. */
export function resultStats(text, ms, language) {
  return { words: unitCount(text, language), pace: pace(text, ms, language), linking: countLinkers(text, language) };
}

/* What Finish writes to the session's speaking ledger (`product/speaking-session.js`): only what
   was really measured, as display strings (the ledger's own "lowest score" reducer reads numbers
   only, and these are counts, not scores). A take too short for a pace leaves Pace out. */
export function ledgerFacts(stats, labels) {
  return [
    { label: labels.words, value: String(stats.words) },
    ...(stats.pace == null ? [] : [{ label: labels.pace, value: `${stats.pace} ${labels.paceUnit}` }]),
  ];
}

/* Up to 3 corrections, exactly the current Free Talk's own `fixesOf` (ui/speaking-free.js:54-56) -
   reimplemented here (not imported: that module is old-UI presentation, never imported by the new
   UI) against the same real `spokenResponseCoaching` shape. */
export function fixesOf(coaching) {
  return (coaching?.landed_differently || []).filter((item) => item?.quote).slice(0, 3);
}

/* What carried, the same shape, capped the same way as the frame's own "Strengths" list (max 3,
   matching the Fixes cap it sits beside). */
export function strengthsOf(coaching) {
  return (coaching?.carried || []).filter((item) => item?.quote).slice(0, 3);
}

/* Short phrases and words only: a whole sentence saved to the library is not a "useful phrase"
   chip (S-18). Capped by unit count (6 words, or 12 Han characters) and length. */
const shortPhrase = (text) => {
  if (text.length > 40 || /[.!?。！？]\s*\S/u.test(text)) return false;
  const han = (text.match(/\p{Script=Han}/gu) || []).length;
  return han ? han <= 12 : text.split(/\s+/).length <= 6;
};

/* The learner's own saved short words, newest first (E2: "real personalised data", `s.saved` in the
   source; `GET /api/library/vocabulary` is the real equivalent). */
export function phraseWords(page, limit = 4) {
  const items = Array.isArray(page?.items) ? page.items : [];
  return items.map((item) => String(item?.word || '').trim()).filter((text) => text && shortPhrase(text)).slice(0, limit);
}

/* Whether a saved item can be said to belong to a topic (LEX-051). Only evidence the screen holds: the item
   appears inside the topic's own words (a Chinese item as a substring - there are no spaces to split on),
   or an English/Vietnamese item equals one of the topic's words of four letters or more. No guess beyond
   that: nothing here is a semantic match, and a topic nothing overlaps with gets no "related" claim. */
export function relatesToTopic(item, topic) {
  const word = String(item || '').trim().toLocaleLowerCase();
  const text = String(topic || '').trim().toLocaleLowerCase();
  if (!word || !text) return false;
  if (/\p{Script=Han}/u.test(word)) return [...word].length >= 2 && text.includes(word);
  const tokens = new Set(text.split(/[^\p{L}\p{N}]+/u).filter((token) => token.length >= 4));
  return word.split(/\s+/).some((token) => token.length >= 4 && tokens.has(token));
}

/* What the setup card shows under "Duration": the saved items that relate to the chosen topic when any do
   (`kind: 'topic'`), otherwise the learner's own recent saved items labelled for what they are
   (`kind: 'library'`), which the screen draws as secondary. `topic` is every string that names the topic
   (its title, the typed text, the authored situation). */
export function phrasesFor(page, topic, limit = 4) {
  const all = phraseWords(page, Infinity);
  const related = all.filter((item) => relatesToTopic(item, topic));
  if (related.length) return { kind: 'topic', items: related.slice(0, limit) };
  return { kind: 'library', items: all.slice(0, limit) };
}

/* 0 fixes -> "headlineNone"; 1 -> "headlineOne" (frame's singular wording); 2+ -> the plural key,
   read with t.plural. Mirrors the current Free Talk's own 3-way headline split
   (ui/speaking-free.js:76) against the real fix count instead of the frame's regex one. */
export function headlineKind(fixCount) {
  if (fixCount <= 0) return 'none';
  if (fixCount === 1) return 'one';
  return 'many';
}
