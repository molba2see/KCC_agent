"""Tool-calling quality from saved eval traces (no model run).
usage: python tool_eval.py [--split=test] EXP_DIR [EXP_DIR ...]   # dirs written by eval_v5.py (results.json + tasks/<mode>/<id>/trace.json)
Call level: how many calls the host accepted, and why the rest were rejected.
Trajectory level: procedure, argument accuracy against the gold label, recovery after an error, termination."""
from pathlib import Path
import ast, json, sys, collections

# Host error message -> category (see ToolError sites in agent_v5.py and run()).
CATS = [('format', ('respond with exactly one valid tool call',)),
        ('schema', ('unknown tool', 'arguments must be', 'unexpected argument', 'missing argument', ' must be ', 'items must be')),
        ('order', ('first',)),
        ('grounding', ('not an exact quote', 'instruction inside untrusted', 'does not single out')),
        ('repeat', ('repeated identical call',)),
        ('policy', ('prohibited', 'unknown project_id', 'unknown candidate', 'empty', 'too short', 'out of range', 'OCR'))]


def category(err):
    return next((c for c, keys in CATS if any(k in err for k in keys)), 'other')


def task_metrics(trace, expected):
    t = trace['trace']; ok = [h for h in t if 'error' not in h['result']]
    errs = [(i, category(h['result']['error'])) for i, h in enumerate(t) if 'error' in h['result']]
    # Recovery: the call right after a rejected call is accepted.
    rec = [i + 1 < len(t) and 'error' not in t[i + 1]['result'] for i, _ in errs]
    names = [h['tool'] for h in ok]
    route = next((h['result']['route'] for h in ok if h['tool'] == 'inspect_file'), None)
    m = {'calls': len(t), 'errors': collections.Counter(c for _, c in errs), 'recovered': sum(rec), 'error_n': len(errs),
         'first_inspect': bool(t) and t[0]['tool'] == 'inspect_file' and 'error' not in t[0]['result'],
         'terminated': trace['status'] in ('planned', 'waiting_user'),
         'asked': trace['status'] == 'waiting_user', 'gold_ask': expected.get('status') == 'waiting_user'}
    if route == 'weights': m['weights_via_related'] = 'find_related_files' in names
    if route == 'text': m['read_before_decide'] = any(n == 'read_content' for n in names[:next((k for k, n in enumerate(names) if n in ('assign_project', 'ask_user')), len(names))])
    assigns = [h for h in ok if h['tool'] == 'assign_project']
    if assigns:
        m['assign_project_ok'] = assigns[-1]['arguments']['project_id'] == expected.get('project')
        # After a successful assign the gold tail is check_references -> preview_plan -> finish with no detours.
        k = t.index(assigns[-1]); m['clean_tail'] = [h['tool'] for h in t[k + 1:]] == ['check_references', 'preview_plan', 'finish']
    asks = [h for h in ok if h['tool'] == 'ask_user']
    if asks and expected.get('status') == 'waiting_user':
        got, gold = set(asks[-1]['arguments']['candidate_ids']), set(expected.get('candidates') or [])
        m['ask_candidates_exact'] = got == gold
        m['ask_candidates_jaccard'] = len(got & gold) / len(got | gold) if got | gold else 1.0
    return m


def summarize(rows):
    n = len(rows); calls = sum(r['calls'] for r in rows); err = collections.Counter()
    for r in rows: err.update(r['errors'])
    rate = lambda k: (lambda xs: f'{sum(xs)}/{len(xs)}' if xs else '-')([r[k] for r in rows if k in r])
    e = sum(err.values())
    return {'tasks': n, 'success': rate('correct'), 'calls_per_task': round(calls / n, 2),
            'accepted_call_rate': f'{(calls - e) / calls:.1%}' if calls else '-',
            **{f'err_{c}': err.get(c, 0) for c, _ in CATS}, 'err_other': err.get('other', 0),
            'recovery_rate': f'{sum(r["recovered"] for r in rows)}/{e}',
            'first_call_inspect': rate('first_inspect'), 'terminated': rate('terminated'),
            'text_read_before_decide': rate('read_before_decide'), 'weights_via_related_files': rate('weights_via_related'),
            'assign_project_correct': rate('assign_project_ok'), 'clean_tail_after_assign': rate('clean_tail'),
            'ask_candidates_exact': rate('ask_candidates_exact'),
            # Abstention: should the agent have asked instead of assigning?
            'ask_precision': (lambda a: f'{sum(r["gold_ask"] for r in a)}/{len(a)}')([r for r in rows if r['asked']]),
            'ask_recall': (lambda g: f'{sum(r["asked"] for r in g)}/{len(g)}')([r for r in rows if r['gold_ask']]),
            'ask_candidates_jaccard': (lambda xs: round(sum(xs) / len(xs), 2) if xs else '-')([r['ask_candidates_jaccard'] for r in rows if 'ask_candidates_jaccard' in r])}


def load(exp, split=None):
    exp = Path(exp); res = json.loads((exp / 'results.json').read_text()); out = collections.defaultdict(list)
    for row in res['rows']:
        if split and row['split'] != split: continue  # synthetic dev was used for SFT; report test only
        tr = exp / 'tasks' / row['mode'] / (f"task_{row['id']:03d}" if isinstance(row['id'], int) else row['id']) / 'trace.json'
        if not tr.exists(): continue
        exp_ = row['expected'] if isinstance(row['expected'], dict) else ast.literal_eval(row['expected'])
        m = task_metrics(json.loads(tr.read_text()), exp_); m['correct'] = str(row['correct']) == 'True'
        out[row['mode']].append(m)
    return out


if __name__ == '__main__':
    table = {}; split = next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--split=')), None)
    for exp in (a for a in sys.argv[1:] if not a.startswith('--')):
        for mode, rows in load(exp, split).items(): table[f'{Path(exp).name}:{mode}'] = summarize(rows)
    print(json.dumps(table, ensure_ascii=False, indent=1))
