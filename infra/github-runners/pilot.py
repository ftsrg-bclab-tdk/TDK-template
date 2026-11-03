#!/usr/bin/env python3
"""Prepare a repository-scoped JIT credential on the trusted operator machine."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid


def request(repo, group, name):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("repository must be OWNER/REPO")
    if group <= 0:
        raise ValueError("runner group ID must be a verified positive integer")
    if not re.fullmatch(r"bme-pilot-[a-f0-9]{32}", name):
        raise ValueError("runner name must be bme-pilot- plus a random UUID hex")
    return {"name": name, "runner_group_id": group,
            "labels": ["self-hosted", "Linux", "X64", name], "work_folder": "_work"}


def create(repo, payload, output):
    # Reserve the output BEFORE registration; never overwrite or follow a symlink.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as dest:
        result = subprocess.run(
            ["gh", "api", "--hostname", "github.com", "--method", "POST",
             f"repos/{repo}/actions/runners/generate-jitconfig",
             "--input", "-"], input=json.dumps(payload), text=True,
            capture_output=True, check=False, timeout=60)
        if result.returncode:
            # Never echo API response bodies: success/failure output can contain credentials.
            raise RuntimeError("JIT registration failed; inspect permissions on the operator host")
        data = json.loads(result.stdout)
        credential = data["encoded_jit_config"]
        runner_id = data["runner"]["id"]
        if not isinstance(credential, str) or not re.fullmatch(r"[A-Za-z0-9+/=]+", credential):
            raise ValueError("invalid JIT response")
        if type(runner_id) is not int or runner_id <= 0:
            raise ValueError("invalid runner ID")
        dest.write(credential + "\n")
    return runner_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="empty, dedicated pilot repository")
    parser.add_argument("--runner-group-id", required=True, type=int)
    parser.add_argument("--name", default="bme-pilot-" + uuid.uuid4().hex)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--isolated-disposable-pilot", action="store_true",
                        help="operator confirms the runbook prerequisites")
    args = parser.parse_args()
    try:
        payload = request(args.repo, args.runner_group_id, args.name)
        if not args.apply:
            print(json.dumps({"repository": args.repo, "request": payload}, indent=2))
            return 0
        if not args.isolated_disposable_pilot or args.output is None:
            raise ValueError("--apply requires --isolated-disposable-pilot and --output")
        print(json.dumps({"registering": args.name, "repository": args.repo}), file=sys.stderr)
        runner_id = create(args.repo, payload, args.output)
        print(json.dumps({"runner_id": runner_id, "label": args.name,
                          "credential_file": str(args.output)}))
        return 0
    except (ValueError, KeyError, OSError, RuntimeError, subprocess.SubprocessError):
        print("Pilot registration failed. No response body printed. If registration may have "
              "succeeded, check the repository runner list and remove the unused pilot runner; "
              "securely remove any output file before retrying.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
