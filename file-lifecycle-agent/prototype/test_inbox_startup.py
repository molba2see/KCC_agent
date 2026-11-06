from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from demo_v5 import Watcher


class InboxStartupTests(unittest.TestCase):
    def test_offline_arrivals_collected_but_previous_imports_skipped(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            inbox = base / 'icloud'
            inbox.mkdir()
            root = base / 'workspace'
            root.mkdir()
            first = inbox / 'first.txt'
            first.write_text('first')
            demo = SimpleNamespace(root=root)
            watcher = Watcher(demo, [str(inbox)], scan_existing=True)
            self.assertIn(first, [p for p, _ in watcher.candidates()])
            watcher.remember(first)
            second = inbox / 'offline.txt'
            second.write_text('arrived while offline')
            restarted = Watcher(demo, [str(inbox)], scan_existing=True)
            candidates = [p for p, _ in restarted.candidates()]
            self.assertNotIn(first, candidates)
            self.assertIn(second, candidates)
            first.write_text('changed since import')
            changed = Watcher(demo, [str(inbox)], scan_existing=True)
            self.assertIn(first, [p for p, _ in changed.candidates()])

    def test_screenshot_source_collects_images_only_and_rejects_symlinks(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); inbox = root / 'Desktop'; inbox.mkdir()
            image = inbox / 'Screenshot.png'; image.write_bytes(b'png')
            (inbox / 'private.txt').write_text('private')
            (inbox / 'link.png').symlink_to(image)
            watcher = Watcher(SimpleNamespace(root=root), [], screenshot_inboxes=[str(inbox)], scan_existing=True)
            self.assertEqual([p for p, _ in watcher.candidates()], [image])

    def test_default_preserves_future_only_behavior(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            inbox = root / 'inbox'
            inbox.mkdir()
            (inbox / 'existing.txt').write_text('existing')
            watcher = Watcher(SimpleNamespace(root=root), [str(inbox)])
            self.assertEqual(list(watcher.candidates()), [])
