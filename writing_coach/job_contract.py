"""Decisions around a provider/content job. Pure; no storage, provider or clock.

I5 of the backbone integration gates, against ORENA_CONTENT_EXECUTION_ARCHITECTURE
sections 3 and 4. The worker-publication fence itself - scope, state, lease
generation, account activity - is `reference_backbone.job_may_publish` and is
reused here rather than restated. The reservation lifecycle this contract hands
work to belongs to I3 - `reference_backbone.dispatch_decision`,
`settle_decision`, `release_decision` - and is neither implemented nor modified
here.

What lives here is everything around those: who may hold a lease and what a lost
one means, when a job may leave a state, how a provider answer maps onto an
application state, which failures may be retried at all, what a crashed worker
leaves behind, and what a finished or abandoned job owes its reservation when it
was never handed to a provider, finished for a known cost, or finished for a
cost nobody can state.

Callers own authorization, the row lock, the provider adapter and the clock.
These functions decide; they do not persist, call a provider, allocate a lease
generation or hold one.
"""
from __future__ import annotations

from dataclasses import dataclass

from writing_coach.reference_backbone import job_may_publish

# The states in section 3's transition table, and no others. Strings so that a
# new state is a code change and not a migration, with this registry as the
# strictness that keeps "string" from meaning "anything".
JOB_STATES = (
    'queued',
    'running',
    'waiting_retry',
    'outcome_unknown',
    'succeeded',
    'failed',
    'cancelled',
    'rejected',
)

# Terminal: a new learner action is a new operation ID, not a reopened job.
TERMINAL_JOB_STATES = ('succeeded', 'failed', 'cancelled', 'rejected')

# Section 3's table. `outcome_unknown` deliberately has no edge back to
# `running`: an unresolved external outcome is reconciled, never re-run.
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    'queued': frozenset({'running', 'cancelled', 'rejected'}),
    'running': frozenset({'succeeded', 'failed', 'waiting_retry', 'outcome_unknown', 'cancelled'}),
    'waiting_retry': frozenset({'running', 'cancelled', 'rejected'}),
    'outcome_unknown': frozenset({'succeeded', 'failed', 'cancelled'}),
    'succeeded': frozenset(),
    'failed': frozenset(),
    'cancelled': frozenset(),
    'rejected': frozenset(),
}


def _token(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')
    return value


def _generation(value: object) -> int:
    if type(value) is not int or value < 1:
        raise ValueError('A lease generation is a positive integer')
    return value


def _present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def job_transition(current: str, requested: str) -> str:
    """`commit`, `noop` when it is already there, or `refused`.

    The job analogue of `work_contract.lifecycle_change`. An unregistered state
    on either side is refused rather than guessed, and no terminal state has an
    exit.
    """
    if current not in _ALLOWED_TRANSITIONS or requested not in JOB_STATES:
        return 'refused'
    if current == requested:
        return 'noop'
    return 'commit' if requested in _ALLOWED_TRANSITIONS[current] else 'refused'


@dataclass(frozen=True)
class Lease:
    """One worker's claim on one job, as the caller's clock sees it.

    `expired` is the caller's verdict, not this module's: expiry is a clock
    decision and the adapter owns the clock. `holder` is the worker or provider
    delivery that claimed the generation - the same holder asking twice is the
    duplicate execution a lease exists to refuse, and a different holder is a
    worker the generation fences out.
    """

    generation: int
    holder: str
    expired: bool

    def __post_init__(self):
        _generation(self.generation)
        _token(self.holder, 'A lease holder')
        if not isinstance(self.expired, bool):
            raise ValueError('Lease expiry must be a boolean the caller decided')


def lease_acquire_decision(
    *, state: str, requester: str, current_lease: Lease | None = None,
    account_active: bool = True, retry_due: bool = True,
) -> str:
    """One worker's attempt to hold a lease on one job.

    Returns 'acquire' (take the next generation), 'already_held' (this same
    holder already holds the live lease - running the work twice is exactly the
    duplicate execution this refuses), 'busy' (another live holder has it),
    'recover' (the lease is expired or absent while the job is still running: a
    crashed worker's job, so recovery - not a plain acquire - decides whether
    the work may run again), 'reconcile_required' (an unresolved outcome is
    resolved, never re-run), 'not_due' (a waiting_retry job whose backoff has
    not elapsed), 'terminal', 'account_inactive' or 'refused'.

    The caller owns the atomic claim. This decides whether claiming is safe, and
    never itself grants a lease.
    """
    _token(requester, 'A lease requester')
    if account_active is not True:
        return 'account_inactive'
    if state not in JOB_STATES:
        return 'refused'
    if state in TERMINAL_JOB_STATES:
        return 'terminal'
    if state == 'outcome_unknown':
        return 'reconcile_required'
    if current_lease is not None and not current_lease.expired:
        return 'already_held' if current_lease.holder == requester else 'busy'
    if state == 'running':
        return 'recover'
    if state == 'waiting_retry' and retry_due is not True:
        return 'not_due'
    return 'acquire'


def lease_renew_decision(
    *, requester: str, held_generation: int, current_lease: Lease | None,
    state: str, cancelled: bool, account_active: bool = True,
) -> str:
    """A worker asking to keep the lease it believes it holds.

    Returns 'renew', or why it may not keep working: 'account_inactive',
    'cancelled', 'not_running' (the job left the states a lease covers),
    'lease_lost' (another generation, another holder, or no lease at all - this
    worker is fenced out and must stop) or 'lease_expired' (the worker's own
    generation is no longer alive). A worker that receives anything but
    'renew' must not commit; `job_commit_decision` refuses the same write
    independently, so a missed renewal cannot publish either.
    """
    _token(requester, 'A lease requester')
    _generation(held_generation)
    if account_active is not True:
        return 'account_inactive'
    if cancelled:
        return 'cancelled'
    if state not in ('queued', 'running'):
        return 'not_running'
    if (current_lease is None or current_lease.generation != held_generation
            or current_lease.holder != requester):
        return 'lease_lost'
    return 'lease_expired' if current_lease.expired else 'renew'


def source_revision_decision(captured_revision: object, current_revision: object) -> str:
    """'current', 'changed' or 'unknown' for a result computed against a source.

    Content architecture section 2: a missing revision is unknown, never a
    fabricated constant, and an unknown revision cannot be claimed to still be
    current - only two equal, present revisions are 'current'. A changed
    revision invalidates offsets and timing-dependent derived output, so the
    result may not attach to the edited source, while the original source
    relationship is still recorded on the evidence that was produced.
    """
    if not _present(captured_revision) or not _present(current_revision):
        return 'unknown'
    return 'current' if captured_revision == current_revision else 'changed'


def _publish_refusal(
    job_scope, current_scope, state: str, lease_generation: int | None,
    current_lease: int | None, account_active: bool,
) -> str | None:
    """The named reason when the shared publication fence says no."""
    if job_may_publish(job_scope, current_scope, state, lease_generation, current_lease, account_active):
        return None
    if job_scope != current_scope:
        return 'foreign_scope'
    if account_active is not True:
        return 'account_inactive'
    if state != 'running':
        return 'not_running'
    return 'lease_lost'


def job_commit_decision(
    *, job_scope, current_scope, state: str, lease_generation: int, current_lease: int | None,
    account_active: bool, captured_source_revision: object, current_source_revision: object,
    cancelled: bool = False,
) -> str:
    """Whether a finished worker may publish its result to the current source.

    'publish', or why not: 'foreign_scope' (another account, incarnation or
    learning language), 'account_inactive' (authorization ended, lease or not),
    'not_running' (the job already left running), 'lease_lost' (a stale worker
    after its generation was fenced - the provider outcome is still real and is
    resolved through reconciliation, never published into current work),
    'cancelled' (the cancellation fence suppresses publication even of a result
    the provider really produced), 'source_revision_changed' or
    'source_revision_unknown' (the result was computed against a source that is
    no longer verifiably the current one).

    Precedence is scope, account, state, lease, cancellation, then source
    revision, so a stale worker is always told it lost the lease rather than
    something derived from the job's later life. Scope/state/lease/account are
    `reference_backbone.job_may_publish`; the added conditions are the ones that
    fence does not carry. Access is revalidated by the adapter - this decides
    about a source it is told about, and decides nothing about retention.
    """
    refusal = _publish_refusal(job_scope, current_scope, state, lease_generation, current_lease, account_active)
    if refusal is not None:
        return refusal
    if cancelled:
        return 'cancelled'
    revision = source_revision_decision(captured_source_revision, current_source_revision)
    if revision == 'changed':
        return 'source_revision_changed'
    if revision == 'unknown':
        return 'source_revision_unknown'
    return 'publish'


def recovery_decision(
    *, state: str, dispatched: bool, provider_handle_known: bool, provider_queryable: bool,
) -> str:
    """What a worker that finds a live-but-unattended job may do.

    'requeue' (nothing was handed to a provider, so running the work again
    duplicates no external execution), 'reconcile' (the provider can be asked
    about this job's own handle - ask it rather than repeat the call),
    'outcome_unknown' (acceptance may have happened and cannot be verified, so
    the job must be marked unresolved and settled explicitly, because lease
    expiry does not prove the provider stopped or that a resubmission is safe)
    or 'not_recoverable' (the state is not one a crashed worker left behind).
    """
    if state not in ('running', 'outcome_unknown'):
        return 'not_recoverable'
    if dispatched is not True:
        return 'requeue'
    return 'reconcile' if provider_handle_known is True and provider_queryable is True else 'outcome_unknown'


# The provider answers this contract can interpret. Anything else - a
# provider's private vocabulary, an absent field, a non-string - is
# `outcome_unknown`, because an unknown enum value must fail truthfully and can
# never become success (ORENA_BACKBONE_CONTRACTS section 4).
#
# `rejected` appears in both vocabularies with two different meanings, so the
# mapping is not one-to-one. The job state `rejected` is the admission refusal
# that happens before a lease (section 3's table reaches it from `queued` and
# `waiting_retry` only). A provider that refuses a request it already accepted
# is not that: the operation produced no result, so it resolves to `failed`
# with the sanitized provider reason kept. `outcome_unknown` has no edge to
# `rejected` for exactly this reason, and none back to `running`.
PROVIDER_OUTCOMES = ('succeeded', 'failed', 'rejected')
_PROVIDER_STATE = {'succeeded': 'succeeded', 'failed': 'failed', 'rejected': 'failed'}


def provider_outcome_state(outcome: object) -> str:
    """The application state one provider answer for one operation means.

    Only an outcome this contract registered maps to a state. 'outcome_unknown'
    is a truthful answer, not an error, and the caller resolves it through
    `reconciliation_decision` rather than inferring a result from latency, HTTP
    shape or an absent field. A provider refusal after acceptance maps to
    `failed`, not to the pre-lease admission state `rejected`; see the note on
    PROVIDER_OUTCOMES.
    """
    if not isinstance(outcome, str):
        return 'outcome_unknown'
    return _PROVIDER_STATE.get(outcome, 'outcome_unknown')


def reconciliation_decision(*, state: str, provider_outcome: object, handle_verified: bool) -> str:
    """Resolving a job whose provider outcome is not yet known.

    'not_applicable' (no unresolved job here), 'resolve' (the provider gave a
    verifiable outcome for this job's own handle: map it with
    `provider_outcome_state` and move the job with `job_transition`),
    'not_started' (the provider verifiably holds no record of this operation:
    the work never ran, so the job resolves terminally without publishing and
    its reservation settles at zero units) or 'unknown' (the provider cannot be
    asked, or its answer cannot be verified - the job stays unresolved).

    'not_started' is an explicit resolution, not a resubmission. The same
    operation ID is never retried automatically, because a provider that cannot
    be asked is a provider whose acceptance cannot be ruled out.
    """
    if state not in ('running', 'outcome_unknown'):
        return 'not_applicable'
    if provider_outcome == 'absent':
        return 'not_started' if handle_verified is True else 'unknown'
    return 'unknown' if provider_outcome_state(provider_outcome) == 'outcome_unknown' else 'resolve'


def cancellation_decision(*, state: str, dispatched: bool) -> str:
    """What recorded cancellation does to a job that may be mid-execution.

    'already_cancelled' (idempotent repeat), 'already_terminal' (nothing left to
    cancel), 'cancel_released' (cancellation before dispatch: the job ends
    terminal now and its reservation is released, because nothing external
    happened), 'cancel_retained' (a provider was already called: the job is
    marked terminal, the lease/cancel fence suppresses publication, and the
    reservation stays until a settlement reconciles it - cancelled never means
    unbilled), 'reconcile_before_terminal' (the outcome is unresolved: the
    provider handle is reconciled first, so a cancelled job is never claimed to
    have cost nothing while an unverified call may still settle) or 'refused'.

    A disconnect ends a subscription or poll; it is not a cancellation.
    """
    if state not in JOB_STATES:
        return 'refused'
    if state == 'cancelled':
        return 'already_cancelled'
    if state in TERMINAL_JOB_STATES:
        return 'already_terminal'
    if state == 'outcome_unknown':
        return 'reconcile_before_terminal'
    return 'cancel_retained' if dispatched is True else 'cancel_released'


# Only an explicitly registered retryable class is retried. An unregistered
# class is a caller bug that must not become a silent retry, and a timeout
# after dispatch is neither retryable nor permanent: the operation may have
# been accepted, so it reconciles instead of repeating a call that could be
# billed twice.
RETRYABLE_FAILURE_CLASSES = ('transient', 'rate_limited', 'provider_unavailable')
RECONCILE_FAILURE_CLASSES = ('timeout_after_dispatch',)
NON_RETRYABLE_FAILURE_CLASSES = (
    'invalid_input',
    'unauthorized',
    'forbidden',
    'conflict',
    'rejected',
    'quota_exhausted',
)
FAILURE_CLASSES = RETRYABLE_FAILURE_CLASSES + RECONCILE_FAILURE_CLASSES + NON_RETRYABLE_FAILURE_CLASSES


def retry_decision(
    *, failure_class: object, attempts: int, max_attempts: int,
    deadline_remaining: bool, budget_remaining: bool,
) -> str:
    """Whether a failed attempt may be retried under this job's own operation.

    'retry', 'permanent_failure' or 'reconcile'. `attempts` counts the attempts
    already made, so a retry needs `attempts < max_attempts`, a remaining
    deadline and a remaining budget. Invalid, unauthenticated, forbidden,
    conflict, rejected and exhausted-quota failures are not generic retryable
    outages (ORENA_BACKBONE_CONTRACTS section 3); a timeout after dispatch
    reconciles instead; everything else is permanent.
    """
    if type(attempts) is not int or attempts < 1:
        raise ValueError('Attempts already made must be a positive integer')
    if type(max_attempts) is not int or max_attempts < 1:
        raise ValueError('Max attempts must be a positive integer')
    if failure_class in RECONCILE_FAILURE_CLASSES:
        return 'reconcile'
    if failure_class not in RETRYABLE_FAILURE_CLASSES:
        return 'permanent_failure'
    if attempts >= max_attempts or deadline_remaining is not True or budget_remaining is not True:
        return 'permanent_failure'
    return 'retry'


def reservation_outcome_decision(*, dispatched: bool, actual_units_known: bool) -> str:
    """What a finished, refused or abandoned job owes its I3 reservation.

    'release' (nothing was handed to a provider, so a cancellation before
    dispatch releases the reservation), 'settle' (a provider was called and the
    actual cost is known: settle once by operation identity, releasing the
    unused remainder) or 'retain_unknown_cost' (a provider was called and its
    cost cannot be stated: the reservation is retained until reconciliation,
    because no TTL may release allowance for work that may still be billed).

    The job contract does not implement or modify I3. The caller maps these
    onto the existing commerce decisions - `reference_backbone.release_decision`
    and `settle_decision` - which own the atomic bucket update, the admitted
    bound and the idempotency of a repeat settlement.
    """
    if dispatched is not True:
        return 'release'
    return 'settle' if actual_units_known is True else 'retain_unknown_cost'


def result_delivery_decision(*, acknowledged: bool, result_ref: object, prior_result_ref: object = None) -> str:
    """One application of one job result to the owning domain.

    'deliver', 'duplicate' (this exact result reference was already
    acknowledged: a job result is not automatically evidence, and a retried
    delivery must not create second evidence) or 'payload_conflict' (the
    operation is acknowledged with a different result reference - a retry
    cannot revise a result). The caller owns the atomic acknowledgment; the
    reservation settles through `settle_decision` and is not decided here.
    """
    _token(result_ref, 'A result reference')
    if acknowledged is not True:
        return 'deliver'
    return 'duplicate' if prior_result_ref == result_ref else 'payload_conflict'
