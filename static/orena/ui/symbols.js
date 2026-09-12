/* Semantic symbols for supplementary information.

   Same drawing grammar as the destination icons in `ui/reference.js` - a
   24-unit grid, a 1.6 stroke in the current ink, round joins - so a hint reads
   as part of Orena rather than as a borrowed icon font. A symbol never carries
   meaning on its own: whatever uses one also supplies the words, for sight and
   for assistive technology alike. */
const strokes = {
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 7.6v.1"/>',
  saved: '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 2.6 2.5L16 9.5"/>',
  warning: '<path d="M12 3.5 2.8 19.5h18.4Z"/><path d="M12 10v4"/><path d="M12 16.9v.1"/>',
};

export function symbol(name, size = 16) {
  return `<svg class="symbol" data-symbol="${name}" viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${strokes[name] || strokes.info}</svg>`;
}
