/* Moved to static/orena/product/draft-marks.js (D-091, the new learner UI's Writing screen needs
   this pure logic too, and it lives in neither UI's own tree). This file now only re-exports it, so
   `ui/expression.js` and `ui/writing-feedback.js` keep working unchanged. */
export { issueMarks, marksIn, markedHtml } from '../product/draft-marks.js';
