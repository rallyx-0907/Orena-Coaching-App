export function questionsFrom(payload) {
  const segments = new Map((payload?.transcript?.segments || []).map(segment => [segment.segment_id,segment]));
  const questions = payload?.catalog?.comprehension;
  if (!Array.isArray(questions) || !questions.length) return [];
  const ids = new Set();
  for (const q of questions) {
    if (!q.id || ids.has(q.id) || !q.prompt || !q.explanation || !Array.isArray(q.options) || q.options.length < 2 ||
        !Number.isInteger(q.correct_index) || q.correct_index < 0 || q.correct_index >= q.options.length ||
        !q.evidence_segment_ids?.length || q.evidence_segment_ids.some(id => !segments.has(id)) ||
        q.evidence_text !== q.evidence_segment_ids.map(id => segments.get(id).original_text).join('\n')) return [];
    ids.add(q.id);
  }
  return questions;
}
export function grade(question, selected) {
  if (!Number.isInteger(selected) || selected < 0 || selected >= question.options.length) return null;
  return { selected_index: selected, correct_index: question.correct_index, correct: selected === question.correct_index };
}
