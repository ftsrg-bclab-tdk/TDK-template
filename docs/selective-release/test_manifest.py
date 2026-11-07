"""Executable proposal contract; no packaging, credentials or network calls."""
import copy
import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parent
SCHEMA = json.loads((ROOT / 'manifest.schema.json').read_text())
VALIDATOR = Draft202012Validator(SCHEMA)


import sys
sys.path.insert(0, str(ROOT.parents[1] / 'scripts' / 'release'))
from packager import validate


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / 'example-separate.json').read_text())

    def reject(self, mutate):
        candidate = copy.deepcopy(self.manifest)
        mutate(candidate)
        with self.assertRaises((ValueError, ValidationError)):
            validate(candidate)

    def test_schema_and_alternative_groupings(self):
        Draft202012Validator.check_schema(SCHEMA)
        for path in ROOT.glob('example-*.json'):
            validate(json.loads(path.read_text()))

    def test_unsafe_source_and_archive_paths(self):
        for path in ['/etc/passwd', '../secret', 'a/../b', './x', 'a/./b',
                     'a\\b', 'a//b', 'a/\x00b', 'a/']:
            for field in ['path', 'archive_path']:
                with self.subTest(path=path, field=field):
                    self.reject(lambda m: m['packages']['software']['files'][0].update({field: path}))

    def test_unknown_properties_cannot_smuggle_credentials_or_publish(self):
        for key in ['token', 'publish', 'zenodo_record_id']:
            with self.subTest(key=key):
                self.reject(lambda m: m.update({key: 'not-allowed'}))

    def test_empty_package_selection(self):
        self.reject(lambda m: m['packages']['software'].update(files=[]))

    def test_unknown_package(self):
        self.reject(lambda m: m['records']['software'].update(packages=['missing']))

    def test_unassigned_package(self):
        self.reject(lambda m: m['records'].pop('data'))

    def test_multiple_record_assignment(self):
        self.reject(lambda m: m['records']['data']['packages'].append('software'))

    def test_case_insensitive_package_collision(self):
        self.reject(lambda m: m['packages']['data'].update(filename='SOFTWARE.zip'))

    def test_case_insensitive_archive_collision(self):
        self.reject(lambda m: m['packages']['software']['files'].append(
            {'origin': 'tracked', 'path': 'other.txt', 'archive_path': 'readme.MD'}))

    def test_reserved_provenance_member(self):
        self.reject(lambda m: m['packages']['software']['files'][0].update(archive_path='PROVENANCE.json'))

    def test_generated_file_requires_build_profile(self):
        self.reject(lambda m: m['packages']['software']['files'][0].update(origin='built'))
        self.manifest['packages']['software']['files'][0]['origin'] = 'built'
        self.manifest['packages']['software']['build_profile'] = 'software-release'
        validate(self.manifest)

    def test_license_required(self):
        self.reject(lambda m: m['packages']['software'].pop('license_expression'))

    def test_access_is_explicit(self):
        self.reject(lambda m: m['records']['software'].pop('access'))
        self.reject(lambda m: m['records']['software'].update(access='inherit'))


if __name__ == '__main__':
    unittest.main()
