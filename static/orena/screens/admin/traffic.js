/* Admin > Overview > Traffic & engagement (the design draws no such page, so kit blocks only, by the
   human's request 2026-10-09). Reads two existing answers: GET /api/admin/console/overview (accounts,
   registrations and learner activity per UTC day, 30 days) and GET /api/admin/product-activity (per
   skill activity, returning / repeat / cross-skill learners, the funnel). Page views and visits are
   not recorded anywhere; the page says so instead of inventing them. */
import { html } from '../../kit/html.js';
import { languages } from '../../copy/index.js';
import { adminApi } from '../../capabilities/admin-api.js';
import { t } from './copy.js';
import { bars, block, chipRow, metrics, pageHead, rowList, skeleton, stateBlock } from './blocks.js';
import { createHost } from './host.js';

export const PERIODS = Object.freeze([7, 30]);

const count = (value, number) => (value == null || Number.isNaN(Number(value)) ? '—' : number.format(Number(value)));
const pct = (value, max) => (max > 0 ? (Number(value) / max) * 100 : 0);
const sum = (list, field) => list.reduce((total, item) => total + (Number(item[field]) || 0), 0);

function dayLabel(iso, ui) {
  const date = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? String(iso) : new Intl.DateTimeFormat(ui, { month: 'short', day: 'numeric', timeZone: 'UTC' }).format(date);
}

const skillLabel = (skill) => {
  const label = t(`trafSkill_${skill}`);
  return label && label !== `trafSkill_${skill}` ? label : String(skill || '').replaceAll('_', ' ');
};

function dayBars(days, field, number, ui) {
  const max = Math.max(0, ...days.map((day) => Number(day[field]) || 0));
  return bars(days.map((day) => ({ label: dayLabel(day.date, ui), pct: pct(day[field], max), value: number.format(Number(day[field]) || 0) })), { labelWidth: '72px' });
}

export function trafficPage({ overview, activity, days = 30, failed = false, ui = 'en', href }) {
  const head = pageHead({ back: { href: href('adminOverview'), label: t('navOverview') }, title: t('trafTitle'), sub: t('trafSub') });
  if (failed) return html`<section class="a-page" data-screen-label="Traffic">${head}${block({ body: t('opUnavailable') })}</section>`;
  if (!overview && !activity) return html`<section class="a-page" data-screen-label="Traffic">${head}${skeleton(t('loading'))}</section>`;
  const number = new Intl.NumberFormat(ui);
  const percent = new Intl.NumberFormat(ui, { maximumFractionDigits: 1 });
  const accounts = overview?.accounts?.available ? overview.accounts : null;
  const learners = overview?.activity?.available ? overview.activity : null;
  const registrations = (accounts?.registrations || []).slice(-days);
  const daily = (learners?.daily || []).slice(-days);
  const signups = accounts ? (days === 7 ? accounts.new_7d : days === 30 ? accounts.new_30d : sum(registrations, 'count')) : null;
  const events = learners ? sum(daily, 'events') : null;
  const unavailable = block({ span: true, body: t('opUnavailable') });
  const skills = activity?.available ? (activity.skills || []) : [];
  const maxSkill = Math.max(0, ...skills.map((skill) => Number(skill.activities) || 0));
  const hasActivity = Boolean(activity?.available) && activity.has_data !== false;
  const stage = (skill, name) => {
    const found = (skill.funnel?.stages || []).find((item) => item.stage === name);
    return found && found.available ? count(found.count, number) : '—';
  };
  const rate = (value) => (value == null ? '—' : `${percent.format(value)}%`);
  return html`<section class="a-page" data-screen-label="Traffic">
    ${head}
    <div class="a-blocks">
      ${block({ span: true, body: chipRow({ label: t('trafPeriod'), a: 'pick', field: 'days', options: PERIODS.map((n) => ({ id: String(n), label: t('trafDays', { n }), on: days === n })) }) })}
      ${block({ span: true, body: metrics([
        { label: t('trafAccounts'), value: count(accounts?.total, number) },
        { label: t('trafSignups'), value: count(signups, number) },
        { label: t('trafActive7'), value: count(learners?.active_7d, number) },
        { label: t('trafActive30'), value: count(learners?.active_30d, number) },
        { label: t('trafReturning7'), value: count(learners?.returning_7d, number) },
        { label: t('trafEvents'), value: count(events, number) },
      ], { columns: 3 }) })}
      ${learners ? block({ title: t('trafPerDay'), body: dayBars(daily, 'learners', number, ui) }) : unavailable}
      ${accounts ? block({ title: t('trafSignupsPerDay'), body: dayBars(registrations, 'count', number, ui) }) : unavailable}
      ${activity ? block({ span: true, title: t('trafSkills'), body: hasActivity
        ? bars(skills.map((skill) => ({ label: skillLabel(skill.skill), pct: pct(skill.activities, maxSkill), value: `${number.format(Number(skill.activities) || 0)} · ${t('trafSkillMeta', { done: number.format(Number(skill.completions) || 0) })}` })), { labelWidth: '104px' })
        : stateBlock({ kind: 'empty', heading: t('opNone') }) }) : unavailable}
      ${hasActivity ? block({ title: t('trafEngagement'), body: metrics([
        { label: t('trafLearners'), value: count(activity.active_learners, number) },
        { label: t('trafReturningLearners'), value: count(activity.returning_learners, number) },
        { label: t('trafRepeat'), value: count(activity.repeat_practice_learners, number) },
        { label: t('trafCross'), value: count(activity.cross_skill_returning_learners, number) },
      ], { columns: 2 }) }) : ''}
      ${hasActivity ? block({ title: t('trafReturnWindows'), body: rowList((activity.return_windows || []).map((win) => ({
        title: t('trafReturnWindow', { n: win.days }),
        meta: t('trafReturnMeta', { returned: number.format(Number(win.returned_learners) || 0), eligible: number.format(Number(win.eligible_learners) || 0) }),
        right: rate(win.return_rate_percent),
      })), { title: t('opNone'), text: '' }) }) : ''}
      ${hasActivity ? block({ span: true, title: t('trafFunnel'), body: rowList(skills.map((skill) => ({
        title: skillLabel(skill.skill),
        meta: [['trafStarted', 'started'], ['trafAttempted', 'attempted'], ['trafCompleted', 'completed']].map(([key, name]) => `${t(key)}: ${stage(skill, name)}`).join(' · '),
        right: rate(skill.completion_rate_percent),
      })), { title: t('opNone'), text: '' }) }) : ''}
      ${block({ span: true, body: t('trafNote') })}
    </div>
  </section>`;
}

export async function mountTraffic(shell, ctx) {
  const host = createHost(shell, ctx);
  const view = { days: 30, overview: null, activity: null, failed: false };
  host.setBuilder(() => ({ title: t('trafTitle'), markup: trafficPage({ overview: view.overview, activity: view.activity, days: view.days, failed: view.failed, ui: languages().ui, href: ctx.href }) }));
  async function loadActivity() {
    try {
      view.activity = await adminApi.productActivity(view.days);
    } catch {
      view.activity = null;
    }
  }
  async function load() {
    view.failed = false;
    view.overview = null;
    view.activity = null;
    host.paint();
    const [overview] = await Promise.all([adminApi.overview().catch(() => null), loadActivity()]);
    view.overview = overview;
    view.failed = !view.overview && !view.activity;
    host.paint();
  }
  host.on('go', (control, dataset) => { if (dataset.to) ctx.go(dataset.to); });
  host.on('pick', (control, dataset) => {
    if (dataset.field !== 'days') return;
    view.days = Number(dataset.value) || 30;
    host.paint();
    loadActivity().then(() => host.paint());
  });
  host.on('reload', () => { load(); });
  await load();
  return () => host.cleanup();
}
