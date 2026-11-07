from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import shutil
import sys
import threading
import unittest
from unittest.mock import patch

from initial_cleanup import InitialCleanup
from lifecycle_v3 import Lifecycle


class InitialCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.base = Path(self.temp.name)
        self.root = self.base / 'workspace'; self.root.mkdir()
        self.originals = self.base / 'Downloads'; self.originals.mkdir()
        self.target = self.base / 'existing'; self.target.mkdir()
        self.projects = self.base / 'projects.json'
        self.projects.write_text(json.dumps({'old': {'name': '수업', 'folder': str(self.target)}}))
        self.catalog = {'old': {'name': '수업', 'profile': '강의 문서를 보관합니다.', 'desc': '수업 자료'}}
        engine = Lifecycle(self.root)
        engine.data.update(projects={'old': 'active'}, folders={'old': str(self.target)}); engine.save()
        self.ids = []
        for name in ['회의록_1.txt', '회의록_2.txt']:
            original = self.originals / name; original.write_text('회의 내용 자료입니다. private body marker')
            copied = self.root / name; shutil.copy2(original, copied)
            self.ids.append(engine.ingest(name))
        self.demo = SimpleNamespace(root=self.root, lock=threading.Lock(), projects_path=self.projects, engine=lambda: Lifecycle(self.root))
        self.cleanup = InitialCleanup(self.demo, self.catalog, sys.executable, self.base / 'worker.py', self.base / 'iCloud' / '모아')

    def tearDown(self): self.temp.cleanup()

    def propose(self, target='new', name='회의록'):
        self.cleanup.accept_groups([{'project_id': target, 'name': name, 'purpose': '회의록과 회의 일정 자료를 보관합니다.', 'files': self.ids}], list(self.demo.engine().data['assets'].values()))
        return self.cleanup.data['groups'][-1]['id']

    def test_proposal_and_dismissal_do_not_create_or_move_files(self):
        group = self.propose()
        self.assertFalse(self.cleanup.destination.exists())
        self.cleanup.decide(group, False)
        self.assertFalse(self.cleanup.destination.exists())
        self.assertTrue(all((self.root / name).exists() for name in ['회의록_1.txt', '회의록_2.txt']))
        with self.assertRaises(ValueError): self.cleanup.decide(group, True)

    def test_confirm_creates_guidance_moves_only_copies_and_survives_restart(self):
        group = self.propose(); result = self.cleanup.decide(group, True)
        self.assertEqual(result['count'], 2)
        folder = self.cleanup.destination / '회의록'
        self.assertTrue((folder / '_project.md').is_file())
        self.assertTrue(all((folder / name).is_file() and (self.originals / name).is_file() for name in ['회의록_1.txt', '회의록_2.txt']))
        self.assertEqual(len(json.loads(self.projects.read_text())), 2)
        restarted = InitialCleanup(self.demo, self.catalog, sys.executable, self.base / 'worker.py', self.cleanup.destination)
        self.assertEqual(restarted.data['groups'][0]['status'], 'approved')
        with self.assertRaises(ValueError): restarted.decide(group, True)

    def test_individual_decision_expires_group_and_returns_files_to_review(self):
        self.propose()
        engine = self.demo.engine()
        engine.data['assets'][self.ids[0]]['keep'] = True
        engine.save()
        public = self.cleanup.public()
        self.assertEqual(public['pending_groups'], 0)
        self.assertEqual(public['groups'], [])
        self.assertEqual(self.cleanup.data['groups'][0]['status'], 'stale')
        self.assertFalse(self.cleanup.destination.exists())

    def test_existing_target_needs_confirmation_and_creates_no_new_folder(self):
        group = self.propose('old')
        self.assertEqual(list(self.target.iterdir()), [])
        self.cleanup.decide(group, True)
        self.assertEqual(len(list(self.target.iterdir())), 2)
        self.assertFalse(self.cleanup.destination.exists())

    def test_confident_existing_classification_is_grouped_without_model_or_move(self):
        engine = self.demo.engine()
        for aid in self.ids: engine.data['assets'][aid]['project'] = 'old'
        engine.save()
        with patch('initial_cleanup.subprocess.Popen') as worker:
            self.cleanup.generate()
            worker.assert_not_called()
        self.assertEqual(self.cleanup.data['status'], 'review')
        self.assertEqual(len(self.cleanup.public()['groups']), 1)
        self.assertFalse(self.cleanup.public()['groups'][0]['new_folder'])
        self.assertEqual(list(self.target.iterdir()), [])
        self.cleanup.decide(self.cleanup.data['groups'][0]['id'], True)
        self.assertEqual(len(list(self.target.iterdir())), 2)

    def test_rescan_reconsiders_dismissed_groups_and_preserves_kept_files(self):
        group = self.propose(); self.cleanup.decide(group, False)
        self.cleanup.data['status'] = 'completed'
        self.cleanup.rescan()
        self.assertEqual(self.cleanup.data['status'], 'scanning')
        self.assertEqual(self.cleanup.data['groups'][0]['status'], 'stale')
        second = self.propose()
        self.assertNotEqual(group, second)
        self.assertEqual(self.cleanup.public()['pending_groups'], 1)
        engine = self.demo.engine(); engine.data['assets'][self.ids[0]]['keep'] = True; engine.save()
        self.assertFalse(self.cleanup.eligible(engine.data['assets'][self.ids[0]]))
        with self.assertRaises(ValueError): self.cleanup.rescan()

    def test_individual_project_change_invalidates_group(self):
        self.propose()
        engine = self.demo.engine(); engine.data['assets'][self.ids[0]]['project'] = 'old'; engine.save()
        self.assertEqual(self.cleanup.public()['pending_groups'], 0)

    def test_rescan_reruns_classifier_before_preparing_confirmations(self):
        self.cleanup.data['status'] = 'completed'; self.cleanup.rescan()
        called = []
        def analyze(aid):
            called.append(aid)
            engine = self.demo.engine(); engine.data['assets'][aid]['project'] = 'old'; engine.save()
        self.demo.analyze = analyze
        with patch('initial_cleanup.subprocess.Popen') as worker:
            self.cleanup.generate(); worker.assert_not_called()
        self.assertEqual(set(called), set(self.ids))
        self.assertEqual(self.cleanup.public()['pending_groups'], 1)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_new_onboarding_request_starts_scan_but_restart_does_not_repeat_it(self):
        group = self.propose(); self.cleanup.data['status'] = 'review'; self.cleanup.save()
        new = InitialCleanup(self.demo, self.catalog, sys.executable, self.base / 'worker.py', self.cleanup.destination, request_id='new-onboarding')
        self.assertEqual(new.data['status'], 'scanning')
        self.assertTrue(new.data['reanalyze'])
        self.assertEqual(new.data['groups'][0]['status'], 'stale')
        new.data['status'] = 'completed'; new.save()
        restarted = InitialCleanup(self.demo, self.catalog, sys.executable, self.base / 'worker.py', self.cleanup.destination, request_id='new-onboarding')
        self.assertEqual(restarted.data['status'], 'completed')

    def test_changed_file_rejects_entire_group_before_folder_creation(self):
        group = self.propose(); (self.root / '회의록_2.txt').write_text('changed')
        with self.assertRaises(ValueError): self.cleanup.decide(group, True)
        self.assertFalse(self.cleanup.destination.exists())
        self.assertTrue((self.root / '회의록_1.txt').exists())

    def test_preexisting_folder_and_guidance_are_never_overwritten_or_removed(self):
        group = self.propose(); folder = self.cleanup.destination / '회의록'; folder.mkdir(parents=True)
        guide = folder / '_project.md'; guide.write_text('user-owned')
        with self.assertRaises(ValueError): self.cleanup.decide(group, True)
        self.assertEqual(guide.read_text(), 'user-owned')

    def test_worker_transport_prepares_proposals_without_applying_them(self):
        worker = self.base / 'worker.py'
        worker.write_text("import sys,json\nfrom pathlib import Path\na=sys.argv\nr=json.loads(Path(a[a.index('--request')+1]).read_text())\nPath(a[a.index('--response')+1]).write_text(json.dumps({'status':'completed','processed':len(r['files']),'groups':[{'project_id':'new','name':'회의록','purpose':'회의 내용을 보관합니다.','files':[f['id'] for f in r['files']]}]}))\n")
        self.cleanup.data['status'] = 'generating'
        self.cleanup.generate()
        self.assertEqual(self.cleanup.data['status'], 'review', self.cleanup.data)
        self.assertEqual(len(self.cleanup.data['groups']), 1)
        self.assertFalse(self.cleanup.destination.exists())
        self.assertEqual(list(self.root.glob('.cleanup-*.json')), [])

    def test_partial_execution_is_rolled_back(self):
        group = self.propose()
        execute = Lifecycle.execute
        calls = []
        def fail_second(engine, aid, plan, **kwargs):
            calls.append(aid)
            if len(calls) == 2: raise OSError('injected failure')
            return execute(engine, aid, plan, **kwargs)
        with patch.object(Lifecycle, 'execute', fail_second):
            with self.assertRaises(OSError): self.cleanup.decide(group, True)
        self.assertTrue(all((self.root / name).exists() for name in ['회의록_1.txt', '회의록_2.txt']))
        self.assertFalse((self.cleanup.destination / '회의록').exists())
        self.assertEqual(len(json.loads(self.projects.read_text())), 1)

    def test_model_cannot_propose_arbitrary_paths_unknown_files_or_duplicate_ids(self):
        assets = list(self.demo.engine().data['assets'].values())
        for ids, name, target in [(self.ids, '../escape', 'new'), (['foreign'], '회의록', 'new'), ([self.ids[0]]*2, '회의록', 'new'), (self.ids, '회의록', 'foreign')]:
            with self.assertRaises(ValueError):
                self.cleanup.accept_groups([{'project_id': target, 'name': name, 'purpose': '회의록 자료를 보관합니다.', 'files': ids}], assets)
        self.assertEqual(self.cleanup.data['groups'], [])

    def test_public_proposal_omits_content_profiles_paths_and_file_hashes(self):
        self.propose(); public = json.dumps(self.cleanup.public(), ensure_ascii=False)
        for private in ['private body marker', str(self.base), self.demo.engine().data['assets'][self.ids[0]]['hash'], 'profile']:
            self.assertNotIn(private, public)

    def test_symlink_destination_is_rejected(self):
        group = self.propose(); outside = self.base / 'outside'; outside.mkdir()
        self.cleanup.destination.parent.mkdir()
        self.cleanup.destination.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError): self.cleanup.decide(group, True)
        self.assertEqual(list(outside.iterdir()), [])
