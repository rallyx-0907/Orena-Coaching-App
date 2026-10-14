# Design addendum: Reading thumbnails and their credit (2026-10-14)

**Status: addendum, pending the next Claude Design export.** The Claude Design project cannot be edited from this
repository, so this file records the addition in the repo first; the next export should draw it and replace this file
with a pin. It adds no colour and no learner component. **Measurement pending:** the browser was not available when this
was built, so the learner and admin sizes below are the existing components' own (already measured against the pinned
frames by earlier slices) and are to be compared in a browser before the surface is called done (CLAUDE.md, UI rule 3).

## Human decision (2026-10-14)

The thumbnail is P1 ship-readiness. A real picture appears only when (a) the source's image policy allows it (off for
every source), (b) an administrator approved that specific candidate, and (c) a credit exists. Otherwise the card keeps the
generated letter tile, which is the design's no-image state. Pictures are never hotlinked: the server keeps its own copy.
Recorded as D-192 (proposed).

## Learner: no new component

- **Discover card** and **Content Detail hero**: the image slot the design already draws for books and media
  (`mediaCard` `image` / Content Detail hero `image`, a `background-image` on `.c-media__img` and the hero box). The article
  payload now carries `image: { url, credit, alt }` (a same-origin address, `/api/reading/articles/{id}/image?v=N`), or
  `null`. `null` draws the letter tile exactly as before. If the file fails to load, the card falls back to the tile
  (`settleCovers`).
- **Reader**: no picture is drawn in the reading room. The picture's credit joins the end-of-article source footnote
  (`READER_SOURCE_LINE_2026-10-14.md`) as one more part, after the original link and the licence: `Image: {credit}`.
  Same style, same placement, drawn only when the card shows a picture.

| | EN | VI | ZH |
| --- | --- | --- | --- |
| Footnote part | Image: {credit} | Ảnh: {credit} | 图片：{credit} (full-width colon) |

The credit is the approved credit, else the candidate's own credit, else the source's publisher. It is not translated.

## Admin: existing components only

- **Reading review page (A17):** one block, "Picture", in the right column above "Original source". Header: title, a pill
  ("Shown to learners" ok / "Letter tile" mute). Body: the existing hint line when the source does not allow pictures (with a
  link to the source), an optional "Credit" field (the existing text input), and the candidates as the existing row list.
  Each row's leading slot is a 96x64 preview (rounded 10px, object-fit cover, previewed by the server so the administrator's
  browser never contacts the publisher); title = role and size; meta = credit or caption; pills = "Approved" and why a
  candidate is not usable (Rejected, Used by other items, Too small, Odd shape); buttons = existing xs buttons
  (Approve primary, Reject, Remove).
- **Source page (A23):** one block, "Pictures", with an On/Off pill, a one-sentence hint, and one button (Allow pictures /
  Stop pictures). Allowing asks for the existing confirm dialog. Off is the default for every source.

## Selection rules (server)

Prefer the page's og:image, then the lead image, then the article's own images; never a logo, icon, sprite, avatar or a
picture 64px or smaller (extractor). A candidate is not offered for approval when its declared or real short side is under
400px, its aspect is outside 1:2 to 2:1, or the same address appears on two or more other items of the same source. Only
JPEG, PNG, WebP and GIF are accepted, by their bytes, up to 5 MB.
