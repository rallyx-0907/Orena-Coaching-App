/* The brand mark and the Orena Intelligence mark (D-090), rendered from the one copy in the Art
   Bible package (assets/brand/orena/logo/orena-marks.svg, served at /orena-brand/logo/). The
   sprite is loaded once and inserted into the document so every <use href="#ol-…"> resolves and
   the marks' own CSS animations (kit/base.css oi-* keyframes) run. */
import { raw } from './html.js';

export const BRAND_SPRITE_URL = '/orena-brand/logo/orena-marks.svg';

/* The agent's states as the design draws them: idle spins and breathes, still is motionless,
   listening draws in, speaking pulses, thinking sways. */
export const INTEL_STATES = Object.freeze({
  idle: 'ol-intel',
  still: 'ol-intel-still',
  listening: 'ol-intel-listen',
  speaking: 'ol-intel-speak',
  thinking: 'ol-intel-think',
});

let loading = null;

export function loadBrand(doc = document) {
  if (doc.getElementById('orena-brand-sprite')) return Promise.resolve(true);
  if (!loading) {
    loading = fetch(BRAND_SPRITE_URL, { cache: 'no-cache' })
      .then((response) => (response.ok ? response.text() : ''))
      .then((text) => {
        if (!text) return false;
        const holder = doc.createElement('div');
        holder.id = 'orena-brand-sprite';
        holder.setAttribute('aria-hidden', 'true');
        holder.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden';
        holder.innerHTML = text;
        doc.body.prepend(holder);
        return true;
      })
      .catch(() => false);
  }
  return loading;
}

/* The mark on its disc: the rail's chip (36px square, radius 11, mark 27), the phone header's
   round chip (28px, mark 21), onboarding's larger chips. */
export function brandChip({ size = 36, mark = 27, round = false, className = '' } = {}) {
  return raw(
    `<span class="o-mark${round ? ' o-mark--round' : ''}${className ? ` ${className}` : ''}" style="width:${size}px;height:${size}px" aria-hidden="true">` +
      `<svg width="${mark}" height="${mark}" viewBox="0 0 100 100" style="display:block;flex:none;overflow:visible"><use href="#ol-mark"></use></svg></span>`,
  );
}

/* The Orena Intelligence mark on its round disc. */
export function intelChip({ size = 32, mark = 26, state = 'idle', className = '' } = {}) {
  const symbol = INTEL_STATES[state] || INTEL_STATES.idle;
  return raw(
    `<span class="o-mark o-mark--round o-mark--intel${className ? ` ${className}` : ''}" style="width:${size}px;height:${size}px" aria-hidden="true">` +
      `<svg width="${mark}" height="${mark}" viewBox="0 0 100 100" style="display:block;flex:none;overflow:visible"><use href="#${symbol}"></use></svg></span>`,
  );
}

/* The bare mark, no disc (onboarding draws it large on the ground). */
export function markGlyph({ size = 48, symbol = 'ol-mark' } = {}) {
  return raw(
    `<svg width="${size}" height="${size}" viewBox="0 0 100 100" style="display:block;flex:none;overflow:visible" aria-hidden="true"><use href="#${symbol}"></use></svg>`,
  );
}
