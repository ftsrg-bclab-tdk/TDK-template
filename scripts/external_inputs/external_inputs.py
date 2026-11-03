"""Verify and materialize accepted external-input ZIPs; never execute their contents."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import stat
import subprocess
import tempfile
import time
import zipfile
import unicodedata

MAX_ARCHIVE = 512 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_FILES = 2048


class Invalid(ValueError):
    """Invalid or mismatched evidence. Never converted to an outage fallback."""


class Unavailable(RuntimeError):
    """Retrieval failed; already verified accepted bytes may still be usable."""


def require(ok, message):
    if not ok:
        raise Invalid(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def hashfile(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def sha(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value), 'invalid SHA256')


def fields(value, required, optional=()):
    require(isinstance(value, dict), 'expected object')
    require(set(required) <= value.keys() <= set(required) | set(optional), 'unexpected or missing fields')


def nonempty(value):
    require(isinstance(value, str) and bool(value.strip()), 'expected nonempty string')


def integer(value, lower=0, upper=MAX_EXPANDED):
    require(type(value) is int and lower <= value <= upper, 'invalid integer or resource limit')


def safe_path(value):
    nonempty(value)
    require(not value.startswith('/') and not any(
        ord(c) < 32 or ord(c) == 127 or c in '\\:' for c in value), 'unsafe inventory path')
    require(all(p not in ('', '.', '..') for p in value.split('/')), 'unsafe inventory path')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def read_json(path, expected=None, *, retain_raw=False):
    require(Path(path).stat().st_size <= 2 * 1024 * 1024, 'JSON too large')
    raw = Path(path).read_bytes()
    if expected:
        sha(expected)
        require(digest(raw) == expected, 'receipt digest mismatch')
    try:
        parsed = json.loads(raw, object_pairs_hook=unique_object)
        return (parsed, raw) if retain_raw else parsed
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Invalid('invalid JSON') from exc


def validate_receipt(r):
    fields(r, ('schema', 'manifest_sha256', 'package_sha256', 'files', 'provenance',
               'acceptance', 'license', 'redistribution', 'access'))
    require(r['schema'] == 'external-inputs/v1', 'unsupported receipt version')
    sha(r['manifest_sha256']); sha(r['package_sha256'])
    require(isinstance(r['files'], list) and 0 < len(r['files']) <= MAX_FILES, 'invalid inventory count')
    names = set()
    for f in r['files']:
        fields(f, ('path', 'sha256', 'size'))
        safe_path(f['path']); sha(f['sha256']); integer(f['size'])
        name = unicodedata.normalize('NFC', f['path']).casefold()
        require(name not in names, 'duplicate/case-colliding inventory path')
        names.add(name)
    require(sum(f['size'] for f in r['files']) <= MAX_EXPANDED, 'expanded package too large')
    for name in names:
        require(not any('/'.join(name.split('/')[:i]) in names
                        for i in range(1, len(name.split('/')))), 'file/directory collision')
    fields(r['provenance'], ('publisher', 'source', 'retrieved_at', 'applicability'))
    for value in r['provenance'].values():
        nonempty(value)
    fields(r['acceptance'], ('status', 'evidence'))
    require(r['acceptance']['status'] == 'accepted', 'receipt is not accepted')
    nonempty(r['acceptance']['evidence']); nonempty(r['license'])
    require(type(r['redistribution']) is bool, 'redistribution must be boolean')
    require(r['access'] in ('public', 'restricted', 'embargoed'), 'unknown access')
    return r


def validate_delivery(d, r, receipt_sha256):
    fields(d, ('schema', 'receipt_sha256', 'package_sha256', 'repository',
               'repository_id', 'release_id', 'tag', 'asset_id', 'size'))
    require(d['schema'] == 'external-inputs-delivery/v1', 'unsupported delivery version')
    require(d['receipt_sha256'] == receipt_sha256, 'delivery receipt mismatch')
    require(d['package_sha256'] == r['package_sha256'], 'delivery archive mismatch')
    require(isinstance(d['repository'], str) and re.fullmatch(
        r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+', d['repository']), 'invalid repository')
    require(d['repository'].split('/')[1] not in ('.', '..'), 'invalid repository path')
    for key in ('repository_id', 'release_id', 'asset_id'):
        integer(d[key], 1, 2**63 - 1)
    nonempty(d['tag']); integer(d['size'], 1, MAX_ARCHIVE)
    return d


def verify_archive(path, r):
    require(0 < Path(path).stat().st_size <= MAX_ARCHIVE, 'archive size exceeds limit')
    require(hashfile(path) == r['package_sha256'], 'archive digest mismatch')
    inventory = {f['path']: f for f in r['files']}
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            require(len(infos) == len(inventory), 'archive inventory count mismatch')
            require(len({i.filename for i in infos}) == len(infos), 'duplicate ZIP entry')
            require({i.filename for i in infos} == inventory.keys(), 'archive inventory mismatch')
            for info in infos:
                mode = info.external_attr >> 16
                require(stat.S_IFMT(mode) in (0, stat.S_IFREG), 'non-regular ZIP entry')
                require(not info.flag_bits & 1, 'encrypted input forbidden')
                require(info.file_size == inventory[info.filename]['size'], 'member size mismatch')
                with archive.open(info) as stream:
                    actual = hashlib.file_digest(stream, 'sha256').hexdigest()
                require(actual == inventory[info.filename]['sha256'], 'member digest mismatch')
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as exc:
        raise Invalid('invalid or unsupported ZIP') from exc


def materialize(path, r, output):
    verify_archive(path, r)
    output = Path(output)
    require(not output.exists() and not output.is_symlink(), 'output must not exist')
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.external-inputs-', dir=output.parent))
    reserved = False
    try:
        with zipfile.ZipFile(path) as archive:
            for f in r['files']:
                dest = stage / f['path']
                dest.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(f['path']) as src, dest.open('xb') as dst:
                    shutil.copyfileobj(src, dst)
        output.mkdir()  # exclusive reservation; never replace an existing checkout directory
        reserved = True
        stage.replace(output)
        reserved = False
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        if reserved:
            output.rmdir()


class GitHub:
    """Use existing gh authentication. No tokens in config, arguments or reports."""

    def __init__(self, timeout=120):
        self.timeout = timeout

    def download(self, path, target, limit, accept='application/octet-stream'):
        command = ['gh', 'api', '--hostname', 'github.com', '--method', 'GET',
                   '-H', 'Accept: ' + accept, path]
        deadline = time.monotonic() + self.timeout
        try:
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:
                try:
                    with selectors.DefaultSelector() as selector, Path(target).open('wb') as out:
                        selector.register(proc.stdout, selectors.EVENT_READ)
                        size = 0
                        while True:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0 or not selector.select(remaining):
                                raise Unavailable('GitHub retrieval timed out')
                            chunk = os.read(proc.stdout.fileno(), 65536)
                            if not chunk:
                                break
                            size += len(chunk)
                            require(size <= limit, 'download exceeds declared size limit')
                            out.write(chunk)
                    if proc.wait(timeout=max(0.01, deadline - time.monotonic())):
                        raise Unavailable('GitHub retrieval failed; verify gh authentication/access')
                finally:
                    if proc.poll() is None:
                        proc.kill()
                    proc.wait()
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise Unavailable('gh unavailable or retrieval timed out') from exc

    def metadata(self, path):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'metadata.json'
            self.download(path, target, 2 * 1024 * 1024, 'application/vnd.github+json')
            return read_json(target)


def fetch(r, d, cache, client=None):
    client = client or GitHub()
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    stored = cache / (r['package_sha256'] + '.zip')
    if stored.exists():
        verify_archive(stored, r)  # corrupt cache is not accepted or silently reused
    prefix = 'repos/' + d['repository']
    try:
        repo = client.metadata(prefix)
        require(isinstance(repo, dict), 'invalid repository metadata')
        require(repo.get('id') == d['repository_id'], 'repository identity mismatch')
        release = client.metadata(prefix + '/releases/' + str(d['release_id']))
        require(isinstance(release, dict), 'invalid release metadata')
        require(release.get('id') == d['release_id'] and release.get('tag_name') == d['tag'], 'release identity mismatch')
        require(release.get('immutable') is True and release.get('draft') is False, 'release must be published and immutable')
        require(isinstance(release.get('assets'), list) and all(isinstance(a, dict) for a in release['assets']), 'invalid assets metadata')
        assets = [a for a in release['assets'] if a.get('id') == d['asset_id']]
        require(len(assets) == 1 and assets[0].get('size') == d['size'], 'asset identity/size mismatch')
        reported = assets[0].get('digest')
        require(reported in (None, 'sha256:' + r['package_sha256']), 'GitHub asset digest mismatch')
        with tempfile.TemporaryDirectory(dir=cache) as temp:
            downloaded = Path(temp) / 'archive.zip'
            client.download(prefix + '/releases/assets/' + str(d['asset_id']), downloaded, d['size'])
            verify_archive(downloaded, r)
            downloaded.replace(stored)
        return stored, 'downloaded_accepted', None
    except Unavailable as exc:
        if stored.exists():
            verify_archive(stored, r)
            return stored, 'reused_accepted', str(exc)
        raise Unavailable('required accepted package unavailable; no verified cached copy') from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('verify', 'materialize', 'fetch'))
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--receipt-sha256', required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--delivery', type=Path)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        parsed, raw_receipt = read_json(args.receipt, args.receipt_sha256, retain_raw=True)
        r = validate_receipt(parsed)
        require(hashfile(args.manifest) == r['manifest_sha256'], 'source manifest digest mismatch')
        state, problem, d = 'verified_local', None, None
        archive = args.archive
        if args.operation == 'fetch':
            require(args.delivery is not None and args.cache is not None, 'fetch needs delivery and cache')
            d = validate_delivery(read_json(args.delivery), r, args.receipt_sha256)
            archive, state, problem = fetch(r, d, args.cache)
        require(archive is not None, 'archive required')
        verify_archive(archive, r)
        if args.operation == 'fetch':
            receipt_copy = args.cache / (args.receipt_sha256 + '.json')
            with tempfile.TemporaryDirectory(dir=args.cache) as temp:
                staged = Path(temp) / 'receipt.json'
                staged.write_bytes(raw_receipt)
                staged.replace(receipt_copy)
        if args.operation == 'materialize':
            require(args.output is not None, 'output required')
        if args.output is not None:
            materialize(archive, r, args.output)
        print(json.dumps({'schema': 'external-inputs-result/v1', 'manifest_sha256': r['manifest_sha256'],
                          'receipt_sha256': args.receipt_sha256, 'package_sha256': r['package_sha256'],
                          'outcome': state, 'retrieval_problem': problem, 'source_freshness': 'not_checked',
                          'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                          'method': 'github-release' if d else 'local', 'delivery': d,
                          'files': r['files'], 'output': str(args.output) if args.output else None}))
        return 0
    except (Invalid, Unavailable, OSError) as exc:
        print(json.dumps({'schema': 'external-inputs-result/v1', 'outcome': 'error', 'reason': str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
