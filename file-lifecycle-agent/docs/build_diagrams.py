from pathlib import Path
from html import escape
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parent/'diagrams';ROOT.mkdir(exist_ok=True)
FONT='/System/Library/Fonts/AppleSDGothicNeo.ttc'
class Canvas:
 def __init__(self,title,sub,h=1120):
  self.im=Image.new('RGB',(1600,h),'#f7f9fc');self.d=ImageDraw.Draw(self.im);self.svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{h}" viewBox="0 0 1600 {h}"><rect width="100%" height="100%" fill="#f7f9fc"/>'];self.text(64,50,title,38);self.text(64,105,sub,22,'#536277')
 def text(self,x,y,t,size=24,color='#152238'):
  self.d.text((x,y),t,font=ImageFont.truetype(FONT,size),fill=color)
  self.svg.append(f'<text x="{x}" y="{y+size}" font-family="Apple SD Gothic Neo, sans-serif" font-size="{size}" fill="{color}">{escape(t)}</text>')
 def box(self,x,y,w,h,title,lines,color='#3267c8'):
  self.d.rounded_rectangle((x,y,x+w,y+h),radius=16,fill='white',outline=color,width=3);self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="white" stroke="{color}" stroke-width="3"/>');self.text(x+22,y+18,title,26,color)
  for i,s in enumerate(lines):self.text(x+22,y+60+i*31,s,21)
 def arrow(self,points,label=None):
  self.d.line(points,fill='#7788a0',width=4);x,y=points[-1];px,py=points[-2];dx,dy=x-px,y-py
  tip=[(x,y),(x-9,y-15),(x+9,y-15)] if dy>0 else [(x,y),(x-15,y-9),(x-15,y+9)] if dx>0 else [(x,y),(x+15,y-9),(x+15,y+9)]
  self.d.polygon(tip,fill='#7788a0');self.svg.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in points)+'" fill="none" stroke="#7788a0" stroke-width="4"/>');self.svg.append('<polygon points="'+' '.join(f'{x},{y}' for x,y in tip)+'" fill="#7788a0"/>')
 def save(self,name):self.im.save(ROOT/f'{name}.png');(ROOT/f'{name}.svg').write_text(''.join(self.svg)+'</svg>')
c=Canvas('파일 라이프사이클 에이전트 · 실행 구조','에이전트는 다음 행동을 선택합니다. 실행기는 허용 범위와 근거를 검증합니다.')
c.box(570,165,480,112,'01  입력과 목표',['허용된 파일 · 프로젝트 · 사용자 요청'])
c.box(570,325,480,145,'02  상태와 컨텍스트',['자료 ID · 관찰 결과 · 출처','프로젝트 상태 · 보존 정책'])
c.box(570,525,480,145,'03  Controller',['고정 / 규칙 / 모델을 같은 도구로 비교','탐색 · 질문 · 계획 · 종료 선택'],'#7750b6')
c.box(570,725,480,145,'04  Tool Gateway',['인자 스키마 · 허용 ID · 반복/예산 검사','검증을 통과한 호출만 실행'])
c.box(64,520,420,180,'도구와 처리 라우터',['텍스트/PDF/OCR · 프로젝트 검색','관련 파일 · 명시적 참조 검사','도구 결과를 관찰로 되돌림'],'#187e71')
c.box(1120,520,416,150,'모호하면 질문 후 대기',['귀속 · 유지 의사 확인','답변을 상태에 반영한 뒤 재개'],'#b37b22')
c.box(1120,725,416,150,'계획 → 승인된 실행기',['실행 직전 상태·해시·참조 재검증','이동 · 저널 · undo'],'#187e71')
c.box(64,935,1472,125,'공통 실행 기록 · 평가',['도구/인자/관찰 · 짧은 결정 근거 · 지연 · 토큰 · 오류 · 계획과 실제 실행 결과','비공개 사고 과정은 수집하지 않습니다. 원문·정답·운영 설정은 공개 저장소에 넣지 않습니다.'],'#536277')
for y in [277,470,670]:c.arrow([(810,y),(810,y+48)])
c.arrow([(570,795),(520,795),(520,610),(484,610)]);c.arrow([(274,520),(274,395),(570,395)])
c.arrow([(1050,600),(1120,600)]);c.arrow([(1050,800),(1120,800)])
c.save('agent-runtime')
c=Canvas('개발 · 평가 · 배포의 진행 구조','모델 학습은 첫 단계가 아닙니다. 관찰된 실패 원인에 맞춰 필요한 부분만 개선합니다.',940)
items=[('1  명세','목표 · 입력/출력 · 금지 행동'),('2  컨텍스트','시스템 프롬프트 · 근거 · 작업 메모리'),('3  도구 계약','타입 스키마 · 라우팅 · 권한'),('4  실행 제어','모델 선택 · 상태 · 종료 · 오류 처리'),('5  평가','성공 · 근거 · 호출 · 질문 · 비용'),('6  관찰과 개선','실패 분류 → 프롬프트/검색/학습 선택')]
for i,(a,b) in enumerate(items):
 col=i%3;row=i//3;x=64+col*500;y=190+row*250;c.box(x,y,460,170,a,[b]);
 if col<2:c.arrow([(x+460,y+85),(x+500,y+85)])
c.box(64,730,1472,140,'배포 및 피드백 · 단계별 통과 후 진행',['현재: 로컬 도구·규칙 controller 검증 / 다음: 서버 모델 tool calling 실측','그다음: 실제 프로젝트 평가 → 승인된 실행 연결 → 사용자 피드백 → 조건부 LoRA'],'#187e71');c.save('development-cycle')
