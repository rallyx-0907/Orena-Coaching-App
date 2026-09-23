/* The Dictation screen (D-066, D-067), drawn from Orena Listening, "Dictation · Nghe chép"
   (frame "Dictation · result inline" and "Dictation mobile · entry").

   Left: the task - which line of how many, the ask, the line's clip, the pills (hear it again,
   speed, hint level), the shape of the line with a reading under each character, the field and its
   two actions. Right: the result, drawn only once there is one - a ring, what was typed with each
   wrong, missing and extra place marked, the right line, and the way on.

   These are markup builders over `capabilities/dictation-result.js` (one honest source for the
   numbers and the shapes); the behaviour - hearing a line, saving evidence, moving on - stays with
   the encounter that owns the player and the learner's memory. Nothing is drawn that the frame does
   not draw: no empty result panel, no save notice, no reveal. */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { hintTokens } from '../capabilities/dictation-hints.js';
import { verdictOf } from '../capabilities/dictation-result.js';

const fill = (template, values) =>
  Object.entries(values).reduce((text, [key, value]) => text.replaceAll(`{${key}}`, String(value)), String(template));

/* The rail of lines, with the way to the line before and the line after on either side of it. */
export function progressHtml(index, total, c = {}) {
  const segments = Array.from({ length: total }, (_, at) => `<i${at < index ? ' data-done' : ''}></i>`).join('');
  const step = (name, iconName, label) =>
    `<button type="button" class="dz-step" data-${name}-moment aria-label="${esc(label || '')}" data-tip="${esc(label || '')}">${icon(iconName, { size: 18 })}</button>`;
  return `<div class="dz-steps">${step('prev', 'caret-left', c.previousLine)}<div class="dz-progress" role="progressbar" aria-valuemin="1" aria-valuemax="${total}" aria-valuenow="${index}"><span class="dz-progress__segments">${segments}</span><span class="dz-progress__count">${index}/${total}</span></div>${step('next', 'caret-right', c.nextLine)}</div>`;
}

/* The shape of the line (HintRow): revealed characters with their reading beneath; the rest as marks. */
export function shapeHtml(view, language, r) {
  const zh = language === 'zh';
  const cells = view.cells
    .map((cell) => {
      const state = cell.kind === 'shown' ? 'shown' : cell.kind === 'partial' ? 'partial' : 'hidden';
      const reading = zh ? `<small>${esc(cell.kind === 'shown' && cell.reading ? cell.reading : '·')}</small>` : '';
      return `<span class="dz-cell dz-cell--${state}" data-state="${state}"><b>${esc(cell.before || '')}${esc(cell.text)}${esc(cell.after || '')}</b>${reading}</span>`;
    })
    .join('');
  const used = view.level > 0;
  return `<div class="dz-cells" lang="${esc(language)}" role="text" aria-label="${esc(fill(r.dictCharacters, { n: view.charRevealed }))}">${cells}</div><footer class="dz-shape__foot"><span>${esc(fill(r.dictCharactersOf, { n: view.charRevealed, m: view.charTotal }))}</span><span class="dz-shape__note">${esc(used ? r.dictAssisted : r.dictNeverAll)}</span></footer>`;
}

export function hintLevelHtml(view, r) {
  return view.level > 0 ? `${icon('lightbulb', { size: 14, filled: true })}<span>${esc(fill(r.dictHintLevel, { n: view.level, m: view.maxLevel }))}</span>` : '';
}

/* The typed line with each mistake marked as the frame marks it: a wrong character on a red tint
   with a solid underline, an extra one the same and struck through, a missing one a dashed blue chip
   that says so. Each mark is a button: it opens the explanation of the right word. */
export function typedHtml(result, language, r) {
  const parts = result.marks.map((mark, at) => {
    if (mark.kind === 'correct') return esc(mark.from);
    if (mark.kind === 'missing')
      return `<button type="button" class="dz-mark dz-mark--missing" data-mark="${at}" lang="${esc(language)}">${icon('minus-circle', { size: 14 })}<span>${esc(r.dictMissing)} ${esc(mark.to)}</span></button>`;
    return `<button type="button" class="dz-mark dz-mark--${mark.kind}" data-mark="${at}" lang="${esc(language)}" aria-label="${esc(mark.kind === 'wrong' ? `${mark.from} → ${mark.to}` : `${r.dictExtra}: ${mark.from}`)}">${esc(mark.from)}</button>`;
  });
  return parts.join(language === 'zh' ? '' : ' ');
}

/* The right line, with the places the learner missed in bold teal. Units are matched in order to the
   line's own tokens, so punctuation and spacing stay where the line has them. */
export function rightLineHtml(original, result, language) {
  const lit = new Set();
  let unit = 0;
  for (const mark of result.marks) {
    if (mark.to == null) continue;
    if (mark.kind !== 'correct') lit.add(unit);
    unit += 1;
  }
  const tokens = hintTokens(original, language);
  if (tokens.filter((token) => token.word).length !== unit) return esc(original);
  let at = 0;
  return tokens
    .map((token) => {
      if (!token.word) return esc(token.text);
      const light = lit.has(at);
      at += 1;
      return light ? `<mark class="dz-fix">${esc(token.text)}</mark>` : esc(token.text);
    })
    .join('');
}

function verdictText(result, r, language) {
  const verdict = verdictOf(result);
  const title =
    verdict.key === 'exact' ? r.dictVerdictExact : fill(verdict.key === 'close' ? r.dictVerdictClose : r.dictVerdictAgain, { n: verdict.places });
  if (verdict.key === 'exact') return { title, detail: r.dictDetailExact };
  const said = [
    verdict.counts.wrong ? fill(r.dictCountWrong, { n: verdict.counts.wrong }) : '',
    verdict.counts.missing ? fill(r.dictCountMissing, { n: verdict.counts.missing }) : '',
    verdict.counts.extra ? fill(r.dictCountExtra, { n: verdict.counts.extra }) : '',
  ].filter(Boolean);
  const glue = language === 'zh' ? '，' : ', ';
  return { title, detail: `${said.join(glue)}${language === 'zh' ? '。' : '. '}${r.dictTapToUnderstand}` };
}

export function resultHtml({ result, language, r, meaning = '', keep = null, last = false }) {
  const { title, detail } = verdictText(result, r, language);
  return `<div class="dz-result__head"><span class="dz-ring" style="--score:${result.score}%" role="img" aria-label="${esc(`${result.score}%`)}"><span class="dz-ring__text"><b>${result.score}</b><small>${result.correctCount} / ${result.totalCount}</small></span></span><div class="dz-result__copy"><strong>${esc(title)}</strong><p>${esc(detail)}</p></div></div>
<div class="dz-result__body"><section class="dz-block"><span class="dz-label">${esc(r.dictYouTyped)}</span><div class="dz-line dz-line--typed" lang="${esc(language)}">${typedHtml(result, language, r)}</div></section>
<section class="dz-block"><span class="dz-label dz-label--good">${esc(r.dictCorrect)}</span><div class="dz-line dz-line--right" lang="${esc(language)}">${rightLineHtml(result.original, result, language)}</div>${result.originalPinyin ? `<div class="dz-reading">${esc(result.originalPinyin)}</div>` : ''}${meaning ? `<div class="dz-meaning">${esc(meaning)}</div>` : ''}</section>
<div class="dz-next"><button type="button" class="dz-go" data-next-line${last ? ' disabled' : ''}>${icon('arrow-right', { size: 18 })}<span>${esc(r.dictNextLine)}</span></button><button type="button" class="dz-pill dz-pill--raised" data-again>${icon('arrow-counter-clockwise', { size: 18 })}<span>${esc(r.dictTryAgain)}</span></button><button type="button" class="dz-pill dz-pill--raised" data-listen-again>${icon('speaker-high', { size: 18 })}<span>${esc(r.dictReplay)}</span></button><button type="button" class="dz-pill dz-pill--raised" data-keep-line>${icon('bookmark-simple', { size: 18 })}<span>${esc(keep ? fill(r.dictKeepTerm, { term: keep }) : r.dictKeepLine)}</span></button></div></div>`;
}

/* The whole screen, before the learner has typed anything: the top bar, the task, and a result panel
   that is not drawn until there is a result. */
export function screenHtml({ title, level, index, total, kind, range, poster, rate, r, c, ask }) {
  const where = [level, fill(r.dictLine, { i: index, n: total })].filter(Boolean).join(' · ');
  return `<header class="dz-top"><button type="button" class="dz-back" data-exit-practice aria-label="${esc(c.exitPractice)}">${icon('arrow-left', { size: 20 })}<span class="dz-lesson">${esc(title)}</span></button><h2 class="dz-name">${esc(r.dictName)}</h2><small class="dz-where">${esc(where)}</small><span class="dz-streak" title="${esc(r.streakUnmeasured)}">${icon('flame', { size: 16, filled: true })}<b>0</b></span></header>
<div class="dz-cols"><section class="dz-task">${progressHtml(index, total, c)}<h3 class="dz-ask" id="dictateAsk">${esc(ask)}</h3>
<div class="dz-media" data-dz-media><span class="dz-media__art">${poster}</span><span class="dz-glow" aria-hidden="true"></span><button type="button" class="dz-play" data-listen aria-label="${esc(r.dictReplay)}">${icon('play', { size: 38, filled: true })}</button><span class="dz-badge">${icon(kind === 'video' ? 'video-camera' : 'headphones', { size: 14, filled: kind === 'video' })}<span>${esc(kind === 'video' ? r.dictVideo : r.dictAudio)}</span></span><span class="dz-range">${esc(range)}</span><span class="dz-clip"><i data-dz-clip></i></span></div>
<div class="dz-pills"><button type="button" class="dz-pill dz-pill--raised" data-listen>${icon('arrow-counter-clockwise', { size: 14 })}<span>${esc(r.dictReplay)}</span></button><button type="button" class="dz-pill dz-pill--raised" data-dz-rate aria-label="${esc(r.dictSpeed)}">${esc(rate)}×</button><span class="dz-pill dz-pill--hint" data-dz-hint-pill hidden></span></div>
<section class="dz-shape" data-hint-panel></section>
<form class="dz-form"><label class="sr-only" for="reconstruction">${esc(ask)}</label><textarea id="reconstruction" rows="2" autocomplete="off" autocapitalize="off" spellcheck="false" aria-describedby="dictateAsk"></textarea><div class="dz-actions"><button type="button" class="dz-btn dz-btn--glass" data-hint>${icon('lightbulb', { size: 17 })}<span>${esc(r.dictMoreHint)}</span></button><button type="submit" class="dz-btn dz-btn--accent">${icon('check', { size: 17 })}<span>${esc(r.dictCheck)}</span></button></div><p class="dz-status" data-evidence-status role="status"></p></form></section>
<aside class="dz-result" data-dz-result aria-live="polite" hidden></aside></div>`;
}
