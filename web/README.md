# 모아 웹 · API

`dist/`는 [운영 사이트](https://moa.3-38-192-19.sslip.io/)의 정적 화면, `backend/`는 사용자별 데이터 API, `bridge/`는 Mac 에이전트와 Django API 사이의 HTTPS 중계 프로그램입니다. `deploy/ec2/`는 EC2 배포 절차입니다.

## 실제 연결 범위

- 사이트의 **에이전트 연결** 화면은 로그인한 사용자의 Mac 상태를 서버에서 읽고, 파일별 답변·승인·유지·되돌리기 명령을 대기열에 넣습니다.
- Mac 브리지는 로컬 에이전트의 `/api/state`를 읽어 요약 메타데이터를 HTTPS 서버에 보내고, 승인 명령을 로컬 API로 전달합니다. Mac 에이전트가 실제 파일 계획과 해시를 다시 검증합니다.
- **대시보드·모든 파일·폴더·분류 대기·삭제 관리**는 연결한 Mac의 에이전트 상태를 사용합니다. 실제 설정과 폴더 지침 수정은 Mac에서 진행합니다.
- Mac 에이전트와 브리지가 실행 중이지 않으면 실제 연결 화면은 연결 대기로 표시됩니다. 실행 방법은 [`bridge/README.md`](bridge/README.md)를 참고하세요.

## 로컬 확인

```sh
cd web/backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
MOA_DJANGO_SECRET_KEY=local-secret .venv/bin/python manage.py test library
MOA_DJANGO_SECRET_KEY=local-secret .venv/bin/python manage.py runserver
```

로컬에서 화면과 로그인·에이전트 연결을 함께 확인하려면 [`../LOCAL_SETUP.md`](../LOCAL_SETUP.md)를 따르세요. `MOA_DEBUG=1`일 때 Django가 `dist/`를 같은 주소에서 제공합니다. API 문서는 `/swagger/`, 헬스 체크는 `/api/v1/health/`입니다. [`INTEGRATION.md`](INTEGRATION.md)에 연결 경계와 남은 작업을 정리했습니다.


## 웹 실제 데이터 모드

웹은 연결한 Mac의 실제 데이터만 표시합니다. 연결 화면에서 로그인하면 대시보드·파일 검색·폴더·분류 대기·보관 대기·Mac 휴지통·명령 기록이 계정별 에이전트 상태를 사용합니다. 답변·이동 승인·유지·되돌리기·휴지통 복구는 기존 브리지 명령 API로 전달되며 5초마다 상태를 갱신합니다. 폴더 설명은 읽기 전용이고 지침·감시·모델·정책 변경은 Mac에서 진행합니다. 브리지 업데이트 후 다시 실행해야 파일별 프로젝트 정보가 전송됩니다.
