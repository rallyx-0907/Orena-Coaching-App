import { annotationSession } from '../product/annotation-session.js';
import { annotatedLine } from './annotated-line.js';
import { esc } from './html.js';
import { openUnderstanding } from './understanding.js';

// Reading composes the same token renderer and explanation as media, without
// manufacturing a playback clock. Each paragraph remains its original source.
export function mountTextLens(passage, controls, ctx, item) {
  const c = ctx.c;
  const lines = [...passage.querySelectorAll('[data-encounter-line]')];
  const segments = lines.map((line, index) => ({
    segment_id: String(index), original_text: (item.paragraphs || [item.text])[index],
  }));
  const alive = () => passage.isConnected && ctx.alive();
  const annotations = annotationSession({request: ctx.api.annotateMediaText,
    language: ctx.language, alive});
  let enabled = false;
  controls.innerHTML = `<button type="button" class="outline" data-text-lens-toggle aria-pressed="false">${esc(c.lookCloser)}</button><p class="word-legend" hidden><span data-role="noun">${esc(c.wordThings)}</span> · <span data-role="verb">${esc(c.wordActions)}</span> · <span data-role="detail">${esc(c.wordDetails)}</span></p><p class="meta" role="status" data-text-lens-status></p>`;
  const toggle = controls.querySelector('button');
  const output = controls.querySelector('[role=status]');
  const render = () => {
    if (!alive()) return;
    let ready = 0;
    lines.forEach((line, index) => {
      const html = enabled ? annotatedLine(segments[index], annotations.values.get(String(index)), {
        pinyin: ctx.profile.pinyin !== 'off',
        labels: { noun: c.wordThings, verb: c.wordActions, detail: c.wordDetails },
      }) : null;
      if (html) ready++;
      line.innerHTML = html || esc(segments[index].original_text).replace(/\n/g, '<br>');
      line.dataset.closeLookState = html ? 'on' : 'off';
    });
    output.textContent = !enabled ? '' : annotations.pending.size ? c.closeLookLoading
      : ready === lines.length ? c.closeLookHelp : c.closeLookUnavailable;
    controls.querySelector('.word-legend').hidden = !enabled || ready === 0;
  };
  toggle.onclick = () => {
    enabled = !enabled;
    toggle.setAttribute('aria-pressed', String(enabled));
    if (enabled) for (const segment of segments) {
      if (annotations.values.get(segment.segment_id) === null) annotations.retry(segment.segment_id);
      void annotations.load(segment).then(() => { if (enabled) render(); });
    }
    render();
  };
  passage.addEventListener('click', (event) => {
    const token = event.target.closest('[data-token]');
    if (!token || !passage.contains(token)) return;
    const line = token.closest('[data-encounter-line]');
    const index = lines.indexOf(line);
    if (index < 0) return;
    openUnderstanding(ctx, { selection: token.dataset.token,
      context: segments[index].original_text, title: item.title,
      origin: { id: item.id, where: item.title, why: 'from_reading' } });
  });
  return { clear() { enabled = false; toggle.setAttribute('aria-pressed', 'false'); render(); } };
}
