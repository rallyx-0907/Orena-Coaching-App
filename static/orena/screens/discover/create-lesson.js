/* Discover's "Create lesson" card (pinned design 2026-10-15, `[data-screen-label="Create lesson"]` in the Discover
   frame): the one place a learner brings their own content in. It replaces the header's "+ Import". Four kinds in a
   segmented tablist - link / video, text, document, audio - each with the one field it needs, one "Create lesson"
   button and three hint chips naming what the kind accepts.

   Create hands what was entered to the Import sheet (screens/import/sheet.js `initial`), which is where the real
   work and its honest states live: a link starts the import, text opens the text step filled in, an audio/video file
   is sent to the upload route. Document files have no route on the backend (UI_BACKEND_GAPS "Create lesson"), so that
   tab says so, as the design's own handler does for the kinds it does not build.

   The markup is DOM-free (`createLessonMarkup`) so scripts/test_orena_screen_discover.mjs can render it. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { toast } from '../../kit/toast.js';
import { langAttr } from '../../kit/lang.js';

export const LESSON_TABS = Object.freeze([
  { id: 'link', labelKey: 'lessonTabLink', icon: 'link' },
  { id: 'text', labelKey: 'lessonTabText', icon: 'file-text' },
  { id: 'file', labelKey: 'lessonTabFile', icon: 'file' },
  { id: 'audio', labelKey: 'lessonTabAudio', icon: 'audio-lines' },
]);

/* What each kind accepts, as the design's three chips. `key` is a translated word; `label` is a format name that is the
   same in every language. `tone` is one of tokens.css's hue tokens (the design's literal hexes, mapped to the nearest). */
export const LESSON_HINTS = Object.freeze({
  link: [
    { label: 'YouTube', tone: 'skill-speak', icon: 'play' },
    { key: 'lessonHintWebsite', tone: 'skill-grammar', icon: 'globe' },
    { label: 'MP4', tone: 'gcat-2', icon: 'film' },
  ],
  text: [
    { key: 'lessonHintArticle', tone: 'skill-grammar', icon: 'file-text' },
    { key: 'lessonHintEmail', tone: 'skill-read', icon: 'mail' },
    { key: 'lessonHintNotes', tone: 'gcat-4', icon: 'notepad-text' },
  ],
  file: [
    { label: 'PDF', tone: 'skill-speak', icon: 'file-text' },
    { label: 'EPUB', tone: 'gcat-4', icon: 'book' },
    { label: 'DOCX', tone: 'skill-grammar', icon: 'file-text' },
  ],
  audio: [
    { label: 'MP3', tone: 'gcat-2', icon: 'music' },
    { label: 'M4A', tone: 'skill-read', icon: 'music' },
    { key: 'lessonHintPodcast', tone: 'skill-speak', icon: 'mic' },
  ],
});

/* The design's own spark mark (an artwork glyph, like the Credits spark - not a Lucide icon). */
const SPARK = '<svg width="30" height="30" viewBox="0 0 32 32" class="s-ic__spark" aria-hidden="true">'
  + '<path class="s-ic__spark-a" d="M13 3c.8 6.3 4 9.5 10.3 10.3C17 14.1 13.8 17.3 13 23.6 12.2 17.3 9 14.1 2.7 13.3 9 12.5 12.2 9.3 13 3z"></path>'
  + '<path class="s-ic__spark-b" d="M24.5 3c.3 2.2 1.3 3.2 3.5 3.5-2.2.3-3.2 1.3-3.5 3.5-.3-2.2-1.3-3.2-3.5-3.5 2.2-.3 3.2-1.3 3.5-3.5z"></path>'
  + '<path class="s-ic__spark-c" d="M25 19.5c.3 2.2 1.3 3.2 3.5 3.5-2.2.3-3.2 1.3-3.5 3.5-.3-2.2-1.3-3.2-3.5-3.5 2.2-.3 3.2-1.3 3.5-3.5z"></path></svg>';
const SPARK_SMALL = SPARK.replace('width="30" height="30"', 'width="20" height="20"').replace('s-ic__spark"', 's-ic__spark s-ic__spark--btn"');

export function createLessonMarkup(state, { t, language }) {
  const tab = state.tab;
  const field = tab === 'link'
    ? html`<label class="s-ic__field">${raw(icon('link', { size: 18 }))}<input type="text" inputmode="url" autocomplete="off" autocapitalize="off" spellcheck="false" data-lesson-url value="${state.url}" placeholder="${t('lessonLinkPlaceholder')}" aria-label="${t('lessonTabLink')}"></label>`
    : tab === 'text'
      ? html`<textarea class="s-ic__text" data-lesson-text rows="3" maxlength="12000" lang="${langAttr(language)}" placeholder="${t('lessonTextPlaceholder')}" aria-label="${t('lessonTabText')}">${state.text}</textarea>`
      : html`<button type="button" class="s-ic__drop" data-lesson-drop>${raw(icon('upload', { size: 18 }))}<span>${t(tab === 'audio' ? 'lessonDropAudio' : 'lessonDropFile')}</span></button>`;
  return html`<div class="s-ic" data-lesson-card data-screen-label="Create lesson">
    <svg class="s-ic__watermark" aria-hidden="true" viewBox="0 0 100 100"><use href="#ol-intel"></use></svg>
    <div class="s-ic__head">
      <div class="s-ic__tile">${raw(SPARK)}</div>
      <div class="s-ic__titles">
        <div class="s-ic__titlerow"><h2 class="s-ic__title">${t('lessonTitle')}</h2><span class="s-ic__badge"><svg width="14" height="14" viewBox="0 0 100 100" aria-hidden="true"><use href="#ol-intel"></use></svg>Orena Intelligence</span></div>
        <p class="s-ic__sub">${t('lessonSub')}</p>
      </div>
    </div>
    <div class="s-ic__tabs" role="tablist">
      ${LESSON_TABS.map((item) => html`<button type="button" class="s-ic__tab" role="tab" aria-selected="${tab === item.id ? 'true' : 'false'}" data-lesson-tab="${item.id}">${raw(icon(item.icon, { size: 16 }))}<span>${t(item.labelKey)}</span></button>`)}
    </div>
    <div class="s-ic__row">
      ${field}
      <button type="button" class="s-ic__create" data-lesson-create>${t('lessonCreate')}${raw(SPARK_SMALL)}</button>
    </div>
    <div class="s-ic__hints">
      ${LESSON_HINTS[tab].map((hint) => html`<span class="s-ic__hint"><span class="s-ic__hint-mark" style="background:var(--${hint.tone})">${raw(icon(hint.icon, { size: 12, stroke: 2.4 }))}</span>${hint.key ? t(hint.key) : hint.label}</span>`)}
    </div>
    <input type="file" accept="audio/*,video/*" data-lesson-file hidden>
  </div>`;
}

/* Mounts the card into `host`. `open(initial)` opens the Import sheet with what was entered. */
export function mountCreateLesson(host, { t, language, open }) {
  const state = { tab: 'link', url: '', text: '' };

  function chooseFile() {
    host.querySelector('[data-lesson-file]')?.click();
  }

  function create() {
    if (state.tab === 'link') {
      const url = state.url.trim();
      if (!url) { toast(t('lessonLinkFirst'), { iconName: 'circle-alert' }); return; }
      open({ source: 'url', url });
    } else if (state.tab === 'text') {
      const text = state.text.trim();
      if (!text) { toast(t('lessonTextFirst'), { iconName: 'circle-alert' }); return; }
      open({ source: 'text', text: state.text });
    } else if (state.tab === 'audio') {
      chooseFile();
    } else {
      toast(t('lessonDocumentSoon'), { iconName: 'circle-alert' });
    }
  }

  function paint(focus = '') {
    mount(host, createLessonMarkup(state, { t, language }));
    host.querySelectorAll('[data-lesson-tab]').forEach((button) => {
      button.addEventListener('click', () => {
        state.tab = button.dataset.lessonTab;
        paint(`[data-lesson-tab="${state.tab}"]`);
      });
    });
    const url = host.querySelector('[data-lesson-url]');
    url?.addEventListener('input', () => { state.url = url.value; });
    url?.addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); create(); } });
    const text = host.querySelector('[data-lesson-text]');
    text?.addEventListener('input', () => { state.text = text.value; });
    host.querySelector('[data-lesson-create]').addEventListener('click', create);

    const drop = host.querySelector('[data-lesson-drop]');
    const file = host.querySelector('[data-lesson-file]');
    const send = (chosen) => {
      if (!chosen) return;
      if (state.tab !== 'audio') { toast(t('lessonDocumentSoon'), { iconName: 'circle-alert' }); return; }
      open({ source: 'file', file: chosen });
    };
    drop?.addEventListener('click', () => (state.tab === 'audio' ? chooseFile() : toast(t('lessonDocumentSoon'), { iconName: 'circle-alert' })));
    drop?.addEventListener('dragover', (event) => event.preventDefault());
    drop?.addEventListener('drop', (event) => { event.preventDefault(); send(event.dataTransfer?.files?.[0]); });
    file?.addEventListener('change', () => { send(file.files?.[0]); file.value = ''; });
    if (focus) host.querySelector(focus)?.focus();
  }

  paint();
  return { paint };
}
