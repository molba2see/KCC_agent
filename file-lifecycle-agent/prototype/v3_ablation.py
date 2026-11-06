"""Authored mini-workflows: fixed labels isolated from explicit-ID baseline; no real-world accuracy claim."""
import json,time
from pathlib import Path
from lifecycle_v3 import Lifecycle,sha
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'experiments'/('v3_ablation_'+time.strftime('%Y%m%d_%H%M%S'));out.mkdir()
rows=[]
for i in range(30):
    root=out/str(i); root.mkdir(); (root/'downloads').mkdir()
    active=i%3==0; shared=i%3==1
    (root/'downloads/result.txt').write_text(f'project_id: P{i}\nresult for experiment {i}\n')
    e=Lifecycle(root); a=e.ingest('downloads/result.txt'); e.assign(a,[f'P{i}',f'Q{i}'])
    e.data['projects'][f'P{i}']='active' if active else 'completed'
    if shared:
        (root/'consumer.py').write_text(f'project_id: Q{i}\nREF: downloads/result.txt\n')
        b=e.ingest('consumer.py');e.assign(b,[f'P{i}',f'Q{i}']);e.data['projects'][f'Q{i}']='active'
    e.save(); expected='keep' if active or shared else 'archive'
    full=e.plan(a); before=sha(root/'downloads/result.txt')
    if full['action']=='archive':
        assert e.execute(a,full); e.undo(a)
    assert sha(root/'downloads/result.txt')==before
    rows.append({'case':i,'expected':expected,'file_only':'archive','project_state':'keep' if active else 'archive','state_and_refs':full['action'],'hash_preserved':True})
result={'scope':'30 authored workflows, 3 templates repeated 10 times; no learned model or held-out real user labels','n':len(rows),'modes':{k:{'correct':sum(x[k]==x['expected'] for x in rows),'unsafe_archive_proposals':sum(x[k]=='archive' and x['expected']=='keep' for x in rows),'archive_coverage_of_eligible':sum(x[k]=='archive' and x['expected']=='archive' for x in rows)/10} for k in ['file_only','project_state','state_and_refs']},'rows':rows}
(out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(out);print(json.dumps(result['modes'],indent=2))
