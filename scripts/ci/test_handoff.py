import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from handoff import extract, fetch, paper_status


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root/"input.zip"
        with zipfile.ZipFile(self.archive,"w") as archive:
            archive.writestr("report.json", "{}")
        self.sha = "a"*40
        self.run = {"id":20,"run_attempt":2,"repository":{"id":10},"head_repository":{"id":10},"head_sha":self.sha,
                    "path":".github/workflows/ci.yml","head_branch":"main","event":"push","status":"completed","conclusion":"failure"}
        self.artifact = {"id":30,"name":f"checks-{self.sha}-20-2","expired":False,"size_in_bytes":self.archive.stat().st_size,
                         "digest":"sha256:"+hashlib.sha256(self.archive.read_bytes()).hexdigest(),"workflow_run":{"id":20,"head_sha":self.sha}}

    def fetch(self, mutation=None, **kwargs):
        owner = self
        class Client:
            def metadata(self, path):
                if "/attempts/" in path:
                    return owner.run
                if "/artifacts?" in path:
                    return {"artifacts":[owner.artifact]}
                return {"id":10,"default_branch":"main"}
            def download(self,path,target,limit):
                shutil.copyfile(owner.archive,target)
                if mutation:
                    mutation(target)
        return fetch(repository="org/repo",repository_id=10,run_id=20,attempt=2,source_sha=self.sha,
                     workflow_path=".github/workflows/ci.yml",artifact_name=f"checks-{self.sha}-20-2",output=self.root/"out",client=Client(),**kwargs)

    def test_release_control_sha_can_differ_from_selected_source(self):
        self.run["head_sha"]="b"*40
        self.artifact["workflow_run"]["head_sha"]="b"*40
        self.run["conclusion"]="success"
        receipt=self.fetch(bind_source=False,require_success=True)
        self.assertEqual(receipt["source_sha"],self.sha)
        self.assertEqual(receipt["producer_control_sha"],"b"*40)

    def test_failed_producer_can_supply_successful_individual_results(self):
        receipt = self.fetch()
        self.assertEqual(receipt["artifact_id"],30)
        self.assertEqual(receipt["producer_conclusion"],"failure")
        self.assertTrue((self.root/"out/report.json").is_file())

    def test_prior_attempt_wrong_workflow_or_fork_rejected(self):
        for field,value in [("run_attempt",1),("path",".github/workflows/other.yml"),("head_repository",{"id":999}),("head_sha","b"*40),("event","pull_request")]:
            previous = self.run[field]
            self.run[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.fetch()
            self.run[field]=previous

    def test_missing_attempt_expired_and_corrupt_artifacts_fail(self):
        self.artifact["name"]="checks-old-attempt"
        with self.assertRaisesRegex(ValueError,"missing"):
            self.fetch()
        self.artifact["name"]=f"checks-{self.sha}-20-2"
        self.artifact["expired"]=True
        with self.assertRaisesRegex(ValueError,"expired"):
            self.fetch()
        self.artifact["expired"]=False
        with self.assertRaisesRegex(ValueError,"digest"):
            self.fetch(lambda path:path.write_bytes(b"tampered"))

    def test_archive_never_extracts_script_paths_outside_destination(self):
        with zipfile.ZipFile(self.archive,"w") as archive:
            archive.writestr("../escape", "bad")
        with self.assertRaises(ValueError):
            extract(self.archive,self.root/"out")
        self.assertFalse((self.root/"escape").exists())

    def test_badges_evaluate_named_result_not_overall_color(self):
        (self.root/"evidence.txt").write_text("build evidence")
        member={"path":"evidence.txt","bytes":14,"sha256":hashlib.sha256(b"build evidence").hexdigest()}
        report={"schema":"project-checks/v1","source":{"source_sha":self.sha,"tested_sha":self.sha,"dirty":False},
                "configuration":{"project_config_sha256":"c"*64},"execution":{"run_id":"20","run_attempt":"2"},
                "gate_outcome":"fail","files":[member],"plan":{"components":{"paper":{"selected":True}}},
                "components":{"paper":{"checks":[dict(name=n,kind="build",execution_status="completed",gate_outcome="pass",raw_exit=0,files=[member]) for n in ("draft","final")]}}}
        def status():
            return paper_status(report,self.root,"build",source_sha=self.sha,config_sha256="c"*64,run_id=20,attempt=2)
        self.assertEqual(status()["outcome"],"pass")
        report["components"]["paper"]["checks"][0]["execution_status"]="not_run"
        with self.assertRaisesRegex(ValueError,"did not pass"):
            status()
        report["components"]["paper"]["checks"][0]["execution_status"]="completed"
        report["plan"]["components"]["paper"]["selected"]=False
        with self.assertRaisesRegex(ValueError,"not selected"):
            status()


if __name__ == "__main__":
    unittest.main()
