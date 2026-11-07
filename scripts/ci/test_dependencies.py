import unittest
from dependencies import plan


class Dependencies(unittest.TestCase):
    def setUp(self):
        self.components = {
            'paper': {'paths': ['paper/*', 'overleaf-draft.tex', 'overleaf-final.tex'], 'depends_on': []},
            'code': {'paths': ['code/*'], 'depends_on': []},
            'proof': {'paths': ['proof/*'], 'depends_on': ['code']},
            'benchmark': {'paths': ['benchmark/*'], 'depends_on': ['proof']}}

    def selected(self, paths, **kwargs):
        return {n for n, v in plan(paths, self.components, **kwargs)['components'].items() if v['selected']}

    def test_transitive_code_dependency(self):
        self.assertEqual(self.selected(['code/main.py']), {'code', 'proof', 'benchmark'})

    def test_root_proxy_runs_paper(self):
        self.assertEqual(self.selected(['overleaf-final.tex']), {'paper'})

    def test_container_inputs_run_all(self):
        for path in ['Dockerfile', 'code/Dockerfile.dev', 'proof/build.Dockerfile',
                     '.dockerignore', 'code/test.Dockerfile.dockerignore',
                     '.devcontainer/devcontainer.json', 'code/.devcontainer/setup.sh',
                     'compose.yaml', 'code/docker-compose.override.yml']:
            with self.subTest(path=path):
                self.assertEqual(self.selected([path]), set(self.components))

    def test_unknown_or_incomplete_runs_all(self):
        self.assertEqual(self.selected(['new-helper.py']), set(self.components))
        self.assertEqual(self.selected([], complete=False), set(self.components))

    def test_all_scope_and_unaffected_are_explicit(self):
        self.assertEqual(self.selected([], all_scope=True), set(self.components))
        self.assertEqual(self.selected([]), set())

    def test_cycles_rejected(self):
        self.components['code']['depends_on'] = ['benchmark']
        with self.assertRaises(ValueError):
            self.selected(['code/main.py'])

    def test_disabled_dependency_and_path_traversal_rejected(self):
        self.components['code']['depends_on'] = ['presentation']
        with self.assertRaises(ValueError):
            self.selected(['code/main.py'])
        self.components['code']['depends_on'] = []
        with self.assertRaises(ValueError):
            self.selected(['../code/main.py'])


if __name__ == '__main__':
    unittest.main()
