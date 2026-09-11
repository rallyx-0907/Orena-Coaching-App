"""Executable backbone counterexamples; no database/provider or runtime activation."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from writing_coach.reference_backbone import (  # noqa: E402
    Scope, Receipt, Mutation, Quota, Evidence, Cursor, ProviderEvent,
    mutation_decision, reserve_decision, result_is_current,
    job_may_publish, projection_evidence, growth_comparable, cursor_matches,
    subscription_event_decision,
)


class BackboneContracts(unittest.TestCase):
    def setUp(self):
        self.en = Scope('owner-a', 'incarnation-1', 'en')
        self.zh = Scope('owner-a', 'incarnation-1', 'zh')

    def test_lost_ack_returns_receipt_before_stale_version(self):
        for scope in (self.en, self.zh):
            command = Mutation(scope, 'draft', 'w1', 'op1', 'hash1', 4)
            receipt = Receipt(command, 'r1', 5)
            self.assertEqual(mutation_decision(command, scope, 5, receipt), 'replay')

    def test_reused_operation_with_changed_payload_is_rejected(self):
        old = Mutation(self.en, 'draft', 'w1', 'op1', 'hash1', 4)
        changed = Mutation(self.en, 'draft', 'w1', 'op1', 'hash2', 4)
        self.assertEqual(mutation_decision(changed, self.en, 5, Receipt(old, 'r1', 5)), 'operation_conflict')

    def test_two_distinct_edits_from_same_version_conflict(self):
        command = Mutation(self.en, 'draft', 'w1', 'op2', 'hash2', 4)
        self.assertEqual(mutation_decision(command, self.en, 5), 'version_conflict')

    def test_foreign_account_language_and_reincarnation_never_replay(self):
        command = Mutation(self.en, 'draft', 'w1', 'op1', 'hash1', 4)
        for scope in (self.zh, Scope('owner-b', 'incarnation-1', 'en'), Scope('owner-a', 'incarnation-2', 'en')):
            self.assertEqual(mutation_decision(command, scope, 5, Receipt(command, 'r1', 5)), 'scope_denied')

    def test_deletion_blocks_old_pending_write(self):
        command = Mutation(self.en, 'draft', 'w1', 'op1', 'hash1', 4)
        self.assertEqual(mutation_decision(command, self.en, 4, deleted=True), 'deleted')

    def test_receipt_for_another_command_is_not_success(self):
        command = Mutation(self.en, 'draft', 'w1', 'op1', 'hash1', 4)
        other = Mutation(self.en, 'recall', 'w1', 'op1', 'hash1', 4)
        self.assertEqual(mutation_decision(command, self.en, 4, Receipt(other, 'r1', 5)), 'operation_conflict')

    def test_quota_last_unit_cannot_be_reserved_twice(self):
        self.assertEqual(reserve_decision(Quota(10, 9, 0), 1), 'admit')
        # The repository must pass a locked, updated bucket to the second call.
        self.assertEqual(reserve_decision(Quota(10, 9, 1), 1), 'exhausted')

    def test_unknown_usage_does_not_become_zero(self):
        self.assertEqual(reserve_decision(Quota(10, None, 0), 1), 'unknown')
        self.assertEqual(reserve_decision(Quota(None, 0, 0), 1, entitlement='unknown'), 'unknown')
        self.assertEqual(reserve_decision(Quota(None, 0, 0), 1, entitlement='denied'), 'denied')

    def test_quota_unlimited_and_invalid_units_are_distinct(self):
        self.assertEqual(reserve_decision(Quota(None, 50, 5), 3), 'admit')
        for units in (-1, 0, True, 1.5):
            with self.assertRaises(ValueError):
                reserve_decision(Quota(10, 0, 0), units)

    def test_stale_response_cannot_attach_to_new_context(self):
        captured = ('session1', 'media', 'source1', 'revision1', 'work1', 'version4', 'focus1', 'request1')
        self.assertTrue(result_is_current(self.en, self.en, captured, captured))
        for index in range(len(captured)):
            changed = list(captured)
            changed[index] = 'new'
            self.assertFalse(result_is_current(self.en, self.en, captured, tuple(changed)))
        self.assertFalse(result_is_current(self.en, self.zh, captured, captured))

    def test_expired_worker_cancel_and_deleted_account_cannot_publish(self):
        self.assertTrue(job_may_publish(self.en, self.en, 'running', 2, 2, True))
        for state, token, active in [('cancelled', 2, True), ('running', 1, True), ('running', 2, False), ('outcome_unknown', 2, True)]:
            self.assertFalse(job_may_publish(self.en, self.en, state, token, 2, active))

    def test_projection_rejects_pending_deleted_and_foreign_evidence(self):
        rows = [Evidence(self.en, 'writing', 'e1', 1, True),
                Evidence(self.en, 'writing', 'e2', 1, False),
                Evidence(self.en, 'writing', 'e3', 1, True, invalidated=True),
                Evidence(self.zh, 'writing', 'e4', 1, True)]
        self.assertEqual([r.id for r in projection_evidence(self.en, rows)], ['e1'])

    def test_out_of_order_evidence_cannot_resurrect_invalidated_version(self):
        rows = [Evidence(self.en, 'recall', 'e1', 2, True, invalidated=True),
                Evidence(self.en, 'recall', 'e1', 1, True)]
        self.assertEqual(projection_evidence(self.en, rows), ())

    def test_same_numeric_id_in_two_domains_is_not_deduplicated(self):
        rows = [Evidence(self.en, 'writing', '1', 1, True), Evidence(self.en, 'reading', '1', 1, True)]
        self.assertEqual(len(projection_evidence(self.en, rows)), 2)

    def test_growth_cannot_compare_assisted_or_incompatible_metrics(self):
        base = ('dictation', 'v1', 'unaided', 'task-family1')
        self.assertTrue(growth_comparable(self.en, self.en, base, base))
        for changed in [('pronunciation', 'v1', 'unaided', 'task-family1'), ('dictation', 'v2', 'unaided', 'task-family1'), ('dictation', 'v1', 'revealed', 'task-family1')]:
            self.assertFalse(growth_comparable(self.en, self.en, base, changed))
        self.assertFalse(growth_comparable(self.en, self.zh, base, base))

    def test_cursor_is_bound_to_scope_filter_and_snapshot(self):
        cursor = Cursor(self.en, 'filter1', 'snapshot1', 10)
        self.assertTrue(cursor_matches(cursor, self.en, 'filter1', 'snapshot1'))
        self.assertFalse(cursor_matches(cursor, self.zh, 'filter1', 'snapshot1'))
        self.assertFalse(cursor_matches(cursor, self.en, 'filter2', 'snapshot1'))
        self.assertFalse(cursor_matches(cursor, self.en, 'filter1', 'snapshot2'))

    def test_inconsistent_same_version_evidence_fails_closed(self):
        rows = [Evidence(self.en, 'recall', 'e1', 1, True),
                Evidence(self.en, 'recall', 'e1', 1, True, invalidated=True)]
        with self.assertRaises(ValueError):
            projection_evidence(self.en, rows)

    def test_missing_comparison_metadata_cannot_be_growth(self):
        self.assertFalse(growth_comparable(self.en, self.en, ('writing', '', 'unaided', 'task'), ('writing', '', 'unaided', 'task')))

    def test_deleted_incarnation_rejects_the_callback_outright(self):
        event = ProviderEvent('evt-1', 'incarnation-1', 3)
        self.assertEqual(
            subscription_event_decision(
                event, current_incarnation='incarnation-1', incarnation_deleted=True,
                already_processed=False, current_object_version=1,
            ),
            'deleted_incarnation_rejected',
        )

    def test_reincarnated_account_rejects_the_old_incarnations_callback(self):
        # Delete and re-register same external identity: the new incarnation
        # rejects the old one's command/cursor/job/callback.
        event = ProviderEvent('evt-1', 'incarnation-old', 3)
        self.assertEqual(
            subscription_event_decision(
                event, current_incarnation='incarnation-new', incarnation_deleted=False,
                already_processed=False, current_object_version=1,
            ),
            'foreign_incarnation',
        )

    def test_duplicate_event_id_never_repeats_a_grant(self):
        event = ProviderEvent('evt-1', 'incarnation-1', 3)
        self.assertEqual(
            subscription_event_decision(
                event, current_incarnation='incarnation-1', incarnation_deleted=False,
                already_processed=True, current_object_version=1,
            ),
            'duplicate',
        )

    def test_reversed_out_of_order_event_is_stale_not_applied(self):
        event = ProviderEvent('evt-2', 'incarnation-1', 1)
        self.assertEqual(
            subscription_event_decision(
                event, current_incarnation='incarnation-1', incarnation_deleted=False,
                already_processed=False, current_object_version=3,
            ),
            'stale',
        )
        # Equal, not just lower, is also not newer.
        self.assertEqual(
            subscription_event_decision(
                event, current_incarnation='incarnation-1', incarnation_deleted=False,
                already_processed=False, current_object_version=1,
            ),
            'stale',
        )

    def test_unverifiable_event_is_unknown_regardless_of_current_state(self):
        event = ProviderEvent('evt-3', 'incarnation-1', None)
        for current_object_version in (1, None):
            self.assertEqual(
                subscription_event_decision(
                    event, current_incarnation='incarnation-1', incarnation_deleted=False,
                    already_processed=False, current_object_version=current_object_version,
                ),
                'unknown',
            )

    def test_first_ever_verified_event_applies_with_nothing_to_be_stale_against(self):
        # No subscription has ever been recorded for this incarnation -
        # current_object_version=None here means "nothing yet", not "unknown".
        # A never-recorded incarnation is not the same fact as one whose
        # last-known version could not be read.
        event = ProviderEvent('evt-4', 'incarnation-1', 5)
        self.assertEqual(
            subscription_event_decision(
                event, current_incarnation='incarnation-1', incarnation_deleted=False,
                already_processed=False, current_object_version=None,
            ),
            'apply',
        )

    def test_newer_verified_event_on_the_current_incarnation_applies(self):
        event = ProviderEvent('evt-5', 'incarnation-1', 4)
        self.assertEqual(
            subscription_event_decision(
                event, current_incarnation='incarnation-1', incarnation_deleted=False,
                already_processed=False, current_object_version=1,
            ),
            'apply',
        )

    def test_deletion_is_checked_before_incarnation_identity(self):
        # A deleted incarnation is rejected outright, even if it happens to
        # equal the (stale) "current" pointer a caller passed in.
        event = ProviderEvent('evt-6', 'incarnation-1', 9)
        self.assertEqual(
            subscription_event_decision(
                event, current_incarnation='incarnation-1', incarnation_deleted=True,
                already_processed=False, current_object_version=1,
            ),
            'deleted_incarnation_rejected',
        )


if __name__ == '__main__':
    unittest.main()
