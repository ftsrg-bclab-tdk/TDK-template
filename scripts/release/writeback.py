#!/usr/bin/env python3
"""Prepare a DOI writeback patch from an externally trusted published receipt."""
import argparse
import difflib
from pathlib import Path
import re

from packager import digest, encode, parse, safe_path, schema_validate


def published_records(raw, expected_digest, repository_id):
    if digest(raw) != expected_digest:
        raise ValueError('Publication receipt digest mismatch')
    receipt = parse(raw)
    schema_validate('publication-receipt.schema.json', receipt)
    if receipt['environment'] != 'production' or receipt['repository_id'] != repository_id:
        raise ValueError('Writeback requires this project’s production receipt')
    records = {}
    for key, record in receipt['records'].items():
        if not re.fullmatch(r'[a-z][a-z0-9_-]*', key):
            raise ValueError('Invalid record key')
        if record['status'] != 'published':
            continue
        if not re.fullmatch(r'https://zenodo.org/records/[1-9][0-9]*', record['record_url']):
            raise ValueError('Expected production record URL')
        if not all(re.fullmatch(r'10\.5281/zenodo\.[1-9][0-9]*', record[k]) for k in ('version_doi','concept_doi')):
            raise ValueError('Expected Zenodo production DOI')
        records[key] = record
    if not records:
        raise ValueError('No verified published records; reserved DOI is not publication')
    return receipt, records


def tex(value):
    substitutions = {'\\':r'\textbackslash{}', '{':r'\{', '}':r'\}', '&':r'\&', '%':r'\%',
                     '$':r'\$', '#':r'\#', '_':r'\_', '^':r'\textasciicircum{}', '~':r'\textasciitilde{}'}
    return ''.join(substitutions.get(c, c) for c in str(value).replace('\n',' '))


def managed_block(existing, key, body, markdown=False):
    begin = f'<!-- tdk-publication:{key} begin -->' if markdown else f'% tdk-publication:{key} begin'
    end = f'<!-- tdk-publication:{key} end -->' if markdown else f'% tdk-publication:{key} end'
    block = begin + '\n' + body.rstrip() + '\n' + end
    if begin in existing or end in existing:
        if existing.count(begin) != 1 or existing.count(end) != 1 or existing.index(end) < existing.index(begin):
            raise ValueError('Malformed managed publication block')
        a, b = existing.index(begin), existing.index(end) + len(end)
        return existing[:a] + block + existing[b:]
    return existing + ('\n' if existing.endswith('\n') or not existing else '\n\n') + block + '\n'


def original(repo, relative):
    safe_path(relative)
    path = Path(repo)
    if path.is_symlink():
        raise ValueError('Repository root cannot be symlinked')
    for part in relative.split('/'):
        path = path / part
        if path.is_symlink():
            raise ValueError('Writeback target cannot traverse symlinks')
    return path.read_text() if path.exists() else ''


def proposal(repo, raw, expected_digest, repository_id, readme, bibliography, availability):
    if len({readme,bibliography,availability}) != 3:
        raise ValueError('Writeback targets must be distinct')
    if Path(bibliography).name.casefold() == 'zotero.bib':
        raise ValueError('Zotero-managed bibliography is never edited')
    receipt, records = published_records(raw, expected_digest, repository_id)
    originals = {p:original(repo,p) for p in (readme,bibliography,availability)}
    outputs = dict(originals)
    for key, record in sorted(records.items()):
        concept = record['concept_doi']
        badge = f'[{key}: ![DOI](https://zenodo.org/badge/DOI/{concept}.svg)](https://doi.org/{concept})'
        outputs[readme] = managed_block(outputs[readme],key,badge,markdown=True)
        citation = 'artifact-' + key
        authors = ' and '.join(tex(name) for name in record.get('creators', []))
        fields = {'title':tex(record.get('title', 'Research artifact ('+key+')')),
                  'doi':record['version_doi'],'url':record['record_url'],
                  'note':tex('Source commit '+receipt['source_sha'])}
        if authors:
            fields['author'] = authors
        if record.get('version'):
            fields['version'] = tex(record['version'])
        if re.match(r'^\d{4}-',record.get('publication_date','')):
            fields['year'] = record['publication_date'][:4]
        bib = '@misc{'+citation+',\n'+',\n'.join('  '+k+' = {'+v+'}' for k,v in fields.items())+'\n}'
        outputs[bibliography] = managed_block(outputs[bibliography],key,bib)
        sentence = "The " + tex(key) + " artifact is archived at " + r"\url{https://doi.org/" + record["version_doi"] + r"}~\cite{" + citation + "}."
        outputs[availability] = managed_block(outputs[availability],key,sentence)
    patch = ''
    changes = []
    for path in sorted(outputs):
        if outputs[path] == originals[path]:
            continue
        patch += ''.join(difflib.unified_diff(originals[path].splitlines(keepends=True),outputs[path].splitlines(keepends=True),
                                             fromfile='a/'+path,tofile='b/'+path))
        changes.append({'path':path,'before_sha256':digest(originals[path].encode()),'after_sha256':digest(outputs[path].encode())})
    evidence = {'schema':'doi-writeback/v1','publication_receipt_sha256':expected_digest,
                'source_sha':receipt['source_sha'],'repository_id':repository_id,'changes':changes,
                'note':'Review this patch. No repository files, Git tags or Zotero entries were changed.'}
    return patch, evidence


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--expected-receipt-sha256',required=True)
    parser.add_argument('--repository-id',type=int,required=True)
    parser.add_argument('--readme',default='README.md')
    parser.add_argument('--bibliography',default='paper/bib/references.bib')
    parser.add_argument('--availability',default='paper/content/artifact-availability.tex')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    patch,evidence=proposal(args.repo,args.receipt.read_bytes(),args.expected_receipt_sha256,args.repository_id,
                            args.readme,args.bibliography,args.availability)
    args.out.mkdir(parents=True,exist_ok=False)
    (args.out/'writeback.patch').write_text(patch)
    (args.out/'writeback.json').write_bytes(encode(evidence))


if __name__=='__main__':
    main()
