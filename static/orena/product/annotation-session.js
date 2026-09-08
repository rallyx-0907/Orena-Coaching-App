// Transient source-bound annotations. No timing, meaning or learner evidence is
// inferred here; the existing language service owns the supplied linguistic data.
export function annotationSession({ request, language, alive = () => true }) {
  const values = new Map(), pending = new Set();
  const texts = new Map();
  return {
    values, pending,
    async load(segment) {
      const id = segment.segment_id, text = segment.original_text;
      if (texts.get(id) === text && (values.has(id) || pending.has(id))) return;
      texts.set(id, text);
      values.delete(id);
      pending.add(id);
      try {
        const result = await request({ text, source_language: language });
        if (alive() && texts.get(id) === text)
          values.set(id, result?.text === text.trim() ? result : null);
      } catch {
        if (alive() && texts.get(id) === text) values.set(id, null);
      } finally {
        if (texts.get(id) === text) pending.delete(id);
      }
    },
    retry(id) { values.delete(id); },
  };
}
