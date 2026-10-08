/* The live conversation, carried across a navigation (human request 2026-10-06): when Orena opens a place
   the learner asked for, the learner keeps talking to Orena there. The Home screen hands its live voice engine
   here instead of ending it, and a small floating pill - Orena's mark, what Orena is doing, Stop - follows the
   learner on every route until they stop or the session ends. Going back to Orena takes the engine back.

   Only a live (§9) session is carried; the device cascade ends with its screen, as before. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { intelChip } from '../../kit/brand.js';
import { useStyles } from '../../kit/styles.js';
import { t } from './copy.js';
import { voicePhaseStatusKey } from './model.js';

let docked = null; // { engine, host }

function paint() {
  if (!docked) return;
  const { engine, host } = docked;
  const state = engine.state();
  if (!state.session) return release(true);
  mount(host, html`<div class="s-orena-dock__pill s-orena-dock__pill--${state.phase}" role="status">
    ${intelChip({ size: 30, mark: 24 })}
    <span class="s-orena-dock__status">${t(voicePhaseStatusKey(state.phase))}</span>
    <button type="button" class="s-orena-dock__stop" data-dock-stop aria-label="${t('stop')}" title="${t('stop')}">${raw(icon('square', { size: 12 }))}</button>
  </div>`);
  host.querySelector('[data-dock-stop]')?.addEventListener('click', () => {
    engine.main(); // in a live session the main action ends it
    release(true);
  });
}

function release(dispose) {
  if (!docked) return null;
  const { engine, host } = docked;
  docked = null;
  host.remove();
  if (dispose) engine.dispose();
  return engine;
}

/* Keep a live engine running after its screen leaves. Returns false when there is nothing live to keep. */
export function dockVoice(engine) {
  if (!engine?.state?.().session) return false;
  release(true);
  const host = document.createElement('div');
  host.className = 's-orena-dock';
  document.body.append(host);
  docked = { engine, host };
  engine.setOnChange?.(paint);
  void useStyles('screens/orena/orena.css').then(paint);
  paint();
  return true;
}

/* The Home screen takes its conversation back (and draws it in its own voice row). */
export function undockVoice() {
  return release(false);
}
