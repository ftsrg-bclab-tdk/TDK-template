"""Portable report verification shared by setup, workflow gates and artifact consumers.

Consistency is checked here; approval and producer authority come from the caller.
Successful local checks are not proof of Overleaf sync or fresh-clone execution.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

try:
    from .config import inside, read_json
except ImportError:
    from config import inside, read_json


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError("Timezone required")
        return result
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid evidence timestamp") from exc


def validate_runtime(runtime, tested_sha, config_sha256, component=None, require_tlc=False):
    if (not isinstance(runtime, dict) or runtime.get("schema") != "runtime-resolution/v1"
            or runtime.get("source_sha") != tested_sha
            or runtime.get("project_config_sha256") != config_sha256):
        raise ValueError("Runtime identity mismatch")
    if component:
        tools = runtime.get("tools")
        required_tools = {"python", "git"} | {
            "paper": {"tex", "latexmk", "inkscape", "pdfinfo", "python_packages"},
            "presentation": {"node", "npm", "browser"},
        }.get(component, set())
        members = runtime.get("components")
        if (not isinstance(tools, dict) or not required_tools <= tools.keys()
                or any(not isinstance(v, str) or not v.strip() for v in tools.values())
                or not isinstance(members, list) or members != [component]):
            raise ValueError("Required component runtime content mismatch: " + component)
    if require_tlc:
        proof = runtime.get("proof_tools")
        if (not isinstance(proof, dict) or not isinstance(proof.get("tlc"), dict)
                or not isinstance(proof.get("java"), dict)):
            raise ValueError("Missing resolved TLC/JVM identity")
        tlc, java = proof["tlc"], proof["java"]
        if (not all(tlc.get(k) for k in ("tag", "release_id", "asset_id", "jar", "requested", "resolved_at"))
                or not all(java.get(k) for k in ("executable", "version"))
                or any(not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")) for item in (tlc, java))
                or any(runtime["tools"].get(k) != json.dumps(proof[k], sort_keys=True) for k in ("tlc", "java"))):
            raise ValueError("Invalid resolved TLC/JVM identity/content")
    return runtime


def uses_tlc(checks):
    return any(any(Path(arg).name == "tlc.py" for arg in step.get("argv", [])) for step in checks)


def verify_report(report_path, *, repository, tested_sha, config_sha256,
                  required_components, expected_report_sha256=None, after=None,
                  require_clean=True, require_runtime=True):
    report_path = Path(report_path)
    report, raw = read_json(report_path)
    if expected_report_sha256 and hashlib.sha256(raw).hexdigest() != expected_report_sha256:
        raise ValueError("Report digest mismatch")
    if not isinstance(report, dict) or report.get("schema") != "project-checks/v1":
        raise ValueError("Expected project-checks/v1")
    source, configuration = report.get("source", {}), report.get("configuration", {})
    if not isinstance(source, dict) or not isinstance(configuration, dict) or not isinstance(source.get("repository"), str):
        raise ValueError("Missing source/configuration identity")
    if (not isinstance(repository, str) or source.get("repository", "").lower() != repository.lower()
            or not re.fullmatch(r"[0-9a-f]{40}", tested_sha)
            or source.get("tested_sha") != tested_sha or source.get("source_sha") != tested_sha
            or configuration.get("project_config_sha256") != config_sha256):
        raise ValueError("Report repository/source/config identity mismatch")
    if require_clean and source.get("dirty") is not False:
        raise ValueError("Dirty or unknown source state")
    source_after = report.get("source_after", {})
    if (not isinstance(source_after, dict) or any(source_after.get(k) != source.get(k)
            for k in ("repository", "source_sha", "tested_sha"))):
        raise ValueError("Post-run source identity mismatch")
    if require_clean and source_after.get("dirty") is not False:
        raise ValueError("Source became dirty during execution")
    execution = report.get("execution", {})
    started, completed = timestamp(execution.get("started_at")), timestamp(execution.get("completed_at"))
    current = datetime.now(timezone.utc)
    if completed < started or started > current or completed > current:
        raise ValueError("Invalid execution interval")
    if after and started < timestamp(after):
        raise ValueError("Evidence predates required roundtrip/clone boundary")
    if not all(execution.get(k) for k in ("actor", "method", "log_reference")):
        raise ValueError("Missing execution provenance")
    plan = report.get("plan")
    if not isinstance(plan, dict) or canonical_digest(plan) != configuration.get("dependency_plan_sha256"):
        raise ValueError("Plan digest mismatch")
    if plan.get("source") != source or plan.get("configuration", {}).get("project_config_sha256") != config_sha256:
        raise ValueError("Plan identity mismatch")
    if report.get("gate_outcome") != "pass" or plan.get("draft") is not False:
        raise ValueError("Checks failed, incomplete or deferred")
    runtime = report.get("runtime")
    if require_runtime and not runtime:
        raise ValueError("Missing runtime resolution evidence")
    if runtime and (runtime.get("schema") != "runtime-resolution/v1"
                    or runtime.get("source_sha") != tested_sha
                    or runtime.get("project_config_sha256") != config_sha256
                    or canonical_digest(runtime) != report.get("runtime_sha256")):
        raise ValueError("Runtime identity mismatch")
    if not required_components or len(set(required_components)) != len(required_components):
        raise ValueError("Caller must declare unique required components")
    for name in required_components:
        nested = runtime.get("components", {}).get(name) if runtime and isinstance(runtime.get("components"), dict) else runtime
        if require_runtime:
            try:
                validate_runtime(nested, tested_sha, config_sha256, name, uses_tlc(report.get("components", {}).get(name, {}).get("checks", [])))
            except ValueError as exc:
                raise ValueError("Required component runtime identity/content mismatch: " + name) from exc
        component = report.get("components", {}).get(name, {})
        if (not plan.get("components", {}).get(name, {}).get("selected")
                or component.get("execution_status") != "completed" or component.get("gate_outcome") != "pass"
                or component.get("outcome") not in ("pass", "findings") or not component.get("checks")):
            raise ValueError("Required component was not verified: " + name)
        for step in component["checks"]:
            if step.get("execution_status") != "completed" or step.get("gate_outcome") != "pass":
                raise ValueError("Required step failed or did not run")
    files = report.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("Missing evidence file inventory")
    seen = set()
    for member in files:
        if not isinstance(member, dict) or not isinstance(member.get("path"), str) or member["path"] in seen or member["path"] == report_path.name:
            raise ValueError("Invalid or duplicate evidence file")
        seen.add(member["path"])
        path = inside(report_path.parent, member["path"])
        if not path.is_file() or path.stat().st_size != member.get("bytes"):
            raise ValueError("Missing or wrong-size evidence file: " + member["path"])
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != member.get("sha256"):
                raise ValueError("Evidence file digest mismatch: " + member["path"])
    return report
