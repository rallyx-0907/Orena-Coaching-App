"""Pure reference contract decisions for future domain adapters.

No storage, authentication, billing or runtime activation. Callers must supply
server-verified scope and transactionally locked state. These functions specify
decisions, not a substitute for repository isolation or durable idempotency.
See docs/product/ORENA_BACKBONE_CONTRACTS.md and its companion specifications.
"""
from dataclasses import dataclass
from collections.abc import Iterable


@dataclass(frozen=True)
class Scope:
    account: str
    incarnation: str
    language: str

    def __post_init__(self):
        if not all(isinstance(v, str) and v.strip() for v in (self.account, self.incarnation, self.language)):
            raise ValueError('A verified, complete scope is required')


@dataclass(frozen=True)
class Mutation:
    scope: Scope
    domain: str
    resource: str
    operation: str
    digest: str
    expected_version: int


@dataclass(frozen=True)
class Receipt:
    command: Mutation
    result_ref: str
    committed_version: int


def mutation_decision(command: Mutation, resource_scope: Scope, current_version: int,
                      receipt: Receipt | None = None, *, deleted: bool = False) -> str:
    """Evaluate after access authorization, inside the owning transaction.

    Version 0 denotes an absent resource for creation. Receipts are looked up by
    scoped domain/operation; compare the full command to prevent payload reuse.
    """
    if command.scope != resource_scope:
        return 'scope_denied'
    if deleted:
        return 'deleted'
    if receipt is not None:
        return 'replay' if receipt.command == command else 'operation_conflict'
    if command.expected_version != current_version:
        return 'version_conflict'
    return 'commit'


@dataclass(frozen=True)
class Quota:
    limit: int | None  # None is explicitly unlimited, not unknown entitlement.
    consumed: int | None
    reserved: int | None


def _units(value: object, *, positive: bool = False) -> bool:
    return type(value) is int and value >= (1 if positive else 0)


def reserve_decision(bucket: Quota, requested: int, *, entitlement: str = 'allowed') -> str:
    """One account/meter/window bucket; language must not create extra allowance.

    Caller owns atomic locking, duplicate-operation receipts and policy/window
    authorization. This decision alone cannot reserve anything.
    """
    if not _units(requested, positive=True):
        raise ValueError('Requested units must be a positive integer')
    if entitlement not in {'allowed', 'denied', 'unknown'}:
        raise ValueError('Unknown entitlement state')
    if entitlement != 'allowed':
        return entitlement
    for value in (bucket.limit, bucket.consumed, bucket.reserved):
        if value is not None and not _units(value):
            raise ValueError('Quota values must be nonnegative integers')
    if bucket.consumed is None or bucket.reserved is None:
        return 'unknown'
    if bucket.limit is None:
        return 'admit'
    return 'admit' if bucket.consumed + bucket.reserved + requested <= bucket.limit else 'exhausted'


def result_is_current(captured_scope: Scope, current_scope: Scope,
                      captured_context: tuple, current_context: tuple) -> bool:
    """Context: session epoch, source kind/ID/revision, work ID/version,
    exact focus identity, request generation. Adapters capture immutable values;
    focus identity includes the selected text/context, not its screen position.
    Unknown source revision still requires exact snapshot validation by adapter.
    """
    return (captured_scope == current_scope and len(captured_context) == 8
            and len(current_context) == 8 and captured_context == current_context)


def job_may_publish(job_scope: Scope, current_scope: Scope, state: str,
                    lease_generation: int, current_lease: int, account_active: bool) -> bool:
    """After provider return; access/source revision must also be revalidated."""
    return (account_active is True and job_scope == current_scope and state == 'running'
            and lease_generation == current_lease)


@dataclass(frozen=True)
class Evidence:
    scope: Scope
    domain: str
    id: str
    version: int
    acknowledged: bool
    invalidated: bool = False


def projection_evidence(scope: Scope, rows: Iterable[Evidence]) -> tuple[Evidence, ...]:
    """Select latest acknowledged domain versions before filtering tombstones.

    Input rows must already be authorized. This is not a mastery or scoring policy.
    Conflicting content for the same domain/version is rejected, never guessed.
    """
    latest: dict[tuple[str, str], Evidence] = {}
    for row in rows:
        if row.scope != scope or not row.acknowledged:
            continue
        key = (row.domain, row.id)
        prior = latest.get(key)
        if prior and prior.version == row.version and prior != row:
            raise ValueError('Conflicting evidence at the same domain version')
        if prior is None or row.version > prior.version:
            latest[key] = row
    return tuple(latest[key] for key in sorted(latest) if not latest[key].invalidated)


def growth_comparable(left_scope: Scope, right_scope: Scope,
                      left_metric: tuple, right_metric: tuple) -> bool:
    """Metric tuple: domain metric, evaluator version, assistance, task family.

    Compatible metadata is necessary; domain policy must still validate that
    the actual observations support a trend. Empty/unknown metadata is insufficient.
    """
    return (left_scope == right_scope and len(left_metric) == 4
            and len(right_metric) == 4 and all(left_metric)
            and left_metric == right_metric)


@dataclass(frozen=True)
class Cursor:
    scope: Scope
    filter_digest: str
    snapshot: str
    watermark: int


def cursor_matches(cursor: Cursor, scope: Scope, filter_digest: str, snapshot: str) -> bool:
    """A match is necessary, not sufficient: adapter validates signature/expiry."""
    return (cursor.scope == scope and cursor.filter_digest == filter_digest
            and cursor.snapshot == snapshot and bool(snapshot))


@dataclass(frozen=True)
class ProviderEvent:
    """One inbound subscription event or checkout callback, as the adapter saw it.

    `object_version` is the provider's own authoritative revision when the
    adapter could read one; it is None when it could not, which must reach
    this decision as an explicit unknown, never as an assumed 0 or a
    timestamp-derived guess. See ORENA_COMMERCE_ARCHITECTURE.md §3: "Arrival
    timestamps alone cannot decide which subscription state is newer."
    """
    event_id: str
    incarnation: str
    object_version: int | None


def subscription_event_decision(
    event: ProviderEvent, *, current_incarnation: str, incarnation_deleted: bool,
    already_processed: bool, current_object_version: int | None,
) -> str:
    """One decision per inbound provider event or checkout callback.

    Returns 'apply', 'duplicate', 'stale', 'unknown', 'foreign_incarnation' or
    'deleted_incarnation_rejected'. The caller owns idempotent receipt storage
    and the transactionally locked version compare/write; this only decides
    whether doing so is safe. 'unknown' must not be treated as safe to apply -
    "do not promote access or erase known valid state" (§3) - and the caller
    refetches current provider object state before deciding again.

    `current_object_version=None` means no subscription has ever been
    recorded for this incarnation - there is nothing to be stale against, so
    a verifiable event applies outright. That is a different situation from
    the event itself carrying no verifiable version, which is 'unknown'
    regardless of what current state exists: an unverifiable *new* fact can
    no more safely promote access than an unverifiable one can safely replace
    a known-good current fact.
    """
    if incarnation_deleted:
        return 'deleted_incarnation_rejected'
    if event.incarnation != current_incarnation:
        return 'foreign_incarnation'
    if already_processed:
        return 'duplicate'
    if event.object_version is None:
        return 'unknown'
    if current_object_version is not None and event.object_version <= current_object_version:
        return 'stale'
    return 'apply'
