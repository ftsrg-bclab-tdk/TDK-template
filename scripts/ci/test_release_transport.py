import json
from pathlib import Path
import subprocess
import unittest
import zipfile

import test_project
from ci.config import load_project
from ci.run import merge_reports
from release_transport import bootstrap, checks_to_bundle
from publication_io import RemoteError


class RegistryBootstrapTests(unittest.TestCase):
    def client(self, *, repo_id=10, default_sha="a"*40, exists=False, lost_reply=False):
        class HTTP:
            def __init__(self):
                self.calls=[]
                self.created=exists
            def request(self,method,path,value=None):
                self.calls.append((method,path,value))
                if path=="/repos/org/project":return {"id":repo_id,"default_branch":"main"}
                if path.endswith("/git/ref/heads/main"):return {"object":{"sha":default_sha}}
                if path.endswith("/git/ref/heads/publication-state"):
                    if self.created:return {"object":{"sha":"e"*40}}
                    raise RemoteError(404)
                if path.endswith("/git/blobs"):return {"sha":"b"*40}
                if path.endswith("/git/trees"):return {"sha":"c"*40}
                if path.endswith("/git/commits"):
                    if value["parents"]!=[]:raise AssertionError("Must not inherit research history")
                    return {"sha":"e"*40}
                if path.endswith("/git/refs"):
                    self.created=True
                    if lost_reply:raise RemoteError()
                    return {"object":{"sha":"e"*40}}
                raise AssertionError(path)
        return HTTP()

    def test_project_id_and_default_control_ref_before_writes(self):
        for http,ref in [(self.client(repo_id=11),"refs/heads/main"),(self.client(),"refs/heads/feature"),(self.client(default_sha="f"*40),"refs/heads/main")]:
            with self.assertRaises(ValueError):
                bootstrap(http,"org/project",10,"a"*40,ref)
            self.assertFalse(any(c[0]=="POST" for c in http.calls))

    def test_existing_branch_and_lost_create_reply_are_not_replayed(self):
        existing=self.client(exists=True)
        self.assertEqual(bootstrap(existing,"org/project",10,"a"*40,"refs/heads/main"),"e"*40)
        self.assertFalse(any(c[0]=="POST" for c in existing.calls))
        lost=self.client(lost_reply=True)
        self.assertEqual(bootstrap(lost,"org/project",10,"a"*40,"refs/heads/main"),"e"*40)
        creates=[c for c in lost.calls if c[0]=="POST" and c[1].endswith("/git/refs")]
        self.assertEqual(len(creates),1)


class ReleaseHandoffTests(unittest.TestCase):
    setUp=test_project.ProjectTests.setUp
    run_report=test_project.ProjectTests.run_report

    def test_real_check_evidence_to_deterministic_packager_without_rebuild(self):
        (self.root/"tool.py").write_text("print('fixture')\n")
        (self.root/"metadata.json").write_text('{"title":"Transport fixture only"}')
        manifest={"schema_version":1,"packages":{"research":{"filename":"research.zip","license_expression":"MIT","build_profile":None,
                  "files":[{"origin":"tracked","path":"tool.py","archive_path":"tool.py"}]}},
                  "records":{"research":{"packages":["research"],"metadata_file":"metadata.json","access":"public"}}}
        (self.root/"release.json").write_text(json.dumps(manifest))
        subprocess.run(["git","-C",str(self.root),"add","tool.py","metadata.json","release.json"],check=True)
        subprocess.run(["git","-C",str(self.root),"-c","user.email=test@example.com","-c","user.name=Fixture","commit","-qm","release fixture"],check=True)
        part=self.run_report("checks/paper")
        config,digest=load_project(self.root)
        checks=self.root/".project/checks"
        report=merge_reports(part["plan"],{"paper":part},checks,config,digest,part["execution"]["started_at"])
        (checks/"report.json").write_text(json.dumps(report))
        # If preparation executes the source again, this now-failing script reveals it.
        # The packager reads immutable Git source, while the check receipt identifies
        # the selected committed source. No selected script is called here.
        (self.root/"paper/build.py").write_text("raise RuntimeError('selected source must not execute during packaging')\n")
        result=checks_to_bundle(checks,self.root,"release.json",self.root/".project/bundle")
        self.assertEqual(result["source_sha"],report["source"]["tested_sha"])
        with zipfile.ZipFile(self.root/".project/bundle/research.zip") as archive:
            self.assertEqual(archive.read("tool.py"),b"print('fixture')\n")
        self.assertTrue((self.root/".project/bundle/receipt.json").is_file())
