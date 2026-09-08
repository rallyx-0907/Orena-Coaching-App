"""Decisions around the work aggregate. Pure; no storage or transaction.

I2 of the backbone integration gates, against ORENA_ACCOUNT_DATA_ARCHITECTURE
sections 4 and 5. The mutation decision itself - scope, receipts, expected
version, deletion - is `reference_backbone.mutation_decision` and is reused
rather than restated. What lives here is everything around it: what a lifecycle
change means, how a conversation turn lands against an expected head, what a
draft conflict hands back, and when a paginated snapshot may continue.

Callers own authorization, the row lock and the transaction. These functions
decide; they do not persist, and none of them can allocate a sequence.
"""
from __future__ import annotations

from collections.abc import Sequence

# The three states in section 3's Work record, and no others.
LIFECYCLE = ('active', 'completed', 'deleted')

# Deletion is terminal. Object IDs are not reused and an older update cannot
# resurrect an object, so nothing leaves `deleted` and nothing reopens
# `completed` - reopening would need a new work, not a state change.
_ALLOWED: dict[str, frozenset[str]] = {
    'active': frozenset({'completed', 'deleted'}),
    'completed': frozenset({'deleted'}),
    'deleted': frozenset(),
}


def lifecycle_change(current: str, requested: str) -> str:
    """`commit`, `noop` when it is already there, or `refused`."""
    if current not in _ALLOWED or requested not in LIFECYCLE:
        return 'refused'
    if current == requested:
        return 'noop'
    return 'commit' if requested in _ALLOWED[current] else 'refused'


def append_decision(
    *, expected_head: int, current_head: int, committed_ordinal: int | None = None
) -> str:
    """Where a conversation turn lands.

    A turn targets the head it was composed against. `committed_ordinal` is the
    ordinal a receipt says this operation already produced: presenting one means
    the append committed and the answer is that same turn, never a second one.
    Anything else that does not meet the current head is a conflict - a turn is
    never inserted behind the head or written ahead of it, because the sequence
    a learner read is part of what they replied to.
    """
    if committed_ordinal is not None:
        return 'replay'
    return 'append' if expected_head == current_head else 'head_conflict'


def conflict_branches(
    *, server_text: str, client_text: str, server_version: int, client_version: int
) -> dict[str, dict[str, object]]:
    """Both sides of a stale write, kept apart.

    Prose is not merged and no side is chosen: the learner reconciles. Equal
    text is still two branches, because two distinct attempts are not the same
    operation merely because they say the same thing.
    """
    return {
        'server': {'text': server_text, 'version': server_version},
        'client': {'text': client_text, 'version': client_version},
    }


def page_decision(
    cursor, scope, filter_digest: str, snapshot: str, *, watermark: int
) -> str:
    """Whether the next page may be served from the cursor the client holds.

    `scope_denied` and `restart` are different answers on purpose. A cursor
    from another account or another incarnation is a refusal. A cursor whose
    snapshot expired, whose filter changed, or whose watermark has moved
    backwards is not a refusal - it means acquiring a fresh snapshot, which the
    architecture requires rather than reading the next page from a different
    live snapshot and silently skipping rows.
    """
    if cursor.scope != scope:
        return 'scope_denied'
    if not snapshot or cursor.snapshot != snapshot or cursor.filter_digest != filter_digest:
        return 'restart'
    return 'serve' if watermark >= cursor.watermark else 'restart'


def sequence_is_contiguous(sequences: Sequence[int], *, after: int) -> bool:
    """Whether a page of change records continues the stream without a gap.

    The next change sequence is allocated under a per-incarnation stream-head
    row lock held until commit, so a reader that sees a gap has seen a writer
    commit ahead of a held lock - which is the failure this ordering exists to
    prevent. A repeat is equally wrong: a sequence identifies one committed
    change.
    """
    expected = after
    for value in sequences:
        expected += 1
        if value != expected:
            return False
    return True
