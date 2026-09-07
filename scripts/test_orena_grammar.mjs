// Grammar reaches the same explanation surface every other capability uses,
// and teaches each pattern against the thing it is not. Depth here is the
// shared system doing more work, not a longer catalog.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import { patternsFor } from '../static/orena/content/patterns.js';
import { JUDGEMENT_KEYS, judgementLabel } from '../static/orena/ui/understanding.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const LANGUAGES = ['en', 'zh'];

// Both languages carry the same authored depth. A pattern taught with a
// contrast in one language and without it in the other is not parity.
const counts = LANGUAGES.map((language) => patternsFor(language).length);
assert.ok(counts.every((n) => n > 0), 'every language has authored patterns');
assert.equal(counts[0], counts[1], 'EN and ZH carry the same number of patterns');

for (const language of LANGUAGES) {
  for (const pattern of patternsFor(language)) {
    const where = `${language}/${pattern.id}`;
    assert.ok(pattern.line, `${where}: no pattern line`);
    assert.ok(pattern.parts?.length, `${where}: no parts`);
    for (const ui of LANGUAGES)
      assert.ok(pattern.title?.[ui], `${where}: no ${ui} title`);

    const contrast = pattern.contrast;
    assert.ok(contrast, `${where}: no contrast - a pattern is learned against what it is not`);
    assert.ok(contrast.instead, `${where}: the contrast shows nothing`);
    assert.notEqual(
      contrast.instead,
      pattern.line,
      `${where}: the contrast must differ from the pattern`,
    );
    // The one vocabulary the product uses to say what kind of problem this is.
    // Grammar naming a problem its own way would mean "wrong" meant something
    // different here than in a writing review or a reading explanation.
    assert.ok(
      JUDGEMENT_KEYS.includes(contrast.judgement),
      `${where}: "${contrast.judgement}" is not a shared judgement`,
    );
    for (const support of ['en', 'zh', 'vi']) {
      const why = contrast.why?.[support];
      assert.ok(why, `${where}: no reason in ${support}`);
      assert.ok(why.length > 40, `${where}: the ${support} reason says too little`);
    }
    // The reason has to teach, not just restate the label.
    assert.notEqual(
      contrast.why.en.trim(),
      judgementLabel(copy.en, contrast.judgement),
      `${where}: the reason only repeats the judgement`,
    );
  }
}

// Every judgement a pattern can carry is readable in both interface languages.
for (const ui of LANGUAGES)
  for (const language of LANGUAGES)
    for (const pattern of patternsFor(language))
      assert.ok(
        judgementLabel(copy[ui], pattern.contrast.judgement),
        `${ui}: no label for "${pattern.contrast.judgement}"`,
      );

for (const ui of LANGUAGES)
  assert.ok(copy[ui].notThis, `${ui}: the contrast heading is missing`);

/* Grammar was the one capability that could not ask its own question. Every
   example now reaches the shared explanation carrying the pattern as context. */
const expression = read('static/orena/ui/expression.js');
assert.ok(
  expression.includes("root.querySelectorAll('[data-explain]')"),
  'grammar examples must be able to ask for an explanation',
);
assert.ok(
  expression.includes('openUnderstanding(ctx, {\n        selection: sentence,'),
  'an example asks about itself, through the shared surface',
);
assert.ok(
  expression.includes('[...new Set([note?.line, sentence]'),
  'the pattern travels as context, and is not repeated when it is the example',
);
assert.ok(
  expression.includes('judgementLabel(c, contrast.judgement)'),
  'the contrast is labelled from the shared vocabulary, not a local string',
);
// The authored contrast is editorial content and must be labelled as such
// wherever the authored note already is.
assert.ok(
  expression.includes('c.generatedNote'),
  'authored grammar presentation stays labelled as authored',
);

console.log('Grammar: shared judgements, EN/ZH contrast pedagogy, and one explanation surface: PASS');
