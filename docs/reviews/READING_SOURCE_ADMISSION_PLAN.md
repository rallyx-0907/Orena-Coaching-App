# Reading source admission plan

Approved intent: S1 and D-111.1/2; human2026-10-04 chooses Reading next,
Grammar deferred. Existing reading engine, repositories, worker and Admin only.

Bounded slice: registered active source selection -> existing ingest job ->
deterministic EN/ZH processing -> automatic publication only with cleared source
rights, automation permission and valid grounded targets. Others stay in review
with recorded reasons. No paid question generation, migration or new content model.
Levels remain coarse estimates, never proof of learner proficiency.

UI provenance: Orena-Admin.dc.html A21 Add content field grid/select pattern
(Language control), A22 Sources and A23 article Review; adapt one existing select
to registered source identity, reuse existing review status/analysis presentation.
No new colour/layout/mascot; preserve human-owned Design Contract edit.

1. Regression tests: ZH targets respect real token and sentence boundaries;
   source binding and inheritance; EN/ZH admission; unknown/denied rights,
   disabled source/automation, invalid content/targets and attribution -> review;
   duplicate input/reopen does not republish or compute source again.
2. Reuse linguistic_annotation for ZH words and bounded repeated token phrases;
   remove character n-gram candidates, retain existing honest count/level contract.
3. Bind optional registered source id to existing Admin job submission. Validate
   state/language/source identity; snapshot inherited source rights with provenance.
4. Atomic candidate creation/admission using existing article/target/event schema;
   deterministic rule version/reasons in existing analysis. Distinguish automated
   approval actor from human review; no learner-side preparation.
5. Existing Admin Add form selects active source; review shows actual admission
   result/reasons with approved patterns and EN/VI/ZH copy.
6. Isolated tests, independent exact-commit review, sandbox EN/ZH browser import
   -> publication/read -> reopen, held invalid example; update canonical memory.
   Do not start unlimited worker loop or populate public content without rights.

Remaining after this slice: source supply at volume, pedagogy/level validation,
question materialization/auto-approval, content breadth; not full S1 completion.
