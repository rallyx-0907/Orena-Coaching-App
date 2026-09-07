// Editorial invitations enrich the catalog. They never limit what can be
// explored, replace a Concept ID or fabricate a sample for an unready entry.
export function grammarShelf(catalog, notes, ui) {
  return (catalog.lessons || [])
    .filter((x) => x.kind !== 'review')
    .map((lesson) => {
      const note = notes.find((x) => x.id === lesson.id);
      const line = note?.line || lesson.preview?.text;
      return line
        ? {
            ...lesson,
            line,
            heading: note?.title?.[ui] || line,
            editorial: Boolean(note),
          }
        : null;
    })
    .filter(Boolean);
}
export function filterGrammar(items, { query = '', level = 'all' } = {}) {
  const needle = query.trim().toLocaleLowerCase();
  return items.filter(
    (item) =>
      (level === 'all' || item.level === level) &&
      (!needle ||
        [item.heading, item.line, item.title, item.category]
          .join(' ')
          .toLocaleLowerCase()
          .includes(needle)),
  );
}
