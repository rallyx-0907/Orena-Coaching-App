/* The word, heard where it is actually said.
 *
 * The canonical frames "Vocabulary context clips" (06) and "Vocabulary context
 * clips mobile" (07): the word's own head with how many clips there are, the
 * clip playing, what is said in it - the line, its reading, its meaning - the
 * two things worth doing with it, and the other places it is said.
 *
 * Every clip is a real moment in real media, so a word the catalogue has never
 * said has no clips and this screen is not reached for it.
 */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { contentCover } from './cover.js';

/* The word picked out inside the line it was said in, and inside its reading.
   Split rather than replaced, so nothing in a transcript can be markup. */
function inLine(text, word, className) {
  const at = String(text).toLowerCase().indexOf(String(word).toLowerCase());
  if (!word || at < 0) return esc(text);
  return `${esc(text.slice(0, at))}<span class="${className}">${esc(text.slice(at, at + word.length))}</span>${esc(text.slice(at + word.length))}`;
}

function clock(seconds) {
  const whole = Math.max(0, Number(seconds) || 0);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}

function otherClip(c, clip, index) {
  return `<button type="button" class="clip-row" data-clip-play="${index}"><span class="clip-row__art">${contentCover(
    { id: String(clip.lessonId || ''), title: clip.title || '', material: 'listening' },
  )}<span class="clip-row__go">${icon('play', { size: 18, filled: true })}</span><span class="clip-row__len ds-data">${esc(clock(clip.seconds))}</span></span><span class="clip-row__text"><span class="clip-row__where ds-data">${esc(clip.title)} · ${esc(clip.at)}</span><span class="clip-row__line">${esc(clip.text)}</span></span></button>`;
}

export function wordClipsHtml(c, state) {
  const { word = '', reading = '', clips = [], at = 0, playing = false, speed = 1, language = '', busy = false } = state;
  const clip = clips[at];
  if (!clip)
    return `<section class="word-clips"><header class="word-clips__head"><button type="button" class="icon-button" data-clips-back aria-label="${esc(c.back)}">${icon('caret-right', { size: 22, className: 'is-flipped' })}</button><strong class="word-clips__word" lang="${esc(language)}">${esc(word)}</strong></header><p class="word-clips__none">${esc(
      busy ? c.loading : c.vocabularyNoClips,
    )}</p></section>`;
  const others = clips.map((item, index) => [item, index]).filter(([, index]) => index !== at);
  return `<section class="word-clips"><header class="word-clips__head"><button type="button" class="icon-button" data-clips-back aria-label="${esc(c.back)}">${icon('caret-right', { size: 22, className: 'is-flipped' })}</button><strong class="word-clips__word" lang="${esc(language)}">${esc(word)}</strong>${
    reading ? `<span class="word-clips__reading ds-data">${esc(reading)}</span>` : ''
  }<span class="word-clips__count ds-data">${esc(String(c.vocabularyClipCount).replace('{n}', String(clips.length)))}</span></header><div class="word-clips__stage"><div class="word-clips__screen">${contentCover(
    { id: String(clip.lessonId || ''), title: clip.title || '', material: 'listening' },
  )}<button type="button" class="word-clips__play" data-clip-toggle aria-pressed="${playing}" aria-label="${esc(playing ? c.pause : c.play)}">${icon(playing ? 'pause' : 'play', { size: 26, filled: true })}</button><span class="word-clips__where ds-data">${icon('video-camera', { size: 12, filled: true })}${esc(clip.title)} · ${esc(clip.at)}</span><button type="button" class="word-clips__speed ds-data" data-clip-speed>${esc(speed === 1 ? '1×' : '0.75×')}</button></div><div class="word-clips__said"><span class="word-clips__line" lang="${esc(language)}">${inLine(
    clip.text,
    word,
    'word-clips__mark',
  )}</span>${clip.pinyin ? `<span class="word-clips__reading-line ds-data">${inLine(clip.pinyin, '', 'word-clips__mark-ink')}</span>` : ''}${
    clip.translation ? `<span class="word-clips__meaning">${esc(clip.translation)}</span>` : ''
  }</div><div class="word-clips__actions"><button type="button" class="clip-action" data-clip-again>${icon('repeat', { size: 16 })}<span>${esc(c.recallPlayAgain)}</span></button><button type="button" class="clip-action" data-clip-open="${esc(clip.lessonId)}">${icon('arrow-square-out', { size: 16 })}<span>${esc(c.vocabularyOpenClip)}</span></button></div>${
    others.length
      ? `<div class="word-clips__rule" aria-hidden="true"></div><span class="ds-label word-clips__label">${esc(c.vocabularyOtherContexts)}</span><div class="word-clips__others">${others
          .map(([item, index]) => otherClip(c, item, index))
          .join('')}</div>`
      : ''
  }</div></section>`;
}
