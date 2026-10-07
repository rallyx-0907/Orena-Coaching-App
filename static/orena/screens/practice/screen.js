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
import { languages } from '../../copy/index.js';
import { openSheet, sheetHead, fillSheet } from '../../kit/overlay.js';
import { loadPendingRows, recentRows, recentMediaFacts, lastSpeakingLine } from './continuation.js';
import { t } from './copy.js';
import { loadAttemptsSince } from '../../product/speaking-history.js';
import { SKILL_ORDER, SKILL_ICONS, SKILL_TINT, SKILL_BUILDERS, SPEAK_GROUPS, buildSkillSections, writeRecommendation, weakestLines } from './model.js';

const GROUP_LABEL_KEY = { natural: 'groupNatural', pronounce: 'groupPronounce', challenge: 'groupChallenge' };

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
/* Speak draws the design's one-line description and duration on each tile ("desc · dur") and the
   duration alone on a Skill Hub row (S1 `phSections` / `phGroups`). */
function speakDur(skill, mode) {
  return skill === 'speak' && mode.group ? t(`${mode.key}Dur`) : '';
}

function modeMeta(skill, mode) {
  // The duration never truncates: only the description gives way in a longer interface language.
  if (skill === 'speak' && mode.group) return html`<span class="s-practice-tile__desc">${t(`${mode.key}Desc`)}</span><span class="s-practice-tile__dur">· ${t(`${mode.key}Dur`)}</span>`;
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
    title: modeLabel(mode.labelRouteId || mode.routeId),
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
  const meta = speakDur(skill, mode) || modeMeta(skill, mode);
  return listRow({
    variant: 'outline',
    radius: 14,
    pad: '13px 18px',
    title: modeLabel(mode.labelRouteId || mode.routeId),
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
  return shellCopy(byId(routeId === 'compare' ? 'speak' : routeId).crumb);
}

function continueSub(row) {
  if (row.reason === 'reading') return t('readingReason', { n: row.percent });
  if (row.reason) return t(`${row.reason}Reason`);
  if (row.line) return t('recentLine', { n: row.line.index, total: row.line.total });
  return t('recentReason');
}

/* languages-5 / finding A: `row.title` is the real content this continuation entry resumes - an
   article, a media lesson, a grammar concept - always in the learner's active learning language
   (`ctx.context.language`, the language every one of Orena's content domains is in; no per-entry
   field exists on device-memory continuation, kit/lang.js's own "the learner's learning language
   the screen already read" source). Only `row.title` is marked, not the leading interface label
   before it. */
function continueRowMarkup(row, language, recent = false) {
  return listRow({
    variant: 'shadow',
    radius: 18,
    pad: '12px',
    leading: rowIconSwatch({ iconName: row.icon, tint: row.tint }),
    title: html`${continueRowLabel(row.routeId)} · ${langSpan(row.title, language)}`,
    sub: continueSub(row),
    trailing: recent ? null : html`<span class="s-practice-pill">${t('continueCta')}</span>`,
    chevron: recent,
    className: 's-practice-continue-row',
    dataset: { go: href(row.routeId, row.params, row.query) },
  });
}

/* The learner's own word inside a sentence of the interface language keeps its own `lang` (WCAG 3.1.2). */
const WORD = '';
function withWord(key, word, language, params = {}) {
  const [before, after = ''] = t(key, { ...params, word: WORD }).split(WORD);
  return html`${before}${langSpan(word, language)}${after}`;
}

function recommendationMarkup(rec, skill) {
  return html`<button type="button" class="s-practice-rec" data-go="${rec.go || href('skillhub', { skill })}">
    <div class="s-practice-rec__body">
      <div class="s-practice-rec__eyebrow">${t('recommended')}${rec.dur ? ` · ${rec.dur}` : ''}</div>
      <div class="s-practice-rec__title">${rec.title}</div>
      ${rec.reason ? html`<div class="s-practice-rec__reason">${rec.reason}</div>` : ''}
    </div>
    <span class="s-practice-rec__cta">${t('start')}</span>
  </button>`;
}

/* Speak's card: the weakest line of the learner's real attempts that can still be opened (its media readable, in
   the learning language, with model audio - the same admission Recent uses), opening that line in the room. */
async function speakRecommendation(ctx, language) {
  const [rows, library] = await Promise.all([
    loadAttemptsSince(api, '', 100),
    api.listeningLibrary(language).then((res) => (Array.isArray(res?.items) ? res.items : [])).catch(() => []),
  ]);
  const options = { api, language, support: languages().support, owner: ctx.context.owner, memory: ctx.context.memory };
  for (const candidate of weakestLines(rows || [])) {
    // An attempt names the media object; the room opens by lesson id (the same value for an import).
    const lessonId = library.find((item) => item?.media_object_id === candidate.assetId)?.lesson_id || candidate.assetId;
    const facts = await recentMediaFacts([{ id: `media:${lessonId}` }], options);
    const fact = facts.get(`media:${lessonId}`);
    if (!fact?.canonicalId) continue;
    // The line itself is the segment the attempt was made on, whichever line the media opened on.
    return {
      title: candidate.word ? withWord('recTitleWord', candidate.word.text, language) : t('recTitleLine'),
      reason: candidate.word ? withWord('recReasonWord', candidate.word.text, language, { n: candidate.word.score }) : t('recReasonLine', { n: candidate.overall }),
      dur: t('speakDur'),
      go: href('speak', { id: `media:${fact.canonicalId}` }, { segment: candidate.segmentId }),
    };
  }
  return null;
}

async function renderHub(element, ctx, data) {
  const memory = ctx.context.memory?.value || {};
  const continuation = await loadPendingRows(ctx.context.memory, ctx.context.language);
  if (!ctx.isCurrent()) return;
  const recent = recentRows(memory.continuation);
  const sections = buildSkillSections(data);
  const language = ctx.context.language;
  mount(
    element,
    html`<div class="s-practice">
      <section class="s-practice-continue">
        ${sectionHead({ title: t('continueTitle'), action: recent.length ? { label: t('recentTitle'), dataset: { recent: '' } } : null })}
        ${continuation.length ? continuation.map((row) => continueRowMarkup(row, language)) : html`<p class="s-practice-empty">${t('nothingPending')}</p>`}
      </section>
      ${sections.map(({ skill, modes }) => sectionMarkup(skill, modes))}
    </div>`,
  );
  let recentOpening = false;
  element.querySelector('[data-recent]')?.addEventListener('click', async event => {
    if (recentOpening) return;
    recentOpening = true;
    const button = event.currentTarget;
    button.disabled = true;
    const facts = await recentMediaFacts(memory.continuation || [], { api, language, support: languages().support, owner: ctx.context.owner, memory: ctx.context.memory });
    recentOpening = false;
    button.disabled = false;
    if (!ctx.isCurrent()) return;
    const rows = recentRows(memory.continuation, facts);
    openSheet({ label: t('recentTitle'), render(sheet, handle) {
      fillSheet(sheet, handle, html`${sheetHead({ title: t('recentTitle'), closeLabel: shellCopy('close') })}
        <div class="s-practice-recent"><p class="s-practice-empty">${t('recentExplanation')}</p>
          ${rows.length ? rows.map(row => continueRowMarkup(row, language, true)) : html`<p class="s-practice-empty">${t('noRecent')}</p>`}
        </div>`);
    } });
  });
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
  const rec = known && skill === 'write' ? writeRecommendation(data.recommendation) : known && skill === 'speak' ? data.speakRecommendation : null;
  mount(
    element,
    html`<div class="s-practice-hub">
      ${pageHeader({ back: { label: shellCopy('back'), dataset: { back: '' } }, title, compact: true, titleSize: 20 })}
      ${rec ? recommendationMarkup(rec, skill) : ''}
      ${modes.length
        ? (modes[0].group
          ? html`<div class="s-practice-hub__groups">${SPEAK_GROUPS.map((group) => {
            const rows = modes.filter((mode) => mode.group === group);
            return rows.length ? html`<section class="s-practice-hub__group">
              <h2 class="s-practice-hub__group-title">${t(GROUP_LABEL_KEY[group])}</h2>
              <div class="s-practice-hub__rows">${rows.map((mode) => hubRowMarkup(skill, mode))}</div>
            </section>` : '';
          })}</div>`
          : html`<div class="s-practice-hub__rows">${modes.map((mode) => hubRowMarkup(skill, mode))}</div>`)
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
  const [speakingItems, listeningItems, reading, recommendation, lastLine, speakRec] = await Promise.all([
    api.speakingLibrary(language).then((res) => (Array.isArray(res?.items) ? res.items : [])).catch(() => []),
    api.listeningLibrary(language).then((res) => (Array.isArray(res?.items) ? res.items : [])).catch(() => []),
    api.readingPracticeNext().catch(() => ({ available: false, next: null })),
    fetchRecommendation ? api.practiceRecommendation().catch(() => null) : Promise.resolve(null),
    // Pronunciation opens the learner's last line at once (D-139 HD-3); only the hub and Speak's hub list it.
    !skill || skill === 'speak' ? lastSpeakingLine(ctx.context.memory, { api, language, support: languages().support, owner: ctx.context.owner }).catch(() => null) : Promise.resolve(null),
    // Skill Hub Speak's Recommended card, from the learner's weakest real attempt (D-139 HD-1); none without attempts.
    skill === 'speak' ? speakRecommendation(ctx, language).catch(() => null) : Promise.resolve(null),
  ]);
  if (!ctx.isCurrent()) return;
  const data = { speakingItems, listeningItems, reading, due: ctx.context.due, recommendation, lastSpeakingLine: lastLine, speakRecommendation: speakRec };
  if (skill) await renderSkillHub(element, ctx, data, skill);
  else await renderHub(element, ctx, data);
}
