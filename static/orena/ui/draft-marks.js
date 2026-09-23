/* Words marked in a piece of writing (D-066, D-067), as the Writing frames draw them: the words the
   evaluator spoke about carry a wash and a line under them - amber for most findings, blue for punctuation
   and for what a revision added, green for what it fixed.

   A highlight is earned. The contracts give the words of a finding, not where they are, so a finding is
   marked only where its words are found in the text exactly once (the rule apply-fix uses, product/
   revision.js); words that are not there, or are there twice, stay guidance and mark nothing. Marks never
   overlap: when two findings meet, the earlier one keeps its words. */
import { esc } from './html.js';
import { revisionTarget } from '../product/revision.js';

// What a review's finding is marked as: punctuation in blue, everything else in amber.
export const issueMarks = (issues) =>
  (issues || []).map((issue) => ({ id: issue.id, fragment: issue.fragment, tone: issue.kind === 'punctuation' ? 'info' : 'warm' }));

export function marksIn(text, items) {
  const found = (items || [])
    .map((item) => ({ item, target: revisionTarget(text, item.fragment) }))
    .filter((entry) => entry.target)
    .sort((a, b) => a.target.start - b.target.start);
  const marks = [];
  let edge = 0;
  for (const { item, target } of found) {
    if (target.start < edge) continue;
    marks.push({ start: target.start, end: target.end, tone: item.tone, id: item.id });
    edge = target.end;
  }
  return marks;
}

/* The text's own words, escaped, with each mark around its words. A newline that ends the text is kept
   visible so a layer of it is as tall as the box it sits behind. */
export function markedHtml(text, items) {
  let html = '';
  let at = 0;
  for (const mark of marksIn(text, items)) {
    html += esc(text.slice(at, mark.start));
    html += `<mark data-tone="${mark.tone}">${esc(text.slice(mark.start, mark.end))}</mark>`;
    at = mark.end;
  }
  return `${html}${esc(text.slice(at))}${text.endsWith('\n') ? '​' : ''}`;
}
