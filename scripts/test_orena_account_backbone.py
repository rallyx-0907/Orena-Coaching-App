"""The account backbone is present and switched off, and says which.

I2 wiring. The adapters exist and are not authorized to run against the runtime
database, so the product has to hold both facts at once without crashing and
without pretending work was saved.

Pure; no database. The repositories themselves are proven against real
PostgreSQL in `tests/test_orena_work_persistence_postgres.py`.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from writing_coach.account_backbone import (  # noqa: E402
    ACTIVE,
    BACKBONE_TABLES,
    DISABLED,
    FLAG,
    UNAVAILABLE,
    AccountBackbone,
    build_backbone,
    requested,
    schema_present,
    state,
)


class OffUnlessAskedFor(unittest.TestCase):
    def test_an_empty_environment_means_off(self):
        self.assertFalse(requested({}))

    def test_only_an_explicit_yes_turns_it_on(self):
        for value in ('on', 'ON', '1', 'true', 'yes', ' on '):
            self.assertTrue(requested({FLAG: value}), value)

    def test_anything_else_is_off_including_plausible_near_misses(self):
        for value in ('', 'off', '0', 'false', 'no', 'enabled', 'maybe'):
            self.assertFalse(requested({FLAG: value}), value)


class ThreeStatesNotTwo(unittest.TestCase):
    def test_switched_off_is_disabled_whatever_the_schema_says(self):
        self.assertEqual(state(present=True, asked=False), DISABLED)
        self.assertEqual(state(present=False, asked=False), DISABLED)

    def test_switched_on_with_the_schema_is_active(self):
        self.assertEqual(state(present=True, asked=True), ACTIVE)

    def test_switched_on_without_the_schema_is_unavailable_not_disabled(self):
        # A product decision and a fault are different news. Someone intended
        # this to be on and something is wrong; saying "disabled" would hide it.
        self.assertEqual(state(present=False, asked=True), UNAVAILABLE)


class SchemaPresenceIsAllEightTables(unittest.TestCase):
    def test_every_table_the_migration_creates_is_listed(self):
        self.assertEqual(len(BACKBONE_TABLES), 8)
        self.assertEqual(len(set(BACKBONE_TABLES)), 8)

    def test_all_eight_present_is_present(self):
        self.assertTrue(schema_present({*BACKBONE_TABLES, 'users', 'essays'}))

    def test_a_partial_set_is_not_present(self):
        # A half-applied migration is not something to run on.
        self.assertFalse(schema_present(set(BACKBONE_TABLES[:-1])))

    def test_no_tables_is_not_present(self):
        self.assertFalse(schema_present(set()))

    def test_an_unreadable_database_is_not_reported_as_missing_tables(self):
        self.assertFalse(schema_present(None))


class BuildingIt(unittest.TestCase):
    def test_the_default_build_is_disabled_and_holds_no_repositories(self):
        backbone = build_backbone(object(), set(BACKBONE_TABLES), env={})
        self.assertEqual(backbone.state, DISABLED)
        self.assertFalse(backbone.is_active)
        self.assertIsNone(backbone.work)
        self.assertIsNone(backbone.incarnations)
        self.assertIsNone(backbone.provenance)

    def test_asking_for_it_without_the_schema_is_unavailable_and_still_builds_nothing(self):
        backbone = build_backbone(object(), set(), env={FLAG: 'on'})
        self.assertEqual(backbone.state, UNAVAILABLE)
        self.assertIsNone(backbone.work)

    def test_the_schema_alone_does_not_switch_it_on(self):
        # A migration applied ahead of a deploy changes nothing by itself.
        self.assertEqual(
            build_backbone(object(), set(BACKBONE_TABLES), env={}).state, DISABLED
        )

    def test_requiring_an_inactive_backbone_raises_rather_than_returning_none(self):
        for backbone in (AccountBackbone(DISABLED), AccountBackbone(UNAVAILABLE)):
            with self.assertRaises(RuntimeError):
                backbone.require()

    def test_no_engine_means_nothing_is_constructed(self):
        backbone = build_backbone(None, set(BACKBONE_TABLES), env={FLAG: 'on'})
        self.assertIsNone(backbone.work)


class TheFlagIsNotWiredToAnythingYet(unittest.TestCase):
    """Wiring is prepared; activation is a separate, human-gated decision."""

    def test_no_module_switches_the_backbone_on_by_default(self):
        root = Path(__file__).resolve().parents[1]
        for path in (root / 'app.py', root / 'writing_coach' / 'persistence' / 'runtime.py'):
            if not path.exists():
                continue
            text = path.read_text(encoding='utf-8')
            self.assertNotIn(
                f"{FLAG}', 'on'", text, f'{path.name} switches the backbone on'
            )
            self.assertNotIn(
                f'{FLAG}"] = "on"', text, f'{path.name} switches the backbone on'
            )

    def test_the_proposal_is_still_outside_the_live_migration_chain(self):
        root = Path(__file__).resolve().parents[1]
        versions = {p.name for p in (root / 'migrations' / 'versions').glob('*.py')}
        self.assertNotIn('20260908_0005_account_work_backbone.py', versions)
        self.assertTrue(
            (root / 'migrations' / 'proposed'
             / '20260908_0005_account_work_backbone.py').exists()
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
