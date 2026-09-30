/* Chinese material with its per-character pinyin (contract §8: an array as long as the text's
   characters, "" for anything that is not a Hanzi), drawn as the design's Hanzi-over-Pinyin
   stack: `data-py` over `data-hz`, shown by kit/base.css only when the learning language is
   Chinese and the learner's pinyin preference is on (frame 14's pattern, the same one Listening
   and the Reader draw). Each character is its own column so a line still wraps between
   characters. A reading whose length does not match the text is not guessed at: the text is drawn
   plain. Non-Chinese text is returned as it is. */
import { html } from '../../kit/html.js';

const NBSP = ' ';

export function hanziMarkup(text, pinyin) {
  const chars = Array.from(String(text || ''));
  if (!Array.isArray(pinyin) || pinyin.length !== chars.length) return html`${text || ''}`;
  return html`${chars.map((ch, i) =>
    /\s/.test(ch)
      ? ch
      : html`<span><span><span data-py="1">${pinyin[i] || NBSP}</span><span data-hz="1">${ch}</span></span></span>`,
  )}`;
}
