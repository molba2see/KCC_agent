"""Local lifecycle experiment. Rules are explicit; no remote model or personal folders."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = Path(__file__).resolve().parent
KST = timezone(timedelta(hours=9))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extract(path):
    path = Path(path)
    if path.suffix.lower() == '.pdf':
        result = subprocess.run(['pdftotext', '-layout', str(path), '-'], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise ValueError('PDF 읽기 실패: ' + result.stderr[:200])
        if len(result.stdout.strip()) > 25:
            return result.stdout, 'pdf_text', []
        with tempfile.TemporaryDirectory() as folder:
            prefix = str(Path(folder) / 'page')
            subprocess.run(['pdftoppm', '-scale-to', '1800', '-png', str(path), prefix], check=True, capture_output=True, timeout=60)
            texts, evidence = [], []
            for page, image in enumerate(sorted(Path(folder).glob('page-*.png')), 1):
                t, _, rows = extract(image)
                texts.append(t)
                evidence.extend(dict(row, page=page) for row in rows)
            return '\n'.join(texts), 'pdf_ocr', evidence
    result = subprocess.run([str(HERE / 'bin/ocr'), str(path)], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise ValueError(result.stderr[:250])
    rows = json.loads(result.stdout)
    return '\n'.join(row['text'] for row in rows), 'vision_ocr', rows


def understand(text):
    """Small deterministic baseline: no hidden fixture names or gold labels used."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError('읽을 수 있는 텍스트 없음')
    category = 'unclassified'
    if re.search('영수증|결제 증빙|신청 완료 확인서', text):
        category = 'receipt'
    elif re.search('과제|참고자료|강의', text):
        category = 'reference'
    elif re.search('신청|접수|공모전|행사|쿠폰', text):
        category = 'event' if re.search('신청|접수|공모전|행사(?!가 아닙니다)|쿠폰', text) else 'unclassified'
    title = lines[0]
    key = re.sub(r'\s+', '', title).casefold()
    dates = []
    date_re = r'(20\d{2})\s*[년.\-/]\s*(\d{1,2})\s*[월.\-/]\s*(\d{1,2})\s*일?'
    reasons = []
    for line in lines:
        if not re.search('접수|제출|사용 기한|마감|유효기간', line):
            continue
        if not re.search(r'\d|내일|오늘|모레|다음|미정', line):
            continue
        match = re.search(date_re, line)
        if not match:
            reasons.append('연도 또는 절대 날짜 확인 필요: ' + line)
            continue
        clock = re.search(r'(\d{1,2})\s*(?:시|:)\s*(?:(\d{1,2})\s*분?)?', line[match.end():])
        if not clock:
            reasons.append('마감 시각 확인 필요: ' + line)
            continue
        try:
            hour, minute = int(clock[1]), int(clock[2] or 0)
            if '오후' in line and hour < 12:
                hour += 12
            if '오전' in line and hour == 12:
                hour = 0
            value = datetime(*map(int, match.groups()), hour, minute, tzinfo=KST).isoformat()
            dates.append({'value': value, 'quote': line, 'kind': 'action_deadline'})
        except ValueError:
            reasons.append('유효하지 않은 날짜: ' + line)
    if len({d['value'] for d in dates}) > 1:
        reasons.append('서로 다른 행동 기한 확인 필요')
    if category == 'unclassified':
        reasons.append('목적 분류 확인 필요')
    if category == 'receipt':
        dates = []
    return dict(category=category, title=title, bundle_key=key, deadline=dates[0]['value'] if dates and not reasons else None,
                evidence=dates, review=reasons, is_update=bool(re.search('기한 변경|마감 연장|접수 연장', text)))


class Engine:
    def __init__(self, root):
        self.root = Path(root).resolve()
        settings_path = self.root / 'pipeline.json'
        self.settings = json.loads(settings_path.read_text()) if settings_path.exists() else {'extractor':'legacy'}
        for name in ['downloads', 'screenshots', 'archive']:
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / 'state.sqlite')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS assets(id INTEGER PRIMARY KEY, hash TEXT UNIQUE, path TEXT, original_path TEXT,
          title TEXT, category TEXT, bundle_id INTEGER, state TEXT, text TEXT, method TEXT, details TEXT, keep INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS bundles(id INTEGER PRIMARY KEY, key TEXT UNIQUE, title TEXT, state TEXT DEFAULT 'waiting',
          deadline TEXT, version INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY, bundle_id INTEGER, version INTEGER, due TEXT, status TEXT);
        CREATE UNIQUE INDEX IF NOT EXISTS one_active ON reminders(bundle_id) WHERE status='active';
        CREATE TABLE IF NOT EXISTS locations(hash TEXT, path TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS moves(id INTEGER PRIMARY KEY, asset_id INTEGER, source TEXT, target TEXT, hash TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, kind TEXT, detail TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS bundle_entities(bundle_id INTEGER PRIMARY KEY, identity TEXT NOT NULL);
        ''')
        self.db.commit()

    def event(self, kind, detail):
        self.db.execute('INSERT INTO events(kind,detail,created) VALUES(?,?,?)',
                        (kind, json.dumps(detail, ensure_ascii=False), datetime.now(KST).isoformat()))

    def allowed(self, path):
        p = Path(path)
        if p.is_symlink():
            raise ValueError('심볼릭 링크는 실험 대상에서 제외')
        p = p.resolve()
        if not any(p.is_relative_to(self.root / name) for name in ['downloads', 'screenshots', 'archive']):
            raise ValueError('실험 폴더 밖의 경로')
        return p

    def plan(self, bundle_id, deadline):
        self.db.execute("UPDATE reminders SET status='cancelled' WHERE bundle_id=? AND status='active'", (bundle_id,))
        self.db.execute('UPDATE bundles SET deadline=?,version=version+1 WHERE id=?', (deadline, bundle_id))
        bundle = self.db.execute('SELECT * FROM bundles WHERE id=?', (bundle_id,)).fetchone()
        if deadline and bundle['state'] != 'completed':
            due = (datetime.fromisoformat(deadline) - timedelta(days=1)).isoformat()
            status = 'expired' if datetime.fromisoformat(deadline) <= datetime.now(KST) else 'active'
            self.db.execute('INSERT INTO reminders(bundle_id,version,due,status) VALUES(?,?,?,?)', (bundle_id, bundle['version'], due, status))

    def ingest(self, path):
        path = self.allowed(path)
        # Two identical stats guard against common in-progress downloads; polling retries later.
        before = (path.stat().st_size, path.stat().st_mtime_ns)
        time.sleep(.12)
        if before != (path.stat().st_size, path.stat().st_mtime_ns):
            return {'status': 'unstable'}
        sha = digest(path)
        old = self.db.execute('SELECT id FROM assets WHERE hash=?', (sha,)).fetchone()
        if old:
            self.db.execute('INSERT OR IGNORE INTO locations VALUES(?,?)', (sha, str(path)))
            self.db.commit()
            return {'status': 'duplicate', 'id': old['id']}
        started = time.monotonic()
        try:
            text, method, rows = extract(path)
            if self.settings.get('extractor') == 'legacy':
                info = understand(text)
            else:
                from pipeline_v2 import analyze
                info = analyze(text, self.settings)
            info['ocr_rows'] = rows
        except Exception as exc:
            text, method, info = '', 'failed', dict(title=path.name, category='unclassified', bundle_key='failed:'+sha,
                deadline=None, evidence=[], review=[str(exc)], is_update=False)
        info['elapsed_ms'] = round((time.monotonic() - started) * 1000)
        bundle_id = None
        if info.get('identity'):
            from pipeline_v2 import resolve_bundle
            known = [dict(id=r['bundle_id'],identity=json.loads(r['identity'])) for r in self.db.execute('SELECT * FROM bundle_entities')]
            bundle_id, key = resolve_bundle(info,known,sha)
            if key: info['bundle_key']=key
        if bundle_id is None:
            self.db.execute('INSERT OR IGNORE INTO bundles(key,title) VALUES(?,?)', (info['bundle_key'], info.get('identity',{}).get('event_name') or info['title']))
            bundle = self.db.execute('SELECT * FROM bundles WHERE key=?', (info['bundle_key'],)).fetchone()
            if info.get('identity'):
                self.db.execute('INSERT OR IGNORE INTO bundle_entities VALUES(?,?)',(bundle['id'],json.dumps(info['identity'],ensure_ascii=False)))
        else:
            bundle = self.db.execute('SELECT * FROM bundles WHERE id=?',(bundle_id,)).fetchone()
        pending = info['is_update'] or bool(bundle['deadline'] and info['deadline'] and bundle['deadline'] != info['deadline'])
        info['pending_update'] = pending
        if pending:
            info['review'].append('기한 변경 확인·승인 필요')
        state = 'review' if info['review'] else ('completed' if bundle['state'] == 'completed' else 'waiting')
        cur = self.db.execute('INSERT INTO assets(hash,path,original_path,title,category,bundle_id,state,text,method,details) VALUES(?,?,?,?,?,?,?,?,?,?)',
           (sha, str(path), str(path), info['title'], info['category'], bundle['id'], state, text, method, json.dumps(info, ensure_ascii=False)))
        self.db.execute('INSERT OR IGNORE INTO locations VALUES(?,?)', (sha, str(path)))
        if info['deadline'] and not pending and not info['review'] and not bundle['deadline']:
            self.plan(bundle['id'], info['deadline'])
        self.event('ingest', {'asset_id': cur.lastrowid, 'method': method, 'review': info['review']})
        self.db.commit()
        return {'status': 'created', 'id': cur.lastrowid, 'method': method}

    def scan(self):
        results = []
        for folder in ['downloads', 'screenshots']:
            for path in sorted((self.root / folder).iterdir()):
                if path.is_file() and not path.is_symlink() and path.suffix.lower() in ['.pdf','.png','.jpg','.jpeg']:
                    try:
                        results.append(dict(file=path.name, **self.ingest(path)))
                    except Exception as exc:
                        results.append(dict(file=path.name, status='error', error=str(exc)))
        return results

    def action(self, asset_id, action):
        a = self.db.execute('SELECT * FROM assets WHERE id=?', (asset_id,)).fetchone()
        if not a:
            raise ValueError('자료가 없습니다')
        b = self.db.execute('SELECT * FROM bundles WHERE id=?', (a['bundle_id'],)).fetchone()
        info = json.loads(a['details'])
        if action == 'approve_update':
            if not info['pending_update'] or not info['deadline']:
                raise ValueError('확인 가능한 기한 변경이 없습니다')
            if any(r != '기한 변경 확인·승인 필요' for r in info['review']):
                raise ValueError('기한 변경 외에 미확인 정보가 있습니다. 먼저 검토해주세요.')
            self.plan(b['id'], info['deadline'])
            info['pending_update'] = False
            info['review'] = [r for r in info['review'] if r != '기한 변경 확인·승인 필요']
            self.db.execute('UPDATE assets SET state=?,details=? WHERE id=?',
                ('review' if info['review'] else 'waiting', json.dumps(info,ensure_ascii=False), a['id']))
        elif action == 'complete':
            if a['state'] == 'review':
                raise ValueError('미확인 정보를 먼저 검토해주세요')
            self.db.execute("UPDATE bundles SET state='completed' WHERE id=?", (b['id'],))
            self.db.execute("UPDATE assets SET state='completed' WHERE bundle_id=? AND state NOT IN ('archived','review')", (b['id'],))
            self.db.execute("UPDATE reminders SET status='cancelled' WHERE bundle_id=? AND status='active'", (b['id'],))
        elif action == 'snooze':
            if b['state'] == 'completed':
                raise ValueError('완료된 작업은 미룰 수 없습니다')
            active = self.db.execute("SELECT * FROM reminders WHERE bundle_id=? AND status='active'", (b['id'],)).fetchone()
            if not active:
                raise ValueError('미룰 알림이 없습니다')
            due = datetime.fromisoformat(active['due']) + timedelta(hours=6)
            if due >= datetime.fromisoformat(b['deadline']):
                raise ValueError('마감 뒤로 미룰 수 없습니다')
            self.db.execute('UPDATE reminders SET due=? WHERE id=?', (due.isoformat(), active['id']))
        elif action == 'keep':
            self.db.execute('UPDATE assets SET keep=1 WHERE id=?', (a['id'],))
        elif action == 'archive':
            if a['state'] != 'completed' or a['keep'] or a['category'] == 'receipt':
                raise ValueError('완료된 정리 후보만 보관 이동할 수 있습니다. 증빙·유지 자료는 제외됩니다.')
            source = self.allowed(a['path'])
            target = self.allowed(self.root / 'archive' / source.name)
            if target.exists():
                raise ValueError('보관 위치에 같은 이름이 있습니다. 덮어쓰지 않습니다.')
            if not source.exists() or digest(source) != a['hash']:
                raise ValueError('원본이 없거나 변경되었습니다. 다시 수집해주세요.')
            cur = self.db.execute("INSERT INTO moves(asset_id,source,target,hash,status) VALUES(?,?,?,?,'planned')", (a['id'], str(source), str(target), a['hash']))
            move_id = cur.lastrowid
            self.db.commit()
            # Hard link reserves the destination atomically and refuses overwrite.
            # All experimental folders live on the same local filesystem.
            try:
                target.hardlink_to(source)
                if digest(target) != a['hash']:
                    raise ValueError('이동 후 해시 불일치')
                source.unlink()
            except Exception:
                if source.exists() and target.exists() and digest(target) == a['hash']:
                    target.unlink()
                self.db.execute("UPDATE moves SET status='failed' WHERE id=?", (move_id,))
                self.db.commit()
                raise
            self.db.execute("UPDATE assets SET path=?,state='archived' WHERE id=?", (str(target), a['id']))
            self.db.execute("UPDATE moves SET status='done' WHERE id=?", (move_id,))
        elif action == 'undo':
            move = self.db.execute("SELECT * FROM moves WHERE asset_id=? AND status='done' ORDER BY id DESC LIMIT 1", (a['id'],)).fetchone()
            if not move:
                raise ValueError('되돌릴 이동이 없습니다')
            source, target = self.allowed(move['source']), self.allowed(move['target'])
            if source.exists():
                raise ValueError('원래 위치가 사용 중입니다. 덮어쓰지 않습니다.')
            if not target.exists() or digest(target) != move['hash']:
                raise ValueError('보관 파일이 없거나 변경되었습니다')
            source.hardlink_to(target)
            target.unlink()
            self.db.execute("UPDATE assets SET path=?,state='completed' WHERE id=?", (str(source), a['id']))
            self.db.execute("UPDATE moves SET status='undone' WHERE id=?", (move['id'],))
        else:
            raise ValueError('지원하지 않는 동작')
        self.event(action, {'asset_id': a['id'], 'bundle_id': b['id']})
        self.db.commit()

    def dispatch(self, now):
        """Experiment inbox, not OS notifications. Clock is explicitly supplied."""
        self.db.execute("UPDATE reminders SET status='expired' WHERE status='active' AND bundle_id IN (SELECT id FROM bundles WHERE deadline<=?)", (now.isoformat(),))
        rows = self.db.execute("SELECT r.* FROM reminders r JOIN bundles b ON b.id=r.bundle_id WHERE r.status='active' AND r.due<=? AND r.version=b.version AND b.state!='completed'", (now.isoformat(),)).fetchall()
        for row in rows:
            self.event('reminder_delivered', dict(row))
            self.db.execute("UPDATE reminders SET status='delivered' WHERE id=?", (row['id'],))
        self.db.commit()
        return len(rows)

    def snapshot(self, query=''):
        assets = [dict(r) for r in self.db.execute('SELECT a.*,b.title AS bundle_title,b.deadline,b.state AS task_state FROM assets a JOIN bundles b ON a.bundle_id=b.id ORDER BY a.id DESC')]
        if query:
            terms = query.casefold().split()
            assets = [a for a in assets if all(t in (a['text']+a['title']).casefold() for t in terms)]
        for a in assets:
            a['details'] = json.loads(a['details'])
            a['cleanup_candidate'] = a['state'] == 'completed' and not a['keep'] and a['category'] != 'receipt'
        return dict(root=str(self.root), pipeline=self.settings, assets=assets,
          bundles=[dict(r) for r in self.db.execute('SELECT * FROM bundles')],
          reminders=[dict(r) for r in self.db.execute('SELECT * FROM reminders ORDER BY id DESC')],
          moves=[dict(r) for r in self.db.execute('SELECT * FROM moves')],
          events=[dict(r) for r in self.db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 40')])


def serve(root, port):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, payload, status=200):
            body = json.dumps(payload,ensure_ascii=False).encode()
            self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8')
            self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            from urllib.parse import urlparse,parse_qs
            url = urlparse(self.path)
            if url.path == '/api/state':
                engine = Engine(root)
                try: self.respond(engine.snapshot(parse_qs(url.query).get('q',[''])[0]))
                finally: engine.db.close()
            elif url.path == '/api/report':
                p = Path(root) / 'report.json'
                self.respond(json.loads(p.read_text()) if p.exists() else {})
            elif url.path == '/api/comparison':
                p = Path(root) / 'comparison.json'
                self.respond(json.loads(p.read_text()) if p.exists() else {})
            elif url.path in ['/pipeline','/pipeline.svg','/analysis']:
                names={'/pipeline':'임시자료_파이프라인_v2.html','/pipeline.svg':'임시자료_파이프라인_v2.svg','/analysis':'파이프라인_v2_분석.md'}
                file=HERE.parent/'deliverables'/names[url.path]
                if not file.exists(): return self.send_error(404)
                body=file.read_text().replace('http://127.0.0.1:8765',f'http://127.0.0.1:{port}')
                if url.path=='/pipeline':
                    body=body.replace('href="임시자료_파이프라인_v2.svg"','href="/pipeline.svg"').replace('href="파이프라인_v2_분석.md"','href="/analysis"')
                mime={'/pipeline':'text/html','/pipeline.svg':'image/svg+xml','/analysis':'text/plain'}[url.path]
                self.send_response(200);self.send_header('Content-Type',mime+'; charset=utf-8');self.end_headers();self.wfile.write(body.encode())
            elif url.path == '/':
                self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers()
                self.wfile.write((HERE/'index.html').read_bytes())
            else: self.send_error(404)
        def do_POST(self):
            if self.headers.get('Origin') not in [None, f'http://127.0.0.1:{port}', f'http://localhost:{port}']:
                return self.respond({'error':'외부 origin 거부'},403)
            engine = Engine(root)
            try:
                data=json.loads(self.rfile.read(min(int(self.headers.get('Content-Length',0)),10000)) or '{}')
                if self.path == '/api/scan': result=engine.scan()
                elif self.path == '/api/action': engine.action(int(data['id']),data['action']); result='ok'
                else: return self.respond({'error':'unknown endpoint'},404)
                self.respond({'result':result})
            except Exception as exc: self.respond({'error':str(exc)},400)
            finally: engine.db.close()
        def log_message(self, *args): pass
    print(f'Local demo: http://127.0.0.1:{port}', flush=True)
    print(f'Experimental root: {root}', flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['scan','watch','serve']);p.add_argument('--root',required=True);p.add_argument('--port',type=int,default=8765)
    args=p.parse_args()
    if args.command=='serve': serve(args.root,args.port)
    elif args.command=='scan':
        e=Engine(args.root); print(json.dumps(e.scan(),ensure_ascii=False,indent=2))
    else:
        while True:
            e=Engine(args.root)
            try:
                changes=[r for r in e.scan() if r['status']!='duplicate']
                if changes: print(json.dumps(changes,ensure_ascii=False),flush=True)
            finally: e.db.close()
            time.sleep(2)
