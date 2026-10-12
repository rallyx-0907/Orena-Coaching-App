/* Library illustrations for the vocabulary card (D-180), keyed by the `ref` the authored-entry importer stores
   (`provenance.illustration`, `kind: "library"`). The card draws an illustration frame only for a `ref` this map knows
   or for an uploaded image; otherwise no frame at all.

   Art Bible boundary: these two line drawings are REFERENCE ART for the two docs/vocab samples only, ported as drawn
   from the human's flashcard design (docs/design/vocab-card: Main.dc.html "sprout-through-crack", Chinese.dc.html
   "ink-pine-trees"). Production artwork for real words is governed by assets/brand/orena/ (the Art Bible) and comes
   from Admin upload (PR 3); nothing is added here for other words. Colours are the card's tokens, through classes in
   kit/vocabulary-card.css (`.va-*`), so a drawing follows light and dark like the card. Trusted markup: no data in it. */

const SPROUT = `<svg viewBox="0 0 440 170" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
  <path class="va-ink" d="M40 130 H186 L198 138 L210 128 L224 137 L236 130 H400"/>
  <path class="va-ink" d="M210 128 L205 146 L213 160"/>
  <path class="va-ink" d="M198 138 L192 152"/>
  <path class="va-ink" d="M212 130 C209 108 218 90 214 62"/>
  <path class="va-ink va-fill-alt" d="M213 96 C190 94 174 80 174 62 C196 62 211 76 213 96 Z"/>
  <path class="va-accent va-fill-accent" d="M214 74 C234 68 252 52 250 34 C228 36 214 52 214 74 Z"/>
  <path class="va-gold" d="M70 56 H140" stroke-dasharray="2 8"/>
  <path class="va-gold" d="M92 76 C120 76 136 70 150 62"/>
  <path class="va-gold" d="M60 96 H128" stroke-dasharray="2 8"/>
  <path class="va-ink3" d="M280 130 v-8 M300 130 v-5 M330 130 v-9 M120 130 v-6"/>
</svg>`;

const PINES = `<svg viewBox="0 0 440 140" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
  <path class="va-accent" d="M0 118 L70 70 L120 100 L190 50 L262 104 L320 76 L440 120" stroke-width="1.5"/>
  <circle class="va-sun" cx="372" cy="36" r="15"/>
  <path class="va-ink va-fill-bg" d="M150 50 L126 98 H174 Z M150 70 L118 118 H182 Z"/>
  <path class="va-ink" d="M150 118 V132"/>
  <path class="va-ink va-fill-bg" d="M220 22 L190 80 H250 Z M220 48 L180 112 H260 Z"/>
  <path class="va-ink" d="M220 112 V132"/>
  <path class="va-ink va-fill-bg" d="M290 58 L268 100 H312 Z M290 76 L262 120 H318 Z"/>
  <path class="va-ink" d="M290 120 V132"/>
  <path class="va-gold" d="M90 132 H360"/>
</svg>`;

export const VOCABULARY_ART = Object.freeze({
  'sprout-through-crack': SPROUT,
  'ink-pine-trees': PINES,
});

export function libraryArt(ref) {
  return Object.prototype.hasOwnProperty.call(VOCABULARY_ART, ref) ? VOCABULARY_ART[ref] : '';
}
