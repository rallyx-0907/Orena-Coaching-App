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


if __name__ == '__main__':
    unittest.main(verbosity=2)
