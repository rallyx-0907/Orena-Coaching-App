# Vendored export profile

`export_profile.schema.json` is Grammar Lab's export profile 1 (`grammar-export-profile/1`), copied byte for byte from
`grammar_lab/schema/export_profile.schema.json` at Grammar Lab commit `3579ece887c226b31d03b759b720261b8fa1d31d`
(`feature/grammar-lab-pipeline`, after PR #97). Decision D-106.8; proposal `GRAMMAR_CONTENT_STORE.md` section 5.1.

- Canonical-JSON SHA-256 (the manifest's `profile_schema_hash`): `0671ac912967a230d6073a454f82d6e66e20af67a6adfe3bde95c03c9f06541f`,
  pinned as `PROFILE_SCHEMA_HASH` in `writing_coach/grammar_store/contract.py`; a test fails if the file drifts.
- It is a schema, not content (D-105.4). No grammar point ships with the source.
- A new profile is a new file, a new constant and a reviewed change, never an edit of this one.
