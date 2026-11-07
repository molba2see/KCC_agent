"""First-run classification proposals. The model proposes; only confirmation changes folders."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import uuid

from agent_v5 import content, TEXT, IMAGE, INSTRUCTION
from lifecycle_v3 import sha


def atomic(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def safe_name(value):
    return (isinstance(value, str) and 1 <= len(value) <= 60 and value.strip() == value
            and not value.startswith('.') and '..' not in value
            and not re.search(r'[/\\:\x00-\x1f]', value) and not INSTRUCTION.search(value))


class InitialCleanup:
    def __init__(self, demo, catalog, python, worker, destination, request_id=None):
        self.demo, self.catalog = demo, catalog
        self.python, self.worker = Path(python), Path(worker)
        self.destination = Path(destination).expanduser().resolve()
        self.path = demo.root / 'initial-cleanup.json'
        self.thread = None
        try:
            self.data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.data = {'status': 'scanning', 'groups': [], 'total': 0, 'model_processed': 0}
        if self.data.get('version') != 2:
            for group in self.data['groups']:
                if group['status'] == 'pending': group['status'] = 'stale'
            self.data.update(version=2, status='scanning', scan_id=uuid.uuid4().hex)
        if self.data['status'] == 'generating':
            self.data.update(status='failed', detail='제안 준비가 중단됐어요. 다시 제안받기를 눌러 주세요.')
        if request_id and self.data.get('request_id') != request_id:
            for group in self.data['groups']:
                if group['status'] in {'pending', 'dismissed'}: group['status'] = 'stale'
            self.data.update(request_id=request_id, status='scanning', detail='', scan_id=uuid.uuid4().hex,
                             reanalyze=bool(self.demo.engine().data['assets']))
        self.save()

    def save(self):
        atomic(self.path, self.data)

    def eligible(self, asset):
        origin = getattr(self.demo, 'origins', {}).get(asset.get('original'), {})
        kind = origin.get('kind') if isinstance(origin, dict) else origin
        return (kind != 'icloud' and not asset.get('context') and not asset.get('keep')
                and asset['path'] == asset['original'] and Path(asset['path']).suffix.lower() in TEXT | IMAGE)

    def rescan(self):
        """Explicitly reconsider unconfirmed files, preserving approvals and kept files."""
        if self.data['status'] in {'scanning', 'generating'} or (self.thread and self.thread.is_alive()):
            raise ValueError('이미 파일을 분석하고 있어요. 완료될 때까지 기다려 주세요.')
        for group in self.data['groups']:
            if group['status'] in {'pending', 'dismissed'}: group['status'] = 'stale'
        self.data.update(status='scanning', detail='', model_processed=0, scan_id=uuid.uuid4().hex, reanalyze=True)
        self.save()
        return {'scanning': True}

    def observe(self, watcher):
        if self.data['status'] != 'scanning':
            return
        with self.demo.lock:
            engine = self.demo.engine()
            known = {a['original'] for a in engine.data['assets'].values()}
            remaining = [p for p, target in watcher.candidates()
                         if target is not None or str(p.relative_to(self.demo.root)) not in known]
            self.data['total'] = max(self.data['total'], len(known) + len(remaining))
            self.save()
        if not remaining:
            self.start()

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        with self.demo.lock:
            self.data.update(status='generating', detail='', model_processed=0)
            self.save()
        self.thread = threading.Thread(target=self.generate, daemon=True)
        self.thread.start()

    def generate(self):
        request_path = response_path = process = None
        try:
            if self.data.get('reanalyze'):
                with self.demo.lock:
                    retry_ids = [asset['id'] for asset in self.demo.engine().data['assets'].values() if self.eligible(asset)]
                for aid in retry_ids:
                    with self.demo.lock:
                        if self.eligible(self.demo.engine().data['assets'][aid]): self.demo.analyze(aid)
                with self.demo.lock:
                    self.data['reanalyze'] = False
                    self.save()
            with self.demo.lock:
                engine = self.demo.engine()
                claimed = {aid for group in self.data['groups'] if group['status'] != 'stale' for aid in group['asset_ids']}
                original_groups = list(self.data['groups'])
                assets = [dict(asset) for asset in engine.data['assets'].values()
                          if self.eligible(asset) and asset['id'] not in claimed]
                catalog = [{'id': pid, 'name': item['name'], 'guide': item.get('profile', '')[:1800]}
                           for pid, item in self.catalog.items()]
            files = []
            # Confident classifications are proposals too; none execute before confirmation.
            assigned = {}
            for asset in assets:
                if asset.get('project') in self.catalog and not asset.get('refs'):
                    assigned.setdefault(asset['project'], []).append(asset['id'])
            with self.demo.lock:
                self.accept_groups([{'project_id': pid, 'purpose': '선택한 폴더의 정리 지침에 맞는 파일입니다.', 'files': ids}
                                    for pid, ids in assigned.items()], assets)
                original_groups = list(self.data['groups'])
                self.save()
            assigned_ids = {aid for ids in assigned.values() for aid in ids}
            for asset in assets:
                if asset['id'] in assigned_ids or asset.get('refs'): continue
                try:
                    text = content(engine.path(asset['path']))[:1000]
                except Exception:
                    text = ''
                files.append({'id': asset['id'], 'name': Path(asset['original']).name, 'text': text})
            if not files:
                with self.demo.lock:
                    self.data['status'] = 'review' if any(g['status'] == 'pending' for g in self.data['groups']) else 'completed'
                    self.save()
                return
            for suffix in ('request', 'response'):
                with tempfile.NamedTemporaryFile(prefix='.cleanup-', suffix='.' + suffix + '.json', dir=self.demo.root, delete=False) as handle:
                    if suffix == 'request': request_path = Path(handle.name)
                    else: response_path = Path(handle.name)
            atomic(request_path, {'catalog': catalog, 'files': files})
            with (self.demo.root / 'cleanup-model.log').open('a') as log:
                process = subprocess.Popen([str(self.python), str(self.worker), '--request', str(request_path), '--response', str(response_path), '--parent-pid', str(os.getpid())],
                                           stdin=subprocess.DEVNULL, stdout=log, stderr=log)
            deadline = time.monotonic() + max(1800, len(files) * 120)
            while True:
                try:
                    response = json.loads(response_path.read_text())
                except (OSError, ValueError):
                    response = {}
                with self.demo.lock:
                    self.data['groups'] = list(original_groups)
                    self.accept_groups(response.get('groups', []), assets)
                    self.data['model_processed'] = min(len(files), int(response.get('processed', 0)))
                    self.save()
                if process.poll() is not None:
                    response = json.loads(response_path.read_text())
                    with self.demo.lock:
                        self.data['groups'] = list(original_groups)
                        self.accept_groups(response.get('groups', []), assets)
                        self.data['model_processed'] = min(len(files), int(response.get('processed', 0)))
                        self.save()
                    if process.returncode or response.get('status') != 'completed':
                        raise ValueError('Model proposal failed')
                    break
                if time.monotonic() > deadline:
                    process.terminate()
                    process.wait(timeout=10)
                    raise TimeoutError('Model proposal timeout')
                time.sleep(1)
            with self.demo.lock:
                self.data['status'] = 'review' if any(g['status'] == 'pending' for g in self.data['groups']) else 'completed'
                self.save()
        except Exception:
            with self.demo.lock:
                self.data.update(status='failed', detail='재분류 제안을 준비하지 못했어요. Mac 연결과 모델 준비 상태를 확인한 뒤 다시 시도해 주세요.')
                self.save()
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
            for path in (request_path, response_path):
                if path is not None: path.unlink(missing_ok=True)

    def accept_groups(self, values, assets):
        if not isinstance(values, list):
            raise ValueError('Invalid groups')
        by_id = {asset['id']: asset for asset in assets}
        claimed = {aid for group in self.data['groups'] if group['status'] != 'stale' for aid in group['asset_ids']}
        existing_ids = {group['id'] for group in self.data['groups']}
        for value in values:
            if not isinstance(value, dict): raise ValueError('Invalid group')
            ids, target = value.get('files'), value.get('project_id')
            if (not isinstance(ids, list) or not ids or any(not isinstance(aid, str) or aid not in by_id for aid in ids) or len(ids) != len(set(ids))):
                raise ValueError('Unknown proposal files')
            if not isinstance(target, str) or (target != 'new' and target not in self.catalog): raise ValueError('Unknown proposal folder')
            name = value.get('name') if target == 'new' else self.catalog[target]['name']
            purpose = value.get('purpose', '')
            if (target == 'new' and not safe_name(name)) or not isinstance(purpose, str) or not 4 <= len(purpose) <= 600 or INSTRUCTION.search(purpose):
                raise ValueError('Invalid proposal description')
            if target == 'new' and any(item['name'].casefold() == name.casefold() for item in self.catalog.values()):
                raise ValueError('Existing folder name')
            group_id = hashlib.sha256(json.dumps([self.data.get('scan_id', 'initial'), target, name, purpose, sorted((aid, by_id[aid]['hash']) for aid in ids)], ensure_ascii=False).encode()).hexdigest()[:32]
            if group_id in existing_ids: continue
            if any(aid in claimed for aid in ids): raise ValueError('Duplicate proposal files')
            self.data['groups'].append({'id': group_id, 'name': name, 'purpose': purpose, 'project_id': target,
                                        'asset_ids': ids, 'hashes': {aid: by_id[aid]['hash'] for aid in ids},
                                        'projects': {aid: by_id[aid].get('project') for aid in ids}, 'status': 'pending'})
            existing_ids.add(group_id); claimed.update(ids)

    def public(self):
        engine = self.demo.engine()
        assets = engine.data['assets']
        groups = []
        changed = False
        for group in self.data['groups']:
            if group['status'] == 'pending' and any(
                aid not in assets or not self.eligible(assets[aid])
                or assets[aid].get('hash') != group['hashes'].get(aid)
                or assets[aid].get('project') != group.get('projects', {}).get(aid)
                for aid in group['asset_ids']
            ):
                group['status'] = 'stale'
                changed = True
        if changed:
            self.save()
        pending = [group for group in self.data['groups'] if group['status'] == 'pending']
        for group in pending[:20]:
            reused = next((old.get('created_project') for old in self.data['groups'] if old['status'] == 'approved' and old['name'] == group['name'] and old.get('created_project') in self.catalog), None)
            groups.append({key: group[key] for key in ('id', 'name', 'purpose', 'status')})
            groups[-1].update(new_folder=group['project_id'] == 'new' and not reused,
                              destination='iCloud Drive / 모아' if group['project_id'] == 'new' else '선택한 폴더',
                              files=[{'id': aid, 'name': Path(assets[aid]['original']).name} for aid in group['asset_ids'] if aid in assets])
        visible = [asset for asset in assets.values() if not asset.get('context')]
        return {'status': self.data['status'], 'detail': self.data.get('detail', ''),
                'total': max(self.data['total'], len(visible)), 'processed': len(visible),
                'classified': sum(bool(a.get('project')) for a in visible),
                'remaining': sum(self.eligible(a) for a in visible),
                'model_processed': self.data.get('model_processed', 0), 'pending_groups': len(pending), 'groups': groups}

    def decide(self, group_id, approve):
        group = next((group for group in self.data['groups'] if group['id'] == group_id), None)
        if not group or group['status'] != 'pending': raise ValueError('이미 처리되었거나 만료된 제안입니다.')
        if not approve:
            group['status'] = 'dismissed'; self.save(); return {'dismissed': True}
        engine = self.demo.engine()
        previous = {aid: dict(engine.data['assets'].get(aid, {})) for aid in group['asset_ids']}
        for aid in group['asset_ids']:
            asset = engine.data['assets'].get(aid)
            if (not asset or not self.eligible(asset) or asset.get('refs') or asset['hash'] != group['hashes'][aid]
                    or asset.get('project') != group.get('projects', {}).get(aid)
                    or sha(engine.path(asset['path'])) != group['hashes'][aid]):
                raise ValueError('파일 상태가 바뀌었어요. 개별 분류 화면에서 다시 확인해 주세요.')
        reused = next((old.get('created_project') for old in self.data['groups'] if old['status'] == 'approved' and old['name'] == group['name'] and old.get('created_project') in self.catalog), None) if group['project_id'] == 'new' else None
        created = group['project_id'] == 'new' and not reused
        pid = 'folder_' + uuid.uuid4().hex[:16] if created else reused or group['project_id']
        folder = self.destination / group['name'] if created else Path(engine.data['folders'][pid]).expanduser()
        if created:
            if self.destination.resolve() != self.destination or folder.exists() or folder.is_symlink():
                raise ValueError('같은 이름의 폴더가 있거나 저장 위치가 바뀌었어요.')
        elif folder.is_symlink() or not folder.is_dir():
            raise ValueError('대상 폴더를 확인해 주세요.')
        names = [Path(engine.data['assets'][aid]['path']).name for aid in group['asset_ids']]
        if len(names) != len(set(names)) or any((folder / name).exists() for name in names):
            raise ValueError('같은 이름의 파일이 있어요. 개별 분류 화면에서 확인해 주세요.')
        moved = []; made_folder = made_guide = False; previous_projects = None; config_written = False
        try:
            if created:
                self.destination.mkdir(parents=True, exist_ok=True)
                if self.destination.resolve() != self.destination: raise ValueError('저장 위치가 바뀌었어요.')
                folder.mkdir(exist_ok=False); made_folder = True
                guide = '# ' + group['name'] + '\n\n' + group['purpose'] + '\n\n## 승인한 자료\n' + ''.join('- ' + name.replace('\n', ' ') + '\n' for name in names)
                with (folder / '_project.md').open('x', encoding='utf-8') as handle: handle.write(guide)
                made_guide = True
                engine.data['projects'][pid] = 'active'; engine.data.setdefault('folders', {})[pid] = str(folder)
                self.catalog[pid] = {'name': group['name'], 'desc': group['purpose'], 'profile': guide, 'keywords': []}
                engine.save()
            for aid in group['asset_ids']:
                engine = self.demo.engine(); engine.data['assets'][aid].update(project=pid, reason='사용자가 일괄 정리 제안을 확인함'); engine.save()
                plan = engine.plan(aid)
                if plan['action'] != 'file': raise ValueError('파일을 이동할 수 없는 상태입니다.')
                engine.execute(aid, plan); moved.append(aid)
            # Publish config last: the supervisor restarts the agent when it changes.
            if created and self.demo.projects_path:
                projects = json.loads(self.demo.projects_path.read_text()); previous_projects = dict(projects)
                projects[pid] = {'name': group['name'], 'folder': str(folder), 'desc': group['purpose'], 'keywords': []}
                atomic(self.demo.projects_path, projects); config_written = True
            if created or reused: group['created_project'] = pid
            group['status'] = 'approved'; self.save()
            return {'approved': True, 'count': len(moved), 'folder': group['name']}
        except Exception:
            if config_written: atomic(self.demo.projects_path, previous_projects)
            group['status'] = 'pending'
            for aid in reversed(moved): self.demo.engine().undo(aid)
            engine = self.demo.engine()
            for aid in group['asset_ids']: engine.data['assets'][aid].update(project=previous[aid].get('project'), reason=previous[aid].get('reason'))
            if created:
                engine.data['projects'].pop(pid, None); engine.data['folders'].pop(pid, None); self.catalog.pop(pid, None)
                if made_folder and folder.is_dir() and not folder.is_symlink():
                    guide_path = folder / '_project.md'
                    if made_guide and guide_path.is_file() and not guide_path.is_symlink() and guide_path.read_text() == guide: guide_path.unlink()
                    try: folder.rmdir()
                    except OSError: pass
            engine.save()
            raise
