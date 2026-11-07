"""Register the user's local helper and open first-run setup in Safari."""
import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import time
from urllib.parse import quote, unquote
import unicodedata
import shutil
from urllib.request import urlopen

REPO = Path(__file__).resolve().parents[2]
DATA = Path.home() / 'Library/Application Support/Moa'
LABEL = 'com.moa.local'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper-only', action='store_true', help='Install the Mac helper without replacing the Safari Dock app')
    args = parser.parse_args()
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    agents = Path.home() / 'Library/LaunchAgents'
    agents.mkdir(exist_ok=True)
    plist = agents / (LABEL + '.plist')
    expected = {'Label': LABEL, 'ProgramArguments': [sys.executable, str(REPO / 'web/local/run.py')],
                'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 10,
                'WorkingDirectory': str(REPO),
                'EnvironmentVariables': {'MOA_CLOUD_ORIGIN': os.environ.get('MOA_CLOUD_ORIGIN', 'https://3.38.192.19').rstrip('/')},
                'StandardOutPath': str(DATA / 'service.log'),
                'StandardErrorPath': str(DATA / 'service.log')}
    existing = plistlib.loads(plist.read_bytes()) if plist.exists() else None
    domain = f'gui/{os.getuid()}'
    if existing != expected:
        subprocess.run(['launchctl', 'bootout', domain + '/' + LABEL], capture_output=True)
        plist.write_bytes(plistlib.dumps(expected))
    result = subprocess.run(['launchctl', 'print', domain + '/' + LABEL], capture_output=True)
    if result.returncode:
        subprocess.run(['launchctl', 'bootstrap', domain, str(plist)], check=True)
    for attempt in range(120):
        # launchd may finish unloading the previous version after bootstrap returns.
        # Re-register a missing job rather than leaving the first installation stuck.
        if attempt and attempt % 10 == 0:
            running = subprocess.run(['launchctl', 'print', domain + '/' + LABEL], capture_output=True)
            if running.returncode:
                subprocess.run(['launchctl', 'bootstrap', domain, str(plist)], capture_output=True)
        if (DATA / 'local-key').exists():
            try:
                with urlopen('http://127.0.0.1:8000/api/v1/health/', timeout=1):
                    break
            except OSError:
                pass
        time.sleep(.5)
    else:
        raise SystemExit(f'모아 실행 실패. 로그를 확인하세요: {DATA / "service.log"}')
    if args.helper_only:
        print('Mac 연결 프로그램이 준비되었습니다. AWS 모아에서 이 Mac 연결하기를 눌러 주세요.')
        return
    url = 'http://127.0.0.1:8000/#local-key=' + quote((DATA / 'local-key').read_text().strip())
    source = REPO / 'web/local/Moa.swift'
    developer_tools = subprocess.run(['xcode-select', '-p'], capture_output=True).returncode == 0
    compiler = shutil.which('swiftc') if developer_tools else None
    if compiler:
        app = Path.home() / 'Applications/모아.app'
        binary = app / 'Contents/MacOS/Moa'
        binary.parent.mkdir(parents=True, exist_ok=True)
        info = {'CFBundleExecutable': 'Moa', 'CFBundleIdentifier': 'com.moa.webapp',
                'CFBundleName': '모아', 'CFBundlePackageType': 'APPL',
                'CFBundleShortVersionString': '0.1.0', 'NSHighResolutionCapable': True, 'CFBundleIconFile': 'Moa',
                'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True}}
        (app / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
        if not binary.exists() or source.stat().st_mtime > binary.stat().st_mtime:
            subprocess.run([compiler, str(source), '-o', str(binary), '-framework', 'Cocoa', '-framework', 'WebKit'], check=True)
        resources = app / 'Contents/Resources'
        resources.mkdir(exist_ok=True)
        if not (resources / 'Moa.icns').exists():
            iconset = DATA / 'Moa.iconset'
            iconset.mkdir(exist_ok=True)
            for size in [16, 32, 128, 256, 512]:
                for scale in [1, 2]:
                    name = f'icon_{size}x{size}' + ('@2x' if scale == 2 else '') + '.png'
                    subprocess.run(['sips', '-z', str(size * scale), str(size * scale),
                                    str(REPO / 'web/local/icon.png'), '--out', str(iconset / name)], check=True, capture_output=True)
            subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o', str(resources / 'Moa.icns')], check=True)
        subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(app)], check=True, capture_output=True)
        dock = subprocess.run(['defaults', 'export', 'com.apple.dock', '-'], capture_output=True, check=True)
        entries = plistlib.loads(dock.stdout).get('persistent-apps', [])
        app_path = unicodedata.normalize('NFC', str(app))
        if not any(app_path in unicodedata.normalize('NFC', unquote(str(item))) for item in entries):
            tile = {'tile-data': {'file-data': {'_CFURLString': app.as_uri() + '/', '_CFURLStringType': 15}}, 'tile-type': 'file-tile'}
            xml = plistlib.dumps(tile).decode()
            element = xml[xml.index('<dict>'):xml.rindex('</dict>') + len('</dict>')]
            subprocess.run(['defaults', 'write', 'com.apple.dock', 'persistent-apps', '-array-add', element], check=True)
            subprocess.run(['killall', 'Dock'], capture_output=True)
        subprocess.run(['open', str(app)], check=True)
        print('모아 웹앱을 설치하고 Dock에 추가했습니다.')
    else:
        subprocess.run(['open', '-a', 'Safari', url], check=True)
    print('앱에서 iCloud Drive를 연결하면 준비가 끝납니다. Safari로 사용할 때는 파일 > Dock에 추가를 선택하세요.')
    print('Mac 로그인 시 실행기는 자동으로 시작됩니다.')


if __name__ == '__main__':
    main()
