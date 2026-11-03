#!/usr/bin/env python3
"""Hosted/local orchestration of one source revision; no publishing or runner routing."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import project
from ci.config import inside, load_project, read_json
from ci.runtime import resolve_oci, snapshot
from ci.evidence import canonical_digest


def call(argv, root, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as stream:
        result = subprocess.run(argv, cwd=root, stdout=stream, stderr=subprocess.STDOUT, timeout=7200)
    return result.returncode


def inventory(directory):
    return [{"path": str(p.relative_to(directory)), "bytes": p.stat().st_size,
             "sha256": project.file_hash(p)} for p in sorted(directory.rglob("*")) if p.is_file() and p != directory/"report.json"]


def merge_reports(plan, reports, output, config, config_digest, started):
    source = plan["source"]
    components = {}
    runtime = {"schema":"runtime-resolution/v1", "source_sha":source["tested_sha"],
               "project_config_sha256":config_digest, "components":{}}
    for name, c in config["components"].items():
        if not c["enabled"]:
            components[name] = {"execution_status":"not_run", "outcome":"not_configured", "gate_outcome":"incomplete", "checks":[]}
        elif plan["draft"] or not plan["components"][name]["selected"]:
            components[name] = {"execution_status":"not_run", "outcome":"deferred" if plan["draft"] else "unaffected", "gate_outcome":"incomplete", "checks":[]}
        elif name not in reports:
            components[name] = {"execution_status":"not_run", "outcome":"unknown", "gate_outcome":"fail", "checks":[], "reason":"missing component evidence"}
        else:
            report = reports[name]
            if report.get("source") != source or report.get("configuration", {}).get("project_config_sha256") != config_digest:
                raise ValueError("Component identity mismatch: " + name)
            components[name] = copy.deepcopy(report["components"][name])
            runtime["components"][name] = report.get("runtime")
    selected = [components[n] for n,d in plan["components"].items() if d["selected"]]
    gate = "incomplete" if plan["draft"] else "pass" if all(c["gate_outcome"] == "pass" for c in selected) else "fail"
    runtime_complete = all(runtime["components"].get(n) for n,d in plan["components"].items() if d["selected"])
    return {"schema":"project-checks/v1", "source":source,
            "configuration":{"project_config_sha256":config_digest,"dependency_plan_sha256":canonical_digest(plan)},
            "control":{"orchestrator_sha256":project.file_hash(Path(__file__))},
            "execution":{"started_at":started,"completed_at":project.now(),"actor":os.environ.get("GITHUB_ACTOR",os.environ.get("USER","unknown")),
                         "method":"github_actions" if os.environ.get("GITHUB_ACTIONS") else "local",
                         "run_id":os.environ.get("GITHUB_RUN_ID"),"run_attempt":os.environ.get("GITHUB_RUN_ATTEMPT"),
                         "workflow_sha":os.environ.get("GITHUB_WORKFLOW_SHA"),
                         "log_reference":"https://github.com/"+config["repository"]+"/actions/runs/"+os.environ.get("GITHUB_RUN_ID","") if os.environ.get("GITHUB_RUN_ID") else str(output)},
            "plan":plan,"components":components,"runtime":runtime,"runtime_sha256":canonical_digest(runtime),
            "gate_outcome":gate,"acceptance_eligible":gate=="pass" and not source["dirty"] and runtime_complete and all(d["selected"] for n,d in plan["components"].items() if config["components"][n]["enabled"]),
            "files":inventory(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("all","affected"), default="all")
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--component", action="append")
    parser.add_argument("--mode", choices=("ordinary","submit","full"), default="ordinary")
    parser.add_argument("--profile")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    started = project.now()
    output = root / ".project/checks"
    try:
        config, config_digest = load_project(root)
        if not config["repository"]:
            raise ValueError("Repository is not configured")
        plan = project.make_plan(root, config, config_digest, args)
        output.mkdir(parents=True, exist_ok=False)
        (output / "plan.json").write_text(json.dumps(plan,indent=2)+"\n")
        (output / "project.json").write_bytes((root / "project.json").read_bytes())
        reports, pending, extra_failures = {}, set(config["components"]), []
        while pending:
            ready = sorted(n for n in pending if not set(config["components"][n]["depends_on"]) & pending)
            for name in ready:
                pending.remove(name)
                component = config["components"][name]
                if not component["enabled"] or not plan["components"][name]["selected"] or args.draft:
                    continue
                if any(dep not in reports or reports[dep]["components"][dep]["gate_outcome"] != "pass" for dep in component["depends_on"] if plan["components"][dep]["selected"]):
                    continue
                report_dir = f".project/checks/{name}"
                runtime_path = f".project/{name}-runtime.json"
                command = ["python3","scripts/project.py","check","--component",name,"--no-dependencies","--mode",args.mode,"--report-dir",report_dir,"--runtime",runtime_path]
                if args.profile:
                    command += ["--profile",args.profile]
                try:
                    if name == "paper":
                        image = resolve_oci("danteev/texlive:latest")
                        image_path = root / ".project/image.json"
                        image_path.write_text(json.dumps(image)+"\n")
                        iid = root / ".project/paper-image.id"
                        build = ["docker","build","--no-cache","--build-arg","TEX_IMAGE="+image["resolved"],"--iidfile",str(iid),"-f","scripts/ci/paper.Dockerfile","scripts/ci"]
                        if call(build,root,output/"paper-image.log"):
                            continue
                        image["built_image_id"] = iid.read_text().strip()
                        image["dockerfile_sha256"] = project.file_hash(root/"scripts/ci/paper.Dockerfile")
                        image_path.write_text(json.dumps(image)+"\n")
                        prefix = ["docker","run","--rm","--init","--network=none","--cap-drop=ALL","--security-opt=no-new-privileges",
                                  "--user",f"{os.getuid()}:{os.getgid()}","-e","HOME=/tmp","-v",str(root)+":/work","-w","/work"]
                        for key in ("GITHUB_ACTIONS","GITHUB_REPOSITORY","GITHUB_ACTOR","GITHUB_RUN_ID","GITHUB_RUN_ATTEMPT","GITHUB_JOB","GITHUB_WORKFLOW_SHA","GITHUB_HEAD_REF","GITHUB_REF_NAME"):
                            if key in os.environ:
                                prefix += ["-e",key]
                        prefix += [image["built_image_id"]]
                        if call(prefix+["python3","scripts/ci/runtime.py","snapshot","--component","paper","--image",".project/image.json","--out",runtime_path],root,output/"paper-runtime.log"):
                            continue
                        call(prefix+command,root,output/"paper-command.log")
                        if args.mode == "ordinary":
                            if call(prefix+["python3","scripts/ci/paper_evidence.py"],root,output/"paper-review.log"):
                                extra_failures.append("paper review bundle")
                            if config["role"] == "template" and call(prefix+["python3","scripts/ci/template.py","paper"],root,output/"paper-template.log"):
                                extra_failures.append("maintainer paper tests")
                    else:
                        runtime = snapshot(root,"project.json",name,npm_stage=".project/runtime/presentation" if name=="presentation" else None)
                        (root/runtime_path).write_text(json.dumps(runtime,indent=2)+"\n")
                        call(command,root,output/(name+"-command.log"))
                    report, _ = read_json(root/report_dir/"report.json")
                    reports[name] = report
                except (ValueError,OSError,subprocess.SubprocessError) as exc:
                    (output/(name+"-error.txt")).write_text(str(exc)+"\n")
        report = merge_reports(plan,reports,output,config,config_digest,started)
        report["additional_failures"] = extra_failures
        if extra_failures:
            report.update(gate_outcome="fail",acceptance_eligible=False)
        if load_project(root)[1] != config_digest:
            report.update(gate_outcome="fail",acceptance_eligible=False,error="Config changed during orchestration")
        (output/"report.json").write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps({"gate_outcome":report["gate_outcome"],"components":{n:c["outcome"] for n,c in report["components"].items()}},indent=2))
        # Draft is useful source feedback but remains explicitly incomplete evidence.
        return 0 if args.draft or report["gate_outcome"]=="pass" else 1
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print(str(exc),file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
