# AGENTS.md router patch — 2026-09-17
## Merge only the routing requirement below; do not duplicate the full design contract in AGENTS.md.

For any learner-facing product, UX, UI, visual, content-discovery, Library, Reading, Listening, Speaking, Writing, Practice, Vocabulary/My Language or navigation task, the agent MUST read and obey:

- `docs/project/PRODUCT_CONSTITUTION.md`
- `docs/project/DESIGN_CONTRACT.md`
- `docs/ORENA_UI_AGENT_RULES.md` (if this repository uses the short UI agent rules file)
- the repository's current verified state/handoff files required by the existing governance chain.

Precedence:

1. authoritative product constitution;
2. durable design contract;
3. current verified product state;
4. task brief;
5. legacy implementation/screenshots.

Legacy UI is evidence of current implementation, not automatic design authority.

If a requested change would violate the constitution/design contract, stop and surface the conflict before implementation.

Do not copy the full product/design laws into AGENTS.md. AGENTS.md remains a router/enforcement entry point.
