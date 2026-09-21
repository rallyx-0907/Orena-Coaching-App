/* The Dictation screen (D-066): its own screen, not a panel beside the player.

   Left: the task - which line of how many, the ask, the line's clip, the pills (hear it
   again, speed, hint level), the shape of the line with a reading under each character,
   the field and its two actions. Right: the result - a ring, what was typed with the
   wrong, missing and extra places marked, the right line, and the way on.

   These are markup builders over `capabilities/dictation-result.js` (one honest source
   for the numbers and the shapes); the behaviour - hearing a line, saving evidence,
   moving on - stays with the encounter that owns the player and the learner's memory. */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { hintTokens } from '../capabilities/dictation-hints.js';
import { verdictOf } from '../capabilities/dictation-result.js';

const fill = (template, values) =>
  Object.entries(values).reduce((text, [key, value]) => text.replaceAll(`{${key}}`, String(value)), String(template));

export function progressHtml(index, total) {
  const segments = Array.from({ length: total }, (_, at) => `<i${at < index ? ' data-done' : ''}></i>`).join('');
  return `<div class="dz-progress" role="progressbar" aria-valuemin="1" aria-valuemax="${total}" aria-valuenow="${index}"><span class="dz-progress__segments">${segments}</span><span class="dz-progress__count">${index}/${total}</span></div>`;
}

/* The shape of the line: revealed characters with their reading beneath; the rest as marks. */
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
  return `<div class="dz-cells" lang="${esc(language)}" role="text" aria-label="${esc(fill(r.dictCharacters, { n: view.charRevealed }))}">${cells}</div><footer class="dz-shape__foot"><span class="ds-data">${esc(fill(r.dictCharactersOf, { n: view.charRevealed, m: view.charTotal }))}</span><span class="dz-shape__note">${esc(used ? r.dictAssisted : r.dictNeverAll)}</span></footer>`;
}

export function hintLevelHtml(view, r) {
  return view.level > 0 ? `${icon('lightbulb', { size: 14 })}<span>${esc(fill(r.dictHintLevel, { n: view.level, m: view.maxLevel }))}</span>` : '';
}

/* The typed line with each mistake marked by shape as well as colour: a wrong or extra
   character is underlined, a missing one is a small chip that says so. Each mark is a
   button: it opens the explanation of the right word. */
export function typedHtml(result, language, r) {
  const parts = result.marks.map((mark, at) => {
    if (mark.kind === 'correct') return esc(mark.from);
    if (mark.kind === 'missing')
      return `<button type="button" class="dz-mark dz-mark--missing" data-mark="${at}" lang="${esc(language)}">${icon('minus-circle', { size: 13 })}<span>${esc(r.dictMissing)}</span> <b>${esc(mark.to)}</b></button>`;
    return `<button type="button" class="dz-mark dz-mark--${mark.kind}" data-mark="${at}" lang="${esc(language)}" aria-label="${esc(mark.kind === 'wrong' ? `${mark.from} → ${mark.to}` : `${r.dictExtra}: ${mark.from}`)}">${esc(mark.from)}</button>`;
  });
  const spaced = language === 'zh' ? '' : ' ';
  return parts.join(spaced);
}

/* The right line, with the places the learner missed lit. Units are matched in order to
   the line's own tokens, so punctuation and spacing stay where the line has them. */
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
  return `<div class="dz-result__head"><span class="dz-ring" style="--score:${result.score}%" role="img" aria-label="${esc(`${result.score}%`)}"><b>${result.score}</b><small class="ds-data">${result.correctCount} / ${result.totalCount}</small></span><div class="dz-result__copy"><strong>${esc(title)}</strong><p>${esc(detail)}</p></div></div>
<section class="dz-block"><span class="ds-label">${esc(r.dictYouTyped)}</span><div class="dz-line dz-line--typed" lang="${esc(language)}">${typedHtml(result, language, r)}</div></section>
<section class="dz-block"><span class="ds-label ds-label--good">${esc(r.dictCorrect)}</span><div class="dz-line dz-line--right" lang="${esc(language)}">${rightLineHtml(result.original, result, language)}</div>${result.originalPinyin ? `<p class="dz-reading" lang="zh-Latn-pinyin">${esc(result.originalPinyin)}</p>` : ''}${meaning ? `<p class="dz-meaning">${esc(meaning)}</p>` : ''}</section>
<div class="dz-next"><button type="button" class="primary" data-next-line${last ? ' disabled' : ''}>${icon('arrow-right', { size: 15 })}<span>${esc(r.dictNextLine)}</span></button><button type="button" class="dz-pill" data-again>${icon('arrow-counter-clockwise', { size: 15 })}<span>${esc(r.dictTryAgain)}</span></button><button type="button" class="dz-pill" data-listen-again>${icon('speaker-high', { size: 15 })}<span>${esc(r.dictReplay)}</span></button><button type="button" class="dz-pill" data-keep-line>${icon('bookmark-simple', { size: 15 })}<span>${esc(keep ? fill(r.dictKeepTerm, { term: keep }) : r.dictKeepLine)}</span></button></div>`;
}

/* The whole screen, before the learner has typed anything. */
export function screenHtml({ title, level, index, total, kind, range, poster, rate, r, c, ask }) {
  const where = [level, fill(r.dictLine, { i: index, n: total })].filter(Boolean).join(' · ');
  return `<header class="dz-top"><button type="button" class="dz-back" data-exit-practice aria-label="${esc(c.exitPractice)}">${icon('arrow-left', { size: 18 })}<span class="dz-lesson">${esc(title)}</span></button><h2 class="dz-name">${esc(r.dictName)}</h2><small class="dz-where">${esc(where)}</small><span class="dz-streak" title="${esc(r.streakUnmeasured)}">${icon('fire', { size: 14, filled: true })}<b>0</b></span></header>
<div class="dz-cols"><section class="dz-task">${progressHtml(index, total)}<h3 class="dz-ask" id="dictateAsk">${esc(ask)}</h3>
<div class="dz-media" data-dz-media><span class="dz-media__art">${poster}</span><span class="dz-badge">${icon(kind === 'video' ? 'video-camera' : 'headphones', { size: 13 })}<span>${esc(kind === 'video' ? r.dictVideo : r.dictAudio)}</span></span><span class="dz-range ds-data">${esc(range)}</span><button type="button" class="dz-play" data-listen aria-label="${esc(r.dictReplay)}">${icon('play', { size: 26, filled: true })}</button><span class="dz-clip"><i data-dz-clip></i></span></div>
<div class="dz-pills"><button type="button" class="dz-pill" data-listen>${icon('arrow-counter-clockwise', { size: 14 })}<span>${esc(r.dictReplay)}</span></button><button type="button" class="dz-pill" data-dz-rate aria-label="${esc(r.dictSpeed)}">${esc(rate)}×</button><span class="dz-pill dz-pill--hint" data-dz-hint-pill hidden></span></div>
<section class="dz-shape" data-hint-panel></section>
<form class="dz-form"><label class="sr-only" for="reconstruction">${esc(ask)}</label><textarea id="reconstruction" rows="3" placeholder="${esc(r.dictPlaceholder)}" autocomplete="off" autocapitalize="off" spellcheck="false" aria-describedby="dictateAsk"></textarea><div class="dz-actions"><button type="button" class="dz-hintbtn" data-hint>${icon('lightbulb', { size: 16 })}<span>${esc(r.dictMoreHint)}</span></button><button type="submit" class="primary dz-check">${icon('check', { size: 16 })}<span>${esc(r.dictCheck)}</span></button></div><p class="notice dz-status" data-evidence-status role="status"></p></form></section>
<aside class="dz-result" data-dz-result aria-live="polite"><p class="dz-empty">${esc(r.dictResultHere)}</p></aside></div>`;
}
