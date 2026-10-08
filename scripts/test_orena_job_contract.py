"""I5 provider/content job decisions. Pure; no database, provider or clock.

Counterexamples for ORENA_CONTENT_EXECUTION_ARCHITECTURE sections 3 and 4:
lease acquisition and loss, duplicate execution, cancellation races, a source
revision that changes mid-job, retry classification, provider outcome mapping,
unknown outcome, unknown cost, reconciliation, worker crash recovery and a
stale worker that tries to commit after its lease was fenced.

The publication fence itself is `reference_backbone.job_may_publish` and the
reservation lifecycle is I3's, so this file also holds the two modules to each
other: nothing here claims to implement quota, entitlement or a worker.
"""
from pathlib import Path
import inspect
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from writing_coach import job_contract  # noqa: E402
from writing_coach.job_contract import (  # noqa: E402
    FAILURE_CLASSES,
    JOB_STATES,
    PROVIDER_OUTCOMES,
    RECONCILE_FAILURE_CLASSES,
    RETRYABLE_FAILURE_CLASSES,
    TERMINAL_JOB_STATES,
    Lease,
    cancellation_decision,
    job_commit_decision,
    job_transition,
    lease_acquire_decision,
    lease_renew_decision,
    provider_outcome_state,
    reconciliation_decision,
    recovery_decision,
    reservation_outcome_decision,
    result_delivery_decision,
    retry_decision,
    source_revision_decision,
)
from writing_coach.reference_backbone import (  # noqa: E402
    Scope,
    job_may_publish,
    release_decision,
    settle_decision,
)


class StateMachine(unittest.TestCase):
    def test_the_eight_states_and_four_terminal_ones_are_the_contract(self):
        self.assertEqual(
            JOB_STATES,
            ('queued', 'running', 'waiting_retry', 'outcome_unknown',
             'succeeded', 'failed', 'cancelled', 'rejected'),
        )
        self.assertEqual(TERMINAL_JOB_STATES, ('succeeded', 'failed', 'cancelled', 'rejected'))

    def test_the_tables_allowed_transitions_commit(self):
        allowed = [
            ('queued', 'running'), ('queued', 'cancelled'), ('queued', 'rejected'),
            ('running', 'succeeded'), ('running', 'failed'), ('running', 'waiting_retry'),
            ('running', 'outcome_unknown'), ('running', 'cancelled'),
            ('waiting_retry', 'running'), ('waiting_retry', 'cancelled'), ('waiting_retry', 'rejected'),
            ('outcome_unknown', 'succeeded'), ('outcome_unknown', 'failed'),
            ('outcome_unknown', 'cancelled'),
        ]
        for current, requested in allowed:
            self.assertEqual(job_transition(current, requested), 'commit', f'{current}->{requested}')

    def test_an_unresolved_outcome_is_never_sent_back_to_running(self):
        # Section 3: outcome_unknown resolves; it does not re-dispatch, and a
        # new attempt would be a new operation ID.
        for requested in ('running', 'waiting_retry', 'queued'):
            self.assertEqual(job_transition('outcome_unknown', requested), 'refused')

    def test_no_terminal_state_has_an_exit(self):
        for state in TERMINAL_JOB_STATES:
            for requested in JOB_STATES:
                expected = 'noop' if requested == state else 'refused'
                self.assertEqual(job_transition(state, requested), expected)

    def test_skipped_and_backward_transitions_are_refused(self):
        for current, requested in [('queued', 'succeeded'), ('queued', 'waiting_retry'),
                                   ('waiting_retry', 'succeeded'), ('running', 'queued')]:
            self.assertEqual(job_transition(current, requested), 'refused')

    def test_an_unregistered_state_is_refused_rather_than_guessed(self):
        self.assertEqual(job_transition('running', 'archived'), 'refused')
        self.assertEqual(job_transition('archived', 'running'), 'refused')
        self.assertEqual(job_transition('', ''), 'refused')


class LeaseAcquisition(unittest.TestCase):
    def test_a_queued_job_is_acquirable(self):
        self.assertEqual(lease_acquire_decision(state='queued', requester='w1'), 'acquire')
        self.assertEqual(
            lease_acquire_decision(state='queued', requester='w1', current_lease=Lease(1, 'w0', True)),
            'acquire',
        )

    def test_the_same_holder_asking_twice_does_not_run_the_work_twice(self):
        live = Lease(2, 'w1', False)
        self.assertEqual(lease_acquire_decision(state='queued', requester='w1', current_lease=live),
                         'already_held')
        self.assertEqual(lease_acquire_decision(state='running', requester='w1', current_lease=live),
                         'already_held')

    def test_another_live_holder_makes_the_lease_busy_rather_than_shared(self):
        live = Lease(2, 'w1', False)
        self.assertEqual(lease_acquire_decision(state='queued', requester='w2', current_lease=live), 'busy')
        self.assertEqual(lease_acquire_decision(state='running', requester='w2', current_lease=live), 'busy')

    def test_an_expired_lease_on_a_running_job_is_recovery_not_a_plain_acquire(self):
        # The call may already be at the provider, so this must not look like a
        # fresh queued job.
        self.assertEqual(
            lease_acquire_decision(state='running', requester='w2', current_lease=Lease(2, 'w1', True)),
            'recover',
        )
        self.assertEqual(lease_acquire_decision(state='running', requester='w2', current_lease=None), 'recover')

    def test_an_unresolved_job_is_reconciled_rather_than_re_run(self):
        self.assertEqual(lease_acquire_decision(state='outcome_unknown', requester='w2'),
                         'reconcile_required')

    def test_a_retry_waits_for_its_backoff(self):
        self.assertEqual(lease_acquire_decision(state='waiting_retry', requester='w1', retry_due=False),
                         'not_due')
        self.assertEqual(lease_acquire_decision(state='waiting_retry', requester='w1', retry_due=True),
                         'acquire')

    def test_terminal_and_deleted_accounts_are_refused(self):
        for state in TERMINAL_JOB_STATES:
            self.assertEqual(lease_acquire_decision(state=state, requester='w1'), 'terminal')
        self.assertEqual(
            lease_acquire_decision(state='queued', requester='w1', account_active=False),
            'account_inactive',
        )
        self.assertEqual(lease_acquire_decision(state='archived', requester='w1'), 'refused')

    def test_a_lease_needs_a_positive_generation_and_a_real_holder(self):
        for generation in (0, -1, True, 1.5, '2'):
            with self.assertRaises(ValueError):
                Lease(generation, 'w1', False)
        for holder in ('', '   ', None, 7):
            with self.assertRaises(ValueError):
                Lease(1, holder, False)
        with self.assertRaises(ValueError):
            Lease(1, 'w1', 'yes')
        for requester in ('', '   ', None):
            with self.assertRaises(ValueError):
                lease_acquire_decision(state='queued', requester=requester)


class LeaseRenewalAndExpiry(unittest.TestCase):
    def test_a_live_lease_of_the_workers_own_generation_renews(self):
        self.assertEqual(
            lease_renew_decision(requester='w1', held_generation=3, current_lease=Lease(3, 'w1', False),
                                 state='running', cancelled=False),
            'renew',
        )

    def test_a_fenced_generation_is_lost_even_before_it_expires(self):
        # Another worker took generation 4 while this one still believes it has 3.
        self.assertEqual(
            lease_renew_decision(requester='w1', held_generation=3, current_lease=Lease(4, 'w2', False),
                                 state='running', cancelled=False),
            'lease_lost',
        )

    def test_the_same_generation_under_another_holder_is_also_lost(self):
        self.assertEqual(
            lease_renew_decision(requester='w1', held_generation=3, current_lease=Lease(3, 'w2', False),
                                 state='running', cancelled=False),
            'lease_lost',
        )

    def test_no_lease_at_all_is_lost_rather_than_silently_renewed(self):
        self.assertEqual(
            lease_renew_decision(requester='w1', held_generation=3, current_lease=None,
                                 state='running', cancelled=False),
            'lease_lost',
        )

    def test_the_workers_own_expired_generation_reports_expiry(self):
        self.assertEqual(
            lease_renew_decision(requester='w1', held_generation=3, current_lease=Lease(3, 'w1', True),
                                 state='running', cancelled=False),
            'lease_expired',
        )

    def test_cancellation_and_a_deleted_account_stop_the_renewal(self):
        lease = Lease(3, 'w1', False)
        self.assertEqual(
            lease_renew_decision(requester='w1', held_generation=3, current_lease=lease,
                                 state='running', cancelled=True),
            'cancelled',
        )
        self.assertEqual(
            lease_renew_decision(requester='w1', held_generation=3, current_lease=lease,
                                 state='running', cancelled=False, account_active=False),
            'account_inactive',
        )

    def test_a_job_that_left_the_leased_states_says_so_rather_than_renewing(self):
        for state in ('succeeded', 'failed', 'cancelled', 'outcome_unknown', 'waiting_retry'):
            self.assertEqual(
                lease_renew_decision(requester='w1', held_generation=3, current_lease=Lease(3, 'w1', False),
                                     state=state, cancelled=False),
                'not_running',
            )
        with self.assertRaises(ValueError):
            lease_renew_decision(requester='w1', held_generation=0, current_lease=None,
                                 state='running', cancelled=False)


class SourceRevision(unittest.TestCase):
    def test_two_present_equal_revisions_are_current(self):
        self.assertEqual(source_revision_decision('rev-7', 'rev-7'), 'current')

    def test_a_changed_revision_invalidates_the_result(self):
        self.assertEqual(source_revision_decision('rev-7', 'rev-8'), 'changed')

    def test_a_missing_revision_is_unknown_never_a_fabricated_constant(self):
        for captured, current in [('', 'rev-8'), ('rev-7', ''), (None, 'rev-8'), ('rev-7', None),
                                  ('   ', 'rev-8'), (7, 7)]:
            self.assertEqual(source_revision_decision(captured, current), 'unknown')


class PublicationFence(unittest.TestCase):
    def setUp(self):
        self.en = Scope('owner-a', 'incarnation-1', 'en')
        self.zh = Scope('owner-a', 'incarnation-1', 'zh')

    def commit(self, **overrides):
        values = dict(job_scope=self.en, current_scope=self.en, state='running', lease_generation=3,
                      current_lease=3, account_active=True, captured_source_revision='rev-1',
                      current_source_revision='rev-1', cancelled=False)
        values.update(overrides)
        return job_commit_decision(**values)

    def test_a_current_worker_on_the_current_source_publishes(self):
        self.assertEqual(self.commit(), 'publish')

    def test_a_stale_worker_after_lease_loss_is_refused_as_lease_lost(self):
        self.assertEqual(self.commit(lease_generation=2, current_lease=3), 'lease_lost')
        # Someone else holds the job now; the old worker is fenced exactly as
        # the shared fence says, and is told why.
        self.assertFalse(job_may_publish(self.en, self.en, 'running', 2, 3, True))

    def test_every_fence_condition_has_its_own_named_refusal(self):
        self.assertEqual(self.commit(current_scope=self.zh), 'foreign_scope')
        self.assertEqual(self.commit(account_active=False), 'account_inactive')
        self.assertEqual(self.commit(state='cancelled'), 'not_running')
        self.assertEqual(self.commit(current_lease=None), 'lease_lost')

    def test_the_cancellation_fence_suppresses_even_a_real_result(self):
        self.assertEqual(self.commit(cancelled=True), 'cancelled')
        # The reference decision does not know about cancellation, so this is
        # the condition this contract adds to it.
        self.assertTrue(job_may_publish(self.en, self.en, 'running', 3, 3, True))

    def test_a_source_revision_that_moved_under_the_job_cannot_publish(self):
        self.assertEqual(self.commit(current_source_revision='rev-2'), 'source_revision_changed')
        self.assertEqual(self.commit(current_source_revision=''), 'source_revision_unknown')
        self.assertEqual(self.commit(captured_source_revision=None), 'source_revision_unknown')

    def test_lease_loss_is_reported_before_cancellation(self):
        # The stale worker is told what actually fenced it, not a reason that
        # depends on what happened to the job afterwards.
        self.assertEqual(self.commit(lease_generation=2, current_lease=3, cancelled=True), 'lease_lost')
        self.assertEqual(self.commit(lease_generation=2, current_lease=3, current_source_revision='rev-2'),
                         'lease_lost')

    def test_publish_is_impossible_whenever_the_shared_fence_says_no(self):
        for job_scope in (self.en, self.zh):
            for current_scope in (self.en, self.zh):
                for state in JOB_STATES:
                    for lease_generation, current_lease in ((3, 3), (2, 3), (3, None)):
                        for account_active in (True, False):
                            for cancelled in (True, False):
                                for captured, current in (('rev-1', 'rev-1'), ('rev-1', 'rev-2'),
                                                          ('', 'rev-1'), ('rev-1', None)):
                                    decision = self.commit(
                                        job_scope=job_scope, current_scope=current_scope, state=state,
                                        lease_generation=lease_generation, current_lease=current_lease,
                                        account_active=account_active, cancelled=cancelled,
                                        captured_source_revision=captured, current_source_revision=current,
                                    )
                                    fenced = job_may_publish(job_scope, current_scope, state,
                                                             lease_generation, current_lease, account_active)
                                    if decision == 'publish':
                                        self.assertTrue(fenced)
                                        self.assertFalse(cancelled)
                                        self.assertEqual(captured, current)
                                        self.assertTrue(captured)
                                    elif fenced and not cancelled and captured and captured == current:
                                        self.fail('the only way past the fence must publish')


class CrashRecovery(unittest.TestCase):
    def test_nothing_handed_to_a_provider_may_simply_run_again(self):
        self.assertEqual(recovery_decision(state='running', dispatched=False, provider_handle_known=False,
                                           provider_queryable=False), 'requeue')

    def test_a_queryable_handle_is_asked_rather_than_repeated(self):
        self.assertEqual(recovery_decision(state='running', dispatched=True, provider_handle_known=True,
                                           provider_queryable=True), 'reconcile')
        self.assertEqual(recovery_decision(state='outcome_unknown', dispatched=True,
                                           provider_handle_known=True, provider_queryable=True),
                         'reconcile')

    def test_unverifiable_acceptance_makes_the_outcome_unknown(self):
        for handle_known, queryable in [(True, False), (False, True), (False, False)]:
            self.assertEqual(recovery_decision(state='running', dispatched=True,
                                               provider_handle_known=handle_known,
                                               provider_queryable=queryable),
                             'outcome_unknown')

    def test_a_state_a_crash_did_not_leave_behind_is_not_recoverable(self):
        for state in ('queued', 'waiting_retry', 'succeeded', 'cancelled', 'archived'):
            self.assertEqual(recovery_decision(state=state, dispatched=True, provider_handle_known=True,
                                               provider_queryable=True), 'not_recoverable')


class ProviderOutcomeMapping(unittest.TestCase):
    def test_a_registered_provider_answer_maps_to_its_state(self):
        self.assertEqual(PROVIDER_OUTCOMES, ('succeeded', 'failed', 'rejected'))
        self.assertEqual(provider_outcome_state('succeeded'), 'succeeded')
        self.assertEqual(provider_outcome_state('failed'), 'failed')
        # A provider refusing a request it already accepted produced no result:
        # that is a failed operation, not the pre-lease admission refusal the
        # job state `rejected` means (section 3 reaches it only from queued and
        # waiting_retry, and never from outcome_unknown).
        self.assertEqual(provider_outcome_state('rejected'), 'failed')
        self.assertEqual(job_transition('outcome_unknown', 'rejected'), 'refused')
        self.assertEqual(job_transition('queued', 'rejected'), 'commit')

    def test_an_unrecognised_provider_answer_never_becomes_success(self):
        for outcome in ('ok', 'SUCCEEDED', 'complete', '', None, 200, True, ['succeeded']):
            self.assertEqual(provider_outcome_state(outcome), 'outcome_unknown')


class EventualReconciliation(unittest.TestCase):
    def test_a_verifiable_provider_answer_resolves(self):
        for outcome in PROVIDER_OUTCOMES:
            self.assertEqual(reconciliation_decision(state='outcome_unknown', provider_outcome=outcome,
                                                     handle_verified=True),
                             'resolve')

    def test_a_verified_absence_is_a_resolution_not_a_resubmission(self):
        self.assertEqual(reconciliation_decision(state='outcome_unknown', provider_outcome='absent',
                                                 handle_verified=True), 'not_started')
        # The same answer without a verified handle proves nothing.
        self.assertEqual(reconciliation_decision(state='outcome_unknown', provider_outcome='absent',
                                                 handle_verified=False), 'unknown')

    def test_an_uninterpretable_answer_leaves_the_job_unresolved(self):
        for outcome in ('ok', None, '', 7):
            self.assertEqual(reconciliation_decision(state='outcome_unknown', provider_outcome=outcome,
                                                     handle_verified=True),
                             'unknown')

    def test_reconciliation_does_not_apply_to_a_job_with_nothing_unresolved(self):
        for state in ('queued', 'waiting_retry', 'succeeded', 'failed', 'cancelled', 'rejected'):
            self.assertEqual(reconciliation_decision(state=state, provider_outcome='succeeded',
                                                     handle_verified=True),
                             'not_applicable')

    def test_a_resolved_outcome_reaches_a_state_the_machine_accepts(self):
        # resolve -> provider_outcome_state -> job_transition is the whole path,
        # and it never passes back through running.
        for outcome in PROVIDER_OUTCOMES:
            self.assertEqual(job_transition('outcome_unknown', provider_outcome_state(outcome)), 'commit')
            self.assertNotEqual(provider_outcome_state(outcome), 'running')
        self.assertEqual(job_transition('outcome_unknown', 'cancelled'), 'commit')


class RetryClassification(unittest.TestCase):
    def retry(self, **overrides):
        values = dict(failure_class='transient', attempts=1, max_attempts=3,
                      deadline_remaining=True, budget_remaining=True)
        values.update(overrides)
        return retry_decision(**values)

    def test_only_registered_retryable_classes_are_retryable(self):
        for failure_class in RETRYABLE_FAILURE_CLASSES:
            self.assertEqual(self.retry(failure_class=failure_class), 'retry')
        non_retryable = [item for item in FAILURE_CLASSES
                         if item not in RETRYABLE_FAILURE_CLASSES + RECONCILE_FAILURE_CLASSES]
        for failure_class in non_retryable:
            self.assertEqual(self.retry(failure_class=failure_class), 'permanent_failure')

    def test_a_timeout_after_dispatch_reconciles_instead_of_repeating_the_call(self):
        self.assertEqual(self.retry(failure_class='timeout_after_dispatch'), 'reconcile')

    def test_an_unregistered_class_is_never_a_silent_retry(self):
        for failure_class in ('exploded', 'Transient', '', None, 500):
            self.assertEqual(self.retry(failure_class=failure_class), 'permanent_failure')

    def test_attempts_deadline_and_budget_all_bound_a_retry(self):
        self.assertEqual(self.retry(attempts=2, max_attempts=3), 'retry')
        self.assertEqual(self.retry(attempts=3, max_attempts=3), 'permanent_failure')
        self.assertEqual(self.retry(attempts=4, max_attempts=3), 'permanent_failure')
        self.assertEqual(self.retry(deadline_remaining=False), 'permanent_failure')
        self.assertEqual(self.retry(budget_remaining=False), 'permanent_failure')

    def test_attempt_counters_must_be_real_attempts(self):
        for attempts in (0, -1, True, 1.5, '1'):
            with self.assertRaises(ValueError):
                self.retry(attempts=attempts)
        for max_attempts in (0, -1, True, 2.5, None):
            with self.assertRaises(ValueError):
                self.retry(max_attempts=max_attempts)


class CancellationRaces(unittest.TestCase):
    def test_cancelling_before_dispatch_ends_the_job_and_releases(self):
        for state in ('queued', 'waiting_retry', 'running'):
            self.assertEqual(cancellation_decision(state=state, dispatched=False), 'cancel_released')

    def test_cancelling_after_dispatch_retains_the_reservation(self):
        self.assertEqual(cancellation_decision(state='running', dispatched=True), 'cancel_retained')
        self.assertEqual(reservation_outcome_decision(dispatched=True, actual_units_known=False),
                         'retain_unknown_cost')

    def test_cancelling_an_unresolved_job_reconciles_first(self):
        for dispatched in (True, False):
            self.assertEqual(cancellation_decision(state='outcome_unknown', dispatched=dispatched),
                             'reconcile_before_terminal')

    def test_repeated_cancellation_and_terminal_jobs_are_idempotent(self):
        self.assertEqual(cancellation_decision(state='cancelled', dispatched=True), 'already_cancelled')
        for state in ('succeeded', 'failed', 'rejected'):
            self.assertEqual(cancellation_decision(state=state, dispatched=True), 'already_terminal')
        self.assertEqual(cancellation_decision(state='archived', dispatched=False), 'refused')

    def test_a_cancelled_job_still_cannot_publish_a_late_result(self):
        scope = Scope('owner-a', 'incarnation-1', 'en')
        race = dict(job_scope=scope, current_scope=scope, state='running', lease_generation=1,
                    current_lease=1, account_active=True, captured_source_revision='rev-1',
                    current_source_revision='rev-1')
        self.assertEqual(job_commit_decision(cancelled=True, **race), 'cancelled')
        # Cancelled is terminal, so a late completion that arrives after the
        # state moved also fails the state gate.
        self.assertEqual(job_commit_decision(**{**race, 'state': 'cancelled'}), 'not_running')
        # And the cancellation does not erase the bill.
        self.assertEqual(reservation_outcome_decision(dispatched=True, actual_units_known=True), 'settle')


class ReservationSeam(unittest.TestCase):
    def test_the_job_names_the_reservation_decision_rather_than_making_it(self):
        self.assertEqual(reservation_outcome_decision(dispatched=False, actual_units_known=True), 'release')
        self.assertEqual(reservation_outcome_decision(dispatched=True, actual_units_known=True), 'settle')
        self.assertEqual(reservation_outcome_decision(dispatched=True, actual_units_known=False),
                         'retain_unknown_cost')

    def test_the_named_decisions_slot_straight_into_the_commerce_ones(self):
        # I3's own decisions remain the authority; nothing here re-implements
        # them, and unknown cost is neither a release nor a zero.
        self.assertEqual(release_decision(reservation_state='reserved'), 'release')
        self.assertEqual(release_decision(reservation_state='dispatched'), 'dispatched_retained')
        self.assertEqual(settle_decision(reservation_state='dispatched', admitted_units=5, actual_units=0,
                                         prior_actual_units=None), 'settle')
        self.assertEqual(settle_decision(reservation_state='settled', admitted_units=5, actual_units=0,
                                         prior_actual_units=0, outcome_ref='job-1',
                                         prior_outcome_ref='job-1'),
                         'duplicate')

    def test_a_real_outcome_settles_usage_exactly_once(self):
        # Two workers report the same finished provider call; the fence refuses
        # the stale one, and the reservation settles once whatever happened.
        self.assertEqual(reservation_outcome_decision(dispatched=True, actual_units_known=True), 'settle')
        self.assertEqual(settle_decision(reservation_state='dispatched', admitted_units=4, actual_units=3,
                                         prior_actual_units=None, outcome_ref='job-9'),
                         'settle')
        self.assertEqual(settle_decision(reservation_state='settled', admitted_units=4, actual_units=3,
                                         prior_actual_units=3, outcome_ref='job-9', prior_outcome_ref='job-9'),
                         'duplicate')


class ResultIdempotency(unittest.TestCase):
    def test_one_result_application_is_delivered_once(self):
        self.assertEqual(result_delivery_decision(acknowledged=False, result_ref='res-1'), 'deliver')
        self.assertEqual(result_delivery_decision(acknowledged=True, result_ref='res-1',
                                                  prior_result_ref='res-1'), 'duplicate')

    def test_a_retry_cannot_revise_an_acknowledged_result(self):
        self.assertEqual(result_delivery_decision(acknowledged=True, result_ref='res-2',
                                                  prior_result_ref='res-1'), 'payload_conflict')

    def test_a_result_reference_must_actually_identify_a_result(self):
        for result_ref in ('', '   ', None, 7):
            with self.assertRaises(ValueError):
                result_delivery_decision(acknowledged=False, result_ref=result_ref)


class TheContractsStayPure(unittest.TestCase):
    """I5 is decisions only: no storage, provider, quota or second framework."""

    def source(self):
        return inspect.getsource(job_contract)

    def test_the_publication_fence_is_the_existing_reference_decision(self):
        # Reused, not restated - a second fence is the second job framework
        # this contract must not become.
        self.assertIn('job_may_publish', self.source())
        self.assertIn('from writing_coach.reference_backbone import', self.source())

    def test_no_persistence_provider_quota_or_ai_import_reaches_this_module(self):
        for forbidden in ('sqlalchemy', 'writing_coach.persistence', 'writing_coach.ai',
                          'writing_coach.product', 'writing_coach.media_providers',
                          'writing_coach.media_ingestion', 'requests', 'os.environ'):
            self.assertNotIn(forbidden, self.source())

    def test_the_module_decides_without_performing_anything(self):
        # No module-level call and no I/O: importing it cannot mutate anything.
        for forbidden in ('open(', 'print(', 'time.', 'datetime'):
            self.assertNotIn(forbidden, self.source())


if __name__ == '__main__':
    unittest.main(verbosity=2)
