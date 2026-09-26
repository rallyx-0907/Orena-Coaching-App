/* The learner's own page (D-067), measured from "Orena Hạn mức sử dụng" in the
   design project: who they are, how far they have come, what they have set,
   and what their plan still allows this period.

   Until now Profile was a dialog. The source draws it as a destination with a
   hero, a settings column and a usage panel, so that is what this is.

   Three things here are honest rather than decorative, and they are the whole
   reason the page reads the way it does:

   - **The plan and its limits are real.** `/api/product/me` already answers
     with the plan and, per feature, the monthly limit and what has been used.
     That is exactly what the source's "Hạn mức sử dụng" draws, so the rows are
     the learner's own numbers - not a mock, and not a percentage invented to
     fill a bar.
   - **XP and the streak are not measured.** The frame draws "15 840 XP" and
     "128 ngày liên tiếp" as sample content. Orena counts neither, so the
     canonical component renders with nothing in it and says so (D-066 rule 4).
     No figure here is ever guessed.
   - **The rank frame waits for a tier.** `ProgressOverview` carries
     `tier {name, level, current, target}` and nothing serves it, so the avatar
     is drawn plain. The crystal appears the day a tier arrives - see
     `rank-frame.js`, which needs only the number. */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { refCopy } from './reference.js';
import { rankFrame } from './rank-frame.js';
import { rankProgress, rankSummary } from '../product/rank.js';

/* The features the source lists, in its order, against the catalogue keys the
   product service already answers with. A key the plan does not carry is left
   out rather than drawn as an empty promise. */
const QUOTA_ROWS = [
  { key: 'writing.evaluate', label: 'profileQuotaWriting' },
  { key: 'writing.improve', label: 'profileQuotaImprove' },
  { key: 'dictionary.lookup', label: 'profileQuotaDictionary' },
  { key: 'vocabulary.save', label: 'profileQuotaVocabulary' },
  { key: 'library.grammar', label: 'profileQuotaGrammar' },
  { key: 'analytics.advanced', label: 'profileQuotaAnalytics' },
];

const pct = (used, limit) => {
  if (!limit || limit <= 0) return 100;
  return Math.max(0, Math.min(100, Math.round((used / limit) * 100)));
};

/* Amber once a limit is nearly spent, so the one row that matters is the one
   that stands out - the source's own rule. */
const toneOf = (feature) => {
  if (!feature) return 'unknown';
  if (feature.monthly_limit === null || feature.monthly_limit === undefined) return 'free';
  if (!feature.enabled) return 'spent';
  return pct(feature.used, feature.monthly_limit) >= 80 ? 'warn' : 'ok';
};

function quotaRow(r, row, feature) {
  const name = r[row.label] || row.key;
  const tone = toneOf(feature);
  if (tone === 'unknown') return '';
  const unlimited = tone === 'free';
  /* Two numbers and a slash: a format, not copy, so it is built here rather
     than kept as a "translation" that reads the same in every language. */
  const value = unlimited
    ? r.profileQuotaUnlimited
    : `${Number(feature.used || 0).toLocaleString()} / ${Number(feature.monthly_limit).toLocaleString()}`;
  const width = unlimited ? 100 : pct(feature.used, feature.monthly_limit);
  return `<div class="quota-row" data-tone="${esc(tone)}">
    <div class="quota-row__head"><span class="quota-row__name">${esc(name)}</span><span class="quota-row__value ds-data">${esc(value)}</span></div>
    <span class="quota-bar"${unlimited ? ' data-unlimited' : ''}><span style="inline-size:${width}%"></span></span>
  </div>`;
}

/* A row the learner can change opens the preferences sheet. Two of the six the
   frame lists - the study reminder and their own content - have nothing behind
   them yet, so the row keeps its place and its glyph, says it is not there yet,
   and does not pretend to open anything (D-066 rule 4). */
function settingRow(glyph, label, value, { ready = true } = {}) {
  return `<button type="button" class="profile-setting"${ready ? ' data-preference' : ' disabled'}>
    <span class="profile-setting__icon">${icon(glyph, { size: 20 })}</span>
    <span class="profile-setting__label">${esc(label)}</span>
    <span class="profile-setting__value${ready ? '' : ' metric-unavailable'}">${esc(value)}</span>
    <span class="profile-setting__go">${icon('caret-right', { size: 17 })}</span>
  </button>`;
}

export function profileSection(ctx, { account, profile, vocabulary = null } = {}) {
  const c = ctx.c;
  const r = refCopy(ctx);
  const languageName = ctx.language === 'zh' ? '中文' : 'English';
  const level = String(profile?.declared_level || '').trim();
  const planName = account?.plan?.name || '';
  const features = account?.features || {};

  /* The rank the learner actually holds. The server works it out from the one
     measure Orena really counts - their mastered words - and answers with it
     on the vocabulary summary; Tiến độ reads the same answer, so the two
     screens cannot disagree, and neither counts words in the browser. Below
     the first rank there is no crystal to draw, and none is invented: the
     frame's plain well stands until it is earned. */
  const state = rankSummary(vocabulary);
  const tier = state.rank;
  const known = state.known ? state.mastered : null;
  const avatarInner = `<span class="profile-avatar__face">${icon('user', { size: 40 })}</span>`;
  const avatar = tier
    ? rankFrame({ rank: tier, size: 168, uid: 'profile', avatar: avatarInner })
    : `<span class="profile-avatar">${avatarInner}</span>`;

  const identity = [
    level ? `${languageName} · ${esc(level)}` : esc(languageName),
  ].join('');

  const quotas = QUOTA_ROWS.map((row) => quotaRow(r, row, features[row.key])).filter(Boolean).join('');

  /* The six rows the frame lists, in its order and with its glyphs. */
  const settings = [
    settingRow('translate', r.profileSettingLanguages, `${languageName} · ${ctx.supportLabel || String(ctx.support || '').toUpperCase()}`),
    /* One of the four goals `account_profile.py` allows. A value with no word
       of its own reads as "not set" rather than as the stored key: the
       interface never shows the read model's own vocabulary. */
    settingRow('target', r.profileSettingGoal, r[`profileGoal_${profile?.goal || ''}`] || r.profileNotSet),
    settingRow('bell', r.profileSettingReminder, r.profileNotYet, { ready: false }),
    settingRow('credit-card', r.profileSettingPlan, planName || r.profileNotSet),
    settingRow('lock-key', r.profileSettingPrivate, r.profileNotYet, { ready: false }),
    settingRow('moon-stars', r.profileSettingTheme, r.profileThemeDark),
  ].join('');

  return `<section class="profile-page">
  <header class="profile-hero">
    <div class="profile-hero__avatar">${avatar}</div>
    <div class="profile-hero__copy">
      <div class="profile-hero__identity">
        <h2 class="profile-hero__name">${esc(profile?.name || r.profileYou)}</h2>
        ${tier ? `<span class="profile-pill profile-pill--rank">${esc(state.rankName)} · ${esc(String(r.profileRankOf).replace('{n}', String(tier)).replace('{t}', String(state.rankTotal)))}</span>` : ''}
        ${planName ? `<span class="profile-pill profile-pill--plan ds-data">${esc(planName)}</span>` : ''}
      </div>
      <p class="profile-hero__meta">${identity}${tier ? ` <span class="profile-hero__dot"></span> ${esc(state.band)}` : ''}</p>
      <div class="profile-xp">
        ${state.known && state.nextRankName
          ? `<div class="profile-xp__head"><span class="ds-data">${esc(`${state.mastered.toLocaleString()} ${r.progressTierWords}`)}</span><span class="ds-data profile-xp__to">${esc(`${r.profileRankTo} ${state.nextRankName}`.replace('{n}', state.nextRankRemaining.toLocaleString()))}</span></div>`
            + `<span class="profile-xp__bar"><span style="inline-size:${rankProgress(state)}%"></span></span>`
          : `<div class="profile-xp__head"><span class="ds-data metric-unavailable">${esc(r.profileXpUnavailable)}</span></div>`
            + `<span class="profile-xp__bar" data-unavailable aria-hidden="true"></span>`}
      </div>
    </div>
    <div class="profile-actions">
      <button type="button" class="profile-action" disabled title="${esc(r.profileSoon)}" aria-label="${esc(`${r.profileShare} — ${r.profileSoon}`)}">${icon('share-network', { size: 17 })}<span>${esc(r.profileShare)}</span></button>
      <button type="button" class="profile-action" data-preference>${icon('pencil-simple', { size: 17 })}<span>${esc(r.profileEdit)}</span></button>
    </div>
  </header>
  <div class="profile-columns">
    <section class="profile-panel profile-panel--settings">
      <h3 class="profile-panel__title">${esc(r.profileSettingsTitle)}</h3>
      ${settings}
    </section>
    <section class="profile-panel profile-panel--quota">
      <div class="profile-panel__head">
        <h3 class="profile-panel__title">${esc(r.profileQuotaTitle)}</h3>
        ${planName ? `<span class="ds-data profile-panel__meta">${esc(planName)}</span>` : ''}
      </div>
      ${quotas
        ? `<div class="quota-list">${quotas}</div>`
        : `<p class="profile-panel__note">${esc(r.profileQuotaUnavailable)}</p>`}
      <p class="profile-panel__note profile-panel__note--foot">${esc(r.profileQuotaNote)}</p>
    </section>
  </div>
</section>`;
}

export async function renderProfile(root, ctx) {
  let released = false;
  const r = refCopy(ctx);
  const paint = (html) => {
    if (!released && ctx.alive()) root.innerHTML = html;
  };
  paint(`<section class="profile-page" aria-busy="true"><div class="profile-hero"><span class="skeleton profile-hero__avatar"></span><div class="profile-hero__copy"><span class="skeleton skeleton--title"></span><span class="skeleton skeleton--line"></span></div></div></section>`);

  const [accountResult, profileResult, wordsResult] = await Promise.allSettled([
    ctx.api.productMe(),
    ctx.api.learnerProfile ? ctx.api.learnerProfile() : Promise.resolve(ctx.profile || {}),
    /* Counts and rank only - no saved word is read to draw this page. A
       failure here costs the crystal, never the page: the ring falls back to
       the plain well rather than to a rank nobody counted. */
    ctx.api.libraryVocabularySummary(),
  ]);
  if (released || !ctx.alive()) return () => {};
  const account = accountResult.status === 'fulfilled' ? accountResult.value : null;
  const profile = profileResult.status === 'fulfilled' ? profileResult.value : ctx.profile || {};
  if (!account) {
    /* The plan is the page's subject, so an unreadable account is said plainly
       rather than drawn as a plan with nothing in it. */
    paint(`<section class="profile-page"><div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 20 })}<div><strong>${esc(r.profileUnavailable)}</strong></div><button type="button" class="outline" data-profile-retry>${icon('arrow-counter-clockwise', { size: 16 })}<span>${esc(ctx.c.retry)}</span></button></div></section>`);
    root.querySelector('[data-profile-retry]')?.addEventListener('click', () => renderProfile(root, ctx));
    return () => { released = true; };
  }
  const vocabulary = wordsResult.status === 'fulfilled' ? wordsResult.value : null;
  paint(profileSection(ctx, { account, profile, vocabulary }));
  return () => {
    released = true;
  };
}
