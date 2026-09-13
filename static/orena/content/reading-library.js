import { readable } from './reading.js';

// A small, reviewed seed catalog demonstrates the admission rule. A provider,
// scraper or import must never promote unknown rights into a published text.
export function admittedReading(record) {
  const rights = record?.rights;
  if (
    record?.generation_mode ||
    record?.origin === 'generated' ||
    record?.origin === 'imported'
  )
    return null;
  try {
    const url = new URL(rights?.evidence_url);
    if (url.protocol !== 'https:' || url.username || url.password) return null;
  } catch {
    return null;
  }
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(rights?.verified_on || '') ||
    !rights.edition ||
    !rights.changes
  )
    return null;
  if (
    rights?.status !== 'cleared' ||
    rights.use !== 'full_text' ||
    !rights.basis ||
    !/^https:\/\//.test(rights.evidence_url || '') ||
    !record.source?.creator ||
    !record.source?.license
  )
    return null;
  const item = readable(record);
  return item
    ? {
        ...item,
        rights: { ...rights },
        origin: 'curated',
        material: record.material || 'text',
      }
    : null;
}
const catalog = [
  {
    id: 'published:north-wind-sun',
    language: 'en',
    title: 'The North Wind and the Sun',
    subtitle:
      'A fable about persuasion. A historical translation, in its original wording.',
    material: 'fable',
    paragraphs: [
      'THE NORTH WIND and the Sun disputed as to which was the most powerful, and agreed that he should be declared the victor who could first strip a wayfaring man of his clothes. The North Wind first tried his power and blew with all his might, but the keener his blasts, the closer the Traveler wrapped his cloak around him, until at last, resigning all hope of victory, the Wind called upon the Sun to see what he could do. The Sun suddenly shone out with all his warmth.',
      'The Traveler no sooner felt his genial rays than he took off one garment after another, and at last, fairly overcome with heat, undressed and bathed in a stream that lay in his path.',
      'Persuasion is better than Force.',
    ],
    source: {
      creator: 'Aesop · translated by George Fyler Townsend (1814–1900)',
      license:
        'Public-domain work; Project Gutenberg records US public-domain status.',
      provenance_url: 'https://www.gutenberg.org/ebooks/21',
    },
    rights: {
      status: 'cleared',
      use: 'full_text',
      basis:
        'Historical public-domain text, translator died 1900. No Gutenberg branding or modern editorial material reproduced.',
      evidence_url: 'https://www.gutenberg.org/ebooks/21',
      verified_on: '2026-09-07',
      edition:
        'Three hundred Aesop’s fables, Project Gutenberg #21 (updated 2025-10-15)',
      changes:
        'Complete fable; source paragraph divisions and wording retained.',
    },
  },
  {
    id: 'published:peach-blossom-spring',
    language: 'zh',
    title: '桃花源記 · 林中的小口',
    subtitle: '古文节选，保留原文繁体字。一个普通的转弯，通向另一种生活。',
    material: 'classical_excerpt',
    paragraphs: [
      '晉太元中，武陵人捕魚爲業。緣溪行，忘路之遠近。忽逢桃花林，夾岸數百步，中無雜樹，芳草鮮美，落英繽紛。漁人甚異之。復前行，欲窮其林。',
      '林盡水源，便得一山，山有小口，髣髴若有光。便捨船，從口入，初極狹，纔通人。復行數十步，豁然開朗。',
    ],
    source: {
      creator: '陶淵明（365–427）',
      license: '公有领域原作 · 古文节选',
      provenance_url:
        'https://zh.wikisource.org/w/index.php?title=桃花源記&oldid=2620894',
    },
    rights: {
      status: 'cleared',
      use: 'full_text',
      basis:
        'Ancient original text. Wikisource identifies the work as public domain worldwide; modern annotations and variant readings are excluded.',
      evidence_url:
        'https://zh.wikisource.org/w/index.php?title=桃花源記&oldid=2620894',
      verified_on: '2026-09-07',
      edition: '维基文库版本 2620894 · 采用正文主要读法',
      changes:
        '仅选开篇两段叙事，省略异文标注与脚注。保留繁体古文，没有改写成现代汉语。',
    },
  },
];
export const publishedReadings = (language) =>
  catalog
    .filter((x) => x.language === language)
    .map(admittedReading)
    .filter(Boolean);
export const publishedReading = (id, language) =>
  publishedReadings(language).find((x) => x.id === id) || null;

// The same facets work on provided, generated and learner-imported text.
export function filterReadings(items, { query = '', origin = 'all' } = {}) {
  const needle = query.trim().toLocaleLowerCase();
  return items.filter((item) => {
    const kind =
      item.origin === 'imported'
        ? 'imported'
        : item.generation_mode === 'generated' || item.origin === 'generated'
          ? 'generated'
          : 'provided';
    return (
      (origin === 'all' || kind === origin) &&
      (!needle ||
        [item.title, item.subtitle, item.source?.creator]
          .filter(Boolean)
          .join(' ')
          .toLocaleLowerCase()
          .includes(needle))
    );
  });
}
