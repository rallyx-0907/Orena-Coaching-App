/* "Luyện sâu với dòng" (D-066, Orena Listening frame 03 C): everything deeper than hearing
   and asking - dictation, shadowing, reading the line aloud, keeping it, looking closer -
   sits behind one button and opens as a sheet over the workspace, not as a row of controls
   on its front. It is the same floating layer as the Quick Sheet (a popover on a desk, a
   bottom sheet with a scrim on a phone); what it holds is the line and five ways to work
   on it. What each way does stays with the encounter that owns the player and the memory. */
import { esc } from './html.js';
import { icon } from './phosphor.js';

const fill = (template, values) =>
  Object.entries(values).reduce((text, [key, value]) => text.replaceAll(`{${key}}`, String(value)), String(template));

/* name: what the encounter is told; the label and note are the interface language's. */
const WAYS = [
  { name: 'dictation', icon: 'keyboard', label: 'listenDeepDictation', note: 'listenDeepDictationNote' },
  { name: 'shadowing', icon: 'microphone', label: 'listenDeepShadow', note: 'listenDeepShadowNote' },
  { name: 'speaking', icon: 'book-open', label: 'listenDeepRead', note: 'listenDeepReadNote' },
  { name: 'keep', icon: 'bookmark-simple', label: 'listenDeepKeep', note: '' },
  { name: 'inspect', icon: 'magnifying-glass', label: 'listenDeepInspect', note: 'listenDeepInspectNote' },
];

export function lineSheetHtml({ r, c, when, text, language }) {
  const ways = WAYS.map(
    (way) =>
      `<button type="button" class="ls-way" data-way="${way.name}">${icon(way.icon, { size: 20 })}<span class="ls-way__text"><strong>${esc(r[way.label])}</strong>${way.note ? `<small>${esc(r[way.note])}</small>` : ''}</span></button>`,
  ).join('');
  return `<button type="button" class="qs-x" data-way="close" aria-label="${esc(c.quickClose)}">${icon('x', { size: 18 })}</button><span class="ds-label ls-title">${esc(fill(r.listenDeepTitle, { t: when }))}</span><p class="ls-line" lang="${esc(language)}">${esc(text)}</p><div class="ls-ways">${ways}</div>`;
}

export function openLineSheet({ r, c, when, text, language, onPick, onClose = () => {} }) {
  const scrim = document.createElement('div');
  scrim.className = 'qs-scrim';
  const sheet = document.createElement('div');
  sheet.className = 'qs qs--deep';
  sheet.setAttribute('role', 'dialog');
  sheet.setAttribute('aria-modal', 'true');
  sheet.setAttribute('aria-label', fill(r.listenDeepTitle, { t: when }));
  sheet.tabIndex = -1;
  sheet.innerHTML = lineSheetHtml({ r, c, when, text, language });
  document.body.append(scrim, sheet);
  sheet.focus({ preventScroll: true });

  let open = true;
  const close = () => {
    if (!open) return;
    open = false;
    window.removeEventListener('hashchange', close);
    document.removeEventListener('keydown', onKey);
    scrim.remove();
    sheet.remove();
    onClose();
  };
  const onKey = (event) => {
    if (event.key === 'Escape') close();
  };
  scrim.addEventListener('click', close);
  sheet.addEventListener('click', (event) => {
    const way = event.target.closest('[data-way]')?.dataset.way;
    if (!way) return;
    close();
    if (way !== 'close') onPick(way);
  });
  // A sheet must not outlive the screen it was opened from.
  window.addEventListener('hashchange', close);
  document.addEventListener('keydown', onKey);
  return { close };
}
