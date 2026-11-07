"""Authenticated browser API and token-authenticated Mac relay."""
import hashlib
import json
import uuid

from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AgentCommand, AgentLink


@ensure_csrf_cookie
def session(request):
    authenticated = request.user.is_authenticated
    display_name = ''
    if authenticated:
        display_name = 'Apple 계정' if hasattr(request.user, 'appleidentity') else request.user.first_name or request.user.get_username()
    completed = bool(authenticated and hasattr(request.user, 'onboardingprogress') and request.user.onboardingprogress.completed_at)
    response = JsonResponse({"authenticated": authenticated,
                             "username": request.user.get_username() if authenticated else None,
                             "display_name": display_name, "onboarding_completed": completed,
                             "csrf": get_token(request)})
    response['Cache-Control'] = 'no-store'
    return response


@csrf_protect
def sign_in(request):
    if request.method != "POST":
        return JsonResponse({"detail": "POST required"}, status=405)
    try:
        body = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid JSON"}, status=400)
    if not isinstance(body, dict) or not isinstance(body.get("username"), str) or not isinstance(body.get("password"), str):
        return JsonResponse({"detail": "아이디와 비밀번호를 입력하세요."}, status=400)
    username = body["username"].strip()
    password = body["password"]
    if len(username) > 150 or len(password) > 1024:
        return JsonResponse({"detail": "로그인 정보가 올바르지 않습니다."}, status=400)
    user = authenticate(request, username=username, password=password)
    if user is None and username != username.lower():
        user = authenticate(request, username=username.lower(), password=password)
    if user is None or not user.is_active:
        return JsonResponse({"detail": "아이디 또는 비밀번호가 올바르지 않습니다."}, status=401)
    login(request, user)
    return JsonResponse({"authenticated": True, "username": user.get_username()})


@csrf_protect
def sign_out(request):
    if request.method != "POST":
        return JsonResponse({"detail": "POST required"}, status=405)
    logout(request)
    return JsonResponse({"authenticated": False})


def _bridge_link(request):
    value = request.headers.get("Authorization", "")
    if not value.startswith("Bearer ") or len(value) > 180:
        return None
    digest = hashlib.sha256(value[7:].encode()).hexdigest()
    # A hash lookup avoids storing the raw token in the database.
    return AgentLink.objects.filter(token_hash=digest).first()


def _command_dict(command):
    return {"id": str(command.id), "action": command.action, "payload": command.payload,
            "status": command.status, "result": command.result, "created_at": command.created_at.isoformat()}


@extend_schema(exclude=True)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def agent_status(request):
    links = AgentLink.objects.filter(owner=request.user)
    output = []
    now = timezone.now()
    for link in links:
        output.append({"id": str(link.id), "label": link.label,
                       "connected": bool(link.last_seen_at and (now - link.last_seen_at).total_seconds() < 30),
                       "last_seen_at": link.last_seen_at.isoformat() if link.last_seen_at else None,
                       "snapshot": link.snapshot,
                       "commands": [_command_dict(c) for c in link.commands.all()[:12]]})
    return Response({"links": output})


@extend_schema(exclude=True)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def queue_command(request):
    try:
        link_id = uuid.UUID(str(request.data.get("link_id")))
    except (ValueError, TypeError):
        return Response({"detail": "Invalid agent link"}, status=400)
    link = AgentLink.objects.filter(id=link_id, owner=request.user).first()
    if link is None:
        return Response({"detail": "Unknown agent link"}, status=404)
    action = request.data.get("action")
    asset_id = request.data.get("asset_id")
    snapshot = link.snapshot or {}
    assets = {str(a.get("id")): a for a in snapshot.get("assets", []) if isinstance(a, dict)}
    payload = {}
    if action == 'preview':
        if 'preview' not in snapshot.get('capabilities', []):
            return Response({'detail': 'Mac 연결 앱을 최신 버전으로 다시 설치한 뒤 미리보기를 사용해 주세요.'}, status=409)
        cleanup = snapshot.get('cleanup') or {}
        group_ids = {file.get('id') for group in cleanup.get('groups', []) for file in group.get('files', [])}
        if not isinstance(asset_id, str) or (asset_id not in assets and asset_id not in group_ids):
            return Response({'detail': 'Unknown asset'}, status=400)
        payload['id'] = asset_id
    elif action in {"answer", "approve", "keep", "undo"}:
        if not isinstance(asset_id, str) or asset_id not in assets:
            return Response({"detail": "Unknown asset"}, status=400)
        asset = assets[asset_id]
        payload["id"] = asset_id
        if action == "answer":
            pid = request.data.get("project_id")
            ids = {p.get("id") for p in snapshot.get("catalog", []) if isinstance(p, dict)}
            if not isinstance(pid, str) or pid not in ids:
                return Response({"detail": "Unknown project"}, status=400)
            payload["project_id"] = pid
        elif action == "approve":
            plan = asset.get("plan")
            if not isinstance(plan, dict) or plan.get("action") not in {"file", "archive"}:
                return Response({"detail": "No executable plan"}, status=400)
            payload["plan"] = plan  # Agent rechecks the plan and current file hash.
        elif action == "undo" and not asset.get("archived"):
            return Response({"detail": "Asset has not moved"}, status=400)
    elif action in {'cleanup_confirm', 'cleanup_dismiss', 'cleanup_retry', 'cleanup_scan'}:
        cleanup = snapshot.get('cleanup')
        if not isinstance(cleanup, dict):
            return Response({'detail': '최신 Mac 연결 앱을 설치해 일괄 정리를 준비하세요.'}, status=409)
        if cleanup.get('status') in {'scanning', 'generating'}:
            return Response({'detail': '일괄 정리 제안을 준비 중입니다.'}, status=409)
        if action == 'cleanup_scan' and 'cleanup_scan' not in snapshot.get('capabilities', []):
            return Response({'detail': 'Mac 연결 앱을 업데이트한 뒤 다시 분석해 주세요.'}, status=409)
        if action not in {'cleanup_retry', 'cleanup_scan'}:
            group_id = request.data.get('group_id')
            group = next((group for group in cleanup.get('groups', []) if isinstance(group, dict) and group.get('id') == group_id and group.get('status') == 'pending'), None)
            if not isinstance(group_id, str) or not group:
                return Response({'detail': '이미 처리되었거나 만료된 제안입니다.'}, status=409)
            payload['group_id'] = group_id
    elif action == "restore_trashed":
        index = request.data.get("trash_index")
        valid = {t.get("i") for t in snapshot.get("trashed", []) if isinstance(t, dict)}
        if not isinstance(index, int) or index not in valid:
            return Response({"detail": "Unknown trash item"}, status=400)
        payload["i"] = index
    else:
        return Response({"detail": "Unsupported action"}, status=400)
    if link.commands.filter(status__in=["pending", "running"]).exists():
        return Response({"detail": "A command is already in progress"}, status=409)
    command = AgentCommand.objects.create(owner=request.user, link=link, action=action, payload=payload)
    return Response(_command_dict(command), status=201)


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def bridge_poll(request):
    link = _bridge_link(request)
    if link is None:
        return Response({"detail": "Invalid bridge token"}, status=403)
    snapshot = request.data.get("snapshot")
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("assets"), list) or not isinstance(snapshot.get("catalog"), list):
        return Response({"detail": "Invalid agent state"}, status=400)
    if len(json.dumps(snapshot, ensure_ascii=False)) > 2_000_000:
        return Response({"detail": "Agent state too large"}, status=413)
    with transaction.atomic():
        link = AgentLink.objects.select_for_update().get(pk=link.pk)
        link.snapshot = snapshot
        link.last_seen_at = timezone.now()
        link.save(update_fields=["snapshot", "last_seen_at"])
        command = link.commands.filter(status="pending").order_by("created_at").first()
        if command:
            command.status = "running"
            command.save(update_fields=["status"])
    return Response({"command": _command_dict(command) if command else None})


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def bridge_result(request):
    link = _bridge_link(request)
    if link is None:
        return Response({"detail": "Invalid bridge token"}, status=403)
    try:
        command_id = uuid.UUID(str(request.data.get("id")))
    except (ValueError, TypeError):
        return Response({"detail": "Invalid command id"}, status=400)
    command = link.commands.filter(id=command_id, status="running").first()
    if command is None:
        return Response({"detail": "Command is not running"}, status=409)
    success = request.data.get("ok") is True
    result = request.data.get("result")
    if len(json.dumps(result, ensure_ascii=False)) > 50_000:
        return Response({"detail": "Result too large"}, status=413)
    command.status = "done" if success else "failed"
    command.result = {"ok": success, "result": result}
    command.finished_at = timezone.now()
    command.save(update_fields=["status", "result", "finished_at"])
    return Response(_command_dict(command))
