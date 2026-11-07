"""Build a universal macOS helper download from explicitly selected source files."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import plistlib
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
DOWNLOADS = ROOT / 'web/dist/downloads'
EXTENSIONS = {'.py', '.md', '.html', '.js', '.css', '.svg', '.png', '.ico', '.webmanifest', '.swift'}


def source_files():
    for directory in ('web/backend', 'web/bridge', 'web/dist', 'file-lifecycle-agent/prototype'):
        for path in sorted((ROOT / directory).rglob('*')):
            relative = path.relative_to(ROOT)
            if not path.is_file() or any(part in {'__pycache__', 'downloads', 'staticfiles', '.venv'} for part in relative.parts):
                continue
            if path.suffix in EXTENSIONS or path.name == 'requirements.txt':
                yield path
    for name in ('web/local/run.py', 'web/local/install.py', 'web/local/folder_guides.py', 'web/local/batch_proposals.py',
                 'web/local/requirements-qwen.txt', 'file-lifecycle-agent/requirements.txt', 'web/THIRD_PARTY_NOTICES.md'):
        yield ROOT / name


def source_archive(ocr):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for path in source_files():
            archive.add(path, arcname=str(path.relative_to(ROOT)))
        archive.add(ocr, arcname='file-lifecycle-agent/prototype/bin/ocr')
    return stream.getvalue()


def universal(source, output, frameworks):
    parts = []
    for architecture in ('arm64', 'x86_64'):
        target = output.with_name(output.name + '-' + architecture)
        command = ['swiftc', '-O', '-target', architecture + '-apple-macos14.0', str(source), '-o', str(target)]
        for name in frameworks:
            command += ['-framework', name]
        subprocess.run(command, check=True)
        parts.append(str(target))
    subprocess.run(['lipo', '-create', *parts, '-output', str(output)], check=True)
    output.chmod(0o755)


def build(origin='https://3.38.192.19'):
    from urllib.parse import urlsplit
    parsed = urlsplit(origin)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
        raise ValueError('Expected an HTTPS site origin')
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(origin.encode())
    for path in [*source_files(), ROOT / 'web/local/HelperLauncher.swift', ROOT / 'web/local/install-helper.sh', Path(__file__)]:
        fingerprint.update(str(path.relative_to(ROOT)).encode()); fingerprint.update(path.read_bytes())
    build_id = fingerprint.hexdigest()
    metadata_path = DOWNLOADS / 'helper.json'
    destination = DOWNLOADS / 'moa-mac-helper.zip'
    if metadata_path.exists() and destination.exists():
        previous = json.loads(metadata_path.read_text())
        if previous.get('build_id') == build_id and previous.get('sha256') == hashlib.sha256(destination.read_bytes()).hexdigest():
            print('Mac helper download is up to date', flush=True)
            return destination
    with tempfile.TemporaryDirectory(prefix='moa-helper-build-') as directory:
        work = Path(directory)
        app = work / 'Moa Helper.app'
        resources = app / 'Contents/Resources'
        binary = app / 'Contents/MacOS/MoaHelper'
        resources.mkdir(parents=True)
        binary.parent.mkdir()
        universal(ROOT / 'file-lifecycle-agent/prototype/ocr.swift', work / 'ocr', ['Vision', 'AppKit'])
        subprocess.run(['codesign', '--force', '--sign', '-', str(work / 'ocr')], check=True, capture_output=True)
        payload = source_archive(work / 'ocr')
        digest = hashlib.sha256(payload).hexdigest()
        (resources / 'source.tar.gz').write_bytes(payload)
        (resources / 'install-helper.sh').write_bytes((ROOT / 'web/local/install-helper.sh').read_bytes())
        info = {'CFBundleExecutable': 'MoaHelper', 'CFBundleIdentifier': 'com.moa.helper',
                'CFBundleName': '모아 연결', 'CFBundleDisplayName': '모아 연결', 'CFBundlePackageType': 'APPL',
                'CFBundleShortVersionString': '0.1.0', 'LSMinimumSystemVersion': '14.0',
                'NSHighResolutionCapable': True, 'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True},
                'MoaOrigin': origin, 'MoaSourceSHA256': digest,
                'CFBundleURLTypes': [{'CFBundleURLName': 'com.moa.helper.connect', 'CFBundleURLSchemes': ['moa-helper']} ]}
        (app / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
        universal(ROOT / 'web/local/HelperLauncher.swift', binary, ['Cocoa'])
        subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(app)], check=True, capture_output=True)
        destination = DOWNLOADS / 'moa-mac-helper.zip'
        temporary = destination.with_suffix('.tmp')
        # ditto preserves macOS app bundle metadata and executable permissions.
        subprocess.run(['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(app), str(temporary)], check=True)
        temporary.replace(destination)
        metadata = {'url': '/downloads/moa-mac-helper.zip', 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
                    'source_sha256': digest, 'build_id': build_id, 'architectures': ['arm64', 'x86_64'], 'minimum_macos': '14.0'}
        (DOWNLOADS / 'helper.json').write_text(json.dumps(metadata, ensure_ascii=False))
        print(f'Built Mac helper: {destination.stat().st_size} bytes ({digest[:12]})', flush=True)
        return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', default='https://3.38.192.19')
    build(parser.parse_args().origin)
