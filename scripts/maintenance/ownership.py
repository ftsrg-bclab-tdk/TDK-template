"""Classify changed paths using trusted template policies, without reading project content."""
import json
from pathlib import PurePosixPath
import re

FIELDS = {'schema', 'template_repository', 'template_repository_id', 'template_files',
          'generated_files', 'mixed_files', 'project_roots', 'excluded_roots'}


def path_name(value):
    if (not isinstance(value, str) or not value or len(value) > 1024 or
            '\\' in value or ':' in value or any(ord(c) < 32 for c in value) or
            any(p in ('', '.', '..', '.git') for p in value.split('/')) or
            str(PurePosixPath(value)) != value):
        raise ValueError('Expected a normalized repository-relative path')
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate ownership key')
        result[key] = value
    return result


def load_policy(raw):
    if len(raw) > 1024 * 1024:
        raise ValueError('Ownership policy exceeds 1 MiB')
    policy = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(policy, dict) or set(policy) != FIELDS or policy['schema'] != 'template-ownership/v1':
        raise ValueError('Unsupported ownership policy')
    if (not isinstance(policy['template_repository'], str) or
            not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', policy['template_repository']) or
            type(policy['template_repository_id']) is not int or policy['template_repository_id'] <= 0):
        raise ValueError('Invalid canonical repository identity')
    exact = set()
    for field in ('template_files', 'generated_files', 'mixed_files', 'project_roots', 'excluded_roots'):
        values = policy[field]
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values) or len(set(values)) != len(values):
            raise ValueError('Policy lists must contain unique paths')
        for value in values:
            path_name(value)
        if field in ('template_files', 'generated_files', 'mixed_files'):
            if exact.intersection(values):
                raise ValueError('Ambiguous exact ownership')
            exact.update(values)
    if any(under(p, policy['excluded_roots']) for p in exact):
        raise ValueError('Excluded paths cannot have automatic or mixed ownership')
    return policy


def under(path, roots):
    return any(path == root or path.startswith(root + '/') for root in roots)


def classify(policy, path):
    path_name(path)
    if under(path, policy['excluded_roots']):
        return 'excluded'
    if path in policy['generated_files']:
        return 'generated'
    if path in policy['mixed_files']:
        return 'mixed'
    if path in policy['template_files']:
        return 'template'
    if under(path, policy['project_roots']):
        return 'project'
    return 'unclassified'


def upstream_decision(baseline, current, path, *, old_mode='100644', new_mode='100644', status='modified'):
    """Eligibility only; never permission to merge, disclose unchecked content or run code."""
    identity = ('template_repository', 'template_repository_id')
    if (baseline['template_repository'].lower() != current['template_repository'].lower() or
            baseline[identity[1]] != current[identity[1]]):
        raise ValueError('Template identity changed')
    before, after = classify(baseline, path), classify(current, path)
    if before == 'excluded' or after == 'excluded':
        return {'eligible': False, 'reason': 'excluded'}
    if status != 'modified':
        return {'eligible': False, 'reason': 'new, deleted or renamed paths need selection'}
    if old_mode not in ('100644', '100755') or new_mode != old_mode:
        return {'eligible': False, 'reason': 'nonregular file or mode change needs selection'}
    if before != 'template' or after != 'template':
        return {'eligible': False, 'reason': f'{before}/{after} ownership needs selection'}
    return {'eligible': True, 'reason': 'established template file in both trusted policies'}
