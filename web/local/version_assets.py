#!/usr/bin/env python3
"""Version the HTML's local CSS/JS URLs by content to prevent mixed cached releases."""
import hashlib
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DIST = Path(__file__).resolve().parents[1] / 'dist'


def main():
    index = DIST / 'index.html'
    source = index.read_text(encoding='utf-8')

    def version(match):
        prefix, address = match.groups()
        parsed = urlsplit(address)
        if parsed.scheme or parsed.netloc or not parsed.path.endswith(('.js', '.css')):
            return match.group(0)
        asset = (DIST / parsed.path.lstrip('/')).resolve()
        if not asset.is_relative_to(DIST.resolve()) or not asset.is_file():
            raise ValueError(f'Missing or invalid static asset: {parsed.path}')
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()[:12]
        query = [(key, value) for key, value in parse_qsl(parsed.query) if key != 'v']
        query.append(('v', digest))
        address = urlunsplit(parsed._replace(query=urlencode(query)))
        return prefix + address + '"'

    updated = re.sub(r'(<(?:script|link)\b[^>]*?\b(?:src|href)=")([^"]+)"', version, source)
    if updated != source:
        index.write_text(updated, encoding='utf-8')
    print('Static asset versions are current.')


if __name__ == '__main__':
    main()
