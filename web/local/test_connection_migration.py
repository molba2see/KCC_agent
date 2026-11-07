import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from run import cloud_configuration


class ConnectionMigrationTests(unittest.TestCase):
    def test_legacy_domain_is_migrated_without_losing_token_or_rewriting_other_servers(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'cloud.json'
            path.write_text(json.dumps({'origin': 'https://moa.3-38-192-19.sslip.io', 'bridge_token': 'fixture-token'}))
            updated = cloud_configuration(path, 'https://3.38.192.19')
            self.assertEqual(updated, {'origin': 'https://3.38.192.19', 'bridge_token': 'fixture-token'})
            self.assertEqual(json.loads((path.parent / 'cloud-before-ip.json').read_text())['bridge_token'], 'fixture-token')
            modified = path.stat().st_mtime_ns
            cloud_configuration(path, 'https://3.38.192.19'); self.assertEqual(path.stat().st_mtime_ns, modified)
            path.write_text(json.dumps({'origin': 'https://other.example.com', 'bridge_token': 'other-token'}))
            self.assertEqual(cloud_configuration(path, 'https://3.38.192.19')['origin'], 'https://other.example.com')
