/* A title the source stored in capitals ("THE CRY IN THE CORRIDOR") is not shouted back at the learner: a Latin
   all-caps title of more than one word (a lone acronym stays as it is) is written in title case; anything with lower case in it, and any
   other script, is left exactly as it is (LEX-079). */
const SMALL = new Set(['a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'in', 'of', 'on', 'or', 'the', 'to']);
export function tidyTitle(value) {
  const text = String(value ?? '');
  if (!/\s/.test(text.trim()) || !/[A-Z]{2}/.test(text) || text !== text.toUpperCase() || /[^\u0000-ɏ]/.test(text)) return text;
  return text.toLowerCase().replace(/[a-z][a-z']*/g, (word, at) => (at > 0 && SMALL.has(word) ? word : word[0].toUpperCase() + word.slice(1)));
}
