/* The coach-notes sheet (AGENT_CONTRACT §10 "the privacy exit"): every note Orena has kept about
   this learner, on this device, with delete - reached at the `preferences.agent_memory` intent
   (agent/intents.js -> Settings, tab=privacy, section=orena). No frame in this pass's set draws an
   entry point for it (D1/E5 read only Orena Home, the Contextual panel and full-screen voice); it
   is built here, exported, and ready for Settings' Plan & privacy tab to open, and the gap is
   recorded in docs/project/UI_BACKEND_GAPS.md rather than given an invented button of its own
   (rule 43 - Settings' own tabs are outside this folder). */
import { openSheet, sheetHead, fillSheet } from '../../kit/overlay.js';
import { html, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { shellCopy } from '../../copy/shell.js';
import { sharedMemory } from './memory-store.js';
import { t } from './copy.js';
import { sortedMemoryNotes, noteKindLabel } from './model.js';

function noteRow(note) {
  return html`<div class="s-orena-mem__row">
    <div class="s-orena-mem__row-head">
      <span class="s-orena-mem__kind">${noteKindLabel(note.kind, t)}</span>
      <button type="button" class="s-orena-mem__del" data-del="${note.id}" aria-label="${t('memoryDeleteLabel')}">${raw(icon('x', { size: 16 }))}</button>
    </div>
    <div class="s-orena-mem__text">${note.text}</div>
    ${note.kind === 'address' ? html`<div class="s-orena-mem__hint">${t('memoryAddressHint')}</div>` : ''}
  </div>`;
}

export async function openAgentMemory() {
  await useStyles('screens/orena/orena.css');
  const memory = sharedMemory();
  let handle = null;

  function paint(sheetEl) {
    const notes = sortedMemoryNotes(memory.notes());
    fillSheet(
      sheetEl,
      handle,
      html`${sheetHead({ title: t('memoryTitle'), closeLabel: shellCopy('close') })}
        <div class="s-orena-mem__body" data-scroll-region>
          <p class="s-orena-mem__intro">${t('memoryIntro')}</p>
          ${notes.length ? notes.map(noteRow) : html`<div class="s-orena-mem__empty">${t('memoryEmpty')}</div>`}
        </div>`,
    );
    sheetEl.querySelectorAll('[data-del]').forEach((button) =>
      button.addEventListener('click', () => {
        memory.removeNote(button.dataset.del);
        paint(sheetEl);
      }),
    );
  }

  handle = openSheet({
    label: t('memoryTitle'),
    className: 's-orena-mem',
    render(element, sheetHandle) {
      handle = sheetHandle;
      paint(element);
      return null;
    },
  });
  return handle;
}
