"""Verify an observer-signed native pilot bundle; never infer observation from hashes.

Trust policy is an application input, not a field in the bundle. No CLI or default
signer is provided. See README.md for the limited claim this boundary represents.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from pathlib import Path
import subprocess
import tempfile

from ci.config import inside, keys, read_json
from ci.evidence import timestamp, verify_report

NAMESPACE = "tdk-overleaf-native-pilot-v1"
_TOKEN = object()


@dataclass(frozen=True, init=False)
class VerifiedBoundary:
    repository: str
    tested_sha: str
    config_digest: str
    completed_at: str
    receipt_sha256: str
    report_sha256: str
    observer: str

    def __init__(self, *, _token=None, **fields):
        if _token is not _TOKEN:
            raise ValueError("Use verify_boundary with independently configured observer trust")
        for name in self.__dataclass_fields__:
            object.__setattr__(self, name, fields[name])


def _digest(value, length=64):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{%d}" % length, value):
        raise ValueError("Invalid digest")
    return value


def _artifact(root, member):
    keys(member, {"path", "sha256"})
    path = inside(root, member["path"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != _digest(member["sha256"]):
        raise ValueError("Missing or modified pilot evidence")
    return path


def verify_boundary(receipt_path, signature_path, *, allowed_signers, principal,
                    repository, tested_sha, config_digest, required_components):
    """Authenticate exact receipt bytes with SSHSIG, then check bound artifacts.

    allowed_signers/principal must come from an operator-controlled trust policy,
    outside the student checkout and bundle. This does not provision that policy.
    A signature proves who asserted observations, not that the assertions are true.
    """
    if not principal or not isinstance(principal, str):
        raise ValueError("Explicit trusted observer principal required")
    receipt_path = Path(receipt_path)
    receipt, raw = read_json(receipt_path)
    # Snapshot trust and signature bytes to avoid file replacement between checks.
    with tempfile.TemporaryDirectory(prefix="native-pilot-verify-") as tmp:
        trust, signature = Path(tmp)/"allowed", Path(tmp)/"signature"
        trust.write_bytes(Path(allowed_signers).read_bytes())
        signature.write_bytes(Path(signature_path).read_bytes())
        result = subprocess.run([
            "ssh-keygen", "-Y", "verify", "-f", str(trust), "-I", principal,
            "-n", NAMESPACE, "-s", str(signature)], input=raw, capture_output=True, timeout=15)
        if result.returncode:
            raise ValueError("Pilot signature is not from the configured observer")
    keys(receipt, {"schema", "method", "actor", "repository", "overleaf_project_id",
                   "source_sha", "tested_sha", "config_digest", "completed_at",
                   "pull", "push", "clone", "compilation", "tree_audit", "report"})
    if receipt["schema"] != "overleaf-native-pilot/v1" or receipt["method"] != "observed_native_ui":
        raise ValueError("Manual attestations cannot establish an observed boundary")
    if receipt["actor"] != principal:
        raise ValueError("Observer identity mismatch")
    if (receipt["repository"] != repository or receipt["tested_sha"] != tested_sha
            or receipt["config_digest"] != config_digest):
        raise ValueError("Pilot repository/source/config mismatch")
    _digest(tested_sha, 40)
    _digest(receipt["source_sha"], 40)
    _digest(config_digest)
    if receipt["source_sha"] == tested_sha:
        raise ValueError("Native push must produce a distinct tested commit")
    if not re.fullmatch(r"[0-9a-f]{24}", receipt["overleaf_project_id"]):
        raise ValueError("Invalid Overleaf project ID")
    root = receipt_path.parent
    previous = None
    for name, sha in (("pull", receipt["source_sha"]), ("push", tested_sha), ("clone", tested_sha)):
        event = receipt[name]
        keys(event, {"commit", "completed_at", "evidence"})
        at = timestamp(event["completed_at"])
        if event["commit"] != sha or (previous and at < previous) or at > datetime.now(timezone.utc):
            raise ValueError("Native event identity/order mismatch")
        previous = at
        _artifact(root, event["evidence"])
    if receipt["completed_at"] != receipt["clone"]["completed_at"]:
        raise ValueError("Boundary must be the post-push fresh clone completion")
    keys(receipt["compilation"], {"paper-draft.tex", "paper-final.tex"})
    for artifact in receipt["compilation"].values():
        _artifact(root, artifact)
    audit_path = _artifact(root, receipt["tree_audit"])
    audit, _ = read_json(audit_path)
    keys(audit, {"before_commit", "after_commit", "inventory", "changes", "unexpected_changes", "before_inventory"})
    if (audit["before_commit"] != receipt["source_sha"] or audit["after_commit"] != tested_sha
            or audit["unexpected_changes"] != []):
        raise ValueError("Unresolved tree transformations or wrong audit commits")
    if not isinstance(audit["changes"], list):
        raise ValueError("Missing full blob/mode changes")
    for inventory in (audit["before_inventory"], audit["inventory"]):
        keys(inventory, {"tracked_files", "payload_bytes", "text_bytes", "largest_text_bytes",
                         "executables", "symlinks", "gitlinks", "lfs_pointers"})
        for field in ("tracked_files", "payload_bytes", "text_bytes", "largest_text_bytes"):
            if type(inventory[field]) is not int or inventory[field] < 0:
                raise ValueError("Invalid tracked-tree budget")
        if (not 0 < inventory["tracked_files"] <= 2000 or inventory["text_bytes"] > 7_000_000
                or inventory["largest_text_bytes"] > 2_000_000):
            raise ValueError("Tracked tree exceeds pilot budget")
        if any(inventory[field] != [] for field in ("symlinks", "gitlinks", "lfs_pointers")):
            raise ValueError("Unsupported tracked objects")
        if not isinstance(inventory["executables"], list):
            raise ValueError("Missing executable inventory")
    report_path = _artifact(root, receipt["report"])
    verify_report(report_path, repository=repository, tested_sha=tested_sha,
                  config_sha256=config_digest, required_components=required_components,
                  expected_report_sha256=receipt["report"]["sha256"],
                  after=receipt["completed_at"], require_clean=True, require_runtime=True)
    return VerifiedBoundary(_token=_TOKEN, repository=repository, tested_sha=tested_sha,
                            config_digest=config_digest, completed_at=receipt["completed_at"],
                            receipt_sha256=hashlib.sha256(raw).hexdigest(),
                            report_sha256=receipt["report"]["sha256"], observer=principal)
