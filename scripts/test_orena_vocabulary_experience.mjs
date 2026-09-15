import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  masteryStars,
  compactSupportMeaning,
  vocabularyLevel,
  vocabularyLevelSkin,
  renderVocabularyCollectionCard,
  renderVocabularyBrowseCard,
  renderVocabularyFeedPreview,
  renderVocabularyRow,
  renderVocabularyStudyCard,
  supportMeaning,
  vocabularyStatus,
} from '../static/orena/ui/vocabulary-experience.js';
import { vocabularyInteractionItems } from '../static/orena/ui/expression.js';

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
  words: 'words',
  vocabularyFramework_cefrinternal: 'Common Vocabulary',
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
  examples: [{ language: 'en', text: 'The company allocated more resources to the project.' }],
};

assert.equal(vocabularyLevel({ level: 'B1' }), 'B1');
assert.equal(vocabularyLevel({ level: 'HSK2' }), 'HSK2');
assert.equal(vocabularyLevel({ level: 'HSK 2' }), 'HSK2');
assert.equal(vocabularyLevel({ level: 'HSK 7–9' }), 'HSK7-9');
assert.equal(vocabularyLevel({ level: 'unknown' }), '');
assert.equal(vocabularyLevelSkin({ level: 'A1' }), 'bronze');
assert.equal(vocabularyLevelSkin({ level: 'B2' }), 'platinum');
assert.equal(vocabularyLevelSkin({ level: 'C2' }), 'aurora');
assert.equal(vocabularyLevelSkin({ level: 'HSK7-9' }), 'aurora');
assert.equal(masteryStars({ review_stage: 0 }), '★☆☆');
assert.equal(masteryStars({ review_stage: 2 }), '★★☆');
assert.equal(masteryStars({ review_stage: 4 }), '★★★');
assert.equal(vocabularyStatus({ saved: false }), 'new');
assert.equal(vocabularyStatus({ saved: true, review_stage: 0, due: true }), 'due');
assert.equal(vocabularyStatus({ saved: true, review_stage: 1, due: false }), 'learning');
assert.equal(vocabularyStatus({ saved: true, review_stage: 3, due: false }), 'mastered');
const studyItems = [card];
assert.equal(
  vocabularyInteractionItems('study', { studyItems }),
  studyItems,
  'Study actions must bind to the focused study item pool',
);
const expressionSource = readFileSync(new URL('../static/orena/ui/expression.js', import.meta.url), 'utf8');
assert.match(expressionSource, /const management = \(title, note = '', withBack = false\)/, 'management views expose an in-content return affordance');
assert.match(expressionSource, /view === 'saved' \? management\(c\.vocabularyManage, c\.vocabularyOverviewNote, true\)/, 'Saved management can return to Vocabulary Overview');
assert.match(expressionSource, /if \(Array\.isArray\(item\.examples\)\) card\.examples = item\.examples;/, 'saved cards keep catalog context examples');
assert.equal(supportMeaning(card, 'vi'), 'phân bổ / cấp phát');
assert.equal(compactSupportMeaning({ meanings: [{ language: 'vi', text: `Một nghĩa ngắn. ${'Một phần giải thích dài hơn để kiểm tra việc rút gọn nội dung. '.repeat(5)}` }] }, 'vi'), 'Một nghĩa ngắn.');

const collection = renderVocabularyCollectionCard(copy, {
  id: 'toeic-600-essential',
  level: 'B1',
  framework: 'cefr-internal',
  title: '600 TOEIC Essential',
  item_count: 600,
  progress: { learned_count: 304, learning_count: 38, due_count: 8, mastered_count: 174 },
});
assert.match(collection, /data-vocabulary-level="B1"/);
assert.match(collection, /Common Vocabulary/);
assert.match(collection, />B1 · Common Vocabulary</);
assert.doesNotMatch(collection, /Rank|vocabulary-rank|data-vocabulary-rank/);

const feed = renderVocabularyFeedPreview(copy, card, { index: 2 });
assert.match(feed, /data-vocabulary-level="B1"/);
assert.match(feed, /class="vocabulary-browse-card"/);
assert.match(feed, /data-vocabulary-feed-item="2"/);

const browse = renderVocabularyBrowseCard(copy, { ...card, saved: false }, { index: 4 });
assert.match(browse, /class="vocabulary-browse-card"/);
assert.match(browse, /data-vocabulary-browse-card="4"/);
assert.match(browse, /data-vocabulary-level="B1"/);
assert.match(browse, />B1</);
assert.match(browse, /allocate/);
assert.match(browse, /phân bổ \/ cấp phát/);
assert.match(browse, /<p class="vocabulary-browse-card__pronunciation" lang="en">\/ˈæləkeɪt\/<\/p>/);
assert.match(browse, /★★☆/);
assert.match(browse, />Study<\/button>/);
assert.match(browse, />\+ Save<\/button>/);
assert.match(browse, /data-vocabulary-study="4"/);
assert.match(browse, /data-vocabulary-save="4"/);
assert.doesNotMatch(browse, /Rank|vocabulary-rank|data-vocabulary-rank/);

for (const [level, skin] of [
  ['A1', 'bronze'], ['A2', 'silver'], ['B1', 'gold'], ['B2', 'platinum'],
  ['C1', 'violet'], ['C2', 'aurora'], ['HSK1', 'bronze'], ['HSK2', 'silver'],
  ['HSK3', 'gold'], ['HSK4', 'platinum'], ['HSK5', 'violet'],
  ['HSK6', 'aurora'], ['HSK7-9', 'aurora'],
]) {
  const sample = renderVocabularyBrowseCard(copy, { ...card, level, saved: false }, { index: 8 });
  assert.match(sample, new RegExp(`data-vocabulary-level="${level}"`));
  assert.match(sample, new RegExp(`data-vocabulary-skin="${skin}"`));
  assert.match(sample, new RegExp(`>${level}<`));
  assert.doesNotMatch(sample, /Rank|vocabulary-rank|data-vocabulary-rank/);
}

const savedBrowse = renderVocabularyBrowseCard(copy, card, { index: 5 });
assert.match(savedBrowse, />Saved ✓<\/button>/);
assert.match(savedBrowse, /aria-label="Saved ✓"/);
assert.match(savedBrowse, /aria-pressed="true"/);
assert.doesNotMatch(savedBrowse, /vocabulary-feed-item__actions/);

const unranked = renderVocabularyRow(copy, { ...card, level: '' }, { index: 6 });
assert.match(unranked, />—<\/span>/, 'missing proficiency metadata stays visibly unknown');
assert.doesNotMatch(unranked, /— · [A-Z]/, 'missing proficiency must not imply another level');

const row = renderVocabularyRow(copy, card, { index: 3 });
assert.match(row, /class="vocabulary-row"/);
assert.match(row, /allocate/);
assert.match(row, /B1/);
assert.match(row, /★★☆/);
assert.match(row, /Due/);
assert.match(row, /data-vocabulary-study="3"/);
assert.match(row, /data-vocabulary-save="3"/);
assert.match(row, /aria-label="Saved ✓"/);

const study = renderVocabularyStudyCard(copy, card, { index: 0 });
assert.match(study, /class="vocabulary-study-card"/);
assert.match(study, /data-study-front/);
assert.match(study, /data-study-back/);
assert.match(study, /data-study-flip/);
assert.match(study, /data-study-grade="again"/);
assert.match(study, /class="vocabulary-study-card__example"/);
assert.match(study, /The company allocated more resources to the project\./);
assert.match(study, /class="vocabulary-study-card__back-body"/);
assert.match(study, /class="vocabulary-study-card__footer"/);
assert.match(study, /vocabulary-study-card__flip/);
assert.ok(study.includes('>B1<'));
assert.match(study, /class="vocabulary-study-card__status"/);
assert.match(study, /phân bổ \/ cấp phát/);
assert.match(study, /aria-label="Saved ✓"/);
assert.match(study, />Saved ✓<\/button>/);
assert.match(study, /data-vocabulary-level="B1"/);
assert.match(study, /data-vocabulary-skin="gold"/);
assert.doesNotMatch(study, /Rank|vocabulary-rank|data-vocabulary-rank/);
assert.doesNotMatch(study, /Keep for later/);

const unrankedStudy = renderVocabularyStudyCard(copy, { ...card, level: '' }, { index: 7 });
assert.doesNotMatch(unrankedStudy, /— · [A-Z]/, 'Study must not invent another level for an ungraded saved word');

const worldCss = readFileSync(new URL('../static/orena/world.css', import.meta.url), 'utf8');
assert.match(worldCss, /#main\s*>\s*\.vocabulary-study-layout\s*\{[\s\S]*max-width:\s*820px/);
assert.match(worldCss, /\.vocabulary-study-card\s*\{[\s\S]*border:\s*4px solid/);
assert.match(worldCss, /\.vocabulary-study-card::before/);
assert.match(worldCss, /\.vocabulary-study-card__back-body\s*\{[\s\S]*overflow-y:\s*auto/);
assert.match(worldCss, /\.vocabulary-study-card__footer\s*\{[\s\S]*flex:\s*0 0 auto/);
assert.match(worldCss, /\.vocabulary-study-card__status\s*\{[\s\S]*align-self:\s*center/);
assert.match(worldCss, /\.vocabulary-browse-card\s*\{[\s\S]*border:\s*3px solid/);
assert.match(worldCss, /data-vocabulary-skin="bronze"/);
assert.match(worldCss, /data-vocabulary-skin="aurora"/);
assert.doesNotMatch(worldCss, /vocabulary-rank|data-vocabulary-rank/);

console.log('Orena Vocabulary Experience helpers: level, mastery, compact row, study card PASS');
