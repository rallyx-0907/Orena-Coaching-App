import { esc } from './html.js';

function text(value) {
  return String(value || '').trim();
}

function meaningsMarkup(meanings, language) {
  return (Array.isArray(meanings) ? meanings : [])
    .filter((meaning) => text(meaning?.text))
    .map(
      (meaning) =>
        `<p lang="${esc(text(meaning.language) || language)}">${esc(meaning.text)}</p>`,
    )
    .join('');
}

function sourcesMarkup(sources) {
  return (Array.isArray(sources) ? sources : [])
    .filter((source) => text(source?.fragment))
    .map(
      (source) =>
        `<blockquote data-source-kind="${esc(source.kind)}">${esc(source.fragment)}</blockquote>`,
    )
    .join('');
}

function orthographyMarkup(orthography, strokeCountLabel) {
  if (!orthography || !Array.isArray(orthography.characters)) return '';
  const characters = orthography.characters
    .filter((item) => text(item?.character))
    .map(
      (item) =>
        `<li data-character="${esc(item.character)}"><span lang="zh">${esc(item.character)}</span><small>${esc(item.stroke_count)} ${esc(strokeCountLabel)}</small></li>`,
    )
    .join('');
  if (!characters) return '';
  return `<section class="vocabulary-card__orthography" data-orthography-script="${esc(orthography.script)}"><ul>${characters}</ul></section>`;
}

/**
 * Render a Vocabulary Card projection without creating or mutating storage.
 *
 * `slots.before` / `slots.after` are trusted, already-built HTML a caller
 * needs inside the same card boundary (provenance, a look-closer action) so
 * the card stays the one bordered surface a collection grid lays out and
 * alternates - a wrapper element around this article would put that content
 * outside the card it is meant to belong to.
 */
export function renderVocabularyCard(copy, card, slots = {}) {
  const headword = text(card?.headword);
  if (!headword) throw new Error('Vocabulary Card requires a headword');
  const language = text(card?.identity?.language) || 'en';
  const pronunciation = text(card?.pronunciation);
  const meanings = meaningsMarkup(card.meanings, language);
  const sources = sourcesMarkup(card.source_encounters);
  const orthography = orthographyMarkup(
    card.orthography,
    text(copy?.strokeCount),
  );
  const before = typeof slots.before === 'string' ? slots.before : '';
  const after = typeof slots.after === 'string' ? slots.after : '';
  return `<article class="vocabulary-card" data-vocabulary-language="${esc(language)}">${before}<header><h2 lang="${esc(language)}">${esc(headword)}</h2>${pronunciation ? `<p class="pinyin">${esc(pronunciation)}</p>` : ''}</header>${meanings ? `<details><summary>${esc(copy?.meaning)}</summary>${meanings}</details>` : ''}${orthography}${sources ? `<section><h3>${esc(copy?.sourceContext)}</h3>${sources}</section>` : ''}${after}</article>`;
}
