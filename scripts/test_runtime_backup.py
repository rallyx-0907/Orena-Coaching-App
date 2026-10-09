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
from datetime import datetime, timedelta, UTC
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.runtime_backup import (  # noqa: E402
    EPHEMERAL_ROOTS,
    default_out,
    ephemeral_reason,
    main,
    rotate,
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


NOW = datetime(2026, 10, 9, 12, 0, 0, tzinfo=UTC)


def _dump(directory: Path, name: str, age: timedelta, content: bytes = b'PGDMP') -> Path:
    path = directory / name
    path.write_bytes(content)
    stamp = (NOW - age).timestamp()
    os.utime(path, (stamp, stamp))
    return path


class RotationKeepsTheStatedRetention(unittest.TestCase):
    """The public Privacy Policy says backups are overwritten within 30 days (D-162). Rotation is how that is true."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / 'operator' / 'backups'
        self.dir.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_boundary_is_exactly_the_retention(self):
        _dump(self.dir, 'orena-a.dump', timedelta(days=30))                       # exactly 30 days: removed
        _dump(self.dir, 'orena-b.dump', timedelta(days=30) - timedelta(seconds=1))  # a second newer: kept
        _dump(self.dir, 'orena-c.dump', timedelta(days=1))
        report = rotate(self.dir, 30, apply=True, now=NOW)
        self.assertEqual(report['removed'], ['orena-a.dump'])
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ['orena-b.dump', 'orena-c.dump'])

    def test_a_dry_run_lists_and_deletes_nothing(self):
        _dump(self.dir, 'orena-old.dump', timedelta(days=90))
        _dump(self.dir, 'orena-new.dump', timedelta(days=2))
        report = rotate(self.dir, 30, apply=False, now=NOW)
        self.assertEqual(report['removed'], ['orena-old.dump'])
        self.assertFalse(report['applied'])
        self.assertEqual(len(list(self.dir.iterdir())), 2, 'nothing was deleted')

    def test_the_older_of_mtime_and_the_name_timestamp_decides(self):
        # A copy reset the file's mtime to yesterday, but the name says it was taken 40 days ago.
        _dump(self.dir, 'orena-20260830-100000.dump', timedelta(days=1))
        _dump(self.dir, 'orena-recent.dump', timedelta(days=1))
        report = rotate(self.dir, 30, apply=True, now=NOW)
        self.assertEqual(report['removed'], ['orena-20260830-100000.dump'])

    def test_only_orena_dumps_directly_in_the_directory_are_ever_touched(self):
        ancient = timedelta(days=900)
        keepers = [
            _dump(self.dir, 'deletions.json', ancient),            # the deletion journal must outlive backups
            _dump(self.dir, 'notes.txt', ancient),
            _dump(self.dir, 'other-20200101.dump', ancient),       # not an orena-*.dump
            _dump(self.dir, 'orena-x.dump.bak', ancient),
        ]
        (self.dir / 'nested').mkdir()
        keepers.append(_dump(self.dir / 'nested', 'orena-inner.dump', ancient))   # a subfolder is not rotated
        _dump(self.dir, 'orena-recent.dump', timedelta(days=1))
        _dump(self.dir, 'orena-old.dump', ancient)
        rotate(self.dir, 30, apply=True, now=NOW)
        for path in keepers:
            self.assertTrue(path.exists(), f'{path.name} must never be touched')
        self.assertFalse((self.dir / 'orena-old.dump').exists())

    def test_a_symlink_is_never_followed_or_removed(self):
        outside = Path(self._tmp.name) / 'outside.dump'
        outside.write_bytes(b'x')
        os.utime(outside, (1, 1))
        link = self.dir / 'orena-link.dump'
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest('symlinks are not available here')
        _dump(self.dir, 'orena-recent.dump', timedelta(days=1))
        rotate(self.dir, 30, apply=True, now=NOW)
        self.assertTrue(outside.exists())
        self.assertTrue(link.is_symlink())

    def test_the_last_backup_is_kept_even_when_stale_unless_allowed(self):
        _dump(self.dir, 'orena-1.dump', timedelta(days=100))
        _dump(self.dir, 'orena-2.dump', timedelta(days=60))
        report = rotate(self.dir, 30, apply=True, now=NOW)
        self.assertEqual(report['spared_last'], 'orena-2.dump')
        self.assertEqual([p.name for p in self.dir.iterdir()], ['orena-2.dump'])
        report = rotate(self.dir, 30, apply=True, now=NOW, allow_empty=True)
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_a_directory_that_is_not_a_backup_directory_is_refused(self):
        with self.assertRaises(ValueError):
            rotate(self.dir / 'missing', 30, now=NOW)
        with self.assertRaises(ValueError):
            rotate(Path(Path.cwd().anchor), 30, now=NOW)
        with self.assertRaises(ValueError):
            rotate(Path.home(), 30, now=NOW)
        with self.assertRaises(ValueError):
            rotate(Path(__file__).resolve().parents[1], 30, now=NOW)
        with self.assertRaises(ValueError):
            rotate(self.dir, 0, now=NOW)

    def test_the_command_is_a_dry_run_unless_told_to_apply(self):
        _dump(self.dir, 'orena-old.dump', timedelta(days=500))
        _dump(self.dir, 'orena-new.dump', timedelta(days=1))
        self.assertEqual(main(['rotate', '--dir', str(self.dir)]), 0)
        self.assertEqual(len(list(self.dir.iterdir())), 2)
        self.assertEqual(main(['rotate', '--dir', str(self.dir), '--apply']), 0)
        self.assertEqual([p.name for p in self.dir.iterdir()], ['orena-new.dump'])
        self.assertEqual(main(['rotate']), 1, 'a directory must be named')
        self.assertEqual(main(['rotate', '--dir', str(self.dir), '--apply', '--dry-run']), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
