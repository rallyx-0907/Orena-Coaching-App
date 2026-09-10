"""A backup must not be written somewhere that dies with its own container.

The operator command that captures a runtime backup is usually run from an
ephemeral container, because the application image does not ship
postgresql-client. That is exactly how a real pre-migration backup was lost:
it was written to `/tmp` inside a `docker run --rm`, so `pg_dump` succeeded,
`verify` succeeded, the rehearsal succeeded, and the file ceased to exist the
moment the container exited. Nothing in the sequence was wrong except where it
landed.

So the destination is checked before anything is captured, and the default is
somewhere durable. Pure; no database and no pg_dump.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.runtime_backup import (  # noqa: E402
    EPHEMERAL_ROOTS,
    default_out,
    ephemeral_reason,
)


class WhereABackupMayNotGo(unittest.TestCase):
    def test_tmp_is_refused_because_a_container_takes_it_with_it(self):
        reason = ephemeral_reason(Path('/tmp/pre-i2.dump'))
        self.assertIsNotNone(reason)
        self.assertIn('/tmp', reason)

    def test_every_listed_ephemeral_root_is_refused(self):
        for root in EPHEMERAL_ROOTS:
            self.assertIsNotNone(ephemeral_reason(Path(root) / 'x.dump'), root)

    def test_a_nested_path_under_an_ephemeral_root_is_still_ephemeral(self):
        self.assertIsNotNone(ephemeral_reason(Path('/tmp/backups/deep/x.dump')))

    def test_a_mounted_working_directory_is_accepted(self):
        self.assertIsNone(ephemeral_reason(Path('/workspace/backups/pre-i2.dump')))

    def test_a_host_path_is_accepted(self):
        self.assertIsNone(ephemeral_reason(Path('/home/operator/backups/x.dump')))

    def test_a_lookalike_directory_is_not_treated_as_tmp(self):
        # `/tmpfiles` is not `/tmp`; matching on the path prefix as a string
        # rather than on path segments would refuse this wrongly.
        self.assertIsNone(ephemeral_reason(Path('/tmpfiles/x.dump')))
        self.assertIsNone(ephemeral_reason(Path('/var/tmpdata/x.dump')))

    def test_the_reason_explains_the_trap_rather_than_just_refusing(self):
        reason = ephemeral_reason(Path('/tmp/x.dump'))
        self.assertIn('--allow-ephemeral', reason)


class TheDefaultDestination(unittest.TestCase):
    def test_it_is_durable(self):
        self.assertIsNone(ephemeral_reason(default_out()))

    def test_it_lands_in_the_repository_backups_directory(self):
        self.assertEqual(default_out().parent.name, 'backups')

    def test_it_is_named_so_two_captures_do_not_collide(self):
        # A timestamp, not a fixed name: overwriting the previous backup with
        # the current one is its own way of having no backup.
        self.assertNotEqual(default_out(at='20260908T101500Z'),
                            default_out(at='20260908T101501Z'))

    def test_it_is_a_dump_file(self):
        self.assertEqual(default_out().suffix, '.dump')


if __name__ == '__main__':
    unittest.main(verbosity=2)
