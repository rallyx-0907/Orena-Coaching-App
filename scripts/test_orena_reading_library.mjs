import assert from 'node:assert/strict';
import {
  publishedReadings,
  publishedReading,
  admittedReading,
  filterReadings,
} from '../static/orena/content/reading-library.js';
for (const language of ['en', 'zh']) {
  const items = publishedReadings(language);
  assert.ok(items.length);
  for (const item of items) {
    assert.equal(item.language, language);
    assert.ok(
      item.source.creator && item.source.license && item.rights.verified_on,
    );
    assert.ok(item.paragraphs.length);
    assert.equal(item.generation_mode, undefined);
    assert.equal(
      item.level,
      undefined,
      'No invented CEFR/HSK for historical text',
    );
    assert.equal(
      publishedReading(item.id, language === 'en' ? 'zh' : 'en'),
      null,
    );
    assert.equal(
      admittedReading({
        ...item,
        rights: { ...item.rights, status: 'unknown' },
      }),
      null,
    );
    assert.equal(
      admittedReading({
        ...item,
        rights: { ...item.rights, use: 'link_only' },
      }),
      null,
    );
    assert.equal(
      admittedReading({ ...item, generation_mode: 'generated' }),
      null,
    );
    assert.equal(
      admittedReading({
        ...item,
        rights: {
          ...item.rights,
          evidence_url: 'https://user:password@example.org/',
        },
      }),
      null,
    );
  }
  assert.equal(filterReadings(items, { query: items[0].title }).length, 1);
  assert.equal(filterReadings(items, { query: 'nonexistent-title' }).length, 0);
  assert.equal(
    filterReadings(
      [
        ...items,
        { title: 'Own', origin: 'imported' },
        { title: 'Created', generation_mode: 'generated' },
      ],
      { origin: 'imported' },
    ).length,
    1,
  );
}
console.log(
  'Reading library: admitted rights, source identity, EN/ZH routes, no invented levels, shared search/provenance facets PASS',
);
