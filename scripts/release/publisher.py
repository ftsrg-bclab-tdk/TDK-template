#!/usr/bin/env python3
"""Stage, reconcile and publish verified bundles; never execute research source."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import io
import os
from pathlib import Path
import re
import urllib.parse
import zipfile

from packager import (MAX_BYTES, check_members, digest, encode, local_file, parse,
                      runtime_evidence, schema_validate, validate)
from publication_io import FileStore, GitHubStore, HTTP, Registry, RemoteError

ORIGINS = {'sandbox': 'https://sandbox.zenodo.org', 'production': 'https://zenodo.org'}


def now():
    return datetime.now(timezone.utc).isoformat()


def positive_id(value):
    if isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0:
        raise ValueError('Positive resource ID required')
    return int(value)


def hash_value(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('SHA-256 required')
    return value


def read_bundle(directory, expected):
    """Revalidate exact reviewed bytes; no extraction or selected-code execution."""
    raw = local_file(directory, 'receipt.json')
    if digest(raw) != hash_value(expected):
        raise ValueError('Reviewed bundle receipt digest mismatch')
    receipt = parse(raw)
    if receipt.get('schema') != 'release-bundle/v1' or not re.fullmatch(r'[0-9a-f]{40,64}', receipt.get('source_sha', '')):
        raise ValueError('Invalid release bundle receipt')
    manifest_raw = local_file(directory, 'manifest.json')
    if digest(manifest_raw) != receipt['manifest_sha256']:
        raise ValueError('Manifest digest mismatch')
    manifest = parse(manifest_raw)
    validate(manifest)
    runtime_raw = local_file(directory, 'runtime.json')
    if digest(runtime_raw) != receipt['runtime_sha256']:
        raise ValueError('Runtime digest mismatch')
    runtime_evidence(runtime_raw)
    if receipt.get('build_receipt_sha256'):
        if digest(local_file(directory, 'build-receipt.json')) != receipt['build_receipt_sha256']:
            raise ValueError('Build receipt digest mismatch')
    if receipt.get('references') != manifest.get('references', {}):
        raise ValueError('Reference bindings differ')
    for key, binding in manifest.get('references', {}).items():
        ref_raw = local_file(directory, 'references/' + key + '.json')
        if digest(ref_raw) != binding['receipt_sha256']:
            raise ValueError('Acceptance receipt digest mismatch')
        reference = parse(ref_raw)
        schema_validate('external-inputs.schema.json', reference)
        if reference['package_sha256'] != binding['package_sha256']:
            raise ValueError('Acceptance package digest mismatch')
    if set(receipt['packages']) != set(manifest['packages']) or set(receipt['records']) != set(manifest['records']):
        raise ValueError('Bundle/manifest keys differ')
    archives = {}
    for key, package in manifest['packages'].items():
        expected_package = receipt['packages'][key]
        if expected_package['filename'] != package['filename']:
            raise ValueError('Package filename mismatch')
        archive = local_file(directory, package['filename'])
        if len(archive) != expected_package['size'] or digest(archive) != expected_package['sha256']:
            raise ValueError('Package bytes differ from reviewed receipt')
        inventory = expected_package['files']
        if len(inventory) != len(package['files']):
            raise ValueError('Package inventory length mismatch')
        for declaration, item in zip(package['files'], inventory):
            if any(item.get(k) != v for k, v in declaration.items()):
                raise ValueError('Selected member binding differs')
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            infos = zf.infolist()
            check_members([x.filename for x in infos])
            if len(infos) > 2048 or sum(x.file_size for x in infos) > MAX_BYTES:
                raise ValueError('Package expansion bound exceeded')
            if set(zf.namelist()) != {f['archive_path'] for f in inventory} | {'PROVENANCE.json'}:
                raise ValueError('Unexpected package members')
            for item in inventory:
                data = zf.read(item['archive_path'])
                if len(data) != item['size'] or digest(data) != item['sha256']:
                    raise ValueError('Package member digest mismatch')
            provenance = parse(zf.read('PROVENANCE.json'))
            if (provenance.get('source_sha') != receipt['source_sha']
                    or provenance.get('manifest_sha256') != receipt['manifest_sha256']
                    or provenance.get('runtime_sha256') != receipt['runtime_sha256']
                    or provenance.get('files') != inventory):
                raise ValueError('Package provenance differs')
        archives[package['filename']] = archive
    metadata = {}
    for key, record in manifest['records'].items():
        stored = receipt['records'][key]
        if any(stored.get(k) != v for k, v in record.items()):
            raise ValueError('Record binding differs')
        data = local_file(directory, 'metadata/' + key + '.json')
        if digest(data) != stored['metadata_sha256']:
            raise ValueError('Record metadata digest mismatch')
        metadata[key] = parse(data)
    return {'receipt': receipt, 'manifest': manifest, 'archives': archives, 'metadata': metadata}


def desired_metadata(bundle, key, marker):
    metadata = copy.deepcopy(bundle['metadata'][key])
    if not isinstance(metadata, dict):
        raise ValueError('Metadata must be an object')
    for name in ('title', 'description', 'upload_type', 'version', 'publication_date'):
        if not isinstance(metadata.get(name), str) or not metadata[name].strip():
            raise ValueError('Missing explicit Zenodo metadata: ' + name)
    if not metadata.get('creators') or not all(isinstance(c, dict) and c.get('name') for c in metadata['creators']):
        raise ValueError('Named creators required')
    if 'doi' in metadata or 'prereserve_doi' in metadata:
        raise ValueError('Do not inherit an old or reserved DOI into new-version metadata')
    access = bundle['manifest']['records'][key]['access']
    if metadata.get('access_right') != {'public': 'open', 'restricted': 'restricted', 'embargoed': 'embargoed'}[access]:
        raise ValueError('Metadata access differs from selected record')
    if access != 'restricted' and not metadata.get('license'):
        raise ValueError('Explicit record license required')
    if access == 'restricted' and not metadata.get('access_conditions'):
        raise ValueError('Restricted access conditions required')
    if access == 'embargoed' and not metadata.get('embargo_date'):
        raise ValueError('Explicit embargo date required')
    metadata['description'] += '\n<p>' + marker + '</p>'
    return metadata


def metadata_matches(actual, desired):
    for key, value in desired.items():
        observed = actual.get(key)
        if key == 'license' and isinstance(observed, dict):
            observed = observed.get('id')
        if observed != value:
            return False
    return True


def copied_metadata_matches(actual, previous):
    # Zenodo reserves a different DOI for a new version. All other copied
    # fields must still match the observed parent before we replace metadata.
    ignored = {'doi', 'prereserve_doi'}
    return ({k:v for k,v in actual.items() if k not in ignored}
            == {k:v for k,v in previous.items() if k not in ignored})


def file_map(remote):
    result = {}
    for item in remote.get('files', []):
        name = item.get('filename', item.get('key'))
        if not isinstance(name, str) or name in result:
            raise ValueError('Invalid or duplicate remote file')
        result[name] = item
    return result


def file_matches(item, data):
    checksum = item.get('checksum', '')
    if re.fullmatch(r'[0-9a-f]{32}', checksum):
        checksum = 'md5:' + checksum
    size = item.get('filesize', item.get('size'))
    return (str(size) == str(len(data)) and checksum == 'md5:' + hashlib.md5(data).hexdigest())


class Zenodo:
    def __init__(self, http, environment):
        self.http, self.environment = http, environment
        self.origin = ORIGINS[environment]

    def get(self, deposition_id):
        return self.http.request('GET', '/api/deposit/depositions/' + str(positive_id(deposition_id)))

    def create(self, metadata):
        return self.http.request('POST', '/api/deposit/depositions', value={'metadata': metadata})

    def update(self, deposition_id, metadata):
        return self.http.request('PUT', '/api/deposit/depositions/' + str(positive_id(deposition_id)), value={'metadata': metadata})

    def newversion(self, deposition_id):
        result = self.http.request('POST', '/api/deposit/depositions/' + str(positive_id(deposition_id)) + '/actions/newversion')
        # Response is the OLD deposition. Follow only a validated API link.
        url = result['links']['latest_draft']
        self.check_api_link(url, 'deposit/depositions')
        return self.http.request('GET', url)

    def check_api_link(self, url, resource):
        self.http.url(url)
        if not re.fullmatch(re.escape(self.origin) + '/api/' + resource + '/[A-Za-z0-9-]+', url):
            raise ValueError('Unexpected API link')

    def upload(self, remote, name, data):
        bucket = remote['links']['bucket']
        self.check_api_link(bucket, 'files')
        return self.http.request('PUT', bucket + '/' + urllib.parse.quote(name, safe=''), data=data)

    def delete_file(self, deposition_id, file_id):
        if not isinstance(file_id, str) or not re.fullmatch(r'[A-Za-z0-9-]+', file_id):
            raise ValueError('Invalid file ID')
        return self.http.request('DELETE', '/api/deposit/depositions/' + str(positive_id(deposition_id)) + '/files/' + file_id)

    def publish(self, deposition_id):
        return self.http.request('POST', '/api/deposit/depositions/' + str(positive_id(deposition_id)) + '/actions/publish')

    def find_marker(self, marker):
        matches = []
        for page in range(1, 101):
            values = self.http.request('GET', f'/api/deposit/depositions?page={page}&size=100')
            if not isinstance(values, list):
                raise ValueError('Unexpected deposition listing')
            matches.extend(v for v in values if marker in v.get('metadata', {}).get('description', ''))
            if len(values) < 100:
                return matches
        raise ValueError('Deposit listing bound reached; manual reconciliation required')

    def published(self, remote):
        rid = positive_id(remote.get('record_id') or remote['id'])
        record = self.http.request('GET', '/api/records/' + str(rid))
        if not (record.get('status') == 'published' or (record.get('submitted') is True and record.get('state') == 'done')):
            raise ValueError('Record not verified published yet')
        doi = record.get('doi')
        concept = record.get('conceptdoi')
        if not all(isinstance(v, str) and re.fullmatch(r'10\.[0-9]{4,9}/[^\s{}\\]+', v) for v in (doi, concept)):
            raise ValueError('Published identifiers unavailable')
        return record, {'record_url': self.origin + '/records/' + str(rid), 'version_doi': doi,
                        'concept_doi': concept, 'verified_at': now()}


class Publisher:
    def __init__(self, registry, api, bundle, expected_digest, operation_id, context=None):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', operation_id):
            raise ValueError('Invalid operation ID')
        self.registry, self.api, self.bundle = registry, api, bundle
        self.operation_id = operation_id
        self.expected = hash_value(expected_digest)
        self.context = context
        self.op = None
        self.desired = {}
        for key in bundle['manifest']['records']:
            marker = f'tdk-release:{registry.data["repository_id"]}:{operation_id}:{key}:{expected_digest}'
            self.desired[key] = desired_metadata(bundle, key, marker)

    def init(self):
        operations = self.registry.data['operations']
        if self.operation_id in operations:
            self.op = operations[self.operation_id]
            if self.op['bundle_receipt_sha256'] != self.expected or self.op['source_sha'] != self.bundle['receipt']['source_sha']:
                raise ValueError('Operation already bound to different reviewed bytes')
            if self.context and self.op.get('context'):
                if any(self.context.get(k) != self.op['context'].get(k) for k in ('repository_id', 'source_sha', 'producer_run_id', 'producer_run_attempt', 'producer_artifact_id', 'artifact_sha256')):
                    raise ValueError('Producer context changed; resume the same verified candidate')
                if self.context not in self.op.setdefault('context_history', []):
                    self.op['context_history'].append(self.context)
                    self.registry.save()
            return
        # A new run ID is not a new publication intent for the same receipt.
        if any(o['bundle_receipt_sha256'] == self.expected for o in operations.values()):
            raise ValueError('Receipt already registered; resume its existing operation ID')
        keys = set(self.desired)
        for other in operations.values():
            if any(k in keys and r['status'] != 'published' for k, r in other['records'].items()):
                raise ValueError('Another operation already owns this record')
        self.op = {'bundle_receipt_sha256': self.expected, 'source_sha': self.bundle['receipt']['source_sha'],
                   'context': self.context, 'records': {k: {'status': 'planned', 'deposition_id': None,
                   'previous_id': self.registry.data['latest'].get(k), 'pending': None} for k in keys}}
        operations[self.operation_id] = self.op
        self.registry.save()

    def expected_files(self, key):
        keys = self.bundle['manifest']['records'][key]['packages']
        return {self.bundle['receipt']['packages'][k]['filename']: self.bundle['archives'][self.bundle['receipt']['packages'][k]['filename']] for k in keys}

    def mutation(self, state, action, call, detail=None):
        state['pending'] = {'action': action, 'detail': detail, 'started_at': now()}
        state['status'] = 'outcome_unknown'
        self.registry.save()  # Must be durable BEFORE remote write.
        result = call()  # No retry here, including 4xx; reconciliation owns recovery.
        return result

    def verify_files(self, key, remote, complete):
        expected, actual = self.expected_files(key), file_map(remote)
        if set(actual) - set(expected):
            raise ValueError('Unexpected remote file; do not delete foreign edits')
        for name, item in actual.items():
            if not file_matches(item, expected[name]):
                raise ValueError('Remote file differs; do not silently replace it')
        if complete and set(actual) != set(expected):
            raise ValueError('Remote package inventory incomplete')
        return set(expected) - set(actual)

    def reconcile_record(self, key):
        state = self.op['records'][key]
        pending = state.get('pending')
        if pending and pending['action'] == 'delete_inherited':
            self.reconcile_inherited(key)
            return self.api.get(state['deposition_id'])
        marker = self.desired[key]['description'].split('<p>')[-1].removesuffix('</p>')
        if not state['deposition_id']:
            if not pending:
                return
            if pending['action'] == 'create':
                matches = self.api.find_marker(marker)
                if len(matches) != 1:
                    raise ValueError('Create outcome unresolved; no automatic POST replay')
                state['deposition_id'] = positive_id(matches[0]['id'])
                state['pending'] = None
                state['status'] = 'draft'
                self.registry.save()
            else:
                raise ValueError('New-version outcome unresolved; explicit reviewed adoption required')
        remote = self.api.get(state['deposition_id'])
        if not metadata_matches(remote.get('metadata', {}), self.desired[key]):
            # A successful newversion returns copied OLD metadata; only our saved
            # ID and pending metadata action permit the single planned update.
            if state.get('status') == 'new_version_created':
                return remote
            raise ValueError('Remote metadata differs from reviewed operation')
        missing = self.verify_files(key, remote, complete=False)
        reserved = remote.get('metadata', {}).get('prereserve_doi', {})
        if isinstance(reserved, dict) and reserved.get('doi'):
            state['reserved_doi'] = reserved['doi']
        if remote.get('submitted') is True and remote.get('state') == 'done':
            if missing:
                raise ValueError('Published record missing reviewed files')
            record, fields = self.api.published(remote)
            self.verify_files(key, record, complete=True)
            if not metadata_matches(record.get('metadata', {}), self.desired[key]):
                raise ValueError('Published metadata not yet verified against reviewed operation')
            state.update(fields, status='published', pending=None)
            self.registry.data['latest'][key] = state['deposition_id']
        elif pending and pending['action'] == 'publish':
            state['status'] = 'publishing'
            # Keep pending: absence of publication isn't proof POST wasn't accepted.
        elif pending and pending['action'] == 'upload' and pending['detail'] in missing:
            state['status'] = 'outcome_unknown'
            raise ValueError('Upload outcome unresolved; explicit retry after reconciliation required')
        else:
            state['status'] = 'draft' if missing else 'staged'
            state['pending'] = None
        self.registry.save()
        return remote

    def stage_record(self, key):
        state = self.op['records'][key]
        if state.get('pending') and state['pending']['action'] == 'delete_inherited':
            self.reconcile_inherited(key)
        if state.get('pending'):
            self.reconcile_record(key)
            if state.get('pending'):
                raise ValueError('Operation mutation still unresolved')
        if not state['deposition_id']:
            previous = state['previous_id']
            if previous:
                prior = self.api.get(previous)
                if prior.get('state') != 'done' or prior.get('submitted') is not True:
                    raise ValueError('Previous deposition not published')
                draft = prior.get('links', {}).get('latest_draft')
                if draft and not draft.rstrip('/').endswith('/' + str(previous)):
                    raise ValueError('Existing latest draft must be reconciled explicitly')
                state['inherited_files'] = file_map(prior)
                state['previous_metadata'] = prior.get('metadata', {})
                result = self.mutation(state, 'newversion', lambda: self.api.newversion(previous))
                if positive_id(result['id']) == previous:
                    raise ValueError('Newversion did not return a new draft')
                state.update(deposition_id=positive_id(result['id']), status='new_version_created', pending=None)
                self.registry.save()
            else:
                result = self.mutation(state, 'create', lambda: self.api.create(self.desired[key]))
                state.update(deposition_id=positive_id(result['id']), status='draft', pending=None)
                self.registry.save()
        if state['status'] == 'new_version_created':
            # Copied old files are never silently removed or replaced.
            remote = self.api.get(state['deposition_id'])
            if not copied_metadata_matches(remote.get('metadata', {}), state.get('previous_metadata', {})):
                raise ValueError('New-version metadata was edited outside this operation')
            self.clear_inherited(key, remote)
            self.mutation(state, 'metadata', lambda: self.api.update(state['deposition_id'], self.desired[key]))
            state.update(status='draft', pending=None)
            self.registry.save()
        remote = self.reconcile_record(key)
        if state['status'] == 'published':
            return
        for name in sorted(self.verify_files(key, remote, complete=False)):
            self.mutation(state, 'upload', lambda: self.api.upload(remote, name, self.expected_files(key)[name]), name)
            # Always read back inventory/checksum, even on successful PUT reply.
            self.reconcile_record(key)
            remote = self.api.get(state['deposition_id'])
        self.reconcile_record(key)
        if state['status'] != 'staged':
            raise ValueError('Record not completely staged')

    def reconcile_inherited(self, key):
        state = self.op['records'][key]
        remote = self.api.get(state['deposition_id'])
        if remote.get('submitted'):
            raise ValueError('Cannot clean inherited files on submitted record')
        pending = state['pending']
        if pending['detail'] in file_map(remote):
            raise ValueError('Delete outcome unresolved; explicit retry required')
        state.update(status='new_version_created', pending=None)
        self.registry.save()

    def clear_inherited(self, key, remote):
        state = self.op['records'][key]
        expected = self.expected_files(key)
        for name, item in file_map(remote).items():
            if name in expected and file_matches(item, expected[name]):
                continue
            previous = state.get('inherited_files', {}).get(name)
            if not previous or any(item.get(f) != previous.get(f) for f in ('checksum', 'filesize', 'size')):
                raise ValueError('Foreign new-version file differs from recorded inherited inventory')
            if remote.get('submitted'):
                raise ValueError('Cannot modify submitted record')
            self.mutation(state, 'delete_inherited', lambda: self.api.delete_file(state['deposition_id'], item['id']), name)
            self.reconcile_inherited(key)

    def recover(self, key, expected_registry_digest, adoption_id=None, retry=False):
        """Explicit operator recovery bound to observed state; never auto-dispatched."""
        if digest(encode(self.registry.data)) != expected_registry_digest:
            raise ValueError('Recovery requires exact observed registry state')
        with self.registry.session():
            self.init()
            state = self.op['records'][key]
            pending = state.get('pending')
            if not pending:
                raise ValueError('No ambiguous mutation to recover')
            action = pending['action']
            if action in ('create', 'newversion'):
                if adoption_id is None:
                    raise ValueError('Explicit deposition ID required for adoption')
                remote = self.api.get(positive_id(adoption_id))
                if remote.get('submitted'):
                    raise ValueError('Cannot adopt an already submitted unknown draft')
                if action == 'create':
                    if not metadata_matches(remote.get('metadata', {}), self.desired[key]):
                        raise ValueError('Adopted draft does not match operation marker/metadata')
                    status = 'draft'
                else:
                    previous = self.api.get(state['previous_id'])
                    target = previous.get('links', {}).get('latest_draft', '')
                    if (not target.endswith('/' + str(adoption_id)) or adoption_id == state['previous_id']
                            or not copied_metadata_matches(remote.get('metadata', {}), state.get('previous_metadata', {}))):
                        raise ValueError('New-version adoption lacks matching parent/copied metadata')
                    status = 'new_version_created'
                state.update(deposition_id=positive_id(adoption_id), status=status, pending=None)
            elif retry and action in ('upload', 'metadata', 'delete_inherited'):
                remote = self.api.get(state['deposition_id'])
                if remote.get('submitted'):
                    raise ValueError('Cannot retry mutation on submitted record')
                if action == 'upload':
                    if not metadata_matches(remote.get('metadata', {}), self.desired[key]):
                        raise ValueError('Metadata changed before retry')
                    missing = self.verify_files(key, remote, complete=False)
                    if pending['detail'] not in missing:
                        raise ValueError('Upload already exists; reconcile instead')
                    state.update(status='draft', pending=None)
                else:
                    if not copied_metadata_matches(remote.get('metadata', {}), state.get('previous_metadata', {})):
                        raise ValueError('Copied metadata changed before retry')
                    state.update(status='new_version_created', pending=None)
            else:
                raise ValueError('Mutation cannot be replayed; reconcile publication separately')
            self.registry.save()
            return self.receipt()

    def publish_record(self, key):
        state = self.op['records'][key]
        if state['status'] == 'planned':
            raise ValueError('Stage and review the operation before publishing')
        remote = self.reconcile_record(key)
        if state['status'] == 'published':
            return
        if state['status'] != 'staged' or state.get('pending'):
            raise ValueError('Publication is pending or record is not staged')
        self.verify_files(key, remote, complete=True)
        self.mutation(state, 'publish', lambda: self.api.publish(state['deposition_id']))
        state['status'] = 'publishing'
        self.registry.save()
        self.reconcile_record(key)
        if state['status'] != 'published':
            raise ValueError('Publication accepted but not verified yet; reconcile later')

    def run(self, phase):
        with self.registry.session():
            self.init()
            errors = {}
            for key in sorted(self.desired):
                try:
                    if phase == 'stage':
                        self.stage_record(key)
                    elif phase == 'publish':
                        self.publish_record(key)
                    elif phase in ('reconcile', 'receipt'):
                        self.reconcile_record(key)
                    else:
                        raise ValueError('Unknown phase')
                except (ValueError, RemoteError, KeyError, TypeError) as exc:
                    state = self.op['records'][key]
                    if state['status'] in ('staged', 'published', 'draft'):
                        state['status'] = 'outcome_unknown'
                        self.registry.save()
                    errors[key] = str(exc) if isinstance(exc, (ValueError, RemoteError)) else 'Unexpected API response; reconcile before retry'
            receipt = self.receipt()
            if errors:
                raise PublicationIncomplete(receipt, errors)
            return receipt

    def receipt(self):
        records = {}
        for key, state in self.op['records'].items():
            status = state['status']
            if status == 'new_version_created':
                status = 'draft'
            record = {'status': status, 'deposition_id': state['deposition_id'],
                      'packages': [{'filename': name, 'sha256': digest(data), 'size': len(data)} for name, data in sorted(self.expected_files(key).items())]}
            if state.get('reserved_doi'):
                record['reserved_doi'] = state['reserved_doi']
            if status == 'published':
                record.update(title=self.desired[key]['title'], version=self.desired[key]['version'],
                              publication_date=self.desired[key]['publication_date'],
                              creators=[c['name'] for c in self.desired[key]['creators']])
                record.update({k: state[k] for k in ('record_url', 'version_doi', 'concept_doi', 'verified_at')})
            records[key] = record
        statuses = [r['status'] for r in records.values()]
        result = {'schema': 'publication-receipt/v1', 'environment': self.registry.data['environment'],
                  'repository_id': self.registry.data['repository_id'], 'operation_id': self.operation_id,
                  'source_sha': self.op['source_sha'], 'bundle_receipt_sha256': self.expected,
                  'status': 'published' if all(s == 'published' for s in statuses) else 'staged' if all(s == 'staged' for s in statuses) else 'partial',
                  'records': records}
        schema_validate('publication-receipt.schema.json', result)
        return result


class PublicationIncomplete(RuntimeError):
    def __init__(self, receipt, errors):
        self.receipt, self.errors = receipt, errors
        super().__init__('Publication operation incomplete; inspect record states')


def validate_context(context, bundle, repository_id):
    if context.get('schema') != 'publication-context/v1' or context.get('kind') != 'research':
        raise ValueError('Publication context schema required')
    if context.get('repository_id') != repository_id or context.get('source_sha') != bundle['receipt']['source_sha']:
        raise ValueError('Context repository/source mismatch')
    if not re.fullmatch(r'[0-9a-f]{40,64}', context.get('control_sha', '')):
        raise ValueError('Control SHA required')
    for key in ('producer_run_id', 'producer_run_attempt', 'producer_artifact_id'):
        positive_id(context.get(key))
    hash_value(context.get('artifact_sha256'))
    return context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['stage', 'reconcile', 'publish', 'receipt', 'recover', 'unlock'], required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--expected-receipt-sha256', required=True)
    parser.add_argument('--operation-id', required=True)
    parser.add_argument('--repository-id', type=int, required=True)
    parser.add_argument('--environment', choices=list(ORIGINS), required=True)
    parser.add_argument('--context', type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--registry-file', type=Path)
    group.add_argument('--registry-github')
    parser.add_argument('--registry-ref')
    parser.add_argument('--registry-path', default='registry/zenodo.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--recover-record')
    parser.add_argument('--expected-registry-sha256')
    parser.add_argument('--adopt-deposition-id', type=int)
    parser.add_argument('--retry-missing-write', action='store_true')
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.bundle.resolve()) or args.output.resolve() == args.context.resolve():
        parser.error('Output must not overwrite verified candidate/context')
    if args.registry_file and args.output.resolve() == args.registry_file.resolve():
        parser.error('Output must not overwrite registry')
    bundle = read_bundle(args.bundle, args.expected_receipt_sha256)
    repository_id = positive_id(args.repository_id)
    context = validate_context(parse(args.context.read_bytes()), bundle, repository_id)
    token = os.environ.get('ZENODO_TOKEN')
    if not token:
        parser.error('ZENODO_TOKEN environment variable required')
    if args.registry_file:
        store = FileStore(args.registry_file)
    else:
        registry_token = os.environ.get('REGISTRY_GITHUB_TOKEN')
        if not registry_token:
            parser.error('Separate REGISTRY_GITHUB_TOKEN required')
        store = GitHubStore(HTTP('https://api.github.com', registry_token), args.registry_github,
                            args.registry_ref, args.registry_path, context['repository_id'])
    registry = Registry(store, repository_id, args.environment)
    api = Zenodo(HTTP(ORIGINS[args.environment], token), args.environment)
    service = Publisher(registry, api, bundle, args.expected_receipt_sha256, args.operation_id, context)
    try:
        if args.phase == 'unlock':
            registry.unlock(hash_value(args.expected_registry_sha256))
            args.output.write_bytes(encode({'schema':'publication-unlock/v1', 'status':'unlocked', 'repository_id':repository_id}))
            return
        if args.phase == 'recover':
            if not args.recover_record:
                parser.error('--recover-record required for explicit recovery')
            receipt = service.recover(args.recover_record, hash_value(args.expected_registry_sha256),
                                      args.adopt_deposition_id, args.retry_missing_write)
        else:
            receipt = service.run(args.phase)
    except PublicationIncomplete as exc:
        args.output.write_bytes(encode(exc.receipt))
        print(encode({'status': 'incomplete', 'errors': exc.errors}).decode(), end='')
        raise SystemExit(2)
    args.output.write_bytes(encode(receipt))
    print(encode({'status': receipt['status'], 'publication_receipt_sha256': digest(encode(receipt))}).decode(), end='')


if __name__ == '__main__':
    main()
