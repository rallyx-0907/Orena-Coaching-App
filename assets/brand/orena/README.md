# Orena Brand Library

Canonical reference package for designers and coding/generation agents.

Start here:
1. `references/00_MASTER_REFERENCE_APPROVED.png`
2. `ART_BIBLE.md`
3. `BRAND_MASCOT_GUIDE.md`
4. `AGENT_GENERATION_CONTRACT.md`
5. `tokens/brand-tokens.json`
6. `actions/` and `expressions/`

Do not regenerate the mascot from memory when these references are available.

## Art direction authority (D-057)

This package is Orena's **Art Bible**: the canonical owner of the product's art
direction. There is no second artwork authority, and no surface, page or
component may define its own visual style outside it. A future `ART_BIBLE.md`
belongs inside this package, as part of the same authority, never beside it.

All production artwork must belong to one visual system. Its governed scope is:

- mascot and character;
- world and scene illustration;
- content thumbnail;
- book cover;
- icon;
- badge;
- empty state;
- background and pattern;
- motion.

Artwork must do at least one job — identify content, create curiosity,
communicate mood, support navigation, create continuity, explain meaning, or
reinforce a learning action. Artwork that only fills an empty space does not
belong in the product.

Content artwork may use a richer, more vivid authored palette than the UI. That
licence belongs to artwork alone: interface colour keeps its single owner in
`static/orena/theme.css`, and any text or control placed over artwork still
meets the contrast rules. See `docs/project/DESIGN_CONTRACT.md` rules 14-16.

`ART_BIBLE.md` holds the direction itself: the overall visual language, mascot
placement, scene illustration, content thumbnails, book covers, the icon family,
backgrounds and patterns, motion, composition, and worked DO / DON'T examples.
The mascot's own identity stays in `BRAND_MASCOT_GUIDE.md` and its generation
procedure in `AGENT_GENERATION_CONTRACT.md`.

### Known gaps

The five specification gaps recorded when this section was written — thumbnails,
book covers, the icon family, backgrounds and patterns, motion — are closed by
`ART_BIBLE.md`.

What remains open is **artwork, not rules**, and is listed in that file's own
"Known gaps": no real book-cover artwork exists in the repository, no approved
artwork exists for curated audio arriving without a poster, icon coverage is
partial, and no shared motion tokens exist yet. Until an asset exists, an agent
uses the deterministic designed-cover system in `ART_BIBLE.md` §D.1 and raises
the gap; it does not invent a style for one surface.
