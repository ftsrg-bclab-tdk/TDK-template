import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/'session/job_image.py'
spec=importlib.util.spec_from_file_location('job_image',PATH)
cache=importlib.util.module_from_spec(spec);spec.loader.exec_module(cache)


class CacheLeaseTests(unittest.TestCase):
    def test_public_oci_is_readable_despite_private_controller_umask(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'oci'
            old=os.umask(0o077)
            try:
                (directory/'blobs/sha256').mkdir(parents=True)
                blob=directory/'blobs/sha256'/('a'*64);blob.write_text('public image')
                cache.public_oci(directory)
            finally:os.umask(old)
            self.assertEqual(directory.stat().st_mode & 0o777,0o755)
            self.assertEqual(blob.parent.stat().st_mode & 0o777,0o755)
            self.assertEqual(blob.stat().st_mode & 0o777,0o644)

    def test_collection_keeps_active_and_pending_digests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'root';base=Path(tmp)/'cache';base.mkdir()
            (root/'sessions').mkdir(parents=True);(root/'operations').mkdir()
            for char in 'abcd':(base/(char*64)).mkdir()
            (root/'sessions/live.json').write_text(json.dumps({'job_image':{'digest':'sha256:'+'a'*64}}))
            pending=root/'operations'/('1'*32+'.json')
            pending.write_text(json.dumps({'phase':'preparing','cache_digest':'sha256:'+'b'*64}))
            current=root/'operations'/('2'*32+'.json');current.write_text('{"phase":"preparing"}')
            with patch.object(cache,'ROOT',root),patch.object(cache,'BASE',base):
                cache.protect_and_prune('sha256:'+'c'*64,'2'*32)
            self.assertEqual({p.name for p in base.iterdir()},{c*64 for c in 'abc'})
            self.assertEqual(json.loads(current.read_text())['cache_digest'],'sha256:'+'c'*64)

    def test_cache_completion_does_not_reopen_cancelled_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'root';base=Path(tmp)/'cache';base.mkdir()
            (root/'sessions').mkdir(parents=True);(root/'operations').mkdir()
            operation=root/'operations'/('1'*32+'.json');operation.write_text('{"phase":"cancelled"}')
            with patch.object(cache,'ROOT',root),patch.object(cache,'BASE',base):
                cache.protect_and_prune('sha256:'+'a'*64,'1'*32)
            self.assertEqual(json.loads(operation.read_text()),{'phase':'cancelled'})


if __name__=='__main__':unittest.main()
