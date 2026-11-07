# 간편 시작: Mac 웹앱 + iCloud Drive

최상위 **모아 시작.command**를 더블클릭 → 모아에서 **iCloud Drive 연결** → 이후 **Dock의 모아**로 실행. Python과 실행기 설정은 자동으로 진행합니다. [설치와 동작 범위](web/local/README.md)를 참고하세요.

# Mac에서 로컬로 실행하기

이 문서는 GitHub 저장소를 새로 클론한 Mac에서 웹·API·파일 에이전트·브리지를 함께 실행하는 절차입니다. Python 3.11 이상과 Git이 필요합니다. 처음에는 에이전트의 데모 작업 공간을 사용합니다.

## 1. 저장소와 Python 준비

```sh
git clone https://github.com/molba2see/KCC_agent.git
cd KCC_agent
python3 -m venv .venv
.venv/bin/python -m pip install -r web/backend/requirements.txt -r file-lifecycle-agent/requirements.txt
```

`python3 --version`이 3.11보다 낮다면 Python 3.11 이상을 설치한 뒤 가상 환경을 만드세요. 아래 명령은 모두 저장소 최상위 폴더에서 실행합니다.

## 2. 웹과 API 실행 (터미널 1)

```sh
export MOA_DEBUG=1
.venv/bin/python web/backend/manage.py migrate
umask 077
.venv/bin/python web/backend/manage.py bootstrap_agent_owner local-owner > web/local-credentials.json
.venv/bin/python web/backend/manage.py runserver 127.0.0.1:8000
```

브라우저에서 <http://127.0.0.1:8000/#connection>을 여세요. 웹 화면과 API가 같은 주소에서 제공됩니다. `web/local-credentials.json`의 사용자 이름과 비밀번호로 로그인합니다. 이 파일은 Git에서 제외되며 Mac에만 저장됩니다. 계정을 이미 만들었다면 `bootstrap_agent_owner`를 다시 실행하지 마세요. 토큰만 교체할 때는 `issue_agent_token local-owner`를 사용합니다.

## 3. 데모 에이전트 실행 (터미널 2)

```sh
cd KCC_agent
.venv/bin/python file-lifecycle-agent/prototype/demo_v5.py --port 8791
```

`http://127.0.0.1:8791/api/state`에서 로컬 에이전트 상태를 확인할 수 있습니다. `--projects`와 `--watch`를 지정하지 않았으므로 데모 작업 공간을 사용합니다.

## 4. 로컬 브리지 실행 (터미널 3)

```sh
cd KCC_agent
MOA_AGENT_TOKEN="$(.venv/bin/python -c 'import json; print(json.load(open("web/local-credentials.json"))["bridge_token"])')" \
  .venv/bin/python web/bridge/mac_bridge.py \
  --server http://127.0.0.1:8000 --allow-insecure-localhost
```

브리지가 5초마다 에이전트 상태를 API에 보냅니다. 웹의 **에이전트 연결** 화면에서 연결 상태와 데모 파일을 확인하세요. `--allow-insecure-localhost`는 로컬 개발 서버에만 HTTP를 허용하며, 운영 서버 연결은 HTTPS를 사용합니다.

## 운영 사이트와 연결할 때

로컬 웹 대신 운영 사이트 <https://3.38.192.19/#connection>을 쓰려면 터미널 1은 필요하지 않습니다. Mac에서 에이전트를 실행하고, 운영용 브리지 토큰을 환경 변수 `MOA_AGENT_TOKEN`에 넣어 다음 명령을 실행하세요.

```sh
.venv/bin/python web/bridge/mac_bridge.py --server https://3.38.192.19
```

운영 계정의 비밀번호와 토큰은 GitHub 저장소에 포함되지 않습니다. 실제 Mac 폴더를 감시하려면 [`file-lifecycle-agent/docs/local_api.md`](file-lifecycle-agent/docs/local_api.md)의 `--root`, `--projects`, `--watch` 설정을 적용하세요. 실제 데이터 모드에서는 주요 운영 화면이 에이전트 데이터를 사용합니다.


## 웹 실제 데이터 모드

웹은 연결한 Mac의 실제 데이터만 표시합니다. 연결 화면에서 로그인하면 대시보드·파일 검색·폴더·분류 대기·보관 대기·Mac 휴지통·명령 기록이 계정별 에이전트 상태를 사용합니다. 답변·이동 승인·유지·되돌리기·휴지통 복구는 기존 브리지 명령 API로 전달되며 5초마다 상태를 갱신합니다. 폴더 지침·감시 범위·모델 변경은 Mac에서 진행하고, 신규 파일 처리 방식과 보관 기한은 웹 설정에서 Mac별로 변경합니다. 브리지 업데이트 후 다시 실행해야 파일별 프로젝트 정보가 전송됩니다.
