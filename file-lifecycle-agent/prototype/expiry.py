"""Persistent expiry proposals, exclusive Trash moves, and restoration. Never empties Trash."""
from pathlib import Path
import errno
import hashlib
import json
import os
import re
import stat
import time
import uuid

from preferences import atomic_json

INSTALLER = {'.dmg', '.pkg', '.mpkg'}
INSTALL_NAME = re.compile(r'(?i)setup|install')
VOLATILE_NAME = re.compile(r'(?i)공지|임시|일회용|(?:^|[\s_.-])(?:temp(?:orary)?|disposable)(?:[\s_.-]|$)')
VOLATILE_TYPES = {'.txt', '.md', '.pdf', '.docx', '.pptx', '.png', '.jpg', '.jpeg', '.heic'}
TRASH = Path.home() / '.Trash'
ACTIVE = {'pending', 'scheduled', 'paused', 'blocked', 'moving'}


def installer(path):
    return path.suffix.lower() in INSTALLER or (path.suffix.lower() in {'.zip', '.exe'} and bool(INSTALL_NAME.search(path.stem)))


def fingerprint(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode): raise ValueError('일반 파일만 처리할 수 있습니다.')
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns]


def digest(path):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'rb') as handle:
        result = hashlib.sha256()
        while chunk := handle.read(1024 * 1024): result.update(chunk)
    return result.hexdigest()


def move_exclusive(source, destination, expected, expected_digest=None):
    """A collision never replaces another file. Recheck identity before unlinking."""
    source, destination = Path(source), Path(destination)
    if fingerprint(source) != expected: raise ValueError('파일이 변경되었습니다.')
    created = False; linked = False
    try:
        try:
            os.link(source, destination, follow_symlinks=False); created = True; linked = True
        except OSError as error:
            if error.errno != errno.EXDEV: raise
            descriptor = os.open(source, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            with os.fdopen(descriptor, 'rb') as reader, destination.open('xb') as writer:
                created = True
                info = os.fstat(reader.fileno())
                if [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns] != expected:
                    raise ValueError('파일이 변경되었습니다.')
                while chunk := reader.read(1024 * 1024): writer.write(chunk)
                writer.flush(); os.fsync(writer.fileno())
                info = os.fstat(reader.fileno())
                if [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns] != expected:
                    raise ValueError('복사 중 파일이 변경되었습니다.')
        actual = fingerprint(destination)
        if linked and actual != expected: raise ValueError('이동 중 파일이 교체되었습니다.')
        if expected_digest and digest(destination) != expected_digest: raise ValueError('파일 내용이 변경되었습니다.')
        if fingerprint(source) != expected: raise ValueError('이동 중 파일이 변경되었습니다.')
        source.unlink()
    except BaseException:
        if created: destination.unlink(missing_ok=True)
        raise


class Expiry:
    def __init__(self, path, inboxes, days=3, trash=TRASH, policy=None, engine=None):
        self.path = Path(path); self.inboxes = [Path(x).expanduser().resolve() for x in inboxes]
        self.days = days; self.trash = Path(trash).expanduser(); self.policy = policy; self.engine = engine
        self._engine_cache = None; self._references_cache = None
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.data.setdefault('entries', {}); self.data.setdefault('trashed', [])
        self.data.pop('seen', None)  # Legacy clocks cannot identify replacement files; start fresh.
        self.by_key = {entry['key']: entry for entry in self.data['entries'].values()}
        for entry in self.data['entries'].values():
            if entry['status'] != 'moving': continue
            source, target = Path(entry['path']), Path(entry['trash'])
            if not source.exists() and target.is_file() and not target.is_symlink() and entry.get('digest') and digest(target) == entry['digest']:
                self._record_move(entry, target, time.time())
            else:
                entry.update(status='blocked', error='이동이 중단됐어요. 원본과 휴지통을 확인한 뒤 취소하거나 다시 예약하세요.')
        self.save()

    def current_engine(self):
        return self._engine_cache if self._engine_cache is not None else self.engine()

    def options(self):
        return self.policy() if self.policy else {'installers_enabled': self.days > 0, 'installer_days': max(1, self.days), 'volatile_mode': 'off', 'volatile_days': 7}

    def save(self): atomic_json(self.path, self.data)

    def _safe(self, path):
        path = Path(path)
        fingerprint(path)
        resolved = path.resolve()
        roots = list(self.inboxes)
        if self.engine:
            engine = self.current_engine(); roots += [engine.root, *[Path(value).expanduser().resolve() for value in engine.data.get('folders', {}).values()]]
        if not any(resolved.is_relative_to(root) for root in roots): raise ValueError('허용된 파일 위치가 아닙니다.')
        return resolved

    def _asset(self, asset_id):
        if not self.engine: raise ValueError('등록된 파일을 확인할 수 없습니다.')
        engine = self.current_engine(); asset = engine.data['assets'].get(asset_id)
        if not asset or asset.get('context') or asset.get('trashed'): raise ValueError('파일을 찾을 수 없습니다.')
        references = self._references_cache if self._references_cache is not None else {ref for item in engine.data['assets'].values() if engine.data['projects'].get(item.get('project')) != 'completed' for ref in item.get('refs', [])}
        if asset.get('keep') or asset.get('refs') or asset['path'] in references or Path(asset['path']).name in references:
            raise ValueError('유지하거나 참조 중인 파일은 삭제 예약에서 제외합니다.')
        return asset, engine.path(asset['path'])

    def _upsert(self, key, path, kind, days, mode, now, asset_id=None, initial=False):
        signature = fingerprint(path); old = self.by_key.get(key)
        if old and old['fingerprint'] == signature:
            if old['status'] in {'cancelled', 'trashed', 'blocked', 'moving'}: return old
            if old.get('mode') == 'approved' and old['status'] != 'paused':
                old['path'] = str(path); return old
            changed = old.get('days') != days or old.get('mode') != mode
            if changed:
                old.update(days=days, mode=mode, due_at=now + days * 86400)
            if old['status'] == 'paused' or changed:
                old.update(status='pending' if mode == 'review' or initial else 'scheduled', due_at=now + days * 86400)
            old['path'] = str(path)
            return old
        if old and old['status'] in ACTIVE: old.update(status='changed', error='파일이 바뀌어 이전 예약을 중단했습니다.')
        entry = {'id': uuid.uuid4().hex, 'key': key, 'path': str(path), 'name': path.name, 'kind': kind,
                 'asset_id': asset_id, 'fingerprint': signature, 'first_seen': now, 'due_at': now + days * 86400,
                 'days': days, 'mode': mode, 'status': 'pending' if mode == 'review' or initial else 'scheduled'}
        self.data['entries'][entry['id']] = entry; self.by_key[key] = entry
        return entry

    def schedule(self, asset_id, due_at, now=None):
        now = time.time() if now is None else now
        self._deadline(due_at, now)
        asset, path = self._asset(asset_id); path = self._safe(path)
        entry = self._upsert('asset:' + asset_id, path, 'manual', self.options()['volatile_days'], 'review', now, asset_id)
        entry.update(kind='manual', status='scheduled', due_at=due_at, error='')
        self.save(); return self._public_entry(entry)

    @staticmethod
    def _deadline(value, now):
        if type(value) not in (int, float) or not now + 60 <= value <= now + 366 * 86400:
            raise ValueError('1분 이후부터 1년 이내의 시간을 선택하세요.')

    def decide(self, entry_id, action, due_at=None, now=None):
        now = time.time() if now is None else now
        entry = self.data['entries'].get(entry_id)
        if not entry or entry['status'] not in ACTIVE | {'changed'}: raise ValueError('예약 상태가 바뀌었어요. 다시 확인해 주세요.')
        if action == 'cancel': entry.update(status='cancelled', error='')
        else:
            path = self._source(entry)
            if fingerprint(path) != entry['fingerprint']: raise ValueError('파일이 바뀌었습니다. 새로 예약해 주세요.')
            if due_at is not None: self._deadline(due_at, now); entry['due_at'] = due_at
            elif entry['due_at'] < now + 60: entry['due_at'] = now + entry['days'] * 86400
            entry.update(status='scheduled', error='', mode='approved')
            options = self.options()
            if (entry['kind'] == 'installer' and not options['installers_enabled']) or (entry['kind'] == 'volatile' and options['volatile_mode'] == 'off'):
                entry['status'] = 'paused'
        self.save(); return self._public_entry(entry)

    def _source(self, entry):
        if entry.get('asset_id'):
            _, path = self._asset(entry['asset_id'])
        else: path = Path(entry['path'])
        return self._safe(path)

    def _record_move(self, entry, destination, now):
        signature = fingerprint(destination)
        if not any(item.get('entry_id') == entry['id'] and not item.get('restored') for item in self.data['trashed']):
            self.data['trashed'].append({'entry_id': entry['id'], 'asset_id': entry.get('asset_id'), 'path': entry['path'],
                                        'trash': str(destination), 'at': now, 'fingerprint': signature, 'digest': entry.get('digest')})
        entry.update(status='trashed', trash=str(destination), error='')
        if entry.get('asset_id') and self.engine:
            engine = self.current_engine(); engine.data['assets'][entry['asset_id']]['trashed'] = True; engine.save()

    def sweep(self, now=None, execute=True):
        self._engine_cache = self.engine() if self.engine else None
        if self._engine_cache is not None:
            engine = self._engine_cache
            self._references_cache = {ref for item in engine.data['assets'].values() if engine.data['projects'].get(item.get('project')) != 'completed' for ref in item.get('refs', [])}
        try: return self._sweep(now, execute)
        finally: self._engine_cache = None; self._references_cache = None

    def _sweep(self, now=None, execute=True):
        now = time.time() if now is None else now; options = self.options(); moved = []
        if options['installers_enabled']:
            for folder in self.inboxes:
                for path in folder.glob('*'):
                    if path.is_symlink() or not path.is_file() or path.name.startswith('.') or not installer(path): continue
                    if 0 <= now - path.stat().st_mtime < 60: continue  # still downloading: register once the file settles
                    try: self._upsert('installer:' + str(path), self._safe(path), 'installer', options['installer_days'], 'auto', now)
                    except (OSError, ValueError): continue
        if self.engine and options['volatile_mode'] != 'off':
            engine = self.current_engine()
            for asset in engine.data['assets'].values():
                path = Path(asset['path'])
                if path.suffix.lower() not in VOLATILE_TYPES or not VOLATILE_NAME.search(path.stem): continue
                old = self.by_key.get('asset:' + asset['id'])
                if old and old['kind'] == 'manual': continue
                try:
                    current, path = self._asset(asset['id'])
                    self._upsert('asset:' + asset['id'], path, 'volatile', options['volatile_days'], options['volatile_mode'], now,
                                 asset['id'], initial=current.get('initial_import', True))
                except (OSError, ValueError): continue
        for entry in list(self.data['entries'].values()):
            if entry['status'] not in {'scheduled', 'pending', 'paused'}: continue
            if (entry['kind'] == 'installer' and not options['installers_enabled']) or (entry['kind'] == 'volatile' and options['volatile_mode'] == 'off'):
                entry['status'] = 'paused'; continue
            if not execute or entry['status'] != 'scheduled' or entry['due_at'] > now: continue
            try:
                source = self._source(entry)
                if fingerprint(source) != entry['fingerprint']:
                    entry.update(status='changed', error='파일이 변경되어 예약을 중단했습니다.'); continue
                if self.trash.is_symlink(): raise ValueError('휴지통 경로가 링크입니다.')
                self.trash.mkdir(parents=True, exist_ok=True, mode=0o700)
                destination = self.trash / source.name
                if destination.exists() or destination.is_symlink():
                    destination = self.trash / (source.stem + ' ' + uuid.uuid4().hex[:12] + source.suffix)
                content_hash = digest(source)
                if fingerprint(source) != entry['fingerprint']: raise ValueError('파일이 변경되었습니다.')
                entry.update(status='moving', path=str(source), trash=str(destination), digest=content_hash); self.save()
                move_exclusive(source, destination, entry['fingerprint'], content_hash)
                self._record_move(entry, destination, now); moved.append(source.name)
            except FileNotFoundError: entry.update(status='missing', error='파일이 이동되었거나 삭제되었습니다.')
            except PermissionError: entry.update(status='blocked', error='파일과 휴지통에 접근할 권한을 확인해 주세요.')
            except OSError: entry.update(status='blocked', error='파일 이동에 실패했습니다. Mac에서 파일 상태를 확인해 주세요.')
            except ValueError as error: entry.update(status='blocked', error=str(error)[:200])
        self.save(); return moved

    def restore(self, index):
        if type(index) is not int or not 0 <= index < len(self.data['trashed']): raise ValueError('복구 항목을 찾을 수 없습니다.')
        item = self.data['trashed'][index]
        if item.get('restored'): raise ValueError('이미 복구한 파일입니다.')
        source, destination = Path(item['trash']), Path(item['path'])
        if not source.resolve().is_relative_to(self.trash.resolve()): raise ValueError('휴지통 경로가 올바르지 않습니다.')
        if destination.exists() or destination.is_symlink(): raise FileExistsError('원래 위치에 같은 이름의 파일이 있습니다.')
        # Validate destination roots without requiring a file that has not yet been restored.
        roots = list(self.inboxes)
        if self.engine:
            engine = self.current_engine(); roots += [engine.root, *[Path(value).expanduser().resolve() for value in engine.data.get('folders', {}).values()]]
        if not any(destination.resolve().is_relative_to(root) for root in roots): raise ValueError('복구 위치가 허용 범위 밖입니다.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        move_exclusive(source, destination, item.get('fingerprint') or fingerprint(source), item.get('digest'))
        now = time.time(); item['restored'] = now
        entry = self.data['entries'].get(item.get('entry_id'))
        if entry: entry.update(status='scheduled', fingerprint=fingerprint(destination), first_seen=now, due_at=now + entry['days'] * 86400)
        if item.get('asset_id') and self.engine:
            engine = self.current_engine(); engine.data['assets'][item['asset_id']]['trashed'] = False; engine.save()
        self.save(); return {'restored': True}

    @staticmethod
    def _public_entry(entry):
        return {key: entry.get(key) for key in ('id', 'asset_id', 'name', 'kind', 'status', 'due_at', 'first_seen', 'error')}

    def public(self):
        entries = [entry for entry in self.data['entries'].values() if entry['status'] in ACTIVE or entry['status'] == 'changed']
        entries.sort(key=lambda entry: entry['due_at'])
        return {'entries': [self._public_entry(entry) for entry in entries[:100]], 'total': len(entries)}
