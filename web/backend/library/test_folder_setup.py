import fcntl
import json
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class FolderSetupTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name)
        self.folder = self.data / 'selected'
        self.folder.mkdir()
        env = patch.dict(os.environ, MOA_LOCAL_KEY='key', MOA_LOCAL_DATA=str(self.data))
        env.start()
        self.addCleanup(env.stop)
        self.user = get_user_model().objects.create_user('local-owner')
        self.client = Client(HTTP_HOST='localhost', REMOTE_ADDR='127.0.0.1')
        self.path = '/api/v1/local/folders/'

    def test_only_authenticated_loopback_with_csrf_can_start_worker(self):
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.path, REMOTE_ADDR='192.168.1.1').status_code, 404)
        self.assertEqual(self.client.get(self.path, HTTP_HOST='example.com').status_code, 400)
        csrf_client = Client(enforce_csrf_checks=True, HTTP_HOST='localhost', REMOTE_ADDR='127.0.0.1')
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(self.path, {'folders': [str(self.folder)]}, content_type='application/json').status_code, 403)
        with patch('library.folder_setup.subprocess.Popen') as spawn:
            response = self.client.post(self.path, {'folders': [str(self.folder)]}, content_type='application/json')
            self.assertEqual(response.status_code, 202)
            self.assertIn('--data', spawn.call_args.args[0])
            self.assertEqual(json.loads((self.data / 'selected-folders.json').read_text()), [str(self.folder.resolve())])
            self.assertTrue(json.loads((self.data / 'initial-cleanup-settings.json').read_text())['enabled'])
        self.assertEqual(self.client.get(self.path).json()['status'], 'failed')  # stopped worker
        other = get_user_model().objects.create_user('other')
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.path).status_code, 403)

    def test_busy_worker_cannot_be_replaced_and_invalid_selection_cannot_start(self):
        self.client.force_login(self.user)
        with patch('library.folder_setup.subprocess.Popen') as spawn:
            for values in [[], ['/does-not-exist'], [str(self.data), str(self.folder)]]:
                self.assertEqual(self.client.post(self.path, {'folders': values}, content_type='application/json').status_code, 400)
            spawn.assert_not_called()
        (self.data / 'folder-setup.json').write_text(json.dumps({'status': 'generating', 'completed': 0}))
        with (self.data / 'folder-setup.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.client.get(self.path).json()['status'], 'generating')
            self.assertEqual(self.client.post(self.path, {'folders': [str(self.folder)]}, content_type='application/json').status_code, 409)

    def test_real_worker_publishes_completed_selection_and_releases_lock(self):
        self.client.force_login(self.user)
        (self.folder / '_project.md').write_text('# Existing owner guidance')
        response = self.client.post(self.path, {'folders': [str(self.folder)], 'initial_cleanup': False}, content_type='application/json')
        self.assertEqual(response.status_code, 202)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = self.client.get(self.path).json()
            if state['status'] in {'completed', 'failed'}:
                break
            time.sleep(.05)
        self.assertEqual(state['status'], 'completed', state)
        projects = json.loads((self.data / 'projects.json').read_text())
        self.assertEqual(next(iter(projects.values()))['folder'], str(self.folder.resolve()))
        self.assertEqual((self.folder / '_project.md').read_text(), '# Existing owner guidance')

    def test_add_mode_preserves_registered_folders_and_does_not_relink_account(self):
        self.client.force_login(self.user)
        (self.data / 'initial-cleanup-settings.json').write_text(json.dumps({'enabled': False}))
        old = self.data / 'old'; old.mkdir()
        prior = {'keep-id': {'name': 'Old', 'folder': str(old.resolve()), 'keywords': ['saved']}}
        (self.data / 'projects.json').write_text(json.dumps(prior))
        (self.folder / '_project.md').write_text('# New folder rules')
        (self.data / 'cloud.json').write_text('unchanged cloud credentials fixture')
        response = self.client.post(self.path, {'folders': [str(self.folder)], 'mode': 'add'}, content_type='application/json')
        self.assertEqual(response.status_code, 202)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = self.client.get(self.path).json()
            if state['status'] in {'completed', 'failed'}:
                break
            time.sleep(.05)
        self.assertEqual(state['status'], 'completed', state)
        self.assertEqual(state['mode'], 'add')
        projects = json.loads((self.data / 'projects.json').read_text())
        self.assertEqual(projects['keep-id'], prior['keep-id'])
        self.assertEqual(len(projects), 2)
        self.assertEqual((self.data / 'cloud.json').read_text(), 'unchanged cloud credentials fixture')
