/* How a card asks its question.
 *
 * `recall.js` decides what *kind* of recall a phrase deserves from how the
 * learner met it. This decides the *task* the card is set: the four the
 * canonical frames draw beside the flashcard - typing the meaning, hearing and
 * choosing, hearing and typing back, and filling the word into its sentence -
 * plus which of them a given card can honestly be asked in.
 *
 * A mode is offered only when the card has what that mode needs. A word with
 * no recording cannot be a listening task and is not made into one with a
 * synthesised stand-in; a word with no sentence cannot be a cloze. That is why
 * every decision here takes the card and answers about that card, rather than
 * a setting deciding for all of them.
 *
 * Everything here is pure, and the choices are deterministic: the same card
 * asked twice offers the same options in the same order, because a learner who
 * answers 2 and comes back to find 2 is now a different answer has been taught
 * nothing.
 */

/* The modes the settings sheet lists, in the order it lists them. Flashcard is
   always on - it is the one task every card can always be set - and speaking
   belongs to the Speaking capability, so it is listed and not operated here. */
export const REVIEW_MODES = ['flashcard', 'typing', 'listen_choose', 'dictation', 'cloze', 'speak'];
export const ALWAYS_ON = 'flashcard';
export const NOT_HERE = 'speak';

export const NEW_PER_DAY = { min: 0, max: 50, step: 5, fallback: 10 };
export const REVIEW_LIMIT = { min: 20, max: 600, step: 20, fallback: 100 };

/* How many chances a typed answer gets before the card shows its answer. The
   frame says "còn 1 lần thử" on the first wrong one, so there are two. */
export const TYPING_TRIES = 2;
export const CHOICES = 4;

export function defaultReviewSettings() {
  return {
    newPerDay: NEW_PER_DAY.fallback,
    limitPerDay: REVIEW_LIMIT.fallback,
    modes: { typing: true, listen_choose: true, dictation: true, cloze: true, speak: false },
  };
}

/* A stored answer is only as trustworthy as its bounds: a setting read back
   from the device is clamped rather than believed. */
export function readReviewSettings(raw) {
  const base = defaultReviewSettings();
  if (!raw || typeof raw !== 'object') return base;
  const clamp = (value, { min, max, fallback }) => {
    const number = Number(value);
    if (!Number.isFinite(number)) return fallback;
    return Math.min(max, Math.max(min, Math.round(number)));
  };
  return {
    newPerDay: clamp(raw.newPerDay, NEW_PER_DAY),
    limitPerDay: clamp(raw.limitPerDay, REVIEW_LIMIT),
    modes: Object.fromEntries(
      Object.entries(base.modes).map(([name, on]) => [
        name,
        name === NOT_HERE ? false : typeof raw.modes?.[name] === 'boolean' ? raw.modes[name] : on,
      ]),
    ),
  };
}

/* Folding: what two spellings have to share to be the same answer.
 *
 * A learner typing Vietnamese without diacritics has recalled the word - the
 * frame says so in as many words ("chấp nhận thiếu dấu") - so the comparison
 * strips the marks, the case, the punctuation and the doubled spaces, and
 * nothing else. It does not strip letters, so "ban" and "bàn" still meet but
 * "ban" and "bank" do not.
 */
export function fold(text) {
  return String(text || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/* A meaning is often written with several answers in it - "vui · happy, glad".
   Any one of them is the learner remembering the word. */
export function answersIn(expected) {
  return String(expected || '')
    .split(/[·,;/]|\bhoặc\b|\bor\b/u)
    .map((part) => part.trim())
    .filter(Boolean);
}

export function checkTyped(typed, expected) {
  const said = String(typed || '').trim();
  if (!said) return { ok: false, exact: false, foldedOnly: false };
  for (const answer of answersIn(expected)) {
    if (said === answer) return { ok: true, exact: true, foldedOnly: false };
  }
  const foldedSaid = fold(said);
  if (!foldedSaid) return { ok: false, exact: false, foldedOnly: false };
  for (const answer of answersIn(expected)) {
    if (foldedSaid === fold(answer)) return { ok: true, exact: false, foldedOnly: true };
  }
  return { ok: false, exact: false, foldedOnly: false };
}

/* The hint the frame draws after a wrong try: how the answer starts and how
   long it is. It gives away neither the word nor its meaning. */
export function hintFor(expected) {
  const answer = answersIn(expected)[0] || '';
  const pieces = answer.split(/\s+/).filter(Boolean);
  return { starts: (pieces[0] || '').slice(0, 1), pieces: pieces.length };
}

/* A small, stable hash, so a card's options do not shuffle between paints. */
function seedOf(text) {
  let hash = 2166136261;
  for (const character of String(text || '')) {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return hash;
}

export function meaningOf(item) {
  return String(item?.definition || item?.translation_vi || '').trim();
}

export function sentenceOf(item) {
  const example = Array.isArray(item?.examples) ? item.examples[0] : null;
  return String(item?.source_fragment || example?.text || example || '').trim();
}

/* The other answers a chooser offers. They come from the learner's own queue -
   words they are actually reviewing - so a wrong answer is a word worth
   telling apart, not a random string. A card with too few neighbours to choose
   between is not made into a chooser at all. */
export function choicesFor(item, pool, count = CHOICES) {
  const right = meaningOf(item);
  if (!right) return [];
  const others = [];
  const seen = new Set([fold(right)]);
  for (const other of pool || []) {
    if (other?.word === item?.word) continue;
    const meaning = meaningOf(other);
    const folded = fold(meaning);
    if (!meaning || seen.has(folded)) continue;
    seen.add(folded);
    others.push(meaning);
  }
  if (others.length < count - 1) return [];
  const seed = seedOf(item?.word);
  const picked = [];
  for (let step = 0; step < count - 1; step += 1) {
    picked.push(others[(seed + step * 7919) % others.length]);
    others.splice((seed + step * 7919) % others.length, 1);
    if (!others.length) break;
  }
  const all = [right, ...picked];
  // Where the right answer sits is decided by the card, not by chance, so it
  // is the same every time this card is asked.
  const at = seed % all.length;
  const ordered = [...all];
  ordered.splice(at, 0, ordered.splice(0, 1)[0]);
  return ordered;
}

/* The sentence with the word taken out of it, and the word itself. Every
   occurrence goes, for the same reason `blankContext` takes every one: a
   sentence that prints the answer two words later is a reading task. */
export function clozeFor(item) {
  const sentence = sentenceOf(item);
  const word = String(item?.word || '');
  if (!sentence || !word || !sentence.includes(word)) return null;
  return { segments: sentence.split(word), answer: word };
}

/* Which tasks this card can honestly be set, before the learner's own
   settings are applied. */
export function modesFor(item, { hasAudio = false, pool = [] } = {}) {
  const modes = [ALWAYS_ON];
  if (meaningOf(item)) modes.push('typing');
  if (hasAudio && choicesFor(item, pool).length === CHOICES) modes.push('listen_choose');
  if (hasAudio) modes.push('dictation');
  if (clozeFor(item) && choicesFor({ ...item, definition: item?.word }, pool.map((other) => ({ ...other, definition: other.word }))).length === CHOICES)
    modes.push('cloze');
  return modes;
}

/* The task this card is set: the first mode the learner has left on that this
   card can actually be asked in, walked in a different order per card so a
   session is not five typing cards in a row. */
export function taskFor(item, settings, context = {}) {
  const can = modesFor(item, context);
  const on = can.filter((mode) => mode === ALWAYS_ON || settings?.modes?.[mode]);
  if (on.length <= 1) return ALWAYS_ON;
  const rotating = on.filter((mode) => mode !== ALWAYS_ON);
  return rotating[seedOf(item?.word) % rotating.length];
}
