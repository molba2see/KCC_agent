from pathlib import Path
from html import escape
R=Path(__file__).parent
parts=['''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1350" viewBox="0 0 1600 1350"><defs><marker id="a" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L7,4 L0,8" fill="#8c9db8"/></marker></defs><rect width="1600" height="1350" rx="24" fill="#f5f7fb"/><g font-family="Apple SD Gothic Neo,Noto Sans KR,sans-serif"><text x="55" y="56" font-size="15" fill="#4f46e5" font-weight="700">SAVE &amp; REMIND · PIPELINE v0.2</text><text x="55" y="105" font-size="36" fill="#15213b" font-weight="800">임시 자료의 목적·기한·사용 상태를 연결하는 파이프라인</text><text x="55" y="147" font-size="19" fill="#64748b">로컬 도구가 자료를 읽고, 추출 결과를 검증한 뒤 상태에 맞는 행동만 실행합니다.</text>''']
def box(x,y,w,h,title,lines,color='#2563eb',dashed=False):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="15" fill="white" stroke="{color}" stroke-width="1.5" '+('stroke-dasharray="7 5"' if dashed else '')+'/>')
    parts.append(f'<rect x="{x+18}" y="{y+20}" width="4" height="{h-40}" rx="2" fill="{color}"/>')
    parts.append(f'<text x="{x+35}" y="{y+37}" font-size="21" fill="{color}" font-weight="700">{escape(title)}</text>')
    for i,line in enumerate(lines):parts.append(f'<text x="{x+35}" y="{y+69+i*26}" font-size="16" fill="#475569">{escape(line)}</text>')
def arrow(d,dashed=False):parts.append(f'<path d="{d}" fill="none" stroke="#8c9db8" stroke-width="2" marker-end="url(#a)" '+('stroke-dasharray="6 5"' if dashed else '')+'/>')
box(55,195,350,150,'입력 · 지금 필요한 도구',['허용된 로컬 폴더만 감시','다운로드 완료 확인 → 해시 중복 검사','파일 원본은 처음부터 이동하지 않음'])
box(55,385,350,150,'원문 읽기 · 로컬 실행',['PDF 텍스트 추출: Poppler','이미지 / 스캔 PDF: macOS OCR','텍스트 · OCR 페이지·좌표 보존'])
arrow('M230 345 V378')
box(470,195,650,150,'① 문맥을 묶어서 추출 · 보강',['줄바꿈된 날짜를 앞뒤 문장과 연결','목적 / 행동 필요 여부 / 기한 종류를 분리','행사명 · 주최자 · 행사일과 원문 인용 추출'],'#7c3aed')
box(470,385,650,150,'② 원문 근거·날짜 검증 · 보강',['인용이 실제 원문에 있는가? 날짜를 코드로 재계산','연도·시간 누락 / 날짜 충돌 / 부정 표현은 재검토','근거가 부족하면 자동 알림을 보류하고 확인 요청'],'#7c3aed')
box(470,575,650,150,'③ 같은 행사인지 판별 · 보강',['문서 제목 대신 행사명 + 주최자 + 행사일 사용','알려진 식별자가 충돌하면 별개 자료로 유지','후보가 여러 개면 자동 병합 대신 확인 대기'],'#7c3aed')
box(470,765,650,150,'④ 상태 기반 다음 행동 · 기존 흐름 연결',['기한 + 행동 필요 + 미완료 → 묶음 알림 1개','연장 공고 → 확인 후 이전 예약 취소·교체','명시적 완료 → 알림 취소 / 증빙 유지 / 정리 제안'],'#047857')
box(470,955,650,125,'⑤ 사용자 확인 후 실행 · 기존 구현',['보관 이동 → 해시 검증 → 이력 → 되돌리기','이름 충돌·파일 변경 시 덮어쓰지 않고 중단'],'#047857')
for y in [345,535,725,915]:arrow(f'M795 {y} V{y+33}')
arrow('M405 460 H437 V270 H462')
box(1180,195,365,150,'ChatGPT 계열 모델 · 선택',['OpenAI Responses 구조화 출력','서버 환경변수로 API 키 설정','연결 어댑터 구현 / 유료 호출 미실행'],'#d97706',True)
arrow('M1180 270 H1128',True)
box(1180,385,365,150,'키가 없을 때 · 실행 경로',['로컬 보강 규칙으로 동작','AI 모델을 사용한 결과와 구분','동일 사례로 v1 / v2 비교'],'#64748b')
box(55,575,350,180,'원문 URL 변경 감시 · 후속',['등록된 공식 URL만 주기 확인','HTML / PDF 가져오기 → 내용 차이','변경 자료를 동일 추출 경로로 입력','현재 로컬 MVP의 필수 도구 아님'],'#d97706',True)
arrow('M405 660 H437 V300 H462',True)
box(55,795,350,205,'실패하면 어디로?',['읽기 실패 → 검토함 (재시도 후속)','기한 불명확 → 알림 보류','식별자 충돌 → 별도 자료 유지','이동 충돌 → 원본 유지','사용자 확인 결과는 이력으로 저장'],'#64748b')
box(1180,575,365,180,'이번 실패의 실제 원인',['날짜를 한 줄씩만 읽었음','신청 불필요를 해석하지 않았음','첫 줄 제목만으로 자료를 묶었음','→ 문맥 / 근거 / 식별자를 추가'],'#dc2626')
box(1180,795,365,205,'크롤링·도구 선택 기준',['폴더 감시 / PDF / OCR: 현재 필요','SQLite / 예약 / 이동: 현재 필요','OpenAI API: 의미 추출용 선택','URL 감시: 공고 자동 갱신 시 필요','웹 검색·광범위 크롤링: 우선 제외'],'#64748b')
box(55,1130,1490,110,'공유 기억 · SQLite',['자료 해시·경로 / 추출기·프롬프트 버전 / 원문 근거 / 행사 식별자 / 상태·알림 버전 / 사용자 확인 / 이동 이력'],'#334155')
parts.append('<text x="55" y="1290" font-size="17" fill="#64748b">보라: 이번 보강 단계   ·   초록: 검증된 실행 흐름   ·   주황 점선: 외부 API 또는 후속 기능   ·   로컬 경로에는 크롤링이 필요하지 않습니다.</text></g></svg>')
svg=''.join(parts);(R/'임시자료_파이프라인_v2.svg').write_text(svg)
html='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>임시 자료 파이프라인 v2</title><style>body{margin:0;background:#f5f7fb;font:17px/1.7 -apple-system,sans-serif;color:#15213b}main{max-width:1600px;margin:auto;padding:20px}svg{display:block;width:100%;height:auto;min-width:1000px}.canvas{overflow:auto;border:1px solid #dce3ee;border-radius:20px}p{padding:0 20px}a{color:#4f46e5}</style><main><div class="canvas">'''+svg+'''</div><p><strong>현재 로컬 MVP는 크롤링 없이 동작합니다.</strong> 공고가 바뀌었는지 자동 확인할 때만 등록 URL 변경 감시를 추가합니다.</p><p><a href="http://127.0.0.1:8765">실험 화면</a> · <a href="임시자료_파이프라인_v2.svg" download>SVG 다운로드</a> · <a href="파이프라인_v2_분석.md">실패 원인과 보강 결과</a></p></main></html>'''
(R/'임시자료_파이프라인_v2.html').write_text(html)
print('Pipeline v2 SVG and HTML generated')
