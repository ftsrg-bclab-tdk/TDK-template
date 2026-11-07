import base64
import io
import urllib.error
import unittest

from packager import encode, parse
from publication_io import HTTP, GitHubStore, RemoteError
from publisher import Zenodo, metadata_matches


class Response(io.BytesIO):
    pass


class Opener:
    def __init__(self, responses):
        self.responses=list(responses)
        self.requests=[]

    def open(self, request, timeout):
        self.requests.append(request)
        result=self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return Response(encode(result))


class TransportTests(unittest.TestCase):
    def test_get_retry_and_write_no_retry(self):
        failed=urllib.error.HTTPError('https://sandbox.zenodo.org/api',429,'busy',{'Retry-After':'2'},None)
        waits=[]
        opener=Opener([failed, {'ok':True}])
        http=HTTP('https://sandbox.zenodo.org','fixture-secret',sleep=waits.append,opener=opener)
        self.assertTrue(http.request('GET','/api')['ok'])
        self.assertEqual(waits,[2])
        opener.responses=[TimeoutError()]
        with self.assertRaises(RemoteError):
            http.request('POST','/api',value={})
        self.assertEqual(len(opener.requests),3)

    def test_cross_origin_and_redirect_rejected(self):
        opener=Opener([])
        http=HTTP('https://sandbox.zenodo.org','secret',opener=opener)
        with self.assertRaises(ValueError):
            http.request('GET','https://attacker.invalid/api')
        self.assertEqual(opener.requests,[])
        opener.responses=[urllib.error.HTTPError('https://sandbox.zenodo.org/api',302,'redirect',{},None)]
        with self.assertRaises(RemoteError) as exc:
            http.request('GET','/api')
        self.assertNotIn('secret',str(exc.exception))
        self.assertEqual(len(opener.requests),1)

    def test_newversion_follows_latest_draft_not_old_id(self):
        opener=Opener([{'id':101,'links':{'latest_draft':'https://sandbox.zenodo.org/api/deposit/depositions/102'}}, {'id':102}])
        api=Zenodo(HTTP('https://sandbox.zenodo.org','secret',opener=opener),'sandbox')
        self.assertEqual(api.newversion(101)['id'],102)
        self.assertEqual([r.method for r in opener.requests],['POST','GET'])
        self.assertTrue(opener.requests[1].full_url.endswith('/102'))

    def test_published_records_endpoint_uses_resource_type(self):
        # Records shape confirmed by read-only GET /api/records/3242074 on 2026-11-05.
        # Identifiers and content below are synthetic; this is never a publish request.
        metadata = {'title': 'Synthetic', 'resource_type': {'title': 'Software', 'type': 'software'},
                    'license': {'id': 'mit'}}
        response = {'id': 101, 'status': 'published', 'state': 'done', 'submitted': True,
                    'doi': '10.5072/zenodo.101', 'conceptdoi': '10.5072/zenodo.100',
                    'metadata': metadata, 'files': []}
        opener = Opener([response])
        api = Zenodo(HTTP('https://sandbox.zenodo.org', 'secret', opener=opener), 'sandbox')
        record, fields = api.published({'id': 101, 'record_id': 101})
        self.assertTrue(metadata_matches(record['metadata'],
                        {'title': 'Synthetic', 'upload_type': 'software', 'license': 'mit'}))
        self.assertEqual(fields['version_doi'], response['doi'])
        self.assertEqual([(r.method, r.full_url) for r in opener.requests],
                         [('GET', 'https://sandbox.zenodo.org/api/records/101')])

    def test_bucket_origin_validation_precedes_upload(self):
        opener=Opener([])
        api=Zenodo(HTTP('https://sandbox.zenodo.org','secret',opener=opener),'sandbox')
        with self.assertRaises(ValueError):
            api.upload({'links':{'bucket':'https://zenodo.org/api/files/other'}},'file.zip',b'bytes')
        self.assertEqual(opener.requests,[])

    def test_listing_is_paginated_for_marker_recovery(self):
        filler=[{'id':n,'metadata':{'description':'other'}} for n in range(100)]
        match={'id':101,'metadata':{'description':'unique-operation'}}
        opener=Opener([filler,[match]])
        api=Zenodo(HTTP('https://sandbox.zenodo.org','secret',opener=opener),'sandbox')
        self.assertEqual(api.find_marker('unique-operation'),[match])
        self.assertIn('page=2',opener.requests[1].full_url)


class FakeContents:
    def __init__(self):
        self.value=None
        self.sha=None
        self.lose=False
        self.writes=0

    def request(self, method, path, value=None):
        if method=='GET' and path == '/repos/org/student-project':
            return {'id': 42}
        if method=='GET':
            if self.value is None:
                raise RemoteError(404)
            raw=encode(self.value)
            return {'type':'file','encoding':'base64','size':len(raw),'sha':self.sha,
                    'content':base64.b64encode(raw).decode()}
        self.writes+=1
        if value.get('sha') != self.sha:
            raise RemoteError(409)
        self.value=parse(base64.b64decode(value['content']))
        self.sha=str(self.writes)
        if self.lose:
            self.lose=False
            raise RemoteError()
        return {'content':{'sha':self.sha}}


class RemoteRegistryTests(unittest.TestCase):
    def test_foreign_repository_rejected_before_registry_access(self):
        remote=FakeContents()
        with self.assertRaisesRegex(ValueError, 'differs from publication context'):
            GitHubStore(remote,'org/student-project','publication-state','registry/zenodo.json',99)
        self.assertEqual(remote.writes,0)
        self.assertIsNone(remote.value)

    def test_missing_repository_id_rejected(self):
        remote=FakeContents()
        with self.assertRaisesRegex(ValueError, 'Positive publication repository ID'):
            GitHubStore(remote,'org/student-project','publication-state','registry/zenodo.json',True)
        self.assertEqual(remote.writes,0)

    def test_lost_put_reply_reads_exact_persisted_state(self):
        remote=FakeContents()
        store=GitHubStore(remote,'org/student-project','publication-state','registry/zenodo.json',42)
        value={'schema':'fixture','owner':None}
        remote.lose=True
        version=store.put(value,None)
        self.assertEqual(store.read(),(value,version))
        self.assertEqual(remote.writes,1)

    def test_conflicting_write_not_replayed(self):
        remote=FakeContents()
        store=GitHubStore(remote,'org/student-project','publication-state','registry/zenodo.json',42)
        store.put({'value':1},None)
        with self.assertRaises(ValueError):
            store.put({'value':2},None)
        self.assertEqual(remote.value,{'value':1})
        self.assertEqual(remote.writes,2)


if __name__=='__main__':
    unittest.main()
