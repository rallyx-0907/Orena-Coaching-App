/* Compare Versions (frame 19, `#/write/:id/compare`; D-091): the earlier draft beside the
   revised one, the words that changed marked in each, a legend of what changed and how the
   grammar score and the estimated range moved. Reached only from the Writing screen's "Compare
   versions" button (itself only shown once a second revision exists).

   Real data: `GET /api/essays/{id}/revision` (RevisionCompare) for the diff itself, `GET
   /api/essays/{id}` for the prompt, the versions' dates and the revised range, and the same for
   the earlier version (its id is in the series list) for the range it started from.

   A learning workspace (rule 49) although the frame draws a page: each draft card and the legend
   scroll inside themselves and nothing scrolls the page. On a phone the frame stacks the two
   drafts and the legend under one Earlier/Revised tab; the legend keeps its place in that order
   and, when it is long, scrolls in its own region. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { langAttr } from '../../kit/lang.js';
import { shellCopy as s } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { whenLabel } from '../writing/model.js';
import { t } from './copy.js';
import { mapCompare, legendRows, earlierSegments, revisedSegments, revisionIdOf } from './model.js';

function diffMarkup(segments) {
  return segments.map((seg) => (seg.tone === 'plain' ? html`${seg.text}` : html`<span class="s-wrc__diff s-wrc__diff--${seg.tone}">${seg.text}</span>`));
}

export default async function mountWritingCompare(element, ctx) {
  await useStyles('screens/writing-compare/writing-compare.css');
  const language = ctx.context?.language || 'en';
  const locale = languages().ui;
  const id = ctx.params?.id;

  const [detail, revision] = await Promise.all([api.essay(id), api.essayRevision(id)]);
  if (!ctx.isCurrent()) return undefined;
  const earlierId = revisionIdOf(detail, revision?.previous?.version);
  const earlier = earlierId ? await api.essay(earlierId).catch(() => null) : null;
  if (!ctx.isCurrent()) return undefined;
  const compare = mapCompare(detail, revision, earlier);
  if (!compare) throw new Error(`Compare Versions: no comparison for essay ${id}`);

  ctx.setCrumb(s('compareVersions'));

  // The frame opens on the revised version (`cvTab: "b"`): the current words first.
  let activePane = 'revised';
  const label = (version) => {
    const when = whenLabel(version.createdAt, locale);
    return when ? t('versionLabel', { n: version.version, when }) : t('versionBare', { n: version.version });
  };

  function legendMarkup() {
    const rows = legendRows(compare);
    const names = { fixed: 'fixedLabel', remaining: 'remainingLabel', added: 'newLabel' };
    return html`<div class="s-wrc__legendcol" data-scroll-region>
      <div class="s-wrc__coltitle">${t('changesHeader')}</div>
      ${rows.map(
        (row) => html`<div class="s-wrc__legendcard">
          <div class="s-wrc__legendhead"><span style="color:${row.color}">${t(names[row.key])}</span><b>${row.n}</b></div>
          <div class="s-wrc__legenditems" lang="${langAttr(language)}">${row.items}</div>
        </div>`,
      )}
      ${
        compare.grammar || compare.range
          ? html`<div class="s-wrc__legendcard s-wrc__delta">${compare.grammar ? html`${t('gramWord')} <b>${compare.grammar.from} → ${compare.grammar.to}</b>` : ''}${compare.grammar && compare.range ? ' · ' : ''}${compare.range ? html`${t('rangeWord')} <b>${compare.range.from} → ${compare.range.to}</b>` : ''}</div>`
          : ''
      }
    </div>`;
  }

  function paint() {
    mount(
      element,
      html`<section class="s-wrc__root" data-active-pane="${activePane}">
        <div class="s-wrc__header">
          <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${s('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
          <div class="s-wrc__title">
            <div class="s-wrc__title-text">${s('compareVersions')}</div>
            ${compare.prompt ? html`<div class="s-wrc__title-meta" lang="${langAttr(language)}">${compare.prompt}</div>` : ''}
          </div>
        </div>
        <div class="s-wrc__tabs">
          <button type="button" class="s-wrc__tab" data-tab="earlier" aria-selected="${activePane === 'earlier'}">${t('earlierTab')}</button>
          <button type="button" class="s-wrc__tab" data-tab="revised" aria-selected="${activePane === 'revised'}">${t('revisedTab')}</button>
        </div>
        <div class="s-wrc__grid">
          <div class="s-wrc__col s-wrc__col--earlier">
            <div class="s-wrc__collabel">${label(compare.previous)}</div>
            <div class="s-wrc__card" data-scroll-region lang="${langAttr(language)}">${diffMarkup(earlierSegments(compare))}</div>
          </div>
          ${legendMarkup()}
          <div class="s-wrc__col s-wrc__col--revised">
            <div class="s-wrc__collabel">${label(compare.current)}</div>
            <div class="s-wrc__card s-wrc__card--revised" data-scroll-region lang="${langAttr(language)}">${diffMarkup(revisedSegments(compare))}</div>
          </div>
        </div>
      </section>`,
    );
    element.querySelector('[data-back]')?.addEventListener('click', () => ctx.back());
    element.querySelectorAll('[data-tab]').forEach((button) => {
      button.addEventListener('click', () => {
        activePane = button.dataset.tab;
        element.querySelector('.s-wrc__root').dataset.activePane = activePane;
        element.querySelectorAll('[data-tab]').forEach((tab) => tab.setAttribute('aria-selected', String(tab.dataset.tab === activePane)));
      });
    });
  }

  paint();
  return undefined;
}
