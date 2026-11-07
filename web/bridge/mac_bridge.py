#!/usr/bin/env python3
"""Poll the Moa server from the Mac; execute queued commands in the local agent."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ACTIONS = {"preferences", "expiry_schedule", "expiry_confirm", "expiry_cancel", "expiry_change", "cleanup_scan", "preview", "answer", "approve", "keep", "undo", "restore_trashed", "cleanup_confirm", "cleanup_dismiss", "cleanup_retry"}


def post(url, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(url, data=json.dumps(body, ensure_ascii=False).encode(), headers=headers, method="POST")
    with urlopen(request, timeout=25) as response:
        return json.load(response)


def get(url):
    with urlopen(url, timeout=8) as response:
        return json.load(response)


def write_pending(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False))
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def public_state(raw):
    """Send only the fields needed by the web UI and command validator."""
    assets = sorted(raw.get("assets", []), key=lambda asset: asset.get("received_at") or 0, reverse=True)
    result = {
        "agent_available": True,
        "capabilities": [name for name in ('preview', 'cleanup_scan', 'preferences', 'expiry') if name in raw.get('capabilities', [])],
        "preferences": {key: raw['preferences'].get(key) for key in ('download_mode', 'screenshot_mode', 'icloud_mode', 'installers_enabled', 'installer_days', 'volatile_mode', 'volatile_days', 'revision', 'updated_at')} if isinstance(raw.get('preferences'), dict) else None,
        "expiry": public_expiry(raw.get('expiry')),
        "assets": [{"id": a.get("id"), "name": Path(a.get("original") or a.get("path") or "").name,
                    "source_kind": a.get("source_kind"), "source_mtime": a.get("source_mtime"), "project": a.get("project"), "archived": bool(a.get("archived")), "keep": bool(a.get("keep")), "trashed": bool(a.get('trashed')),
                    "plan": a.get("plan"),
                    "why": [str(x)[:500] for x in (a.get("why") or [])[:4]],
                    "run": {k: (a.get("run") or {}).get(k) for k in ("status", "question", "candidates")}}
                   for a in assets[:500]],
        "catalog": [{k: p.get(k) for k in ("id", "name", "desc", "status")}
                    for p in raw.get("catalog", [])],
        "trashed": [{"i": t.get("i"), "name": Path(t.get("path") or t.get("trash") or "").name}
                    for t in raw.get("trashed", [])],
        "cleanup": public_cleanup(raw.get("cleanup")),
        "counts": {"files": len(assets), "moved": sum(bool(asset.get('archived')) for asset in assets),
                   "pending": sum(not asset.get('archived') and not asset.get('keep') and not asset.get('trashed') for asset in assets),
                   "folders": {str(project.get('id')): sum(asset.get('project') == project.get('id') for asset in assets) for project in raw.get('catalog', [])}},
        "pending": raw.get("pending", 0),
    }
    # A first scan may contain thousands of files. Keep the relay below nginx's body limit.
    while result['assets'] and len(json.dumps(result, ensure_ascii=False).encode()) > 750_000:
        del result['assets'][-25:]
    result['assets_truncated'] = len(result['assets']) < len(assets)
    return result



def public_expiry(value):
    if not isinstance(value, dict): return None
    return {'total': value.get('total', 0), 'entries': [
        {**{key: entry.get(key) for key in ('id', 'asset_id', 'kind', 'status', 'due_at', 'first_seen', 'error')}, 'name': Path(str(entry.get('name') or '')).name}
        for entry in value.get('entries', [])[:100] if isinstance(entry, dict)]}


def public_cleanup(value):
    if not isinstance(value, dict): return None
    result = {key: value.get(key) for key in ('status', 'detail', 'total', 'processed', 'classified', 'remaining', 'model_processed', 'pending_groups', 'deferred_count')}
    result['groups'] = [{**{key: group.get(key) for key in ('id', 'name', 'purpose', 'status', 'new_folder', 'destination', 'destination_path', 'project_id')},
                         'files': [{'id': file.get('id'), **{key: file.get(key) for key in ('source', 'destination') if key in file},
                                    'name': Path(str(file.get('name') or '')).name,
                                    **{key: Path(str(file.get(key) or '')).name for key in ('source_name', 'target_name') if key in file}} for file in group.get('files', [])]}
                        for group in value.get('groups', []) if isinstance(group, dict)]
    return result

def server_allowed(server, allow_insecure_localhost=False):
    parsed = urlsplit(server)
    if parsed.scheme == "https":
        return True
    return (
        allow_insecure_localhost
        and parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost"}
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )


def run(server, local, token, interval, state_file, allow_insecure_localhost=False):
    if not server_allowed(server, allow_insecure_localhost):
        raise SystemExit("Server URL must use HTTPS (or explicit local HTTP mode)")
    if not local.startswith("http://127.0.0.1:"):
        raise SystemExit("Local agent URL must use 127.0.0.1")
    server, local = server.rstrip("/"), local.rstrip("/")
    print("Moa bridge started; local files remain on this Mac", flush=True)
    last_snapshot = None
    while True:
        try:
            if state_file.exists():
                result = json.loads(state_file.read_text())
                post(server + "/api/v1/agent/bridge/result/", result, token)
                state_file.unlink()
            try:
                snapshot = public_state(get(local + "/api/state")); last_snapshot = snapshot
            except (HTTPError, URLError, ValueError, OSError):
                snapshot = {**(last_snapshot or {'assets': [], 'catalog': []}), 'agent_available': False}
            reply = post(server + "/api/v1/agent/bridge/poll/", {"snapshot": snapshot}, token)
            command = reply.get("command")
            if command:
                action = command.get("action")
                if action not in ACTIONS:
                    result = {"ok": False, "error": "Unsupported action"}
                else:
                    try:
                        result = post(local + "/api/" + action, command.get("payload") or {})
                    except (HTTPError, URLError, ValueError) as exc:
                        result = {"ok": False, "error": str(exc)}
                report = {"id": command["id"], "ok": result.get("ok") is True,
                          "result": result.get("result") if result.get("ok") is True else result.get("error", "Agent error")}
                write_pending(state_file, report)
                post(server + "/api/v1/agent/bridge/result/", report, token)
                state_file.unlink()
                print(f"Command {command['id']} {action}: {'done' if report['ok'] else 'failed'}", flush=True)
        except (HTTPError, URLError, ValueError, OSError) as exc:
            print(f"Bridge waiting: {exc}", file=sys.stderr, flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True, help="Moa HTTPS site origin")
    parser.add_argument("--local", default="http://127.0.0.1:8791", help="Mac agent origin")
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--state-file", type=Path, default=Path.home() / ".moa" / "bridge-result.json")
    parser.add_argument("--allow-insecure-localhost", action="store_true", help="Allow HTTP only to localhost for local development")
    args = parser.parse_args()
    token = os.environ.get("MOA_AGENT_TOKEN")
    if not token:
        raise SystemExit("Set MOA_AGENT_TOKEN in the Mac environment")
    run(args.server, args.local, token, args.interval, args.state_file, args.allow_insecure_localhost)
