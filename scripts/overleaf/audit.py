"""Read-only Git tree audit. Output is evidence input, never native observation."""
import argparse
import json
import subprocess


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True).stdout


def tree(root, commit):
    result = {}
    for record in git(root, 'ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
        if not record:
            continue
        meta, path = record.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        result[path.decode('utf-8')] = {'mode': mode, 'type': kind, 'oid': oid}
    return result


def inventory(root, entries):
    result = dict(tracked_files=len(entries), payload_bytes=0, text_bytes=0, largest_text_bytes=0,
                  executables=[], symlinks=[], gitlinks=[], lfs_pointers=[])
    for path, entry in entries.items():
        mode = entry['mode']
        if mode == '160000':
            result['gitlinks'].append(path)
            continue
        if mode == '120000':
            result['symlinks'].append(path)
        if mode == '100755':
            result['executables'].append(path)
        raw = git(root, 'cat-file', 'blob', entry['oid'])
        result['payload_bytes'] += len(raw)
        # Conservative estimate: every NUL-free blob counts as editable text,
        # including undecodable bytes. Actual Overleaf classification needs UI audit.
        if b'\0' not in raw:
            result['text_bytes'] += len(raw)
            result['largest_text_bytes'] = max(result['largest_text_bytes'], len(raw))
        if raw.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
            result['lfs_pointers'].append(path)
    return result


def audit(root, before, after):
    before = git(root, 'rev-parse', '--verify', before + '^{commit}').decode().strip()
    after = git(root, 'rev-parse', '--verify', after + '^{commit}').decode().strip()
    old, new = tree(root, before), tree(root, after)
    changes = [{'path': path, 'before': old.get(path), 'after': new.get(path)}
               for path in sorted(old.keys() | new.keys()) if old.get(path) != new.get(path)]
    return dict(before_commit=before, after_commit=after,
                before_inventory=inventory(root, old), inventory=inventory(root, new),
                changes=changes, unexpected_changes=[item['path'] for item in changes])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before')
    parser.add_argument('after')
    parser.add_argument('--repo', default='.')
    args = parser.parse_args()
    print(json.dumps(audit(args.repo, args.before, args.after), indent=2))
