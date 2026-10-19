/* Links to the public legal pages (D-238). Legal documents and app-information pages exist in English only: every
   interface language opens the English page, so the address carries no language (an old `?lang=` is tolerated by
   the server and ignored). Outside an English interface a link's label gets a small "(English)" after it, in the
   text the link already has - no new visual. */
export const LEGAL_LANGUAGE_NOTE = '(English)';

/* The address of a public legal page: always the same, whatever the interface language. */
export function legalHref(path) {
  return path;
}

/* A link label with the language note when the interface is not English. */
export function legalLabel(label, ui) {
  return ui && ui !== 'en' ? `${label} ${LEGAL_LANGUAGE_NOTE}` : label;
}
