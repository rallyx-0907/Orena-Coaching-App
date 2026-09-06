import {ApiClient, SESSION_COOKIE_NAME} from './client';
import {dictionaryWordToLibraryInput} from '../capabilities/dictionary-save';

const response = (body: unknown): Response => ({status: 200, ok: true, json: async () => body} as Response);
const session = {id: 41, created_at: '2026-08-30T00:00:00Z', language_code: 'en', target_level: 'B1', topic: 'daily_life', learner_goal: 'work', title: 'A small change', passage: 'A short passage.', questions: [{id: 1, question: 'What changed?', options: ['A', 'B', 'C', 'D']}], recycled_words: [], generation_mode: 'generated', material: 'article'};
const item = {word: 'steady', phonetic: '/ˈstedi/', part_of_speech: 'adjective', definition: 'calm and reliable', translation_vi: '', added_at: '2026-08-30T00:00:00Z', source_essay_id: null, source_fragment: 'a steady pace', source_kind: 'dictionary', focus_note: 'Context', review_stage: 1, stage_label: 'New', successful_recalls: 0, lapse_count: 0, last_reviewed_at: '', next_review_at: '2026-08-31T00:00:00Z', due: false};

describe('Reading and Library contracts', () => {
  it('posts a validated Reading session request with the secure cookie', async () => {
    let call: {url: string; init?: RequestInit} | undefined;
    const client = new ApiClient({baseUrl: 'https://learn.example.test', fetchImpl: async (input, init) => { call = {url: String(input), init}; return response(session); }});
    expect(await client.createReadingSession({topic: 'daily_life', material: 'article', target_level: 'B1', recycle_library: true}, {sessionCookie: 'cookie'})).toMatchObject({id: 41, language_code: 'en'});
    expect(call?.url).toBe('https://learn.example.test/api/reading/session');
    expect(call?.init?.body).toBe(JSON.stringify({topic: 'daily_life', material: 'article', target_level: 'B1', recycle_library: true}));
    expect((call?.init?.headers as Record<string, string>).Cookie).toBe(`${SESSION_COOKIE_NAME}=cookie`);
  });

  it('posts contextual dictionary evidence and preserves the confirmed claim', async () => {
    let body = '';
    const result = {available: true, source_language: 'en', target_language: 'zh', selected_text: 'steady', summary: 'Meaning in context', natural_translation: '稳定的', vocabulary: [{fragment: 'steady', meaning: 'reliable', pos: 'adjective', pronunciation: '/ˈstedi/'}], claim: 'contextual_dictionary'};
    const client = new ApiClient({baseUrl: 'https://learn.example.test', fetchImpl: async (_input, init) => { body = String(init?.body); return response(result); }});
    expect(await client.contextualDictionary({text: 'steady', source_language: 'en', target_language: 'zh', context: 'A steady pace.'})).toMatchObject({available: true, claim: 'contextual_dictionary'});
    expect(body).toBe(JSON.stringify({text: 'steady', source_language: 'en', target_language: 'zh', context: 'A steady pace.'}));
  });

  it('forwards dictionary source context when saving a confirmed word', async () => {
    let body = '';
    const client = new ApiClient({baseUrl: 'https://learn.example.test', fetchImpl: async (_input, init) => { body = String(init?.body); return response({saved: true, item}); }});
    const result = {available: true, source_language: 'en', target_language: 'zh', selected_text: 'steady', summary: 'Meaning in context', natural_translation: '稳定的', vocabulary: [{fragment: 'steady', meaning: 'reliable', pos: 'adjective', pronunciation: '/ˈstedi/'}], claim: 'contextual_dictionary'};
    const input = dictionaryWordToLibraryInput(result, ' steady ');
    expect(input).toEqual({word: 'steady', phonetic: '/ˈstedi/', part_of_speech: 'adjective', definition: 'reliable', translation_vi: '', source_fragment: 'steady', source_kind: 'dictionary', focus_note: 'Meaning in context'});
    expect(await client.saveLibraryVocabulary(input!, {sessionCookie: 'cookie'})).toMatchObject({saved: true, item: {word: 'steady'}});
    expect(body).toBe(JSON.stringify(input));
  });

  it('does not create a Library handoff from unavailable or empty dictionary evidence', () => {
    const base = {source_language: 'en', target_language: 'zh', selected_text: '', claim: 'contextual_dictionary_unavailable'};
    expect(dictionaryWordToLibraryInput({available: false, ...base}, 'steady')).toBeNull();
    expect(dictionaryWordToLibraryInput({available: true, ...base, vocabulary: []}, 'steady')).toBeNull();
    expect(dictionaryWordToLibraryInput({available: true, source_language: 'en', target_language: 'zh', selected_text: 'steady', summary: 'Meaning in context', claim: 'contextual_dictionary', vocabulary: [{fragment: 'other', meaning: 'wrong', pos: 'noun', pronunciation: ''}]}, 'different')).toBeNull();
    expect(dictionaryWordToLibraryInput({available: true, source_language: 'en', target_language: 'zh', selected_text: 'steady', summary: 'Meaning in context', claim: 'contextual_dictionary', vocabulary: [{fragment: 'steady', meaning: 'right', pos: 'adjective', pronunciation: ''}]}, 'unsteady')).toBeNull();
  });

  it('ignores an unrelated first vocabulary entry when the server confirms a later match', () => {
    const input = dictionaryWordToLibraryInput({available: true, source_language: 'en', target_language: 'zh', selected_text: 'steady', summary: 'Meaning', claim: 'contextual_dictionary', vocabulary: [{fragment: 'unrelated', meaning: 'wrong', pos: 'noun', pronunciation: ''}, {fragment: 'steady', meaning: 'right', pos: 'adjective', pronunciation: '/steady/'}]}, 'steady');
    expect(input?.word).toBe('steady');
    expect(input?.definition).toBe('right');
  });
});
