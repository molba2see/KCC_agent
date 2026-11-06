"""Additional text-only probes; separate from the synthetic end-to-end corpus."""
from pathlib import Path
import json
from app import understand

project=Path(__file__).resolve().parent.parent
root=Path(json.loads((project/'experiments/latest.json').read_text())['root'])
report=json.loads((root/'report.json').read_text())
due=report['per_file'][0]['gold_deadline']
from datetime import datetime
date=datetime.fromisoformat(due).strftime('%Y년 %m월 %d일 %H시 %M분')
checks=[]
def check(name,passed,detail): checks.append(dict(name=name,passed=bool(passed),detail=detail))
a=understand('아이디어 공모전\n접수 마감:\n'+date)
check('줄이 나뉜 기한을 연결해 추출',a['deadline']==due,{'expected':due,'actual':a['deadline']})
a=understand('공개 행사\n신청이 필요하지 않습니다.\n접수 마감: '+date)
check('신청 불필요 문서에서 행동 기한을 억제',a['deadline'] is None,{'expected':None,'actual':a['deadline']})
a=understand('공모전\n접수 마감: 내일 오후 6시')
check('상대 날짜는 확인 대기로 남김',bool(a['review']) and a['deadline'] is None,a['review'])
a=understand('공모전\n접수 마감: '+date+'\n제출 마감: 2026년 12월 20일 18시 00분')
check('충돌하는 행동 기한은 자동 확정하지 않음',a['deadline'] is None and bool(a['review']),a['review'])
a=understand('데이터 공모전\n주최: A대학교\n접수 마감: '+date)
b=understand('데이터 공모전\n주최: B대학교\n접수 마감: '+date)
check('같은 제목·다른 주최자의 행사를 구분',a['bundle_key']!=b['bundle_key'],'현재 제목 일치만으로 연결하므로 잘못 묶일 수 있음')
a=understand('캠퍼스 아이디어 공모전\n행사 안내\n접수 마감: '+date)
b=understand('참가신청서\n행사명: 캠퍼스 아이디어 공모전\n접수 마감: '+date)
check('서로 다른 문서 제목에서도 같은 행사를 연결',a['bundle_key']==b['bundle_key'],'현재 첫 줄을 제목으로 사용하므로 같은 행사도 누락될 수 있음')
report['challenge_probes']=dict(kind='text_only_after_core_run',passed=sum(c['passed'] for c in checks),total=len(checks),cases=checks)
report['development_note']='첫 실행에서 제출 안내문을 날짜 누락으로 처리하고 부정 문구를 행사로 분류한 오류를 수정함. 이후 같은 개발 자료로 재검증. 추가 probe 6개는 수정하지 않고 한계로 기록함.'
(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
with (root/'결과.md').open('a') as f:
 f.write('\n\n## 추가 난도 점검 — 원문 텍스트만 평가\n\n')
 f.write('PDF/OCR 성능과 별개인 추출·연결 규칙 점검입니다. 이 실패는 이번 실행에서 수정하지 않았습니다.\n\n')
 f.write('| 사례 | 결과 |\n|---|---|\n')
 for c in checks:f.write(f"| {c['name']} | {'PASS' if c['passed'] else 'FAIL'} |\n")
 f.write('\n'+report['development_note']+'\n')
print(json.dumps(report['challenge_probes'],ensure_ascii=False,indent=2))
