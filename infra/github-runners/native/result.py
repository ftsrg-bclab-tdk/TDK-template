#!/usr/bin/env python3
"""Record systemd's termination cause outside the offline sandbox."""
import json
import os
from pathlib import Path
import re
import sys

name = sys.argv[1]
if os.geteuid() != 0 or not re.fullmatch(r'tdk-sandbox-[a-f0-9]{32}', name):
    raise RuntimeError('invalid result context')
path = Path('/run/tdk-native-results') / (name + '.json')
with path.open('x') as output:
    os.chmod(path, 0o600)
    json.dump({key: os.environ.get(key) for key in ['SERVICE_RESULT','EXIT_CODE','EXIT_STATUS']},output)
