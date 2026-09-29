/* The Platform Admin's pure formatters: numbers, durations, dates and the state tone of a status
   word. DOM-free and free of any UI layer, so the old console (admin/format.js re-exports these)
   and the new UI's Admin (screens/admin) read one implementation (D-101 E). */

export function fill(template, values = {}) {
  /* Zero is a value. `values[key] ?? values[key] === 0` reads as "or zero" but
     binds as `(values[key] ?? (values[key] === 0))`, so a 0 short-circuits to
     a falsy 0 and the placeholder survives into the sentence - "{dropped}
     dropped" instead of "0 dropped". Only null and undefined mean unfilled. */
  return String(template ?? '').replace(/\{(\w+)\}/g, (_, key) => (
    values[key] === undefined || values[key] === null ? `{${key}}` : String(values[key])
  ));
}

/* The old console speaks English and Chinese; the new UI speaks Vietnamese as well. */
export function locale(ui) {
  return ui === 'zh' ? 'zh-CN' : ui === 'vi' ? 'vi-VN' : 'en-GB';
}

export const DASH = '—';

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

export function tone(status) {
  const value = String(status || '');
  for (const [name, members] of Object.entries(TONE)) if (members.includes(value)) return name;
  return 'neutral';
}
