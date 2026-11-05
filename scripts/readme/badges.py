#!/usr/bin/env python3
"""Render repository-specific README status blocks without executing builds."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote, urlencode

START = '<!-- tdk-status:start -->'
END = '<!-- tdk-status:end -->'
WORKFLOWS = (
    ('ci.yml', 'Project checks', 'push'),
    ('paper-build.yml', 'Paper build', 'workflow_run'),
    ('paper-lint.yml', 'Paper lint report', 'workflow_run'),
)


def repository(value):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value):
        raise ValueError('repository must be owner/name')
    result = subprocess.run(['gh', 'api', f'repos/{value}'], check=True,
                            capture_output=True, text=True, timeout=30)
    data = json.loads(result.stdout)
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', data.get('full_name', ''))
            or not isinstance(data.get('id'), int)
            or not isinstance(data.get('private'), bool)
            or not isinstance(data.get('default_branch'), str)
            or not data['default_branch']):
        raise ValueError('incomplete GitHub repository metadata')
    return data


def validate_workflows(root):
    for filename, label, _ in WORKFLOWS:
        path = root / '.github' / 'workflows' / filename
        if not path.is_file():
            raise ValueError(f'missing workflow: {path}')
        # The agreed workflow names are simple YAML scalars. Do not accept a
        # different implementation silently merely because the filename exists.
        names = re.findall(r'^name:\s*[\'\"]?([^\n\'\"]+?)[\'\"]?\s*$',
                           path.read_text(), re.MULTILINE)
        if names != [label]:
            raise ValueError(f'{path}: expected workflow name {label!r}')


def md_text(value):
    return re.sub(r'([\\`*_{}\[\]()<>!|])', r'\\\1', value).replace('\n', ' ')


def published_badges(path, expected_digest, repo_id):
    """Consume the release owner's receipt; never treat a local claim as trust."""
    if not re.fullmatch(r'[0-9a-f]{64}', expected_digest or ''):
        raise ValueError('publication requires an externally trusted SHA-256 receipt digest')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_digest:
        raise ValueError('publication receipt digest mismatch')
    data = json.loads(raw)
    if (not isinstance(data, dict) or data.get('schema') != 'publication-receipt/v1'
            or data.get('repository_id') != repo_id):
        raise ValueError('publication receipt schema/repository mismatch')
    if data.get('environment') == 'sandbox':
        return []
    if data.get('environment') != 'production':
        raise ValueError('invalid publication environment')
    if data.get('status') not in ('staged', 'partial', 'published'):
        raise ValueError('invalid publication receipt status')
    records = data.get('records')
    if not isinstance(records, dict):
        raise ValueError('publication records must be keyed by manifest record ID')
    rendered = []
    for key, record in sorted(records.items()):
        if not isinstance(record, dict):
            raise ValueError(f'invalid publication record {key}')
        if record.get('status') != 'published':
            if record.get('status') not in ('planned', 'draft', 'staged', 'publishing', 'outcome_unknown'):
                raise ValueError(f'invalid publication status for {key}')
            if any(field in record for field in ('version_doi', 'concept_doi', 'record_url', 'verified_at')):
                raise ValueError(f'unpublished record {key} carries published identifiers')
            continue
        doi = record.get('version_doi', '')
        concept = record.get('concept_doi', '')
        url = record.get('record_url', '')
        # Zenodo can retain an existing DOI. Do not infer DOI identity from the
        # numeric record ID; the verified receipt supplies both identifiers.
        if (not isinstance(doi, str) or not isinstance(concept, str) or not isinstance(url, str)
                or not re.fullmatch(r'10\.[0-9]{4,9}/[^\s{}\\]+', doi)
                or not re.fullmatch(r'10\.[0-9]{4,9}/[^\s{}\\]+', concept)
                or not re.fullmatch(r'https://zenodo\.org/records/[1-9][0-9]*', url)
                or not isinstance(record.get('verified_at'), str)):
            raise ValueError(f'invalid published identifiers for record {key}')
        verified = datetime.fromisoformat(record['verified_at'].replace('Z', '+00:00'))
        if verified.tzinfo is None:
            raise ValueError(f'publication verification time needs a timezone for {key}')
        rendered.append(f'[![{md_text(key)} DOI](https://zenodo.org/badge/DOI/'
                        f'{quote(doi, safe="/")}.svg)](https://doi.org/{quote(doi, safe="/")})')
    return rendered


def render(metadata, publication=None, publication_digest=None):
    base = f'https://github.com/{metadata["full_name"]}/actions/workflows/'
    rows = []
    for filename, label, event in WORKFLOWS:
        params = urlencode({'branch': metadata['default_branch'], 'event': event})
        target = base + filename
        run_filter = urlencode({'query': f'branch:{metadata["default_branch"]} event:{event}'})
        rows.append(f'[![{label}]({target}/badge.svg?{params})]({target}?{run_filter})')
    rows += ['', 'Paper lint report success means reporting completed; writing findings may remain.',
             'Open the run for the checked SHA, runtime and scope. These badges do not certify Overleaf synchronization.']
    if metadata['private']:
        rows += ['Private results require GitHub access; badge images may be unavailable outside GitHub.']
    published = published_badges(publication, publication_digest, metadata['id']) if publication else []
    rows += ['', *published] if published else ['', 'No verified published artifact DOI has been supplied.']
    return START + '\n' + '\n'.join(rows) + '\n' + END


def replace_block(original, block):
    if original.count(START) != 1 or original.count(END) != 1:
        raise ValueError('README needs exactly one tdk-status start/end marker pair')
    start, end = original.index(START), original.index(END)
    if end < start:
        raise ValueError('README status markers are reversed')
    return original[:start] + block + original[end + len(END):]


def invalidated(original):
    return replace_block(original, START + "\nProject status pending: regenerate badges for this repository with scripts/readme/badges.py.\n" + END)


def invalidate_blocks(root):
    """Preflight both marked blocks before changing either README."""
    changes = []
    for relative in ("README.md", "paper/README.md"):
        path = root / relative
        if path.exists():
            before = path.read_text()
            changes.append((path, invalidated(before)))
    for path, after in changes:
        path.write_text(after)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, help='actual target owner/name; resolved with gh api')
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--readme', type=Path, action='append', required=True,
                        help='path relative to root; repeat for root and paper README')
    parser.add_argument('--publication-receipt', type=Path)
    parser.add_argument('--publication-sha256', help='trusted reviewed receipt digest, not computed from untrusted input')
    parser.add_argument('--write', action='store_true', help='replace marked blocks; default prints proposed block')
    args = parser.parse_args()
    try:
        if bool(args.publication_receipt) != bool(args.publication_sha256):
            raise ValueError('supply both publication receipt and trusted digest, or neither')
        validate_workflows(args.root)
        metadata = repository(args.repo)
        block = render(metadata, args.publication_receipt, args.publication_sha256)
        changes = []
        for relative in args.readme:
            path = args.root / relative
            if path.is_symlink() or not path.resolve().is_relative_to(args.root.resolve()):
                raise ValueError('README must be a regular file within root')
            with path.open(newline='') as stream:
                original = stream.read()
            changes.append((path, replace_block(original, block)))
        # Validate every target before modifying any of them.
        if args.write:
            for path, content in changes:
                with path.open('w', newline='') as stream:
                    stream.write(content)
        else:
            print(block)
    except (ValueError, OSError, subprocess.SubprocessError, TypeError, KeyError) as error:
        # Do not print gh stderr, which may contain service/authentication details.
        print(f'badge generation failed: {error if not isinstance(error, subprocess.SubprocessError) else "GitHub metadata lookup failed"}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
