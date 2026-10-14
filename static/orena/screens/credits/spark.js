/* The Credits spark: the design's own glyph (`#cr-spark` symbol, gradient `cr-g` of the 2026-10-14 export), the mark of
   Credits. It is brand artwork of the design, not a Lucide icon (Design Contract rule 46 governs icons; recorded as a
   kit request in UI_BACKEND_GAPS "Credits"). The sprite is inserted once so every <use href="#cr-spark"> resolves. */
import { raw } from '../../kit/html.js';

export const SPARK_SPRITE = '<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">'
  + '<defs><linearGradient id="cr-g" x1="4" y1="2" x2="20" y2="22" gradientUnits="userSpaceOnUse"><stop offset="0" style="stop-color:var(--spark-g0)"></stop><stop offset=".55" style="stop-color:var(--spark-g1)"></stop><stop offset="1" style="stop-color:var(--spark-g2)"></stop></linearGradient></defs>'
  + '<symbol id="cr-spark" viewBox="0 0 24 24" overflow="visible"><path d="M11 2.5c.7 5 2.6 6.9 7.6 7.6-5 .7-6.9 2.6-7.6 7.6-.7-5-2.6-6.9-7.6-7.6 5-.7 6.9-2.6 7.6-7.6Z" fill="url(#cr-g)"></path>'
  + '<path d="M19 15.2c.3 1.9 1 2.6 2.9 2.9-1.9.3-2.6 1-2.9 2.9-.3-1.9-1-2.6-2.9-2.9 1.9-.3 2.6-1 2.9-2.9Z" fill="url(#cr-g)" opacity=".8"></path></symbol></svg>';

export function ensureSpark(doc = globalThis.document) {
  if (!doc || !doc.body || doc.getElementById('orena-spark-sprite')) return;
  const holder = doc.createElement('div');
  holder.id = 'orena-spark-sprite';
  holder.setAttribute('aria-hidden', 'true');
  holder.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden';
  holder.innerHTML = SPARK_SPRITE;
  doc.body.prepend(holder);
}

/* The glyph at a size. */
export function spark(size) {
  return raw(`<svg width="${size}" height="${size}" viewBox="0 0 24 24" style="display:block;flex:none;overflow:visible"><use href="#cr-spark"></use></svg>`);
}

/* The dark tile the design sets the spark on. */
export function sparkTile(size, glyph, { radius = 14, className = '' } = {}) {
  return raw(`<span class="s-cr-tile${className ? ` ${className}` : ''}" style="width:${size}px;height:${size}px;border-radius:${radius}px" aria-hidden="true"><svg width="${glyph}" height="${glyph}" viewBox="0 0 24 24" style="display:block;flex:none;overflow:visible"><use href="#cr-spark"></use></svg></span>`);
}
