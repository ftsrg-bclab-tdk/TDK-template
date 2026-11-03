import json
from pathlib import Path
import unittest
import ownership


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.raw=(Path(__file__).resolve().parents[2]/'template-ownership.json').read_bytes()
        self.policy=ownership.load_policy(self.raw)

    def test_helper_change_is_candidate_but_project_content_and_mixed_files_are_not(self):
        for path in ('scripts/setup.py','paper/scripts/lint.lua','proof/tlc.py'):
            self.assertTrue(ownership.upstream_decision(self.policy,self.policy,path)['eligible'])
        for path in ('paper/content/01-introduction.tex','paper/bib/zotero.bib','paper/draft.tex',
                     'project.json','code/src/research.py','scratch/notes/consultation.md',
                     'presentation/slides.md','registry/zenodo.json','.onboarding/session.json',
                     'DOI.txt','scripts/my-private-experiment.py'):
            self.assertFalse(ownership.upstream_decision(self.policy,self.policy,path)['eligible'],path)

    def test_project_cannot_expand_policy_and_new_paths_wait_for_selection(self):
        changed=json.loads(self.raw)
        changed['template_files'].append('scripts/new.py')
        self.assertFalse(ownership.upstream_decision(self.policy,changed,'scripts/new.py')['eligible'])
        for status in ('added','deleted','renamed'):
            self.assertFalse(ownership.upstream_decision(self.policy,self.policy,'scripts/setup.py',status=status)['eligible'])

    def test_symlinks_and_mode_changes_are_held(self):
        for old,new in (('100644','120000'),('120000','120000'),('100755','100644')):
            self.assertFalse(ownership.upstream_decision(self.policy,self.policy,'scripts/setup.py',old_mode=old,new_mode=new)['eligible'])

    def test_invalid_and_ambiguous_policies_fail(self):
        for field,value in (('template_files',['../secret']),('mixed_files',['scripts/setup.py']),('schema','v2')):
            changed=json.loads(self.raw); changed[field]=value
            with self.assertRaises(ValueError): ownership.load_policy(json.dumps(changed))
        for path in ('/tmp/a','a/../b','a//b','a/.git/config','a\\b'):
            with self.assertRaises(ValueError): ownership.classify(self.policy,path)
        with self.assertRaises(ValueError): ownership.load_policy('{"schema":1,"schema":2}')

    def test_exclusion_and_generated_files_never_become_candidates(self):
        self.assertEqual(ownership.classify(self.policy,'paper/guide/essentials.tex'),'generated')
        self.assertEqual(ownership.classify(self.policy,'registry/zenodo.json'),'excluded')
        changed=json.loads(self.raw); changed['template_files'].append('registry/secret')
        with self.assertRaises(ValueError): ownership.load_policy(json.dumps(changed))

    def test_identity_changes_fail(self):
        changed=json.loads(self.raw); changed['template_repository_id']+=1
        with self.assertRaises(ValueError): ownership.upstream_decision(self.policy,changed,'scripts/setup.py')


if __name__=='__main__': unittest.main()
