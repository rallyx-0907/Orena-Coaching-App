/* One way to open a piece of media by its id, for every room that plays it (Listening, Content
   Detail, Respond). The same three sources the old Encounter opened (ui/encounter.js), so an
   imported item opens through the canonical flow instead of being assumed a curated lesson:

   - `url:<link>`      a source the learner pasted: re-acquired from its provider
                       (capabilities/media-acquisition.js -> POST /api/media-learning/import, then
                       /import/status while the backend's own job is resumable);
   - `upload:<id>`     a file the learner uploaded, Orena's own stored content: resolved by identity
                       (GET /api/media/my/<id>), with no provider and possibly no transcript;
   - anything else     a curated or shared lesson id (GET /api/listening/library/<id>). A bare
                       stored media id (what the upload route answers with as `media_id`) resolves
                       there too, because the library route falls back to the stored entry.

   All three answer the one acquisition payload shape (asset / playback / transcript / translations),
   so the room that renders it does not care which it was. */
import { acquireMedia } from '../capabilities/media-acquisition.js';

export function mediaRef(id) {
  const value = String(id || '');
  if (value.startsWith('url:')) return { kind: 'url', value: value.slice(4) };
  if (value.startsWith('upload:')) return { kind: 'upload', value: value.slice(7) };
  return { kind: 'lesson', value };
}

/* `support` is the learner's support language: the target a provider source's meanings are
   translated into. `language` is the learning language: it keys the resumable-job handle with the
   owner, so the same link in another language never resumes the wrong job. */
export async function openMedia(id, { api, support = '', language = '', owner = 'local', alive = () => true, onProgress = () => {} } = {}) {
  const ref = mediaRef(id);
  if (!ref.value) throw new Error('No media id');
  if (ref.kind === 'url') {
    return acquireMedia({ api, url: ref.value, target: support, owner, language, alive, onProgress });
  }
  if (ref.kind === 'upload') return api.mediaMy(ref.value);
  return api.listeningLibraryLesson(ref.value, support);
}
