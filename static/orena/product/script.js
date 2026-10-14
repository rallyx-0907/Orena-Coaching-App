/* The script a Chinese Reading article is written in (D-197): the learner list and detail payloads carry
   `script` for a Chinese article (writing_coach/languages/chinese/script_detection.py).

   Simplified is the default and is never labelled. Only a Traditional article is: the label reuses a place the design
   already draws (a Discover card tag, the Content Detail hero meta, the Reader toolbar meta line) and adds no
   component. `mixed` and `unknown` are reviewer signals, not learner copy, so they draw nothing. */
export const TRADITIONAL = 'zh-Hant';

export function isTraditional(article) {
  return String(article?.language || '') === 'zh' && String(article?.script || '') === TRADITIONAL;
}
