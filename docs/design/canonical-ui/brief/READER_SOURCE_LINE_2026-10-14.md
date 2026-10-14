# Design addendum: the Reader's source line (2026-10-14)

**Status: addendum, pending the next Claude Design export.** The Claude Design project cannot be edited from this
repository, so this file records the addition in the repo first; the next export should draw it and replace this
file with a pin. It reuses styles the pinned `Orena.dc.html` already draws and adds no colour and no component.

## Human decision (2026-10-14)

"Do the source/licence presentation in the Reader now, but keep the scope small. Add it to the canonical design
first, then implement: publisher/source; creator/author when needed; an 'Original article' link ('Bài gốc') to the
canonical original URL; licence name + licence link when the metadata determines them." Source and original URL are
mandatory for external-source articles; if rights or licence is unknown the article is not auto-published (admin
publish needs an audited override, D-190), so the word "unknown" is never displayed. Not a Reader redesign;
the thumbnail is not a blocker.

## Where it sits

At the **end of the article text, inside the scrolled reading region**, after the last paragraph and before the
end-of-text block (`rdEndNote` and its buttons). It is a footnote to the text, scrolls with it, takes no space in the
toolbar, aids bar or side panels, and so changes no layout and no viewport fit (Design Contract rule 49). Same
placement on desktop and phone: a wrapping line in the 680px text column. The toolbar's `rdDocMeta` keeps showing the
publisher only (D-189); a toolbar line cannot hold a link or a licence without crowding the workspace.

Content Detail: not changed (its hero meta already shows the publisher; a licence/link row would be a new
component there). Learner-imported texts and library books are unaffected: only the article payload carries
`provenance`.

## How it looks (reused, measured from the pinned frame 14)

- Text style: the Reader toolbar's meta line (`rdDocMeta` container): 13px, weight 400, colour `var(--muted)`,
  interface face (`var(--font-ui)`), line-height 1.6.
- Links: the inline text link the Reader already draws for "Retry" (`.s-reader__retry`): `var(--accent-text)`,
  weight 600, no outline, no ring, underline on hover only. No violet.
- Separator: a middle dot, as the toolbar meta line uses (` · `).
- Spacing: a 26px column gap like every article child, pulled 8px toward the text (a footnote), then the end block's
  own top rule.

## Content and behaviour

`Source: {publisher} · by {author} · Original article · {licence}`, each part only when its data exists:

| Part | Shown when | Behaviour |
| --- | --- | --- |
| `Source: {publisher}` | `provenance.publisher` | plain text |
| `by {author}` | `provenance.author` and it differs (case-insensitive) from the publisher | plain text |
| `Original article` | `provenance.url` is a valid http or https address | link, `target="_blank" rel="noopener noreferrer"` |
| `{licence}` | `provenance.license.name` is present (a recognised licence) | link to `license.url` when that is a safe http(s) address, else plain name |

Nothing is drawn when none applies. A value that is empty or says "unknown" is dropped, never printed. A non-http(s)
address (for example `javascript:`) is never an href. `provenance.text` (English fallback) is not displayed.

| | EN | VI | ZH |
| --- | --- | --- | --- |
| Source | Source: {name} | Nguồn: {name} | 来源：{name} (full-width colon) |
| Author | by {name} | tác giả {name} | 作者：{name} |
| Original link | Original article | Bài gốc | 原文 |

The licence is shown by its own name (for example "CC BY 3.0"), which is not translated.
