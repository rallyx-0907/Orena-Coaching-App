/* History (D-059 Phase 4, D-060) - "History · secondary by design": the last
   thirty days of the learner's own work, grouped by day, one row per piece:
   the domain's icon, what it was, and its result where one was recorded.

   Read from the owners that already hold the work - writing reviews, reading
   sessions, speaking takes, practice outcomes - and never merged into a new
   store. A result is shown only where the owner recorded one: a speaking take
   has no score until a recogniser is configured (GAP-021), so its row carries
   none rather than a number that was never measured. */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { refCopy } from './reference.js';
import { link } from '../product/intent.js';

const WINDOW_DAYS = 30;
const DOMAIN = {
  writing: ['writing', 'pencil-simple'],
  reading: ['reading', 'book-open'],
  speaking: ['speaking', 'microphone'],
  dictation: ['dictation', 'keyboard'],
  listening: ['listening', 'headphones'],
  vocabulary: ['vocabulary', 'cards'],
};

const firstLine = (text) => String(text || '').split('\n')[0].trim();
const clip = (text, n = 60) => (text.length > n ? `${text.slice(0, n - 1)}…` : text);

function rows(ctx, results) {
  const r = refCopy(ctx);
  const [essays, reading, speaking, outcomes] = results;
  const out = [];
  if (essays.status === 'fulfilled')
    for (const e of Array.isArray(essays.value) ? essays.value : essays.value.items || [])
      out.push({
        at: e.created_at,
        kind: 'writing',
        title: `${r.writing} · ${clip(firstLine(e.prompt) || r.writing)}`,
        meta: e.revision_no ? r.historyVersion.replace('{n}', e.revision_no) : '',
        score: Number.isFinite(Number(e.overall)) ? String(Math.round(Number(e.overall))) : '',
        href: link('expression', { id: `essay:${e.id}` }),
      });
  if (reading.status === 'fulfilled')
    for (const s of reading.value.items || [])
      out.push({
        at: s.created_at,
        kind: 'reading',
        title: `${r.reading} · ${clip(s.title || '')}`,
        meta: Number.isFinite(Number(s.total)) ? r.historyAnswered.replace('{n}', s.correct_count).replace('{t}', s.total) : '',
        score: '',
        href: link('encounter', { id: `article:${s.article_id}`, intent: 'reading' }),
      });
  if (speaking.status === 'fulfilled')
    for (const a of speaking.value.items || []) {
      const scored = Number(a.dimensions?.pronunciation);
      out.push({
        at: a.created_at,
        kind: 'speaking',
        title: `${r.speaking} · ${clip(a.transcript_text || '')}`,
        meta: '',
        score: Number.isFinite(scored) && a.dimensions?.pronunciation !== null ? String(Math.round(scored)) : '',
        href: link('practice', { intent: 'speaking' }),
      });
    }
  if (outcomes.status === 'fulfilled')
    for (const o of outcomes.value.items || []) {
      const kind = DOMAIN[o.intent || o.kind] ? o.intent || o.kind : 'dictation';
      const score = Number(o.accuracy_percent ?? o.score);
      out.push({
        at: o.observed_at || o.created_at || o.at,
        kind,
        title: `${r[kind] || kind} · ${clip(o.title || o.source_title || '')}`,
        meta: '',
        score: Number.isFinite(score) ? String(Math.round(score)) : '',
        href: o.source_id ? link('encounter', { id: o.source_id, intent: o.intent || null }) : link(),
      });
    }
  const since = Date.now() - WINDOW_DAYS * 86400000;
  return out
    .filter((x) => x.at && Date.parse(x.at) >= since)
    .sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
}

function dayLabel(ctx, at) {
  const r = refCopy(ctx);
  const date = new Date(at);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) return r.historyToday;
  const locale = ctx.ui === 'zh' ? 'zh-CN' : ctx.ui === 'vi' ? 'vi-VN' : 'en-GB';
  return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short' }).format(date);
}

export async function renderHistory(root, ctx) {
  const c = ctx.c;
  const r = refCopy(ctx);
  const head = `<header class="history-head"><a class="icon-button history-back" href="${esc(link('progress'))}" aria-label="${esc(r.progress)}">${icon('caret-right', { size: 18, className: 'is-flipped' })}</a><h1>${esc(r.historyTitle)}</h1><span class="history-window ds-label">${esc(r.historyWindow)}</span></header>`;
  root.innerHTML = `<section class="history-page">${head}<div class="history-list" aria-busy="true">${Array.from({ length: 4 }, () => '<span class="skeleton history-skeleton"></span>').join('')}</div></section>`;
  const results = await Promise.allSettled([ctx.api.essays(), ctx.api.readingEvidence(30), ctx.api.speakingAttempts(30), ctx.api.practiceOutcomes(30)]);
  if (!ctx.alive()) return;
  const list = rows(ctx, results);
  const failed = results.filter((x) => x.status === 'rejected').length;
  let body = '';
  let current = '';
  for (const row of list) {
    const day = dayLabel(ctx, row.at);
    if (day !== current) {
      current = day;
      body += `<h2 class="history-day ds-label">${esc(day)}</h2>`;
    }
    const [domain, glyph] = DOMAIN[row.kind] || ['neutral', 'clock'];
    body += `<a class="history-row" href="${esc(row.href)}" data-domain="${domain}"><span class="history-row__icon">${icon(glyph, { size: 18 })}</span><span class="history-row__text"><strong>${esc(row.title)}</strong>${row.meta ? `<small>${esc(row.meta)}</small>` : ''}</span>${row.score ? `<span class="history-row__score">${esc(row.score)}</span>` : ''}</a>`;
  }
  const degraded = failed
    ? `<div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 20 })}<div><strong>${esc(c.growthPartialNote || c.unavailable)}</strong></div></div>`
    : '';
  root.innerHTML = `<section class="history-page">${head}${degraded}<div class="history-list">${body || `<div class="state-panel state-panel--empty">${icon('clock-counter-clockwise', { size: 22 })}<div><strong>${esc(r.historyEmpty)}</strong></div></div>`}</div></section>`;
  return () => {};
}
