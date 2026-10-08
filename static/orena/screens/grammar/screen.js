/* Frame "Grammar Library" (pinned design, frame 44; route "grammarlib"). A browsing place (Design
   Contract rule 47): shell drawn, rail/tab bar present.

   Data: the Grammar Store's catalogue for the learning language and the learner's completed points, through the one
   seam product/grammar-source.js. The page is the frame's own group heading, hint and concept card, composed as the
   human decided on 2026-10-08 (model.js buildLibrary): levels, continue learning, explore by topic, then all grammar
   of the chosen level in sections by topic. The chosen level and topic live in the address (?level=&topic=), so
   reload and Back from a point land where the learner was.

   Rule 50: the frame's subtitle under the "Grammar" heading only restates the group headings below it and is
   dropped. */
import { html, mount } from '../../kit/html.js';
import { useStyles } from '../../kit/styles.js';
import { pageHeader, listRow } from '../../kit/components.js';
import { langSpan } from '../../kit/lang.js';
import { emptyMarkup } from '../../kit/states.js';
import { shellCopy as shell } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { t } from './copy.js';
import { grammarLibraryData, grammarProgress, levelCode } from '../../product/grammar-source.js';
import { TOPIC_PREVIEW, buildLibrary } from './model.js';
import { hanziMarkup } from './hanzi.js';

function cardTitle(item) {
  return langSpan(item.lang === 'zh' ? hanziMarkup(item.title, item.titlePinyin) : item.title, item.lang);
}

function tag(item) {
  if (item.done) {
    const label = item.score ? `✓ ${t('tagScore', { correct: item.score.correct, total: item.score.total })}` : `✓ ${t('tagDone')}`;
    return html`<span class="s-grammar__tag s-grammar__tag--done">${label}</span>`;
  }
  return html`<span class="s-grammar__tag s-grammar__tag--new">${t('tagNew')}</span>`;
}

function card(item) {
  return listRow({ radius: 20, pad: '16px', title: cardTitle(item), titleLineHeight: 20, sub: item.note, trailing: tag(item), dataset: { open: item.id } });
}

function groupHead(title, hint = '', extra = '') {
  return html`<div class="s-grammar__ghead"><h2 class="s-grammar__gname">${title}</h2>${hint ? html`<span class="s-grammar__ghint">${hint}</span>` : ''}${extra}</div>`;
}

/* The design's Level chip row (Discover, design revision of 2026-10: label 13/600 muted, chips 36px pill 13.5/600, the
   state script's chip(on) colours). */
function levelChips(levels) {
  return html`<div class="s-grammar__filter"><span class="s-grammar__flabel">${t('levelLabel')}</span>${levels.map(
    (level) => html`<button type="button" class="o-chip s-grammar__chip" data-level="${level.key}" aria-pressed="${level.selected ? 'true' : 'false'}">${levelCode(level.level)}</button>`,
  )}</div>`;
}

function topicCard(topic) {
  return html`<button type="button" class="s-grammar__topic" data-topic="${topic.id || '-'}" aria-pressed="${topic.selected ? 'true' : 'false'}">
    <span class="s-grammar__topicName">${topic.title}</span>
    <span class="s-grammar__topicMeta">${topic.done ? t('topicMeta', { n: topic.count, done: topic.done }) : t('levelPoints', { n: topic.count })}</span>
  </button>`;
}

export default async function grammarLibrary(element, ctx) {
  await useStyles('screens/grammar/grammar.css');
  const target = ctx.context.language === 'zh' ? 'zh' : 'en';
  const [data, progress] = await Promise.all([grammarLibraryData(target), grammarProgress()]);
  if (!ctx.isCurrent()) return;
  const state = { level: ctx.query?.get?.('level') || '', topic: ctx.query?.get?.('topic') || '', allTopics: false };

  function render() {
    const view = buildLibrary({
      rows: data.points, functions: data.functions, progress, current: ctx.context.level || '',
      selected: state.level, topic: state.topic, support: languages().support, t,
    });
    if (!view.level) {
      mount(element, html`<div class="s-grammar">${pageHeader({ back: { label: shell('back'), dataset: { back: '1' } }, title: t('title') })}${emptyMarkup({ text: t('empty'), iconName: 'inbox' })}</div>`);
      return;
    }
    const code = levelCode(view.level.level);
    const topics = state.allTopics ? view.topics : view.topics.slice(0, TOPIC_PREVIEW);
    mount(
      element,
      html`<div class="s-grammar">
        ${pageHeader({ back: { label: shell('back'), dataset: { back: '1' } }, title: t('title') })}

        ${levelChips(view.levels)}

        <section class="s-grammar__group">
          ${groupHead(t('continueTitle'), t('continueHint', { level: code }))}
          ${view.continue.length
            ? html`<div class="s-grammar__grid s-grammar__continue">${view.continue.map(card)}</div>`
            : html`<div class="s-grammar__empty">${t('levelComplete')}</div>`}
        </section>

        <section class="s-grammar__group">
          ${groupHead(t('topicsTitle'), t('topicsHint', { n: view.topics.length, level: code }))}
          <div class="s-grammar__topics">${topics.map(topicCard)}</div>
          ${view.topics.length > TOPIC_PREVIEW
            ? html`<button type="button" class="s-grammar__more" data-all-topics>${state.allTopics ? t('showFewerTopics') : t('showAllTopics', { n: view.topics.length })}</button>`
            : ''}
        </section>

        <section class="s-grammar__group" data-all>
          ${groupHead(t('allTitle'), t('allHint', { level: code, n: view.shown }), view.topic
            ? html`<button type="button" class="s-grammar__clear" data-topic="">${t('clearTopic')} ×</button>`
            : '')}
          <div class="s-grammar__sections s-grammar__sections--under">${view.sections.map((section) => html`<div class="s-grammar__section">
            <div class="s-grammar__shead"><h3 class="s-grammar__sname">${section.title}</h3><span class="s-grammar__ssub">${t('levelPoints', { n: section.items.length })}</span></div>
            <div class="s-grammar__grid">${section.items.map(card)}</div>
          </div>`)}</div>
        </section>
      </div>`,
    );
  }

  function remember() {
    const query = {};
    if (state.level) query.level = state.level;
    if (state.topic) query.topic = state.topic;
    // The address keeps the choice without a new render (as screens/library and listening do).
    history.replaceState(history.state, '', ctx.href('grammarlib', {}, query));
  }

  render();
  element.addEventListener('click', (event) => {
    if (event.target.closest('[data-back]')) {
      ctx.back();
      return;
    }
    const open = event.target.closest('[data-open]');
    if (open) {
      ctx.go(ctx.href('gconcept', { id: open.dataset.open }));
      return;
    }
    const level = event.target.closest('[data-level]');
    if (level) {
      state.level = level.dataset.level;
      state.topic = '';
      state.allTopics = false;
      remember();
      render();
      return;
    }
    const topic = event.target.closest('[data-topic]');
    if (topic) {
      const id = topic.dataset.topic === '-' ? '' : topic.dataset.topic;
      state.topic = state.topic === id ? '' : id;
      remember();
      render();
      if (state.topic) element.querySelector('[data-all]')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    if (event.target.closest('[data-all-topics]')) {
      state.allTopics = !state.allTopics;
      render();
    }
  });
}
