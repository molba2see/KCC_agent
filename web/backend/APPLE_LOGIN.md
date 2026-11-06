# AWS 웹앱 · Apple 로그인 · Mac 연결

## 사용자 흐름

1. Safari에서 운영 사이트의 **에이전트 연결**을 엽니다.
2. **무료 회원가입**으로 모아 계정을 만들거나 기존 아이디·비밀번호로 로그인합니다. Apple 설정이 완료된 환경에서는 **Apple로 계속하기**도 사용할 수 있습니다.
3. **이 Mac 연결 → Mac 연결 화면 열기**를 누릅니다.
4. localhost 도우미에서 연결할 AWS 주소를 확인하고 **이 Mac 연결 승인**을 누릅니다.
5. **iCloud Drive 연결**을 누르고 **AWS 모아로 돌아가기**로 돌아갑니다.
6. Safari **파일 → Dock에 추가**에서 `모아 AWS`로 저장합니다.

이 Mac에 처음 설치할 때는 저장소의 `모아 시작.command`를 한 번 실행합니다. Mac 도우미는 로그인 시 자동 실행되고, AWS 웹앱이 닫혀 있어도 Mac이 켜져 있으면 상태를 전송합니다. Mac이 잠들거나 꺼져 있으면 처리가 멈춥니다.

Apple 로그인은 모아 사용자를 식별합니다. iCloud Drive API 권한이나 전체 파일 접근을 부여하지 않습니다. 파일은 macOS에서 이미 로그인한 Apple 계정의 `iCloud Drive/KCC-inbox`에서 읽으며 파일명·분류 상태 등을 AWS에 전달합니다. 확실한 분류 계획은 작업 사본을 자동 이동하고, 애매한 파일은 사용자 결정을 기다립니다. 원본은 유지합니다.

## Apple 로그인 활성화에 필요한 운영 설정

Apple은 반환 주소에 HTTPS 도메인을 요구하며 IP나 localhost를 허용하지 않습니다. 현재 IP 주소만으로는 Apple 로그인을 활성화할 수 없습니다.

1. 운영 도메인을 EC2에 연결하고 정상 HTTPS 인증서를 설정합니다.
2. Apple Developer의 Sign in with Apple이 활성화된 기본 App ID와 웹용 Services ID를 준비합니다.
3. Services ID에 운영 도메인과 반환 URL `https://<운영도메인>/api/v1/auth/apple/callback/`을 등록합니다.
4. Apple 로그인용 개인 키(.p8)를 발급하고 Team ID, Key ID를 확인합니다.
5. 서버 `/etc/moa.env`에 아래 환경 변수를 설정합니다. 비밀 키 파일은 릴리스·Git 저장소 밖에 두고 `moa` 서비스 사용자만 읽도록 합니다.

```ini
MOA_PUBLIC_ORIGIN=https://<운영도메인>
MOA_APPLE_CLIENT_ID=<Services ID>
MOA_APPLE_TEAM_ID=<Team ID>
MOA_APPLE_KEY_ID=<Key ID>
MOA_APPLE_PRIVATE_KEY_PATH=/etc/moa/apple-signin.p8
MOA_ALLOWED_HOSTS=<운영도메인>,127.0.0.1,localhost
MOA_CSRF_TRUSTED_ORIGINS=https://<운영도메인>
```

`systemctl restart moa-api` 후 `/api/v1/auth/config/`의 `apple_enabled=true`를 확인합니다. 미설정 상태에서는 준비 중 문구와 기존 계정 로그인만 표시하며, 임시 Apple 로그인이나 성공 화면을 제공하지 않습니다.

Mac 도우미에도 동일 운영 주소를 `MOA_CLOUD_ORIGIN`으로 등록해야 합니다. 설치기는 `MOA_CLOUD_ORIGIN=https://<운영도메인> .venv-moa/bin/python web/local/install.py`로 실행합니다. 도메인 변경 후 배포 시 `MOA_PUBLIC_HOST=<운영도메인>`으로 실행하여 허용 호스트 설정을 유지합니다.

## 연결 및 계정 보호

- Apple 서명, 발급자, 대상 Services ID, 만료, nonce를 검증합니다.
- 10분짜리 일회용 state와 브라우저별 HttpOnly/Secure 쿠키로 로그인 요청을 묶습니다. Apple의 교차 사이트 POST 반환만 CSRF 예외이며 일반 세션 쿠키는 Lax를 유지합니다.
- Apple subject로 사용자를 구분하고 이메일 주소만으로 기존 계정에 연결하지 않습니다. 기존 모아 계정의 기록은 Apple 계정으로 자동 이전되지 않습니다.
- Mac 연결 코드는 로그인·CSRF 검증 후 발급하고 5분간 한 번만 사용할 수 있습니다. 새 링크를 발급하면 이전 미사용 링크가 무효화됩니다.
- 코드는 localhost URL fragment로 전달해 HTTP 접근 로그에 남기지 않으며, 로컬 확인 화면에서 즉시 URL에서 제거합니다.
- Mac은 등록된 운영 HTTPS 주소에만 연결 코드를 전송합니다. 브리지 토큰은 브라우저나 AWS 화면에 표시하지 않고 Mac의 `~/Library/Application Support/Moa/cloud.json`에 권한 0600으로 저장합니다.
- 로컬 도우미의 **AWS 연결 해제**는 서버 연결·상태·명령 기록을 삭제하고 토큰을 무효화한 뒤 Mac의 토큰 파일을 제거합니다. iCloud 파일은 유지합니다.

관련 코드: `library/apple_auth.py`, `library/pairing.py`, `library/local_setup.py`, `web/local/run.py`, `web/dist/cloud.js`, `web/dist/setup.js`.

공식 설정 문서: https://developer.apple.com/documentation/signinwithapple/configuring-your-webpage-for-sign-in-with-apple
