"""Inspect downloaded public manifests only. No model inference or raw-file execution."""
from pathlib import Path
from collections import Counter
import argparse, json, unicodedata


def audit(root):
    root=Path(root); result={'scope':'3 subset annotation manifests; not a model benchmark','profiles':[]}
    for profile,name in [('Adam','Adam_Subset'),('Bei','Bei_Subset'),('Victoria','Victoria_Subset')]:
        path=root/profile/'Subset'/(name+'.json')
        rows=json.loads(path.read_text())
        qa=Counter(str(r.get('QA_type')) for r in rows)
        light={'pdf','png','jpg','jpeg'}
        broader=light|{'gif','docx','eml','ics','md','txt','csv','xlsx','json','pptx'}
        # Eligibility means only format-compatible, not verified answerability after extraction.
        def eligible(types):return [r for r in rows if set(r.get('file_type',[]))<=types and r.get('file_type')]
        sets=[set(r.get('file_path',[])) for r in rows]
        overlap=sum(bool(sets[i]&sets[j]) for i in range(len(sets)) for j in range(i+1,len(sets)))
        fields=set().union(*(r.keys() for r in rows))
        result['profiles'].append({'profile':profile,'qa_records':len(rows),'qa_types':dict(qa),
          'light_format_candidates':len(eligible(light)),'broader_no_audio_video_candidates':len(eligible(broader)),
          'evidence_files_unique':len(set().union(*sets)),'qa_pairs_sharing_files':overlap,
          'fields':sorted(fields),'destination_label_present':any('destination' in x for x in fields),
          'retention_label_present':any(x in fields for x in ['retention','delete_safe','completed','project_state'])})
        tree=root/(profile+'_Subset_'+name+'_tree.json')
        if tree.exists():
            prefix=profile+'/Subset/'+name+'/'
            norm=lambda p:unicodedata.normalize('NFC',p.strip().replace('\\','/')).casefold()
            paths={norm(r['path'][len(prefix):]) for r in json.loads(tree.read_text()) if r['type']=='file'}
            missing={p for r in rows for p in r.get('file_path',[]) if norm(p) not in paths}
            result['profiles'][-1]['path_alignment']={'raw_files':len(paths),'unmatched_target_paths':len(missing),
                'affected_qa_ids':[r['id'] for r in rows if any(norm(p) not in paths for p in r.get('file_path',[]))],
                'policy':'unmatched is a release-path discrepancy, not a model failure; verify aliases or obtain missing files before scoring'}
    tree_path=root/'Bei_Fullset_Bei_tree.json'
    if tree_path.exists():
        tree=json.loads(tree_path.read_text());files=[r for r in tree if r['type']=='file']
        suffix=Counter(Path(r['path']).suffix.lower() for r in files)
        result['bei_fullset_tree']={'files_counted':len(files),'pt_files':suffix['.pt'],'pth_files':suffix['.pth'],
          'py_files':suffix['.py'],'ipynb_files':suffix['.ipynb'],'note':'file-list metadata only; weights not downloaded or executed'}
    result['subset_total_qa']=sum(p['qa_records'] for p in result['profiles'])
    result['evaluation_policy']={'agent_inputs':['question','allowed raw files','permitted metadata'],
       'scorer_only':['answer','file_path target set','evidence','rationale','agent_cap'],
       'gold_text':'separate assisted-text experiment; never silently mix into raw end-to-end score',
       'subset_fullset':'overlap is possible; do not treat as independent train/test sets'}
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out',required=True);args=p.parse_args()
    r=audit(args.root);Path(args.out).write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
