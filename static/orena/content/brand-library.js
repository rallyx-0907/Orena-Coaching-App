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
   should show nothing rather than reach for a mascot.

   The approved set was replaced, and the replacement is uniform in a way the
   old one was not: every scene is 16:9 and every character is square, and no
   scene carries a printed caption strip any more. Six scenes now exist where
   ten were mapped, so the scenes go to the three page heroes and the three
   rooms that are actually composed around one, and the states that used to
   hold a scene take the character artwork that says the same thing. Nothing
   here is a stand-in chosen to satisfy a check: a state whose meaning no
   approved file carries would be removed, not filled. */
const library = {
  // The three editorial heroes. These are the only places a full 16:9 scene
  // is given room, so each one goes to the scene that names that room.
  discovery: { file: 'scenes/exploreing-the-world.png', kind: SCENE, width: 264, height: 149 },
  returning: { file: 'scenes/a-brighter-tomorrow.png', kind: SCENE, width: 264, height: 149 },
  together: { file: 'scenes/learning-at-home.png', kind: SCENE, width: 264, height: 149 },
  // Rooms composed around a scene of their own.
  listening: { file: 'scenes/listening-to-the-world.png', kind: SCENE, width: 264, height: 149 },
  conversation: { file: 'scenes/studying-together.png', kind: SCENE, width: 264, height: 149 },
  creating: { file: 'scenes/creating-ideas.png', kind: SCENE, width: 264, height: 149 },
  // The learner in a moment, on transparency, sitting directly on the page.
  exploring: { file: 'actions/explore.png', kind: CHARACTER, width: 160, height: 160 },
  reading: { file: 'actions/learn.png', kind: CHARACTER, width: 160, height: 160 },
  speaking: { file: 'actions/speak.png', kind: CHARACTER, width: 160, height: 160 },
  writing: { file: 'actions/take-notes.png', kind: CHARACTER, width: 160, height: 160 },
  focus: { file: 'actions/practice.png', kind: CHARACTER, width: 160, height: 160 },
  thinking: { file: 'actions/think.png', kind: CHARACTER, width: 160, height: 160 },
  // Recall and the kept collection sit under "your growing world", and this is
  // the action that says it.
  remembering: { file: 'actions/grow.png', kind: CHARACTER, width: 160, height: 160 },
  completion: { file: 'actions/achieve.png', kind: CHARACTER, width: 160, height: 160 },
  celebrating: { file: 'actions/celebrate.png', kind: CHARACTER, width: 160, height: 160 },
  empty: { file: 'actions/hello.png', kind: CHARACTER, width: 160, height: 160 },
  recovery: { file: 'actions/care.png', kind: CHARACTER, width: 160, height: 160 },
  learning: { file: 'actions/idea.png', kind: CHARACTER, width: 160, height: 160 },
  perspective: { file: 'actions/discover.png', kind: CHARACTER, width: 160, height: 160 },
  world: { file: 'actions/plan.png', kind: CHARACTER, width: 160, height: 160 },
  resting: { file: 'actions/reset.png', kind: CHARACTER, width: 160, height: 160 },
};

/* A feeling, for moments that carry one. Kept apart from the states above
   because an expression answers "how did that go?" rather than "where am I?".

   Six expressions are approved where ten were mapped. The four with no
   artwork are gone rather than pointed at a substitute; the two that were
   renamed keep their meaning here, because this library addresses artwork by
   what it means and not by what it is called on disk. */
const feelings = {
  curious: 'expressions/curious.png',
  thinking: 'expressions/thinking.png',
  happy: 'expressions/happy.png',
  surprised: 'expressions/surprised.png',
  laughing: 'expressions/laugh.png',
  winking: 'expressions/wink.png',
};

export const SCENE_STATES = Object.keys(library);
export const FEELINGS = Object.keys(feelings);

export function sceneAsset(state) {
  const entry = library[state];
  return entry ? shape(entry, state) : null;
}

/* Presentation facts taken from the artwork itself.

   The previous set mixed ratios and printed a caption strip under a few
   scenes, which had to be framed out. The approved set is uniform - 16:9
   scenes, square characters, no strips - so every asset is now shown whole.
   `fit` stays in the shape because it is what the stylesheet reads; it simply
   has one value while every approved file is a clean edge-to-edge image. */
function shape(entry, state) {
  return {
    ...entry,
    state,
    src: `${BRAND_ROOT}/${entry.file}`,
    ratio: entry.width / entry.height,
    fit: entry.caption ? 'crop-caption' : 'whole',
  };
}

export function feelingAsset(feeling) {
  const file = feelings[feeling];
  return file
    ? shape({ file, kind: CHARACTER, width: 122, height: 122 }, feeling)
    : null;
}
