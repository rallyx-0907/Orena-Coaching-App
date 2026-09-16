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
  renderVocabularyFeedCarousel,
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
  vocabularyFeedSoundOn: 'Turn feed snap sound off',
  vocabularyFeedSoundOff: 'Turn feed snap sound on',
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
const vocabularyExperienceSource = readFileSync(new URL('../static/orena/ui/vocabulary-experience.js', import.meta.url), 'utf8');
const worldSource = readFileSync(new URL('../static/orena/ui/world.js', import.meta.url), 'utf8');
assert.match(expressionSource, /const management = \(title, note = '', withBack = false\)/, 'management views expose an in-content return affordance');
assert.match(expressionSource, /view === 'saved' \? management\(c\.vocabularyManage, c\.vocabularyOverviewNote, true\)/, 'Saved management can return to Vocabulary Overview');
assert.match(expressionSource, /view === 'library' \? libraryView\(\)/, 'Library is an expanded view rather than an in-page scroll target');
assert.match(expressionSource, /collections\.slice\(0, 3\)/, 'Overview bounds the collection preview');
assert.match(expressionSource, /savedCards[\s\S]*?slice\(0, 3\)/, 'Overview bounds the saved preview');
assert.match(expressionSource, /renderVocabularyFeedCarousel/, 'Overview uses the shared Feed carousel');
assert.match(expressionSource, /class="vocabulary-dashboard"/, 'Overview gives Library and Feed distinct dashboard regions');
assert.match(expressionSource, /vocabulary-dashboard__library/, 'Library owns the primary dashboard column');
assert.match(expressionSource, /vocabulary-dashboard__feed/, 'Feed is a secondary dashboard widget');
assert.doesNotMatch(expressionSource, /vocabulary-collection-grid'\)\?\.scrollIntoView/, 'View all collections must navigate to Library');
assert.match(expressionSource, /dataset\.vocabularyStudySource === 'feed'[\s\S]*?feedCards\.slice\(0, 5\)/, 'Overview Feed Study actions use the Feed pool');
assert.match(expressionSource, /data-vocabulary-level-filter/, 'Collection management exposes internal proficiency-level filters');
assert.match(expressionSource, /vocabulary-collection-detail-progress/, 'Collection detail exposes progress before the dense word list');
assert.match(vocabularyExperienceSource, /class="vocabulary-study-card__inner"/, 'Study uses a transformable inner card for the flip animation');
assert.match(vocabularyExperienceSource, /data-study-surface/, 'Study exposes the whole card as a flip surface');
assert.match(vocabularyExperienceSource, /data-study-back[^>]*aria-hidden="true"[^>]*inert/, 'Study keeps the inactive back out of the accessibility and keyboard order');
assert.doesNotMatch(vocabularyExperienceSource, /data-study-back[^>]*\s+hidden(?:=|\s|>)/, 'Study does not hide the back with display:none, which would prevent the flip animation');
assert.doesNotMatch(expressionSource, /front\.hidden|back\.hidden/, 'Study state is animated with transforms rather than display:none toggles');
assert.match(expressionSource, /const flipStudyCard = \(\) =>/, 'Study centralizes the card flip state transition');
assert.match(expressionSource, /studyCard\.addEventListener\('click'/, 'Study flips from the card surface, not only from the hint button');
assert.match(expressionSource, /closest\('button, a, input, select, textarea, \[data-study-no-flip\]'\)/, 'Study does not hijack interactive pronunciation, meaning, or action controls');
assert.match(expressionSource, /studyCard\.addEventListener\('keydown'/, 'Study card surface remains keyboard operable');
const discoveryBranch = worldSource.slice(worldSource.indexOf('  } else {', worldSource.indexOf('export async function renderWorld')), worldSource.indexOf('  root\n    .querySelectorAll', worldSource.indexOf('export async function renderWorld')));
assert.doesNotMatch(discoveryBranch, /data-vocabulary-library/, 'Discovery no longer mounts Vocabulary Library');
assert.match(discoveryBranch, /data-vocabulary-feed/, 'Discovery keeps only the Daily Vocabulary surface');
assert.match(worldSource, /discoveryVocabularySection\(c\)/, 'Discovery uses the feed-only vocabulary surface helper');
assert.match(worldSource, /renderVocabularyFeedCarousel\([\s\S]*full: false/, 'Discovery uses the compact Feed widget variant');
assert.match(vocabularyExperienceSource, /vocabulary-feed-slide/, 'Feed slides use a dedicated deck presentation');
assert.match(vocabularyExperienceSource, /slide\.classList\.toggle\('is-active'/, 'deck keeps one active slide');
assert.match(vocabularyExperienceSource, /slide\.toggleAttribute\('inert'/, 'inactive slides are removed from keyboard interaction');
assert.match(vocabularyExperienceSource, /let activeIndex = 0;/, 'carousel keeps an explicit active position during controlled navigation');
assert.match(vocabularyExperienceSource, /activeIndex = bounded;/, 'carousel updates the active position before the snap');
assert.match(vocabularyExperienceSource, /track\.addEventListener\('pointerdown'/, 'desktop drag and touch swipe arm the deck');
assert.match(vocabularyExperienceSource, /Math\.abs\(delta\) >= 32/, 'a swipe changes cards only after a deliberate threshold');
assert.match(vocabularyExperienceSource, /AudioContext/, 'snap feedback uses optional local Web Audio');
assert.match(vocabularyExperienceSource, /!interactionArmed \|\| !soundEnabled/, 'sound is gated behind interaction and an explicit toggle');
assert.match(vocabularyExperienceSource, /prefers-reduced-motion/, 'deck checks reduced-motion preferences');
assert.match(expressionSource, /if \(Array\.isArray\(item\.examples\)\) card\.examples = item\.examples;/, 'saved cards keep catalog context examples');
assert.match(expressionSource, /button\.closest\('\[data-vocabulary-source\]'\)/, 'Feed Save actions resolve against Feed cards on the overview');
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
const rangedCollection = renderVocabularyCollectionCard(copy, {
  ...{
    id: 'common-3000',
    levels: ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'],
    level_range: 'A1–C2',
    framework: 'cefr-internal',
    title: '3000 Common Words',
    item_count: 3000,
  },
  progress: {},
});
assert.match(rangedCollection, /data-vocabulary-level="A1"/);
assert.match(rangedCollection, /data-vocabulary-level-range="A1–C2"/);
assert.match(rangedCollection, />A1–C2 · Common Vocabulary</);

const feed = renderVocabularyFeedPreview(copy, card, { index: 2 });
assert.match(feed, /data-vocabulary-level="B1"/);
assert.match(feed, /class="vocabulary-browse-card vocabulary-feed-slide"/);
assert.match(feed, /data-vocabulary-feed-item="2"/);
assert.match(feed, /data-vocabulary-study-source="feed"/);

const carouselCards = Array.from({ length: 6 }, (_, index) => ({
  ...card,
  headword: `word-${index}`,
}));
const carousel = renderVocabularyFeedCarousel(copy, carouselCards, { limit: 5 });
assert.match(carousel, /data-vocabulary-feed-carousel/);
assert.match(carousel, /data-vocabulary-feed-track/);
assert.match(carousel, /data-vocabulary-feed-prev/);
assert.match(carousel, /data-vocabulary-feed-next/);
assert.match(carousel, /data-vocabulary-feed-position/);
assert.match(carousel, /data-vocabulary-feed-dot="0"/);
assert.match(carousel, /data-vocabulary-feed-sound/);
assert.match(carousel, /data-vocabulary-feed-sound-on/);
assert.match(carousel, /data-vocabulary-feed-sound-off/);
assert.equal(
  (carousel.match(/class="vocabulary-browse-card vocabulary-feed-slide"/g) || []).length,
  5,
  'Feed carousel keeps the overview/session limit instead of rendering every candidate',
);
assert.equal((carousel.match(/aria-hidden="false"/g) || []).length, 1, 'only the first deck card is initially active');
assert.equal((carousel.match(/ inert/g) || []).length, 4, 'inactive deck cards are inert');

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
const feedCss = worldCss.slice(worldCss.indexOf('/* Feed is a small tactile deck'), worldCss.indexOf('.seek-line'));
assert.match(worldCss, /#main\s*>\s*\.vocabulary-study-layout\s*\{[\s\S]*max-width:\s*820px/);
assert.match(worldCss, /\.vocabulary-study-card\s*\{[\s\S]*border:\s*4px solid/);
assert.match(worldCss, /\.vocabulary-study-card__inner\s*\{[\s\S]*transition:\s*transform/);
assert.match(worldCss, /\.vocabulary-study-card\[data-study-state="back"\][\s\S]*rotateY\(180deg\)/);
assert.match(worldCss, /\.vocabulary-study-card::before/);
assert.match(worldCss, /\.vocabulary-study-card__back-body\s*\{[\s\S]*overflow-y:\s*auto/);
assert.match(worldCss, /\.vocabulary-study-card__footer\s*\{[\s\S]*flex:\s*0 0 auto/);
assert.match(worldCss, /\.vocabulary-study-card__status\s*\{[\s\S]*align-self:\s*center/);
assert.match(worldCss, /\.vocabulary-browse-card\s*\{[\s\S]*border:\s*3px solid/);
assert.match(worldCss, /data-vocabulary-skin="bronze"/);
assert.match(worldCss, /data-vocabulary-skin="aurora"/);
assert.match(worldCss, /\.vocabulary-dashboard\s*\{[\s\S]*grid-template-columns:\s*minmax\(0, 1fr\) minmax\(320px, 380px\)/);
assert.match(feedCss, /\.vocabulary-feed-carousel\s*\{[\s\S]*max-width:\s*380px/);
assert.match(feedCss, /\.vocabulary-feed-carousel--discovery\s*\{[\s\S]*max-width:\s*360px/);
assert.match(worldCss, /#main\s*>\s*\.discovery-vocabulary-feed\s*\{[\s\S]*max-width:\s*380px/);
assert.match(feedCss, /\.vocabulary-feed-carousel:not\(\.vocabulary-feed-carousel--full\) \.vocabulary-feed-preview\s*\{[\s\S]*height:\s*300px/);
assert.match(feedCss, /\.vocabulary-feed-carousel:not\(\.vocabulary-feed-carousel--full\) \.vocabulary-browse-card__actions button\s*\{[\s\S]*min-height:\s*36px/);
assert.match(feedCss, /\.vocabulary-feed-preview\s*\{[\s\S]*display:\s*block/);
assert.match(feedCss, /\.vocabulary-feed-preview\s*\{[\s\S]*overflow:\s*hidden/);
assert.doesNotMatch(feedCss, /overflow-x:\s*auto/);
assert.match(feedCss, /\.vocabulary-feed-preview\s*>\s*\.vocabulary-feed-slide\s*\{[\s\S]*position:\s*absolute/);
assert.match(feedCss, /\.vocabulary-feed-preview\.is-dragging[\s\S]*rotateZ/);
assert.match(feedCss, /@media \(max-width: 700px\)[\s\S]*\.vocabulary-feed-preview\s*>\s*\.vocabulary-feed-slide[\s\S]*inset-inline/);
const feedDotCss = feedCss.match(/\.vocabulary-feed-carousel__dot\s*\{([\s\S]*?)\n\}/)?.[1] || '';
assert.match(feedDotCss, /min-height:\s*44px/, 'carousel dots keep a compact visual dot with an accessible hit area');
assert.match(feedCss, /\.vocabulary-feed-carousel__dot::before\s*\{/, 'carousel dots render their visual mark independently from the hit area');
const collectionOpenCss = worldCss.match(/\.vocabulary-collection-card__open\s*\{([\s\S]*?)\n\}/)?.[1] || '';
assert.match(collectionOpenCss, /height:\s*190px/);
assert.match(collectionOpenCss, /min-height:\s*0/);
assert.doesNotMatch(worldCss, /vocabulary-rank|data-vocabulary-rank/);

console.log('Orena Vocabulary Experience helpers: level, mastery, compact row, study card PASS');
