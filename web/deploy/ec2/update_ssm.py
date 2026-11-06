#!/usr/bin/env python3
"""Deploy the static site and Django API through SSM without an inbound SSH port."""

from concurrent.futures import ThreadPoolExecutor
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time


ROOT = Path(__file__).resolve().parents[2]
INSTANCE = os.environ.get("MOA_EC2_INSTANCE")
REGION = os.environ.get("MOA_AWS_REGION", "ap-northeast-2")
PROFILE = os.environ.get("MOA_AWS_PROFILE")
PUBLIC_HOST = os.environ.get("MOA_PUBLIC_HOST")
AWS = os.environ.get("MOA_AWS_CLI", "aws")


def aws(*args):
    env = os.environ.copy()
    if env.get("MOA_AWS_TIME_PRELOAD"):
        env["LD_PRELOAD"] = env["MOA_AWS_TIME_PRELOAD"]
    command = [AWS, *args, *(["--profile", PROFILE] if PROFILE else []), "--region", REGION, "--output", "json"]
    result = subprocess.run(command, check=True, capture_output=True, text=True, env=env)
    return json.loads(result.stdout)


def bundle():
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as archive:
        for directory in (ROOT / "dist", ROOT / "backend"):
            for file in sorted(directory.rglob("*")):
                if not file.is_file() or any(part in {".venv", "__pycache__", "staticfiles"} for part in file.parts):
                    continue
                if file.name == "db.sqlite3" or file.suffix == ".pyc":
                    continue
                archive.add(file, arcname=str(file.relative_to(ROOT)))
    return data.getvalue()


def send(commands, comment):
    result = aws(
        "ssm", "send-command", "--instance-ids", INSTANCE,
        "--document-name", "AWS-RunShellScript",
        "--comment", comment,
        "--parameters", json.dumps({"commands": commands}),
    )
    command_id = result["Command"]["CommandId"]
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            result = aws("ssm", "get-command-invocation", "--command-id", command_id, "--instance-id", INSTANCE)
        except subprocess.CalledProcessError:
            time.sleep(2)
            continue
        if result["Status"] in {"Success", "Failed", "Cancelled", "TimedOut"}:
            if result["Status"] != "Success":
                print(result.get("StandardErrorContent", "")[-2000:], file=sys.stderr)
                print(result.get("StandardOutputContent", "")[-2000:], file=sys.stderr)
                raise RuntimeError(f"SSM command {command_id} ended with {result['Status']}")
            return result.get("StandardOutputContent", "")
        time.sleep(3)
    raise TimeoutError(f"SSM command {command_id} did not complete")


def main():
    if not INSTANCE or not PUBLIC_HOST:
        raise SystemExit("Set MOA_EC2_INSTANCE and MOA_PUBLIC_HOST before deployment")
    subprocess.run([sys.executable, str(ROOT / 'local/version_assets.py')], check=True)
    # Generate the downloadable helper from this exact source state.
    subprocess.run([sys.executable, str(ROOT / "local/build_helper.py"), "--origin", "https://" + PUBLIC_HOST], check=True)
    archive = bundle()
    version = hashlib.sha256(archive).hexdigest()[:12]
    encoded = base64.b64encode(archive).decode("ascii")
    parts = [encoded[i:i + 8000] for i in range(0, len(encoded), 8000)]
    print(f"Bundle {len(archive)} bytes, {len(parts)} SSM parts, release {version}", flush=True)
    upload_dir = f"/tmp/moa-upload/{version}"
    send([f"mkdir -p {upload_dir}"], "Prepare Moa upload")
    groups = [list(enumerate(parts))[i:i + 3] for i in range(0, len(parts), 3)]
    def upload(group):
        send([f"printf '%s' '{part}' > {upload_dir}/{index:03d}.b64" for index, part in group],
             f"Upload Moa parts {group[0][0] + 1}-{group[-1][0] + 1}/{len(parts)}")
        return len(group)
    uploaded = 0
    with ThreadPoolExecutor(max_workers=3) as workers:
        for count in workers.map(upload, groups):
            uploaded += count
            print(f"Uploaded {uploaded}/{len(parts)}", flush=True)
    script = f"""set -euo pipefail
release=/opt/moa/releases/{version}
mkdir -p "$release" /var/lib/moa
cat {upload_dir}/*.b64 | base64 -d | tar -xz -C "$release"
dnf install -y python3.11 python3.11-pip >/tmp/moa-dnf.log 2>&1
python3.11 -m venv /opt/moa/venv
/opt/moa/venv/bin/pip install --disable-pip-version-check -q -r "$release/backend/requirements.txt"
id moa >/dev/null 2>&1 || useradd --system --shell /sbin/nologin --home-dir /var/lib/moa moa
chown -R moa:moa /var/lib/moa
if [ ! -f /etc/moa.env ]; then
  python3.11 -c 'import secrets; print("MOA_DJANGO_SECRET_KEY=" + secrets.token_urlsafe(64))' > /etc/moa.env
  chmod 600 /etc/moa.env
fi
allowed_hosts=$(sed -n 's/^MOA_ALLOWED_HOSTS=//p' /etc/moa.env | tail -n 1)
sed -i '/^MOA_ALLOWED_HOSTS=/d; /^MOA_DB_PATH=/d; /^MOA_HTTPS=/d' /etc/moa.env
printf '%s\\n' "MOA_ALLOWED_HOSTS={PUBLIC_HOST},127.0.0.1,localhost,$allowed_hosts" 'MOA_DB_PATH=/var/lib/moa/db.sqlite3' 'MOA_HTTPS=1' >> /etc/moa.env
ln -sfnT "$release" /opt/moa/current
set -a
. /etc/moa.env
set +a
cd /opt/moa/current/backend
runuser -u moa -- /opt/moa/venv/bin/python manage.py migrate --noinput >/tmp/moa-migrate.log
cat > /etc/systemd/system/moa-api.service <<'UNIT'
[Unit]
Description=Moa Django API
After=network.target
[Service]
User=moa
Group=moa
WorkingDirectory=/opt/moa/current/backend
EnvironmentFile=/etc/moa.env
ExecStart=/opt/moa/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 moa_api.wsgi:application
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
touch /etc/nginx/moa-ssl.conf
cat > /etc/nginx/nginx.conf <<'NGINX'
user nginx;
worker_processes auto;
pid /run/nginx.pid;
events {{ worker_connections 1024; }}
http {{
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    sendfile on;
    server {{
        listen 80 default_server;
        server_name _;
        root /opt/moa/current/dist;
        index index.html;
        location /api/ {{ proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; }}
        location /swagger/ {{ proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; }}
        location / {{ try_files $uri $uri/ /index.html; }}
        add_header X-Content-Type-Options nosniff always;
    }}
    include /etc/nginx/moa-ssl.conf;
}}
NGINX
nginx -t
systemctl daemon-reload
systemctl enable --now moa-api
systemctl restart moa-api
systemctl reload nginx
for attempt in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8000/api/v1/health/; then break; fi
  sleep 1
done
curl -fsS http://127.0.0.1:8000/api/v1/health/ >/dev/null
"""
    result = send([script], f"Deploy Moa release {version}")
    print(result[-1000:], flush=True)


if __name__ == "__main__":
    main()
