"""Build SFT trajectories for the v5 tool-calling agent from gold labels.
Each trajectory is replayed through the real ToolHostV5, so observations are exactly what the model sees at inference.
Outputs sft/split.json (train/eval case ids) and sft/train.jsonl (one example per assistant turn).
usage: python make_sft.py [OUT_DIR]"""
from pathlib import Path
import json, sys, re, tempfile, collections
from lifecycle_v3 import Lifecycle
from agent_v5 import ToolHostV5, ToolError, run, rule_controller, SYSTEM
from case_check import build as build_case, check
from tasks_v5 import build as build_synth
from qwen_tool_controller import QwenToolController

R = Path(__file__).resolve().parents[1]
DC = R / 'data_collect'


def load_cases():
    # batch_t*.json is the held-out test set: never loaded for training.
    cases = {c['id']: c for f in sorted(DC.glob('batch_[0-9]*.json')) for c in json.loads(f.read_text())}
    V = collections.defaultdict(dict)
    for lens in ['label', 'realism', 'policy']:
        for v in json.loads((DC / f'verdict_{lens}.json').read_text()): V[v['id']][lens] = v['verdict']
    return cases, V


def split(cases, V):
    """Eval: every other verified-keep case (sorted by kind, id) so kinds are spread. Train: the rest that are not
    dropped and whose label the blind relabeler did not dispute."""
    keep = sorted((i for i in cases if all(V[i].get(l) == 'keep' for l in ['label', 'realism', 'policy'])), key=lambda i: (cases[i]['kind'], i))
    ev = keep[::2]
    tr = [i for i in sorted(cases) if i not in ev and 'drop' not in V[i].values() and V[i].get('label') == 'keep' and not check(cases[i])]
    return tr, ev


def first_line(text):
    return next((l.strip()[:60] for l in text.splitlines() if len(l.strip()) > 5), text[:60])


def oracle(task, gold, catalog, guards=True):
    """Gold path through the host. Returns the host history, or None if the host rejects the gold label."""
    h = ToolHostV5(Lifecycle(task['dir']), task['asset'], catalog, guards=guards)
    def call(name, **a):
        r = h.call(name, a); h.history.append({'tool': name, 'arguments': a, 'reason': '', 'result': r}); return r
    try:
        info = call('inspect_file'); text = ''
        if info['route'] == 'text':
            off = 0
            while off is not None and off < 6000:
                r = call('read_content', offset=off); text += r['text']; off = r['next_offset']
        elif info['route'] == 'weights':
            call('find_related_files', query=info['name'])
        explicit = gold['status'] == 'planned' and re.search(r'project_id\s*[:=]', gold['evidence'] or '')
        # Project ids are only visible through search results, so search unless the id is explicit or a related file names it.
        if info['route'] == 'text' and not explicit:
            call('search_projects', query=(gold.get('evidence') or first_line(text))[:60])
        if gold['status'] == 'planned':
            call('assign_project', project_id=gold['project'], evidence=gold['evidence'])
            call('check_references'); call('preview_plan'); call('finish')
        else:
            c = gold.get('candidates') or []
            q = '이 파일이 어느 프로젝트 자료인지 확인해 주세요.' + (f' 후보: {", ".join(c)}' if c else ' 근거가 없습니다.')
            call('ask_user', question=q, candidate_ids=c)
        return h.history
    except ToolError:
        return None


def examples(history):
    """One example per assistant turn: the exact inference prompt (messages so far) and the call to produce."""
    shim = type('S', (), {'system': SYSTEM})()
    for k, h in enumerate(history):
        yield {'messages': QwenToolController.messages(shim, history[:k]), 'call': {'name': h['tool'], 'arguments': h['arguments']}}


def main(out, guards=True):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    cases, V = load_cases(); tr, ev = split(cases, V)
    stats = collections.Counter(); rows = []
    with tempfile.TemporaryDirectory() as t:
        for i in tr:
            c = cases[i]; task = build_case(c, Path(t) / 'c')
            hist = oracle(task, c['gold'], task['catalog'], guards)
            stats['collected_ok' if hist else 'collected_rejected'] += 1
            if hist: rows += [dict(e, source=i) for e in examples(hist)]
        # Synthetic dev split only; the test split stays held out. Gold evidence = the rule baseline's accepted quote.
        for task in build_synth(Path(t) / 's'):
            if task['split'] != 'dev': continue
            h = ToolHostV5(Lifecycle(task['dir']), task['asset'], task['catalog']); rec = run(h, rule_controller)
            ev_ = next((x['arguments']['evidence'] for x in rec['trace'] if x['tool'] == 'assign_project' and 'error' not in x['result']), None)
            gold = {'status': task['truth']['status'], 'project': task['truth']['project'], 'evidence': ev_, 'candidates': task['truth']['candidates'] or []}
            task2 = dict(task); hist = oracle(task2, gold, task['catalog'], guards) if rec['status'] == task['truth']['status'] else None
            stats['synthetic_ok' if hist else 'synthetic_rejected'] += 1
            if hist: rows += [dict(e, source=f'synth-{task["id"]}') for e in examples(hist)]
    (out / 'split.json').write_text(json.dumps({'train': tr, 'eval': ev}, indent=1))
    with open(out / 'train.jsonl', 'w') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(dict(stats), 'turn examples', len(rows), 'train cases', len(tr), 'eval cases', len(ev))
    print('eval kinds', collections.Counter(cases[i]['kind'] for i in ev))


if __name__ == '__main__':
    # --dense: observations come from the bge-m3 search the model will see at inference (scores are cosines, not counts).
    from agent_v5 import DEFAULT_GUARDS
    args = [a for a in sys.argv[1:] if a != '--dense']
    main(args[0] if args else R / 'sft', set(DEFAULT_GUARDS) | {'dense'} if '--dense' in sys.argv else True)
