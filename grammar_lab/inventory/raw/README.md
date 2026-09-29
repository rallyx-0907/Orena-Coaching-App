# Raw source metadata (SPEC section 4, step 1)

Metadata only -- item codes, short names and the level a source gives them. No explanatory text is
copied from any source; sources are used to cross-check the catalogue and to anchor points
(`source_anchors`), never as wording.

| File | Source | How it was made |
| --- | --- | --- |
| `core_inventory_en.csv` | British Council / EAQUALS *Core Inventory for General English* (2011 edition, Appendix E "Exponents for Language Content", A1-C1; public, free) | text layer of the public PDF parsed by `sources/parse_core_inventory.py`; `code` is the inventory's own item number, `level` the level section it is listed under (the numbering restarts at each level, which is how the level is told), `page` the PDF page. Names are cut where the PDF wraps a line, so treat `code` + `level` as the key, not `name`. |

The HSK 3.0 grammar outline (GF 0025-2021, appendix 4, PDF pages 176-260 of a scanned file with no text
layer) is read by a vision model, not OCR on this machine; its rows will land here as
`hsk3_grammar_zh.csv` when that run is approved.
