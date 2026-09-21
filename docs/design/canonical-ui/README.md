# Canonical UI Baseline (pinned)

## Governance

Purpose: a repository copy of the frozen learner-facing UI baseline, so the
visual and data authority does not live only in a design tool. Authority: D-066.
The screens here are the visual source of truth; nothing under `static/` or
`templates/` outranks them. Change when the human approves a new baseline
revision; never edit these files to make an implementation pass. Do not store
demo data here that could reach production.

## Source

claude.ai design project `7a5604ca-1e11-4d8e-8305-7d0cb32d552d`, pinned on
2026-09-21. `PINS.tsv` lists every file here with its byte size and SHA-256.

| Path | What it is |
| --- | --- |
| `screens/Orena-*.dc.html` | The frozen canonical screens: the master preview and the Home Discover, Reading, Listening, Speaking, Writing, Vocabulary and Progress files. Desktop 1920x1080 and mobile 390x844 frames, one file per capability. |
| `data-contracts/*.json` | The 17 canonical data contracts. A screen's API contract is derived from these, not from the backend's older shapes. |
| `tokens.json` | The Glass System foundations, extracted verbatim. |

Not pinned, and where to read it:

- `Orena Quick Sheet.dc.html` - the design tool returns it inline, so it could
  not be copied byte for byte. Read it from the design project when a slice
  needs it (DesignSync `get_file`), and pin it here when a copy can be made.
- `ui-baseline/*.md` (screen matrix, templates, components, patterns,
  responsive, states) and `UI_BASELINE.md` - derived indexes over the screens.
  The screens and contracts win where they differ.
- `examples/mock-data.json` - deliberately not pinned. Its figures are demo
  values (a 128-day streak, 61 hours, rank 4) that D-066 forbids in production.
- `support.js` - the design tool's runtime, not part of the product.

## Reading a `.dc.html` file

Each file is a design canvas: the markup between `<x-dc>` tags carries one
`data-screen-label` block per screen and per frame, with inline styles that hold
the exact values. `{{ }}` placeholders and `x-import` frames are the tool's.
Extract a screen with `data-screen-label`, do not open the file as a web page.

## Known incompleteness in the baseline itself

Profile, My Content, Admin, Onboarding, Loading / Empty / Error, Modal / Drawer
and the tablet breakpoint have no canonical design. D-066 keeps the existing
implementation for those until the human supplies one.
