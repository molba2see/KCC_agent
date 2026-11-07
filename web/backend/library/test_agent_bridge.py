import hashlib
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import AgentLink, AgentCommand


class AgentBridgeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('owner', password='strong-password-123')
        self.other = get_user_model().objects.create_user('other', password='strong-password-123')
        self.token = 'test-bridge-token'
        self.link = AgentLink.objects.create(owner=self.user, token_hash=hashlib.sha256(self.token.encode()).hexdigest())
        self.browser = APIClient()
        self.browser.force_authenticate(self.user)
        self.mac = APIClient()
        self.mac.credentials(HTTP_AUTHORIZATION='Bearer '+self.token)
        self.snapshot = {'assets':[{'id':'asset-1','original':'downloads/notes.txt','path':'downloads/notes.txt',
                                    'archived':False,'plan':{'action':'file','target':'/safe/project/notes.txt','reason':'project folder'},
                                    'run':{'status':'planned'}}],
                         'catalog':[{'id':'project-1','name':'Project'}], 'trashed':[]}

    def test_actual_command_round_trip(self):
        self.assertEqual(self.mac.post('/api/v1/agent/bridge/poll/', {'snapshot':self.snapshot}, format='json').status_code, 200)
        result = self.browser.post('/api/v1/agent/commands/', {'link_id':str(self.link.id),'action':'approve','asset_id':'asset-1'}, format='json')
        self.assertEqual(result.status_code, 201)
        command = self.mac.post('/api/v1/agent/bridge/poll/', {'snapshot':self.snapshot}, format='json').json()['command']
        self.assertEqual(command['payload']['plan'], self.snapshot['assets'][0]['plan'])
        self.assertEqual(command['status'], 'running')
        self.assertEqual(self.mac.post('/api/v1/agent/bridge/result/', {'id':command['id'],'ok':True,'result':True}, format='json').status_code, 200)
        status = self.browser.get('/api/v1/agent/status/').json()['links'][0]
        self.assertTrue(status['connected'])
        self.assertEqual(status['commands'][0]['status'], 'done')

    def test_preview_uses_registered_ids_and_requires_updated_helper(self):
        self.mac.post('/api/v1/agent/bridge/poll/', {'snapshot': self.snapshot}, format='json')
        body = {'link_id': str(self.link.id), 'action': 'preview', 'asset_id': 'asset-1', 'path': '/etc/passwd'}
        self.assertEqual(self.browser.post('/api/v1/agent/commands/', body, format='json').status_code, 409)
        self.snapshot['capabilities'] = ['preview']
        self.mac.post('/api/v1/agent/bridge/poll/', {'snapshot': self.snapshot}, format='json')
        response = self.browser.post('/api/v1/agent/commands/', body, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['payload'], {'id': 'asset-1'})
        AgentCommand.objects.all().delete()
        body['asset_id'] = 'unknown'
        self.assertEqual(self.browser.post('/api/v1/agent/commands/', body, format='json').status_code, 400)
        self.snapshot['cleanup'] = {'groups': [{'files': [{'id': 'group-only'}]}]}
        self.mac.post('/api/v1/agent/bridge/poll/', {'snapshot': self.snapshot}, format='json')
        body['asset_id'] = 'group-only'
        self.assertEqual(self.browser.post('/api/v1/agent/commands/', body, format='json').status_code, 201)

    def test_invalid_token_owner_and_plan_are_rejected(self):
        self.assertEqual(APIClient().post('/api/v1/agent/bridge/poll/', {'snapshot':self.snapshot}, format='json').status_code, 403)
        self.mac.post('/api/v1/agent/bridge/poll/', {'snapshot':self.snapshot}, format='json')
        foreign = APIClient()
        foreign.force_authenticate(self.other)
        self.assertEqual(foreign.get('/api/v1/agent/status/').json()['links'], [])
        self.assertEqual(foreign.post('/api/v1/agent/commands/', {'link_id':str(self.link.id),'action':'approve','asset_id':'asset-1'}, format='json').status_code, 404)
        self.assertEqual(self.browser.post('/api/v1/agent/commands/', {'link_id':str(self.link.id),'action':'approve','asset_id':'missing'}, format='json').status_code, 400)
        self.assertEqual(self.browser.post('/api/v1/agent/commands/', {'link_id':str(self.link.id),'action':'delete','asset_id':'asset-1'}, format='json').status_code, 400)
        self.assertEqual(AgentCommand.objects.count(), 0)

    def test_only_one_inflight_command(self):
        self.mac.post('/api/v1/agent/bridge/poll/', {'snapshot':self.snapshot}, format='json')
        body={'link_id':str(self.link.id),'action':'approve','asset_id':'asset-1'}
        self.assertEqual(self.browser.post('/api/v1/agent/commands/', body, format='json').status_code, 201)
        self.assertEqual(self.browser.post('/api/v1/agent/commands/', body, format='json').status_code, 409)

    def test_cleanup_confirmation_uses_only_server_group_id_and_is_owner_scoped(self):
        self.snapshot['cleanup'] = {'status': 'review', 'groups': [{'id': 'group-1', 'status': 'pending', 'files': [{'id': 'asset-1'}]}]}
        self.mac.post('/api/v1/agent/bridge/poll/', {'snapshot': self.snapshot}, format='json')
        response = self.browser.post('/api/v1/agent/commands/', {'link_id': str(self.link.id), 'action': 'cleanup_confirm',
            'group_id': 'group-1', 'folder': '/untrusted/path', 'files': ['foreign']}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['payload'], {'group_id': 'group-1'})
        AgentCommand.objects.all().delete()
        self.assertEqual(self.browser.post('/api/v1/agent/commands/', {'link_id': str(self.link.id), 'action': 'cleanup_confirm', 'group_id': 'foreign'}, format='json').status_code, 409)
        self.snapshot['cleanup']['status'] = 'generating'
        self.mac.post('/api/v1/agent/bridge/poll/', {'snapshot': self.snapshot}, format='json')
        self.assertEqual(self.browser.post('/api/v1/agent/commands/', {'link_id': str(self.link.id), 'action': 'cleanup_confirm', 'group_id': 'group-1'}, format='json').status_code, 409)

class BrowserLoginTests(TestCase):
    def test_login_needs_csrf_and_valid_password(self):
        from django.test import Client
        get_user_model().objects.create_user('owner', password='strong-password-123')
        client = Client(enforce_csrf_checks=True)
        session = client.get('/api/v1/auth/session/')
        self.assertEqual(session.status_code, 200)
        self.assertFalse(session.json()['authenticated'])
        self.assertEqual(client.post('/api/v1/auth/login/', data='{"username":"owner","password":"strong-password-123"}', content_type='application/json').status_code, 403)
        token = session.json()['csrf']
        self.assertEqual(client.post('/api/v1/auth/login/', data='{"username":"owner","password":"wrong"}', content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code, 401)
        self.assertEqual(client.post('/api/v1/auth/login/', data='{"username":"owner","password":"strong-password-123"}', content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertEqual(client.get('/api/v1/agent/status/').status_code, 200)

    @override_settings(ALLOWED_HOSTS=['3.38.192.19'], SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'))
    def test_login_accepts_https_origin_through_proxy(self):
        from django.test import Client
        get_user_model().objects.create_user('owner', password='strong-password-123')
        client = Client(enforce_csrf_checks=True, HTTP_HOST='3.38.192.19', HTTP_X_FORWARDED_PROTO='https')
        token = client.get('/api/v1/auth/session/').json()['csrf']
        response = client.post('/api/v1/auth/login/',
                               data='{"username":"owner","password":"strong-password-123"}',
                               content_type='application/json', HTTP_X_CSRFTOKEN=token,
                               HTTP_ORIGIN='https://3.38.192.19')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['authenticated'])
