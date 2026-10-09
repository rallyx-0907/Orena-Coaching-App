/* AI & Models, wired: the four pages of ai-pages.js over the shared controller
   (capabilities/admin-ai.js), which owns every request. This file owns only what a browser page
   needs - which page, the draft the operator is editing, one event listener, focus kept across a
   repaint. The requests go to the existing control plane through the shared client
   (capabilities/admin-api.js); nothing here has a fetch of its own. */
import { html, mount } from '../../kit/html.js';
import { toast } from '../../kit/toast.js';
import { languages } from '../../copy/index.js';
import { adminApi } from '../../capabilities/admin-api.js';
import { createAiAdmin, credentialState, routeDraft, routingIsLive } from '../../capabilities/admin-ai.js';
import { t } from './copy.js';
import { capabilityPage, keyPage, listPage, loadFailed, providerPage, removeDialog } from './ai-pages.js';
import { dialog, pageHead, skeleton } from './blocks.js';
import { validateKey } from './model.js';

/* A selector for the control that had focus, so a repaint can give it back. */
function focusSelector(element) {
  if (!element || !element.dataset) return '';
  const { aInput, a, field, value, id, side, tab } = element.dataset;
  if (aInput) return `[data-a-input="${CSS.escape(aInput)}"]`;
  if (!a) return '';
  return `[data-a="${CSS.escape(a)}"]${field ? `[data-field="${CSS.escape(field)}"]` : ''}${value !== undefined ? `[data-value="${CSS.escape(value)}"]` : ''}${id ? `[data-id="${CSS.escape(id)}"]` : ''}${side ? `[data-side="${CSS.escape(side)}"]` : ''}${tab ? `[data-tab="${CSS.escape(tab)}"]` : ''}`;
}

function remember(container, paint) {
  const active = document.activeElement;
  const selector = active && container.contains(active) ? focusSelector(active) : '';
  const range = selector && typeof active.selectionStart === 'number' ? [active.selectionStart, active.selectionEnd] : null;
  paint();
  if (!selector) return;
  const again = container.querySelector(selector);
  if (!again) return;
  again.focus({ preventScroll: true });
  if (range && typeof again.setSelectionRange === 'function') again.setSelectionRange(range[0], range[1]);
}

export async function mountAi(shell, ctx) {
  const routeId = ctx.route.id;
  const view = {
    tab: ['route', 'tok'].includes(ctx.query.get('tab')) ? ctx.query.get('tab') : 'prov',
    usage: { days: 30, report: null, failed: false, loaded: false },
    query: '',
    id: ctx.params.id || '',
    form: { key: '', endpoint: null, model: '', busy: '', error: '', reason: '' },
    draft: null,
    draftFor: '',
    error: '',
    busy: false,
    dialog: null,
    loading: true,
    failed: false,
  };
  let alive = true;
  const controller = createAiAdmin({ onChange: () => paint() });

  function ensureDraft() {
    if (routeId !== 'adminCapability' || !controller.state.config) return;
    if (view.draft && view.draftFor === view.id) return;
    const capability = (controller.state.config.capabilities || []).find((item) => item.key === view.id);
    view.draft = capability ? routeDraft(capability, controller.state.providers) : null;
    view.draftFor = view.id;
  }

  function pending(body) {
    return html`<section class="a-page">${pageHead({ title: t('aiTitle'), sub: routeId === 'adminAi' ? t('aiSub') : '' })}${body}</section>`;
  }

  function build() {
    if (view.loading) return { title: t('aiTitle'), markup: pending(skeleton(t('loading'))) };
    if (view.failed || !controller.state.config) return { title: t('aiTitle'), markup: pending(html`<div class="a-blocks">${loadFailed(t)}</div>`) };
    ensureDraft();
    const args = { state: controller.state, view, t, ui: languages().ui, href: ctx.href, now: Date.now() };
    if (routeId === 'adminProvider') return providerPage(args);
    if (routeId === 'adminProviderKey') return keyPage(args);
    if (routeId === 'adminCapability') return view.draft ? capabilityPage(args) : capabilityPage({ ...args, view: { ...view, draft: routeDraft({}, []) } });
    return listPage(args);
  }

  function paintDialog() {
    if (!view.dialog) {
      mount(shell.layer, '');
      return;
    }
    const content = removeDialog({ state: controller.state, providerId: view.dialog.providerId, typed: view.dialog.typed, t });
    if (!content) {
      view.dialog = null;
      mount(shell.layer, '');
      return;
    }
    mount(shell.layer, dialog(content));
    shell.layer.querySelector('[data-a-typed]')?.focus({ preventScroll: true });
  }

  function paint() {
    if (!alive) return;
    const page = build();
    shell.setTitle(page.title);
    if (page.crumb) ctx.setCrumb(page.crumb);
    shell.setFilter({ enabled: routeId === 'adminAi' && view.tab !== 'tok' && !view.loading && !view.failed, value: view.query });
    remember(shell.page, () => mount(shell.page, page.markup));
  }

  async function load() {
    view.loading = true;
    view.failed = false;
    paint();
    try {
      await controller.loadCore();
    } catch (error) {
      if (!alive || error?.name === 'AbortError') return;
      view.failed = true;
    }
    if (!alive) return;
    view.loading = false;
    paint();
    if (!view.failed) controller.loadCatalog().catch(() => {});
    if (!view.failed && view.tab === 'tok') loadUsage();
  }

  /* Token usage reads the AI cost ledger for the chosen period; a late answer for a period the operator left is dropped. */
  async function loadUsage() {
    const days = view.usage.days;
    view.usage.report = null;
    view.usage.failed = false;
    view.usage.loaded = true;
    paint();
    let report = null;
    let failed = false;
    try {
      report = await adminApi.aiCosts(days);
    } catch (error) {
      if (error?.name === 'AbortError') return;
      failed = true;
    }
    if (!alive || view.usage.days !== days) return;
    view.usage.report = report;
    view.usage.failed = failed;
    paint();
  }

  const capability = () => (controller.state.config?.capabilities || []).find((item) => item.key === view.id);
  const provider = (id) => controller.state.providers.find((item) => item.id === id);

  /* A provider picked for a side: its default model, else the first it offers. */
  function firstModel(id) {
    const chosen = provider(id);
    if (!chosen) return '';
    return chosen.models.includes(chosen.default_model) ? chosen.default_model : chosen.models[0] || '';
  }

  function pick(field, value) {
    if (routeId === 'adminProviderKey') {
      if (field === 'model') view.form.model = value;
    } else if (view.draft) {
      view.draft[field] = value;
      if (field === 'provider') view.draft.model = firstModel(value);
      if (field === 'backup_provider') view.draft.backup_model = value ? firstModel(value) : '';
      view.error = '';
    }
    paint();
  }

  async function saveKey(withTest) {
    const target = provider(view.id);
    if (!target) return;
    const needsKey = credentialState(target) !== 'not_required';
    const failure = validateKey(view.form.key, { required: needsKey });
    if (failure) {
      view.form.error = failure;
      view.form.reason = '';
      paint();
      return;
    }
    view.form.error = '';
    view.form.reason = '';
    view.form.busy = withTest ? 'verifying' : 'saving';
    paint();
    const result = await controller.saveProvider(view.id, {
      baseUrl: view.form.endpoint ?? target.configuration?.endpoint_url ?? '',
      apiKey: view.form.key,
      defaultModel: view.form.model || target.default_model || '',
      remember: withTest,
    });
    if (!alive) return;
    view.form.busy = '';
    if (!result.ok) {
      view.form.reason = result.reason || t('healthError_unknown');
      paint();
      return;
    }
    view.form.key = '';
    toast(t('keySaved'));
    ctx.go(ctx.href('adminProvider', { id: view.id }));
  }

  async function saveRoute() {
    view.busy = true;
    view.error = '';
    paint();
    const result = await controller.saveRoute(view.id, view.draft);
    if (!alive) return;
    view.busy = false;
    if (result.ok) {
      view.draft = null;
      toast(t(routingIsLive(controller.state.config) ? 'routeSaved' : 'routeSavedLegacy'));
    } else {
      view.error = t('routeRejected', { reason: result.reason || t('healthError_unknown') });
    }
    paint();
  }

  async function removeKey() {
    const id = view.dialog?.providerId;
    if (!id) return;
    const result = await controller.removeProvider(id);
    if (!alive) return;
    view.dialog = null;
    paintDialog();
    if (result.ok) toast(t('keyRemoved'));
    else toast(result.reason || t('healthError_unknown'));
    paint();
  }

  function onClick(event) {
    const control = event.target.closest?.('[data-a]');
    if (!control || !shell.page.contains(control)) return;
    /* A row that opens another place also holds buttons: the button acts, the row does not. */
    event.stopPropagation();
    event.preventDefault();
    if (control.disabled) return;
    const { a, id, field, value, side, tab, to } = control.dataset;
    if (a === 'tab') {
      view.tab = tab;
      paint();
      if (tab === 'tok' && !view.usage.loaded) loadUsage();
    } else if (a === 'tk-period') {
      view.usage.days = Number(value) || 30;
      loadUsage();
    } else if (a === 'go') ctx.go(to);
    else if (a === 'reload') load();
    else if (a === 'test-provider') controller.testProvider(id);
    else if (a === 'open-key') ctx.go(ctx.href('adminProviderKey', { id }));
    else if (a === 'ask-remove') {
      view.dialog = { providerId: id, typed: '' };
      paintDialog();
    } else if (a === 'pick') pick(field, value);
    else if (a === 'toggle') {
      view.draft.enabled = !view.draft.enabled;
      view.error = '';
      paint();
    } else if (a === 'test-route') controller.testRoute(view.id, side === 's');
    else if (a === 'discard-route') {
      view.draft = routeDraft(capability(), controller.state.providers);
      view.error = '';
      paint();
    } else if (a === 'save-route') saveRoute();
    else if (a === 'save-key') saveKey(control.dataset.test === '1');
  }

  function onInput(event) {
    const input = event.target.closest?.('[data-a-input]');
    if (!input) return;
    if (input.dataset.aInput === 'key') view.form.key = input.value;
    if (input.dataset.aInput === 'endpoint') view.form.endpoint = input.value;
    if (input.dataset.aInput === 'model') view.form.model = input.value;
    if (view.form.error) {
      view.form.error = '';
      input.classList.remove('a-input--invalid');
      shell.page.querySelector('.a-error')?.remove();
    }
  }

  function onFilter() {
    view.query = shell.filter.value;
    if (routeId === 'adminAi') paint();
  }

  function onLayerClick(event) {
    const control = event.target.closest?.('[data-a]');
    if (!control) return;
    if (control.dataset.a === 'dialog-cancel') {
      view.dialog = null;
      paintDialog();
    } else if (control.dataset.a === 'dialog-confirm' && !control.disabled) removeKey();
  }

  /* Typing the provider's name arms the removal; repainting on each key would take the focus. */
  function onLayerInput(event) {
    const field = event.target.closest?.('[data-a-typed]');
    if (!field || !view.dialog) return;
    view.dialog.typed = field.value;
    const content = removeDialog({ state: controller.state, providerId: view.dialog.providerId, typed: field.value, t });
    const confirm = shell.layer.querySelector('[data-a="dialog-confirm"]');
    if (confirm && content) confirm.disabled = !content.ready;
  }

  function onKey(event) {
    if (event.key === 'Escape' && view.dialog) {
      view.dialog = null;
      paintDialog();
    }
  }

  shell.page.addEventListener('click', onClick);
  shell.page.addEventListener('input', onInput);
  shell.layer.addEventListener('click', onLayerClick);
  shell.layer.addEventListener('input', onLayerInput);
  shell.filter.addEventListener('input', onFilter);
  document.addEventListener('keydown', onKey);

  /* Not awaited: the page draws its skeleton at once and the shell hands back the cleanup, so leaving
     mid-load stops this page painting. */
  load();

  return () => {
    alive = false;
    shell.page.removeEventListener('click', onClick);
    shell.page.removeEventListener('input', onInput);
    shell.layer.removeEventListener('click', onLayerClick);
    shell.layer.removeEventListener('input', onLayerInput);
    shell.filter.removeEventListener('input', onFilter);
    document.removeEventListener('keydown', onKey);
  };
}
