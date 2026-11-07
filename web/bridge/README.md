# Mac 에이전트 연결

Mac에서 로컬 에이전트와 이 브리지를 각각 실행합니다. 브리지는 운영 사이트에 HTTPS로 접속하며, 에이전트의 로컬 API는 `127.0.0.1` 밖에 열지 않습니다. 브라우저에서 계정 로그인 후 상태와 승인 요청을 볼 수 있습니다.

GitHub 클론부터 로컬 웹·API까지 실행하는 절차는 [`../../LOCAL_SETUP.md`](../../LOCAL_SETUP.md)를 참고하세요. 로컬 개발에서만 `--allow-insecure-localhost`로 `http://127.0.0.1` 연결을 허용할 수 있습니다.

1. 서버에서 처음 연결하는 경우 `python backend/manage.py bootstrap_agent_owner <username>`으로 로그인 계정과 브리지 토큰을 함께 만듭니다. 기존 계정의 토큰을 교체하려면 `python backend/manage.py issue_agent_token <username>`을 사용합니다. 토큰 원문은 다시 조회할 수 없고, 재발급하면 이전 토큰은 무효가 됩니다.
2. Mac에서 `python file-lifecycle-agent/prototype/demo_v5.py --root <작업폴더> --projects <projects.json> --watch --port 8791`을 실행합니다. 실제 감시 경로·모델·프로필 설정은 `file-lifecycle-agent/docs/local_api.md`를 따릅니다.
3. Mac의 별도 터미널에서 `MOA_AGENT_TOKEN=<발급받은 토큰> python web/bridge/mac_bridge.py --server https://3.38.192.19 --local http://127.0.0.1:8791`을 실행합니다. 셸 기록에 토큰을 남기지 않으려면 `read -rs MOA_AGENT_TOKEN; export MOA_AGENT_TOKEN`으로 입력하세요.

브리지는 5초마다 상태를 보내고, 웹에서 승인된 명령이 있으면 로컬 에이전트에 전달합니다. 명령 결과는 `~/.moa/bridge-result.json`에 먼저 기록해 전송 실패 후 재시작 시 다시 보고합니다. Mac이 꺼져 있으면 명령은 서버에 대기합니다. 실행 중 Mac이 갑자기 종료되어 명령이 `running`에 남으면 자동 재실행하지 않습니다. 파일 이동의 중복 위험을 피하기 위해 실행기 저널을 확인한 뒤 복구해야 합니다.

현재 연결은 한 Django 계정과 하나 이상의 Mac 브리지를 지원하지만, Mac 로그인·기기별 파일 권한은 브리지 실행 사용자의 OS 권한을 따릅니다. 사이트의 기존 시연 화면과 실제 에이전트 화면은 분리되어 있습니다.

브리지는 원본 파일 내용, 에이전트 추론 trace, 작업 폴더의 루트 경로를 서버에 보내지 않습니다. 파일명, 분류 이유 일부, 프로젝트 목록, 승인에 필요한 계획 대상 경로는 로그인 계정의 서버 데이터로 전송됩니다.


## 웹 실제 데이터 모드

웹은 연결한 Mac의 실제 데이터만 표시합니다. 연결 화면에서 로그인하면 대시보드·파일 검색·폴더·분류 대기·보관 대기·Mac 휴지통·명령 기록이 계정별 에이전트 상태를 사용합니다. 답변·이동 승인·유지·되돌리기·휴지통 복구는 기존 브리지 명령 API로 전달되며 5초마다 상태를 갱신합니다. 폴더 지침·감시 범위·모델 변경은 Mac에서 진행하고, 신규 파일 처리 방식과 보관 기한은 웹 설정에서 Mac별로 변경합니다. 브리지 업데이트 후 다시 실행해야 파일별 프로젝트 정보가 전송됩니다.
