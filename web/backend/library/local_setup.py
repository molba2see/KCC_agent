"""First-run setup for the opt-in, loopback-only Mac installation."""
import json
import os
import secrets
from pathlib import Path

from django.contrib.auth import get_user_model, login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST


def enabled(request):
    return (bool(os.environ.get('MOA_LOCAL_KEY'))
            and request.META.get('REMOTE_ADDR') in {'127.0.0.1', '::1'}
            and request.get_host().split(':')[0] in {'localhost', '127.0.0.1'})


def storage():
    return Path(os.environ['MOA_LOCAL_DATA'])


def cloud_root():
    return Path.home() / 'Library/Mobile Documents/com~apple~CloudDocs'


@require_POST
@csrf_protect
def unlock(request):
    if not enabled(request):
        return JsonResponse({'detail': 'Local installation required'}, status=404)
    if not secrets.compare_digest(request.headers.get('X-Moa-Local-Key', ''), os.environ['MOA_LOCAL_KEY']):
        return JsonResponse({'detail': 'Invalid local key'}, status=403)
    user = get_user_model().objects.get(username='local-owner')
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return JsonResponse({'ok': True})


@require_http_methods(['GET', 'POST'])
@csrf_protect
def setup(request):
    if not enabled(request):
        return JsonResponse({'detail': 'Local installation required'}, status=404)
    if not request.user.is_authenticated or request.user.get_username() != 'local-owner':
        return JsonResponse({'detail': 'Open Moa from the installed Mac launcher'}, status=403)
    root = cloud_root()
    config_path = storage() / 'icloud.json'
    inbox = root / 'KCC-inbox'
    legacy_inbox = root / '모아' / '받은 파일'
    existing_inbox = None
    if config_path.exists():
        try:
            existing_inbox = json.loads(config_path.read_text(encoding='utf-8')).get('inbox')
        except (OSError, ValueError, AttributeError):
            return JsonResponse({'detail': '기존 iCloud 연결 설정을 읽을 수 없습니다.'}, status=409)
    if request.method == 'POST' and (not config_path.exists() or existing_inbox == str(legacy_inbox)):
        if not root.is_dir():
            return JsonResponse({'detail': '시스템 설정에서 iCloud Drive를 먼저 켜 주세요.'}, status=409)
        try:
            base = root / '모아'
            inbox.mkdir(parents=True, exist_ok=True)
            base.mkdir(parents=True, exist_ok=True)
            projects = {}
            for pid, name, desc, keywords in [
                ('documents', '문서', '보고서, 기획서와 일반 문서를 보관합니다.', ['보고서', '기획서', '문서']),
                ('receipts', '영수증', '결제 영수증과 구매 증빙을 보관합니다.', ['영수증', '결제', 'receipt']),
                ('meetings', '회의', '회의록과 회의 자료를 보관합니다.', ['회의록', '회의', 'meeting']),
            ]:
                folder = base / name
                folder.mkdir(exist_ok=True)
                guide = folder / '_project.md'
                if not guide.exists():
                    guide.write_text('# ' + name + '\n\n' + desc + '\n', encoding='utf-8')
                projects[pid] = {'name': name, 'folder': str(folder), 'desc': desc, 'keywords': keywords}
            projects_path = storage() / 'projects.json'
            if not projects_path.exists():
                projects_path.write_text(json.dumps(projects, ensure_ascii=False), encoding='utf-8')
            tmp = config_path.with_suffix('.tmp')
            tmp.write_text(json.dumps({'inbox': str(inbox)}, ensure_ascii=False), encoding='utf-8')
            tmp.replace(config_path)
            existing_inbox = str(inbox)
        except OSError:
            return JsonResponse({'detail': 'iCloud Drive 폴더에 접근할 수 없습니다. Mac의 파일 접근 권한을 확인해 주세요.'}, status=409)
    cloud_path = storage() / 'cloud.json'
    cloud_origin = json.loads(cloud_path.read_text()).get('origin') if cloud_path.exists() else None
    return JsonResponse({'available': root.is_dir(), 'configured': config_path.exists(),
                         'shortcut_ready': config_path.exists() and existing_inbox == str(inbox),
                         'cloud_origin': cloud_origin, 'folder': 'iCloud Drive / KCC-inbox'})


@require_POST
@csrf_protect
def connect_cloud(request):
    """Receive a ticket after an explicit same-origin confirmation on this Mac."""
    from django.conf import settings
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlsplit
    from urllib.request import Request, urlopen

    if not enabled(request):
        return JsonResponse({'detail': 'Local installation required'}, status=404)
    try:
        body = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'detail': '잘못된 연결 요청입니다.'}, status=400)
    if not isinstance(body, dict):
        return JsonResponse({'detail': '잘못된 연결 요청입니다.'}, status=400)
    origin, secret = body.get('origin'), body.get('pairing_secret')
    trusted = settings.MOA_CLOUD_ORIGIN
    parsed = urlsplit(trusted)
    if (origin != trusted or parsed.scheme != 'https' or not parsed.hostname
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment
            or parsed.username or parsed.password):
        return JsonResponse({'detail': '등록된 모아 AWS 주소만 연결할 수 있습니다.'}, status=400)
    if not isinstance(secret, str) or not 32 <= len(secret) <= 128:
        return JsonResponse({'detail': '잘못된 연결 코드입니다.'}, status=400)
    config = storage() / 'cloud.json'
    if config.exists():
        return JsonResponse({'detail': '이 Mac은 이미 AWS에 연결되어 있습니다. 기존 연결을 해제한 뒤 다시 연결하세요.'}, status=409)
    try:
        payload = json.dumps({'pairing_secret': secret}).encode()
        with urlopen(Request(trusted + '/api/v1/agent/pairing/consume/', data=payload,
                             headers={'Content-Type': 'application/json'}), timeout=15) as response:
            token = json.load(response)['bridge_token']
        if not isinstance(token, str) or not 32 <= len(token) <= 128:
            raise ValueError('Invalid token')
        # Exclusive create prevents a competing connection from overwriting a token.
        fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as output:
            json.dump({'origin': trusted, 'bridge_token': token}, output)
    except FileExistsError:
        return JsonResponse({'detail': '이미 연결되었습니다.'}, status=409)
    except HTTPError:
        return JsonResponse({'detail': '연결 코드가 만료되었거나 거절되었습니다. AWS에서 다시 연결하세요.'}, status=400)
    except (URLError, OSError, ValueError, KeyError):
        return JsonResponse({'detail': 'AWS 연결에 실패했습니다. 네트워크와 HTTPS 인증서를 확인하세요.'}, status=502)
    user = get_user_model().objects.get(username='local-owner')
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return JsonResponse({'connected': True, 'origin': trusted})


@require_POST
@csrf_protect
def disconnect_cloud(request):
    from django.conf import settings
    from urllib.request import Request, urlopen
    if not enabled(request):
        return JsonResponse({'detail': 'Local installation required'}, status=404)
    if not request.user.is_authenticated or request.user.get_username() != 'local-owner':
        return JsonResponse({'detail': '로컬 모아에서 연결을 해제하세요.'}, status=403)
    config = storage() / 'cloud.json'
    if config.exists():
        saved = json.loads(config.read_text())
        if saved['origin'] != settings.MOA_CLOUD_ORIGIN:
            return JsonResponse({'detail': '운영 주소 설정을 확인하세요.'}, status=409)
        try:
            with urlopen(Request(saved['origin'] + '/api/v1/agent/pairing/disconnect/', data=b'{}',
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + saved['bridge_token']}), timeout=15):
                pass
        except OSError:
            return JsonResponse({'detail': 'AWS 연결을 해제하지 못했습니다. 네트워크 확인 후 다시 시도하세요.'}, status=502)
        config.unlink()
    return JsonResponse({'disconnected': True})
