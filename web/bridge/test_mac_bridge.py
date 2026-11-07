import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import URLError
from mac_bridge import public_state, server_allowed


class PrivacyTests(unittest.TestCase):
    def test_timeout_sends_retained_snapshot_heartbeat_without_leaking_exception(self):
        import mac_bridge
        posts = []
        with TemporaryDirectory() as directory, patch('mac_bridge.get', side_effect=[{'assets': [{'id': 'a', 'original': 'file.txt'}], 'catalog': []}, URLError('/private/exception')]), patch('mac_bridge.post', side_effect=lambda url, body, token: posts.append(body) or {'command': None}), patch('mac_bridge.time.sleep', side_effect=[None, KeyboardInterrupt]):
            with self.assertRaises(KeyboardInterrupt): mac_bridge.run('https://example.com', 'http://127.0.0.1:8791', 'fixture', 5, Path(directory) / 'pending.json')
        self.assertEqual(len(posts), 2)
        self.assertFalse(posts[1]['snapshot']['agent_available'])
        self.assertEqual(posts[1]['snapshot']['assets'][0]['id'], 'a')
        self.assertNotIn('/private', str(posts))

    def test_state_omits_content_and_trace_but_keeps_approval_plan(self):
        state = {'root':'/private/home', 'assets':[{'id':'a','project':'p','original':'/private/notes.txt','path':'/private/notes.txt',
                  'plan':{'action':'file','target':'/projects/notes.txt'}, 'run':{'status':'planned','full':[{'secret':'body'}], 'trace':['private content']},
                  'why':['Project hint']}], 'catalog':[{'id':'p','name':'Project','profile':'private data'}],
                 'trashed':[], 'journal':[{'src':'/private/notes.txt'}]}
        result = public_state(state)
        self.assertEqual(result['assets'][0]['name'], 'notes.txt')
        self.assertEqual(result['assets'][0]['project'], 'p')
        self.assertEqual(result['assets'][0]['plan'], state['assets'][0]['plan'])
        self.assertNotIn('/private', str(result))
        self.assertNotIn('private content', str(result))
        self.assertNotIn('body', str(result))

    def test_cleanup_proposals_keep_only_public_confirmation_fields(self):
        result = public_state({'assets': [], 'catalog': [], 'cleanup': {'status': 'review', 'total': 2,
            'root': '/private/user', 'groups': [{'id': 'g', 'name': '회의록', 'purpose': '회의 자료 모음',
            'status': 'pending', 'new_folder': True, 'hashes': {'a': 'secret-hash'},
            'files': [{'id': 'a', 'name': '/private/user/file.txt', 'text': 'secret body'}]}]}})['cleanup']
        self.assertEqual(result['groups'][0]['files'], [{'id': 'a', 'name': 'file.txt'}])
        for private in ('/private', 'secret-hash', 'secret body'):
            self.assertNotIn(private, str(result))

    def test_bulk_snapshot_is_bounded_but_counts_and_new_icloud_arrival_are_kept(self):
        files = [{'id': str(i), 'original': f'file-{i}.txt', 'why': ['긴 설명' * 300], 'received_at': i} for i in range(2000)]
        files.append({'id': 'phone', 'original': 'new-phone.png', 'received_at': 5000, 'source_kind': 'icloud'})
        result = public_state({'assets': files, 'catalog': []})
        self.assertEqual(result['counts']['files'], 2001)
        self.assertTrue(result['assets_truncated'])
        self.assertEqual(result['assets'][0]['id'], 'phone')
        import json
        self.assertLess(len(json.dumps(result, ensure_ascii=False).encode()), 751000)


class ServerUrlTests(unittest.TestCase):
    def test_plain_http_requires_explicit_loopback_mode(self):
        self.assertFalse(server_allowed('http://127.0.0.1:8000'))
        self.assertTrue(server_allowed('http://127.0.0.1:8000', True))
        self.assertTrue(server_allowed('http://localhost:8000', True))
        self.assertFalse(server_allowed('http://127.0.0.1.evil.example:8000', True))
        self.assertFalse(server_allowed('http://192.168.1.10:8000', True))
        self.assertFalse(server_allowed('http://localhost:8000/path', True))
        self.assertTrue(server_allowed('https://3.38.192.19'))


if __name__ == '__main__':
    unittest.main()
