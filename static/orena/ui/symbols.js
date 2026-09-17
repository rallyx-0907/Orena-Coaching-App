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
  // Lines of text under a lens: looking at the words of a line.
  words: '<path d="M3.5 6.5h10"/><path d="M3.5 11.5h6"/><path d="M3.5 16.5h4.5"/><circle cx="15.5" cy="14" r="4"/><path d="m18.4 16.9 2.6 2.6"/>',
  // A character and a letter side by side: what a line means in another language.
  meaning: '<path d="M3.5 6h8"/><path d="M7.5 4v2"/><path d="M5 6c.9 3 2.8 5.1 5.8 6.4"/><path d="M10 6c-.9 3-2.8 5.1-5.8 6.4"/><path d="m12.8 20 3.7-8.5 3.7 8.5"/><path d="M14.1 17h4.8"/>',
  // A list with its markers: the chapters of a book.
  contents: '<path d="M9 6.5h11"/><path d="M9 12h11"/><path d="M9 17.5h11"/><path d="M4.5 6.5h.1"/><path d="M4.5 12h.1"/><path d="M4.5 17.5h.1"/>',
  // A ribbon marker: somewhere to come back to.
  bookmark: '<path d="M6.5 3.5h11v17l-5.5-4-5.5 4Z"/>',
  back: '<path d="m14.5 5.5-6.5 6.5 6.5 6.5"/>',
  forward: '<path d="m9.5 5.5 6.5 6.5-6.5 6.5"/>',
};

export function symbol(name, size = 16) {
  return `<svg class="symbol" data-symbol="${name}" viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${strokes[name] || strokes.info}</svg>`;
}
