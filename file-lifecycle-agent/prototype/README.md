# 임시 자료 라이프사이클 관리 — 로컬 실험

## v2 보강 · 2026-11-02

현재 새 실험에는 문맥 추출·원문 검증·행사 식별자 비교를 연결했다. 기존 실패 사례 비교는 v1 2/6 → 로컬 v2 6/6, 추가 PNG 통합 6/6, 기존 파일·상태 시나리오 24/24, 원문 검증·API 경계 오프라인 테스트 16/16이다. 같은 실패를 보고 개선한 회귀 검증으로 일반화 성능은 아니다.

```sh
.venv/bin/python prototype/experiment.py --pipeline local_v2
.venv/bin/python prototype/compare_v2.py
.venv/bin/python prototype/test_pipeline_v2.py
.venv/bin/python prototype/run_demo.py --port 8766
```

현재 비교 화면은 http://127.0.0.1:8766 이다. 실험 데이터는 새 폴더에 만들고 v1 결과는 보존한다. 아래의 `challenge.py`와 기본 `experiment.py` 명령은 v1 재현용이므로 v2 결과에 혼용하지 않는다.

OpenAI Responses 구조화 출력 연결 코드도 추가했다. 기본값은 로컬 실행이며 외부 전송은 비활성이다. 합성 텍스트 8회 이하의 실제 API 비교는 다음 명령으로 별도 실행한다. 터미널에서 API 키를 숨김 입력하며 파일에 저장하지 않는다. 현재까지 유료 실호출은 하지 않았다.

```sh
.venv/bin/python prototype/run_openai_eval.py
```

예제 모델은 `gpt-4.1-mini`이며 `OPENAI_MODEL`로 바꿀 수 있다. `.env.example`은 설명용이고 자동으로 로드되지 않는다. API 실제 접근·한도·모델 품질은 키 연결 후 검증해야 한다. API 테스트 16개 중 제공업체 경계 검사는 모의 응답을 사용한다.

자세한 분석과 그림은 [v2 분석](../deliverables/파이프라인_v2_분석.md)을 참고한다. v2에서도 주최자·행사일이 모두 없는 동명 행사의 구분, 의미상 별칭, 복잡한 표, 수동 필드·묶음 수정, 재처리, OS 알림, 크롤링, 이동 중 강제 종료 복구는 남아 있다.

## v1 실험 재현과 공통 구성

로컬 Vision OCR, Poppler PDF 추출, 명시적 규칙, SQLite 상태 저장을 연결한 실행 가능한 첫 베이스라인이다. 외부 LLM 호출이나 API 키 없이 동작한다. 의미 추출 모델을 붙이기 전에 파일·상태 흐름을 확인하는 목적이다.

## 실행

macOS, Python 3.10 이상, Swift 컴파일러, Poppler가 필요하다. 이번 실행에서는 uv가 선택한 Python 3.14.3과 프로젝트의 `.venv`를 사용했다.

```sh
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
mkdir -p prototype/bin
swiftc prototype/ocr.swift -o prototype/bin/ocr
.venv/bin/python prototype/experiment.py
.venv/bin/python prototype/challenge.py
.venv/bin/python prototype/run_demo.py
```

브라우저에서 http://127.0.0.1:8765 를 연다. 서버는 localhost에만 바인딩된다. `Ctrl+C`로 종료한다. 서버를 다시 실행하면 `experiments/latest.json`이 가리키는 마지막 실행의 DB 상태를 불러온다.

## 무엇을 만드나

매 실험마다 `experiments/run_실행시각/` 안에 다운로드·스크린샷·보관 폴더와 SQLite DB, 합성 정답, 실행 전후 스냅샷, 상세 JSON 결과, `결과.md`가 생긴다. 실제 사용자의 다운로드 폴더는 감시하거나 이동하지 않는다.

본문이 있는 PDF 6개, 스캔 PDF 1개, PNG 6개를 생성한다. 연장 공고 1개는 초기 수집 이후 넣는다. 바이트 복사본은 별도로 두 개 투입한다. 정답 파일은 엔진 입력으로 사용하지 않는다. 생성일을 기준으로 미래·과거 날짜를 만들어 재실행할 수 있다.

자동 실험이 완료되면 행사 신청은 완료 상태이고, 한 자료는 유지 상태다. 실제 보관 이동과 충돌 방지·되돌리기가 실행된 이력이 남는다. 남은 정리 후보에서 보관·되돌리기를 직접 눌러볼 수 있다. 알림은 예약·취소와 명시적 가상 시각의 DB 수신함 기록을 검증하며 실제 OS 알림은 보내지 않는다.

UI의 `폴더 스캔`으로 실험 폴더를 다시 읽을 수 있다. 별도 폴더 자동 감시는 다음 명령을 실행한다. 실험 스크립트도 별도 감시 프로세스를 잠시 띄워 신규 복사본 감지를 확인한 뒤 종료한다.

```sh
.venv/bin/python prototype/app.py watch --root 'experiments/run_실행시각'
```

## 현재 한계와 다음 실험

- 분류·날짜 추출은 규칙 기반이다. 줄바꿈된 날짜, 행동 부정 표현, 복잡한 날짜 충돌에 취약하다.
- 묶음은 첫 줄 제목 일치에 의존한다. 같은 제목의 다른 행사와 서로 다른 제목의 같은 행사를 구분하지 못한다.
- 검색은 텍스트 포함 검색이다. 임베딩 검색은 미구현이다.
- 미분류 확인 UI는 원문과 사유를 보여준다. 추출값을 수동 수정하는 기능은 아직 없다.
- 이동은 같은 볼륨의 하드 링크·검증·원본 경로 제거로 구현한다. 충돌 시 덮어쓰지 않는다. 정상 실패와 되돌리기는 검증했지만 이동 중 강제 종료 복구는 아직 없다.
- 실험 중 규칙을 수정한 합성 개발 사례라서 분류·기한의 높은 일치율을 일반 성능으로 해석하면 안 된다. 추가 난도 사례의 실패도 결과에 함께 기록한다.

다음에는 `understand()`를 근거가 포함된 구조화 출력 모델로 교체하고, 주최자·행사일·본문 식별자를 사용한 묶음을 비교한다. 한국어 실문서의 복사본으로 별도 고정 평가셋을 만들어 B1/B2/B3를 측정해야 한다.

OCR 구현 참고: [Apple Vision VNRecognizeTextRequest](https://developer.apple.com/documentation/vision/vnrecognizetextrequest).

## v3 프로젝트·관계·상태 실행 기준선

```sh
.venv/bin/python prototype/run_v3.py
.venv/bin/python prototype/v3_ablation.py
```

`lifecycle_v3.py`는 허용 sandbox에서 자료 ID·해시·경로, 명시적 project_id 귀속, REF 참조 보호, 완료/활성 상태, 보관 계획 재검증, 무덮어쓰기 이동, 중단 저널 복구 및 undo를 연결한다. 모호한 프로젝트와 참조를 가진 파일의 이동은 보류한다. 프로젝트 의미 추론 LLM이나 임베딩은 포함하지 않은 결정적 기준선이다. `.pth`는 읽거나 실행하지 않는다.

`run_v3.py`는 고정 revision의 Adam/Bei subset에서 PDF/일반 이미지·개별 5MB 이하인 **모든** 파일을 검색 corpus로 수집하므로 정답 파일 외 방해 파일도 포함한다. 추론 검색기는 question·원본 추출문·허용 경로만 받는다. 채점기가 별도로 target file_path를 비교한다. 형식·크기 제외와 추출 실패도 JSON에 남는다. 질문/답변/라벨은 인덱스에 넣지 않는다. 다운로드 및 원문은 git에서 제외된다.

사전 주석 점검 폴더는 `HIPPOCAMP_AUDIT_ROOT`로 지정한다. 기본은 이번 연구 세션의 `/private/tmp/hippocamp-data-audit-20261102`. 사전 manifest가 없으면 명시적으로 실패한다. 인터넷·macOS Vision 실행파일·Poppler가 필요하며 유료 API나 cv01은 필요하지 않다.

통제 사례는 반복 템플릿으로 만든 개발/회귀 검증이며 실제 사용자의 일반화 정확도가 아니다. 가중치 검증은 비실행 dummy bytes와 명시적 참조를 사용한다. 대규모 묶음 트랜잭션·undo 도중 강제 종료·다른 볼륨 이동·동시 외부 변경의 완전 보장은 구현하지 않았다. 실사용 전체 폴더 자동 이동은 아직 허용하지 않는다.
