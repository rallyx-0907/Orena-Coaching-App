import { esc } from './html.js';

const LEVEL_SKINS = {
  A1: 'bronze',
  A2: 'silver',
  B1: 'gold',
  B2: 'platinum',
  C1: 'violet',
  C2: 'aurora',
  HSK1: 'bronze',
  HSK2: 'silver',
  HSK3: 'gold',
  HSK4: 'platinum',
  HSK5: 'violet',
  HSK6: 'aurora',
  'HSK7-9': 'aurora',
};

function value(input) {
  return String(input || '').trim();
}

function rawVocabularyLevel(input = {}) {
  return value(input && typeof input === 'object' ? input.level : input);
}

export function vocabularyLevel(input = {}) {
  const raw = rawVocabularyLevel(input);
  const normalized = raw.toUpperCase().replace(/[–—]/g, '-').replace(/\s+/g, '');
  return LEVEL_SKINS[normalized] ? normalized : '';
}

export function vocabularyLevelSkin(input = {}) {
  return LEVEL_SKINS[vocabularyLevel(input)] || 'neutral';
}

export function masteryStars(card = {}) {
  const stage = Math.max(0, Math.min(4, Number(card.review_stage) || 0));
  const count = stage >= 4 ? 3 : stage >= 2 ? 2 : 1;
  return `${'★'.repeat(count)}${'☆'.repeat(3 - count)}`;
}

export function vocabularyStatus(card = {}) {
  if (!card.saved) return 'new';
  if (card.due) return 'due';
  if ((Number(card.review_stage) || 0) >= 3) return 'mastered';
  return 'learning';
}

export function supportMeaning(card = {}, supportLanguage = '') {
  const target = value(card.identity?.language);
  const meanings = Array.isArray(card.meanings) ? card.meanings : [];
  const support = meanings.find(
    (meaning) => value(meaning?.language) === value(supportLanguage),
  );
  if (support?.text) return value(support.text);
  const vietnamese = meanings.find((meaning) => value(meaning?.language) === 'vi');
  if (vietnamese?.text) return value(vietnamese.text);
  return value(
    meanings.find((meaning) => value(meaning?.language) !== target)?.text ||
      meanings[0]?.text,
  );
}

export function compactSupportMeaning(card = {}, supportLanguage = '', maxLength = 150) {
  const meaning = supportMeaning(card, supportLanguage);
  if (meaning.length <= maxLength) return meaning;
  const firstSentence = meaning.split(/(?<=[.!?。！？])\s+/)[0].trim();
  const compact = firstSentence && firstSentence.length <= maxLength ? firstSentence : meaning;
  return compact.length <= maxLength ? compact : `${compact.slice(0, maxLength - 1).trimEnd()}…`;
}

function targetMeaning(card = {}) {
  const language = value(card.identity?.language);
  const meanings = Array.isArray(card.meanings) ? card.meanings : [];
  return value(
    meanings.find((meaning) => value(meaning?.language) === language)?.text ||
      meanings[0]?.text,
  );
}

function exampleText(card = {}) {
  const authored = Array.isArray(card.examples) ? card.examples : [];
  const first = authored.find((example) => value(example?.text || example?.target || example));
  return value(card.example) || value(first?.text || first?.target || first);
}

function exampleLanguage(card = {}, fallback = '') {
  const authored = Array.isArray(card.examples) ? card.examples : [];
  const first = authored.find((example) => value(example?.text || example?.target || example));
  return value(first?.language) || value(card.identity?.language) || fallback || 'en';
}

function frameworkLabel(copy, framework) {
  const raw = value(framework);
  if (!raw) return '';
  const key = `vocabularyFramework_${raw.replace(/[^a-z0-9]/gi, '').toLowerCase()}`;
  return value(copy[key]) || raw;
}

export function vocabularyKeepPayload(card, sourceKind, supportLanguage) {
  return {
    word: card.headword,
    phonetic: card.pronunciation || '',
    part_of_speech: card.part_of_speech || '',
    definition: targetMeaning(card),
    translation_vi: supportMeaning(card, supportLanguage),
    source_kind: sourceKind,
  };
}

function statusLabel(copy, status) {
  return copy[
    { new: 'newWord', learning: 'learning', due: 'due', mastered: 'mastered' }[
      status
    ]
  ];
}

function metadata(copy, card) {
  const level = vocabularyLevel(card) || '—';
  const framework = frameworkLabel(copy, card.framework);
  const status = vocabularyStatus(card);
  return `<span class="vocabulary-meta"><span>${esc(level)}</span>${framework ? `<span>${esc(framework)}</span>` : ''}<span class="vocabulary-stars" aria-label="${esc(masteryStars(card))}">${esc(masteryStars(card))}</span><span class="vocabulary-state vocabulary-state--${esc(status)}">${esc(statusLabel(copy, status))}</span></span>`;
}

export function renderVocabularyCollectionCard(copy, collection, { index = 0 } = {}) {
  const progress = collection.progress || {};
  const learned = Number(progress.learned_count) || 0;
  const total = Number(collection.item_count) || 0;
  const percent = total ? Math.round((learned / total) * 100) : 0;
  const level = vocabularyLevel(collection);
  const skin = vocabularyLevelSkin(collection);
  const framework = frameworkLabel(copy, collection.framework);
  return `<article class="vocabulary-collection-card" data-vocabulary-level="${esc(level || 'unknown')}" data-vocabulary-skin="${esc(skin)}" data-vocabulary-collection-card="${esc(index)}"><button class="vocabulary-collection-card__open" data-vocabulary-collection="${esc(collection.id)}" data-open-collection="${esc(collection.id)}"><span class="vocabulary-collection-card__cap"><span class="vocabulary-collection-card__eyebrow">${esc(level || '—')}${framework ? ` · ${esc(framework)}` : ''}</span></span><h3>${esc(collection.title || '')}</h3>${collection.topic ? `<p>${esc(collection.topic)}</p>` : ''}<div class="vocabulary-collection-card__progress"><span>${esc(learned)} / ${esc(total)} ${esc(copy.words || 'words')}</span><span>${esc(percent)}%</span></div><div class="vocabulary-progress" aria-hidden="true"><span style="width:${percent}%"></span></div><div class="vocabulary-collection-card__stats"><span>${esc(progress.learning_count || 0)} ${esc(copy.learning || 'Learning')}</span><span>${esc(progress.due_count || 0)} ${esc(copy.due || 'Due')}</span><span>${esc(progress.mastered_count || 0)} ${esc(copy.mastered || 'Mastered')}</span></div><span class="vocabulary-collection-card__footer">${esc(copy.open || 'Open')} <span aria-hidden="true">→</span></span></button></article>`;
}

function browseMetadata(copy, card) {
  const parts = [];
  const partOfSpeech = value(card.part_of_speech);
  const framework = frameworkLabel(copy, card.framework);
  const topic = value(card.topic);
  if (partOfSpeech) parts.push(partOfSpeech);
  if (framework) parts.push(framework);
  if (topic) parts.push(topic);
  if (!parts.length) return '';
  return `<p class="vocabulary-browse-card__meta">${parts.map((part) => `<span>${esc(part)}</span>`).join('<span aria-hidden="true">·</span>')}</p>`;
}

export function renderVocabularyBrowseCard(copy, card, { index = 0, saveAttribute = 'data-vocabulary-save', source = 'browse' } = {}) {
  const language = value(card.identity?.language) || 'en';
  const headword = value(card.headword);
  const meaning = compactSupportMeaning(card, copy.supportLanguage);
  const pronunciation = value(card.pronunciation);
  const level = vocabularyLevel(card);
  const skin = vocabularyLevelSkin(card);
  const stars = masteryStars(card);
  const state = vocabularyStatus(card);
  const saved = Boolean(card.saved);
  const sourceAttr = source ? ` data-vocabulary-source="${esc(source)}"` : '';
  const feedAttr = source === 'feed' ? ` data-vocabulary-feed-item="${esc(index)}"` : '';
  const saveLabel = saved ? `${copy.saved || 'Saved'} ✓` : `+ ${copy.save || 'Save'}`;
  return `<article class="vocabulary-browse-card" data-vocabulary-level="${esc(level || 'unknown')}" data-vocabulary-skin="${esc(skin)}" data-vocabulary-browse-card="${esc(index)}"${sourceAttr}${feedAttr}><div class="vocabulary-browse-card__top"><span class="vocabulary-browse-card__level">${esc(level || '—')}</span></div><div class="vocabulary-browse-card__content"><h3 lang="${esc(language)}">${esc(headword)}</h3><p class="vocabulary-browse-card__meaning" lang="${esc(copy.supportLanguage || 'en')}">${esc(meaning)}</p>${pronunciation ? `<p class="vocabulary-browse-card__pronunciation" lang="${esc(language)}">${esc(pronunciation)}</p>` : ''}${browseMetadata(copy, card)}</div><div class="vocabulary-browse-card__status"><span class="vocabulary-stars" aria-label="${esc(stars)}">${esc(stars)}</span><span class="vocabulary-state vocabulary-state--${esc(state)}">${esc(statusLabel(copy, state))}</span></div><div class="vocabulary-browse-card__actions"><button class="primary vocabulary-browse-card__study" data-vocabulary-study="${esc(index)}">${esc(copy.study || copy.open)}</button><button class="outline vocabulary-browse-card__save" ${saveAttribute}="${esc(index)}" aria-label="${esc(saveLabel)}" aria-pressed="${saved ? 'true' : 'false'}" ${saved ? 'disabled' : ''}>${esc(saveLabel)}</button></div></article>`;
}

export function renderVocabularyFeedPreview(copy, card, { index = 0, saveAttribute = 'data-vocabulary-save' } = {}) {
  return renderVocabularyBrowseCard(copy, card, { index, saveAttribute, source: 'feed' });
}

export function renderVocabularyRow(copy, card, { index = 0, saveAttribute = 'data-vocabulary-save' } = {}) {
  const headword = value(card.headword);
  const language = value(card.identity?.language) || 'en';
  const translation = compactSupportMeaning(card, copy.supportLanguage);
  const pronunciation = value(card.pronunciation);
  const saved = Boolean(card.saved);
  const saveLabel = saved ? `${copy.saved} ✓` : copy.save;
  const level = vocabularyLevel(card);
  const skin = vocabularyLevelSkin(card);
  return `<article class="vocabulary-row" data-vocabulary-level="${esc(level || 'unknown')}" data-vocabulary-skin="${esc(skin)}" data-vocabulary-row="${esc(index)}"><div class="vocabulary-row__word"><strong lang="${esc(language)}">${esc(headword)}</strong>${pronunciation ? `<span class="vocabulary-row__pronunciation">${esc(pronunciation)}</span>` : ''}</div><div class="vocabulary-row__meaning" lang="${esc(copy.supportLanguage || 'en')}">${esc(translation || targetMeaning(card))}</div>${metadata(copy, card)}<div class="vocabulary-row__actions"><button class="quiet" data-vocabulary-study="${esc(index)}">${esc(copy.study || copy.open)}</button><button class="quiet" ${saveAttribute}="${esc(index)}" aria-label="${esc(saveLabel)}" ${saved ? 'disabled aria-pressed="true"' : ''}>${esc(saveLabel)}</button></div></article>`;
}

function orthography(card, copy) {
  const characters = Array.isArray(card.orthography?.characters)
    ? card.orthography.characters.filter((item) => value(item?.character))
    : [];
  if (!characters.length) return '';
  return `<section class="vocabulary-study__orthography"><h3>${esc(copy.orthography || 'Orthography')}</h3><ul>${characters
    .map(
      (item) =>
        `<li lang="zh"><span>${esc(item.character)}</span><small>${esc(item.stroke_count)} ${esc(copy.strokes)}</small></li>`,
    )
    .join('')}</ul></section>`;
}

export function renderVocabularyStudyCard(copy, card, { index = 0 } = {}) {
  const language = value(card.identity?.language) || 'en';
  const headword = value(card.headword);
  const pronunciation = value(card.pronunciation);
  const support = supportMeaning(card, copy.supportLanguage);
  const definition = targetMeaning(card);
  const example = exampleText(card);
  const exampleLang = exampleLanguage(card, language);
  const saved = Boolean(card.saved);
  const status = vocabularyStatus(card);
  const level = vocabularyLevel(card);
  const skin = vocabularyLevelSkin(card);
  const saveLabel = saved ? `${copy.saved} ✓` : copy.save;
  const proficiencyLabel = level || '—';
  return `<article class="vocabulary-study-card" data-vocabulary-level="${esc(level || 'unknown')}" data-vocabulary-skin="${esc(skin)}" data-vocabulary-index="${esc(index)}" data-study-state="front"><div class="vocabulary-study-card__front" data-study-front><div class="vocabulary-study-card__top"><span>${esc(proficiencyLabel)}</span><span class="vocabulary-stars" aria-label="${esc(masteryStars(card))}">${esc(masteryStars(card))}</span></div><div class="vocabulary-study-card__target"><h2 lang="${esc(language)}">${esc(headword)}</h2>${pronunciation ? `<p lang="${esc(language)}">${esc(pronunciation)} <button class="icon-button" data-study-audio aria-label="${esc(copy.audio || 'Play audio')}">◖</button></p>` : ''}</div><button class="quiet vocabulary-study-card__flip" data-study-flip>${esc(copy.flip)}</button></div><div class="vocabulary-study-card__back" data-study-back hidden><div class="vocabulary-study-card__top"><span>${esc(proficiencyLabel)}</span><span class="vocabulary-stars" aria-label="${esc(masteryStars(card))}">${esc(masteryStars(card))}</span></div><div class="vocabulary-study-card__back-body"><h2 lang="${esc(language)}">${esc(headword)}</h2>${card.part_of_speech || pronunciation ? `<p class="vocabulary-study__pronunciation" lang="${esc(language)}">${esc(value(card.part_of_speech))}${card.part_of_speech && pronunciation ? ' · ' : ''}${esc(pronunciation)}</p>` : ''}<p class="vocabulary-study__support" lang="${esc(copy.supportLanguage || 'en')}">${esc(support)}</p>${definition && definition !== support ? `<p class="vocabulary-study__definition" lang="${esc(language)}">${esc(definition)}</p>` : ''}${example ? `<section class="vocabulary-study-card__example"><h3>${esc(copy.example)}</h3><p lang="${esc(exampleLang)}">${esc(example)}</p></section>` : ''}${card.usage ? `<section class="vocabulary-study__usage"><h3>${esc(copy.usage)}</h3><p lang="${esc(language)}">${esc(card.usage)}</p></section>` : ''}${orthography(card, copy)}</div><div class="vocabulary-study-card__footer"><div class="vocabulary-study-card__actions"><button class="quiet vocabulary-study-card__flip" data-study-flip>${esc(copy.front || copy.flip)}</button><button class="quiet" data-vocabulary-save="${esc(index)}" aria-label="${esc(saveLabel)}" ${saved ? 'disabled aria-pressed="true"' : ''}>${esc(saveLabel)}</button></div>${saved ? `<div class="vocabulary-study-card__grades" aria-label="${esc(copy.review)}"><button class="outline" data-study-grade="again">${esc(copy.again)}</button><button class="primary" data-study-grade="got_it">${esc(copy.gotIt)}</button></div>` : ''}<div class="vocabulary-study-card__status"><span class="vocabulary-state vocabulary-state--${esc(status)}">${esc(statusLabel(copy, status))}</span></div></div></div></article>`;
}
