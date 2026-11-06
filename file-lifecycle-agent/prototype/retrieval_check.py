"""Offline check: does project search find the gold project? Lexical score() vs bge-m3 dense vs bge-reranker-v2-m3.
Queries are the ones the model actually sent to search_projects in an eval run, plus the gold evidence line.
usage: python retrieval_check.py EXP_DIR MODE [batch.json ...]"""
from pathlib import Path
import json, sys, glob
import torch
from transformers import AutoTokenizer, AutoModel, AutoModelForSequenceClassification
from agent_v5 import score

HUB = Path.home() / '.cache/huggingface/hub'
dev = 'mps' if torch.backends.mps.is_available() else 'cpu'


def snap(repo, need):
    return next(str(p) for p in (HUB / repo / 'snapshots').glob('*') if (p / need).exists())


class Dense:
    def __init__(self):
        p = snap('models--BAAI--bge-m3', 'tokenizer.json')
        self.tok = AutoTokenizer.from_pretrained(p); self.m = AutoModel.from_pretrained(p).to(dev).eval()

    @torch.no_grad()
    def __call__(self, q, docs):
        x = self.tok([q] + docs, padding=True, truncation=True, max_length=512, return_tensors='pt').to(dev)
        e = torch.nn.functional.normalize(self.m(**x).last_hidden_state[:, 0], dim=-1)  # bge-m3 dense = CLS
        return (e[1:] @ e[0]).tolist()


class Rerank:
    def __init__(self):
        p = snap('models--BAAI--bge-reranker-v2-m3', 'tokenizer.json')
        self.tok = AutoTokenizer.from_pretrained(p); self.m = AutoModelForSequenceClassification.from_pretrained(p).to(dev).eval()

    @torch.no_grad()
    def __call__(self, q, docs):
        x = self.tok([[q, d] for d in docs], padding=True, truncation=True, max_length=512, return_tensors='pt').to(dev)
        return torch.sigmoid(self.m(**x).logits[:, 0]).tolist()


def main(exp, mode, batches):
    cases = {c['id']: c for b in batches for c in json.loads(Path(b).read_text())}
    res = json.loads((Path(exp) / 'results.json').read_text())
    scorers = {'lexical': lambda q, d: [float(score(q, x)) for x in d], 'bge-m3': Dense(), 'reranker': Rerank()}
    out = []
    for r in res['rows']:
        if r['mode'] != mode or r['id'] not in cases: continue
        c = cases[r['id']]; t = json.loads((Path(exp) / 'tasks' / mode / r['id'] / 'trace.json').read_text())['trace']
        qs = [h['arguments']['query'] for h in t if h['tool'] == 'search_projects']
        if c['gold']['status'] == 'planned' and c['gold'].get('evidence'): qs.append(c['gold']['evidence'])
        if not qs: continue
        pids = list(c['catalog']); docs = [c['catalog'][p]['name'] + ' ' + c['catalog'][p]['desc'] for p in pids]
        row = {'id': r['id'], 'kind': c['kind'], 'gold': c['gold'], 'model_correct': str(r['correct']) == 'True', 'queries': []}
        for q in qs:
            sc = {k: f(q[:500], docs) for k, f in scorers.items()}
            row['queries'].append({'q': q[:80], **{k: sorted(zip(v, pids), reverse=True)[:3] for k, v in sc.items()}})
        out.append(row); print(r['id'], 'done', flush=True)
    Path(exp, 'retrieval_check.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3:] or sorted(glob.glob(str(Path(__file__).resolve().parents[1] / 'data_collect/batch_t*.json'))))
