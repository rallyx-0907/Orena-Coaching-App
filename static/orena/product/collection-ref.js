/* The composite id a Thư viện của tôi / My Library row is addressed by: the owning domain and the
   owner's own id from a `/api/collection` entry (`writing_coach/collection_query.py`'s
   `CollectionEntry.as_dict()`, `ref: {domain, id}`), joined the one way every reader of that entry
   needs it.

   Moved out of `ui/collection.js` (the old My Library room defined this inline) so the new My
   Library screen (`screens/library/model.js`) can key its own Content-tab rows the same way
   without importing the old room's presentation, and so the two cannot quietly drift into two
   different id schemes for the same kind of row. Pure and DOM-free. */
export function refOf(entry) {
  return `${entry.ref.domain}:${entry.ref.id}`;
}
