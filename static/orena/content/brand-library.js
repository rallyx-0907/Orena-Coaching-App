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
  discovery: { file: 'scenes/bigger-world-awaits.png', kind: SCENE, ratio: 16 / 9 },
  exploring: { file: 'actions/explore.png', kind: CHARACTER, ratio: 1 },
  reading: { file: 'scenes/stories-everywhere.png', kind: SCENE, ratio: 16 / 9 },
  listening: { file: 'scenes/listening-to-the-world.png', kind: SCENE, ratio: 16 / 9 },
  speaking: { file: 'actions/speak.png', kind: CHARACTER, ratio: 1 },
  conversation: { file: 'scenes/same-curiosity-further-together.png', kind: SCENE, ratio: 16 / 9 },
  writing: { file: 'actions/write.png', kind: CHARACTER, ratio: 1 },
  creating: { file: 'scenes/creating-ideas.png', kind: SCENE, ratio: 16 / 9 },
  focus: { file: 'actions/practice.png', kind: CHARACTER, ratio: 1 },
  thinking: { file: 'actions/think.png', kind: CHARACTER, ratio: 1 },
  remembering: { file: 'actions/take-notes.png', kind: CHARACTER, ratio: 1 },
  returning: { file: 'scenes/small-steps-real-progress.png', kind: SCENE, ratio: 16 / 9 },
  completion: { file: 'actions/achieve.png', kind: CHARACTER, ratio: 1 },
  celebrating: { file: 'actions/celebrate.png', kind: CHARACTER, ratio: 1 },
  empty: { file: 'actions/hello.png', kind: CHARACTER, ratio: 1 },
  recovery: { file: 'actions/care.png', kind: CHARACTER, ratio: 1 },
  learning: { file: 'scenes/learning-at-home.png', kind: SCENE, ratio: 16 / 9 },
  together: { file: 'scenes/studying-together.png', kind: SCENE, ratio: 16 / 9 },
  perspective: { file: 'scenes/different-places-new-perspectives.png', kind: SCENE, ratio: 16 / 9 },
  world: { file: 'scenes/exploring-the-world.png', kind: SCENE, ratio: 16 / 9 },
  tomorrow: { file: 'scenes/a-brighter-tomorrow.png', kind: SCENE, ratio: 16 / 9 },
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
  return entry
    ? { ...entry, src: `${BRAND_ROOT}/${entry.file}`, state }
    : null;
}

export function feelingAsset(feeling) {
  const file = feelings[feeling];
  return file
    ? { file, src: `${BRAND_ROOT}/${file}`, kind: CHARACTER, ratio: 1, state: feeling }
    : null;
}
