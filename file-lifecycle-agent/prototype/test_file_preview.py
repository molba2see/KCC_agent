from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from file_preview import preview
from lifecycle_v3 import Lifecycle


class FilePreviewTests(unittest.TestCase):
    def test_text_is_bounded_and_preview_never_changes_classification(self):
        with TemporaryDirectory() as directory:
            engine = Lifecycle(directory)
            path = Path(directory) / 'notes.txt'; path.write_text('회의 <script> 내용\n' * 2000)
            aid = engine.ingest('notes.txt')
            before = engine.db.read_bytes()
            result = preview(engine, aid)
            self.assertEqual(result['kind'], 'text')
            self.assertEqual(len(result['text']), 6000)
            self.assertTrue(result['truncated'])
            self.assertLess(len(json.dumps(result)), 50000)
            self.assertEqual(engine.db.read_bytes(), before)

    def test_unknown_missing_unsupported_and_outside_paths_are_rejected(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as outside:
            engine = Lifecycle(directory)
            with self.assertRaises(ValueError): preview(engine, 'unknown')
            path = Path(directory) / 'notes.txt'; path.write_text('notes')
            aid = engine.ingest('notes.txt'); path.unlink()
            with self.assertRaises(ValueError): preview(engine, aid)
            external = Path(outside) / 'private.txt'; external.write_text('private')
            path.symlink_to(external)
            with self.assertRaises(ValueError): preview(engine, aid)
            path.unlink(); path = Path(directory) / 'app.command'; path.write_text('echo private')
            aid = engine.ingest('app.command')
            with self.assertRaises(ValueError): preview(engine, aid)


if __name__ == '__main__': unittest.main()
