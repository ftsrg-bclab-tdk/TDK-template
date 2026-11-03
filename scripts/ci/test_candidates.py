import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import release_transport  # Loads the shared release libraries from their controlled source path.
from ci.candidates import retain, recover
from publication_io import RemoteError


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.archive=self.root/"candidate.zip"
        with zipfile.ZipFile(self.archive,"w") as archive:
            archive.writestr("receipt.json",'{"fixture":true}')
        self.transport={"schema":"ci-artifact/v1","repository_id":10,"source_sha":"a"*40,"run_id":20,"run_attempt":1,"artifact_id":30,
                        "artifact_sha256":hashlib.sha256(self.archive.read_bytes()).hexdigest(),"workflow_path":".github/workflows/release-prepare.yml"}
        class Remote:
            def __init__(self):self.value=None;self.data={};self.posts=0
            def request(self,method,path,value=None,data=None):
                if path=="/repos/org/project":return {"id":10}
                if path.endswith("immutable-releases"):raise RemoteError(403)
                if "/releases?" in path:return [self.value] if self.value else []
                if "/releases/tags/" in path:
                    if not self.value or self.value["draft"]:raise RemoteError(404)
                    return self.value
                if method=="POST" and path.endswith("/releases"):
                    self.posts+=1
                    self.value=dict(value,id=40,assets=[],immutable=False)
                    return self.value
                if method=="POST" and "/assets?name=" in path:
                    name=path.split("name=")[1];identifier=len(self.data)+50;self.data[identifier]=data
                    item={"id":identifier,"name":name,"size":len(data),"digest":"sha256:"+hashlib.sha256(data).hexdigest()}
                    self.value["assets"].append(item);return item
                if method=="PATCH":self.value.update(value);self.value["immutable"]=True
                return self.value
            def download(self,path,target,limit):
                data=self.data[int(path.rsplit('/',1)[1])]
                if len(data)>limit:raise ValueError("limit")
                Path(target).write_bytes(data)
        self.remote=Remote()

    def test_verified_bytes_survive_actions_expiry_and_retain_is_idempotent(self):
        for _ in range(2):
            locator=retain(self.remote,self.remote,"org/project",10,"a"*40,"b"*64,self.archive,self.transport,self.remote)
            self.assertEqual(locator["release_id"],40)
        self.assertEqual(self.remote.posts,1)
        self.assertEqual(self.remote.value["make_latest"],"false")
        recovered,locator=recover(self.remote,"org/project",10,"b"*64,self.transport,self.root/"recovered",self.remote)
        self.assertEqual(recovered,self.transport)
        self.assertEqual((self.root/"recovered/receipt.json").read_bytes(),b'{"fixture":true}')

    def test_wrong_retained_identity_and_corrupt_archive_are_rejected(self):
        retain(self.remote,self.remote,"org/project",10,"a"*40,"b"*64,self.archive,self.transport,self.remote)
        expected=dict(self.transport,run_attempt=9)
        with self.assertRaisesRegex(ValueError,"identity"):
            recover(self.remote,"org/project",10,"b"*64,expected,self.root/"bad",self.remote)
        self.remote.data[50]=b"corrupt"
        with self.assertRaisesRegex(ValueError,"digest"):
            recover(self.remote,"org/project",10,"b"*64,self.transport,self.root/"bad",self.remote)

    def test_lost_draft_creation_is_found_without_tag_lookup_or_second_post(self):
        self.remote.value={"id":40,"tag_name":"release-candidates/"+"b"*64,"draft":True,"immutable":False,"assets":[]}
        retain(self.remote,self.remote,"org/project",10,"a"*40,"b"*64,self.archive,self.transport,self.remote)
        self.assertEqual(self.remote.posts,0)
        self.assertTrue(self.remote.value["immutable"])

    def test_ambiguous_drafts_block_creation(self):
        original=self.remote.request
        def request(method,path,**kwargs):
            if "/releases?" in path:
                return [{"tag_name":"release-candidates/"+"b"*64,"id":40},
                        {"tag_name":"release-candidates/"+"b"*64,"id":41}]
            return original(method,path,**kwargs)
        self.remote.request=request
        with self.assertRaisesRegex(ValueError,"ambiguous"):
            retain(self.remote,self.remote,"org/project",10,"a"*40,"b"*64,self.archive,self.transport,self.remote)
        self.assertEqual(self.remote.posts,0)

    def test_mutable_published_candidate_never_becomes_durable_receipt(self):
        original=self.remote.request
        def request(method,path,**kwargs):
            value=original(method,path,**kwargs)
            if method=="PATCH":self.remote.value["immutable"]=False
            return value
        self.remote.request=request
        with self.assertRaisesRegex(ValueError,"not immutable"):
            retain(self.remote,self.remote,"org/project",10,"a"*40,"b"*64,self.archive,self.transport,self.remote)
