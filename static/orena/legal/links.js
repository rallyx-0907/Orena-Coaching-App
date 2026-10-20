/* Links to the public legal pages (D-238). Legal documents and app-information pages exist in English only: every
   interface language opens the English page, so the address carries no language (an old `?lang=` is tolerated by
   the server and ignored). A link's label is its own translated name and nothing else: no language note after it (#437). */

/* The address of a public legal page: always the same, whatever the interface language. */
export function legalHref(path) {
  return path;
}
