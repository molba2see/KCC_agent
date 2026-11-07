import hashlib
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import AgentCommand, AgentLink


class RuntimePolicyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('owner', password='test-password-1234')
        self.other = get_user_model().objects.create_user('other')
        self.link = AgentLink.objects.create(owner=self.user, token_hash=hashlib.sha256(b'token').hexdigest(), last_seen_at=timezone.now(),
            snapshot={'capabilities': ['preferences', 'expiry'], 'preferences': {'revision': 2},
                      'assets': [{'id': 'a'}], 'catalog': [], 'expiry': {'entries': [{'id': 'e', 'status': 'pending'}]}})
        self.browser = APIClient(); self.browser.force_authenticate(self.user)
        self.path = '/api/v1/agent/commands/'

    def post(self, action, **values):
        return self.browser.post(self.path, {'link_id': str(self.link.id), 'action': action, **values}, format='json')

    def test_settings_are_validated_versioned_and_owner_scoped(self):
        for values in [{'installer_days': 0}, {'installer_days': True}, {'installers_enabled': 'yes'}, {'download_mode': 'delete'}, {'path': '/etc'}]:
            self.assertEqual(self.post('preferences', settings=values, revision=2).status_code, 400)
        self.assertEqual(self.post('preferences', settings={'download_mode': 'review'}, revision=1).status_code, 409)
        self.browser.force_authenticate(self.other)
        self.assertEqual(self.post('preferences', settings={'download_mode': 'review'}, revision=2).status_code, 404)
        self.browser.force_authenticate(self.user)
        result = self.post('preferences', settings={'download_mode': 'review', 'installer_days': 3}, revision=2, folder='/untrusted')
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json()['payload'], {'settings': {'download_mode': 'review', 'installer_days': 3}, 'revision': 2})

    def test_schedule_and_entry_actions_never_accept_arbitrary_paths(self):
        due = timezone.now().timestamp() + 86400
        for values in [{'asset_id': 'foreign', 'due_at': due}, {'asset_id': 'a', 'due_at': 1}, {'asset_id': 'a', 'due_at': True}]:
            self.assertEqual(self.post('expiry_schedule', **values).status_code, 400)
        self.assertEqual(self.post('expiry_cancel', entry_id='foreign').status_code, 409)
        result = self.post('expiry_schedule', asset_id='a', due_at=due, path='/etc/passwd')
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json()['payload'], {'id': 'a', 'due_at': due})
        AgentCommand.objects.all().delete()
        self.assertEqual(self.post('expiry_confirm', entry_id='e').json()['payload'], {'entry_id': 'e'})

    def test_offline_and_old_helpers_are_blocked_and_session_csrf_is_required(self):
        self.link.last_seen_at = timezone.now() - timedelta(seconds=60); self.link.save()
        self.assertEqual(self.post('preferences', settings={'download_mode': 'review'}, revision=2).status_code, 409)
        self.link.last_seen_at = timezone.now(); self.link.snapshot['capabilities'] = []; self.link.save()
        self.assertEqual(self.post('expiry_cancel', entry_id='e').status_code, 409)
        self.link.snapshot['capabilities'] = ['preferences']; self.link.save()
        client = Client(enforce_csrf_checks=True); client.force_login(self.user)
        payload = {'link_id': str(self.link.id), 'action': 'preferences', 'settings': {'download_mode': 'review'}, 'revision': 2}
        self.assertEqual(client.post(self.path, payload, content_type='application/json').status_code, 403)
        csrf = client.get('/api/v1/auth/session/').json()['csrf']
        self.assertEqual(client.post(self.path, payload, content_type='application/json', HTTP_X_CSRFTOKEN=csrf).status_code, 201)
