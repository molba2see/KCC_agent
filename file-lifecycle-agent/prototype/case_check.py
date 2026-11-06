"""Mechanical checks for collected cases, and conversion into eval_v5 task sandboxes.
usage: python case_check.py cases/*.json [--build OUT_DIR]
A case is one target file plus the folder context the agent can see and a gold label (schema in CASE_SCHEMA.md)."""
from pathlib import Path
import json, sys, re, random
from lifecycle_v3 import Lifecycle
from agent_v5 import TEXT, WEIGHTS
from tasks_v5 import CATALOG as EVAL_CATALOG

KINDS = {'explicit', 'semantic', 'ambiguous', 'no_evidence', 'weights_referenced', 'weights_orphan', 'long_doc', 'injection', 'other'}
PID = re.compile(r'^[A-Z][A-Z0-9_]{2,40}$')


def check(case):
    """Return a list of problems; empty means mechanically valid."""
    p = []
    need = ['id', 'kind', 'catalog', 'files', 'target', 'gold']
    if missing := [k for k in need if k not in case]: return [f'missing keys {missing}']
    if case['kind'] not in KINDS: p.append(f'unknown kind {case["kind"]}')
    cat = case['catalog']
    if not isinstance(cat, dict) or len(cat) < 2: p.append('catalog needs at least 2 projects')
    for k, v in cat.items():
        if not PID.match(k): p.append(f'bad project id {k}')
        if k in EVAL_CATALOG: p.append(f'project {k} collides with the eval catalog (leak)')
        if v.get('status') not in ('active', 'completed') or not v.get('name') or not v.get('desc'): p.append(f'project {k} needs name, desc, status')
    files = {f.get('path'): f for f in case['files']}
    for path, f in files.items():
        if not path or path.startswith('/') or '..' in Path(path).parts: p.append(f'unsafe path {path}'); continue
        suf = Path(path).suffix.lower()
        if suf in WEIGHTS and 'binary_bytes' not in f: p.append(f'{path}: weights need binary_bytes, not content')
        if suf in TEXT and not isinstance(f.get('content'), str): p.append(f'{path}: text file needs content')
        if suf not in TEXT | WEIGHTS: p.append(f'{path}: unsupported suffix')
    if case['target'] not in files: p.append('target not in files')
    for path, c in case.get('context', {}).items():
        if path not in files: p.append(f'context {path} not in files')
        if c.get('project') not in cat: p.append(f'context {path} project not in catalog')
        if path == case['target']: p.append('target cannot be a context file')
    g = case['gold']
    if g.get('status') == 'planned':
        if g.get('project') not in cat: p.append('gold project not in catalog')
        ev = g.get('evidence') or ''
        sources = [files[case['target']].get('content') or ''] + [files[x].get('content') or '' for x in case.get('context', {})]
        if len(ev) < 6 or not any(ev in s for s in sources): p.append('gold evidence is not an exact quote from the target or a context file')
    elif g.get('status') == 'waiting_user':
        if g.get('project') is not None: p.append('waiting_user gold must have project null')
        if not isinstance(g.get('candidates'), list) or any(c not in cat for c in g['candidates']): p.append('candidates must be catalog ids')
    else: p.append('gold.status must be planned or waiting_user')
    return p


def build(case, root):
    """Materialize a case as an eval_v5 task (same dict shape tasks_v5.build returns)."""
    d = Path(root) / case['id']; d.mkdir(parents=True)
    rng = random.Random(case['id'])
    for f in case['files']:
        q = d / f['path']; q.parent.mkdir(parents=True, exist_ok=True)
        q.write_bytes(rng.randbytes(f['binary_bytes'])) if 'binary_bytes' in f else q.write_text(f['content'])
    e = Lifecycle(d); e.data['projects'].update({k: v['status'] for k, v in case['catalog'].items()})
    for path, c in case.get('context', {}).items():
        e.data['assets'][e.ingest(path)].update(project=c['project'], refs=c.get('refs', []))
    e.save(); aid = e.ingest(case['target']); g = case['gold']
    truth = {'status': g['status'], 'project': g.get('project'), 'candidates': g.get('candidates') if g['status'] == 'waiting_user' and g.get('candidates') else None}
    if g['status'] == 'planned':
        a = e.data['assets'][aid]; a['project'] = g['project']; truth['action'] = e.plan(aid)['action']; a['project'] = None; e.save()
    return {'id': case['id'], 'kind': case['kind'], 'split': case.get('split', 'collected'), 'dir': str(d), 'asset': aid,
            'catalog': {k: {'name': v['name'], 'desc': v['desc']} for k, v in case['catalog'].items()}, 'truth': truth}


def load(paths):
    cases = []
    for x in paths:
        data = json.loads(Path(x).read_text())
        cases += data if isinstance(data, list) else data['cases']
    return cases


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--build')]
    out = next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--build=')), None)
    cases = load(args); bad = 0; ids = set()
    for c in cases:
        probs = check(c)
        if c.get('id') in ids: probs.append('duplicate id')
        ids.add(c.get('id'))
        if probs: bad += 1; print(c.get('id'), '; '.join(probs))
    print(f'{len(cases) - bad}/{len(cases)} mechanically valid')
    if out:
        tasks = [build(c, out) for c in cases if not check(c)]
        (Path(out) / 'tasks.json').write_text(json.dumps(tasks, ensure_ascii=False, indent=1)); print('built', len(tasks), 'tasks in', out)
