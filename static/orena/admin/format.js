/* Presentation helpers for the admin console: numbers, dates, state chips,
   dense tables and pagination. Pure string builders, so every view can be
   rendered and checked without a browser.

   A state is always a word with a glyph, never colour alone, and its colour
   comes from a semantic panel token pair in theme.css through `data-tone`. */
import { esc } from '../ui/html.js';
import { hint } from '../ui/patterns.js';

export { esc };

export function fill(template, values = {}) {
  /* Zero is a value. `values[key] ?? values[key] === 0` reads as "or zero" but
     binds as `(values[key] ?? (values[key] === 0))`, so a 0 short-circuits to
     a falsy 0 and the placeholder survives into the sentence - "{dropped}
     dropped" instead of "0 dropped". Only null and undefined mean unfilled. */
  return String(template ?? '').replace(/\{(\w+)\}/g, (_, key) => (
    values[key] === undefined || values[key] === null ? `{${key}}` : String(values[key])
  ));
}

export function locale(ui) {
  return ui === 'zh' ? 'zh-CN' : 'en-GB';
}

const DASH = '—';

export function num(value, ui) {
  if (value === null || value === undefined || value === '' || Number.isNaN(Number(value))) return DASH;
  return new Intl.NumberFormat(locale(ui)).format(Number(value));
}

export function percent(value, ui) {
  if (value === null || value === undefined) return DASH;
  return `${new Intl.NumberFormat(locale(ui), { maximumFractionDigits: 1 }).format(Number(value))}%`;
}

export function latency(value, ui) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return DASH;
  const ms = Number(value);
  return ms < 1000 ? `${num(Math.round(ms), ui)} ms` : `${new Intl.NumberFormat(locale(ui), { maximumFractionDigits: 1 }).format(ms / 1000)} s`;
}

export function duration(value) {
  const total = Math.max(0, Math.round(Number(value || 0) / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = String(total % 60).padStart(2, '0');
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${seconds}` : `${minutes}:${seconds}`;
}

export function bytes(value, ui) {
  const size = Number(value || 0);
  if (size < 1024) return `${num(size, ui)} B`;
  if (size < 1024 * 1024) return `${new Intl.NumberFormat(locale(ui), { maximumFractionDigits: 0 }).format(size / 1024)} KB`;
  return `${new Intl.NumberFormat(locale(ui), { maximumFractionDigits: 1 }).format(size / (1024 * 1024))} MB`;
}

function parse(value) {
  if (!value) return null;
  const stamp = new Date(value);
  return Number.isNaN(stamp.getTime()) ? null : stamp;
}

export function dateShort(value, ui) {
  const stamp = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T00:00:00Z`) : parse(value);
  if (!stamp) return DASH;
  return new Intl.DateTimeFormat(locale(ui), { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(stamp);
}

export function dateTime(value, ui) {
  const stamp = parse(value);
  if (!stamp) return DASH;
  return new Intl.DateTimeFormat(locale(ui), { dateStyle: 'medium', timeStyle: 'short' }).format(stamp);
}

export function relative(value, ui, now = Date.now()) {
  const stamp = parse(value);
  if (!stamp) return DASH;
  const seconds = Math.round((stamp.getTime() - now) / 1000);
  const format = new Intl.RelativeTimeFormat(locale(ui), { numeric: 'auto' });
  const steps = [['day', 86400], ['hour', 3600], ['minute', 60]];
  for (const [unit, size] of steps) {
    if (Math.abs(seconds) >= size) return format.format(Math.round(seconds / size), unit);
  }
  return format.format(0, 'minute');
}

export function languageName(code, t) {
  const value = String(code || '').trim();
  if (!value) return DASH;
  return t[`lang_${value}`] || value.toUpperCase();
}

/* Which panel pairing a state wears. Only these five exist; each is a
   semantic surface/ink pair already checked for contrast in every theme. */
const TONE = {
  ok: ['published', 'ready', 'healthy', 'configured', 'enabled', 'active', 'ok', 'selected', 'imported', 'success', 'saved'],
  warn: ['degraded', 'draft', 'pending_review', 'insufficient', 'demo', 'fallback', 'mismatch', 'transcript_missing', 'warning'],
  bad: ['failed', 'error', 'provider_failure', 'unavailable', 'invalid', 'unreadable', 'deleted', 'index_corrupt', 'index_unreadable', 'critical', 'failure'],
  info: ['processing', 'queued', 'deferred', 'human_gated', 'info'],
};
const GLYPH = { ok: '✓', warn: '!', bad: '✕', info: '•', neutral: '○' };

export function tone(status) {
  const value = String(status || '');
  for (const [name, members] of Object.entries(TONE)) if (members.includes(value)) return name;
  return 'neutral';
}

export function chip(status, t, { label = '', title = '' } = {}) {
  const kind = tone(status);
  const text = label || t[`status_${status}`] || String(status || '').replaceAll('_', ' ') || DASH;
  return `<span class="ac-chip" data-tone="${kind}"${title ? ` title="${esc(title)}"` : ''}><span class="ac-chip__mark" aria-hidden="true">${GLYPH[kind]}</span>${esc(text)}</span>`;
}

export function info(text, label = '') {
  return hint({ text, label: label || text });
}

export function table({ head = [], rows = [], empty = '', caption = '', className = '' }) {
  if (!rows.length) return empty ? `<p class="ac-empty">${esc(empty)}</p>` : '';
  const headRow = head.map((cell) => {
    const spec = typeof cell === 'string' ? { label: cell } : cell;
    return `<th scope="col"${spec.numeric ? ' data-numeric' : ''}${spec.hidden ? ' class="ac-th-hidden"' : ''}>${spec.hidden ? `<span class="sr-only">${esc(spec.label)}</span>` : esc(spec.label)}</th>`;
  }).join('');
  const body = rows.map((row) => {
    // A row that belongs to the one above it - an editor, a detail - spans
    // the whole table rather than squeezing into the first column.
    if (!Array.isArray(row) && row.full !== undefined) {
      return `<tr${row.attributes || ''}><td colspan="${head.length}">${row.full}</td></tr>`;
    }
    const cells = Array.isArray(row) ? row : row.cells;
    const attributes = Array.isArray(row) ? '' : row.attributes || '';
    return `<tr${attributes}>${cells.map((cell, index) => {
      const column = head[index];
      const spec = typeof column === 'string' || !column ? { label: typeof column === 'string' ? column : '' } : column;
      /* Every cell carries its column's name, so a narrow screen can stack the
         row into a card and still say what each value is (canonical study 02:
         the mobile panels are the same data, read vertically). */
      return `<td${spec.numeric ? ' data-numeric' : ''}${spec.label ? ` data-label="${esc(spec.label)}"` : ''}>${cell}</td>`;
    }).join('')}</tr>`;
  }).join('');
  return `<div class="ac-table-wrap"><table class="ac-table${className ? ` ${className}` : ''}">${caption ? `<caption class="sr-only">${esc(caption)}</caption>` : ''}<thead><tr>${headRow}</tr></thead><tbody>${body}</tbody></table></div>`;
}

export function pager({ offset = 0, limit = 25, total = 0 }, t, ui) {
  if (!total) return '';
  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  return `<div class="ac-pager"><span>${esc(fill(t.pageRange, { from: num(from, ui), to: num(to, ui), total: num(total, ui) }))}</span><span class="ac-pager__buttons"><button type="button" class="ac-button" data-page="prev"${offset <= 0 ? ' disabled' : ''}>${esc(t.previous)}</button><button type="button" class="ac-button" data-page="next"${to >= total ? ' disabled' : ''}>${esc(t.next)}</button></span></div>`;
}

export function panel({ title = '', body = '', actions = '', className = '', note = '' }) {
  return `<section class="ac-panel${className ? ` ${className}` : ''}">${title || actions ? `<header class="ac-panel__head">${title ? `<h2>${esc(title)}</h2>` : ''}${actions ? `<div class="ac-panel__actions">${actions}</div>` : ''}</header>` : ''}${note ? `<p class="ac-note">${esc(note)}</p>` : ''}${body}</section>`;
}

export function notice(text, kind = 'neutral') {
  return `<p class="ac-notice" data-tone="${esc(kind)}" role="${kind === 'bad' ? 'alert' : 'status'}">${esc(text)}</p>`;
}

export function kv(rows) {
  return `<dl class="ac-kv">${rows.filter(Boolean).map(([term, value]) => `<div><dt>${esc(term)}</dt><dd>${value}</dd></div>`).join('')}</dl>`;
}

export function select({ name, label, options, value = '', attributes = '' }) {
  return `<label class="ac-field"><span>${esc(label)}</span><select name="${esc(name)}"${attributes}>${options.map(([optionValue, optionLabel]) => `<option value="${esc(optionValue)}"${String(optionValue) === String(value) ? ' selected' : ''}>${esc(optionLabel)}</option>`).join('')}</select></label>`;
}

export function mono(value) {
  return `<code class="ac-code">${esc(value)}</code>`;
}
