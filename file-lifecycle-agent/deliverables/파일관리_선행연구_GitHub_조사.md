# 임시 자료 라이프사이클 관리 — 선행연구·GitHub 조사

조사일: 2026-11-02. 범위는 ‘다운로드한 여러 파일을 내용·목적에 따라 분류하고, 사용 후 보관·정리를 돕는 에이전트’다. 행사 리마인더에 한정하지 않는다.

후속 심층 검토: [소스·논문 심층 분석과 차별화 전략](파일관리_심층분석_차별화전략.md). 특히 Local File Organizer의 확인한 실행 경로는 원본 이동이 아니라 하드링크/심볼릭 링크 생성이라는 점을 보완했다. 이 문서는 최초 탐색 기록이며 상세 구현 판단은 후속 분석을 우선한다.

공식 저장소 README·일부 소스와 논문 원문/초록을 확인했다. 아래 프로젝트를 설치하거나 같은 자료로 성능 비교한 것은 아니다. 기능 설명은 개발자 문서의 주장과 실제 확인 범위를 구분해 읽어야 한다. 특히 README의 기능 개수나 GitHub 별 수는 품질 검증 결과가 아니다.

## 핵심 판단

**AI 파일 자동 분류 자체는 이미 구현 사례가 많다.** 폴더 감시, 본문·이미지 이해, 자동 이름 변경, 미리보기, 되돌리기, 사용자 수정 반영도 기존 프로젝트에서 다룬다. 따라서 이 기능만으로 독창성을 주장하기 어렵다. [AI File Sorter](https://github.com/hyperfield/ai-file-sorter), [Local File Organizer](https://github.com/QiuYannnn/Local-File-Organizer), [폴더 감시형 예제](https://github.com/pneelamr/ai-file-organizer)

현재의 2~3단계 분류 데모를 제품으로 확장할 때는 기존 도구와 비교해야 한다. ‘다운로드 파일 자동 정리 + 프로젝트·사용 상태를 고려한 보관 판단’은 검증할 가설로 잡되, 이 조사만으로 선행 구현이 없다고 주장할 수는 없다.

## 1. 직접 관련된 GitHub 프로젝트

| 프로젝트 | 공식 문서에서 확인한 기능 | 우리에게 필요한 참고점 |
|---|---|---|
| [tfeldmann/organize](https://github.com/tfeldmann/organize) | 규칙 기반 분류, PDF/DOCX 텍스트 활용, 중복 찾기, 이동·복사·이름 변경, 충돌 처리, 사전 시뮬레이션 | LLM 없이도 되는 부분의 비교 기준선 |
| [QiuYannnn/Local-File-Organizer](https://github.com/QiuYannnn/Local-File-Organizer) | Nexa SDK의 로컬 텍스트·비전 모델로 문서·이미지 설명, 파일명·폴더명 생성, 링크 기반 정리 구조, dry-run | ‘내용 이해 → 메타데이터 → 정리 계획’ 구조가 직접 겹침. 원본 이동과 구분 필요 |
| [hyperfield/ai-file-sorter](https://github.com/hyperfield/ai-file-sorter) | 로컬·원격 LLM, 내용 기반 분류와 이름 제안, 사용자 검토, dry-run, 지속적 undo, 사용자 검토 결정을 통한 로컬 학습, 구조화된 프로젝트 폴더 보호 | 가장 먼저 기능을 비교할 제품형 사례. 프로젝트 내부 파일을 함부로 분해하지 않는 설계도 참고 |
| [pneelamr/ai-file-organizer](https://github.com/pneelamr/ai-file-organizer) | watchdog 새 파일 감지 → PDF/OCR → Ollama 분류 → 카테고리 폴더 이동, macOS 백그라운드 실행 안내 | ‘다운로드하면 알아서 정리’하는 최소 파이프라인이 거의 동일 |
| [TheYellowDuck/ai-file-organizer](https://github.com/TheYellowDuck/ai-file-organizer) | 오프라인 임베딩·외부 LLM 분류, OCR·비전, 분류 체계 생성, 이동 저널·undo, dry-run·copy 모드를 설명 | 추출·판단과 파일 실행을 나누고 실행 이력을 남기는 구조 참고. 문서상 기능을 실측으로 검증하지 않음 |
| [agiresearch/AIOS-LSFS](https://github.com/agiresearch/AIOS-LSFS) | 논문 공식 구현. 자연어 파일 관리, 의미 기반 연산, rollback 등. AIOS 설정과 rollback용 Redis 의존성 명시 | 논문·시스템 구조의 참고 대상. 작은 캡스톤에서 전체 프레임워크를 도입할지는 별도 판단 |

Local File Organizer에서 중복 탐지는 열람 당시 README의 미완료 roadmap 항목이었다. 지원 파일 유형과 실제 처리 품질도 구분해야 한다. [README](https://github.com/QiuYannnn/Local-File-Organizer#roadmap-)

재사용 시 저장소가 표시한 라이선스: organize·Local File Organizer·AIOS-LSFS는 MIT, AI File Sorter는 AGPL-3.0, TheYellowDuck 저장소는 PolyForm Noncommercial 1.0.0이다. pneelamr 저장소는 README에서 MIT라고 설명한다. 실제 가져올 파일의 LICENSE를 다시 확인해야 한다. 이는 저장소 표기 확인이며 법률 해석은 아니다. [organize](https://github.com/tfeldmann/organize), [Local File Organizer](https://github.com/QiuYannnn/Local-File-Organizer), [AIOS-LSFS](https://github.com/agiresearch/AIOS-LSFS), [AI File Sorter](https://github.com/hyperfield/ai-file-sorter#license), [TheYellowDuck](https://github.com/TheYellowDuck/ai-file-organizer#license)

## 2. 선행연구

### R1. Finding and Reminding: File Organization from the Desktop — 1995

Deborah Barreau, Bonnie A. Nardi. ACM SIGCHI Bulletin 27(3), 39–43. DOI: 10.1145/221296.221307.

파일 정리·찾기 사용자 연구를 종합하며 자료를 ephemeral / working / archived로 구분한다. 복잡한 분류 체계뿐 아니라 파일의 위치가 작업을 기억하게 하는 기능을 한다는 관찰을 제시한다. 우리의 임시 자료 → 사용 중 → 보관 상태 모델과 연결되는 개념적 근거다. 현대 다운로드 폴더나 LLM 에이전트의 효과를 입증한 연구는 아니다. [원문](https://www.ibiblio.org/msmckoy/spring2006/articles/fileOrganizationFromTheDesktop.pdf), [저자들의 1997년 후속 논의](https://homepages.cwi.nl/~steven/sigchi/bulletin/1997.1/nardi.html)

### R2. From Commands to Prompts: LLM-based Semantic File System for AIOS — ICLR 2025

Zeru Shi 외. arXiv:2410.11843. 2024년 최초 공개, 2025년 개정본과 arXiv의 ICLR 2025 채택 표기를 확인했다.

자연어로 파일을 검색·관리하는 LSFS를 제안한다. 의미 인덱스와 파일 연산 API를 바탕으로 검색, 업데이트 모니터링·요약, rollback과 버전 비교 등을 다룬다. 의미 기반 파일 관리와 복구 자체가 기존 연구라는 직접 근거다. 사용자에게서 내려받은 파일의 자동 정리 품질이나 프로젝트 종료 후 보존 판단까지 동일하게 평가했다고 해석하면 안 된다. [논문](https://arxiv.org/abs/2410.11843), [공식 코드](https://github.com/agiresearch/AIOS-LSFS)

### R3. HippoCamp: Benchmarking Contextual Agents on Personal Computers — 2026 프리프린트

Zhe Yang 외. arXiv:2604.01221, 2026-04-01 공개.

개인 컴퓨터의 다양한 파일에서 문맥을 이해하고 필요한 정보를 찾는 에이전트를 평가한다. 저자들은 42.4GB, 2천 개 이상 파일, 581 QA 쌍을 설명한다. 우리의 관련 파일 탐색·근거 연결 평가를 설계할 때 참고할 수 있다. 다만 핵심 평가가 파일 이동·삭제의 정답 검증인 것은 아니므로 별도 실행 평가가 필요하다. [논문](https://arxiv.org/abs/2604.01221), [공식 프로젝트 페이지](https://hippocamp-ai.github.io/)

### R4. Filesystem-Based Memory for LLM Agents: Organization, Evolution, and Sustainability — 2026 프리프린트

Sizhe Zhou 외. arXiv:2607.26637, 2026-07-29 공개.

에이전트의 장기 기억을 파일 트리로 관리할 때, 자료 증가와 충돌·노후화 속에서도 조직을 유지하는지 연구한다. 저자들은 정리의 검색 비용 이득과 답변 품질 이득이 반드시 같지는 않다고 보고한다. 사용자 다운로드 파일 정리 연구와 대상은 다르지만, ‘폴더를 예쁘게 만드는 것’과 ‘실제로 더 빨리 찾는 것’을 분리해 평가해야 한다는 시사점이 있다. [논문](https://arxiv.org/abs/2607.26637)

## 3. 무엇이 이미 있고 무엇을 더 검증해야 하나

| 기능·주장 | 이번 조사로 확인한 상황 | 우리의 다음 행동 |
|---|---|---|
| 확장자·날짜·텍스트로 분류 | 규칙 도구에서도 지원 | organize를 기준선에 포함 |
| LLM으로 본문을 읽고 폴더·이름 제안 | 여러 직접 구현 존재 | 신규 기능으로 주장하지 않기 |
| 새 파일을 감지해 자동 이동 | 직접 구현 존재 | 감지 안정화·오분류·원본 보존 비교 |
| 승인·미리보기·되돌리기 | 직접 구현 존재 | 필수 안전 기능으로 구현·검증 |
| 사용자 수정으로 개인화 | AI File Sorter가 문서에 명시 | ‘개인화 추가’만을 차별점으로 삼지 않기 |
| 프로젝트 파일 보호 | AI File Sorter가 문서에 명시 | 코드·가중치 파일의 경로 의존성 고려 |
| 사용 상태에 맞춘 보관·정리 | 비교 대상별 세부 구현·효과를 아직 평가하지 않음 | 선행 부재를 단정하지 않고 상태·정책·사용자 부담 효과 검증 |

근거: [organize](https://github.com/tfeldmann/organize), [Local File Organizer](https://github.com/QiuYannnn/Local-File-Organizer), [폴더 감시 예제](https://github.com/pneelamr/ai-file-organizer), [AI File Sorter](https://github.com/hyperfield/ai-file-sorter).

## 4. 우리 프로젝트의 구체화 제안 — 조사 결과에 따른 판단

기본 정의는 **‘다운로드 파일을 사용자의 프로젝트·보관 기준에 맞춰 정리하고, 불확실한 부분만 확인하는 에이전트’**로 유지하는 것이 자연스럽다.

첫 비교는 수동 정리 / organize 규칙 / Local File Organizer 또는 AI File Sorter / 현재 프로토타입으로 구성한다. 합성 6개 실패 사례를 고치는 것에서 나아가 서로 다른 프로젝트의 PDF·이미지·ZIP·CSV·노트·모델 파일이 섞인 고정 평가 폴더를 만들어야 한다. 기존 도구의 지원 형식 밖 사례는 공통 평가와 구분한다.

평가 지표는 분류 정확도만 두지 않는다. 사용자가 수정한 파일 수, 잘못 이동한 파일 수, 기존 프로젝트 경로를 깨뜨린 수, 실제 파일 찾는 시간, 확인 질문 수, undo 성공률, 토큰·시간 비용을 함께 기록한다. 유일한 폴더 트리를 정답으로 강제하기보다 사용자가 허용한 목적지와 보존 정책을 평가 전에 정의한다.

‘다운로드 → 사용 → 보관·정리’ 상태 관리가 단순 분류보다 사용자 부담을 줄이는지는 우리의 실험 가설이다. 같은 자료·같은 모델로 상태 관리가 있는 경우와 없는 경우를 비교해야 한다. 실제 파일을 언제 삭제해도 되는지 내용을 보고 완전히 알 수 있다고 가정하지 않는다.

연구 기획에서 먼저 읽을 세 가지는 **AI File Sorter**(제품 중복 확인), **organize**(규칙 기준선), **AIOS-LSFS 논문·코드**(연구·시스템 구조)다. 이는 확인한 기능 범위에 따른 제안이며 실제 성능 순위가 아니다.
