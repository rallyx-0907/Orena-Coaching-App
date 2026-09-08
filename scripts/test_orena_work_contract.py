"""I2 work aggregate decisions. Pure; no database, transaction or session.

Counterexamples for ORENA_ACCOUNT_DATA_ARCHITECTURE sections 4 and 5: work
lifecycle, conversation append against an expected head, conflicts that retain
both branches rather than merging prose, and snapshot pages that come from one
snapshot rather than a fresh read each time.

The mutation decision itself is `reference_backbone.mutation_decision` and is
not restated here - these are the decisions that sit around it.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from writing_coach.reference_backbone import Cursor, Scope  # noqa: E402
from writing_coach.work_contract import (  # noqa: E402
    LIFECYCLE,
    MUTATION_DOMAINS,
    WORK_KINDS,
    UnknownRegistryValue,
    validate_domain,
    validate_kind,
    append_decision,
    conflict_branches,
    lifecycle_change,
    page_decision,
    sequence_is_contiguous,
)


class CanonicalRegistries(unittest.TestCase):
    """`works.kind` and `mutation_receipts.domain` are strings in PostgreSQL.

    Review finding 9: they stay strings backed by canonical application
    registries and strict validation, not PostgreSQL ENUMs - a new domain
    should not need a migration, and an ENUM would make it need one. The
    strictness therefore has to live here, and has to be enforced before a
    write rather than trusted.
    """

    def test_the_registries_are_not_empty_and_are_stable_tuples(self):
        self.assertIsInstance(WORK_KINDS, tuple)
        self.assertIsInstance(MUTATION_DOMAINS, tuple)
        self.assertTrue(WORK_KINDS and MUTATION_DOMAINS)

    def test_a_registered_kind_validates(self):
        for kind in WORK_KINDS:
            self.assertEqual(validate_kind(kind), kind)

    def test_a_registered_domain_validates(self):
        for domain in MUTATION_DOMAINS:
            self.assertEqual(validate_domain(domain), domain)

    def test_an_unregistered_kind_is_refused_by_name(self):
        with self.assertRaises(UnknownRegistryValue) as caught:
            validate_kind('screenplay')
        self.assertEqual(caught.exception.value, 'screenplay')
        self.assertEqual(caught.exception.registry, 'works.kind')

    def test_an_unregistered_domain_is_refused_by_name(self):
        with self.assertRaises(UnknownRegistryValue) as caught:
            validate_domain('billing')
        self.assertEqual(caught.exception.registry, 'mutation_receipts.domain')

    def test_empty_and_non_string_values_are_refused(self):
        for value in ('', None, 7, '  '):
            with self.assertRaises(UnknownRegistryValue):
                validate_kind(value)
            with self.assertRaises(UnknownRegistryValue):
                validate_domain(value)

    def test_validation_is_exact_and_not_case_or_space_forgiving(self):
        # A near-miss is a bug in the caller, not something to normalise away.
        with self.assertRaises(UnknownRegistryValue):
            validate_kind(WORK_KINDS[0].upper())
        with self.assertRaises(UnknownRegistryValue):
            validate_domain(f' {MUTATION_DOMAINS[0]} ')


class WorkLifecycle(unittest.TestCase):
    def test_the_three_states_are_the_ones_the_contract_names(self):
        self.assertEqual(LIFECYCLE, ('active', 'completed', 'deleted'))

    def test_active_work_may_be_completed_or_deleted(self):
        self.assertEqual(lifecycle_change('active', 'completed'), 'commit')
        self.assertEqual(lifecycle_change('active', 'deleted'), 'commit')

    def test_completed_work_may_still_be_deleted(self):
        self.assertEqual(lifecycle_change('completed', 'deleted'), 'commit')

    def test_deleted_work_never_comes_back(self):
        # "Older updates cannot resurrect an object", and object IDs are not
        # reused - so nothing leaves the deleted state.
        for requested in ('active', 'completed'):
            self.assertEqual(lifecycle_change('deleted', requested), 'refused')

    def test_deleting_twice_is_not_a_second_deletion(self):
        self.assertEqual(lifecycle_change('deleted', 'deleted'), 'noop')

    def test_reopening_completed_work_is_refused_rather_than_silently_allowed(self):
        self.assertEqual(lifecycle_change('completed', 'active'), 'refused')

    def test_an_unknown_state_is_refused_rather_than_guessed(self):
        self.assertEqual(lifecycle_change('active', 'archived'), 'refused')
        self.assertEqual(lifecycle_change('whatever', 'deleted'), 'refused')


class ConversationAppend(unittest.TestCase):
    def test_an_append_at_the_current_head_is_accepted(self):
        self.assertEqual(append_decision(expected_head=4, current_head=4), 'append')

    def test_a_retry_of_the_same_turn_returns_that_turn_rather_than_a_second_one(self):
        # The receipt is the caller's; presenting one means this operation
        # already committed, so the answer is the turn it committed.
        self.assertEqual(
            append_decision(expected_head=4, current_head=5, committed_ordinal=5),
            'replay',
        )

    def test_a_simultaneous_different_append_conflicts(self):
        self.assertEqual(append_decision(expected_head=4, current_head=5), 'head_conflict')

    def test_an_append_behind_the_head_conflicts_rather_than_inserting(self):
        self.assertEqual(append_decision(expected_head=2, current_head=5), 'head_conflict')

    def test_an_append_ahead_of_the_head_is_refused(self):
        # A client cannot skip an ordinal; turns are contiguous.
        self.assertEqual(append_decision(expected_head=9, current_head=5), 'head_conflict')


class ConflictsRetainBothTexts(unittest.TestCase):
    def test_a_stale_draft_write_keeps_both_versions_for_the_learner(self):
        branches = conflict_branches(
            server_text='The last train had already gone.',
            client_text='The last train home had gone without me.',
            server_version=7,
            client_version=6,
        )
        self.assertEqual(branches['server']['text'], 'The last train had already gone.')
        self.assertEqual(branches['client']['text'], 'The last train home had gone without me.')
        self.assertEqual(branches['server']['version'], 7)
        self.assertEqual(branches['client']['version'], 6)

    def test_nothing_is_merged_and_no_side_is_chosen(self):
        branches = conflict_branches(
            server_text='a', client_text='b', server_version=2, client_version=1
        )
        self.assertNotIn('merged', branches)
        self.assertNotIn('winner', branches)
        self.assertNotIn('resolved', branches)

    def test_identical_text_from_two_attempts_is_still_two_branches(self):
        # "Two distinct attempts must not be deduplicated merely because their
        # text is equal." Equal prose is not the same operation.
        branches = conflict_branches(
            server_text='same', client_text='same', server_version=3, client_version=2
        )
        self.assertEqual(branches['server']['version'], 3)
        self.assertEqual(branches['client']['version'], 2)


class SnapshotPaging(unittest.TestCase):
    def setUp(self):
        self.scope = Scope('acct-1', 'inc-1', 'en')
        self.cursor = Cursor(self.scope, 'filter-a', 'snap-1', 42)

    def test_a_page_from_the_same_snapshot_and_filter_is_served(self):
        self.assertEqual(
            page_decision(self.cursor, self.scope, 'filter-a', 'snap-1', watermark=42),
            'serve',
        )

    def test_another_accounts_cursor_is_denied_not_restarted(self):
        other = Scope('acct-2', 'inc-1', 'en')
        self.assertEqual(
            page_decision(self.cursor, other, 'filter-a', 'snap-1', watermark=42),
            'scope_denied',
        )

    def test_a_cursor_from_the_previous_incarnation_is_denied(self):
        recreated = Scope('acct-1', 'inc-2', 'en')
        self.assertEqual(
            page_decision(self.cursor, recreated, 'filter-a', 'snap-1', watermark=42),
            'scope_denied',
        )

    def test_an_expired_snapshot_restarts_acquisition_rather_than_reading_live(self):
        # "Paginated snapshot pages use a stable snapshot token until
        # completion; do not read later pages from different live snapshots."
        self.assertEqual(
            page_decision(self.cursor, self.scope, 'filter-a', 'snap-2', watermark=42),
            'restart',
        )

    def test_a_changed_filter_restarts_rather_than_skipping_rows(self):
        self.assertEqual(
            page_decision(self.cursor, self.scope, 'filter-b', 'snap-1', watermark=42),
            'restart',
        )

    def test_a_watermark_that_moved_backwards_restarts(self):
        # A watermark below the cursor's means this is not the same consistent
        # read, so continuing from it could miss a committed change.
        self.assertEqual(
            page_decision(self.cursor, self.scope, 'filter-a', 'snap-1', watermark=41),
            'restart',
        )


class AccountStreamOrdering(unittest.TestCase):
    def test_a_contiguous_run_of_sequences_is_contiguous(self):
        self.assertTrue(sequence_is_contiguous([7, 8, 9], after=6))

    def test_a_gap_means_a_writer_committed_ahead_of_a_held_lock(self):
        # The stream head is allocated under a row lock held until commit, so
        # a visible gap is the thing that must not happen.
        self.assertFalse(sequence_is_contiguous([7, 9], after=6))

    def test_a_repeat_is_not_contiguous(self):
        self.assertFalse(sequence_is_contiguous([7, 7, 8], after=6))

    def test_going_backwards_is_not_contiguous(self):
        self.assertFalse(sequence_is_contiguous([7, 8], after=8))

    def test_an_empty_page_is_trivially_contiguous(self):
        self.assertTrue(sequence_is_contiguous([], after=6))


if __name__ == '__main__':
    unittest.main(verbosity=2)
