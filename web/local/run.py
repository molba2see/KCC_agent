#!/usr/bin/env python3
"""One local supervisor for the web app, file agent and private bridge."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
from urllib.request import urlopen

REPO = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get('MOA_LOCAL_DATA', Path.home() / 'Library/Application Support/Moa'))


def main():
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (DATA / 'run.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    os.umask(0o077)
    key_path = DATA / 'local-key'
    if not key_path.exists():
        key_path.write_text(secrets.token_urlsafe(48))
    env = {**os.environ, 'MOA_DEBUG': '1', 'MOA_DB_PATH': str(DATA / 'db.sqlite3'),
           'MOA_LOCAL_KEY': key_path.read_text().strip(), 'MOA_LOCAL_DATA': str(DATA),
           'MOA_DJANGO_SECRET_KEY': key_path.read_text().strip(), 'PYTHONUNBUFFERED': '1'}
    manage = [sys.executable, str(REPO / 'web/backend/manage.py')]
    subprocess.run(manage + ['migrate', '--noinput'], env=env, check=True)
    credentials = DATA / 'credentials.json'
    if not credentials.exists():
        result = subprocess.run(manage + ['bootstrap_agent_owner', 'local-owner'], env=env, check=True, capture_output=True, text=True)
        credentials.write_text(result.stdout)
    token = json.loads(credentials.read_text())['bridge_token']
    children = []
    logs = []

    def start(name, args, extra=None):
        log = (DATA / (name + '.log')).open('a')
        logs.append(log)
        child = subprocess.Popen([sys.executable, *map(str, args)], env={**env, **(extra or {})}, stdout=log, stderr=log)
        children.append(child)
        return child

    def stop(*_):
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
        for log in logs:
            log.close()

    def signal_stop(*_):
        stop()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, signal_stop)
    signal.signal(signal.SIGINT, signal_stop)
    try:
        start('web', [REPO / 'web/backend/manage.py', 'runserver', '127.0.0.1:8000', '--noreload'])
        for _ in range(60):
            if children[0].poll() is not None:
                raise RuntimeError('Web server failed; inspect web.log (port 8000 may be occupied)')
            try:
                with urlopen('http://127.0.0.1:8000/api/v1/health/', timeout=1):
                    break
            except OSError:
                time.sleep(.5)
        else:
            raise RuntimeError('Web server did not become ready')
        agent = bridge = cloud_bridge = None
        agent_inbox = None
        cloud_version = None
        while True:
            if children[0].poll() is not None:
                raise RuntimeError('Web server stopped')
            config = DATA / 'icloud.json'
            if config.exists():
                inbox = json.loads(config.read_text())['inbox']
                if agent is not None and agent.poll() is None and agent_inbox != inbox:
                    agent.terminate()
                    agent.wait(timeout=10)
                if agent is None or agent.poll() is not None:
                    agent = start('agent', [REPO / 'file-lifecycle-agent/prototype/demo_v5.py',
                        '--root', DATA / 'workspace', '--projects', DATA / 'projects.json',
                        '--watch', '--scan-existing-inbox', '--auto-inbox', inbox, '--port', '8791'])
                    agent_inbox = inbox
                if bridge is None or bridge.poll() is not None:
                    bridge = start('bridge', [REPO / 'web/bridge/mac_bridge.py',
                        '--server', 'http://127.0.0.1:8000', '--allow-insecure-localhost',
                        '--state-file', DATA / 'bridge-result.json'], {'MOA_AGENT_TOKEN': token})
                cloud_file = DATA / 'cloud.json'
                if cloud_file.exists():
                    cloud = json.loads(cloud_file.read_text())
                    version = cloud_file.stat().st_mtime_ns
                    if cloud_bridge and version != cloud_version and cloud_bridge.poll() is None:
                        cloud_bridge.terminate()
                        cloud_bridge.wait(timeout=10)
                    if cloud_bridge is None or cloud_bridge.poll() is not None:
                        cloud_bridge = start('cloud-bridge', [REPO / 'web/bridge/mac_bridge.py',
                            '--server', cloud['origin'], '--state-file', DATA / ('cloud-bridge-result-' + hashlib.sha256(cloud['bridge_token'].encode()).hexdigest()[:16] + '.json')],
                            {'MOA_AGENT_TOKEN': cloud['bridge_token']})
                        cloud_version = version
                elif cloud_bridge is not None:
                    if cloud_bridge.poll() is None:
                        cloud_bridge.terminate()
                        cloud_bridge.wait(timeout=10)
                    cloud_bridge = None
                    cloud_version = None
            time.sleep(3)
    finally:
        stop()


if __name__ == '__main__':
    main()
