"""Local account interaction and durable storage; no service mutations."""

import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone

from . import accounts


def load(path, catalog):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("state_symlink_not_allowed")
    if not path.exists():
        return accounts.prepare(catalog)["accounts"]
    if not path.is_file() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise ValueError("state_permissions_not_private")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) != {"schema", "accounts"} or document["schema"] != 1:
        raise ValueError("invalid_state_envelope")
    return accounts.prepare(catalog, document["accounts"])["accounts"]


def save(path, catalog, state):
    """Atomic replacement; failure is propagated, never reported as saved.

    Caller chooses an untracked private path and serializes writers. This module
    does not merge simultaneous onboarding sessions or retain raw answers.
    """
    path = Path(path)
    if path.is_symlink():
        raise ValueError("state_symlink_not_allowed")
    clean = accounts.prepare(catalog, state)["accounts"]
    payload = json.dumps({"schema": 1, "accounts": clean}, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".onboarding-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def collect(path, catalog, ask, emit, *, dry_run=False):
    """ask(prompt) returns an answer; EOF/interrupt retains previous saved state.

    emit receives structured events without identifier values. Dry run never asks
    for answers or saves: it exposes the remaining structured prompt descriptors.
    """
    state = load(path, catalog)
    if dry_run:
        return {"saved": False, "prompts": accounts.prompts(catalog, state)}
    while True:
        remaining = accounts.prompts(catalog, state)
        if not remaining:
            return accounts.status(catalog, state)
        prompt = remaining[0]
        try:
            answer = ask(prompt)
        except (EOFError, KeyboardInterrupt):
            return {"interrupted": True, "status": accounts.status(catalog, state)}
        result = accounts.apply_answer(catalog, state, prompt["service"],
                                       prompt["field"], answer,
                                       checked_at=datetime.now(timezone.utc).isoformat())
        if not result["accepted"]:
            emit({"event": "invalid_answer", "diagnostics": result["diagnostics"]})
            continue
        save(path, catalog, result["accounts"])
        state = result["accounts"]
        emit({"event": "saved", "service": prompt["service"], "field": prompt["field"]})
        if prompt["field"] == "account_attested" and answer is False:
            return {"interrupted": False, "status": accounts.status(catalog, state)}
