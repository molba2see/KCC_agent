"""Native Qwen function-calling controller (transformers, in-process on the GPU server).
History is rebuilt from host observations as assistant tool_calls + tool messages, so the model
sees the official Qwen tool template, not the ad-hoc JSON action prompt."""
import json,re,time
from agent_runtime import SYSTEM,TOOLS

DESC={'inspect_file':'Get suffix, size and processing route of the bound file.',
 'read_content':'Read text/PDF/OCR content of the bound file. Not allowed for weights or unsupported files.',
 'search_projects':'Find the verified project for the bound file.',
 'check_references':'Check active references and retention policy before planning.',
 'ask_user':'Ask the user which project the file belongs to when evidence is ambiguous. Ends the run.',
 'preview_plan':'Build the organization plan. Requires check_references first.',
 'finish':'Return the verified plan. Requires preview_plan first.'}
SPECS=[{'type':'function','function':{'name':t,'description':DESC[t],'parameters':{'type':'object','properties':{},'required':[]}}} for t in TOOLS]
# Native template replaces the JSON-output instruction in system.md.
NATIVE_SYSTEM=SYSTEM.replace('Return JSON only: {"tool": name, "arguments": {}, "reason": short evidence-based reason}.','Call exactly one tool per turn.')
TASK='Organize the bound downloaded file. Pick the next tool.'

class QwenToolController:
    def __init__(self,model_path,thinking=False,specs=None,system=None,adapter=None):
        import torch
        from transformers import AutoTokenizer,AutoModelForCausalLM
        self.tok=AutoTokenizer.from_pretrained(model_path)
        # CUDA on the GPU server, Apple GPU (MPS) on a Mac laptop, CPU otherwise.
        self.device='cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'
        self.model=AutoModelForCausalLM.from_pretrained(model_path,torch_dtype=torch.bfloat16,device_map=self.device).eval()
        if adapter:
            from peft import PeftModel
            self.model=PeftModel.from_pretrained(self.model,adapter).eval()
        # Qwen3 hybrid thinking; Qwen2.5 templates ignore the flag.
        self.specs=specs or SPECS;self.system=system or NATIVE_SYSTEM
        self.thinking=thinking;self.max_new_tokens=1536 if thinking else 128;self.usage=[];self.torch=torch
    def messages(self,obs):
        m=[{'role':'system','content':self.system},{'role':'user','content':TASK}]
        # v4 passes {tool: result}; v5 passes a history list with real arguments and errors.
        hist=[{'tool':k,'arguments':{},'result':v} for k,v in obs.items()] if isinstance(obs,dict) else obs
        for h in hist:
            if h['tool'] is None:
                m.append({'role':'assistant','content':h.get('raw','')});m.append({'role':'user','content':'Error: '+h['result']['error']});continue
            m.append({'role':'assistant','content':'','tool_calls':[{'type':'function','function':{'name':h['tool'],'arguments':h['arguments']}}]})
            m.append({'role':'tool','name':h['tool'],'content':json.dumps(h['result'],ensure_ascii=False)})
        return m
    def __call__(self,obs):
        enc=self.tok.apply_chat_template(self.messages(obs),tools=self.specs,add_generation_prompt=True,enable_thinking=self.thinking,return_tensors='pt',return_dict=True).to(self.device)
        ids=enc['input_ids'];t=time.monotonic()
        with self.torch.no_grad():out=self.model.generate(**enc,max_new_tokens=self.max_new_tokens,do_sample=False)
        text=self.tok.decode(out[0,ids.shape[1]:],skip_special_tokens=True)
        self.usage.append({'prompt_tokens':ids.shape[1],'completion_tokens':out.shape[1]-ids.shape[1],'latency_ms':(time.monotonic()-t)*1000})
        return parse(text)

def parse(text):
    """Return runtime action; malformed output passes through as an invalid action so run() blocks it."""
    text=re.sub(r'<think>.*?</think>','',text,flags=re.S)  # thinking is not logged as decision summary
    m=re.search(r'<tool_call>\s*(\{.*?\})\s*</tool_call>',text,re.S)
    if not m:return {'invalid_output':text[:300]}
    try:call=json.loads(m.group(1))
    except json.JSONDecodeError:return {'invalid_output':text[:300]}
    reason=re.sub(r'<tool_call>.*?</tool_call>','',text,flags=re.S).strip()[:200] or 'native tool call'
    args=call.get('arguments',{})
    if isinstance(args,str):
        try:args=json.loads(args)
        except json.JSONDecodeError:pass
    return {'tool':call.get('name'),'arguments':args,'reason':reason}

if __name__=='__main__':
    assert parse('<tool_call>\n{"name": "inspect_file", "arguments": {}}\n</tool_call>')=={'tool':'inspect_file','arguments':{},'reason':'native tool call'}
    assert 'invalid_output' in parse('I will inspect the file.')
    assert parse('<think>x</think>\n<tool_call>{"name": "finish", "arguments": {}}</tool_call>')['reason']=='native tool call'
    print('parse ok')
