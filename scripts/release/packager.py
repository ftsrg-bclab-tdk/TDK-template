#!/usr/bin/env python3
"""Offline selective packager. Does not build, download, upload, or publish."""
import argparse
import hashlib
import io
import importlib.metadata
import platform
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import unicodedata
import zipfile

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
MAX_BYTES = 512 * 1024 * 1024  # Deliberate local v1 bound; no unbounded ZIP expansion.


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n').encode()


def parse(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique)


def safe_path(value):
    if (not isinstance(value, str) or not value or value.startswith('/')
            or any(ord(c) < 32 or ord(c) == 127 or c in '\\:' for c in value)
            or any(p in ('', '.', '..') for p in value.split('/'))):
        raise ValueError('Unsafe relative path: ' + repr(value))
    return value


def collision_key(path):
    return unicodedata.normalize('NFC', safe_path(path)).casefold()


def check_members(paths):
    keys = [collision_key(p) for p in paths]
    if len(keys) != len(set(keys)):
        raise ValueError('Archive name collision')
    for key in keys:
        parts = key.split('/')
        if any('/'.join(parts[:n]) in keys for n in range(1, len(parts))):
            raise ValueError('Archive file/directory collision')


def schema_validate(name, value):
    schema = parse((HERE / name).read_bytes())
    Draft202012Validator(schema).validate(value)


def validate(manifest):
    schema_validate('manifest.schema.json', manifest)
    packages = manifest['packages']
    check_members([p['filename'] for p in packages.values()])
    assigned = []
    for record in manifest['records'].values():
        safe_path(record['metadata_file'])
        for key in record['packages']:
            if key not in packages:
                raise ValueError('Unknown package')
            assigned.append(key)
    if set(assigned) != set(packages) or len(assigned) != len(set(assigned)):
        raise ValueError('Each package must belong to exactly one record')
    used_refs = set()
    for package in packages.values():
        check_members([f['archive_path'] for f in package['files']] + ['PROVENANCE.json'])
        for f in package['files']:
            safe_path(f['path'])
            if f['origin'] == 'built' and not package['build_profile']:
                raise ValueError('Generated files require a build profile')
            if f['origin'] == 'verified_reference':
                used_refs.add(f['reference'])
    if used_refs != set(manifest.get('references', {})):
        raise ValueError('Missing or unused reference binding')


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


class Snapshot:
    def __init__(self, repo, revision):
        self.repo = repo
        self.sha = git(repo, 'rev-parse', '--verify', '--end-of-options', revision + '^{commit}').decode().strip()
        self.files = {}
        for entry in git(repo, 'ls-tree', '-rz', self.sha).split(b'\0'):
            if not entry:
                continue
            info, name = entry.split(b'\t', 1)
            mode, kind, oid = info.decode().split()
            self.files[name.decode()] = (mode, kind, oid)

    def read(self, path):
        safe_path(path)
        entry = self.files.get(path)
        if not entry or entry[0] not in ('100644', '100755') or entry[1] != 'blob':
            raise ValueError('Missing/nonregular tracked file: ' + path)
        size = int(git(self.repo, 'cat-file', '-s', entry[2]))
        if size > MAX_BYTES:
            raise ValueError('Input exceeds v1 size bound')
        data = git(self.repo, 'cat-file', 'blob', entry[2])
        if data.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
            raise ValueError('Unmaterialized LFS pointer: ' + path)
        return data, 0o755 if entry[0] == '100755' else 0o644


def local_file(root, relative):
    safe_path(relative)
    if root is None:
        raise ValueError('Missing local input directory')
    current = Path(root)
    if current.is_symlink() or not current.is_dir():
        raise ValueError('Input root must be a real directory')
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Symlink local input')
    if not current.is_file() or current.stat().st_size > MAX_BYTES:
        raise ValueError('Missing/oversized regular input: ' + relative)
    return current.read_bytes()


def runtime_evidence(data):
    value = parse(data)
    if value.get('schema') != 'runtime-evidence/v1' or not value.get('tools'):
        raise ValueError('Runtime evidence needs schema and actual tool versions')
    if not all(isinstance(k, str) and isinstance(v, str) and v for k, v in value['tools'].items()):
        raise ValueError('Invalid tool versions')
    for image in value.get('images', []):
        if not image.get('platform') or not re.fullmatch(r'sha256:[0-9a-f]{64}', image.get('digest', '')):
            raise ValueError('Images need immutable digest and platform')
    return value


def reference_inputs(snapshot, manifest, root):
    result = {}
    for key, binding in manifest.get('references', {}).items():
        raw = local_file(root, binding['receipt_sha256'] + '.json')
        if digest(raw) != binding['receipt_sha256']:
            raise ValueError('Reference receipt digest mismatch')
        receipt = parse(raw)
        schema_validate('external-inputs.schema.json', receipt)
        source, _ = snapshot.read(binding['source_manifest'])
        if digest(source) != receipt['manifest_sha256'] or receipt['package_sha256'] != binding['package_sha256']:
            raise ValueError('Reference manifest/package binding mismatch')
        archive = local_file(root, binding['package_sha256'] + '.zip')
        if digest(archive) != binding['package_sha256']:
            raise ValueError('Reference package digest mismatch')
        inventory = {f['path']: f for f in receipt['files']}
        check_members([f['path'] for f in receipt['files']])
        content = {}
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            infos = zf.infolist()
            check_members([i.filename for i in infos])
            if set(inventory) != {i.filename for i in infos}:
                raise ValueError('Reference inventory mismatch')
            if sum(i.file_size for i in infos) > MAX_BYTES:
                raise ValueError('Expanded reference exceeds v1 size bound')
            for info in infos:
                mode = info.external_attr >> 16
                if info.is_dir() or stat.S_IFMT(mode) not in (0, stat.S_IFREG) or info.flag_bits & 1:
                    raise ValueError('Nonregular/encrypted reference member')
                data = zf.read(info)
                expected = inventory[info.filename]
                if len(data) != expected['size'] or digest(data) != expected['sha256']:
                    raise ValueError('Reference member digest/size mismatch')
                content[info.filename] = data
        if not receipt['redistribution']:
            raise ValueError('Reference receipt does not allow redistribution')
        result[key] = (receipt, content, raw)
    return result


def zip_bytes(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as zf:
        for name, (data, mode) in sorted(entries.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | mode) << 16
            zf.writestr(info, data)
    return stream.getvalue()


def prepare(repo, revision, manifest_path, runtime_path, out, built_dir=None,
            build_receipt_path=None, reference_dir=None):
    snapshot = Snapshot(repo, revision)
    manifest_raw, _ = snapshot.read(manifest_path)
    manifest = parse(manifest_raw)
    validate(manifest)
    runtime_raw = Path(runtime_path).read_bytes()
    runtime_evidence(runtime_raw)
    runtime_hash = digest(runtime_raw)
    build = None
    build_hash = None
    if build_receipt_path:
        build_raw = Path(build_receipt_path).read_bytes()
        build = parse(build_raw)
        build_hash = digest(build_raw)
        if (build.get('schema') != 'build-outputs/v1' or build.get('source_sha') != snapshot.sha
                or build.get('runtime_sha256') != runtime_hash):
            raise ValueError('Build evidence does not match source/runtime')
    references = reference_inputs(snapshot, manifest, reference_dir)
    records = {}
    metadata_bytes = {}
    access_for = {}
    for key, record in manifest['records'].items():
        raw, _ = snapshot.read(record['metadata_file'])
        metadata = parse(raw)
        if not isinstance(metadata, dict):
            raise ValueError('Record metadata must be an object')
        records[key] = {**record, 'metadata_sha256': digest(raw)}
        metadata_bytes[key] = raw
        for package_key in record['packages']:
            access_for[package_key] = record['access']
    tool_hash = digest(Path(__file__).read_bytes())
    prepared = {}
    receipt = {'schema': 'release-bundle/v1', 'source_sha': snapshot.sha,
               'manifest_sha256': digest(manifest_raw), 'runtime_sha256': runtime_hash,
               'packager_sha256': tool_hash, 'build_receipt_sha256': build_hash,
               'packaging_runtime': {'python': platform.python_version(),
                                     'jsonschema': importlib.metadata.version('jsonschema')},
               'schema_sha256': {p.name: digest(p.read_bytes()) for p in HERE.glob('*.schema.json')},
               'records': records, 'packages': {}, 'references': manifest.get('references', {})}
    for key, package in manifest['packages'].items():
        entries = {}
        evidence = []
        for f in package['files']:
            origin = f['origin']
            mode = 0o644
            if origin == 'tracked':
                data, mode = snapshot.read(f['path'])
            elif origin == 'built':
                if not build:
                    raise ValueError('Built inputs require build evidence')
                expected = build.get('outputs', {}).get(f['path'])
                if not expected or expected.get('profile') != package['build_profile']:
                    raise ValueError('Missing build profile/output evidence')
                data = local_file(built_dir, f['path'])
                if digest(data) != expected.get('sha256') or len(data) != expected.get('size'):
                    raise ValueError('Built input does not match evidence')
            else:
                ref, content, _ = references[f['reference']]
                if ref['access'] != 'public' and access_for[key] == 'public':
                    raise ValueError('Restricted reference cannot enter a public record')
                if f['path'] not in content:
                    raise ValueError('Selected reference member absent')
                data = content[f['path']]
            entries[f['archive_path']] = (data, mode)
            evidence.append({**f, 'sha256': digest(data), 'size': len(data), 'mode': oct(mode)})
        if sum(len(data) for data, _ in entries.values()) > MAX_BYTES:
            raise ValueError('Package exceeds v1 size bound')
        provenance = {k: v for k, v in receipt.items() if k not in ('packages', 'records')}
        provenance.update(package=key, license_expression=package['license_expression'],
                          build_profile=package['build_profile'], files=evidence)
        entries['PROVENANCE.json'] = (encode(provenance), 0o644)
        archive = zip_bytes(entries)
        if len(archive) > MAX_BYTES:
            raise ValueError('Package including provenance and ZIP overhead exceeds v1 size bound')
        prepared[package['filename']] = archive
        receipt['packages'][key] = {'filename': package['filename'], 'sha256': digest(archive),
                                    'size': len(archive), 'files': evidence}
    # Complete verification precedes any output. Never overwrite an old bundle.
    out = Path(out)
    if out.exists():
        raise ValueError('Output already exists; choose a new bundle directory')
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.release-', dir=out.parent))
    try:
        for name, data in prepared.items():
            (stage / name).write_bytes(data)
        (stage / 'metadata').mkdir()
        for key, raw in metadata_bytes.items():
            (stage / 'metadata' / (key + '.json')).write_bytes(raw)
        (stage / 'receipt.json').write_bytes(encode(receipt))
        (stage / 'runtime.json').write_bytes(runtime_raw)
        (stage / 'manifest.json').write_bytes(manifest_raw)
        if build_receipt_path:
            (stage / 'build-receipt.json').write_bytes(build_raw)
        # Include exact acceptance receipts for durable evidence, not private
        # delivery locators or all external bytes unless explicitly selected.
        if references:
            (stage / 'references').mkdir()
            for key, binding in manifest['references'].items():
                (stage / 'references' / (key + '.json')).write_bytes(
                    references[key][2])
        os.rename(stage, out)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--manifest', required=True, help='Tracked manifest path at source revision')
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--built-dir', type=Path)
    parser.add_argument('--build-receipt', type=Path)
    parser.add_argument('--reference-dir', type=Path)
    args = parser.parse_args()
    receipt = prepare(args.repo, args.source, args.manifest, args.runtime, args.out,
                      args.built_dir, args.build_receipt, args.reference_dir)
    print(json.dumps({'source_sha': receipt['source_sha'], 'bundle': str(args.out),
                      'receipt_sha256': digest((args.out / 'receipt.json').read_bytes())}))


if __name__ == '__main__':
    main()
