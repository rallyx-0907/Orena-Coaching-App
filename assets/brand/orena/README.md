# Orena Brand Library

Canonical reference package for designers and coding/generation agents.

Start here:
1. `references/00_MASTER_REFERENCE_APPROVED.png`
2. `BRAND_MASCOT_GUIDE.md`
3. `AGENT_GENERATION_CONTRACT.md`
4. `tokens/brand-tokens.json`
5. `actions/` and `expressions/`

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

### Known gaps

This package currently specifies the mascot, brand model, the three brand
layers, props, tokens and approved references. It does **not** yet specify:

- content thumbnail rules (real image versus illustration, crop, title overlay,
  category markers, duration and level placement);
- book cover system (cover-first layout, genre variation, title legibility, no
  single-letter placeholder);
- the icon family (stroke and fill, colour, active and inactive states,
  decorative versus learning-action icons);
- background and pattern usage;
- motion vocabulary.

These are recorded gaps, to be closed by an explicit art-direction task. Until
then an agent reuses what this package already approves and raises the gap; it
does not invent a style for one surface.
