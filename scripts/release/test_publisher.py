import copy
import json
import hashlib
import unittest
from unittest.mock import patch
import os
import sys

from packager import digest, encode
from publication_io import FileStore, Registry, RemoteError
from publisher import Publisher, PublicationIncomplete, read_bundle, main, validate_context, metadata_matches, metadata_type
import test_packager


class FakeZenodo:
    environment = 'sandbox'
    origin = 'https://sandbox.zenodo.org'

    def __init__(self):
        self.deposits = {}
        self.calls = []
        self.failure = None
        self.async_publish = False
        self.next_id = 100

    def trip(self, action, before=False):
        if self.failure == (action, before):
            self.failure = None
            raise RemoteError()

    def get(self, dep):
        self.calls.append(('get', dep))
        return copy.deepcopy(self.deposits[dep])

    def create(self, metadata):
        self.calls.append(('create', None))
        self.trip('create', True)
        self.next_id += 1
        dep = {'id':self.next_id, 'metadata':copy.deepcopy(metadata), 'files':[], 'submitted':False,
               'state':'unsubmitted', 'links':{'bucket':self.origin+'/api/files/fixture'}}
        self.deposits[dep['id']] = dep
        self.trip('create')
        return copy.deepcopy(dep)

    def newversion(self, dep):
        self.calls.append(('newversion', dep))
        self.trip('newversion', True)
        self.next_id += 1
        result = copy.deepcopy(self.deposits[dep])
        result.update(id=self.next_id, submitted=False, state='unsubmitted')
        self.deposits[dep]['links']['latest_draft'] = self.origin+'/api/deposit/depositions/'+str(self.next_id)
        self.deposits[self.next_id] = result
        self.trip('newversion')
        return copy.deepcopy(result)

    def update(self, dep, metadata):
        self.calls.append(('metadata', dep))
        self.trip('metadata', True)
        self.deposits[dep]['metadata'] = copy.deepcopy(metadata)
        self.trip('metadata')
        return self.get(dep)

    def upload(self, remote, name, data):
        self.calls.append(('upload', name))
        self.trip('upload', True)
        dep = self.deposits[remote['id']]
        dep['files'].append({'filename':name,'filesize':len(data),'checksum':hashlib.md5(data).hexdigest(),'id':'file-'+str(len(dep['files']))})
        self.trip('upload')
        return {}

    def delete_file(self, dep, file_id):
        self.calls.append(('delete_inherited', file_id))
        self.trip('delete_inherited', True)
        self.deposits[dep]['files'] = [f for f in self.deposits[dep]['files'] if f['id'] != file_id]
        self.trip('delete_inherited')

    def publish(self, dep):
        self.calls.append(('publish', dep))
        self.trip('publish', True)
        if not self.async_publish:
            self.deposits[dep].update(submitted=True, state='done')
        self.trip('publish')
        return {}

    def find_marker(self, marker):
        return [self.get(k) for k,v in self.deposits.items() if marker in v['metadata']['description']]

    def published(self, remote):
        record = self.get(remote['id'])
        metadata = record['metadata']
        kind = metadata.pop('upload_type')
        resource = {'type': kind, 'title': kind.title()}
        if kind in ('publication', 'image'):
            resource['subtype'] = metadata.pop(kind + '_type')
        metadata['resource_type'] = resource
        metadata['license'] = {'id': metadata['license']}
        record['files'] = [{'key': f['filename'], 'size': f['filesize'],
                            'checksum': 'md5:' + f['checksum']} for f in record['files']]
        return record, {'version_doi':'10.5072/zenodo.'+str(remote['id']),
            'concept_doi':'10.5072/zenodo.100','record_url':self.origin+'/records/'+str(remote['id']),
            'verified_at':'2026-11-04T00:00:00+00:00'}


class PublisherTests(unittest.TestCase):
    def setUp(self):
        # Reuse a real temporary Git/bundle fixture without inheriting its tests.
        self.fixture = test_packager.PackagerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.metadata = {'title':'Synthetic test only', 'description':'Synthetic research fixture',
                         'upload_type':'software','creators':[{'name':'Fixture, Test'}],
                         'access_right':'open','license':'mit','version':'1.0','publication_date':'2026-11-04'}
        self.fixture.write('meta.json', encode(self.metadata))
        self.fixture.commit()
        self.fixture.run_pack()
        self.bundle_dir = self.root/'out'
        self.bundle_hash = digest((self.bundle_dir/'receipt.json').read_bytes())
        self.bundle = read_bundle(self.bundle_dir, self.bundle_hash)
        self.api = FakeZenodo()
        self.store = FileStore(self.root/'registry.json')

    def service(self, operation='study-1', bundle=None, expected=None):
        registry = Registry(self.store, 42, 'sandbox')
        return Publisher(registry, self.api, bundle or self.bundle, expected or self.bundle_hash, operation)

    def mutation_count(self, action):
        return sum(1 for name, _ in self.api.calls if name == action)

    def test_stage_publish_and_repeat_are_idempotent(self):
        staged = self.service().run('stage')
        self.assertEqual(staged['status'], 'staged')
        self.assertNotIn('version_doi', staged['records']['research'])
        self.service().run('stage')
        published = self.service().run('publish')
        self.assertEqual(published['status'], 'published')
        self.service().run('publish')
        self.assertEqual(self.mutation_count('create'), 1)
        self.assertEqual(self.mutation_count('upload'), 1)
        self.assertEqual(self.mutation_count('publish'), 1)

    def test_lost_create_reply_recovers_by_unique_marker(self):
        self.api.failure = ('create', False)
        with self.assertRaises(PublicationIncomplete):
            self.service().run('stage')
        self.assertEqual(self.service().run('stage')['status'], 'staged')
        self.assertEqual(self.mutation_count('create'), 1)

    def test_missing_create_outcome_never_replays_post(self):
        self.api.failure = ('create', True)
        for _ in range(2):
            with self.assertRaises(PublicationIncomplete):
                self.service().run('stage')
        self.assertEqual(self.mutation_count('create'), 1)

    def test_duplicate_create_marker_is_not_adopted(self):
        self.api.failure = ('create', False)
        with self.assertRaises(PublicationIncomplete):
            self.service().run('stage')
        self.api.deposits[999] = copy.deepcopy(self.api.deposits[101])
        self.api.deposits[999]['id'] = 999
        with self.assertRaises(PublicationIncomplete):
            self.service().run('reconcile')
        self.assertEqual(self.mutation_count('create'), 1)

    def test_lost_upload_reply_uses_readback(self):
        self.api.failure = ('upload', False)
        with self.assertRaises(PublicationIncomplete):
            self.service().run('stage')
        self.assertEqual(self.service().run('stage')['status'], 'staged')
        self.assertEqual(self.mutation_count('upload'), 1)

    def test_missing_upload_needs_explicit_digest_bound_retry(self):
        self.api.failure = ('upload', True)
        with self.assertRaises(PublicationIncomplete):
            self.service().run('stage')
        with self.assertRaises(PublicationIncomplete):
            self.service().run('stage')
        self.assertEqual(self.mutation_count('upload'), 1)
        state, _ = self.store.read()
        with self.assertRaises(ValueError):
            self.service().recover('research', '0'*64, retry=True)
        self.service().recover('research', digest(encode(state)), retry=True)
        self.assertEqual(self.service().run('stage')['status'], 'staged')
        self.assertEqual(self.mutation_count('upload'), 2)

    def test_lost_publish_reply_does_not_publish_twice(self):
        self.service().run('stage')
        self.api.failure = ('publish', False)
        with self.assertRaises(PublicationIncomplete):
            self.service().run('publish')
        self.assertEqual(self.service().run('reconcile')['status'], 'published')
        self.service().run('publish')
        self.assertEqual(self.mutation_count('publish'), 1)

    def test_async_publish_requires_reconciliation(self):
        self.service().run('stage')
        self.api.async_publish = True
        with self.assertRaises(PublicationIncomplete) as failure:
            self.service().run('publish')
        self.assertEqual(failure.exception.receipt['records']['research']['status'], 'publishing')
        with self.assertRaises(PublicationIncomplete):
            self.service().run('publish')
        self.assertEqual(self.mutation_count('publish'), 1)
        self.api.deposits[101].update(state='done', submitted=True)
        self.assertEqual(self.service().run('reconcile')['status'], 'published')

    def test_foreign_file_and_metadata_edits_block_publish(self):
        self.service().run('stage')
        self.api.deposits[101]['files'].append({'filename':'foreign.txt','checksum':'0'*32,'filesize':1})
        with self.assertRaises(PublicationIncomplete):
            self.service().run('publish')
        self.api.deposits[101]['files'].pop()
        self.api.deposits[101]['metadata']['title'] = 'changed'
        with self.assertRaises(PublicationIncomplete):
            self.service().run('publish')
        self.assertEqual(self.mutation_count('publish'), 0)

    def test_same_receipt_different_operation_rejected(self):
        self.service().run('stage')
        with self.assertRaises(ValueError):
            self.service('duplicate').run('stage')

    def test_registry_lock_and_environment_guard(self):
        registry = Registry(self.store, 42, 'sandbox')
        with registry.session():
            with self.assertRaises(ValueError):
                self.service().run('stage')
        with self.assertRaises(ValueError):
            Registry(self.store, 43, 'sandbox')
        with self.assertRaises(ValueError):
            Registry(self.store, 42, 'production')

    def test_stale_registry_cas_rejected(self):
        first = Registry(self.store, 42, 'sandbox')
        second = Registry(self.store, 42, 'sandbox')
        first.save()
        with self.assertRaises(ValueError):
            second.save()

    def next_bundle(self, version=2):
        self.fixture.write('code/main.py', f'print("version {version}")\n'.encode())
        self.metadata['version'] = f'{version}.0'
        self.fixture.write('meta.json', encode(self.metadata))
        self.fixture.commit()
        self.fixture.run_pack(f'version-{version}')
        path=self.root/f'version-{version}'
        expected=digest((path/'receipt.json').read_bytes())
        return read_bundle(path, expected), expected

    def test_new_version_replaces_only_verified_inherited_bytes(self):
        self.service().run('stage')
        self.service().run('publish')
        bundle, expected = self.next_bundle()
        result=self.service('study-2', bundle, expected).run('stage')
        self.assertEqual(result['status'], 'staged')
        self.assertEqual(self.mutation_count('newversion'), 1)
        self.assertEqual(self.mutation_count('delete_inherited'), 1)
        self.assertTrue(self.api.deposits[101]['submitted'])
        self.assertEqual(self.api.deposits[101]['metadata']['version'], '1.0')
        self.assertEqual(self.api.deposits[102]['metadata']['version'], '2.0')

    def test_historical_receipts_preserve_tip_and_allow_three_versions(self):
        self.service().run('stage')
        self.service().run('publish')
        second, second_hash = self.next_bundle()
        self.service('study-2', second, second_hash).run('stage')
        self.service('study-2', second, second_hash).run('publish')
        for phase in ('receipt', 'reconcile', 'publish'):
            self.assertEqual(self.service().run(phase)['status'], 'published')
            self.assertEqual(self.store.read()[0]['latest']['research'], 102)
        third, third_hash = self.next_bundle(3)
        self.service('study-3', third, third_hash).run('stage')
        self.assertEqual(self.service('study-3', third, third_hash).run('publish')['status'], 'published')
        for service in (self.service('study-2', second, second_hash), self.service(),
                        self.service('study-3', third, third_hash), self.service()):
            self.assertEqual(service.run('reconcile')['status'], 'published')
            self.assertEqual(self.store.read()[0]['latest']['research'], 103)
        self.assertEqual(self.mutation_count('publish'), 3)
        self.assertEqual(self.mutation_count('newversion'), 2)

    def test_unrelated_latest_is_not_overwritten(self):
        self.service().run('stage')
        self.service().run('publish')
        registry = Registry(self.store, 42, 'sandbox')
        registry.data['latest']['research'] = 999
        registry.save()
        with self.assertRaises(PublicationIncomplete):
            self.service().run('receipt')
        self.assertEqual(self.store.read()[0]['latest']['research'], 999)

    def test_record_type_and_subtype_are_verified_with_other_metadata(self):
        for kind, subtype in (('software', None), ('publication', 'article'), ('image', 'diagram')):
            desired = {**self.metadata, 'upload_type': kind}
            if subtype:
                desired[kind + '_type'] = subtype
            actual = {k: v for k, v in desired.items() if k not in
                      ('upload_type', 'publication_type', 'image_type')}
            actual['resource_type'] = {'type': kind, 'title': 'Display label'}
            if subtype:
                actual['resource_type']['subtype'] = subtype
            actual['license'] = {'id': 'mit'}
            self.assertTrue(metadata_matches(actual, desired))
            actual['title'] = 'Foreign edit'
            self.assertFalse(metadata_matches(actual, desired))
            actual['title'] = desired['title']
            actual['resource_type'] = {'type': 'dataset'}
            self.assertFalse(metadata_matches(actual, desired))
            if subtype:
                actual['resource_type'] = {'type': kind, 'subtype': 'other'}
                self.assertFalse(metadata_matches(actual, desired))

    def test_invalid_and_conflicting_type_representations_rejected(self):
        invalid = [{}, {'upload_type': 'unknown'}, {'upload_type': 'publication'},
                   {'upload_type': 'software', 'image_type': 'figure'},
                   {'resource_type': {'type': 'image', 'subtype': 'article'}},
                   {'resource_type': {'type': 'software', 'subtype': 'other'}},
                   {'resource_type': {'type': 'software', 'unexpected': True}},
                   {'resource_type': 'software'},
                   {'upload_type': 'software', 'resource_type': {'type': 'dataset'}}]
        for metadata in invalid:
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                metadata_type(metadata)

    def test_lost_new_version_reply_requires_explicit_adoption(self):
        self.service().run('stage')
        self.service().run('publish')
        bundle, expected = self.next_bundle()
        self.api.failure=('newversion', False)
        with self.assertRaises(PublicationIncomplete):
            self.service('study-2',bundle,expected).run('stage')
        with self.assertRaises(PublicationIncomplete):
            self.service('study-2',bundle,expected).run('stage')
        state,_=self.store.read()
        self.service('study-2',bundle,expected).recover('research',digest(encode(state)),adoption_id=102)
        self.assertEqual(self.service('study-2',bundle,expected).run('stage')['status'], 'staged')
        self.assertEqual(self.mutation_count('newversion'), 1)

    def test_partial_publication_preserves_success_and_resumes_other_record(self):
        manifest = self.fixture.manifest
        manifest['packages']['proof'] = copy.deepcopy(manifest['packages']['research'])
        manifest['packages']['proof']['filename'] = 'proof.zip'
        manifest['records']['zproof'] = {'packages':['proof'],'metadata_file':'meta.json','access':'public'}
        self.fixture.commit()
        self.fixture.run_pack('multi')
        self.bundle_dir = self.root/'multi'
        self.bundle_hash = digest((self.bundle_dir/'receipt.json').read_bytes())
        self.bundle = read_bundle(self.bundle_dir,self.bundle_hash)
        self.service().run('stage')
        old = self.api.deposits[102]['metadata']['title']
        self.api.deposits[102]['metadata']['title'] = 'foreign edit'
        with self.assertRaises(PublicationIncomplete) as failed:
            self.service().run('publish')
        self.assertEqual(failed.exception.receipt['status'],'partial')
        self.assertEqual(failed.exception.receipt['records']['research']['status'],'published')
        self.assertNotIn('version_doi',failed.exception.receipt['records']['zproof'])
        self.api.deposits[102]['metadata']['title'] = old
        self.assertEqual(self.service().run('publish')['status'],'published')
        self.assertEqual(self.mutation_count('publish'),2)

    def test_published_verification_failure_does_not_emit_fresh_success(self):
        self.service().run('stage')
        self.service().run('publish')
        self.api.deposits[101]['metadata']['title'] = 'foreign edit'
        with self.assertRaises(PublicationIncomplete) as failed:
            self.service().run('receipt')
        self.assertEqual(failed.exception.receipt['records']['research']['status'],'outcome_unknown')
        self.assertNotIn('version_doi',failed.exception.receipt['records']['research'])

    def test_hard_crash_lock_requires_exact_manual_unlock(self):
        registry=Registry(self.store,42,'sandbox')
        registry.data['owner']='stopped-runner'
        registry.save()
        with self.assertRaises(ValueError):
            self.service().run('stage')
        fresh=Registry(self.store,42,'sandbox')
        with self.assertRaises(ValueError):
            fresh.unlock('0'*64)
        fresh.unlock(digest(encode(fresh.data)))
        self.assertEqual(self.service().run('stage')['status'],'staged')

    def test_cli_stage_context_and_output(self):
        context = {'schema':'publication-context/v1','kind':'research','repository_id':42,
                   'source_sha':self.bundle['receipt']['source_sha'],'control_sha':'a'*40,
                   'producer_run_id':1,'producer_run_attempt':1,'producer_artifact_id':2,'artifact_sha256':'b'*64}
        context_path=self.root/'context.json'
        context_path.write_bytes(encode(context))
        out=self.root/'publication.json'
        args=['publisher.py','--phase','stage','--bundle',str(self.bundle_dir),'--expected-receipt-sha256',self.bundle_hash,
              '--operation-id','study-1','--repository-id','42','--environment','sandbox','--context',str(context_path),
              '--registry-file',str(self.root/'registry.json'),'--output',str(out)]
        with patch.object(sys,'argv',args), patch.dict(os.environ,{'ZENODO_TOKEN':'synthetic-secret'}), patch('publisher.Zenodo',return_value=self.api), patch('builtins.print'):
            main()
        self.assertEqual(json.loads(out.read_bytes())['status'],'staged')
        context['kind']='external-inputs'
        with self.assertRaises(ValueError):
            validate_context(context,self.bundle,42)

    def test_new_control_commit_can_resume_same_producer(self):
        context={'schema':'publication-context/v1','kind':'research','repository_id':42,
                 'source_sha':self.bundle['receipt']['source_sha'],'control_sha':'a'*40,
                 'producer_run_id':1,'producer_run_attempt':1,'producer_artifact_id':2,'artifact_sha256':'b'*64}
        service=self.service()
        service.context=context
        service.run('stage')
        service=self.service()
        service.context={**context,'control_sha':'c'*40}
        self.assertEqual(service.run('publish')['status'],'published')
        service=self.service()
        service.context={**context,'producer_artifact_id':99}
        with self.assertRaises(ValueError):
            service.run('receipt')

    def test_foreign_new_version_metadata_not_overwritten(self):
        self.service().run('stage')
        self.service().run('publish')
        bundle,expected=self.next_bundle()
        self.api.failure=('newversion',False)
        with self.assertRaises(PublicationIncomplete):
            self.service('study-2',bundle,expected).run('stage')
        self.api.deposits[102]['metadata']['title']='foreign title'
        state,_=self.store.read()
        with self.assertRaises(ValueError):
            self.service('study-2',bundle,expected).recover('research',digest(encode(state)),adoption_id=102)
        self.assertEqual(self.mutation_count('metadata'),0)

    def test_package_tamper_prevents_api_calls(self):
        (self.bundle_dir/'research.zip').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            read_bundle(self.bundle_dir, self.bundle_hash)
        self.assertEqual(self.api.calls, [])


if __name__ == '__main__':
    unittest.main()
