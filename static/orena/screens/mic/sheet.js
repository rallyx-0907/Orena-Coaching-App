/* The Mic state sheet (frame 62, E2 §11): the one shared modal for every microphone-permission /
   recording-failure state across Speaking (and any other room that records). Not a route - a
   centred sheet any caller opens over whatever it is doing.

   `openMicState(ctx, { state, onAction, textFallback })` renders one of the six drawn states and
   reports which action was pressed; the caller decides what that action does (retry the recording,
   keep the attempt, …) and, unless its `onAction` returns `false`, the sheet then closes itself -
   matching the source, where every button here ends in either `close()` or `run()` (which itself
   closes before resuming). The one state that needs to stay open across an async step (retrying
   real microphone access without a flash of "closed, then reopened") returns `false` and manages
   its own close.

   `micGate(ctx, start)` is the other half: it is what actually decides *whether* to show
   `permission`/`blocked` at all, from `capabilities/mic-readiness.js`'s real
   `navigator.mediaDevices.getUserMedia` outcome - never a simulated scenario. The four
   post-recording states (`notheard`/`noisy`/`provider`/`offline`) are not this module's to decide;
   only a real recording attempt and its own assessment call know which of those applies, so a
   caller reaches them by calling `openMicState` directly once it knows. */
import { openSheet } from '../../kit/overlay.js';
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { toast } from '../../kit/toast.js';
import { watchMicrophone, MIC_STATES } from '../../capabilities/mic-readiness.js';
import { t } from './copy.js';
import { micStateSpec, gateStateFor } from './model.js';

/* Session-scoped: once the browser has actually granted the microphone this visit, later gated
   actions go straight through - the browser itself remembers the grant, so asking again inside the
   same visit would be asking a question already answered. Resets on reload, matching the source's
   own `b6.mic.granted` being fresh per session. */
let granted = false;

function actionMarkup(action) {
  return html`<button type="button" class="s-mic__action s-mic__action--${action.variant}" data-action="${action.key}">${t(action.labelKey)}</button>`;
}

function bodyMarkup(spec) {
  return html`
    <div class="s-mic__icon" style="background:${spec.iconBg};color:${spec.iconColor}">${raw(icon('mic', { size: 28 }))}</div>
    <div class="s-mic__title">${t(spec.titleKey)}</div>
    <div class="s-mic__body">${t(spec.bodyKey)}</div>
    ${spec.stepsKey ? html`<div class="s-mic__steps">${t(spec.stepsKey)}</div>` : ''}
    <div class="s-mic__actions">${spec.actions.map(actionMarkup)}</div>
  `;
}

/* Opens the sheet for one of the six drawn states. `onAction(key, handle)` fires on any button
   press; returning `false` keeps the sheet open (the caller closes it itself, once its own async
   step resolves) - every other return value closes it, matching the source (every action here ends
   the sheet, directly or through `run()`). No head, no close button (the frame draws none): the
   shared scrim and Escape, already wired by kit/overlay.js, are the only other way out. */
export async function openMicState(ctx = {}, { state, onAction, textFallback = true } = {}) {
  const spec = micStateSpec(state, { textFallback });
  if (!spec) return null;
  await useStyles('screens/mic/mic.css');
  if (ctx.isCurrent && !ctx.isCurrent()) return null;
  const handle = openSheet({
    label: t(spec.titleKey),
    className: 's-mic',
    scrim: true,
    render(element, sheetHandle) {
      mount(element, bodyMarkup(spec));
      element.querySelectorAll('[data-action]').forEach((button) => {
        button.addEventListener('click', async () => {
          const result = onAction ? await onAction(button.dataset.action, sheetHandle) : undefined;
          if (result !== false) sheetHandle.close();
        });
      });
      return null;
    },
  });
  return handle;
}

async function checkReadiness() {
  return new Promise((resolve) => {
    // watchMicrophone reports `checking` synchronously, before its own return value can be
    // assigned to a local - a bare `const watcher = watchMicrophone({ onState: () =>
    // watcher.stop() })` throws "Cannot access 'watcher' before initialization" on every call, so
    // every mic gate ("Allow microphone") crashed instead of ever reaching a real ready/denied
    // outcome. `let` plus a `checking`-state guard fixes both: the callback only ever runs once
    // the initializer has returned, and only a terminal state resolves/stops the probe.
    let watcher;
    watcher = watchMicrophone({
      onState: (info) => {
        if (info.state === MIC_STATES.CHECKING) return;
        watcher.stop();
        resolve(info);
      },
    });
  });
}

/* Runs `start()` once the microphone is actually ready, asking first when it has not been this
   session and explaining plainly when the browser has refused it - never a silent failure and
   never a guessed permission state. */
export async function micGate(ctx, start) {
  if (granted) {
    start();
    return;
  }
  await openMicState(ctx, {
    state: 'permission',
    onAction: async (key, handle) => {
      if (key !== 'allow') return undefined; // 'dismiss': close, nothing runs.
      const outcome = await checkReadiness();
      const next = gateStateFor(outcome.state);
      if (!next) {
        granted = true;
        handle.close();
        start();
        return false;
      }
      handle.close();
      openBlocked(ctx, start);
      return false;
    },
  });
}

function openBlocked(ctx, start) {
  return openMicState(ctx, {
    state: 'blocked',
    onAction: async (key, handle) => {
      if (key === 'typeInstead') {
        toast(t('micOffTypeInstead'));
        return undefined;
      }
      if (key === 'close') return undefined;
      // 'retry'
      const outcome = await checkReadiness();
      if (!gateStateFor(outcome.state)) {
        granted = true;
        handle.close();
        start();
        return false;
      }
      toast(t('blockedStillBlocked'));
      return false;
    },
  });
}
