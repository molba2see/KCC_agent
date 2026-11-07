from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import time
import unittest

from expiry import Expiry, fingerprint, move_exclusive
from lifecycle_v3 import Lifecycle
from preferences import DEFAULTS, Preferences


class PreferencesTests(unittest.TestCase):
    def test_persistent_versioned_settings_and_validation(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'preferences.json'; preferences = Preferences(path)
            self.assertEqual(preferences.values['download_mode'], 'auto')
            preferences.update({'download_mode': 'review', 'installer_days': 5}, 0)
            self.assertEqual(Preferences(path).values['download_mode'], 'review')
            with self.assertRaises(ValueError): preferences.update({'download_mode': 'auto'}, 0)
            for values in [{'installer_days': True}, {'installer_days': 0}, {'folder': '/etc'}, {'volatile_mode': 'delete'}, {'installers_enabled': 'yes'}]:
                with self.assertRaises(ValueError): preferences.update(values, 1)


class ExpiryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.root = Path(self.temp.name)
        self.inbox = self.root / 'Downloads'; self.inbox.mkdir()
        self.trash = self.root / 'Trash'; self.trash.mkdir()
        self.workspace = self.root / 'workspace'; self.workspace.mkdir()
        self.options = dict(DEFAULTS)
        self.expiry = Expiry(self.root / 'expiry.json', [self.inbox], trash=self.trash,
                             policy=lambda: self.options, engine=lambda: Lifecycle(self.workspace))

    def tearDown(self): self.temp.cleanup()

    def test_installers_start_now_move_after_three_days_and_restore_without_overwrite(self):
        path = self.inbox / 'app.dmg'; path.write_text('installer')
        self.assertEqual(self.expiry.sweep(now=1000), [])
        entry = self.expiry.public()['entries'][0]
        self.assertEqual(entry['due_at'], 1000 + 3 * 86400)
        self.assertEqual(self.expiry.sweep(now=entry['due_at'] - 1), [])
        self.assertEqual(self.expiry.sweep(now=entry['due_at']), ['app.dmg'])
        self.assertFalse(path.exists())
        path.write_text('new download')
        with self.assertRaises(FileExistsError): self.expiry.restore(0)
        self.assertEqual(path.read_text(), 'new download'); path.unlink()
        self.expiry.restore(0); self.assertEqual(path.read_text(), 'installer')
        self.assertGreater(self.expiry.public()['entries'][0]['due_at'], time.time())

    def test_replacement_restarts_clock_and_trash_collision_never_overwrites(self):
        path = self.inbox / 'app.dmg'; path.write_text('old')
        self.expiry.sweep(now=0)
        path.unlink(); path.write_text('replacement')
        self.assertEqual(self.expiry.sweep(now=3 * 86400), [])
        self.assertTrue(path.exists())
        source = self.inbox / 'source.dmg'; source.write_text('source')
        target = self.trash / 'taken.dmg'; target.write_text('user file')
        with self.assertRaises(FileExistsError): move_exclusive(source, target, fingerprint(source))
        self.assertEqual(source.read_text(), 'source'); self.assertEqual(target.read_text(), 'user file')

    def test_pause_resume_and_deadline_change_apply_without_instant_purge(self):
        path = self.inbox / 'app.pkg'; path.write_text('installer')
        self.expiry.sweep(now=0); self.options['installers_enabled'] = False
        self.expiry.sweep(now=4 * 86400); self.assertTrue(path.exists())
        self.assertEqual(self.expiry.public()['entries'][0]['status'], 'paused')
        self.options['installers_enabled'] = True
        self.expiry.sweep(now=4 * 86400)
        self.assertEqual(self.expiry.public()['entries'][0]['due_at'], 7 * 86400)
        self.options['installer_days'] = 1
        self.expiry.sweep(now=5 * 86400)
        self.assertEqual(self.expiry.public()['entries'][0]['due_at'], 6 * 86400)

    def asset(self, name='임시 공지.txt', initial=True):
        path = self.workspace / name; path.write_text('temporary information')
        engine = Lifecycle(self.workspace); aid = engine.ingest(name)
        engine.data['assets'][aid]['initial_import'] = initial; engine.save()
        return aid, path

    def test_volatile_requires_approval_and_can_change_cancel_and_reschedule(self):
        aid, path = self.asset()
        self.expiry.sweep(now=1000); entry = self.expiry.public()['entries'][0]
        self.assertEqual(entry['status'], 'pending')
        self.expiry.sweep(now=1000 + 8 * 86400); self.assertTrue(path.exists())
        self.expiry.decide(entry['id'], 'confirm', due_at=1000 + 10 * 86400, now=1000 + 8 * 86400)
        self.expiry.sweep(now=1000 + 9 * 86400); self.assertTrue(path.exists())
        self.expiry.decide(entry['id'], 'cancel'); self.expiry.sweep(now=1000 + 11 * 86400)
        self.assertTrue(path.exists())
        self.expiry.schedule(aid, 2000, now=1000); self.expiry.sweep(now=2000)
        self.assertFalse(path.exists()); self.assertTrue(Lifecycle(self.workspace).data['assets'][aid]['trashed'])
        self.expiry.restore(0); self.assertTrue(path.exists())
        self.assertFalse(Lifecycle(self.workspace).data['assets'][aid]['trashed'])

    def test_new_volatile_can_auto_schedule_but_initial_files_still_wait(self):
        self.options['volatile_mode'] = 'auto'
        self.asset('임시 old.txt', initial=True); self.asset('임시 new.txt', initial=False)
        self.expiry.sweep(now=1000)
        statuses = {entry['name']: entry['status'] for entry in self.expiry.public()['entries']}
        self.assertEqual(statuses, {'임시 old.txt': 'pending', '임시 new.txt': 'scheduled'})

    def test_keep_reference_symlink_and_outside_paths_are_not_deleted(self):
        aid, path = self.asset('important.txt')
        engine = Lifecycle(self.workspace); engine.data['assets'][aid]['keep'] = True; engine.save()
        with self.assertRaises(ValueError): self.expiry.schedule(aid, 2000, now=1000)
        external = self.root / 'private.dmg'; external.write_text('private')
        (self.inbox / 'link.dmg').symlink_to(external)
        self.expiry.sweep(now=1000); self.assertEqual(self.expiry.public()['entries'], [])
        self.assertTrue(external.exists())

    def test_schedule_survives_restart_and_public_state_has_no_paths(self):
        path = self.inbox / 'app.dmg'; path.write_text('installer'); self.expiry.sweep(now=1000)
        restarted = Expiry(self.root / 'expiry.json', [self.inbox], trash=self.trash)
        self.assertEqual(restarted.public()['entries'][0]['due_at'], 1000 + 3 * 86400)
        self.assertNotIn(str(self.root), json.dumps(restarted.public()))

    def test_later_keep_and_new_reference_block_an_existing_schedule(self):
        aid, path = self.asset('notes.txt')
        self.expiry.schedule(aid, 2000, now=1000)
        engine = Lifecycle(self.workspace); engine.data['assets'][aid]['keep'] = True; engine.save()
        self.expiry.sweep(now=2000); self.assertTrue(path.exists())
        self.assertEqual(self.expiry.public()['entries'][0]['status'], 'blocked')
        engine = Lifecycle(self.workspace); engine.data['assets'][aid]['keep'] = False
        reference = self.workspace / 'config.txt'; reference.write_text('reference')
        engine.save(); other = engine.ingest('config.txt'); engine.data['assets'][other]['refs'] = ['notes.txt']; engine.save()
        with self.assertRaises(ValueError): self.expiry.schedule(aid, 4000, now=2000)

    def test_expiry_scans_reuse_one_manifest_snapshot(self):
        for number in range(12): self.asset('임시 ' + str(number) + '.txt')
        calls = []
        def engine(): calls.append(True); return Lifecycle(self.workspace)
        self.expiry.engine = engine
        self.expiry.sweep(now=1000)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.expiry.public()['total'], 12)


if __name__ == '__main__': unittest.main()
