/* The one translated title of the derived General catalogue (D-188). A vocabulary collection's title is a stored
   string the clients show as it is; the General catalogue is not stored, so the server sends `system_kind` with an
   English fallback `title` and the clients name it here, in the interface language (rule: every label in the
   learner's language setting, no hardcoded string). Discover, Library and Collection Detail share this one key. */
import { defineCopy } from './index.js';

export const GENERAL_SYSTEM_KIND = 'general_catalogue';

const generalCopy = defineCopy('general-catalogue', {
  layers: { generalCatalogueTitle: 'interface' },
  en: { generalCatalogueTitle: 'General catalogue' },
  vi: { generalCatalogueTitle: 'Danh mục chung' },
  zh: { generalCatalogueTitle: '通用词库' },
});

/* The title to draw for a collection item from GET /api/vocabulary/library/collections[/{id}]: the translated name
   for the General catalogue, the stored title for every other collection, and the server's English fallback if the
   copy cannot be read. */
export function collectionTitle(item) {
  const stored = String(item?.title || '');
  if (item?.system_kind !== GENERAL_SYSTEM_KIND) return stored;
  try {
    return generalCopy('generalCatalogueTitle') || stored;
  } catch {
    return stored;
  }
}
