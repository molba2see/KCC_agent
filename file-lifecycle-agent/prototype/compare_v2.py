"""Same-case comparison plus new file-backed integration probes. No model call by default."""
from pathlib import Path
from datetime import datetime
import argparse
import json
import os
import sys
from app import Engine, understand
from pipeline_v2 import analyze, resolve_bundle

PROJECT=Path(__file__).resolve().parent.parent


def run(backend='local_v2'):
    if backend=='openai' and not os.environ.get('OPENAI_API_KEY'):
        raise SystemExit('OPENAI_API_KEY 미설정: API 요청 0회. 로컬 환경변수로 키를 설정한 뒤 실행하세요.')
    root=Path(json.loads((PROJECT/'experiments/latest.json').read_text())['root'])
    report=json.loads((root/'report.json').read_text())
    due=report['per_file'][0]['gold_deadline']
    date=datetime.fromisoformat(due).strftime('%Y년 %m월 %d일 %H시 %M분')
    settings={'extractor':backend,'allow_external':backend=='openai'}
    versions={}
    for version, fn in [('v1',understand),('v2',lambda t:analyze(t,settings))]:
        rows=[]
        def check(name, passed): rows.append({'name':name,'passed':bool(passed)})
        a=fn('아이디어 공모전\n접수 마감:\n'+date)
        check('줄이 나뉜 기한을 연결해 추출',a['deadline']==due)
        a=fn('공개 행사\n신청이 필요하지 않습니다.\n접수 마감: '+date)
        check('신청 불필요 문서에서 행동 기한을 억제',a['deadline'] is None)
        a=fn('공모전\n접수 마감: 내일 오후 6시')
        check('상대 날짜는 확인 대기로 남김',bool(a['review']) and a['deadline'] is None)
        a=fn('공모전\n접수 마감: '+date+'\n제출 마감: 2026년 12월 20일 18시 00분')
        check('충돌하는 행동 기한은 자동 확정하지 않음',a['deadline'] is None and bool(a['review']))
        a=fn('데이터 공모전\n주최: A대학교\n접수 마감: '+date)
        b=fn('데이터 공모전\n주최: B대학교\n접수 마감: '+date)
        check('같은 제목·다른 주최자의 행사를 구분',a['bundle_key']!=b['bundle_key'])
        a=fn('캠퍼스 아이디어 공모전\n행사 안내\n접수 마감: '+date)
        b=fn('참가신청서\n행사명: 캠퍼스 아이디어 공모전\n접수 마감: '+date)
        check('서로 다른 문서 제목에서도 같은 행사를 연결',a['bundle_key']==b['bundle_key'])
        versions[version]={'passed':sum(r['passed'] for r in rows),'total':len(rows),'cases':rows}
    if backend=='openai':
        # Text-only provider comparison has 8 calls; it never rewrites the live pipeline settings.
        output={'backend':backend,'same_cases':versions,'live_provider_calls':8,'scope':'synthetic text only'}
        (root/'openai_comparison.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
        print(json.dumps(output,ensure_ascii=False,indent=2));return
    # New PNG integration cases go through OCR, validation, DB grouping and scheduling.
    from experiment import make_file
    docs=[
      ('v2_multiline.png',['학술 발표회','접수 마감:',date]),
      ('v2_optional.png',['공개 관람 행사','신청이 필요하지 않습니다.','접수 마감: '+date]),
      ('v2_org_a.png',['지역 아이디어 공모전','주최: A대학교','접수 마감: '+date]),
      ('v2_org_b.png',['지역 아이디어 공모전','주최: B대학교','접수 마감: '+date]),
      ('v2_org_unknown.png',['지역 아이디어 공모전','접수 마감: '+date]),
      ('v2_named.png',['지역 디자인 공모전','주최: 지역 문화원','접수 마감: '+date]),
      ('v2_form.png',['참가신청서','행사명: 지역 디자인 공모전','주최: 지역 문화원','접수 마감: '+date]),
    ]
    engine=Engine(root)
    for name,lines in docs:
        path=root/'screenshots'/name
        if not path.exists(): make_file(path,lines)
        engine.ingest(path)
    def asset(name):return next(a for a in engine.snapshot()['assets'] if Path(a['original_path']).name==name)
    integration=[]
    def check(name,passed): integration.append({'name':name,'passed':bool(passed)})
    check('PNG OCR 후 줄바꿈 기한을 실제 예약',asset('v2_multiline.png')['deadline']==due and any(r['bundle_id']==asset('v2_multiline.png')['bundle_id'] and r['status']=='active' for r in engine.snapshot()['reminders']))
    check('신청 불필요 PNG는 실제 예약 없음',not any(r['bundle_id']==asset('v2_optional.png')['bundle_id'] for r in engine.snapshot()['reminders']))
    check('다른 주최자 PNG는 DB에서 다른 묶음',asset('v2_org_a.png')['bundle_id']!=asset('v2_org_b.png')['bundle_id'])
    check('주최자 없는 동명 후보는 보류·별도 묶음',asset('v2_org_unknown.png')['state']=='review' and asset('v2_org_unknown.png')['bundle_id'] not in [asset('v2_org_a.png')['bundle_id'],asset('v2_org_b.png')['bundle_id']] and asset('v2_org_unknown.png')['deadline'] is None)
    check('안내와 다른 제목의 신청서가 DB에서 같은 묶음',asset('v2_named.png')['bundle_id']==asset('v2_form.png')['bundle_id'])
    check('서로 다른 제목의 같은 행사 알림은 1개',sum(r['bundle_id']==asset('v2_named.png')['bundle_id'] and r['status']=='active' for r in engine.snapshot()['reminders'])==1)
    output={'backend':backend,'same_cases':versions,'new_png_integration':{'passed':sum(r['passed'] for r in integration),'total':len(integration),'cases':integration},
      'api_live_test':'not_run_no_key','note':'이전 실패 사례를 보며 보강한 회귀 검증. 일반화 성능이나 LLM 성능이 아님.'}
    (root/'comparison.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
    report['challenge_probes']=versions['v2'];report['v2_comparison']=output
    report['limitations']=['로컬 보강 규칙으로 실험; OpenAI 유료 호출은 미실행','같은 제목이며 주최자·행사일이 모두 없는 서로 다른 행사는 여전히 혼동 가능',
       '의미상 별칭·복잡한 표·복수 작업 기한·의도적인 부정 표현의 범위를 모두 해결하지 못함','크롤링·OS 알림·임베딩 검색·이동 중 강제 종료 복구 미구현']
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    engine.db.close()
    print(json.dumps(output,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--backend',choices=['local_v2','openai'],default='local_v2')
    run(p.parse_args().backend)
