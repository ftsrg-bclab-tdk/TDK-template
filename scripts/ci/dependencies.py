"""Pure changed-path planner; workflow callers supply the complete diff and enabled graph."""
from fnmatch import fnmatchcase
from pathlib import PurePosixPath

COMPONENTS = {'paper', 'code', 'proof', 'benchmark', 'scratch', 'presentation'}


def container_input(path):
    parts = PurePosixPath(path).parts
    name = parts[-1]
    return (name.startswith('Dockerfile') or name.endswith('.Dockerfile') or
            name == '.dockerignore' or name.endswith('.dockerignore') or
            '.devcontainer' in parts or name == 'devcontainer.json' or
            name in ('compose.yml', 'compose.yaml', 'docker-compose.yml', 'docker-compose.yaml') or
            name.startswith(('compose.', 'docker-compose.')) and name.endswith(('.yml', '.yaml')))


def plan(changed_paths, components, *, complete=True, all_scope=False):
    """components: enabled name -> {paths: glob list, depends_on: component list}.

    Unknown changed paths and container/shared build configuration select all.
    This is selection evidence, not execution or success evidence.
    """
    if not isinstance(components, dict) or not components.keys() <= COMPONENTS:
        raise ValueError('invalid enabled component map')
    for name, value in components.items():
        if (not isinstance(value, dict) or set(value) != {'paths', 'depends_on'} or
                not isinstance(value['paths'], list) or not value['paths'] or
                not all(isinstance(p, str) and p for p in value['paths']) or
                not isinstance(value['depends_on'], list) or
                not all(d in components for d in value['depends_on'])):
            raise ValueError('invalid component dependency declaration: ' + name)
    visited, active = set(), set()

    def visit(name):
        if name in active:
            raise ValueError('cyclic component dependencies')
        if name in visited:
            return
        active.add(name)
        for dep in components[name]['depends_on']:
            visit(dep)
        active.remove(name)
        visited.add(name)

    for name in components:
        visit(name)
    reasons = {name: [] for name in components}
    broad = 'all scope' if all_scope else 'incomplete diff' if not complete else None
    for path in changed_paths:
        if (not isinstance(path, str) or not path or path.startswith('/') or
                any(p in ('', '.', '..') for p in path.split('/')) or '\\' in path):
            raise ValueError('invalid changed path')
        if container_input(path) or path == 'Makefile' or path.startswith(('.github/', 'scripts/ci/')):
            broad = 'shared/container build input: ' + path
        matched = [name for name, c in components.items() if any(fnmatchcase(path, g) for g in c['paths'])]
        if not matched:
            broad = 'unclassified input: ' + path
        for name in matched:
            reasons[name].append('changed: ' + path)
    if broad:
        for values in reasons.values():
            values.append(broad)
    changed = True
    while changed:
        changed = False
        for name, c in components.items():
            if not reasons[name]:
                triggered = [dep for dep in c['depends_on'] if reasons[dep]]
                if triggered:
                    reasons[name].append('dependency: ' + ', '.join(sorted(triggered)))
                    changed = True
    return {'schema': 'project-check-plan/v1', 'components': {
        name: {'selected': bool(reasons[name]), 'reasons': reasons[name]} for name in sorted(components)}}
