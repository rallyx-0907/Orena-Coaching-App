/* Practice Hub (route 'practice', design 'practice') and Skill Hub (route 'skillhub', design
   'skillhub', 08/09 of the pinned design) - one folder, one mount, because shell/routes.js already
   keys both to `screen: 'practice'` and the two are one continuous picker: the hub's skill sections
   inline, the per-skill drill-down one level deeper. See SCRATCH/reports/practice.md for the full
   accounting of what maps to what and why. */
import { html, mount } from '../../kit/html.js';
import { useStyles } from '../../kit/styles.js';
import { listRow, rowIconSwatch, sectionHead, pageHeader } from '../../kit/components.js';
import { langSpan } from '../../kit/lang.js';
import { emptyMarkup } from '../../kit/states.js';
import { href, byId } from '../../shell/routes.js';
import { api } from '../../infrastructure/api.js';
import { shellCopy } from '../../copy/shell.js';
import { t } from './copy.js';
import { SKILL_ORDER, SKILL_ICONS, SKILL_TINT, SKILL_BUILDERS, buildSkillSections, continuationRows, writeRecommendation } from './model.js';

const SKILL_LABEL_KEY = {
  speak: 'skillSpeak',
  write: 'skillWrite',
  listen: 'skillListen',
  vocabulary: 'skillVocabulary',
  grammar: 'skillGrammar',
  reading: 'skillReading',
};

function modeLabel(routeId) {
  return shellCopy(byId(routeId).crumb);
}

/* A mode's real per-item level (Speak's sentence/clip, Listen's dictation/shadowing item, Reading's
   next article) doubles as its meta text when there is nothing more specific to show - never an
   invented duration (rule 40: no skill's schema carries one). */
function modeMeta(skill, mode) {
  if (skill === 'vocabulary' && mode.key === 'review') return t.plural('due', mode.due);
  if ((skill === 'speak' || skill === 'listen' || skill === 'reading') && mode.level) return mode.level;
  return '';
}

function tileMarkup(skill, mode) {
  return listRow({
    variant: 'outline',
    radius: 18,
    pad: '14px',
    leading: rowIconSwatch({ iconName: SKILL_ICONS[skill][mode.key] || 'target', tint: SKILL_TINT[skill] }),
    title: modeLabel(mode.routeId),
    sub: modeMeta(skill, mode),
    className: 's-practice-tile',
    dataset: { go: href(mode.routeId, mode.params, mode.query) },
  });
}

/* Skill Hub's mode row is one line - label, then a trailing meta value, then the chevron
   (09-Skill-Hub.html: `{{md.label}}` and `{{md.dur}}` sit side by side, not stacked) - unlike
   Practice Hub's tile, which stacks label/meta in two lines. `listRow`'s `trailing` slot, not
   `sub`, is what reproduces that. */
function hubRowMarkup(skill, mode) {
  const meta = modeMeta(skill, mode);
  return listRow({
    variant: 'outline',
    radius: 14,
    pad: '13px 18px',
    title: modeLabel(mode.routeId),
    trailing: meta ? html`<span class="s-practice-hubrow__meta">${meta}</span>` : null,
    chevron: true,
    className: 's-practice-hubrow',
    dataset: { go: href(mode.routeId, mode.params, mode.query) },
  });
}

/* No trailing "see all" action: confirmed live (device:"mobile" renders the same six inline
   sections as desktop, just single-column - Skill Hub's only entry point in the pinned design,
   `phTiles`, is not wired into any rendered element in this snapshot, D2 Open Question #1). Adding
   one here would be an interaction the source does not draw (rule 44); recorded as a gap instead. */
function sectionMarkup(skill, modes) {
  return html`<section class="s-practice-section">
    ${sectionHead({ title: t(SKILL_LABEL_KEY[skill]), size: 'lg' })}
    <div class="s-practice-grid">${modes.map((mode) => tileMarkup(skill, mode))}</div>
  </section>`;
}

function continueRowLabel(routeId) {
  return shellCopy(byId(routeId).crumb);
}

function continueSub(row) {
  if (row.place) return `${row.place.index}/${row.place.total}`;
  if (row.context) return row.context;
  return '';
}

/* languages-5 / finding A: `row.title` is the real content this continuation entry resumes - an
   article, a media lesson, a grammar concept - always in the learner's active learning language
   (`ctx.context.language`, the language every one of Orena's content domains is in; no per-entry
   field exists on device-memory continuation, kit/lang.js's own "the learner's learning language
   the screen already read" source). Only `row.title` is marked, not the leading interface label
   before it. */
function continueRowMarkup(row, language) {
  return listRow({
    variant: 'shadow',
    radius: 18,
    pad: '12px',
    leading: rowIconSwatch({ iconName: row.icon, tint: row.tint }),
    title: html`${continueRowLabel(row.routeId)} · ${langSpan(row.title, language)}`,
    sub: continueSub(row),
    trailing: html`<span class="s-practice-pill">${t('continueCta')}</span>`,
    className: 's-practice-continue-row',
    dataset: { go: href(row.routeId, row.params, row.query) },
  });
}

function recommendationMarkup(rec, skill) {
  return html`<button type="button" class="s-practice-rec" data-go="${href('skillhub', { skill })}">
    <div class="s-practice-rec__body">
      <div class="s-practice-rec__eyebrow">${t('recommended')}</div>
      <div class="s-practice-rec__title">${rec.title}</div>
      ${rec.reason ? html`<div class="s-practice-rec__reason">${rec.reason}</div>` : ''}
    </div>
    <span class="s-practice-rec__cta">${t('start')}</span>
  </button>`;
}

async function renderHub(element, ctx, data) {
  const continuation = continuationRows(ctx.context.memory?.value?.continuation || []);
  const sections = buildSkillSections(data);
  const language = ctx.context.language;
  mount(
    element,
    html`<div class="s-practice">
      ${continuation.length ? html`<div class="s-practice-continue">${continuation.map((row) => continueRowMarkup(row, language))}</div>` : ''}
      ${sections.map(({ skill, modes }) => sectionMarkup(skill, modes))}
    </div>`,
  );
}

/* A skill with real modes right now (`modes.length`) renders its row list; a skill this build
   knows about but with nothing real to open this visit (Listen with no catalogue item carrying
   dictation/shadowing, Reading with no article published) and an unrecognised `:skill` param both
   fall to the same honest empty state (rule 40) - the only difference is the title: a known skill
   still gets its own heading, an unknown one falls back to the hub's own title rather than
   inventing a label for a place that does not exist. */
async function renderSkillHub(element, ctx, data, skill) {
  const known = SKILL_ORDER.includes(skill);
  const modes = known ? SKILL_BUILDERS[skill](data) : [];
  const title = known ? t(SKILL_LABEL_KEY[skill]) : shellCopy('practiceHub');
  const rec = known && skill === 'write' ? writeRecommendation(data.recommendation) : null;
  mount(
    element,
    html`<div class="s-practice-hub">
      ${pageHeader({ back: { label: shellCopy('back'), dataset: { back: '' } }, title, compact: true, titleSize: 20 })}
      ${rec ? recommendationMarkup(rec, skill) : ''}
      ${modes.length
        ? html`<div class="s-practice-hub__rows">${modes.map((mode) => hubRowMarkup(skill, mode))}</div>`
        : emptyMarkup({ text: t('emptySkill'), iconName: 'compass' })}
    </div>`,
  );
  element.querySelector('[data-back]')?.addEventListener('click', () => ctx.back());
}

export default async function practiceHub(element, ctx) {
  await useStyles('screens/practice/practice.css');
  const language = ctx.context.language;
  const skill = ctx.params?.skill || '';
  const fetchRecommendation = skill === 'write';
  /* Speak/Listen/Reading are all fetched unconditionally, the same way Speak's library already
     was before this fix - Practice Hub needs all three to decide which sections are real, and a
     Skill Hub visit needs whichever one its own skill owns. Each degrades to a real, honest empty
     on failure rather than throwing (this route is not `lesson: true`, so there is no router load-
     error screen to catch it). */
  const [speakingItems, listeningItems, reading, recommendation] = await Promise.all([
    api.speakingLibrary(language).then((res) => (Array.isArray(res?.items) ? res.items : [])).catch(() => []),
    api.listeningLibrary(language).then((res) => (Array.isArray(res?.items) ? res.items : [])).catch(() => []),
    api.readingPracticeNext().catch(() => ({ available: false, next: null })),
    fetchRecommendation ? api.practiceRecommendation().catch(() => null) : Promise.resolve(null),
  ]);
  if (!ctx.isCurrent()) return;
  const data = { speakingItems, listeningItems, reading, due: ctx.context.due, recommendation };
  if (skill) await renderSkillHub(element, ctx, data, skill);
  else await renderHub(element, ctx, data);
}
