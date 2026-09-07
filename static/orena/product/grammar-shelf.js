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
export function filterGrammar(
  items,
  { query = '', level = 'all', family = '' } = {},
) {
  const needle = query.trim().toLocaleLowerCase();
  return items.filter(
    (item) =>
      (level === 'all' || item.level === level) &&
      // Entering a family is a different act from searching inside one, so it
      // is its own filter rather than a query the learner could half-erase.
      (!family || item.module === family || item.category === family) &&
      (!needle ||
        [item.heading, item.line, item.title, item.category]
          .join(' ')
          .toLocaleLowerCase()
          .includes(needle)),
  );
}

/* Two ways in, because a catalogue and a syllabus are different things.

   Two hundred and thirty-four patterns in one flat list is a reference work: it
   answers "where is the pattern I already know the name of" and nothing else. A
   learner who does not yet know what they need has no way in at all.

   The syllabus already carries the structure that answer needs - every entry
   declares its level and the family it belongs to - so the families are read
   from the data rather than invented here. Nothing is ordered by difficulty,
   recommended, or marked as known: the catalogue says what exists, not what the
   learner has learned. */
export function grammarFamilies(items) {
  const levels = new Map();
  for (const item of items) {
    if (!levels.has(item.level)) levels.set(item.level, new Map());
    const families = levels.get(item.level);
    const name = item.module || item.category || '';
    if (!name) continue;
    if (!families.has(name)) families.set(name, []);
    families.get(name).push(item);
  }
  return [...levels.entries()]
    .sort(([a], [b]) => String(a).localeCompare(String(b)))
    .map(([level, families]) => ({
      level,
      total: [...families.values()].reduce((sum, list) => sum + list.length, 0),
      families: [...families.entries()].map(([name, list]) => ({
        name,
        level,
        count: list.length,
        // One real line from the family, so its name is not the only thing the
        // learner has to go on. Never a sample invented to fill the slot.
        line: list.find((x) => x.line)?.line || '',
      })),
    }));
}
