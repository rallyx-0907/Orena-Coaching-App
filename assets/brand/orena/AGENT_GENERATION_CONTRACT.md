# Agent Generation Contract — Orena Mascot

Use this contract whenever a new Orena mascot pose, action, or scene is required.

## Required inputs

Before generation, inspect:
- `references/00_MASTER_REFERENCE_APPROVED.png`
- the closest existing `actions/*.png`
- the closest `expressions/*.png`
- `tokens/brand-tokens.json`

## Generation instruction template

Create a new Orena red-panda mascot illustration for: **{ACTION / MOMENT}**.

The character MUST visually match the approved Orena mascot reference:
- same rounded red-panda face and proportions;
- same cream facial mask;
- same orange / sunset-red fur;
- same dark forest-ink limbs/details;
- same large curled striped tail;
- same compact friendly silhouette;
- same flat-vector construction;
- same soft restrained shading;
- same warm, curious, supportive personality.

Use the closest existing pose as structural reference:
`actions/{CLOSEST_REFERENCE}.png`

Expression reference:
`expressions/{EXPRESSION}.png`

The new action may change:
- pose;
- prop;
- gaze;
- hand/paw position;
- small environmental cues.

It MUST NOT change:
- species identity;
- face construction;
- ear construction;
- muzzle;
- tail language;
- core palette;
- overall body proportions;
- illustration style.

Prefer a simple readable silhouette at small size.
Avoid photorealism, 3D rendering, realistic fur, anime transformation,
generic fox anatomy, excessive gradients, neon AI aesthetics, and busy backgrounds.

If a scene is required, preserve the mascot exactly and expand only the environment.

## Acceptance checks

Reject and regenerate if:
- it reads as a fox rather than a red panda;
- the tail no longer matches the approved identity;
- the face looks like a different mascot;
- it becomes too baby/chibi;
- it becomes photorealistic or 3D;
- the palette drifts substantially;
- the action is unclear at thumbnail size;
- the prop becomes more visually important than the mascot;
- it looks inconsistent beside existing files in `actions/`.
