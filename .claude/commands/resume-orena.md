# Resume Orena

Restore current project context without relying on chat history and without
loading the historical repository.

1. Inspect, without mutation:
   - `git branch --show-current`
   - `git rev-parse HEAD`
   - `git status --short`
   - `git log -5 --oneline`
2. Read in order:
   - `docs/project/PROJECT_MEMORY.md`
   - `docs/project/PRODUCT_CONSTITUTION.md`
   - `docs/project/CURRENT_PRODUCT_STATE.yaml`
   - `docs/project/LEGACY_TOMBSTONES.md`
   - `docs/project/CURRENT_HANDOFF.md`
3. Determine the current task from the handoff. Read only its relevant section
   in `docs/project/PRODUCT_MAP.md` and only its relevant section in
   `docs/project/ROADMAP.md`.
4. Consult `DECISION_LOG.md` only if a durable decision is relevant. Do not load
   archived handoffs or all historical evidence.
5. If the current task is learner-facing UI or native work, read
   `docs/project/DESIGN_CONTRACT.md`, then the Orena UI foundation in order:
   `ORENA_PRODUCT_DNA.md`, `ORENA_DESIGN_TOKENS.json`,
   `ORENA_COMPONENT_CONTRACT.md`, `ORENA_RESPONSIVE_COMPOSITION.md`, and the
   relevant `ORENA_*_GOLDEN_SPEC.md` when one exists.
6. If live Git/code contradicts memory, use the intent/fact precedence in
   `PROJECT_MEMORY.md` and report `MEMORY CONTRADICTION` rather than guessing.

Output only:

```text
PRODUCT:
BRANCH:
HEAD:
CURRENT STAGE:
LAST VERIFIED:
IN PROGRESS:
OPEN P0/P1:
HUMAN GATES:
NEXT TASK:
```
