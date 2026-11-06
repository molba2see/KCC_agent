"""Bounded tool-selection runtime; rule controller and local JSON model endpoint are distinct backends."""
from pathlib import Path
import json,time,urllib.request
from lifecycle_v3 import Lifecycle
from app import extract
SYSTEM=(Path(__file__).parent/'agent_specs/system.md').read_text()
TOOLS=['inspect_file','read_content','search_projects','check_references','ask_user','preview_plan','finish']
class ToolHost:
    def __init__(self,engine,aid,projects):
        self.e=engine;self.aid=aid;self.projects=projects;self.obs={}
    def call(self,name,args):
        if name not in TOOLS or args!={}: raise ValueError('invalid tool or arguments')
        a=self.e.data['assets'][self.aid];p=self.e.path(a['path'])
        if name=='inspect_file':
            suffix=p.suffix.lower();route='metadata' if suffix in ['.pt','.pth','.bin'] else 'document' if suffix=='.pdf' else 'ocr' if suffix in ['.png','.jpg','.jpeg'] else 'text' if suffix in ['.txt','.md','.py','.json'] else 'unsupported'
            result={'suffix':suffix,'route':route,'bytes':p.stat().st_size}
        elif name=='read_content':
            route=self.obs.get('inspect_file',{}).get('route')
            if route in ['metadata','unsupported',None]:raise ValueError('content route prohibited')
            text=p.read_text(errors='replace') if route=='text' else extract(p)[0]
            result={'text':text[:12000],'truncated':len(text)>12000,'empty':not text.strip()}
        elif name=='search_projects':
            if 'inspect_file' not in self.obs:raise ValueError('inspect first')
            # Reuses exact-evidence baseline, not semantic LLM project assignment.
            project=self.e.assign(self.aid,self.projects)
            result={'project':project,'reason':a['reason']}
        elif name=='check_references':
            if 'search_projects' not in self.obs:raise ValueError('search first')
            result={'policy_plan':self.e.plan(self.aid),'scope':'registered assets only'}
        elif name=='ask_user':
            if self.obs.get('search_projects',{}).get('project') is not None:raise ValueError('unnecessary question')
            result={'status':'waiting_user','question':'어느 프로젝트 자료인지 확인해 주세요.','choices':self.projects}
        elif name=='preview_plan':
            if 'check_references' not in self.obs:raise ValueError('references not checked')
            result=self.e.plan(self.aid)
        else:
            if 'preview_plan' not in self.obs:raise ValueError('no verified plan')
            result={'status':'planned','plan':self.obs['preview_plan']}
        self.obs[name]=result;return result

def rule_controller(obs):
    if 'inspect_file' not in obs:t='inspect_file'
    elif 'read_content' not in obs and obs['inspect_file']['route'] in ['text','document','ocr']:t='read_content'
    elif 'search_projects' not in obs:t='search_projects'
    elif obs['search_projects']['project'] is None:t='ask_user'
    elif 'check_references' not in obs:t='check_references'
    elif 'preview_plan' not in obs:t='preview_plan'
    else:t='finish'
    return {'tool':t,'arguments':{},'reason':'Choose next unmet evidence requirement.'}

class JsonModelController:
    """Local /v1/chat/completions endpoint; never sends user files by default."""
    def __init__(self,endpoint,model):
        if not endpoint.startswith(('http://127.0.0.1:','http://localhost:')):raise ValueError('use local SSH tunnel')
        self.endpoint=endpoint;self.model=model;self.usage=[]
    def __call__(self,obs):
        body={'model':self.model,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps({'observations':obs},ensure_ascii=False)}],'temperature':0,'max_tokens':180}
        req=urllib.request.Request(self.endpoint,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as r:reply=json.load(r)
        self.usage.append(reply.get('usage',{}));return json.loads(reply['choices'][0]['message']['content'])

def run(host,controller,trace_path,max_steps=8):
    trace=[];seen=set();status='budget_exceeded';start=time.monotonic()
    for step in range(max_steps):
        t=time.monotonic()
        try:
            action=controller(dict(host.obs))
            if not isinstance(action,dict) or set(action)!={'tool','arguments','reason'} or not isinstance(action['reason'],str):raise ValueError('invalid action schema')
            fingerprint=json.dumps([action['tool'],action['arguments']],sort_keys=True)
            if fingerprint in seen:raise ValueError('repeated call blocked')
            seen.add(fingerprint)
            result=host.call(action['tool'],action['arguments'])
            trace.append({'step':step,'tool':action['tool'],'arguments':action['arguments'],'decision_summary':action['reason'],'result':result,'latency_ms':(time.monotonic()-t)*1000})
            if action['tool'] in ['ask_user','finish']:status=result['status'];break
        except Exception as e:
            status='blocked';trace.append({'step':step,'error':type(e).__name__+': '+str(e)});break
    record={'status':status,'steps':len(trace),'elapsed_ms':(time.monotonic()-start)*1000,'trace':trace,'backend':type(controller).__name__,'model_usage':getattr(controller,'usage',[])}
    Path(trace_path).write_text(json.dumps(record,ensure_ascii=False,indent=2));return record
