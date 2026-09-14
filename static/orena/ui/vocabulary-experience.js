import { esc } from './html.js';

const RANKS = {
  A1: 'D',
  A2: 'C',
  B1: 'B',
  B2: 'A',
  C1: 'S',
  C2: 'S+',
  HSK1: 'D',
  HSK2: 'C',
  HSK3: 'B',
  HSK4: 'A',
  HSK5: 'S',
  HSK6: 'S+',
};

function value(input) {
  return String(input || '').trim();
}

export function rankForVocabulary(card = {}) {
  const level = value(card.level).toUpperCase();
  return RANKS[level] || 'D';
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
  const level = value(card.level) || '—';
  const rank = rankForVocabulary(card);
  const framework = frameworkLabel(copy, card.framework);
  const status = vocabularyStatus(card);
  return `<span class="vocabulary-meta"><span>${esc(level)} · ${esc(rank)}</span>${framework ? `<span>${esc(framework)}</span>` : ''}<span class="vocabulary-stars" aria-label="${esc(masteryStars(card))}">${esc(masteryStars(card))}</span><span class="vocabulary-state vocabulary-state--${esc(status)}">${esc(statusLabel(copy, status))}</span></span>`;
}

export function renderVocabularyCollectionCard(copy, collection, { index = 0 } = {}) {
  const progress = collection.progress || {};
  const learned = Number(progress.learned_count) || 0;
  const total = Number(collection.item_count) || 0;
  const percent = total ? Math.round((learned / total) * 100) : 0;
  const rank = rankForVocabulary(collection);
  const framework = frameworkLabel(copy, collection.framework);
  return `<article class="vocabulary-collection-card" data-vocabulary-rank="${esc(rank)}" data-vocabulary-collection-card="${esc(index)}"><button class="vocabulary-collection-card__open" data-vocabulary-collection="${esc(collection.id)}" data-open-collection="${esc(collection.id)}"><span class="vocabulary-collection-card__cap"><span class="vocabulary-collection-card__eyebrow">${esc(collection.level || '')} · ${esc(framework)}</span><span class="vocabulary-rank-token" aria-label="${esc(copy.rank || 'Rank')} ${esc(rank)}">${esc(rank)}</span></span><h3>${esc(collection.title || '')}</h3>${collection.topic ? `<p>${esc(collection.topic)}</p>` : ''}<div class="vocabulary-collection-card__progress"><span>${esc(learned)} / ${esc(total)} ${esc(copy.words || 'words')}</span><span>${esc(percent)}%</span></div><div class="vocabulary-progress" aria-hidden="true"><span style="width:${percent}%"></span></div><div class="vocabulary-collection-card__stats"><span>${esc(progress.learning_count || 0)} ${esc(copy.learning || 'Learning')}</span><span>${esc(progress.due_count || 0)} ${esc(copy.due || 'Due')}</span><span>${esc(progress.mastered_count || 0)} ${esc(copy.mastered || 'Mastered')}</span></div></button></article>`;
}

export function renderVocabularyFeedPreview(copy, card, { index = 0, saveAttribute = 'data-vocabulary-save' } = {}) {
  const language = value(card.identity?.language) || 'en';
  const meaning = compactSupportMeaning(card, copy.supportLanguage);
  const rank = rankForVocabulary(card);
  return `<article class="vocabulary-feed-item" data-vocabulary-rank="${esc(rank)}" data-vocabulary-feed-item="${esc(index)}"><div class="vocabulary-feed-item__content"><span class="vocabulary-feed-item__level">${esc(value(card.level) || '—')} · ${esc(rank)}</span><h3 lang="${esc(language)}">${esc(card.headword)}</h3><p lang="${esc(copy.supportLanguage || 'en')}">${esc(meaning)}</p></div><div class="vocabulary-feed-item__actions"><button class="quiet" data-vocabulary-study="${esc(index)}">${esc(copy.study || copy.open)}</button><button class="quiet" ${saveAttribute}="${esc(index)}" aria-label="${esc(card.saved ? copy.saved : copy.save)}" ${card.saved ? 'disabled aria-pressed="true"' : ''}>${esc(card.saved ? copy.saved : copy.save)}</button></div></article>`;
}

export function renderVocabularyRow(copy, card, { index = 0, saveAttribute = 'data-vocabulary-save' } = {}) {
  const headword = value(card.headword);
  const language = value(card.identity?.language) || 'en';
  const translation = compactSupportMeaning(card, copy.supportLanguage);
  const pronunciation = value(card.pronunciation);
  const saved = Boolean(card.saved);
  return `<article class="vocabulary-row" data-vocabulary-rank="${esc(rankForVocabulary(card))}" data-vocabulary-row="${esc(index)}"><div class="vocabulary-row__word"><strong lang="${esc(language)}">${esc(headword)}</strong>${pronunciation ? `<span class="vocabulary-row__pronunciation">${esc(pronunciation)}</span>` : ''}</div><div class="vocabulary-row__meaning" lang="${esc(copy.supportLanguage || 'en')}">${esc(translation || targetMeaning(card))}</div>${metadata(copy, card)}<div class="vocabulary-row__actions"><button class="quiet" data-vocabulary-study="${esc(index)}">${esc(copy.study || copy.open)}</button><button class="quiet" ${saveAttribute}="${esc(index)}" aria-label="${esc(saved ? copy.saved : copy.save)}" ${saved ? 'disabled aria-pressed="true"' : ''}>${esc(saved ? copy.saved : copy.save)}</button></div></article>`;
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
  const saved = Boolean(card.saved);
  const status = vocabularyStatus(card);
  return `<article class="vocabulary-study-card" data-vocabulary-rank="${esc(rankForVocabulary(card))}" data-vocabulary-index="${esc(index)}" data-study-state="front"><div class="vocabulary-study-card__front" data-study-front><div class="vocabulary-study-card__top"><span>${esc(value(card.level) || '—')}</span><span class="vocabulary-rank-badge">${esc(rankForVocabulary(card))}</span><span class="vocabulary-stars" aria-label="${esc(masteryStars(card))}">${esc(masteryStars(card))}</span></div><div class="vocabulary-study-card__target"><h2 lang="${esc(language)}">${esc(headword)}</h2>${pronunciation ? `<p>${esc(pronunciation)} <button class="icon-button" data-study-audio aria-label="${esc(copy.audio || 'Play audio')}">◖</button></p>` : ''}</div><p class="vocabulary-study-card__prompt">${esc(copy.flip)}</p><button class="quiet" data-study-flip>${esc(copy.flip)}</button></div><div class="vocabulary-study-card__back" data-study-back hidden><div class="vocabulary-study-card__top"><span>${esc(value(card.level) || '—')} · ${esc(rankForVocabulary(card))}</span><span class="vocabulary-stars" aria-label="${esc(masteryStars(card))}">${esc(masteryStars(card))}</span></div><h2 lang="${esc(language)}">${esc(headword)}</h2>${card.part_of_speech || pronunciation ? `<p class="vocabulary-study__pronunciation">${esc(value(card.part_of_speech))}${card.part_of_speech && pronunciation ? ' · ' : ''}${esc(pronunciation)}</p>` : ''}<p class="vocabulary-study__support" lang="${esc(copy.supportLanguage || 'en')}">${esc(support)}</p>${definition && definition !== support ? `<p class="vocabulary-study__definition" lang="${esc(language)}">${esc(definition)}</p>` : ''}${card.example ? `<section><h3>${esc(copy.example)}</h3><p lang="${esc(language)}">${esc(card.example)}</p></section>` : ''}${card.usage ? `<section><h3>${esc(copy.usage)}</h3><p lang="${esc(language)}">${esc(card.usage)}</p></section>` : ''}${orthography(card, copy)}<div class="vocabulary-study-card__actions"><button class="quiet" data-study-flip>${esc(copy.front || copy.flip)}</button><button class="quiet" data-vocabulary-save="${esc(index)}" aria-label="${esc(saved ? copy.saved : copy.save)}" ${saved ? 'disabled aria-pressed="true"' : ''}>${esc(saved ? copy.saved : copy.save)}</button></div>${saved ? `<div class="vocabulary-study-card__grades" aria-label="${esc(copy.review)}"><button class="outline" data-study-grade="again">${esc(copy.again)}</button><button class="primary" data-study-grade="got_it">${esc(copy.gotIt)}</button></div>` : ''}<span class="vocabulary-state vocabulary-state--${esc(status)}">${esc(statusLabel(copy, status))}</span></div></article>`;
}
