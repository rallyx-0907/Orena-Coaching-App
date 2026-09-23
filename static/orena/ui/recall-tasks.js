/* The four ways a review card can ask its question.
 *
 * The canonical frames "Review typing retry", "Review typing mobile",
 * "Review listen choose mobile", "Review dictation mobile" and "Review cloze
 * mobile". They share a shell - the way out, how far through the sitting the
 * learner is, one glass card, a mode pill at its top left - and differ only in
 * what the card holds and what the foot offers.
 *
 * Pure: every function here turns a card and an answer-so-far into markup.
 * Which task a card is set is `product/recall-modes.js`; what happens to the
 * answer is the room's.
 */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { clozeFor, hintFor, meaningOf, sentenceOf } from '../product/recall-modes.js';

const PILL = {
  typing: { icon: 'keyboard', key: 'recallModeTyping' },
  listen_choose: { icon: 'headphones', key: 'recallModeListenChoose' },
  dictation: { icon: 'ear', key: 'recallModeDictation' },
  cloze: { icon: 'text-aa', key: 'recallModeCloze' },
};

function pill(c, mode) {
  const drawn = PILL[mode];
  if (!drawn) return '';
  return `<span class="recall-task__pill ds-data">${icon(drawn.icon, { size: 14 })}${esc(c[drawn.key])}</span>`;
}

/* The word being asked, with its reading and a way to hear it - the head of
   the typing and dictation cards. */
function subject(c, item, { reading = true } = {}) {
  return `<div class="recall-task__subject"><span class="recall-task__word" lang="${esc(item.language || '')}">${esc(item.word)}</span>${
    reading && item.phonetic
      ? `<span class="recall-task__reading ds-data">${esc(item.phonetic)}<button type="button" class="icon-button recall-task__speak" data-recall-speak aria-label="${esc(c.vocabularyAudio)}">${icon('speaker-high', { size: 16, filled: true })}</button></span>`
      : ''
  }</div>`;
}

/* The answer's own spelling, with the marks the learner left out picked out,
   so "chấp nhận thiếu dấu" is something they can see rather than be told. */
function spelled(typed, answer) {
  const said = String(typed || '');
  const right = String(answer || '');
  let out = '';
  for (let at = 0; at < right.length; at += 1) {
    const character = right[at];
    const same = said[at] === character;
    out += same ? esc(character) : `<b>${esc(character)}</b>`;
  }
  return out;
}

export function typingCard(c, item, state) {
  const { typed = '', verdict = null, tries = 0 } = state;
  const answer = meaningOf(item);
  const tone = verdict ? (verdict.ok ? 'good' : 'warn') : '';
  const hint = hintFor(answer);
  const field = verdict
    ? `<div class="recall-field" data-tone="${tone}"><span class="recall-field__said">${esc(typed)}</span>${icon(verdict.ok ? 'check-circle' : 'arrow-counter-clockwise', { size: verdict.ok ? 20 : 22, filled: verdict.ok })}</div>`
    : `<div class="recall-field"><input type="text" data-recall-typed value="${esc(typed)}" autocomplete="off" autocapitalize="off" spellcheck="false" aria-label="${esc(c.recallTypeMeaning)}"></div>`;
  const verdictLine = !verdict
    ? ''
    : verdict.ok
      ? `<div class="recall-verdict" data-tone="good"><span class="recall-verdict__head">${esc(verdict.foldedOnly ? c.recallRightNoMarks : c.recallRight)}</span><span class="recall-verdict__body">${esc(c.recallSpelledRight)} <b>${spelled(typed, answer)}</b></span></div>`
      : `<div class="recall-verdict" data-tone="warn">${icon('warning-circle', { size: 22, filled: true })}<span class="recall-verdict__head">${esc(
          tries < 2 ? String(c.recallWrongOneMore) : String(c.recallWrong),
        )}</span><span class="recall-verdict__hint">${esc(
          String(c.recallHint).replace('{c}', hint.starts).replace('{n}', String(hint.pieces)),
        )}</span></div>`;
  return `<div class="recall-task recall-task--typing">${pill(c, 'typing')}${subject(c, item)}<div class="recall-task__answer">${field}${verdictLine}</div></div>`;
}

export function listenChooseCard(c, item, state) {
  const { options = [], chosen = -1, verdict = null, speed = 1 } = state;
  const right = meaningOf(item);
  const rows = options
    .map((text, at) => {
      const tone = verdict === null ? '' : text === right ? 'good' : at === chosen ? 'warn' : '';
      return `<button type="button" class="recall-choice" data-recall-choose="${at}"${tone ? ` data-tone="${tone}"` : ''}${verdict !== null ? ' disabled' : ''}><span class="recall-choice__n ds-data">${at + 1}</span><span>${esc(text)}</span></button>`;
    })
    .join('');
  return `<div class="recall-task recall-task--listen">${pill(c, 'listen_choose')}<div class="recall-task__hear"><button type="button" class="recall-play" data-recall-speak aria-label="${esc(c.vocabularyAudio)}">${icon('speaker-high', { size: 36, filled: true })}</button><div class="recall-task__again"><button type="button" class="recall-chip" data-recall-speak>${esc(c.recallPlayAgain)}</button><button type="button" class="recall-chip ds-data" data-recall-speed>${esc(speed === 1 ? '1×' : '0.75×')}</button></div></div></div><div class="recall-choices">${rows}</div>`;
}

export function dictationCard(c, item, state) {
  const { attempts = [], typed = '', verdict = null } = state;
  const sentence = sentenceOf(item);
  const said = attempts.length
    ? `<div class="recall-task__block"><span class="ds-label">${esc(c.recallYouTyped)}</span>${attempts
        .map(
          (line, at) =>
            `<div class="recall-attempt"><span class="ds-data">${at + 1}</span><s>${esc(line)}</s></div>`,
        )
        .join('')}</div>`
    : '';
  const revealed = verdict
    ? `<div class="recall-task__rule" aria-hidden="true"></div><div class="recall-task__block"><span class="ds-label">${esc(c.recallAnswer)}</span><span class="recall-task__answerword" lang="${esc(item.language || '')}">${esc(item.word)}</span><span class="recall-task__gloss">${esc(meaningOf(item))}</span></div>${
        sentence
          ? `<div class="recall-task__example"><span lang="${esc(item.language || '')}">${esc(sentence)}</span></div>`
          : ''
      }`
    : `<div class="recall-field"><input type="text" data-recall-typed value="${esc(typed)}" autocomplete="off" autocapitalize="off" spellcheck="false" lang="${esc(item.language || '')}" aria-label="${esc(c.recallTypeWhatYouHear)}"></div>`;
  return `<div class="recall-task recall-task--dictation"><div class="recall-task__pillrow">${pill(c, 'dictation')}<button type="button" class="icon-button recall-task__speak" data-recall-speak aria-label="${esc(c.vocabularyAudio)}">${icon('speaker-high', { size: 20, filled: true })}</button></div>${said}${revealed}</div>`;
}

export function clozeCard(c, item, state) {
  const { options = [], chosen = -1, verdict = null } = state;
  const gap = clozeFor(item);
  if (!gap) return '';
  const blank =
    chosen >= 0 && options[chosen]
      ? `<span class="recall-blank" data-filled="true">${esc(options[chosen])}</span>`
      : '<span class="recall-blank"></span>';
  const sentence = gap.segments.map((part) => esc(part)).join(blank);
  const rows = options
    .map((text, at) => {
      const tone = verdict === null ? (at === chosen ? 'chosen' : '') : text === item.word ? 'good' : at === chosen ? 'warn' : '';
      return `<button type="button" class="recall-option" data-recall-choose="${at}"${tone ? ` data-tone="${tone}"` : ''}${verdict !== null ? ' disabled' : ''}>${esc(text)}</button>`;
    })
    .join('');
  return `<div class="recall-task recall-task--cloze">${pill(c, 'cloze')}<div class="recall-task__sentence"><span lang="${esc(item.language || '')}">${sentence}</span>${
    meaningOf(item) ? `<span class="recall-task__gloss">${esc(meaningOf(item))}</span>` : ''
  }</div></div><div class="recall-options">${rows}</div>`;
}

/* What the foot offers, which depends only on whether the learner has
   committed: before, the two ways to answer; after, what was recorded and the
   way on. */
export function taskFoot(c, mode, state, recorded) {
  const { verdict = null, typed = '', chosen = -1 } = state;
  if (verdict !== null)
    return `<div class="recall-task__foot">${
      recorded ? `<span class="recall-task__recorded ds-data">${esc(c.recallRecorded)} <b data-tone="${recorded.tone}">${esc(recorded.label)}${recorded.when ? ` · ${esc(recorded.when)}` : ''}</b></span>` : ''
    }<button type="button" class="primary recall-task__on" data-recall-next>${esc(c.nextLine)}</button></div>`;
  if (mode === 'listen_choose')
    return `<div class="recall-task__foot recall-task__foot--quiet"><button type="button" class="quiet" data-recall-unknown>${esc(c.recallDontKnow)}</button></div>`;
  const ready = mode === 'cloze' ? chosen >= 0 : Boolean(String(typed).trim());
  return `<div class="recall-task__foot">${
    mode === 'cloze' ? '' : `<button type="button" class="outline" data-recall-unknown>${esc(c.recallDontKnow)}</button>`
  }<button type="button" class="primary recall-task__on" data-recall-check${ready ? '' : ' disabled'}>${esc(c.recallCheck)}</button></div>`;
}

export function taskCard(c, mode, item, state) {
  if (mode === 'typing') return typingCard(c, item, state);
  if (mode === 'listen_choose') return listenChooseCard(c, item, state);
  if (mode === 'dictation') return dictationCard(c, item, state);
  if (mode === 'cloze') return clozeCard(c, item, state);
  return '';
}

/* The settings sheet the frames "Review settings mobile" and "Review settings
   desktop" draw: two limits and the list of modes. Flashcard says it is always
   on rather than offering a switch that does nothing; speaking is listed
   because the frame lists it, and is not operated here because saying a word
   aloud is the Speaking capability's. */
const SHEET_MODES = [
  ['flashcard', 'recallModeFlashcard'],
  ['typing', 'recallModeTyping'],
  ['listen_choose', 'recallModeListenChoose'],
  ['dictation', 'recallModeDictation'],
  ['cloze', 'recallModeCloze'],
  ['speak', 'recallModeSpeak'],
];

function slider(c, name, label, value, bounds) {
  return `<div class="recall-settings__slider"><div class="recall-settings__row"><span>${esc(label)}</span><span class="ds-data">${esc(value)}</span></div>`
    + `<input type="range" data-recall-setting="${esc(name)}" min="${bounds.min}" max="${bounds.max}" step="${bounds.step}" value="${esc(value)}" aria-label="${esc(label)}"></div>`;
}

export function reviewSettingsSheet(c, settings, bounds) {
  const rows = SHEET_MODES.map(([name, key]) => {
    if (name === 'flashcard')
      return `<div class="recall-settings__mode"><span>${esc(c[key])}</span><span class="recall-settings__always">${esc(c.recallAlwaysOn)}</span></div>`;
    const on = Boolean(settings.modes?.[name]);
    const elsewhere = name === 'speak';
    return `<div class="recall-settings__mode"><span>${esc(c[key])}</span><button type="button" class="recall-switch" role="switch" aria-checked="${on}" data-recall-mode="${esc(name)}"${elsewhere ? ` disabled title="${esc(c.recallModeSpeakElsewhere)}"` : ''}><span></span></button></div>`;
  }).join('');
  return `<div class="recall-settings" role="dialog" aria-modal="true" aria-label="${esc(c.recallSettings)}">`
    + `<button type="button" class="recall-settings__scrim" data-recall-settings-close aria-label="${esc(c.close || c.back)}"></button>`
    + `<section class="recall-settings__sheet"><span class="recall-settings__grab" aria-hidden="true"></span>`
    + `<h2>${esc(c.recallSettings)}</h2>`
    + slider(c, 'newPerDay', c.recallNewPerDay, settings.newPerDay, bounds.newPerDay)
    + slider(c, 'limitPerDay', c.recallLimitPerDay, settings.limitPerDay, bounds.limitPerDay)
    + `<div class="recall-settings__modes"><span class="recall-settings__modes-head">${esc(c.recallModesUsed)}</span>${rows}</div>`
    + `</section></div>`;
}
