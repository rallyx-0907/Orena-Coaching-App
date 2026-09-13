# Orena account and data architecture

Status: implementation specification; logical contracts only. No new database
schema, synchronization service or migration has shipped through this document.
Companion: ORENA_BACKBONE_CONTRACTS.md. This resolves the architecture design
portion of reference package E; schema/production activation remains gated.

## 1. Identity and access boundary

Keep current `User.id`, `user_key`, verified session identity and repository
mapping. New APIs derive accountId on the server, never trust a client owner
field or email. Language-scoped resources require both account and learning
language in service authorization and repository predicates. Child-resource
access also verifies its parent scope; opaque IDs alone provide no access.
Background execution serializes the authenticated scope and rechecks account
status and resource access at execution and commit. Do not inherit ambient
request context in a worker. Admin access needs an explicit authorized use case
and audit record; an admin role is not implicit access to learner drafts.

Development `legacy` identity is not a shared production account. Account linking
never joins records by equal email; preserve existing identity until a separately
authorized identity migration. Session expiry preserves local work under its
original namespace, but prevents account writes. Reauthentication must resolve
the same principal before replay. Account switch does not upload old work.

Account identity additionally has a server-owned incarnation/access epoch. Keep
the stable external identity mapping, but after deletion ordinary auth upsert
must not silently recreate an active account. A durable deletion barrier denies
reactivation until an explicit re-registration flow creates a new incarnation.
Commands, receipts, private references, job scopes, caches and sync cursors include
that incarnation. Old sessions and pending uploads cannot target the new one;
external provider callbacks for the old incarnation may settle historical usage
under policy but cannot grant access to the new account. Deletion is permanent
(D-054): a deleted incarnation is never reactivated or restored, and
re-registration with the same external identity is a new incarnation that
inherits nothing. The barrier is therefore kept for the life of the deployment;
deletion cannot discard it while old credentials, jobs or operations could still
be accepted. No production identity change here.

### Learner profile, preferences and state

Identity profile (display identity) is account-wide. Learning profile is keyed by
account incarnation + learning language: goals, declared target level, preferred
practice context and language-specific aids. Support-language preference and
interface language are explicit independent values. A declared level is a goal,
never measured proficiency; projections cannot overwrite it as inferred fact.
Existing `UserLanguageProfile` and repository adapters remain the starting point.

Represent each effective setting as `{value, source, version}` with precedence:
temporary explicit session override, saved scoped preference, declared product
default. Defaults come from the language registry/policy, not scattered room
constants. A language switch loads that language's profile; it does not copy EN
work/settings into ZH. Preserve Vietnamese diacritics in support copy. Account-wide
settings must not be accidentally keyed by the current learning language.

Profile updates patch named supported fields with an expected profile version;
unknown fields do not erase existing values. Session overrides are ephemeral.
Playback position/focus belongs to work/continuation, not profile. Accessibility
and theme presentation are separate preferences; consume Opus's committed theme
registry and adapter without renaming presets or changing its storage now.
Any future account preference sync maps stable theme IDs through that owner and
handles an unavailable theme explicitly. A profile query composes identity,
preferences, commerce facts and learner projections through their read contracts;
it does not acquire write authority over those other domains.

## 2. Storage ownership matrix

| Object | Present authority | Target authority after gated implementation | Sync/conflict unit |
| --- | --- | --- | --- |
| Account/profile | PostgreSQL existing repositories | same account owner | explicit versioned profile fields; theme domain reserved to Opus |
| Shared media | canonical Media Learning, learner-neutral | same canonical owner with access/admission metadata outside media payload | source revision; never duplicate per skill |
| Imported private text/media relationship | device work plus existing media contracts | account-owned content access record and versioned body/reference | private source revision; no public promotion by saving |
| Draft/reading response | owner/language device memory | account work aggregate; device pending cache | one work ID and server version |
| Revision snapshots | device history plus existing essay/revision records | immutable submitted snapshot linked to existing evaluator result | submission ID; never overwrite the before-text |
| Conversation | device sequence | account work with ordered immutable turns and versioned head | expected head; separate learner/provider turn identities |
| Saved word/review | PostgreSQL library and schedule | same owner, additive provenance relationship | saved object ID; occurrences are separate relationships |
| Kept-language provenance | device sidecar after acknowledged save | account relation to saved object/source/focus | relation ID; missing provenance stays unknown |
| Continue | device references | account work-derived index plus device unsent work | source + work ref; not learning evidence |
| Evaluations/attempts | domain PostgreSQL repositories | same domain owners | immutable attempt and evaluator version |
| Derived learner view | existing domain summaries | rebuildable scoped projection | evidence versions + projection policy version |
| Microphone raw audio | transient capture | transient by default | no durable audio without separate authorization |

The target specifies ownership, not permission to upload device data today.
No generic JSON learner document becomes the source of truth for all domains.
Work stores drafts/turns, not a second copy of canonical evidence or curriculum.

## 3. Logical storage contract for Opus schema proposals

Reuse equivalent existing records rather than adding parallel ones. Where absent,
the implementation needs the following logical records (names are not table DDL):

- Work: immutable ID, account, language, kind, source reference, version,
  lifecycle (`active`, `completed`, `deleted`), domain payload, timestamps.
- Work revision/turn: immutable ID, parent work, version/ordinal, author role,
  exact content and source revision, optional acknowledged EvidenceRef.
- Provenance: ID, account/language, existing saved-object ID, SourceRef, focus,
  reason, availability. Deleting provenance does not grade or delete a review.
- Mutation receipt: account, command domain, operation ID, semantic request hash,
  committed result reference/version, server sequence. Unique command identity.
- Deletion tombstone/change record: scoped object ID, deleted version, monotonically
  increasing account sync sequence; acknowledgment/cursor policy.
- Projection checkpoint: account/language, policy version, consumed evidence
  references/checkpoint; discardable without loss of source evidence.

Account/language/parent constraints are enforced at writes and reads. Index
account+language+updated sequence for work lists, account+language+due for recall,
and scoped operation identity uniquely. Paginate bounded queries using stable
server cursors with tie-break IDs; avoid whole-account JSON scans. Large binaries
do not belong in work rows. Do not introduce object storage for transient audio.

## 4. Mutation and concurrency contract

New state-changing commands accept `operationId`, expected aggregate version
(creation uses absence), domain payload and source/work references. Scope comes
from the server. `operationId` identifies one logical action, not each HTTP try.
The server hashes validated semantic input, including command type and references.

In one transaction: recheck account/access and deletion state; inspect existing
receipt; return the same committed result for an identical retry; reject reuse
with different input; compare expected version; write domain changes, receipt
and change record atomically. Receipt lookup precedes version comparison for a
committed retry, but never bypasses present authorization. Parallel duplicates
serialize through the unique receipt/aggregate constraint. An uncommitted crash
leaves no success receipt. A lost response retries the same operation ID.

Use `committed {resultRef, version}`, `conflict {currentVersion}`,
`rejected {reason}`, or `pending {operationRef}`. Transport timeout means unknown
commit status, not permission to issue a new operation. A failed refresh only
retries the read. Two distinct attempts must not be deduplicated merely because
their text is equal. Server success must never be inferred from a browser cache.

Optimistic concurrency is the default for mutable work. A stale draft write
returns conflict with both versions retained for learner reconciliation; do not
last-write-win by client timestamp or merge prose automatically. A conversation
append targets an expected head; a retry returns its same turn, a simultaneous
different append conflicts. Evaluations point to immutable submitted snapshots;
editing a draft does not retarget an in-flight evaluation to new text.

Listening's existing aggregate replacement and client recovery remain current
behavior, not multi-device exactly-once evidence. The persistence implementation
package must move new attempts through a domain transaction and stable operation
identity before claiming concurrent safety. Migrate aggregates through an explicit
baseline record; do not fabricate historical individual attempts from counters.

## 5. Account synchronization and deletion

After activation, account work is authoritative on the server; local pending
work is explicitly unsynced. Pull uses an opaque cursor bound to account and
server sequence. Language filters cannot skip changes in another language:
maintain cursors per filter or consume the entire account stream. Push uses the
same mutation contract, never a separate offline write path. Auth/access failures
pause replay; version conflict retains both branches. Logout cancels replay and
clears active private objects; no browser callback crosses account namespaces.

Allocate the next change sequence under a per-account-incarnation stream-head
row lock held until commit, in the same transaction as the domain write. Every
producer (including deletion and workers) uses that ordering. A database sequence
allocated outside commit order is insufficient. A rolled-back transaction emits
no visible change; the next writer cannot commit ahead of a held stream lock.
Reads fetch a bounded committed watermark; snapshots and watermark come from one
consistent database snapshot. Pull after that watermark cannot miss a concurrent
write. Paginated snapshot pages use a stable snapshot token/materialized snapshot
until completion; do not read later pages from different live snapshots. Expired
snapshot token restarts snapshot acquisition without discarding pending edits.
Implement bounded snapshot lifetime; do not hold a DB transaction across browser
requests. Reconcile per-account serialization throughput in the load gate.

Deletion increments version and emits a tombstone in the same transaction.
Older updates cannot resurrect an object. A client older than retained change
history must fetch a fresh snapshot; pending edits remain quarantined until
explicit conflict resolution. Object IDs are not reused. Deleting a source makes
return unavailable and invalidates dependent projections; it does not turn
learner work into public content. Access revocation takes effect before cached
body or projection reads, including jobs waiting to commit.

Account deletion workflow: revoke new writes/sessions, cancel owned jobs, deny
private reads, enumerate domain-owned records, execute resumable domain deletion,
invalidate projections/caches, confirm completion. Hard deletion and retention
execution require approved policy and operator gate. Do not invent retention
days or legal obligations. A versioned policy supplies retention by data class,
receipt/tombstone horizon, backup expiry and restore suppression; missing policy
disables destructive purge and blocks sync activation if replay safety cannot
be maintained. Restore must reapply deletion records before serving learners:
every incarnation deleted after the backup was taken is marked deleted again in
the restored database, so its data is never served and it cannot be reactivated
(D-054). Retention durations for backups and logs are a separate
operational/legal policy; absent, destructive purge stays disabled and nothing
deleted is ever served.
Backups are access-controlled operational copies, never account sync authority.

Receipt compaction must preserve deduplication for all still-valid operations.
Retain minimal identity/hash/result markers, or reject expired operation epochs;
never forget a receipt and then accept its old ID as a new write. A privacy purge
can remove content while preserving a non-content replay barrier under the
approved retention policy. No perpetual retention promise is implied.

## 6. Migration and rollback sequence

1. Inventory real models/contracts and legacy scoped ID mappings; no resets.
2. Opus proposes additive Alembic changes and adapters against this specification.
   Codex reviews constraints, parent isolation, transactional receipts and indexes.
3. Run isolated migration/rollback and concurrent contract tests on PostgreSQL;
   SQLite tests alone are insufficient for transaction/concurrency acceptance.
4. Obtain explicit schema/runtime authorization, approved policy values and
   backup/restore evidence before any activation. Startup only verifies schema.
5. Add schema through an operator command. Keep existing domain API readers
   compatible; no startup Alembic, reverse sync or dual database write.
6. Offer explicit learner import of device work with preview and per-item
   source/owner/language validation. Deterministic import operation IDs prevent
   duplicates; retain local originals until acknowledged and explicitly retired.
   Unknown origin stays unknown; local timestamps do not establish evidence.
7. Activate new writes by coherent domain/version boundary. Existing evidence
   remains owned by existing repositories; no parallel authoritative store.
8. Verify scoped counts, representative content hashes, permissions, replay,
   deletion and projection parity. Observe before retiring compatibility reads.

Rollback before writes may disable the feature while keeping additive schema.
After new writes, roll back only to code able to read those versions, or disable
new writes and apply a reviewed forward repair. Do not down-migrate away learner
data. Restore is an authorized incident operation with measured recovery loss,
not a routine feature rollback. No rollback to SQLite authority.

## 7. Implementation acceptance

Require two accounts times EN/ZH; nested-resource foreign IDs; expired sessions;
simultaneous same/different operation IDs; response loss after commit; stale work
version; source revision mid-evaluation; offline stale edit after delete; account
switch mid-replay; old cursor full resync; failed migration and restore rehearsal.
Exact expected outcomes are in the backbone scenario gate and package ledger.
Operational policy values and credentials are activation inputs, not permission
for Opus to invent account architecture during feature work.
