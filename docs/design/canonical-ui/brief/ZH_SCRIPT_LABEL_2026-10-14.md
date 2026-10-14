# Design addendum: the Traditional Chinese label (2026-10-14)

**Status: addendum, pending the next Claude Design export** (same footing as `READER_SOURCE_LINE_2026-10-14.md`). It
reuses three places the pinned `Orena.dc.html` already draws and adds no component, colour or line.

## Decision it carries out

D-189: Traditional script is allowed but must be labelled and never mixed with Simplified. Simplified is the default of
the Chinese content and is **not labelled**. Only a Traditional Chinese article (`script` = `zh-Hant`) is.

## Where the label sits (existing elements only)

| Surface | Element reused | Position |
| --- | --- | --- |
| Discover card | the card's tag list (the level and topic chips, `mediaCard()` `tags`) | one more neutral tag, after the level |
| Content Detail hero | the hero meta line (`source · level · minutes`) | after the level: `source · level · Traditional · minutes` |
| Reader toolbar | the second line `rdDocMeta` (`source · kind · level · mode · page`) | after the level: `… · level · Traditional · mode …` |

The Content Detail "Related" list rows use the same meta line as the hero. No new row, no badge, no icon, no colour;
the neutral tag is the topic chip's style (not the accent-toned level chip).

## Copy

| | EN | VI | ZH |
| --- | --- | --- | --- |
| Label | Traditional | Phồn thể | 繁體 |

The Chinese label names the script in that script on purpose, so a learner who reads only Simplified recognises it.

## Not drawn for the learner

`mixed` (Simplified and Traditional in one text) and `unknown` (too short to tell) are reviewer signals. Admin Reading
shows them in the evidence panel (Chinese script) and `script_mixed` as a soft quality issue; the learner sees nothing.
