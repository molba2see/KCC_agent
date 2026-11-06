from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import threading
import unittest

from agent_v5 import doc_text
from demo_v5 import Watcher
from lifecycle_v3 import Lifecycle


class DownloadTrackingTests(unittest.TestCase):
    def test_pdf_readable_without_external_pdf_tools(self):
        from reportlab.pdfgen import canvas
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'AWS application.pdf'
            pdf = canvas.Canvas(str(path)); pdf.drawString(30, 700, 'AWS application development'); pdf.save()
            with patch('subprocess.run', side_effect=AssertionError('No external PDF programs')):
                self.assertIn('AWS application development', doc_text(path))

    def test_existing_download_is_ingested_once_and_original_is_preserved(self):
        with TemporaryDirectory() as temp:
            base = Path(temp); root = base / 'workspace'; root.mkdir()
            inbox = base / 'Downloads'; inbox.mkdir()
            file = inbox / 'AWS application.pdf'; file.write_bytes(b'fixture bytes')
            demo = SimpleNamespace(root=root, lock=threading.Lock(), engine=lambda: Lifecycle(root), sources={}, save_sources=lambda: None)
            watcher = Watcher(demo, [], strict_inboxes=[str(inbox)], scan_existing=True)
            watcher.tick()  # first size observation
            with patch('demo_v5.where_froms', return_value=[]):
                watcher.tick()  # stable download is copied and fingerprinted
            self.assertTrue(file.exists())
            self.assertEqual((root / 'screenshots' / file.name).read_bytes(), b'fixture bytes')
            restarted = Watcher(demo, [], strict_inboxes=[str(inbox)], scan_existing=True)
            self.assertNotIn(file, [p for p, _ in restarted.candidates()])

    def test_three_sources_with_identical_names_never_overwrite_staged_copies(self):
        with TemporaryDirectory() as temp:
            base = Path(temp); root = base / 'workspace'; root.mkdir()
            inboxes = []
            for index in range(3):
                inbox = base / f'source-{index}'; inbox.mkdir()
                (inbox / 'capture.png').write_bytes(f'capture-{index}'.encode())
                inboxes.append(str(inbox))
            demo = SimpleNamespace(root=root, lock=threading.Lock(), engine=lambda: Lifecycle(root), sources={}, save_sources=lambda: None)
            watcher = Watcher(demo, inboxes, scan_existing=True)
            watcher.tick()
            with patch('demo_v5.time.strftime', return_value='same-second'), patch('demo_v5.where_froms', return_value=[]):
                watcher.tick()
            copies = list((root / 'screenshots').glob('*.png'))
            self.assertEqual(len(copies), 3)
            self.assertEqual({copy.read_bytes() for copy in copies}, {b'capture-0', b'capture-1', b'capture-2'})

    def test_reimported_name_does_not_reuse_a_filed_assets_original_path(self):
        with TemporaryDirectory() as temp:
            base = Path(temp); root = base / 'workspace'; (root / 'screenshots').mkdir(parents=True)
            old = root / 'screenshots' / 'notes.txt'; old.write_text('previous file')
            engine = Lifecycle(root); previous_id = engine.ingest('screenshots/notes.txt')
            (root / 'archive').mkdir(); old.rename(root / 'archive' / 'notes.txt')
            engine.data['assets'][previous_id]['path'] = 'archive/notes.txt'; engine.save()
            inbox = base / 'Downloads'; inbox.mkdir(); (inbox / 'notes.txt').write_text('new file')
            demo = SimpleNamespace(root=root, lock=threading.Lock(), engine=lambda: Lifecycle(root), sources={}, save_sources=lambda: None)
            watcher = Watcher(demo, [str(inbox)], scan_existing=True); watcher.tick()
            with patch('demo_v5.where_froms', return_value=[]): watcher.tick()
            copied = next((root / 'screenshots').glob('*.txt'))
            self.assertNotEqual(copied, old)
            self.assertEqual(copied.read_text(), 'new file')
            self.assertNotEqual(Lifecycle(root).ingest(str(copied.relative_to(root))), previous_id)

    def test_repeated_ocr_captions_never_overwrite_another_copy(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); (root / 'screenshots').mkdir()
            demo = SimpleNamespace(root=root, ctl=None, engine=lambda: Lifecycle(root), sources={})
            watcher = Watcher(demo, [])
            paths = []
            with patch('demo_v5.content', return_value='회의 자료'), patch('demo_v5.make_caption', return_value='회의'):
                for index in range(3):
                    source = root / 'screenshots' / f'source-{index}.png'; source.write_bytes(f'image-{index}'.encode())
                    path, _ = watcher.rename(source); paths.append(path)
            self.assertEqual(len(set(paths)), 3)
            self.assertEqual({path.read_bytes() for path in paths}, {b'image-0', b'image-1', b'image-2'})

    def test_manifest_access_waits_for_http_state_lock(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); lock = threading.Lock(); touched = threading.Event()
            def engine():
                touched.set()
                return Lifecycle(root)
            demo = SimpleNamespace(root=root, lock=lock, engine=engine)
            watcher = Watcher(demo, [], scan_existing=True)
            with lock:
                worker = threading.Thread(target=watcher.tick); worker.start()
                self.assertFalse(touched.wait(.05))
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
            self.assertTrue(touched.is_set())
