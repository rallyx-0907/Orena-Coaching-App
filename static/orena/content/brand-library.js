/* The approved Orena red-panda library, addressed by what a moment means
   rather than by filename.

   Fifty-two pieces of approved artwork existed and four reached the runtime -
   one of them used for both the arrival and the empty state, because the only
   way to reach any of it was to hardcode a path. A surface asking for
   `scene('listening')` cannot make that mistake, and a new approved asset
   becomes available to the whole product by being named here once.

   Nothing is generated, redrawn or recoloured. These are the approved files,
   served from where they live. */

const BRAND_ROOT = '/orena-brand';

/* Artwork is one of two kinds, and the difference decides how it may be
   presented rather than being a styling preference:

   `character` - a red panda on transparency. Sits on the page, no frame.
   `scene`     - a composed illustration with its own painted ground. Needs a
                 frame, because putting a painted rectangle straight onto the
                 page is what makes a light image look broken in dark mode. */
const CHARACTER = 'character';
const SCENE = 'scene';

/* Semantic states, each mapped to approved artwork. A state may be absent:
   content is the protagonist, and a surface with nothing worth illustrating
   should show nothing rather than reach for a mascot. */
const library = {
  discovery: { file: 'scenes/bigger-world-awaits.png', kind: SCENE, width: 196, height: 147 },
  exploring: { file: 'actions/explore.png', kind: CHARACTER, width: 122, height: 167 },
  reading: { file: 'scenes/stories-everywhere.png', kind: SCENE, width: 197, height: 147 },
  listening: { file: 'scenes/listening-to-the-world.png', kind: SCENE, width: 262, height: 132 },
  speaking: { file: 'actions/speak.png', kind: CHARACTER, width: 123, height: 167 },
  conversation: { file: 'scenes/studying-together.png', kind: SCENE, width: 262, height: 152, caption: true },
  writing: { file: 'actions/write.png', kind: CHARACTER, width: 122, height: 167 },
  creating: { file: 'scenes/creating-ideas.png', kind: SCENE, width: 261, height: 132 },
  focus: { file: 'actions/practice.png', kind: CHARACTER, width: 122, height: 167 },
  thinking: { file: 'actions/think.png', kind: CHARACTER, width: 138, height: 181 },
  remembering: { file: 'actions/take-notes.png', kind: CHARACTER, width: 139, height: 181 },
  returning: { file: 'scenes/small-steps-real-progress.png', kind: SCENE, width: 197, height: 147 },
  completion: { file: 'actions/achieve.png', kind: CHARACTER, width: 139, height: 193 },
  celebrating: { file: 'actions/celebrate.png', kind: CHARACTER, width: 123, height: 167 },
  empty: { file: 'actions/hello.png', kind: CHARACTER, width: 139, height: 185 },
  recovery: { file: 'actions/care.png', kind: CHARACTER, width: 139, height: 181 },
  learning: { file: 'scenes/learning-at-home.png', kind: SCENE, width: 262, height: 152, caption: true },
  together: { file: 'scenes/different-places-new-perspectives.png', kind: SCENE, width: 197, height: 147 },
  perspective: { file: 'scenes/exploring-the-world.png', kind: SCENE, width: 261, height: 152, caption: true },
  world: { file: 'scenes/a-brighter-tomorrow.png', kind: SCENE, width: 262, height: 132 },
};

/* A feeling, for moments that carry one. Kept apart from the states above
   because an expression answers "how did that go?" rather than "where am I?". */
const feelings = {
  curious: 'expressions/curious.png',
  thinking: 'expressions/thinking.png',
  happy: 'expressions/happy.png',
  proud: 'expressions/proud.png',
  cheering: 'expressions/cheering.png',
  calm: 'expressions/calm.png',
  surprised: 'expressions/surprised.png',
  excited: 'expressions/excited.png',
  laughing: 'expressions/laughing.png',
  winking: 'expressions/winking.png',
};

export const SCENE_STATES = Object.keys(library);
export const FEELINGS = Object.keys(feelings);

export function sceneAsset(state) {
  const entry = library[state];
  return entry ? shape(entry, state) : null;
}

/* Presentation facts taken from the artwork itself. A few approved scenes carry
   a caption strip printed beneath the illustration: those are framed to the art
   above it, which excludes the strip at every size without touching a pixel of
   the character. Everything else keeps its own full ratio. */
function shape(entry, state) {
  const height = entry.caption ? entry.height - 24 : entry.height;
  return {
    ...entry,
    state,
    src: `${BRAND_ROOT}/${entry.file}`,
    ratio: entry.width / height,
    // Only a captioned scene is framed tighter than its file; everything else
    // is shown whole.
    fit: entry.caption ? 'crop-caption' : 'whole',
  };
}

export function feelingAsset(feeling) {
  const file = feelings[feeling];
  return file
    ? shape({ file, kind: CHARACTER, width: 122, height: 141 }, feeling)
    : null;
}
