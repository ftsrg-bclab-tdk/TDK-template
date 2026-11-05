#!/usr/bin/env python3
"""systemd calls this outside the job sandbox; workload stdout is not the receipt."""
import json
import os
from pathlib import Path
import re
import sys
import time

identifier = sys.argv[1]
if os.geteuid() != 0 or not re.fullmatch(r'[a-f0-9]{32}', identifier):
    raise RuntimeError('invalid finish context')
root = Path('/var/lib/tdk-isolation')
receipt = {'id': identifier, 'finished_at': time.time(),
           'result': os.environ.get('SERVICE_RESULT'),
           'exit_code': os.environ.get('EXIT_CODE'),
           'exit_status': os.environ.get('EXIT_STATUS')}
path = root / 'receipts' / (identifier + '.json')
with open(path, 'x') as output:
    os.chmod(path, 0o600)
    json.dump(receipt, output)
