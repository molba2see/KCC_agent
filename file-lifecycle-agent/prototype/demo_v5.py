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
from agent_v5 import ToolHostV5, run, run_hybrid, rule_controller, DEFAULT_GUARDS, content, caption, TEXT, IMAGE, WEIGHTS, CHUNK, DOCS, ToolError, semantic_doc, dense_scores
from sources import where_froms, source_keys, Rules
from profile_learn import learn, profile_text, rule_note, make_caption
from digest import parse_reply, guide, user_active, propose_folders, MIN_FILES
from expiry import Expiry
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


ASK = '''on run argv
  set opts to items 3 thru -1 of argv
  set r to choose from list opts with title "KCC 에이전트" with prompt (item 1 of argv) default items {item 2 of argv}
  if r is false then return ""
  return item 1 of r
end run'''
LEAVE = '여기 그대로 두기'


def ask_folder(demo, aid, name, guess):
    """First time for this download page: ask in a macOS dialog; the answer files it and teaches the page rule,
    so the next file from the same page is filed without asking. Runs in its own thread (the dialog waits for the user)."""
    names = {CAT[k]['name']: k for k in CAT}; opts = [*names, LEAVE]
    default = CAT[guess]['name'] if guess in CAT else opts[0]
    try: r = subprocess.run(['osascript', '-e', ASK, f'{name}\n어느 폴더에 저장할까요? (다음부터는 묻지 않고 저장합니다)', default, *opts],
                            capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired: return
    pick = r.stdout.strip()
    if not pick: return  # cancelled: the file waits on the page
    with demo.lock:
        try:
            if pick == LEAVE: demo.keep(aid); text = '그대로 두기'
            else:
                pid = names[pick]; demo.answer(aid, pid); plan = demo.engine().plan(aid)
                if plan['action'] == 'file': demo.approve(aid, plan)
                text = f'{pick} 폴더에 저장 (이 페이지는 다음부터 자동)'
        except Exception as exc: text = f'저장 실패: {exc}'
        demo.events.append({'path': name, 'text': text}); demo.events = demo.events[-20:]; demo.version += 1


def notify(title, text):
    # argv, not string interpolation: file names are untrusted.
    subprocess.run(['osascript', '-e', 'on run argv', '-e', 'display notification (item 2 of argv) with title (item 1 of argv)',
                    '-e', 'end run', title, text], capture_output=True, timeout=10)


class Watcher(threading.Thread):
    """Trigger: a new file in a watched folder is ingested and analyzed, then the user is notified.
    --inbox folders (e.g. ~/Desktop for screenshots) are copied in, never moved: user originals stay untouched."""
    def __init__(self, demo, inboxes, interval=2.0, auto_inboxes=(), strict_inboxes=(), ask_inboxes=(), scan_existing=False):
        super().__init__(daemon=True); self.d = demo; self.interval = interval
        self.ask_inboxes = {Path(x).expanduser() for x in ask_inboxes}; self.ask = set()  # not auto-filed -> ask in a dialog
        # auto: any confident 'file' plan runs without a click (iPhone captures). strict: only download-source rules and the
        # rule controller, and only documents/screenshots (Downloads, Desktop: personal notes and mixed files live there).
        self.auto_inboxes = {Path(x).expanduser() for x in auto_inboxes}; self.strict_inboxes = {Path(x).expanduser() for x in strict_inboxes}
        self.auto = set(); self.strict = set()
        self.inboxes = list(dict.fromkeys([Path(x).expanduser() for x in inboxes] + sorted(self.auto_inboxes) + sorted(self.strict_inboxes)))
        self.sizes = {}; self.fetching = set()
        self.scan_existing = scan_existing
        self.seen_file = Path(self.d.root) / 'inbox-seen.json'
        try: self.seen_fingerprints = json.loads(self.seen_file.read_text()) if scan_existing else {}
        except (OSError, ValueError): self.seen_fingerprints = {}
        self.seen = set() if scan_existing else {p for x in self.inboxes for p in x.glob('*')}

    def candidates(self):
        for x in self.inboxes:
            for p in x.glob('*'):
                if p not in self.seen and p.is_file() and not p.name.startswith(('.', '~$')) and p.suffix.lower() in TEXT | IMAGE | WEIGHTS and (not self.scan_existing or self.seen_fingerprints.get(str(p)) != self.fingerprint(p)):
                    yield p, self.d.root / 'screenshots' / p.name
        for sub in WATCH_DIRS:
            for p in (self.d.root / sub).glob('*'):
                if p.is_file() and not p.name.startswith('.'): yield p, None

    def stable(self, p):
        # Wait until the size stops changing (downloads and screenshots are written in pieces).
        n = p.stat().st_size; prev = self.sizes.get(p); self.sizes[p] = n
        return prev == n and n > 0 and p.suffix.lower() not in PARTIAL

    def fingerprint(self, p):
        stat = p.stat()
        return [stat.st_size, stat.st_mtime_ns]

    def remember(self, p):
        self.seen.add(p)
        if self.scan_existing:
            self.seen_fingerprints[str(p)] = self.fingerprint(p)
            tmp = self.seen_file.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.seen_fingerprints), encoding='utf-8')
            tmp.replace(self.seen_file)

    def rename(self, p):
        try: cap = make_caption(None if self.d.ctl is rule_controller else self.d.ctl, content(p))
        except (ToolError, OSError) as exc: print('watcher: caption failed:', p.name, exc, flush=True); cap = None
        if cap:
            new = p.with_name(cap + p.suffix)
            used = {a['original'] for a in self.d.engine().data['assets'].values()}  # an earlier capture may already be filed under this name
            if new.exists() or str(new.relative_to(self.d.root)) in used: new = new.with_stem(f'{new.stem}_{time.strftime("%m%d_%H%M")}')
            p.rename(new); old = str(p.relative_to(self.d.root))
            for s in (self.auto, self.strict, self.ask):
                if p in s: s.discard(p); s.add(new)
            if old in self.d.sources: self.d.sources[str(new.relative_to(self.d.root))] = self.d.sources.pop(old); self.d.save_sources()
            p = new
        return p, str(p.relative_to(self.d.root))

    def tick(self):
        known = {a['original'] for a in self.d.engine().data['assets'].values()}
        for p, copy_to in list(self.candidates()):
            if not self.stable(p): continue
            if copy_to:
                if p.stat().st_size > 50 << 20: self.remember(p); continue  # shortcut: skips >50MB
                if copy_to.exists(): copy_to = copy_to.with_stem(f'{copy_to.stem}_{time.strftime("%Y%m%d_%H%M%S")}')  # iPhone names repeat
                copy_to.parent.mkdir(exist_ok=True)
                try: shutil.copy2(p, copy_to)
                except OSError as exc:
                    copy_to.unlink(missing_ok=True)
                    if p not in self.fetching:  # iCloud keeps new files 'dataless' until something asks for them
                        self.fetching.add(p); subprocess.run(['brctl', 'download', str(p)], capture_output=True, timeout=30)
                        print('watcher: asked iCloud to download', p.name, exc, flush=True)
                    continue
                self.remember(p)
                urls = where_froms(p)
                if urls: self.d.sources[str(copy_to.relative_to(self.d.root))] = urls; self.d.save_sources()
                if p.parent in self.auto_inboxes: self.auto.add(copy_to)
                if p.parent in self.strict_inboxes: self.strict.add(copy_to)
                if p.parent in self.ask_inboxes and p.suffix.lower() in DOCS: self.ask.add(copy_to)
                continue  # analyzed on the next tick
            rel = str(p.relative_to(self.d.root))
            if rel in known: continue
            with self.d.lock:
                if p.suffix.lower() in IMAGE and p.parent.name == 'screenshots' and not caption(p):
                    p, rel = self.rename(p)  # 'IMG_1234.png' -> 'KCC 대회 공지.png', named by the agent from the OCR text
                aid = self.d.engine().ingest(rel)
                try: r = self.d.analyze(aid); r['trigger'] = 'watch'; self.d.save_runs()
                except Exception as exc: r = {'status': f'error: {exc}', 'project': None}
                a = self.d.engine().data['assets'][aid]; plan = self.d.engine().plan(aid) if a['project'] else None
                text = (f'{r["project"]} 자료 · ' + {'file': '폴더 저장 권장', 'archive': '보관 권장', 'keep': '유지 권장', 'defer': '보류'}[plan['action']]) if plan \
                    else '어느 프로젝트인지 확인이 필요해요' if r['status'] == 'waiting_user' else str(r['status'])
                strict_ok = p in self.strict and r.get('decider') in ('source', 'rule') and p.suffix.lower() in DOCS | IMAGE
                if (p in self.auto or strict_ok) and plan and plan['action'] == 'file':
                    # Auto inbox (iPhone captures): the user captured on purpose, so a confident 'file' plan runs now; undo stays on the page.
                    try: self.d.engine().execute(aid, plan); text = f'{CAT[a["project"]]["name"]} 폴더에 자동 저장 (되돌리기 가능)'
                    except Exception as exc: text += f' · 자동 저장 실패: {exc}'
                self.d.events.append({'path': rel, 'text': text}); self.d.events = self.d.events[-20:]; self.d.version += 1
                filed = self.d.engine().data['assets'][aid]['path'] != rel
            if p in self.ask and not filed:
                threading.Thread(target=ask_folder, args=(self.d, aid, p.name, r.get('project') or (r.get('candidates') or [None])[0]), daemon=True).start()
            else: notify(f'새 파일: {p.name}', text)

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
        self.sources_path = self.root / 'sources.json'  # copy path -> download URLs (kMDItemWhereFroms of the original)
        self.sources = json.loads(self.sources_path.read_text()) if self.sources_path.exists() else {}
        self.rules = None  # sources.Rules: page URL -> project, learned from answers and approvals
        self.expiry = None  # expiry.Expiry: installers to the Trash after N days

    def engine(self): return Lifecycle(self.root)
    def save_runs(self): self.runs_path.write_text(json.dumps(self.runs, ensure_ascii=False, indent=1))
    def save_sources(self): self.sources_path.write_text(json.dumps(self.sources, ensure_ascii=False, indent=1))

    def learn_source(self, a, pid):
        keys = source_keys(self.sources.get(a['original'], []))
        changed = self.rules.learn(keys, pid) if self.rules and keys else {}
        if changed: self.runs.setdefault(a['id'], {}).setdefault('rule_learned', {}).update(changed); self.save_runs()  # undo forgets these
        return changed

    def learn_profile(self, e, a, pid):
        """Append one note about the file to the project's _project.md (once per file)."""
        r = self.runs.setdefault(a['id'], {}); folder = e.data.get('folders', {}).get(pid)
        if not folder or r.get('learned'): return r.get('learned')
        prof = Path(folder).expanduser() / '_project.md'
        try: text = content(e.path(a['path'])) if Path(a['path']).suffix.lower() in TEXT | IMAGE else ''
        except Exception: text = ''
        note, trace = learn(None if self.ctl is rule_controller else self.ctl, prof, Path(a['original']).name, CAT[pid]['name'], text)
        r['learned'] = {'note': note, 'trace': trace}
        if note: CAT[pid]['profile'] = profile_text(prof)
        self.save_runs(); return r['learned']

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
                'catalog': [{'id': k, 'name': v['name'], 'desc': v['desc'], 'status': e.data['projects'].get(k)} for k, v in CAT.items()],
                'digest': self.digest, 'pending': len(self.pending()),
                'trashed': [{'i': i, **t} for i, t in enumerate(self.expiry.data['trashed']) if 'restored' not in t][-10:] if self.expiry else []}

    def analyze(self, aid):
        e = self.engine(); a = e.data['assets'][aid]
        if a['path'] != a['original']: raise ValueError('이미 보관된 파일입니다. 먼저 되돌리세요.')
        a.update(project=None, keep=False, reason=None); e.save()
        m = self.rules and self.rules.match(source_keys(self.sources.get(a['original'], [])))
        if m and m[1] in CAT:  # downloaded from a page the user already mapped to a folder: no model call needed
            a.update(project=m[1], reason='source rule'); e.save()
            self.runs[aid] = {'status': 'planned', 'decider': 'source', 'project': m[1], 'steps': 0, 'errors': 0, 'seconds': 0,
                              'evidence': m[0], 'question': None, 'candidates': None, 'trace': [], 'stats': {}, 'full': []}
            self.save_runs(); return self.runs[aid]
        if self.ctl is rule_controller: host = ToolHostV5(e, aid, CAT); rec = run(host, self.ctl)
        else: rec, host = run_hybrid(lambda g: ToolHostV5(e, aid, CAT, guards=g), self.ctl, {*DEFAULT_GUARDS, 'dense'})
        last = lambda tool: next((h for h in reversed(rec['trace']) if h['tool'] == tool and 'error' not in h['result']), None)
        ask, assign = last('ask_user'), last('assign_project')
        self.runs[aid] = {
            'status': rec['status'], 'decider': rec.get('decider', 'rule'), 'project': host.assigned, 'steps': rec['steps'], 'errors': rec['invalid_calls'],
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
        r = self.runs.setdefault(aid, {}); r['answered'] = pid; self.learn_source(a, pid)
        return self.learn_profile(e, a, pid)  # learn from the answer: a note in the project's _project.md

    def keep(self, aid):
        e = self.engine(); e.data['assets'][aid]['keep'] = True; e.save()

    def approve(self, aid, plan):
        # execute() re-plans and refuses if anything changed since the user saw the plan.
        out = self.engine().execute(aid, plan)
        e = self.engine(); a = e.data['assets'][aid]
        if a['project']:  # approving a filing teaches its download page and, unless a page rule decided it, the profile
            self.learn_source(a, a['project'])
            if (self.runs.get(aid) or {}).get('decider') != 'source': self.learn_profile(e, a, a['project'])
        return out

    def expire(self):
        moved = self.expiry.sweep()
        if moved:
            text = f'설치 파일 {len(moved)}개를 휴지통으로 옮겼어요 (화면에서 복구 가능)'
            self.events.append({'path': ', '.join(moved), 'text': text}); self.events = self.events[-20:]; self.version += 1
            notify(f'설치 파일 {len(moved)}개 정리', text)
        return moved

    def undo(self, aid):
        self.engine().undo(aid)
        learned = (self.runs.get(aid) or {}).pop('rule_learned', None)
        if learned and self.rules: self.rules.forget(learned); self.save_runs()  # a wrong approval must not keep filing that page

    # Digest: ask once in a while where the unresolved files go; a plain-language reply becomes a confirmed proposal.
    digest = None; projects_path = None; new_root = Path.home() / 'Desktop'

    def pending(self):
        e = self.engine()
        return [a for a in e.data['assets'].values() if not a.get('context') and not a['project'] and not a['keep']
                and a['path'] == a['original'] and (self.runs.get(a['id']) or {}).get('status') == 'waiting_user']

    def digest_now(self):
        e = self.engine(); items = []; texts = []
        for n, a in enumerate(self.pending(), 1):
            try: text = content(e.path(a['path'])) if Path(a['path']).suffix.lower() in TEXT | IMAGE else ''
            except Exception: text = ''
            cands = ', '.join(CAT[c]['name'] for c in self.runs[a['id']].get('candidates') or [] if c in CAT)
            hint = rule_note(Path(a['original']).name, text)[:80] + (f' (후보: {cands})' if cands else '')
            items.append({'n': n, 'aid': a['id'], 'name': Path(a['original']).name, 'hint': hint}); texts.append(text)
        if not items: self.digest = None; return None
        self.digest = {'items': items, 'asked': time.time(), 'proposal': None}
        if self.ctl is not rule_controller and len(items) >= MIN_FILES:  # look-alike files that fit no folder -> offer one
            try:
                docs = [semantic_doc(c) for c in CAT.values()]
                q = [Path(x['name']).stem + '\n' + t for x, t in zip(items, texts)]
                sim = [dense_scores(x, q) for x in q]; best = [max(dense_scores(x, docs), default=0) for x in q]
                prop = propose_folders(self.ctl, items, texts, sim, best, [c['name'] for c in CAT.values()], self.new_root)
                if prop: self.digest.update(proposal=prop, reply='(에이전트 제안) 비슷한 파일을 새 폴더로 모을까요?', suggested=True)
            except Exception as exc: print('digest: folder proposal failed:', exc, flush=True)
        self.events.append({'path': f'정리 안 된 파일 {len(items)}개', 'text': '어디에 넣을지 답장해 주세요'}); self.version += 1
        notify(f'정리 안 된 파일 {len(items)}개', '어디에 넣을지 한 줄로 답해 주세요 (localhost 화면)')
        return self.digest

    def digest_reply(self, text):
        if not self.digest: raise ValueError('물어볼 파일이 없습니다')
        if self.ctl is rule_controller: raise ValueError('자연어 답장은 --qwen 모델이 필요합니다')
        cat = {k: {'name': c['name']} for k, c in CAT.items()}
        prop, trace = parse_reply(self.ctl, self.digest['items'], cat, self.new_root, text)
        self.digest.update(reply=text, proposal=prop, trace=trace); return self.digest

    def digest_apply(self):
        d = self.digest
        if not d or not d.get('proposal'): raise ValueError('확인할 제안이 없습니다')
        prop = d['proposal']; e = self.engine(); ids = {}
        for tmp, c in prop['new_projects'].items():
            folder = Path(c['folder']); pid = 'U_' + c['name'].replace(' ', '_')
            folder.mkdir(parents=True, exist_ok=True)
            names = [m['name'] for m in prop['moves'] if m['project_id'] == tmp]
            if not (folder / '_project.md').exists(): (folder / '_project.md').write_text(guide(c['name'], c['desc'], names))
            CAT[pid] = {'name': c['name'], 'desc': c['desc'], 'profile': profile_text(folder / '_project.md'), 'keywords': []}
            e.data['projects'][pid] = 'active'; e.data.setdefault('folders', {})[pid] = str(folder); e.save()
            if self.projects_path:
                P = json.loads(self.projects_path.read_text()); P[pid] = {'name': c['name'], 'folder': str(folder), 'desc': c['desc']}
                self.projects_path.write_text(json.dumps(P, ensure_ascii=False, indent=1))
            ids[tmp] = pid
        done = []
        for m in prop['moves']:
            pid = ids.get(m['project_id'], m['project_id']); self.answer(m['aid'], pid)  # also appends a learned note
            plan = self.engine().plan(m['aid'])
            done.append({'name': m['name'], 'project': pid, **(self.engine().execute(m['aid'], plan) or {} if plan['action'] == 'file' else {'skipped': plan['action']})})
        for x in prop['leave']: self.keep(x['aid'])
        self.digest = None; return done


STATUS_KO = {'active': '진행 중', 'completed': '완료'}
PLAN_KO = {'file': '폴더 저장 권장', 'archive': '보관 권장', 'keep': '유지 권장', 'defer': '보류'}


def explain(e, a, r, plan):
    """Reasoning steps built only from what the tools actually returned (no invented evidence)."""
    out, full = [], {h['tool']: h for h in r.get('full', [])}
    ev = r.get('evidence')
    if r.get('decider') == 'source':
        out.append(f'다운로드 출처 {ev} → 이전에 이 페이지 자료를 {a["project"]} 폴더로 정리함 (학습된 출처 규칙)'); ev = None
    if ev:
        try: text = content(e.path(a['path'])) if Path(a['path']).suffix.lower() in TEXT | IMAGE else ''
        except (OSError, ValueError, ToolError): text = ''  # the user moved or deleted the filed file: the page must still load
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


def serve(demo, port, origins=()):
    page = (HERE / 'demo_v5.html').read_bytes()

    class H(BaseHTTPRequestHandler):
        def cors(self):
            # Only origins listed with --allow-origin may call the API from a browser: the API moves the user's files.
            o = self.headers.get('Origin')
            if o and o in origins:
                self.send_header('Access-Control-Allow-Origin', o); self.send_header('Vary', 'Origin')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type'); self.send_header('Access-Control-Allow-Methods', 'GET, POST')
                self.send_header('Access-Control-Allow-Private-Network', 'true')  # Chrome: a public page calling localhost

        def reply(self, obj, code=200):
            b = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.cors()
            self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)

        def do_OPTIONS(self):
            self.send_response(204 if self.headers.get('Origin') in origins else 403); self.cors(); self.send_header('Content-Length', '0'); self.end_headers()

        def do_GET(self):
            if self.path == '/':
                self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.end_headers(); self.wfile.write(page)
            elif self.path == '/api/state':
                with demo.lock: self.reply(demo.state())
            elif self.path == '/api/events': self.reply({'version': demo.version, 'events': demo.events, 'watch': demo.watching})
            else: self.send_error(404)

        def do_POST(self):
            # JSON only: a browser cannot send it cross-origin without the preflight above, so other sites cannot forge calls.
            if 'application/json' not in (self.headers.get('Content-Type') or ''): return self.reply({'ok': False, 'error': 'Content-Type must be application/json'}, 415)
            try:
                d = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
                aid = d.get('id')
                with demo.lock:
                    if self.path == '/api/analyze': out = demo.analyze(aid)
                    elif self.path == '/api/answer': out = demo.answer(aid, d.get('project_id'))
                    elif self.path == '/api/keep': out = demo.keep(aid)
                    elif self.path == '/api/approve': out = demo.approve(aid, d.get('plan'))
                    elif self.path == '/api/undo': out = demo.undo(aid)
                    elif self.path == '/api/digest_now': out = demo.digest_now()
                    elif self.path == '/api/restore_trashed': out = demo.expiry.restore(int(d.get('i')))
                    elif self.path == '/api/digest_reply': out = demo.digest_reply(str(d.get('text', ''))[:1000])
                    elif self.path == '/api/digest_apply': out = demo.digest_apply()
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
    ap.add_argument('--scan-existing-inbox', action='store_true', help='collect iCloud files received while the agent was offline, remembering processed file versions')
    ap.add_argument('--digest-hours', type=float, default=0, help='ask about unresolved files every N hours while the user is at the Mac (0 = off; the page also has an "ask now" button)')
    ap.add_argument('--auto-inbox', action='append', default=[], help='like --inbox, but a confident "save to project folder" plan is executed without a click (e.g. the iCloud KCC-inbox for iPhone captures); questions still wait')
    ap.add_argument('--strict-auto-inbox', action='append', default=[], help='like --inbox, but documents/screenshots are filed without a click when a download-source rule or the rule controller decided (e.g. ~/Downloads, ~/Desktop)')
    ap.add_argument('--source-rules', help='JSON {page key: project id}; learned from answers/approvals (see sources.py)')
    ap.add_argument('--projects', help="real projects JSON {pid: {name, folder, desc, keywords}} (see build_profiles.py); approved files are filed into each project's folder")
    ap.add_argument('--expire-installers-days', type=float, default=0, help='move .dmg/.pkg installers in the inboxes to the Trash N days after first seen, by the Mac clock (0 = off)')
    ap.add_argument('--allow-origin', action='append', default=[], help='web page origin allowed to call the API from a browser, e.g. http://localhost:3000 (repeatable; default: only this page)')
    ap.add_argument('--ask-inbox', action='append', default=[], help='documents from this folder that were not filed automatically are asked about in a macOS dialog (e.g. ~/Downloads)')
    a = ap.parse_args()
    if a.projects:
        P = json.loads(Path(a.projects).read_text())
        CAT = {k: {'name': v['name'], 'desc': v['desc'], 'profile': profile_text(Path(v['folder']) / '_project.md'), 'keywords': v.get('keywords', [])} for k, v in P.items()}
        e = Lifecycle(a.root)  # real mode: no demo seed; the watcher fills downloads/ and screenshots/
        for d in ('downloads', 'screenshots'): (Path(a.root) / d).mkdir(exist_ok=True)
        e.data['projects'].update({k: 'active' for k in P}); e.data['folders'] = {k: v['folder'] for k, v in P.items()}; e.save()
    elif not (Path(a.root) / 'manifest.json').exists(): seed(a.root)
    if a.qwen:
        from qwen_tool_controller import QwenToolController
        from agent_v5 import SPECS, SYSTEM
        ctl, name = QwenToolController(a.qwen, specs=SPECS, system=SYSTEM, adapter=a.adapter), '규칙 → Qwen3 하이브리드 (bge-m3 검색): ' + Path(a.qwen).name
    else:
        ctl, name = rule_controller, '규칙 controller (GPU 없이 실행)'
    demo = Demo(a.root, ctl, name); demo.watching = a.watch
    if a.source_rules: demo.rules = Rules(a.source_rules)
    if a.watch: Watcher(demo, a.inbox, auto_inboxes=a.auto_inbox, strict_inboxes=a.strict_auto_inbox, ask_inboxes=a.ask_inbox, scan_existing=a.scan_existing_inbox).start()
    if a.projects: demo.projects_path = Path(a.projects)
    if a.expire_installers_days:
        demo.expiry = Expiry(Path(a.root) / 'expiry.json', a.inbox + a.strict_auto_inbox, a.expire_installers_days)
        def sweeper():  # every minute, so a clock moved forward is noticed quickly
            while True:
                try:
                    with demo.lock: demo.expire()
                except Exception as exc: print('expiry:', exc, flush=True)
                time.sleep(60)
        threading.Thread(target=sweeper, daemon=True).start()
    if a.digest_hours:
        def ticker():
            last = time.time()
            while True:
                time.sleep(60)
                if time.time() - last >= a.digest_hours * 3600 and user_active():
                    with demo.lock:
                        if demo.pending() and not demo.digest: demo.digest_now()
                    last = time.time()
        threading.Thread(target=ticker, daemon=True).start()
    serve(demo, a.port, set(a.allow_origin))
