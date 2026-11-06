import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class LocalSetupTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / 'data'
        self.data.mkdir()
        self.cloud = Path(self.temp.name) / 'cloud'
        self.cloud.mkdir()
        self.env = patch.dict(os.environ, MOA_LOCAL_KEY='local-secret', MOA_LOCAL_DATA=str(self.data))
        self.env.start()
        self.addCleanup(self.env.stop)
        self.root = patch('library.local_setup.cloud_root', return_value=self.cloud)
        self.root.start()
        self.addCleanup(self.root.stop)
        self.user = get_user_model().objects.create_user('local-owner')
        self.client = Client(HTTP_HOST='localhost', REMOTE_ADDR='127.0.0.1')

    def test_opt_in_local_access_and_secret_required(self):
        self.assertEqual(self.client.get('/api/v1/local/setup/').status_code, 403)
        self.assertEqual(self.client.post('/api/v1/local/unlock/', HTTP_X_MOA_LOCAL_KEY='wrong').status_code, 403)
        self.assertEqual(self.client.post('/api/v1/local/unlock/', HTTP_X_MOA_LOCAL_KEY='local-secret').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/local/setup/').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/local/setup/', REMOTE_ADDR='192.168.1.2').status_code, 404)
        with patch.dict(os.environ, MOA_LOCAL_KEY=''):
            self.assertEqual(self.client.get('/api/v1/local/setup/').status_code, 404)

    def test_connect_creates_only_app_folders_and_preserves_guides(self):
        self.client.force_login(self.user)
        response = self.client.post('/api/v1/local/setup/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['configured'])
        config = json.loads((self.data / 'icloud.json').read_text())
        self.assertEqual(config['inbox'], str(self.cloud / 'KCC-inbox'))
        self.assertTrue((self.cloud / 'KCC-inbox').is_dir())
        self.assertTrue(response.json()['shortcut_ready'])
        guide = self.cloud / '모아/문서/_project.md'
        guide.write_text('User guide')
        self.client.post('/api/v1/local/setup/')
        self.assertEqual(guide.read_text(), 'User guide')
        projects = json.loads((self.data / 'projects.json').read_text())
        self.assertEqual(len(projects), 3)
        self.assertFalse((self.data / 'workspace').exists())

    def test_existing_legacy_inbox_switches_without_moving_files(self):
        self.client.force_login(self.user)
        old = self.cloud / '모아/받은 파일'
        old.mkdir(parents=True)
        (old / 'existing.png').write_bytes(b'original')
        (self.data / 'icloud.json').write_text(json.dumps({'inbox': str(old)}))
        custom_projects = '{"custom":{"folder":"/Users/example/Documents"}}'
        (self.data / 'projects.json').write_text(custom_projects)
        self.assertFalse(self.client.get('/api/v1/local/setup/').json()['shortcut_ready'])
        response = self.client.post('/api/v1/local/setup/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['shortcut_ready'])
        self.assertEqual(json.loads((self.data / 'icloud.json').read_text())['inbox'], str(self.cloud / 'KCC-inbox'))
        self.assertEqual((old / 'existing.png').read_bytes(), b'original')
        self.assertEqual((self.data / 'projects.json').read_text(), custom_projects)

    def test_missing_icloud_does_not_claim_connection(self):
        self.client.force_login(self.user)
        self.cloud.rmdir()
        self.assertFalse(self.client.get('/api/v1/local/setup/').json()['available'])
        self.assertEqual(self.client.post('/api/v1/local/setup/').status_code, 409)
        self.assertFalse((self.data / 'icloud.json').exists())

    def test_unlock_and_setup_enforce_csrf(self):
        client = Client(enforce_csrf_checks=True, HTTP_HOST='localhost', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(client.post('/api/v1/local/unlock/', HTTP_X_MOA_LOCAL_KEY='local-secret').status_code, 403)
        token = client.get('/api/v1/auth/session/').json()['csrf']
        self.assertEqual(client.post('/api/v1/local/unlock/', HTTP_X_MOA_LOCAL_KEY='local-secret', HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertEqual(client.post('/api/v1/local/setup/').status_code, 403)
