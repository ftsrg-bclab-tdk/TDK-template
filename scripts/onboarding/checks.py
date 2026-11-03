"""Onboarding consumes the shared CI verifier; no parallel CI validation schema."""
import hashlib
from pathlib import Path

from ci.evidence import verify_report


def ingest(report_path, config, config_digest, tested_sha, *, report_digest=None,
           verified_boundary=None):
    """verified_boundary is supplied by a trusted pilot adapter, never CLI JSON.

    Until that adapter is available, temporal roundtrip/fresh-clone verification
    remains pending. A hash proves consistency, not the authority of its producer.
    """
    required = [name for name, component in config["components"].items() if component["enabled"]]
    after = verified_boundary["completed_at"] if verified_boundary else None
    if verified_boundary and any(verified_boundary.get(key) != value for key, value in (
            ("repository", config["repository"]), ("tested_sha", tested_sha),
            ("config_digest", config_digest))):
        raise ValueError("Independent boundary does not match current project/source/config")
    report = verify_report(report_path, repository=config["repository"], tested_sha=tested_sha,
                           config_sha256=config_digest, required_components=required,
                           expected_report_sha256=report_digest, after=after,
                           require_clean=True, require_runtime=True)
    return {"scope": "component_report_consistency", "status": "verified",
            "repository": config["repository"], "tested_sha": tested_sha,
            "config_digest": config_digest,
            "report_sha256": hashlib.sha256(Path(report_path).read_bytes()).hexdigest(),
            "required_components": required, "execution": report["execution"],
            "runtime_sha256": report["runtime_sha256"],
            "roundtrip_and_clone": "independently_verified" if verified_boundary else "pending",
            "artifact_transport": "pending_authoritative_envelope",
            "onboarding_ready": False}
