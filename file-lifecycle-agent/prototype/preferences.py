"""Persistent Mac policy. Browser requests cannot change paths or model arguments."""
import json
import os
from pathlib import Path
import tempfile
import time

DEFAULTS = {'download_mode': 'auto', 'screenshot_mode': 'auto', 'icloud_mode': 'auto',
            'installers_enabled': True, 'installer_days': 3, 'volatile_mode': 'review', 'volatile_days': 7}


def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, prefix='.' + path.name, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            os.chmod(temporary, 0o600)
            json.dump(value, handle, ensure_ascii=False)
            handle.flush(); os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True); raise
    try: os.replace(temporary, path)
    finally: temporary.unlink(missing_ok=True)


def validate(values):
    if not isinstance(values, dict) or not values or set(values) - set(DEFAULTS):
        raise ValueError('알 수 없는 설정입니다.')
    for key, value in values.items():
        if key.endswith('_days'):
            valid = type(value) is int and 1 <= value <= 365
        elif key == 'installers_enabled': valid = type(value) is bool
        elif key == 'volatile_mode': valid = value in ('off', 'review', 'auto')
        else: valid = value in ('review', 'auto')
        if not valid: raise ValueError('설정 값이 올바르지 않습니다: ' + key)
    return dict(values)


class Preferences:
    def __init__(self, path):
        self.path = Path(path)
        stored = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.values = {**DEFAULTS, **validate(stored['values'])} if stored else dict(DEFAULTS)
        self.revision = stored.get('revision', 0)
        self.updated_at = stored.get('updated_at')

    def public(self): return {**self.values, 'revision': self.revision, 'updated_at': self.updated_at}

    def update(self, values, revision):
        if type(revision) is not int or revision != self.revision:
            raise ValueError('다른 화면에서 설정이 변경됐어요. 새로고침 후 다시 저장해 주세요.')
        changes = validate(values)
        updated = {**self.values, **changes}
        now = time.time()
        atomic_json(self.path, {'values': updated, 'revision': self.revision + 1, 'updated_at': now})
        self.values = updated; self.revision += 1; self.updated_at = now
        return self.public()
