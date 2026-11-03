"""Bounded HTTPS transport and durable compare-and-swap publication registry."""
import base64
import contextlib
import fcntl
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
import os
from pathlib import Path
import random
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from packager import digest, encode, parse, safe_path


class RemoteError(RuntimeError):
    def __init__(self, status=None):
        self.status = status
        super().__init__('Remote request failed' + (f' (HTTP {status})' if status else ' (outcome unavailable)'))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class HTTP:
    """No write retries; GET retries only. Tokens never follow redirects."""
    def __init__(self, origin, token, sleep=time.sleep, opener=None):
        self.origin = origin.rstrip('/')
        self.token = token
        self.sleep = sleep
        self.opener = opener or urllib.request.build_opener(NoRedirect())

    def url(self, path):
        url = path if path.startswith('https://') else self.origin + path
        parts = urllib.parse.urlsplit(url)
        if (parts.scheme != 'https' or parts.netloc != urllib.parse.urlsplit(self.origin).netloc
                or parts.username or parts.password or parts.fragment):
            raise ValueError('Remote link origin not allowed')
        return url

    def request(self, method, path, value=None, data=None):
        url = self.url(path)
        if value is not None:
            data = encode(value)
        headers = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json',
                   'Content-Type': 'application/json' if value is not None or data is None else 'application/octet-stream'}
        attempts = 3 if method == 'GET' else 1
        for attempt in range(attempts):
            try:
                req = urllib.request.Request(url, data=data, method=method, headers=headers)
                with self.opener.open(req, timeout=45) as response:
                    raw = response.read(4 * 1024 * 1024 + 1)
                    if len(raw) > 4 * 1024 * 1024:
                        raise RemoteError()
                    return parse(raw) if raw else None
            except urllib.error.HTTPError as exc:
                retry = exc.code == 429 or 500 <= exc.code < 600
                if not retry or attempt + 1 == attempts:
                    raise RemoteError(exc.code) from None
                delay = exc.headers.get('Retry-After', '')
                if delay.isdigit():
                    delay = min(float(delay), 30)
                else:
                    try:
                        delay = min(max((parsedate_to_datetime(delay) - datetime.now(timezone.utc)).total_seconds(), 0), 30)
                    except (ValueError, TypeError):
                        delay = 2 ** attempt + random.random()
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt + 1 == attempts:
                    raise RemoteError() from None
                delay = 2 ** attempt + random.random()
            self.sleep(delay)


class FileStore:
    """Durable POSIX store for local pilots; directory must survive the runner."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self):
        if self.path.is_symlink():
            raise ValueError('Registry cannot be a symlink')
        if not self.path.exists():
            return None, None
        raw = self.path.read_bytes()
        return parse(raw), digest(raw)

    def put(self, value, expected):
        with open(str(self.path) + '.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            _, version = self.read()
            if version != expected:
                raise ValueError('Registry changed concurrently')
            raw = encode(value)
            fd, name = tempfile.mkstemp(dir=self.path.parent, prefix='.registry-')
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name, self.path)
                directory = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
            return digest(raw)


class GitHubStore:
    """CAS on one file in an existing registry branch; no branch creation."""
    def __init__(self, http, repository, ref, path):
        parts = repository.split('/')
        if len(parts) != 2 or any(not p or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-' for c in p) for p in parts):
            raise ValueError('Invalid registry repository')
        safe_path(path)
        if not ref:
            raise ValueError('Registry branch required')
        self.http, self.ref = http, ref
        self.endpoint = '/repos/' + repository + '/contents/' + urllib.parse.quote(path, safe='/')

    def read(self):
        try:
            data = self.http.request('GET', self.endpoint + '?ref=' + urllib.parse.quote(self.ref, safe=''))
        except RemoteError as exc:
            if exc.status == 404:
                return None, None
            raise
        if data.get('type') != 'file' or data.get('encoding') != 'base64' or data.get('size', 0) > 900000:
            raise ValueError('Registry must be a small JSON file')
        return parse(base64.b64decode(data['content'])), data['sha']

    def put(self, value, expected):
        raw = encode(value)
        if len(raw) > 900000:
            raise ValueError('Registry requires archival before further writes')
        body = {'message': 'Record publication operation state', 'branch': self.ref,
                'content': base64.b64encode(raw).decode()}
        if expected:
            body['sha'] = expected
        try:
            result = self.http.request('PUT', self.endpoint, value=body)
            return result['content']['sha']
        except (RemoteError, KeyError):
            # A lost CAS reply may already have persisted the exact intended state.
            current, version = self.read()
            if current == value:
                return version
            raise ValueError('Registry write unresolved; no remote publication write allowed') from None


class Registry:
    def __init__(self, store, repository_id, environment):
        self.store = store
        self.data, self.version = store.read()
        if self.data is None:
            self.data = {'schema': 'publication-registry/v1', 'repository_id': repository_id,
                         'environment': environment, 'owner': None, 'operations': {}, 'latest': {}}
        if (self.data.get('schema') != 'publication-registry/v1' or self.data.get('repository_id') != repository_id
                or self.data.get('environment') != environment):
            raise ValueError('Registry project/environment mismatch')
        self.owner = None

    def save(self):
        if self.owner and self.data['owner'] != self.owner:
            raise ValueError('Registry lock lost')
        self.version = self.store.put(self.data, self.version)

    @contextlib.contextmanager
    def session(self):
        if self.data['owner']:
            raise ValueError('Registry locked: confirm previous runner stopped before explicit unlock')
        self.owner = str(uuid.uuid4())
        self.data['owner'] = self.owner
        self.save()
        try:
            yield self
        finally:
            self.data['owner'] = None
            self.owner = None
            self.save()

    def unlock(self, expected_digest):
        if digest(encode(self.data)) != expected_digest:
            raise ValueError('Unlock requires exact observed registry digest')
        self.data['owner'] = None
        self.save()
