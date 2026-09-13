"""Startup verifies the schema; it does not create it.

Migration order item 1 of ORENA_BACKBONE_INTEGRATION_GATES, and the standing
persistence invariant that there is no automatic startup Alembic. An empty
database used to be silently migrated to head by the first process that
connected - so a pointed-at-the-wrong-database deployment built itself a
schema instead of refusing, and the operator never chose a moment.

Four states, four answers, and only one of them starts.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from writing_coach.runtime_schema import (  # noqa: E402
    BOOTSTRAP_COMMAND,
    SchemaNotReady,
    describe_readiness,
    readiness,
)


class FourDatabaseStates(unittest.TestCase):
    def test_a_database_at_the_expected_revision_is_ready(self):
        self.assertEqual(readiness(actual='abc123', tables={'users'}, expected='abc123'), 'ready')

    def test_an_empty_database_is_empty_rather_than_a_mismatch(self):
        # No revision and no tables is the state that used to be migrated
        # automatically. It is a distinct answer because the operator needs to
        # know that creating the schema is what is being asked for.
        self.assertEqual(readiness(actual=None, tables=set(), expected='abc123'), 'empty')

    def test_a_database_at_the_wrong_revision_is_a_mismatch(self):
        self.assertEqual(readiness(actual='old999', tables={'users'}, expected='abc123'), 'mismatch')

    def test_tables_without_a_revision_is_a_mismatch_not_an_empty_database(self):
        # Someone else's schema, or a half-applied one. Creating tables on top
        # of it is the worst available move.
        self.assertEqual(readiness(actual=None, tables={'users'}, expected='abc123'), 'mismatch')

    def test_an_unreachable_database_is_its_own_answer(self):
        self.assertEqual(readiness(actual=None, tables=None, expected='abc123'), 'unavailable')


class RefusalsAreActionable(unittest.TestCase):
    def test_the_empty_refusal_names_the_operator_command(self):
        message = describe_readiness('empty', expected='abc123', actual=None)
        self.assertIn(BOOTSTRAP_COMMAND, message)

    def test_the_mismatch_refusal_reports_both_revisions(self):
        message = describe_readiness('mismatch', expected='abc123', actual='old999')
        self.assertIn('abc123', message)
        self.assertIn('old999', message)

    def test_the_mismatch_refusal_does_not_suggest_creating_a_schema(self):
        # A database that already has something in it is not bootstrapped.
        message = describe_readiness('mismatch', expected='abc123', actual='old999')
        self.assertNotIn(BOOTSTRAP_COMMAND, message)

    def test_an_unavailable_database_is_not_reported_as_a_schema_problem(self):
        message = describe_readiness('unavailable', expected='abc123', actual=None)
        self.assertNotIn(BOOTSTRAP_COMMAND, message)
        self.assertIn('unavailable', message.casefold())

    def test_a_ready_database_has_nothing_to_say(self):
        self.assertEqual(describe_readiness('ready', expected='abc123', actual='abc123'), '')


class StartupNeverMigrates(unittest.TestCase):
    def test_every_state_but_ready_raises_rather_than_creating_a_schema(self):
        for state in ('empty', 'mismatch', 'unavailable'):
            with self.assertRaises(SchemaNotReady) as caught:
                SchemaNotReady.raise_for(state, expected='abc123', actual=None)
            self.assertEqual(caught.exception.state, state)

    def test_the_runtime_module_no_longer_upgrades_on_its_own(self):
        source = Path(__file__).resolve().parents[1] / 'writing_coach' / 'persistence' / 'runtime.py'
        text = source.read_text(encoding='utf-8')
        self.assertNotIn(
            'command.upgrade',
            text,
            'startup must verify the schema, never apply migrations',
        )

    def test_the_operator_command_exists_and_is_the_one_named(self):
        script = Path(__file__).resolve().parents[1] / 'scripts' / 'bootstrap_runtime_schema.py'
        self.assertTrue(script.exists(), 'the operator bootstrap command is missing')
        self.assertIn(script.name, BOOTSTRAP_COMMAND)


class TheOperatorCommandIsTwoDifferentRisks(unittest.TestCase):
    """Creating a schema and migrating a database with work in it differ.

    The command is driven through its own `main` with the runtime inspection
    stubbed, so these are the real argument rules rather than a description of
    them.
    """

    def _run(self, argv, state, actual):
        import importlib.util

        path = Path(__file__).resolve().parent / 'bootstrap_runtime_schema.py'
        spec = importlib.util.spec_from_file_location('_bootstrap_under_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        applied = []
        original_inspect = module.inspect_runtime
        original_apply = module._apply
        module.inspect_runtime = lambda: (state, 'head-new', actual)
        module._apply = lambda label: applied.append(label) or 0
        try:
            return module.main(argv), applied
        finally:
            module.inspect_runtime = original_inspect
            module._apply = original_apply

    def test_a_ready_database_is_left_alone(self):
        code, applied = self._run([], 'ready', 'head-new')
        self.assertEqual(code, 0)
        self.assertEqual(applied, [])

    def test_an_empty_database_needs_confirm_and_then_creates(self):
        code, applied = self._run([], 'empty', None)
        self.assertEqual((code, applied), (2, []))
        code, applied = self._run(['--confirm'], 'empty', None)
        self.assertEqual((code, applied), (0, ['creation']))

    def test_a_database_with_data_is_not_created_over(self):
        # Plain --confirm is the creation path and must refuse here.
        code, applied = self._run(['--confirm'], 'mismatch', 'head-old')
        self.assertEqual(code, 1)
        self.assertEqual(applied, [], 'an existing database was migrated by the create path')

    def test_upgrading_requires_stating_the_revision_you_expect(self):
        code, applied = self._run(['--upgrade', '--confirm'], 'mismatch', 'head-old')
        self.assertEqual((code, applied), (1, []))

    def test_upgrading_stops_when_the_database_is_at_a_different_revision(self):
        # The usual cause is a connection string pointing somewhere else, which
        # is exactly the moment not to migrate.
        code, applied = self._run(
            ['--upgrade', '--from', 'head-old', '--confirm'], 'mismatch', 'someone-elses'
        )
        self.assertEqual((code, applied), (1, []))

    def test_upgrading_reports_before_it_acts(self):
        code, applied = self._run(['--upgrade', '--from', 'head-old'], 'mismatch', 'head-old')
        self.assertEqual((code, applied), (2, []), 'it migrated without --confirm')

    def test_a_confirmed_upgrade_from_the_stated_revision_applies(self):
        code, applied = self._run(
            ['--upgrade', '--from', 'head-old', '--confirm'], 'mismatch', 'head-old'
        )
        self.assertEqual((code, applied), (0, ['migration']))

    def test_upgrade_refuses_an_empty_database(self):
        code, applied = self._run(
            ['--upgrade', '--from', '', '--confirm'], 'empty', None
        )
        self.assertEqual((code, applied), (1, []))

    def test_an_unreachable_database_is_never_migrated(self):
        for argv in ([], ['--confirm'], ['--upgrade', '--from', 'x', '--confirm']):
            code, applied = self._run(argv, 'unavailable', None)
            self.assertEqual((code, applied), (1, []), argv)


if __name__ == '__main__':
    unittest.main(verbosity=2)
