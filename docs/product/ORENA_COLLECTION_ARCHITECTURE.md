# Orena Collection, My Content and My Language architecture

Status: implementation specification. This defines retrieval and ownership,
not a navigation redesign. `#/collection` remains a deferred presentation; the
eleven current destinations and Opus's valid UI remain intact.

## 1. Distinct owners, one retrieval seam

My Content owns an account's relationships to content: imported, saved, started
or intentionally kept. Canonical body/media belongs to the content domain, and
unfinished responses belong to work. My Language owns saved language and its
encounter provenance; review history/scheduling remain with the existing library
and recall owner. Collection is a query/projection across those owners and work,
not a new authoritative copy of everything the learner has done.

Current anchors: `static/orena/product/memory.js` holds device relationships,
`static/orena/ui/collection.js` implements a deferred local view,
`static/orena/ui/collection-search.js` supplies the shared interaction primitive,
and `writing_coach/persistence/models.py:SavedWord` plus learning repositories
own saved words/review fields. Account architecture specifies how device sidecars
may later migrate; their presence is not current account durability.

## 2. Logical contracts

`ContentMembership = {id, accountIncarnation, learningLanguage, sourceRef,
relationship, version, createdAt, updatedAt, availability}`. A source may have
several relationships but one membership identity per relationship/scope. Starting
work does not imply saving; saving does not imply completing or acquiring rights.

`LanguageItemRef` points to the existing saved object, scoped by account/language.
`EncounterProvenance = {id, languageItemRef, sourceRef?, workRef?, focus?, reason,
observedAt?, version, availability}` records multiple real occurrences. Equal
normalized words do not establish equal meaning or identical encounters. Keep
existing word normalization/identity contract; add occurrence identities instead
of changing library keys or collapsing different contexts. Unknown origin remains
unknown. Reason is the shared KEEP_REASONS vocabulary, not fabricated evidence.

`CollectionEntry = {ref:{domain,id}, kind, sourceRef?, workRef?, languageItemRef?,
relationshipRefs, learningLanguage, title, snippet?, availability, durability,
updatedAt?, actions}` is a read projection. Namespace the entry ref by domain:
numeric ID 1 in Writing and Reading is not the same object. One source row may
group several work/relationship refs but must keep each return destination; never
drop a draft merely because its source already appeared in a media row.

Do not add folders, sharing or arbitrary tags implicitly. Their future seams
are membership relations with explicit access/version contracts. No public
sharing follows from an account collection; public promotion requires admission.

## 3. Retrieval query and pagination

`queryCollection(scope, {query, kinds, relationships, cursor, limit, sort})`
returns `{entries, nextCursor, completeness, unavailableOwners, snapshotVersion}`.
Scope is server-derived. Learning-language default is the current language;
any multi-language view is an explicit filter and labels entries individually.
Durability distinguishes account, device-unsynced and unavailable data.

Access filtering occurs before ranking, snippets and counts. Fetch private bodies
only through the authorized owner; index membership is not permission. Query
results re-resolve refs on open, so stale search cannot bypass revocation. Missing
or revoked items show unavailable only where the learner is entitled to know the
relationship; otherwise omit them. Do not leak global counts or foreign titles.

Start with bounded domain queries/projections; add PostgreSQL search indexing when
measured needed. No new search service/vector store or browser download of all
private content. A dedicated query adapter may aggregate owners without moving
their write authority. Stable sort uses server updated sequence and domain/id
tie-breaks. Cursor binds scope/incarnation, filters, sort and snapshot. Reject a
cursor reused with another query. Multi-owner pages use a materialized authorized
result snapshot or owner cursors plus a stable merge boundary; offset pagination
over changing data is not complete retrieval. Snapshot expiry requests refresh.

Search normalization is language-aware and separate from stored originals. EN
case/word matching and ZH character/segmentation matching use existing adapters;
do not require whitespace or romanize Chinese for identity. Declare indexed
fields and supported matching behavior; no claim of semantic search without it.
Returned snippets reference original text and preserve its writing system.
An owner outage gives a partial result with that owner unavailable, not an empty
collection. Counts specify exact-for-filter or unknown; never infer total from
the first page. Search queries and snippets are private, excluded from telemetry.

## 4. Mutation, retrieval and deletion lifecycle

Save uses the owner command plus idempotency receipt, then updates/invalidate the
query projection. A projection refresh failure cannot repeat a successful save.
Keep-language provenance is attached only after the saved object acknowledgment;
failure to attach provenance leaves a saved item with origin unavailable and a
retryable relation operation, not a second saved word.

Remove-from-My-Content deletes the chosen relationship; it does not erase the
source, learner response, saved phrase or review evidence. Delete-private-source
is a different explicit command with dependent access handling. Removing a saved
language item uses the library owner's lifecycle and review policy; Collection
cannot independently reschedule or delete related domain evidence. Deleting one
provenance occurrence leaves other occurrences intact. Deletion/revocation
invalidates retrieval snippets/indexes and prevents resurrection on offline sync.

`actions` contains resolvable semantic actions (open source, resume work, review
language) selected through canonical routing. No source is guessed from its title
or most recent unrelated thread. Capability lenses describe actual relationships,
not evidence of mastery. A work completion does not remove saved content, and a
plan downgrade does not delete a collection; entitlement limits affect authorized
new operations according to commerce policy.

## 5. Implementation acceptance

Opus first implements typed query adapters over existing stores, then account
membership/provenance repositories after the schema gate, then connects existing
My Content/My Language surfaces. Any promotion of deferred Collection navigation
is a distinct product decision. Require mixed source/work rows, namespace ID
collision, repeated phrase with two origins, private source revocation, owner
outage, snapshot pagination with concurrent additions, query/cursor mismatch,
remove relationship versus source deletion, and EN/ZH retrieval. Every result
must reach the actual source/work through current routing contracts.
