"""Local deterministic project lifecycle baseline. No remote model, no arbitrary code execution."""
from pathlib import Path
import hashlib, json, re, os, uuid, math
from collections import Counter

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def tokens(s): return re.findall(r'[a-z0-9_]+|[가-힣]+|[\u4e00-\u9fff]',s.lower())
def search(query, docs, mode='bm25'):
    fields=[tokens(d['path'] if mode=='name' else d['path']+' '+d.get('text','')) for d in docs]
    tf=[Counter(x) for x in fields]; n=len(docs); avg=sum(map(len,fields))/max(n,1) or 1
    df=Counter(t for x in fields for t in set(x)); q=set(tokens(query)); scores=[]
    for d,c,x in zip(docs,tf,fields):
        score=sum(math.log(1+(n-df[t]+.5)/(df[t]+.5))*c[t]*2.2/(c[t]+1.2*(.25+.75*len(x)/avg)) for t in q if c[t])
        scores.append((score,d['path']))
    return [p for s,p in sorted(scores,key=lambda x:(-x[0],x[1])) if s>0]

class Lifecycle:
    def __init__(self, root):
        self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/'manifest.json'
        self.data=json.loads(self.db.read_text()) if self.db.exists() else {'assets':{},'projects':{},'journal':[]}
        self.recover()
    def save(self):
        tmp=self.db.with_suffix('.tmp'); tmp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2)); os.replace(tmp,self.db)
    def path(self,p):
        p=(self.root/p).resolve()
        if not p.is_relative_to(self.root): raise ValueError('outside sandbox')
        return p
    def ingest(self,rel):
        p=self.path(rel)
        if (self.root/rel).is_symlink() or not p.is_file(): raise ValueError('not regular')
        h=sha(p)
        for a in self.data['assets'].values():
            if a['path']==rel:
                if a['hash']!=h: a['previous_hash']=a['hash']; a['hash']=h
                self.save(); return a['id']
        aid=uuid.uuid4().hex
        self.data['assets'][aid]={'id':aid,'path':rel,'original':rel,'hash':h,'project':None,'refs':[],'keep':False}
        self.save(); return aid
    def assign(self,aid,projects):
        a=self.data['assets'][aid]; p=self.path(a['path'])
        text=p.read_text(errors='replace') if p.suffix in ['.txt','.md','.py','.json','.ipynb'] else ''
        hits=[k for k in projects if re.search(r'(?im)^project_id\s*:\s*'+re.escape(k)+r'\s*$',text)]
        a['project']=hits[0] if len(hits)==1 else None
        a['refs']=re.findall(r'REF:\s*(.+)',text)
        a['reason']='explicit project_id' if len(hits)==1 else 'missing or ambiguous project_id'
        self.save(); return a['project']
    def plan(self,aid):
        a=self.data['assets'][aid]; proj=a['project']
        if a['keep']: return {'action':'keep','reason':'user keep'}
        if not proj: return {'action':'defer','reason':a.get('reason','unknown project')}
        if any(x['refs'] and (a['path'] in x['refs'] or Path(a['path']).name in x['refs']) for x in self.data['assets'].values() if self.data['projects'].get(x['project'])!='completed'):
            return {'action':'keep','reason':'active reference'}
        if a['refs']: return {'action':'defer','reason':'reference-bearing file requires bundle-preserving move'}
        if self.data['projects'].get(proj)!='completed': return {'action':'keep','reason':'active project'}
        return {'action':'archive','reason':'explicit completed project','target':f'archive/{proj}/{a["path"]}'}
    def execute(self,aid,plan,crash=False):
        if plan!=self.plan(aid): raise ValueError('stale plan')
        if plan['action']!='archive': return False
        a=self.data['assets'][aid]; src=self.path(a['path']); dst=self.path(plan['target'])
        if sha(src)!=a['hash']: raise ValueError('changed source')
        if dst.exists(): raise FileExistsError(dst)
        dst.parent.mkdir(parents=True,exist_ok=True)
        j={'asset':aid,'src':a['path'],'dst':plan['target'],'hash':a['hash'],'state':'prepared'}
        self.data['journal'].append(j); self.save()
        os.link(src,dst) # atomic no-overwrite; originals retained until journal is durable
        if sha(dst)!=a['hash']:
            dst.unlink(); j['state']='rolled_back'; self.save(); raise ValueError('source changed during execution')
        if crash: raise RuntimeError('injected crash after link')
        src.unlink(); a['path']=j['dst']; j['state']='done'; self.save(); return True
    def recover(self):
        for j in self.data['journal']:
            if j['state']!='prepared': continue
            src,dst=self.path(j['src']),self.path(j['dst'])
            # Roll back incomplete link, or finish bookkeeping after unlink.
            if src.exists() and dst.exists() and os.path.samefile(src,dst) and sha(src)==sha(dst)==j['hash']: dst.unlink(); j['state']='rolled_back'
            elif not src.exists() and dst.exists() and sha(dst)==j['hash']:
                self.data['assets'][j['asset']]['path']=j['dst']; j['state']='done'
            elif src.exists() and not dst.exists(): j['state']='rolled_back'
            else: raise ValueError('recovery needs review')
        self.save()
    def undo(self,aid):
        a=self.data['assets'][aid]; src=self.path(a['path']); dst=self.path(a['original'])
        if dst.exists(): raise FileExistsError(dst)
        if sha(src)!=a['hash']: raise ValueError('changed archive')
        dst.parent.mkdir(parents=True,exist_ok=True); os.link(src,dst); src.unlink()
        # recover() only replays 'prepared' entries, so an 'undone' record is history only.
        self.data['journal'].append({'asset':aid,'src':a['path'],'dst':a['original'],'hash':a['hash'],'state':'undone'}); a['path']=a['original']; self.save()
