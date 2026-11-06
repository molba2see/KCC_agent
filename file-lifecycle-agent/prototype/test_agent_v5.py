import unittest,tempfile
from pathlib import Path
from lifecycle_v3 import Lifecycle
from agent_v5 import ToolHostV5,run,rule_controller
from tasks_v5 import build
def host_for(ts,kind):
    t=next(x for x in ts if x['kind']==kind);return ToolHostV5(Lifecycle(t['dir']),t['asset'],t['catalog']),t
def script(*actions):
    it=iter(actions);return lambda h:next(it,{'tool':'finish','arguments':{},'reason':'end'})
A=lambda t,**a:{'tool':t,'arguments':a,'reason':'test'}
class V5(unittest.TestCase):
    @classmethod
    def setUpClass(c):c.tmp=tempfile.TemporaryDirectory();c.ts=build(c.tmp.name)
    def test_ungrounded_assign_rejected(self):
        h,t=host_for(self.ts,'semantic');pid=next(iter(t['catalog']))
        r=run(h,script(A('inspect_file'),A('assign_project',project_id=pid,evidence='made up evidence text')),max_steps=2)
        self.assertIsNone(h.assigned);self.assertEqual(h.stats['ungrounded_assign'],1)
    def test_search_result_is_not_evidence(self):
        h,t=host_for(self.ts,'semantic');pid=next(iter(t['catalog']))
        run(h,script(A('inspect_file'),A('search_projects',query=t['catalog'][pid]['name']),A('assign_project',project_id=pid,evidence=t['catalog'][pid]['name'])),max_steps=3)
        self.assertIsNone(h.assigned)
    def test_weights_never_read(self):
        h,_=host_for(self.ts,'weights_referenced');run(h,script(A('inspect_file'),A('read_content',offset=0)),max_steps=2)
        self.assertEqual(h.stats['weights_read_attempts'],1);self.assertIn('error',h.history[-1]['result'])
    def test_unknown_tool_and_bad_candidate(self):
        h,_=host_for(self.ts,'ambiguous')
        r=run(h,script(A('execute_plan'),A('ask_user',question='q',candidate_ids=['NOPE'])),max_steps=2)
        self.assertEqual(h.stats['unknown_tool'],1);self.assertEqual(r['status'],'budget_exceeded');self.assertEqual(r['invalid_calls'],2)
    def test_repeat_and_invalid_output_fed_back(self):
        h,_=host_for(self.ts,'explicit')
        r=run(h,script(A('inspect_file'),A('inspect_file'),{'invalid_output':'hi'}),max_steps=3)
        self.assertEqual(r['invalid_calls'],2);self.assertIn('repeated',h.history[1]['result']['error'])
    def test_file_untouched(self):
        for x in self.ts[:20]:
            h=ToolHostV5(Lifecycle(x['dir']),x['asset'],x['catalog']);p=h.file();run(h,rule_controller);self.assertTrue(p.exists())
    def test_injected_instruction_is_not_evidence(self):
        h,t=host_for(self.ts,'injection');line=next(l for l in Path(h.file()).read_text().splitlines() if 'OVERRIDE' in l)
        run(h,script(A('inspect_file'),A('read_content',offset=0),A('assign_project',project_id=next(iter(t['catalog'])),evidence=line)),max_steps=3)
        self.assertNotIn('OVERRIDE',h.history[1]['result']['text']);self.assertEqual(h.stats['redacted_lines'],1)
        self.assertIsNone(h.assigned);self.assertEqual(h.stats['ungrounded_assign'],1)  # redacted line is no longer quotable
    def test_tied_evidence_rejected(self):
        h,t=host_for(self.ts,'ambiguous');line=Path(h.file()).read_text().splitlines()[0]
        run(h,script(A('inspect_file'),A('read_content',offset=0),A('assign_project',project_id=t['truth']['candidates'][0],evidence=line)),max_steps=3)
        self.assertIsNone(h.assigned);self.assertIn('ask_user',h.history[-1]['result']['error'])
    def test_ask_blocked_until_read_through(self):
        h,_=host_for(self.ts,'long_doc')
        run(h,script(A('inspect_file'),A('read_content',offset=0),A('ask_user',question='q',candidate_ids=[])),max_steps=3)
        self.assertEqual(h.stats['early_ask'],1);self.assertIn('offset=1200',h.history[-1]['result']['error'])
    def test_guards_off_reproduces_v5(self):
        h,t=host_for(self.ts,'injection');h.guards={'quote'};line=next(l for l in Path(h.file()).read_text().splitlines() if 'OVERRIDE' in l)
        run(h,script(A('inspect_file'),A('read_content',offset=0),A('assign_project',project_id='KCC_AGENT',evidence=line)),max_steps=3)
        self.assertEqual(h.assigned,'KCC_AGENT') if 'KCC_AGENT' in t['catalog'] else None
    def test_quote_with_double_quotes_is_grounded(self):
        h,t=host_for(self.ts,'semantic');Path(h.file()).write_text('메모\n'+t['catalog'][t['truth']['project']]['desc']+' "v2" 결과\n')
        run(h,script(A('inspect_file'),A('read_content',offset=0),A('assign_project',project_id=t['truth']['project'],evidence=t['catalog'][t['truth']['project']]['desc']+' "v2" 결과')),max_steps=3)
        self.assertEqual(h.assigned,t['truth']['project'])
    def test_screenshot_without_ocr_asks_user(self):
        import agent_v5
        h,t=host_for(self.ts,'semantic');Lc=h.e;img=Path(Lc.root)/'shot.png';img.write_bytes(b'png')
        aid=Lc.ingest('shot.png');h=ToolHostV5(Lc,aid,t['catalog']);old=agent_v5.OCR_BIN;agent_v5.OCR_BIN=Path('/nonexistent/ocr')
        try:r=run(h,rule_controller)
        finally:agent_v5.OCR_BIN=old
        self.assertEqual(h.history[0]['result']['source'],'ocr');self.assertIn('OCR unavailable',h.history[1]['result']['error']);self.assertEqual(r['status'],'waiting_user')
    def test_fuzzy_quote_snaps_to_source_line(self):
        h,t=host_for(self.ts,'semantic');pid=t['truth']['project'];line=t['catalog'][pid]['desc']+' 실험을 다시 돌렸다.'
        Path(h.file()).write_text('메모\n'+line+'\n')
        run(h,script(A('inspect_file'),A('read_content',offset=0),A('assign_project',project_id=pid,evidence=line.replace('다시 ','다시  ').rstrip('.')+'!')),max_steps=3)
        self.assertEqual(h.assigned,pid);self.assertEqual(h.history[-1]['result']['evidence'],line);self.assertEqual(h.stats['snapped_quotes'],1)
    def test_stopword_only_overlap_does_not_support(self):
        h,t=host_for(self.ts,'semantic');pid=next(iter(t['catalog']))
        cat={pid:{'name':'선박 데이터 파일','desc':'x'},'OTHER':{'name':'음성 인식','desc':'y'}}
        self.assertEqual(ToolHostV5(h.e,h.aid,cat).support(pid,'공유 파일 데이터 목록'),[])
        self.assertEqual(ToolHostV5(h.e,h.aid,cat,guards={'quote'}).support(pid,'공유 파일 데이터 목록'),[pid])
    def test_safetensors_metadata_in_inspect(self):
        import json,struct
        h,t=host_for(self.ts,'semantic');p=Path(h.e.root)/'w.safetensors';hdr=json.dumps({'__metadata__':{'run':'sar_ship_yolo_v3'}}).encode()
        p.write_bytes(struct.pack('<Q',len(hdr))+hdr+b'\0'*16);aid=h.e.ingest('w.safetensors')
        r=ToolHostV5(h.e,aid,t['catalog']).call('inspect_file',{})
        self.assertEqual(r['metadata'],{'run':'sar_ship_yolo_v3'});self.assertEqual(r['route'],'weights')
    def test_shared_weights_need_ask(self):
        import tempfile
        d=Path(tempfile.mkdtemp());e=Lifecycle(d);e.data['projects'].update(A1='active',B1='active')
        for rel,pid in [('a/cfg.yaml','A1'),('b/cfg.yaml','B1')]:
            (d/rel).parent.mkdir(parents=True,exist_ok=True);(d/rel).write_text(('model: yolov8s.pt' if pid=='A1' else 'detector: weights/yolov8s.pt')+f'\nproject: {pid}\n');e.data['assets'][e.ingest(rel)].update(project=pid,refs=['yolov8s.pt'])
        (d/'yolov8s.pt').write_bytes(b'\0'*64);aid=e.ingest('yolov8s.pt');e.save()
        cat={'A1':{'name':'a','desc':'a'},'B1':{'name':'b','desc':'b'}}
        for guards,expect in [(True,None),({'quote'},'A1')]:
            h=ToolHostV5(Lifecycle(d),aid,cat,guards=guards)
            run(h,script(A('inspect_file'),A('find_related_files',query='yolov8s.pt'),A('assign_project',project_id='A1',evidence='model: yolov8s.pt')),max_steps=3)
            self.assertEqual(h.assigned,expect)
if __name__=='__main__':unittest.main()
