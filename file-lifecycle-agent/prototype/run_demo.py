from pathlib import Path
import json
import argparse
from app import serve
project=Path(__file__).resolve().parent.parent
latest=project/'experiments/latest.json'
if not latest.exists():
    raise SystemExit('먼저 .venv/bin/python prototype/experiment.py 를 실행해주세요.')
parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765)
serve(json.loads(latest.read_text())['root'],parser.parse_args().port)
