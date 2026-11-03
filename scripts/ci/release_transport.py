#!/usr/bin/env python3
"""Bind exact CI bytes to release packaging and manual student-owned publication."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"release"))
from ci.config import inside, load_project, read_json
from ci.evidence import verify_report
from ci.handoff import fetch, require, ArtifactUnavailable
from ci.candidates import retain, recover
from external_inputs.external_inputs import Unavailable
from publication_io import HTTP, RemoteError
from publisher import read_bundle
from packager import prepare


def control(http, repository, repository_id, control_sha, ref):
    require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repository)),"Invalid repository")
    prefix = "/repos/"+repository
    repo = http.request("GET",prefix)
    require(repo.get("id") == repository_id,"Publication registry repository ID mismatch")
    require(ref == "refs/heads/"+repo["default_branch"],"Publication must run from default-branch control ref")
    current = http.request("GET",prefix+"/git/ref/heads/"+repo["default_branch"])
    require(current.get("object",{}).get("sha") == control_sha,"Control SHA moved; review and dispatch current workflow")
    return prefix


def bootstrap(http, repository, repository_id, control_sha, ref):
    """Create an isolated project-owned state branch; no selected source tree or POST retry."""
    prefix = control(http,repository,repository_id,control_sha,ref)
    endpoint = prefix+"/git/ref/heads/publication-state"
    try:
        return http.request("GET",endpoint)["object"]["sha"]
    except RemoteError as exc:
        if exc.status != 404:
            raise
    blob = http.request("POST",prefix+"/git/blobs",value={"content":"Publication operation journal. Not project source or a template contribution.\n","encoding":"utf-8"})
    tree = http.request("POST",prefix+"/git/trees",value={"tree":[{"path":"README.txt","mode":"100644","type":"blob","sha":blob["sha"]}]})
    commit = http.request("POST",prefix+"/git/commits",value={"message":"Initialize isolated publication state","tree":tree["sha"],"parents":[]})
    try:
        http.request("POST",prefix+"/git/refs",value={"ref":"refs/heads/publication-state","sha":commit["sha"]})
    except RemoteError:
        # Reconcile a lost create response by reading; never blindly replay the POST.
        observed = http.request("GET",endpoint)
        require(observed.get("object",{}).get("sha") == commit["sha"],"Publication branch creation is ambiguous")
    return commit["sha"]


def checks_to_bundle(checks, source, manifest, output):
    config, config_hash = load_project(source)
    report_path = checks/"report.json"
    report, _ = read_json(report_path)
    actual_sha = subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD"],text=True).strip()
    selected = json.loads(subprocess.check_output(["git","-C",str(source),"show",actual_sha+":"+manifest]))
    selected_components={f.get("path","").split("/",1)[0] for p in selected["packages"].values() for f in p["files"]}
    for name in selected_components & config["components"].keys():
        require(config["components"][name]["enabled"],"Selected release component is not configured: "+name)
    required = [n for n,c in config["components"].items() if c["enabled"]]
    verified = verify_report(report_path,repository=config["repository"],tested_sha=report["source"]["tested_sha"],
                             config_sha256=config_hash,required_components=required)
    require(actual_sha == verified["source"]["tested_sha"],"Selected source differs from check artifact")
    for package in selected["packages"].values():
        if any(f.get("path","").startswith("paper/") for f in package["files"]):
            require(verified["components"].get("paper",{}).get("profile") == "submit","Selected paper release requires strict submit evidence")
    staging = output.parent/"release-inputs"
    staging.mkdir(parents=True,exist_ok=False)
    tools = {}
    for component, resolution in verified["runtime"].get("components", {}).items():
        if resolution:
            tools.update({component+"/"+name:version for name,version in resolution.get("tools",{}).items()})
    if not tools:
        tools = verified["runtime"].get("tools",{})
    runtime = {"schema":"runtime-evidence/v1","tools":tools,"producer_resolution":verified["runtime"],
               "dependency_resolution":{"project_checks_sha256":hashlib.sha256(report_path.read_bytes()).hexdigest(),"runtime_sha256":verified["runtime_sha256"]}}
    runtime_path=staging/"runtime.json"
    runtime_path.write_text(json.dumps(runtime,indent=2)+"\n")
    built=staging/"built"
    built.mkdir()
    receipt={"schema":"build-outputs/v1","source_sha":actual_sha,"runtime_sha256":hashlib.sha256(runtime_path.read_bytes()).hexdigest(),"outputs":{}}
    for name,c in verified["components"].items():
        for step in c.get("checks",[]):
            for member in step.get("files",[]):
                path = inside(checks,member["path"])
                require(hashlib.sha256(path.read_bytes()).hexdigest()==member["sha256"],"Selected built bytes changed")
                key = config["components"][name]["cwd"]+"/"+member["source_path"]
                require(key not in receipt["outputs"],"Duplicate built output identity")
                target=inside(built,key);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
                receipt["outputs"][key]={"sha256":member["sha256"],"size":member["bytes"],"profile":name+":"+c["profile"]}
    receipt_path=staging/"build-receipt.json"
    receipt_path.write_text(json.dumps(receipt,indent=2)+"\n")
    return prepare(source,actual_sha,manifest,runtime_path,output,built,receipt_path,checks/"references")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation",choices=("prepare","publish"))
    parser.add_argument("--inputs",type=Path,required=True,help="workflow_dispatch inputs JSON; no secrets")
    args=parser.parse_args()
    inputs,_=read_json(args.inputs)
    repository=os.environ["GITHUB_REPOSITORY"]
    repository_id=int(os.environ["GITHUB_REPOSITORY_ID"])
    source_sha=inputs["source_sha"]
    run_id,attempt,artifact_id=(int(inputs[k]) for k in ("producer_run_id","producer_run_attempt","producer_artifact_id"))
    is_publish=args.operation=="publish"
    artifact_name=("release-bundle" if is_publish else "checks")+f"-{source_sha}-{run_id}-{attempt}"
    output=Path(".project/incoming")
    candidate_locator=None
    http=None
    control_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
    if is_publish:
        require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}",inputs["operation_id"])),"Invalid operation ID")
        require(bool(re.fullmatch(r"[0-9a-f]{64}",inputs["receipt_sha256"])),"Expected reviewed receipt SHA256")
        require(inputs["phase"] in ("stage","reconcile","publish","receipt"),"Unsupported publication phase")
        require(inputs["environment"] in ("sandbox","production"),"Unsupported Zenodo environment")
        require(bool(os.environ.get("ZENODO_TOKEN")),"Student Zenodo token is not configured")
        http=HTTP("https://api.github.com",os.environ["REGISTRY_GITHUB_TOKEN"])
        control(http,repository,repository_id,control_sha,os.environ["GITHUB_REF"])
    try:
        receipt=fetch(repository=repository,repository_id=repository_id,run_id=run_id,attempt=attempt,source_sha=source_sha,
                  workflow_path=".github/workflows/release-prepare.yml" if is_publish else ".github/workflows/ci.yml",
                  artifact_name=artifact_name,output=output,allowed_events=("workflow_dispatch",) if is_publish else ("push","workflow_dispatch"),
                  artifact_id=artifact_id,expected_artifact_sha256=inputs["artifact_sha256"],bind_source=not is_publish,require_success=True,
                  retain_archive=Path(".project/candidate.zip") if is_publish else None)
    except (ArtifactUnavailable,Unavailable):
        if not is_publish:
            raise
        expected={"repository_id":repository_id,"source_sha":source_sha,"run_id":run_id,"run_attempt":attempt,
                  "artifact_id":artifact_id,"artifact_sha256":inputs["artifact_sha256"],"workflow_path":".github/workflows/release-prepare.yml"}
        receipt,candidate_locator=recover(http,repository,repository_id,inputs["receipt_sha256"],expected,output)
    if not is_publish:
        bundle=Path(".project/bundle")
        result=checks_to_bundle(output,Path("source").resolve(),inputs["manifest"],bundle)
        print(json.dumps({"source_sha":result["source_sha"],"receipt_sha256":hashlib.sha256((bundle/"receipt.json").read_bytes()).hexdigest()}))
        return 0
    bundle=read_bundle(output,inputs["receipt_sha256"])
    require(bundle["receipt"]["source_sha"]==source_sha,"Bundle source mismatch")
    if candidate_locator is None:
        candidate_locator=retain(http,HTTP("https://uploads.github.com",os.environ["REGISTRY_GITHUB_TOKEN"]),repository,repository_id,
                                 source_sha,inputs["receipt_sha256"],Path(".project/candidate.zip"),receipt)
    bootstrap(http,repository,repository_id,control_sha,os.environ["GITHUB_REF"])
    context={"schema":"publication-context/v1","kind":"research","repository_id":repository_id,"source_sha":source_sha,
             "control_sha":control_sha,"producer_run_id":run_id,"producer_run_attempt":attempt,"producer_artifact_id":artifact_id,"artifact_sha256":receipt["artifact_sha256"],
             "durable_candidate":candidate_locator}
    context_path=Path(".project/publication-context.json")
    context_path.write_text(json.dumps(context,indent=2)+"\n")
    journal="registry/zenodo.json" if inputs["environment"]=="production" else "registry/zenodo-sandbox.json"
    return subprocess.call([sys.executable,"scripts/release/publisher.py","--phase",inputs["phase"],"--bundle",str(output),
                           "--expected-receipt-sha256",inputs["receipt_sha256"],"--operation-id",inputs["operation_id"],
                           "--repository-id",str(repository_id),"--environment",inputs["environment"],"--context",str(context_path),
                           "--registry-github",repository,"--registry-ref","publication-state","--registry-path",journal,
                           "--output",".project/publication-receipt.json"])


if __name__=="__main__":
    try:
        sys.exit(main())
    except (ValueError,OSError,KeyError,RemoteError,Unavailable,subprocess.SubprocessError) as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(2)
