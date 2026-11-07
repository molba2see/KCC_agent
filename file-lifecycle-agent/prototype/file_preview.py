"""Read a registered file only when the user requests a bounded preview."""
import base64
from pathlib import Path
import subprocess
import tempfile

from agent_v5 import content, DOCS, IMAGE, TEXT


def preview(engine, asset_id):
    asset = engine.data['assets'].get(asset_id)
    if not asset or asset.get('context'):
        raise ValueError('등록된 파일을 찾을 수 없습니다.')
    path = engine.path(asset['path'])
    if not path.is_file():
        raise ValueError('파일이 이동되었거나 삭제되었습니다.')
    size = path.stat().st_size
    if size > 20_000_000:
        raise ValueError('20MB 이하 파일만 미리볼 수 있습니다.')
    result = {'name': path.name, 'size': size}
    suffix = path.suffix.lower()
    if suffix in IMAGE:
        with tempfile.TemporaryDirectory(prefix='moa-preview-') as directory:
            target = Path(directory) / 'preview.jpg'
            for dimension in (640, 320, 160):
                subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '55',
                                '-Z', str(dimension), str(path), '--out', str(target)],
                               check=True, capture_output=True, timeout=20)
                data = target.read_bytes()
                if len(data) <= 28_000:
                    return {**result, 'kind': 'image', 'mime': 'image/jpeg',
                            'data': base64.b64encode(data).decode('ascii')}
        raise ValueError('이미지 미리보기를 만들지 못했습니다.')
    if suffix in TEXT or suffix in DOCS:
        if suffix in DOCS:
            text = content(path)
        else:
            with path.open('rb') as stream:
                text = stream.read(64_000).decode('utf-8', errors='replace')
        return {**result, 'kind': 'text', 'text': text[:6000],
                'truncated': len(text) > 6000 or (suffix not in DOCS and size > 64_000)}
    raise ValueError('이 형식은 웹 미리보기를 지원하지 않습니다. Mac에서 원본을 확인해 주세요.')
