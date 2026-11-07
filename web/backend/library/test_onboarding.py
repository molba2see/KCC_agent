from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import AgentLink, OnboardingProgress


class OnboardingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('owner')
        self.other = get_user_model().objects.create_user('other')
        self.client.force_login(self.user)
        self.path = '/api/v1/onboarding/'
        self.link = AgentLink.objects.create(owner=self.user, token_hash='1' * 64,
            last_seen_at=timezone.now(), snapshot={'assets': [{'id': 'old', 'name': 'existing.png'}], 'catalog': []})

    def action(self, name):
        return self.client.post(self.path, {'action': name}, content_type='application/json')

    def test_flow_requires_confirmation_and_a_new_file(self):
        self.assertEqual(self.action('start_test').status_code, 409)
        self.assertEqual(self.action('complete').status_code, 409)
        self.assertEqual(self.action('confirm_iphone').status_code, 200)
        self.assertEqual(self.action('start_test').status_code, 409)
        self.assertEqual(self.action('defer_cleanup').status_code, 200)
        self.assertEqual(self.action('start_test').status_code, 200)
        state = self.client.get(self.path).json()
        self.assertFalse(state['file_received'])
        self.assertEqual(self.action('complete').status_code, 409)
        self.link.last_seen_at = timezone.now()
        self.link.save()
        self.assertFalse(self.client.get(self.path).json()['file_received'])
        self.link.snapshot['assets'].append({'id': 'new', 'name': '새 스크린샷.png'})
        self.link.last_seen_at = timezone.now()
        self.link.save()
        state = self.client.get(self.path).json()
        self.assertTrue(state['file_received'])
        self.assertEqual(state['received_filename'], '새 스크린샷.png')
        self.assertTrue(self.action('complete').json()['completed'])
        self.assertTrue(self.client.get('/api/v1/auth/session/').json()['onboarding_completed'])
        self.client.logout()
        self.client.force_login(self.user)
        self.assertTrue(self.client.get(self.path).json()['completed'])

    def test_offline_mac_cannot_complete_and_another_owner_is_ignored(self):
        AgentLink.objects.create(owner=self.other, token_hash='2' * 64, last_seen_at=timezone.now(),
                                 snapshot={'assets': [{'id': 'foreign', 'name': '비공개.png'}]})
        self.action('confirm_iphone')
        self.action('defer_cleanup')
        self.action('start_test')
        self.assertFalse(self.client.get(self.path).json()['file_received'])
        self.link.last_seen_at = timezone.now() - timedelta(seconds=60)
        self.link.save()
        self.assertFalse(self.client.get(self.path).json()['mac_connected'])
        self.assertEqual(self.action('start_test').status_code, 409)
        self.assertEqual(self.action('complete').status_code, 409)
        self.client.force_login(self.other)
        self.assertFalse(self.client.get(self.path).json()['iphone_icloud_confirmed'])

    def test_first_cleanup_requires_decisions_and_downloads_do_not_pass_iphone_test(self):
        self.assertEqual(self.action('confirm_cleanup').status_code, 409)
        self.link.snapshot['cleanup'] = {'status': 'failed', 'groups': []}
        self.link.save()
        self.assertEqual(self.action('confirm_cleanup').status_code, 409)
        self.link.snapshot['cleanup'] = {'status': 'generating', 'groups': []}
        self.link.save()
        self.assertEqual(self.action('confirm_cleanup').status_code, 409)
        self.link.snapshot['cleanup'] = {'status': 'review', 'groups': [{'status': 'pending'}]}
        self.link.save()
        self.assertEqual(self.action('confirm_cleanup').status_code, 409)
        self.link.snapshot['cleanup']['groups'][0]['status'] = 'dismissed'
        self.link.save()
        self.assertEqual(self.action('confirm_cleanup').status_code, 200)
        self.action('confirm_iphone'); self.action('start_test')
        self.link.snapshot['assets'].append({'id': 'download', 'name': 'new.pdf', 'source_kind': 'download'})
        self.link.snapshot['assets'].append({'id': 'old-phone-import', 'name': 'old.png', 'source_kind': 'icloud', 'source_mtime': 0})
        self.link.last_seen_at = timezone.now(); self.link.save()
        self.assertFalse(self.client.get(self.path).json()['file_received'])
        self.link.snapshot['assets'].append({'id': 'phone', 'name': 'new.png', 'source_kind': 'icloud'})
        self.link.last_seen_at = timezone.now(); self.link.save()
        self.assertTrue(self.client.get(self.path).json()['file_received'])

    def test_progress_requires_login_and_does_not_accept_client_completion_flags(self):
        self.assertEqual(self.action('unsupported').status_code, 400)
        response = self.client.post(self.path, {'completed': True, 'file_received': True}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(OnboardingProgress.objects.get(owner=self.user).completed_at)
        self.client.logout()
        self.assertEqual(self.client.get(self.path).status_code, 403)
