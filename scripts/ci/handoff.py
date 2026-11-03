#!/usr/bin/env python3
"""Fetch one exact Actions artifact and inspect data without executing producer code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci.config import inside, load_project, read_json
from external_inputs.external_inputs import GitHub, Unavailable

MAX_BYTES = 512 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def extract(archive, output):
    require(not output.exists(), "Artifact destination must be fresh")
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        require(0 < len(entries) <= 2048, "Artifact member limit")
        require(sum(e.file_size for e in entries) <= MAX_BYTES, "Expanded artifact limit")
        seen = set()
        for entry in entries:
            require(not entry.is_dir(), "Explicit ZIP directories are not accepted")
            inside(output, entry.filename)
            key = entry.filename.casefold()
            require(key not in seen, "Duplicate artifact member")
            seen.add(key)
            mode = entry.external_attr >> 16
            require(stat.S_IFMT(mode) in (0, stat.S_IFREG) and not entry.flag_bits & 1, "Nonregular/encrypted artifact member")
        for name in seen:
            require(not any(parent in seen for parent in (str(p) for p in Path(name).parents) if parent != "."), "Artifact file/directory collision")
        output.mkdir(parents=True)
        for entry in entries:
            target = inside(output, entry.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(entry) as source, target.open("xb") as destination:
                while data := source.read(65536):
                    destination.write(data)


def fetch(*, repository, repository_id, run_id, attempt, source_sha, workflow_path,
          artifact_name, output, allowed_events=("push",), artifact_id=None,
          expected_artifact_sha256=None, client=None):
    require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)), "Invalid repository")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", source_sha)), "Invalid source SHA")
    for number in (repository_id, run_id, attempt):
        require(type(number) is int and number > 0, "Invalid numeric identity")
    client = client or GitHub()
    prefix = "repos/" + repository
    repo = client.metadata(prefix)
    require(repo.get("id") == repository_id, "Repository ID mismatch")
    run = client.metadata(f"{prefix}/actions/runs/{run_id}/attempts/{attempt}")
    require(run.get("id") == run_id and run.get("run_attempt") == attempt, "Run/attempt mismatch")
    require(run.get("repository", {}).get("id") == repository_id and run.get("head_repository", {}).get("id") == repository_id, "Producer repository mismatch")
    require(run.get("head_sha") == source_sha and run.get("path", "").split("@")[0] == workflow_path, "Producer SHA/workflow mismatch")
    require(run.get("event") in allowed_events and run.get("status") == "completed", "Ineligible producer event/state")
    candidates = []
    for page in range(1, 21):
        listing = client.metadata(f"{prefix}/actions/runs/{run_id}/artifacts?per_page=100&page={page}")
        artifacts = listing.get("artifacts")
        require(isinstance(artifacts, list), "Invalid artifact listing")
        candidates.extend(a for a in artifacts if a.get("name") == artifact_name)
        if len(artifacts) < 100:
            break
    require(len(candidates) == 1, "Exact attempt artifact missing or ambiguous")
    artifact = candidates[0]
    require(artifact.get("expired") is False, "Artifact expired")
    require(artifact_id is None or artifact.get("id") == artifact_id, "Artifact ID mismatch")
    require(artifact.get("workflow_run", {}).get("id") == run_id and artifact.get("workflow_run", {}).get("head_sha") == source_sha, "Artifact producer mismatch")
    size = artifact.get("size_in_bytes")
    require(type(size) is int and 0 < size <= MAX_BYTES, "Artifact size limit")
    reported_digest = artifact.get("digest", "")
    require(bool(re.fullmatch(r"sha256:[0-9a-f]{64}", reported_digest)), "Missing API artifact digest")
    digest = reported_digest.split(":", 1)[1]
    require(expected_artifact_sha256 is None or digest == expected_artifact_sha256, "Expected artifact digest mismatch")
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / "artifact.zip"
        client.download(f"{prefix}/actions/artifacts/{artifact['id']}/zip", archive, MAX_BYTES)
        require(sha_file(archive) == digest, "Downloaded artifact digest mismatch")
        extract(archive, Path(output))
    return {"schema": "ci-artifact/v1", "repository": repository, "repository_id": repository_id,
            "source_sha": source_sha, "workflow_path": workflow_path, "run_id": run_id, "run_attempt": attempt,
            "artifact_id": artifact["id"], "artifact_name": artifact_name, "artifact_sha256": digest,
            "producer_conclusion": run.get("conclusion")}


def paper_status(report, directory, kind, *, source_sha, config_sha256, run_id, attempt):
    require(report.get("schema") == "project-checks/v1", "Invalid check report")
    require(report.get("source", {}).get("tested_sha") == source_sha and report["source"].get("source_sha") == source_sha and report["source"].get("dirty") is False, "Report SHA/clean state mismatch")
    require(report.get("configuration", {}).get("project_config_sha256") == config_sha256, "Report config mismatch")
    execution = report.get("execution", {})
    require(str(execution.get("run_id")) == str(run_id) and str(execution.get("run_attempt")) == str(attempt), "Report run/attempt mismatch")
    files = report.get("files")
    require(isinstance(files, list) and files, "Missing report inventory")
    for member in files:
        path = inside(directory, member["path"])
        require(path.is_file() and path.stat().st_size == member["bytes"] and sha_file(path) == member["sha256"], "Evidence file mismatch")
    component = report.get("components", {}).get("paper", {})
    require(report.get("plan", {}).get("components", {}).get("paper", {}).get("selected") is True, "Paper was not selected")
    checks = component.get("checks", [])
    names = ("draft", "final") if kind == "build" else ("lint",)
    for name in names:
        matches = [c for c in checks if c.get("name") == name]
        require(len(matches) == 1, "Missing/ambiguous paper result: " + name)
        step = matches[0]
        require(step.get("execution_status") == "completed" and step.get("gate_outcome") == "pass", "Paper check did not pass: " + name)
        require(step.get("raw_exit") in ((0,) if kind == "build" else (0, 1)), "Unexpected paper exit")
        if kind == "build":
            require(step.get("kind") == "build" and bool(step.get("files")), "No built output evidence")
        else:
            require(step.get("kind") == "writing", "Not a lint result")
    return {"outcome": "pass", "scope": "paper build" if kind == "build" else "lint execution; writing findings advisory", "source_sha": source_sha}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("build", "lint"))
    parser.add_argument("--event", type=Path, default=Path(os.environ.get("GITHUB_EVENT_PATH", "event.json")))
    parser.add_argument("--output", type=Path, default=Path(".project/handoff"))
    args = parser.parse_args()
    try:
        event, _ = read_json(args.event)
        run, repo = event["workflow_run"], event["repository"]
        require(run["event"] == "push" and run["head_branch"] == repo["default_branch"], "Badge requires a default-branch push")
        config, config_hash = load_project(Path.cwd())
        client = GitHub()
        current = client.metadata("repos/" + repo["full_name"] + "/commits/" + repo["default_branch"])
        require(current["sha"] == run["head_sha"], "Producer is stale relative to default branch")
        require(config["repository"].lower() == repo["full_name"].lower(), "Badge repository differs from project config")
        receipt = fetch(repository=repo["full_name"], repository_id=repo["id"], run_id=run["id"], attempt=run["run_attempt"],
                        source_sha=run["head_sha"], workflow_path=".github/workflows/ci.yml",
                        artifact_name=f"checks-{run['head_sha']}-{run['id']}-{run['run_attempt']}", output=args.output, client=client)
        report, raw = read_json(args.output / "report.json")
        status = paper_status(report, args.output, args.kind, source_sha=run["head_sha"], config_sha256=config_hash, run_id=run["id"], attempt=run["run_attempt"])
        receipt["report_sha256"] = hashlib.sha256(raw).hexdigest()
        print(json.dumps({"status": status, "transport": receipt}, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, Unavailable, zipfile.BadZipFile) as exc:
        print(json.dumps({"outcome": "fail", "reason": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
