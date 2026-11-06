"""v5 demo: agent proposes, user approves, executor moves, undo restores.
usage: python demo_v5.py [--root DIR] [--port 8765] [--qwen /path/to/Qwen3-8B]
Trigger: --watch analyzes new files in <root>/downloads and <root>/screenshots and sends a macOS notification;
add --inbox ~/Desktop to copy new screenshots in (originals are never moved). Images need bin/ocr: swiftc -O ocr.swift -o bin/ocr
Without --qwen the deterministic rule controller drives the same tools (no GPU needed).
On the GPU server run with --qwen and open it through `ssh -L 8765:localhost:8765 ...`."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import argparse, json, random, shutil, subprocess, threading, time
from lifecycle_v3 import Lifecycle
from agent_v5 import ToolHostV5, run, rule_controller, content, TEXT, IMAGE, WEIGHTS, CHUNK
from tasks_v5 import CATALOG, SHARED, FILLER, INJECT, NOISE_TEXT

HERE = Path(__file__).resolve().parent
MARK = '.demo_seed'  # reset only ever deletes a folder this script created
STATUS = {'DACON_PORT_2026': 'active', 'DACON_PORT_2025': 'completed', 'SAR_SHIP': 'completed',
          'SAR_OIL': 'completed', 'KCC_AGENT': 'active', 'CV_CLASS': 'completed'}
CAT = {k: {'name': v['name'], 'desc': v['desc']} for k, v in CATALOG.items() if k in STATUS}


def seed(root):
    """One folder with the eight situations the agent must handle."""
    root = Path(root)
    if root.exists():
        if not (root / MARK).exists(): raise SystemExit(f'{root} exists and was not created by the demo; refusing to touch it')
        shutil.rmtree(root)
    root.mkdir(parents=True); (root / MARK).write_text('created by demo_v5.py\n')
    e = Lifecycle(root); e.data['projects'].update(STATUS)
    # Registered context: configs already attributed to their projects.
    ctx = {'configs/port26_fold0.yaml': ('DACON_PORT_2026', 'ckpt/port26_fold0.pth'),
           'configs/sarship_train.yaml': ('SAR_SHIP', 'ckpt/sarship_seed1.pth')}
    for rel, (pid, ref) in ctx.items():
        p = root / rel; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f'project: {CATALOG[pid]["name"]}\nlr: 0.001\nREF: {ref}\n')
        e.data['assets'][e.ingest(rel)].update(project=pid, refs=[ref], context=True)
    rng = random.Random(3)
    inbox = {
        'downloads/memo.txt': f'실험 메모\nproject_id: KCC_AGENT\n{FILLER}',
        'notes/실험노트.md': FILLER + '\n' + CATALOG['SAR_SHIP']['sem'][0],
        'downloads/안내.txt': SHARED[('DACON_PORT_2026', 'DACON_PORT_2025')],
        'downloads/scan.md': NOISE_TEXT[2],
        'ckpt/port26_fold0.pth': None,
        'ckpt/model_best.pth': None,
        'downloads/회의록.md': FILLER * 16 + '\n' + CATALOG['CV_CLASS']['sem'][1] + '\n',
        'downloads/forwarded.txt': CATALOG['SAR_OIL']['sem'][0] + INJECT,
    }
    for rel, body in inbox.items():
        p = root / rel; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(rng.randbytes(2048)) if body is None else p.write_text(body)
        e.ingest(rel)
    e.save()


PARTIAL = {'.crdownload', '.download', '.part', '.tmp'}
WATCH_DIRS = ['downloads', 'screenshots']  # inside the demo root; the executor never leaves the root


def notify(title, text):
    # argv, not string interpolation: file names are untrusted.
    subprocess.run(['osascript', '-e', 'on run argv', '-e', 'display notification (item 2 of argv) with title (item 1 of argv)',
                    '-e', 'end run', title, text], capture_output=True, timeout=10)


class Watcher(threading.Thread):
    """Trigger: a new file in a watched folder is ingested and analyzed, then the user is notified.
    --inbox folders (e.g. ~/Desktop for screenshots) are copied in, never moved: user originals stay untouched."""
    def __init__(self, demo, inboxes, interval=2.0):
        super().__init__(daemon=True); self.d = demo; self.inboxes = [Path(x).expanduser() for x in inboxes]; self.interval = interval
        self.sizes = {}
        self.seen = {p for x in self.inboxes for p in x.glob('*')}  # only files that appear after start

    def candidates(self):
        for x in self.inboxes:
            for p in x.glob('*'):
                if p not in self.seen and p.is_file() and not p.name.startswith('.') and p.suffix.lower() in TEXT | IMAGE | WEIGHTS:
                    yield p, self.d.root / 'screenshots' / p.name
        for sub in WATCH_DIRS:
            for p in (self.d.root / sub).glob('*'):
                if p.is_file() and not p.name.startswith('.'): yield p, None

    def stable(self, p):
        # Wait until the size stops changing (downloads and screenshots are written in pieces).
        n = p.stat().st_size; prev = self.sizes.get(p); self.sizes[p] = n
        return prev == n and n > 0 and p.suffix.lower() not in PARTIAL

    def tick(self):
        known = {a['original'] for a in self.d.engine().data['assets'].values()}
        for p, copy_to in list(self.candidates()):
            if not self.stable(p): continue
            if copy_to:
                self.seen.add(p)
                if p.stat().st_size > 50 << 20 or copy_to.exists(): continue  # shortcut: skips >50MB and name clashes
                copy_to.parent.mkdir(exist_ok=True); shutil.copy2(p, copy_to); continue  # analyzed on the next tick
            rel = str(p.relative_to(self.d.root))
            if rel in known: continue
            with self.d.lock:
                aid = self.d.engine().ingest(rel)
                try: r = self.d.analyze(aid); r['trigger'] = 'watch'; self.d.save_runs()
                except Exception as exc: r = {'status': f'error: {exc}', 'project': None}
                a = self.d.engine().data['assets'][aid]; plan = self.d.engine().plan(aid) if a['project'] else None
                text = (f'{r["project"]} 자료 · ' + {'archive': '보관 권장', 'keep': '유지 권장', 'defer': '보류'}[plan['action']]) if plan \
                    else '어느 프로젝트인지 확인이 필요해요' if r['status'] == 'waiting_user' else str(r['status'])
                self.d.events.append({'path': rel, 'text': text}); self.d.events = self.d.events[-20:]; self.d.version += 1
            notify(f'새 파일: {p.name}', text)

    def run(self):
        for sub in WATCH_DIRS: (self.d.root / sub).mkdir(exist_ok=True)
        while True:
            try: self.tick()
            except Exception as exc: print('watcher:', exc, flush=True)
            time.sleep(self.interval)


class Demo:
    def __init__(self, root, controller, name):
        self.root = Path(root); self.ctl = controller; self.name = name
        self.runs_path = self.root / 'agent_runs.json'
        self.runs = json.loads(self.runs_path.read_text()) if self.runs_path.exists() else {}
        self.lock = threading.Lock()  # HTTP handler and watcher share the manifest and the model
        self.version = 0; self.events = []; self.watching = False  # watcher activity the page polls for

    def engine(self): return Lifecycle(self.root)
    def save_runs(self): self.runs_path.write_text(json.dumps(self.runs, ensure_ascii=False, indent=1))

    def state(self):
        e = self.engine(); assets = []
        for a in e.data['assets'].values():
            if a.get('context'): continue
            r = self.runs.get(a['id'])
            plan = e.plan(a['id']) if a['project'] or a['keep'] else None
            assets.append({'id': a['id'], 'path': a['path'], 'original': a['original'], 'project': a['project'],
                           'keep': a['keep'], 'archived': a['path'] != a['original'], 'plan': plan, 'run': r,
                           'why': explain(e, a, r, plan) if r else []})
        assets.sort(key=lambda x: x['original'])
        return {'controller': self.name, 'root': str(self.root), 'assets': assets, 'journal': e.data['journal'][-20:],
                'catalog': [{'id': k, **v, 'status': e.data['projects'].get(k)} for k, v in CAT.items()]}

    def analyze(self, aid):
        e = self.engine(); a = e.data['assets'][aid]
        if a['path'] != a['original']: raise ValueError('이미 보관된 파일입니다. 먼저 되돌리세요.')
        a.update(project=None, keep=False, reason=None); e.save()
        host = ToolHostV5(e, aid, CAT)
        rec = run(host, self.ctl)
        last = lambda tool: next((h for h in reversed(rec['trace']) if h['tool'] == tool and 'error' not in h['result']), None)
        ask, assign = last('ask_user'), last('assign_project')
        self.runs[aid] = {
            'status': rec['status'], 'project': host.assigned, 'steps': rec['steps'], 'errors': rec['invalid_calls'],
            'seconds': round(rec['elapsed_ms'] / 1000, 1),
            'evidence': assign and assign['result'].get('evidence', assign['arguments']['evidence']),
            'question': ask and ask['arguments']['question'], 'candidates': ask and ask['arguments']['candidate_ids'],
            'trace': [{'tool': h['tool'], 'arguments': h['arguments'],
                       'result': h['result'].get('error') and ('오류: ' + h['result']['error']) or _brief(h['result'])}
                      for h in rec['trace']],
            'stats': {k: v for k, v in rec['stats'].items() if v},
            'full': [{'tool': h['tool'], 'arguments': h['arguments'], 'result': h['result']} for h in rec['trace'] if h['tool'] and 'error' not in h['result'] and h['tool'] != 'read_content']}
        self.save_runs(); return self.runs[aid]

    def answer(self, aid, pid):
        if pid not in CAT: raise ValueError('알 수 없는 프로젝트')
        e = self.engine(); a = e.data['assets'][aid]
        a.update(project=pid, reason='user answer'); e.save()
        self.runs.setdefault(aid, {})['answered'] = pid; self.save_runs()

    def keep(self, aid):
        e = self.engine(); e.data['assets'][aid]['keep'] = True; e.save()

    def approve(self, aid, plan):
        # execute() re-plans and refuses if anything changed since the user saw the plan.
        return self.engine().execute(aid, plan)

    def undo(self, aid): self.engine().undo(aid)


STATUS_KO = {'active': '진행 중', 'completed': '완료'}
PLAN_KO = {'archive': '보관 권장', 'keep': '유지 권장', 'defer': '보류'}


def explain(e, a, r, plan):
    """Reasoning steps built only from what the tools actually returned (no invented evidence)."""
    out, full = [], {h['tool']: h for h in r.get('full', [])}
    ev = r.get('evidence')
    if ev:
        text = content(e.path(a['path'])) if Path(a['path']).suffix.lower() in TEXT | IMAGE else ''
        line = next((i for i, l in enumerate(text.splitlines(), 1) if ev in l), None)
        if line:
            pos = text.find(ev); page = pos // CHUNK + 1
            out.append(f'대상 파일 {line}번째 줄, {pos:,}번째 글자 근처(읽기 {page}페이지)에 근거 문장이 있음: "{ev}"')
        rel = full.get('find_related_files')
        for f in (rel['result'].get('files', []) if rel else []):
            if any(ev in l for l in f['matching_lines']):
                out.append(f'관련 파일 {f["path"]}이 이 파일을 언급함: "{ev}" → 그 파일의 프로젝트는 {f["project_id"]} ({STATUS_KO.get(f["project_status"], f["project_status"])})')
        if not out: out.append(f'근거 문장: "{ev}"')
    s = full.get('search_projects')
    if s and 'candidates' in s['result']:
        c = s['result']['candidates']
        out.append('프로젝트 검색 결과: ' + (', '.join(f'{x["project_id"]}(일치 {x["score"]})' for x in c) if c else '일치하는 프로젝트 없음'))
    rel = full.get('find_related_files')
    if rel and not rel['result'].get('files'): out.append('이 파일을 언급하는 등록된 설정·로그 파일 없음')
    cr = full.get('check_references')
    if cr:
        refs = cr['result'].get('referenced_by', [])
        out.append('참조 확인: ' + ('; '.join(f'{x["path"]}({x["project_id"]}, {STATUS_KO.get(x["project_status"], x["project_status"])})가 이 파일을 참조' for x in refs) if refs else '이 파일을 참조하는 등록 파일 없음'))
    if a['project']:
        st = e.data['projects'].get(a['project'])
        out.append(f'프로젝트 {a["project"]} 상태: {STATUS_KO.get(st, st)}' + (' (사용자 답변)' if r.get('answered') else ''))
    if r.get('status') == 'waiting_user' and not a['project']:
        c = r.get('candidates') or []
        out.append('판단: ' + (f'근거가 {", ".join(c)} 중 하나로 좁혀지지 않아 사용자에게 질문' if len(c) > 1 else '프로젝트를 정할 근거가 없어 사용자에게 질문'))
    if plan:
        out.append(f'결론: {PLAN_KO[plan["action"]]}')
    return out


def _brief(r):
    s = json.dumps(r, ensure_ascii=False)
    return s if len(s) <= 220 else s[:220] + '…'


def serve(demo, port):
    page = (HERE / 'demo_v5.html').read_bytes()

    class H(BaseHTTPRequestHandler):
        def reply(self, obj, code=200):
            b = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code); self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            if self.path == '/':
                self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.end_headers(); self.wfile.write(page)
            elif self.path == '/api/state':
                with demo.lock: self.reply(demo.state())
            elif self.path == '/api/events': self.reply({'version': demo.version, 'events': demo.events, 'watch': demo.watching})
            else: self.send_error(404)

        def do_POST(self):
            try:
                d = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
                aid = d.get('id')
                with demo.lock:
                    if self.path == '/api/analyze': out = demo.analyze(aid)
                    elif self.path == '/api/answer': out = demo.answer(aid, d.get('project_id'))
                    elif self.path == '/api/keep': out = demo.keep(aid)
                    elif self.path == '/api/approve': out = demo.approve(aid, d.get('plan'))
                    elif self.path == '/api/undo': out = demo.undo(aid)
                    elif self.path == '/api/reset': seed(demo.root); demo.runs = {}; demo.events = []; out = 'reset'
                    else: return self.send_error(404)
                self.reply({'ok': True, 'result': out})
            except Exception as exc:
                self.reply({'ok': False, 'error': f'{type(exc).__name__}: {exc}'}, 400)

        def log_message(self, *a): pass

    # Single-threaded server; demo.lock serializes it with the watcher thread (manifest is a JSON file without locking).
    print(f'http://localhost:{port}  ({demo.name}, {demo.root})', flush=True)
    HTTPServer(('127.0.0.1', port), H).serve_forever()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=str(HERE.parent / 'demo_workspace'))
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--qwen', help='HF model dir; omit to use the rule controller')
    ap.add_argument('--adapter', help='LoRA adapter dir for --qwen')
    ap.add_argument('--watch', action='store_true', help='trigger: analyze new files in <root>/downloads and <root>/screenshots')
    ap.add_argument('--inbox', action='append', default=[], help='with --watch: copy new files from this folder in (e.g. ~/Desktop for screenshots)')
    a = ap.parse_args()
    if not (Path(a.root) / 'manifest.json').exists(): seed(a.root)
    if a.qwen:
        from qwen_tool_controller import QwenToolController
        from agent_v5 import SPECS, SYSTEM
        ctl, name = QwenToolController(a.qwen, specs=SPECS, system=SYSTEM, adapter=a.adapter), 'Qwen3 native tool calling: ' + Path(a.qwen).name
    else:
        ctl, name = rule_controller, '규칙 controller (GPU 없이 실행)'
    demo = Demo(a.root, ctl, name); demo.watching = a.watch
    if a.watch: Watcher(demo, a.inbox).start()
    serve(demo, a.port)
