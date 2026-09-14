import assert from 'node:assert/strict';
import {
  masteryStars,
  rankForVocabulary,
  renderVocabularyRow,
  renderVocabularyStudyCard,
  supportMeaning,
  vocabularyStatus,
} from '../static/orena/ui/vocabulary-experience.js';

const copy = {
  save: 'Save',
  saved: 'Saved',
  open: 'Open',
  study: 'Study',
  meaning: 'Meaning',
  pronunciation: 'Pronunciation',
  flip: 'Tap to flip',
  front: 'Recall',
  back: 'Learn',
  again: 'Again',
  gotIt: 'I remembered',
  due: 'Due',
  learning: 'Learning',
  mastered: 'Mastered',
  newWord: 'New',
  strokes: 'strokes',
  usage: 'Usage',
  example: 'Example',
  review: 'Review',
};

const card = {
  identity: { language: 'en', normalized: 'allocate' },
  headword: 'allocate',
  pronunciation: '/ˈæləkeɪt/',
  part_of_speech: 'verb',
  meanings: [
    { language: 'en', text: 'to give something for a particular purpose' },
    { language: 'vi', text: 'phân bổ / cấp phát' },
  ],
  level: 'B1',
  framework: 'cefr-internal',
  saved: true,
  review_stage: 2,
  due: true,
};

assert.equal(rankForVocabulary({ level: 'B1' }), 'B');
assert.equal(rankForVocabulary({ level: 'HSK2' }), 'C');
assert.equal(rankForVocabulary({ level: 'unknown' }), 'D');
assert.equal(masteryStars({ review_stage: 0 }), '★☆☆');
assert.equal(masteryStars({ review_stage: 2 }), '★★☆');
assert.equal(masteryStars({ review_stage: 4 }), '★★★');
assert.equal(vocabularyStatus({ saved: false }), 'new');
assert.equal(vocabularyStatus({ saved: true, review_stage: 0, due: true }), 'due');
assert.equal(vocabularyStatus({ saved: true, review_stage: 1, due: false }), 'learning');
assert.equal(vocabularyStatus({ saved: true, review_stage: 3, due: false }), 'mastered');
assert.equal(supportMeaning(card, 'vi'), 'phân bổ / cấp phát');

const row = renderVocabularyRow(copy, card, { index: 3 });
assert.match(row, /class="vocabulary-row"/);
assert.match(row, /allocate/);
assert.match(row, /B1 · B/);
assert.match(row, /★★☆/);
assert.match(row, /Due/);
assert.match(row, /data-vocabulary-study="3"/);
assert.match(row, /data-vocabulary-save="3"/);

const study = renderVocabularyStudyCard(copy, card, { index: 0 });
assert.match(study, /class="vocabulary-study-card"/);
assert.match(study, /data-study-front/);
assert.match(study, /data-study-back/);
assert.match(study, /data-study-flip/);
assert.match(study, /data-study-grade="again"/);
assert.match(study, /phân bổ \/ cấp phát/);
assert.match(study, /aria-label="Saved"/);
assert.doesNotMatch(study, /Keep for later/);

console.log('Orena Vocabulary Experience helpers: rank, mastery, compact row, study card PASS');
