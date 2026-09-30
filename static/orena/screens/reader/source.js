/* Where the Reader's text comes from (frame 14 and frame 40 read the same document): a published
   article (`GET /api/reading/articles/{id}`), a shared-library book's chapter (`GET
   .../library/books/{id}` + `.../chapters/{chapterId}`) or a learner's own imported text (device
   memory, never the network). One shape out for all three, so the Reader and Reading Complete
   never each read a source their own way. */
import { api } from '../../infrastructure/api.js';
import {
  blocksForSource,
  pageBlocks,
  paragraphsOf,
  chapterNeighbours,
  contentIdFor,
  libraryKindFor,
  savedFromSentences,
  sentencesOf,
} from './model.js';

const byPosition = (chapters) => [...(chapters || [])].sort((a, b) => (a.position ?? 0) - (b.position ?? 0));

/* -> { kind, id, title, language, author, level, blocks, paragraphs, isBook, bookId, chapterId,
        chapterTitle, chapters, neighbours }.
   `blocks` are what the page draws (pageBlocks: a repeated title dropped); `paragraphs` are the
   paragraph blocks alone, each carrying its `pi`, the stable paragraph index a note is keyed by. */
export async function loadReadable(parsed, memory) {
  const { kind, id, chapterId } = parsed;
  if (kind === 'article') {
    const article = await api.readingArticle(id);
    const title = String(article?.title || '');
    const blocks = pageBlocks(blocksForSource('article', article), title);
    return {
      kind,
      id,
      title,
      language: String(article?.language || ''),
      author: String(article?.attribution?.author || ''),
      level: String(article?.level || ''),
      blocks,
      paragraphs: paragraphsOf(blocks),
      isBook: false,
      chapters: [],
    };
  }
  if (kind === 'book') {
    const book = await api.libraryBook(id);
    const ordered = byPosition(book?.chapters);
    const targetId = chapterId || ordered[0]?.id;
    if (!targetId) throw new Error('This book has no chapters.');
    const chapter = await api.libraryBookChapter(id, targetId);
    const chapterTitle = String(chapter?.title || '');
    const blocks = pageBlocks(blocksForSource('book', chapter), chapterTitle);
    return {
      kind,
      id,
      title: String(chapter?.book_title || book?.title || ''),
      chapterTitle,
      language: String(chapter?.language || book?.learning_language || ''),
      author: String(chapter?.author || book?.author || ''),
      level: '',
      blocks,
      paragraphs: paragraphsOf(blocks),
      isBook: true,
      bookId: id,
      chapterId: targetId,
      chapters: ordered,
      neighbours: chapterNeighbours(book?.chapters, targetId),
    };
  }
  const record = memory.value.imports.find((item) => item.id === contentIdFor('text', id));
  if (!record) throw new Error('This text is not on this device.');
  const title = String(record.title || '');
  const blocks = pageBlocks(blocksForSource('text', record), title);
  return {
    kind,
    id,
    title,
    language: String(record.language || ''),
    author: '',
    level: '',
    blocks,
    paragraphs: paragraphsOf(blocks),
    isBook: false,
    chapters: [],
  };
}

/* The content id the Reader records progress under and every next screen is addressed by: a
   chapter's own id for a book ("book:<bookId>:<chapterId>"), else the id the learner arrived by. */
export function realContentIdOf(doc) {
  return doc.isBook ? contentIdFor('book', `${doc.bookId}:${doc.chapterId}`) : contentIdFor(doc.kind, doc.id);
}

/* Whether a real approved comprehension question set exists for this article (Content Detail's own
   `loadHasPractice` makes the same check): a 404 is "Free Reading, no set", not an error. Books and
   imported texts have no comprehension-question contract today. */
export async function loadHasQuiz(kind, id) {
  if (kind !== 'article') return false;
  try {
    await api.readingPracticeSet(id);
    return true;
  } catch {
    return false;
  }
}

/* The learner's kept state for this text: the server's own kept-item state for a kind
   `/api/library/items` understands, or device memory's `kept[]` for an imported text (which has no
   server kind). */
export async function loadSaved(kind, doc, memory) {
  const libKind = libraryKindFor(kind);
  if (!libKind) return { saved: memory.value.kept.includes(contentIdFor('text', doc.id)), itemId: '' };
  const result = await api.libraryItems({ kind: libKind, sources: [doc.isBook ? doc.bookId : doc.id] }).catch(() => null);
  const item = result?.items?.[0];
  return { saved: Boolean(item), itemId: item?.id || '' };
}

/* The words the learner kept from this text's own sentences (savedFromSentences). Reads the most
   recent page of saved words - the ones kept in this session are on it - never the whole
   vocabulary (api.libraryVocabulary's own contract). `null` when the read fails, so a caller can
   tell "nothing kept from here" from "could not ask". */
export async function loadSavedFromText(doc) {
  const sentences = doc.paragraphs.flatMap((paragraph) => sentencesOf(paragraph.text));
  try {
    const page = await api.libraryVocabulary({ limit: 100, order: 'recent' });
    return savedFromSentences(page?.items, sentences);
  } catch {
    return null;
  }
}
