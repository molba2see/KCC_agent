"""Reproducible raw-only retrieval + controlled lifecycle evaluation. Never executes downloaded files."""
from pathlib import Path
import json, time, urllib.request, urllib.parse, concurrent.futures, shutil, argparse
from lifecycle_v3 import Lifecycle, search, sha
from app import extract
REV='ff212ff7ec1a60d28023e65f7e7c4df5a87f552c'
BASE='https://huggingface.co/datasets/MMMem-org/HippoCamp/resolve/'+REV+'/'
ROOT=Path(__file__).resolve().parents[1]
AUDIT=Path(__import__('os').environ.get('HIPPOCAMP_AUDIT_ROOT','/private/tmp/hippocamp-data-audit-20261102'))
DATA=ROOT/'experiments/v3_data'; DATA.mkdir(exist_ok=True)

def fetch(row):
    p=DATA/row['path']; p.parent.mkdir(parents=True,exist_ok=True)
    try:
        if not p.exists() or p.stat().st_size!=row['size']:
            with urllib.request.urlopen(BASE+urllib.parse.quote(row['path']),timeout=90) as r: b=r.read()
            if len(b)!=row['size']: raise ValueError('size mismatch')
            p.write_bytes(b)
        cache=p.with_suffix(p.suffix+'.extracted.json')
        if cache.exists(): return json.loads(cache.read_text())
        text,method,locators=extract(p)
        d={'path':row['path'],'text':text,'method':method,'chars':len(text),'sha256':sha(p),'locator_rows':len(locators)}
        cache.write_text(json.dumps(d,ensure_ascii=False)); return d
    except Exception as e: return {'path':row['path'],'text':'','error':type(e).__name__+': '+str(e)[:160]}

def retrieval(out):
    result={}; allrows=[]; queries={}
    for profile in ['Adam','Bei']:
        tree=json.loads((AUDIT/f'{profile}_Subset_{profile}_Subset_tree.json').read_text())
        # Fixed format/size filter independent of questions/answers. Include distractors.
        rows=[x for x in tree if x['type']=='file' and Path(x['path']).suffix.lower() in ['.pdf','.png','.jpg','.jpeg'] and x['size']<=5_000_000]
        allrows+=rows; queries[profile]=json.loads((AUDIT/profile/'Subset'/f'{profile}_Subset.json').read_text())
    print('download/extract',len(allrows),'files',sum(r['size'] for r in allrows),'bytes',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: docs=list(pool.map(fetch,allrows))
    result['corpus']={'files':len(docs),'nonempty':sum(bool(d['text'].strip()) for d in docs),'failures':[{'path':d['path'],'error':d.get('error','empty extraction')} for d in docs if not d['text'].strip()]}
    result['profiles']={}
    for profile,qa in queries.items():
        prefix=f'{profile}/Subset/{profile}_Subset/'; corpus=[d for d in docs if d['path'].startswith(prefix)]
        paths={d['path'] for d in corpus}; eligible=[]; excluded=[]
        for q in qa:
            targets={prefix+p for p in q['file_path']}
            if targets and targets<=paths: eligible.append((q,targets))
            else: excluded.append({'id':q['id'],'missing_target_count':len(targets-paths)})
        modes={}
        for mode in ['name','bm25']:
            details=[]
            for q,targets in eligible:
                ranked=search(q['question'],corpus,mode)
                hit=lambda k:len(set(ranked[:k])&targets)/len(targets)
                ranks=[ranked.index(p)+1 for p in targets if p in ranked]
                details.append({'id':q['id'],'recall5':hit(5),'recall10':hit(10),'mrr':1/min(ranks) if ranks else 0,'all10':int(hit(10)==1),'target_count':len(targets),'top10':ranked[:10]})
            modes[mode]={'n':len(details),'means':{k:sum(x[k] for x in details)/len(details) if details else None for k in ['recall5','recall10','mrr','all10']},'details':details}
        result['profiles'][profile]={'corpus':len(corpus),'excluded':excluded,'modes':modes}
    (out/'retrieval.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result

def controlled(out):
    checks=[]
    def check(name,fn):
        try: fn(); checks.append({'name':name,'pass':True})
        except Exception as e: checks.append({'name':name,'pass':False,'error':repr(e)})
    def case(i,kind):
        root=out/'sandbox'/f'{kind}_{i}'; root.mkdir(parents=True)
        p=root/'downloads'/'notes.txt'; p.parent.mkdir(); p.write_text(f'project_id: P{i}\nunique experiment {i}')
        e=Lifecycle(root); aid=e.ingest('downloads/notes.txt'); e.assign(aid,[f'P{i}',f'Q{i}']); e.data['projects'][f'P{i}']='active'; e.save()
        assert e.plan(aid)['action']=='keep'
        assert e.ingest('downloads/notes.txt')==aid
        e.data['projects'][f'P{i}']='completed'; e.save(); plan=e.plan(aid)
        if kind=='normal':
            h=sha(p); assert e.execute(aid,plan); assert not p.exists(); e.undo(aid); assert sha(p)==h
        elif kind=='crash':
            try:e.execute(aid,plan,crash=True)
            except RuntimeError:pass
            e=Lifecycle(root); assert p.exists() and sha(p)==e.data['assets'][aid]['hash']; assert e.execute(aid,e.plan(aid)); e.undo(aid)
        elif kind=='conflict':
            dst=e.path(plan['target']); dst.parent.mkdir(parents=True); dst.write_text('different')
            try:e.execute(aid,plan); raise AssertionError('overwrite accepted')
            except FileExistsError:pass
            assert p.exists() and dst.read_text()=='different'
        elif kind=='shared':
            q=root/'reader.py'; q.write_text(f'project_id: Q{i}\nREF: downloads/notes.txt\n'); qid=e.ingest('reader.py'); e.assign(qid,[f'P{i}',f'Q{i}']); e.data['projects'][f'Q{i}']='active'; e.save(); assert e.plan(aid)['action']=='keep'
        elif kind=='stale':
            e.data['assets'][aid]['keep']=True; e.save()
            try:e.execute(aid,plan); raise AssertionError('stale plan accepted')
            except ValueError:pass
            assert p.exists()
        elif kind=='ambiguous':
            p.write_text(f'project_id: P{i}\nproject_id: Q{i}\n'); e.ingest('downloads/notes.txt'); assert e.assign(aid,[f'P{i}',f'Q{i}']) is None; assert e.plan(aid)['action']=='defer'
        elif kind=='weights':
            w=root/'checkpoint.pth'; w.write_bytes(b'INERT TEST BYTES NOT A MODEL'); wid=e.ingest('checkpoint.pth'); e.data['assets'][wid]['project']=f'P{i}'
            p.write_text(f'project_id: Q{i}\nREF: checkpoint.pth\n'); e.ingest('downloads/notes.txt'); e.assign(aid,[f'P{i}',f'Q{i}']); e.data['projects'][f'Q{i}']='active'; e.save(); assert e.plan(wid)['action']=='keep'
    for kind in ['normal','crash','conflict','shared','stale','ambiguous','weights']:
        for i in range(10): check(f'{kind}/{i}',lambda i=i,kind=kind:case(i,kind))
    r={'scope':'70 authored controlled scenarios; repeated templates, not independent real-world samples','passed':sum(c['pass'] for c in checks),'total':len(checks),'checks':checks}
    (out/'controlled.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)); return r

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--skip-retrieval',action='store_true');args=p.parse_args()
    out=ROOT/'experiments'/('v3_'+time.strftime('%Y%m%d_%H%M%S'));out.mkdir(); print(out,flush=True)
    c=controlled(out); print('controlled',c['passed'],c['total'],flush=True)
    r=None if args.skip_retrieval else retrieval(out)
    summary={'revision':REV,'controlled':c,'retrieval':r,'unrun':['E1 Gold-assisted comparison','E3 human-annotated real relations','E4 real destination labels','E5 user study','embedding/LLM comparison'],'api_calls':0,'server_used':False}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)); (ROOT/'experiments/latest_v3.json').write_text(json.dumps({'root':str(out)})); print('DONE',out,flush=True)
