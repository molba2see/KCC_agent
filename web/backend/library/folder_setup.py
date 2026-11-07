"""Authenticated loopback-only access to the Mac folder onboarding worker."""
import fcntl
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import uuid

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .local_setup import enabled, storage

WORKER = Path(__file__).resolve().parents[2] / 'local/folder_guides.py'


@require_http_methods(['GET', 'POST'])
@csrf_protect
def folders(request):
    if not enabled(request):
        return JsonResponse({'detail': 'Local installation required'}, status=404)
    if not request.user.is_authenticated or request.user.get_username() != 'local-owner':
        return JsonResponse({'detail': 'Mac 연결 앱에서 폴더를 선택해 주세요.'}, status=403)
    data = storage()
    status_file = data / 'folder-setup.json'
    with (data / 'folder-setup.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if request.method == 'POST':
                return JsonResponse({'detail': '이미 폴더 지침을 작성하고 있어요.'}, status=409)
            return JsonResponse(json.loads(status_file.read_text()))
        if request.method == 'GET':
            status = json.loads(status_file.read_text()) if status_file.exists() else {'status': 'not_started'}
            if status['status'] not in {'completed', 'failed', 'not_started'}:
                status = {'status': 'failed', 'detail': '폴더 지침 작성이 중단됐어요. 연결 앱에서 다시 시작해 주세요.'}
            return JsonResponse(status)
        spec = importlib.util.spec_from_file_location('moa_folder_guides', WORKER)
        guides = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guides)
        try:
            body = json.loads(request.body)
            selected = guides.validate_folders(body.get('folders') if isinstance(body, dict) else None)
            mode = body.get('mode', 'replace')
            if 'initial_cleanup' in body and not isinstance(body['initial_cleanup'], bool): raise ValueError('Invalid cleanup option')
            if mode not in {'replace', 'add'}:
                raise ValueError('Invalid mode')
            if mode == 'add':
                guides.validate_additions(selected, data)
        except (ValueError, OSError, TypeError):
            return JsonResponse({'detail': '접근 가능한 폴더를 1~20개 선택하세요. 상위·하위 폴더는 중복 선택할 수 없습니다.'}, status=400)
        if mode == 'replace':
            guides.atomic_json(data / 'initial-cleanup-settings.json', {'enabled': body.get('initial_cleanup', True), 'request_id': uuid.uuid4().hex})
        guides.atomic_json(data / 'selected-folders.json', [str(folder) for folder in selected])
        status = {'status': 'preparing', 'completed': 0, 'total': len(selected), 'mode': mode}
        guides.atomic_json(status_file, status)
        try:
            with (data / 'folder-setup.log').open('a') as log:
                # The child retains the lock for its entire lifetime, including model setup.
                subprocess.Popen([sys.executable, str(WORKER), '--data', str(data), *(['--append'] if mode == 'add' else [])],
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                 pass_fds=(lock.fileno(),), start_new_session=True)
        except OSError:
            guides.atomic_json(status_file, {'status': 'failed', 'mode': mode})
            return JsonResponse({'detail': 'QWEN 실행 프로그램을 시작하지 못했어요.'}, status=503)
    return JsonResponse(status, status=202)
