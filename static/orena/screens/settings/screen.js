/* Settings (frame 26-Settings.html, D-091). A focus route (shell/routes.js `settings.focus`),
   reached only from Profile's action list, with five tabs as local UI state on one route
   (`?tab=`, matching Profile's own `ctx.href('settings', {}, { tab: 'plan' })` link) - not five
   routes, the same pattern Progress already establishes for its own six tabs.

   Real data only (Design Contract rule 40 - model.js explains the shape, this reads it):
   - Languages: GET /api/platform/languages (target/support options + active), the shell's own
     profile (support_language), the device's chosen interface (copy/index.js).
   - Learning: product/reader-settings.js (reader text size), product/transcript-stage.js
     (transcript auto-scroll, translation-under-transcript default).
   - Review: the device's own review settings (product/recall-modes.js, via shell/context.js's
     `memory`).
   - Notifications: no real source anywhere (model.js, UI_BACKEND_GAPS.md N-28) - every row drawn
     disabled.
   - Plan & privacy: GET /api/product/commerce (plan, writing-review quota),
     capabilities/mic-readiness.js (microphone), a real navigation to Progress's History tab.
   Every row the backend cannot back is drawn with its real (never invented) fallback value and
   an inert control (rule 40/43) - see docs/project/UI_BACKEND_GAPS.md N-25..N-31 (renumbered from
   this section's earlier N-11..N-17 once N-11 collided with Word Detail's own gap; model.js's own
   per-row comments already cite the current ids). */
import { html, mount } from '../../kit/html.js';
import { useStyles } from '../../kit/styles.js';
import { listRow, segmentedControl, pageHeader } from '../../kit/components.js';
import { toast } from '../../kit/toast.js';
import { api } from '../../infrastructure/api.js';
import { shellCopy } from '../../copy/shell.js';
import { chooseInterface, languages as copyLanguages, setSupportFromProfile } from '../../copy/index.js';
import { updateContext, refreshCounts } from '../../shell/context.js';
import { learnerMemory } from '../../product/memory.js';
import { learningLanguage } from '../../product/languages.js';
import { readReaderSettings, writeReaderSettings, sizeBucketOf, SIZE_BUCKETS } from '../../product/reader-settings.js';
import { readStage, writeStage, transcriptDefaults } from '../../product/transcript-stage.js';
import { readReviewSettings } from '../../product/recall-modes.js';
import { MIC_STATES, watchMicrophone } from '../../capabilities/mic-readiness.js';
import { t } from './copy.js';
import { TABS, tabFromQuery, rowsForTab, barPercent } from './model.js';

const TAB_LABEL_KEY = { languages: 'tabLanguages', learning: 'tabLearning', review: 'tabReview', notifications: 'tabNotifications', plan: 'tabPlan' };
/* Every row's sub reads t(`${id}Sub`) except these two: "Plan" has no chrome sub at all (its sub
   is the real plan name/description, assembled from data, not copy - see planSub() below), and
   "Writing reviews" shares the same "This month" text "Pronunciation minutes" already has its own
   copy of, rather than duplicating a second identical key. */
const SUB_KEY = { plan: null, writingReviews: 'thisMonth' };

function safeStorage() {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function rowLabel(row) {
  return t(`${row.id}Label`);
}

function planSub(row) {
  const parts = [row.planName, row.planDescription].filter(Boolean);
  return parts.join(' · ');
}

function rowSub(row) {
  if (row.id === 'plan') return planSub(row);
  const key = SUB_KEY[row.id] === undefined ? `${row.id}Sub` : SUB_KEY[row.id];
  return key ? t(key) : '';
}

/* Target/support/interface language option labels: a language's own name, translated for support
   and interface (their own endonym) but through shellCopy's existing `lang_en`/`lang_zh` keys for
   the target list (D-079: chrome, not the learning content, so it follows the interface language -
   the same choice app.js's own INTERFACE_NAMES/preferences dialog already makes), with the real
   native_name appended only when it differs from the translated name (English's does not). */
function targetOptionLabel(opt) {
  const key = `lang_${opt.code}`;
  const translated = shellCopy.has(key) ? shellCopy(key) : opt.name;
  // Compare against `translated` (the string actually about to render), not the backend's raw,
  // always-English `opt.name`: under a Chinese interface shellCopy('lang_zh') already resolves to
  // "中文", so comparing against the untranslated "Chinese" would still differ and wrongly append
  // the native name again, producing "中文 · 中文" (P1, independent review).
  return opt.nativeName && opt.nativeName !== translated ? `${translated} · ${opt.nativeName}` : translated;
}

function choiceOptions(row) {
  if (row.id === 'target') return row.options.map((opt) => ({ value: opt.code, label: targetOptionLabel(opt), selected: opt.code === row.value }));
  if (row.id === 'support') return row.options.map((opt) => ({ value: opt.code, label: opt.label, selected: opt.code === row.value }));
  if (row.id === 'interface') return row.options.map((opt) => ({ value: opt.code, label: opt.label, selected: opt.code === row.value }));
  if (row.id === 'readerSize') return row.options.map((size) => ({ value: size, label: t(`size${size}`), selected: size === row.value }));
  // sessionLength: plain numerals, identical in every locale.
  return row.options.map((value) => ({ value, label: value, selected: value === row.value }));
}

function toggleControl(row) {
  return html`<button type="button" class="s-settings-toggle" role="switch" aria-checked="${row.value ? 'true' : 'false'}" data-toggle="${row.id}" ${row.disabled ? 'disabled' : ''}><span class="s-settings-toggle__knob"></span></button>`;
}

function choiceControl(row) {
  const control = segmentedControl({ options: choiceOptions(row), name: row.id });
  return row.disabled ? html`<span class="s-settings-row__inert">${control}</span>` : control;
}

function barControl(row) {
  const pct = barPercent(row.used, row.limit);
  return html`<div class="s-settings-bar"><div class="s-settings-bar__labels"><span>${row.used}</span><span>${row.limit}</span></div><div class="s-settings-bar__track"><div class="s-settings-bar__fill" style="width:${pct}%"></div></div></div>`;
}

function actionControl(row) {
  const label = { plan: t('manageAction'), learnerAudio: t('deleteAudioAction'), history: t('openAction') }[row.id] || '';
  return html`<button type="button" class="s-settings-action" data-action-row="${row.id}" ${row.disabled ? 'disabled' : ''}>${label}</button>`;
}

function controlMarkup(row) {
  if (row.kind === 'toggle') return toggleControl(row);
  if (row.kind === 'choice') return choiceControl(row);
  if (row.kind === 'bar') return barControl(row);
  if (row.kind === 'action') return actionControl(row);
  return '';
}

function rowMarkup(row) {
  return listRow({
    tag: 'div',
    radius: 16,
    pad: '18px 20px',
    title: rowLabel(row),
    sub: rowSub(row),
    trailing: controlMarkup(row),
    dataset: { row: row.id },
  });
}

export default async function settingsScreen(element, ctx) {
  await useStyles('screens/settings/settings.css');
  const storage = safeStorage();

  const state = {
    tab: tabFromQuery(ctx.query.get('tab')),
    languagesData: null,
    commerce: null,
    mic: { on: false, state: undefined },
  };

  async function readMicState() {
    try {
      if (!navigator.permissions?.query) return { on: false, state: undefined };
      const status = await navigator.permissions.query({ name: 'microphone' });
      if (status.state === 'granted') return { on: true, state: MIC_STATES.READY };
      if (status.state === 'denied') return { on: false, state: MIC_STATES.DENIED };
      return { on: false, state: undefined };
    } catch {
      return { on: false, state: undefined };
    }
  }

  const [languagesData, commerce, mic] = await Promise.all([
    api.languages().catch(() => null),
    api.productCommerce().catch(() => null),
    readMicState(),
  ]);
  if (!ctx.isCurrent()) return undefined;
  state.languagesData = languagesData;
  state.commerce = commerce;
  state.mic = mic;

  function buildInputs() {
    const context = ctx.context;
    const stage = transcriptDefaults(readStage(storage || undefined));
    const reader = readReaderSettings(storage || undefined);
    // Never read raw: an unwritten device (a first visit, no `orena.encounters.*` key yet at
    // all) leaves `memory.value.reviewSettings` at its own literal `null` (product/memory.js's
    // own initial shape, only overwritten once something has been parsed from storage) -
    // `readReviewSettings(null)` is what turns that into the real default (typing/cloze/
    // dictation on), the same normalization ui/expression.js's own Review room already applies
    // every time it reads this same field.
    const reviewSettings = readReviewSettings(context.memory?.value?.reviewSettings);
    const writingEvaluate = state.commerce?.features?.['writing.evaluate'] || null;
    return {
      languages: {
        languages: state.languagesData?.languages,
        supportLanguages: state.languagesData?.support_languages,
        targetCode: context.language,
        supportCode: context.profile?.support_language || '',
        interfaceCode: copyLanguages().ui,
      },
      learning: {
        sizeBucket: sizeBucketOf(reader.size),
        autoscroll: stage.autoscroll,
        meaning: stage.meaning,
      },
      review: { modes: reviewSettings?.modes },
      plan: {
        plan: state.commerce?.plan || null,
        features: state.commerce?.features || {},
        micOn: state.mic.on,
        micState: state.mic.state,
      },
    };
  }

  function currentRows() {
    return rowsForTab(state.tab, buildInputs());
  }

  function paintShell() {
    mount(
      element,
      html`<div class="s-settings">
        ${pageHeader({ back: { label: shellCopy('back'), dataset: { go: ctx.href('profile') } }, title: shellCopy('settings') })}
        <div class="s-settings__tabs" data-scroll-region>${TABS.map((tab) => html`<button type="button" class="o-chip" aria-pressed="${tab === state.tab ? 'true' : 'false'}" data-tab="${tab}">${t(TAB_LABEL_KEY[tab])}</button>`)}</div>
        <div class="s-settings__body" data-scroll-region></div>
      </div>`,
    );
  }

  function paintTab() {
    const body = element.querySelector('.s-settings__body');
    if (!body) return;
    mount(body, html`${currentRows().map((row) => rowMarkup(row))}`);
  }

  function repaintTabsBar() {
    element.querySelectorAll('[data-tab]').forEach((el) => {
      el.setAttribute('aria-pressed', String(el.dataset.tab === state.tab));
    });
  }

  async function onTargetPick(code) {
    const context = ctx.context;
    if (!code || code === context.language) return;
    try {
      await api.setLanguage(code);
    } catch {
      toast(t('saveError'));
      return;
    }
    if (!ctx.isCurrent()) return;
    const nextLanguage = learningLanguage(code);
    const memory = learnerMemory(storage, context.owner, nextLanguage);
    updateContext({ language: nextLanguage, memory });
    refreshCounts().catch(() => {});
    paintTab();
  }

  async function onSupportPick(code) {
    const context = ctx.context;
    if (!code || code === (context.profile?.support_language || '')) return;
    try {
      const next = await api.patchLearnerProfile({ expected_version: context.profile?.version ?? '', support_language: code });
      if (!ctx.isCurrent()) return;
      updateContext({ profile: next });
      setSupportFromProfile(next);
      paintTab();
    } catch (error) {
      if (!ctx.isCurrent()) return;
      if (error?.status === 409) {
        try {
          const fresh = await api.learnerProfile();
          if (ctx.isCurrent()) updateContext({ profile: fresh });
        } catch {
          // The stale value stays; the toast already says to reopen Settings.
        }
        toast(t('conflictError'));
      } else {
        toast(t('saveError'));
      }
      paintTab();
    }
  }

  function onInterfacePick(code) {
    if (!code || code === copyLanguages().ui) return;
    // Device-only: chooseInterface's onLanguageChange listener (main.js) repaints the shell and
    // re-runs the router, which remounts this screen fresh in the new interface language - no
    // local repaint needed or safe to race against that remount.
    chooseInterface(code);
  }

  function onReaderSizePick(size) {
    const bucket = SIZE_BUCKETS[size];
    if (bucket == null) return;
    const settings = readReaderSettings(storage || undefined);
    writeReaderSettings({ ...settings, size: bucket }, storage || undefined);
    paintTab();
  }

  function onChoicePick(rowId, value) {
    const row = currentRows().find((r) => r.id === rowId);
    if (!row || row.disabled) return;
    if (rowId === 'target') return onTargetPick(value);
    if (rowId === 'support') return onSupportPick(value);
    if (rowId === 'interface') return onInterfacePick(value);
    if (rowId === 'readerSize') return onReaderSizePick(value);
    // sessionLength is always disabled today (model.js) - nothing to wire.
  }

  function onStageToggle(field) {
    const stage = transcriptDefaults(readStage(storage || undefined));
    stage[field] = !stage[field];
    writeStage(stage, storage || undefined);
    paintTab();
  }

  function onReviewModeToggle(field) {
    const memory = ctx.context.memory;
    if (!memory) return;
    const current = readReviewSettings(memory.value?.reviewSettings);
    memory.setReview({ ...current, modes: { ...current.modes, [field]: !current.modes[field] } });
    paintTab();
  }

  function onMicToggle() {
    const watcher = watchMicrophone({
      onState: (info) => {
        if (info.state === MIC_STATES.READY) {
          state.mic = { on: true, state: MIC_STATES.READY };
        } else {
          state.mic = { on: false, state: info.state };
          if (info.state === MIC_STATES.DENIED) toast(t('micDeniedToast'));
        }
        watcher.stop();
        if (ctx.isCurrent()) paintTab();
      },
    });
  }

  const REVIEW_FIELD = { targetMeaning: 'typing', sourceAware: 'cloze', audioWord: 'dictation' };

  function onToggle(id) {
    const row = currentRows().find((r) => r.id === id);
    if (!row || row.disabled) return;
    if (id === 'autoscroll' || id === 'meaning') return onStageToggle(id);
    if (REVIEW_FIELD[id]) return onReviewModeToggle(REVIEW_FIELD[id]);
    if (id === 'mic') return onMicToggle();
  }

  function onAction(id) {
    const row = currentRows().find((r) => r.id === id);
    if (!row || row.disabled) return;
    if (id === 'history') return ctx.go(ctx.href('progress', {}, { tab: 'history' }));
  }

  function onClick(event) {
    const tabBtn = event.target.closest('[data-tab]');
    if (tabBtn) {
      state.tab = tabBtn.dataset.tab;
      repaintTabsBar();
      paintTab();
      return;
    }
    const toggleBtn = event.target.closest('[data-toggle]');
    if (toggleBtn) return onToggle(toggleBtn.dataset.toggle);
    const segOpt = event.target.closest('.c-seg__opt');
    if (segOpt) {
      const group = segOpt.closest('[data-seg]');
      if (group) return onChoicePick(group.dataset.seg, segOpt.dataset.value);
      return;
    }
    const actionBtn = event.target.closest('[data-action-row]');
    if (actionBtn) return onAction(actionBtn.dataset.actionRow);
  }

  paintShell();
  element.addEventListener('click', onClick);
  paintTab();

  return () => element.removeEventListener('click', onClick);
}

// Exported for the node gate (scripts/test_orena_screen_settings.mjs): the DOM-free row-shaping
// helpers model.js cannot cover itself (label/sub copy-key mapping, choice-option labels).
export const __internal = { rowLabel, rowSub, planSub, targetOptionLabel, choiceOptions };
