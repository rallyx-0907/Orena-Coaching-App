# Design addendum: hiding built-in lessons from learners (2026-10-14)

**Status: addendum, pending the next Claude Design export.** The Claude Design project cannot be edited from this
repository, so this file records the decision in the repo first; the next export should draw it and replace this file with
a pin. It adds **no component, no colour and no new copy**: it reuses what Admin Content already draws for media. **Measurement
pending:** no browser was used for this slice (the owner barred it), so the sizes are the existing components' own, already
measured by earlier slices; compare in a browser before the surface is called done (CLAUDE.md, UI rule 3).

## Human decision (2026-10-14)

Content that ships in the repository (the Listening catalogue's six lessons, for example "A pen in my bag") is test material.
The Admin must be able to remove it from the product, with a server-side flag and without a code edit. Recorded as D-203
(proposed).

## Admin: existing components only

Where: Admin Content, Media (`#/admin/media`, the A11 list and the A12 detail). Curated (built-in) lessons are already listed
there with `origin: curated`; they were read-only (`preview` only).

- **List row and detail header:** the existing status pill. A hidden lesson shows the pill the design already draws for a media
  item that is off the shelf, "Unpublished" (mute). A shown lesson shows "Published" (ok). No new pill.
- **Action:** the existing footer/header button pair of a media item, unchanged: **Unpublish** (confirm dialog, "Learners stop
  seeing it. Nothing is deleted...") and **Republish** (primary). A built-in lesson offers no Archive, Reprocess or rights form
  (its text, rights and timing are the repository's).
- **Filter:** the existing status tabs. A hidden lesson is found under "Unpublished".
- **Learner link:** "Open as learner" is drawn only while published, as for every media item.

| | EN | VI | ZH |
| --- | --- | --- | --- |
| Hide | Unpublish | Gỡ xuất bản | 取消发布 |
| Show | Republish | Xuất bản lại | 重新发布 |

All of these strings already exist in `screens/admin/copy-content.js` (`ctAct_unpublish`, `ctAct_republish`,
`ctStatusUnpublished`, `ctStatusPublished`, in EN/VI/ZH). The owner's wording suggestion ("Ẩn khỏi người học" / "Hiện lại") is
not used: the existing pair means the same and adds nothing to translate.

## Known imprecision, not changed here

The existing Republish confirm body reads "It returns to the shelf. Putting it in front of learners again is a separate
decision." For an imported media item and for a built-in lesson, Republish makes it visible at once. This predates the slice and
is shared by both; it is reported to the human rather than reworded here (rule 4: no copy the design does not draw).

## Learner: nothing

A hidden lesson is simply absent: from the Listening library and its rails, from Speaking's shadowing list, from a word's
"heard in context" clips, from the learner's collection (a stored progress row for it reads as unavailable, with no title), and
a direct open answers the existing "This Listening lesson is unavailable." (404). No learner component is added or changed.
