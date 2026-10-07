/* Words of the Lesson complete modal (frame 63, E3 §7). The frame draws two chrome strings, not
   one: the fixed "Lesson complete" eyebrow (a category label) and the caller's own dynamic title
   below it (e.g. "Due review", "Check understanding") - both 'interface' (chrome, not
   explanation). "Continue" is the only action. Fact labels are the caller's own copy (the caller
   already speaks the learner's languages for whatever it measured); this table carries only the
   modal's own fixed strings. */
import { defineCopy } from '../../copy/index.js';

export const t = defineCopy('lesson-complete', {
  layers: { eyebrow: 'interface', continueLabel: 'interface', scoreLabel: 'interface' },
  en: { eyebrow: 'Lesson complete', continueLabel: 'Continue', scoreLabel: 'correct' },
  vi: { eyebrow: 'Hoàn thành bài học', continueLabel: 'Tiếp tục', scoreLabel: 'đúng' },
  zh: { eyebrow: '课程完成', continueLabel: '继续', scoreLabel: '正确' },
});
