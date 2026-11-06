import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from build_helper import ROOT, source_archive, source_files


class HelperDistributionTests(unittest.TestCase):
    def test_payload_has_runtime_and_no_local_state_or_recursive_downloads(self):
        paths = {str(path.relative_to(ROOT)) for path in source_files()}
        for required in ['web/local/run.py', 'web/local/install.py', 'web/local/folder_guides.py',
                         'web/local/requirements-qwen.txt', 'web/local/batch_proposals.py',
                         'file-lifecycle-agent/prototype/initial_cleanup.py', 'web/backend/manage.py',
                         'web/bridge/mac_bridge.py', 'file-lifecycle-agent/prototype/demo_v5.py',
                         'file-lifecycle-agent/prototype/agent_specs/system_v5.md', 'web/THIRD_PARTY_NOTICES.md']:
            self.assertIn(required, paths)
        for path in paths:
            self.assertNotIn('/downloads/', path)
            self.assertNotIn('.venv', path)
            self.assertFalse(path.endswith(('db.sqlite3', '.p8', '.pem', '.env', 'credentials.json', 'cloud.json', 'local-key')))
        with tempfile.TemporaryDirectory() as directory:
            ocr = Path(directory) / 'ocr'
            ocr.write_bytes(b'test executable')
            ocr.chmod(0o755)
            with tarfile.open(fileobj=io.BytesIO(source_archive(ocr)), mode='r:gz') as archive:
                binary = archive.getmember('file-lifecycle-agent/prototype/bin/ocr')
                self.assertTrue(binary.mode & 0o111)
                self.assertFalse(any(item.name.startswith('/') or '..' in Path(item.name).parts for item in archive.getmembers()))


if __name__ == '__main__':
    unittest.main()
