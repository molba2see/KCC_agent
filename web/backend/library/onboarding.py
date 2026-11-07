"""Account-specific Mac/iPhone setup progress and observable file receipt."""
from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AgentLink, OnboardingProgress


def current_state(user, progress):
    links = list(AgentLink.objects.filter(owner=user))
    cutoff = timezone.now() - timedelta(seconds=30)
    online = [link for link in links if link.last_seen_at and link.last_seen_at > cutoff]
    received = []
    baseline = set(progress.baseline_assets)
    if progress.test_started_at:
        for link in online:
            if link.last_seen_at <= progress.test_started_at:
                continue
            for asset in (link.snapshot or {}).get('assets', []):
                recent_source = isinstance(asset, dict) and (asset.get('source_mtime') is None or (isinstance(asset.get('source_mtime'), (int, float)) and asset['source_mtime'] >= progress.test_started_at.timestamp()))
                if recent_source and (not link.snapshot.get('cleanup') or asset.get('source_kind') == 'icloud') and str(link.id) + ':' + str(asset.get('id')) not in baseline:
                    received.append(str(asset.get('name') or '새 파일'))
    cleanup_link = next((link for link in online if isinstance((link.snapshot or {}).get('cleanup'), dict)), None)
    return {'cleanup_confirmed': progress.initial_cleanup_confirmed,
            'cleanup': cleanup_link.snapshot['cleanup'] if cleanup_link else None,
            'cleanup_link_id': str(cleanup_link.id) if cleanup_link else str(online[0].id) if online else None,
            'cleanup_busy': bool(cleanup_link and (cleanup_link.snapshot.get('agent_available') is False or cleanup_link.commands.filter(status__in=['pending', 'running']).exists())),
            'mac_connected': bool(online), 'iphone_icloud_confirmed': progress.iphone_icloud_confirmed,
            'test_started': progress.test_started_at is not None,
            'file_received': bool(received), 'received_filename': received[0] if received else None,
            'completed': progress.completed_at is not None,
            'completed_at': progress.completed_at.isoformat() if progress.completed_at else None}


@extend_schema(exclude=True)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def progress(request):
    record, _ = OnboardingProgress.objects.get_or_create(owner=request.user)
    if request.method == 'POST':
        if not isinstance(request.data, dict):
            return Response({'detail': '온보딩 요청이 올바르지 않습니다.'}, status=400)
        action = request.data.get('action')
        if action == 'defer_cleanup':
            if not current_state(request.user, record)['mac_connected']:
                return Response({'detail': 'Mac 연결을 먼저 확인하세요.'}, status=409)
            record.initial_cleanup_confirmed = True
            record.save(update_fields=['initial_cleanup_confirmed'])
        elif action == 'confirm_cleanup':
            state = current_state(request.user, record)
            cleanup = state.get('cleanup')
            if not state['mac_connected'] or not cleanup or state['cleanup_busy'] or cleanup.get('status') not in {'review', 'completed'} or cleanup.get('pending_groups', 0) or any(group.get('status') == 'pending' for group in cleanup.get('groups', [])):
                return Response({'detail': '일괄 정리 제안을 확인하거나 보류한 뒤 계속하세요.'}, status=409)
            record.initial_cleanup_confirmed = True
            record.save(update_fields=['initial_cleanup_confirmed'])
        elif action == 'confirm_iphone':
            record.iphone_icloud_confirmed = True
            record.save(update_fields=['iphone_icloud_confirmed'])
        elif action == 'start_test':
            state = current_state(request.user, record)
            if not state['mac_connected'] or not record.iphone_icloud_confirmed or not record.initial_cleanup_confirmed:
                return Response({'detail': 'Mac 연결과 iPhone iCloud 설정 확인을 먼저 완료하세요.'}, status=409)
            record.baseline_assets = [str(link.id) + ':' + str(asset.get('id'))
                for link in AgentLink.objects.filter(owner=request.user)
                for asset in (link.snapshot or {}).get('assets', []) if isinstance(asset, dict)]
            record.test_started_at = timezone.now()
            record.save(update_fields=['baseline_assets', 'test_started_at'])
        elif action == 'complete':
            state = current_state(request.user, record)
            if not (state['mac_connected'] and state['iphone_icloud_confirmed'] and state['file_received']):
                return Response({'detail': '테스트 시작 후 새 파일이 Mac에서 수신되어야 완료할 수 있습니다.'}, status=409)
            record.completed_at = record.completed_at or timezone.now()
            record.save(update_fields=['completed_at'])
        else:
            return Response({'detail': '지원하지 않는 온보딩 요청입니다.'}, status=400)
    return Response(current_state(request.user, record))
