/* Today (T1, frame 10-Today.html, Design Contract rule 47 - a browsing place, the shell stays).
   Real data only: recommendations from the learner's real due-vocabulary-review queue, Reading's
   selection policy, the Listening and Speaking catalogues, and the Daily Vocabulary Feed;
   unfinished work from device memory; evidence from LearnerSummary. The goal ring, streak and
   level/XP card have no cross-activity backend (rule 40, 0; docs/project/UI_BACKEND_GAPS.md N-21)
   - not the Writing-only streak of /api/dashboard. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { mediaCard, sectionHead, progressRing } from '../../kit/components.js';
import { useStyles } from '../../kit/styles.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { shellCopy } from '../../copy/shell.js';
import { t } from './copy.js';
import {
  buildRecommendationPool,
  buildForYou,
  usedRecommendationIds,
  buildGoalSummary,
  buildSkillRings,
  buildStreak,
  buildLevel,
  todayDateLabel,
} from './model.js';

export default async function mountToday(element, ctx) {
  await useStyles('screens/today/today.css');
  const state = ctx.context;
  const language = state.language === 'zh' ? 'zh' : 'en';
  const level = state.profile?.declared_level || '';
  const supportLang = languages().support;

  const [readingResult, listeningResult, speakingResult, feedResult, summaryResult, reviewResult] = await Promise.allSettled([
    api.readingPracticeNext(),
    api.listeningLibrary(language),
    api.speakingLibrary(language),
    api.dailyVocabularyFeed(language, level || undefined),
    api.learnerSummary('7d'),
    api.libraryReviewQueue(),
  ]);

  const reading = readingResult.status === 'fulfilled' ? readingResult.value : { available: false, next: null };
  const listeningItems = listeningResult.status === 'fulfilled' ? listeningResult.value?.items || [] : [];
  const speakingItems = speakingResult.status === 'fulfilled' ? speakingResult.value?.items || [] : [];
  const feedItems = feedResult.status === 'fulfilled' ? feedResult.value?.items || [] : [];
  const summary = summaryResult.status === 'fulfilled' ? summaryResult.value : null;
  // Same source My Library's own Due-Review tab reads (screens/library/screen.js): {due_count,
  // first_due_word}. A rejected/aborted call is a rule-40 empty queue, never an invented one.
  const review = reviewResult.status === 'fulfilled' ? reviewResult.value : { due_count: 0, first_due_word: '' };

  const pool = buildRecommendationPool({ reading, listening: listeningItems, speaking: speakingItems, review }, t);
  const usedIds = usedRecommendationIds(pool);
  const continuation = Array.isArray(state.memory?.value?.continuation) ? state.memory.value.continuation : [];
  const forYou = buildForYou(
    {
      continuation,
      listening: listeningItems.slice(1),
      speaking: speakingItems.slice(1),
      feed: feedItems,
      usedIds,
      supportLang,
    },
    t,
  );

  const goal = buildGoalSummary(summary || {}, t);
  const skills = buildSkillRings(t);
  const streak = buildStreak(t);
  const lvl = buildLevel(t);

  let heroIndex = 0;

  function goAttr(item) {
    return ctx.href(item.routeId, item.routeParams, item.routeQuery);
  }

  function headMarkup() {
    const name = String(state.name || '').trim();
    return html`<div class="s-today-head">
      <div class="s-today-head__col">
        ${name ? html`<div class="s-today-eyebrow">${name},</div>` : ''}
        <h1 class="s-today-h1">${shellCopy('today')}</h1>
      </div>
      <span class="s-today-date">${todayDateLabel(new Date(), languages().ui)}</span>
    </div>`;
  }

  function progressMarkup() {
    return html`<div class="s-today-progress">
      <div class="s-today-goal">
        ${progressRing({
          percent: goal.pct,
          size: 112,
          radius: 50,
          stroke: 12,
          center: html`<span class="s-today-goal-pct">${goal.pct}<span>%</span></span><span class="s-today-goal-caption">${t('ofGoalLabel')}</span>`,
        })}
        <div class="s-today-goal-body">
          <div class="s-today-goal-label">${goal.label}</div>
          <div class="s-today-skills">
            ${skills.map(
              (skill) => html`<div class="s-today-skill" title="${skill.label}">
                ${progressRing({
                  percent: skill.percent,
                  size: 44,
                  radius: 19,
                  stroke: 4,
                  color: skill.color,
                  center: html`<span style="color:${skill.color};display:flex">${raw(icon(skill.icon, { size: 22 }))}</span>`,
                })}
                <span class="s-today-skill-label">${skill.label}</span>
              </div>`,
            )}
          </div>
          <div class="s-today-goal-sub">${goal.sub}</div>
        </div>
      </div>
      <div class="s-today-side">
        <div class="s-today-streak">
          <div class="s-today-streak-head">
            <span class="s-today-streak-icon">${raw(icon('flame', { size: 22 }))}</span>
            <span class="s-today-streak-text">${streak.before}<b class="s-today-streak-n">${streak.n}</b>${streak.after}</span>
          </div>
          <div class="s-today-streak-days">
            ${streak.days.map(
              (day) => html`<div class="s-today-day">
                <span class="${day.done ? 's-today-day-dot s-today-day-dot--done' : 's-today-day-dot'}">${day.done ? raw(icon('check', { size: 12 })) : ''}</span>
                <span class="s-today-day-letter">${day.letter}</span>
              </div>`,
            )}
          </div>
        </div>
        <div class="s-today-level">
          <span class="s-today-level-badge">${lvl.badge}</span>
          <div class="s-today-level-body">
            <div class="s-today-level-row"><b>${lvl.name}</b><span>${lvl.xp}</span></div>
            <div class="s-today-level-track"><span style="width:${lvl.pct}%"></span></div>
            <div class="s-today-level-next">${lvl.next}</div>
          </div>
        </div>
      </div>
    </div>`;
  }

  function recommendedMarkup() {
    if (!pool.length) return '';
    const heroPos = heroIndex % pool.length;
    const hero = pool[heroPos];
    const rest = pool.filter((_, index) => index !== heroPos);
    return html`<div class="s-today-rec">
      ${sectionHead({ title: t('recommendedTitle'), action: { label: t('anotherAction'), dataset: { another: '1' } } })}
      <div class="s-today-rec-grid">
        <button type="button" class="s-today-hero" data-go="${goAttr(hero)}">
          <span class="s-today-hero__deco s-today-hero__deco--a"></span>
          <span class="s-today-hero__deco s-today-hero__deco--b"></span>
          <span class="s-today-hero__head">
            <span class="s-today-hero__icon" style="background:${hero.tint}">${raw(icon(hero.icon, { size: 20 }))}</span>
            <span class="s-today-hero__kind">${[hero.kind, hero.durationLabel].filter(Boolean).join(' · ')}</span>
          </span>
          <span class="s-today-hero__body">
            <span class="s-today-hero__title">${hero.title}</span>
            ${hero.reason ? html`<span class="s-today-hero__reason">${hero.reason}</span>` : ''}
          </span>
          <span class="s-today-hero__cta">${t('startAction')} ${raw(icon('arrow-right', { size: 17 }))}</span>
        </button>
        <div class="s-today-rest">
          ${rest.map(
            (item) => html`<button type="button" class="s-today-rest-card" data-go="${goAttr(item)}">
              <span class="s-today-rest-card__icon" style="background:${item.tint}">${raw(icon(item.icon, { size: 20 }))}</span>
              <span class="s-today-rest-card__title">${item.title}</span>
              <span class="s-today-rest-card__meta">${[item.kind, item.durationLabel].filter(Boolean).join(' · ')}</span>
            </button>`,
          )}
        </div>
      </div>
    </div>`;
  }

  function forYouMarkup() {
    if (!forYou.length) return '';
    return html`<div class="s-today-foryou">
      ${sectionHead({ title: t('forYouTitle'), action: { label: t('seeAllAction'), dataset: { go: ctx.href('discover') } } })}
      <div class="s-today-rail">
        ${forYou.map((item) =>
          mediaCard({
            image: item.image ? `url("${item.image}")` : '',
            imageHeight: 130,
            kind: item.kind,
            duration: item.durationLabel,
            title: item.title,
            meta: item.meta || '',
            tags: item.tag ? [{ label: item.tag }] : [],
            dataset: { go: ctx.href(item.routeId, item.routeParams, item.routeQuery) },
          }),
        )}
      </div>
    </div>`;
  }

  function paint() {
    mount(
      element,
      html`<div class="s-today">
        ${headMarkup()}
        ${progressMarkup()}
        ${recommendedMarkup()}
        ${forYouMarkup()}
      </div>`,
    );
    element.querySelector('[data-another]')?.addEventListener('click', () => {
      heroIndex += 1;
      paint();
    });
  }

  paint();
}
