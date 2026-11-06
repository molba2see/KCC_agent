"""OpenAPI descriptions for Django views and shared agent endpoints.

Schema-only metadata keeps the existing Django authentication/CSRF behavior intact.
"""


def obj(properties=None, required=()):
    return {"type": "object", "properties": properties or {}, **({"required": list(required)} if required else {})}


STRING = {"type": "string"}
BOOL = {"type": "boolean"}
JSON = {"type": "object", "additionalProperties": True}
COMMAND = obj({"id": {"type": "string", "format": "uuid"}, "action": STRING,
               "payload": JSON, "status": {"type": "string", "enum": ["pending", "running", "done", "failed"]},
               "result": JSON, "created_at": {"type": "string", "format": "date-time"}})


def complete_schema(result, generator, request, public):
    """Add views that the DRF schema generator cannot discover automatically."""
    def add(path, method, tag, summary, description, response, body=None, errors=(), secured=True, parameters=()):
        operation = {
            "operationId": path.strip('/').replace('/', '_') + '_' + method,
            "tags": [tag], "summary": summary, "description": description,
            "security": [{"cookieAuth": []}] if secured else [],
            "responses": {"201" if path.endswith('/commands/') else "200": {
                "description": "처리 성공", "content": {"application/json": {"schema": response}}}},
        }
        for code, detail in errors:
            operation['responses'][str(code)] = {"description": detail, "content": {"application/json": {
                "schema": obj({"detail": STRING})}}}
        if body is not None:
            operation['requestBody'] = {"required": True, "content": {"application/json": {"schema": body}}}
        if parameters:
            operation['parameters'] = list(parameters)
        if secured and method == 'post':
            operation.setdefault('parameters', []).append({"in": "header", "name": "X-CSRFToken", "required": True,
                                                          "schema": STRING, "description": "세션 조회에서 받은 csrf 값"})
        result['paths'].setdefault(path, {})[method] = operation

    add('/api/v1/health/', 'get', '시스템', '서버 상태 확인', '인증 없이 API 서비스의 상태와 버전을 확인합니다.',
        obj({"status": STRING, "service": STRING, "version": STRING}), secured=False)
    add('/api/v1/auth/session/', 'get', '기기 연결', '로그인 상태와 CSRF 토큰 조회',
        '로그인 화면에서 먼저 호출합니다. 세션 인증 여부, 사용자 이름, 변경 요청의 X-CSRFToken에 사용할 csrf 값을 반환하고 CSRF 쿠키를 설정합니다.',
        obj({"authenticated": BOOL, "username": {"type": "string", "nullable": True}, "csrf": STRING, "display_name": STRING, "onboarding_completed": BOOL}), secured=False)
    csrf = ({"in": "header", "name": "X-CSRFToken", "required": True, "schema": STRING,
             "description": "세션 조회에서 받은 csrf 값. CSRF 쿠키도 함께 전송합니다."},)
    add('/api/v1/auth/login/', 'post', '기기 연결', '아이디와 비밀번호로 로그인',
        '세션 조회 후 호출합니다. 성공하면 세션 쿠키가 발급됩니다. 로그인으로 CSRF 토큰이 바뀌므로 세션을 다시 조회합니다.',
        obj({"authenticated": BOOL, "username": STRING}), obj({"username": STRING, "password": {"type": "string", "format": "password"}}, ('username', 'password')),
        ((400, 'JSON 형식 오류'), (401, '로그인 정보 불일치'), (403, 'CSRF 검증 실패')), False, csrf)
    add('/api/v1/auth/logout/', 'post', '기기 연결', '로그아웃', '현재 브라우저의 로그인 세션을 종료합니다.',
        obj({"authenticated": BOOL}), errors=((403, 'CSRF 검증 실패'),), secured=False, parameters=csrf)
    add('/api/v1/agent/status/', 'get', '대시보드 · 에이전트 상태', 'Mac 연결 상태·파일·명령 기록 조회',
        '대시보드, 모든 파일, 폴더, 분류 대기, 보관 대기, Mac 휴지통, 명령 기록에서 함께 사용합니다. '
        'links[].snapshot의 assets, catalog, trashed를 화면에 사용합니다. 마지막 수신 후 30초 미만이면 connected=true입니다. '
        'commands는 기기별 최근 12개입니다. 연결된 기기가 없으면 links는 빈 배열입니다.',
        obj({"links": {"type": "array", "items": obj({"id": STRING, "label": STRING, "connected": BOOL,
            "last_seen_at": {"type": "string", "format": "date-time", "nullable": True}, "snapshot": JSON,
            "commands": {"type": "array", "items": COMMAND}})}}), errors=((403, '로그인 필요'),))
    add('/api/v1/agent/commands/', 'post', '파일 처리 · 보관 · 휴지통', '분류 답변·이동 승인·유지·되돌리기·휴지통 복구 요청',
        'Mac 브리지가 실행할 명령을 대기열에 저장합니다. 응답 201은 실행 완료가 아닌 접수입니다. '
        '분류 대기: answer는 asset_id와 project_id로 분류 위치를 선택합니다. '
        '분류/보관 대기: approve는 asset_id의 기존 file/archive 계획을 승인하고 keep은 현재 파일을 유지합니다. '
        '이동한 파일: undo는 asset_id의 이동을 되돌립니다. Mac 휴지통: restore_trashed는 trash_index 항목을 복구합니다. '
        'link_id는 상태 조회의 links[].id입니다. 실행 결과는 상태 조회의 commands에서 확인합니다. 기기별 대기/실행 중 명령은 하나만 허용합니다.',
        COMMAND, obj({"link_id": {"type": "string", "format": "uuid"}, "action": {"type": "string", "enum": ['answer', 'approve', 'keep', 'undo', 'restore_trashed']},
            "asset_id": {**STRING, "description": "answer/approve/keep/undo 필수. snapshot.assets의 id"},
            "project_id": {**STRING, "description": "answer 필수. snapshot.catalog의 id"},
            "trash_index": {"type": "integer", "description": "restore_trashed 필수. snapshot.trashed의 i"}}, ('link_id', 'action')),
        ((400, '잘못된 명령·파일·프로젝트·실행 계획'), (403, '로그인 또는 CSRF 검증 필요'), (404, '내 기기를 찾을 수 없음'), (409, '이미 진행 중인 명령이 있음')))
    bearer = ({"in": "header", "name": "Authorization", "required": True, "schema": STRING,
               "description": "Bearer <Mac 브리지 토큰>"},)
    add('/api/v1/agent/bridge/poll/', 'post', 'Mac 브리지', 'Mac 상태 전송과 대기 명령 수신',
        'Mac 브리지가 주기적으로 snapshot을 전송합니다. assets와 catalog 배열이 필수이며 상태는 최대 2,000,000자입니다. '
        '가장 오래된 pending 명령 하나를 running으로 바꾸어 반환합니다. 대기 명령이 없으면 command=null입니다.',
        obj({"command": {**COMMAND, "nullable": True}}), obj({"snapshot": obj({"assets": {"type": "array", "items": JSON}, "catalog": {"type": "array", "items": JSON}}, ('assets', 'catalog'))}, ('snapshot',)),
        ((400, '잘못된 snapshot'), (403, '브리지 토큰 오류'), (413, '상태 크기 초과')), False, bearer)
    add('/api/v1/agent/bridge/result/', 'post', 'Mac 브리지', 'Mac 명령 실행 결과 저장',
        '현재 running인 명령의 결과를 보고합니다. ok=true일 때 done, 그 외에는 failed로 저장합니다. result는 최대 50,000자입니다.',
        COMMAND, obj({"id": {"type": "string", "format": "uuid"}, "ok": BOOL, "result": {}}, ('id', 'ok')),
        ((400, '명령 ID 오류'), (403, '브리지 토큰 오류'), (409, '실행 중인 명령이 아님'), (413, '결과 크기 초과')), False, bearer)
    local_response = obj({"available": BOOL, "configured": BOOL, "folder": STRING})
    local_desc = 'Mac 로컬 설치 전용입니다. 로컬 키 설정 및 localhost 접속이 필요하며 AWS 운영 서버에서는 404를 반환합니다. '
    add('/api/v1/local/unlock/', 'post', '로컬 설정', 'Mac 실행기에서 로컬 세션 열기', local_desc + '실행기가 로컬 키로 local-owner 세션을 시작합니다.',
        obj({"ok": BOOL}), errors=((403, '로컬 키 또는 CSRF 오류'), (404, '로컬 설치 아님')), secured=False,
        parameters=csrf + ({"in": "header", "name": "X-Moa-Local-Key", "required": True, "schema": STRING},))
    for method, summary, description in [('get', 'iCloud Drive 연결 상태 조회', 'iCloud Drive 사용 가능 여부와 초기 설정 상태를 조회합니다.'),
                                         ('post', 'iCloud Drive 초기 폴더 설정', 'KCC-inbox와 모아/문서·영수증·회의 폴더를 만들고 기존 받은 파일 설정은 KCC-inbox로 전환합니다.')]:
        add('/api/v1/local/setup/', method, '로컬 설정', summary, local_desc + description + ' local-owner 로그인이 필요합니다.',
            local_response, errors=((403, '로컬 실행기 로그인 또는 CSRF 필요'), (404, '로컬 설치 아님'), (409, 'iCloud Drive 또는 파일 접근 오류')))
    add('/api/v1/auth/config/', 'get', '기기 연결', 'Apple 로그인 사용 가능 여부 조회',
        'Apple 로그인과 운영 주소 설정을 조회합니다. 설정이 완료되지 않으면 apple_enabled=false이며 로그인 버튼을 활성화하지 않습니다.',
        obj({'apple_enabled': BOOL, 'cloud_origin': STRING, 'local_helper_url': STRING, 'setup_required': STRING}), secured=False)
    add('/api/v1/auth/apple/start/', 'get', '기기 연결', 'Apple 로그인 시작',
        'Apple 인증 페이지로 이동합니다. 10분간 유효한 일회용 state와 브라우저 확인 쿠키를 발급합니다. Apple Developer 설정과 HTTPS 도메인이 필요합니다.',
        obj(), errors=((503, 'Apple 설정 미완료'),), secured=False)
    result['paths']['/api/v1/auth/apple/start/']['get']['responses']['302'] = {'description': 'Apple 인증 페이지로 이동'}
    del result['paths']['/api/v1/auth/apple/start/']['get']['responses']['200']
    add('/api/v1/auth/apple/callback/', 'post', '기기 연결', 'Apple 인증 결과 확인 및 모아 로그인',
        'Apple이 호출하는 반환 주소입니다. state·브라우저 쿠키·nonce와 Apple 토큰 서명·발급자·대상·만료를 검증합니다. Apple subject로 계정을 구분하며 이메일로 기존 계정을 자동 연결하지 않습니다. 성공하면 모아 세션을 발급합니다. iCloud 파일 접근 권한을 부여하는 API는 아닙니다.',
        obj(), secured=False)
    callback = result['paths']['/api/v1/auth/apple/callback/']['post']
    callback['requestBody'] = {'content': {'application/x-www-form-urlencoded': {'schema': obj({'state': STRING, 'code': STRING, 'error': STRING}, ('state',))}}}
    callback['responses'] = {'302': {'description': '연결 화면으로 이동. 실패 시 apple_error 표시'}}
    add('/api/v1/agent/pairing/', 'post', '기기 연결', '이 Mac 연결 링크 발급',
        '로그인한 계정에 연결할 5분짜리 일회용 비밀 코드를 발급합니다. 앞서 발급한 미사용 링크는 무효화합니다. 코드는 localhost 연결 화면의 URL fragment로만 전달합니다.',
        obj({'pairing_secret': STRING, 'expires_in': {'type': 'integer'}}), errors=((403, '로그인 또는 CSRF 검증 필요'),))
    pairing = result['paths']['/api/v1/agent/pairing/']['post']['responses']
    pairing['201'] = pairing.pop('200')
    add('/api/v1/agent/pairing/consume/', 'post', 'Mac 브리지', '일회용 연결 코드 교환',
        'Mac 연결 도우미 전용입니다. 유효한 코드를 한 번만 소비하고 해당 계정의 새 Mac 연결과 브리지 토큰을 생성합니다. 토큰은 Mac 전용 저장소에 보관하며 브라우저에 반환하지 않습니다.',
        obj({'bridge_token': STRING}), obj({'pairing_secret': STRING}, ('pairing_secret',)),
        ((400, '잘못된 코드 형식'), (403, '만료 또는 사용된 코드')), False)
    add('/api/v1/local/cloud/connect/', 'post', '로컬 설정', '이 Mac에서 AWS 연결 승인',
        'Mac 도우미의 연결 승인 버튼이 호출합니다. 로컬 설치·localhost·CSRF 검증 후 등록된 HTTPS 운영 주소에만 코드를 전송합니다. 브리지 토큰을 권한 0600 파일에 저장하고 로컬 세션을 시작합니다. iCloud 설정 후 도우미가 AWS 브리지를 실행합니다.',
        obj({'connected': BOOL, 'origin': STRING}), obj({'origin': STRING, 'pairing_secret': STRING}, ('origin', 'pairing_secret')),
        ((400, '허용되지 않은 운영 주소 또는 코드'), (403, 'CSRF 검증 필요'), (404, '로컬 설치 아님'), (409, '이미 연결됨'), (502, 'AWS 네트워크 또는 인증서 오류')), False, csrf)
    add('/api/v1/agent/pairing/disconnect/', 'post', 'Mac 브리지', '현재 Mac 연결과 서버 상태 삭제',
        'Mac 도우미 전용입니다. Bearer 토큰에 해당하는 Mac 연결과 저장된 상태·명령 기록을 삭제하고 토큰을 무효화합니다. Mac과 iCloud 파일은 삭제하지 않습니다.',
        obj({'disconnected': BOOL}), errors=((403, '브리지 토큰 오류'),), secured=False, parameters=bearer)
    add('/api/v1/local/cloud/disconnect/', 'post', '로컬 설정', '이 Mac의 AWS 연결 해제',
        '로컬 소유자 세션과 CSRF가 필요합니다. AWS 연결을 삭제한 후 Mac의 저장된 브리지 토큰을 지우고 AWS 동기화를 중지합니다. 로컬 파일 감시는 계속됩니다.',
        obj({'disconnected': BOOL}), errors=((403, '로컬 로그인 또는 CSRF 필요'), (404, '로컬 설치 아님'), (409, '운영 주소 불일치'), (502, 'AWS 연결 해제 실패')))
    add('/api/v1/auth/signup/', 'post', '기기 연결', '회원가입 후 자동 로그인',
        '아이디·닉네임·비밀번호로 일반 사용자 계정을 생성합니다. 아이디는 4~30자의 영문·숫자·밑줄·점·하이픈이며 소문자로 저장합니다. 닉네임은 선택 사항이며 최대 30자입니다. 비밀번호는 10~128자로 흔한 값·숫자만 사용한 값·사용자 정보와 비슷한 값은 거절합니다. Django 사용자 DB에 비밀번호 해시를 저장하고 가입 즉시 세션을 발급합니다. 세션 조회의 csrf를 X-CSRFToken으로 보내며, 가입 후 CSRF 토큰을 다시 조회합니다. Mac 연결과 파일 수집은 별도로 승인합니다.',
        obj({'authenticated': BOOL, 'username': STRING, 'display_name': STRING}),
        obj({'username': {**STRING, 'minLength': 4, 'maxLength': 30},
             'nickname': {**STRING, 'maxLength': 30, 'description': '선택 입력'},
             'password': {'type': 'string', 'format': 'password', 'writeOnly': True, 'minLength': 10, 'maxLength': 128},
             'password_confirm': {'type': 'string', 'format': 'password', 'writeOnly': True}}, ('username', 'password', 'password_confirm')),
        ((400, '입력 오류. errors 객체에 필드별 오류 메시지 배열 반환'), (403, 'CSRF 검증 필요'), (409, '이미 로그인되어 있거나 아이디 중복')), False, csrf)
    registration = result['paths']['/api/v1/auth/signup/']['post']['responses']
    registration['201'] = registration.pop('200')
    for code in ('400', '409'):
        registration[code]['content']['application/json']['schema'] = obj({'detail': STRING, 'errors': {
            'type': 'object', 'additionalProperties': {'type': 'array', 'items': STRING}}})
    onboarding_state = obj({'mac_connected': BOOL, 'iphone_icloud_confirmed': BOOL,
        'test_started': BOOL, 'file_received': BOOL, 'received_filename': {'type': 'string', 'nullable': True},
        'completed': BOOL, 'completed_at': {'type': 'string', 'format': 'date-time', 'nullable': True}})
    add('/api/v1/onboarding/', 'get', '시작하기', 'Mac·iPhone 온보딩 진행 상황 조회',
        '계정에 저장된 iPhone 설정 확인·테스트 진행·완료 상태와 현재 Mac 연결·새 파일 수신 상태를 반환합니다. Mac은 최근 30초 이내에 상태를 전송해야 연결됨으로 표시합니다. iPhone 설정 확인은 사용자의 자기 확인이며 웹에서 Apple 계정이나 발신 기기를 조회하지 않습니다.',
        onboarding_state, errors=((403, '로그인 필요'),))
    add('/api/v1/onboarding/', 'post', '시작하기', 'iPhone 설정 확인·파일 수신 테스트·온보딩 완료',
        'confirm_iphone은 같은 Apple 계정과 받은 파일 폴더를 사용자가 확인했음을 저장합니다. start_test는 연결된 Mac과 iPhone 확인이 필요하며 기존 파일 목록을 기준으로 새 파일 수신을 기다립니다. complete는 테스트 시작 후 연결된 Mac에서 새 파일을 수신한 경우에만 완료를 저장합니다. 진행 상황은 같은 모아 계정의 기기에서 이어볼 수 있습니다.',
        onboarding_state, obj({'action': {'type': 'string', 'enum': ['confirm_iphone', 'start_test', 'complete']}}, ('action',)),
        ((400, '지원하지 않는 action'), (403, '로그인 또는 CSRF 필요'), (409, '선행 단계 또는 새 파일 수신 미완료')))
    return result
