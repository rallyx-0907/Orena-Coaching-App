import type {DictionaryResult, SaveLibraryVocabularyInput} from '../api/contracts/library';

export function dictionaryWordToLibraryInput(result: DictionaryResult, selectedText: string): SaveLibraryVocabularyInput | null {
  const selected = selectedText.trim();
  const confirmed = result.selected_text.trim();
  const sameSelection = confirmed.localeCompare(selected, undefined, {sensitivity: 'accent'}) === 0;
  if (!result.available || !selected || !confirmed || !sameSelection) return null;
  const word = result.vocabulary?.find((entry) => entry.fragment.trim().localeCompare(confirmed, undefined, {sensitivity: 'accent'}) === 0);
  const term = word?.fragment.trim() || confirmed;
  if (!term || (!word && !result.summary?.trim())) return null;
  return {
    word: term,
    phonetic: word?.pronunciation ?? '',
    part_of_speech: word?.pos ?? '',
    definition: word?.meaning ?? result.summary?.trim() ?? '',
    translation_vi: word ? '' : result.natural_translation?.trim() ?? '',
    source_fragment: selected,
    source_kind: 'dictionary',
    focus_note: result.summary ?? '',
  };
}
