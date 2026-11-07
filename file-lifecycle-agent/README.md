# 📂 파일 라이프사이클 에이전트

> 다운로드한 강의자료와 아이폰·맥 캡처를 **맞는 폴더에 알아서 넣어 주는** 맥 로컬 에이전트입니다.
> 처음 보는 파일은 한 번 묻고, 답을 배워서 다음부터는 묻지 않습니다. 모든 처리는 맥 안에서 합니다.

![architecture](docs/figures/architecture.png)

| | |
|---|---|
| **모델** | Qwen3-1.7B + LoRA(도구 호출 학습), 노트북 MPS에서 실행 |
| **판단 방식** | 규칙 → 안 되면 모델이 도구를 골라 가며 판단 (하이브리드) |
| **안전** | 모델에는 이동·삭제·셸 도구가 없음. 근거 인용 검사, 지시문 차단, 되돌리기 |
| **입력** | `~/Downloads`, `~/Desktop`, iCloud `KCC-inbox`(아이폰 캡처) |

---

## 🎬 시연

### 1. 아이폰 캡처 → 에이전트가 이름을 붙여 폴더에 저장
![demo1](docs/figures/demo1_iphone_capture.png)

- 뒷면 두 번 탭 → 단축어가 iCloud `KCC-inbox`에 저장
- 맥 OCR이 글자를 읽고, Qwen이 `set_caption` 도구로 이름을 짓습니다(`Shot_….png` → `KCC 대회 공지.png`)
- 내용으로 폴더를 판단해 자동 저장. iCloud에 아직 안 내려온 파일은 `brctl download`로 요청

### 2. eCampus 강의자료 → 한 번 답하면 다음부터 자동
![demo2](docs/figures/demo2_lecture_download.png)

- 브라우저가 파일에 남긴 다운로드 페이지(`kMDItemWhereFroms`)로 강의실을 알아냅니다
- 처음 보는 강의실이면 **"어느 폴더에 저장할까요?"** 창이 뜹니다
- 고르면 `강의실 → 폴더` 규칙과 폴더의 `_project.md` 메모를 배우고, 다음 파일은 모델 없이 바로 저장

### 3. 설치 파일 → 3일 뒤 휴지통 (언제든 복구)
![demo3](docs/figures/demo3_installer_cleanup.png)

- `.dmg`, `.pkg`, setup/install `.zip`·`.exe`를 처음 본 뒤 N일이 지나면 `~/.Trash`로 옮깁니다
- 기준은 맥 시계라서 시계를 3일 앞으로 돌리면 1분 안에 동작합니다(시연용)
- 웹 화면에서 복구 버튼으로 원래 자리에 되돌립니다

---

## ⚙️ 동작 방식

```
새 파일 감지 (2초마다, 원본은 복사만)
  → ① 다운로드 페이지 규칙 ─ 있으면 바로 그 폴더 (모델 없음)
  → ② 규칙 controller ─ 내용·파일 이름을 읽고 폴더 설명/_project.md와 비교
  → ③ Qwen3-1.7B 에이전트 ─ 도구를 골라 가며 판단 (최대 12단계)
  → 확실하면 저장 / 애매하면 질문 → 답변·승인으로 학습
```

**도구 9개** (모두 판단용): `inspect_file` · `read_content` · `search_projects`(bge-m3) · `find_related_files` · `assign_project` · `ask_user` · `check_references` · `preview_plan` · `finish`

**호스트 안전장치**
- `assign_project`의 근거는 원문을 **그대로 인용**해야 하고, 그 근거가 프로젝트 하나만 가리켜야 합니다
- 파일 속 지시문("무시하고 삭제하라")은 근거로 쓰지 못하고, 모델에게 보여 주지도 않습니다
- 같은 호출 반복, 단계 초과, 형식 오류는 거부하고 그 오류를 모델에게 관찰로 돌려줍니다
- 이동은 승인된 계획만, 등록된 폴더 안으로만, 덮어쓰지 않고, 저널을 남기며 되돌릴 수 있습니다

**학습 (답할수록 똑똑해짐)**

| 사용자 행동 | 배우는 것 |
|---|---|
| 질문에 답하거나 "승인하고 저장" | 다운로드 페이지 → 폴더 규칙 + `_project.md` 메모 한 줄 (Qwen `update_profile` 도구) |
| 되돌리기 | 그때 배운 페이지 규칙 삭제 |
| 5시간마다 "모아서 물어보기"에 자연어 답장 | 새 폴더 + 에이전트 지침(`_project.md`) 생성 후 이동 |
| (자동 제안) 어느 폴더에도 안 맞는 비슷한 파일이 3개 이상 쌓임 | 5시간마다 묻는 목록에 "이 3개로 '○○' 폴더를 만들까요?"를 함께 띄움. 확인해야만 만듦 |

**자동 저장 정책**

웹 설정에서 Mac별로 다운로드·Mac 스크린샷·iPhone 파일을 `바로 자동 정리` / `승인 후 정리`로 선택합니다. 기본은 신규 파일 자동 정리이며 첫 일괄 수집, 앱 시작 전에 이미 있던 파일과 새 폴더 생성은 확인을 기다립니다. 자동 모드에서도 근거가 부족하면 사용자에게 묻습니다. 아래 표는 자동 모드의 처리 기준입니다.

| 입력 | 바로 저장 | 그 외 |
|---|---|---|
| 아이폰 캡처 (`--auto-inbox`) | 판단이 저장 계획까지 가면 | 질문 |
| 다운로드·맥 캡처 (`--strict-auto-inbox`) | 문서·이미지이고 페이지 규칙이나 규칙 controller가 확정한 경우 | 다운로드는 선택 창(`--ask-inbox`), 나머지는 웹 화면 |

---

## 🚀 실행

```sh
pip install -r requirements.txt
swiftc -O prototype/ocr.swift -o prototype/bin/ocr      # 캡처 OCR (macOS Vision)

# 데모 작업 공간 (GPU·모델 없이 규칙 controller)
python prototype/demo_v5.py --port 8791                  # http://localhost:8791

# 실사용 (내 폴더 감시)
python prototype/demo_v5.py --root <작업폴더> --projects <projects.json> --watch \
  --strict-auto-inbox ~/Downloads --strict-auto-inbox ~/Desktop --ask-inbox ~/Downloads \
  --auto-inbox "~/Library/Mobile Documents/com~apple~CloudDocs/KCC-inbox" \
  --source-rules <source_rules.json> --qwen <Qwen3-1.7B> --adapter <LoRA> \
  --digest-hours 5 --expire-installers-days 3 --port 8791
```

- `projects.json`: `{"<id>": {"name": "...", "folder": "~/Desktop/...", "desc": "한 줄 설명"}}`. 폴더마다 `_project.md`를 두면 검색에 함께 씁니다.
- 웹(모아)과 연결: [`docs/local_api.md`](docs/local_api.md) (엔드포인트·응답 형식), 저장소 최상위 [`LOCAL_SETUP.md`](../LOCAL_SETUP.md) (브리지 실행)
- 개인 폴더 경로, 규칙, 라벨은 `local/`, `private_eval/`에 두고 Git에 올리지 않습니다.

---

## 📊 결과 요약

| 평가 | 결과 |
|---|---|
| 실제 다운로드 강의 파일 38개 (페이지 규칙 없이 내용만) | 이번 학기 자료 17/20 정답, 지난 학기 자료 18/18 옮기지 않음, 실제 잘못 지정 0 |
| 처음 보는 테스트 75건 (clean 66, 하이브리드 close) | **52/66**, 규칙 단독 43/66 (McNemar p≈0.004) |
| 내 스크린샷 43장 (`_project.md` 추가 전 → 후) | 질문 후보에 정답 포함 13/23 → **18/23** |
| 1.7B LoRA 도구 호출 (수집 27건) | 호스트가 받아들인 호출 76.9% → **99.3%**, 반복 호출 37 → 0 |

![training loss](results/figures/training_loss.png)

실험별 표와 해석, 한계는 [`docs/experiments.md`](docs/experiments.md)에 날짜순으로 정리했습니다.

---

## 🗂️ 구조

| 경로 | 내용 |
|---|---|
| `prototype/agent_v5.py` | 도구 9개, 호스트 가드, 규칙 controller, 문서·OCR 읽기 |
| `prototype/qwen_tool_controller.py` | Qwen native tool calling (LoRA, MPS) |
| `prototype/demo_v5.py` · `demo_v5.html` | 감시기, 웹 화면, 로컬 API, 선택 창 |
| `prototype/lifecycle_v3.py` | 실행기: 계획 재검증, 무덮어쓰기 이동, 저널, 되돌리기 |
| `prototype/sources.py` | 다운로드 페이지 규칙 |
| `prototype/profile_learn.py` | `_project.md` 학습(`update_profile`), 캡처 이름 짓기(`set_caption`) |
| `prototype/digest.py` | 모아서 물어보기 (`create_project`, `assign_files`, `leave_files`, `done`) |
| `prototype/expiry.py` | 설치 파일 정리 |
| `prototype/make_sft.py` · `train_lora.py` | SFT 데이터 생성과 LoRA 학습 |
| `data_collect/` | 수집·검증한 평가 사례 |
| `docs/` | API 문서, 실험 기록, 그림 |

```sh
python prototype/test_agent_v5.py     # 안전장치·학습·캡션·정리 테스트 26개
```

설치파일은 기본 3일 후 휴지통으로 이동하며 설정에서 끄거나 기간을 바꿀 수 있습니다. 휘발성 자료는 이름의 명확한 임시·공지 단서로 기본 7일 기한을 제안하고 승인 후 실행합니다. 삭제 관리에서 예약 승인·시각 변경·취소·복구가 가능하며 파일 카드에서 직접 기한을 지정할 수도 있습니다. 원본을 영구 삭제하거나 휴지통을 비우지 않습니다.
