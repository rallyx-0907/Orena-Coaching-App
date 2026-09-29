# Canonical learner design (pinned)

## Governance

**This folder is a byte-for-byte pin of the design, not a second authority
(D-088).** The authority is Claude Design project
`e6dc1cb2-72d0-40b4-a916-5dcd47e17cc0`, read at its source; the pin exists so
the frames can be rendered and measured offline and so a later revision can be
diffed against exactly what was implemented. Never edit these files to make an
implementation pass. Change when the human approves a new revision: pin it,
record a `SYNC_<date>.md`, recompute `PINS.tsv`, and update
`IMPLEMENTATION_MAP.md` for every surface the revision touches.

Pinned revision: **`1790473816124946`**, 2026-09-27 (`SYNC_2026-09-27.md`).

## What is here

| Path | What it is |
| --- | --- |
| `screens/Orena.dc.html` | The learner app: shell, 63 frames, light/dark tokens and the state script. |
| `screens/Onboarding.dc.html` | First run. |
| `screens/Compare-With-Model.dc.html` | Speaking comparison, embedded by the Compare With Model frame. |
| `screens/support.js` | The design tool's runtime, to render the frames offline. Not product code. |
| `screens/Orena-Admin.dc.html` | Platform Admin's authority (project e6dc1cb2, pinned 2026-09-29, `SYNC_2026-09-29.md`, D-099). Its brief is `brief/ORENA_ADMIN_DESIGN_SPEC.md`. |
| `brief/` | The designer's brief, fidelity rules and project note: intent, not authority over a frame. |
| `IMPLEMENTATION_MAP.md` | Frame → route → code → gate → status, for every frame. |
| `data-contracts/*.json` | Backend response contracts written for the previous design; still read by backend tests (`WritingReview`, `WordDetail`, `DictationResult`). A surface's data is shaped by the new frames; these change only with their backend. |
| `tokens.json` | The superseded Dark Glass tokens, read only by the old UI's foundation gate until the cutover (D-091). |
| `superseded/7a5604ca/` | The previous learner design, the previous Admin Control Center and their sync notes. History, never a visual source. |
| `PINS.tsv` | Byte size and SHA-256 of every file here, recomputed from disk. |

## Reading a `.dc.html` file

The markup between `<x-dc>` tags is a template; `{{ }}` values and handlers come
from `class Component` in the `<script data-dc-script>` at the end of the file.
`<sc-if>` / `<sc-for>` render conditionally and repeat; `style-hover` and
`style-active` carry hover and pressed styles. Device and theme are CSS
variables on `body[data-device]` and `body[data-theme]`; `body[data-focus=1]`
is a learning workspace. Locate a frame by `[data-screen-label="…"]`.

To render it: `cd docs/design/canonical-ui/screens && python -m http.server 8765
--bind 127.0.0.1`, open `Orena.dc.html`, and use the prototype strip (Desktop /
Mobile, Light / Dark). That strip is prototype chrome, not product UI.

Sample content - lessons, sentences, names, numbers, the avatar - is not data
(D-068) and never reaches the product.
