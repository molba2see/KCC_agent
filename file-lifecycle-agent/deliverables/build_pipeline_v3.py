from pathlib import Path
from html import escape
R=Path(__file__).parent

def canvas(title,subtitle,height):
    return [f'''<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="{height}" viewBox="0 0 1500 {height}"><defs><marker id="a" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L7,4 L0,8" fill="#8c9db8"/></marker></defs><rect width="1500" height="{height}" rx="20" fill="#f5f7fb"/><g font-family="Apple SD Gothic Neo,Noto Sans KR,sans-serif"><text x="50" y="43" font-size="15" fill="#4f46e5" font-weight="700">FILE LIFECYCLE AGENT · v3 · 2026.11.02 · 설계</text><text x="50" y="92" font-size="33" fill="#14213a" font-weight="800">{escape(title)}</text><text x="50" y="128" font-size="18" fill="#64748b">{escape(subtitle)}</text>''']

def box(p,x,y,w,h,title,lines,color='#047857',dash=False):
    p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="white" stroke="{color}" stroke-width="1.5" '+('stroke-dasharray="7 5"' if dash else '')+'/>')
    p.append(f'<rect x="{x+16}" y="{y+18}" width="4" height="{h-36}" rx="2" fill="{color}"/><text x="{x+31}" y="{y+35}" font-size="20" fill="{color}" font-weight="700">{escape(title)}</text>')
    for i,line in enumerate(lines):p.append(f'<text x="{x+31}" y="{y+65+25*i}" font-size="16" fill="#475569">{escape(line)}</text>')
def arrow(p,d,dash=False):p.append(f'<path d="{d}" fill="none" stroke="#8c9db8" stroke-width="2" marker-end="url(#a)" '+('stroke-dasharray="7 5"' if dash else '')+'/>')
def save(p,name):
    svg=''.join(p)+'</g></svg>';(R/(name+'.svg')).write_text(svg);return svg

p=canvas('파일을 작업에 연결하고, 필요한 관계를 보존하며 정리합니다','S0 데이터 경계 → S1–S7 제품 처리 · 기존 모듈 재사용과 추가 구현 범위를 구분합니다.',1380)
steps=[('S1  수집·파일 식별',['안정화 → 자료 ID / 해시 / 경로 이력'], '#2563eb'),
('S2  내용·메타데이터 추출',['PDF / OCR → 본문·페이지·좌표·추출 상태'],'#2563eb'),
('S3  기존 작업·관련 파일 후보 검색',['파일명 + 본문 + 허용 경로·프로젝트 문맥'],'#047857'),
('S4  프로젝트 귀속·묶음·관계 제안',['첨부 / 복사본 / 버전 후보 / 명시적 참조'],'#047857'),
('S5  원문·식별자·참조 검증',['허위 근거·없는 경로·충돌 → 확인 또는 보류'],'#047857'),
('S6  상태·보관 정책 → 정리 계획',['진행 / 완료 / 재개 + 공유 참조 → 유지·보관'],'#047857'),
('S7  허용 정책에 따른 실행·복구',['묶음 확인 → 실행 직전 검사 → 이력·되돌리기'],'#2563eb')]
for i,(t,lines,c) in enumerate(steps):
 y=180+i*140;box(p,440,y,640,110,t,lines,c)
 if i<6:arrow(p,f'M760 {y+110} V{y+133}')
box(p,45,180,340,175,'S0  로컬 입력',['허용한 다운로드·프로젝트 폴더','기존 폴더 / README / 승인 자료','개인 파일은 허용 범위만 읽기'],'#2563eb')
arrow(p,'M385 267 H432')
box(p,45,415,340,175,'S0  HippoCamp 입력',['선택 프로필의 원본 · 읽기 전용','작업은 별도 sandbox 복사본','QA 정답·Gold는 기본 입력 제외'],'#7c3aed')
arrow(p,'M385 502 H410 V235 H432')
box(p,1130,180,325,175,'의미 추출기 · 선택',['로컬 규칙 또는 LLM 어댑터','OpenAI 키는 서버 환경변수','유료 실험은 아직 미실행'],'#d97706',True)
arrow(p,'M1130 267 H1110 V655 H1088',True)
box(p,1130,415,325,175,'관계의 근거',['단순 유사도는 후보 신호','명시적 ID / 경로 / 매니페스트','확인된 관계와 추정을 분리'],'#047857')
box(p,1130,650,325,175,'모호하면 묶음 확인',['무조건 옮기지 않고 보류','대표 질문 한 번으로 귀속 확인','유지·거절 이력은 반복 억제'],'#64748b')
arrow(p,'M1130 735 H1105 V940 H1088',True)
box(p,45,650,340,175,'상태·보존 원칙',['완료는 명시적 사용자 사건','날짜·파일 열기만으로 완료 금지','모델 가중치는 임의 로드 금지'],'#64748b')
box(p,45,885,340,175,'이번 구현 범위',['재사용: 로컬 감지·PDF/OCR','재사용: SQLite·단일 파일 undo','추가: 프로젝트 검색·관계·계획'],'#64748b')
box(p,1130,885,325,175,'현재 필수가 아닌 도구',['웹 크롤링 / 다중 에이전트','전 디스크 감시 / 파인튜닝','원본 URL 감시는 별도 확장'],'#64748b')
box(p,45,1190,1410,105,'공유 기억 · SQLite',['자료 ID / 원본·현재 경로 / 추출·근거 / 프로젝트 / 관계 / 상태 사건 / 보관 정책 / 계획 / 실행 이력'],'#334155')
p.append('<text x="50" y="1342" font-size="17" fill="#64748b">파랑: 기존 모듈 재사용·확장   ·   초록: 추가 구현 설계   ·   보라: 평가 데이터   ·   도식은 전체 구현 완료를 뜻하지 않습니다.</text>')
a=save(p,'파일관리_v3_제품파이프라인')

p=canvas('HippoCamp는 검색·근거 평가에, 추가 시나리오는 정리·보존 평가에','정답은 채점기에만 전달합니다. 모델 입력과 정답 저장소를 분리합니다.',1100)
box(p,50,180,650,140,'평가 트랙 A · HippoCamp 원본',['question + 허용된 원본·메타데이터만 Agent에 제공','raw 추출 / 검색 / 관계·근거 검증 → 답변·파일 ID'],'#7c3aed')
box(p,800,180,650,140,'채점기 전용 · 모델 입력 차단',['answer / 정답 file_path / evidence / rationale','QAID·QANum 연결 열 → 인덱스에서 제거'],'#dc2626')
box(p,50,380,650,165,'E0–E3  읽기·검색·연결을 분리해서 평가',['E0 경로·형식·데이터 누수 점검','E1 raw 추출 vs Gold-text 보조 조건','E2 검색 기준선 / E3 관계·프로젝트 추가 라벨'],'#7c3aed')
box(p,800,380,650,165,'검색·근거 지표',['Recall@k / MRR / 정답 파일 집합 회수','인용·경로 검증 / 잘못된 귀속 / 처리 coverage','Gold 텍스트는 별도 조건, 공식 raw 점수와 구분'],'#dc2626')
arrow(p,'M375 320 V373');arrow(p,'M1125 320 V373');arrow(p,'M700 462 H792')
box(p,50,610,650,165,'평가 트랙 B · 직접 작성하는 사건·정답',['파일 유입 → 다른 버전 → 작업 완료 → 재개','허용 목적지 / 관계 / 유지·보관 / 사용자 확인','데이콘 가중치·코드는 작은 묶음의 확장 사례'],'#047857')
box(p,800,610,650,165,'E4–E7  복사본 sandbox 실행 평가',['E4 정리 후 작업 유지 / E5 라이프사이클','E6 충돌·중단·복구 / E7 모델 파일 묶음 보호','원본·필수 참조 보존 + 사용자 부담 + 자동 처리율'],'#047857')
arrow(p,'M700 692 H792')
box(p,50,850,1400,145,'먼저 할 일과 결과 해석',['① E0 매핑·원본 판독 확인 → ② E2 파일명/BM25 → ③ E1 추출 한계 분리 → ④ E3–E5 묶음·상태 효과','subset 주석 56문항 중 PDF·일반 이미지 형식 후보 19개 확인. 모델 성능은 아직 측정하지 않았습니다.','HippoCamp의 QA 동시 근거를 같은 프로젝트·버전 정답으로 간주하지 않습니다. 정리·보존 라벨은 별도 작성합니다.'],'#334155')
b=save(p,'파일관리_v3_데이터실험설계')
html='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>파일 관리 v3 · 데이터와 실험</title><style>body{margin:0;background:#f5f7fb;color:#14213a;font:17px/1.7 -apple-system,sans-serif}main{max-width:1550px;padding:20px;margin:auto}.diagram{overflow:auto;border:1px solid #dce3ee;border-radius:18px;margin:20px 0}svg{display:block;width:100%;height:auto;min-width:1050px}a{color:#4f46e5}p{padding:10px 20px}</style><main><p><strong>파일 관리 v3 · HippoCamp 활용 설계</strong> — 현재 로컬 모듈과 앞으로 구현할 프로젝트·관계·계획을 구분했습니다.</p><div class="diagram">'''+a+'''</div><div class="diagram">'''+b+'''</div><p><a href="HippoCamp_활용_파이프라인_실험계획.md">단계별 근거·실험·작업계획</a> · <a href="HippoCamp_데이터점검.json">실제 사전 점검 JSON</a></p></main></html>'''
(R/'파일관리_v3_파이프라인.html').write_text(html)
print('Created two SVG diagrams and HTML overview')
