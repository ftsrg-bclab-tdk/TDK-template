from pathlib import Path
import subprocess
import tempfile
import unittest

from packager import digest, encode, schema_validate
from writeback import proposal, published_records


def fixture_receipt():
    return {'schema':'publication-receipt/v1','environment':'production','repository_id':42,
            'operation_id':'synthetic-test','source_sha':'a'*40,'bundle_receipt_sha256':'b'*64,'status':'published',
            'records':{'research':{'status':'published','deposition_id':123456789,
            'record_url':'https://zenodo.org/records/123456789','version_doi':'10.5281/zenodo.123456789',
            'concept_doi':'10.5281/zenodo.123456788','verified_at':'2026-11-04T00:00:00+00:00',
            'title':'Synthetic fixture ONLY, not an actual published record','version':'1.0','publication_date':'2026-11-04',
            'creators':['Fixture, Test'],'packages':[{'filename':'research.zip','sha256':'c'*64,'size':12}]}}}


class WritebackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo=Path(self.tmp.name)
        (self.repo/'README.md').write_text('# Student research\n\nKeep this text.\n')
        (self.repo/'paper/bib').mkdir(parents=True)
        (self.repo/'paper/bib/references.bib').write_text('% Keep this bibliography\n')
        (self.repo/'paper/content').mkdir()
        self.receipt=fixture_receipt()

    def patch(self):
        raw=encode(self.receipt)
        return proposal(self.repo,raw,digest(raw),42,'README.md','paper/bib/references.bib','paper/content/artifact-availability.tex')

    def test_patch_preserves_text_and_is_idempotent(self):
        patch,evidence=self.patch()
        self.assertIn('10.5281/zenodo.123456788.svg',patch)
        self.assertIn('doi = {10.5281/zenodo.123456789}',patch)
        self.assertIn('Keep this text.',patch)
        self.assertNotIn('-Keep this text.',patch)
        self.assertEqual(len(evidence['changes']),3)
        subprocess.run(['git','apply','--unsafe-paths','-'],input=patch.encode(),cwd=self.repo,check=True,stderr=subprocess.PIPE)
        second,_=self.patch()
        self.assertEqual(second,'')

    def test_reserved_and_sandbox_not_published(self):
        raw=encode(self.receipt)
        with self.assertRaises(ValueError):
            published_records(raw,'0'*64,42)
        self.receipt['environment']='sandbox'
        with self.assertRaises(ValueError):
            self.patch()
        self.receipt['environment']='production'
        self.receipt['records']={'research':{'status':'draft','deposition_id':123,'reserved_doi':'10.5281/zenodo.123','packages':[]}}
        self.receipt['status']='partial'
        with self.assertRaises(ValueError):
            self.patch()

    def test_zotero_and_symlink_targets_rejected(self):
        raw=encode(self.receipt)
        with self.assertRaises(ValueError):
            proposal(self.repo,raw,digest(raw),42,'README.md','paper/bib/zotero.bib','availability.tex')
        (self.repo/'readme-link').symlink_to(self.repo/'README.md')
        with self.assertRaises(ValueError):
            proposal(self.repo,raw,digest(raw),42,'readme-link','refs.bib','availability.tex')

    def test_partial_renders_published_records_only(self):
        self.receipt['status']='partial'
        self.receipt['records']['waiting']={'status':'staged','deposition_id':999,'packages':[]}
        patch,_=self.patch()
        self.assertIn('tdk-publication:research',patch)
        self.assertNotIn('tdk-publication:waiting',patch)

    def test_schema_rejects_doi_on_draft(self):
        self.receipt['records']['research']['status']='draft'
        from jsonschema import ValidationError
        with self.assertRaises(ValidationError):
            schema_validate('publication-receipt.schema.json',self.receipt)


if __name__=='__main__':
    unittest.main()
