"""Generate synthetic files, run golden-label checks and real filesystem scenarios."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from app import Engine, KST, digest

PROJECT = Path(__file__).resolve().parent.parent
FONT = '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'
NOW = datetime.now(KST)
BASE = NOW.replace(hour=18, minute=0, second=0, microsecond=0)
DUE = BASE + timedelta(days=7)
EXTENDED = BASE + timedelta(days=10)
def date(dt): return dt.strftime('%Y년 %m월 %d일 %H시 %M분')


def make_file(path, lines):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.suffix=='.pdf':
        c=canvas.Canvas(str(path),pagesize=(595,842))
        c.setTitle(lines[0]);c.setFillColorRGB(.96,.97,.99);c.rect(0,0,595,842,fill=1,stroke=0)
        c.setFillColorRGB(.1,.15,.25)
        for i,line in enumerate(lines):
            c.setFont('Korean',22 if i==0 else 15);c.drawString(45,765-i*53,line)
        c.setFont('Korean',10);c.setFillColorRGB(.4,.45,.55);c.drawString(45,60,'LOCAL TEST / 합성 실험 자료 / 실제 행사가 아닙니다')
        c.save()
    else:
        im=Image.new('RGB',(1400,1000),'#f3f6fb');d=ImageDraw.Draw(im)
        d.rounded_rectangle((55,55,1345,945),radius=35,fill='white',outline='#dce3ee',width=3)
        for i,line in enumerate(lines):
            d.text((110,125+i*112),line,font=ImageFont.truetype(FONT,54 if i==0 else 38),fill='#14213a')
        d.text((110,850),'합성 실험 자료',font=ImageFont.truetype(FONT,25),fill='#94a3b8');im.save(path)


def run(pipeline='legacy'):
    root=PROJECT/'experiments'/datetime.now().strftime('run_%Y%m%d_%H%M%S')
    root.mkdir(parents=True)
    (root/'pipeline.json').write_text(json.dumps({'extractor':pipeline,'allow_external':False}))
    pdfmetrics.registerFont(TTFont('Korean',FONT))
    event='캠퍼스 아이디어 공모전'
    # File names deliberately do not contain the classification or deadline labels.
    fixtures=[
      ('downloads/01.pdf',[event,'신청 양식','주최: 캠퍼스 운영팀','접수 마감: '+date(DUE),'신청서 제출이 필요합니다.'],'event',DUE.isoformat()),
      ('screenshots/02.png',[event,'행사 안내','접수 마감: '+date(DUE),'신청서와 안내를 함께 확인하세요.'],'event',DUE.isoformat()),
      ('downloads/03.pdf',[event,'신청 완료 확인서','결제 증빙','보관용 증빙입니다.'],'receipt',None),
      ('downloads/04.pdf',['데이터 분석 과제','제출 안내','제출 마감: '+date(DUE+timedelta(days=1)),'보고서 제출이 필요합니다.'],'reference',(DUE+timedelta(days=1)).isoformat()),
      ('downloads/05.pdf',['사진 전시 행사','관람 안내','행사일: '+date(DUE+timedelta(days=2)),'신청이 필요하지 않습니다.'],'event',None),
      ('downloads/06.pdf',['자료 읽기 노트','개인 메모','다음에 읽어볼 항목입니다.'],'unclassified',None),
      ('screenshots/07.png',['디자인 워크숍','신청 안내','접수 마감: 11월 9일 오후 6시','연도는 안내되지 않았습니다.'],'event',None),
      ('screenshots/08.png',['동네 카페 쿠폰','사용 기한: '+date(BASE-timedelta(days=3)),'음료 1잔 할인'],'event',(BASE-timedelta(days=3)).isoformat()),
      ('screenshots/09.png',['온라인 강의 참고자료','강의 복습 링크','내용을 참고하세요.'],'reference',None),
      ('screenshots/10.png',['간이 영수증','결제일: '+date(BASE-timedelta(days=2)),'결제 금액: 12000원'],'receipt',None),
      ('screenshots/11.png',['오픈 세미나','신청 접수 마감: '+date(DUE+timedelta(days=4)),'참가 신청이 필요합니다.'],'event',(DUE+timedelta(days=4)).isoformat()),
    ]
    for name,lines,_,_ in fixtures: make_file(root/name,lines)
    # A scanned PDF has image bytes only, so it exercises the OCR fallback too.
    Image.open(root/'screenshots/02.png').save(root/'downloads/13.pdf','PDF')
    fixtures.append(('downloads/13.pdf',[], 'event', DUE.isoformat()))
    # A changed notice enters later, after the initial scan.
    extension=root/'staging/12.pdf'
    make_file(extension,[event,'기한 변경 / 접수 연장','접수 마감: '+date(EXTENDED),'기존 접수 마감이 연장되었습니다.'])
    shutil.copy2(root/'downloads/01.pdf',root/'downloads/01_copy.pdf')
    gold=[dict(file=n,category=c,deadline=d) for n,_,c,d in fixtures]
    (root/'gold.json').write_text(json.dumps(gold,ensure_ascii=False,indent=2))
    started=time.monotonic();engine=Engine(root);scanned=engine.scan()
    initial=engine.snapshot(); elapsed=round(time.monotonic()-started,3)
    checks=[]
    def check(name,condition,detail=''):
        checks.append(dict(name=name,passed=bool(condition),detail=detail))
    def asset(name):
        return next(a for a in engine.snapshot()['assets'] if Path(a['original_path']).name==name)
    def count_active(): return sum(r['status']=='active' for r in engine.snapshot()['reminders'])
    per_file=[]
    for g in gold:
        a=asset(Path(g['file']).name)
        per_file.append(dict(file=g['file'],gold_category=g['category'],actual_category=a['category'],
          category_correct=g['category']==a['category'],gold_deadline=g['deadline'],actual_deadline=a['details']['deadline'],
          deadline_correct=g['deadline']==a['details']['deadline'],method=a['method'],elapsed_ms=a['details']['elapsed_ms'],
          review=a['details']['review']))
    check('동일 바이트 복사본이 자료를 늘리지 않음',len(initial['assets'])==len(fixtures),str(scanned))
    check('PDF와 이미지가 같은 행사로 묶임',asset('01.pdf')['bundle_id']==asset('02.png')['bundle_id'])
    check('스캔 PDF를 이미지 OCR로 읽음',asset('13.pdf')['method']=='pdf_ocr' and asset('13.pdf')['details']['deadline']==DUE.isoformat())
    event_id=asset('01.pdf')['bundle_id']
    check('행사 묶음당 활성 알림 1개',sum(r['status']=='active' and r['bundle_id']==event_id for r in initial['reminders'])==1)
    check('연도 없는 날짜는 확인 대기·기한 비움',asset('07.png')['state']=='review' and asset('07.png')['details']['deadline'] is None)
    check('행사 날짜를 신청 마감으로 잘못 예약하지 않음',asset('05.pdf')['deadline'] is None)
    check('쿠폰 만료 후 활성 알림 없음',not any(r['status']=='active' and r['bundle_id']==asset('08.png')['bundle_id'] for r in initial['reminders']))
    before=len(initial['assets']);reminders_before=len(initial['reminders']);engine.scan()
    check('재스캔이 자료·예약을 중복 생성하지 않음',len(engine.snapshot()['assets'])==before and len(engine.snapshot()['reminders'])==reminders_before)
    form=asset('01.pdf');engine.action(form['id'],'snooze')
    check('미루기 6시간이 활성 알림을 갱신',next(r for r in engine.snapshot()['reminders'] if r['bundle_id']==event_id and r['status']=='active')['due']==(DUE-timedelta(days=1)+timedelta(hours=6)).isoformat())
    shutil.copy2(extension,root/'downloads/12.pdf');engine.scan();update=asset('12.pdf')
    check('변경 공고를 승인 전에 덮어쓰지 않음',update['details']['pending_update'] and update['deadline']==DUE.isoformat())
    engine.action(update['id'],'approve_update')
    rs=[r for r in engine.snapshot()['reminders'] if r['bundle_id']==event_id]
    check('연장 승인 시 이전 알림 취소·새 예약 1개',len([r for r in rs if r['status']=='active'])==1 and any(r['status']=='cancelled' and r['version']==1 for r in rs) and asset('01.pdf')['deadline']==EXTENDED.isoformat())
    snapshots={'initial':initial,'after_extension':engine.snapshot()}
    engine.action(form['id'],'complete')
    check('완료 시 관련 행동 알림 전부 취소',not any(r['status']=='active' and r['bundle_id']==event_id for r in engine.snapshot()['reminders']))
    check('영수증·증빙은 정리 후보에서 제외',not asset('03.pdf')['cleanup_candidate'])
    # No approval = no move. All original hashes still match before explicit archive calls.
    check('승인 전 모든 원본 경로와 바이트 유지',all(Path(a['path']).exists() and digest(a['path'])==a['hash'] for a in engine.snapshot()['assets']))
    engine.action(asset('02.png')['id'],'keep')
    check('유지 선택 후 정리 후보 억제',asset('02.png')['keep']==1 and not asset('02.png')['cleanup_candidate'])
    conflict=root/'archive/01.pdf';conflict.write_text('다른 파일: 충돌 실험')
    try: engine.action(form['id'],'archive');blocked=False
    except ValueError: blocked=True
    check('이동 이름 충돌 시 원본·대상 보존',blocked and (root/'downloads/01.pdf').exists() and conflict.read_text()=='다른 파일: 충돌 실험')
    conflict.rename(root/'archive/conflict_kept.txt')
    original_hash=digest(root/'downloads/01.pdf');engine.action(form['id'],'archive')
    check('승인 후 실제 보관 이동·해시 일치',not (root/'downloads/01.pdf').exists() and digest(root/'archive/01.pdf')==original_hash)
    (root/'downloads/01.pdf').write_text('다른 원본 경로 점유')
    try: engine.action(form['id'],'undo');blocked=False
    except ValueError: blocked=True
    check('되돌리기 이름 충돌 시 덮어쓰기 방지',blocked and (root/'downloads/01.pdf').read_text()=='다른 원본 경로 점유' and (root/'archive/01.pdf').exists())
    (root/'downloads/01.pdf').rename(root/'downloads/conflict_kept.txt')
    engine.action(form['id'],'undo')
    check('되돌리기로 원래 위치와 바이트 복구',digest(root/'downloads/01.pdf')==original_hash and not (root/'archive/01.pdf').exists())
    check('텍스트 검색으로 관련 묶음 자료 검색',len(engine.snapshot('캠퍼스')['assets'])==5)
    snapshots['after_complete_undo']=engine.snapshot()
    engine.db.close();engine=Engine(root)
    check('프로세스 재시작 후 완료·이동 이력 유지',asset('01.pdf')['task_state']=='completed' and engine.snapshot()['moves'][-1]['status']=='undone')
    dispatch_time= DUE+timedelta(days=3,hours=1)
    first=engine.dispatch(dispatch_time);second=engine.dispatch(dispatch_time)
    check('실험 시각의 수신함 기록은 재실행 시 중복 없음',first==1 and second==0,dict(first=first,second=second,simulated_time=dispatch_time.isoformat()))
    check('완료된 행사에는 실험 알림 발송 없음',not any(e['kind']=='reminder_delivered' and json.loads(e['detail'])['bundle_id']==event_id for e in engine.snapshot()['events']))
    # Start a real polling process and observe a newly copied file without calling scan here.
    watch = subprocess.Popen([sys.executable,str(PROJECT/'prototype/app.py'),'watch','--root',str(root)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        watch_file=root/'screenshots/watch_copy.pdf'
        shutil.copy2(root/'downloads/01.pdf',watch_file)
        observed=False
        for _ in range(40):
            if engine.db.execute('SELECT 1 FROM locations WHERE path=?',(str(watch_file),)).fetchone():
                observed=True;break
            time.sleep(.2)
        check('별도 폴더 감시 프로세스가 새 복사본 자동 감지',observed)
    finally:
        watch.terminate();watch.wait(timeout=10)
    snapshots['final']=engine.snapshot()
    report=dict(created_at=NOW.isoformat(),root=str(root),implementation='local Vision OCR + '+pipeline+'; no LLM',
       samples=dict(unique_initial=len(fixtures),unique_with_extension=len(fixtures)+1,authored_pdf=7,authored_png=6,byte_duplicate=2),
       initial_scan_seconds=elapsed,per_file=per_file,
       metrics=dict(category_accuracy=sum(r['category_correct'] for r in per_file)/len(per_file),
                    deadline_exact_match=sum(r['deadline_correct'] for r in per_file)/len(per_file),
                    ocr_images=sum(a['method']=='vision_ocr' for a in initial['assets']),
                    checks_passed=sum(c['passed'] for c in checks),checks_total=len(checks)),checks=checks,
       limitations=['합성 소규모 개발 사례이며 일반화 성능이 아님','정확히 같은 제목으로 묶는 규칙; 의미 기반 연결 미구현',
         'LLM 미연결; 규칙 기반 종류·날짜 추출','OCR 좌표는 이미지 정규화 좌표; PDF 텍스트 추출은 원문 텍스트만 보존',
         '폴더 감시는 2초 폴링; 상시 서비스 등록 안 함','OS 알림 미전송; 가상 시각의 DB 수신함 기록만 검증',
         '임베딩 검색·충돌 날짜 수동 수정·이동 중 강제종료 복구는 미구현'])
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (root/'snapshots.json').write_text(json.dumps(snapshots,ensure_ascii=False,indent=2))
    rows=['# 로컬 실험 결과','',f'실행: {NOW.isoformat()}',f'경로: {root}','',
       '로컬 Vision OCR + 규칙 기반 베이스라인. 외부 LLM 호출 없음. 실험용 합성 자료만 처리.','',
       f"초기 고유 자료 {len(fixtures)}개 + 연장 PDF 1개 + 바이트 복사본 1개. 초기 스캔 {elapsed}초.",
       f"분류 일치: {sum(r['category_correct'] for r in per_file)}/{len(per_file)}. 기한 값 일치(null 포함): {sum(r['deadline_correct'] for r in per_file)}/{len(per_file)}.",
       '', '| 시나리오 | 결과 |','|---|---|']
    rows += [f"| {c['name']} | {'PASS' if c['passed'] else 'FAIL'} |" for c in checks]
    rows += ['', '## 한계', ''] + ['- '+s for s in report['limitations']]
    rows += ['', '## OCR 근거', '', 'Apple Vision 텍스트 인식: https://developer.apple.com/documentation/vision/vnrecognizetextrequest']
    (root/'결과.md').write_text('\n'.join(rows))
    (PROJECT/'experiments/latest.json').write_text(json.dumps({'root':str(root)},ensure_ascii=False))
    engine.db.close()
    print(json.dumps(dict(root=str(root),metrics=report['metrics'],failed=[c for c in checks if not c['passed']],per_file=per_file),ensure_ascii=False,indent=2))
    return root

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--pipeline',choices=['legacy','local_v2'],default='legacy')
    run(parser.parse_args().pipeline)
