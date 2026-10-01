/* Onboarding (Onboarding.dc.html, frames 01-05; route 'welcome', bare - shell/routes.js). See
   model.js's header for what changed from the prototype script and why. A bare route draws no
   shell (shell/shell.css `[data-bare='1']`); this screen owns the whole viewport and, per Design
   Contract rule 49, never scrolls as a page - only `[data-scroll-region]` does. */
import { html, mount, raw } from '../../kit/html.js';
import { useStyles } from '../../kit/styles.js';
import { icon } from '../../kit/icons.js';
import { brandChip, intelChip, markGlyph } from '../../kit/brand.js';
import { api } from '../../infrastructure/api.js';
import { toast } from '../../kit/toast.js';
import { shellCopy } from '../../copy/shell.js';
import { chooseInterface, languages as copyLanguages, setSupportFromProfile } from '../../copy/index.js';
import { adoptLearningLanguage, updateContext } from '../../shell/context.js';
import { selectLearningLanguage } from '../../product/account-settings.js';
import { t } from './copy.js';
import {
  STEP_COUNT, STEPS, clampStep, stepDots,
  identityOf, targetOptions, targetLabel, supportOptions, interfaceOptions,
  levelsFor, defaultLevelCode, levelRow, declaredLevelPatch, greetingParams, languageName,
} from './model.js';

const STEP_LABEL_KEY = { welcome: 'stepWelcome', account: 'stepAccount', languages: 'stepLanguages', level: 'stepLevel', orena: 'stepOrena' };
const STEP_KEY = 'orena.onboarding.step';
const LEVEL_KEY = 'orena.onboarding.level';
/* The controls a re-render replaces: focus goes back to the same one (a pick keeps the learner's
   place for the keyboard), or to the step's heading when the step itself changed. */
const FOCUS_ATTRS = ['data-target', 'data-support', 'data-iface', 'data-level'];
/* A support or interface pick re-renders the whole app in the new language (copy/index.js's
   onLanguageChange remounts the route), so the control the learner was on, and how far the step had
   scrolled, are remembered outside the mounted screen and restored by the next mount. It lasts a few
   seconds and every click replaces it (a click on anything but a pick control replaces it with an
   empty one, and a step change clears it), so it is never stale. */
const REFOCUS_MS = 5000;
const NO_CARRY = Object.freeze({ selector: '', top: 0, at: 0 });
let carry = NO_CARRY;

function sessionStore() {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function localStore() {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/* The onboarding position and the level picked so far are session-only UI state (the same non-
   learner-owned convenience shell/router.js's own navOrigin/depth already keep) - never a
   completion flag, never sent anywhere. Completion is known from the profile existing (task
   brief), not from a stored step. */
function readStep(storage) {
  try {
    return clampStep(storage?.getItem(STEP_KEY));
  } catch {
    return 0;
  }
}

function readLevel(storage) {
  try {
    return String(storage?.getItem(LEVEL_KEY) || '');
  } catch {
    return '';
  }
}

function writeSession(storage, key, value) {
  try {
    if (value === '' || value == null) storage?.removeItem(key);
    else storage?.setItem(key, String(value));
  } catch {
    /* kept for this visit only */
  }
}

function targetGlyph(option) {
  return option.selected
    ? html`<span class="s-onboarding__target-check" aria-hidden="true">${raw(icon('check', { size: 14, stroke: 3 }))}</span>`
    : '';
}

export default async function onboardingScreen(element, ctx) {
  await useStyles('screens/onboarding/onboarding.css');
  const stepStorage = sessionStore();
  const memoryStorage = localStore();
  const context = ctx.context;

  const levelOnly = ctx.query?.get?.('step') === 'level';
  const state = {
    step: levelOnly ? STEPS.indexOf('level') : readStep(stepStorage),
    level: readLevel(stepStorage),
    languagesData: null,
    busy: '',
  };

  const languagesData = await api.languages().catch(() => null);
  if (!ctx.isCurrent()) return undefined;
  state.languagesData = languagesData;

  /* The grid of the learning language the learner is on: the levels the platform lists for it. */
  function levelGrid() {
    const listed = state.languagesData?.languages?.find?.((item) => item?.code === context.language)?.levels;
    return levelsFor(context.language, listed);
  }

  function setStep(next) {
    state.step = clampStep(next);
    writeSession(stepStorage, STEP_KEY, state.step);
    render({ heading: true });
  }

  /* ---- Step bodies -------------------------------------------------------------------------- */

  /* The step's one primary control. It rests where the frame draws it (after the content, or at the
     foot of the column) and sticks to the foot of the scroll region when the content is longer than
     the window (a long support-language list, a phone), so it is never scrolled out of reach. */
  function cta(action, label, place = '', disabled = false) {
    return html`<div class="s-onboarding__cta${place ? ` s-onboarding__cta--${place}` : ''}"><button type="button" class="o-btn o-btn--primary o-btn--block" data-action="${action}" ${disabled ? 'disabled' : ''}>${label}</button></div>`;
  }

  function welcomeBody() {
    return html`<section class="s-onboarding__panel s-onboarding__panel--welcome">
      <div class="s-onboarding__welcome-center">
        <div class="s-onboarding__hero"><span class="s-onboarding__glow" aria-hidden="true"></span>${intelChip({ size: 148, mark: 108 })}</div>
        <div class="s-onboarding__brandrow s-onboarding__brandrow--bare">${markGlyph({ size: 26 })}<span class="o-wordmark s-onboarding__wordmark--sm">Orena</span></div>
        <h1 class="s-onboarding__h1" tabindex="-1">${t('welcomeHeadline')}</h1>
        <p class="s-onboarding__lead">${t('welcomeSub')}</p>
      </div>
      ${cta('welcome-next', t('getStarted'), 'welcome')}
    </section>`;
  }

  function accountBody() {
    const id = identityOf(context.user);
    return html`<section class="s-onboarding__panel">
      <div class="s-onboarding__head"><h1 class="s-onboarding__title" tabindex="-1">${t('accountTitle')}</h1></div>
      <div class="s-onboarding__identity">
        <span class="s-onboarding__avatar o-avatar">${id.picture ? html`<img src="${id.picture}" alt="">` : id.initial}</span>
        <div class="s-onboarding__identity-body">
          <div class="s-onboarding__identity-name">${id.name}</div>
          ${id.email ? html`<div class="s-onboarding__identity-email">${id.email}</div>` : ''}
          <div class="s-onboarding__identity-provider">${id.google ? t('signedInGoogle') : t('signedInLocal')}</div>
        </div>
      </div>
      ${cta('account-next', t('cont'))}
    </section>`;
  }

  function languagesBody() {
    const ui = copyLanguages().ui;
    const targets = targetOptions(context.languageOptions, context.language);
    const supportCode = context.profile?.support_language || '';
    const supports = supportOptions(state.languagesData?.support_languages, supportCode);
    const ifaces = interfaceOptions(ui);
    return html`<section class="s-onboarding__panel s-onboarding__panel--languages">
      <div class="s-onboarding__head"><h1 class="s-onboarding__title" tabindex="-1">${t('langTitle')}</h1><p class="s-onboarding__subtitle">${t('langSub')}</p></div>
      <div class="s-onboarding__group s-onboarding__group--learning">
        <div class="s-onboarding__label">${t('learningLabel')}</div>
        <div class="s-onboarding__targets">${targets.map((tg) => {
          const label = targetLabel(tg, shellCopy(`lang_${tg.code}`), ui);
          return html`<button type="button" class="s-onboarding__target${tg.selected ? ' is-selected' : ''}" aria-pressed="${tg.selected ? 'true' : 'false'}" data-target="${tg.code}" ${state.busy === 'target' ? 'disabled' : ''}>
            <span class="s-onboarding__target-tile" lang="${tg.code}" aria-hidden="true" style="background:${tg.tint};font-family:${tg.font}">${tg.glyph}</span>
            <span class="s-onboarding__target-body"><span class="s-onboarding__target-name">${label}</span><span class="s-onboarding__target-sub">${t(tg.code === 'zh' ? 'targetSubZh' : 'targetSubEn')}</span></span>
            ${targetGlyph(tg)}
          </button>`;
        })}</div>
      </div>
      <div class="s-onboarding__group">
        <div class="s-onboarding__label">${t('supportLabel')}</div>
        <div class="s-onboarding__note-sub">${t('supportSub')}</div>
        <div class="s-onboarding__pills">${supports.map((sp) => html`<button type="button" class="s-onboarding__pill" lang="${sp.code}" aria-pressed="${sp.selected ? 'true' : 'false'}" data-support="${sp.code}" ${state.busy === 'support' ? 'disabled' : ''}>${sp.label}</button>`)}</div>
      </div>
      <div class="s-onboarding__group">
        <div class="s-onboarding__label">${t('ifaceLabel')}</div>
        <div class="s-onboarding__note-sub">${t('ifaceSub')}</div>
        <div class="s-onboarding__pills">${ifaces.map((ifc) => html`<button type="button" class="s-onboarding__pill" lang="${ifc.code}" aria-pressed="${ifc.selected ? 'true' : 'false'}" data-iface="${ifc.code}">${ifc.label}</button>`)}</div>
      </div>
      <div class="s-onboarding__note"><span class="s-onboarding__note-badge" aria-hidden="true">i</span><span class="s-onboarding__note-text">${t('langNote')}</span></div>
      ${cta('lang-next', t('cont'), 'languages')}
    </section>`;
  }

  function levelBody() {
    const levels = levelGrid();
    const row = levelRow(levels, state.level);
    return html`<section class="s-onboarding__panel">
      <div class="s-onboarding__head"><h1 class="s-onboarding__title" tabindex="-1">${t('pickTitle')}</h1><p class="s-onboarding__subtitle">${t('pickSub')}</p></div>
      <div class="s-onboarding__group s-onboarding__group--learning">
        <div class="s-onboarding__label">${t('adjustLabel')}</div>
        <div class="s-onboarding__levels">${levels.map((lv) => html`<button type="button" class="s-onboarding__level${lv.code === row.code ? ' is-selected' : ''}" aria-pressed="${lv.code === row.code ? 'true' : 'false'}" data-level="${lv.code}">
          <span class="s-onboarding__level-code">${lv.label}</span><span class="s-onboarding__level-name">${t(lv.nameKey)}</span>
        </button>`)}</div>
        <div class="s-onboarding__level-desc" lang="${t.lang(row.descKey)}">${t(row.descKey)}</div>
      </div>
      ${cta('level-next', t('cont'), '', state.busy === 'level')}
    </section>`;
  }

  /* The greeting is in the support language (explanation, D-079), with the two language names
     written in that same language - the learning language and the support language the learner just
     picked, from the platform's own names, never a hand-kept table. */
  function greetingLine() {
    const locale = t.lang('greeting');
    const params = greetingParams(context, copyLanguages().support, { levels: levelGrid(), picked: state.level });
    const values = {
      name: params.name,
      language: languageName(params.target, locale),
      level: params.level,
      support: languageName(params.support, locale),
    };
    return { text: t(params.name ? 'greeting' : 'greetingAnon', values), locale };
  }

  function orenaBody() {
    const line = greetingLine();
    return html`<section class="s-onboarding__panel s-onboarding__panel--orena">
      <div class="s-onboarding__orena-head">${intelChip({ size: 56, mark: 44 })}<h1 class="s-onboarding__title" tabindex="-1">${t('meetTitle')}</h1></div>
      <div class="s-onboarding__log"><div class="s-onboarding__bubble">${intelChip({ size: 28, mark: 22, className: 's-onboarding__bubble-mark' })}<div class="s-onboarding__bubble-text" lang="${line.locale}">${line.text}</div></div></div>
      ${cta('finish', t('goToday'), 'finish', state.busy === 'finish')}
    </section>`;
  }

  const BODY = [welcomeBody, accountBody, languagesBody, levelBody, orenaBody];

  /* ---- Frame: aside step list (desktop) + top bar (back/progress) ---------------------------- */

  function asideMarkup() {
    const dots = stepDots(state.step, STEPS.map((id) => t(STEP_LABEL_KEY[id])));
    return html`<aside class="s-onboarding__aside">
      <div class="s-onboarding__brandrow">${brandChip({ size: 40, mark: 30 })}<span class="o-wordmark s-onboarding__wordmark--lg">Orena</span></div>
      <div class="s-onboarding__asidehero">
        <div class="s-onboarding__ahero"><span class="s-onboarding__glow" aria-hidden="true"></span><span class="s-onboarding__disc" aria-hidden="true"><svg viewBox="0 0 100 100"><use href="#ol-intel"></use></svg></span></div>
        <div class="s-onboarding__abrand">${t('brandTitle')}</div>
        <div class="s-onboarding__asub">${t('brandSub')}</div>
      </div>
      <div class="s-onboarding__steplist">${dots.map((d, i) => html`<div class="s-onboarding__stepitem${d.current ? ' is-current' : ''}${d.done ? ' is-done' : ''}"><span class="s-onboarding__stepdot">${d.done ? raw(icon('check', { size: 12, stroke: 3 })) : String(i + 1)}</span>${d.label}</div>`)}</div>
    </aside>`;
  }

  function topbarMarkup() {
    if (state.step === 0) return '';
    const bars = [1, 2, 3, 4].map((i) => html`<span class="s-onboarding__bar${i <= state.step ? ' is-filled' : ''}"></span>`);
    return html`<div class="s-onboarding__topbar">
      <button type="button" class="s-onboarding__back" data-action="back" aria-label="${shellCopy('back')}">${raw(icon('chevron-left', { size: 20 }))}</button>
      <div class="s-onboarding__bars">${bars}</div>
      <span class="s-onboarding__count">${state.step} / ${STEP_COUNT - 1}</span>
    </div>`;
  }

  function focusSelector(node) {
    if (!node || !element.contains(node)) return '';
    const attr = FOCUS_ATTRS.find((name) => node.hasAttribute(name));
    return attr ? `[${attr}="${CSS.escape(node.getAttribute(attr))}"]` : '';
  }

  function scrollRegion() {
    return element.querySelector('[data-scroll-region]');
  }

  function carried() {
    return Date.now() - carry.at < REFOCUS_MS ? carry : NO_CARRY;
  }

  /* Focus the control the learner was on (or, after a step change, that step's heading). A control
     disabled while its request runs cannot take focus; the render that re-enables it does. */
  function applyFocus(selector) {
    const node = selector ? element.querySelector(selector) : null;
    if (!node || node.disabled) return;
    node.focus({ preventScroll: true });
  }

  /* A re-render replaces the scroll region, so a pick that keeps the learner on the step keeps how far
     they had scrolled (a long support-language list: the pick must not throw them back to the top). */
  function render({ heading = false, top = null } = {}) {
    if (heading) carry = NO_CARRY;
    const keepFocus = heading ? '' : focusSelector(document.activeElement) || carried().selector;
    const keepTop = heading ? 0 : top ?? scrollRegion()?.scrollTop ?? 0;
    mount(
      element,
      html`<div class="s-onboarding">
        ${asideMarkup()}
        <div class="s-onboarding__main">
          ${topbarMarkup()}
          <div class="s-onboarding__body" data-scroll-region>
            <div class="s-onboarding__col">${BODY[state.step]()}</div>
          </div>
        </div>
      </div>`,
    );
    const region = scrollRegion();
    if (region && keepTop) region.scrollTop = keepTop;
    if (heading) element.querySelector('.s-onboarding__col [tabindex="-1"]')?.focus({ preventScroll: true });
    else applyFocus(keepFocus);
  }

  /* ---- Actions -------------------------------------------------------------------------------- */

  /* A profile change against the version the shell holds. A 409 means the profile moved on (another
     device, or the learning language just changed - a profile is kept per learning language): read
     it again and send the same change once more, so the learner's tap is never silently dropped. */
  async function patchProfile(fields) {
    let version = context.profile?.version ?? '';
    for (let attempt = 0; ; attempt += 1) {
      try {
        return await api.patchLearnerProfile({ expected_version: version, ...fields });
      } catch (error) {
        if (error?.status !== 409 || attempt >= 1) throw error;
        const fresh = await api.learnerProfile();
        updateContext({ profile: fresh });
        version = fresh?.version ?? '';
      }
    }
  }

  async function pickTarget(code) {
    if (!code || code === context.language || state.busy) return;
    state.busy = 'target';
    render();
    try {
      await selectLearningLanguage(code);
    } catch {
      state.busy = '';
      toast(t('saveError'));
      render();
      return;
    }
    /* The profile is per learning language: the support language, the declared level and its
       version the shell holds are the previous language's until read again. The context is the
       shell's, so it is brought up to date even if the screen was left meanwhile. */
    await adoptLearningLanguage(code, memoryStorage || undefined);
    if (!ctx.isCurrent()) return;
    state.busy = '';
    state.level = '';
    writeSession(stepStorage, LEVEL_KEY, '');
    render();
  }

  async function pickSupport(code) {
    if (!code || code === (context.profile?.support_language || '') || state.busy) return;
    state.busy = 'support';
    render();
    let failed = false;
    try {
      const next = await patchProfile({ support_language: code });
      updateContext({ profile: next });
      // A changed support language repaints the whole app in it (copy/index.js), which remounts this
      // screen - the next mount picks the step, the focus and the scroll up again.
      setSupportFromProfile(next);
    } catch {
      failed = true;
    }
    if (!ctx.isCurrent()) return;
    state.busy = '';
    if (failed) toast(t('saveError'));
    render();
  }

  function pickInterface(code) {
    if (!code || code === copyLanguages().ui) return;
    // Device-only: chooseInterface's onLanguageChange listener (main.js) remounts this screen -
    // readStep() above restores this same step from sessionStorage, so no local repaint here (the
    // same reasoning settings/screen.js's own onInterfacePick already documents).
    chooseInterface(code);
  }

  function pickLevel(code) {
    if (!code) return;
    state.level = code;
    writeSession(stepStorage, LEVEL_KEY, code);
    render();
  }

  async function finishLevel() {
    if (state.busy) return;
    const code = levelRow(levelGrid(), state.level).code;
    state.level = code;
    writeSession(stepStorage, LEVEL_KEY, code);
    const listed = state.languagesData?.languages?.find?.((item) => item?.code === context.language)?.levels;
    const patch = declaredLevelPatch(code, listed, context.language);
    if (patch) {
      state.busy = 'level';
      render();
      try {
        const next = await patchProfile(patch);
        updateContext({ profile: next, level: String(next?.declared_level || '').trim() });
      } catch {
        // The level did not save. The flow never blocks on it and never claims it did (rule 40):
        // the shell's level below stays what the server holds, and Today offers the level again.
      }
    }
    if (!ctx.isCurrent()) return;
    state.busy = '';
    if (levelOnly) return leaveLevelOnly();
    setStep(state.step + 1);
  }

  /* The level question opened from Today's prompt (H-19): the same Level step, nothing replayed. It
     ends back at Today, and Back leaves without saving. */
  function leaveLevelOnly() {
    writeSession(stepStorage, STEP_KEY, 0);
    writeSession(stepStorage, LEVEL_KEY, '');
    ctx.go(ctx.href('today'));
  }

  function finish() {
    if (state.busy) return;
    state.busy = 'finish';
    carry = NO_CARRY;
    render();
    writeSession(stepStorage, STEP_KEY, 0);
    writeSession(stepStorage, LEVEL_KEY, '');
    ctx.go(ctx.href('today'));
  }

  function onClick(event) {
    const target = event.target.closest('[data-action], [data-target], [data-support], [data-iface], [data-level]');
    if (!target) return;
    carry = { selector: focusSelector(target), top: scrollRegion()?.scrollTop ?? 0, at: Date.now() };
    const action = target.dataset.action;
    if (action === 'back') return levelOnly ? leaveLevelOnly() : setStep(state.step - 1);
    if (action === 'welcome-next') return setStep(1);
    if (action === 'account-next') return setStep(2);
    if (action === 'lang-next') return setStep(3);
    if (action === 'level-next') return finishLevel();
    if (action === 'finish') return finish();
    if (target.dataset.target) return pickTarget(target.dataset.target);
    if (target.dataset.support) return pickSupport(target.dataset.support);
    if (target.dataset.iface) return pickInterface(target.dataset.iface);
    if (target.dataset.level) return pickLevel(target.dataset.level);
  }

  if (!state.level) state.level = defaultLevelCode(levelGrid());
  const restored = carried();
  render({ top: restored.top });
  // The router focuses the main region once a screen has mounted; a control carried over from before
  // a remount (the language pick that caused it) takes focus back right after that.
  if (restored.selector) {
    setTimeout(() => {
      if (ctx.isCurrent()) applyFocus(restored.selector);
    }, 0);
  }
  element.addEventListener('click', onClick);
  return () => element.removeEventListener('click', onClick);
}
